# NPJ GPU 合同落地结果

## 结论

CPU 范围 T5 验收通过：最终完整回归 12/12、exit 0；shell 语法、真实 CLI help、内存语法检查、diff whitespace 检查均通过。按派单禁止项，未启动 GPU 训练、未执行真实 120 秒 GPU 门禁、未 SSH、未下载、未 commit/push。真实 GPU batch probe 与正式发车仍须由 Claude 在获用户授权后于 landau 互审并执行。

## ① 改动文件清单

生产文件：

- `NPJ/config/gpu_train.yaml`（新建）：GPU 合同默认配置。
- `NPJ/main_survival.py`：配置解析与优先级、正式合同校验、真实 dataset batch probe、DataLoader I/O 参数、non-blocking 搬运、epoch 末同步、梯度累积。
- `NPJ/model/fusion_model.py`：仅修改 `MainModalityMoE.forward()` 的 surv_heads 分派；同癌种 batch 单次 head，混合癌种保留旧循环。未改 compensator/CAP-Recall/bank 语义。
- `NPJ/scripts/gpu_util_gate.py`（新建）：`nvidia-smi` 周期采样、JSON 汇总及 0/2/3 退出码。
- `NPJ/scripts/launch_formal.sh`（新建、可执行）：绝对 log、`FORMAL_RUN=1`、`setsid`、GPU util 门禁、豁免及进程组终止。

协作与测试文件：

- `collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py`（新建）：T5 CPU 行为测试。
- `collab/20260902-NPJ-GPU合同/scratch/sitecustomize.py`（新建）：仅在测试进程边界替代本机缺失的非业务顶层依赖，使真实 CLI help 可导入；不进入生产路径。
- `collab/20260902-NPJ-GPU合同/notes.md`（append-only）：预检、RED/GREEN、取舍、问题与修正。
- `collab/20260902-NPJ-GPU合同/result.md`（本文件）。

## ② plan.md 验收标准逐条达成情况

### T1 `gpu_train.yaml`：PASS

- 13 个指定键和值全部落地；`batch_size: null`，不默认回退到 1。

### T2 `main_survival.py`：PASS（CPU 可验部分全部实测）

1. PASS：新增 `--gpu_config`；`--batch_size`/`--num_workers` 默认 `None`；优先级为显式 CLI > YAML > probe；resolved 配置打印 `batch_size_source=cli/yaml/probe`。CPU 且两层 batch 均为空时明确 `RuntimeError` 退出。
2. PASS（代码审查；依禁令未上 GPU 实跑）：用真实 train dataset 重复头部样本构造 32/64/128/256，每档 2 个 forward+backward；CUDA OOM 取前一档，每档清 cache；32 即 OOM 时打印样本 shape 并失败；成功打印 `BATCH_PROBE_RESULT` 与 `PEAK_MEM`。
3. PASS：`FORMAL_RUN=1`、batch=1 且无 `BATCH_SIZE_BLOCKED_REASON` 时 exit 3；有原因或非正式运行不拦截。
4. PASS：train/valid/test 三处 DataLoader 共用 resolved I/O 配置；workers=0 时不传 persistent/prefetch。
5. PASS：label 与所有输入张量均使用配置驱动 `non_blocking`。
6. PASS：train/eval/prediction 热循环内不再 `.item()`/`.cpu()`；loss/hazard/time/censor/index 均 detach 后留在 device，epoch 末集中搬到 CPU。
7. PASS：accum=1 的三轮 loss 序列与 HEAD 旧函数逐位 `==`；accum>1 按 loss/accum、窗口 step、末窗 step，3 batch/accum=2 实测 optimizer step 2 次。
8. PASS：显式 batch CLI 覆盖 YAML、不触发 probe；真实 `main_survival.py --help` exit 0；显式 `--batch_size 2 --epochs 1` CPU 合成训练循环通过。

### T3 surv_heads 快速路径：PASS

- 单癌种 batch：head 调用次数 1；相对旧逐样本函数 hazard 最大差 `2.9802322387695312e-08`，小于 `atol=1e-6`。
- 混合癌种 batch：回退逐样本循环，BLCA/LUAD 各调用 2 次；hazard 最大差 0。
- compensator 相关逻辑未改语义。

### T4 发车门禁：PASS（mock `nvidia-smi` CPU 验收）

- log 非绝对路径 exit 64。
- YAML warmup/min 由 Python 读取，launcher 以显式 `--warmup`/`--min` 调 gate。
- `FORMAL_RUN=1`、`setsid`、PGID、stdout/stderr log、gate JSON 追加、通过后 wait/透传退出码均已实现。
- 四态实测退出码：低 util 拒绝 2；达标放行 0；低 util + 非空原因豁免 0；豁免但空原因拒绝 2。
- `nvidia-smi` 不存在实测 exit 3。

