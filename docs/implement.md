# CountGD → TPC-268 实现记录

更新：2026-10-25。实现/数据协议基线：`0c99a25`，当前main代码HEAD为`92edcb72b986181bdd7c68ca7d74689d77b45466`；原数据协议和三图代码排除保持。本文描述本仓库**实际**实现；训练顺序、命令及实测结果记录在 [experiment.md](experiment.md)。以后每次修改代码、配置或数据协议，同步更新这两个文件。

## 与原 CountGD 的边界

| 模块 | 原 CountGD | 当前 TPC-268 实现 |
|---|---|---|
| 数据与标签 | FSC/COCO/ODVG 的框和计数任务；已有 exemplar 变换 | 新增官方 TPC-268 点标注适配与七级分类 registry；2 px 伪框只承载点中心，匹配和 L1 只监督中心，GIoU 代价/权重为 0 |
| 增强 | 随机 flip、两路 resize，其中一路 random crop；batch 按最少 exemplar 数统一 shot | 沿用原策略；同步变换点，裁掉的点不再计入训练 GT；评估固定 resize、原图数量和三个 exemplar |
| 主模型 | Swin、BERT、Feature Enhancer、Decoder、900 queries、匹配器、预测头 | 结构及原检测/计数损失保持；训练时从最终 decoder `hs[-1]` 取与最终 logits/boxes 同序的 query，加两个小投影头和辅助损失 |
| 主文本 | 单目标 CountGD caption | `organ`、`species`、`full_taxonomy` 三种单目标 caption；taxonomy prefix 另行编码，仅训练辅助分支使用 |
| 计数评估 | 原仓库有其特定推理及后处理流程 | 新 `main.py --eval` 用固定 resize、整图阈值计数，输出逐图 count 与 MAE/RMSE/R²；目前没有 TPC-268 adaptive crop、SAM 或 exemplar correction |

最终 query 读取图像、caption 和 exemplars，属于**条件表征**。辅助损失或锥指标改善不能直接证明纯视觉分类能力；计数改善必须看配对的验证/测试 MAE、RMSE。

## 官方数据适配与三张排除图

