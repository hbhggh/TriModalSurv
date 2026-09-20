# I02_population_prototypes

编码后 WSI 聚类，配对 RNA/Text 簇均值，仅验证/推理补偿。训练后每轮全 train 建库，严格早停并重载最佳模型和库。

- [代码](model.py) · [配置](config.yaml)
- [知识](knowledge/index.md) · [结果](results/index.md)
- 模块入口：`python -m experiments.I02_population_prototypes.train --help`、`python -m experiments.I02_population_prototypes.evaluate --help`。从仓库checkout使用，需将仓库与 `src` 放入 `PYTHONPATH`；配置中的预设是来源说明，不等于启动授权。
- 新入口必须显式提供 `--bin_mode`；真实结果与checkpoint保持原字节。
- 迁移核验边界见 [实验报告](../../docs/refactor/20260916-080006-full-project/experiments-report.md)。

## 参数与输出契约

`config.yaml` 的 `runtime` 是唯一生效参数区；未知的顶层训练/模型参数会被拒绝。不能配置的构造常量以 `model.py` 和实际 `resolved_config.yaml` 为准，不再维护第二份看似可编辑的超参数表。

未来获准运行时，显式把 `--result_path` 指向本实验新批次的 checkpoint 输出区域，把 `--run_record_root` 指向本实验 `results/`。历史 checkpoint 命名合同保留，不同分箱/配置须选不同输出目录；已有产物会被拒绝覆盖。这里不授权启动训练。