### T5 CPU 验收：PASS

- 最终完整回归 12/12、exit 0。
- `bash -n` exit 0。
- 真实 CLI help exit 0（仅测试进程依赖替代）。
- CPU 空 batch 配置真实入口明确拒绝，exit 1 为预期合同结果。
- 所有 Python 文件用内存 `compile()`；未用裸 `py_compile`。

## ③ 测试命令与真实原始输出

### T5 完整行为回归

命令（cwd=`/Users/wuhao/Desktop/TriModalSurv`）：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py
```

退出码：`0`

原始输出：

```text
test_accum_one_three_epoch_losses_are_bitwise_equal_to_head (__main__.ConfigAndLoopTests) ... ok
test_accumulation_steps_on_full_and_partial_windows (__main__.ConfigAndLoopTests) ... ok
test_cli_overrides_yaml_and_cpu_null_is_rejected (__main__.ConfigAndLoopTests) ... ok
test_formal_batch_one_requires_reason_and_workers_zero_omits_worker_only_keys (__main__.ConfigAndLoopTests) ... GPU_CONTRACT_VIOLATION: FORMAL_RUN batch_size=1 requires non-empty BATCH_SIZE_BLOCKED_REASON
ok
test_gpu_yaml_has_contract_defaults (__main__.ConfigAndLoopTests) ... ok
test_help_and_explicit_batch_two_cpu_smoke (__main__.ConfigAndLoopTests) ... ok
test_gate_four_launch_states (__main__.LaunchGateTests) ... ok
test_gate_missing_nvidia_smi_is_exit_three (__main__.LaunchGateTests) ... ok
test_launch_rejects_relative_log_path_with_exit_64 (__main__.LaunchGateTests) ... ok
test_launch_shell_syntax (__main__.LaunchGateTests) ... ok
test_mixed_cancer_falls_back_and_is_allclose (__main__.SurvivalHeadFastPathTests) ... ok
test_single_cancer_is_fast_and_allclose_to_legacy (__main__.SurvivalHeadFastPathTests) ... ok

----------------------------------------------------------------------
Ran 12 tests in 14.058s

OK
HEAD_LOSSES=[0.14330822850267091, 0.1425183154642582, 0.14173518121242523]
NEW_LOSSES=[0.14330822850267091, 0.1425183154642582, 0.14173518121242523]
BITWISE_EQUAL=True
ACCUM_STEPS=2 OPTIMIZER_STEPS=2
CPU_NULL_BATCH_REJECTED=1
CPU_SMOKE batch_size=2 epochs=1 loss=0.08559350296854973
GATE_CODES low=2 high=0 waived=0 empty_reason=2
SURV_HEAD_MIXED hazard_max_diff=0.0 blca_calls=2 luad_calls=2
SURV_HEAD_SINGLE hazard_max_diff=2.9802322387695312e-08 calls=1
```

### launcher shell 语法

命令（cwd=`/Users/wuhao/Desktop/TriModalSurv/NPJ`）：

```bash
bash -n scripts/launch_formal.sh
```

退出码：`0`

原始输出：

```text
```

### 真实 `main_survival.py --help`

本机 `protomasksurv-exp1` 缺 sksurv/transformers/accelerate/torchmetrics/easydict，按台账 E8/E10 仅在测试进程通过白名单 scratch shim 替代无关导入。

命令（cwd=`/Users/wuhao/Desktop/TriModalSurv/NPJ`）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/wuhao/Desktop/TriModalSurv/collab/20260902-NPJ-GPU合同/scratch /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python main_survival.py --help
```

退出码：`0`

原始输出：