`datasets/tpc268.py` 读官方 txt（将 `\` 统一为 `/`），用图像 basename 查逐图 annotation，缺失即报错。与官方 split JSON 逐个交叉核对 species-organ 单元，审计拒绝不同 split 的图像路径重叠。`datasets/tpc268_taxonomy.py` 用官方七级 IDs/向量建 registry，节点身份为 `(rank, official_id)`；可读公开分类表，但训练候选、边、单位和负节点只来自有效 train split。当前显式 alias 仅 `Acacia_tortilis → Vachellia tortilis`，附 Kew 证据；其余名称不模糊猜测。

官方原文件仍有 train/val/test 7000/1000/2000 张和 269 个 species-organ 单元。配置 `tpc268_excluded_paths` 在加载时统一排除：

- train：`Malus_domestica/fruit/Malus_domestica_fruit_1.jpg`、`Musa_sapientum/fruit/Musa_sapientum_fruit_45.jpg`；
- val：`Punica_granatum/fruit/Punica_granatum_fruit_17.jpg`；test 没有排除项。

有效计数为 **6998/999/2000**；原 annotation 与 split 文件不被修改。三张排除图不进入训练、评估和 train-only registry。`tpc268_coordinate_policy=strict_points_clip_exemplars_v1`：全部原点坐标必须有限且位于原图内，越界即报错；三个四角 exemplar 转像素 xyxy 后与图像边界取交集，交集必须有正面积，审计记录原框与裁剪框。2026-10-14 本地全量审计中 train 有 91 张、val 有 1 张需裁剪 exemplar，test 0 张；剩余图像的坐标错误为 0，路径缺失为 0。这与训练的**随机 crop**不同：这里先修正原图边界的 exemplar ROI，不删除任何有效点。

点以变换后的归一化 xy 保存；2 px 原图伪框随 resize 缩放，crop membership 由点中心是否处于 `[0,w)×[0,h)` 决定，避免夹断伪框后移动目标中心。三个原始 exemplar 缺失或非法时报错；训练 crop 后可剩 0–3 个，移除无面积的 exemplar，engine 在一个 batch 内取共同的最少 shot 数。空目标保留单目标 caption 与 `[0]` 的 `labels_uncropped`。`count` 为增强后的点数，`orig_count` 为原图点数；整图评估使用后者。

当前 registry 指纹：`cf080ec256b9f9595a0cd6110b30d80fa84da0d49799217054e682185d79d65d`。有效图像中的已解析数为 train **6545/6998**、val **943/999**、test **1895/2000**；仍有 22 个原始 species 名称未确认。未解析图像保留计数训练/评估，跳过无效层级辅助目标；full-taxonomy caption 对它们退回 species 文本。官方 train 中仍有 64 张原始 count>900，最大 1462；val/test 最大 833/709。固定 900 query 不改写 GT 数量。

## 文本与辅助模型

`groundingdino.py` 的 exemplar 插入改为去 padding → 插入 → 重新 padding，并重建正确的 2D attention mask；检查 caption 加 exemplar 后的总长，不能静默截断 species/organ。三个主 caption 例子：`fruit .`、`fruit of Abutilon indicum .`、`fruit of Abutilon indicum; taxonomy: ... .`。每张图只有一个待计数类别。

`taxonomy_aux.py` 在 model 内注册 query/text 两个 `Linear → GELU → Linear` 投影头，输出 128 维；输入分别取 `model.hidden_dim` 与 `feat_map.out_features`。最终 decoder query 是 `[B,Q,C]`，与最终 logits/boxes 同序，DN 当前为 0，新增形状断言。不 detach query，不改 Backbone、Feature Enhancer、Decoder、预测头或 top-k。辅助七级 prefix 和 species-organ 文本复用原 tokenizer、`BertModelWarper` 与共享 `feat_map`，排除 padding/特殊 token 后 mean pooling；每 step 去重并每块编码 32 条，无跨 step hidden state 缓存、无新 BERT/CLIP。默认冻结 `backbone.0` 和 `bert`，共享 `feat_map` 仍可收到辅助文本梯度。

## 辅助损失与几何

`taxonomy_losses.py` 在最终 Hungarian 匹配后选出对应 query/GT 路径，只将三项新损失加在最终层，不复制到 decoder 辅助层或 encoder。`loss_level_contrast` 是同 rank 的 I↔T cosine 对比：去重正节点，每层至多补 16 个 train 负节点；匹配 GT query 每图至多随机选 64 个作为辅助监督，这不删原 GT，也不改变计数损失。

`loss_entail_tt` 把文本相邻正确父子放进锥，并用错误上一层父节点的负蕴涵排除错误分支；每 child 至多 16 个错误父节点，排除真实祖先，优先正确父节点的兄弟。负损失 `relu(aperture(wrong_parent)-angle(wrong_parent,child)+0.1)`，每 child 再每层平均。另有 species→species-organ 的**计数任务 bridge**，不是第八级生物分类。`loss_entail_tv` 只让正确计数单元包含匹配 query；错误父节点与 query 的包含率有 detached 诊断，**没有 TV 负蕴涵损失**。未匹配 query、未解析路径不加辅助监督。

`lorentz.py` 使用双曲 Lorentz 锥，并提供欧氏锥对照；曲率默认固定 `c=1`，几何计算用 float32。径向映射先加入合法域余量：Lorentz `r=asinh(2K(1+0.05))/sqrt(c)+||αu||`、欧氏 `r=K(1+0.05)+||αu||`，再限制上界；非法 parent 显式报错。零/极小方向使用确定性坐标轴。日志按层记录正确/错误父锥包含率、margin 违例、pair 数、半径、非法域和饱和率；pair=0 的零率没有证据意义。正式总损失为原 CountGD loss `+0.1 contrast+0.05 TT+0.05 TV`，辅助权重在第一 epoch 按 step warmup，默认不是经调优的最优值。

## 训练、检查点和推理协议

创建辅助头和冻结既有层发生在 DDP/optimizer 之前；运行时检查每个 trainable parameter 恰好进入 optimizer 一次。空匹配/缺分类时辅助参数通过图连接零参与。DDP 的动态分支启用 `find_unused_parameters`，checkpoint 路径使用 `use_reentrant=False`。`util/checkpoint.py` 保存训练协议，恢复时核对 taxonomy fingerprint、prompt、坐标策略、三张排除图、增强、分支/损失配置等；不同协议不能接续 optimizer，旧 checkpoint 不作相同实验的续训。

TPC 评估按 CountGD sigmoid max-token 置信度和 text threshold 判断每个 query，默认阈值 `0.23/0`；固定 800 短边/1333 长边，使用三个 exemplar，整图计数。结果写 `{split}_counts.json` 与 `{split}_metrics.json`，比较工具按逐图 GT/预测重算 MAE/RMSE，要求同 split、同主 caption、同数据与训练/推理协议的配对 baseline。评估不编码辅助 taxonomy 文本。原仓库的 adaptive crop 由**预测数量**是否达到 query 上限触发，不能因 GT<900 就判定永远不会触发；当前 TPC 推理入口尚未接入它或 SAM/exemplar correction。

`pyproject.toml`/`uv.lock` 已配置 uv 的 `[[tool.uv.index]]` 与 PyTorch CUDA 13 wheel 来源；CUDA 扩展已移除旧 THC 头、旧 Tensor `.type()` 分派和 `.data<T>()` 接口。macOS 本地只做 CPU/接口检查，Ubuntu 上须编译并检查实际 CUDA 运行。项目不下载标注、图像或权重；它们分别由本地 `data/TPC-268/`、`data/tpc268_metadata/annotations|splits/` 和 `checkpoints/` 提供，Git 忽略大型资产。

## 已有验证与更新规则

2026-10-12 的本地真实权重 CPU smoke：organ caption 为 `fruit .`，900 query，某样本随机 crop 后 47→38 点、剩 2 个 exemplar；query、`feat_map` 与 Decoder 梯度通路有效。这是**单样本检查**，不等于正式计数结果。数据/几何/比较工具的模块内 smoke 已通过；2026-10-14 又对当前 `0c99a25` 做全量图片/坐标/离线 tokenizer 审计，三个 split 无缺图/坐标错误，主 caption 最长 token（含 exemplar）分别为 organ 8、species 17、full taxonomy 59，taxonomy prefix 最长 48。2026-10-15已读取服务器真实日志与结果：R01/R03训练及best-val/test评估已完成；R02/R04/R05正在运行。最新快照和判定边界见 [experiment.md](experiment.md)。

以后每次仓库工作都检查并更新本文件与 `experiment.md`。实现变化写清“原行为→当前行为→对实验协议的影响”；没有实现变化时记录日期及“实现协议未变”。

## 2026-10-15 R03 测试评估记录

本次实现、模型、损失与数据协议未变。按用户明确要求，使用验证集选定的 R03 第12轮 best checkpoint，在 GPU3 执行2000张 test 全量整图评估；沿用 species+organ caption、三张统一排除名单（test无排除项）和阈值0.23/0。仅增加 runs 下的评估脚本及产物，不按 test 修改模型/阈值。实测结果在 experiment.md 同步记录。

R03 test 本次实测已完成（2026-10-15）：2000张，MAE=12.5750、RMSE=37.7194、R2=0.782445；逐图结果重算和完整性检查通过。评估沿用既有实现，无模型/损失/数据/推理代码修改；详细命令、时间、权重指纹与结果路径已同步至 experiment.md。

## 2026-10-15 R04 启动准备

实现协议未变。本次复用既有 cfg_tpc268_species_full.py，为原计划R04准备GPU3后台脚本：species+organ主caption，完整层级对比与Lorentz TT/TV，从原FSC147权重独立初始化，匹配R03的冻结/预算/增强/数据排除协议。仅准备脚本，未开始训练；命令与状态在experiment.md同步记录。

## 2026-10-15 R01 test与R05准备

本次实现协议未变：R01按用户要求用val选出的best权重在GPU0评估2000张test，主文本full-taxonomy、3 exemplars、整图阈值0.23/0。已准备原计划R05 organ-only baseline的GPU0后台脚本，从原FSC147初始化，匹配既有冻结/增强/数据排除/30epoch预算；R05未启动。任务状态与实测结果同步至experiment.md。

R01测试评估已完成（2026-10-15）：采用val选定的第2轮best权重，test2000张，MAE=12.6490、RMSE=36.6432、R2=0.794682。完整性与逐图指标独立重算检查通过；实现协议未变，详细命令/时间/产物与R05待启动状态已同步至experiment.md。

## 2026-10-15 实验计划调整：先诊断负结果

本次实现协议未变，仅更新实验优先级与执行记录。已启动R02/R04/R05保持原代码、配置、30轮预算、原始初始化、loss系数、冻结、增强、数据排除及推理协议，不改进程或启动脚本。

当前R02 seed42/full-taxonomy组合的最佳val MAE=10.6867，高于同协议R01基线的10.0030，计数表现退化；不能据此拆分归因contrast或Lorentz无效。R04仅完成1轮、R05尚无完整epoch结果，不能提前下结论。

后续先以既有cfg_tpc268_contrast.py和cfg_tpc268_entailment.py进行独立短程，再各30轮、seed42、同full-taxonomy基线的单项诊断；R06/R09、多seed、bridge及真正纯视觉基线转为满足条件后执行。未新增loss、模型、配置或可执行训练代码；本次不启动新实验。R09只隔离full目标下几何，不能替代entailment-only目标的匹配Euclidean对照。

R01/R03 test已经用户授权提前查看，后续方案选择只基于val；不使用test做权重/阈值/seed搜索。有限负结果、候选收益、跨seed主张的区分及完整命令见experiment.md。旧文档备份存runs/tpc268_v3_exclude3/planning/，docs仍恰好两份。

## 2026-10-16 R07 GPU2启动脚本

实现协议未变：复用现有cfg_tpc268_contrast.py，仅层级对比训练，关闭TT/TV，与R01同full-taxonomy、原FSC147初始化和30轮预算配对。新增runs目录下run_r07.sh启动编排，固定物理GPU2，自动执行该分支约15步短程与999张val完整性/有限值检查，通过后执行独立正式训练及best-val重评；短程与正式输出分离，脚本带防重复锁和状态记录，不自动test。只准备命令，未启动；现有代码/配置/训练进程未变。R02已实测正常完成，数据及性能记录同步至experiment.md。

## 2026-10-16 R02测试评估

按用户要求准备GPU1评估R02第3轮best-val权重，沿用full-taxonomy、Lorentz完整辅助方案的checkpoint，eval不编码辅助文本；2000张test、逐图batch1、3exemplars、阈值0.23/0、原整图推理。仅增加runs下评估脚本，实际结果待运行后写experiment.md。已有transformer.py autocast API兼容替换经检查保持禁用混合精度的语义，本次不修改该文件，保存执行差异以供复核。

R02测试已完成（2026-10-16）：GPU1、val选定第3轮best权重，test2000张，MAE=12.3755、RMSE=37.9426、R2=0.779863；峰值显存1584MiB。逐图指标/完整性及与R01的配对协议核对通过。相对R01为MAE降低、RMSE升高的单seed取舍，不据test调整实现或后续计划。详细实测、差异快照及结果路径已同步至experiment.md；本次未修改模型/数据/阈值。

## 2026-10-16 阶段实验报告整理

本次实现协议未变，没有修改训练代码、配置、进程、权重或原始数据。experiment.md已整理为持续更新的实验报告，新增模型修改边界、主caption与独立辅助文本的真实模板、R01–R09设置矩阵、实测状态、best checkpoint轮次、同权重val/test三指标、配对分析与更新流程。

快照约11:00：R01/R02/R03完成训练及best-val/test；R04/R05完成14/15轮，best分别第11/12轮；R07通过短程检查并处于第1轮正式训练，尚无正式验证成绩。已直接核对R01–R05 best checkpoint元数据；三组已完成实验的六份val/test JSON均重算通过。

主caption代码实际使用`organ of species; taxonomy: ... .`、`organ of species .`、`organ .`；独立辅助prefix为`A biological taxon classified as ... .`，计数单位文本为`organ belonging to species.`。辅助投影头为256→256→128，主CountGD结构/900queries/预测头不替换。organ-only仍不是纯视觉。

启动console核验显示R01–R03训练HEAD为9df0651且dirty，R04/R05/R07为8a26e86且dirty；保存配置/checkpoint都含当前exclude3和坐标协议，不能按HEAD误判为旧数据协议。当前transformer.py的autocast API兼容改动保留；源码完整不可变归档不足的限制已披露。报告snapshot/曲线/整理前文档均保存在runs/planning，docs保持恰好两份。后续每次实验更新同一状态与结果表，保留阶段性与最终重评的区分，不暗示已经部署自动刷新任务。

## 2026-10-16 R04/R05/R07当前best快照并行测试

按用户明确要求，在GPU3/0/2分别后台评估R04/R05/R07截至15:39的best权重，第11/12/1轮。每项先复制固定checkpoint、验证epoch与正式val日志、保存SHA256和工作区代码diff，再使用既有main.py --eval --eval_split test；三项均于15:40:32启动。输出为各run下test_snapshot_20261016_153930，不能把仍会刷新的训练best路径视为已评估的不可变权重。实现、模型、损失、caption、数据排除与整图推理协议未改，现有训练照常运行；仅新增runs下评估编排与产物，CPU线程数设为2控制并行资源占用。结果待实际2000图完成后更新experiment.md；阶段性test不用于调整后续参数。

三项test于15:50:52/15:51:14/15:52:43完成，退出码均为0。实际2000图结果：R04 MAE=13.6800、RMSE=36.0976、R²=0.800751；R05 MAE=10.5470、RMSE=29.8706、R²=0.863565；R07 MAE=13.3415、RMSE=36.7346、R²=0.793657。15:53核验各自官方test图集/GT、逐图指标重算和快照SHA256通过，核验JSON及同caption配对比较保存在runs/planning/verified_test_snapshot_20261016_153930.json，experiment.md已同步更新。方法仍只完成部分训练预算，配对baseline已完成30轮，不能将这些test快照当作最终同预算方法结论；不因结果修改已有训练或后续参数。GPU测试进程已释放显存，原三个训练进程仍在运行。

## 2026-10-17 训练完成状态与论文复现协议核验

实现、配置、原始数据和已启动训练均未修改。R04/R05分别于07:13:21/01:50:16成功完成30轮及best-val重评（退出码0），best仍为第11/12轮，val三指标未刷新。读取最终checkpoint核对epoch/best_val_mae，最终best文件SHA256与10月16日已测test快照一致，所以已有test仍对应最终选定权重，无需重复推理。R07约11:26完成21轮，正在第22轮，best已更新为第16轮，val MAE=11.0701/RMSE=36.0906/R²=0.8863；旧第1轮test不能冒充当前best。状态/完整epoch日志与SHA核验见runs/tpc268_v3_exclude3/planning/report_snapshot_20261017.json，experiment.md已同步。

按用户最新目标，P01论文Table 4全分类文本基线复现优先于尚未启动的R08/R06/R09，R07保持原预算。论文§4.5只明确“retrain CountGD”和纯七级名称逗号文本，未说明初始化来自CountGD-FSC147还是GroundingDINO；本地FSC147微调是既有选择，不是已确认的论文配方。作者点监督转换、训练参数、推理后处理、三图异常和未解析taxonomy处理均未知，不能将原CountGD默认值或本地适配填成作者设置。公开通用Dataset只返回点与exemplar框；已保存官方README/Dataset和来源hash，当前官方HEAD仍与本地metadata来源a382e850一致。7份标注/split hash核验通过。

P01审计及未发送的作者问题草稿在runs/tpc268_paper_reproduction_20261017。用户确认没有额外作者代码/权重，目前尚未找到公开CountGD专用配置/checkpoint；P01为WAITING_AUTHOR_PROTOCOL，未启动猜测配置的新训练。三张排除图继续在代码层排除，原数据不变；公开原split与当前exclude3不同，taxonomy未解析回退也使当前R01不能视为论文全分类文本逐项复现。需要公开信息重建时必须另列假设/协议/匹配baseline。GPU宿主机index仅0–3，当前空闲0和3，没有index4；本次没有占用空闲卡或改变训练进程。

## 2026-10-17 R08层级蕴涵启动脚本

用户随后明确要求先提供原计划仅层级蕴涵R08的启动命令，本次准备runs/tpc268_v3_exclude3/run_r08.sh，固定GPU0；准备时GPU0剩余24124MiB，启动会复查至少20000MiB。R08复用既有cfg_tpc268_entailment.py，不修改模型/损失实现或数据协议：关闭contrast，仅Lorentz TT/TV，各权重0.05，TT保留既有unit bridge；同R01的full-taxonomy主文本、原FSC147初始化、batch4/seed42/30轮、冻结及三图排除。

脚本在独立短程约15步与999图val通过后，从原初始化独立开始正式30轮训练并重评best-val，短程权重不用于正式训练；检查loss有限、TT/TV存在、contrast关闭及锥合法域。锁、状态、阶段、退出码和日志保留，后台独立session不受SSH断开影响，不自动test。bash语法、内嵌Python语法、有效继承配置及预检日志字段均核对通过。仅准备命令，真实GPU短程尚未执行，R08记录为READY，不能记为RUNNING或预检已通过；experiment.md同步给出唯一推荐后台命令。R07继续运行，P01作者配方缺项继续保留，R06/R09未启动。


## 2026-10-17 物种名称异名核验表（未启用）

按用户要求逐项核实当前22个未解析目录物种名，优先使用Kew POWO、IPNI、Index Fungorum、Flora of North America、分类研究者的Waterloo Astereae Lab及台湾植物/生物多样性数据库。结果为**13项已证实可关联到TPC官方表键，9项仍不能安全关联**。这里核实的是文献/数据库中的名称关系，不是对照片逐张进行植物学重新鉴定。查无结果不等于名称绝不存在，未把目录顺序、种加词相似或未使用表项的数量当作异名证据。

机器审计表：[tpc268_species_alias_audit_20261017.json](../config/tpc268_species_alias_audit_20261017.json)；待启用的已核实名称表：[tpc268_species_aliases_verified_20261017.json](../config/tpc268_species_aliases_verified_20261017.json)；便于筛选的导出：[species_alias_audit.csv](../runs/tpc268_taxonomy_audit_20261017/species_alias_audit.csv)。待启用表含13个新映射及原已启用的Acacia_tortilis映射，共14项，兼容现有registry读取格式，但**没有被任何现有配置引用**。正式标注、split、现有data/tpc268_metadata/species_aliases.json及原始图像均未修改。

“目标”固定指TPC分类向量文件中的精确键，**不保证是当前权威数据库采用的接受名**。Drynaria、Gelasia、Myrica、Tibetiodes等条目在当前权威资料中的接受名反而是目录名；映射到官方表中的旧组合仅为关联既有七级ID，不将POWO的门/纲体系覆盖官方分类链。Pentanema属于有记录的拼写修订；真菌组合以Index Fungorum同一基名/当前名核对。详细作者名、同物关系、完整官方七级ID/名称及逐split图像数在机器审计表内。

| 原目录物种名 | 核验结论 / TPC目标键 | 证据 | 说明 |
|---|---|---|---|
| Achyranthes_affinis | 未确认，不映射 | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:77203312-1) | 未找到可把目录原名可靠关联到Achyranthes aspera的异名证据。Achyranthemum affine是另一个属的正式名称，仅作为疑似误写线索，不能据此重命名或推断图像身份。 |
| Achyranthes_argentea | 存在冲突或缺目标，不映射 | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:85324-3)、[来源2](https://powo.science.kew.org/taxon/326791-2) | POWO分别有Lam.与Thwaites同名记录，均指向Achyranthes sicula；不能证实与官方键Psilotrichum argenteum同物。目录不带作者，保持未解析。 |
| Achyranthes_mucronata | 存在冲突或缺目标，不映射 | [来源1](https://powo.science.kew.org/taxon/58817-1)、[来源2](https://www.ipni.org/n/58817-1) | 查到的Lam.记录为Alternanthera pungens异名，没有Cyathula mucronata对应证据。也存在名称相近的菊科Achyranthemum mucronatum，不能据此推断原图。 |
| Achyranthes_recurvata | 未确认，不映射 | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:77203310-1) | 未找到与Psilotrichum recurvatum的可靠异名关联。菊科Achyranthemum recurvatum是独立的正式名称，仅列为作者核实线索。 |
| Achyranthes_sordescens | 未确认，不映射 | [来源1](https://pza.sanbi.org/achyranthemum-sordescens) | SANBI记录的是菊科Achyranthemum sordescens/Syncarpha sordescens；无法证明目录Achyranthes sordescens所指。不能因为Banksia ashbyi是剩余表项就强行配对。 |
| Achyranthes_stricta | 未确认，不映射 | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:1158-1) | 未找到Achyranthes stricta到Centrostachys stricta的权威关系。POWO的Centrostachys属页面仅列接受种C. aquatica，但这本身不证明候选异名绝不存在。 |
| Agrocybe_aegerita | 已核实 → Cyclocybe aegerita | [来源1](https://www.indexfungorum.org/names/namesrecord.asp?RecordID=114787)、[来源2](https://www.indexfungorum.org/names/NamesRecord.asp?RecordID=550610) | 两条Index Fungorum记录共享基名Agaricus aegerita V.Brig.；当前均链接Cyclocybe cylindracea。此映射保留TPC官方键Cyclocybe aegerita，不将其误称当前数据库接受名。 |
| Arenaria_paludicola | 已核实 → Minuartia paludicola | [来源1](https://www.efloras.org/florataxon.aspx?flora_id=1&taxon_id=250060022) | Flora of North America的Arenaria paludicola条目明确列出Minuartia paludicola (B.L.Rob.) House。使用TPC表键，不替换其上级分类。 |
| Doellingeria_breweri | 已核实 → Eucephalus breweri | [来源1](https://uwaterloo.ca/astereae-lab/research/asters/eucephalus/doellingeria-eucephalus-breweri) | Waterloo分类研究者页面明确串联Doellingeria breweri、Aster breweri与Eucephalus breweri。不同数据库版本采用的属名可不同，映射目标固定为TPC键。 |
| Doellingeria_engelmannii | 已核实 → Eucephalus engelmannii | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:97873-2)、[来源2](https://uwaterloo.ca/astereae-lab/research/asters/eucephalus/doellingeria-eucephalus-engelmannii) | POWO在Eucephalus engelmannii同型异名列表中列Doellingeria engelmannii；Waterloo另说明属转移历史。 |
| Doellingeria_ledophylla | 已核实 → Eucephalus ledophyllus | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:97882-2) | POWO接受种Eucephalus ledophyllus明确列Doellingeria ledophylla为同型异名，词尾差异来自组合中的性别一致。 |
| Drynaria_roosii | 已核实 → Aglaomorpha fortunei | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:77163105-1) | 当前POWO把Aglaomorpha fortunei列为Drynaria roosii异名。映射方向为原目录名到TPC表键，与当前接受名方向相反但关系明确。 |
| Gelasia_filifolia | 已核实 → Scorzonera filifolia | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:77204026-1) | POWO接受Gelasia filifolia，其同型异名为Scorzonera filifolia Boiss.；使用TPC的旧组合键。 |
| Lansium_parasiticum | 存在冲突或缺目标，不映射 | [来源1](https://powo.science.kew.org/taxon/578885-1)、[来源2](https://repository.naturalis.nl/document/566264) | Lansium parasiticum (Osbeck) K.C.Sahni & Bennet在POWO归入Epicharis parasitica，但该名不在TPC表中，也未证实Aglaia parasitica为等价组合。另有历史文献指出L. parasiticum曾误用于L. domesticum；目录无作者/来源，不能用该记录确认照片身份。 |
| Mentha_haplocalyx | 已核实 → Mentha canadensis | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:157356-2) | POWO的Mentha haplocalyx Briq.条目明确指向Mentha canadensis。 |
| Mitella_formosana | 已核实 → Asimitellaria formosana | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:77217833-1)、[来源2](https://www.worldfloraonline.org/taxon/wfo-1000025544) | POWO接受Asimitellaria formosana，并列Mitella formosana (Hayata) Masam.为同型异名。 |
| Musa_sapientum | 已核实 → Musa × paradisiaca | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:797606-1) | 目录省略杂交符号；当前规范化已允许此差异。POWO的Musa × sapientum L.明确指向Musa × paradisiaca；此为名称关系，不是对每张照片栽培品种的重新鉴定。 |
| Myrica_pensylvanica | 已核实 → Morella pensylvanica | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:1001459-2) | 当前POWO接受Myrica pensylvanica，Morella pensylvanica为其异名；映射到TPC的Morella键，不声称它是当前POWO接受名。 |
| Nubelaria_arisanensis | 存在冲突或缺目标，不映射 | [来源1](https://tai2.ntu.edu.tw/species/324%20012%2003%200)、[来源2](https://www.tbn.org.tw/taxa/0a70ae0b-3884-403d-82a9-116e774983ff) | 台湾植物与生物多样性资料将Nubelaria arisanensis关联Stellaria arisanensis，归石竹科。TPC候选Vaccinium arisanense的表内链为杜鹃花科，不能因种加词相似映射；正确链不能从现有候选键恢复。 |
| Pentanema_britannicum | 已核实 → Pentanema britannica | [来源1](https://www.ipni.org/n/77178407-1)、[来源2](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:77178407-1) | IPNI同一条目记录发表时写作britannicum，修订名称为britannica，并说明种加词为同位名词；这是有文献依据的拼写修订。 |
| Tibetiodes_flaccida | 已核实 → Aster flaccidus | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:181223-1)、[来源2](https://www.ipni.org/n/77218930-1) | POWO的Aster flaccidus明确指向Tibetiodes flaccida，IPNI的新组合也引用Aster flaccidus为基名。映射保留TPC旧组合。 |
| Wedelia_mexicana | 存在冲突或缺目标，不映射 | [来源1](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:267957-2)、[来源2](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:10406-1) | POWO接受Wedelia mexicana (Sch.Bip.) McVaugh，其异名列表未提供Pascalia mexicana。Pascalia属页面列出的接受种也无mexicana；没有足够依据使用官方候选键，不能据此断言该组合从未发表。 |

需要特别区分的未解决问题：

- Achyranthes的6项不能根据相近名称替换为Achyranthemum；后者若干名称确属菊科，但当前尚无证据确认目录名所指。Achyranthes argentea的作者同名问题及A. mucronata所查Lam.条目均不支持当前候选表项。Banksia ashbyi不能仅因是剩余项就配给A. sordescens。
- Nubelaria arisanensis的来源链为石竹科，与官方候选Vaccinium arisanense的杜鹃花科链不同，拒绝该配对。正确Nubelaria/Stellaria链不在现有官方向量键中。
- Lansium parasiticum的所查作者组合指向Epicharis parasitica，不能据此映射Aglaia parasitica；历史误用及目录缺作者使图像所指仍需确认。
- Wedelia mexicana已找到接受种记录，但未证实Pascalia mexicana对应关系；Pascalia属接受种清单没有该键不能单独作为“该名从未存在”的证明。

仅离线试读新表的覆盖率，不是训练或评估成绩：train由6545/6998变为6878/6998（新增333，剩120未解析），val由943/999变为999/999（新增56），test由1895/2000变为1919/2000（新增24，剩81）。合计新解析413张，9个名称仍未解析。当前运行配置和实验仍为原覆盖率/原指纹cf080ec256b9f9595a0cd6110b30d80fa84da0d49799217054e682185d79d65d。

若将来启用，候选表产生的新registry指纹为e72c02067bd416b61ada53630629df9386294d98be9bed3a57279ccf17a6e2d0；它会改变主caption、train候选节点/边和辅助监督，必须另开协议、匹配baseline并独立初始化，不能把旧checkpoint直接续训后称同一实验。本次没有启用新表、修改训练代码或重跑任何实验。已核对全部13个新目标存在完整官方七级ID、22项审计覆盖完整且不重复、9项未确认名称不进入候选表、旧alias内容和旧registry指纹不变。


## 2026-10-17 P01 独立原始 mask 复现准备

用户选择 GroundingDINO Swin-B 初始化，并指定只使用官方直接名称对应的完整分类链，缺失则仅 species；不使用自行匹配/异名表。已从 b6f362b3f5cd20db4a171faa410dfed8f2f466d8 建分支 repro/tpc268-b6f362b-original-mask，工作树 runs/tpc268_paper_reproduction_20261017/worktree；本 main 的模型与现有运行不因这次工作修改。新增入口/数据适配/脚本在该工作树，其两个 docs 记录完整实现和协议。

该分支保持 models/、groundingdino/、engine.py、原 FSC147 配置逐字节等于 b6，并在入口核对哈希；原插入后含 padding 的全部 True mask 特意保留。TPC 适配只同步点坐标与裁剪归属，不修改模型/匹配/损失，b6 原本就采用中心匹配、中心 L1 与零 GIoU。独立 uv/Python3.9.19/torch2.2.1/transformers4.39.1 环境，CUDA 算子独立编译，当前准备中。

P01 的官方名称查找仅将目录下划线转空格后精确查表，不加载此前 Acacia 或13项已核验异名，不删除 ×。全链文本为七级实际名称逗号连接并以句号结束，无 organ 和 taxonomy:；缺失则 Species.。有效 train/val/test=6998/999/2000，完整链6258/943/1895，回退740/56/105；三张异常图仍仅代码排除。原数据与标注不修改。此新规则不回写 R01–R08。

用户选的初始化权重已从官方 GroundingDINO release 下载，SHA256=46270f7a822e6906b655b729c90613e48929d0f2bb8b9b76fd10a856f3ac6ab7；不使用 FSC147 权重。原版未启用的 feature_map_encoder 也保留，初始化缺失键须显式审计。评估沿用原 batch4，整图800/max1333、阈值.23/0，无 crop/SAM/校正；作者具体初始化及训练/后处理未公开，不能据此宣称完全对齐论文。后续若比较 mask/初始化收益须建立同协议匹配基线。检查和正式状态待实测产物更新。

2026-10-17 P01检查补记：现有环境完成全有效划分坐标和分词审计，最大46 tokens（含3个exemplar）；53份b6原核心文件逐字节相同，8组点增强检查通过。独立旧版环境/GPU检查待完成；没有训练性能记录。GroundingDINO初始化的label_enc.weight在b6 CountGD中不存在（dn_number=0），只允许这一明确的多余项，逐键加载报告保留。

2026-10-17 初始化兼容补记：官方旧权重还序列化了bert.embeddings.position_ids（1×512固定arange）；固定版Transformers将其作为非持久buffer自动生成。入口验证其内容后允许忽略；并非丢弃可学习的BERT参数。除label_enc.weight和这一固定buffer外，其余unexpected键均阻止训练。

2026-10-17 独立环境更新：uv已安装原requirements固定依赖，完整67项解析版本存requirements-reproduction.lock。Python3.9.19、torch2.2.1+cu121、torchvision0.17.1+cu121、transformers4.39.1；以CUDA Toolkit12.6、gcc/g++11、TORCH_CUDA_ARCH_LIST=8.6、MAX_JOBS=4用uv pip --no-build-isolation --no-deps编译原版ops并安装成功（ops_build.log）。固定环境也已完成全有效数据坐标/分词审计。后台入口显式uv run --offline --no-project --python指定该.venv解释器，避免继承main的Python版本选择。CUDA算子数值检查和短程训练仍待完成，正式指标未知。

2026-10-17 CUDA数值校验已完成：原版ops/test.py的float/double前向对照和D=30/32/64/71四组数值梯度检查全部True（6/6），日志为复现实验根目录ops_check.log。下一阶段为原mask检查、初始化逐键核对及短程训练；正式训练未启动、正式指标未知。

2026-10-17 12:13运行更新：复现代码已固定为492688c13a25e7bfa9566124ebebab7b99eae627，后台pipeline PID4079418，GPU3；阶段PREFLIGHT。初始化实际加载1106个GroundingDINO张量，缺失仅CountGD新增模块，额外仅已审查的label_enc与固定位置buffer。长短caption原mask运行检查通过，插入后padding仍保留且mask全True；已看到首个真实训练批次有限loss。15批+999张val完整检查尚在运行，正式30轮未开始，正式性能未知。

2026-10-17 12:17最终运行更新：P01已在GPU3正式后台训练，pipeline PID4079418，stage=TRAINING 2026-10-17T12:17:29+08:00，代码提交492688c13a25e7bfa9566124ebebab7b99eae627。原版环境/全量数据审计、6项CUDA数值检查、原all-True mask检查、GroundingDINO逐键加载及15批训练+999张val均通过，audit/preflight/train指纹一致（fb63d9616f2f98f85ea17eb75352405d1fb048d4e75334c7b8d6d7acca1e84e8）。正式训练独立重置seed42并重新加载官方GroundingDINO，没有使用短程checkpoint。epoch从0起，目前正式val最佳轮次和val/test性能仍未知，尚无完整正式训练轮次。

短程产物仅供技术验证：preflight/val_metrics.json记录15个训练批次后val n=999、MAE=34.845845845845844、RMSE=58.18040872974304、R²=0.7044194824592861；这不是30轮正式实验成绩或最终模型，不进入正式对照表。训练将完成30轮，以val MAE选best，再固定权重重评val和一次test。训练drop_last=True、评估drop_last=False沿用原规则；batch和顺序记录在协议中，原mask缺陷被保留。依赖锁、编译器、算子文件哈希见requirements-reproduction.lock、上级environment.json和ops_build/check日志。

现在已启动，勿重复执行nohup命令。监控：`tail -f runs/tpc268_paper_reproduction_20261017/train.console.log`（在主仓库根目录执行）；阶段：`cat runs/tpc268_paper_reproduction_20261017/stage`。此次仅创建独立复现工作树和新环境/权重，没有改动已启动R07/R08、主工作树原有模型修改、数据及标注。原始b6核心文件仍逐字节相同。作者未公开的训练细节仍未知，本次是明确假设下的复现，不据当前准备结果宣称复现论文性能。

2026-10-17 清理记录：按用户明确要求，仅删除P01 preflight/checkpoint.pth和preflight/checkpoint_best.pth两个预检权重，实际删除2个文件，共2500235378字节（约2.33GiB）。正式训练独立从GroundingDINO初始化，不读取这两个文件；正式train权重、审计JSON、检查日志、数据、标注和实验协议未变。


## 2026-10-17 R07完成核查与评估入口（核查：2026-10-17T22:18:34+08:00）

R07 status=DONE 2026-10-17T20:46:36+08:00、exitcode=0、正式日志30行；checkpoint epoch=15（第16轮），best_val_mae=11.07007007007007。最终999张best-val逐图重算MAE=11.07007007007007、RMSE=36.09060170642118、R²=0.8862607095040076，与日志和独立重评一致。相对同协议R01 val MAE增加1.0671，本seed此协议下contrast-only未改善val；旧test仅为第1轮快照。

R08完成8/30、正在第9轮，当前best第5轮，val MAE=11.35935935935936、RMSE=30.388080482903746、R²=0.91936403173151，尚未完成预算。P01仍在GPU3训练。R06要求R04或单项诊断有候选收益，当前尚无；R09要求R07/R08最终结果及蕴涵/组合潜力或明确几何检验目标，R08仍未完成。因此不释放新的30轮训练，下一步先补齐R07最终best的test，并等待R08/P01；不根据test选择后续训练。

已准备 `runs/tpc268_v3_exclude3/run_r07_test_final.sh`，shell及内嵌Python语法检查通过，READY、未启动。固定GPU2并要求至少4096MiB空闲，核对训练成功退出和第16轮权重身份，锁防重复，记录权重前后SHA256及代码diff。沿用原R07 caption、taxonomy、初始化来源、数据/整图推理协议、阈值.23/0、3 exemplars、实际eval batch1；CPU线程2/worker2仅控制评估资源。结果写contrast_seed42/test_final/，保留第1轮旧快照，结束核对完整2000张test与有限指标。当前test指标未知，没有修改已有训练、模型配置或数据。

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_v3_exclude3/run_r07_test_final.sh > runs/tpc268_v3_exclude3/contrast_seed42/test_final.console.log 2>&1 < /dev/null &
```

