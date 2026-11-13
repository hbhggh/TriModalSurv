"""I08 机理与可解释性定量核验（handoff v1 §6.2 第 1–4 项）。

全部在 M2 默认基座（r=32、λ_m=0.1）+ B6-LOO（in_fold_masked）默认超参（K=10、τ=0.1、α_max=0.5）上、只用本折 train / val 计算：
  mechanism    可恢复子空间 p^sha = U_uU_uᵀx^F_u 与正交剩余 p^res = (I − U_uU_uᵀ)x^F_u 的跨模态可预测性
               （另两个模态的可见 x^Ω → 目标，闭式 Ridge 在 train 拟合，val 上算 R² 与逐患者余弦）；
               风险头权重在共享子空间的能量保留率 ρ_r(u) = ‖U_uᵀw_u‖² / ‖w_u‖²（随机 r 维子空间期望 r/d）。
  stability    train 20 次 80% 子采样：val 患者 Top-K 邻居集合（按 train 原下标）的 Jaccard 与残差修正方向 Σ a e 的余弦
               （α_i > 0 时余弦对 α 缩放不变，故不受 δ 重估影响）。
  faithfulness 移除注意力最大的 Top-1 邻居 vs 随机移除另 1 个邻居（softmax 在剩余邻居上重新归一化），风险分变化 |Δh|；
               风险对 ẑ 线性：Δh = Σ_u (U_uᵀw_u)ᵀ α_i (corr_u − corr_u^{(−j)})，为精确值。配对 Wilcoxon 在报告层汇总。
  utility      ΔE_i = |h^B1 − h^F| − |h^B6 − h^F|（h^F = I07 完整风险）与 s_{i,(1)}、α_i 的 Spearman；
               高 / 低置信半区（s_{i,(1)} ≥ δ_Ω）内 C(B6) − C(B1)。
"""
from __future__ import annotations

import math

import numpy as np
import torch

from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.survival import c_index

from . import operators as op
from .contract import PATTERNS, targets

EPS = 1e-8


def _r2(y, yhat):
    sst = float((y - y.mean(0)).pow(2).sum())
    return 1.0 - float((y - yhat).pow(2).sum()) / sst if sst > 0 else float('nan')


def _cos_rows(a, b):
    return float(((a * b).sum(1) / (a.norm(dim=1) * b.norm(dim=1)).clamp(min=EPS)).mean())


def mechanism(fold, L, cfg):
    lam = cfg['interpretability']['mechanism_ridge']
    U = L['U']
    out = {}
    for u in MODALITIES:
        pat = '+'.join(m for m in MODALITIES if m != u)
        Xtr = torch.cat([fold.x['train'][pat][m] for m in pat.split('+')], -1)
        Xva = torch.cat([fold.x['val'][pat][m] for m in pat.split('+')], -1)
        P = U[u] @ U[u].T
        row = {}
        for name, proj in (('sha', lambda y: y @ P), ('res', lambda y: y - y @ P)):
            ytr, yva = proj(fold.x['train']['full'][u]).double(), proj(fold.x['val']['full'][u]).double()
            fit = op.ridge_fit(Xtr, ytr, lam)
            yhat = op.ridge_predict(fit, Xva)
            row[f'r2_{name}'] = _r2(yva, yhat)
            row[f'cos_{name}'] = _cos_rows(yva, yhat)
        yva = fold.x['val']['full'][u]
        row['energy_sha'] = float((yva @ P).pow(2).sum() / yva.pow(2).sum())
        w = fold.head.w_of(u)
        row['rho'] = float((U[u].T @ w).pow(2).sum() / w.pow(2).sum())
        row['rho_random'] = U[u].shape[1] / U[u].shape[0]
        out[u] = row
    return out


def stability(fold, plugin, K, tau, n, frac, seed):
    g = torch.Generator().manual_seed(seed)
    N = len(fold.tr['ids'])
    m = int(round(frac * N))
    subs = [torch.sort(torch.randperm(N, generator=g)[:m]).values for _ in range(n)]
    jac, cos = [], []
    for pat in PATTERNS:
        idx, w, _ = plugin.retrieve(pat, K, tau)
        full_sets = [set(r.tolist()) for r in idx]
        for sub in subs:
            idx_s, w_s, _ = op.topk_attention(plugin.sim[pat][:, sub], K, tau)
            idx_o = sub[idx_s]
            for i, s in enumerate(full_sets):
                t = set(idx_o[i].tolist())
                jac.append(len(s & t) / len(s | t))
            for u in targets(pat):
                e = plugin.pool[(pat, u)]
                v = (w.unsqueeze(-1) * e[idx]).sum(1)
                v_s = (w_s.unsqueeze(-1) * e[idx_o]).sum(1)
                cos.append(((v * v_s).sum(1) / (v.norm(dim=1) * v_s.norm(dim=1)).clamp(min=EPS)).numpy())
    return {'jaccard_mean': float(np.mean(jac)), 'cos_mean': float(np.mean(np.concatenate(cos))),
            'n_subsamples': n, 'frac': frac}