```text
usage: main_survival.py [-h] [--seed SEED] [--epochs EPOCHS]
                        [--batch_size BATCH_SIZE] [--num_workers NUM_WORKERS]
                        [--gpu_config GPU_CONFIG] [--lr LR]
                        [--cpt_name CPT_NAME] [--result_path RESULT_PATH]
                        [--report_label_path REPORT_LABEL_PATH]
                        [--model_config MODEL_CONFIG]
                        [--cancer_type CANCER_TYPE] [--train TRAIN]
                        [--task_type TASK_TYPE] [--network_type NETWORK_TYPE]
                        [--hidden_size HIDDEN_SIZE]
                        [--cancer_types CANCER_TYPES]
                        [--n_image_tokens N_IMAGE_TOKENS]
                        [--pretrain_path PRETRAIN_PATH] [--finetune_head_only]
                        [--simulate_missing_modality SIMULATE_MISSING_MODALITY]
                        [--compensator {none,capr,bank}]
                        [--modality_dropout MODALITY_DROPOUT]
                        [--consistency_lambda CONSISTENCY_LAMBDA]

options:
  -h, --help            show this help message and exit
  --seed SEED
  --epochs EPOCHS
  --batch_size BATCH_SIZE
  --num_workers NUM_WORKERS
  --gpu_config GPU_CONFIG
  --lr LR
  --cpt_name CPT_NAME
  --result_path RESULT_PATH
  --report_label_path REPORT_LABEL_PATH
  --model_config MODEL_CONFIG
  --cancer_type CANCER_TYPE
  --train TRAIN
  --task_type TASK_TYPE
  --network_type NETWORK_TYPE
  --hidden_size HIDDEN_SIZE
  --cancer_types CANCER_TYPES
  --n_image_tokens N_IMAGE_TOKENS
  --pretrain_path PRETRAIN_PATH
                        Path to pre-trained model checkpoint
  --finetune_head_only  Only finetune the head; freeze the rest of the model
  --simulate_missing_modality SIMULATE_MISSING_MODALITY
  --compensator {none,capr,bank}
  --modality_dropout MODALITY_DROPOUT
  --consistency_lambda CONSISTENCY_LAMBDA
```

### CPU + `batch_size: null` 的真实入口拒绝