监控：`tail -f runs/tpc268_v3_exclude3/contrast_seed42/test_final.console.log`。本次仅提供命令，未启动新test/训练。核查快照：planning/next_step_20261017_r07_final.json。


2026-10-17 R07最终test启动脚本修复：用户SSH环境不包含编辑器扩展目录中的rg，原脚本以rg检查DONE导致错误地报告训练未完成。实际原训练status=DONE、exitcode=0，评估此前未启动，test_final/仅有锁文件。将检查改成Bash内置read和条件判断，避免rg依赖；提前注册退出处理，使后续启动检查失败也记录FAILED/exitcode。bash语法、两段内嵌Python语法及PATH=/usr/bin:/bin下的真实训练状态检查均通过。仅修复启动兼容性，不修改权重、caption、数据、推理阈值或实验协议；保留失败console日志，接下来重启原定GPU2评估，实际状态待启动日志核实。

2026-10-17 R07最终test修复后启动核实：RUNNING 2026-10-17T22:29:35+08:00，后台PID377476，GPU2，实际评估代码HEAD=6341592d13575f3626bc70f08604b96ab231f4ef（不是旧训练启动HEAD）。checkpoint_metadata.json已核对第16轮/val MAE11.07007007007007；console已输出TPC-268 test [130/2000]真实推理进度，无原rg错误。正式test性能仍未知、评估未完成；沿用原定权重和评估协议。无需用户重复启动，查看同一test_final.console.log即可。


## 2026-10-17 最终结果维护与实现边界



### 2026-10-17 最终test结果维护记录（2026-10-17T22:46:00+08:00）

R07最终test DONE、exitcode=0；第16轮权重SHA256=`37ae8b38f4b59b3789539e89d42b05f1aaaa586e031d0c618780f7308457fe04`与运行前记录及运行后检查一致。全部2000张路径唯一、集合等于官方test，每张GT等于原annotation点数；MAE/RMSE/R²独立重算一致。compare_tpc268_runs验证R01/R02/R07同caption、冻结、seed、初始化来源、30轮预算及训练/推理协议；R07实际eval代码提交6341592，与启动源码差异和溯源边界见第9节。本次只更新结果表、当前结论、分组诊断与曲线，不启动训练/测试或修改模型、数据、配置。R08/P01的best轮次已读checkpoint核对，训练状态依最近日志；实时GPU/进程查询因自动审批服务403未执行。历史启动与检查记录继续保留，均以当时的日期/状态理解，当前结论以第1–9节为准。

R07的contrast-only最终val/test均未改善同协议R01，退化集中于高计数与seed组；这是已测设置的负结果，不证明所有对比损失无效，也不能替代R08及欧氏几何对照来评价双曲建模。R02/R04组合仍有MAE与RMSE取舍，不能写成全面改善或统一失败机制。全部当前结果、分组表及证据链接见experiment.md第5–9节。此次实现/数据/训练/推理协议无实质修改，仅新增报告核验JSON和曲线，保持既有训练不变。


## 2026-10-17 下一项实验建议：P02 mask配对对照（PROPOSED；2026-10-17T22:52:43+08:00）

本节是针对用户“下一步应该进行什么实验”的建议，尚未实现或启动，不表示已获得性能或已释放旧R06/R09门槛。最新日志：R08完成9/30、正在第10轮，best第5轮val MAE11.35935935935936；P01完成10/30、正在第11轮，best第2轮val MAE10.933933933933934。当前已运行实验保持原设置完成。

若新增一项正式训练，优先P02：P01的配对CountGD基线，只将视觉exemplar插入改为去padding→插入→重新padding，并同步正确token/attention mask。其余沿用P01：同一官方GroundingDINO Swin-B权重哈希、原b6模型/计数目标、无contrast/TT/TV、官方精确名称七级文本/缺失回退species且无手工异名、三图代码排除、6998/999/2000、Python3.9.19/torch2.2.1/transformers4.39.1、train/eval batch4、seed42、30轮、冻结/优化器/学习率/增强/推理阈值相同。修复须在独立工作树最小移植并核对diff，不把main环境或eval batch1顺带带入；正式训练独立从GroundingDINO开始，不续训P01。P01继续保留原bug用于原版设置复现。

P02目的是回答已知padding/mask错误在P01协议下的影响。主要比较各自val MAE选择的best，报告同权重RMSE/R²及完整曲线；先用val判断，不提前看P02 test挑方案。P01/P02均完成固定预算后，才用各自冻结best做完整test。不要将P02与FSC147初始化/不同caption的R01直接比较并归因mask；单seed配对也不证明普遍效应。P02结果未知，无预设改善方向。

同时可用已有val逐图输出按预定GT计数桶/organ检查R01与R07的少计是否在val也存在，这是无需新训练的描述性诊断；不根据已看到的test改loss系数、阈值或挑旧epoch。当前不优先扩展organ完整方法或full几何对照。若R08最终出现val收益，再考虑相同TT/TV-only目标的欧氏配对（区别于R09 full目标）；若没有收益，保留负结果，下一轮先建立固定基线再决定机制改动或预先指定的多seed确认。


## 2026-10-17 P02启动准备（PREPARING）

用户要求P02启动命令。已从P01固定提交492688c创建独立分支repro/tpc268-p02-maskfix和工作树runs/tpc268_p02_maskfix_20261017/worktree；只改GroundingDINO.add_exemplar_tokens的padding/mask处理，其余52份核心源文件原样，groundingdino.py方法外逐字节核对。数据适配/增强/配置/依赖锁保持P01一致，入口核对P01的资产、初始化、配置、环境、全部67个实际依赖版本及原CUDA扩展SHA；不改变P01、R08或main模型。共享P01锁定.venv与CUDA扩展，只读使用；保留P01 audit/protocol.json、environment.json及环境。

混合caption屏蔽padding、真实token/特征插入、梯度、同长度无padding与原版等价的CPU检查已通过。GPU2本次实测空闲24124MiB；GPU短程15批+999val仍待验证。正式P02训练尚未启动，指标未知；与早期PROPOSED记录区分。脚本为独立工作树run_p02.sh，固定GPU2、要求22000MiB空闲，无rg依赖；通过配对检查后按P01预算从GroundingDINO独立训练30轮，随后best-val和一次test。P02没有辅助损失或新超参数，不把main eval batch1带入，train/eval均为4。完整协议和后台命令见该工作树两个docs；准备完成后更新状态。


## 2026-10-17 P02已准备：READY，正式训练未启动

代码固定为d521714b4515d07688a8686b34a03514842be56c（repro/tpc268-p02-maskfix）。配对协议指纹de263a0557b393fe8f02497798f3fc4331d95cc0bc66574346a21a5a8337f224，引用P01指纹fb63d9616f2f98f85ea17eb75352405d1fb048d4e75334c7b8d6d7acca1e84e8。逐项核对53份核心源码，只有exemplar方法改动；其余适配/配置/资产/初始化/67项实际依赖/算子哈希相同。GPU2真实预检15批训练+999图val完成、exitcode0、有限日志/梯度/正确mask/原版无padding等价及checkpoint保存通过；audit/preflight指纹相同。证据为runs/tpc268_p02_maskfix_20261017/readiness.json与preflight/，不是正式结果。

短程技术检查val MAE=36.269269269269266、RMSE=59.023917379506614、R²=0.6957866074722191，仅供核查，不进入正式性能表、不据此调参。正式P02尚未启动，训练0/30，正式val/test和best轮次未知；启动后独立重置seed42并加载官方GroundingDINO，绝不续用P01/预检权重。P01/P02仅mask处理不同，已有P01/R08保持原训练。

