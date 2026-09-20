# I04_cap4_multi_prototypes 机制与来源

现有 D 底座，每个风险箱 L 个原型，K-means 初始化、箱内 EMA、有效槽温度召回。没有新建 C 版配置或实验。

`model.py` 中的标记定位实验差异；共享编码、融合、数据和损失在 `src/trimodalsurv/`。

来源为根NPJ T0 CAPRecallMulti v3，保留logit_scale和slot buffers。底层既有NPJC可构造接口及旧测试保留，但不代表C版实验已实现、验证或启动；新预设与实验对拍限D版。
