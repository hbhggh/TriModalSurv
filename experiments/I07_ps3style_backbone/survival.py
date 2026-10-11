"""Cox 部分似然损失与 Harrell C-index。风险分越大 = 预期生存越短，方向只在这里定义一次（坑 V4）。"""
from __future__ import annotations

import numpy as np
import torch


def cox_loss(risk: torch.Tensor, time: torch.Tensor, event: torch.Tensor) -> torch.Tensor:
    """负对数部分似然（Breslow 处理并列时间），按事件数平均；没有事件时返回 0（梯度也为 0）。

    risk_i 的风险集 = {j : t_j >= t_i}。
    """
    risk, time, event = risk.reshape(-1), time.reshape(-1), event.reshape(-1).to(risk.dtype)
    n_events = event.sum().clamp(min=1.0)  # 0 事件时分子为 0 → 损失与梯度都为 0；不用 .item()，避免热循环同步
    at_risk = time.unsqueeze(0) >= time.unsqueeze(1)                      # [i, j]：j 在 i 的风险集里
    log_risk_set = torch.logsumexp(risk.unsqueeze(0).masked_fill(~at_risk, float('-inf')), dim=1)
    return -((risk - log_risk_set) * event).sum() / n_events


def c_index(risk, time, event) -> float:
    """Harrell C-index：可比较对 = t_i < t_j 且 i 发生事件；风险并列记 0.5。没有可比较对时报错（坑 V7）。"""
    risk, time, event = (np.asarray(x, dtype=np.float64).reshape(-1) for x in (risk, time, event))
    if not np.isfinite(risk).all():
        raise ValueError('风险分含 NaN/Inf')
    conc, total = 0.0, 0
    for i in np.flatnonzero(event == 1):
        j = time > time[i]
        n = int(j.sum())
        if n == 0:
            continue
        total += n
        conc += float((risk[i] > risk[j]).sum()) + 0.5 * float((risk[i] == risk[j]).sum())
    if total == 0:
        raise ValueError('没有可比较的病人对')
    return conc / total