启动命令（固定GPU2，至少22000MiB空闲，nohup+setsid防SSH断开，锁防重复）：

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_p02_maskfix_20261017/worktree/run_p02.sh > runs/tpc268_p02_maskfix_20261017/pipeline.console.log 2>&1 < /dev/null &
```

预检已经完成，启动仍重核数据/协议并复用一致预检，然后正式30轮→best-val重评→固定best的2000图test。监控阶段：`tail -F runs/tpc268_p02_maskfix_20261017/pipeline.console.log`；训练明细：`tail -F runs/tpc268_p02_maskfix_20261017/train.console.log`（检查通过后生成，-F会等待文件）。结果根目录runs/tpc268_p02_maskfix_20261017/。P02通过.venv链接复用P01锁定环境，保留P01工作树.venv、audit/protocol.json和environment.json；不执行uv sync/install。


## 2026-10-18 训练状态更新（2026-10-18T10:24:10+08:00）

宿主机后台主进程R08/P01/P02=4037155/4079418/431449，GPU计算进程4041756/4084068/431915分别位于GPU0/3/2，已只读核实。当前R08完成19/30、正在第20轮；best checkpoint epoch11（第12轮），val MAE9.987987987987989、RMSE29.508520002750945、R²0.9239643740684884。P01完成21/30、正在第22轮；best epoch1（第2轮），val10.933933933933934/26.88757969661721/0.9368714679409043。P02已由用户启动，stage=TRAINING 2026-10-17T23:30:34+08:00，完成10/30、正在第11轮；best epoch5（第6轮），val11.05005005005005/30.248106518391328/0.9201051737165991。三份best元数据与正式逐轮日志对应一致，全部val999张，均是阶段性结果；尚无三项最终test。

R08主指标比R01低约0.0150但RMSE较差，继续原预算，不宣称全面或稳定提升；P01/P02完成预算不同，不对mask修复收益下结论。此次仅更新状态/指标，不修改训练、配置、数据或推理协议。原计划门槛、30轮预算和val选择规则保持。核查快照：runs/tpc268_v3_exclude3/planning/training_status_20261018.json。旧READY/PREPARING及10月17日的审批403记录为历史时点，本次进程/GPU核查已成功。


## 2026-10-18 下一项建议：P03初始化来源对照（PROPOSED；2026-10-18T20:33:01+08:00）

用户说明GPU3已空闲并询问下一项实验。本次核实P01完成30轮，pipeline DONE 2026-10-18T19:43:01+08:00且exit_code=0；第2轮best的独立val为10.933933933933934/26.88757969661721/0.9368714679409043，最终test2000张为19.4665/50.45931529460145/0.6106668647985156。全部test路径唯一且等于官方集合，每张GT等于原点标注，三指标独立重算一致。R08完成27轮、正在28轮，best仍第12轮；P02完成20轮、正在21轮，best更新为第14轮，val10.894894894894895/31.2739837894385/0.914593940870526。P02预算尚未完成，不能先判断mask效应。

建议P03配对P02，仅改变初始化来源：由官方GroundingDINO Swin-B改为本地checkpoints/checkpoint_fsc147_best.pth（FSC147预训练CountGD权重，文件已核实存在；不是随机初始化，也不是续训已有TPC checkpoint）。保持P02的mask修复、b6模型、无辅助损失、纯七级caption/缺链species/无手工异名、三图排除、6998/999/2000、Python3.9.19/torch2.2.1/transformers4.39.1、train/eval batch4、seed42、30轮、冻结/优化/增强/阈值/后处理全部相同。只加载模型权重，optimizer/scheduler/训练随机状态重新初始化；实现准备时需严格核对共享参数与初始化键兼容性，不静默跳过未知缺失键。

P03−P02用于估计**修复mask协议下**初始化来源的影响；P02−P01用于观察GroundingDINO初始化下mask处理的影响。不能用P03−P01单独归因初始化（两因素不同），也不能从这三个单元推断完整mask×初始化交互。R01与P01在caption、mask、环境、名称解析等也不同，因此不能把已有test差值6.8175直接归因FSC147。这一控制问题来自此前已明确的初始化缺项；P03是在已经查看test后提出的探索性协议核验，不包装为预注册或独立确认性结果，不因test调参数、阈值或选epoch。

P03先按固定30轮与val MAE选择规则对照P02，并报告同权重RMSE/R²及曲线；阶段性指标不同不提前下因果结论。预训练来源是否改善是未知结果，不能预填预期分数。用户本次仅询问建议，P03状态PROPOSED，尚无已实现启动脚本/代码提交，未启动训练。计划分配GPU3（空闲由用户说明，正式启动前重新核实）；不改R08/P02，不因空卡自动扩展R06/R09或扫辅助loss。R08仅有val MAE约0.015的微小改善，几何/多seed结论仍待完成预算和匹配控制。


## 2026-10-18 P03 初始化配对实验（PREPARING；2026-10-18T20:40:29+08:00）

用户已授权在GPU3后台启动。run ID=tpc268_p03_fsc147_init_20261018，独立分支repro/tpc268-p03-fsc147-init，从P02提交d521714b4515d07688a8686b34a03514842be56c创建；P03实际提交、PID及训练指标待启动核实。GPU3启动前实测24124MiB空闲，磁盘2.1TiB可用。

P03仅把P02官方GroundingDINO Swin-B初始化换为checkpoints/checkpoint_fsc147_best.pth（FSC147预训练CountGD），SHA256=c1bab864b17db345b4c6e3aaabb5765bc2c0a90d0bc8defb5e664a74a50aa126。模型全部参数/持久buffer要求严格键名和shape匹配；仅加载model，重新seed42、AdamW及StepLR，不加载FSC/TPC/预检optimizer、scheduler或随机状态。P02其余协议不变：已修复mask、原CountGD无辅助loss、官方精确名称七级逗号文本+句点，缺链只用species，无手工异名；三图在代码层排除，原数据/标注不改，split6998/999/2000；30轮、FP32、train/eval batch4、worker4、freeze backbone.0/bert、lr1e-4/wd1e-4/StepLR10/clip0.1、原增强和2px中心监督；整图800/1333、eval3 exemplars、阈值.23/0，无NMS/裁剪/SAM/数量校正。

入口核对P02 audit/protocol.json的53份核心源码、数据适配/增强/配置/依赖锁、资产、除initialization外全部配置、Python/torch/CUDA/mask/推理描述；只允许初始化与记录机制变化。共享P01的Python3.9.19/torch2.2.1+cu121/torchvision0.17.1+cu121/transformers4.39.1锁定环境，核对67项依赖和CUDA扩展SHA，uv显式指定解释器，不安装或同步。保留P01的.venv及environment.json和P02 audit/protocol.json作为依赖，不更改R08/P02。

固定GPU3，nohup+setsid防SSH断连，flock防重复启动，要求22000MiB空闲。流程audit→15训练批预检+完整999val及保存→重新初始化正式30轮→val选best复评→一次2000test。preflight只是技术验证，不纳入正式结果。已有test已公开，本次是探索性初始化来源控制；P03−P02仅解释修复mask协议下初始化效应，P02−P01仅解释GroundingDINO下mask效应，不能从三组推出完整交互或用P03−P01单独归因初始化。R06/R09门槛保持。

后台启动：
```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_p03_fsc147_init_20261018/worktree/run_p03.sh > runs/tpc268_p03_fsc147_init_20261018/pipeline.console.log 2>&1 < /dev/null &
```
阶段日志：`tail -F runs/tpc268_p03_fsc147_init_20261018/pipeline.console.log`；预检：`tail -F runs/tpc268_p03_fsc147_init_20261018/preflight.console.log`；正式：`tail -F runs/tpc268_p03_fsc147_init_20261018/train.console.log`。结果根目录同run ID。尚无正式val/test/best轮次。


### 2026-10-18 P03 后台启动核实（2026-10-18T20:41:38+08:00）

后台主进程PID1510920、PPID1、SID1510920、TTY=?已在宿主机核实，nohup+setsid独立运行。固定GPU3；源码提交2e964cdb9ef1ec6c02f3c4438bf1863ba3eea49b，启动worktree.diff为空。AUDIT于20:40:47开始并完成，PREFLIGHT于20:41:08开始；当前仍为技术预检，正式epoch0/30。数据6998/999/2000、完整链6258/943/1895及回退740/56/105已核对。配对指纹c9a750ff0e49ba0be91c130eebd31f79fa03a3aaf90da26768e65bac63d159fe；P02参考指纹de263a0557b393fe8f02497798f3fc4331d95cc0bc66574346a21a5a8337f224，模型53文件/配置/资产/依赖/算子检查通过。严格初始化加载与实际GPU训练/val仍待预检产物，正式best/val/test未知。早期PROPOSED/PREPARING仅是历史时点。


### 2026-10-18 P03 正式训练已启动（2026-10-18T20:46:07+08:00）

状态TRAINING，正式训练开始2026-10-18T20:45:05+08:00，当前第1/30轮（日志epoch0，已输出step20/1749）；0轮完整train+val完成，正式best/val/test均未知。GPU3实测占用7824MiB；后台PID1510920、训练PID1514919，PPID1/SID1510920/无TTY，SSH断开后继续运行。启动源码2e964cdb9ef1ec6c02f3c4438bf1863ba3eea49b，运行后仅追加文档状态说明，运行代码不改。

预检15批+完整999val及checkpoint保存已成功，1146项参数/持久buffer严格加载，缺失/额外/shape不符均0；mask/padding/插入梯度/同长度原版等价检查通过。audit/preflight/train指纹均c9a750ff0e49ba0be91c130eebd31f79fa03a3aaf90da26768e65bac63d159fe。预检技术结果MAE12.8008008008008、RMSE40.12493003121638、R²0.8594111606536942，不是正式最佳性能，不能纳入正式结果表。正式进程重新加载原FSC147，仅model；独立seed/optimizer/scheduler，首批loss280.8177与预检首批一致，而非从预检15批续训。正式loss日志有限，目前未出现报错。

记录：runs/tpc268_p03_fsc147_init_20261018/launch_verified.json。自动按30轮固定预算完成，再以val MAE选择best并重评val及一次2000test，无需再次启动。main及本工作树两份docs均已同步，P02/R08未修改。阶段监控pipeline.console.log，正式训练监控train.console.log；后台启动命令见上，当前不要重复执行。


## 2026-10-19 R08/P02完成后的结果核查（2026-10-19T11:03:11+08:00）

R08于2026-10-18T23:35:27+08:00正常退出0，30条完整训练/val日志，best checkpoint epoch11（第12轮）及独立val一致：9.987987987987989/29.508520002750945/0.9239643740684884，999张。启动HEAD8a26e86cffc8f5209c7924cf0d425044eaa0bdd4；保留历史dirty启动与实际评估代码的溯源边界。原run_r08.sh只执行best-val，不包含test，当前确无R08 test，不能把训练日志test_mae（test_split=val）误报为测试集。

P02于2026-10-19T06:07:41+08:00整条pipeline正常退出0，30条epoch0–29日志，best checkpoint epoch13（第14轮）与完成标志和best-val/test文件一致：val999张=10.894894894894895/31.2739837894385/0.914593940870526，test2000张=19.208/51.636527768625186/0.5922887239363432。代码d521714b4515d07688a8686b34a03514842be56c，指纹de263a0557b393fe8f02497798f3fc4331d95cc0bc66574346a21a5a8337f224。本次R08 val、P02 val/test及配对R01 val/P01 val/test逐图路径均唯一且等于官方split扣除既定三图，每张GT等于原points数量，三指标独立重算一致。

P03宿主机PID1514919、后台PID1510920仍存活，GPU3实测22964MiB/100%（瞬时）；GPU0/2各1MiB/0%，两项完成释放。P03完成14轮、正在15轮，日志batch660/1749，阶段性best epoch4（第5轮）val10.485485485485485/28.17653131449854/0.9306738112230415，与best checkpoint核对；未完成预算，无test。进度为带时间快照，非固定状态。

当前结论与下一步已更新第1/8节：R08无全面val收益、test缺失；P02 mask修复无全面收益、不能解释全部早期差距；P03待完成初始化控制。保持P03、R06/R09门槛及原协议，不依据test挑epoch或调参。本次仅只读核验、写结果记录和同步两份docs，未启动新训练/评估，未改模型、数据、配置或推理。证据：[results_verified_20261019.json](../runs/tpc268_v3_exclude3/planning/results_verified_20261019.json)。早期PROPOSED/READY/RUNNING段落按其当时日期理解。

实现/协议本次实质不变：既定三图只在代码中排除；官方原数据、标注及split未动。P02正确mask与原版mask的性能效应、P03初始化来源的性能效应分别比较，不能将代码正确性等同计数收益，也不能混合R/P两套环境和caption归因单一因素。


## 2026-10-19 R08 第12轮best测试集评估准备（2026-10-19T11:13:20+08:00）

用户明确授权完成R08最终best的test。准备runs/tpc268_v3_exclude3/run_r08_test_final.sh，固定空闲GPU0、至少4096MiB空闲，输出entailment_seed42/test_final/，不覆盖val或其他run。核对训练DONE/exit0、checkpoint epoch11（第12轮）/best val MAE9.987987987987989、full_taxonomy、Lorentz TT/TV-only系数.05/.05、seed42/30轮/train batch4，记录checkpoint前后SHA、实际代码HEAD/diff和环境；锁防重复。shell和内嵌Python语法已通过。

沿用原R08主caption/registry/三图代码排除/原初始化来源/冻结/模型/整图推理协议，测试2000张无排除、3exemplars、短边800/max1333、box/text阈值.23/0，无crop/SAM/exemplar correction；eval实际batch1与R系列一致。沿用main锁定uv环境，不安装依赖；只把CPU线程/worker设为2控制资源。运行代码HEAD及真实参数记录在输出目录；历史dirty训练源码边界保持。结束核对完整官方集合、每图GT点数、三指标独立重算、test与best-val training_protocol完全相同及权重SHA不变。测试性能、PID及实际启动状态尚未知；不根据test重选epoch或改阈值。无需更改P03/其他训练，模型和数据协议本次实质不变。

后台命令：`nohup setsid bash runs/tpc268_v3_exclude3/run_r08_test_final.sh > runs/tpc268_v3_exclude3/entailment_seed42/test_final.console.log 2>&1 < /dev/null &`；监控对应test_final.console.log。启动后核实状态，完成后同步本文件与另一份docs的正式结果。


2026-10-19 R08 test已启动：RUNNING 2026-10-19T11:13:24+08:00，后台PID2214660，GPU0；输出entailment_seed42/test_final/。实际评估HEAD已保存git_commit.txt，指标仍未知，等待进度与完成校验。训练DONE状态保持，test状态单独记录，不把启动当完成。


## 2026-10-19 R08 第12轮最终best测试完成（11:21:15 +08:00）

用户授权的评估已完成，GPU0，后台PID2214660；RUNNING 11:13:24→DONE 11:21:15，exitcode=0。输出runs/tpc268_v3_exclude3/entailment_seed42/test_final/；checkpoint_best_regular.pth元数据epoch11（第12轮）/best-val MAE9.987987987987989，前后SHA256一致：edd82a3f2ffb5a9d1d672e5efcadb772ac240f4fe09428937ce60292220fda40。原权重没有改写，严格加载missing/unexpected均空。

最终test：2000张，MAE13.689、RMSE37.20697515251676、R²0.7883163139084353。官方test路径集合逐项一致且唯一，每图GT等于原points长度，三指标独立重算吻合；与该run best-val的training_protocol及taxonomy_fingerprint一致。整图、3exemplars、实际eval batch1、阈值.23/0、无crop/SAM/exemplar correction；固定seed42，CPU线程/worker2只控制资源，数据/配置/训练/模型协议未改。PyTorch日志峰值allocated1584MiB。

实际eval HEAD6341592d13575f3626bc70f08604b96ab231f4ef，保存的运行源码diff为空；训练原启动HEAD8a26e86cffc8f5209c7924cf0d425044eaa0bdd4及dirty来源边界照旧保留，不能仅凭HEAD声称历史源码逐字节一致。实测Python3.10.12/torch2.13.0+cu130/torchvision0.28.0+cu130/transformers4.57.6及同main CUDA扩展，无依赖安装或环境同步，不与P系列旧版环境混用。

compare_tpc268_runs对照R01通过caption逐字、每图GT、相同官方图像集合、冻结、seed、初始化来源、预算、训练/推理协议核对。R08−R01：test ΔMAE+1.0400（+8.2220%）、ΔRMSE+0.5637356669035896（+1.5384%）、ΔR²−0.006365989760866997。逐图787张改善、689张变差、524张相同，但总体三指标退化。结合val仅MAE微降且RMSE/R²退化，本seed当前TT/TV-only未显示整体计数收益；不据此推广为所有双曲几何无效，不改loss/阈值/epoch，不追加新训练。P03继续原预算，R06/R09门槛保持。

证据：[test_metrics.json](../runs/tpc268_v3_exclude3/entailment_seed42/test_final/test_metrics.json)、[verified.json](../runs/tpc268_v3_exclude3/entailment_seed42/test_final/verified.json)、[R01_R08_comparison.json](../runs/tpc268_v3_exclude3/entailment_seed42/test_final/R01_R08_comparison.json)。早先11:03的test缺失记录和11:13的启动记录均为历史快照，当前正式结果以本节和主表为准。两份docs已同步，未修改官方数据及标注。


## 2026-10-19 下一项新训练建议：P04 organ-only配对基线（PROPOSED；2026-10-19T11:32:47+08:00）

用户询问下一步做什么实验，本节仅记录建议，不代表已批准启动、已实现或已测得结果。刚读取P03日志：完整14/30轮、正在第15轮，最新已输出batch1560/1749；best仍第5轮（epoch4），val MAE10.485485485485485、RMSE28.17653131449854、R²0.9306738112230415，无完整30轮结果/test。此处依据日志，不补写未查询的实时PID/GPU状态；P03继续原设置完成，随后既有pipeline按val MAE选best并评估test。

下一项新训练优先建议P04：以P03为严格配对基线，仅改变主caption策略，从官方精确名称七级逗号链/缺链species回退，改为目录所标器官`{organ}.`（例`fruit.`、`flower.`、`seed.`）。这定义为输入策略对照，同时移除species/taxonomy名称并提供organ词，不能进一步把差异单独归因分类层级长度或语义。organ-only仍含语义文本，不称纯视觉实验，不改CountGD结构/正标签路径或推理规则。

其余全部沿用P03：FSC147 CountGD模型权重SHA c1bab864b17db345b4c6e3aaabb5765bc2c0a90d0bc8defb5e664a74a50aa126，严格model-only加载、fresh optimizer/scheduler/RNG、修复mask、无对比/TT/TV、Python3.9.19/torch2.2.1+cu121/transformers4.39.1锁定环境及同CUDA扩展、同冻结/AdamW/StepLR/原增强/中心监督、seed42、30轮、train/eval batch4、3原始exemplars（训练按增强后batch最少数）、同官方数据划分和三图代码排除、6998/999/2000、阈值.23/0及同整图计数。数据和标注不修改；不能顺带引入R系列环境、eval batch1、alias或额外后处理。P04独立从原FSC147初始化，不从P03/TPC微调或短程checkpoint续训。

动机：R07 test三指标退化，R08 test MAE较R01增加8.2220%，R02/R04未获配对val收益；P02 mask修复未带来全面改善。现在缺的是统一协议下可靠的输入基线，非更多辅助loss组合。R05现有test MAE10.5470为已完成基线中最低，但其val并非最优，且与P03环境/caption解析/eval batch不同，因此只能提示检验organ-only，不能充当P04的严格baseline或证明organ优越。P04−P03仅解释本固定P协议/seed下prompt策略效应；不能用P04−R05归因单一因素。

执行前需实现新prompt协议/独立输出与运行指纹，核对除caption相关字段外P03配对项完全一致，并通过真实短程训练+完整val检查。正式30轮预算及按val MAE选best规则预先固定，不改阈值，不据test挑epoch；报告同best的RMSE/R²和完整曲线，之后一次完整test。P04是在已看过R05等test后提出的探索性对照，不能包装为未见test的确认性研究；若后续要主张稳定优越，需预先固定比较并增加配对seed，不只给有利模型补seed。

R06 organ完整方法、R09 full目标欧氏对照暂不优先；当前没有全面辅助收益，不因GPU空闲展开系数扫描。若后续研究问题是隔离几何，仍需与具体TT/TV或full目标完全匹配的欧氏对照，旧R09不能替代TT/TV-only对照。本次不新增可执行配置/脚本、不启动训练，P04提交/运行ID/GPU/指标均未知；后续用户要求执行时再准备完整可核验实现。P03和已运行实验不变。


## 2026-10-19 P04 organ-only配对实验准备（PREPARING；2026-10-19T11:39:48+08:00）

用户已明确授权在空闲GPU后台启动P04。运行ID=tpc268_p04_organ_20261019，独立分支repro/tpc268-p04-organ，从P03固定提交2e964cdb9ef1ec6c02f3c4438bf1863ba3eea49b创建。GPU2刚核实24124MiB空闲/0%利用率，0/1/3均有占用；固定GPU2，不改P03。P04实际提交/进程/PID/正式指标仍待启动核实。

唯一实验因素为主caption：P03官方七级文本/缺链species回退→P04目录器官`{organ}.`（`fruit.`、`flower.`、`seed.`等），所有split每张图都用organ，不因taxonomy缺失回退species。实际train含flower/fruit/leaf/plant/resin/root/seed/stem/stoma共9种，val/test含其中6种；不删除罕见器官或训练样本。organ-only含语义文本，不称纯视觉；同时更改输入信息和提示格式，不能单独归因层级长度。

其余与P03严格一致：FSC147 CountGD checkpoint_fsc147_best.pth的SHA256=c1bab864b17db345b4c6e3aaabb5765bc2c0a90d0bc8defb5e664a74a50aa126；严格加载全部model参数及持久buffer，不加载预训练optimizer/scheduler/RNG；独立seed42，修复mask，无对比/TT/TV，无辅助分支。原CountGD配置、冻结backbone.0/bert、AdamW lr1e-4/wd1e-4/StepLR10/clip0.1、原resize/crop/flip、2px中心监督、30轮、FP32、train/eval batch4、worker4、eval3exemplars/训练按增强后batch最少数、6998/999/2000及三图代码排除、800/1333整图/阈值.23/0/无crop/SAM/NMS/数量校正均保持。数据、标注和官方split不改。

共享P01只读锁定.venv：Python3.9.19/torch2.2.1+cu121/torchvision0.17.1+cu121/transformers4.39.1及既有CUDA扩展；uv显式指定该解释器、不安装/sync。保留P01 .venv及environment.json、P03 audit/protocol.json和工作树dataset源文件（真实数据配对检查依赖），不引入main新环境或eval batch1。

实现边界：53份模型/core源码、transforms和依赖锁要求逐hash等于P03；config仅prompt_protocol不同；Dataset仅self.phrases换organ及审计metadata字段改名；taxonomy完整标志仍作为元数据供分组，绝不进入caption。原full_taxonomy_images/species_fallback_images/fallback_species报告改为official_*_metadata名称，避免误报P04使用分类文本/回退species。主训练main、evaluate、loader和mask-check函数逐源核对P03完全相同；初始化/模型/损失/优化和推理无改动。入口比较P03指纹c9a750ff0e49ba0be91c130eebd31f79fa03a3aaf90da26768e65bac63d159fe，只允许caption相关变化；审计还会比较全split路径/GT及每个器官代表样本同随机种子下的图像增强、points/boxes/exemplars/labels等全部非文本target和RNG消耗，未执行前不写通过。

脚本run_p04.sh：GPU2至少22000MiB空闲、flock防重复、nohup+setsid防SSH断连。流程audit→15批GPU预检+999val和保存→重新从原FSC147独立初始化正式30轮→按val MAE选best重评→一次2000test。预检不算正式结果，不从P03或预检checkpoint续训。语法检查已通过，实际audit/GPU预检待运行。

后台启动：
```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_p04_organ_20261019/worktree/run_p04.sh > runs/tpc268_p04_organ_20261019/pipeline.console.log 2>&1 < /dev/null &
```
阶段日志pipeline.console.log，预检preflight.console.log，正式train.console.log，均在同一run根目录。当前正式训练尚未启动，正式val/test/best未知。

P04−P03检验统一P协议下的prompt策略；R05只提供探索动机，不能直接当作P04匹配baseline。本方向在已查看R05等test后提出，属于探索性实验；不因test调阈值/挑epoch，若主张稳定优越再预先固定配对多seed。R06/R09门槛保持，不启动其它新实验；两份docs同步更新。


### 2026-10-19 P04后台启动与配对审计通过（2026-10-19T11:41:31+08:00）

P04源码固定fc6ad2e66602b234111f965d3bcac618e68fa408，启动worktree.diff为空。nohup+setsid后台PID2247612、PPID1、SID2247612、无TTY已在宿主机核实；GPU2。AUDIT开始11:40:20，PREFLIGHT开始11:40:47；正式训练尚未开始，GPU预检结果待完成。

审计指纹51c7e4a04e3d5c266b1d77265fcdef7f98366ebd63acd9e1ecfdc4aa75c465a2，对照P03指纹c9a750ff0e49ba0be91c130eebd31f79fa03a3aaf90da26768e65bac63d159fe。全部53份核心源文件、非caption配置/资产/初始化/67项环境依赖及native扩展SHA逐项匹配。main/evaluate/loader/mask-check逐源相同，dataset/config严格限制为caption及报告字段改动。train/val/test=6998/999/2000每图organ提示均检查，21个代表样本（9/6/6器官）同seed下图像张量、全部非文本target及RNG消耗与P03相同。数据/标注原样，完整taxonomy标志只保留为metadata；不存在P04 species回退。证据audit/protocol.json、matched_data_check.json、dataset_audit.json、captions.json；caption含3exemplars最大8tokens，未截断。

正式30轮best/val/test均未知，15批预检通过后脚本会独立重新初始化开始正式训练；当前不要重复启动。


### 2026-10-19 P04 正式训练已启动并核实（2026-10-19T11:45:29+08:00）

状态TRAINING，正式开始2026-10-19T11:44:28+08:00；当前第1/30轮（epoch0，已输出batch20/1749），完整train+val为0轮，正式best/val/test仍未知。后台PID2247612、训练PID2254352、PPID1/SID2247612/无TTY已在宿主机核实；GPU2，瞬时占用7902MiB。nohup+setsid保持SSH断开后运行，锁防重复，不要再次执行启动命令。

15批真实训练+完整999val与checkpoint保存已通过，1146项模型参数/持久buffer严格加载无缺失/额外/shape差异；正确mask、exemplar插入及梯度、无padding原版等价检查通过。audit/preflight/train的协议指纹均为51c7e4a04e3d5c266b1d77265fcdef7f98366ebd63acd9e1ecfdc4aa75c465a2，代码fc6ad2e66602b234111f965d3bcac618e68fa408，启动源码diff为空；启动后只追加文档状态，运行代码不改。

预检技术结果val MAE10.65065065065065、RMSE28.446567582174254、R²0.9293386368130596，不是正式最佳性能，不进入正式性能表。正式进程已重新加载原FSC147权重并重新创建seed42/optimizer/scheduler；首批loss12.4044与预检首批一致，绝非从预检15批或P03权重续训。实际首批训练loss有限，未出现报错。

后续自动完成30轮→按val MAE选best→best-val重评→一次完整2000图test，保持P03及其他实验不变。记录runs/tpc268_p04_organ_20261019/launch_verified.json；正式进度命令`tail -F runs/tpc268_p04_organ_20261019/train.console.log`，阶段命令`tail -F runs/tpc268_p04_organ_20261019/pipeline.console.log`。两份主docs和本工作树两份docs同步；早先PROPOSED/PREPARING/PREFLIGHT按当时时点理解。


## 2026-10-19 P03/P04训练进度核查（15:51 Asia/Shanghai）

只读读取正式训练日志、best_val_metrics.json、实际运行protocol并查询宿主机进程/GPU。P03后台PID1510920/训练PID1514919仍运行于GPU3，已完成19/30个完整train+val，正在第20轮（日志epoch19，最近batch10/1749）；best仍第5轮（epoch4），val999张MAE10.485485485485485、RMSE28.17653131449854、R²0.9306738112230415。P04后台PID2247612/训练PID2254352仍运行于GPU2，已完成4/30，正在第5轮（epoch4，最近batch560/1749）；best第2轮（epoch1），val999张MAE10.793793793793794、RMSE32.30663583102888、R²0.9088606888426949。两份best指标均与各自正式逐轮日志最小MAE的同一轮一致。两组均尚无最终test/30轮完成标志，阶段性结果不当作完整预算比较；轮次采用1-based。

P03代码2e964cdb9ef1ec6c02f3c4438bf1863ba3eea49b，主caption为官方精确名称七级逗号链+句点，缺链只用Species.，无手工异名、无organ前缀；P04代码fc6ad2e66602b234111f965d3bcac618e68fa408，仅主caption换为目录器官{organ}.，例fruit.，不含species或taxonomy文本。两者共享FSC147 CountGD model-only独立初始化、修复mask、无对比/TT/TV辅助损失，seed42/30轮/FP32/train和eval batch4、冻结backbone.0/bert、AdamW lr1e-4/wd1e-4/StepLR10/clip0.1、同原增强/中心监督、三图代码排除6998/999/2000、旧版锁定环境和整图阈值.23/0推理。P03对P02控制初始化，P04对P03控制prompt策略。

GPU瞬时占用P03=22964MiB/100%，P04=21926MiB/100%；状态来自15:51宿主机核查，不用历史启动状态冒充实时状态。只更新进度和两份docs，不改模型/数据/环境/配置、不重启训练。两组按原预算继续，结束由既有pipeline对val MAE选择的best重评val并跑完整test。


## 2026-10-20 P03最终最佳权重测试核验（2026-10-20T10:10:16+08:00）

用户要求在GPU3测试P03。核查发现原run_p03.sh固定CUDA_VISIBLE_DEVICES=3，已自动完成TRAINING→BEST_VAL→TEST：训练完成30轮，BEST_VAL 03:08:02、TEST 03:11:20、DONE 03:17:34，整条pipeline exit_code=0。故本次直接核验已完成的同卡同权重测试，不另启动重复推理；GPU3当前24124MiB空闲/0%，原后台PID1510920/训练PID1514919已退出。

best checkpoint epoch4（第5轮）、best_val_mae10.485485485485485、training_mode=train、指纹c9a750ff0e49ba0be91c130eebd31f79fa03a3aaf90da26768e65bac63d159fe，均与30条完整训练日志最低val、train/completed.json、best-val及test结果对应。当前权重SHA256=d973c7ba576149f39e467c651115aa5ff2e09cc309e32e86cd6cfdcc4f0ef944；原pipeline未另存运行前后SHA，本次仅记录当前权重哈希，不补称已做历史前后比对。代码commit2e964cdb9ef1ec6c02f3c4438bf1863ba3eea49b，audit/train/best_val/test指纹及commit一致，沿用原Python3.9.19/torch2.2.1+cu121/transformers4.39.1环境和编译扩展。

最终val999张：MAE10.485485485485485、RMSE28.17653131449854、R²0.9306738112230415；test2000张：MAE11.338、RMSE35.49826756336145、R²0.807312750302844。两份计数输出路径唯一且等于官方split（val按既定排除1图，test无排除），每图GT等于原points数量，整数预测/GT与三指标独立重算吻合，未修改任何数据/预测。test使用原seed42、3exemplars、eval batch4、整图800/1333、阈值.23/0，无crop/SAM/NMS/数量校正；无推理协议变动。

P03/P02协议核对：53份core、资产/配置（除初始化路径）、环境/修复mask/增强/推理及Dataset/config/锁文件hash均一致，audit/captions.json逐项相同，只比较既定初始化来源差异。P03相对P02：val ΔMAE−0.4094094094094096、ΔRMSE−3.09745247493996、ΔR²+0.016079870352515457；test ΔMAE−7.87（−40.9725%）、ΔRMSE−16.138260205263734（−31.2536%）、ΔR²+0.21502402636650075。该受控seed支持初始化来源有明显影响，不推广到所有设置，不将P03−P01两因素差异冒充单一因素，P04继续原定prompt对照。

证据：[test_metrics.json](../runs/tpc268_p03_fsc147_init_20261018/test/test_metrics.json)、[verified.json](../runs/tpc268_p03_fsc147_init_20261018/test/verified.json)、checkpoint_metadata_verified.json及原pipeline/test console。两份主docs及P03工作树docs已同步更新；实现、模型、环境、数据、超参数均未更改。早期P03 RUNNING/无test记录按当时时点理解。


## 2026-10-20 R06原设置、20轮预算：仅准备命令

按用户明确要求，原计划R06 organ-only完整辅助方法现准备为20轮（run=`organ_method_seed42_e20`），后续用户要求只给命令，因此未启动训练/预检。复用原`cfg_tpc268_organ_full.py`，`{organ} .`主caption，contrast+Lorentz TT/TV权重.1/.05/.05，从FSC147 CountGD独立初始化，seed42，保留R系列冻结/增强/三图排除/registry、eval batch1及整图推理协议；不使用P系列工作树/环境。仅命令行epochs=20，StepLR仍每10轮衰减；模型、loss、原配置、数据集/标注均未改。

新增runs下[run_r06_e20.sh](../runs/tpc268_v3_exclude3/run_r06_e20.sh)：固定GPU3（准备时24124MiB空闲，实际启动重查20000MiB），uv显式选择主`.venv`且不更新环境、flock、拒绝已有训练产物以免main.py自动resume、原始初始化训练20轮→999图best-val重评，不自动test，保存status/exitcode/stage和启动来源hash。此为用户指定的探索性追加，覆盖旧R06自动调度门槛，不宣称此前候选收益门槛满足，R09不变。

配置核对相对R05仅epochs30→20与两个辅助开关False→True。R05前20轮val选出的best为第12轮，与全30轮best相同（10.476476476476476/30.35284657647937/0.9195509124443442）；StepLR不依赖总epochs，可将R05既有前20轮作为R06预算对齐参照，不将20轮写成30轮同预算。R05历史dirty源码不可完全重建的边界继续披露。bash语法、内嵌Python语法、配置/日志检查通过，记录见[r06_e20_prepared_20261020.json](../runs/tpc268_v3_exclude3/planning/r06_e20_prepared_20261020.json)；没有执行本次GPU训练或验证，不产生新性能。完整协议/命令同步到experiment.md，docs仍恰好两份。


## 2026-10-20 R08-LC：可学习曲率20轮命令准备（未启动）

新增[cfg_tpc268_entailment_learnable.py](../config/cfg_tpc268_entailment_learnable.py)继承原R08，唯一有效配置变化为learn_curvature=False→True、epochs30→20，curvature_init仍1。模型已有log_c Parameter支持，无需修改模型/损失/训练主程序；TT/TV共享c∈[.1,10]（空间曲率−c），alpha_t/alpha_v、原AdamW学习率/weight decay与StepLR10保留。contrast关闭，TT/TV权重.05/.05，主full-taxonomy文本、FSC147独立初始化、seed42、冻结、增强、数据三图排除、环境、train4/eval1及整图推理均沿用R08；原数据/标注不变。

新脚本[r08 launch](../runs/tpc268_v3_exclude3/run_r08_learnable_e20.sh)使用独立run=`entailment_learnable_seed42_e20`，默认GPU1，可由R08_GPU指定；启动重查至少20000MiB，uv显式原环境离线no-project、flock、防main自动resume，20轮训练→val选best→999图val重评，不自动test。GPU实时查询自动审批超时，空闲状态未核实；并非已启动训练。记录HEAD/diff、配置/数据资产/初始化hash及curvature_protocol，既有简版training_protocol未包含曲率开关，沿用但由launch_manifest与checkpoint args补足，无核心代码改动影响在训实验。

有效配置与原R08比对及bash/内嵌Python语法检查通过；CPU合成实际几何/Parameter/优化器检查通过：log_c梯度0.25372225046157837，一次AdamW将c由1更新为0.9998999834060669，非法锥0。这不是实际CountGD训练或计数结果。原R08前20轮val最佳仍第12轮（9.987987987987989/29.508520002750945/0.9239643740684884），后续按相同20轮选择范围比较，不使用test选参数。源训练dirty/归档不足边界保留。证据见[r08_learnable_e20_prepared_20261020.json](../runs/tpc268_v3_exclude3/planning/r08_learnable_e20_prepared_20261020.json)；用户本次只要求命令，没有执行训练/数据预检/GPU评估，两份docs同步记录，性能及真实训练状态未知。

同期只读补记：R06状态/stage文件显示10月20日10:20:16进入RUNNING/TRAINING，主报告已区分早先命令准备快照和文件记录；未查询其活进程/轮次，不影响本次R08-LC未启动结论，也未更改R06运行代码。


## 2026-10-20 R08-GD：独立GroundingDINO初始化入口

用户授权基于原R08、GPU2执行GroundingDINO初始化对照，沿用固定c=1、TT/TV .05/.05、contrast关闭、30轮（不继承R08-LC的20轮/可学习曲率）。复用cfg_tpc268_entailment.py；有效配置与原R08逐项一致，唯一实验因素是初始化来源。主caption、修复mask、数据/三图代码排除、R系列环境、优化与整图推理协议不变，细节/命令/状态同步记于experiment.md。不修改数据、标注及其他在训实验。

新增`tools/train_tpc268_groundingdino.py`，只在本进程fresh入口初始化阶段设置main.load_countgd_state，退出恢复；共享main.py、util/checkpoint.py及模型/loss/Dataset文件均未更改。入口拒绝resume/eval/非0起始epoch/已有训练产物，要求固定官方Swin-B权重路径及SHA256=46270f7a822e6906b655b729c90613e48929d0f2bb8b9b76fd10a856f3ac6ab7，禁止加载optimizer/scheduler/RNG。枚举40个确切CountGD专有参数名及既有is_auxiliary_key允许的12项辅助参数/持久buffer，严格要求缺失集合相等；仅允许丢弃label_enc.weight及固定arange的bert.embeddings.position_ids，共享1106项逐shape匹配。任一额外差异报错。CountGD专有模块/辅助头按seed42模型构造初始化，因此初始化对照包含其是否预训练，非只改backbone。best权重评估仍由原main.py严格加载全部CountGD/辅助状态。

实际CPU构建/严格加载检查通过，报告`runs/tpc268_v3_exclude3/planning/r08_gd_initialization_cpu_20261020.json`；bash -n、两处Python AST、相对R08零配置差异检查通过。CPU结果不是GPU训练/性能。新脚本`runs/tpc268_v3_exclude3/run_r08_groundingdino.sh`固定CUDA_VISIBLE_DEVICES=2，显式uv离线no-project/主.venv，不安装环境；GPU至少20000MiB空闲、flock、防隐式resume、保存HEAD/diff/源码及数据协议hash/初始化报告/status/stage/exitcode。后台训练30轮后按val MAE选best重评999图val，不自动test。

准备HEAD=6341592d13575f3626bc70f08604b96ab231f4ef，新入口及文档尚未提交；实际启动commit及源码hash由启动清单记录。原R08历史dirty源码归档不足的限制保留，R08-GD仅作当前单seed初始化来源探索性对照，不与P系列跨协议单因素归因。宿主机已核实GPU2空闲24124MiB/0%，启动另查；此段不冒充正式已启动或已有指标，启动后另记。


### 2026-10-20 R08-GD后台启动核实（19:35 Asia/Shanghai）

实际后台启动于19:34:39，TRAINING阶段19:34:48；19:35:43核实launcher PID253082、训练PID253270，PPID1/SID253082/无TTY，GPU2 UUID=GPU-3163c4c0-3619-4198-ffcd-664c831f1cb9实际分配训练进程10750MiB，nohup+setsid防SSH断连。当前第1/30轮（epoch0），已输出batch10/1749，完成完整train+val为0轮；正式best/val/test尚无，不重复启动。

launch_manifest确认有效配置相对原R08零差异，GroundingDINO源SHA与预定值一致；实际GPU加载1106项共享张量及40+12项明确随机初始化状态通过。首批loss1700.2583，batch10最新loss880.6318，均有限；日志包含TT/TV、不含contrast、c=1、锥非法率0。这只说明启动/初期优化正常，不是模型性能或最终收敛结论。模型代码及环境未变，后续按30轮/val MAE选best规则继续，结束重评val，不自动test。

启动代码HEAD6341592d13575f3626bc70f08604b96ab231f4ef，专用新入口未提交，故不把HEAD单独当完整源码身份；launch_manifest含入口及核心源码hash，launch_sources另存入口/启动脚本快照，launch_verified记录hash、进程与初期日志检查。证据`runs/tpc268_v3_exclude3/entailment_groundingdino_seed42/{launch_manifest,initialization_report,launch_verified}.json`；进度`tail -f runs/tpc268_v3_exclude3/launch_entailment_groundingdino_seed42.log`。两份docs同步记录。此前READY段按准备时点理解，R08-LC/R06/P04状态未在本任务重新审计。


## 2026-10-21 R06 / R08-LC完整测试集评估（准备）

用户明确要求评估两组测试集。已核实各自20条完整train+val日志、训练及best-val pipeline DONE/exitcode0：R06完成于11:11:21，第5轮best-val=10.64064064064064/26.04504452567406/0.9407658067617174；R08-LC完成于11:12:52，第1轮best-val=10.23023023023023/28.625118294906617/0.9284488119034939。此前READY/RUNNING按历史时点理解，测试前均无test结果。

只使用上述val MAE选择的checkpoint_best_regular.pth，不用最后一轮、不重训或依据test挑epoch。GPU3运行R06、GPU1运行R08-LC，启动前宿主机两卡各24124MiB空闲。新增本地脚本runs/tpc268_v3_exclude3/run_r06_r08lc_test.sh，输出各自test_final/；nohup+setsid、flock及防覆盖检查，独立eval状态/退出码，不改训练状态。先核对best epoch/训练参数、环境、全部训练启动manifest的源码/配置/数据协议hash，记录best权重SHA和曲率；评估后再比SHA。若检查未通过则退出，不放宽协议。

完全沿用各自最佳权重重评val协议：主仓库既有.venv、uv离线no-project不安装/同步，seed42、FP32、train配置batch4（eval实际batch1）、workers4、3exemplars、整图800/1333、阈值.23/0、无crop/SAM/数量校正；同registry/数据排除/坐标策略。R06为organ提示、contrast+固定曲率TT/TV；R08-LC为full_taxonomy提示、仅TT/TV、learn_curvature=True且加载第1轮best保存的log_c（不使用最后一轮曲率）。测试集官方2000张全评，不额外排除任何test图。

脚本将验证2000条路径唯一且等于官方split、GT等于原annotation点数、从整数计数独立重算MAE/RMSE/R²，并核对推理及training_protocol与best-val一致。既有指标摘要遗漏learn_curvature/curvature_init，因此额外在checkpoint_metadata.json记录这两个字段及best实际c，不改共享核心代码。数据、标注、模型/loss/配置及在训R08-GD均不修改；两份docs同步更新。此节为准备记录，PID/实测test/成功状态待运行后记录。

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_r06_r08lc_test.sh R06 > runs/tpc268_v3_exclude3/launch_r06_test_final.log 2>&1 < /dev/null &
nohup setsid bash runs/tpc268_v3_exclude3/run_r06_r08lc_test.sh R08-LC > runs/tpc268_v3_exclude3/launch_r08lc_test_final.log 2>&1 < /dev/null &
```


