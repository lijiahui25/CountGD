# CountGD / TPC-268 阶段实验报告与后续计划

**报告更新：2026-10-25，Asia/Shanghai；LC-T04/05/06已在GPU0/1/2分别后台训练20轮，启动核验时均第1轮/batch50，尚无完整val/test。** R04-ELC及LC-T01最终val/test已补齐，见§5–8；三项新实验设置/启动证据见§8.8及末节。

**2026-10-22补记：R08-GD已完成30轮、best-val及完整test核验，最佳第25轮；test=19.0240/49.7241/0.6219（MAE/RMSE/R²），详见末节。**

实验根目录：`runs/tpc268_v3_exclude3/`。本次评估实查当前HEAD=`92edcb72b986181bdd7c68ca7d74689d77b45466`，工作区存在未提交修改；**当前HEAD不等于每个实验启动时的源码身份**。R06-ELC训练HEAD=6341592，评估HEAD=92edcb7，但训练清单89项源/资产hash完全一致，详见末节。所有指标来自实际日志、最佳checkpoint元数据或计数JSON；没有结果的单元格用“—”，不填推测值。

## 1. 当前结论摘要

- R01–R05、R07、R08、P01、P02、P03均已完成30轮及best-val重评；各自最终test见第7节，均对应val选出的固定权重。
- **R07 contrast-only最终结果为负。** 第16轮best：val=11.0701/36.0906/0.8863，test=18.3190/48.8021/0.6358（MAE/RMSE/R²）。相对同协议R01，test MAE增加44.83%、RMSE增加33.18%，val三指标也退化。本seed、当前实现与超参数下不支持contrast-only的整体计数收益。
- **退化具有分组差异。** R07低计数图像略好，高计数图像和seed器官组明显少计；不是每张图都变差，不能把总指标退化直接等同于已经查明失败机制。
- R02完整辅助方案：val三指标均差于R01；test MAE仅改善2.16%，RMSE/R²退化。R04相对R03：val和test MAE均变差，test RMSE/R²改善。现有结果不支持完整方法全面提升，也不宜抹去局部指标取舍。
- R05在已完成基线中test MAE/RMSE最低，R03的val MAE最低；三组主文本不同且只有seed42，不能宣称organ-only普遍最好，或层级文本天然有害。
- **R08 TT/TV-only未显示整体计数收益。** 最终第12轮best：val=9.9880/29.5085/0.9240，test=13.6890/37.2070/0.7883。相对R01，val MAE仅降0.1501%、RMSE升11.4547%；test MAE升8.2220%、RMSE升1.5384%、R²下降0.0064，测试三指标退化。
- **P02仅修复mask没有带来全面改善。** 第14轮best：val=10.8949/31.2740/0.9146，test=19.2080/51.6365/0.5923；对照P01的test=19.4665/50.4593/0.6107，MAE降1.3279%，RMSE升2.3330%，无法解释与R01的全部差距。
- **P03初始化来源对照显示明显收益。** 完成30轮，第5轮best：val=10.4855/28.1765/0.9307，test=11.3380/35.4983/0.8073。仅相对P02由GroundingDINO换为FSC147 CountGD初始化，val三指标改善，test MAE降低40.9725%、RMSE降低31.2536%、R²增加0.2150；结论限于当前固定P协议/seed42及修复mask条件。
- **P04最终结果已补齐。** 30轮、10月20日16:55:13正常完成，最佳第5轮；器官文本`{organ}.`，val=9.8218/25.0690/0.9451，test=12.1860/35.2510/0.8100。相对P03，val三指标较好，test MAE较差而RMSE/R²略好，不能声称器官文本全面改善。
- **尚不能判定双曲几何无效。** R07没有TT/TV；R08最终test三指标退化，R09欧氏匹配对照未做。P01同时改变初始化、caption、原mask与环境，不能单独归因任何一项，也不能声称已复现论文最终性能。R06及R08-LC均已完成20轮及best-val/test；R09保留原门槛；不根据已查看test临时调参数或选择测试集最佳epoch。

- **10月21日新增：R06未显示organ完整辅助方案的测试收益。** 第5轮best，test=10.7340/30.7243/0.8557，相对R05 MAE增加1.7730%、RMSE增加2.8582%；val MAE略差，val RMSE/R²较好，不能用验证集局部改善代替测试收益。
- **R08-LC相对固定曲率R08测试三指标改善。** 第1轮best，c=0.84096497，test=11.1400/32.8648/0.8348；MAE降低18.6208%、RMSE降低11.6703%、R²增加0.0465253。val MAE仍差2.4253%，因此尚无val MAE选择指标的收益。两组旧基线前20轮与30轮选择相同best，可作等预算选择范围参照；结论限于当前单seed/当前实现，不能宣称普遍有效或根据test继续调曲率。

- **10月22日新增：R08-GD的初始化来源对照未显示收益。** 第25轮best，val=10.5656/33.0084/0.9049，test=19.0240/49.7241/0.6219。相对同30轮固定曲率R08，val三指标退化，test MAE增加38.9729%、RMSE增加33.6418%、R²下降0.1663863；当前单seed下FSC147 CountGD初始化更好。这不是双曲与欧氏几何的配对实验，不能据此归因几何本身；旧R08源码归档及监控依赖元数据差异的边界保留。

- **10月22日新增：R08-GD-LC完成并补齐test。** 第12轮best，c=0.63181096，val=10.8919/31.3099/0.9144，test=15.4620/42.5036/0.7238。相对同20轮的R08-LC仅初始化不同，val三指标均较差，test MAE增加38.7971%、RMSE增加29.3285%、R²下降0.1110834；当前单seed仍支持FSC147 CountGD初始化。GD-LC与GD30轮test的差异混有预算/权重选择范围变化，不能当作曲率单因素结论；固定GD前20轮参照仅核到val，尚无对应test。

- **10月23日新增：R06-ELC未显示器官文本下的测试收益。** 最终best更新为第18轮，c=0.62728363，val=10.1862/32.9836/0.9050，test=11.2675/31.1812/0.8513。相对R05，val MAE降低2.7709%，但val RMSE/R²及test三指标较差，test MAE增加6.8313%；相对同20轮R06，test MAE增加4.9702%、RMSE增加1.4869%。当前“关闭contrast+学习曲率”的组合未改善测试表现，不能单独归因其中一个开关。对同20轮R08-LC（仅主文本不同），test MAE高1.1445%，RMSE低5.1228%，属于指标取舍。

- **10月25日新增：R04-ELC与LC-T01均完成并补齐test。** 最佳第14/18轮，val分别10.1622 / 30.6343 / 0.9181、9.5656 / 31.2567 / 0.9147；test分别12.3855 / 35.4329 / 0.8080、9.6360 / 28.8573 / 0.8727。LC-T01降低lr使val MAE改善6.50%，但val RMSE退化9.19%；test配对结论见§8.7，保留指标取舍与单seed边界。

- **10月25日启动：LC-T04/05/06分别在GPU0/1/2运行。** 以LC-T01为匹配基线，只分别改lambda_tv=.01、普通lr=1e-5、aux warmup=3；其他设置/seed42/20轮相同。正式首批loss及GPU分配已核验，目前完整轮次0，best/val/test未知。

## 2. 模型结构与训练目标有什么修改

### 2.1 基础模型与TPC适配

所有实验沿用CountGD的Swin-B、BERT、Feature Enhancer、Transformer Decoder、900个queries及原预测头；没有另换视觉backbone、语言模型、Decoder或主计数头。默认冻结`backbone.0`和`bert`；共享`feat_map`、Enhancer、Decoder、原预测头等未被冻结的参数按既有参数组训练。基线不启用新增taxonomy辅助分支。

针对TPC点标注新增Dataset、taxonomy registry和整图计数评估入口；2px伪框只承载点中心，匹配及L1只监督中心，GIoU代价/权重为0。原flip/resize/crop策略保留，同步变换点和exemplar；不同长度caption的视觉exemplar插入修复为去padding→插入→重新padding，保留正确attention mask。上述是各组共同的适配，不是仅辅助方法才获得的改动。

因此R01/R03/R05是**当前TPC训练/输入协议下的CountGD基线**，不是对原论文训练配方的逐项复现。三组基线之间的主文本不同。

### 2.2 新增辅助分支

R02/R04在训练时取最终Decoder的对象query（与最终logits/boxes同序），依据最终Hungarian匹配选GT对应query，最多每图抽64个辅助实例；原GT和计数目标不删改。

新增两个模型内注册的投影头：query与辅助文本各一个`Linear(256,256) → GELU → Linear(256,128)`。独立辅助文本复用同一个BERT和共享`feat_map`，按非padding/非特殊token进行mean pooling，按step去重、每块32条编码；没有新BERT/CLIP、LoRA、跨step隐藏特征缓存或每层独立视觉头。辅助文本梯度可进入共享`feat_map`，不能因BERT冻结就声称共享文本通路完全不受影响。

完整目标为：

```text
L_total = L_CountGD + w(step) * [0.1 L_contrast + 0.05 L_TT + 0.05 L_TV]
```

`w(step)`在第一epoch从0线性升至1；三项只加在最终层，不复制到原Decoder辅助层/encoder loss。

| 项目 | 实现 | 边界 |
|---|---|---|
| 分层对比 | 同rank的query↔text cosine对比，train-only负节点，每层最多补16个 | R07只启用该项；不使用Lorentz TT/TV约束 |
| TT蕴涵 | taxonomy相邻正确父子边、错误父节点负项、species→species-organ任务bridge | bridge不是第八级生物分类 |
| TV蕴涵 | 正确计数单位文本→匹配对象query的正蕴涵 | 当前没有额外TV负蕴涵loss；错误父query包含率仅为诊断 |
| Lorentz几何 | 128维space表示，固定曲率参数c=1（曲率−1），合法半径映射、可学习文本/视觉尺度；float32几何 | 候选负父节点最多16个、margin0.1、negative weight1；合法锥率不等于计数收益 |

独立taxonomy文本分支仅在训练时使用；评估跳过该分支，但保留该run对应的主caption与视觉exemplars。最终query始终是图像+提示条件表征，不能把辅助指标称作纯视觉分类性能。

## 3. 输入是什么：主文本模板与辅助文本

所有训练输入为整图（经增强）、0–3个变换后exemplar及单目标主caption；GT点与taxonomy metadata用于训练监督。验证/test固定3个原始exemplar及resize后的整图；GT计数用于算指标，不用于预测数量校正。主caption由已提供的物种/器官/分类metadata构造，模型不是先自行识别物种再生成该文本。

| 模式 | 主caption模板 | 使用实验 |
|---|---|---|
| `full_taxonomy` | `{organ} of {species}; taxonomy: {Kingdom}, {Phylum}, {Class}, {Order}, {Family}, {Genus}, {Species} .` | R01/R02/R07/R08，条件式R09 |
| `species` | `{organ} of {species} .` | R03/R04/R04-ELC |
| `organ` | `{organ} .` | R05、R06、R06-ELC |

从当前registry实际生成的同一物种示例：

```text
fruit of Abutilon indicum; taxonomy: Plantae, Tracheophyta, Magnoliopsida, Malvales, Malvaceae, Abutilon, Abutilon indicum .
fruit of Abutilon indicum .
fruit .
```

无法解析taxonomy的图像，full-taxonomy模式退回species模板，计数监督保留，无效辅助关系跳过。完整taxonomy并非所有图像都提供。器官模板仍是语义文本，**organ-only不是纯视觉CountGD**。

辅助文本与主caption独立：第k级使用累计prefix `A biological taxon classified as {Kingdom}, ..., {rank_k_name}.`；蕴涵方案另编码计数单位文本 `{organ} belonging to {species}.`。例如`A biological taxon classified as Plantae, Tracheophyta.`与`fruit belonging to Abutilon indicum.`。它们是训练目标的节点文本，不会被当成多个待计数类别，也不是eval阶段的额外GT预测校正。

## 4. 实验矩阵与公共设置

| ID | 主文本模式 | 新增辅助目标 | 配置文件 | 配对基线 |
|---|---|---|---|---|
| R01 | full_taxonomy | 无 | `cfg_tpc268_baseline.py` | 自身 |
| R02 | full_taxonomy | contrast + Lorentz TT/TV | `cfg_tpc268_full.py` | R01 |
| R03 | species | 无 | `cfg_tpc268_species.py` | 自身 |
| R04 | species | contrast + Lorentz TT/TV | `cfg_tpc268_species_full.py` | R03 |
| R04-ELC | species（器官+物种名） | 仅Lorentz TT/TV .05/.05，可学习c；contrast关闭 | `cfg_tpc268_species_entailment_learnable.py` | R06-ELC（仅增加主文本中的物种名）；R08-LC（去掉主文本祖先链） |
| R05 | organ | 无 | `cfg_tpc268_organ_baseline.py` | 自身 |
| R06 | organ | contrast + Lorentz TT/TV | `cfg_tpc268_organ_full.py` | R05 |
| R06-ELC | organ | 仅Lorentz TT/TV .05/.05，可学习c；contrast关闭 | `cfg_tpc268_organ_entailment_learnable.py` | R06（两开关组合对照）；R08-LC（主文本对照）；R05基线 |
| R07 | full_taxonomy | contrast-only，权重0.1 | `cfg_tpc268_contrast.py` | R01 |
| R08 | full_taxonomy | Lorentz TT/TV-only，权重0.05/0.05，固定c=1 | `cfg_tpc268_entailment.py` | R01 |
| R08-LC | full_taxonomy | 同R08，TT/TV共享可学习c，初始1 | `cfg_tpc268_entailment_learnable.py` | 固定曲率R08前20轮 |
| LC-T01 | full_taxonomy | 同R08-LC，仅lr=3e-5 | `cfg_tpc268_entailment_learnable_lr3e5.py` | R08-LC（仅普通参数组学习率变化，20轮） |
| LC-T04 | full_taxonomy | Lorentz TT/TV，可学习c；仅lambda_tv=.01；lr3e-5/TT.05/warmup1 | `cfg_tpc268_entailment_learnable_lr3e5_tv001.py` | LC-T01（同seed42/20轮，仅单项变化） |
| LC-T05 | full_taxonomy | Lorentz TT/TV，可学习c；仅普通lr=1e-5；TT/TV .05/.05/warmup1 | `cfg_tpc268_entailment_learnable_lr1e5.py` | LC-T01（同seed42/20轮，仅单项变化） |
| LC-T06 | full_taxonomy | Lorentz TT/TV，可学习c；仅aux warmup=3；lr3e-5/TT/TV .05/.05 | `cfg_tpc268_entailment_learnable_lr3e5_warmup3.py` | LC-T01（同seed42/20轮，仅单项变化） |
| R08-GD | full_taxonomy | 同R08固定c=1的TT/TV；改用GroundingDINO Swin-B初始化 | `cfg_tpc268_entailment.py`，专用初始化入口 | R08（30轮初始化来源对照） |
| R08-GD-LC | full_taxonomy | GroundingDINO初始化，可学习c，仅TT/TV .05/.05 | `cfg_tpc268_entailment_learnable.py`，独立入口 | R08-LC（同20轮，初始化对照）；R08-GD前20轮（曲率对照） |
| R09 | full_taxonomy | contrast + Euclidean TT/TV | `cfg_tpc268_euclidean.py` | R01；几何配对R02 |

| 公共项目 | 实际设置 |
|---|---|
| 初始化 | R系列默认独立从`checkpoints/checkpoint_fsc147_best.pth`开始；R08-GD及R08-GD-LC例外，使用原始GroundingDINO Swin-B；不从其他TPC微调权重初始化 |
| 语言权重 | `checkpoints/bert-base-uncased` |
| 随机种子 / 预算 | seed42，单GPU，默认30epochs；R06、R06-ELC、R04-ELC、R08-LC、R08-GD-LC及LC-T01/04/05/06按用户要求20epochs，FP32，不启用AMP |
| batch / steps | train batch4、drop_last；每完整epoch1749个训练batch；eval实际batch1 |
| 优化 | AdamW；基础LR1e-4、weight decay1e-4、clip0.1；StepLR每10epoch衰减 |
| 冻结 | `backbone.0`和`bert`；900queries，DN实际为0 |
| 训练增强 | 原CountGD flip + 两路resize/crop，最终短边480–800、长边≤1333；crop同步点和exemplar，按batch最少exemplar统一shot |
| 验证/test | 短边800、长边≤1333、3exemplars、整图计数，box/text threshold=0.23/0 |
| 后处理 | 不使用adaptive crop、SAM、exemplar correction |
| 模型选择 | 只按val MAE选best，RMSE/R²报告同一权重的结果；不用test挑epoch/seed/阈值 |

原始split为7000/1000/2000；代码层面统一排除以下三张图，有效**6998/999/2000**，原图片、标注和split文件不修改：

- train：`Malus_domestica/fruit/Malus_domestica_fruit_1.jpg`；
- train：`Musa_sapientum/fruit/Musa_sapientum_fruit_45.jpg`；
- val：`Punica_granatum/fruit/Punica_granatum_fruit_17.jpg`；test没有排除图。

坐标策略=`strict_points_clip_exemplars_v1`：计数点必须有效且在原图内；exemplar ROI与图像取正面积交集，保留全部有效GT。有效taxonomy覆盖train6545/6998、val943/999、test1895/2000；registry fingerprint=`cf080ec256b9f9595a0cd6110b30d80fa84da0d49799217054e682185d79d65d`。原始269个species-organ单元保留；split物种仍有交集，不能统称完全未见物种划分。

### 4.1 P01独立复现协议（不与上述公共设置混用）

第2–4节的FSC147初始化和公共caption协议适用于R01–R09。P01工作树为`runs/tpc268_paper_reproduction_20261017/worktree/`，代码提交`492688c13a25e7bfa9566124ebebab7b99eae627`；从官方GroundingDINO Swin-B初始化，保留b6原始插入后全True mask，不启用辅助损失。使用官方七级名称逗号连接的caption；仅下划线转空格后精确查表，缺链则`Species.`，不使用任何手工异名映射。train/val/test=6998/999/2000，其中完整链6258/943/1895，其余740/56/105只用species；相同三图代码排除。独立Python3.9.19/torch2.2.1/transformers4.39.1，原train及eval batch4，30轮seed42、中心监督及原增强、整图阈值.23/0。作者未公开的配方仍标未知，不能将P01与R01差值当作单一因素效应。

### 4.2 P01/P02/P03/P04控制矩阵

P01/P02/P03均用纯官方七级逗号caption、无链species回退；P04仅相对P03改为organ-only。四组均为无辅助损失CountGD，原数据划分及三图代码排除，无手工异名，旧版锁定环境，train/eval batch4、seed42、30轮预算及统一推理。与R系列的额外organ/species文字、环境和名称解析规则区分。

| ID | 初始化 | exemplar padding/mask | 唯一配对变化 | 运行源码提交 |
|---|---|---|---|---|
| P01 | GroundingDINO Swin-B | b6原版all-True | 公开材料重建基线 | `492688c13a25e7bfa9566124ebebab7b99eae627` |
| P02 | GroundingDINO Swin-B | 去padding→插入→重新padding | 相对P01仅修复mask | `d521714b4515d07688a8686b34a03514842be56c` |
| P03 | FSC147 CountGD | 与P02一致 | 相对P02仅初始化来源；只载model | `2e964cdb9ef1ec6c02f3c4438bf1863ba3eea49b` |
| P04 | 与P03相同 | 与P03一致 | 相对P03仅主caption为`{organ}.` | `fc6ad2e66602b234111f965d3bcac618e68fa408` |

## 5. 实验状态与最佳权重轮次

本节及主表轮次均为**1-based**，原始日志/checkpoint的epoch从0起。完整轮数只统计训练和整轮val都完成的日志；R08/P02已核对30条完整训练+val日志、成功退出状态及最佳权重；P03已核对完整30轮、best checkpoint、成功退出及val/test产物；P04本次重核完成30轮、最佳第5轮及独立best-val/test，历史段落保留其原日期。

| ID | 训练GPU | 状态 | 完整预算与进度 | 最佳权重轮次 |
|---|---:|---|---|---|
| R01 | 0 | DONE | 30/30，best-val及test完成 | 2 |
| R02 | 2 | DONE | 30/30，best-val及test完成 | 3 |
| R03 | 3 | DONE | 30/30，best-val及test完成 | 12 |
| R04 | 3 | DONE | 30/30，best-val及固定快照test完成，最终best SHA相同 | 11 |
| R05 | 0 | DONE | 30/30，best-val及固定快照test完成，最终best SHA相同 | 12 |
| R07 | 2 | DONE | 30/30，best-val及最终test完成，exitcode=0 | 16 |
| R08 | 0（已释放） | DONE | 30/30，best-val及test完成；test于10月19日11:21:15退出0 | 12 |
| P01 | 3（已释放） | DONE | 30/30，best-val及test完成，10月18日19:43:01正常退出 | 2 |
| P02 | 2（已释放） | DONE | 30/30，best-val及test完成；10月19日06:07:41退出0 | 14 |
| P03 | 3（已释放） | DONE | 30/30，best-val及test完成；10月20日03:17:34退出0 | 5 |
| P04 | 2（原训练设备；已结束） | DONE | 30/30、best-val及test完成；10月20日16:55:13退出0，本次重核 | 5 |
| R06 | 3（测试已结束） | DONE | 20/20，best-val及test完成；10月21日11:55:28退出0 | 5 |
| R08-LC | 1（测试已结束） | DONE | 20/20，best-val及test完成；10月21日11:55:52退出0 | 1 |
| R08-GD | 2（已释放） | DONE | 30/30、best-val及完整test完成；10月22日09:52核验通过；后处理检查修正见末节 | 25 |
| R08-GD-LC | 1（测试进程已释放） | DONE | 20/20、best-val及完整test完成；10月22日14:07:58退出0；best c=0.63181096 | 12 |
| R06-ELC | 3（已释放） | DONE | 20/20、best-val及完整test完成；10月23日10:58:57退出0；best c=0.62728363 | 18 |
| R04-ELC | 2（已释放） | DONE | 20/20、best-val及test完成；DONE 2026-10-25T13:00:21+08:00，退出0；best c=0.63700980 | 14 |
| LC-T01 | 0（已释放） | DONE | 20/20、best-val及test完成；DONE 2026-10-25T13:01:00+08:00，退出0；best c=0.75624907 | 18 |
| LC-T04 | 0 | RUNNING（10月25日启动核验） | 第1/20轮，batch50/1749，完整轮次0；独立后台训练 | — |
| LC-T05 | 1 | RUNNING（10月25日启动核验） | 第1/20轮，batch50/1749，完整轮次0；独立后台训练 | — |
| LC-T06 | 2 | RUNNING（10月25日启动核验） | 第1/20轮，batch50/1749，完整轮次0；独立后台训练 | — |
| R09 | — | BLOCKED | 尚未启动，门槛保留 | — |

