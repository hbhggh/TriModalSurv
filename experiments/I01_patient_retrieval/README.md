# I01：固定患者库配对检索

[确定] 本目录整理 `patient-fixed-padmask-v2` 的固定患者检索机制与历史证据。试点范围仅为固定回归验证；本目录不自动训练，回归是否通过以主任务的实际报告为准。

**机制**：以冻结 train 患者的 WSI 缓存建立检索键；按共同有效行去中心余弦选 Top-1 donor，缺失 RNA/Text 由同一 donor 的投影前原始 feature 提供。在 `mean → projector` 之前注入，后续调用 `compensator=None` 的 NPJC，仅推理、不学习库参数。

**边界**：这是本项目的患者等权去中心与 padding-aware 适配，不能称作者完全同构复现；不是簇级跨患者原型库。旧笔记中的后续训练提议不属于本次试点。

- [model.py](model.py)：查找文字标记 `# [创新 I01-01]`，定位新目录中的实际创新实现。
- [config.yaml](config.yaml)：本实验配置，具体生效值须由真实构造对象回读。
- [机制与图](knowledge/method.md) · [知识索引](knowledge/index.md)
- [结果索引](results/index.md)：历史正式档案的校验副本与本次工程回归分开保存。
- [项目状态追加段](../../STATUS.md#refactor-20260916-002337)