### 2026-10-21 R06 / R08-LC最佳权重test已启动（11:48 Asia/Shanghai）

两组预检均通过：checkpoint epoch分别4/0（第5/1轮），与20轮完整日志最低val MAE及best-val重评一致；全部训练启动清单中的78/79份源码/配置/资产hash与当前逐一相同。R06 best SHA256=4e4a790c5e4343be454395f4274531bf936ba69f63abd22c35e73674fc406166，固定c=1；R08-LC best SHA256=e8a760e9b0ce114e109270da08591ce4b6568f2723592819bddc724d152a1cb0，可学习c=0.8409649729728699（第1轮best，非最后一轮）。具体源码hash、环境/native扩展hash、训练参数及曲率字段保存于各自test_final/checkpoint_metadata.json。

11:48:08后台启动，评估进入RUNNING于11:48:35，launcher PID分别1038552（R06/GPU3）、1038553（R08-LC/GPU1）。首批真实test推理均通过，日志已输出10/2000；尚无最终性能，不提前填写。两份docs同步更新，主表训练状态和已确认best-val改为20轮完成、test运行中；没有更改模型/配置/数据/环境或推理协议。


## 2026-10-21 R06 / R08-LC完整测试完成并核验（11:55 Asia/Shanghai）

R06：训练commit=6341592d13575f3626bc70f08604b96ab231f4ef，测试commit=6341592d13575f3626bc70f08604b96ab231f4ef；best第5轮，GPU3；val MAE/RMSE/R²=10.64064064064064/26.04504452567406/0.9407658067617174；test2000图=10.734/30.724338886296643/0.8556543321384513；权重SHA256=4e4a790c5e4343be454395f4274531bf936ba69f63abd22c35e73674fc406166，best c=1.0；DONE 2026-10-21T11:55:28+08:00、exitcode0。

