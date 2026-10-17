# CountGD / TPC-268 阶段实验报告与后续计划

**报告更新：2026-10-17，Asia/Shanghai。** 本次状态采集约11:26–11:28，R04/R05完成并核验best-val，R07仍在训练；10月16日test快照保留各自权重身份。新增论文复现协议审计与优先级修订，见附录A的2026-10-17说明。本报告是实验记录的固定入口，后续按第10节规则持续更新。实现细节见 [implement.md](implement.md)。

实验根目录：`runs/tpc268_v3_exclude3/`。当前代码HEAD=`8a26e86cffc8f5209c7924cf0d425044eaa0bdd4`，存在已记录的工作区修改；**当前HEAD不等于每个实验启动时的代码版本**，详见第9节。所有指标来自实际日志、最佳checkpoint元数据或计数JSON；没有结果的单元格用“—”，不填推测值。

## 1. 当前结论摘要

- R01/R02/R03均已完成30轮训练、best-val独立重评及用户指定的2000张test评估；退出码均为0。
- R04/R05均已完成30轮训练及best-val重评，退出码0；分别于10月17日07:13:21/01:50:16结束。best仍为第11/12轮，无更新。最终best文件SHA256与10月16日已评估快照一致，已有test可用于相同最终选定权重，无需重复推理。
- R07完成21轮，正在第22轮；best已从第1轮更新为第16轮，val MAE=11.0701、RMSE=36.0906、R²=0.8863。10月16日test=13.3415对应旧第1轮，不能作为当前best的test。该训练继续按原预算进行。
- 完整辅助方案R02相对同文本基线R01：val MAE恶化，但test MAE小幅降低、RMSE升高。证据是**单seed、数据划分和指标相关的取舍**，不支持“全面提升”，也不足以证明contrast或双曲建模分别无效。
- 10月17日用户先提出论文Table 4全分类文本基线复现，随后明确要求先提供原计划R08层级蕴涵实验的启动命令。R08现为READY，GPU0脚本已准备但尚未执行；R07不修改。论文初始化与训练配方仍待核实，P01继续记录缺项，不能把R08或猜测配置称作论文完全复现。

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
| `full_taxonomy` | `{organ} of {species}; taxonomy: {Kingdom}, {Phylum}, {Class}, {Order}, {Family}, {Genus}, {Species} .` | R01/R02/R07，计划R08/R09 |
| `species` | `{organ} of {species} .` | R03/R04 |
| `organ` | `{organ} .` | R05，条件式R06 |

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
| R05 | organ | 无 | `cfg_tpc268_organ_baseline.py` | 自身 |
| R06 | organ | contrast + Lorentz TT/TV | `cfg_tpc268_organ_full.py` | R05 |
| R07 | full_taxonomy | contrast-only，权重0.1 | `cfg_tpc268_contrast.py` | R01 |
| R08 | full_taxonomy | Lorentz TT/TV-only，权重0.05/0.05 | `cfg_tpc268_entailment.py` | R01 |
| R09 | full_taxonomy | contrast + Euclidean TT/TV | `cfg_tpc268_euclidean.py` | R01；几何配对R02 |

| 公共项目 | 实际设置 |
|---|---|
| 初始化 | 每组独立从`checkpoints/checkpoint_fsc147_best.pth`开始；不从其他TPC微调权重初始化 |
| 语言权重 | `checkpoints/bert-base-uncased` |
| 随机种子 / 预算 | seed42，单GPU，30epochs，FP32，不启用AMP |
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

## 5. 实验状态与最佳权重轮次

所有轮次均为**1-based**；日志`epoch=0`是第1轮。RUNNING取本次采集时刻，正式`log.txt`一行代表完成一轮训练与验证。R07的外层console包含短程输出，正式进度/结果只读取正式目录`log.log`/`log.txt`及checkpoint。

