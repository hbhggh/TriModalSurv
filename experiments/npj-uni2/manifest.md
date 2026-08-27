# 实验身份：exp/npj-uni2
方法 NPJ 骨架 MainModalityMoE（Song et al. BiB 2026，零修改 E0）| WSI UNI2-h 1536 | text 作者公开嵌入（parsed [200,768]）| RNA BLCA=作者公开、4新癌=自制 BulkRNABert（数据变体如实标注）| split 4:2:4 CSV 原生 | 超参 官方 shell 默认（hidden 256 生效）| seeds 同左 | 模型口径 best-valid ckpt | 桥接 BLCA 作者2048特征版复用阶段0结果不重跑 | 评估 A/B 双口径