R08-LC：训练commit=6341592d13575f3626bc70f08604b96ab231f4ef，测试commit=6341592d13575f3626bc70f08604b96ab231f4ef；best第1轮，GPU1；val MAE/RMSE/R²=10.23023023023023/28.625118294906617/0.9284488119034939；test2000图=11.14/32.864798797497606/0.8348416191688222；权重SHA256=e8a760e9b0ce114e109270da08591ce4b6568f2723592819bddc724d152a1cb0，best c=0.8409649729728699；DONE 2026-10-21T11:55:52+08:00、exitcode0。

两组均为20轮完整训练范围内按val MAE选出的同一best，不从test挑epoch。每组2000条唯一relative_path精确等于官方test，GT逐图等于原annotation的points数量，从整数预测独立重算三指标吻合（R²仅浮点末位差）；阈值/整图推理/3exemplars及training_protocol、taxonomy指纹与其best-val重评相同。权重评估前后SHA一致，源码/配置/数据协议78/79份训练manifest hash逐项相同。R08-LC实际使用第1轮best保存的c=0.8409649729728699，绝非第20轮或曾报告的训练中c≈0.645；评估跳过训练辅助分支，但完整checkpoint状态按相同配置载入。

比较参照：R05/R08原30轮日志的前20轮val最优均仍第12轮，等于全30轮best，StepLR10不依赖总epochs，故已有同best测试可作20轮选择范围的参照；不把20轮新训练冒称完整30轮预算，原历史dirty源码归档不足的可重建性边界保留。R06对R05：test ΔMAE+0.187（+1.773016%）、ΔRMSE+0.8537680849209188（+2.858225%）、ΔR²−0.007910696442368637；val MAE+1.566979%、RMSE−14.192415%，说明当前organ完整辅助方案没有整体测试收益，验证集RMSE改善未转化为测试改善。

R08-LC对固定曲率R08：test ΔMAE−2.5489999999999995（−18.620790%）、ΔRMSE−4.342176355019156（−11.670329%）、ΔR²+0.046525305260386896；val MAE+2.425336%、RMSE−2.993717%、R²+0.004484437835005517。该固定seed/协议下测试三指标改善，支持可学习曲率版本值得进一步检验，但val MAE仍未改善，不能称稳定普遍有效、不能把曲率变化本身当收益证明；曲率与既有可学习alpha尺度仍存在耦合。R08-LC test MAE11.14仍高于organ基线R05的10.547，这属于跨prompt描述，不能用来单因素归因曲率。实验是在已看历史test后提出的探索性对照，不据此次test继续调阈值/曲率/系数或选择epoch；若要确认可重复收益，需要预先固定的配对多seed验证。

结果文件（每个run均有）：`test_final/test_metrics.json`、`test_counts.json`、`checkpoint_metadata.json`、`checkpoint.sha256`、`verified.json`、`launch_verified.json`、`status`/`exitcode`及完整console；启动脚本快照eval_script.sh。汇总`runs/tpc268_v3_exclude3/planning/r06_r08lc_test_results_20261021.json`。R06测试后台PID1038552/推理PID1039245；R08-LC后台PID1038553/推理PID1039238，启动时宿主机核实PPID1、SID=后台PID、无TTY，GPU分别3/1。成功完成时间如上，不用历史PID存活推断当前状态。

两份docs同步更新训练完成/val/test主表及结论；仅新增本地评估脚本与证据，没有修改main/model/loss/config、数据/标注、环境或在训R08-GD。此前测试准备/RUNNING记录按其时间理解，最新状态均DONE。


## 2026-10-21 R08-GD-LC独立初始化入口与20轮协议（准备）

用户授权GroundingDINO Swin-B初始化、可学习曲率、仅TT/TV辅助目标、20 epochs，固定新ID=R08-GD-LC，GPU1后台运行计划；完整设置/配对范围/命令同步见experiment.md。复用现有cfg_tpc268_entailment_learnable.py（初始c1，[.1,10]共享TT/TV，lambda .05/.05，contrast关闭）。计数主损失保留，主caption/full_taxonomy、修复mask、数据/三图排除、增强/优化/环境/推理协议不改。

新增`tools/train_tpc268_groundingdino_learnable.py`，复用旧GroundingDINO入口的SHA常量及严格加载函数；仅本进程fresh训练适配，拒绝resume/eval/已有产物，限定20轮、learn_curvature=True、初始c1、Lorentz/TTTV/full_taxonomy及log_c为Parameter。共享1106项加载、40项CountGD模块及12项taxonomy状态保留构造初始化，严格限制两项源额外key；不继承FSC147/TPC权重/optimizer/scheduler/RNG。旧tools/train_tpc268_groundingdino.py逐SHA等于旧运行的快照，不修改GPU2上R08-GD或其训练入口、main/model/loss/Dataset。

新增本地run_r08_groundingdino_learnable_e20.sh，固定GPU1/uv离线主.venv、flock及空闲20000MiB/防隐式resume，记录源文件/初始化/数据协议/native扩展hash及曲率清单；对R08-LC有效配置零差异、仅初始化不同；对R08-GD仅learn_curvature及预算不同，后续限前20轮val选择范围比较（当前只读确认R08-GD完成13轮，不提前给匹配结果）。启动CPU检查实际构造/加载模型、优化器log_c唯一性及合成几何梯度/更新，技术检查模型不用于正式训练；独立新进程fresh seed42训练20轮→按val MAE选best→best-val重评，无自动test。

准备时HEAD6341592d13575f3626bc70f08604b96ab231f4ef，新入口/配置及文档未提交；正式版本另存hash与参数。GPU1实查24124MiB空闲，bash/两处Python语法已过，实际CPU/GPU技术检查、正式训练进度与指标待启动后核实。数据及标注不改；本次属于看过历史test后的探索性初始化/曲率对照，不用test选择epoch或调参。两份docs同步更新。


### 2026-10-21 R08-GD-LC启动检查发现并记录监控依赖元数据差异

首次仅运行CPU前的源码检查，于12:04:36因pyproject.toml/uv.lock相对两对照的hash不同而退出1，未进行模型训练、未产生训练checkpoint/log.txt。失败证据保留新run/prelaunch_attempt_1/。检查发现这两个文件在12:02:13被会话外同步修改：pyproject仅新增dev组nvitop>=1.7.1，原project及uv训练依赖配置完全相同；锁文件新增nvitop/psutil/nvidia-ml-py/windows-curses、根项目元数据hgic→countgd并更新下载镜像/辅助元数据，所有共同包的锁定版本无变化。保留这些用户工作区改动，不回退或安装/sync。

实际核对原锁文件中的63个已安装依赖版本均未改变；colorama为未安装的可选平台包，hgic为旧根项目元数据。Python/torch/torchvision/transformers仍3.10.12/2.13.0+cu130/0.28.0+cu130/4.57.6，native扩展SHA256=c58d6ff7e9a8fad209d099fd1e058f86afd3567b8960311b75fbb290ee1ad4ee，与R08-LC刚完成test记录相同。完整审计见planning/r08_gd_lc_environment_20261021.json。该核对证明原训练依赖版本/核心native一致，不声称新增监控包后整个site-packages逐字节相同。

新脚本仅为这两个文件加入精确新hash白名单，并每次校验该审计、63个原依赖实际版本、native hash及其他全部源码/资产hash；不忽略任何模型/数据/配置变化，不放宽checkpoint加载。正式run清单另存dependency_metadata_delta/audit及新lock hash，完整环境身份含这项监控工具差异；与旧对照比较须保留此边界，后续确认性配对运行应统一同一依赖快照。依然使用uv --offline --no-project显式原解释器，锁文件不参与安装或训练依赖解析。首次失败不是模型/曲率故障，重试仍fresh GroundingDINO/seed42，已有R08-GD不变。两份docs同步补记。


### 2026-10-21 R08-GD-LC正式训练已启动（2026-10-21T12:09:14.572465+08:00）

新run=entailment_groundingdino_learnable_seed42_e20，GPU1；正式TRAINING阶段开始12:08:05。后台PID1060614，PPID1/SID1060614/无TTY；实际训练PID1061031已在宿主机核实使用GPU1（UUID=GPU-b82ea893-51d2-9c44-dfcf-fe24537493c1），nohup+setsid独立于SSH。当前第1/20轮（epoch0），已输出batch20/1749，完整train+val轮次0，best/val/test均未知，不重复启动。

真实CPU构造/严格加载通过；log_c为可学习Parameter、唯一进入原优化器普通lr1e-4组，合成几何梯度0.2475481778383255，一步AdamW使c由1→0.9998999834060669，非法锥0。该CPU模型未用于正式训练；正式进程重新seed42/加载原始GroundingDINO。GPU正式加载共享1106项，CountGD构造初始化40项、taxonomy构造初始化12项；前20批日志loss有限，最新loss=293.7841，包含TT/TV、无level_contrast，锥非法率0。实际训练日志c已由初始1更新至0.9998，证明真实训练中曲率在更新，尚不代表计数性能改善。

启动HEAD=6341592d13575f3626bc70f08604b96ab231f4ef，新入口/配置未提交，另存launch_sources双入口及启动脚本/依赖元数据/环境审计快照和hash；launch_manifest保留配置、曲率及优化器设置/源码资产hash/元数据差异，launch_verified保留实际进程、首批运行证据。相对R08-LC有效配置零差异；相对R08-GD只epochs30→20、learn_curvature False→True；77/80份其余源码/资产hash逐项一致，只有已审计pyproject/uv.lock监控依赖元数据差异，63个原已安装依赖版本及native hash仍相同。不把整个环境逐字节相同作为比较前提，后续确认性配对需统一完整快照；不放宽模型或数据检查。

本次核对初始化报告也纠正文档中的计数笔误：此前“38项CountGD专有参数”应为40项（3层encoder每层12项，共36项，加encoder最终norm与feature_map_proj各2项）；原严格加载代码和缺失名单始终正确，代码/权重未因此改动。两份docs相关文字同步更正。

训练将按预定20轮继续，每轮完整999图val，按val MAE选择best，结束重评同best的val；不自动test。启动日志`runs/tpc268_v3_exclude3/launch_entailment_groundingdino_learnable_seed42_e20.log`，训练日志/状态/清单位于新run。没有修改共享main/model/loss/Dataset、已有GroundingDINO入口或GPU2上R08-GD，数据/标注不改；两份docs同步更新。首次失败仅为依赖元数据预检查，先前PREPARING/FAILED均有历史证据，当前正式状态TRAINING。


## 2026-10-21 R06-ELC：器官文本的仅蕴涵可学习曲率配置（准备）

用户授权空闲GPU后台20轮。新增cfg_tpc268_organ_entailment_learnable.py继承R06 organ_full，只关闭use_level_contrast、开启learn_curvature并定20轮/初始c1；与R06实际20轮配置仅这两个开关不同，与R08-LC仅prompt_mode不同。CountGD主计数loss保留，辅助目标仅原Lorentz TT/TV .05/.05（含TT负父项/bridge），不修改模型/损失公式，器官主caption仍{organ} .，辅助taxonomy监督保留。

FSC147 CountGD原checkpoint独立model-only初始化，seed42/原训练增强/冻结/匹配、修复mask、三图排除/registry、train batch4/eval实际batch1、原环境/整图推理和AdamW/StepLR均保持。已有nvitop dev元数据差异按前节审计精确记录，63个原依赖版本/native hash及模型/数据/配置源hash严格检查，不安装或同步；数据/标注不改。

新本地脚本run_r06_entailment_learnable_e20.sh固定GPU3（短时其他占用退出后已实查空闲；启动再要求used≤64MiB/free≥20000MiB）、flock、防覆盖/隐式resume，保存源码/资产/初始化hash与曲率协议；CPU实际构造/严格FSC147加载（仅允许12项新辅助状态）及log_c参数/优化器唯一性/梯度/更新，检查模型不用于正式训练。uv离线no-project显式现有主.venv，另进程重新seed42 fresh训练20轮→按val MAE选best→best-val重评，无自动test；main.py/model/loss/Dataset及已有训练脚本均不改。bash和内嵌Python/配置语法检查已过；实际CPU/GPU结果待运行，不提前填写。

ID R06-ELC、run organ_entailment_learnable_seed42_e20。相对R06两项联合改变，不能单独证明关闭contrast或曲率学习的作用；R08-LC为同20轮只改主文本的参照，R05前20轮作无辅助参照。当前HEAD6341592d13575f3626bc70f08604b96ab231f4ef，新配置和文档未提交，运行另存hash/diff；已看既有test后提出，属于探索性对照。完整协议/启动命令同步记于experiment.md，两份docs均更新。


### 2026-10-21 R06-ELC短时GPU占用与自动等待

首次后台PID1385232仅运行预检查：17:29:13启动时GPU3再次有其他任务约4806MiB占用、free19319MiB，因此空闲断言拒绝并退出1；没有模型训练或checkpoint/log.txt，证据保留新run/prelaunch_attempt_1/。不终止或调整其他用户进程。

新脚本改为先完成CPU配置/权重/梯度检查，随后在后台每15秒只读查询GPU3；used≤64MiB且free≥20000MiB时才进入正式TRAINING，新状态WAITING_FOR_GPU、启动前gpu_at_training_start.csv及manifest.idle_gpu_at_training_start记录实际空闲证据。CPU检查模型丢弃，正式进程仍从原FSC147/seed42 fresh初始化，20轮协议不变。此改动只涉及新脚本调度，不改已有训练或模型/数据/环境；两份docs同步记录。重试PID/真实训练状态待核实。


### 2026-10-21 R06-ELC正式训练已启动（2026-10-21T17:32:33.971827+08:00）

run=organ_entailment_learnable_seed42_e20，GPU3，后台PID1386799/训练PID1387249，宿主机已核实PPID1/SID1386799/无TTY，实际GPU3分配训练进程显存9228MiB（核实时瞬时值），nohup+setsid防SSH断连。进入TRAINING于17:31:27，此时GPU3实测used1MiB/free24124MiB，空闲门槛已通过，不与启动前短时任务共享。当前第1/20轮（epoch0），最新batch20/1749，完整轮次0；best/val/test均未知。

预检实际CPU模型严格加载FSC147共享1146项，仅允许新增12项taxonomy参数/持久buffer，unexpected为空；新log_c为Parameter且唯一进入优化器，合成几何梯度0.2475481778383255有限非零，AdamW一步使c由1→0.9998999834060669。正式训练另进程从原FSC147重新seed42初始化，未使用CPU检查状态，也没有从R06最佳或最后一轮续训。

真实GPU前20批loss有限，最新loss=4.9626；包含loss_entail_tt/loss_entail_tv、不含loss_level_contrast，锥非法率0。曲率由初始1更新至日志0.9994，确认实际训练中正在学习，但不推断性能。有效配置与R06只差use_level_contrast True→False及learn_curvature False→True，与R08-LC只差prompt_mode；76/77份原源码/资产hash一致，另外pyproject/uv.lock仅为已审计监控元数据差异，63项原依赖版本及native hash保持匹配。保留该环境身份边界，不声称整体site-packages逐字节相同。

启动HEAD=6341592d13575f3626bc70f08604b96ab231f4ef，新配置/文档及此前工作区修改尚未提交；launch_sources保存新配置/脚本、pyproject/uv.lock和环境审计快照及hash，launch_manifest记录曲率协议、初始化/data/source hash与启动前GPU空闲证据，launch_verified记录进程和首批日志检查。数据/标注、main/model/loss/Dataset及已有运行均未改。训练继续预定20轮，每轮完整val按MAE选best，结束重评999图best-val，不自动test。两份docs同步更新主状态表及本记录，之前PREPARING/首次预检失败均为历史记录；当前正式TRAINING。

进度：`tail -f runs/tpc268_v3_exclude3/launch_organ_entailment_learnable_seed42_e20.log`；启动已成功，无需再次执行。


## 2026-10-22 R08-GD第25轮best测试评估（准备）

本次仅新增本地评估脚本`runs/tpc268_v3_exclude3/run_r08_groundingdino_test.sh`并更新两份docs，不修改模型、损失、数据、配置或训练入口。实际训练已DONE30轮/退出0，独立best-val与逐轮日志一致，最优第25轮val=10.565565565565565/33.0083709466637/0.9048583997504364（999图）。用户授权对该固定权重评估完整2000图test，计划使用实查空闲GPU2、nohup+setsid独立后台运行。

沿用原R协议/同full_taxonomy与3exemplar、修复mask、排除3图和原始annotation，整图推理/阈值/实际batch1均不变；用main.py --eval --eval_split test --resume完整最佳checkpoint，辅助分支eval不参与预测。只增加运行防重复、最佳轮次/协议/源hash/原依赖版本/native/GPU检查和完整测试结果验证，不引入新推理方法。仅对已审计nvitop dev元数据的两个精确hash变更设例外，不覆盖用户修改，不同步安装；其他已有源/数据/初始化hash全部检查，保留环境可比性边界。

测试完成后将复核2000条路径/GT和三指标重算、协议一致性及checkpoint SHA未改变；此时test结果尚未知，不将准备状态写成成功。完整命令和准备记录同步见experiment.md；训练参数和既有实验不改。

### 2026-10-22 R08-GD测试启动核验（09:44 Asia/Shanghai）

最佳权重/有效配置与环境检查已通过；GPU2后台PID2175382、推理PID2175880（PPID1/SID2175382/无TTY），09:44:05 RUNNING，140/2000图。使用epoch24固定c1，checkpoint SHA及源文件hash/63项原依赖版本/native检查实际通过，两个监控元数据hash例外已完整记录；并非训练或初始化重跑。完成状态和test指标待结束验证，当前只确认启动成功；两份docs同步记录。


## 2026-10-22 R08-GD测试完成：指标与核验脚本修正

