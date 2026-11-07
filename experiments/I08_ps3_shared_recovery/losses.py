"""I08 训练损失（handoff v1 §3.5）：L_Cox^missing + λ_a L_anchor + λ_m L_modal + λ_c L_cons。

- L_Cox^missing：六种缺失模式的 Cox 负偏似然等权平均，复用 I07 的 cox_loss（风险集与并列口径一致）。
- L_anchor：E_{i,m}‖x^F − U_mU_mᵀx^F‖²/d（三模态平均）。
- L_modal（C1-a）：E_{i,(m,n)}[1 − cos(z^F_m, z^F_n)]，三对。
- L_cons（C1-b）：E_{i,Ω,u}(1/r)‖ẑ^Ω_u − sg(z^F_u)‖²，stop_grad 只包目标项。
"""
from __future__ import annotations

import itertools

import torch

from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.survival import cox_loss

PAIRS = tuple(itertools.combinations(MODALITIES, 2))   # (rna,wsi), (rna,text), (wsi,text)


def cox_missing_mean(risks: dict, time, event):
    """risks: {pattern: [N]}，必须恰为六种缺失模式（Full 不进损失）。"""
    from .contract import PATTERNS
    if set(risks) != set(PATTERNS):
        raise ValueError(f'cox_missing_mean 需要恰好六种缺失模式，实际 {sorted(risks)}')
    return torch.stack([cox_loss(risks[p], time, event) for p in PATTERNS]).mean()


def anchor_loss(x_full: dict, U: dict):
    """x_full: {m: [N, d]}（已用 μ^F_m 中心化）；U: {m: [d, r]}。"""
    terms = []
    for m in MODALITIES:
        x = x_full[m]
        res = x - (x @ U[m]) @ U[m].T
        terms.append(res.pow(2).sum(1).mean() / x.shape[1])
    return torch.stack(terms).mean()


def modal_loss(z_full: dict, eps=1e-8):
    terms = []
    for m, n in PAIRS:
        a, b = z_full[m], z_full[n]
        den = (a.norm(dim=1) * b.norm(dim=1)).clamp(min=eps)
        terms.append(1.0 - (a * b).sum(1) / den)
    return torch.stack(terms, dim=1).mean()


def cons_loss(z_hat: dict, z_full: dict):
    """z_hat: {(pattern, u): [N, r]}；z_full: {m: [N, r]}。目标 z^F_u 停梯度，输入侧 ẑ 保留梯度。"""
    terms = []
    for (_, u), zh in z_hat.items():
        terms.append((zh - z_full[u].detach()).pow(2).sum(1).mean() / zh.shape[1])
    return torch.stack(terms).mean()
