# experiments：实验与创新点

一个创新点一个目录，集中管理模型实现、参数、知识解释和结果。相同机制的不同 seed、超参数或重复运行，使用不同结果批次，不复制一套公共模型。

## 内容索引

| 路径 | 用途 |
|---|---|
| [_template/](_template/) | 新实验的六文件空壳；本身不作为真实实验运行 |
| [I01_patient_retrieval/](I01_patient_retrieval/README.md) | 患者配对检索；在原始特征投影前填补 |
| [I02_population_prototypes/](I02_population_prototypes/README.md) | 人群配对原型；编码后的原型补偿 |
| [I03_npj_d_dm_e1/](I03_npj_d_dm_e1/README.md) | NPJ-D、Dm 与旧 E1 的历史对照 |
| [I04_cap4_multi_prototypes/](I04_cap4_multi_prototypes/README.md) | 时间箱内多原型；已有 D 版实现 |
| [_comparisons/](_comparisons/index.md) | 跨实验结果导航与比较边界 |
| [mcat-1536/](mcat-1536/manifest.md) | MCAT 对照的实验清单 |
| [npj-uni2/](npj-uni2/manifest.md) | NPJ UNI2 对照的实验清单 |
| [porpoise-mutsig-1536/](porpoise-mutsig-1536/manifest.md) | PORPOISE 对照的实验清单 |

## 新实验怎么放

确认 ID 后，以 `_template/` 建立 `README.md`、`model.py`、`config.yaml`、`knowledge/index.md`、`knowledge/method.md`、`results/index.md`。核心创新算子在 `model.py` 标注，公共实现复用 `src/trimodalsurv/`。

机制确定后补可编辑机制图；真正运行时才创建 `results/<run_id>/`，保存生效参数、来源清单、原始结果与分析 MD。已有结果不覆盖，历史对照不自动等同于同协议消融。

[返回项目首页](../README.md) · [项目状态](../STATUS.md)
