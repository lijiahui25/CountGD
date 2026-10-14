# CountGD → TPC-268 实现记录

更新：2026-10-14。当前代码基线：`0c99a25`（已把三个标注异常样本排除）。本文描述本仓库**实际**实现；训练顺序、命令及实测结果记录在 [experiment.md](experiment.md)。以后每次修改代码、配置或数据协议，同步更新这两个文件。

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

2026-10-12 的本地真实权重 CPU smoke：organ caption 为 `fruit .`，900 query，某样本随机 crop 后 47→38 点、剩 2 个 exemplar；query、`feat_map` 与 Decoder 梯度通路有效。这是**单样本检查**，不等于正式计数结果。数据/几何/比较工具的模块内 smoke 已通过；2026-10-14 又对当前 `0c99a25` 做全量图片/坐标/离线 tokenizer 审计，三个 split 无缺图/坐标错误，主 caption 最长 token（含 exemplar）分别为 organ 8、species 17、full taxonomy 59，taxonomy prefix 最长 48。服务器训练已由用户确认开始；当前本地没有服务器日志，具体 run、commit、loss 和 MAE/RMSE 待核实，见 [experiment.md](experiment.md)。

以后每次仓库工作都检查并更新本文件与 `experiment.md`。实现变化写清“原行为→当前行为→对实验协议的影响”；没有实现变化时记录日期及“实现协议未变”。
