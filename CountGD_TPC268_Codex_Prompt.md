# 给 Codex 的实现提示词：CountGD + TPC-268 + 分层对比学习 + 双曲蕴涵
整理日期：2026-10-12

你现在位于我已经 clone 到本地的 CountGD 项目中。请直接修改这个项目，分步骤完成下面的实现。目标是提高 TPC-268 上的目标计数性能，而不仅是得到好看的层级嵌入或更高的物种分类准确率。

这是实现任务，请不要只给建议、伪代码或计划。先阅读本地源码，再按阶段实现。每阶段说明实际修改的文件、接口和仍存在的输入缺口，然后继续下一阶段，不要反复询问是否继续。不覆盖我的已有修改；遵守本地 AGENTS.md，但“无需单独测试代码”的要求优先于相冲突的普通工作流建议。

## 一、确定的研究范围

1. 基础模型为当前本地 CountGD，不主动改成 CountGD++，不替换 backbone、Feature Enhancer、Decoder、原有预测头或 top-k query 选择策略。
2. 数据集为 TPC-268，使用官方 train/val/test 划分。
3. 主要基线为“3 个视觉 exemplars + 完整 taxonomy 文本”的 CountGD；同时提供 species 文本基线作为辅助对照。所有主要消融采用相同的计数目标文本模板、organ 信息、初始化、训练参数和推理协议。
4. 新增两个训练目标：
   - 按分类层级限制候选、同级文本去重、多正样本的对比学习。
   - 基于 MERU Lorentz 几何的双曲蕴涵：分类文本相邻层级，以及正确计数单位文本到匹配实例 query 的关系。
5. 辅助视觉特征使用最终 Decoder 输出、与 Hungarian 匹配结果一致的 query。不要用整图平均特征代替目标实例，也不要监督所有未匹配 query 为错误物种。
6. 首版以训练时辅助分支实现，推理仍然走原 CountGD 计数路径，不依赖真实点、真实数量、匹配结果或验证集/测试集标签来修正预测。
7. 这里研究的是 TPC-268 的七级生物分类关系，不是 BunchCount 的群体—成员关系。不要照搬“另一个群体中的个体作为负样本”的设计。
8. 不新建 tests/、test_*.py 或 pytest/unittest 测试。确实必要的短小 smoke check 只能放在对应模块的：
   if __name__ == "__main__":
   内，并通过显式参数启动。不要在导入模块时运行检查，不启动完整训练，不下载大数据集或大权重来做检查。正常的训练、验证和计数评估代码属于交付功能，需要实现。

## 二、必须读取和可直接复用的参考资料

A. CountGD
- 论文：https://arxiv.org/abs/2407.04619
- 官方仓库：https://github.com/niki-amini-naieni/CountGD
- 重点文件：
  models/GroundingDINO/groundingdino.py
  models/GroundingDINO/matcher.py
  models/GroundingDINO/transformer.py
  datasets/odvg.py
  datasets/coco.py
  datasets/transforms.py
  datasets/__init__.py
  engine.py
  main.py
  engine_inference.py
  main_inference.py
  models_inference/
  config/
  training.md

公开仓库的 training.md 另有官方训练代码下载入口。请先核对我的本地版本是否已经具备完整训练接口，以本地实际源码为准，不凭网上文件名假设训练包已经存在。

B. TPC-268
- 论文：https://arxiv.org/abs/2603.21229
- 官方仓库：https://github.com/tiny-smart/TPC-268
- 可直接复制并适配：
  https://github.com/tiny-smart/TPC-268/blob/main/tools/tpc268_dataset.py
  https://github.com/tiny-smart/TPC-268/blob/main/tools/tpc268_visualize_dataset.py
- 必须读取的数据格式文件：
  annotations/tpc268_annotations.json
  annotations/tpc268_taxonomy_ids.json
  annotations/tpc268_taxonomy_vectors.json
  splits/tpc268_train.txt
  splits/tpc268_val.txt
  splits/tpc268_test.txt
  splits/tpc268_split.json
- tools/tpc268_generate_benchmark_split.py 仅用于理解官方协议；不要重新生成并替换官方划分。

C. MERU
- 论文：Hyperbolic Image-text Representations，ICML 2023
  https://proceedings.mlr.press/v202/desai23a.html
- 官方仓库：https://github.com/facebookresearch/meru
- 可直接复制几何工具：
  https://github.com/facebookresearch/meru/blob/main/meru/lorentz.py
