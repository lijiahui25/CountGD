# CountGD → TPC-268 实现记录

更新：2026-10-16。实现/数据协议基线：`0c99a25`，当前代码HEAD为`8a26e86`（已把三个标注异常样本排除）。本文描述本仓库**实际**实现；训练顺序、命令及实测结果记录在 [experiment.md](experiment.md)。以后每次修改代码、配置或数据协议，同步更新这两个文件。

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