第25轮best在GPU2完成完整2000图推理，test=19.024/49.7240786742198/0.6219300579384277；val999图=10.565565565565565/33.0083709466637/0.9048583997504364，固定c1。09:52:23独立核对官方2000唯一路径、原annotation点数、非负整数预测及重算三指标，best-val推理和training_protocol一致，checkpoint SHA前后均为806bd3ca6d7e55a806ee8848d269d2ade2c03c714d1ae05d5c99c780fd3a04b5。80份原源/资产hash匹配，两个已审计监控元数据hash例外、63项原依赖版本/native hash再次匹配；不声称整个环境逐字节相同。GPU2于09:52:51实查释放，其他训练继续。

初次推理成功，后处理核验因适配20→30轮时过宽字符串替换将预期`len(rows)==2000`误改为3000而退出1。仅修正新本地脚本该断言为官方2000后重跑核验，未重跑推理或改任何计数/指标、权重、阈值、模型/训练配置/数据。原FAILED和脚本/退出码保留test_final/verification_attempt_1，修正脚本eval_script.sh及verification_recovery.json明确原后处理1、修正核验0；最终DONE/exitcode0。测试指标真实来自原推理输出。

相对同30轮R08，test MAE增加38.9729%、RMSE增加33.6418%、R²降低0.1663863，val三指标也较差；当前单seed下GroundingDINO初始化没有收益。此为初始化来源对照，不是几何消融；R08历史源码归档及监控依赖差异边界继续保留，不扩大结论到几何本身。20轮GD-LC的配对固定曲率参照应按GD前20轮val选择，本次第25轮不是该参照。结果/时间/状态与完整证据同步写入experiment.md及planning/r08_gd_test_results_20261022.json；实现协议保持不变，两份docs同日更新。


## 2026-10-22 R08-GD-LC完成与完整test评估准备

用户要求核查新完成实验并补缺失test，实际新完成为R08-GD-LC（13:23:37 DONE、20轮/退出0），最佳第12轮val999=10.891891891891891/31.309859586195962/0.9143978821993909，原日志与独立best-val一致；test尚无产物。沿用既有GroundingDINO初始化、full_taxonomy及3exemplar、仅TT/TV .05/.05、共享可学习c（初始1/[.1,10]）、contrast关闭、20轮/seed42，CountGD主模型与主损失保留。

本次仅新增本地脚本run_r08_groundingdino_learnable_test.sh，不修改模型/损失/配置/数据/标注。main.py --eval --eval_split test --resume原best权重，在GPU1足够余量下共享测试，启动前至少8192MiB门槛；原推理及数据协议保持，实际eval batch1。uv离线显式原解释器、nohup+setsid/flock和防重复；要求本run训练清单89项源/资产hash完整一致，并复查63项原依赖实际版本/native hash、最佳轮次/配置/c；完整2000图输出后逐项核查路径/GT/整数预测、重算三指标、best-val协议和权重SHA。运行PID/实际test/最佳c待检查，不提前写成功。

R08-LC为同20轮初始化来源参照；固定GD前20轮日志最优第12轮val=10.578578578578579/31.36271065484646/0.9141086453992188，此选择范围区别于GD30轮第25轮，不用不等预算test单独归因曲率。完整设置/状态和命令同步记录experiment.md，两份docs同日更新。

### 2026-10-22 R08-GD-LC测试已正式运行（13:58:47核实）

13:58:28进入RUNNING，后台PID2474953（PPID1/SID2474953/无TTY），推理PID2475436；宿主机实查GPU1约3004MiB，该卡原进程2422347约6224MiB仍在，未终止或改动既有任务。完整best checkpoint严格加载missing/unexpected均为空，epoch11=第12轮；最佳权重c=0.6318109631538391，SHA256=c96f5f5393cf5374b017e47ce16ea7a16fa2964b0e72e87adc7acea53ff39c8f。89份源码/资产hash与本run训练manifest逐项相同，63项原依赖实际版本/native hash一致；源HEAD及dirty diff、实际显存/进程及最佳权重信息留存test_final。训练参数/推理协议未改；当前仅确认启动，完整test指标待结束核验。两份docs同步记录。


## 2026-10-22 R08-GD-LC完整test核验完成（14:07:58）

新完成R08-GD-LC：20轮、GroundingDINO初始化、R full_taxonomy+3exemplar、仅TT/TV .05/.05/可学习c，无contrast，CountGD主损失及原TPC适配保持。按20轮val MAE选第12轮，best c=0.6318109631538391（初始1）；val999=10.891891891891891/31.309859586195962/0.9143978821993909，test2000=15.462/42.50356455639927/0.7237582172256081。

本次新增本地评估脚本的实际运行已13:58:28–14:07:58 DONE/退出0，GPU1共享推理约9分07秒，14:08:30实查测试进程释放显存；既有其他任务继续。严格完整best加载无missing/unexpected，89份源/资产hash等于本训练manifest，63项原依赖版本/native hash不变。路径全且唯一等于官方2000测试集合、GT=原annotation点数，非负整数预测、独立重算三指标和best-val推理/training_protocol均一致；SHA256 c96f5f5393cf5374b017e47ce16ea7a16fa2964b0e72e87adc7acea53ff39c8f 测试前后不变。曲率/初始c/learn_curvature单独保存checkpoint metadata，避免旧协议摘要未含这些字段造成误解。

相对同20轮R08-LC仅改初始化，val三指标退化，test MAE增加38.7971%、RMSE增加29.3285%、R²降低0.1110834；当前单seed下FSC147 CountGD初始化仍较好。与GD30轮比较混入预算/最佳权重选择范围差异；GD前20轮日志最优第12轮的val虽已核实，对应test仍未知，不把不等预算差异当曲率的单因素收益。完整成绩、设置、证据/时间和分析同步experiment.md及planning/r08_gd_lc_test_results_20261022.json；两份docs同日更新，模型/loss/config、数据/标注、环境及在训任务均未改动。


## 2026-10-22 虚拟环境终端提示名称修正（不改变实验协议）

用户已将`.venv/pyvenv.cfg`的prompt改为countgd，但uv创建环境时生成的激活脚本仍嵌入hgic，激活不会重新从pyvenv.cfg读取该字段，因此自动激活继续显示旧名称。本次只把主`.venv/bin/`下activate、activate.bat/csh/fish/nu/ps1/xsh与activate_this.py中的嵌入提示名称统一为countgd，保留其他字节/换行及脚本权限；pyvenv.cfg沿用用户设置。已用独立bash实际激活/退出验证提示名称及原提示恢复。

这仅影响后续shell激活时显示的环境名称，不修改解释器、依赖包、CUDA算子、pyproject/uv.lock、训练/推理代码、数据或实验协议；现有运行进程和实测结果不变，无需新实验基线。已打开终端需要重新source .venv/bin/activate或重开终端才能更新其进程内提示。两份docs同日同步补记。


## 2026-10-23 R06-ELC最终best测试准备

实查R06-ELC已于10月22日16:46:26完成20轮及独立best-val，退出0，按val MAE选最终第18轮（原第5轮best已更新）；val999=10.186186186186186/32.983570393696255/0.9050013136725523，test尚无产物。该run为FSC147 CountGD fresh初始化、organ caption `{organ} .`、3exemplar、主计数损失+TT/TV .05/.05、无contrast、共享可学习c（初始1/[.1,10]）、20轮seed42；不改已有实现和数据协议。

用户授权补test，本次仅新增本地run_r06_entailment_learnable_test.sh与文档记录，main.py --eval --eval_split test --resume完整第18轮best，在实查空闲GPU3后台nohup+setsid/uv离线原解释器运行。新脚本明确20轮/2000图，预检训练89项源/资产hash、63项原依赖版本/native、最佳轮次/配置/最佳实际c，结束核对完整官方2000路径、GT原点数、整数预测、重算三指标、best-val推理/training_protocol和权重前后SHA。最佳c/PID/实测test/完成状态待实际运行；不改模型/loss/config、数据/标注或环境，不引入新推理设置。两份docs同步补记设置/命令/结果准备；与R06涉及两开关联合变化，不能单独归因，保留与R08-LC仅主文本不同的20轮参照。

### 2026-10-23 R06-ELC测试启动核实（10:53:06）

10:52:28进入RUNNING；后台PID3351310/推理PID3351689，宿主机核实PPID1、SID3351310、无TTY，GPU3推理约3004MiB，当前110/2000图。严格加载最终best epoch17=第18轮，无missing/unexpected；best c=0.6272836327552795，SHA256=6be3e8a78cd2df96046055767c3678e5b1e7ea50f392dc5c6c1f6b9f01bbfb47。89份源/资产hash与本run训练manifest一致，63项原依赖实际版本/native hash通过。训练HEAD6341592d13575f3626bc70f08604b96ab231f4ef，评估HEAD92edcb72b986181bdd7c68ca7d74689d77b45466，不能仅凭HEAD差异推断运行代码变化；实际被核验的模型/数据/配置/native源hash均相同。已有shell提示名称countgd改动只影响激活显示，不影响解释器/依赖或运行进程。完整test指标仍待结束核验；两份docs同步补记。


## 2026-10-23 R06-ELC最终best完整测试完成

R06-ELC训练20轮、seed42，10月22日16:46:26完成及独立best-val；最终按val MAE选第18轮（epoch17），已更新先前第5轮best。best c=0.6272836327552795（初始1、TT/TV共享可学习c），val999=10.186186186186186/32.983570393696255/0.9050013136725523，test2000=11.2675/31.181188239064912/0.851329780365249。

原设置保持FSC147 CountGD fresh初始化、organ caption `{organ} .`+3exemplar、主计数损失+TT/TV .05/.05、无contrast。新本地评估脚本在GPU3于10月23日10:52:28–10:58:57 DONE/退出0，实际推理约6分07秒，10:59:39实查已释放显存。完整官方2000唯一路径、GT原点数、非负整数预测、重算三指标和best-val推理/training_protocol全部核验一致；checkpoint SHA256 6be3e8a78cd2df96046055767c3678e5b1e7ea50f392dc5c6c1f6b9f01bbfb47 测试前后不变。89份源/资产hash及63项原依赖版本/native hash与该run训练匹配；训练HEAD6341592、评估HEAD92edcb7（完整值见清单），按实际hash识别源码，不凭HEAD推断代码变化。曲率相关字段额外保存在checkpoint metadata，补足旧摘要边界。

相对R05器官无辅助基线，test MAE增加6.8313%、RMSE增加4.3877%、R²降低0.01223525；val MAE较好而val RMSE/R²较差。R05前20轮日志仍选第12轮同best，保留原30轮实际预算和历史归档边界。相对同20轮R06，test三指标也较差（MAE+4.9702%），本次同时关闭contrast并学习曲率，不能单独归因其中一项。相对同20轮R08-LC，仅主caption不同，test MAE+1.1445%但RMSE−5.1228%/R²+0.01648816；不能称organ全面改善。当前设置未显示测试整体收益，结论限seed42和既有协议，不根据test换epoch/调参。

完整设置、状态、成绩、证据及比较同步experiment.md与planning/r06_elc_test_results_20261023.json；两份docs同日更新。实现改动仅本地评估脚本和记录，不修改模型/loss/config、数据/标注、环境或原训练协议。


## 2026-10-23 R04-ELC：器官+物种主caption配对配置（准备）

用户授权在R06-ELC基础上只改主文本为器官+物种，其余设置一致并找空闲GPU后台运行。新增cfg_tpc268_species_entailment_learnable.py继承cfg_tpc268_organ_entailment_learnable.py，仅设prompt_mode='species'。直接复用已有counting_phrase的`{organ} of {species} .`，不带taxonomy祖先后缀；没有更改Dataset、主模型、loss、数据/标注或既有配置。新ID R04-ELC，run species_entailment_learnable_seed42_e20，正式GPU2（11:27实查空闲）。

继续原FSC147 CountGD model-only fresh初始化，seed42/20轮、主计数损失+Lorentz TT/TV .05/.05、contrast关闭、共享可学习c初始1/[.1,10]、alpha尺度及TT负父/bridge均相同；保留训练辅助分类文本/监督，不能把删除主caption祖先文本误称删除辅助taxonomy。原冻结/增强/优化/FP32/batch/3exemplar/修复mask/三图排除/registry/推理和uv离线原环境不变，不从R06-ELC最佳权重或末轮续训。

新增本地run_r04_entailment_learnable_e20.sh，仅为新run调度，nohup+setsid/flock、防隐式resume/覆盖，正式GPU启动门槛used≤64MiB/free≥20000MiB。启动时核对R06-ELC仅prompt_mode变化、89份原源/资产hash与63项原依赖/native一致；全split caption/token/路径/GT和9例同RNG增强的图像/非文本target检查，CPU严格初始化与曲率参数检查。CPU检查模型丢弃后独立新GPU进程fresh训练20轮→按val MAE选best→独立best-val，不自动test。准备时仅语法检查已过，实际检查/PID/运行状态/实测val/test待执行后记录。

R06-ELC为主要输入配对基线，R08-LC为同20轮full-taxonomy参照；相对R04原实验还存在loss/预算变化，不能只归因文本。完整设置、启动命令与状态同步experiment.md；两份docs同日更新，新配置未提交，运行另存源码/hash/diff，保留探索性单seed边界。

### 2026-10-23 R04-ELC正式训练已启动（11:36:43核验）

run species_entailment_learnable_seed42_e20在GPU2于11:35:38正式TRAINING，启动空闲used4MiB/free24121MiB。后台PID3410506（PPID1/SID3410506/无TTY）、训练PID3411377已宿主机确认，瞬时显存11796MiB；当前epoch0=第1/20轮，batch20/1749，完整轮次0，best/val/test未知。

实际预检通过：相对R06-ELC有效配置仅prompt_mode organ→species（模板organ of species），89项原源/资产hash和63项原依赖版本/native hash一致；相对R08-LC只改变主文本，保留其旧监控元数据两个hash差异的身份边界。train6998/val999/test2000路径/原GT计数/registry相同，全部caption含3exemplar最长17/16/17tokens且单目标未截断；9个含已解析/未解析taxonomy的样本在同seed下增强图像、全部非文本target与Python/NumPy/Torch RNG完全一致。

实际CPU严格FSC147加载1146共享项，仅新增12项taxonomy状态，unexpected空，无TPC权重/optimizer/scheduler/RNG；log_c参数唯一进原优化器组，有限非零合成梯度.2475481778383255使c1→.9998999834060669。CPU模型丢弃后正式新进程fresh seed42/原FSC147初始化。真实GPU前20批loss有限，最新26.4017，TT/TV存在而contrast缺席，非法锥0；c已更新到日志.9996，确认曲率在学习，不能据此推断计数收益。

启动HEAD92edcb72b986181bdd7c68ca7d74689d77b45466，新配置/文档未提交；run保存launch_sources配置/脚本/依赖元数据快照、manifest源/资产hash、数据配对/CPU初始化/实际进程首批证据。继续20轮→val MAE选best→独立best-val，与R06-ELC原训练流程一致，无自动test。两份docs同步状态，既有代码/配置/数据/标注及其他任务不改。


## 2026-10-23 按初始化来源整理结果（实现/协议不变）

用户要求按GroundingDINO与FSC147 CountGD分组整理，experiment.md新增§7.1，列出17个已启动正式run（16完成、R04-ELC训练），并保留R/P文本、名称解析、mask、环境/eval batch和训练预算差异；R09未启动，不冒充实测实验。初始化从各run实际训练参数读取；现有32份val/test均从逐图计数重算MAE/RMSE/R²，并校验999/2000唯一路径等于官方split（代码排除3图）、GT等于原annotation点数、预测非负整数，全通过。缺失单独commit文件的旧run在汇总JSON中记null，不猜测提交。

P04旧主表为10月19日阶段快照，本次从completed.json/30条日志/独立best-val与test的epoch4及逐图计数确认：已于10月20日16:55:13 DONE/退出0，best第5轮，val999=9.821821821821821/25.06903381577472/0.9451221028170154，test2000=12.186/35.250985801818366/0.8099879278313405。仅补齐现存结果，不重跑推理；未在本次重算其历史checkpoint SHA，不添加新的前后SHA声明。R04-ELC 11:46日志第1/20轮/batch280，11:47:36宿主机核实GPU2/PID3411377，完整轮次0、best/val/test仍未知。

匹配初始化对照P02→P03、R08-GD→R08、R08-GD-LC→R08-LC分别同P30轮/固定曲率R30轮/可学习曲率R20轮；换FSC147后test MAE分别降低40.9725%/28.0435%/27.9524%，三组val/test三指标均更好。结论限seed42/既有协议与历史dirty源码/监控元数据身份边界；P01到P03同时变mask不作纯初始化比较，GD30轮与GD-LC20轮不作纯曲率比较，不能跨R/P直接归因。

完整数据快照`runs/tpc268_v3_exclude3/planning/results_by_initialization_20261023.json`保存每项run/实际初始化/状态/轮次/指标/来源路径和核验标志。两份docs同步更新，模型/loss/config、初始化权重、原数据/标注、环境、推理与在训任务均未改；本次只是组织和重新核验已有结果。


## 2026-10-23 初始化分组表展示筛选（实现/实验协议不变）

用户要求从分组表过滤仅器官设置，按主计数caption为organ-only、不含species判定：experiment.md §7.1删除展示R05、R06、R06-ELC、P04四行，保留13个含物种文本实验（GD4/FSC147 9，12完成/1在训），器官+物种的R04-ELC保留。原始17个run、完整主表与results_by_initialization_20261023.json保持，另存派生表results_by_initialization_species_text_20261023.json及筛选条件/来源快照；不新增实测指标或刷新未核验进度。

本次仅筛选结果展示，不改变数据集排除名单、原始数据/标注、模型/loss/config、初始化、训练/推理协议或任何任务，不需要新基线。两份docs同日同步记录。


## 2026-10-23 蕴涵可学习曲率的趋势诊断与调参建议（仅提案）

本次读取R08/R08-LC/R08-GD/R08-GD-LC完整日志及best/latest权重的c、alpha标量，生成共同前20轮曲线和全轮次CSV/分析JSON，记录于runs/tpc268_v3_exclude3/planning/entailment_tuning_20261023。experiment.md §8.6写明测试改善与val MAE未改善的边界、GD20/30预算不匹配，区分原始损失与lambda/warmup后的loss，以及epoch均值c与best checkpoint实际c；没有训练候选实验。

