"""I08 算子（handoff v1 §3）：A1 / A5、B1、B3、B5、B6-LOO / B6-Naive、B0 / C0 / M7 闭式 Ridge，以及路由与风险头拼接。

记号与 handoff 一致：p^F（完整前向 pooled）、p^Ω（缺失前向的可见 pooled）、x = p − μ（μ 只来自本折 train）、
z = U_mᵀx、ẑ（恢复的缺失共享坐标）、p̂ = μ^F_u + U_u ẑ。
两种"残差"命名严格区分：x_orth_res = (I − U Uᵀ)x（A1 的正交剩余，缺失模态直接截断）；
e_pool = z^F_u − f(b_in)（B6 的潜空间预测误差残差）。

路由（画布阶段 ⑥）：full → 直接返回缓存的 I07 原风险分（D0 恒等）；缺失模式 → 可见位用 p^Ω 原样（W1-4），
只有缺失位填 p̂，按 rna|wsi|text 拼接后过冻结风险头。
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn
from torch.nn.utils import parametrizations

from experiments.I07_ps3style_backbone.model import MODALITIES

from . import contract
from .contract import PATTERNS, targets, visible

COS_EPS = 1e-8
LEV_FLOOR = 1e-4          # exact_loo_hat：max(1 − H_jj, 1e-4)
NEG_INF = float('-inf')


# ---------------------------------------------------------------- 统计量（只来自本折 train）

def train_stats(p_train: dict):
    """p_train: {view: {m: [N_tr, d]}} → (mu_full {m: [d]}, mu_pat {(pattern, m): [d]})。只接收 train 部分。"""
    mu_full = {m: p_train['full'][m].mean(0) for m in MODALITIES}
    mu_pat = {(p, m): p_train[p][m].mean(0) for p in PATTERNS for m in visible(p)}
    return mu_full, mu_pat


def center(p: dict, mu_full: dict, mu_pat: dict):
    """返回 x: {'full': {m: x^F}, pattern: {m: x^Ω}}；可见输入用该模式自己的 μ^Ω（features.input_mean = pattern）。"""
    x = {'full': {m: p['full'][m] - mu_full[m] for m in MODALITIES}}
    for pat in PATTERNS:
        x[pat] = {m: p[pat][m] - mu_pat[(pat, m)] for m in visible(pat)}
    return x


# ---------------------------------------------------------------- A1 / A5

def pca_basis(x: torch.Tensor, r: int) -> torch.Tensor:
    """x：已中心化的 [N, d]（本折 train 的 x^F_m）。返回前 r 个右奇异向量 [d, r]，列正交；
    符号固定为每列绝对值最大的分量为正（确定性）。"""
    _, _, vh = torch.linalg.svd(x.double(), full_matrices=False)
    if vh.shape[0] < r:
        raise ValueError(f'train 样本数 {x.shape[0]} 不足以取 r={r} 个主方向')
    v = vh[:r].T.contiguous()
    sign = torch.sign(v.gather(0, v.abs().argmax(0, keepdim=True)))
    sign[sign == 0] = 1.0
    return (v * sign).to(x.dtype)


class SharedBasis(nn.Module):
    """每模态一套 U_m ∈ R^{d×r}。trainable=True：A1，orthogonal 参数化（结构上 U_mᵀU_m = I_r），PCA 初始化；
    trainable=False：A5，冻结的 PCA 主方向（buffer，不进优化器）。"""

    def __init__(self, init: dict, trainable: bool = True):
        super().__init__()
        self.trainable = trainable
        self.lins = nn.ModuleDict()
        for m in MODALITIES:
            u0 = init[m].float()
            d, r = u0.shape
            if trainable:
                lin = nn.Linear(r, d, bias=False)         # weight: [d, r]（tall），正交参数化保证列正交
                # 显式 cayley：tall 矩阵默认的 householder 映射叠加 AdamW weight_decay 后 UᵀU 偏离 I 达 1.0（本会话实测）
                parametrizations.orthogonal(lin, orthogonal_map='cayley')
                with torch.no_grad():
                    lin.weight = u0
                self.lins[m] = lin
            else:
                self.register_buffer(f'U_{m}', u0.clone())

    def U(self, m):
        return self.lins[m].weight if self.trainable else getattr(self, f'U_{m}')

    def all(self):
        return {m: self.U(m) for m in MODALITIES}


# ---------------------------------------------------------------- B1

def b1_key(pattern, u):
    return f'{pattern}->{u}'


class PatternLinear(nn.Module):
    """B1：每个 (Ω, u) 一个 R_{Ω→u} ∈ R^{r×k·r} 与 b_{Ω,u} ∈ R^r。〔裁定〕零初始化（起点 = 缺失位填 μ^F_u）。"""

    def __init__(self, r: int):
        super().__init__()
        self.r = r
        self.maps = nn.ModuleDict()
        for p in PATTERNS:
            k = len(visible(p))
            for u in targets(p):
                lin = nn.Linear(k * r, r, bias=True)
                nn.init.zeros_(lin.weight)
                nn.init.zeros_(lin.bias)
                self.maps[b1_key(p, u)] = lin

    def forward(self, pattern, b_in):
        return {u: self.maps[b1_key(pattern, u)](b_in) for u in targets(pattern)}

    def weights(self, pattern, u):
        lin = self.maps[b1_key(pattern, u)]
        return lin.weight, lin.bias


def b_in_of(z_vis: dict, pattern):
    """可见 z 按 MODALITIES 顺序拼接 → [B, k·r]。"""
    return torch.cat([z_vis[m] for m in visible(pattern)], dim=-1)


# ---------------------------------------------------------------- 风险头与路由

class Head:
    """冻结的 I07 self.risk：risk = head_in · w + b（w: [768]，b: 标量）。只读张量，不参与优化。"""

    def __init__(self, w: torch.Tensor, b: torch.Tensor):
        self.w = w.detach().float().reshape(-1)
        self.b = b.detach().float().reshape(())
        self.d = self.w.numel() // len(MODALITIES)

    def w_of(self, m):
        i = MODALITIES.index(m)
        return self.w[i * self.d:(i + 1) * self.d]

    def __call__(self, head_in):
        return head_in @ self.w + self.b


def missing_risk(head: Head, pattern, p_vis: dict, p_hat: dict):
    """W1-4：可见位 p^Ω 原样，缺失位 p̂；拼接顺序由 contract.assemble_head_in 钉死。"""
    return head(contract.assemble_head_in(pattern, {m: p_vis[m] for m in visible(pattern)}, p_hat))


class Recovery(nn.Module):
    """Stage 2a 的 A + B1（单癌单折）。forward 返回训练所需的一切中间量。"""

    def __init__(self, basis: SharedBasis, r: int, mu_full: dict, head: Head):
        super().__init__()
        self.basis = basis
        self.b1 = PatternLinear(r)
        self.r = r
        self.mu_full = {m: v.detach() for m, v in mu_full.items()}
        self.head = head

    def forward(self, x: dict, p: dict):
        """x：center() 的输出；p：同一部分的原始 pooled（可见位直送风险头）。"""
        U = self.basis.all()
        z_full = {m: x['full'][m] @ U[m] for m in MODALITIES}
        z_vis, z_hat, risks = {}, {}, {}
        for pat in PATTERNS:
            zv = {m: x[pat][m] @ U[m] for m in visible(pat)}
            zh = self.b1(pat, b_in_of(zv, pat))
            p_hat = {u: self.mu_full[u] + zh[u] @ U[u].T for u in zh}
            risks[pat] = missing_risk(self.head, pat, p[pat], p_hat)
            z_vis[pat] = zv
            for u, v in zh.items():
                z_hat[(pat, u)] = v
        return {'U': U, 'z_full': z_full, 'z_vis': z_vis, 'z_hat': z_hat, 'risk': risks}


def orth_error(U: torch.Tensor) -> float:
    r = U.shape[1]
    return float((U.T @ U - torch.eye(r, dtype=U.dtype, device=U.device)).abs().max())


# ---------------------------------------------------------------- 检索：相似度、自掩码、Top-K、门控

def _unit(z):
    return z / z.norm(dim=-1, keepdim=True).clamp(min=COS_EPS)


def similarity(zq: dict, zt: dict, mode='per_modality_mean_cos'):
    """zq: {m: [B, r]}，zt: {m: [N, r]}，键为同一组可见模态（按 MODALITIES 顺序）。返回 [B, N]。"""
    mods = [m for m in MODALITIES if m in zq]
    if set(zq) != set(zt) or not mods:
        raise ValueError(f'查询与锚点的可见模态必须一致：{sorted(zq)} vs {sorted(zt)}')
    if mode == 'per_modality_mean_cos':
        return torch.stack([_unit(zq[m]) @ _unit(zt[m]).T for m in mods]).mean(0)
    if mode == 'concat_cos':
        return _unit(torch.cat([zq[m] for m in mods], -1)) @ _unit(torch.cat([zt[m] for m in mods], -1)).T
    raise ValueError(f'未知相似度模式 {mode!r}')


def mask_self(sim: torch.Tensor, query_ids, train_ids):
    """查询与 train 同一 patient_id 的位置置 -inf（按 id 对齐，不按下标）。"""
    col = {p: j for j, p in enumerate(train_ids)}
    rows = [(i, col[p]) for i, p in enumerate(query_ids) if p in col]
    if rows:
        sim = sim.clone()
        i, j = zip(*rows)
        sim[list(i), list(j)] = NEG_INF
    return sim


def topk_attention(sim: torch.Tensor, K: int, tau: float):
    """返回 (idx [B, K], attn_w [B, K], s1 [B])：s1 = 最近邻相似度。要求每行至少 K 个有限值。"""
    finite = torch.isfinite(sim).sum(1)
    if K < 1 or bool((finite < K).any()):
        raise ValueError(f'K={K} 超过可检索的锚点数（最少 {int(finite.min())}）')
    vals, idx = sim.topk(K, dim=1)
    w = torch.softmax(vals / tau, dim=1)
    return idx, w, vals[:, 0]


def gate_stats(z_train_vis: dict, sim_mode='per_modality_mean_cos', exclude_self=True, gamma_mode='iqr_scaled'):
    """本折 train 留一最近邻相似度 s_{q,(1)} 的中位数 δ 与 IQR → γ = clamp(1.349 / max(IQR, 1e-3), 5, 30)。"""
    sim = similarity(z_train_vis, z_train_vis, sim_mode)
    if exclude_self:
        sim = sim.clone()
        sim.fill_diagonal_(NEG_INF)
    s1 = sim.max(1).values.double()
    q25, q50, q75 = torch.quantile(s1, torch.tensor([0.25, 0.5, 0.75], dtype=torch.float64))
    iqr = float(q75 - q25)
    if gamma_mode == 'iqr_scaled':
        gamma = min(max(1.349 / max(iqr, 1e-3), 5.0), 30.0)
    elif gamma_mode == 'fixed_10':
        gamma = 10.0
    else:
        raise ValueError(f'未知 gamma_mode {gamma_mode!r}')
    return {'delta': float(q50), 'iqr': iqr, 'gamma': gamma}


def gate_alpha(s1: torch.Tensor, alpha_max: float, delta: float, gamma: float, gated=True):
    """α_i = α_max · σ(γ (s_{i,(1)} − δ)) ∈ [0, α_max]；gated=False（M5）时 α_i ≡ α_max。返回 [B, 1]。"""
    if gated:
        a = alpha_max * torch.sigmoid(gamma * (s1 - delta))
    else:
        a = torch.full_like(s1, alpha_max)
    return a.unsqueeze(1)


# ---------------------------------------------------------------- 残差池

def residual_pool_in_fold(z_full_u_train, z_hat_b1_train):
    """口径 A：e_j = z^F_{j,u} − ẑ^{B1}_{j,u}（梯度训练的 B1 在 train 上的误差）；检索时自身由 mask_self 排除。"""
    return (z_full_u_train - z_hat_b1_train).detach()


def ridge_fit(X: torch.Tensor, Y: torch.Tensor, lam: float):
    """带截距的闭式 Ridge（截距不罚）：中心化后解。p > n 时走对偶形式。float64 计算。
    返回 dict(W [p, q], x_mean [p], y_mean [q], Xc, A_inv 形式由 hat_diag 使用)。"""
    X, Y = X.double(), Y.double()
    xm, ym = X.mean(0), Y.mean(0)
    Xc, Yc = X - xm, Y - ym
    n, p = Xc.shape
    if p <= n:
        G = Xc.T @ Xc + lam * torch.eye(p, dtype=X.dtype)
        W = torch.linalg.solve(G, Xc.T @ Yc)
    else:
        G = Xc @ Xc.T + lam * torch.eye(n, dtype=X.dtype)
        W = Xc.T @ torch.linalg.solve(G, Yc)
    return {'W': W, 'x_mean': xm, 'y_mean': ym, 'lam': lam, 'Xc': Xc, 'primal': p <= n}


def ridge_predict(fit, X):
    return ((X.double() - fit['x_mean']) @ fit['W'] + fit['y_mean'])


def ridge_hat_diag(fit):
    """H = Xc (XcᵀXc + λI)^{-1} Xcᵀ + 11ᵀ/n 的对角线（截距贡献 1/n）。"""
    Xc, lam = fit['Xc'], fit['lam']
    n, p = Xc.shape
    if fit['primal']:
        G = Xc.T @ Xc + lam * torch.eye(p, dtype=Xc.dtype)
        h = (Xc * torch.linalg.solve(G, Xc.T).T).sum(1)
    else:
        K = Xc @ Xc.T
        H = K @ torch.linalg.solve(K + lam * torch.eye(n, dtype=Xc.dtype), torch.eye(n, dtype=Xc.dtype))
        h = torch.diagonal(H)
    return h + 1.0 / n


def ridge_loo_residuals(X, Y, lam):
    """PRESS 恒等式：e^LOO_j = (y_j − ŷ_j) / max(1 − H_jj, 1e-4)。返回 (e [n, q] float32, fit)。"""
    fit = ridge_fit(X, Y, lam)
    yhat = ridge_predict(fit, X)
    h = ridge_hat_diag(fit)
    e = (Y.double() - yhat) / (1.0 - h).clamp(min=LEV_FLOOR).unsqueeze(1)
    return e.float(), fit


def residual_pool_exact_loo(b_in_train, z_full_u_train, lam):
    """口径 B：固定 U_m 下对 (b_in → z^F_u) 做闭式 Ridge，取代数精确留一残差。"""
    e, _ = ridge_loo_residuals(b_in_train, z_full_u_train, lam)
    return e


# ---------------------------------------------------------------- B3 / B6

def b6_correct(z_hat_b1: torch.Tensor, e_pool: torch.Tensor, idx, attn_w, alpha):
    """ẑ^{B6} = ẑ^{B1} + α_i Σ_j a_ij e_j。α_max = 0 时 α_i = 0，修正项为精确 0，输出逐值等于 ẑ^{B1}。"""
    corr = (attn_w.unsqueeze(-1) * e_pool[idx]).sum(1)
    if not bool(torch.isfinite(corr).all()):
        raise FloatingPointError('B6 修正项含 NaN / Inf')
    return z_hat_b1 + alpha * corr


def b3_aggregate(z_full_u_train, idx, attn_w):
    """ẑ^{B3} = Σ_j a_ij z^F_{j,u}（直接邻居特征聚合，无全局线性项）。"""
    return (attn_w.unsqueeze(-1) * z_full_u_train[idx]).sum(1)


def retrieve(zq_vis, zt_vis, K, tau, sim_mode, query_ids=None, train_ids=None):
    """相似度 → 自掩码 → Top-K。返回 dict(sim, idx, attn_w, s1)。query_ids 给出时按 id 屏蔽自查询并过守卫。"""
    sim = similarity(zq_vis, zt_vis, sim_mode)
    if query_ids is not None:
        sim = mask_self(sim, query_ids, train_ids)
    idx, w, s1 = topk_attention(sim, K, tau)
    if query_ids is not None:
        contract.check_b6_no_self_leak(sim, query_ids, train_ids, idx)
    return {'sim': sim, 'idx': idx, 'attn_w': w, 's1': s1}


# ---------------------------------------------------------------- B5

def b5_map_precision(zq_vis: dict, single_maps: dict, sigma2: dict, prior2: float):
    """M4-a：ẑ_u = Σ_m τ_{m→u} ẑ^{(m→u)} / (1 + Σ_m τ_{m→u})，τ = σ²_prior / max(σ²_{m→u}, ε)。
    single_maps: {m: callable(z_m) → ẑ^{(m→u)}}；sigma2: {m: σ²_{m→u}}（已 clamp）。"""
    num, den = 0.0, 1.0
    for m, zm in zq_vis.items():
        tau = prior2 / sigma2[m]
        num = num + tau * single_maps[m](zm)
        den = den + tau
    return num / den


def b5_direct_coord(zq_vis: dict, sigma2: dict, prior2: float):
    """M4-b：ẑ_u = Σ_m τ_m z_m / (1 + Σ_m τ_m)，τ_m = σ²_prior / max(σ²_m, ε)。"""
    num, den = 0.0, 1.0
    for m, zm in zq_vis.items():
        tau = prior2 / sigma2[m]
        num = num + tau * zm
        den = den + tau
    return num / den


def mse_per_dim(a, b):
    """(1 / (N·r)) Σ‖a − b‖²。"""
    return float((a - b).pow(2).sum() / a.numel())


def is_finite_number(x):
    return isinstance(x, float) and math.isfinite(x)