R07最终test于2026-10-17 22:36:54结束；第1轮旧test另列为历史快照，不替换第16轮最终结果。

## 6. 验证集性能

**指标全部对应各自val MAE最低的同一个权重；RMSE不是另挑最低轮次。** MAE越低越好；RMSE更重罚大错误；R²相对该集合均值预测基线计算，不是准确率。999张val与2000张test数量分布不同，R²不作跨split直接比较。

| ID | 最佳轮次 | 图像数 | MAE ↓ | RMSE ↓ | R² ↑ | 证据状态 |
|---|---:|---:|---:|---:|---:|---|
| R01 | 2 | 999 | 10.0030 | 26.4758 | 0.9388 | best权重独立重评完成 |
| R02 | 3 | 999 | 10.6867 | 29.0248 | 0.9264 | best权重独立重评完成 |
| R03 | 12 | 999 | 9.6707 | 28.6010 | 0.9286 | best权重独立重评完成 |
| R04 | 11 | 999 | 10.7818 | 32.4995 | 0.9078 | 最终best权重独立重评完成 |
| R05 | 12 | 999 | 10.4765 | 30.3528 | 0.9196 | 最终best权重独立重评完成 |
| R07 | 16 | 999 | 11.0701 | 36.0906 | 0.8863 | 最终best独立重评及逐图重算一致 |
| R08 | 12 | 999 | 9.9880 | 29.5085 | 0.9240 | 最终best独立重评；逐图重算与checkpoint核对通过 |
| P01 | 2 | 999 | 10.9339 | 26.8876 | 0.9369 | 最终best独立重评完成 |
| P02 | 14 | 999 | 10.8949 | 31.2740 | 0.9146 | 最终best独立重评；逐图重算与checkpoint核对通过 |
| P03 | 5 | 999 | 10.4855 | 28.1765 | 0.9307 | 最终best独立重评；checkpoint/逐图重算核验通过 |
| P04 | 5 | 999 | 9.8218 | 25.0690 | 0.9451 | 最终best独立重评；日志/完成元数据/逐图重算一致 |
| R08-LC | 1 | 999 | 10.2302 | 28.6251 | 0.9284 | 20轮完成，best权重独立重评完成 |
| R08-GD | 25 | 999 | 10.5656 | 33.0084 | 0.9049 | 30轮完成；最佳权重独立重评，与逐轮日志一致 |
| R06 | 5 | 999 | 10.6406 | 26.0450 | 0.9408 | 20轮完成，best权重独立重评完成 |
| R08-GD-LC | 12 | 999 | 10.8919 | 31.3099 | 0.9144 | 20轮完成，独立best-val与完整训练日志一致 |
| R06-ELC | 18 | 999 | 10.1862 | 32.9836 | 0.9050 | 20轮完成，独立best-val与逐轮日志一致 |
| R04-ELC | 14 | 999 | 10.1622 | 30.6343 | 0.9181 | 20轮完成；独立best-val、checkpoint/日志及逐图重算一致 |
| LC-T01 | 18 | 999 | 9.5656 | 31.2567 | 0.9147 | 20轮完成；独立best-val、checkpoint/日志及逐图重算一致 |
| LC-T04 | — | — | — | — | — | 正式训练中，完整轮次0，尚无完整val |
| LC-T05 | — | — | — | — | — | 正式训练中，完整轮次0，尚无完整val |
| LC-T06 | — | — | — | — | — | 正式训练中，完整轮次0，尚无完整val |
| R09 | — | — | — | — | — | 尚未训练，无性能 |

R01–R05的训练best日志、checkpoint的epoch/best_val_mae与独立重评一致；R04/R05最终999张best-val逐图MAE/RMSE/R²已重新计算核验。R07短程约15步技术检查不能混入正式实验表；当前best来自正式第16轮。

历史记录：2026-10-16约15:39核对R04/R05/R07的best快照为第11/12/1轮，checkpoint的best_val_mae均与正式log.txt对应轮次一致。R07当时第2–4轮MAE分别为13.7167、14.2322、13.2993；10月17日已更新为第16轮。

## 7. 测试集性能

均用**验证集选出的best权重**，完整test2000张，没有排除任何test图片。R01/R03于2026-10-15、R02于2026-10-16由用户明确要求评估；不根据test重新选权重或改阈值。

| ID | 使用权重轮次 | 图像数 | MAE ↓ | RMSE ↓ | R² ↑ | 状态 |
|---|---:|---:|---:|---:|---:|---|
| R01 | 2 | 2000 | 12.6490 | 36.6432 | 0.7947 | DONE，退出码0 |
| R02 | 3 | 2000 | 12.3755 | 37.9426 | 0.7799 | DONE，退出码0 |
| R03 | 12 | 2000 | 12.5750 | 37.7194 | 0.7824 | DONE，退出码0 |
| R04 | 11 | 2000 | 13.6800 | 36.0976 | 0.8008 | DONE；快照SHA256与最终best完全一致 |
| R05 | 12 | 2000 | 10.5470 | 29.8706 | 0.8636 | DONE；快照SHA256与最终best完全一致 |
| R07最终best | 16 | 2000 | 18.3190 | 48.8021 | 0.6358 | DONE，退出码0；完整逐图与SHA核验通过 |
| R07旧快照（历史） | 1 | 2000 | 13.3415 | 36.7346 | 0.7937 | 阶段性旧权重，不用于最终同预算比较 |
| P01 | 2 | 2000 | 19.4665 | 50.4593 | 0.6107 | DONE，退出码0；逐图独立核验通过 |
| P02 | 14 | 2000 | 19.2080 | 51.6365 | 0.5923 | DONE，退出码0；路径/GT/三指标独立重算通过 |
| R08 | 12 | 2000 | 13.6890 | 37.2070 | 0.7883 | DONE，退出码0；完整路径/GT/三指标/权重SHA核验通过 |
| P03 | 5 | 2000 | 11.3380 | 35.4983 | 0.8073 | DONE，退出0；官方集合/GT/三指标独立核验通过 |
| R06 | 5 | 2000 | 10.7340 | 30.7243 | 0.8557 | DONE，退出0；完整集合/GT/指标/权重SHA核验通过 |
| R08-LC | 1 | 2000 | 11.1400 | 32.8648 | 0.8348 | DONE，退出0；完整集合/GT/指标/权重SHA核验通过 |
| R08-GD | 25 | 2000 | 19.0240 | 49.7241 | 0.6219 | DONE；完整路径/GT/独立指标/权重SHA核验通过；修正核验脚本后完成 |
| R08-GD-LC | 12 | 2000 | 15.4620 | 42.5036 | 0.7238 | DONE，退出0；完整路径/GT/重算指标/权重SHA核验通过 |
| R06-ELC | 18 | 2000 | 11.2675 | 31.1812 | 0.8513 | DONE，退出0；完整路径/GT/重算指标/权重SHA核验通过 |
| R04-ELC | 14 | 2000 | 12.3855 | 35.4329 | 0.8080 | DONE，退出0；官方集合/GT/指标重算/权重SHA核验通过 |
| LC-T01 | 18 | 2000 | 9.6360 | 28.8573 | 0.8727 | DONE，退出0；官方集合/GT/指标重算/权重SHA核验通过 |
| LC-T04 | — | — | — | — | — | 正式训练中，无test |
| LC-T05 | — | — | — | — | — | 正式训练中，无test |
| LC-T06 | — | — | — | — | — | 正式训练中，无test |
| P04 | 5 | 2000 | 12.1860 | 35.2510 | 0.8100 | DONE；官方集合/GT/逐图指标重算通过 |
| R09 | — | — | — | — | — | 未启动，无test |

R01/R02/R03共六份val/test结果已从逐图计数JSON独立重算MAE、RMSE、R²，与metrics文件一致，无重复图片；此前test核验图片集合与官方test一致、GT等于原annotation点数。

| ID | test GPU | 时间（Asia/Shanghai） | 退出码 | 说明 |
|---|---:|---|---:|---|
| R01 | 0 | 2026-10-15 18:59:54–19:07:20 | 0 | 完整2000图 |
| R06 | 3 | 2026-10-21 11:48:35–11:55:28 | 0 | 第5轮best，完整2000图及核验 |
| R08-LC | 1 | 2026-10-21 11:48:35–11:55:52 | 0 | 第1轮best，完整2000图及核验 |
| R06-ELC | 3 | 2026-10-23 10:52:28–10:58:57 | 0 | 第18轮best，完整2000图；实际推理约6分07秒 |
| R08-GD-LC | 1 | 2026-10-22 13:58:28–14:07:58 | 0 | 第12轮best，完整2000图；共享GPU，实际推理约9分07秒 |
| R08-GD | 2 | 2026-10-22 09:44:05–09:51:24推理；09:52:23修正核验通过 | 推理0；初次后处理1，修正核验0 | 第25轮best，完整2000图；未重跑推理，原失败状态保留 |
| R02 | 1 | 2026-10-16 10:29:53–10:40:55 | 0 | 与其他任务共享GPU，峰值显存1584MiB |
| R03 | 3 | 2026-10-15 17:26:54–17:33:34 | 0 | 完整2000图 |
| R04 | 3 | 2026-10-16 15:40:32–15:50:52 | 0 | 部分训练预算best快照，完整2000图 |
| R05 | 0 | 2026-10-16 15:40:32–15:51:14 | 0 | 部分训练预算best快照，完整2000图 |
| R07 | 2 | 2026-10-16 15:40:32–15:52:43 | 0 | 部分训练预算best快照，完整2000图 |
| R07最终best | 2 | 2026-10-17 22:29:35–22:36:54 | 0 | 第16轮固定权重，完整2000图 |
| P02 | 2 | 2026-10-19 06:07:41整条pipeline结束 | 0 | 第14轮固定权重，完整2000图；单独test起止未核实，不填估计 |
| R08 | 0 | 2026-10-19 11:13:24–11:21:15 | 0 | 第12轮最终best，完整2000图；实际推理日志约7分15秒 |
| P03 | 3 | 2026-10-20 03:11:20–03:17:34 | 0 | 原pipeline自动测试；第5轮best、完整2000图 |

2026-10-16阶段性test：按用户明确要求，15:40:32在GPU3/0/2并行评估R04/R05/R07当时val选出的best（第11/12/1轮），训练继续运行。启动前GPU剩余显存约12.7/6.9/7.2GiB（GPU0/2/3），此前同协议eval峰值约1.6GiB。每项输出单独保存为`<run>/test_snapshot_20261016_153930/`；使用复制并读取验证过的`checkpoint_best_snapshot.pth`，保存SHA256、快照时间/epoch/val指标、config及工作区代码diff，避免训练刷新best改变评估对象。后台进程使用独立session，日志/status/exitcode留在输出目录，不依赖SSH。清单见[parallel_test_snapshot_20261016_153930.json](../runs/tpc268_v3_exclude3/planning/parallel_test_snapshot_20261016_153930.json)。这些结果属于当前部分训练预算的快照，不替代最终30轮模型；不使用test挑epoch、阈值或后续参数。推理沿用原caption、3exemplars、整图、阈值0.23/0及2000张test；仅设置CPU线程数为2以控制并行资源占用。

15:53核验通过：三个快照的SHA256未改变；逐图路径各有2000张且唯一，与官方test清单一致；每张GT与原annotation点数一致；MAE/RMSE/R²均独立重算吻合。核验及配对结果见[verified_test_snapshot_20261016_153930.json](../runs/tpc268_v3_exclude3/planning/verified_test_snapshot_20261016_153930.json)。PyTorch峰值allocated为R04/R05/R07=1584/1583/1584MiB，nvidia-smi进程占用约3004MiB，各卡仍有余量；完成后测试进程释放显存，原GPU0/2/3训练进程仍在。没有修改正在运行的训练配置或数据。

### 7.1 按初始化来源整理：保留物种文本的实验（2026-10-25）

展示筛选按**主计数文本**判断：排除仅含器官词、不含物种名的R05、R06、R06-ELC、P04，保留“器官+物种名”与全分类文本设置。当前展示17个实验（GroundingDINO 4个、FSC147 CountGD 13个），原14个已完成训练、best-val及test；新LC-T04/05/06已在GPU0/1/2分别训练（第1/20轮，完整轮次0，best/val/test未知）。R04-ELC与LC-T01状态/指标在10月25日从实际产物独立重核并补测，其余行沿用10月23日已核验快照。完整21个已启动实验（含四个organ-only）保留在前面主表；历史汇总JSON保持原时点，新两项与匹配对照的核验见planning/r04elc_lct01_results_20261025.json。

表中指标依次为**MAE / RMSE / R²**；“预算/最佳轮”均为1-based，最佳轮按val MAE选择，test使用相应固定权重。未完成的新run保留空值；R09未启动，不作为实测实验纳入初始化分组。

**R/P协议需区分**：R完整文本为`{organ} of {species}; taxonomy: ... .`，species模式为`{organ} of {species} .`，organ为`{organ} .`；P完整文本为官方七级名称逗号串、缺链只用species，P04为`{organ}.`。P与R还存在名称解析规则、依赖环境及eval batch等差异，分到同一初始化组不代表能直接单因素比较。所有组均seed42/3视觉exemplar、同3图代码排除，val999/test2000；不根据test选择权重。

**GroundingDINO 初始化**

| 实验 | 主文本 | 辅助损失/曲率 | 预算/最佳轮 | 验证 MAE / RMSE / R² | 测试 MAE / RMSE / R² |
|---|---|---|---:|---|---|
| P01 | 官方七级文本（P） | 无；原all-True mask | 30/2 | 10.9339 / 26.8876 / 0.9369 | 19.4665 / 50.4593 / 0.6107 |
| P02 | 官方七级文本（P） | 无；修复mask | 30/14 | 10.8949 / 31.2740 / 0.9146 | 19.2080 / 51.6365 / 0.5923 |
| R08-GD | 器官+物种+分类链（R） | TT/TV，固定c | 30/25 | 10.5656 / 33.0084 / 0.9049 | 19.0240 / 49.7241 / 0.6219 |
| R08-GD-LC | 器官+物种+分类链（R） | TT/TV，可学习c | 20/12 | 10.8919 / 31.3099 / 0.9144 | 15.4620 / 42.5036 / 0.7238 |

**FSC147 CountGD 初始化**

| 实验 | 主文本 | 辅助损失/曲率 | 预算/最佳轮 | 验证 MAE / RMSE / R² | 测试 MAE / RMSE / R² |
|---|---|---|---:|---|---|
| R01 | 器官+物种+分类链（R） | 无 | 30/2 | 10.0030 / 26.4758 / 0.9388 | 12.6490 / 36.6432 / 0.7947 |
| R02 | 器官+物种+分类链（R） | 对比+TT/TV，固定c | 30/3 | 10.6867 / 29.0248 / 0.9264 | 12.3755 / 37.9426 / 0.7799 |
| R03 | 器官+物种（R） | 无 | 30/12 | 9.6707 / 28.6010 / 0.9286 | 12.5750 / 37.7194 / 0.7824 |
| R04 | 器官+物种（R） | 对比+TT/TV，固定c | 30/11 | 10.7818 / 32.4995 / 0.9078 | 13.6800 / 36.0976 / 0.8008 |
| R07 | 器官+物种+分类链（R） | 仅对比 | 30/16 | 11.0701 / 36.0906 / 0.8863 | 18.3190 / 48.8021 / 0.6358 |
| R08 | 器官+物种+分类链（R） | TT/TV，固定c | 30/12 | 9.9880 / 29.5085 / 0.9240 | 13.6890 / 37.2070 / 0.7883 |
| R08-LC | 器官+物种+分类链（R） | TT/TV，可学习c | 20/1 | 10.2302 / 28.6251 / 0.9284 | 11.1400 / 32.8648 / 0.8348 |
| LC-T01 | 器官+物种+分类链（R） | TT/TV，可学习c；lr3e-5 | 20/18 | 9.5656 / 31.2567 / 0.9147 | 9.6360 / 28.8573 / 0.8727 |
| LC-T04 | 器官+物种+分类链（R） | TT/TV，可学习c；仅lambda_tv=.01；lr3e-5/TT.05/warmup1 | 20/—（训练中） | — | — |
| LC-T05 | 器官+物种+分类链（R） | TT/TV，可学习c；仅普通lr=1e-5；TT/TV .05/.05/warmup1 | 20/—（训练中） | — | — |
| LC-T06 | 器官+物种+分类链（R） | TT/TV，可学习c；仅aux warmup=3；lr3e-5/TT/TV .05/.05 | 20/—（训练中） | — | — |
| R04-ELC | 器官+物种（R） | TT/TV，可学习c | 20/14 | 10.1622 / 30.6343 / 0.9181 | 12.3855 / 35.4329 / 0.8080 |
| P03 | 官方七级文本（P） | 无 | 30/5 | 10.4855 / 28.1765 / 0.9307 | 11.3380 / 35.4983 / 0.8073 |

**只比较匹配设置的初始化对照**（箭头为GroundingDINO→FSC147 CountGD）：

| 配对 | 协议与预算 | test MAE变化 | test RMSE变化 | test R²变化 |
|---|---|---:|---:|---:|
| P02 → P03 | P、修复mask、无辅助、30轮 | 19.2080 → 11.3380（-40.97%） | 51.6365 → 35.4983（-31.25%） | 0.5923 → 0.8073 |
| R08-GD → R08 | R、TT/TV固定c、30轮 | 19.0240 → 13.6890（-28.04%） | 49.7241 → 37.2070（-25.17%） | 0.6219 → 0.7883 |
| R08-GD-LC → R08-LC | R、TT/TV可学习c、20轮 | 15.4620 → 11.1400（-27.95%） | 42.5036 → 32.8648（-22.68%） | 0.7238 → 0.8348 |

三组配对中FSC147 CountGD初始化的val/test三指标均较好，当前seed42结果支持其作为TPC微调起点；不扩大为任意任务/随机种子上的结论，保留旧run dirty源码归档及监控元数据差异的可重建性边界。P01与P03同时改mask和初始化，不作为纯初始化对照；GD30轮与GD-LC20轮不作为纯曲率对照。当前展示的FSC147初始化R系列实验中，LC-T01的test MAE最低（9.6360）；这只是筛选后不同文本/损失/预算结果的描述性排序，不推出单因素因果结论。

筛选后的机器可读表：`runs/tpc268_v3_exclude3/planning/results_by_initialization_species_text_20261023.json`；完整汇总与证据路径仍为`runs/tpc268_v3_exclude3/planning/results_by_initialization_20261023.json`。10月23日汇总快照保持；10月25日补测上述两组并更新文档，不改变初始化、数据/标注、模型/loss/config或训练任务。

R04-ELC与LC-T01新增实测依据各run的20轮日志、独立best-val、test_final/checkpoint_metadata.json与verified.json；原10月23日分组JSON保留历史快照，不覆盖历史结果。10月25日两项及匹配对照详见新汇总JSON；未在本次重新推理其余实验。

## 8. 实验结果分析

### 8.1 同文本、同初始化、同预算的辅助训练配对

`Δ=method−matched baseline`，负的MAE/RMSE差值为改善。只报告val选出的同一权重，不从test更换epoch。

| 配对 | split | ΔMAE | ΔRMSE | ΔR² | 支持的观察 |
|---|---|---:|---:|---:|---|
| R02−R01 | val | +0.6837 | +2.5490 | -0.0124 | 完整辅助方案验证三指标退化 |
| R02−R01 | test | -0.2735 | +1.2994 | -0.0148 | MAE小幅改善，RMSE/R²退化 |
| R04−R03 | val | +1.1111 | +3.8985 | -0.0208 | 同species文本，验证三指标退化 |
| R04−R03 | test | +1.1050 | -1.6218 | +0.0183 | MAE退化，RMSE/R²改善 |
| R07−R01 | val | +1.0671 | +9.6148 | -0.0525 | contrast-only最终验证退化 |
| R07−R01 | test | +5.6700 | +12.1588 | -0.1589 | contrast-only最终测试三指标退化 |
| R08−R01 | val | -0.0150 | +3.0327 | -0.0148 | TT/TV-only最终MAE微降，RMSE/R²退化 |
| R08−R01 | test | +1.0400 | +0.5637 | -0.0064 | TT/TV-only最终测试三指标退化 |
| P02−P01 | val | -0.0390 | +4.3864 | -0.0223 | 仅mask修复，MAE微降，RMSE/R²退化 |
| P02−P01 | test | -0.2585 | +1.1772 | -0.0184 | 仅mask修复，test也未全面改善 |
| P03−P02 | val | -0.4094 | -3.0975 | +0.0161 | 修复mask条件下，仅初始化来源不同，三指标改善 |
| P03−P02 | test | -7.8700 | -16.1383 | +0.2150 | 完整30轮/同val规则，FSC147初始化test三指标改善 |

**支持的结论**：当前seed42、初始化、输入、系数与预算下，R07的contrast-only没有整体计数收益，且test退化较大；R02/R04完整方法也没有获得配对val收益，test各指标存在取舍。现有证据不支持把完整方法写成“全面改善CountGD”。这些是当前设置的实测结论，不是统计等效检验，也不是所有对比学习/层级方法无效的证明。

R02测试优于R07，只是本seed的组合观察；它尚不能证明双曲几何本身带来收益。R08 TT/TV-only已完成，最终val相对R01仅MAE降低0.0150（0.1501%）、RMSE增加3.0327（11.4547%）；最终test MAE增加1.0400（8.2220%）、RMSE增加0.5637（1.5384%）、R²下降0.0064。当前层级蕴涵设置在本seed没有整体计数收益；但R09及同TT/TV-only目标的欧氏对照仍缺，不能从R07（没有TT/TV）的失败推出双曲蕴涵普遍无效，也不能从组合结果拆出几何效应。

### 8.2 R07退化集中在哪里：已有逐图预测的描述性诊断

完整2000张test，R07相对R01：730张绝对误差改善、693张变差、577张不变；总体MAE仍增加5.67，因为变差图像的误差增量更大。平均有符号误差（预测−GT）由R01的−5.400变为R07的−12.633，整体少计幅度加大。此处没有新推理或修改任何预测。

按既定GT计数桶分析（GT计数不是每像素密度）：

| GT数量 | n | R01 MAE | R07 MAE | ΔMAE |
|---|---:|---:|---:|---:|
| [0,20) | 784 | 4.4579 | 3.4872 | -0.9707 |
| [20,50) | 465 | 5.1419 | 4.0796 | -1.0624 |
| [50,100) | 265 | 5.8528 | 5.9736 | +0.1208 |
| [100,200) | 296 | 21.9865 | 46.5811 | +24.5946 |
| [200,+∞) | 190 | 59.7526 | 87.5579 | +27.8053 |

器官分组也显示异质性：