| ID | 训练GPU | 状态 | 完整轮数与最新训练位置 | 最佳权重轮次 |
|---|---:|---|---|---|
| R01 | 0 | DONE | 30/30，训练及best-val重评结束 | 第2轮（checkpoint元数据已核对） |
| R02 | 2 | DONE | 30/30，训练及best-val重评结束 | 第3轮（checkpoint元数据已核对） |
| R03 | 3 | DONE | 30/30，训练及best-val重评结束 | 第12轮（checkpoint元数据已核对） |
| R04 | 3 | DONE | 30/30，10月17日07:13:21结束，best-val重评完成，退出码0 | 第11轮，未刷新（checkpoint已核对） |
| R05 | 0 | DONE | 30/30，10月17日01:50:16结束，best-val重评完成，退出码0 | 第12轮，未刷新（checkpoint已核对） |
| R07 | 2 | RUNNING | 完成21/30；第22轮，batch 1480/1749（10月17日约11:26） | 第16轮，已刷新（checkpoint已核对） |
| R06 | — | BLOCKED | 未启动，等待计划门槛 | — |
| R08 | 0（准备分配） | READY | 用户明确要求先启动，run_r08.sh已准备；本次未执行 | — |
| R09 | — | BLOCKED | 未启动，等待计划门槛 | — |

DONE表示训练与best-val重评结束；test是否完成见第7节，二者不混用。R01–R05退出码均为0。R07只完成部分预算，当前不能作最终结论。宿主机只显示GPU0/1/2/3，10月17日11:26空闲为0和3；不存在index4，避免混淆物理编号与第几张卡。

## 6. 验证集性能

**指标全部对应各自val MAE最低的同一个权重；RMSE不是另挑最低轮次。** MAE越低越好；RMSE更重罚大错误；R²相对该集合均值预测基线计算，不是准确率。999张val与2000张test数量分布不同，R²不作跨split直接比较。

| ID | 最佳轮次 | 图像数 | MAE ↓ | RMSE ↓ | R² ↑ | 证据状态 |
|---|---:|---:|---:|---:|---:|---|
| R01 | 2 | 999 | 10.0030 | 26.4758 | 0.9388 | best权重独立重评完成 |
| R02 | 3 | 999 | 10.6867 | 29.0248 | 0.9264 | best权重独立重评完成 |
| R03 | 12 | 999 | 9.6707 | 28.6010 | 0.9286 | best权重独立重评完成 |
| R04 | 11 | 999 | 10.7818 | 32.4995 | 0.9078 | 最终best权重独立重评完成 |
| R05 | 12 | 999 | 10.4765 | 30.3528 | 0.9196 | 最终best权重独立重评完成 |
| R07 | 16 | 999 | 11.0701 | 36.0906 | 0.8863 | 阶段性正式训练日志；best checkpoint已核对 |
| R06/R08/R09 | — | — | — | — | — | 尚未启动 |

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
| R07旧快照 | 1 | 2000 | 13.3415 | 36.7346 | 0.7937 | DONE；仅对应第1轮，当前第16轮best未测test |
| R06/R08/R09 | — | — | — | — | — | 尚未启动，未评估 |

R01/R02/R03共六份val/test结果已从逐图计数JSON独立重算MAE、RMSE、R²，与metrics文件一致，无重复图片；此前test核验图片集合与官方test一致、GT等于原annotation点数。

| ID | test GPU | 时间（Asia/Shanghai） | 退出码 | 说明 |
|---|---:|---|---:|---|
| R01 | 0 | 2026-10-15 18:59:54–19:07:20 | 0 | 完整2000图 |
| R02 | 1 | 2026-10-16 10:29:53–10:40:55 | 0 | 与其他任务共享GPU，峰值显存1584MiB |
| R03 | 3 | 2026-10-15 17:26:54–17:33:34 | 0 | 完整2000图 |
| R04 | 3 | 2026-10-16 15:40:32–15:50:52 | 0 | 部分训练预算best快照，完整2000图 |
| R05 | 0 | 2026-10-16 15:40:32–15:51:14 | 0 | 部分训练预算best快照，完整2000图 |
| R07 | 2 | 2026-10-16 15:40:32–15:52:43 | 0 | 部分训练预算best快照，完整2000图 |

