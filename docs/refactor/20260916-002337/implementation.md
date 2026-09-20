# I01 最小迁移实现记录

## 迁移边界

- 固定源：`/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ`，commit `6a04a0bf5c283a57e90207899ddffe3867fd5e0a`。
- `NPJC`、`SurvivalHead`、`consistency_loss` 原样抽取到 `src/trimodalsurv/models/`；未引入旧多模型文件的 transformers/scattermoe 依赖。
- `patient_retrieval_bank.py` 迁到实验 `model.py`，只增加 `[创新 I01-01]` 标记；中心化、共同有效行 cosine、候选限制、配对 payload 与 mean → projector 顺序未改。
- 通用评测工具抽到 `src/trimodalsurv/evaluation/common.py`。`data` 和 `training` 仅声明当前边界；本次未迁移训练，不虚构 engine。
- 逐符号来源、源文件 SHA256、源行号与目标文件在 `migration-map.json`。

## 接口与配置

- 支持 `PYTHONPATH=<repo>/src:<repo>` 导入 `experiments.I01_patient_retrieval.evaluate` 与 `.model`。
- 保留 `read_labels/load_cache/CachedPatients/prepare_batch/build_model/strict_e0_load/forward_numpy/checkpoint_path/preflight_cancer/evaluate_unit` 签名；公开 `dual_risk_from_logits`、`FixedPatientBank`、`SHAPES`、`MODEL_SPEC`。
- `parser()` 只提供显式 CLI 参数；完整合并后参数通过 `resolve_args(argv)` 获取。公共默认 → 实验配置 → 显式 CLI，未传 CLI 不覆盖实验配置。
- 模型锁定 hidden256、pred4、dropout0.1、mlp4、backbone1、heads4、img/text/rna、compensator=None。配置不匹配直接拒绝。
- 默认配置以 JSON 兼容 YAML 表示，无 PyYAML 时仍可读；自定义常规 YAML 需要已存在的 PyYAML。
- `resolved_config(args, model, *, inputs, checkpoints, sources)` 从实际参数与模型层读取结构；历史训练学习率/epoch/batch/optimizer 写“未记录”。
- `--out-dir` 保留指定本次唯一 run 目录的语义，已存在即拒绝。产出 `raw/`、`logs/`、`audit/`、`analysis.md`、`resolved_config.yaml`、三类 manifest，另保留历史兼容 `diagnostics/` 和单位 JSON 根路径。
- `resolved_config.yaml` 为合法 JSON 兼容 YAML；单癌详细记录位于 `audit/resolved_config_<cancer>.json`。
- `summarize(input_dir, output_dir)` 接口保留。CLI `--out-dir` 可省略，此时创建本 run 的 `analysis/` 并写入；不预建空目录。75 单元完整性、配对 hash、原风险方向、严格胜/平/负统计与 artifact 校验保持。
- 默认仅 preflight。正式评测保留完整五癌五 seed 和 review record 门，并额外要求 `--formal-approved`；这个 flag 只记录调用者声明，不能代替真实人工审查和用户批准。本轮没有运行正式评测或训练。

## 本地核验

- 内存 `compile()`：23 个 Python 文件通过，无 `.pyc` 写入。
- AST 对拍：NPJC、SurvivalHead、consistency_loss、grid_parts、masked_modalities、grid_sha256、dual_risk_from_logits、strip_data_parallel_prefix、extract_state_dict、file_sha256、_atomic_json_dump 与固定源逐符号完全一致。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python3 -m unittest experiments.I01_patient_retrieval.tests.test_config -v`：3/3 通过。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python3 -m unittest experiments.I01_patient_retrieval.tests.test_patient_retrieval_summary -v`：27/27 通过。
- NumPy/Torch 运行、真实 preflight 与旧/新预测对拍交由主 Agent 在既有 tako 环境执行。本子任务不声称数值验收通过。

## 目标环境命令（由主 Agent 执行）

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest discover -s experiments/I01_patient_retrieval/tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m experiments.I01_patient_retrieval.evaluate --data-root /home/wuhao/npj_fixed_eval_20260915_HpSkli/assets --cancers BLCA --seeds 123 --stage preflight --out-dir results/I01-preflight-UNIQUE
```

目标环境解释器应由主 Agent 替换为已核实的绝对路径；不安装依赖。`pytest` 若已存在可使用 `python -m pytest experiments/I01_patient_retrieval/tests`。

### Bug Post-Mortem

- **现象**: 初次写公共配置时 `configs/` 尚不存在，shell 中段报错。
- **根因**: 新路径父目录未先建立；后续成功命令造成封装总体 exit 0。
- **修复**: 创建白名单目录并重写配置，3 个配置测试实跑通过。
- **Prevention Rule**: 新文件先创建父目录；批量 shell 写入应 fail-fast，不能只看最后命令退出码。属于既有 V10/V22 类规则，不另加重复坑项。

## 汇总器新 run 布局兼容修复

仅修改 `summarize.py`、`tests/test_patient_retrieval_summary.py` 和本记录；未修改模型、评测或配置核心。

- 对 `source_manifest.json`、`data_manifest.json`、`checkpoint_manifest.json` 显式识别，校验顶层字段、完整五癌、空失败集合以及各自的 hash/checkpoint schema 后才排除。
- 其他未知根 JSON 仍报错；历史无 manifest 的输入保持兼容；75 单元、300 格点、配对 metadata/hash 和 artifact 检查保持。
- 新增新布局测试：根 manifest/YAML/analysis + `raw/` 与 `audit/` 的 artifact 路径可完成全量汇总。
- 新增畸形 manifest 测试：对象类型、缺字段、有失败、癌种缺失、错误 commit 均在产出前拒绝。
- RED：新增新布局测试在修复前实际报 `unknown unit filename: checkpoint_manifest.json`。
- GREEN：下列整套汇总测试本地 29/29 通过。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python3 -m unittest experiments.I01_patient_retrieval.tests.test_patient_retrieval_summary -v
```

### Bug Post-Mortem

- **现象**: 新 formal run 根目录含三类 manifest，旧汇总器会报 unknown unit filename，合法新 run 无法汇总。
- **根因**: 新入口添加根 JSON，但消费端仍将全部根 JSON 当作单元；旧汇总测试仅覆盖旧目录布局。
- **修复**: 为三个精确名称增加 schema 验证分支，验证通过后跳过，未知 JSON 和原单元完整性检查保持。
- **Prevention Rule**: 新增产物名称或位置时，必须用生产者完整 run 布局验证下游读取器，不能只测试单个导出函数。旧坑台账在本轮受字节保护，不修改。