def faithfulness(fold, plugin, K, tau, amax, seed):
    g = torch.Generator().manual_seed(seed)
    U = plugin.L['U']
    top1, rand, share = [], [], []
    for pat in PATTERNS:
        idx, w, s1 = plugin.retrieve(pat, K, tau)
        st = plugin.stats[pat]
        alpha = op.gate_alpha(s1, amax, st['delta'], st['gamma']).squeeze(1)
        vals = plugin.sim[pat].gather(1, idx)
        gvec = {u: U[u].T @ fold.head.w_of(u) for u in targets(pat)}
        # 每个邻居对风险的线性贡献（不重归一化）：c_ij = α_i a_ij Σ_u g_uᵀ e_{j,u}
        contrib = sum((plugin.pool[(pat, u)][idx] @ gvec[u]) for u in targets(pat)) * w * alpha.unsqueeze(1)
        for i in range(idx.shape[0]):
            def drop(j):
                keep = [k for k in range(K) if k != j]
                ww = torch.softmax(vals[i, keep] / tau, 0)
                dh = 0.0
                for u in targets(pat):
                    e = plugin.pool[(pat, u)][idx[i]]
                    corr, corr_j = (w[i].unsqueeze(1) * e).sum(0), (ww.unsqueeze(1) * e[keep]).sum(0)
                    dh += float(alpha[i] * gvec[u] @ (corr - corr_j))
                return abs(dh)
            j_rand = 1 + int(torch.randint(K - 1, (1,), generator=g))           # 随机移除 Top-1 以外的一个邻居
            top1.append(drop(0))
            rand.append(drop(j_rand))
            tot = float(contrib[i].abs().sum())
            share.append(float(contrib[i, 0].abs()) / tot if tot > 0 else float('nan'))
    return {'abs_dh_top1': top1, 'abs_dh_rand': rand, 'top1_linear_share_mean': float(np.nanmean(share))}


def utility(fold, plugin, K, tau, amax):
    risks_b6, _, aux = plugin.b6(K, tau, amax, True, return_aux=True)
    risks_b1 = plugin.L['val']['risk']
    hF = fold.va['risk_full']
    t, e = fold.va['time'].numpy(), fold.va['event'].numpy()
    out = {'s1': [], 'alpha': [], 'dE': [], 'half_dC': {}}
    for pat in PATTERNS:
        dE = (risks_b1[pat] - hF).abs() - (risks_b6[pat] - hF).abs()
        s1 = aux[pat]['s1']
        out['s1'] += s1.tolist()
        out['alpha'] += aux[pat]['alpha'].squeeze(1).tolist()
        out['dE'] += dE.tolist()
        hi = (s1 >= plugin.stats[pat]['delta']).numpy()
        for name, mask in (('high', hi), ('low', ~hi)):
            try:
                dc = (c_index(risks_b6[pat].numpy()[mask], t[mask], e[mask])
                      - c_index(risks_b1[pat].numpy()[mask], t[mask], e[mask]))
            except ValueError:                                 # 该半区没有可比较对
                dc = None
            out['half_dC'].setdefault(name, []).append(dc)
    return out


def run_all(fold, base, plugin, cfg, b6_default):
    K, tau, amax = b6_default
    it = cfg['interpretability']
    return {'config': {'base': base['hp'], 'K': K, 'tau': tau, 'alpha_max': amax, 'residual_mode': 'in_fold_masked'},
            'mechanism': mechanism(fold, base['latent'], cfg),
            'stability': stability(fold, plugin, K, tau, it['bootstrap_n'], it['bootstrap_frac'], it['seed']),
            'faithfulness': faithfulness(fold, plugin, K, tau, amax, it['seed']),
            'utility': utility(fold, plugin, K, tau, amax)}


# ---------------------------------------------------------------- 报告表

def _f(x, nd=4):
    return '—' if x is None or (isinstance(x, float) and not math.isfinite(x)) else f'{x:.{nd}f}'