| organ | n | R01 MAE | R07 MAE | ΔMAE |
|---|---:|---:|---:|---:|
| flower | 422 | 13.8649 | 10.4384 | -3.4265 |
| fruit | 1069 | 8.3667 | 7.7933 | -0.5734 |
| leaf | 11 | 15.1818 | 19.7273 | +4.5455 |
| plant | 69 | 9.6957 | 7.7101 | -1.9855 |
| seed | 317 | 29.7192 | 72.3817 | +42.6625 |
| stoma | 112 | 2.1964 | 1.8571 | -0.3393 |

seed组R07平均有符号误差−69.6625，R01为−26.7350。高计数和seed组的大误差是本次总体退化的主要**描述性位置**；两种分组可能重叠，不能将它们当成独立原因。leaf只有11张，不作稳定趋势推断。此诊断是查看test后的分析，不用于改阈值、挑epoch、改损失系数或只选择有利组汇报。

### 8.3 模型选择、文本和几何：哪些结论仍不支持

- R07第16轮的val MAE低于其第1轮，但test MAE由旧快照13.3415升至18.3190，说明这个run的val排名没有保证test同步改善。仍保留预先规定的val选择第16轮；不能事后改报第1轮为最终模型。泛化退化/选择不一致与这些观察相符，但无法仅凭此确定过拟合、分布差异、梯度冲突、表示坍塌或权重过强是哪一个原因。
- R03的val MAE最低（9.6707），R05的已完成基线test MAE/RMSE最低（10.5470/29.8706）；主文本不同，不能据单seed宣称organ-only普遍最好或taxonomy文本天然有害。organ-only仍是语义文本，尚无真正纯视觉对照。
- R08已完成30轮，最终best-val MAE=9.9880，较R01低0.0150（0.1501%），但RMSE较高11.4547%；其test三指标也退化，不能声称稳定或全面提升。P01最终test MAE19.4665高于论文全分类文本参考16.90，尚未达到该参考；初始化、caption、缺链规则、mask与环境等协议边界仍需保留，不能将其与R01差值单独归因某一项。
- Lorentz锥非法域率为0只说明已记录的数值检查；辅助loss下降和机制指标不能替代计数收益。R08已补齐test且三指标退化，仍缺同辅助目标的欧氏对照与预先选择的多seed配对，不能从本设置负结果推广到双曲几何普遍有效或无效。

R08/P01/P02/P03均已完成固定预算和best测试，P03−P02初始化来源控制已补齐。下一步由P04完成后与P03配对比较prompt策略；本次核验已有GPU3自动测试，未启动重复推理或新训练，未更改任何在训实验。R06后按10月20日用户明确要求准备20轮命令（未启动，见文末）；R09仍按val门槛和研究问题决定，不因test退化扫lambda、挑seed或扩展实验填卡。 P04已获用户授权，独立实现organ-only主caption配对基线，10月19日15:51快照为GPU2完成4/30、正在第5轮，本次未重查；完整设置、状态及探索性边界见文末记录。

### 8.4 P01/P02/P03：mask与初始化的控制结论（2026-10-20更新）

P01/P02均完成30轮、共享GroundingDINO Swin-B初始化和同一纯七级文本/官方精确名称协议；核对运行protocol，核心源码仅exemplar方法不同，其余数据适配/配置/资产/依赖/推理一致。P02修复mask后，val MAE仅降0.3570%，RMSE升16.3139%；test MAE降1.3279%，RMSE升2.3330%，R²也退化。因此修复具有正确性依据，但当前seed的实验不支持它带来全面性能增益；它没有消除P01/P02与R01的差距，不能把此前差距主要归因该bug。P01/P02的best来自各自固定val MAE规则，不同轮次不是额外训练预算。

P03与P02模型/数据/文本/配置/环境/修复mask一致，仅把GroundingDINO换成FSC147 CountGD初始化，严格加载1146项model参数/缓冲区，optimizer/scheduler/RNG独立创建。P03已完成30/30，第5轮best最终val=10.485485485485485/28.17653131449854/0.9306738112230415、test=11.338/35.49826756336145/0.807312750302844。相对P02，val MAE降3.7578%、RMSE降9.9042%，test MAE降40.9725%、RMSE降31.2536%、R²增加0.2150。两组固定预算、同一val选择规则的三指标均改善，支持FSC147预训练CountGD初始化在当前修复mask的P协议/seed42下优于GroundingDINO初始化，且影响大于本次mask修复观察到的变化。

此结果是初始化来源控制的实测收益，不应推广为所有seed/初始化/数据集都成立；也不能说已逐项解释R01全部优势，因为R01的caption、环境和名称解析等仍不同。P03−P02限于修复mask条件，P03−P01仍同时变化初始化和mask，三组不能识别完整mask×初始化交互。P04对照只改变主caption，等待其固定预算结果再判断输入策略，不从test反向调整超参数。

### 8.5 完整逐轮验证曲线与数据来源

![所有已完成epoch的val MAE；P01独立面板](../runs/tpc268_v3_exclude3/planning/val_mae_curves_results_20261017.png)

原始逐轮点、无平滑或补点，星号为各run最低val MAE。这张曲线为2026-10-17历史快照，不包含10月18新增轮次/P02；最新状态以第5–7节、[2026-10-19 11:03核验快照](../runs/tpc268_v3_exclude3/planning/results_verified_20261019.json)及其后完成的[R08最终test核验](../runs/tpc268_v3_exclude3/entailment_seed42/test_final/verified.json)、[P03最终test核验](../runs/tpc268_p03_fsc147_init_20261018/test/verified.json)为准。P01单列，避免与R01协议混淆。核验产物：[最终配对](../runs/tpc268_v3_exclude3/planning/test_full_taxonomy_final_20261017.json)、[R07逐图/分组核验](../runs/tpc268_v3_exclude3/planning/r07_final_test_verified_20261017.json)、[状态快照](../runs/tpc268_v3_exclude3/planning/report_results_verified_20261017.json)。

### 8.6 TT/TV可学习曲率的损失趋势与调参建议（2026-10-23，PROPOSED，未启动）

**后续状态：用户授权的LC-T01已于13:19:25在GPU0正式训练，最新核实见末节。LC-T02/LC-T03仍未启动，下文保留原始分析和提案记录。**

