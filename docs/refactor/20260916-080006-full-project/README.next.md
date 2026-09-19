# TriModalSurv

三模态生存研究项目。共享实现放 `src/trimodalsurv/`，一个创新点一个实验目录，每批结果独立保存；旧实现与原文保存在 `archive/`。

## 阅读入口

- [项目状态与历史](STATUS.md)
- [项目纪律](AGENTS.md) · [坑台账](docs/engineering/pitfalls.md)
- [项目结构与文件归属](docs/project-structure.md)
- [通用科研初始化模板](docs/templates/experiment-oriented-ml-template.md)
- [本次重构证据](docs/refactor/20260916-080006-full-project/progress.md)

## 实验

| ID | 内容 | 实现边界 |
|---|---|---|
| [I01](experiments/I01_patient_retrieval/README.md) | 患者配对检索 | 原始特征投影前填补，train-only 固定检索库 |
| [I02](experiments/I02_population_prototypes/README.md) | 人群配对原型 | 编码后聚类，每轮更新；仅验证/推理补偿 |
| [I03](experiments/I03_npj_d_dm_e1/README.md) | NPJ-D、Dm、旧 E1 历史对照 | 保留旧结果与口径，不宣称新创新 |
| [I04](experiments/I04_cap4_multi_prototypes/README.md) | 时间箱内多原型 | 本轮整理已有 D 版；C 版科研方案未落地 |

NPJ-A/B 是风险评估口径，见[说明](docs/metrics/NPJ-A&NPJ-B区别.md)。跨实验结果见 [comparisons](experiments/_comparisons/index.md)。外部 [MCAT](baselines/MCAT) 与 [PORPOISE](baselines/PORPOISE) 保持独立仓库。

## 开发与运行边界

在项目 checkout 中设置 `PYTHONPATH=<项目绝对路径>/src:<项目绝对路径>`。公共启动入口为 [train_launcher.py](scripts/train_launcher.py)，各实验入口见实验 README。远端既有部署没有自动更改；历史命令不能直接视为新部署命令。

新实验 ID 由用户确定，从 [六文件骨架](experiments/_template/) 开始；机制确定后添加可编辑图，真正运行时才创建 `results/<run_id>/`。不覆盖旧结果，不把历史未知超参数补写为真实参数。正式实验仍须 Claude 审查与用户授权。

[论文](manuscript/) · [工作流笔记](docs/workflow/) · [研究构想](docs/research-ideas/) · [历史归档](archive/)

未来获准运行时，启动清单须显式指定所属实验 `results/` 内的新输出批次；旧 checkpoint 命名保留，分箱或配置不同不能复用输出目录。`--run_record_root` 管理独占运行记录，`--result_path` 管理原启动器的 checkpoint/预测产物，二者均纳入该实验目录。