- 参考投影、曲率和损失：
  https://github.com/facebookresearch/meru/blob/main/meru/models.py
  重点看 MERU.encode_image、encode_text、forward。
- 复用 exp_map0、pairwise_dist、half_aperture、oxy_angle 等必要函数，不引入整个 MERU 模型、CLIP tokenizer、MERU 图像编码器或它的训练框架。

D. 分层对比学习
- Beyond Flat Labels: Level-Restricted Contrastive Learning for Hierarchical Fine-Grained Vision Classification
  https://arxiv.org/abs/2606.21838
  https://zhiyuantao623.github.io/beyond-flat-labels/
- 借鉴同层比较、taxonomy prefix 文本、同级标签去重、多正样本与层级均衡；本项目把其图像级思想适配到 CountGD 的匹配实例 query。
- 默认采用欧氏 cosine 对比 + Lorentz 蕴涵，不声称逐项复现该论文的双曲对比版本。

E. 分类层级蕴涵参考
- Hyperbolic Multimodal Representation Learning for Biological Taxonomies
  https://arxiv.org/abs/2508.16744
- 借鉴分层/stacked entailment 思路。本项目先实现相邻 taxonomy 边，不引入 DNA 分支，也不声称完全复现原论文。

F. 欧氏有向关系对照
- Hyperbolic Entailment Cones for Learning Hierarchical Embeddings，ICML 2018
  https://proceedings.mlr.press/v80/ganea18a.html
- 原文同时给出欧氏与双曲蕴涵锥，可作为相同关系监督的几何对照。

允许把上述 GitHub 文件复制到项目中再做必要修改。请保留原版权、许可证、来源 URL 和版本信息，新增 THIRD_PARTY_NOTICES.md 或沿用现有机制。复制 MERU 文件并不使其自动采用 CountGD 的 MIT 许可证。不复制训练数据、权重或整个外部项目。记录来源 commit；如果只能获得文件 blob SHA，应明确它是 blob SHA。

## 三、阶段 1：审计本地接口并确定最小修改位置

先用 rg 搜索本地实际代码，确认：
- 数据集注册、collate_fn、图像和 exemplar 的变换流程。
- GroundingDINO.forward 中 hs 的维度、最终 hs[-1] 与 pred_logits/pred_boxes 的对应关系。
- 是否存在 denoising query，以及它们如何被切分。
- SetCriterion.forward 中最终层 Hungarian indices 的产生与后续辅助层重匹配。
- matcher 的分类、中心位置与 GIoU 代价。
- engine.py 如何提取 caption、cap_list、exemplars、labels_uncropped，以及如何把 targets 移到 GPU。
- 模型参数、criterion 参数、optimizer、DDP、checkpoint 的构造顺序。
- 训练版 models/ 与推理版 models_inference/ 的差异。

已核对公开代码的两个易错点：
1. engine.py 可能只保留 targets 中的 Tensor 字段。taxonomy 若只以字符串或嵌套 dict 保存会被丢弃。要么使用 Tensor ID + 模型侧 registry，要么显式保留必要 metadata；不要盲目对字符串调用 .to(device)。
2. SetCriterion 的 indices 在 aux_outputs 循环中会被覆盖。必须在最终输出匹配完成后立即保存 final_indices，并用它计算新增损失。

先简要报告本地定位结果，随后直接实施。若本地版本不同，适配真实代码，不照着公开行号硬改。

## 四、阶段 2：实现 TPC-268 数据适配与分类 registry

建议新增 datasets/tpc268.py 与独立的 taxonomy registry 工具；具体路径可按本地结构调整。

### 2.1 图像、点与示例框

- split txt 每行是相对图像路径；图片目录形式为：
  {species_directory}/{organ}/{filename}.jpg
