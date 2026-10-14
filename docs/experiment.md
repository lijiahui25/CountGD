# TPC-268 实验协议与执行记录

更新：2026-10-14；代码基线 `0c99a25`。实现差异见 [implement.md](implement.md)。本文同时承担可交给 Codex 的命令手册和后续实验记录；以后每次仓库工作都同步更新这两个文档。

**已知状态**：用户确认 Ubuntu 服务器已开始训练。当前本地没有服务器日志，因此实际运行 ID、开始时间、使用的 commit、配置、seed、输出路径和结果都尚未核实。下方 R01–R19 是预定矩阵，不代表相应任务已启动。服务器 Codex 应先把正在运行的任务和真实日志回填到本文第 8 节，再决定是否执行余下命令；不得重复启动同一 run。

**协议版本**：GitHub `0c99a25` 开始统一排除三张错误标注图，并裁剪与图像相交的越界 exemplar。它与之前的 `9df0651` 数据协议不同。已在旧版本启动的训练应在原代码/原配置下继续，记录旧 commit 和独立输出目录；不要以新版本续训旧 checkpoint，也不要直接和新协议结果作成对消融。以下是当前代码的新实验模板，目录使用 `runs/tpc268_exclusions_v1/`；已有服务器目录必须按实际情况登记。

## 给服务器 Codex 的任务

先记录正在运行的真实实验与环境，再按 M0 → M1 → M2 → M3 的未完成部分执行；每阶段更新本文第 8 节。M4 是正式结论所需的多 seed 扩展。不要新增独立测试文件，不要下载本地已有的数据集、标注或权重。数据/权重/`runs/` 不提交；`docs/implement.md` 与 `docs/experiment.md` 进入 Git 并随之后的工作同步维护。

机器、数据、驱动或 CUDA 算子不满足 M0 时，先修复具体问题并重做检查，再开始新的正式训练。计数指标没有提升也是有效结果；不要为得到正结果反复挑 seed、挑 test 阈值或改标签。任何协议变更须写入本文，使用新输出目录并重跑相应基线。以下模板默认单 GPU、FP32、batch size 4；服务器已有任务以实测配置为准。

## 1. 要验证的主张和固定边界

| 主张 | 要排除的解释 | 最低证据 | 对应实验 |
|---|---|---|---|
| C1：基于匹配对象 query 的层级辅助训练能改善官方划分上的计数泛化 | 收益只来自更丰富的主 caption 或一次幸运 seed | 同 caption、同冻结策略的计数对照；多 seed；species/organ 主 caption 控制 | B1、B2、B4 |
| C2：Lorentz 锥几何在同辅助目标下比欧氏锥几何更有效 | 任意额外监督均有相同收益，几何没有独立贡献 | full、contrast-only、entailment-only、Euclidean 对照；几何主张需多 seed | B3、B4 |

当前仅是原型，尚无正式训练结果。以下“预期”是待验证假设与判定条件，不是已取得的结果，也不是承诺的 MAE/RMSE 数值。

### 数据和模型协议

- 官方 train/val/test 原始数量为 7000/1000/2000 张；当前统一排除 2 张 train、1 张 val，有效数量为 6998/999/2000 张。验证集用于 checkpoint 选择，测试集只用于最终报告。species-organ 单元划分不能等同于完全无重叠的 species 划分：当前 train-val、train-test、val-test 原始 species 名称分别重叠 3、7、4 个。若声称“未见物种泛化”，必须从最终逐图结果单独报告未见 species 子集。
- 固定当前 alias 与 taxonomy registry。当前有 22 个原始 species 名称未匹配；可解析图像覆盖率 train 6545/6998、val 943/999、test 1895/2000。除三张明确排除图外，其余图像保留计数监督，无法解析的图像跳过层级辅助监督；full-taxonomy caption 在这部分退回 species 文本。不能报告成 100% 层级覆盖。
- 当前审计实际有 269 个 species-organ 单元。保留官方原文件；只按明确的数据质量规则排除三张图，不为对齐名称中的“268”删单元。当前有效 train 中原始 count 超过 900 的图像有 64 张、最大 1462；val 最大 833，test 最大 709。
- 所有独立训练从 `checkpoints/checkpoint_fsc147_best.pth` 初始化，BERT/tokenizer 从 `checkpoints/bert-base-uncased` 读取。不要把 baseline 微调后的权重当作 full 的初始化。
- Swin backbone 与 BERT 按原配置冻结；共享 `feat_map`、Feature Enhancer、Decoder、预测头按原训练设置训练。启用辅助项时，再训练 query/text 两个 128 维小头。冻结 BERT 不等于冻结共享适配器：辅助文本梯度能进入 `feat_map`。不引入新 BERT、CLIP、LoRA 或各层独立图像头。
- 900 个 query、DN=0，最终 Decoder query 与最终预测的 Hungarian 匹配对应；计数损失不变。辅助实例每图至多抽取 64 个已匹配 GT query，此上限不删 GT，也不改变计数目标。
- 训练使用原 CountGD 随机 flip + resize/crop 策略：一半走直接随机 resize，另一半走 400/500/600 resize → 384–600 random crop → 最终随机 resize，短边 480–800、长边上限 1333。裁掉的点同步从 GT 删除，crop 后 exemplar 为 0–3 个，batch 按剩余最少 exemplar 数统一；原始标注仍须有三个合法 exemplar；先将与图像相交的越界 ROI 截到原图内，点越界则报错。
- 验证/测试固定短边 800、长边上限 1333，使用三个 exemplar 和原图 GT count。主结果统一整图推理，box threshold 0.23、text threshold 0，不加 adaptive crop、SAM、exemplar correction。
- 原仓库自适应裁切按**预测数达到 900**触发；真实 count 小于 900 不能排除预测过多时触发。SAM 和 exemplar correction 也不是由这个 GT 条件统一控制。本计划现有 TPC-268 评估入口没有这三个后处理开关，不使用不存在的命令。
- AdamW，基础 LR 1e-4、weight decay 1e-4、梯度裁剪 0.1；30 epochs，StepLR 每 10 epochs 衰减。相同冻结/参数组设置，单 GPU batch size 4，seed 首轮 42，正式复跑 43、44，不启用 `--amp`。
- full 的权重：contrast 0.1、TT 0.05、TV 0.05，辅助权重第一 epoch 按 step 线性 warmup。曲率 c=1 固定；合法半径映射开启；每相邻文本边至多 16 个错误父节点，排除真实祖先，negative margin=0.1、negative weight=1。
- 文本 TT 包含正确父边、错误父节点负蕴涵及 species→species-organ 任务 bridge。TV 当前只实现正确计数单元→匹配 query 的正蕴涵；错误文本父节点与 query 的锥关系是诊断指标，**没有额外 TV 负蕴涵损失**。entailment-only 因而不能解释成完整的视觉分支排斥目标。
- species→species-organ 是计数任务 bridge，不是生物分类学第八级。主 query 已接受 caption/exemplars 条件，不能把辅助分类或锥包含率直接叫作纯图像识别能力。

