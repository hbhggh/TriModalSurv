"""规则 2：用有效 WSI 行的患者均值构造 1536 维检索键。"""
from __future__ import annotations

import numpy as np


def _signature(wsi, valid_mask, center, *, epsilon: float, context: str):
    array = np.asarray(wsi)
    mask = np.asarray(valid_mask)
    center = np.asarray(center)
    if array.ndim != 2 or mask.dtype != np.bool_ or mask.shape != (array.shape[0],):
        raise ValueError(f"{context}: invalid WSI/mask")
    if center.shape != (array.shape[1],) or not mask.any():
        raise ValueError(f"{context}: invalid center or empty valid rows")
    value = array[mask].astype(np.float64, copy=False).mean(axis=0, dtype=np.float64)
    value = value - center.astype(np.float64, copy=False)
    norm = float(np.linalg.norm(value))
    if not np.isfinite(norm) or norm <= epsilon:
        raise ValueError(f"{context}: invalid meanpool centered norm {norm}")
    return value, norm


def meanpool_wsi_score(query, donor, query_mask, donor_mask, center, *, epsilon: float) -> float:
    """患者内行置换不变；padding 行在求均值前排除。"""
    q, qnorm = _signature(query, query_mask, center, epsilon=epsilon, context="query meanpool")
    k, knorm = _signature(donor, donor_mask, center, epsilon=epsilon, context="donor meanpool")
    score = float(np.sum(q * k, dtype=np.float64) / (qnorm * knorm))
    if not np.isfinite(score):
        raise ValueError("nonfinite meanpool WSI cosine")
    return score