- 官方 annotation 按图像 basename 检索，目标点字段为 points；示例框字段为 box_examples_coordinates。
- points 为 [N,2] 的像素 xy 坐标；示例框为 [M,4,2] 的四角 xy 坐标，转换成像素 xyxy。
- 缺失 annotation 必须报出文件名，不能像通用 loader 一样默认为空标注，从而伪造负样本。
- exemplars 是提示输入，不能加入 N 个计数 GT。官方 dataset 的 target["boxes"] 是示例框，不是所有目标的真实框，禁止直接交给 Hungarian matcher。
- 沿用 CountGD 的点监督表示：将目标点构造成匹配接口所需的很小伪框，中心必须是目标点。优先复用本地 FSC-147 的做法；公开配置的匹配和 L1 主要监督中心，GIoU 权重为 0。若需独立实现，提供 point_box_size_px=2.0 配置，并明确只是点的兼容载体，不监督虚构的物体宽高。
- Resize/flip/crop 必须同步更新图像、点和 exemplars。裁剪后的 GT 按点中心是否在裁剪区域内过滤，不按伪框是否与裁剪相交决定。不能用 exemplar 框数当 GT count。
- targets["boxes"] 对 matcher 应为归一化 cxcywh；targets["exemplars"] 进入 roi_align 时应符合本地模型要求，公开训练代码使用变换后图像上的像素 xyxy。不要把二者混用。
- 初始实现先使用 flip + resize 的稳定适配；确认点和示例框的裁剪语义后再启用本地 crop。所有消融必须采用同样增强。
- 空目标、缺示例框、裁剪后示例框不足 3 个必须有明确策略，不复制无意义 exemplars。固定 3-shot 时优先避免会损坏 exemplars 的裁剪。
- 给出原图 count 与变换后 count；训练用变换后的目标数，整图评估用原始目标数。

建议 target 至少包括：
boxes: FloatTensor[N,4]
points: FloatTensor[N,2]，坐标约定在接口注释中说明
labels: LongTensor[N]，当前单个计数目标通常全 0，不是全局物种 ID
exemplars: FloatTensor[M,4]
labels_uncropped: 与本地 exemplar 插入逻辑兼容
caption、cap_list
image_id、relative_path、orig_size、size
taxonomy_ids: LongTensor[7]，官方每个 rank 的局部 ID
taxonomy_uids: LongTensor[7]，registry 中唯一 ID
taxonomy_valid_mask: BoolTensor[7]
organ_id、count

### 2.2 分类路径与别名

- 固定层级顺序：
  Kingdom, Phylum, Class, Order, Family, Genus, Species。
- taxonomy_vectors 的 key 是学名，value 为七级 ID 向量。
- taxonomy_ids 按层级保存 name -> ID，用其反向映射得到各级真实名称。
- ID 在不同层级可能重复，节点键必须含 rank，例如 (rank, local_id)，不能把所有“ID=1”的节点合并。
- 父子边来自每条官方路径，去重后构图；检查同一节点是否出现冲突父节点。
- organ 从相对路径的目录读取，不通过盲目拆分文件名最后几个 "_" 推断。
- 保留原始文件名物种名与 canonical taxonomy 学名。规范化空格、下划线、Unicode、杂交符号可以用于查找，但不允许用模糊相似度或只匹配 genus 自动认定 species。
- 官方路径和 taxonomy 表可能存在现行学名/异名差异，例如公开 split 出现 Acacia_tortilis，而 taxonomy 表出现 Vachellia tortilis。实现显式 species_aliases.json，并逐条记录依据；无法确认的映射列入 unresolved_taxonomy.json。
- 未解析 taxonomy 的样本仍可做原始计数，辅助层级损失以 valid_mask 跳过；严格模式可要求启动前全部解析。不得用默认分类路径掩盖缺失，也不得静默丢弃计数样本。报告映射覆盖率，不宣称缺映射时完成了全量层级训练。
- 用 train.txt 的真实样本路径建立训练节点集合；split.json 用于交叉核对。不要把 268 个 species-organ 单元误当成 268 个独立物种。
- 全量公开分类表可用于解析标签，但默认训练的正边、负候选和类别原型只来自 train 路径。验证/测试专有节点不参与训练损失；如果未来做全 taxonomy 先验实验，必须另设开关并标明协议。

### 2.3 计数文本与辅助分类文本分开

提供 prompt_mode = species / full_taxonomy：
- species：包含 canonical species 与 organ 的单个目标短语。
- full_taxonomy：包含七级真实名称和 organ 的单个目标短语。
- 首版 full_taxonomy 模板可为：
  "{organ} of {species}; taxonomy: {kingdom}, {phylum}, {class}, {order}, {family}, {genus}, {species} ."
  这是工程模板；不要称它与论文中仅七级名称的模板完全相同。