def render_tables(results, cancers, folds):
    from scipy import stats
    runs = [results[(c, k)].get('interpretability') for c in cancers for k in folds]
    if any(r is None for r in runs):
        return '\n## 表 4 / 表 5\n\n本次运行未计算可解释性（--no-interp）。\n'
    nf = len(runs)
    L = [f'\n## 表 4　机理：可恢复子空间 vs 正交剩余的跨模态可预测性（val，{nf} 个癌×折平均）\n\n',
         '可见 = 另外两个模态的 x^Ω；Ridge 在本折 train 拟合（λ 固定）。ρ_r = 风险头权重在 U_u 列空间的能量占比，随机 r 维子空间期望 r/d。\n\n',
         '| 目标模态 u | R²_val(p^sha) | R²_val(p^res) | cos(p^sha) | cos(p^res) | val 能量占比 p^sha | ρ_r(u) | 随机期望 r/d |\n',
         '|---|---|---|---|---|---|---|---|\n']
    for u in MODALITIES:
        rows = [r['mechanism'][u] for r in runs]
        mean = {k: float(np.nanmean([x[k] for x in rows])) for k in rows[0]}
        L.append(f'| {u} | {_f(mean["r2_sha"])} | {_f(mean["r2_res"])} | {_f(mean["cos_sha"])} | {_f(mean["cos_res"])} | '
                 f'{_f(mean["energy_sha"])} | {_f(mean["rho"])} | {_f(mean["rho_random"])} |\n')
    jac = [r['stability']['jaccard_mean'] for r in runs]
    cs = [r['stability']['cos_mean'] for r in runs]
    t1 = np.concatenate([r['faithfulness']['abs_dh_top1'] for r in runs])
    rd = np.concatenate([r['faithfulness']['abs_dh_rand'] for r in runs])
    try:
        wil = stats.wilcoxon(t1, rd, alternative='greater')
        wil_txt = f'W={wil.statistic:.1f}, 单侧 p={wil.pvalue:.2e}'
    except ValueError as ex:
        wil_txt = f'无法计算（{ex}）'
    share = float(np.nanmean([r['faithfulness']['top1_linear_share_mean'] for r in runs]))
    s1 = np.concatenate([r['utility']['s1'] for r in runs])
    al = np.concatenate([r['utility']['alpha'] for r in runs])
    dE = np.concatenate([r['utility']['dE'] for r in runs])
    rs1, ps1 = stats.spearmanr(s1, dE)
    ral, pal = stats.spearmanr(al, dE)
    half = {h: [x for r in runs for x in r['utility']['half_dC'][h] if x is not None] for h in ('high', 'low')}
    L += ['\n## 表 5　可解释性定量核验（M2 默认基座 + B6-LOO 默认超参，val）\n\n',
          '| 检验 | 指标 | 值 |\n|---|---|---|\n',
          f'| ① 稳定性（train 20×80% 子采样） | Top-K 邻居 Jaccard（均值 ± sd，{nf} 折） | {np.mean(jac):.4f} ± {np.std(jac):.4f} |\n',
          f'| ① 稳定性 | 残差修正方向余弦（均值 ± sd） | {np.mean(cs):.4f} ± {np.std(cs):.4f} |\n',
          f'| ② 忠实性（Top-1 擦除） | 中位 \\|Δh\\|：Top-1 / 随机另一邻居（n={len(t1)}） | {np.median(t1):.5f} / {np.median(rd):.5f} |\n',
          f'| ② 忠实性 | 配对 Wilcoxon（Top-1 > 随机） | {wil_txt} |\n',
          f'| ② 忠实性 | Top-1 在线性贡献中的平均占比 | {share:.4f} |\n',
          f'| ③ 门控-收益关联 | Spearman(s_(1), ΔE)（n={len(dE)}） | ρ={rs1:.4f}, p={ps1:.2e} |\n',
          f'| ③ 门控-收益关联 | Spearman(α_i, ΔE) | ρ={ral:.4f}, p={pal:.2e} |\n',
          f'| ③ 门控-收益关联 | 平均 ΔE（>0 表示 B6 比 B1 更接近 I07 完整风险） | {np.mean(dE):+.5f} |\n',
          f'| ③ 半区 ΔC-index（B6 − B1） | 高置信 s_(1) ≥ δ（n={len(half["high"])} 个模式×折） | {np.mean(half["high"]) if half["high"] else float("nan"):+.4f} |\n',
          f'| ③ 半区 ΔC-index（B6 − B1） | 低置信 s_(1) < δ（n={len(half["low"])}） | {np.mean(half["low"]) if half["low"] else float("nan"):+.4f} |\n']
    return ''.join(L)