主 caption 三种模式，例如同一图像分别用 `fruit of Abutilon indicum; taxonomy: ... .`、`fruit of Abutilon indicum .`、`fruit .`。每对 baseline/full 必须具有完全相同主 caption；organ 控制仍保留器官名称与视觉 exemplar。训练辅助文本由七级 registry 的独立 prefix 与计数单元组成，使用同一 BERT/feat_map；推理不需要辅助文本编码。

## 2. 服务器准备：M0

以下 shell 块从仓库根目录执行，使用 Bash。服务器先拉取远程 main（其中已经包含本文件），并上传全部本地数据与标注目录、完整权重。上传 `data/TPC-268/`、`data/tpc268_metadata/annotations/`、`data/tpc268_metadata/splits/`、`checkpoints/` 的实际文件；不要只复制 macOS 的绝对路径符号链接。小型 sources/alias/unresolved 元数据随代码提交，dataset annotations 和图像不随 Git 提交。

### 2.1 锁定依赖并记录设备

```bash
set -euo pipefail
mkdir -p runs/tpc268_exclusions_v1/preflight
uv --version
uv sync --locked --python 3.10
nvidia-smi | tee runs/tpc268_exclusions_v1/preflight/nvidia-smi.txt
nvcc --version | tee runs/tpc268_exclusions_v1/preflight/nvcc.txt
uv run --no-sync python - <<'PY' | tee runs/tpc268_exclusions_v1/preflight/environment.json
import json, platform, torch
from torch.utils.cpp_extension import CUDA_HOME
assert torch.cuda.is_available(), 'CUDA unavailable: repair driver/runtime before training'
assert CUDA_HOME, 'CUDA toolkit/nvcc required to compile the extension'
print(json.dumps({'python': platform.python_version(), 'torch': torch.__version__,
                  'torch_cuda': torch.version.cuda, 'CUDA_HOME': CUDA_HOME,
                  'gpu': torch.cuda.get_device_name(0),
                  'gpu_memory_bytes': torch.cuda.get_device_properties(0).total_memory}, indent=2))
PY
git rev-parse HEAD > runs/tpc268_exclusions_v1/preflight/git_commit.txt
uv pip freeze > runs/tpc268_exclusions_v1/preflight/packages_before_extension.txt
```

当前 lock 固定 torch 2.13.0 / torchvision 0.28.0，`pyproject.toml` 用 uv 的 `[[tool.uv.index]]` 和 `[tool.uv.sources]` 明确选择 CUDA 13 wheel；必须核对实际安装的 `torch.version.cuda`、nvcc、驱动与 GPU 架构。不要把 `nvidia-smi` 显示的最高 CUDA 支持版本当成已安装的 nvcc。运行包有 CUDA runtime 不代表系统已有编译工具链。

依赖安装失败或机器不支持该组合时，停止 M0，明确记录错误。只有在选定并验证另一套 Python/PyTorch/CUDA/lock 后，才能另开协议目录重新开始全部对照；不要仅为某一种方法换环境。本轮仍以 lock 与服务器实际安装结果为准。

### 2.2 编译现有 CUDA 扩展并执行现有检查

```bash
uv pip install --python .venv/bin/python setuptools wheel ninja
MAX_JOBS=4 uv pip install --python .venv/bin/python --no-build-isolation --no-deps ./models/GroundingDINO/ops
uv run --no-sync python -c 'import MultiScaleDeformableAttention; print("CUDA extension import passed")'
uv run --no-sync python models/GroundingDINO/ops/test.py | tee runs/tpc268_exclusions_v1/preflight/cuda_ops.txt
uv pip freeze > runs/tpc268_exclusions_v1/preflight/packages.txt
```

通过标准：扩展可导入，现有检查的两项 forward 对照和四项 gradcheck 都输出 `True`，无 CUDA kernel error。这个旧检查脚本的 forward 部分只打印布尔值，必须检查输出，不能只看退出码。代码已将旧 THC 头文件、Tensor `.type()` 分派和 `.data<T>()` 更新为现行 ATen 接口；macOS 无法验证真实 CUDA 编译，服务器这一步是必需门槛。