命令（cwd=`/Users/wuhao/Desktop/TriModalSurv/NPJ`）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/wuhao/Desktop/TriModalSurv/collab/20260902-NPJ-GPU合同/scratch /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python main_survival.py --epochs 1
```

退出码：`1`（预期拒绝）

原始输出：

```text
Traceback (most recent call last):
  File "/Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py", line 805, in <module>
    main(args)
  File "/Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py", line 625, in main
    gpu_config = resolve_gpu_config(args)
  File "/Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py", line 110, in resolve_gpu_config
    raise RuntimeError(
RuntimeError: batch_size is unset and CUDA is unavailable; GPU batch probing cannot run
Training Arguments: Namespace(seed=123, epochs=1, batch_size=None, num_workers=None, gpu_config='config/gpu_train.yaml', lr=0.0005, cpt_name='tcga', result_path='out', report_label_path='data/TCGA_9523sample_label_Censorship.csv', model_config='model/config/multimodal_early_fusion.yml', cancer_type='None', train=True, task_type='surv', network_type='DEMainModalityMILMoE', hidden_size=256, cancer_types='None', n_image_tokens=128, pretrain_path='', finetune_head_only=False, simulate_missing_modality='', compensator='none', modality_dropout=0.0, consistency_lambda=0.1)
```

### 内存语法检查（S1）

命令（cwd=`/Users/wuhao/Desktop/TriModalSurv`）：

```bash
python - <<'PY'
from pathlib import Path
paths = [
    Path('NPJ/main_survival.py'),
    Path('NPJ/model/fusion_model.py'),
    Path('NPJ/scripts/gpu_util_gate.py'),
    Path('collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py'),
    Path('collab/20260902-NPJ-GPU合同/scratch/sitecustomize.py'),
]
for path in paths:
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    print(f'COMPILE_OK {path}')
PY
```

退出码：`0`

原始输出：

```text
COMPILE_OK NPJ/main_survival.py
COMPILE_OK NPJ/model/fusion_model.py
COMPILE_OK NPJ/scripts/gpu_util_gate.py
COMPILE_OK collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py
COMPILE_OK collab/20260902-NPJ-GPU合同/scratch/sitecustomize.py
```

### whitespace 与源码旁缓存审计

命令（cwd=`/Users/wuhao/Desktop/TriModalSurv`）：

```bash
git -C NPJ status --short
test ! -e NPJ/__pycache__/main_survival.cpython-310.pyc && echo WHITELIST_CACHE_CHECK=PASS
git -C NPJ diff --check -- main_survival.py model/fusion_model.py config/gpu_train.yaml scripts/launch_formal.sh scripts/gpu_util_gate.py && echo DIFF_CHECK=PASS
```

退出码：`0`

原始输出：

```text
 M loc_utils_3yr/tcga_dataset.py
 M main_survival.py
 M model/fusion_model.py
?? config/gpu_train.yaml
?? loc_utils/__pycache__/model_util.cpython-310.pyc
?? loc_utils_3yr/__pycache__/tcga_dataset.cpython-310.pyc
?? model/__pycache__/compensator.cpython-310.pyc
?? model/__pycache__/fusion_model.cpython-310.pyc
?? model/compensator.py
?? scattermoe/__pycache__/
?? scattermoe/kernels/__pycache__/
?? scripts/
WHITELIST_CACHE_CHECK=PASS
DIFF_CHECK=PASS
```

说明：上述 `loc_utils_3yr/tcga_dataset.py`、`model/compensator.py` 与 `loc_utils/model/scattermoe` 缓存均在本单开始前已存在；本单未修改、未清理。`scripts/` 状态同时包含原有未跟踪脚本和本单两个新脚本，故 Git 以目录汇总显示。

## ④ 遇到的问题

1. 本机缺少部分 NPJ 运行依赖。处理：不安装、不改生产导入；仅在 `scratch/sitecustomize.py` 的测试进程边界提供最小替代，真实 help 和目标函数测试均抵达业务路径。
2. 首次 RED 夹具的 `tqdm` 替身缺 `__spec__`，Torch Dynamo 插件发现报错。处理：给所有替身设置合法 `ModuleSpec`，重新取得有效业务 RED。详见 `notes.md` Post-Mortem。
3. 首次真实 help 导入生成白名单外 `NPJ/__pycache__/main_survival.cpython-310.pyc`。处理：单文件可恢复移动到 `/private/tmp/trimodalsurv-main_survival.cpython-310.pyc-20260902-1148`，以 `PYTHONDONTWRITEBYTECODE=1` 重跑并确认缓存不存在。详见 `notes.md` Post-Mortem。
4. 本机未发现 `ruff`/`shellcheck`。处理：使用完整行为测试、`bash -n`、内存 compile 和 `git diff --check`；不声称执行了不存在的 lint 工具。

## ⑤ 未尽事项与边界

- 未运行任何 GPU 训练、正式 120 秒 warmup 或真实 `nvidia-smi` 门禁；这是派单明确禁止项，不是遗漏。GPU probe 的 OOM 档位、真实 util 中位数和显存峰值目前没有实测数据。
- 未 SSH/同步 landau，未触碰 `baselines/`、`adapters/`、`tmp_sur_cache/`、已有结果目录或 compensator 逻辑语义。
- 未执行 git commit/push/merge。按项目互审纪律，本 patch 与本结果必须回到 Claude review；CPU 通过不等于获准正式发车。

## ⑥ 互审打回增补：短任务提前完成处理

### 增补改动

- `NPJ/scripts/gpu_util_gate.py`
  - 新增 `--watch-pid <pid>`。
  - 每轮采样前以 `os.kill(pid, 0)` 检查训练进程。
  - PID 已消失时停止采样；JSON 增加 `early_exit: true`，exit 4。
  - 正常采满窗口时 JSON 同样带 `early_exit: false`，原 0/2/3 语义不变。
- `NPJ/scripts/launch_formal.sh`
  - 调 gate 时传 `--watch-pid "$training_pid"`。
  - gate exit 4 时执行 `wait`：训练 exit 0 则记录 `FORMAL_GATE_EARLY_COMPLETE` 并 exit 0；训练非零则记录 `FORMAL_TRAINING_FAILED EXIT_CODE=<n>` 并透传。
- `collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py`
  - 新增提前成功与提前失败两个端到端用例，总数由 12 增至 14。

### RED 原始证据

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py LaunchGateTests.test_training_early_success_is_allowed LaunchGateTests.test_training_early_failure_exit_code_is_preserved
```

旧实现退出码：`1`

原始输出：

```text
test_training_early_success_is_allowed (__main__.LaunchGateTests) ... FAIL
test_training_early_failure_exit_code_is_preserved (__main__.LaunchGateTests) ... FAIL

======================================================================
FAIL: test_training_early_success_is_allowed (__main__.LaunchGateTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/wuhao/Desktop/TriModalSurv/collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py", line 590, in test_training_early_success_is_allowed
    self.assertEqual(code, 0, log)
AssertionError: 2 != 0 : FORMAL_LAUNCH_PID=17413 PGID=17413 GPU=0
{"util_median":10.0,"mem_peak_mib":2048.0,"samples":1,"pass":false}
FORMAL_GATE_REJECTED: utilization below contract minimum


======================================================================
FAIL: test_training_early_failure_exit_code_is_preserved (__main__.LaunchGateTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/wuhao/Desktop/TriModalSurv/collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py", line 603, in test_training_early_failure_exit_code_is_preserved
    self.assertEqual(code, 7, log)
AssertionError: 2 != 7 : FORMAL_LAUNCH_PID=17430 PGID=17430 GPU=0
{"util_median":10.0,"mem_peak_mib":2048.0,"samples":1,"pass":false}
FORMAL_GATE_REJECTED: utilization below contract minimum


----------------------------------------------------------------------
Ran 2 tests in 4.058s

FAILED (failures=2)
EARLY_SUCCESS_CODE=2
EARLY_FAILURE_CODE=2
```

### 最终 14/14 原始验收

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py
```

退出码：`0`

原始输出：

```text
test_accum_one_three_epoch_losses_are_bitwise_equal_to_head (__main__.ConfigAndLoopTests) ... ok
test_accumulation_steps_on_full_and_partial_windows (__main__.ConfigAndLoopTests) ... ok
test_cli_overrides_yaml_and_cpu_null_is_rejected (__main__.ConfigAndLoopTests) ... ok
test_formal_batch_one_requires_reason_and_workers_zero_omits_worker_only_keys (__main__.ConfigAndLoopTests) ... GPU_CONTRACT_VIOLATION: FORMAL_RUN batch_size=1 requires non-empty BATCH_SIZE_BLOCKED_REASON
ok
test_gpu_yaml_has_contract_defaults (__main__.ConfigAndLoopTests) ... ok
test_help_and_explicit_batch_two_cpu_smoke (__main__.ConfigAndLoopTests) ... ok
test_gate_four_launch_states (__main__.LaunchGateTests) ... ok
test_gate_missing_nvidia_smi_is_exit_three (__main__.LaunchGateTests) ... ok
test_launch_rejects_relative_log_path_with_exit_64 (__main__.LaunchGateTests) ... ok
test_launch_shell_syntax (__main__.LaunchGateTests) ... ok
test_training_early_failure_exit_code_is_preserved (__main__.LaunchGateTests) ... ok
test_training_early_success_is_allowed (__main__.LaunchGateTests) ... ok
test_mixed_cancer_falls_back_and_is_allclose (__main__.SurvivalHeadFastPathTests) ... ok
test_single_cancer_is_fast_and_allclose_to_legacy (__main__.SurvivalHeadFastPathTests) ... ok

----------------------------------------------------------------------
Ran 14 tests in 74.168s

OK
HEAD_LOSSES=[0.14330822850267091, 0.1425183154642582, 0.14173518121242523]
NEW_LOSSES=[0.14330822850267091, 0.1425183154642582, 0.14173518121242523]
BITWISE_EQUAL=True
ACCUM_STEPS=2 OPTIMIZER_STEPS=2
CPU_NULL_BATCH_REJECTED=1
CPU_SMOKE batch_size=2 epochs=1 loss=0.08559350296854973
GATE_CODES low=2 high=0 waived=0 empty_reason=2
EARLY_FAILURE_CODE=7
EARLY_FAILURE_GATE={"util_median":null,"mem_peak_mib":null,"samples":0,"pass":false,"early_exit":true}
EARLY_SUCCESS_CODE=0
EARLY_SUCCESS_GATE={"util_median":null,"mem_peak_mib":null,"samples":0,"pass":false,"early_exit":true}
SURV_HEAD_MIXED hazard_max_diff=0.0 blca_calls=2 luad_calls=2
SURV_HEAD_SINGLE hazard_max_diff=2.9802322387695312e-08 calls=1
```

### 补丁静态验收

命令：

```bash
bash -n NPJ/scripts/launch_formal.sh
python - <<'PY'
from pathlib import Path
for path in [
    Path('NPJ/scripts/gpu_util_gate.py'),
    Path('collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py'),
]:
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    print(f'COMPILE_OK {path}')
PY
git -C NPJ diff --check -- scripts/gpu_util_gate.py scripts/launch_formal.sh
test ! -e NPJ/__pycache__/main_survival.cpython-310.pyc
find NPJ -type f -newermt '2026-09-02 12:00:00' -print | sort
```

退出码：`0`

原始输出：

```text
COMPILE_OK NPJ/scripts/gpu_util_gate.py
COMPILE_OK collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py
NPJ/scripts/gpu_util_gate.py
NPJ/scripts/launch_formal.sh
```

### 增补边界

- 本轮未修改 `main_survival.py`、`fusion_model.py`、配置、compensator、`baselines/` 或其他白名单外文件。
- 未 SSH、未启动 GPU 训练、未执行真实门禁、未 commit/push。
- `collab/pitfalls.md` 位于本派单白名单之外，因此本轮只把新 Post-Mortem 追加到 `notes.md`；台账回流交由 Claude 互审阶段处理。