2026-10-16阶段性test：按用户明确要求，15:40:32在GPU3/0/2并行评估R04/R05/R07当时val选出的best（第11/12/1轮），训练继续运行。启动前GPU剩余显存约12.7/6.9/7.2GiB（GPU0/2/3），此前同协议eval峰值约1.6GiB。每项输出单独保存为`<run>/test_snapshot_20261016_153930/`；使用复制并读取验证过的`checkpoint_best_snapshot.pth`，保存SHA256、快照时间/epoch/val指标、config及工作区代码diff，避免训练刷新best改变评估对象。后台进程使用独立session，日志/status/exitcode留在输出目录，不依赖SSH。清单见[parallel_test_snapshot_20261016_153930.json](../runs/tpc268_v3_exclude3/planning/parallel_test_snapshot_20261016_153930.json)。这些结果属于当前部分训练预算的快照，不替代最终30轮模型；不使用test挑epoch、阈值或后续参数。推理沿用原caption、3exemplars、整图、阈值0.23/0及2000张test；仅设置CPU线程数为2以控制并行资源占用。

15:53核验通过：三个快照的SHA256未改变；逐图路径各有2000张且唯一，与官方test清单一致；每张GT与原annotation点数一致；MAE/RMSE/R²均独立重算吻合。核验及配对结果见[verified_test_snapshot_20261016_153930.json](../runs/tpc268_v3_exclude3/planning/verified_test_snapshot_20261016_153930.json)。PyTorch峰值allocated为R04/R05/R07=1584/1583/1584MiB，nvidia-smi进程占用约3004MiB，各卡仍有余量；完成后测试进程释放显存，原GPU0/2/3训练进程仍在。没有修改正在运行的训练配置或数据。

## 8. 实验结果分析

### 8.1 同文本的辅助训练配对

`Δ=method−同caption baseline`，负的MAE/RMSE差值为改善。

| 配对 | split | ΔMAE | ΔRMSE | ΔR² | 当前解释 |
| R02−R01 | val | +0.6837 | +2.5490 | -0.0124 | 验证三指标均退化，当前组合未获收益 |
| R02−R01 | test | -0.2735 | +1.2994 | -0.0148 | MAE改善、RMSE/R²退化，存在取舍 |
| R04−R03 | val | +1.1111 | +3.8985 | -0.0208 | 完成同30轮预算；单seed验证三指标均退化 |
| R04−R03 | test | +1.1050 | -1.6218 | +0.0183 | 最终同权重：MAE退化、RMSE/R²改善 |
| R07−R01 | val | +1.0671 | +9.6148 | -0.0525 | 第16轮best，R07训练未完成 |
| R07快照−R01 | test | +0.6925 | +0.0914 | -0.0010 | 阶段性快照：三指标均未优于R01；训练未完成 |

- **R02：结论需同时保留正负证据。** val MAE升高约6.8%，test MAE降低约2.16%，但test RMSE升高约3.55%、R²降低。不能将它概括为全面有效或全面无效；更不能把组合结果分别归因为contrast和Lorentz。test差异仅用于报告，不反向驱动后续方案选择。
- **R04：同预算单seed未获得MAE收益。** 完成30轮后best-val MAE=10.7818，对应R03=9.6707；test MAE变差但RMSE/R²改善，需保留指标取舍，不能将组合结果分别归因于contrast或Lorentz。
- **R05：缺少配对辅助方案。** 最终organ-only best-val MAE=10.4765，test MAE=10.5470；R06尚未启动，不能判断organ条件下辅助训练是否有效。
- **R07：当前阶段尚未优于R01。** 完成21/30轮，第16轮best-val MAE=11.0701，对应R01=10.0030；需按原预算继续并重评，旧第1轮test不能替代当前best。

10月16日test快照的解释：R04相对同species文本R03的test MAE升高1.1050，但RMSE降低1.6218，反映指标取舍（逐图绝对误差697张改善、756张变差、547张相同）。R07旧第1轮相对同full-taxonomy文本R01的MAE升高0.6925、RMSE升高0.0914（531张改善、1064张变差、405张相同）。比较工具已核对相同数据/初始化/配置训练预算和推理协议；在10月16日测试时方法尚未完成30轮，原报告将其标为阶段性。10月17日R04完成30轮且最终best SHA与该快照相同，R04比较现已对应最终同预算选定权重；R07仍在训练且best已改变，其旧test保持历史阶段性身份。R05在这三组已测权重中MAE/RMSE最低，但caption不同且没有已完成R06配对，不能据此单独证明文本信息越少越好或辅助方案无效。后续选择仍只根据val，不因已查看test调整方案。

