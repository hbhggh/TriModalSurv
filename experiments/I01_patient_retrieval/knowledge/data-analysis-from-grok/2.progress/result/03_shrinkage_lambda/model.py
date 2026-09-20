"""规则 3：在投影前原始 feature 空间向 train mean 收缩。"""
from __future__ import annotations

import numpy as np


def shrink_feature(mean, donor, lambda_: float, *, output_dtype) -> np.ndarray:
    """计算 mu + lambda * (donor - mu)，中间量固定为 float64。"""
    lam = float(lambda_)
    if not np.isfinite(lam) or lam < 0.0 or lam > 1.0:
        raise ValueError("lambda must be finite and in [0, 1]")
    raw_mean = np.asarray(mean)
    raw_donor = np.asarray(donor)
    mu = raw_mean.astype(np.float64, copy=False)
    value = raw_donor.astype(np.float64, copy=False)
    if mu.shape != value.shape or not np.isfinite(mu).all() or not np.isfinite(value).all():
        raise ValueError("invalid shrinkage operands")
    # 端点直接复制，避免极端尺度下 mu + (donor - mu) 的灾难性消去。
    if lam == 0.0:
        return raw_mean.astype(np.dtype(output_dtype), copy=True)
    if lam == 1.0:
        return raw_donor.astype(np.dtype(output_dtype), copy=True)
    result = mu + lam * (value - mu)
    return result.astype(np.dtype(output_dtype), copy=False)