之后统一 `uv run --no-sync`，不要在中间重新 `uv sync` 清掉额外安装的扩展。需要更新依赖时重新安装扩展并复查。参考 [uv 同步语义](https://docs.astral.sh/uv/concepts/projects/sync/) 与 [uv/PyTorch 官方指南](https://docs.astral.sh/uv/guides/integration/pytorch/)。

### 2.3 文件指纹、数据、crop 和几何检查

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export MPLCONFIGDIR="$PWD/runs/tpc268_exclusions_v1/.mpl-cache"
export CUDA_VISIBLE_DEVICES=0
uv run --no-sync python - <<'PY' > runs/tpc268_exclusions_v1/preflight/input_sha256.json
import hashlib, json
from pathlib import Path
files = [Path('checkpoints/checkpoint_fsc147_best.pth'), Path('uv.lock')]
files += sorted(Path('checkpoints/bert-base-uncased').rglob('*'))
files += sorted(Path('data/tpc268_metadata').rglob('*'))
out = {}
for p in files:
    if p.is_file():
        h = hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        out[str(p)] = h.hexdigest()
assert 'checkpoints/checkpoint_fsc147_best.pth' in out
assert Path('checkpoints/bert-base-uncased/config.json').is_file()
assert Path('data/TPC-268').is_dir()
print(json.dumps(out, indent=2))
PY
uv run --no-sync python -m datasets.tpc268 --audit --crop-smoke-check \
  --config config/cfg_tpc268_full.py --tokenizer checkpoints/bert-base-uncased \
  --output runs/tpc268_exclusions_v1/preflight/data_audit.json
uv run --no-sync python - <<'PY'
import json
from pathlib import Path
x = json.loads(Path('runs/tpc268_exclusions_v1/preflight/data_audit.json').read_text())
for split, count in [('train', 6998), ('val', 999), ('test', 2000)]:
    assert x[split]['images'] == count
    assert not x[split]['missing_images'], (split, x[split]['missing_images'])
    assert not x[split]['coordinate_audit']['errors'], (split, x[split]['coordinate_audit']['errors'])
assert len({x[s]['registry_fingerprint'] for s in ('train', 'val', 'test')}) == 1
assert x['train']['registry_fingerprint'] == 'cf080ec256b9f9595a0cd6110b30d80fa84da0d49799217054e682185d79d65d'
assert [len(x[s]['excluded_paths']) for s in ('train', 'val', 'test')] == [2, 1, 0]
print('Effective split sizes, coordinates, exclusions and registry consistency passed')
PY
uv run --no-sync python -m models.GroundingDINO.taxonomy_losses --smoke-check
uv run --no-sync python tools/compare_tpc268_runs.py --smoke-check
```

通过标准：三个 split 无图片交叉；官方 txt/JSON 单元交叉核对通过；缺失图片为零；annotation/exemplar 校验无错误；crop 后 GT/count/exemplar 同步、空目标可用；完整主文本和辅助 prefix 不被截断。Lorentz/Euclidean 检查须有有限梯度、合法半径和同方向坍缩被负蕴涵惩罚。审计将未解析名称写到输出 JSON 的同名 `.unresolved_taxonomy.json` 旁文件，不修改仓库内的 provenance 元数据；确认 coverage/fingerprint 与固定协议一致。当前本地审计：train/val/test 的越界 exemplar 修正图数为 91/1/0，剩余坐标错误 0。

可选 CPU 模型复查（已有入口，非 GPU 训练证明）：

```bash
uv run --no-sync python -m models.GroundingDINO.groundingdino --smoke-check \
  --config config/cfg_tpc268_organ_full.py --augmentation-seed 0 \
  --output runs/tpc268_exclusions_v1/preflight/cpu_model_smoke.json
```

### 2.4 真正的 GPU optimizer 短程检查

```bash
for variant in baseline full organ_full euclidean; do
  uv run --no-sync python main.py -c "config/cfg_tpc268_${variant}.py" \
    --datasets config/datasets_tpc268.json --device cuda --seed 42 --num_workers 4 \
    --pretrain_model_path checkpoints/checkpoint_fsc147_best.pth --debug --save_log \
    --output_dir "runs/tpc268_exclusions_v1/preflight/gpu_${variant}" \
    --options text_encoder_type=checkpoints/bert-base-uncased epochs=1 batch_size=4
done
```

`--debug` 只把训练截到约 15 个 optimizer step，验证仍跑完整 999 张，所以此阶段不是几秒钟检查。crop、文本长度和辅助项改变显存，必须至少覆盖上述四种配置。通过标准：实际 CUDA 前向/反向/更新完成、loss 无 NaN/Inf、没有锥定义域异常、保存 checkpoint 和验证 JSON 成功。查看梯度通路与日志时，应确认冻结 encoder、共享适配器和辅助小头的状态符合固定协议。短程中辅助权重尚处在 warmup，不能根据此时数值判断方法有效性。

若 OOM，先在所有配置统一改 `batch_size=2` 或 `1`，重做本节；随后修改下方 helper 的固定 batch，并另建协议目录。当前没有梯度累积实现，不宣称 batch 变小仍有相同有效 batch。不得使用 debug checkpoint 开始正式 run。

## 3. 正式训练命令与顺序

### 3.1 建立复用命令

以下块在当前 Bash 中定义函数，也可整体保存为忽略目录下的 `runs/tpc268_exclusions_v1/helpers.sh`，以后 `source` 它。每个 run 有唯一目录；重复执行同一个训练函数会从该目录的 `checkpoint.pth` 自动续训，评估加载该 run 的最佳验证 checkpoint。

```bash
set -euo pipefail
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=0
export MPLCONFIGDIR="$PWD/runs/tpc268_exclusions_v1/.mpl-cache"
TPC_RUN_ROOT="runs/tpc268_exclusions_v1"
train_run() {
  local run_id="$1" cfg="$2" seed="$3"
  shift 3
  mkdir -p "$TPC_RUN_ROOT/${run_id}_seed${seed}"
  uv run --no-sync python main.py -c "$cfg" \
    --datasets config/datasets_tpc268.json --device cuda --seed "$seed" --num_workers 4 \
    --pretrain_model_path checkpoints/checkpoint_fsc147_best.pth --save_log \
    --output_dir "$TPC_RUN_ROOT/${run_id}_seed${seed}" \
    --options text_encoder_type=checkpoints/bert-base-uncased batch_size=4 "$@" \
    2>&1 | tee -a "$TPC_RUN_ROOT/${run_id}_seed${seed}/console.txt"
}
eval_run() {
  local run_id="$1" cfg="$2" seed="$3" split="${4:-val}"
  local run_dir="$TPC_RUN_ROOT/${run_id}_seed${seed}"
  test -f "$run_dir/checkpoint_best_regular.pth"
  mkdir -p "$run_dir/$split"
  uv run --no-sync python main.py -c "$cfg" \
    --datasets config/datasets_tpc268.json --device cuda --seed "$seed" --num_workers 4 \
    --eval --eval_split "$split" --resume "$run_dir/checkpoint_best_regular.pth" \
    --output_dir "$run_dir/$split" \
    --options text_encoder_type=checkpoints/bert-base-uncased batch_size=4 \
    2>&1 | tee -a "$run_dir/$split/console.txt"
}
```

评估返回的 `training_protocol` 来自训练 checkpoint。训练目录根下的 `val_counts.json` 会每 epoch 覆盖，通常对应最后 epoch；最终比较必须用 helper 重评 best 后的 `<run>/val/`，不能把最后 epoch 指标冒充最佳 checkpoint 指标。训练 `log.txt` 中的 `test_mae` 实际是当 epoch 的 **val** MAE，不是 test。

### 3.2 第一阶段 M1：先建立 full-taxonomy 主结果（R01–R02）

```bash
# R01：原计数目标，无层级辅助；full-taxonomy 主 caption。
train_run full_baseline config/cfg_tpc268_baseline.py 42
eval_run  full_baseline config/cfg_tpc268_baseline.py 42 val
# R02：逐级对比 + Lorentz TT/TV；与 R01 相同主 caption。
train_run full_method config/cfg_tpc268_full.py 42
eval_run  full_method config/cfg_tpc268_full.py 42 val
uv run --no-sync python tools/compare_tpc268_runs.py \
  "$TPC_RUN_ROOT/full_baseline_seed42/val" "$TPC_RUN_ROOT/full_method_seed42/val" \
  --output "$TPC_RUN_ROOT/M1_val_comparison.json"
```

预期：两者计数训练稳定；若辅助监督有用，R02 的 val MAE/RMSE 应低于 R01，并具有较好的正确父锥包含率/较低错误父锥包含率。单 seed 的改进只能作为候选证据。若只有锥指标变好、计数不变，不能支持 C1；仍继续下一阶段定位原因。

### 3.3 第二阶段 M2：控制主 caption 中的分类信息（R03–R06）

```bash
# R03/R04：仅 species + organ，不输入七级主 caption。
train_run species_baseline config/cfg_tpc268_species.py 42
eval_run  species_baseline config/cfg_tpc268_species.py 42 val
train_run species_method config/cfg_tpc268_species_full.py 42
eval_run  species_method config/cfg_tpc268_species_full.py 42 val
uv run --no-sync python tools/compare_tpc268_runs.py \
  "$TPC_RUN_ROOT/species_baseline_seed42/val" "$TPC_RUN_ROOT/species_method_seed42/val" \
  --output "$TPC_RUN_ROOT/M2_species_val_comparison.json"

# R05/R06：仅 organ 主 caption，独立辅助文本仍只在训练时使用。
train_run organ_baseline config/cfg_tpc268_organ_baseline.py 42
eval_run  organ_baseline config/cfg_tpc268_organ_baseline.py 42 val
train_run organ_method config/cfg_tpc268_organ_full.py 42
eval_run  organ_method config/cfg_tpc268_organ_full.py 42 val
uv run --no-sync python tools/compare_tpc268_runs.py \
  "$TPC_RUN_ROOT/organ_baseline_seed42/val" "$TPC_RUN_ROOT/organ_method_seed42/val" \
  --output "$TPC_RUN_ROOT/M2_organ_val_comparison.json"
```

预期：若辅助训练产生超出读取主 taxonomy 文本的收益，在 species 和尤其 organ 配对中仍应出现计数改进。不同 caption 的绝对 MAE 可以作输入比较，但方法增益必须分别计算同 caption 的 delta。若只有 R02/R01 有增益，应收窄结论为 taxonomy 条件下的计数收益；organ 配对即使成功，也只支持在器官文本/exemplar 条件下的定位计数改善，不能宣称 query 是纯视觉表示。

### 3.4 第三阶段 M3：隔离监督与几何贡献（R07–R09）

```bash
# R07：只保留逐级对比，没有 TT/TV。
train_run contrast config/cfg_tpc268_contrast.py 42
eval_run  contrast config/cfg_tpc268_contrast.py 42 val
# R08：只保留蕴涵；TT 含错误父节点负项，TV 当前仍只有正项。
train_run entailment config/cfg_tpc268_entailment.py 42
eval_run  entailment config/cfg_tpc268_entailment.py 42 val
# R09：相同逐级对比 + TT/TV，换为合法域内的欧氏锥。
train_run euclidean config/cfg_tpc268_euclidean.py 42
eval_run  euclidean config/cfg_tpc268_euclidean.py 42 val
uv run --no-sync python tools/compare_tpc268_runs.py \
  "$TPC_RUN_ROOT/full_baseline_seed42/val" "$TPC_RUN_ROOT/full_method_seed42/val" \
  "$TPC_RUN_ROOT/contrast_seed42/val" "$TPC_RUN_ROOT/entailment_seed42/val" \
  "$TPC_RUN_ROOT/euclidean_seed42/val" --output "$TPC_RUN_ROOT/M3_val_comparison.json"
```

预期：若组合目标各有作用，full 相对两种单项应有额外计数收益；若 Lorentz 有独立价值，full 应优于 Euclidean。Euclidean 是当前的欧氏**锥**对照，不是复现任一论文的完整欧氏分类基线。若 contrast 与 full 相当，现有蕴涵项收益未被证明，优先选择更简单的 contrast 方法；若 Euclidean 与 Lorentz 相当，报告层级监督有效，但不主张双曲几何更好。entailment-only 必须同时检查错误父锥包含率，不能只据正边损失接近 0 判定树已学好。

## 4. M4：多 seed、简化检查及最终 test

首轮共 9 次正式训练。它们完成后先冻结判断标准和待复跑对照，再增加 seed，所有复跑仍从原 FSC147 权重初始化。

### 4.1 必需的主结果稳定性（R10–R13，累计 13 次）

```bash
for seed in 43 44; do
  train_run full_baseline config/cfg_tpc268_baseline.py "$seed"
  eval_run  full_baseline config/cfg_tpc268_baseline.py "$seed" val
  train_run full_method config/cfg_tpc268_full.py "$seed"
  eval_run  full_method config/cfg_tpc268_full.py "$seed" val
  uv run --no-sync python tools/compare_tpc268_runs.py \
    "$TPC_RUN_ROOT/full_baseline_seed${seed}/val" "$TPC_RUN_ROOT/full_method_seed${seed}/val" \
    --output "$TPC_RUN_ROOT/M4_full_seed${seed}_val.json"
done
```

seed42/43/44 各自报告 MAE、RMSE、相对对应 baseline 的 delta，再报告 mean±sample std。`delta = method - baseline`，负值代表改善。主张需要配对增益方向一致、平均改善不被 seed 波动解释；只有一个 seed 好而另两个不支持时，报告不稳定。三个 seed 仍是小样本，不自动意味着统计显著；可以补充固定 checkpoint 的逐图配对 bootstrap，注明它不替代训练 seed 不确定性。

### 4.2 结论决定的扩展

如果保留“Lorentz 优于 Euclidean”的 C2，**必须**再跑 Euclidean seed43/44（累计 15 次）：

```bash
for seed in 43 44; do
  train_run euclidean config/cfg_tpc268_euclidean.py "$seed"
  eval_run  euclidean config/cfg_tpc268_euclidean.py "$seed" val
  uv run --no-sync python tools/compare_tpc268_runs.py \
    "$TPC_RUN_ROOT/full_baseline_seed${seed}/val" "$TPC_RUN_ROOT/full_method_seed${seed}/val" \
    "$TPC_RUN_ROOT/euclidean_seed${seed}/val" --output "$TPC_RUN_ROOT/M4_geometry_seed${seed}_val.json"
done
```

如果保留“无需主 caption 的 taxonomy/species 名称仍有收益”的强 C1，**必须**增加 organ 配对 seed43/44（累计 19 次，包括上项）：

```bash
for seed in 43 44; do
  train_run organ_baseline config/cfg_tpc268_organ_baseline.py "$seed"
  eval_run  organ_baseline config/cfg_tpc268_organ_baseline.py "$seed" val
  train_run organ_method config/cfg_tpc268_organ_full.py "$seed"
  eval_run  organ_method config/cfg_tpc268_organ_full.py "$seed" val
  uv run --no-sync python tools/compare_tpc268_runs.py \
    "$TPC_RUN_ROOT/organ_baseline_seed${seed}/val" "$TPC_RUN_ROOT/organ_method_seed${seed}/val" \
    --output "$TPC_RUN_ROOT/M4_organ_seed${seed}_val.json"
done
```

可选附录的简化检查（首轮仅一个 seed，若成为主结论再复跑）：关闭 species→unit bridge 的 TT 项，检查这个任务假设是否必要。其他配置不变，TV 仍存在，因此这是 **TT bridge 删除**，不是删除所有计数单元关系。

```bash
train_run no_tt_bridge config/cfg_tpc268_full.py 42 bridge_weight=0.0
eval_run  no_tt_bridge config/cfg_tpc268_full.py 42 val
uv run --no-sync python tools/compare_tpc268_runs.py \
  "$TPC_RUN_ROOT/full_baseline_seed42/val" "$TPC_RUN_ROOT/full_method_seed42/val" \
  "$TPC_RUN_ROOT/no_tt_bridge_seed42/val" --output "$TPC_RUN_ROOT/optional_bridge_val.json"
```

不在本轮增加 BERT 解冻、LoRA、更多视觉头或新数据集；它们会扩大研究范围。若以后尝试解冻，须加入同等解冻的 CountGD baseline。

### 4.3 最终 test：方法与阈值冻结后执行

选 checkpoint 的唯一依据是该 run 的 val MAE。不得通过 test 选择 epoch、seed、lambda 或 threshold。以下评估首轮 9 个方法，形成完整 test 主表/消融表；如果预算只保留部分方法，至少保留全部主张需要的配对基线，并在 tracker 说明未执行项。

```bash
for spec in \
  'full_baseline cfg_tpc268_baseline' 'full_method cfg_tpc268_full' \
  'species_baseline cfg_tpc268_species' 'species_method cfg_tpc268_species_full' \
  'organ_baseline cfg_tpc268_organ_baseline' 'organ_method cfg_tpc268_organ_full' \
  'contrast cfg_tpc268_contrast' 'entailment cfg_tpc268_entailment' \
  'euclidean cfg_tpc268_euclidean'; do
  read -r run_id cfg_name <<< "$spec"
  eval_run "$run_id" "config/${cfg_name}.py" 42 test
done
uv run --no-sync python tools/compare_tpc268_runs.py \
  "$TPC_RUN_ROOT/full_baseline_seed42/test" "$TPC_RUN_ROOT/full_method_seed42/test" \
  "$TPC_RUN_ROOT/species_baseline_seed42/test" "$TPC_RUN_ROOT/species_method_seed42/test" \
  "$TPC_RUN_ROOT/organ_baseline_seed42/test" "$TPC_RUN_ROOT/organ_method_seed42/test" \
  "$TPC_RUN_ROOT/contrast_seed42/test" "$TPC_RUN_ROOT/entailment_seed42/test" \
  "$TPC_RUN_ROOT/euclidean_seed42/test" --split test --output "$TPC_RUN_ROOT/final_seed42_test.json"
for seed in 43 44; do
  eval_run full_baseline config/cfg_tpc268_baseline.py "$seed" test
  eval_run full_method config/cfg_tpc268_full.py "$seed" test
  uv run --no-sync python tools/compare_tpc268_runs.py \
    "$TPC_RUN_ROOT/full_baseline_seed${seed}/test" "$TPC_RUN_ROOT/full_method_seed${seed}/test" \
    --split test --output "$TPC_RUN_ROOT/final_full_seed${seed}_test.json"
done
```

执行了 Euclidean、organ 扩展时，用同一个 `eval_run ... test` 重评各 seed，并带对应 seed 的 baseline 交给比较工具。报告所有预先指定 seed，不从 test 挑最佳 seed。测试结果为 2000 张；val 为 999 张。每个目录保存 `*_counts.json`、`*_metrics.json` 与 console；比较工具重新计算计数误差并拒绝不同 caption、冻结策略、数据指纹、训练预算或推理协议的无配对比较。

后续可以单独实现并验证官方 adaptive crop/SAM/exemplar correction 推理，但须为对应 baseline 与 full 同时运行、单列协议与表。TPC-268 不能直接复用 FSC147 特定图像的纠错名单。本轮不把后处理结果混入整图训练改动的主比较。

## 5. 五个实验块及结果判定

| 实验块 | 数据/比较/设置 | 核心指标和预期 | 失败解释 | 表或图/优先级 |
|---|---|---|---|---|
| B1 主结果，C1 | 官方 train→val/test；R01/R02，同 full-taxonomy caption；30 epochs，seed42/43/44 | MAE 主指标、RMSE 次指标、R² 描述；配对改善稳定，同时报告每 seed | 辅助层级监督未改善计数；不得以辅助 loss 替代结论 | 主表；必需 |
| B2 caption 控制，C1 | R03/R04、R05/R06；冻结和预算与 B1 相同；organ 强主张需三 seed | 各 caption 内 delta；预期 organ 配对仍改善才支持超出主分类文本的收益 | full 主文本有益，但辅助监督可能只适配已有分类条件 | 主表；首轮必需 |
| B3 新意隔离，C2 | R02/R07/R08/R09 与 R01；相同训练数据/主 caption/辅助权重 | MAE/RMSE；TT 正/负包含率与定义域；geometry 主张需三 seed | 单项更简洁；或几何无独立价值，收窄 C2 | 消融表；首轮必需 |
| B4 简化与稳定性，C1/C2 | 三 seed 配对；可选 no-TT-bridge；不引入新 encoder | 配对 delta mean±std、训练 step 时间/峰值显存、参数增量；bridge 删除无损则选更简单版本 | seed 不稳定则证据不足；bridge 非必需则不包装成关键贡献 | 主表误差条/附录；多 seed 必需，bridge 可选 |
| B5 失败分析，C1 | 用已有逐图结果，不再训练；按 organ、GT数量区间、已见/未见 species、taxonomy是否解析分组 | 每组 n、MAE/RMSE、有符号误差、预测=900 比例；检查低/高密度和漏/过计数 | 平均值掩盖某类退化、未解析样本或密集图像上限问题 | 失败案例图与分组表；必需 |

B5 固定 count 桶为 `[0,20)`、`[20,50)`、`[50,100)`、`[100,200)`、`[200,+∞)`，不要看结果后移动边界。示例图各取固定数量的最改善、最退化、预测达到上限和未解析 taxonomy 样本，同时保留原始逐图结果便于复核。这里的分组统计和三 seed 汇总尚无独立 CLI；服务器 Codex 可用一次性的 `uv run --no-sync python - <<'PY'` 读取真实 JSON、在 `runs/` 产出表，不能把辅助分类准确率当作计数分组结果。

现有几何诊断在**训练 loss 日志**中，评估路径不编码辅助文本，因此不能声称 `val_metrics.json` 已测得未见节点的锥包含率。重点查看 `train_tax_tt_rank_<rank>_positive_inclusion_rate_unscaled`、`...negative_inclusion_rate_unscaled`、`...negative_margin_violation_rate_unscaled`、`train_tax_aperture_invalid_rate_unscaled`、`train_tax_query_rank_<rank>_positive/negative_inclusion_rate_unscaled`（实际可用 rank 和 pair 数以日志为准）。没有合法 pair 的层级，其 0 值不代表完美表现。

预期非法锥率始终 0；正父包含率上升、错误父包含率下降、负 margin 违例下降，但没有预设必须达到 100%/0%。query 的正确/错误父包含率只是机制诊断，最终以 MAE/RMSE 判定。若训练几何良好而未见子集计数无增益，只支持训练表征被约束，不支持泛化主张。

## 6. 预算、暂停条件与恢复

| 阶段 | 正式训练数 | 继续条件 | 成本/风险 |
|---|---:|---|---|
| M0 环境、数据、GPU短程 | 0 | CUDA 算子、真实 optimizer、数据/crop/几何检查通过 | 四个短程各包含完整 val；实测显存/step时间 |
| M1 主结果 | 2 | 技术协议一致、计数 JSON 完整；无数值异常 | baseline 与 full 的辅助文本开销不同，分别测时 |
| M2 caption 控制 | +4 | 对照内主文本完全一致；记录正负结果 | caption 长度改变成本与条件信息 |
| M3 消融 | +3，累计9 | 检查计数与锥指标，不只看 loss | entailment-only 视觉负项缺失，结论有限 |
| M4 核心多seed | +4，累计13 | seed42/43/44全量报告 | 若 claim 扩展，加 Euclidean2 / organ4，累计19 |

先用 M0 和 R01 的真实数据估预算，不凭 GPU 型号编造小时数。单 GPU、batch4、drop_last 时每 epoch 为 1749 个训练 batch 与 999 张 val，30 epochs 的近似 GPU 小时：`30 × (1749 × 每训练step秒数 + 999 × 每val图秒数) / 3600`，另加最终重评和预检查。full/organ/Euclidean 分别测量自己的 step 时间；多卡改变全局 batch，不能直接替换当前单卡协议。

每 run 保存 latest、best 和第10/20/30 epoch checkpoint，约五份完整训练状态。先量 R01 的 checkpoint 实际大小，再按 runs 数估磁盘余量。不要自动删除 best、latest 或原始日志；可在完成归档后另行安排清理周期快照。

技术异常时暂停依赖该异常的运行：缺文件、split重叠、非法 exemplar、NaN/Inf、非法锥、CUDA kernel错误、fingerprint不一致、缺计数结果、配置与checkpoint不匹配。修复后记录新代码提交/环境/协议是否变化；如变化影响对照，重新跑相应组。单纯 MAE 未改善不属于技术异常。

断点续训：同一协议下重新执行同一个 `train_run`，自动读取 `checkpoint.pth` 与 optimizer/scheduler，保留历史最佳 val。若没有 latest 文件，会从原 FSC147 权重开始；执行前核对 tracker。旧协议 v1 的 checkpoint 不用于继续当前 `negative_parents_valid_cones_v2`。若希望重新从零初始化，用新 run ID，不能先删除检查点再悄悄重跑同一 ID。

## 7. 交付与最终核对

- [ ] M0 审计与 CUDA/optimizer 输出、git commit、lock 和输入 SHA256 保存完整。
- [ ] R01–R09 完成或明确记录技术阻塞；best checkpoint 的 val 单独重评。
- [ ] full-taxonomy、species、organ 各使用自己的匹配 baseline。
- [ ] 核心结果 seed42/43/44；几何/organ 强主张按要求补齐配对 seed。
- [ ] test 在方法/阈值冻结后执行；未使用 test 做调参或 checkpoint 选择。
- [ ] 输出主表、消融表、mean±std、分组错误与固定规则选择的案例。
- [ ] 区分训练几何诊断、条件 query 表征、真实计数泛化；报告 taxonomy 部分覆盖。
- [ ] 对无收益结果保留原始记录并收窄主张，不追加未经对照的 BERT/LoRA 收益。
- [ ] 数据/权重/`runs/` 保持 Git 忽略；本文及 `implement.md` 跟随 Git，同步服务器更新。

本地 2026-10-12 曾完成旧数据协议的 CPU 前后向/几何 smoke；2026-10-14 已对当前代码完成有效 6998/999/2000 图的本地全量数据审计，仍须在 Ubuntu 核对 CUDA/实际训练。用户已确认服务器训练开始；具体任务及指标待真实日志回填。

## 8. 执行追踪（持续更新）

本表是待核实的**计划矩阵**，不是服务器运行监控。用户于 2026-10-14 告知实验已开始，尚未提供具体 run/log；先查服务器实际进程、commit、配置、output_dir，再把对应行的 `UNKNOWN` 改为 `RUNNING` 或 `DONE` 并附证据。旧数据协议与 `0c99a25` 当前协议分表/分目录记录，不混作同一对照。

## 协议快照

| 项目 | 固定值或待填信息 |
|---|---|
| 代码 commit | 见 `runs/tpc268_v2/preflight/git_commit.txt`，服务器执行时填写 |
| Python / uv / PyTorch / CUDA / nvcc / GPU | M0 实测后填写，禁止猜测 |
| 数据/权重/lock 指纹 | `preflight/input_sha256.json` 与数据审计；审计后另存最终版本 |
| registry fingerprint | 当前审计：`cf080ec256b9f9595a0cd6110b30d80fa84da0d49799217054e682185d79d65d`；服务器核对 |
| 数据 | 原始7000/1000/2000；当前有效6998/999/2000；部分层级覆盖 |
| taxonomy覆盖 | train6545 / val943 / test1895 可解析；训练前固定 alias |
| 训练 | 30 epochs，单GPU batch4，FP32，原 resize/crop；固定 backbone/BERT 冻结 |
| 选择/评估 | best val MAE；整图、3 exemplar，threshold0.23，text_threshold0 |
| seed | 首轮42，正式稳定性43/44 |

状态只使用 UNKNOWN / TODO / RUNNING / DONE / FAILED / BLOCKED / SKIPPED。UNKNOWN 表示服务器状态未核实。每次开始记录时间、准确命令和输出目录；结束记录退出码、最佳 epoch（注明 0-based 或 1-based）、最佳 val MAE/RMSE、峰值显存、耗时。完成训练后重评 best 的 val，再填 DONE；test 在协议冻结后另填。

## 必需运行

| ID | 阶段/目的 | 配置或变体 | seed | 输出目录（根目录之下） | 状态 | best val MAE / RMSE | test MAE / RMSE |
|---|---|---|---:|---|---|---|---|
| S0 | 本地数据审计与历史 CPU smoke | 当前代码全量图片/坐标；旧协议 CPU 前后向 | — | 本地审计摘要见 `implement.md` | DONE | 不适用 | 不适用 |
| S1 | M0 环境/算子/数据检查 | CUDA extension + dataset audit | — | preflight/ | UNKNOWN | — | — |
| S2 | M0 GPU更新检查 | baseline/full/organ_full/euclidean，debug1epoch | 42 | preflight/gpu_* | UNKNOWN | 仅技术检查 | 不运行 |
| R01 | M1 full-caption baseline | cfg_tpc268_baseline.py | 42 | full_baseline_seed42/ | UNKNOWN | — | — |
| R02 | M1 主方法 | cfg_tpc268_full.py | 42 | full_method_seed42/ | UNKNOWN | — | — |
| R03 | M2 species baseline | cfg_tpc268_species.py | 42 | species_baseline_seed42/ | UNKNOWN | — | — |
| R04 | M2 species方法 | cfg_tpc268_species_full.py | 42 | species_method_seed42/ | UNKNOWN | — | — |
| R05 | M2 organ baseline | cfg_tpc268_organ_baseline.py | 42 | organ_baseline_seed42/ | UNKNOWN | — | — |
| R06 | M2 organ方法 | cfg_tpc268_organ_full.py | 42 | organ_method_seed42/ | UNKNOWN | — | — |
| R07 | M3 对比监督消融 | cfg_tpc268_contrast.py | 42 | contrast_seed42/ | UNKNOWN | — | — |
| R08 | M3 蕴涵监督消融 | cfg_tpc268_entailment.py | 42 | entailment_seed42/ | UNKNOWN | — | — |
| R09 | M3 几何对照 | cfg_tpc268_euclidean.py | 42 | euclidean_seed42/ | UNKNOWN | — | — |
| R10 | M4 基线复跑 | cfg_tpc268_baseline.py | 43 | full_baseline_seed43/ | UNKNOWN | — | — |
| R11 | M4 方法复跑 | cfg_tpc268_full.py | 43 | full_method_seed43/ | UNKNOWN | — | — |
| R12 | M4 基线复跑 | cfg_tpc268_baseline.py | 44 | full_baseline_seed44/ | UNKNOWN | — | — |
| R13 | M4 方法复跑 | cfg_tpc268_full.py | 44 | full_method_seed44/ | UNKNOWN | — | — |

## 根据结论范围追加

| ID | 执行条件 | 配置/seed | 输出目录 | 状态 | 结果或跳过理由 |
|---|---|---|---|---|---|
| R14 | 保留 Lorentz 优势主张则必需 | cfg_tpc268_euclidean.py / 43 | euclidean_seed43/ | UNKNOWN | — |
| R15 | 保留 Lorentz 优势主张则必需 | cfg_tpc268_euclidean.py / 44 | euclidean_seed44/ | UNKNOWN | — |
| R16 | 保留 organ 下收益主张则必需 | cfg_tpc268_organ_baseline.py / 43 | organ_baseline_seed43/ | UNKNOWN | — |
| R17 | 同上 | cfg_tpc268_organ_full.py / 43 | organ_method_seed43/ | UNKNOWN | — |
| R18 | 同上 | cfg_tpc268_organ_baseline.py / 44 | organ_baseline_seed44/ | UNKNOWN | — |
| R19 | 同上 | cfg_tpc268_organ_full.py / 44 | organ_method_seed44/ | UNKNOWN | — |
| A01 | 附录可选：删除 TT bridge | cfg_tpc268_full.py / 42 / bridge_weight=0 | no_tt_bridge_seed42/ | UNKNOWN | — |

## 每阶段记录模板

复制下列记录并填真实值；不要把模板的破折号当作实验结果。

```text
Run ID / 数据协议版本:
状态:
开始/结束时间（时区）:
代码 commit / 三张排除图 / 坐标策略 / 环境 / 输入指纹:
准确命令:
输出目录 / console / log.txt:
退出码 / 异常信息:
实际训练完成 epochs / best epoch（注明索引）:
最佳 checkpoint 路径 / 训练是否在旧版9df0651启动:
重评 best val: images / MAE / RMSE / R2:
配对 baseline / delta MAE / delta RMSE:
训练几何诊断（pair数、正负包含率、非法域率、饱和率）:
秒/step / 秒/val图 / 峰值显存 / checkpoint大小 / GPU小时:
是否达到下一阶段技术门槛:
协议变更与重跑范围:
最终 test（仅冻结协议后）:
```

## 结果交付

- [ ] M1/M2/M3 验证对照 JSON，所有最终目录均为 best checkpoint 重评。
- [ ] 三 seed 的各自 MAE/RMSE 和配对 delta、mean±sample std，不挑 seed。
- [ ] test 主表/消融表；测试指标不是训练日志里的 `test_mae`。
- [ ] 逐 organ、数量桶、已见/未见 species、taxonomy 是否解析的 n 与计数误差。
- [ ] 改善/退化/预测900/未解析样本的固定规则选图。
- [ ] C1/C2：支持、部分支持、不支持或证据不足，说明结论边界。

## 文档维护记录

- 2026-10-14：把旧计划与 tracker 合并，按照 `0c99a25` 更新三张排除图、有效样本数、坐标审计和 uv 源配置；服务器实际运行状态与指标未知。实现协议变化已同步写入 `implement.md`。后续每次工作同时更新两份文档。