- 如本地已经有确定的 TPC 模板，沿用并让所有消融一致。
- 不把七级祖先分别写成 7 个由句号分隔的检测类别。caption、cap_list、labels、token positive map、exemplar 插入位置应始终对应一个计数目标。
- 验证 tokenizer 截断是否丢失 species/organ；可把 organ/species 放在前面，但所有模型使用相同顺序。
- 这些点只监督当前 species-organ 目标，不是整图 genus/family/kingdom 的完整数量。绝不通过“替换 caption 为父类别，复用同一批 points”生成祖先计数样本。
- 数据没有完整非目标物种定位标注时，不生成“错误物种数量为 0”的额外计数样本。分类原型负样本只用于匹配目标的类别关系，不等于整图没有该物种。

## 五、阶段 3：新增训练时特征与文本编码分支

### 3.1 匹配实例特征

- 在最终预测对应的 hs[-1] 上取 query，通常维度 [B,Q,C]，以实际源码为准。
- 新增 model outputs 的 taxonomy_aux 字段，包含对齐最终预测顺序的辅助特征和文本 registry 索引。
- 去除 denoising query 后，辅助特征 Q 必须与 pred_logits/pred_boxes 的 Q 完全一致。
- 在 criterion 中用 final_indices 的 src_idx 选 query，用 tgt_idx 查 GT metadata，不能依赖 query 顺序或按最高置信度选择“正实例”。
- 原始 hs 与 CountGD Decoder 不 detach；新增损失必须能回传到实际用于计数的 query。
- 第一版仅最终 Decoder 层计算新损失；不要自动为每一层 aux_outputs、interm_outputs、DN 复制这些损失。

### 3.2 独立分类文本编码

- 复用 CountGD 已有 tokenizer、BERT 和必要的 feat_map，不新建第二个大型文本编码器，不引入 CLIP。
- taxonomy 节点文本逐个独立编码，不从 full caption 中按第几个 token 抽取类别，不把一个学名当成一个 tokenizer token。
- rank-l 节点文本采用明确的 taxonomy prefix：
  "A biological taxon classified as {kingdom}, ..., {rank_l_name}."
- 同一个 rank 节点使用唯一规范 prefix；独立 taxonomy 文本不包含 organ。
- 另外编码计数单位文本：
  "{organ} belonging to {canonical_species}."
  它保留 organ，用于文本到匹配实例的终端蕴涵；organ 不是第八个生物分类 rank。
- 使用 attention mask 排除 padding、特殊 token，做规范的 mean pooling；复用 BERT 时要符合本地生成 attention mask 的接口。
- 每步需要的节点与计数单位先去重，再分块编码，避免对每个 query 重复跑 BERT。
- 允许缓存 tokenization；只有相关编码层全被冻结时才能缓存其原始输出。训练中的 BERT/feat_map/projection 输出不能跨 step detach 缓存。
- 如果冻结 BERT 是配置选项，必须同样应用到所有对照；不能为了辅助分支性能偷偷更换基线的冻结策略。

### 3.3 小型投影头

- 投影头、log_alpha、curvature 等可训练参数注册在 model 下，并在 optimizer 和 DDP 包装之前创建。criterion 尽量只做无参数损失计算，避免参数未进入 optimizer 或未被 DDP 同步。
- query/text 各一个小投影头，输出 D=128，输入维度从本地模型读取，不写死 BERT=768 或 hs=256。
- 得到 raw tangent 向量 u_v、u_t。
- 默认对比学习使用 F.normalize(u_v)、F.normalize(u_t) 的 cosine。
- 双曲分支使用未 L2 归一化的 raw tangent 向量，经各自正尺度 alpha 后 exp_map0。不能把 L2-normalized 对比向量直接当作唯一双曲输入，否则会丢失必要的径向自由度。
- 不增加 7 套计数预测头，taxonomy 分支只是表征监督。

## 六、阶段 4：实现 level-restricted contrastive loss

默认采用欧氏 cosine；以参考论文的同级比较原则为基础，适配到匹配实例。

对每个 rank l：
1. 取有效 matched queries，映射到它们所属的 rank-l 节点。
2. 候选文本节点 C_l 只来自该层。先合并 batch 中重复的节点，必须保留所有正确节点。
3. 默认从训练节点池补充最多 16 个该层不同节点作为负候选；候选数少时全部使用。可优先采样同父兄弟节点，不足时用该层其他节点补齐。采样使用受 seed 管理的 RNG。
4. 一个 query 的正文本是它的 rank-l 节点。同物种、同 genus 或同 family 的不同图像，在对应层级共享正标签，不能作为该层错误负样本。
5. I->T 使用 query 对去重文本候选的交叉熵：
   s_jk = cosine(v_j,t_k) / temperature
   L_vt = -mean_j log softmax_k(s_jk)[correct_node(j)]
