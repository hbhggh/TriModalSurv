# 实验身份：exp/mcat-1536
方法 MCAT（coattn，Chen et al. ICCV 2021）| 特征 UNI2-h 1536（--path_input_dim 1536，结果目录后缀 pid1536）| 基因组 官方 signatures 六组 | 标签 labels_424 统一结局（adapted trainval CSV 顶名）| split custom424r2（train=train/val=valid/test 冻结评估）| 超参 官方默认 20 epochs | seeds 123/132/213/231/321 | 模型口径 末轮 s_0_checkpoint.pt | patch mcat_patch.diff（torch2 兼容+5点修复+pid身份）
