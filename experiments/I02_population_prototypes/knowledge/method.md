# I02_population_prototypes 机制与来源

编码后 WSI 聚类，配对 RNA/Text 簇均值，仅验证/推理补偿。训练后每轮全 train 建库，严格早停并重载最佳模型和库。

`model.py` 中的标记定位实验差异；共享编码、融合、数据和损失在 `src/trimodalsurv/`。

来源为684e/code/NPJ/model/population_prototypes.py和population_runtime.py；银行buffer键保留compensator.wsi/rna/text/counts/ready，无额外module外包装。正式历史K=8、hidden=256；构造器实际dropout=0.1、mlp_ratio=4，与模型YAML宣称值必须区分。
