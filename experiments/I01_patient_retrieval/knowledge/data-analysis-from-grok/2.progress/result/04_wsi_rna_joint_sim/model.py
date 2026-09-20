"""规则 4：text_100 下的 WSI + RNA 联合相似度。"""
from __future__ import annotations

import numpy as np


def token_mean_cosine(query_rna, donor_rna, *, epsilon: float) -> float:
    """对完整 RNA token 在投影前求均值，不去中心。"""
    query = np.asarray(query_rna)
    donor = np.asarray(donor_rna)
    if query.ndim != 2 or donor.shape != query.shape:
        raise ValueError("invalid RNA token shape")
    q = query.astype(np.float64, copy=False).mean(axis=0, dtype=np.float64)
    k = donor.astype(np.float64, copy=False).mean(axis=0, dtype=np.float64)
    qnorm, knorm = float(np.linalg.norm(q)), float(np.linalg.norm(k))
    if any(not np.isfinite(norm) or norm <= epsilon for norm in (qnorm, knorm)):
        raise ValueError("invalid RNA meanpool norm")
    score = float(np.sum(q * k, dtype=np.float64) / (qnorm * knorm))
    if not np.isfinite(score):
        raise ValueError("nonfinite RNA cosine")
    return score


def joint_similarity(score_wsi: float, score_rna: float, alpha: float) -> float:
    values = np.asarray([score_wsi, score_rna, alpha], dtype=np.float64)
    if not np.isfinite(values).all() or float(alpha) < 0.0:
        raise ValueError("invalid joint similarity inputs")
    return float(values[0] + values[2] * values[1])
