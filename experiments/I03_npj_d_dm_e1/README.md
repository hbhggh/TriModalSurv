# I03_npj_d_dm_e1

D 为去 gate 的等权融合；Dm 复用 D checkpoint 并在输入做训练均值填补；旧 E1 为 NPJC+CAPRecall。它们是历史对照，不是新的创新。

- [代码](model.py) · [配置](config.yaml)
- [知识](knowledge/index.md) · [结果](results/index.md)
- 模块入口：`python -m experiments.I03_npj_d_dm_e1.train --help`、`python -m experiments.I03_npj_d_dm_e1.evaluate --help`。从仓库checkout使用，需将仓库与 `src` 放入 `PYTHONPATH`；配置预设可由 `--config config.yaml --preset <名称>` 显式解析，不自动选择科研臂，也不等于启动授权。
- 新入口必须从实验配置或显式 CLI 提供 `bin_mode`；真实结果与checkpoint保持原字节。
- 迁移核验边界见 [实验报告](../../docs/refactor/20260916-080006-full-project/experiments-report.md)。

## 配置预检（不训练）

从完整 checkout 根目录运行以下示例，仅解析配置并构造 CPU 模型：

```sh
PYTHONPATH=src:. python -m experiments.I03_npj_d_dm_e1.train --config experiments/I03_npj_d_dm_e1/config.yaml --preset D --dry_run
```

参数优先级为公共默认 → 实验公共参数 → 显式 preset → 显式 CLI。未知字段或未选择 preset 均拒绝；`model.pred_dim` 必须与所选 `model_config` 的实际预测维度一致，不能被静默忽略。`src` 安装包仅提供公共库，实验与脚本运行依赖完整 checkout 及其 `configs/`，不是独立 wheel 的命令行产品。

`D`/`Dm` 的训练模型相同；`evaluation.Dm.arm=m1` 只描述评测入口应选择的均值填补臂，不会由训练入口执行填补。历史 Dm 复用 D checkpoint；上述预检不授权另训 Dm。`E1` 保留 NPJC+CAPRecall、modality_dropout=0.15、consistency_lambda=0.1。