### 8.2 主文本与早期最佳现象

R03的best-val MAE=9.6707略低于full-taxonomy基线R01的10.0030，但RMSE分别为28.6010与26.4758；test MAE分别12.5750与12.6490，RMSE分别37.7194与36.6432。不能据此宣称更长的taxonomy文本更好，也不能把跨caption差异算成层级辅助训练收益。当前没有真正visual-only对照，无法隔离全部文本输入的贡献，也没有严格复现TPC论文的CountGD配方。

| 已完成实验 | 最佳轮次 | best-val MAE / RMSE | 第30轮val MAE / RMSE |
| R01 | 2 | 10.0030 / 26.4758 | 10.7017 / 35.3798 |
| R02 | 3 | 10.6867 / 29.0248 | 11.6687 / 38.5785 |
| R03 | 12 | 9.6707 / 28.6010 | 9.9129 / 31.2750 |

后期train loss下降但val未刷新best，与泛化停滞/退化相符；这不是“再增加epoch就会改善”的证据。也不足以确定失败机制是梯度冲突、辅助权重过强或双曲几何本身；这些目前都是待验证假设。

### 8.3 结论强度与剩余证据

只有seed42，不能主张稳定收益、统计显著、统计等效或所有条件下无效。各caption配对和单项诊断尚未全部完成；多seed、Euclidean几何对照及更细粒度密度/器官分组分析仍待条件满足后执行。合法锥率0、辅助loss下降只说明已记录的数值/机制检查，不能替代计数指标或证明实现无缺陷。

![各caption内的逐轮val MAE](../runs/tpc268_v3_exclude3/planning/val_mae_curves_20261016.png)

图中每点为一轮完整验证；三个panel按主caption分开，未作平滑或补点。R07尚无正式epoch点，未画入；此图仅对应本次报告快照。

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

R01/R02/R03在`9df0651`且dirty的工作区启动，不代表它们用了未排除三图的旧数据协议；实际保存配置和checkpoint均记录了三张排除名单、当前坐标策略和有效registry fingerprint。本次已核对这些字段，但缺乏每次启动的完整不可变源码归档，不能仅凭HEAD声称逐字节复现。当前`8a26e86`也有工作区改动：transformer.py将禁用autocast的旧API替换为`torch.amp.autocast('cuda', enabled=False)`；该语义兼容改动已为R02 test单独存diff，本次不修改它。

