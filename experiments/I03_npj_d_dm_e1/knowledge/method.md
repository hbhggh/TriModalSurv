# I03_npj_d_dm_e1 机制与来源

D 为去 gate 的等权融合；Dm 复用 D checkpoint 并在输入做训练均值填补；旧 E1 为 NPJC+CAPRecall。它们是历史对照，不是新的创新。

`model.py` 中的标记定位实验差异；共享编码、融合、数据和损失在 `src/trimodalsurv/`。

历史git f2e2358 的 code/NPJ/model/compensator.py、fusion_model.py已读取并记录hash。公共CAPRecall/MissingBank不复制；D/Dm与旧E1并非I01患者检索。
