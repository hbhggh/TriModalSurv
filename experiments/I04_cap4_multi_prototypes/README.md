# I04_cap4_multi_prototypes

现有 D 底座，每个风险箱 L 个原型，K-means 初始化、箱内 EMA、有效槽温度召回。没有新建 C 版配置或实验。

- [代码](model.py) · [配置](config.yaml)
- [知识](knowledge/index.md) · [结果](results/index.md)
- 模块入口：`python -m experiments.I04_cap4_multi_prototypes.train --help`、`python -m experiments.I04_cap4_multi_prototypes.evaluate --help`。从仓库checkout使用，需将仓库与 `src` 放入 `PYTHONPATH`；配置预设可由 `--config config.yaml --preset <名称>` 显式解析，不自动选择科研臂，也不等于启动授权。
- 新入口必须从实验配置或显式 CLI 提供 `bin_mode`；真实结果与checkpoint保持原字节。
- 迁移核验边界见 [实验报告](../../docs/refactor/20260916-080006-full-project/experiments-report.md)。

## 配置预检（不训练）

从完整 checkout 根目录运行以下示例，仅解析配置并构造 CPU 模型：

```sh
PYTHONPATH=src:. python -m experiments.I04_cap4_multi_prototypes.train --config experiments/I04_cap4_multi_prototypes/config.yaml --preset dq0 --dry_run
```

参数优先级为公共默认 → 实验公共参数 → 显式 preset → 显式 CLI。未知字段或未选择 preset 均拒绝；`model.pred_dim` 必须与所选 `model_config` 的实际预测维度一致，不能被静默忽略。`src` 安装包仅提供公共库，实验与脚本运行依赖完整 checkout 及其 `configs/`，不是独立 wheel 的命令行产品。