| ID | 相对实验根目录的run | 准确启动脚本 | 主要证据 |
| R01 | `full_baseline_seed42/` | `run_r01.sh` | `full_baseline_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R02 | `full_method_seed42/` | `run_r02.sh` | `full_method_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R03 | `species_baseline_seed42/` | `run_r03.sh` | `species_baseline_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R04 | `species_method_seed42/` | `run_r04.sh` | `species_method_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R05 | `organ_baseline_seed42/` | `run_r05.sh` | `organ_baseline_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |
| R07 | `contrast_seed42/` | `run_r07.sh` | `contrast_seed42/config_args_all.json`、`log.txt`、`console.txt`、`checkpoint_best_regular.pth`（若已生成） |

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
| R07快照 | 第1轮正式训练val日志及snapshot_metadata.json | [test_metrics.json](../runs/tpc268_v3_exclude3/contrast_seed42/test_snapshot_20261016_153930/test_metrics.json) | [test_counts.json](../runs/tpc268_v3_exclude3/contrast_seed42/test_snapshot_20261016_153930/test_counts.json) |

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

## 附录 A：后续实验计划与命令（2026-10-17优先级修订）

**2026-10-17优先级补充：用户随后明确要求先提供R08启动命令。** 本次已准备原计划R08的GPU0后台脚本，READY但未执行；R07继续原训练，R06/R09仍不自动展开。P01论文Table 4“3 visual exemplars＋full taxonomy”的初始化和监督配方缺项继续保留，P01训练尚未启动，不能把R08或猜测配置称作论文完全复现。

核查来源：[论文§4.5与Table 4](https://arxiv.org/html/2603.21229v1#S4.SS5)、[官方仓库](https://github.com/tiny-smart/TPC-268)、[项目页](https://tiny-smart.github.io/tpc268-project-page/)、[公开权重请求Issue #3](https://github.com/tiny-smart/TPC-268/issues/3)。论文确认重新训练、3个视觉exemplars，主文本格式为七级名称逗号序列`Kingdom, Phylum, Class, Order, Family, Genus, Species.`；对应test为MAE=16.90/RMSE=43.32/R²=0.71，未单独报告该设置的val。**论文未说明从FSC147 CountGD权重微调还是GroundingDINO初始化**；“retrain”不能推出具体初始化，更不代表随机初始化全部网络。

当前R01文本为`organ of species; taxonomy: ... .`，从checkpoint_fsc147_best.pth初始化，使用2px载体框/center-only监督、冻结backbone.0与BERT、30epoch及整图阈值0.23/0。这些是本地协议，不是已验证的作者配方。除了文本差异，作者的初始化、点到监督转换、冻结/优化/预算、阈值、crop/SAM/exemplar后处理及坐标问题处理均待核实；不能默认打开原CountGD的所有后处理就等于TPC论文设置。

本地7份官方标注/split资产SHA256与记录来源一致，官方repo HEAD仍为`a382e85013673a3485e76a2fc2af158c0f779fdf`。当前有效split=6998/999/2000，公开原split=7000/1000/2000；用户批准的3图排除保持不变。taxonomy未解析图像train453/val56/test105，当前full-taxonomy会退回species，作者如何处理未知。因此直接改caption或改回全量split不足以完成严格复现，也不能擅自恢复已排除图、猜测分类或修改原数据。

已保存审计：[protocol_audit.json](../runs/tpc268_paper_reproduction_20261017/protocol_audit.json)，官方README/通用Dataset副本及来源hash在同目录reference。该Dataset只给出点和3个exemplar框，不给CountGD专用监督转换/训练配置。已审阅的公开main仓库/项目页/论文未找到Table 4对应训练配置或权重；用户确认没有额外代码或权重。GitHub API限流403，但原始文件/HTML及git ls-remote可访问，此结论不是把网络失败误当文件不存在。

下一步先取得或核实上述作者配方；所需问题已整理为[author_questions.md](../runs/tpc268_paper_reproduction_20261017/author_questions.md)，仅为本地草稿，未联系作者。若只能依据公开资料重建，必须逐项声明假设并另列“公开信息重建基线”，不能称完全复现；至少固定纯七级文本、原型覆盖、点监督、初始化与推理协议，和原R01独立记录。P01目前为WAITING_AUTHOR_PROTOCOL，尚无可信的完整复现启动命令。

| 优先级 | ID | 状态 | 配置 / 输出run ID | 对照与问题 | 启动条件 |
|---|---|---|---|---|---|
| P1 | R07 | RUNNING | cfg_tpc268_contrast.py / contrast_seed42 | 对R01：contrast单独是否改善计数？ | 已在GPU2运行；短程已通过，正在正式30轮训练 |
| P0 | P01 | WAITING_AUTHOR_PROTOCOL | tpc268_paper_reproduction_20261017 / protocol_audit.json | 复现论文Table 4全分类文本基线 | 先核实初始化/监督/训练推理配方；未启动 |
| P1（用户明确先启动） | R08 | READY | cfg_tpc268_entailment.py / entailment_seed42 | 对R01：TT/TV单独是否改善计数？ | 执行下方run_r08.sh；先独立短程通过，再正式30轮 |
| P2 | R09 | BLOCKED | cfg_tpc268_euclidean.py / euclidean_seed42 | 同完整辅助目标换几何，隔离Lorentz价值 | R02最终best-val及R07/R08结果就绪，且蕴涵或组合显示潜力；若仍要检验/主张几何差异则必做 |
| P2 | R06 | BLOCKED | cfg_tpc268_organ_full.py / organ_method_seed42 | 配对R05，检查弱主文本下辅助收益 | R05完成，且R04或单项诊断有候选收益；若所有组合/单项均退化则不自动展开 |
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