6. T->I 只以本 batch 有正 query 的文本节点为 anchor；每个 anchor 的正集合为所有属于它的有效 queries。
   L_tv = -mean_k mean_{j in positives(k)}
          log softmax_over_queries(s[:,k])[j]
   不能用一个对角线标签代表多正样本，也不能让未在本 batch 出现的文本节点成为没有正样本的 anchor。
7. 两个方向取平均，各 rank 再取平均。只对具有至少两种有效 query 标签的层级计算 T->I；I->T 若只有一个候选则返回可回传的零，避免无意义训练。

额外要求：
- 一个 query 在所有 rank 共享同一视觉投影，不强制其靠近错误祖先，也不混合不同 rank 到一个 softmax。
- 按图像先平均 query loss，再按图像平均，避免高数量图像统治损失。T->I 的正例也按“节点内各图像→图像内 queries”分层平均。
- 每图可随机选至多 aux_max_instances=64 个匹配 queries 计算辅助损失；不能删掉原始计数 GT 或改变原始检测损失。空匹配要安全处理。
- 首版使用本 rank 的匹配 queries + 训练文本候选，不做跨 GPU query gather，避免可变长度 gather 错误。DDP 仍需正常同步模型梯度。
- 不依赖大 batch 才产生负样本；补充训练文本原型可使 batch_size=1 下的 I->T 仍有定义。
- 每层记录候选数、有效正例数、loss；不要把无负样本的零损失解释为分类已经学好。
- 同 species 不同 organ 的 query 在 taxonomy 分类上是同类，终端 organ 差异由计数目标文本及原 CountGD 多模态提示保留。本首版不另加 organ 对比损失。

## 七、阶段 5：实现双曲蕴涵与欧氏关系对照

### 5.1 统一 Lorentz 约定

从 MERU 复制必要几何函数，内部统一为：
- c > 0，空间曲率为 -c。
- 输入/返回通常仅保存 D 维 space components；time component 由 sqrt(1/c + ||x||²) 隐式恢复。
- 不在某处保存 D+1 完整坐标后，又交给只接收 D 维 space components 的函数。
- H_v = exp_map0(alpha_v * u_v, c)
  H_t = exp_map0(alpha_t * u_t, c)
- alpha 使用 log 参数表示，初始化参考 MERU 的 D^(-1/2)。
- 首版 c=1 固定，提供 learn_curvature 开关；开启时使用 log_c，并把实际 c 有界化到 [0.1,10]。
- 禁止用 .item() 或 float(c) 参与损失，从而意外切断 curvature 梯度。

定义：
E(parent, child)
  = relu(oxy_angle(parent, child, c)
         - half_aperture(parent, c, min_radius=0.1))

父节点在前、子节点在后。不要写成角度减去 child 的 aperture，也不要把它变成双向对称距离损失。

### 5.2 文本层级损失 L_hyp_tt

- 使用 train taxonomy 的相邻边：
  Kingdom -> Phylum -> Class -> Order -> Family -> Genus -> Species。
- 同一步 batch 正路径和采样训练候选的有效路径均可参与；先去重。
- 分别对六种边类型求平均，再对有效类型平均，避免 genus-species 边数量多而压过高层。
- 补充 Species -> 对应 species-organ 计数单位文本的桥接项，使七级文本结构连接到终端计数表征。
- 桥接只使用训练中实际出现的 species-organ 单元；此单位节点不是额外分类 rank，也不意味着有 organ 层的独立计数标注。
- 把桥接项单独记录为 loss_hyp_unit_bridge，并在 L_hyp_tt 内通过可配置 bridge_weight 合入。它只是 L_hyp_tt 的组成，不要在 engine 再重复加权。
- 第一版不额外对所有祖先-后代重复计算正损失，不强行加入 root 节点。

### 5.3 文本到实例损失 L_hyp_tv

- 对每个 Hungarian 匹配 query，使用其真实 species-organ 计数单位文本：
  E(H_count_unit, H_matched_query)
- 这里“实例”是已标注的果实、花、叶、气孔等计数单位，不必是整株植物，所以不能丢掉 organ。
- 不用整图向量，不监督未匹配 query 的物种，不令每个 query 属于全部文本原型。
- 按图像先平均，再按图像平均；使用与对比学习相同的辅助 query 子集。
- 错误同级文本的判别首版交给 level-restricted contrastive，不再加一套难以区分收益的负蕴涵损失。

