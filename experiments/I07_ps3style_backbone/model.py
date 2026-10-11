"""I07 PS3-style 三模态骨架（研究计划书 v0.2 第 1 节）。

token：P = 50 条 Hallmark 通路（每条一个 2 层 SNN）；H = 128 个 WSI 中心（Linear 1536→d）；
T = 逐字段文本（Linear 768→d + 字段身份嵌入；not mentioned 用可学习 [NOT_MENTIONED]）。每个 token 加模态嵌入 e_r
（PS3 原文为拼接，这里取加法以保持维度 d，计划书注明）。

融合（PS3 式单层）：Z = [P | H | T] → 单头 Q/K/V → logits = QK^T/√d + b_m[key 的模态] → key mask → 单一 row-wise
softmax → Z + AV → LayerNorm → + FFN → LayerNorm（MMP 代码库的 attn → ff → layernorm 结构）。9 个注意力块即
三模态两两（含自身）的 QK^T 子块，单一 softmax 下等价于对拼接序列做一次全注意力。

生存头（PS3）：每个模态 MLP f_β → LayerNorm → 模态内对有效 token 求均值 → 按 MODALITIES 顺序拼接 → Linear → 风险分。
缺失模态：不进入注意力（key 与 query 都去掉），它在头里的那一路用 fill 提供的向量（零或训练集均值）。
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn

MODALITIES = ('rna', 'wsi', 'text')  # 拼接顺序 = PS3 的 [P | H | T]
NEG = -1e9


class SNN(nn.Module):
    def __init__(self, d_in, d=256, dropout=0.25):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(d_in, d), nn.ELU(), nn.AlphaDropout(dropout),
                                 nn.Linear(d, d), nn.ELU(), nn.AlphaDropout(dropout))

    def forward(self, x):
        return self.net(x)


class PS3Style(nn.Module):
    def __init__(self, pathways, n_fields, d=256, wsi_dim=1536, text_dim=768, modalities=MODALITIES, dropout=0.25):
        super().__init__()
        unknown = set(modalities) - set(MODALITIES)
        if not modalities or unknown:
            raise ValueError(f'非法模态：{modalities}')
        self.modalities = tuple(m for m in MODALITIES if m in modalities)
        self.d = d
        self.pathways = [torch.as_tensor(p, dtype=torch.long) for p in pathways]
        for i, p in enumerate(self.pathways):
            self.register_buffer(f'pw{i}', p, persistent=False)
        self.snn = nn.ModuleList([SNN(len(p), d, dropout) for p in pathways])
        self.wsi_proj = nn.Linear(wsi_dim, d)
        self.text_proj = nn.Linear(text_dim, d)
        self.field_emb = nn.Parameter(torch.randn(n_fields, d) * 0.02)
        self.not_mentioned = nn.Parameter(torch.randn(d) * 0.02)
        self.mod_emb = nn.ParameterDict({m: nn.Parameter(torch.randn(d) * 0.02) for m in MODALITIES})
        self.b_m = nn.ParameterDict({m: nn.Parameter(torch.zeros(())) for m in MODALITIES})
        self.q, self.k, self.v = nn.Linear(d, d), nn.Linear(d, d), nn.Linear(d, d)
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.ffn = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Dropout(dropout), nn.Linear(d, d))
        self.drop = nn.Dropout(dropout)
        self.f_beta = nn.ModuleDict({m: nn.Sequential(nn.Linear(d, d), nn.ReLU(), nn.Dropout(dropout))
                                     for m in MODALITIES})
        self.head_ln = nn.ModuleDict({m: nn.LayerNorm(d) for m in MODALITIES})
        self.risk = nn.Linear(d * len(self.modalities), 1)

    # ---------- token 化 ----------
    def tokens(self, batch, m):
        """返回 (tokens[B, n, d], valid[B, n] bool)。"""
        if m == 'rna':
            x = batch.rna
            t = torch.stack([net(x[:, getattr(self, f'pw{i}')]) for i, net in enumerate(self.snn)], dim=1)
            valid = torch.ones(t.shape[:2], dtype=torch.bool, device=t.device)
        elif m == 'wsi':
            t, valid = self.wsi_proj(batch.wsi), batch.wsi_mask
        else:
            t = self.text_proj(batch.text) + self.field_emb
            nm = batch.text_nm.unsqueeze(-1)
            t = torch.where(nm, (self.not_mentioned + self.field_emb).expand_as(t), t)
            valid = torch.ones(t.shape[:2], dtype=torch.bool, device=t.device)
        return t + self.mod_emb[m], valid

    def forward(self, batch, present=None, fill=None):
        """present：本次可用的模态（默认全部 self.modalities）；fill：{模态: [d] 向量}，缺失模态在头里的那一路。
        返回 {'risk': [B]（越大预后越差）, 'pooled': {模态: [B, d]}}，契约见 contract.py。"""
        present = tuple(m for m in self.modalities if m in (present or self.modalities))
        if not present:
            raise ValueError('至少需要一个模态')
        toks, valids, owners = [], [], []
        for m in present:
            t, v = self.tokens(batch, m)
            toks.append(t)
            valids.append(v)
            owners.append(torch.full((t.shape[1],), MODALITIES.index(m), device=t.device))
        z, valid, owner = torch.cat(toks, 1), torch.cat(valids, 1), torch.cat(owners)
        bias = torch.stack([self.b_m[m] for m in MODALITIES])[owner]                      # [L]
        logits = self.q(z) @ self.k(z).transpose(1, 2) / math.sqrt(self.d) + bias       # [B, L, L]
        logits = logits.masked_fill(~valid.unsqueeze(1), NEG)
        attn = torch.softmax(logits, dim=-1)
        h = self.ln1(z + self.drop(attn @ self.v(z)))
        h = self.ln2(h + self.drop(self.ffn(h)))

        pooled, start = {}, 0
        for m, t in zip(present, toks):
            n = t.shape[1]
            hm, vm = h[:, start:start + n], valid[:, start:start + n].unsqueeze(-1).to(h.dtype)
            hm = self.head_ln[m](self.f_beta[m](hm))
            pooled[m] = (hm * vm).sum(1) / vm.sum(1).clamp(min=1)
            start += n
        B = h.shape[0]
        parts = []
        for m in self.modalities:
            if m in pooled:
                parts.append(pooled[m])
            else:
                vec = (fill or {}).get(m)
                if vec is None:
                    raise ValueError(f'缺失模态 {m} 未提供 fill 向量')
                parts.append(vec.to(h.dtype).expand(B, -1))
        return {'risk': self.risk(torch.cat(parts, dim=-1)).squeeze(-1), 'pooled': pooled}