用户希望基于损失趋势继续调参。本次只读取既有R08/R08-LC/R08-GD/R08-GD-LC日志和best/latest checkpoint标量，不修改代码/配置或在训R04-ELC，不启动候选实验。外部参考仅用于确认锥包含关系和可学习曲率/尺度的一般实现：[原始蕴涵锥论文](https://arxiv.org/abs/1804.01882)、[MERU官方实现](https://github.com/facebookresearch/meru/blob/main/meru/models.py)；下列测量与建议依据本仓库实际日志/实现，不从别的任务直接搬运最优超参。

**收益判断边界**：FSC R08-LC test=11.140/32.8648/0.8348，优于固定c的R08=13.689/37.2070/0.7883，但val MAE10.23023023023023仍差于9.987987987987989；R08前20轮与30轮选中相同第12轮，可作选择范围参照。GD-LC test15.462/42.5036/0.7238较GD30轮第25轮的19.024/49.7241/0.6219好，但预算20/30不同，不能直接称纯曲率因果收益。GD前20轮val最优第12轮MAE10.578578578578579，仍优于GD-LC20轮第12轮10.891891891891891；该固定GD第12轮对应test尚未知，若无权重快照，应另做固定c/20轮匹配基线，不能拿末轮checkpoint0019当第12轮best。当前两种初始化都有探索性测试改善迹象，但均没有val MAE改善证据，也不能据此宣称蕴涵已稳定胜过各自无辅助基线；GD的无辅助P系列与R系列协议不同。

**共同前20轮曲线**（固定c实际训练30轮；图仅对齐前20轮，CSV保留全部）：

![TT/TV损失、曲率与验证误差](../runs/tpc268_v3_exclude3/planning/entailment_tuning_20261023/entailment_curves_first20.png)

下表为FSC R08-LC的未乘lambda/warmup损失与val，不把加权loss和原始loss混用：

| 轮次 | 原始L_TT | 原始L_TV | val MAE | 曲率c（epoch均值） |
|---|---:|---:|---:|---:|
| 1 | 1.0882 | 0.841732 | 10.230230 | 0.912295 |
| 2 | 0.146233 | 0.00247218 | 14.202202 | 0.811152 |
| 12 | 0.0257705 | 0.000171737 | 10.235235 | 0.644370 |
| 20 | 0.0245952 | 1.18907e-05 | 12.024024 | 0.645156 |

L_TT包含taxonomy正边+错误父TT负项+加权species-organ bridge；L_TV目前只有正确单位文本→匹配query的正蕴涵。TV在第2轮已降至约0.00247，第20轮约1.19e-5，而val第1轮10.2302、第12轮10.2352近似持平，第20轮12.0240更差，不能把辅助loss继续下降当计数泛化收益。GD-LC的TV同样由约.8324降到第2轮.002224、第20轮1.66e-5，TT在两种初始化下最终均约.025。

第20轮正确单位→query包含率已近100%，同时错误**species taxonomy节点**→query的训练诊断包含率亦近100%（FSC99.99934%、GD99.99955%）。这是train/no_grad的错误物种taxon诊断，不是test分类准确率，也不是已记录的错误species-organ单位负loss；提示投影可能缺乏区分，但不能仅凭此断言CountGD主预测头/所有表示坍塌。当前代码对这些错误节点query关系没有反向传播排斥项，单纯增大lambda_tv不会直接优化该诊断。

可学习曲率确有可观察的优化作用：第20轮映射触及径向上限的混合text/query比例，FSC固定c为11.7348%、LC约.006647%，GD固定c为6.7119%、LC为0。该比例不等于非法锥率（非法锥均为0），不能把混合统计误称仅视觉query饱和，也不能据此单独证明语义层级有效。曲率未逼近[.1,10]边界，暂不扩大范围或以训练末值作为最佳固定曲率。

best与末轮标量由实际checkpoint读取（float32 clamp/exp）：FSC-LC best第1轮c=.8409649729728699、末轮c=.6453250050544739；GD-LC best第12轮c=.6318109631538391、末轮c约.633296。alpha_t/v也在学习，数值保留checkpoint_scalars.json。当前映射的无量纲半径为`asinh(2K(1+m)) + sqrt(c)*alpha*||raw||`（再做上限4保护），因此c与alpha及投影范数存在尺度耦合，末轮c≈.63–.65不等于独立识别出的生物最优曲率。可学习曲率的改进可能包含优化/尺度适配作用，需匹配消融才能分离。

后期加权TT+TV只占总训练loss标量约.004%，但角度loss与CountGD多层分类/定位loss单位、归约方式不同，不能据此断言辅助梯度太小或机械放大权重。目前没有保存分支梯度范数、log_c梯度/步长或梯度裁剪比例，相关原因均为待验证假设。

**建议第一批以FSC147的R08-LC为固定基线，只改一个参数，均fresh初始化/seed42/20轮；不是把三个候选同时组合**：

| 提案ID | 唯一改动 | 其余保持 | 目的/不确定性 |
|---|---|---|---|
| LC-T01（优先） | lr 1e-4→3e-5 | warmup1、lambda_tt=lambda_tv=.05、c_init1 | 检验较慢适配能否减小val震荡；初始/第12轮较好并不独自证明lr过大 |
| LC-T02 | aux_loss_warmup_epochs 1→3 | 原lr/损失权重/曲率 | 检验辅助项缓慢介入能否改善早期主计数适配，不假定越慢越好 |
| LC-T03 | lambda_tv .05→.01 | lambda_tt=.05及原lr/warmup | 检验减弱早期正例进锥压力是否有益；不会凭空增加错误关系分离 |

主文本固定R full_taxonomy，不与正在进行的species提示对照混改；R04-ELC按原计划运行完。第一轮按val MAE筛选并观察RMSE/R²，不根据test排名选择参数。若要组合两个赢家，作为新候选再次验证，不能自动宣称相加有效。GD后续单独复核：由于CountGD新增模块为构造初始化，不能默认FSC的较小lr也最优；先保留原1e-4作为对照，必要时单独试5e-5。既有GD专用fresh入口对loss权重有固定检查，未来改lambda需新配置及专用检查支持，本次不绕过或修改原入口。

第二阶段若有val证据：固定其他参数单独搜索lambda_tt∈{.02,.05,.1}（.05已有基线）；或曲率lr倍率∈{.1,1}（默认与主普通参数同lr，目前没有独立lr_c选项，需新增优化器组并保留公共基线）。c_init先保留1，范围[.1,10]、K=.1、clip=.1、bridge/负margin/采样数先不动；temperature与lambda_contrast在contrast关闭时不参与目标，不作为这条分支的有效调参项。无需因TV数值小而盲增其lambda。

未来仅对新run增加诊断时，应记录raw/weighted TT、TV、TT正负/bridge、c与alpha和有效尺度、共享feat_map的主损失/TT/TV梯度范数、log_c梯度/更新、整体裁剪率、分开的text/query径向触顶率及验证集正确/错误taxon或单位包含率；辅助诊断不用于GT校正计数。加入诊断需同版本基线，避免把实现变化混入超参效果。若错误taxon包含长期近100%，可另开TV负蕴涵的机制实验；它是新增损失目标，不能与本轮纯数值调参混称一项。预先固定最终方案后再测test，所有已看旧test驱动的新提案仍标探索性，确认性收益需预先固定的配对多seed。

产物`planning/entailment_tuning_20261023/`：PNG/PDF曲线、epoch_metrics.csv、loss_analysis.json、checkpoint_scalars.json、proposed_tuning.json。以上是10月23日提案时的状态；截至10月25日LC-T01已完成20轮及val/test（见§8.7），LC-T02/03仍未启动，不填写未来指标；其余历史分析与候选定义保留。两份docs同日同步记录。

### 8.7 R04-ELC与LC-T01：20轮完成结果（2026-10-25）

两组均FSC147 CountGD fresh初始化、seed42、20轮、TT/TV各.05、无contrast、共享可学习曲率初始1；最低val MAE选权重后，本日仅测该固定权重的完整2000张test。R04-ELC第14轮，主caption为`{organ} of {species} .`、普通lr1e-4；LC-T01第18轮，主caption为R full_taxonomy、普通lr3e-5。特殊linear-projection组仍1e-5。val/test数值见§6/7。

有效配置逐项比较：LC-T01相对R08-LC只差lr；R04-ELC相对R06-ELC/R08-LC只差prompt_mode。共同20轮预算，无初始化、数据划分或推理改动，LC-T01同图caption亦逐项相同。

| 配对 | split | ΔMAE | ΔRMSE | ΔR² |
|---|---|---:|---:|---:|
| LC-T01−R08-LC | val | -0.6647（-6.50%） | +2.6315（+9.19%） | -0.013760 |
| LC-T01−R08-LC | test | -1.5040（-13.50%） | -4.0075（-12.19%） | +0.037822 |
| R04-ELC−R06-ELC | val | -0.0240（-0.24%） | -2.3493（-7.12%） | +0.013051 |
| R04-ELC−R06-ELC | test | +1.1180（+9.92%） | +4.2517（+13.64%） | -0.043308 |
| R04-ELC−R08-LC | val | -0.0681（-0.67%） | +2.0092（+7.02%） | -0.010397 |
| R04-ELC−R08-LC | test | +1.2455（+11.18%） | +2.5681（+7.81%） | -0.026820 |

降低普通lr使val MAE由10.2302降为9.5656（−6.4971%），但val RMSE由28.6251升至31.2567（+9.1931%）、R²降低；不能把它称为验证集全面改善。LC-T01 test相对R08-LC：MAE变化-13.5009%、RMSE变化-12.1938%、R²变化+0.03782238。当前seed42下，较小普通lr改善val MAE及test三指标，支持其作为需独立确认的候选；val RMSE/R²仍退化，不能称所有指标全面改善。按预先固定的val MAE规则保留第18轮，不根据test更换权重或继续选择超参。

加入物种主文本（R04-ELC对R06-ELC）使val MAE微降0.2358%、RMSE降7.1226%；test MAE变化+9.9223%、RMSE变化+13.6354%、R²变化-0.04330775。相对全分类主文本R08-LC，仅改为organ+species：test MAE变化+11.1804%、RMSE变化+7.8141%、R²变化-0.02681959。这里只能描述当前seed42/当前模型下主文本与优化设置的配对观察；不是多seed稳定收益、纯几何有效性或任意文本策略普遍优劣的证明。

两项是已看历史test后提出的探索性对照，本次用户明确要求补测；不把新test用于选epoch/阈值/后续参数，不启动LC-T02/03。核验JSON保存完整指标、实际来源、同路径/GT/caption与配置差异。

### 8.8 LC-T01损失诊断与下一批单因素调参（2026-10-25）

**后续授权：用户要求在GPU0/1/2分别启动LC-T04/05/06，已实现配置/后台入口并正式训练，当前启动核验状态见§5及末节；下文分析保留原提案时点。**

本次重新读取LC-T01与R08-LC各20条完整正式train+val日志，检查test_split=val、999图、有效LR日程与有限指标，记录日志SHA。分析只使用既有日志/最佳权重元数据，不改模型、配置、数据、环境或训练/推理协议；不启动实验。当前较小lr候选依据val MAE及稳定性，已暴露test结果不用于本批参数排序或改epoch规则。

![LC-T01与原学习率的损失及验证曲线](../runs/tpc268_v3_exclude3/planning/lc_t01_followup_20261025/lc_t01_vs_r08lc.png)

上图虚线表示第10轮后LR衰减：普通组3e-5→3e-6，特殊linear-projection组1e-5→1e-6；两者均由现有StepLR作用。下表TT/TV是未乘lambda/warmup的原始loss，c是epoch均值，不冒充该轮checkpoint精确值：

| 轮次 | 原始TT | 原始TV | c（epoch均值） | val MAE | val RMSE |
|---|---:|---:|---:|---:|---:|
| 1 | 1.84936 | 1.71975 | 0.970462 | 10.1191 | 29.1806 |
| 2 | 0.817238 | 0.0772801 | 0.923391 | 11.5786 | 29.8997 |
| 4 | 0.246016 | 0.00643081 | 0.863066 | 9.5696 | 29.2015 |
| 10 | 0.0533015 | 0.000442432 | 0.768380 | 9.8358 | 26.8694 |
| 18 | 0.0433478 | 3.93692e-05 | 0.756640 | 9.5656 | 31.2567 |
| 20 | 0.0427784 | 4.46097e-05 | 0.755288 | 10.3223 | 34.3846 |

**观察与边界**：

- 降低普通lr后，前10轮val MAE跨轮总体标准差由1.334904降至.598194，后10轮由.568772降至.186624；这是同一seed内跨轮波动，不是多seed方差或置信区间。后10轮val MAE均值为9.932432，较原lr的11.184885好。
- 第4轮MAE9.56956956956957与第18轮9.565565565565565仅差.004004（999张绝对误差总和差4）；第4轮RMSE29.20148500892937也低于第18轮31.256663。第18轮仍按预定最低MAE规则作为最终best，不事后改报第4轮test。不能因为best在第18轮就推断还需延长训练；暂不优先增加预算。
- TV从1.719755降到第2轮.0772801、第4轮.00643081、第18轮3.93692e-5；第20轮4.46097e-5。20个epoch均值加权TV标量的总和中，前5轮占99.3477%；这不是梯度贡献比例。TV目前只有正确单位文本→query的正蕴涵，数值很小不等于层级区分学好，也不支持盲增lambda_tv。第20轮错误species taxon→query训练包含率约99.99996%，是no_grad诊断，不是错误unit负loss、test错误率或主模型坍塌证明。
- TT仍由1.849359降至.0427784，但原lr最终TT更低（.0245952），计数val却更差。不存在“TT必须降到原lr一样低才有用”的证据，暂保留lambda_tt=.05，不按原始loss大小机械增权。辅助梯度范数/裁剪率没有记录，早期干扰或梯度太强只是待检验解释。
- 最佳checkpoint c=.7562490701675415，末轮epoch均值.7552878，离[.1,10]边界很远；20轮混合text/query径向触顶率和非法锥率均0。保持c_init1/范围[.1,10]及共享可学习c；c与alpha_t/v及投影范数耦合，普通lr改变同时影响它们，不能认定.756是通用最优固定曲率或把收益单独归因c。

**下一批以LC-T01为固定匹配基线，fresh原FSC147初始化/seed42/20轮，独立单因素比较，不累积三个变更**：

| 新提案ID | 优先级 | 相对LC-T01唯一改动 | 目的与风险 |
|---|---:|---|---|
| LC-T04 | 1 | lambda_tv .05→.01；lr仍3e-5、TT仍.05、warmup仍1 | 检验减弱早期正例进锥压力是否改善计数；不会增加负TV，也没有已证实权重过大或必然收益 |
| LC-T05 | 2 | 普通lr 3e-5→1e-5；TT/TV仍.05/.05、warmup仍1 | 对已获val改善的lr做局部下探；20轮内可能适配不足，特殊projection组初始仍1e-5，c/alpha仍随普通组 |
| LC-T06 | 3 | aux warmup 1→3；lr仍3e-5、TT/TV仍.05/.05 | 单独检验TT+TV缓慢介入，和LC-T04不叠加；当前未测分支梯度冲突 |

如果只做一组，优先LC-T04。TV后期已接近0，使这项实验主要检验早期辅助约束的影响；该方向是可证伪的假设，.01不是从日志推导出的最优值。三组均保留full_taxonomy主caption/3exemplars、原6998/999/2000划分及三图代码排除、同registry/环境/阈值/模型/冻结/主损失，预算20轮，按val MAE选best并记录RMSE/R²。最终候选固定后再测test，不因某次test更好就继续选超参；单seed候选收益需预先固定的匹配seed43/44确认。

原LC-T02/03仍保留10月23日以R08-LC、lr1e-4为基线的提案定义，不悄悄换成LC-T01；它们仍未启动。原分析时新LC-T04/05/06均PROPOSED_NOT_LAUNCHED；现用户已授权，三项配置与专用检查已实现并实际后台训练，PID/配置与来源见末节，性能仍未知。新入口按各自有效权重检查criterion，不复用旧入口固定lambda=.05的断言。

日程核查补记：当前main.py:208始终构建StepLR，multi_step_lr/lr_drop_list分支处于注释中，直接设这两个配置不会生效。lr_drop=5会每5轮反复降10倍，20轮中将出现3e-5/3e-6/3e-7/3e-8，不等于只在第5轮后降一次。此语义已核对[PyTorch StepLR官方文档](https://docs.pytorch.org/docs/stable/generated/torch.optim.lr_scheduler.StepLR.html)及当前源码；本次不修改scheduler实现，也不把无效配置当可执行建议。如未来改变日程或增加梯度诊断/独立c参数组，单独记录实现与匹配baseline。

产物为planning/lc_t01_followup_20261025/下analyze.py、epoch_metrics.csv、analysis.json、proposed_followup.json、PNG/PDF曲线。曲线/数值均来自原始20轮日志；提案收益未知。原分析步骤仅更新两份docs/曲线，没有启动训练或测试；随后用户明确授权启动三项训练，实测结果表仍待完整val后更新。

## 9. 代码、环境、产物与可追溯性

当前环境实测：Python3.10.12、torch2.13.0+cu130、torchvision0.28.0+cu130、transformers4.57.6、timm1.0.28；GPU为RTX3090。CUDA扩展曾用GCC11及虚拟环境CUDA13编译器构建，六项forward/gradcheck通过。当前系统默认nvcc可能与该构建环境不同，不用nvidia-smi版本代替编译器版本。维持现有uv环境，不在训练中途sync移除额外扩展。

**启动Git记录与实际协议必须分开。** console包含训练和后续重评多个Git行，下表只取第一次训练启动记录，而非最后一行：

| 实验 | 首次训练记录的HEAD | 工作区 | 解释 |
| R01 | `9df0651` | has uncommited changes | 以保存的配置/checkpoint及已有源码快照共同复核 |
| R02 | `9df0651` | has uncommited changes | 以保存的配置/checkpoint及已有源码快照共同复核 |
| R03 | `9df0651` | has uncommited changes | 以保存的配置/checkpoint及已有源码快照共同复核 |
| R04 | `8a26e86` | has uncommited changes | 以保存的配置/checkpoint及已有源码快照共同复核 |
| R05 | `8a26e86` | has uncommited changes | 以保存的配置/checkpoint及已有源码快照共同复核 |
| R07 | `8a26e86` | has uncommited changes | 以保存的配置/checkpoint及已有源码快照共同复核 |

R01/R02/R03在`9df0651`且dirty的工作区启动，不代表它们用了未排除三图的旧数据协议；实际保存配置和checkpoint均记录了三张排除名单、当前坐标策略和有效registry fingerprint。本次已核对这些字段，但缺乏每次启动的完整不可变源码归档，不能仅凭HEAD声称逐字节复现。当前HEAD为`6341592d13575f3626bc70f08604b96ab231f4ef`；相对R07启动记录8a26e86，模型代码差异仅为transformer.py禁用autocast的API替换，另有未启用的候选异名JSON。R07最终test的工作区代码diff为空，实际使用协议与逐图caption已经与R01核对；历史dirty启动缺乏全部不可变源码，因此不声称所有旧run源码逐字节一致。

| ID | 相对实验根目录的run | 准确启动脚本 | 主要证据 |
| R01 | `full_baseline_seed42/` | `run_r01.sh` | `full_baseline_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R02 | `full_method_seed42/` | `run_r02.sh` | `full_method_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R03 | `species_baseline_seed42/` | `run_r03.sh` | `species_baseline_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R04 | `species_method_seed42/` | `run_r04.sh` | `species_method_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R05 | `organ_baseline_seed42/` | `run_r05.sh` | `organ_baseline_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R07 | `contrast_seed42/` | `run_r07.sh` | `contrast_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R08 | `entailment_seed42/` | `run_r08.sh`、`run_r08_test_final.sh` | best epoch11；`val/`及`test_final/`的metrics、counts、checkpoint_metadata、verified、status/exitcode、SHA和源码记录 |
| R06-ELC | `organ_entailment_learnable_seed42_e20/` | `run_r06_entailment_learnable_e20.sh`、`run_r06_entailment_learnable_test.sh` | best epoch17，c=0.62728363；`val/`及`test_final/`完整指标/计数、SHA、源码/依赖及集合核验 |
| R04-ELC | `species_entailment_learnable_seed42_e20/` | `run_r04_entailment_learnable_e20.sh`、`run_r04_entailment_learnable_test.sh` | best epoch13，c=0.63700980；20轮日志、独立val、test_final完整指标/计数/权重SHA/源和依赖核验 |
| R08-GD | `entailment_groundingdino_seed42/` | `run_r08_groundingdino.sh`、`run_r08_groundingdino_test.sh` | best epoch24；`val/`及`test_final/`完整指标/逐图计数、SHA、源码/依赖核验；首次后处理失败及修正证据保留 |
| R08-GD-LC | `entailment_groundingdino_learnable_seed42_e20/` | `run_r08_groundingdino_learnable_e20.sh`、`run_r08_groundingdino_learnable_test.sh` | best epoch11，c=0.63181096；`val/`及`test_final/`完整指标/逐图计数、SHA、源码/依赖与完整集合核验 |
| LC-T01 | `entailment_learnable_lr3e5_seed42_e20/` | `run_lc_t01_lr3e5_e20.sh`、`run_lc_t01_lr3e5_test.sh` | best epoch17，c=0.75624907；20轮日志、独立val、test_final完整指标/计数/权重SHA/源和依赖核验 |
| LC-T04 | `entailment_learnable_lr3e5_tv001_seed42_e20/` | `run_lc_followup_e20.sh LC-T04` | `launch_manifest.json`、`cpu_initialization_report.json`、`launch_sources/`、`launch_verified.json`、真实console与stage/status；20轮后best-val |
| LC-T05 | `entailment_learnable_lr1e5_seed42_e20/` | `run_lc_followup_e20.sh LC-T05` | `launch_manifest.json`、`cpu_initialization_report.json`、`launch_sources/`、`launch_verified.json`、真实console与stage/status；20轮后best-val |
| LC-T06 | `entailment_learnable_lr3e5_warmup3_seed42_e20/` | `run_lc_followup_e20.sh LC-T06` | `launch_manifest.json`、`cpu_initialization_report.json`、`launch_sources/`、`launch_verified.json`、真实console与stage/status；20轮后best-val |

- 最佳checkpoint：`<run>/checkpoint_best_regular.pth`；latest：`<run>/checkpoint.pth`。训练根目录`val_metrics.json`通常是末轮，**最终比较只使用`<run>/val/val_metrics.json`**。本报告运行中best取训练日志并核对best checkpoint，而不把根目录末轮指标冒充best。
- 独立重评：`<run>/val/val_metrics.json`、`val_counts.json`；test：`<run>/test/test_metrics.json`、`test_counts.json`、`checkpoint.sha256`、`run_test.sh`、`status`/`exitcode`。R01/R02配对test比较在`R01_R02_test_comparison.json`。
- 本次原始快照：`planning/report_snapshot_20261016.json`；曲线：`planning/val_mae_curves_20261016.png`。整理前文档备份：`planning/experiment_before_report_20261016.md`。这些均在runs下，docs恰好保留两份文档。
- R07短程证据为`preflight/gpu_contrast_only/`，正式为`contrast_seed42/`，两者不同初始化和预算，不混合统计。既有M0四组摘要为`preflight/summary.json`，不作为正式成绩。

### 已完成结果快速入口

| 实验 | 最佳权重验证指标 | 测试指标 | 逐图测试预测 |
|---|---|---|---|
| R01 | [val_metrics.json](../runs/tpc268_v3_exclude3/full_baseline_seed42/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/full_baseline_seed42/test/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/full_baseline_seed42/test/test_counts.json) |
| R02 | [val_metrics.json](../runs/tpc268_v3_exclude3/full_method_seed42/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/full_method_seed42/test/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/full_method_seed42/test/test_counts.json) |
| R03 | [val_metrics.json](../runs/tpc268_v3_exclude3/species_baseline_seed42/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/species_baseline_seed42/test/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/species_baseline_seed42/test/test_counts.json) |
| R04最终best | [val_metrics.json](../runs/tpc268_v3_exclude3/species_method_seed42/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/species_method_seed42/test_snapshot_20261016_153930/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/species_method_seed42/test_snapshot_20261016_153930/test_counts.json) |
| R05最终best | [val_metrics.json](../runs/tpc268_v3_exclude3/organ_baseline_seed42/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/organ_baseline_seed42/test_snapshot_20261016_153930/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/organ_baseline_seed42/test_snapshot_20261016_153930/test_counts.json) |
| R07最终best | [val_metrics.json](../runs/tpc268_v3_exclude3/contrast_seed42/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/contrast_seed42/test_final/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/contrast_seed42/test_final/test_counts.json) |
| R07快照 | 第1轮正式训练val日志及snapshot_metadata.json | [test_metrics.json](../runs/tpc268_v3_exclude3/contrast_seed42/test_snapshot_20261016_153930/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/contrast_seed42/test_snapshot_20261016_153930/test_counts.json) |
| R04-ELC | [val_metrics.json](../runs/tpc268_v3_exclude3/species_entailment_learnable_seed42_e20/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/species_entailment_learnable_seed42_e20/test_final/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/species_entailment_learnable_seed42_e20/test_final/test_counts.json) |
| LC-T01 | [val_metrics.json](../runs/tpc268_v3_exclude3/entailment_learnable_lr3e5_seed42_e20/val/val_metrics.json) | [test_metrics.json](../runs/tpc268_v3_exclude3/entailment_learnable_lr3e5_seed42_e20/test_final/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/entailment_learnable_lr3e5_seed42_e20/test_final/test_counts.json) |

## 10. 后续持续更新规则

本文件采用“前半部当前报告＋后半部批准的计划”，下一次实验状态变化时更新同一组表，避免在末尾累积互相矛盾的旧状态。**这不是已部署的自动刷新服务**；每次后续实验工作都需从真实日志/产物刷新本报告，并同步implement.md的日期记录。

1. 更新采集时刻、当前HEAD/工作区差异；核对status、进程与GPU，RUNNING状态文件本身不能证明进程仍活着。
2. 读取正式训练目录的log.txt，记录完整轮数与log.log最新batch；R07先区分短程/正式阶段。最佳按val MAE选，保留同一epoch的RMSE/R²，不分别挑各列最优。
3. 核对best checkpoint的epoch（转换为1-based）及best_val_mae；若正在写checkpoint导致读取失败，稍后重读，不能改checkpoint来绕过。
4. 训练结束后确认退出码0并重评best-val；独立重评通过才把阶段性val改成最终val。评估test只在用户要求或冻结计划的评估阶段执行，不因尚缺结果擅自补跑。
5. 更新对应val/test表和同caption配对差值；逐图检查图片数、去重、官方split与GT一致，重算MAE/RMSE/R²，核对training_protocol。没有产物填“未评估”，不填0。
6. 重画未平滑曲线、更新snapshot文件及持续记录。报告所有已执行seed和失败/未运行项，不挑选有利结果，不使用已查看test调整后续参数。
7. 遵守原始资产不修改、已启动实验不变和同协议baseline配对；模型/输入/标签/环境变化另开协议目录和匹配baseline。docs只保留experiment.md与implement.md。

### 本次维护记录（2026-10-16）

整理R01–R09设置矩阵、实际文本模板、状态/最佳epoch/完整val与test表、同caption分析、代码与产物证据及更新流程。R01/R02/R03六份重评结果已独立重算，R01–R05的best checkpoint轮次已核对；现有训练与配置未变，未启动新实验或额外test。下附既有计划，保留R08优先级和R06/R09/多seed的门槛。

15:39–15:53追加维护：用户明确要求并行测试R04/R05/R07当前best。三项固定快照测试与核验均完成，实测结果、epoch/GPU/时间、不可变权重证据、逐图产物及阶段性配对分析已写回第1/5/6/7/8/9节；训练继续运行，原计划不因test改动。曲线文件仍为11:00的历史快照，本次进度与结果以更新后的表和新增核验JSON为准。

### 2026-10-17维护记录

核对R04/R05退出码、30轮日志、最终best元数据和999图独立重评，重算val指标并确认最终best与既有test快照SHA256一致；核对R07当前第16轮best和21轮完成进度。采集原始状态/逐epoch日志见[report_snapshot_20261017.json](../runs/tpc268_v3_exclude3/planning/report_snapshot_20261017.json)，更新的未平滑曲线见[val_mae_curves_20261017.png](../runs/tpc268_v3_exclude3/planning/val_mae_curves_20261017.png)。按用户要求优先论文基线核验，记录初始化等公开信息缺项；未启动新训练，未修改已有实现、配置、数据或进程。



### 2026-10-17 最终test结果维护记录（2026-10-17T22:46:00+08:00）

R07最终test DONE、exitcode=0；第16轮权重SHA256=`37ae8b38f4b59b3789539e89d42b05f1aaaa586e031d0c618780f7308457fe04`与运行前记录及运行后检查一致。全部2000张路径唯一、集合等于官方test，每张GT等于原annotation点数；MAE/RMSE/R²独立重算一致。compare_tpc268_runs验证R01/R02/R07同caption、冻结、seed、初始化来源、30轮预算及训练/推理协议；R07实际eval代码提交6341592，与启动源码差异和溯源边界见第9节。本次只更新结果表、当前结论、分组诊断与曲线，不启动训练/测试或修改模型、数据、配置。R08/P01的best轮次已读checkpoint核对，训练状态依最近日志；实时GPU/进程查询因自动审批服务403未执行。历史启动与检查记录继续保留，均以当时的日期/状态理解，当前结论以第1–9节为准。

## 附录 A：后续实验计划与命令（2026-10-17优先级修订）

当前状态以本节表及文末R07完成决策为准；下方作者配方核查段落是当日早期快照，用户随后已确认P01假设并启动，见P01节。

**2026-10-17优先级补充：用户随后明确要求先提供R08启动命令。** 本次已准备原计划R08的GPU0后台脚本，READY但未执行；R07继续原训练，R06/R09仍不自动展开。P01论文Table 4“3 visual exemplars＋full taxonomy”的初始化和监督配方缺项继续保留，P01训练尚未启动，不能把R08或猜测配置称作论文完全复现。

核查来源：[论文§4.5与Table 4](https://arxiv.org/html/2603.21229v1#S4.SS5)、[官方仓库](https://github.com/tiny-smart/TPC-268)、[项目页](https://tiny-smart.github.io/tpc268-project-page/)、[公开权重请求Issue #3](https://github.com/tiny-smart/TPC-268/issues/3)。论文确认重新训练、3个视觉exemplars，主文本格式为七级名称逗号序列`Kingdom, Phylum, Class, Order, Family, Genus, Species.`；对应test为MAE=16.90/RMSE=43.32/R²=0.71，未单独报告该设置的val。**论文未说明从FSC147 CountGD权重微调还是GroundingDINO初始化**；“retrain”不能推出具体初始化，更不代表随机初始化全部网络。

当前R01文本为`organ of species; taxonomy: ... .`，从checkpoint_fsc147_best.pth初始化，使用2px载体框/center-only监督、冻结backbone.0与BERT、30epoch及整图阈值0.23/0。这些是本地协议，不是已验证的作者配方。除了文本差异，作者的初始化、点到监督转换、冻结/优化/预算、阈值、crop/SAM/exemplar后处理及坐标问题处理均待核实；不能默认打开原CountGD的所有后处理就等于TPC论文设置。

本地7份官方标注/split资产SHA256与记录来源一致，官方repo HEAD仍为`a382e85013673a3485e76a2fc2af158c0f779fdf`。当前有效split=6998/999/2000，公开原split=7000/1000/2000；用户批准的3图排除保持不变。taxonomy未解析图像train453/val56/test105，当前full-taxonomy会退回species，作者如何处理未知。因此直接改caption或改回全量split不足以完成严格复现，也不能擅自恢复已排除图、猜测分类或修改原数据。

已保存审计：[protocol_audit.json](../runs/tpc268_paper_reproduction_20261017/protocol_audit.json)，官方README/通用Dataset副本及来源hash在同目录reference。该Dataset只给出点和3个exemplar框，不给CountGD专用监督转换/训练配置。已审阅的公开main仓库/项目页/论文未找到Table 4对应训练配置或权重；用户确认没有额外代码或权重。GitHub API限流403，但原始文件/HTML及git ls-remote可访问，此结论不是把网络失败误当文件不存在。

下一步先取得或核实上述作者配方；所需问题已整理为[author_questions.md](../runs/tpc268_paper_reproduction_20261017/author_questions.md)，仅为本地草稿，未联系作者。若只能依据公开资料重建，必须逐项声明假设并另列“公开信息重建基线”，不能称完全复现；至少固定纯七级文本、原型覆盖、点监督、初始化与推理协议，和原R01独立记录。P01目前为WAITING_AUTHOR_PROTOCOL，尚无可信的完整复现启动命令。

| 优先级 | ID | 状态 | 配置 / 输出run ID | 对照与问题 | 启动条件 |
|---|---|---|---|---|---|
| P1 | R07 | DONE；最终test DONE | cfg_tpc268_contrast.py / contrast_seed42 | 对R01：contrast单独是否改善计数？ | 下一步GPU2评估第16轮最终best的test |
| P0 | P01 | RUNNING | tpc268_paper_reproduction_20261017 / protocol_audit.json | 用户确认假设下重建论文全分类文本基线 | GPU3运行，原mask、GroundingDINO初始化，详见P01节 |
| P1 | R08 | RUNNING（日志） | cfg_tpc268_entailment.py / entailment_seed42 | 对R01：TT/TV单独是否改善计数？ | 完成9轮、正在第10轮；继续既定30轮 |
| P1 | P02 | READY | tpc268_p02_maskfix_20261017 / worktree/run_p02.sh | 同P01仅修复exemplar padding/mask | GPU2预检通过，正式训练未启动；使用文末命令 |
| P2 | R09 | BLOCKED | cfg_tpc268_euclidean.py / euclidean_seed42 | 同完整辅助目标换几何，隔离Lorentz价值 | R02最终best-val及R07/R08结果就绪，且蕴涵或组合显示潜力；若仍要检验/主张几何差异则必做 |
| 用户指定 | R06 | READY（10月20日，未启动） | cfg_tpc268_organ_full.py / organ_method_seed42_e20 | 配对R05前20轮，检查弱主文本下辅助收益 | 用户明确要求执行原设置但预算20轮；只准备启动命令，覆盖原自动调度门槛，不代表候选收益门槛已满足 |
| P3 | 纯视觉控制 | BLOCKED | 尚未实现，不提供伪启动命令 | 控制所有语义文本输入，解释文本条件的贡献 | 主损失诊断后单独确定并验证真正visual-only路径；不以空caption或organ模式冒充 |
| P3 | R10–R19 | BLOCKED | seed43/44扩展 | 检查候选收益稳定性 | 见附录C，不再按原计划默认跑满13–19组 |
| P3 | A01 no-TT-bridge | BLOCKED | bridge_weight=0.0，新run | 仅删除TT bridge | 只有蕴涵已表现出可重复价值且需解释bridge时考虑；当前预算不展开 |

BLOCKED在本计划表示明确的前置条件尚未满足，不表示程序故障。每次条件判断记录依据、时间、释放/跳过的ID；未启动项最终不执行时记SKIPPED并说明理由。新GPU只分配给未启动任务，不能抢占R04/R05/R07；R02已完成。

**R07/R08首次短程**：R07已通过，不重复执行。R08仍需独立短程：配置不改，使用`--debug`、epochs=1、batch4，各约15步optimizer更新并完整val999张；目录必须为 `preflight/gpu_contrast_only` / `preflight/gpu_entailment_only`，不得用其checkpoint初始化30轮正式run。有限loss/实际反向与更新、checkpoint保存、完整计数JSON均通过后才启动正式run；失败先排查技术原因。下方helper是正式30轮，不带debug。

### 2026-10-17 R08可直接使用的后台命令

已准备`runs/tpc268_v3_exclude3/run_r08.sh`，固定物理GPU0，启动时要求剩余显存≥20000MiB；准备时实测空闲24124MiB。本次仅检查配置和脚本，没有执行训练。流程为独立短程约15步＋完整val999张 → 检查有限值、TT/TV存在且contrast关闭、Lorentz锥合法域及checkpoint → 从原FSC147权重独立训练30轮 → 最终best-val重评。不自动评估test。状态/阶段/日志分别写`entailment_seed42/status`、`stage`和`launch_entailment_seed42.log`；锁防重复，失败不继续后续阶段，独立session不依赖SSH。

R08沿用原配置：full-taxonomy主文本、同三图排除、batch4、seed42、冻结backbone.0/BERT，与R01配对；`use_level_contrast=False`、`use_taxonomy_entailment=True`、Lorentz曲率默认固定1，总损失为原CountGD损失＋0.05 TT＋0.05 TV（TT含既有unit bridge），首epoch按step warmup。未修改模型、训练配置或数据协议。此启动方式替代下方旧的手动分步示例；不要同时执行两套命令。

```bash
cd /home/lijiahui/research/CountGD
nohup setsid bash runs/tpc268_v3_exclude3/run_r08.sh \
  > runs/tpc268_v3_exclude3/launch_entailment_seed42.log 2>&1 < /dev/null &
```

查看日志：`tail -f runs/tpc268_v3_exclude3/launch_entailment_seed42.log`。脚本语法、内嵌Python、有效配置及预检使用的日志字段已核对；真实GPU短程和正式结果均待用户执行后验证。

```bash
# R08短程示例：从仓库根目录执行，GPU1须在启动时重新核验空闲。
CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
MPLCONFIGDIR="$PWD/runs/tpc268_v3_exclude3/.mpl-cache" \
uv run --no-sync python -u main.py -c config/cfg_tpc268_entailment.py \
  --datasets config/datasets_tpc268.json --device cuda --seed 42 --num_workers 4 \
  --pretrain_model_path checkpoints/checkpoint_fsc147_best.pth --debug --save_log \
  --output_dir runs/tpc268_v3_exclude3/preflight/gpu_entailment_only \
  --options text_encoder_type=checkpoints/bert-base-uncased epochs=1 batch_size=4
# R07已通过短程且正在训练；不要重复执行R07短程或正式启动命令。
```

### 正式训练与best-val重评helper

仅为尚未启动且门槛已通过的任务使用。把本块保存为 `runs/tpc268_v3_exclude3/diagnosis_helpers.sh` 后source；调用函数的第1参数是已核验空闲的物理GPU。函数在独立子shell中设置CUDA设备并对整个训练+验证持锁；训练失败则停止，不继续评估。相同协议、同目录重新执行会自动恢复latest；更改任何协议必须用新run ID及匹配baseline。

```bash
train_and_val() (
  set -euo pipefail
  local gpu="$1" run_id="$2" cfg="$3" seed="$4"
  cd /home/lijiahui/research/CountGD
  export PATH="$HOME/.local/bin:$PATH"
  export CUDA_VISIBLE_DEVICES="$gpu" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  export MPLCONFIGDIR="$PWD/runs/tpc268_v3_exclude3/.mpl-cache"
  local run_dir="$PWD/runs/tpc268_v3_exclude3/${run_id}_seed${seed}"
  mkdir -p "$run_dir"
  exec 9>"$run_dir/train.lock"
  flock -n 9 || { echo 'This run is already active'; exit 1; }
  echo "$BASHPID" > "$run_dir/launcher.pid"
  uv run --no-sync python -u main.py -c "$cfg" \
    --datasets config/datasets_tpc268.json --device cuda --seed "$seed" --num_workers 4 \
    --pretrain_model_path checkpoints/checkpoint_fsc147_best.pth --save_log \
    --output_dir "$run_dir" \
    --options text_encoder_type=checkpoints/bert-base-uncased batch_size=4 epochs=30 \
    2>&1 | tee -a "$run_dir/console.txt"
  uv run --no-sync python -u main.py -c "$cfg" \
    --datasets config/datasets_tpc268.json --device cuda --seed "$seed" --num_workers 4 \
    --eval --eval_split val --resume "$run_dir/checkpoint_best_regular.pth" \
    --output_dir "$run_dir/val" \
    --options text_encoder_type=checkpoints/bert-base-uncased batch_size=4 epochs=30 \
    2>&1 | tee -a "$run_dir/val_console.txt"
)
```

R08通用helper后台示例：先保存helper、确认GPU1空闲并通过R08短程后再执行。本次不启动；R07已在GPU2训练，不再提供重复启动命令：

```bash
cd /home/lijiahui/research/CountGD
nohup setsid bash -c 'source runs/tpc268_v3_exclude3/diagnosis_helpers.sh; train_and_val 1 entailment config/cfg_tpc268_entailment.py 42' \
  > runs/tpc268_v3_exclude3/launch_entailment_seed42.log 2>&1 < /dev/null &
# 第1参数是物理GPU编号，执行前按实际空闲状态调整。
# R09通过门槛后：<空闲GPU> euclidean config/cfg_tpc268_euclidean.py 42。
# R06通过门槛后：<空闲GPU> organ_method config/cfg_tpc268_organ_full.py 42。
```

所有完成后的正式比较使用`<run>/val/`的best重评，不能读取训练根目录最后epoch的val_counts冒充best。训练log中的`test_mae`实际为val MAE。

```bash
uv run --no-sync python tools/compare_tpc268_runs.py \
  runs/tpc268_v3_exclude3/full_baseline_seed42/val \
  runs/tpc268_v3_exclude3/full_method_seed42/val \
  runs/tpc268_v3_exclude3/contrast_seed42/val \
  runs/tpc268_v3_exclude3/entailment_seed42/val \
  --output runs/tpc268_v3_exclude3/diagnosis_full_val.json
# 等所有列出的目录存在且best-val重评完成后执行；R09若运行，再加入euclidean_seed42/val。
```

R04完成后单独比较species_baseline_seed42/val与species_method_seed42/val；R06若运行，单独比较organ_baseline_seed42/val与organ_method_seed42/val。每次比较必须有且只有一个同caption、冻结和seed的baseline；不得把R03当成R02的baseline。

## 附录 B：决策规则：不为取得正结果反复试验

令 `ΔMAE=method−matched baseline`，负值为改善；RMSE同样记录。

| 实测情况 | 能支持的解释 | 下一步 |
|---|---|---|
| R07优于R01，R08/full较差 | contrast可能有用，蕴涵或组合可能引入干扰 | 先复跑contrast与baseline的seed43/44；不宣称双曲收益 |
| R08优于R01，R07/full较差 | TT/TV可能有用，contrast或组合可能干扰 | 对蕴涵方案复跑；若保留几何主张，再增同entailment-only目标的Euclidean新对照；R09只是full目标几何对照，不能替代它 |
| 两单项均有收益而full无收益 | 现有组合可能存在优化冲突 | 记录组合失败；不在本轮自动扫lambda或改已启动run |
| R09与R02相当/更好 | 当前实验不支持Lorentz的额外价值 | 优先简单/更稳方案；没有多seed不声称两几何等效 |
| R04优于R03，R02不优于R01 | 收益可能依赖主文本条件 | 用species配对复跑；若做organ扩展则R05/R06成对，收窄结论 |
| R02/R04最终均无收益，R07/R08也不优于R01 | 现有实现/系数在已测条件下缺乏支持 | 本轮停止自动扩展R06/R09/bridge/权重搜索及大规模多seed；保留负结果与逐图诊断 |
| 某方法MAE改善但RMSE退化 | 主/次指标存在取舍 | 明确报告取舍，不写成全面提升；可作为MAE主目标候选，但需排查高密度退化 |

单seed的ΔMAE<0仅是候选门槛，不能据此宣称有效或显著；不按噪声幅度临时发明阈值、不从test挑方案。若全部单项/组合都无收益，可以报告限定于本协议的负结果；若要作跨seed稳定无收益的结论，须另跑预先确定的关键配对，不把“未显著改善”叫作统计等效。

使用已保存的best-val逐图结果进行低成本诊断：同图误差差值、organ、GT数量固定桶`[0,20)、[20,50)、[50,100)、[100,200)、[200,+∞)`、species已见/未见及taxonomy解析/未解析。每组报告n、MAE/RMSE和有符号误差。原split有species交集，未见species须由有效train真实名单定义。

辅助日志只检查机制：有效pair数、correct/wrong-parent包含率、negative-margin违例、非法域率、半径/饱和。已记录R02非法域率0只能说明该数值检查通过，不保证实现完全正确或辅助目标有益。梯度冲突/权重过强是待验证假设；除非另开明确诊断run取得证据，不把它们写成失败原因。此阶段不修改loss系数、warmup、LR、冻结策略或架构。

## 附录 C：多seed与计算预算

- 不再默认执行原M4的R10–R19。先完成原先已启动的5组、现在已启动的R07和待执行的R08；R06/R09各额外1组，均受门槛约束。短程、重评和分组分析另计，不承诺总小时数。
- 根据seed42的**验证集**诊断选择至多一个最有证据且最简单的方案优先确认；seed42属于探索结果，保留所有已试方案，不能只报告获益者。
- 确认固定seed43、44，每个seed同时训练候选和同caption baseline（额外4组，均从原FSC147初始化、30epochs），报告seed42/43/44各自指标、配对delta、均值±sample std。三seed仍是小样本，不自动等于显著。
- 若坚持“Lorentz优于Euclidean”，必须补齐同辅助目标、同caption的Lorentz/Euclidean及对应baseline的三seed；若坚持“无需主文本物种信息仍有收益”，必须补齐organ配对三seed。未完成对应证据即放弃该强主张，不能用单seed锥指标替代。
- 全部结果无收益时不自动投入上述4组；若研究目标需要稳健的负结果，预先指定完整方法或单项的关键配对再跑43/44，明确该追加预算与有限结论。
- 纯视觉基线是输入协议核验，不是对比/蕴涵的单项消融。尚未实现前不启动；须核对CountGD视觉提示路径、正标签token和推理规则，不只把文本改成空字符串。未来若为比较论文而执行，使用新prompt协议/目录、相同原始初始化和30epoch预算，先做真实GPU检查；即使结果不同也不能自动归因于文本，仍需对齐作者训练/推理配方。

## 附录 D：测试集使用与结果冻结

R01/R03的test已经按用户明确要求提前查看（2026-10-16又按用户要求评估R02 test及R04/R05/R07阶段性best快照），属于本次研究的已暴露信息，保留并如实披露；后续选择完全基于val，不能再称整个研究过程从未查看test。原计划R04/R05/R06/R07/R08/R09配置此前已确定，本次只按验证证据调整优先级，不根据test数值挑lambda、epoch或seed。

已有test不重复跑以挑更好结果。尚未评估的任务仅在其模型/阈值固定后使用val选出的best checkpoint做一次完整test；用户另行明确要求时可执行并记录时间，不把它用于继续调参。本次计划修改不启动任何test评估。报告所有已执行预定seed，缺失项明确标出；不能把val成绩与论文test成绩直接比较。

## 附录 E：技术门槛、产物与文档

- M0当前证据：根目录preflight/gpu_checks.status为DONE、exitcode=0，summary.json记录四组约15step+999张val、finite日志和checkpoint保存；原始资产哈希见preflight/input_sha256.json。旧协议失败日志及排除图可视化若仍在旧目录，仅作历史证据，不重用旧checkpoint。
- 每个正式run保存latest/best/周期checkpoint、训练配置、console、逐epoch log；best重评保存val_counts/val_metrics。本轮以best val MAE选模型，保留对应RMSE/R2，另报末轮指标用于诊断。
- 缺文件、坐标错误、split/指纹不一致、NaN/Inf、CUDA错误、计数JSON不完整为技术阻塞；MAE没改善不是技术异常。若修复改变协议，使用新run ID并重跑匹配baseline，不接续既有optimizer。
- 不删除best/latest/原始日志，不修改或下载原数据/权重，不引入独立测试文件。`docs/`仅保留implement.md与experiment.md。每次实验/协议工作同步更新两文档，并从真实产物核实状态。
- 原计划全文备份在 `runs/tpc268_v3_exclude3/planning/experiment_before_20261015_revision.md`；旧准备/测试时点记录由本节与上方状态表统一接续，备份不作为当前调度命令。

## 附录 F：计划变更边界

- 2026-10-15修订实验优先级；2026-10-16本次整理报告。原计划和整理前文档备份在runs/planning，本次不触碰任何已有启动脚本、配置、checkpoint、数据或运行进程。
- 2026-10-17用户最新顺序：R04/R05已完成，R07照常完成；先准备R08层级蕴涵独立短程＋30轮启动命令（READY，未执行），同时继续核实P01论文全分类文本基线配方 → 条件式R06/R09 → 有候选才做确认seed → 冻结后汇总test。旧手动helper保留作历史参考，不与run_r08.sh重复执行。
- 新计划是对当前负结果的探索性响应，后续结果必须披露这一调整和实际完成项，不包装成完全预注册的验证。


## 2026-10-17 异名映射核验记录（仅建表，未改实验协议）

用户要求核实22个未解析名称并建立带证据的表。完整22项人可读核验表、逐项权威来源及边界见[implement.md末节](implement.md)；机器审计表为[config/tpc268_species_alias_audit_20261017.json](../config/tpc268_species_alias_audit_20261017.json)，待启用别名为[config/tpc268_species_aliases_verified_20261017.json](../config/tpc268_species_aliases_verified_20261017.json)，CSV为[species_alias_audit.csv](../runs/tpc268_taxonomy_audit_20261017/species_alias_audit.csv)。

结论：13项名称关系已证实，9项没有充分证据关联TPC表键；没有为了覆盖率强行凑22对。已核实表含13个新增项和此前Acacia_tortilis项，共14项，但未被现有配置引用。当前data/tpc268_metadata/species_aliases.json、原数据、排除名单、已运行实验的caption和分类协议保持不变；现有R01–R08的权重、性能记录不因本次核验改变。本次没有启动新训练或评估。

| split | 当前协议可解析 / 有效图像 | 仅试读新表的可解析数 | 理论新增解析 | 新表仍未解析 |
|---|---:|---:|---:|---:|
| train | 6545 / 6998 | 6878 / 6998 | 333 | 120 |
| val | 943 / 999 | 999 / 999 | 56 | 0 |
| test | 1895 / 2000 | 1919 / 2000 | 24 | 81 |

这些是元数据覆盖率检查，**不是新训练结果或性能提升**。当前22个名称影响614张；若仅启用13项，可关联其中413张，剩9名/201张需要作者或原始来源确认。Nubelaria与Vaccinium候选跨科，不能视为异名；几项Achyranthes疑似名称问题也未凭图像或相近拼写重标。名称同物关系也不独立证明每张照片的物种鉴定正确。数据库现在接受的名称与TPC存储键不同的，保留TPC键关联原ID，不重写整套上层分类。

激活新表会改变caption输入、train taxonomy候选和辅助监督，须建立新的taxonomy协议和匹配baseline，不能改变已启动run或沿用旧结果冒充新协议。旧registry指纹仍为cf080ec256b9f9595a0cd6110b30d80fa84da0d49799217054e682185d79d65d；离线新表指纹e72c02067bd416b61ada53630629df9386294d98be9bed3a57279ccf17a6e2d0。已有试验继续原设定，P01缺作者初始化/训练配方问题仍存在，建立异名表不等于已完全复现论文。


## 2026-10-17 P01 用户确认后的独立复现协议

P01 工作树为 runs/tpc268_paper_reproduction_20261017/worktree，分支 repro/tpc268-b6f362b-original-mask，基于 b6f362b3f5cd20db4a171faa410dfed8f2f466d8；用户明确固定 GroundingDINO Swin-B 初始化，原 exemplar all-True mask，不应用修复。当前准备中，正式训练未启动、指标未知；不修改任何已启动实验。R08 的 stage 已实际核实为 TRAINING（2026-10-17 11:39:39 +08:00），此前 READY 仅为准备时点记录。

用户最终缺失链规则：只用官方精确名称的七级链，无完整对应时只用 species，不启用自行推断/匹配的任何别名。保留原划分（代码排除既定3张）：train6998/full6258/species740，val999/full943/species56，test2000/full1895/species105。Acacia 旧异名和 × 缺省均不自行匹配。这是元数据覆盖率，不是性能；新完整图像/坐标/分词审计待执行。完整示例：Plantae, Tracheophyta, Magnoliopsida, Rosales, Rosaceae, Malus, Malus domestica.；回退：Musa sapientum.。没有 organ 或 taxonomy: 前缀。

原版 Swin-B CountGD，无对比或层级辅助项；独立原版依赖；seed42、batch4、FP32、30轮、冻结backbone.0/bert、AdamW lr1e-4 wd1e-4、StepLR10、clip0.1，原图像增强和中心损失。验证/测试batch4、3个原exemplar、整图800/max1333、阈值.23/0，无SAM/裁剪/校正。crop训练时遵循原批内最少存活exemplar规则，不重复被裁掉的框。以 val MAE 选最佳，再固定权重重评 val 和一次 test。

后台命令（准备检查通过后使用；如已启动勿重复执行）：

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_paper_reproduction_20261017/worktree/run_reproduction.sh > runs/tpc268_paper_reproduction_20261017/pipeline.console.log 2>&1 < /dev/null &
```

脚本固定GPU3且要求至少22000MiB空闲；有独占锁，SSH断连继续运行。流程 audit → 15批短程训练＋999张val → 独立重新初始化正式30轮 → best val重评 → test。详细记录在该工作树 docs/implement.md 和 docs/experiment.md；本仓库此处为索引。论文该设置 test=16.90/43.32/0.71，val未报告。作者初始化、缺失分类链处理及完整训练推理配方仍未知；加上既定3图排除与species回退，P01属于明确记录假设的公开材料复现，不能称严格逐项一致，也不能从其与R01的差值单独归因mask/文本/初始化。

2026-10-17 P01检查补记：现有环境完成全有效划分坐标和分词审计，最大46 tokens（含3个exemplar）；53份b6原核心文件逐字节相同，8组点增强检查通过。独立旧版环境/GPU检查待完成；没有训练性能记录。GroundingDINO初始化的label_enc.weight在b6 CountGD中不存在（dn_number=0），只允许这一明确的多余项，逐键加载报告保留。

2026-10-17 初始化兼容补记：官方旧权重还序列化了bert.embeddings.position_ids（1×512固定arange）；固定版Transformers将其作为非持久buffer自动生成。入口验证其内容后允许忽略；并非丢弃可学习的BERT参数。除label_enc.weight和这一固定buffer外，其余unexpected键均阻止训练。

2026-10-17 独立环境更新：uv已安装原requirements固定依赖，完整67项解析版本存requirements-reproduction.lock。Python3.9.19、torch2.2.1+cu121、torchvision0.17.1+cu121、transformers4.39.1；以CUDA Toolkit12.6、gcc/g++11、TORCH_CUDA_ARCH_LIST=8.6、MAX_JOBS=4用uv pip --no-build-isolation --no-deps编译原版ops并安装成功（ops_build.log）。固定环境也已完成全有效数据坐标/分词审计。后台入口显式uv run --offline --no-project --python指定该.venv解释器，避免继承main的Python版本选择。CUDA算子数值检查和短程训练仍待完成，正式指标未知。

2026-10-17 CUDA数值校验已完成：原版ops/test.py的float/double前向对照和D=30/32/64/71四组数值梯度检查全部True（6/6），日志为复现实验根目录ops_check.log。下一阶段为原mask检查、初始化逐键核对及短程训练；正式训练未启动、正式指标未知。

2026-10-17 12:13运行更新：复现代码已固定为492688c13a25e7bfa9566124ebebab7b99eae627，后台pipeline PID4079418，GPU3；阶段PREFLIGHT。初始化实际加载1106个GroundingDINO张量，缺失仅CountGD新增模块，额外仅已审查的label_enc与固定位置buffer。长短caption原mask运行检查通过，插入后padding仍保留且mask全True；已看到首个真实训练批次有限loss。15批+999张val完整检查尚在运行，正式30轮未开始，正式性能未知。

2026-10-17 12:17最终运行更新：P01已在GPU3正式后台训练，pipeline PID4079418，stage=TRAINING 2026-10-17T12:17:29+08:00，代码提交492688c13a25e7bfa9566124ebebab7b99eae627。原版环境/全量数据审计、6项CUDA数值检查、原all-True mask检查、GroundingDINO逐键加载及15批训练+999张val均通过，audit/preflight/train指纹一致（fb63d9616f2f98f85ea17eb75352405d1fb048d4e75334c7b8d6d7acca1e84e8）。正式训练独立重置seed42并重新加载官方GroundingDINO，没有使用短程checkpoint。epoch从0起，目前正式val最佳轮次和val/test性能仍未知，尚无完整正式训练轮次。

短程产物仅供技术验证：preflight/val_metrics.json记录15个训练批次后val n=999、MAE=34.845845845845844、RMSE=58.18040872974304、R²=0.7044194824592861；这不是30轮正式实验成绩或最终模型，不进入正式对照表。训练将完成30轮，以val MAE选best，再固定权重重评val和一次test。训练drop_last=True、评估drop_last=False沿用原规则；batch和顺序记录在协议中，原mask缺陷被保留。依赖锁、编译器、算子文件哈希见requirements-reproduction.lock、上级environment.json和ops_build/check日志。

现在已启动，勿重复执行nohup命令。监控：`tail -f runs/tpc268_paper_reproduction_20261017/train.console.log`（在主仓库根目录执行）；阶段：`cat runs/tpc268_paper_reproduction_20261017/stage`。此次仅创建独立复现工作树和新环境/权重，没有改动已启动R07/R08、主工作树原有模型修改、数据及标注。原始b6核心文件仍逐字节相同。作者未公开的训练细节仍未知，本次是明确假设下的复现，不据当前准备结果宣称复现论文性能。

2026-10-17 清理记录：按用户明确要求，仅删除P01 preflight/checkpoint.pth和preflight/checkpoint_best.pth两个预检权重，实际删除2个文件，共2500235378字节（约2.33GiB）。正式训练独立从GroundingDINO初始化，不读取这两个文件；正式train权重、审计JSON、检查日志、数据、标注和实验协议未变。


## 2026-10-17 R07完成后的下一步（核查：2026-10-17T22:18:34+08:00）

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


## 2026-10-20 R06：按用户指定准备20轮启动命令（未启动）

用户明确要求做原计划R06，但训练预算改为20轮，随后明确“给我启动命令，不需要帮我启动”。因此覆盖此前R06自动调度门槛，仅准备脚本，状态READY，不启动GPU训练或短程预检。新run ID=`organ_method_seed42_e20`，提交沿用当前HEAD `6341592d13575f3626bc70f08604b96ab231f4ef`（文档有未提交修改、runs脚本为本地产物）；实际启动提交/进程/指标尚无。GPU3准备时查询空闲24124MiB，脚本启动时重新检查至少20000MiB，显式固定`CUDA_VISIBLE_DEVICES=3`。

R06用原`config/cfg_tpc268_organ_full.py`，主caption=`{organ} .`，例如`fruit .`；训练时开启分层对比+Lorentz TT/TV，系数0.1/0.05/0.05，首轮warmup。FSC147 CountGD原权重独立初始化，不载入R05/P03/P04的TPC权重或短程checkpoint。seed42、train batch4/eval实际batch1、冻结backbone.0/bert、原增强、三图代码排除、registry/坐标协议、原阈值.23/0和StepLR每10轮衰减均沿用R系列。正式训练20轮，每轮完整val，只按val MAE选best，结束后独立重评999图val；不自动test。使用主仓库既有Python3.10.12/torch2.13.0+cu130/torchvision0.28.0+cu130/transformers4.57.6，uv显式指定`.venv/bin/python`并离线/no-project，不同步或安装环境。

**预算对齐**：有效配置与R05逐项比较，只有epochs30→20、两项辅助开关False→True。R05训练日志虽将val字段命名`test_*`，已检查`test_split=val`；30条完整日志中，前20轮val MAE最优仍是第12轮，等于全30轮最优：MAE10.476476476476476、RMSE30.35284657647937、R²0.9195509124443442。因学习率使用StepLR而非依赖总epochs的日程，可用R05原训练前20轮作为等预算参照，无需重复训练R05；不能把R06的20轮结果标为与30轮完整搜索预算相同。R05历史训练工作区dirty、完整源码不可变归档不足的既有边界仍保留。P04属于不同环境/输入协议，不是R06的匹配基线。

启动脚本：[run_r06_e20.sh](../runs/tpc268_v3_exclude3/run_r06_e20.sh)。包含flock、防已有训练产物隐式resume/覆盖、退出码/status/stage、启动时配置/环境检查及源码/数据协议/初始化hash清单。既有10月13日organ_full技术检查通过属于历史证据，不冒充本次已跑GPU预检；本次只执行bash语法、内嵌Python语法、有效配置与R05前20轮日志核对，准备记录：[r06_e20_prepared_20261020.json](../runs/tpc268_v3_exclude3/planning/r06_e20_prepared_20261020.json)。模型、loss实现、原配置及数据集未改，两份docs同步更新。

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_v3_exclude3/run_r06_e20.sh \
  > runs/tpc268_v3_exclude3/launch_organ_method_seed42_e20.log 2>&1 < /dev/null &
```

查看进度（启动日志也包含训练与最终best-val输出）：

```bash
tail -f runs/tpc268_v3_exclude3/launch_organ_method_seed42_e20.log
```


## 2026-10-20 R08-LC：可学习曲率、20轮，只准备启动命令

用户明确要求R08可学习曲率版本训练20轮，并给出命令；本次没有启动真实训练、短程数据预检或GPU评估。ID=`R08-LC`，run=`entailment_learnable_seed42_e20`，状态READY。当前HEAD仍为`6341592d13575f3626bc70f08604b96ab231f4ef`，新配置/文档尚未提交，实际训练commit/PID/指标未知，启动时另存HEAD、diff和源文件hash。运行配置：[cfg_tpc268_entailment_learnable.py](../config/cfg_tpc268_entailment_learnable.py)，脚本：[run_r08_learnable_e20.sh](../runs/tpc268_v3_exclude3/run_r08_learnable_e20.sh)。

配置继承原R08，仅`learn_curvature=False→True`及`epochs=30→20`。保持`curvature_init=1`，空间曲率为−c，TT/TV共享一个全局log_c参数，有效c范围[0.1,10]；原有alpha_t/alpha_v继续学习，曲率无额外正则/独立学习率变更，沿用原AdamW lr1e-4、weight decay1e-4、StepLR10。只有TT/TV辅助损失（系数.05/.05、含既有bridge与TT负父项），对比损失关闭。主caption仍是R系列full_taxonomy：`{organ} of {species}; taxonomy: {Kingdom}, ..., {Species} .`，缺链按既有species回退。相同FSC147 CountGD权重独立model初始化、seed42、train batch4/eval实际batch1、冻结backbone.0/bert、原增强及三图代码排除，6998/999/2000、registry/坐标/整图阈值.23/0全部保持。禁止用R08已训练或短程权重续训新实验。

使用主仓库原Python3.10.12/torch2.13.0+cu130/torchvision0.28.0+cu130/transformers4.57.6；uv离线no-project、显式主`.venv/bin/python`，不更新环境。训练20轮，每轮全量val，按val MAE选择best，完成后重评999张val，不自动test。日志已有`train_tax_curvature_unscaled`，配合TT/TV损失、锥非法率/饱和率及alpha尺度诊断；曲率变化或辅助loss下降不代表计数改善。既有val_metrics.training_protocol没有curvature_init/learn_curvature字段，本次不修改训练核心代码，两个字段完整保存在新配置、config_args_all/checkpoint args及launch_manifest.curvature_protocol，不把旧协议摘要误当完整曲率配置。

**等预算参照**：原R08的30条日志均为val（原字段前缀test），前20轮最低val MAE仍是第12轮，等于全30轮best：9.987987987987989/29.508520002750945/0.9239643740684884。StepLR不依赖总预算，后续R08-LC与R08前20轮val选择范围配对，不冒称与30轮搜索预算相同。R08历史源码dirty/不可完整重建边界保留；本次属于已查看历史test后的探索性实验，不依据新test改阈值、lambda或挑epoch。

技术检查：bash -n、内嵌Python AST、相对R08有效配置只差上述两项、R08前20轮选择均通过。真实代码的CPU合成几何反向检查确认log_c为Parameter且唯一进入优化器，梯度0.25372225046157837有限且非零，一次AdamW step使c从1更新为0.9998999834060669，锥非法数0。这只是合成数据CPU技术检查，不是CountGD训练或性能。准备证据：[r08_learnable_e20_prepared_20261020.json](../runs/tpc268_v3_exclude3/planning/r08_learnable_e20_prepared_20261020.json)。没有修改损失/模型/训练主程序或其他在训实验，数据及标注未变。

默认计划GPU1（`R08_GPU`可改为另一单卡索引）；实时GPU查询的自动审批超时，当前GPU1空闲状态未知。脚本会在实际启动时重新检查指定卡至少20000MiB空闲，不自动抢占/转移到GPU0；独立flock、防已有训练产物隐式resume，保存日志/status/stage/exitcode及协议来源。启动命令不由本次助手执行：

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
R08_GPU=1 nohup setsid bash runs/tpc268_v3_exclude3/run_r08_learnable_e20.sh \
  > runs/tpc268_v3_exclude3/launch_entailment_learnable_seed42_e20.log 2>&1 < /dev/null &
```

查看进度：

```bash
tail -f runs/tpc268_v3_exclude3/launch_entailment_learnable_seed42_e20.log
```


同期只读补记：R06的`organ_method_seed42_e20/status`实际记录`RUNNING 2026-10-20T10:20:16+08:00`、stage=`TRAINING`，配置文件已生成，故主状态表由早先READY更新为状态文件已启动，未核查GPU/PID或轮次，不把文件状态当作当前活进程证明。本助手本次未执行R06或R08-LC启动命令。


## 2026-10-20 R08-GD：GroundingDINO初始化来源对照（准备）

用户要求在R08基础上使用GroundingDINO初始化并使用GPU2。本次沿用原版R08固定曲率c=1、30轮预算，不继承另一个R08-LC的可学习曲率或20轮设置。ID=R08-GD，run=`entailment_groundingdino_seed42`，复用`config/cfg_tpc268_entailment.py`。准备时HEAD=`6341592d13575f3626bc70f08604b96ab231f4ef`，新入口及文档未提交，启动另存HEAD/diff/hash。宿主机已核实GPU2空闲24124MiB/0%，入口重新检查至少20000MiB。不改其他训练。

唯一实验因素为初始化来源：FSC147 CountGD改为`checkpoints/groundingdino_swinb_cogcoor.pth`，SHA256=`46270f7a822e6906b655b729c90613e48929d0f2bb8b9b76fd10a856f3ac6ab7`。共享1106项张量严格匹配并加载；GroundingDINO缺少的40项CountGD参数（feature_map_proj及feature_map_encoder）保留原构造初始化，taxonomy辅助分支12项参数/持久buffer同样保留原初始化。固定BERT position_ids必须为arange，label_enc为当前dn_number=0模型不使用的源参数，明确丢弃这两项；任何其他缺失/额外项或shape差异报错。初始化因素包含CountGD专有模块是否经过预训练，不解释为仅更换视觉backbone。独立seed42、fresh optimizer/scheduler/RNG，不加载FSC147/TPC权重或CPU检查模型。

其余与R08相同：主caption为R系列`{organ} of {species}; taxonomy: {Kingdom}, ..., {Species} .`，缺链原species回退/registry/alias策略，非P系列官方模板；修复mask，3个visual exemplars，TT/TV系数.05/.05、contrast关闭、固定Lorentz曲率−1、原冻结/增强/2px中心监督，FP32、train batch4/eval实际batch1、AdamW lr1e-4 wd1e-4 StepLR10，三图代码排除及6998/999/2000划分，整图800/1333、阈值.23/0，无额外推理后处理。主环境Python3.10.12/torch2.13.0+cu130/torchvision0.28.0+cu130/transformers4.57.6；uv离线/no-project显式`.venv/bin/python`，不安装或同步环境。数据及标注不改。

专用入口`tools/train_tpc268_groundingdino.py`只在该进程fresh初始化阶段设置严格GroundingDINO加载边界，正常评估使用原main.py；共享main/model/loss/loader不变。启动脚本`runs/tpc268_v3_exclude3/run_r08_groundingdino.sh`固定CUDA_VISIBLE_DEVICES=2，flock、防已有产物隐式resume/覆盖、GPU空闲检查、status/stage/exitcode及初始化报告/源码/数据协议/环境hash。流程为30轮训练、每轮完整val按MAE选best、结束独立重评999图val；不自动test。

已通过bash语法、入口及内嵌Python AST、有效配置与原R08逐项完全一致检查；实际CPU构建CountGD并严格加载权重通过，报告`runs/tpc268_v3_exclude3/planning/r08_gd_initialization_cpu_20261020.json`，不冒充真实训练/性能。原R08配对参照为30轮、第12轮best-val 9.987987987987989/29.508520002750945/0.9239643740684884；历史dirty源码缺少完整不可变归档的边界仍保留。此次仅检验本R08协议/seed下初始化来源，不跨P系列归因；已看历史test后提出，属于探索性实验，不用test选epoch/调参。

后台启动命令（本次用户已授权执行）：
```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_v3_exclude3/run_r08_groundingdino.sh > runs/tpc268_v3_exclude3/launch_entailment_groundingdino_seed42.log 2>&1 < /dev/null &
```
进度：`tail -f runs/tpc268_v3_exclude3/launch_entailment_groundingdino_seed42.log`。此段为准备记录，实际启动/首批检查另记；正式best/val/test尚未知。两份docs同步更新。


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


## 2026-10-21 R08-GD-LC：GroundingDINO初始化、可学习曲率、TT/TV-only，20轮（准备）

用户要求独立训练该设置20 epochs，本次准备并后台启动。ID=R08-GD-LC，run=`entailment_groundingdino_learnable_seed42_e20`，GPU1（启动前实查24124MiB空闲/0%，GPU3亦空闲）；不占用GPU2的R08-GD，后者只读日志已完成13轮且继续原30轮预算，不重启或改配置。新实验复用`config/cfg_tpc268_entailment_learnable.py`，独立入口`tools/train_tpc268_groundingdino_learnable.py`，本地启动脚本`runs/tpc268_v3_exclude3/run_r08_groundingdino_learnable_e20.sh`。当前HEAD=6341592d13575f3626bc70f08604b96ab231f4ef，新入口/配置尚未提交；正式启动另存commit/hash/原始参数及diff，不仅凭HEAD识别运行源码。

计数主损失保留；辅助目标只有Lorentz TT/TV（各0.05，含原TT负父项/bridge），分层对比关闭。TT/TV共享可学习log_c，初始c=1、空间曲率−c、有效范围[0.1,10]，继续学习alpha_t/alpha_v；沿用AdamW lr1e-4/wd1e-4、StepLR10，无曲率专用学习率或额外正则，首轮辅助warmup。seed42、20轮、FP32、train batch4/eval实际batch1、冻结backbone.0/bert、原resize/crop增强/2px中心监督、三图代码排除、原registry/alias/坐标协议和6998/999/2000、3exemplars及整图800/1333阈值.23/0全部保持。主caption仍为R系列`{organ} of {species}; taxonomy: {Kingdom}, ..., {Species} .`，缺链原species回退；保留修复mask，不切换P系列模板或旧mask。

模型独立从官方`checkpoints/groundingdino_swinb_cogcoor.pth`初始化，SHA256=46270f7a822e6906b655b729c90613e48929d0f2bb8b9b76fd10a856f3ac6ab7。复用已核验的严格GroundingDINO加载函数：共享1106项加载，40项CountGD专有参数及12项taxonomy参数/持久buffer按seed42构造初始化；只丢弃已知label_enc及固定arange position_ids，其他差异拒绝。不从任何TPC/FSC147已训练权重或CPU检查模型续训，不加载预训练optimizer/scheduler/RNG。主仓库既有.venv和Python3.10.12/torch2.13.0+cu130/torchvision0.28.0+cu130/transformers4.57.6，uv离线no-project显式解释器，不安装或同步环境。

配对关系预先固定：①对R08-LC同为20轮、有效配置完全相同，只更换初始化来源；②对R08-GD同GroundingDINO初始化与TT/TV实现，只有learn_curvature=False→True以及预算30→20，后续按R08-GD前20轮val MAE选择的权重比较，StepLR不依赖总epochs；现有R08-GD尚未完成20轮，此参照的best/性能未知，不把当前13轮best或未来30轮best直接当等预算结果。新实验只按20轮val MAE选best，结束独立重评999图val，不自动test。已看历史test后提出，属于探索性对照，不按test调阈值/曲率/lambda或选epoch。

新入口只为本进程fresh训练设置初始化适配；旧`tools/train_tpc268_groundingdino.py`及原R08-GD脚本/共享main/model/loss/Dataset均未改，新旧入口复用相同严格加载函数。旧入口hash仍等于其launch_sources快照。启动脚本核对两对照的有效配置差异及全部训练manifest源码/资产hash、环境/权重SHA，CPU实际构造/严格加载并检查log_c为Parameter、唯一进入优化器、有限非零梯度及一步更新，然后另进程重新初始化seed42正式20轮。flock、防已有训练产物隐式resume/覆盖、GPU空闲检查、status/stage/exitcode、运行源码与曲率清单均保留。

bash -n、新入口和内嵌Python AST已通过；真实CPU/GPU检查待启动脚本执行，不提前写通过，不填未知best/val/test。数据、标注、环境及已有训练不改；两份docs同步记录。

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_v3_exclude3/run_r08_groundingdino_learnable_e20.sh > runs/tpc268_v3_exclude3/launch_entailment_groundingdino_learnable_seed42_e20.log 2>&1 < /dev/null &
```
进度：`tail -f runs/tpc268_v3_exclude3/launch_entailment_groundingdino_learnable_seed42_e20.log`。此段为准备记录，实际启动核验另记。


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


## 2026-10-21 R06-ELC：器官文本、删除对比、可学习曲率、20轮（准备）

用户明确要求基于R06，删除对比损失、只保留双曲蕴涵辅助目标并采用可学习曲率，空闲GPU后台训练20轮。新ID=R06-ELC，run=`organ_entailment_learnable_seed42_e20`，GPU3；首次GPU查询曾见其他用户短时占用约5GiB，复查已退出、24124MiB空闲/0%，启动脚本再次要求used≤64MiB且free≥20000MiB，避免与现有任务共享训练卡。GPU1/GPU2上的R08-GD-LC/R08-GD不变。

新增`config/cfg_tpc268_organ_entailment_learnable.py`继承R06的cfg_tpc268_organ_full.py，设置use_level_contrast=False、learn_curvature=True、curvature_init=1、epochs=20。有效配置与R06实际20轮配置逐项核对，只差contrast True→False、曲率学习False→True；与20轮R08-LC只差prompt_mode full_taxonomy→organ。主caption仍为`{organ} .`（如`fruit .`），不额外加入species/taxonomy主文本，但训练辅助TT/TV继续按原registry使用分类及species-organ任务文本。保留CountGD计数主损失；TT/TV各0.05，含原TT负父项/bridge，分层对比计算关闭，lambda_contrast存储值虽为0.1但不产生该loss。

共享Lorentz曲率由c=1起学习，有效c范围[.1,10]，空间曲率−c；既有alpha_t/alpha_v仍学习；普通AdamW参数组lr1e-4/wd1e-4、StepLR10、首轮辅助warmup，无新增几何公式/正则或曲率专用lr。相同FSC147 CountGD checkpoint_fsc147_best.pth独立model-only初始化（SHA256=c1bab864b17db345b4c6e3aaabb5765bc2c0a90d0bc8defb5e664a74a50aa126），不从R06/TPC最佳权重或技术检查模型续训，不载入预训练optimizer/scheduler/RNG。seed42，train batch4/eval实际batch1，FP32、workers4、原冻结/增强/2px中心监督、修复mask、三图代码排除6998/999/2000、registry/坐标协议、3exemplars和整图800/1333阈值.23/0均保持。数据及标注不改。

现有主.venv，uv --offline --no-project显式解释器，不安装/同步环境。沿用已经审计的nvitop监控dev元数据差异：63个原已安装依赖版本、Python/torch/torchvision/transformers和native扩展hash仍要求与审计完全一致；相对R06/R08-LC只允许pyproject/uv.lock两个已知新hash，模型/数据/旧配置任何变化均拒绝。记录完整新环境元数据；不声称site-packages逐字节相同，后续确认性配对仍应统一完整快照。

本地脚本`runs/tpc268_v3_exclude3/run_r06_entailment_learnable_e20.sh`：flock/空闲GPU检查、防已有产物隐式resume、保存commit/diff/源文件及初始化/data协议hash、CPU实际构造并用原严格load_countgd_state加载FSC147（仅允许新增12项auxiliary状态）、log_c Parameter与优化器唯一性/有限非零合成几何梯度/一步更新检查；该CPU模型丢弃，另进程fresh seed42正式20轮，每轮完整val按MAE选best，结束重评999图best-val，不自动test。训练入口仍为原main.py，不更改共享模型/loss/Dataset/其他在训配置。

配对解释：相对R06同时“关闭对比”和“学习曲率”，任何差异只能归因这组联合改动，不能隔离其中一项；R08-LC为同初始化/目标/曲率/20轮而仅主prompt不同的参照；R05前20轮best仍第12轮，可作为organ无辅助基线的等选择预算参照，但其历史dirty源码边界保留。新实验在看过R06/R08-LC测试后提出，属于探索性验证，不用test挑epoch或调阈值/曲率/lambda。准备HEAD=6341592d13575f3626bc70f08604b96ab231f4ef，配置/文档及既有入口有未提交改动，正式启动身份由hash/参数清单记录；当前尚无真实best/val/test，实际CPU/GPU检查待运行。两份docs同步更新。

```bash
cd /home/new_space_1/new_space_1_for_lijiahui/research/CountGD
nohup setsid bash runs/tpc268_v3_exclude3/run_r06_entailment_learnable_e20.sh > runs/tpc268_v3_exclude3/launch_organ_entailment_learnable_seed42_e20.log 2>&1 < /dev/null &
```
进度：`tail -f runs/tpc268_v3_exclude3/launch_organ_entailment_learnable_seed42_e20.log`。此段为准备记录，实际启动另记。


### 2026-10-21 R06-ELC短时GPU占用与自动等待

首次后台PID1385232仅运行预检查：17:29:13启动时GPU3再次有其他任务约4806MiB占用、free19319MiB，因此空闲断言拒绝并退出1；没有模型训练或checkpoint/log.txt，证据保留新run/prelaunch_attempt_1/。不终止或调整其他用户进程。

新脚本改为先完成CPU配置/权重/梯度检查，随后在后台每15秒只读查询GPU3；used≤64MiB且free≥20000MiB时才进入正式TRAINING，新状态WAITING_FOR_GPU、启动前gpu_at_training_start.csv及manifest.idle_gpu_at_training_start记录实际空闲证据。CPU检查模型丢弃，正式进程仍从原FSC147/seed42 fresh初始化，20轮协议不变。此改动只涉及新脚本调度，不改已有训练或模型/数据/环境；两份docs同步记录。重试PID/真实训练状态待核实。


### 2026-10-21 R06-ELC正式训练已启动（2026-10-21T17:32:33.971827+08:00）

run=organ_entailment_learnable_seed42_e20，GPU3，后台PID1386799/训练PID1387249，宿主机已核实PPID1/SID1386799/无TTY，实际GPU3分配训练进程显存9228MiB（核实时瞬时值），nohup+setsid防SSH断连。进入TRAINING于17:31:27，此时GPU3实测used1MiB/free24124MiB，空闲门槛已通过，不与启动前短时任务共享。当前第1/20轮（epoch0），最新batch20/1749，完整轮次0；best/val/test均未知。

预检实际CPU模型严格加载FSC147共享1146项，仅允许新增12项taxonomy参数/持久buffer，unexpected为空；新log_c为Parameter且唯一进入优化器，合成几何梯度0.2475481778383255有限非零，AdamW一步使c由1→0.9998999834060669。正式训练另进程从原FSC147重新seed42初始化，未使用CPU检查状态，也没有从R06最佳或最后一轮续训。

真实GPU前20批loss有限，最新loss=4.9626；包含loss_entail_tt/loss_entail_tv、不含loss_level_contrast，锥非法率0。曲率由初始1更新至日志0.9994，确认实际训练中正在学习，但不推断性能。有效配置与R06只差use_level_contrast True→False及learn_curvature False→True，与R08-LC只差prompt_mode；76/77份原源码/资产hash一致，另外pyproject/uv.lock仅为已审计监控元数据差异，63项原依赖版本及native hash保持匹配。保留该环境身份边界，不声称整体site-packages逐字节相同。

启动HEAD=6341592d13575f3626bc70f08604b96ab231f4ef，新配置/文档及此前工作区修改尚未提交；launch_sources保存新配置/脚本、pyproject/uv.lock和环境审计快照及hash，launch_manifest记录曲率协议、初始化/data/source hash与启动前GPU空闲证据，launch_verified记录进程和首批日志检查。数据/标注、main/model/loss/Dataset及已有运行均未改。训练继续预定20轮，每轮完整val按MAE选best，结束重评999图best-val，不自动test。两份docs同步更新主状态表及本记录，之前PREPARING/首次预检失败均为历史记录；当前正式TRAINING。

进度：`tail -f runs/tpc268_v3_exclude3/launch_organ_entailment_learnable_seed42_e20.log`；启动已成功，无需再次执行。


## 2026-10-22 R08-GD第25轮最佳权重完整测试集评估（准备）

已读取run `entailment_groundingdino_seed42` 的30条完整val日志、DONE/exitcode0及独立best-val；训练于08:23:56结束，按30轮最低val MAE选择第25轮（epoch24），val999图=10.565565565565565/33.0083709466637/0.9048583997504364（MAE/RMSE/R²）。此前该run没有test产物。用户授权评估，宿主机09:41核实GPU2空闲（used1MiB/free24124MiB）；不占用GPU1/GPU3的在训任务。

新增本地脚本 `runs/tpc268_v3_exclude3/run_r08_groundingdino_test.sh`，沿用既有best-test实现，显式GPU2/uv离线原解释器/nohup+setsid、flock和防重复结果，严格加载完整最佳checkpoint，不重新训练或使用GroundingDINO原始权重作推理。沿用R08-GD full_taxonomy、3 exemplar、修复mask、三图排除、整图800/max1333、阈值0.23/text0、无crop/SAM/NMS/计数校正，实际eval batch1。完整2000图test；只评估val选定的第25轮，不按test选择epoch或调参。

预检查记录checkpoint轮次/val/曲率与有效配置、源文件和数据hash、GPU/源码HEAD及dirty diff；仅允许已审计nvitop监控依赖导致的pyproject.toml/uv.lock两个精确hash差异，逐项复查63项原依赖版本及native hash。保留完整环境身份差异，不声称所有文件逐字节相同；不安装/同步依赖。完成后核对全部测试路径唯一且等于官方split、GT等于原始点数、整数预测，并独立重算三指标，核对best-val推理协议及测试前后权重SHA。产物写入run的`test_final/`，实测指标/启动PID/完成状态待运行后记录。模型/loss/config、数据/标注均未改，两份docs同日同步更新。

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_r08_groundingdino_test.sh > runs/tpc268_v3_exclude3/launch_entailment_groundingdino_seed42_test.log 2>&1 < /dev/null &
tail -f runs/tpc268_v3_exclude3/launch_entailment_groundingdino_seed42_test.log
```

### 2026-10-22 R08-GD测试已启动（09:44 Asia/Shanghai）

启动预检通过，后台PID2175382/推理PID2175880，宿主机核实PPID1、SID2175382、无TTY，GPU2实际推理显存约3004MiB。09:44:05进入RUNNING，已处理140/2000图。checkpoint epoch24与完整30轮最低val MAE一致，固定c1；源文件/数据/初始化hash除两项已审计监控元数据外均匹配，63个原依赖版本及native hash通过。证据`test_final/checkpoint_metadata.json`、`dependency_metadata_audit.json`、`gpu_at_eval_start.csv`与`launch_verified.json`。此时没有完整test指标，待结束核验。其余在训任务不受影响，两份docs同步记录。


## 2026-10-22 R08-GD完整测试完成与核验修正（09:52 Asia/Shanghai）

run `entailment_groundingdino_seed42`，第25轮（epoch24）best，固定c=1。GPU2于09:44:05开始，全部2000图推理于09:51:24前完成；最终指标MAE=19.024，RMSE=49.7240786742198，R²=0.6219300579384277。独立best-val999图=10.565565565565565/33.0083709466637/0.9048583997504364。训练/评估HEAD均实查为6341592d13575f3626bc70f08604b96ab231f4ef，但训练入口及其他修改未提交，身份以launch_manifest/source hash和工作区记录为准。

初次pipeline退出1是**推理后的核验脚本错误**：从20轮脚本适配30轮时，字符串替换误将`len(rows) == 2000`变成`== 3000`；实际模型推理完整、输出2000图。只将预期数恢复官方2000，未修改任何计数/指标文件、模型、配置、阈值、权重或数据，未重跑推理。原FAILED/exitcode1/原脚本保存`test_final/verification_attempt_1/`，修正脚本保存`eval_script.sh`；`verification_recovery.json`保留推理0、原后处理1、修正核验0及恢复过程。最终状态DONE，exitcode0表示修正核验完成，不抹去原pipeline失败。

09:52:23独立核验通过：2000路径唯一且完全等于官方test split，GT逐图等于原始annotation点数，预测为非负整数，MAE/RMSE/R²重算一致（R²浮点末位差异在容差内）；推理及training_protocol与独立best-val一致。最佳checkpoint SHA256=`806bd3ca6d7e55a806ee8848d269d2ade2c03c714d1ae05d5c99c780fd3a04b5`，测试前后相同。80份原源码/资产hash保持一致，只有已审计两个监控依赖元数据文件不同，63项原依赖实际版本和native hash再次检查通过；保留完整环境身份边界。09:52:51宿主机核实GPU2已释放（used1MiB/free24124MiB），GPU1/GPU3原训练进程仍在。

相对同30轮的固定曲率R08：test ΔMAE=+5.335（+38.97289795%），ΔRMSE=+12.517103521703035（+33.64181977%），ΔR²=−0.16638625597000756；val三指标也较差。本次单seed对照支持FSC147 CountGD初始化比GroundingDINO初始化更适合当前TT/TV全分类文本协议，不能证明双曲几何本身无效。R08-GD-LC只训练20轮，其固定曲率配对应取R08-GD前20轮val选择范围，本次30轮第25轮权重不可冒称该等预算参照；本次不据test修改后续训练或选择其他epoch。

证据：`test_final/test_metrics.json`、`test_counts.json`、`checkpoint_metadata.json`、`verified.json`、`checkpoint.sha256`、`verification_recovery.json`及完整console；汇总`planning/r08_gd_test_results_20261022.json`。两份docs同步更新状态/结果和分析；本次实现仅本地评估脚本及其核验修正，模型/loss/config、数据/标注和既有训练均未修改。


## 2026-10-22 R08-GD-LC训练完成与最佳权重test准备（13:56核查）

新结束实验为R08-GD-LC，run `entailment_groundingdino_learnable_seed42_e20`，训练/最佳权重独立val于13:23:37 DONE、退出0，20条完整val日志按最低MAE选第12轮（epoch11），val999图=10.891891891891891/31.309859586195962/0.9143978821993909。尚无test产物。与此同时R06-ELC仍在GPU3训练（本次只读快照完成17轮，当前轮次未精确核查），不是此次新完成实验。

设置保持原计划：GroundingDINO Swin-B原始权重fresh初始化（非FSC147 CountGD、非TPC续训），CountGD主计数损失保留，辅助仅Lorentz TT/TV .05/.05，contrast关闭；TT/TV共享可学习c，初始1、范围[0.1,10]，投影头/学习尺度及原TT负父项/bridge均不改。主caption为R系列`{organ} of {species}; taxonomy: {Kingdom}, ..., {Species} .`，分类不全按原R协议回退species；评估3图像exemplar。seed42、20epochs、train batch4/eval实际batch1、原冻结/增强/AdamW/StepLR10/修复mask/三图代码排除及原环境保持。

用户授权缺失test则补测。新增本地`run_r08_groundingdino_learnable_test.sh`，固定GPU1/uv离线原解释器，nohup+setsid、flock、防覆盖、严格完整best checkpoint加载，绝不重新初始化或续训。当前各GPU均有其他任务，13:56实查GPU1剩余17891MiB，选择该卡共享评估，预检和正式开始再次要求至少8192MiB；此前同类测试进程约3004MiB，不终止/调整任何既有任务。不把共享卡写成空闲卡。

完整2000图test，沿用训练对应全分类caption/3exemplar及整图800/max1333、阈值.23/text0、无crop/SAM/计数校正；仅评估val选定的第12轮。新脚本逐项复查训练清单89份源码/资产hash、63项原依赖实际版本/native hash、有效配置及best轮次，记录best实际c。该run启动时已审计nvitop监控元数据，因此本次要求与其自身完整manifest hash一致，不另忽略文件差异。完成后核对官方2000唯一路径、GT原始点数、非负整数预测、重算三指标、best-val协议和checkpoint前后SHA；准备阶段PID/实际test/c暂未知。

配对参考：R08-LC同20轮仅初始化不同；R08-GD固定曲率的**前20轮**最佳同为第12轮，日志val=10.578578578578579/31.36271065484646/0.9141086453992188，不能拿其30轮第25轮当等预算曲率参照，前20轮参照test尚未知。此处仅由日志核对选择范围，不额外启动固定曲率权重测试，也不按test调参。两份docs同步更新；模型/loss/config、数据/标注和已有训练均不改。

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_r08_groundingdino_learnable_test.sh > runs/tpc268_v3_exclude3/launch_entailment_groundingdino_learnable_seed42_e20_test.log 2>&1 < /dev/null &
```

### 2026-10-22 R08-GD-LC测试已正式运行（13:58:47核实）

13:58:28进入RUNNING，后台PID2474953（PPID1/SID2474953/无TTY），推理PID2475436；宿主机实查GPU1约3004MiB，该卡原进程2422347约6224MiB仍在，未终止或改动既有任务。完整best checkpoint严格加载missing/unexpected均为空，epoch11=第12轮；最佳权重c=0.6318109631538391，SHA256=c96f5f5393cf5374b017e47ce16ea7a16fa2964b0e72e87adc7acea53ff39c8f。89份源码/资产hash与本run训练manifest逐项相同，63项原依赖实际版本/native hash一致；源HEAD及dirty diff、实际显存/进程及最佳权重信息留存test_final。训练参数/推理协议未改；当前仅确认启动，完整test指标待结束核验。两份docs同步记录。


## 2026-10-22 R08-GD-LC第12轮best完整测试完成（14:07:58）

run `entailment_groundingdino_learnable_seed42_e20`，20轮/seed42，训练及独立best-val于13:23:37 DONE/退出0；新测试于13:58:28开始、14:07:58 DONE/退出0。GPU1共享推理约9分07秒，后台PID2474953、推理PID2475436，14:08:30实查测试进程显存已释放，该卡原任务2422347及GPU3原训练仍在。未改动或终止其他进程。

| 数据 | 最佳轮次 | 图像数 | MAE | RMSE | R² |
|---|---:|---:|---:|---:|---:|
| val（独立best重评） | 12 | 999 | 10.891891891891891 | 31.309859586195962 | 0.9143978821993909 |
| test（本次实测） | 12 | 2000 | 15.462 | 42.50356455639927 | 0.7237582172256081 |

最佳权重c=0.6318109631538391，初始c1；共享可学习Lorentz曲率，TT/TV .05/.05、无contrast，CountGD主计数损失保留。输入为3图像exemplar + R全分类文本（含organ/species及taxonomy；缺失分类链按原R协议回退species），不是P系列官方逗号文本。GroundingDINO原始Swin-B fresh初始化，非FSC147模型续训；冻结、增强、优化、修复mask、三图排除、seed42和整图阈值/推理设置均沿用本run原协议。评估实际batch1，checkpoint metadata额外记录learn_curvature/初始c/最佳c，补足旧training_protocol摘要未包含这些字段的边界。

14:07:57独立核验：2000条路径唯一且完全等于官方test split，GT等于原annotation点数，预测为非负整数；从逐图计数重算MAE/RMSE/R²一致（R²末位浮点误差在容差内）；推理设置及training_protocol与best-val一致。checkpoint SHA256=`c96f5f5393cf5374b017e47ce16ea7a16fa2964b0e72e87adc7acea53ff39c8f`，测试前后未变。89份源/资产hash与该训练启动manifest完全相同，63项原依赖实际版本/native hash检查通过。训练/测试HEAD实查均6341592d13575f3626bc70f08604b96ab231f4ef，dirty源身份仍以清单/hash/diff为准；本run启动时已有已审计nvitop元数据，未更换或同步环境。

同20轮、同可学习曲率的初始化配对R08-LC：val MAE+6.46771037%、RMSE+9.37897012%、R²−0.014050929704103043；test MAE+4.322（+38.79712747%）、RMSE+9.638765758901663（+29.32854030%）、R²−0.11108340194321409。当前seed42下改GroundingDINO初始化没有性能收益。与GD30轮最终test相比三指标较好，但20与30轮选择范围不同，不据此归因曲率；GD前20轮最优第12轮val=10.578578578578579/31.36271065484646/0.9141086453992188，对应test尚未知。因此当前GD初始化下尚无完整等预算test的曲率结论，也不能扩大成所有双曲方案均无效；不据test改变在训实验、阈值或选择epoch。

证据位于`test_final/`：`test_metrics.json`、`test_counts.json`、`checkpoint_metadata.json`、`verified.json`、`checkpoint.sha256`、`launch_verified.json`、`gpu_at_eval_start.csv`、`status`/`exitcode`及完整console/脚本快照。汇总`planning/r08_gd_lc_test_results_20261022.json`。两份docs同步更新主表与分析；本次仅本地评估脚本/结果记录，无模型/loss/config、数据/标注改动。


## 2026-10-22 虚拟环境终端提示名称修正（不改变实验协议）

用户已将`.venv/pyvenv.cfg`的prompt改为countgd，但uv创建环境时生成的激活脚本仍嵌入hgic，激活不会重新从pyvenv.cfg读取该字段，因此自动激活继续显示旧名称。本次只把主`.venv/bin/`下activate、activate.bat/csh/fish/nu/ps1/xsh与activate_this.py中的嵌入提示名称统一为countgd，保留其他字节/换行及脚本权限；pyvenv.cfg沿用用户设置。已用独立bash实际激活/退出验证提示名称及原提示恢复。

这仅影响后续shell激活时显示的环境名称，不修改解释器、依赖包、CUDA算子、pyproject/uv.lock、训练/推理代码、数据或实验协议；现有运行进程和实测结果不变，无需新实验基线。已打开终端需要重新source .venv/bin/activate或重开终端才能更新其进程内提示。两份docs同日同步补记。


## 2026-10-23 R06-ELC训练完成与第18轮best测试准备（10:50核查）

用户要求核查新结束实验，缺少test则补测。实际新完成为R06-ELC，run `organ_entailment_learnable_seed42_e20`，训练及独立best-val于10月22日16:46:26 DONE、退出0；完整20条训练/val日志按最低val MAE选择第18轮（epoch17），独立val999图=10.186186186186186/32.983570393696255/0.9050013136725523。此前第5轮best已被更新；不能把旧进度中的最佳性能当作最终best。当前该run尚无test产物。10:50实查GPU0–3全部无计算进程，均24124MiB空闲，本次选GPU3评估。

设置沿用原R06-ELC：FSC147 CountGD原始checkpoint独立fresh初始化（不是GroundingDINO、不是从R06权重续训），organ主caption `{organ} .`（如`fruit .`，含语义文本，不是纯视觉），验证/test3图像exemplar；CountGD主计数损失保留，辅助仅原Lorentz TT/TV .05/.05、contrast关闭，TT负父项/bridge保持，TT/TV共享可学习c（初始1，范围[.1,10]）。seed42、20epochs、train batch4/eval实际batch1、原冻结/增强/AdamW/StepLR10、修复mask、三图代码排除/registry及环境不变。最佳权重实际c待checkpoint读取，不用末轮训练日志均值替代。

新增本地`runs/tpc268_v3_exclude3/run_r06_entailment_learnable_test.sh`，复用已验证20轮best-test脚本，仅固定本run/config/GPU3/最佳epoch17和FSC147+organ预检；bash与内嵌Python语法检查通过，保留明确20轮/2000图断言。nohup+setsid、防重复flock、uv离线原解释器，不重新训练/初始化。开始前复查当前剩余显存≥8192MiB、20轮val选出的最佳checkpoint/配置、训练清单89项源/资产hash、63项原依赖实际版本/native hash；只评估val选定第18轮，不按test换epoch/调阈值。

完整2000图test沿用整图800/max1333、阈值.23/text0、无crop/SAM/计数校正、相同organ caption及3exemplar。完成后核对官方测试路径唯一且完整、GT原annotation点数、非负整数预测，独立重算MAE/RMSE/R²，核对best-val推理/training_protocol以及checkpoint前后SHA。结果写入本run/test_final；当前实测test、PID、最佳c与完成状态待运行后记录。相对R06同20轮同时改变contrast开关和曲率学习，不能单独归因；R08-LC同20轮可作为主caption参照，R05前20轮选择best作为无辅助参照。数据/标注、模型/loss/config与已有实验均不改，两份docs同步更新。

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_r06_entailment_learnable_test.sh > runs/tpc268_v3_exclude3/launch_organ_entailment_learnable_seed42_e20_test.log 2>&1 < /dev/null &
```

### 2026-10-23 R06-ELC测试启动核实（10:53:06）

10:52:28进入RUNNING；后台PID3351310/推理PID3351689，宿主机核实PPID1、SID3351310、无TTY，GPU3推理约3004MiB，当前110/2000图。严格加载最终best epoch17=第18轮，无missing/unexpected；best c=0.6272836327552795，SHA256=6be3e8a78cd2df96046055767c3678e5b1e7ea50f392dc5c6c1f6b9f01bbfb47。89份源/资产hash与本run训练manifest一致，63项原依赖实际版本/native hash通过。训练HEAD6341592d13575f3626bc70f08604b96ab231f4ef，评估HEAD92edcb72b986181bdd7c68ca7d74689d77b45466，不能仅凭HEAD差异推断运行代码变化；实际被核验的模型/数据/配置/native源hash均相同。已有shell提示名称countgd改动只影响激活显示，不影响解释器/依赖或运行进程。完整test指标仍待结束核验；两份docs同步补记。


## 2026-10-23 R06-ELC第18轮最终best完整test完成（10:58:57）

run `organ_entailment_learnable_seed42_e20`，训练20轮seed42及独立best-val于10月22日16:46:26 DONE/退出0；20轮最低val MAE选最终第18轮（epoch17），取代先前第5轮best。新test在GPU3于10月23日10:52:28开始，10:58:57 DONE/退出0，实际推理约6分07秒。后台PID3351310、推理PID3351689（PPID1/SID3351310/无TTY）；10:59:39实查GPU3释放至used1MiB/free24124MiB，四卡均无计算进程。

| 数据 | best轮次 | 图像数 | MAE | RMSE | R² |
|---|---:|---:|---:|---:|---:|
| val（独立best重评） | 18 | 999 | 10.186186186186186 | 32.983570393696255 | 0.9050013136725523 |
| test（本次实测） | 18 | 2000 | 11.2675 | 31.181188239064912 | 0.851329780365249 |

最佳权重c=0.6272836327552795，初始1，TT/TV共享可学习Lorentz曲率。设置为FSC147 CountGD fresh初始化、organ文本`{organ} .`（如`fruit .`）+3视觉exemplar，CountGD主计数损失+TT/TV .05/.05、无contrast；原TT负父/bridge与主模型/增强/冻结/优化/数据/修复mask协议均保持。本次测试只读第18轮best，不按test选择其他epoch。旧第5轮RMSE较低不改变预先固定的最低val MAE选权重规则。

独立核验全部通过：2000路径唯一且等于官方test split、GT=原annotation点数、非负整数预测，逐图重算MAE/RMSE/R²一致（R²末位浮点差异在容差内），推理和training_protocol与best-val一致；曲率/初始c/learn_curvature由checkpoint_metadata额外保存，补足旧协议摘要未列这些字段的边界。checkpoint SHA256=`6be3e8a78cd2df96046055767c3678e5b1e7ea50f392dc5c6c1f6b9f01bbfb47`，前后相同。89份源/资产hash和63项原依赖实际版本/native hash与本run训练清单匹配。训练HEAD6341592d13575f3626bc70f08604b96ab231f4ef、评估HEAD92edcb72b986181bdd7c68ca7d74689d77b45466；HEAD不同不等于训练/评估核心源不同，实际检查以hash为准，不声称所有旧基线整个环境逐字节相同。

比较结果（MAE/RMSE/R²）：

| 参照 | test ΔMAE | test ΔRMSE | test ΔR² | 可支持的解释 |
|---|---:|---:|---:|---|
| R05 organ无辅助 | +0.7205（+6.8313%） | +1.3106174（+4.3877%） | −0.01223525 | 三项测试指标较差；val MAE降低2.7709%未转化为测试收益 |
| R06 organ完整辅助，20轮 | +0.5335（+4.9702%） | +0.4568494（+1.4869%） | −0.00432455 | 关闭contrast且学习曲率的组合未改善测试表现，不能分离两个开关贡献 |
| R08-LC full-taxonomy、TT/TV/可学习c，20轮 | +0.1275（+1.1445%） | −1.6836106（−5.1228%） | +0.01648816 | 本次有效配置仅主caption不同，organ下MAE稍差、RMSE/R²较好，是指标取舍 |

R05原30轮的前20轮日志最优仍第12轮，与正式best一致，StepLR10不依赖总epochs，可作20轮选择范围参照；不冒称R05只训练了20轮，保留旧run dirty源码归档不足及监控元数据差异的可重建性边界。R06-ELC相对R06的val MAE降低4.2709%，但val RMSE增加26.6405%，test三指标也较差；最低val MAE的改善不能代替测试整体收益。所有结论限当前seed/协议，不据此次test继续调阈值、换epoch或修改在训实验，不据此宣称双曲几何普遍无效。

证据`test_final/test_metrics.json`、`test_counts.json`、`checkpoint_metadata.json`、`verified.json`、`checkpoint.sha256`、`launch_verified.json`、`gpu_at_eval_start.csv`、`status`/`exitcode`及完整console/脚本快照；汇总`planning/r06_elc_test_results_20261023.json`。两份docs同步更新主表与分析；本次仅新增本地评估脚本和记录，模型/loss/config、数据/标注及训练协议保持不变。


## 2026-10-23 R04-ELC：R06-ELC的器官+物种主文本配对实验（准备）

用户授权保持R06-ELC其余设置，只把主文本改为物种名+器官，在空闲GPU后台训练。新ID=R04-ELC，run=`species_entailment_learnable_seed42_e20`，新配置`config/cfg_tpc268_species_entailment_learnable.py`继承R06-ELC的organ_entailment_learnable，只设prompt_mode='species'。这里species模式实际模板是`{organ} of {species} .`，例`fruit of Malus domestica .`，不含界门纲目科属等祖先文本；不把模式名误解为只有物种名。仅复用已有caption模式，main/Dataset/model/loss均不修改。

主配对R06-ELC同seed42/20轮，唯一有效配置变化为prompt_mode organ→species；初始化仍为原FSC147 CountGD checkpoint（model-only fresh），不使用R06-ELC的TPC best/latest权重、optimizer、scheduler或RNG。CountGD主计数损失保留，辅助仅原Lorentz TT/TV .05/.05，contrast关闭，原TT负父项和species-organ bridge不变；TT/TV共享可学习c，初始1、范围[.1,10]，原可学习alpha尺度保持。辅助文本/分类监督、缺链策略和既有aliases/registry均不变，仅更改主计数caption。

train6998/val999/test2000、三图代码排除/原始标注不动，3个原始exemplar（训练经原增强）、修复padding mask、冻结backbone.0/bert、900queries、中心监督、FP32/train batch4/eval实际batch1、workers4、AdamW lr/wd1e-4/clip.1/StepLR10、原resize/crop/flip及整图推理阈值.23/0均保持。另有同20轮R08-LC可作full_taxonomy→species的主文本对照；不能把R04原30轮完整辅助方案当本次仅改文本的配对基线。

11:27:55宿主机核实GPU2无计算进程、used4MiB/free24121MiB；GPU3出现短时新进程，因此固定选GPU2。新本地脚本`run_r04_entailment_learnable_e20.sh`带nohup+setsid/flock、防已有产物覆盖/隐式resume、uv离线显式原解释器；CPU检查结束后每15秒查询GPU2，须used≤64MiB且free≥20000MiB才进入正式训练，不终止或调整其他任务。

启动预检将核对相对R06-ELC仅prompt配置差异，训练源/资产清单89份逐hash相同、63项原依赖实际版本/native hash及初始化SHA；相对旧R08-LC仅保留已审计监控依赖两个精确元数据差异，不安装/sync环境。额外检查全部split路径/GT计数和registry相同、所有新caption格式与BERT长度/单目标标点，覆盖已解析和未解析物种的9个代表样本在同RNG下图像和全部非文本target/RNG状态相同。实际CPU构造/严格FSC147加载与原曲率参数/梯度检查；该检查模型丢弃，正式新进程重设seed42 fresh训练。以上为待执行检查，未提前写通过或填写指标。

正式预算20轮，每轮完整999图val，按最低val MAE选best，训练后独立重评best-val；与R06-ELC原训练脚本相同，不自动test、不按已有test调参数或epoch。run另存源码/资产hash、配置/脚本快照、HEAD/dirty diff、数据配对和曲率检查证据及status/stage/exitcode；新配置尚未提交，不仅用HEAD标识源码。验证/测试结果未知。本次是在已看既有test后提出的探索性单seed输入对照；两份docs同步更新协议/状态。

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_r04_entailment_learnable_e20.sh > runs/tpc268_v3_exclude3/launch_species_entailment_learnable_seed42_e20.log 2>&1 < /dev/null &
tail -f runs/tpc268_v3_exclude3/launch_species_entailment_learnable_seed42_e20.log
```

### 2026-10-23 R04-ELC正式启动核验（11:36:43 Asia/Shanghai）

预检全部通过，11:35:38进入TRAINING；GPU2启动前实际used4MiB/free24121MiB，通过空闲门槛。后台PID3410506，PPID1/SID3410506/无TTY，训练PID3411377已在宿主机GPU2核实，瞬时显存11796MiB；nohup+setsid独立于SSH。当前第1/20轮（epoch0）、batch20/1749，完整train+val轮次0，best轮次/val/test均未知，不重复启动。

配置与R06-ELC逐项比较，唯一差异prompt_mode organ→species；与R08-LC仅full_taxonomy→species。原R06-ELC训练清单89份源/资产hash均逐项一致，63项原已安装依赖实际版本/native hash通过；R08-LC旧清单77项相同，另有已审计nvitop监控依赖元数据两个精确hash差异，完整环境身份边界保留，未安装或同步依赖。

实际数据配对检查：train6998/val999/test2000路径及原GT计数完全相同、registry fingerprint相同，三张图仍只在代码层排除；全部新caption均为organ of species单目标，无祖先后缀，BERT含3exemplar最大token分别17/16/17、无截断。9个含完整/缺失分类链的代表样本，同seed下增强后图像、全部非caption/cap_list target及Python/NumPy/Torch RNG状态相同。这不冒称逐张重跑了全部图像增强，完整坐标协议沿用已核验源/原数据。

CPU真实模型严格加载FSC147共享1146项，仅12项新taxonomy状态保留构造初始化，unexpected为空，不加载TPC权重或optimizer/scheduler/RNG；log_c为可学习Parameter且唯一进入原lr1e-4优化器组，合成几何梯度0.2475481778383255、c由1→0.9998999834060669，非法锥0。CPU检查模型丢弃，正式GPU进程从原FSC147/seed42 fresh启动。实际前20批loss有限，最新loss26.4017，含TT/TV且无contrast，曲率已由1→日志0.9996，非法锥率0。

启动HEAD=92edcb72b986181bdd7c68ca7d74689d77b45466，新配置和文档未提交，原用户已有文件删除保留；launch_sources保存新配置/启动脚本及pyproject/uv.lock，完整身份以launch_manifest/hash/dirty diff与工作区记录为准。新run中的paired_data_check、cpu_initialization_report、launch_verified和gpu_at_training_start留存实际证据。后续继续20轮→最低val MAE选best→独立best-val，不自动test；模型/loss/Dataset及既有运行不改。两份docs同步更新矩阵/状态/本记录。


## 2026-10-23 按初始化来源分组汇总维护记录

依用户要求，新增§7.1 GroundingDINO/FSC147 CountGD两组完整实验结果与三组匹配初始化对照表；16个已完成实验的32份val/test结果均从逐图计数重算，核对999/2000官方路径、原始GT点数及整数预测，全部一致。第17个R04-ELC仍训练，无完整val/test，保持未知；R09未启动不纳入实测分组。补齐P04最终DONE/第5轮best与真实val/test，旧历史记录保留原日期。完整证据路径/状态/初始化/轮次/指标与可得run提交记在planning/results_by_initialization_20261023.json，缺失单独commit文件记null而不猜测。

两份docs同日更新；本次不新增或重跑实验，不变更模型、初始化、数据/标注、训练/推理协议、环境或GPU2在训R04-ELC。R/P协议仍分开解释，不从初始化分组中推出不同文本/环境/预算可直接比较，三组配对结论限现有seed42及可追溯性边界。


## 2026-10-23 初始化分组表的器官文本展示过滤

依用户要求，将“只有器官没有文本”按主caption仅有器官、不含物种名解释：§7.1移除R05/R06/R06-ELC/P04四行，保留13行（GD4、FSC147 9），含12个完成实验和R04-ELC在训。R04-ELC等species模式含organ+species，继续保留；辅助分支是否使用taxonomy不作为本次筛选条件。表中指标/状态沿用既有核验时间，不据本次排版声称新进度。

此为展示过滤，不删除实验结果、数据样本或标注，不修改训练/推理协议与在训任务；完整主表/原始JSON和所有run仍保留。另存派生结果results_by_initialization_species_text_20261023.json记录来源快照与排除的实验ID，保留完整快照可追溯性。两份docs同日同步补记。


## 2026-10-23 LC-T01：GPU0降低学习率对照（准备）

用户要求在GPU0执行上一条建议的第一项实验，因此固定LC-T01，run `entailment_learnable_lr3e5_seed42_e20`。新增`config/cfg_tpc268_entailment_learnable_lr3e5.py`继承R08-LC，只设置lr=3e-5；主要配对基线为FSC147 CountGD初始化的R08-LC，同seed42/20轮/全分类主文本/3exemplar/TTTV各.05/可学习c初始1/范围[.1,10]/warmup1/无contrast。fresh加载原FSC147模型，不续训R08-LC best/latest，不加载TPC optimizer/scheduler/RNG。

其余数据6998/999/2000、三图代码排除/registry/原始标注、修复mask、冻结backbone.0/bert、原增强/中心监督、FP32/train batch4/eval实际batch1、AdamW wd1e-4/clip.1/StepLR10及整图推理设置不变。这里lr改变原普通优化器组（包括log_c、alpha和原普通可训练参数），不新增独立曲率组；特殊linear-projection组仍1e-5，冻结backbone配置lr也仍1e-5。以实际参数分组比较，不能误称所有组统一乘0.3。

13:16:35实查GPU0空闲used4MiB/free24121MiB，GPU2 R04-ELC仍在运行。本地`run_lc_t01_lr3e5_e20.sh`固定GPU0、nohup+setsid/flock、防已有产物覆盖/隐式resume、uv离线原解释器；CPU配置/hash/严格初始化/曲率梯度检查后，正式训练前等待used≤64MiB/free≥20000MiB。新配置和内嵌脚本语法检查已过，真实CPU/GPU检查/PID/性能仍待运行核实。

预检要求有效配置相对R08-LC只有lr1e-4→3e-5；R06-ELC清单89项原源/资产hash一致，R08-LC旧77项相同及两个已审计监控元数据精确hash差异，63项原依赖版本/native与FSC147 SHA不变，不安装/sync依赖。CPU真实模型严格共享1146项，仅12项新增taxonomy状态；验证log_c唯一进入lr3e-5普通组、梯度有限且更新，检查模型丢弃，正式GPU独立新进程seed42 fresh训练20轮→val MAE选best→独立best-val，不自动test。

模型/loss/Dataset/旧配置/数据/标注及其他任务不改；两份docs同步准备/协议。新配置未提交，run另存HEAD/dirty diff、配置和脚本快照、源/资产hash与状态，未来指标未知，不将建议写成已测收益。其他调参候选未启动。

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_lc_t01_lr3e5_e20.sh > runs/tpc268_v3_exclude3/launch_entailment_learnable_lr3e5_seed42_e20.log 2>&1 < /dev/null &
```

### 2026-10-23 LC-T01正式训练启动核验（13:20）

13:19:25进入TRAINING，GPU0启动前used4MiB/free24121MiB，空闲门槛通过。后台PID3507464（宿主机核实PPID1/SID3507464/无TTY）、训练PID3507881已实查GPU0，13:20:05瞬时显存9296MiB；nohup+setsid独立于SSH。当前第1/20轮（epoch0），batch20/1749，完整train+val0，best/val/test未知。

实际配置相对R08-LC仅lr=.0001→.00003；原R06-ELC清单89项源/资产hash一致，R08-LC旧77项匹配及两个精确监控元数据差异已审计，63项原依赖版本/native hash和FSC147 SHA通过。CPU实际严格加载FSC147共享1146项，只允许新taxonomy12项，unexpected为空；c参数唯一进3e-5普通组，合成几何梯度.2475481778383255有限，一步c1→.999970018863678。特殊linear-projection组仍1e-5，原冻结设置不变，不把普通组lr变更描述为所有参数组同比下降。

CPU检查模型丢弃后，正式新进程fresh FSC147/seed42训练。实际batch0 loss1492.6223与R08-LC参考batch0完全一致，是相同起点数值的附加核对；不能仅凭单个loss证明所有随机过程逐字节相同。batch20 loss248.9449，所有loss有限、TT/TV存在、contrast关闭、日志lr=.00003、非法锥0。曲率日志四位小数仍1.0000，不虚构已测到非1的GPU曲率；CPU参数/梯度更新检查通过，后续以训练日志/checkpoint记录实际变化。

启动HEAD92edcb72b986181bdd7c68ca7d74689d77b45466，新配置及文档未提交；run另存launch_sources配置/脚本/pyproject/uv.lock、manifest源/资产hash/参数分组、CPU初始化、gpu_at_training_start与launch_verified实际进程证据。原用户工作区删除和R04-ELC文件保持。继续原20轮→最低val MAE选best→独立best-val，无自动test；LC-T02/03仍未启动。两份docs同步更新矩阵/状态/提案进展，既有模型/loss/Dataset、旧配置、数据/标注、环境与其他任务不改。


## 2026-10-25 R04-ELC与LC-T01训练完成及补测记录

用户要求汇报刚结束两组实验的val/test，缺少test则补测。实际核对两组log.txt均20条完整train+val记录、训练status/stage DONE、exitcode0及独立best-val：R04-ELC于10月24日10:07:25完成，第14轮最低val MAE，val999张=10.162162162162161/30.63426934755354/0.9180521955583507；LC-T01于10月24日13:13:15完成，第18轮最低val MAE，val999张=9.565565565565565/31.256662953344506/0.9146885175455899（顺序MAE/RMSE/R²）。原10月23日启动记录是历史快照。两组此前均没有test_metrics.json。

12:53:30在实查空闲的GPU2/0分别后台启动run_r04_entailment_learnable_test.sh与run_lc_t01_lr3e5_test.sh，PID380027/380028，宿主机核实PPID1、各自独立SID、无TTY。固定最终val选出的checkpoint_best_regular.pth，输出各自test_final；预检源码/配置/依赖/native/权重身份、完整20轮及best元数据，随后原推理协议测试2000张并独立重算。启动时完整test指标未知；现已全部完成并核验，最终指标见下文，未更换epoch或调阈值。HEAD实查92edcb72b986181bdd7c68ca7d74689d77b45466，配置/文档尚未提交，源码身份以训练manifest和评估快照/hash为准。

两组都从FSC147 CountGD fresh初始化、seed42、TT/TV各.05/可学习c初始1/无contrast；R04-ELC主文本organ+species，普通lr1e-4，仅主caption区别于R06-ELC/R08-LC；LC-T01为R full_taxonomy，普通lr3e-5，相对R08-LC仅普通组学习率改变。模型、loss、数据/标注、环境与训练设置不变，两份docs同步更新；LC-T02/03仍未启动。最终结果与配对比较已同步本节及§5–8主表。


### 2026-10-25 两组最终best测试完成与独立核验

R04-ELC：DONE 2026-10-25T13:00:21+08:00、exitcode0；best第14轮，c=0.6370097994804382；val999=10.162162162162161/30.63426934755354/0.9180521955583507，test2000=12.3855/35.432873154741486/0.8080220278659153。权重SHA256=7ef4b6c01d7d8b3f8259b4b47d6fef017f42ba261b7d7ae8fbd804c70591548c，评估前后未变；90份源/资产hash与本run训练manifest一致，63项原依赖实际版本/native SHA匹配。训练HEAD=92edcb72b986181bdd7c68ca7d74689d77b45466，评估HEAD=92edcb72b986181bdd7c68ca7d74689d77b45466，未提交配置仍由manifest/launch_sources/hash定位。

独立核验时间2026-10-25T13:00:20.977420+08:00；2000官方路径唯一且集合一致，每图GT与原annotation点数一致，整数非负预测，三指标独立重算一致；原推理training_protocol、prompt/registry/3exemplars/整图800-max1333/阈值.23-0不变，无crop/SAM/校正。验证集999条计数也在本次重算，与20轮日志最佳及checkpoint一致。

LC-T01：DONE 2026-10-25T13:01:00+08:00、exitcode0；best第18轮，c=0.7562490701675415；val999=9.565565565565565/31.256662953344506/0.9146885175455899，test2000=9.636/28.857338754639173/0.8726639962191843。权重SHA256=5acbecab9f684aae3047c879761658b9ae9a9c3587efd3655cbcd2430f55361f，评估前后未变；91份源/资产hash与本run训练manifest一致，63项原依赖实际版本/native SHA匹配。训练HEAD=92edcb72b986181bdd7c68ca7d74689d77b45466，评估HEAD=92edcb72b986181bdd7c68ca7d74689d77b45466，未提交配置仍由manifest/launch_sources/hash定位。

独立核验时间2026-10-25T13:01:00.510218+08:00；2000官方路径唯一且集合一致，每图GT与原annotation点数一致，整数非负预测，三指标独立重算一致；原推理training_protocol、prompt/registry/3exemplars/整图800-max1333/阈值.23-0不变，无crop/SAM/校正。验证集999条计数也在本次重算，与20轮日志最佳及checkpoint一致。

主表§5–7、初始化筛选表§7.1、配对分析§8.7及调参计划同步更新；核验汇总planning/r04elc_lct01_results_20261025.json。两份docs同日更新；模型/loss/config、数据/标注、初始化、依赖环境及训练/推理协议均未改，无新增训练；LC-T02/03仍PROPOSED_NOT_LAUNCHED。

13:02:10宿主机复查四张GPU均used1MiB/free24124MiB，无计算进程；两组测试已释放GPU0/2，未启动其他训练。


## 2026-10-25 LC-T04/05/06：GPU0/1/2后台训练准备

用户明确授权启动上节三个单因素实验，映射为LC-T04→GPU0、LC-T05→GPU1、LC-T06→GPU2；实际查询四卡均used1MiB/free24124MiB、无计算进程。三份新配置都继承LC-T01 cfg_tpc268_entailment_learnable_lr3e5.py；离线解析实际有效配置与LC-T01训练manifest逐键比较，分别仅lambda_tv .05→.01、普通lr3e-5→1e-5、aux_loss_warmup_epochs1→3，其他差异为空。

- LC-T04：`entailment_learnable_lr3e5_tv001_seed42_e20`，配置`cfg_tpc268_entailment_learnable_lr3e5_tv001.py`，GPU0，仅lambda_tv=.01；lr3e-5/TT.05/warmup1。
- LC-T05：`entailment_learnable_lr1e5_seed42_e20`，配置`cfg_tpc268_entailment_learnable_lr1e5.py`，GPU1，仅普通lr=1e-5；TT/TV .05/.05/warmup1。
- LC-T06：`entailment_learnable_lr3e5_warmup3_seed42_e20`，配置`cfg_tpc268_entailment_learnable_lr3e5_warmup3.py`，GPU2，仅aux warmup=3；lr3e-5/TT/TV .05/.05。

共用本地入口`run_lc_followup_e20.sh LC-T04|LC-T05|LC-T06`与CPU核验`lc_followup_precheck.py`。各自flock、防已有log/checkpoint/manifest覆盖、nohup+setsid独立session，原uv离线no-project显式.venv，不安装或sync；原6998/999/2000划分及三图代码排除/registry/full_taxonomy/3exemplars/FP32/冻结/AdamW/StepLR10/阈值.23-0均保持。每组独立fresh原FSC147 model-only、seed42/20轮，不续训TPC模型/optimizer/scheduler/RNG；按val MAE选best后独立999图best-val，无自动test。

入口语法/内嵌Python及可用输出目录/主机RAM已检查。后台正式训练前还须实际核对LC-T01清单91份原源码/资产、63项原依赖/native/初始化SHA、CPU严格加载1146共享张量+12新taxonomy项、curvature/alpha参数组归属及有限非零梯度/更新，再次要求目标GPU used≤64MiB/free≥20000MiB。准备时尚无真实CPU/GPU结果和PID；现已实际启动并核验，见下节，完整轮次/best/val/test仍未知；不将合成几何检查称正式性能。

两份docs同步记录新增配置/入口和协议；模型/loss/Dataset/引擎代码、旧配置、数据/标注与依赖环境不改。原用户删除文件与既有未提交配置/文档保持，HEAD及dirty身份由实际launch记录/源hash定位。原LC-T02/03仍未启动，三项按各自val比较，不累计参数变更或按test挑选。


### 2026-10-25 三项正式启动核验

LC-T04：TRAINING 2026-10-25T16:47:05+08:00，status RUNNING；GPU0，后台PID441440，实际训练PID441913；宿主机核实PPID1/SID441440/无TTY、CUDA_VISIBLE_DEVICES=0与对应UUID一致。核验时第1/20轮、batch50/1749、完整轮次0；首批loss=1492.6222、最近日志loss=89.9213，所有已输出batch的loss meter有限。best轮次/正式val/test仍未知。启动前GPU used=1MiB/free=24124MiB，核验瞬时进程占用13778MiB。

LC-T05：TRAINING 2026-10-25T16:47:05+08:00，status RUNNING；GPU1，后台PID441441，实际训练PID441890；宿主机核实PPID1/SID441441/无TTY、CUDA_VISIBLE_DEVICES=1与对应UUID一致。核验时第1/20轮、batch50/1749、完整轮次0；首批loss=1492.6223、最近日志loss=162.7807，所有已输出batch的loss meter有限。best轮次/正式val/test仍未知。启动前GPU used=1MiB/free=24124MiB，核验瞬时进程占用13778MiB。

LC-T06：TRAINING 2026-10-25T16:47:04+08:00，status RUNNING；GPU2，后台PID441442，实际训练PID441823；宿主机核实PPID1/SID441442/无TTY、CUDA_VISIBLE_DEVICES=2与对应UUID一致。核验时第1/20轮、batch50/1749、完整轮次0；首批loss=1492.6222、最近日志loss=83.0297，所有已输出batch的loss meter有限。best轮次/正式val/test仍未知。启动前GPU used=1MiB/free=24124MiB，核验瞬时进程占用13778MiB。

三组实际config_args_all逐项匹配各自manifest，并确认seed42/epochs20/batch4/FP32、pretrain原FSC147且resume为空。有效配置对LC-T01各只有一个指定字段差异，91份原源/资产hash全部相同；每run新清单96项，63项原依赖实际版本、native SHA和FSC147 SHA通过。CPU真实严格加载共享1146项，仅12新taxonomy项、unexpected空；curve/alpha各唯一进入普通组，合成有限log_c梯度均.2475481778383255，c1→.999970018863678（LC-T04/06）/.9999899864196777（LC-T05）。CPU模型丢弃，正式GPU独立重置seed42/fresh原FSC147；首批主CE/box/xy损失与LC-T01在打印精度内一致，TT/TV的首批权重按各自lambda及warmup因子核对通过。曲率GPU四位日志仍1.0000，不虚构已测曲率变化或性能改善。

LC-T06 warmup是两项辅助loss权重在前三轮线性升至目标：第1/2/3轮末因子1/3、2/3、1；不是学习率warmup，也没有改变普通lr3e-5。LC-T05普通lr降低会同时影响log_c/alpha，特殊projection组初始仍1e-5；三项均保持StepLR10，未启用注释中的MultiStepLR。

实际启动命令（已在运行，勿重复执行）：

```bash
nohup setsid bash runs/tpc268_v3_exclude3/run_lc_followup_e20.sh LC-T04 > runs/tpc268_v3_exclude3/launch_entailment_learnable_lr3e5_tv001_seed42_e20.log 2>&1 < /dev/null &
nohup setsid bash runs/tpc268_v3_exclude3/run_lc_followup_e20.sh LC-T05 > runs/tpc268_v3_exclude3/launch_entailment_learnable_lr1e5_seed42_e20.log 2>&1 < /dev/null &
nohup setsid bash runs/tpc268_v3_exclude3/run_lc_followup_e20.sh LC-T06 > runs/tpc268_v3_exclude3/launch_entailment_learnable_lr3e5_warmup3_seed42_e20.log 2>&1 < /dev/null &
```

查看三组日志：

```bash
tail -f runs/tpc268_v3_exclude3/launch_entailment_learnable_lr{3e5_tv001,1e5,3e5_warmup3}_seed42_e20.log
```

实际HEAD三组均92edcb72b986181bdd7c68ca7d74689d77b45466，工作区有未提交配置/文档；源身份以各run保存的hash/配置与launcher快照定位，不称HEAD已包含新配置。各run/launch_verified.json及planning/lc_t01_followup_20261025/launch_verified_20261025.json保存实际GPU/进程/初始化/首批证据，proposed_followup.json改RUNNING，旧LC-T02/03继续未启动。三组独立20轮→val MAE选best→独立best-val，无自动test；SSH断开后由独立session继续运行。

两份docs同步更新矩阵/状态/分组/未知指标和代码边界。没有更改模型/loss/engine/Dataset源码、原配置、数据/标注、初始化或依赖环境；仅新增上述三项配置和本地启动/核验入口。


## 2026-10-25 BunchCount 标注核查与计划约束（未训练）

本次仅审计 BunchCount、生成可视化并按用户要求修正一处 exemplar；TPC-268 模型、配置、训练/推理协议和已有运行未改。`data/bunchcount-dataset-0928/annotations.json` 中 `690-pencils.individual_exemplars` 原有4个，仅删除最后一个，现为3个；逐记录深比较确认只有该字段变化，其余全部一致。删除框为 `[28.643259048461914,62.03076934814453,390.4894104003906,628.0615234375]`。原标注备份、前后SHA256及机器可读审计保存在 `runs/bunchcount_audit_20261025/annotations.before.json` 与 `audit.json`。

按显式 `bbox_to_points` 检出185个单成员群体，涉及52张图；群体数按train/val/test为32/3/150。这些为用户指出的错误标注，暂仅列清单和可视化，未删除框、关系、个体点或修改群体exemplar，等待用户决定修正方式。逐群体0-based框/点索引、坐标和split见 `singleton_groups.csv/json`；`index.html` 汇总逐图标注及185个局部放大图，另有4张contact sheet。灰框为其他群体、青点为所有个体、红框和黄圈为单成员群体与其唯一成员。

缺失group_description的3张图全部属于train：`coco-trains-000000115118.jpg`、`coco-trains-000000419882.jpg`、`openimages-trains-0001.jpg`；清单见 `missing_group_description.json`，可视化亦已纳入index，字段保持原样，由用户决定处理方法。

用户明确收紧后续BunchCount计划：保留共享900 queries，使用FSC147 CountGD预训练权重；训练GT>900不排除、不截断、不调整query容量或引入特殊采样/分块，保持全部GT及原始计数。联合目标可能超过900，标准一对一匹配只能匹配至多900个query，未匹配GT不能冒称全部接受了匹配监督；评估仍使用完整GT。群体和个体分别报告MAE/RMSE，禁止合并成一个计数指标。此前1024-query建议撤回。未来数据协议对照需使用相同修正版标注、prompt/exemplar/初始化/增强和推理策略；旧标注实验不可直接混为相同协议。

后续权重选择建议（仅提案，未实施）：保留群体最佳、个体最佳和一个预先约定规则的联合选择checkpoint；联合规则使用两个val MAE各除以固定、相同数据协议的预先指定共享检测baseline的val MAE后等权平均，分母在候选方法比较前固定，并设正epsilon处理零值。此分数仅用于选择同一个模型权重，不作为合并计数性能汇报；不接受加权规则时保留Pareto候选，由用户确定取舍，不能声称存在唯一双任务最优。两个RMSE单独报告，可作预定平局规则，不把四项随意加权。不使用test选择规则或权重。

关系评估建议（仅提案）：先按类型分别一对一匹配群体框和个体点，不使用预测关系参与节点匹配；框采用预先约定IoU阈值，点采用原图坐标下固定容差及敏感性报告。端到端边precision/recall/F1需计入节点漏检/误检导致的FN/FP；另报两端均匹配子集的关系指标和覆盖率、父群体含null准确率及独立个体precision/recall/F1。关系阈值/点容差仅按训练定义或val确定，固定后test；null不计为群体实体。完整成员集合准确率和成员数误差作为补充，不能由计数一致推断关系正确。

本次没有新增训练或评估模型；BunchCount run ID、训练commit、服务器状态和性能均未知，以上清单数目来自本地实际标注审计，非模型实测性能。