### 5.4 数值与梯度

- 在 autocast disabled 区域显式转 float32 计算 exp/sinh/acosh/asin/acos；不要照搬“autocast(dtype=float32)”却误以为已可靠禁用半精度。
- 使用合理 clamp/eps，注意 float32 中 1-1e-8 可能舍入成 1；角度端点 eps 首选 1e-6。
- 显式限制 exp_map0 前 tangent norm 的过大范围，并保留 MERU 的 sinh 稳定处理；按实际源码说明采用的边界。
- log 空间正尺度与曲率做有界约束。不要用 nan_to_num 掩盖错误。
- 记录父节点 aperture、radial distance、正边违反率，以及进入 aperture 无效/饱和区域的比例。尤其注意 sqrt(c)*||parent_space|| < 2*min_radius 时，arcsin clamp 会让 cone 接近半空间；不能把“loss=0”当作层级已正确。
- 无效节点用 mask；空集合返回当前设备上与辅助参数计算图相连的零。DDP 上处理无匹配、无有效 taxonomy 与消融关闭时的未使用参数问题。
- 所有层级损失梯度应到达投影头和匹配 query；BERT 若按配置训练，也应获得文本分支梯度。

### 5.5 欧氏层级对照

为了区分“分类关系监督”和“双曲几何”带来的收益，提供 entailment_geometry=lorentz/euclidean_cones。
- 欧氏版本参考 Ganea 2018 的欧氏锥定义，用相同父子边、unit bridge、文本到实例关系、投影维度、采样和权重。
- 在欧氏 raw embedding x 上可使用 outward axis x 与 (y-x) 的夹角，以及 psi_E(x)=asin(K/||x||) 的有效定义域；先核对原论文常数约定与数值处理，不把 Lorentz 角度公式直接用于欧氏坐标。
- 默认仍为 Lorentz。欧氏关系对照不是无层级监督的普通 cosine 对比；配置与文档要区分清楚。
- 这是对照实现，不拓展成新的大型几何框架。

## 八、阶段 6：接入原 criterion、optimizer 和训练循环

总损失：
L_total = L_CountGD_original
          + lambda_contrast * L_level_contrast
          + lambda_tt * L_entail_tt
          + lambda_tv * L_entail_tv

- 保留本地原 CountGD 损失、Hungarian 代价、预测头和已有辅助层逻辑。
- 新增 loss_level_contrast、loss_entail_tt、loss_entail_tv 到 criterion.weight_dict；只返回 raw loss，由 engine 的现有加权机制乘系数一次。
- 日志统计项如 bridge、aperture、violations 不加入 weight_dict，避免无意参与反向传播。
- 新权重不要自动进入原来“复制 aux 层权重/encoder 权重”的代码。
- 保存 final_indices 后计算新损失，aux 层可以继续原来的重匹配。
- optimizer 创建前建立所有新模块，检查它们按合理参数组纳入；不在 forward 临时新建 nn.Linear 或 nn.Parameter。
- 固定曲率用 buffer；可学习曲率/尺度/temperature 用注册参数。不要对冻结参数添加没有意义的参数组。
- 使用开关时处理 DDP unused parameters；checkpoint 保存、恢复全部新增参数及配置。
- 加载原 CountGD checkpoint 时允许新增辅助参数缺失，但必须明确打印 missing/unexpected keys；只放行预期的新模块差异，不能用 strict=False 静默忽略 backbone/decoder 不匹配。
- 学习率、weight decay、BERT/图像 backbone 冻结与原基线保持一致；新增头的参数组需写清。

建议配置入口（根据本地 config 机制落地，不硬编码路径）：
tpc268_root
tpc268_annotation_file
tpc268_taxonomy_ids_file
tpc268_taxonomy_vectors_file
tpc268_train_split / val_split / test_split
tpc268_species_aliases_file
strict_taxonomy
prompt_mode = full_taxonomy
num_exemplars = 3
use_level_contrast = True
use_taxonomy_entailment = True
entailment_geometry = lorentz
aux_embed_dim = 128
aux_max_instances = 64
negatives_per_level = 16
temperature = 0.07
lambda_contrast = 0.1
lambda_tt = 0.05
lambda_tv = 0.05
bridge_weight = 1.0
curvature_init = 1.0
learn_curvature = False
cone_min_radius = 0.1
aux_loss_warmup_epochs = 1