实际TV迅速接近0，FSC-LC第1→2→12→20轮原始TV约.8417/.002472/.0001717/.00001189，但val MAE10.2302/14.2022/10.2352/12.0240。错误species taxonomy节点→query的no_grad训练包含率亦接近100%，不等于test分类错误率/错误单位负loss或主模型坍塌；当前TV只有正例，单增lambda_tv不直接排斥错误关系。可学习c使20轮混合text/query映射径向触顶率FSC11.7348%→.006647%、GD6.7119%→0，非法锥一直0；c与alpha及投影范数在sqrt(c)*alpha尺度中耦合，不能从末轮c≈.63–.65推断独立最佳曲率。分支梯度范数/裁剪率未记录，不能仅据loss约.004%的标量占比判断梯度弱。

提案LC-T01仅lr1e-4→3e-5、LC-T02仅aux warmup1→3、LC-T03仅lambda_tv.05→.01（TT仍.05），均在FSC147 R08-LC全分类/seed42/20轮同协议fresh初始化上独立比较，不先组合。GD保留自己的lr对照，不默认复制FSC最优；后续lambda_tt{.02,.05,.1}和独立曲率lr倍率{.1,1}为条件提案，后者当前无独立参数组需新实现/匹配基线。固定c初值1/范围[.1,10]及其他几何项，contrast关闭时temperature/lambda_contrast不参与目标，不调无效参数。

仅提出今后记录共享feat_map分支梯度、c/alpha/有效尺度、裁剪、分开text/query触顶与验证包含率等诊断，不在本次加入引擎；TV负蕴涵另属机制消融，不混称单纯调参。按val选择，最终配置固定后测test，已看历史test后提案均为探索性。两份docs同日更新建议；模型/loss/config、数据/标注、环境及在训R04-ELC完全不改，提案状态PROPOSED，未来性能未知。


## 2026-10-23 LC-T01学习率配置与后台训练准备

用户指定GPU0执行已建议的第一项调参。新增cfg_tpc268_entailment_learnable_lr3e5.py继承R08-LC，仅设lr=3e-5，run entailment_learnable_lr3e5_seed42_e20；FSC147 model-only fresh初始化、seed42/20轮、R full_taxonomy、TT/TV .05/.05/可学习c初始1/warmup1/无contrast，其余R08-LC设置不变。普通组含log_c/alpha随lr变为3e-5，原特殊linear-projection组仍1e-5；未引入独立曲率组或损失改动。

新本地run_lc_t01_lr3e5_e20.sh固定GPU0（13:16实查空闲），uv离线原解释器/nohup+setsid/flock、防覆盖/隐式resume，启动前核空闲门槛，预检仅lr配置差异、原源/资产/依赖/native/初始化hash与CPU严格FSC147加载及曲率参数/梯度/更新；CPU检查模型不用于正式GPU训练。新配置/脚本语法检查已过，其余真实运行证据/PID/指标待运行后填写。20轮按val MAE选best后独立best-val，不自动test，其他LC-T02/03仅提案。

两份docs同日同步设置/状态；模型/loss/Dataset、旧配置、数据/标注、环境和在训R04-ELC不改。新文件尚未提交，运行以manifest/hash/配置脚本快照识别，不只凭HEAD；本次只授权LC-T01，不同时组合其他候选参数。

### 2026-10-23 LC-T01正式启动核实（13:20）

新run entailment_learnable_lr3e5_seed42_e20于13:19:25进入TRAINING，GPU0启动前used4MiB/free24121MiB。后台PID3507464，PPID1/SID3507464/无TTY，实际训练PID3507881/显存瞬时9296MiB已宿主机核实；当前epoch0=第1/20轮，batch20/1749，完整轮次0，best/val/test未知。

有效配置相对R08-LC仅lr1e-4→3e-5；R06-ELC原89项源/资产hash相同，R08-LC旧77项相同和两个已审计监控元数据差异，63项原依赖实际版本/native hash及初始化SHA均通过。CPU真实FSC147严格加载1146共享项、仅12新taxonomy项、unexpected空；log_c唯一进3e-5普通组，有限非零合成梯度.2475481778383255使c1→.999970018863678。新lr同时作用普通组内curvature/alpha与其他普通参数，特殊linear-projection组保持1e-5，无新增曲率组。

CPU检查模型丢弃，正式新进程fresh seed42/FSC147；首批loss1492.6223与R08-LC首批相同。真实batch20 loss248.9449有限，TT/TV存在、无contrast，lr3e-5、非法锥0；GPU曲率四位日志仍1.0000，不预写非1变化或性能改善。启动HEAD92edcb72b986181bdd7c68ca7d74689d77b45466，新配置/文档未提交，源码身份按快照/hash/diff；run保存manifest/CPU初始化/launch_sources/空闲GPU/实际进程和首批证据。

20轮按val MAE选best后独立best-val，不自动test；调参计划LC-T01改RUNNING，LC-T02/03保留PROPOSED。两份docs同日同步，模型/loss/Dataset/旧配置、数据/标注、环境及GPU2上R04-ELC不改。


## 2026-10-25 R04-ELC与LC-T01完成及最佳权重测试记录

按用户要求核实两组各20条完整train+val日志、训练及独立best-val成功退出：R04-ELC于10月24日10:07:25完成，best第14轮，val999=10.162162162162161/30.63426934755354/0.9180521955583507；LC-T01于10月24日13:13:15完成，best第18轮，val999=9.565565565565565/31.256662953344506/0.9146885175455899。此前两组均无test结果。

新增本地测试入口run_r04_entailment_learnable_test.sh、run_lc_t01_lr3e5_test.sh，复用R06-ELC的严格身份/指标检查，只分别设置本run/config/GPU/best epoch/prompt/lr断言。12:53:30在空闲GPU2/0以nohup+setsid启动，PID380027/380028，宿主机核实PPID1/独立SID/无TTY。测试输出各run/test_final，固定val选出的第14/18轮，不从test重选；流程要求训练manifest源/资产一致、依赖/native核验、测试2000张官方路径/原GT/指标重算与checkpoint SHA前后一致。启动时完整test及最终核验未知，未预填指标；现已完成，实测结果见下文。

模型、loss、配置、初始化、数据及标注、训练/推理协议与环境均不改，无新增训练，不启动LC-T02/03；两份docs同日更新，完整结果已同步主表及下文完成记录。


### 2026-10-25 最终测试与报告核验完成（实现/协议不变）

R04-ELC完成20轮，最低val MAE选第14轮，best c=0.6370097994804382；val999=10.162162162162161/30.63426934755354/0.9180521955583507，test2000=12.3855/35.432873154741486/0.8080220278659153。DONE 2026-10-25T13:00:21+08:00、exitcode0；权重SHA256=7ef4b6c01d7d8b3f8259b4b47d6fef017f42ba261b7d7ae8fbd804c70591548c，测试前后相同。90份源/资产hash完全匹配该run训练manifest，63项原依赖实际版本和native扩展SHA一致；不声称整个环境逐字节相同。

LC-T01完成20轮，最低val MAE选第18轮，best c=0.7562490701675415；val999=9.565565565565565/31.256662953344506/0.9146885175455899，test2000=9.636/28.857338754639173/0.8726639962191843。DONE 2026-10-25T13:01:00+08:00、exitcode0；权重SHA256=5acbecab9f684aae3047c879761658b9ae9a9c3587efd3655cbcd2430f55361f，测试前后相同。91份源/资产hash完全匹配该run训练manifest，63项原依赖实际版本和native扩展SHA一致；不声称整个环境逐字节相同。

两项test均严格加载最终best，全部2000官方路径唯一、集合相同、GT逐图等于原点标注，三指标由逐图预测独立重算；本次同时重核两项val999与R08-LC/R06-ELC参照结果，配置差异严格只有lr或prompt_mode。LC-T01与R08-LC全split caption逐项相同；R04-ELC主caption是organ+species，没有祖先后缀。结果、配置差异、来源、SHA/提交与核验标志保存planning/r04elc_lct01_results_20261025.json，实验报告主表/初始化筛选表/配对分析同步更新。

降低lr的val MAE改善伴随val RMSE/R²退化，不能称全面提升；具体test相对变化见experiment.md §8.7。结论限既有seed42/20轮配对，不据test重选epoch、阈值或后续参数，不作双曲几何独立因果结论。两份docs同日更新，模型/loss/config、数据及标注、初始化、训练/推理协议与环境均不变，未新增训练或启动LC-T02/03。

13:02:10宿主机复查GPU0/2测试进程已退出；全部四卡used1MiB/free24124MiB，无计算进程。未启动LC-T02/03或其他训练。


## 2026-10-25 LC-T01损失趋势诊断与后续调参提案（实现不变）

用户要求结合LC-T01实测结果/损失趋势调整参数。本次只读LC-T01和R08-LC完整20轮日志及已核验best元数据，生成planning/lc_t01_followup_20261025/的CSV/分析JSON/PNG/PDF/提案JSON；原日志SHA保留，曲线区分raw与weighted损失、c的epoch均值和checkpoint标量，不重推test或启动训练。experiment.md新增§8.8，同日同步说明提案与实现边界。

LC-T01前/后10轮val MAE跨轮总体标准差.598194/.186624（原lr1.334904/.568772），第4轮MAE9.56957与最终第18轮9.56557仅差总绝对计数误差4，不能仅因best靠后而增加预算。TV第1/2/4/18/20轮约1.719755/.0772801/.00643081/3.93692e-5/4.46097e-5；前5轮占20轮epoch均值weighted TV标量和99.3477%，不是梯度比例。TV仅正蕴涵，错误taxon包含为detached训练诊断，不能从loss小或包含率近100%直接认定辅助分支梯度太小/太强或主模型坍塌。TT末轮.0427784高于旧lr .0245952而val更好，不强求更小辅助loss。best c=.75624907，20轮径向触顶及非法锥率均0，保持c_init/范围/共享学习形式。

新提案全部以LC-T01为匹配baseline，fresh原FSC147、full_taxonomy/3exemplars/seed42/20轮及原数据/环境/推理不变，分别单改LC-T04 lambda_tv .05→.01（优先）、LC-T05普通lr3e-5→1e-5、LC-T06 aux warmup1→3；不组合，其他TT/TV/lr/warmup保持LC-T01。普通lr包含log_c/alpha，special projection初始lr仍1e-5，不称独立曲率lr消融。原LC-T02/03仍是旧lr1e-4基线上的独立提案，不重新定义；所有新候选PROPOSED_NOT_LAUNCHED，未来指标未知，无新config/launcher/PID。

当前main.py始终StepLR，multi_step_lr/lr_drop_list配置对应分支被注释；lr_drop=5会每5轮反复降，不是第5轮仅降一次。本次只核查并记录，不修改scheduler。新增独立c组、TV负蕴涵或梯度诊断均不在本次实现范围，未来须单独记录实现/匹配基线。两份docs同步，模型/loss/config、数据/标注、初始化、环境、训练/推理协议与既有实测表均不改；提案是在已查看历史test后的探索性建议，后续按val选模型，test不用于继续排序超参。


## 2026-10-25 LC-T04/05/06配置与后台入口准备

用户授权将三个LC-T01单因素候选分别放在GPU0/1/2后台训练。新增cfg_tpc268_entailment_learnable_lr3e5_tv001.py、cfg_tpc268_entailment_learnable_lr1e5.py、cfg_tpc268_entailment_learnable_lr3e5_warmup3.py，均继承LC-T01，仅分别覆盖lambda_tv=.01、lr=1e-5、aux_loss_warmup_epochs=3。实际有效配置与LC-T01 manifest比较，各自严格只有上述单项差异；原TT/TV目标实现、共享可学习c初始1/范围[.1,10]、full_taxonomy/3exemplar/seed42/20轮及训练/推理协议均不变。

新增runs本地共用run_lc_followup_e20.sh与lc_followup_precheck.py，固定LC-T04→GPU0、LC-T05→GPU1、LC-T06→GPU2，各自输出/锁/status/stage/日志，防已有产物覆盖和隐式resume，nohup+setsid脱离SSH；uv离线原解释器，无安装/sync。CPU准备核对原LC-T01全部91源/资产hash、63项原依赖/native/初始化SHA、实际严格FSC147 model-only加载与curvature/alpha参数分组/有限梯度/更新；CPU模型丢弃后新GPU进程重新fresh seed42/FSC147训练，GPU分配前再要求空闲，20轮后best-val不自动test。脚本/内嵌Python语法和有效配置检查已过，准备阶段的实际CPU/GPU检查/PID当时待验证；现已通过并训练，见下节，正式性能仍未知。

四卡实查空闲used1MiB/free24124MiB且无计算进程，输出路径未用，主机RAM足以做三个CPU检查。两份docs同日更新矩阵/准备状态/未知指标及旧提案状态；模型/loss/engine/Dataset代码、旧配置、原数据/标注、初始化与依赖环境不改，保留用户已有工作区修改；LC-T02/03继续未启动。


### 2026-10-25 LC-T04/05/06实际训练启动核验

LC-T04已进入TRAINING 2026-10-25T16:47:05+08:00，GPU0，后台PID441440/训练PID441913；宿主机核实PPID1/SID441440/无TTY、CUDA_VISIBLE_DEVICES与UUID正确，核验时epoch0=第1/20轮/batch50/1749，完整轮次0；首批loss1492.6222、最近loss89.9213有限，正式best/val/test未知。

LC-T05已进入TRAINING 2026-10-25T16:47:05+08:00，GPU1，后台PID441441/训练PID441890；宿主机核实PPID1/SID441441/无TTY、CUDA_VISIBLE_DEVICES与UUID正确，核验时epoch0=第1/20轮/batch50/1749，完整轮次0；首批loss1492.6223、最近loss162.7807有限，正式best/val/test未知。

LC-T06已进入TRAINING 2026-10-25T16:47:04+08:00，GPU2，后台PID441442/训练PID441823；宿主机核实PPID1/SID441442/无TTY、CUDA_VISIBLE_DEVICES与UUID正确，核验时epoch0=第1/20轮/batch50/1749，完整轮次0；首批loss1492.6222、最近loss83.0297有限，正式best/val/test未知。

三组真实有效配置分别严格只差lambda_tv/lr/aux warmup；LC-T01的91份原源/资产hash全部一致，每run新增完整清单96项，原63项依赖版本/native/FSC147 SHA核验通过。实际CPU共享1146项严格加载、只允许12新taxonomy项、无unexpected；c/alpha唯一普通组，非零有限合成c梯度.2475481778383255，各自正确lr使c更新，CPU模型不用于正式训练。正式GPU进程fresh seed42/FSC147、resume空，实际config_args_all匹配manifest、首批主CE/box/xy与LC-T01在打印精度内一致，首批TT/TV权重匹配各自lambda和warmup；GPUc日志仍四位1.0000，不填未知c/性能。

LC-T06只延长TT/TV权重warmup（前三轮末1/3、2/3、1），不改LR日程；LC-T05 c/alpha随普通组1e-5，特殊projection初始1e-5不变。三项20轮/最低val MAE选best/独立best-val，无自动test；各自锁防重复，nohup+setsid独立session脱离SSH。HEAD92edcb72b986181bdd7c68ca7d74689d77b45466，新配置未提交；launch_sources/hash/diff/manifest/launch_verified保存实际源与运行身份，证据汇总planning/lc_t01_followup_20261025/launch_verified_20261025.json。

两份docs同日同步矩阵/状态/未知结果及启动命令，三项计划由提案改RUNNING，LC-T02/03保持未启动；既有模型/loss/engine/Dataset、旧配置、原数据及标注、初始化与环境均不改。


## 2026-10-25 BunchCount 标注核查与计划约束（未训练）

本次仅审计 BunchCount、生成可视化并按用户要求修正一处 exemplar；TPC-268 模型、配置、训练/推理协议和已有运行未改。`data/bunchcount-dataset-0928/annotations.json` 中 `690-pencils.individual_exemplars` 原有4个，仅删除最后一个，现为3个；逐记录深比较确认只有该字段变化，其余全部一致。删除框为 `[28.643259048461914,62.03076934814453,390.4894104003906,628.0615234375]`。原标注备份、前后SHA256及机器可读审计保存在 `runs/bunchcount_audit_20261025/annotations.before.json` 与 `audit.json`。

按显式 `bbox_to_points` 检出185个单成员群体，涉及52张图；群体数按train/val/test为32/3/150。这些为用户指出的错误标注，暂仅列清单和可视化，未删除框、关系、个体点或修改群体exemplar，等待用户决定修正方式。逐群体0-based框/点索引、坐标和split见 `singleton_groups.csv/json`；`index.html` 汇总逐图标注及185个局部放大图，另有4张contact sheet。灰框为其他群体、青点为所有个体、红框和黄圈为单成员群体与其唯一成员。

缺失group_description的3张图全部属于train：`coco-trains-000000115118.jpg`、`coco-trains-000000419882.jpg`、`openimages-trains-0001.jpg`；清单见 `missing_group_description.json`，可视化亦已纳入index，字段保持原样，由用户决定处理方法。

用户明确收紧后续BunchCount计划：保留共享900 queries，使用FSC147 CountGD预训练权重；训练GT>900不排除、不截断、不调整query容量或引入特殊采样/分块，保持全部GT及原始计数。联合目标可能超过900，标准一对一匹配只能匹配至多900个query，未匹配GT不能冒称全部接受了匹配监督；评估仍使用完整GT。群体和个体分别报告MAE/RMSE，禁止合并成一个计数指标。此前1024-query建议撤回。未来数据协议对照需使用相同修正版标注、prompt/exemplar/初始化/增强和推理策略；旧标注实验不可直接混为相同协议。

后续权重选择建议（仅提案，未实施）：保留群体最佳、个体最佳和一个预先约定规则的联合选择checkpoint；联合规则使用两个val MAE各除以固定、相同数据协议的预先指定共享检测baseline的val MAE后等权平均，分母在候选方法比较前固定，并设正epsilon处理零值。此分数仅用于选择同一个模型权重，不作为合并计数性能汇报；不接受加权规则时保留Pareto候选，由用户确定取舍，不能声称存在唯一双任务最优。两个RMSE单独报告，可作预定平局规则，不把四项随意加权。不使用test选择规则或权重。

关系评估建议（仅提案）：先按类型分别一对一匹配群体框和个体点，不使用预测关系参与节点匹配；框采用预先约定IoU阈值，点采用原图坐标下固定容差及敏感性报告。端到端边precision/recall/F1需计入节点漏检/误检导致的FN/FP；另报两端均匹配子集的关系指标和覆盖率、父群体含null准确率及独立个体precision/recall/F1。关系阈值/点容差仅按训练定义或val确定，固定后test；null不计为群体实体。完整成员集合准确率和成员数误差作为补充，不能由计数一致推断关系正确。

本次没有新增训练或评估模型；BunchCount run ID、训练commit、服务器状态和性能均未知，以上清单数目来自本地实际标注审计，非模型实测性能。
