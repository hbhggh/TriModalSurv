"""规则 5：只在 Transformer 末端 pooling 降低填值 token 权重。"""
from __future__ import annotations

import numpy as np


MODALITY_ORDER = ("img", "text", "rna")


def build_pool_weights(original_valid, fusion_valid, imputed, *, w: float,
                       downweight: bool) -> np.ndarray:
    """invalid=0、本人真实=1、规则 5 填值=w；不返回或修改 bool mask。"""
    weight = float(w)
    if not np.isfinite(weight) or weight <= 0.0 or weight > 1.0:
        raise ValueError("w must be finite and in (0, 1]")
    batch_size = len(next(iter(fusion_valid.values())))
    result = np.zeros((batch_size, len(MODALITY_ORDER)), dtype=np.float64)
    for column, mm in enumerate(MODALITY_ORDER):
        fused = np.asarray(fusion_valid[mm])
        original = np.asarray(original_valid[mm])
        filled = np.asarray(imputed[mm])
        if any(array.shape != (batch_size,) for array in (fused, original, filled)):
            raise ValueError("pool-weight mask shape mismatch")
        fused, original, filled = fused.astype(bool), original.astype(bool), filled.astype(bool)
        if np.any(original & ~fused) or np.any(filled & ~fused) or np.any(filled & original):
            raise ValueError("inconsistent original/fusion/imputed masks")
        result[:, column] = np.where(
            ~fused, 0.0, np.where(filled & downweight, weight, 1.0)
        )
    return result


def weighted_forward(model, inputs, cancer, device, pool_weights, *, non_blocking=False):
    """复用原 NPJC projector/backbone/head，只替换最终 pooling 分子和分母。"""
    import torch

    if model.training:
        raise ValueError("model must be in eval mode")
    if getattr(model, "compensator", None) is not None:
        raise ValueError("weighted inference requires compensator=None")
    if tuple(model.modalities) != MODALITY_ORDER:
        raise ValueError(f"unexpected modality order: {model.modalities}")
    tensors = {
        key: torch.as_tensor(value).to(
            device=device, dtype=torch.float32, non_blocking=bool(non_blocking)
        )
        for key, value in inputs.items()
    }
    tokens, valids = model.encode_patient_modalities(tensors)
    seq = torch.stack([tokens[mm] for mm in model.modalities], dim=1) + model.modality_embed
    valid = torch.stack([valids[mm] for mm in model.modalities], dim=1)
    h = model.backbone(seq, src_key_padding_mask=~valid)
    weights = torch.as_tensor(pool_weights, device=h.device, dtype=h.dtype)
    if weights.shape != valid.shape or not torch.isfinite(weights).all() or torch.any(weights < 0):
        raise ValueError("invalid pool_weights")
    weights = weights * valid.to(dtype=h.dtype)
    pooled = (h * weights.unsqueeze(-1)).sum(dim=1) / weights.sum(
        dim=1, keepdim=True
    ).clamp_min(1.0)
    cancer_types = [cancer] * pooled.shape[0] if isinstance(cancer, str) else list(cancer)
    if len(cancer_types) != pooled.shape[0]:
        raise ValueError("cancer batch size mismatch")
    if all(ct == cancer_types[0] for ct in cancer_types):
        hazard, _ = model.surv_heads[cancer_types[0]](pooled)
        return hazard
    hazards = [model.surv_heads[ct](pooled[i].unsqueeze(0))[0]
               for i, ct in enumerate(cancer_types)]
    return torch.cat(hazards, dim=0)