这些数值只是工程初始设置，不是论文验证的最优参数。warmup 期间辅助权重线性升至目标值，不改变 loss 的 raw logging。原始计数训练参数沿用当前仓库合理配置。

## 九、阶段 7：训练配置、推理与评估接口

至少交付这些可切换配置或等价明确命令：
1. CountGD + species 文本，关闭两种辅助损失。
2. CountGD + full taxonomy 文本，关闭两种辅助损失：主要基线。
3. 主要基线 + level contrast。
4. 主要基线 + Lorentz entailment。
5. 主要基线 + level contrast + Lorentz entailment：完整方法。
6. 主要基线 + level contrast + Euclidean cones：几何对照。

要求：
- 配置 2-6 的输入文本、exemplars、数据划分、初始化及推理计数方法完全一致。
- 开关关闭时跳过相关计算，而不是只把系数置零却还跑全部文本编码。关闭所有辅助模块时，原 CountGD 输入/输出行为应尽量一致。
- 原 config 的 FSC-147 label_list 不能继续充当 TPC-268 全局候选；新 dataset 的 caption/cap_list 应正确驱动单目标计数。
- 如果 main.py 默认注册 COCO evaluator，而 TPC 数据不具备 COCO API，新增正常的计数评估路径，不强造 COCO detection 标注。
- 输出 MAE、RMSE，可输出 R²，并输出每张图的预测数量、GT 数量、species、organ、split。R² 在 GT 方差为零时按明确约定处理。
- 只用 val 选择 checkpoint/阈值，不用 test 调参；best checkpoint 主指标为 val MAE。
- 数量超过 num_queries 的样本不能删点或改 GT；记录数量分布与 query 上限。沿用 CountGD 已有自适应裁剪等协议时，所有方法保持一致，明确评估模式。
- 是否使用 crop、SAM test-time normalization、exemplar 修正必须在命令与文档中显式记录，默认不要新增 SAM 依赖。
- 训练模型在 eval 时不运行辅助文本库和层级损失。
- 本地若使用 models_inference/ 独立模型加载完整方法 checkpoint，确保可兼容新增辅助键并只忽略这些已知键；原推理不需要 taxonomy 投影头。
- 不以真实层级分类准确率、membership 指标替代计数指标；这里无需 BunchCount 成员 AP。
- 数据、权重或 CUDA ops 不在本地时，仍完成所有可独立实现部分，列出准确缺失路径与启动要求，不自动开展长时间下载/训练。

## 十、阶段 8：交付与必要验证

建议新增文件：
datasets/tpc268.py
datasets/tpc268_taxonomy.py（或同等 registry 模块）
models/GroundingDINO/taxonomy_aux.py
models/GroundingDINO/taxonomy_losses.py
models/GroundingDINO/lorentz.py（从 MERU vendor，保留来源）
config/cfg_tpc268_*.py 或同等消融配置
config/datasets_tpc268.json
docs/countgd_tpc268_implementation.md
THIRD_PARTY_NOTICES.md
少量必要的已有接口修改；具体路径以本地架构为准。

不要同时引入密度图分支、祖先计数头、负物种整图计数、图像生成增强、教师模型或自适应新损失。先把这一个明确的研究方案完整实现。

无需编写测试套件。必要时只做：
- 语法编译、导入与配置/路径静态检查。
- 在模块 __main__ 内放一个显式开启的 CPU 几何检查或有真实输入时的单样本前向/反向检查，验证形状、finite loss、梯度连通；确实没条件运行就注明。
- 不伪造数据集评估结果，不声称计数提升或已复现论文结果。
- 交付前查看 git diff，确认没有混入与任务无关的修改。

最终用中文报告：
1. 已实现的分阶段内容和真实文件位置。
2. Dataset -> model auxiliary outputs -> final_indices -> losses -> optimizer -> checkpoint 的数据流。
3. 三项新损失的实际定义、有效样本 mask 与归一化方式。
4. 基线、单项消融、完整方法、欧氏对照的可直接运行命令。
5. 从原 CountGD 权重初始化及恢复新 checkpoint 的命令。
6. 实际执行的最小检查，以及未运行的训练/评估。
7. taxonomy 别名覆盖率、输入缺口、公开协议与工程模板之间的差别。

