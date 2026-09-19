"""I03 历史对照：D、Dm 与旧 E1；不是新科研创新。"""
from trimodalsurv.models.fusion import MainModalityMoE, MeanFusion, GatedFusion
from trimodalsurv.models.npjc import NPJC
from trimodalsurv.models.compensator import CAPRecall, MissingBank

# [历史差异 I03] D 删除 gate；Dm 在数据入口做均值填补；旧 E1 用 C+CAPRecall。
def build_model(arm, *, device, modalities, hidden_size=256, pred_dim=4,
                dropout_rate=0.1, mlp_ratio=4, n_backbone=1, n_head=4,
                cancer_types=None):
    if arm in ('D', 'Dm'):
        return MainModalityMoE(device, modalities, hidden_size,
            dropout_rate=dropout_rate, pred_dim=pred_dim, mlp_ratio=mlp_ratio,
            n_backbone=n_backbone, n_head=n_head, cancer_types=cancer_types,
            compensator=None, fusion_type='mean')
    if arm == 'E1':
        bank = CAPRecall(tuple(m for m in ('text', 'rna') if m in modalities), hidden_size)
        return NPJC(device, modalities, hidden_size, dropout_rate, pred_dim,
                    mlp_ratio, n_backbone, n_head, cancer_types=cancer_types,
                    compensator=bank)
    raise ValueError(f'Unknown historical arm: {arm}')
