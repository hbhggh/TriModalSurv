"""I08 Stage 2a / 2b 训练、M0–M10 全部方法的本折 val 评测与汇总报告（handoff v1 §3、§6、§7 Step 3–4）。

开发期 val 实验（用户裁定 2026-11-08）：val 同时用于选参与报告，数字偏乐观，只用于方法间开发期比较，不进论文主表。
每个需要选参的方法另报一行"固定默认超参、不在 val 上选择"的参照（@default）。全程只读缓存的 train / val。

单癌单折流程（run_fold）：
  Stage 2a  在缓存 pooled 上 full-batch AdamW 训练 A1 + B1（+ C1），每个 epoch 末按 val 六模式平均 Cox 选最佳 epoch，
            再在候选网格上按同一指标选最佳配置。基座：M2（r × λ_m，λ_c = 1）、M10-a/b/c（r）、M9（A5 PCA-32 冻结）。
  Stage 2b  固定基座的 U_m、R、b，零重训挂载 B3 / B5 / B6（Naive、LOO 两种残差口径），K × τ × α_max 网格按 val 选。
  对照      M0-a 零填充（= 缓存的 I07 缺失前向风险）、M0-b 训练均值、M1-a B0 / M1-b C0 闭式 Ridge、M7（256 维 B6-LOO）。
  Full 场景 一律直通缓存的 I07 原风险分（D0：与 I07 逐值恒等）。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.survival import c_index, cox_loss

from . import cache, contract, losses
from . import operators as op
from .contract import PATTERNS, targets, visible

SPLITS = ('train', 'val')
ONE_MOD = ('rna', 'wsi', 'text')
TWO_MOD = ('rna+wsi', 'rna+text', 'wsi+text')
M0A_TOL = 1e-5
REPORT_REQUIRE_FULL = True   # report 只接受 config 全集（5 癌 × 5 折）的运行；测试经 monkeypatch 放宽，不挂 CLI          # 本机 CPU 用缓存特征重算的零填充风险 vs 缓存的 I07 风险（跨设备容差，I05-02）

# 方法 → (表 1 的显示名, 槽位说明)
METHODS = {
    'M0-a': 'I07 + Zero', 'M0-b': 'I07 + Train-Mean (w/o B)', 'M1-a': 'B0 (256-d Ridge)', 'M1-b': 'C0 (risk-residual Ridge)',
    'M2': 'A1 + B1 + C1', 'M3': 'A1 + B3 + C1', 'M4-a': 'A1 + B5-MapPrecision + C1', 'M4-b': 'A1 + B5-DirectCoord + C1',
    'M5': 'A1 + B6-Naive + C1', 'M6-a': 'A1 + B6-LOO (in_fold_masked) + C1', 'M6-b': 'A1 + B6-LOO (exact_loo_hat) + C1',
    'M7': '256-d B6-LOO (w/o A1)', 'M8': 'A1 + B6-LOO (w/o C1)', 'M9': 'PCA-32 (A5) + B6-LOO',
    'M10-a': 'A1 + B1 (λm=0, λc=0)', 'M10-b': 'A1 + B1 + C1 (λm=0, λc=1)', 'M10-c': 'A1 + B1 + C1 (λm=0.1, λc=0)',
}


# ================================================================ 数据

@dataclass
class Fold:
    tr: dict
    va: dict
    x: dict          # {'train': center(...), 'val': center(...)}
    mu_full: dict
    mu_pat: dict
    head: op.Head


def prepare(ft: dict) -> Fold:
    mu_full, mu_pat = op.train_stats(ft['train']['p'])          # 只来自本折 train
    x = {s: op.center(ft[s]['p'], mu_full, mu_pat) for s in SPLITS}
    tr_ids, va_ids = set(ft['train']['ids']), set(ft['val']['ids'])
    if tr_ids & va_ids:
        raise AssertionError('train 与 val 患者重叠')
    return Fold(ft['train'], ft['val'], x, mu_full, mu_pat, op.Head(ft['head_w'], ft['head_b']))


# ================================================================ 打分

def score(risks: dict, part: dict) -> dict:
    """risks：{pattern: [N]}（六种缺失模式）。Full 一律用缓存的 I07 原风险。"""
    t, e = part['time'], part['event']
    allr = dict(risks, full=part['risk_full'])
    cox = {p: float(cox_loss(allr[p], t, e)) for p in ('full',) + PATTERNS}
    ci = {p: c_index(allr[p].numpy(), t.numpy(), e.numpy()) for p in ('full',) + PATTERNS}
    return {'cox': cox, 'cox_missing_mean': float(np.mean([cox[p] for p in PATTERNS])), 'cindex': ci}


def risks_from_p_hat(fold: Fold, part: dict, p_hat: dict) -> dict:
    """p_hat：{(pattern, u): [N, d]} → {pattern: risk}；可见位用 p^Ω 原样（W1-4）。"""
    return {pat: op.missing_risk(fold.head, pat, part['p'][pat], {u: p_hat[(pat, u)] for u in targets(pat)})
            for pat in PATTERNS}


def risks_from_z_hat(fold: Fold, part: dict, U: dict, z_hat: dict) -> dict:
    return risks_from_p_hat(fold, part, {(pat, u): fold.mu_full[u] + z @ U[u].T for (pat, u), z in z_hat.items()})


def select(cands: list):
    """cands：[(hparams, risks_val, score)]；按 val_cox_missing_mean 最小选，并列取网格中靠前者。"""
    best = min(range(len(cands)), key=lambda i: (cands[i][2]['cox_missing_mean'], i))
    return cands[best]


def pack(hp, sc, extra=None):
    d = {'hparams': hp, 'val': sc}
    if extra:
        d.update(extra)
    return d


# ================================================================ Stage 2a

def train_base(fold: Fold, r: int, lam_m: float, lam_c: float, cfg: dict, trainable=True, max_epochs=None):
    """返回 dict(model, best_epoch, best_val, curve)；model 已载入最佳 epoch 的参数并冻结。"""
    tr_cfg = cfg['train']
    torch.manual_seed(tr_cfg['seed'])
    init = {m: op.pca_basis(fold.x['train']['full'][m], r) for m in MODALITIES}
    model = op.Recovery(op.SharedBasis(init, trainable=trainable), r, fold.mu_full, fold.head)
    opt = torch.optim.AdamW(model.parameters(), lr=tr_cfg['lr'], weight_decay=tr_cfg['weight_decay'])
    lam_a = cfg['loss']['lambda_anchor']
    t, e = fold.tr['time'], fold.tr['event']
    best, best_epoch, best_state, curve = math.inf, None, None, []
    for epoch in range(1, (max_epochs or tr_cfg['max_epochs']) + 1):
        out = model(fold.x['train'], fold.tr['p'])
        terms = {'cox': losses.cox_missing_mean(out['risk'], t, e), 'anchor': losses.anchor_loss(fold.x['train']['full'], out['U']),
                 'modal': losses.modal_loss(out['z_full'], cfg['operator_C']['cos_eps']),
                 'cons': losses.cons_loss(out['z_hat'], out['z_full'])}
        loss = terms['cox'] + lam_a * terms['anchor'] + lam_m * terms['modal'] + lam_c * terms['cons']
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        with torch.no_grad():
            vo = model(fold.x['val'], fold.va['p'])
            vl = float(losses.cox_missing_mean(vo['risk'], fold.va['time'], fold.va['event']))
        if not math.isfinite(vl) or not math.isfinite(float(loss)):
            raise FloatingPointError(f'Stage 2a 损失非有限：epoch {epoch} train {float(loss)} val {vl}')
        curve.append({'epoch': epoch, 'train_total': float(loss), **{k: float(v) for k, v in terms.items()}, 'val_cox_missing': vl})
        if vl < best:
            best, best_epoch, best_state = vl, epoch, copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    U = model.basis.all()
    worst = max(op.orth_error(U[m]) for m in MODALITIES)
    if not worst < cfg['operator_A']['orth_tol']:
        raise AssertionError(f'U_m 正交误差 {worst} 超出容差')
    return {'model': model, 'best_epoch': best_epoch, 'best_val': best, 'curve': curve, 'orth_err': worst}


@torch.no_grad()
def latent(fold: Fold, model) -> dict:
    """固定基座下 train / val 的 z_full、z_vis、z_hat(B1)、B1 风险。"""
    out = {}
    for s, part in (('train', fold.tr), ('val', fold.va)):
        o = model(fold.x[s], part['p'])
        out[s] = {'z_full': o['z_full'], 'z_vis': o['z_vis'], 'z_hat': o['z_hat'], 'risk': o['risk']}
    out['U'] = {m: v.detach().clone() for m, v in model.basis.all().items()}
    out['model'] = model
    return out


def stage2a_grid(fold, cfg, rs, lam_ms, lam_c, trainable=True, max_epochs=None, default=None):
    """返回 (selected, default_entry, all)：每项 dict(hp, base, latent, score)。"""
    entries = []
    for r, lm in itertools.product(rs, lam_ms):
        b = train_base(fold, r, lm, lam_c, cfg, trainable, max_epochs)
        L = latent(fold, b['model'])
        sc = score(L['val']['risk'], fold.va)
        entries.append({'hp': {'r': r, 'lambda_modal': lm, 'lambda_cons': lam_c, 'best_epoch': b['best_epoch'],
                               'orth_err': b['orth_err']}, 'base': b, 'latent': L, 'score': sc})
    sel = min(entries, key=lambda en: (en['score']['cox_missing_mean'], entries.index(en)))
    dft = None
    if default is not None:
        dft = next(en for en in entries if (en['hp']['r'], en['hp']['lambda_modal']) == default)
    return sel, dft, entries


# ================================================================ Stage 2b 插件

class Plugin:
    """固定基座 L 上的检索插件：缓存每个模式的相似度、门控统计、残差池，网格只重算 Top-K / softmax / α。"""

    def __init__(self, fold: Fold, L: dict, cfg: dict, residual_mode='in_fold_masked', sim_mode='per_modality_mean_cos',
                 stats_exclude_self=True):
        b6 = cfg['operator_B_variants']['B6_LOO']
        self.fold, self.L, self.sim_mode = fold, L, sim_mode
        self.gamma_mode = b6['gate_gamma_mode']
        self.sim, self.stats, self.pool = {}, {}, {}
        tr_ids, va_ids = fold.tr['ids'], fold.va['ids']
        for pat in PATTERNS:
            zt, zq = L['train']['z_vis'][pat], L['val']['z_vis'][pat]
            self.sim[pat] = op.mask_self(op.similarity(zq, zt, sim_mode), va_ids, tr_ids)
            self.stats[pat] = op.gate_stats(zt, sim_mode, exclude_self=stats_exclude_self, gamma_mode=self.gamma_mode)
            for u in targets(pat):
                zf = L['train']['z_full'][u]
                if residual_mode == 'in_fold_masked':
                    e = op.residual_pool_in_fold(zf, L['train']['z_hat'][(pat, u)])
                elif residual_mode == 'exact_loo_hat':
                    e = op.residual_pool_exact_loo(op.b_in_of(zt, pat), zf, b6['ridge_lam_for_hat'])
                else:
                    raise ValueError(residual_mode)
                self.pool[(pat, u)] = e

    def retrieve(self, pat, K, tau):
        idx, w, s1 = op.topk_attention(self.sim[pat], K, tau)
        contract.check_b6_no_self_leak(self.sim[pat], self.fold.va['ids'], self.fold.tr['ids'], idx)
        return idx, w, s1

    def b6(self, K, tau, amax, gated=True, return_aux=False):
        z_hat, aux = {}, {}
        for pat in PATTERNS:
            idx, w, s1 = self.retrieve(pat, K, tau)
            st = self.stats[pat]
            alpha = op.gate_alpha(s1, amax, st['delta'], st['gamma'], gated)
            for u in targets(pat):
                z_hat[(pat, u)] = op.b6_correct(self.L['val']['z_hat'][(pat, u)], self.pool[(pat, u)], idx, w, alpha)
            aux[pat] = {'idx': idx, 'w': w, 's1': s1, 'alpha': alpha}
        risks = risks_from_z_hat(self.fold, self.fold.va, self.L['U'], z_hat)
        return (risks, z_hat, aux) if return_aux else risks

    def b3(self, K, tau):
        z_hat = {}
        for pat in PATTERNS:
            idx, w, _ = self.retrieve(pat, K, tau)
            for u in targets(pat):
                z_hat[(pat, u)] = op.b3_aggregate(self.L['train']['z_full'][u], idx, w)
        return risks_from_z_hat(self.fold, self.fold.va, self.L['U'], z_hat)


def grid_b6(plugin: Plugin, cfg, gated=True, default=None):
    c = cfg['operator_B_variants']['B6_LOO']['candidates']
    cands = []
    for K, tau, a in itertools.product(c['K'], c['tau'], c['alpha_max']):
        risks = plugin.b6(K, tau, a, gated)
        cands.append(({'K': K, 'tau': tau, 'alpha_max': a}, risks, score(risks, plugin.fold.va)))
    sel = select(cands)
    dft = next(cd for cd in cands if (cd[0]['K'], cd[0]['tau'], cd[0]['alpha_max']) == default) if default else None
    return sel, dft


def grid_b3(plugin: Plugin, cfg, default):
    c = cfg['operator_B_variants']['B6_LOO']['candidates']
    cands = []
    for K, tau in itertools.product(c['K'], c['tau']):
        risks = plugin.b3(K, tau)
        cands.append(({'K': K, 'tau': tau}, risks, score(risks, plugin.fold.va)))
    sel = select(cands)
    dft = next(cd for cd in cands if (cd[0]['K'], cd[0]['tau']) == default)
    return sel, dft


# ================================================================ B5

def b5_risks(fold: Fold, L: dict, cfg, mode):
    eps = cfg['operator_B_variants']['B5']['var_eps']
    model = L['model']
    z_hat, info = {}, {}
    tr, va = L['train'], L['val']
    for pat in PATTERNS:
        vis = visible(pat)
        for u in targets(pat):
            if mode == 'B5_MapPrecision':
                prior2 = float(tr['z_full'][u].pow(2).sum() / tr['z_full'][u].numel())
                maps, sig = {}, {}
                for m in vis:
                    lin = model.b1.maps[op.b1_key(m, u)]                      # 单模态模式 {m} → u 的 B1 映射
                    maps[m] = lin
                    sig[m] = max(op.mse_per_dim(tr['z_full'][u], lin(tr['z_vis'][m][m])), eps)
                z = op.b5_map_precision({m: va['z_vis'][pat][m] for m in vis}, maps, sig, prior2)
                info[(pat, u)] = {'sigma2': sig, 'prior2': prior2}
            elif mode == 'B5_DirectCoord':
                zbar = torch.stack([tr['z_full'][m] for m in MODALITIES]).mean(0)
                prior2 = float(zbar.pow(2).sum() / zbar.numel())
                sig = {m: max(op.mse_per_dim(tr['z_vis'][pat][m], zbar), eps) for m in vis}
                z = op.b5_direct_coord({m: va['z_vis'][pat][m] for m in vis}, sig, prior2)
                info[(pat, u)] = {'sigma2': sig, 'prior2': prior2}
            else:
                raise ValueError(mode)
            z_hat[(pat, u)] = z
    return risks_from_z_hat(fold, fold.va, L['U'], z_hat), info


# ================================================================ Ridge 对照：B0 / C0 / M7

def x_in(fold, s, pat):
    return torch.cat([fold.x[s][pat][m] for m in visible(pat)], -1)


def b0_parts(fold, lam):
    """每个 (Ω, u)：256k → 256 闭式 Ridge。返回 ({(pat,u): x̂_val}, {(pat,u): e^LOO_train}, )。"""
    pred, loo = {}, {}
    for pat in PATTERNS:
        Xtr, Xva = x_in(fold, 'train', pat), x_in(fold, 'val', pat)
        for u in targets(pat):
            e, fit = op.ridge_loo_residuals(Xtr, fold.x['train']['full'][u], lam)
            pred[(pat, u)] = op.ridge_predict(fit, Xva).float()
            loo[(pat, u)] = e
    return pred, loo


def b0_risks(fold, pred):
    return risks_from_p_hat(fold, fold.va, {k: fold.mu_full[k[1]] + v for k, v in pred.items()})


def c0_risks(fold, lam):
    risks = {}
    for pat in PATTERNS:
        y = (fold.tr['risk_full'] - fold.tr['risk_zero'][pat]).unsqueeze(1)
        fit = op.ridge_fit(x_in(fold, 'train', pat), y, lam)
        risks[pat] = fold.va['risk_zero'][pat] + op.ridge_predict(fit, x_in(fold, 'val', pat)).float().squeeze(1)
    return risks


def m7_grid(fold, cfg, lams, default):
    """256 维 B6-LOO：B0 预测 + α Σ a e^{LOO,256}；相似度用 256 维可见 x^Ω。"""
    b6 = cfg['operator_B_variants']['B6_LOO']
    c = b6['candidates']
    sims, stats = {}, {}
    for pat in PATTERNS:
        xt = {m: fold.x['train'][pat][m] for m in visible(pat)}
        xq = {m: fold.x['val'][pat][m] for m in visible(pat)}
        sims[pat] = op.mask_self(op.similarity(xq, xt, b6['sim_mode']), fold.va['ids'], fold.tr['ids'])
        stats[pat] = op.gate_stats(xt, b6['sim_mode'], True, b6['gate_gamma_mode'])
    cands = []
    for lam in lams:
        pred, loo = b0_parts(fold, lam)
        for K, tau, a in itertools.product(c['K'], c['tau'], c['alpha_max']):
            p_hat = {}
            for pat in PATTERNS:
                idx, w, s1 = op.topk_attention(sims[pat], K, tau)
                contract.check_b6_no_self_leak(sims[pat], fold.va['ids'], fold.tr['ids'], idx)
                alpha = op.gate_alpha(s1, a, stats[pat]['delta'], stats[pat]['gamma'])
                for u in targets(pat):
                    p_hat[(pat, u)] = fold.mu_full[u] + op.b6_correct(pred[(pat, u)], loo[(pat, u)], idx, w, alpha)
            risks = risks_from_p_hat(fold, fold.va, p_hat)
            cands.append(({'ridge_lambda': lam, 'K': K, 'tau': tau, 'alpha_max': a}, risks, score(risks, fold.va)))
    sel = select(cands)
    dft = next(cd for cd in cands if (cd[0]['ridge_lambda'], cd[0]['K'], cd[0]['tau'], cd[0]['alpha_max']) == default)
    return sel, dft


def ridge_grid(fold, lams, fn, default):
    cands = []
    for lam in lams:
        risks = fn(lam)
        cands.append(({'ridge_lambda': lam}, risks, score(risks, fold.va)))
    return select(cands), next(cd for cd in cands if cd[0]['ridge_lambda'] == default)


# ================================================================ 单癌单折

def run_fold(ft: dict, cfg: dict, max_epochs=None, with_interp=True):
    """返回 (summary: dict 可 JSON 化, preds: {方法: {pattern: np.ndarray}}, extras)。"""
    fold = prepare(ft)
    tr_cfg, bv = cfg['train'], cfg['operator_B_variants']
    b6d = bv['B6_LOO']
    b6_default = (b6d['K'], b6d['tau'], b6d['alpha_max'])
    base_default = (cfg['operator_A']['r'], cfg['operator_C']['lambda_modal'])
    lams, lam_def = tr_cfg['ridge_alphas'], tr_cfg['ridge_default']
    rs = tr_cfg['candidates']['r']
    res, preds = {}, {}

    def put(name, sel, dft=None, extra=None):
        hp, risks, sc = sel
        res[name] = pack(hp, sc, extra)
        preds[name] = {p: v.detach().numpy() for p, v in risks.items()}
        if dft is not None:
            res[name + '@default'] = pack(dft[0], dft[2])
            preds[name + '@default'] = {p: v.detach().numpy() for p, v in dft[1].items()}

    # ---- M0：静态填充
    d = fold.mu_full['rna'].shape[0]
    zero = risks_from_p_hat(fold, fold.va, {(p, u): torch.zeros(len(fold.va['ids']), d) for p in PATTERNS for u in targets(p)})
    m0a_err = max(float((zero[p] - fold.va['risk_zero'][p]).abs().max()) for p in PATTERNS)
    if not m0a_err < M0A_TOL:
        raise AssertionError(f'M0-a 重算与缓存的 I07 零填充风险差 {m0a_err} ≥ {M0A_TOL}')
    m0a = {p: fold.va['risk_zero'][p] for p in PATTERNS}                     # 直接用 I07 自己的缺失前向风险
    put('M0-a', ({}, m0a, score(m0a, fold.va)), extra={'recompute_max_abs_err': m0a_err})
    m0b = risks_from_p_hat(fold, fold.va, {(p, u): fold.mu_full[u].expand(len(fold.va['ids']), -1)
                                           for p in PATTERNS for u in targets(p)})
    put('M0-b', ({}, m0b, score(m0b, fold.va)))

    # ---- M1：无分解 Ridge
    b0_cache = {lam: b0_parts(fold, lam) for lam in lams}
    put('M1-a', *ridge_grid(fold, lams, lambda lam: b0_risks(fold, b0_cache[lam][0]), lam_def))
    put('M1-b', *ridge_grid(fold, lams, lambda lam: c0_risks(fold, lam), lam_def))

    # ---- Stage 2a 基座
    lam_c = cfg['operator_C']['lambda_cons']
    m2_sel, m2_def, _ = stage2a_grid(fold, cfg, rs, tr_cfg['candidates']['lambda_modal'], lam_c, True, max_epochs, base_default)
    m10a_sel, m10a_def, _ = stage2a_grid(fold, cfg, rs, [0.0], 0.0, True, max_epochs, (base_default[0], 0.0))
    m10b_sel, m10b_def, _ = stage2a_grid(fold, cfg, rs, [0.0], 1.0, True, max_epochs, (base_default[0], 0.0))
    m10c_sel, m10c_def, _ = stage2a_grid(fold, cfg, rs, [0.1], 0.0, True, max_epochs, (base_default[0], 0.1))
    a5, _, _ = stage2a_grid(fold, cfg, [32], [0.0], 1.0, False, max_epochs)            # M9 基座：A5 PCA-32 冻结 + B1
    for name, sel, dft in (('M2', m2_sel, m2_def), ('M10-a', m10a_sel, m10a_def), ('M10-b', m10b_sel, m10b_def),
                           ('M10-c', m10c_sel, m10c_def)):
        put(name, (sel['hp'], sel['latent']['val']['risk'], sel['score']), (dft['hp'], dft['latent']['val']['risk'], dft['score']))
    put('M9-base', (a5['hp'], a5['latent']['val']['risk'], a5['score']))

    # ---- Stage 2b：固定 M2 基座（选中的 / 默认的）插拔
    plugins = {}
    for tag, base in (('sel', m2_sel), ('def', m2_def)):
        L = base['latent']
        plugins[tag] = {
            'in_fold': Plugin(fold, L, cfg, 'in_fold_masked', b6d['sim_mode']),
            'exact': Plugin(fold, L, cfg, 'exact_loo_hat', b6d['sim_mode']),
            'naive': Plugin(fold, L, cfg, 'in_fold_masked', b6d['sim_mode'], stats_exclude_self=False),
        }
    b3d = (bv['B3']['K'], bv['B3']['tau'])
    s3, _ = grid_b3(plugins['sel']['in_fold'], cfg, b3d)
    _, d3 = grid_b3(plugins['def']['in_fold'], cfg, b3d)
    put('M3', s3, d3, extra={'base': m2_sel['hp']})
    for name, mode in (('M4-a', 'B5_MapPrecision'), ('M4-b', 'B5_DirectCoord')):
        rs_sel, info = b5_risks(fold, m2_sel['latent'], cfg, mode)
        rs_def, _ = b5_risks(fold, m2_def['latent'], cfg, mode)
        put(name, ({}, rs_sel, score(rs_sel, fold.va)), ({}, rs_def, score(rs_def, fold.va)),
            extra={'base': m2_sel['hp'], 'precision': {f'{p}->{u}': v for (p, u), v in info.items()}})
    for name, key, gated in (('M5', 'naive', False), ('M6-a', 'in_fold', True), ('M6-b', 'exact', True)):
        sel, _ = grid_b6(plugins['sel'][key], cfg, gated)
        _, dft = grid_b6(plugins['def'][key], cfg, gated, b6_default)
        put(name, sel, dft, extra={'base': m2_sel['hp'],
                                   'gate_stats': {p: plugins['sel'][key].stats[p] for p in PATTERNS}})

    # ---- M7 / M8 / M9
    put('M7', *m7_grid(fold, cfg, lams, (lam_def,) + b6_default))
    for name, sel_base, def_base in (('M8', m10a_sel, m10a_def), ('M9', a5, a5)):
        sel, _ = grid_b6(Plugin(fold, sel_base['latent'], cfg, 'in_fold_masked', b6d['sim_mode']), cfg)
        _, dft = grid_b6(Plugin(fold, def_base['latent'], cfg, 'in_fold_masked', b6d['sim_mode']), cfg, True, b6_default)
        put(name, sel, dft, extra={'base': sel_base['hp']})

    summary = {'n': {'train': len(fold.tr['ids']), 'val': len(fold.va['ids'])}, 'methods': res,
               'stage2a_curves': {'M2': m2_sel['base']['curve'][-1], 'M2_best_epoch': m2_sel['hp']['best_epoch']}}
    extras = {'fold': fold, 'm2_def': m2_def, 'plugins_def': plugins['def'], 'b6_default': b6_default}
    if with_interp:
        from . import interpretability
        summary['interpretability'] = interpretability.run_all(fold, m2_def, plugins['def']['in_fold'], cfg, b6_default)
    return summary, preds, extras


# ================================================================ 汇总报告

def fmt(x, nd=4):
    return '—' if x is None or (isinstance(x, float) and not math.isfinite(x)) else f'{x:.{nd}f}'


def case_avgs(ci: dict) -> dict:
    one = float(np.mean([ci[p] for p in ONE_MOD]))
    two = float(np.mean([ci[p] for p in TWO_MOD]))
    miss = float(np.mean([ci[p] for p in PATTERNS]))
    return {'1mod': one, '2mod': two, 'full': ci['full'], 'miss6': miss,
            'all7': float(np.mean([ci[p] for p in ('full',) + PATTERNS]))}


def aggregate(results: dict, cancers, folds):
    """results[(c, k)] = summary。返回 per-method 表数据（先折内平均到癌种，再五癌宏平均）。"""
    names = list(next(iter(results.values()))['methods'])
    table = {}
    for name in names:
        per_cancer = {}
        for c in cancers:
            rows = [case_avgs(results[(c, k)]['methods'][name]['val']['cindex']) for k in folds]
            per_cancer[c] = {key: float(np.mean([r[key] for r in rows])) for key in rows[0]}
            per_cancer[c]['per_pattern'] = {p: float(np.mean([results[(c, k)]['methods'][name]['val']['cindex'][p]
                                                               for k in folds])) for p in PATTERNS}
            per_cancer[c]['cox_missing'] = float(np.mean([results[(c, k)]['methods'][name]['val']['cox_missing_mean']
                                                          for k in folds]))
        macro = {key: float(np.mean([per_cancer[c][key] for c in cancers]))
                 for key in ('1mod', '2mod', 'full', 'miss6', 'all7', 'cox_missing')}
        macro['per_pattern'] = {p: float(np.mean([per_cancer[c]['per_pattern'][p] for c in cancers])) for p in PATTERNS}
        table[name] = {'macro': macro, 'per_cancer': per_cancer}
    return table


def paired(results, cancers, folds, a, b):
    """配对 Δ（6-Missing Avg C-index，a − b）：25 个 (癌, 折) 的均值与严格胜场数。"""
    ds = []
    for c in cancers:
        for k in folds:
            m = results[(c, k)]['methods']
            if a not in m or b not in m:
                return None
            ds.append(case_avgs(m[a]['val']['cindex'])['miss6'] - case_avgs(m[b]['val']['cindex'])['miss6'])
    return {'mean': float(np.mean(ds)), 'wins': int(sum(x > 0 for x in ds)), 'ties': int(sum(x == 0 for x in ds)), 'n': len(ds)}


def write_report(results: dict, cancers, folds, out_md: Path, meta: dict):
    from . import interpretability
    table = aggregate(results, cancers, folds)
    order = []
    for base in METHODS:
        order += [n for n in (base, base + '@default') if n in table]
        if base == 'M9' and 'M9-base' in table:
            order.append('M9-base')
    L = []
    L.append('# I08 验证集消融与可解释性报告 v1（开发期 val，不进论文主表）\n')
    L.append(f'> 生成：`train_eval.py report`｜缓存 manifest sha256 `{meta.get("cache_manifest_sha256", "?")}`｜'
             f'config sha256 `{meta.get("config_sha256", "?")}`｜源码 commit `{meta.get("commit", "?")}`｜'
             f'结果摘要 sha256 `{meta.get("results_digest", "?")}`\n')
    L.append('> 范围：5 癌（' + ', '.join(cancers) + f'）× {len(folds)} 折，只用本折 train / val；test 未读取（test_access: false）。\n')
    L.append('\n## 口径与必须一并阅读的事实\n')
    for s in CAVEATS:
        L.append(f'- {s}\n')

    L.append('\n## 表 1　总体消融（val C-index，折内平均 → 五癌宏平均）\n\n')
    nf = len(cancers) * len(folds)
    L.append(f'`@default` = 固定默认超参、不在 val 上选择的参照行。Δ 列为 6-Missing Avg 的配对差（{nf} 个癌×折均值，括号内为严格胜场 / {nf}）。\n\n')
    L.append('| 方法 | 变体 | 1-Mod Avg | 2-Mod Avg | Full | 6-Missing Avg | Overall 7-Case | val Cox (6 缺失) | Δ vs M0-a | Δ vs M2 | Δ vs M3 |\n')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|\n')
    for n in order:
        mac = table[n]['macro']
        cells = []
        for ref in ('M0-a', 'M2', 'M3'):
            pr = paired(results, cancers, folds, n, ref) if n != ref else None
            cells.append('—' if pr is None else f'{pr["mean"]:+.4f} ({pr["wins"]}/{pr["n"]})')
        base = n.split('@')[0]
        L.append(f'| {n} | {METHODS.get(base, "A5 + B1（M9 基座）")} | {fmt(mac["1mod"])} | {fmt(mac["2mod"])} | {fmt(mac["full"])} | '
                 f'{fmt(mac["miss6"])} | {fmt(mac["all7"])} | {fmt(mac["cox_missing"])} | ' + ' | '.join(cells) + ' |\n')

    L.append('\n## 表 2　分缺失模式（五癌平均 val C-index；列 = 可见模态）\n\n')
    L.append('| 方法 | ' + ' | '.join(PATTERNS) + ' |\n|---|' + '---|' * len(PATTERNS) + '\n')
    for n in order:
        pp = table[n]['macro']['per_pattern']
        L.append(f'| {n} | ' + ' | '.join(fmt(pp[p]) for p in PATTERNS) + ' |\n')

    L.append('\n## 表 3　分癌种（6 种缺失模式平均 val C-index，5 折平均）\n\n')
    L.append('| 方法 | ' + ' | '.join(cancers) + ' |\n|---|' + '---|' * len(cancers) + '\n')
    for n in order:
        pc = table[n]['per_cancer']
        L.append(f'| {n} | ' + ' | '.join(fmt(pc[c]['miss6']) for c in cancers) + ' |\n')

    L.append(interpretability.render_tables(results, cancers, folds))
    L.append('\n## 选中的超参数（逐癌×折）\n\n见同目录 `val_runs/<癌>_fold<k>.json` 的 `methods.<方法>.hparams`。\n')
    out_md.write_text(''.join(L))
    return table


CAVEATS = [
    '**开发期 val**：本报告的 val 同时用于 Stage 2a 选 epoch / 选配置与 Stage 2b 选 K、τ、α_max，数字对网格大的方法偏乐观'
    '（M6 在 36 组里选，M2 在 4 组里选）；`@default` 行不在 val 上选超参（Stage 2a 仍按 val 选最佳 epoch），是更公平的参照。不进论文主表；test 需另行授权。',
    '**Full 列对所有方法相同**：Full 场景一律直通缓存的 I07 原风险分（D0 恒等，导出时逐患者误差 < 1e-6）。',
    '**M0-a 与 M0-b 的 C-index 必然相同**：常数填充经线性风险头只给所有患者加同一常数，排序不变（I07 已证实）；两者只在 Cox 损失上不同。'
    'M0-a 直接使用缓存的 I07 缺失前向风险；本机用缓存特征重算的零填充风险与它的差 < 1e-5（跨设备容差）。I07 历史只存了 test 预测，'
    '“与 I07 历史逐值一致”只能由导出时的 D0 守卫证明。',
    '**LOO 自掩码对 val 查询不起作用**：val 患者本不在 train 残差池里；自掩码只影响 train 侧的 δ / IQR。'
    'M5 按用户裁定（2026-11-08）定义为“去门控（α_i ≡ α_max）+ δ/IQR 统计不做自掩码”；由于去门控后 δ/IQR 不再被使用，M5 实际只与 M6-a 相差门控一项。',
    '**M6-b 口径**：残差池来自固定 U_m 上 (b_in → z^F_u) 的闭式 Ridge 精确留一残差（λ = ridge_lam_for_hat），基座预测仍是梯度训练的 B1，'
    '两者不是同一个预测器；保留 B1 基座是为了保证 α_max = 0 时与 M2 逐值相同。',
    '**B5 口径**：M4-a 的单模态映射 R_{m→u} 在单模态视角 p^{m} 上训练，用于双模态视角时输入的是 p^{Ω} 下的 z_m，存在分布偏移；'
    'σ²_{m→u} 为 train 上的样本内均方误差（handoff 写“留一”，公式为样本内，按公式实现）。M4-b 假设 C1 已把各模态坐标对齐。',
    '**零初始化**：B1 的 R、b 零初始化（起点 = 缺失位填 μ^F_u，即 M0-b），〔裁定〕handoff 未规定初始化。',
    '**正交参数化**：U_m 用 torch orthogonal 参数化的 cayley 映射；tall 矩阵默认的 householder 映射叠加 weight decay 会失去正交性（本会话实测）。',
    '**可解释性表**（表 4、表 5）对 M2 默认基座（r=32、λ_m=0.1）+ B6-LOO 默认超参（K=10、τ=0.1、α_max=0.5）计算，'
    '避免 val 选出 α_max=0 时修正量恒为 0、无法分析；不代表选中配置。',
]


# ================================================================ CLI

def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cmd_run(a):
    cfg, cfg_sha = contract.load_config()
    if cfg['train']['test_access'] is not False:
        raise PermissionError('test_access 必须为 false')
    ident = cache.source_identity(a.expected_commit)                 # 强制源码身份门（finding 3）
    manifest_blob = (a.cache / 'manifest.json').read_bytes()
    if hashlib.sha256(manifest_blob).hexdigest() != a.cache_manifest_sha256:
        raise PermissionError('缓存 manifest.json 的 sha256 与 --cache-manifest-sha256 不同，拒绝')
    manifest = json.loads(manifest_blob)
    cache.verify_cache_manifest(manifest, cfg)
    want_c, want_k = cfg['backbone']['cancers'], cfg['backbone']['folds']
    if not set(a.cancers.split(',')) <= set(want_c) or not {int(k) for k in a.folds.split(',')} <= set(want_k):
        raise PermissionError('--cancers / --folds 超出 config 的癌×折范围')
    out = a.out / 'val_runs'
    out.mkdir(parents=True, exist_ok=False)
    run_meta = {'verified': True, 'source': ident, 'cache_source': manifest['source'], 'config_sha256': cfg_sha, 'cache_manifest_sha256': hashlib.sha256(manifest_blob).hexdigest(),
                'max_epochs': a.max_epochs or cfg['train']['max_epochs'], 'cancers': a.cancers.split(','),
                'folds': [int(k) for k in a.folds.split(',')], 'files': {}}
    for c in run_meta['cancers']:
        for k in run_meta['folds']:
            ft = cache.fold_tensors(cache.load_fold_cache(a.cache, c, k, manifest))
            summary, preds, _ = run_fold(ft, cfg, a.max_epochs, with_interp=not a.no_interp)
            summary.update({'cancer': c, 'fold': k, 'val_ids': ft['val']['ids']})
            js = json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True).encode()
            buf = io.BytesIO()
            np.savez(buf, val_ids=np.array(ft['val']['ids']), time=ft['val']['time'].numpy(), event=ft['val']['event'].numpy(),
                     **{f'{m}__{p}': v for m, d in preds.items() for p, v in d.items()})
            for name, blob in ((f'{c}_fold{k}.json', js), (f'{c}_fold{k}_preds_val.npz', buf.getvalue())):
                cache.write_atomic(out / name, blob)
                run_meta['files'][name] = hashlib.sha256(blob).hexdigest()
            m6 = summary['methods']['M6-a']['val']['cindex']
            print(json.dumps({'fold': f'{c}/{k}', 'M6-a miss6': case_avgs(m6)['miss6'],
                              'M2 miss6': case_avgs(summary['methods']['M2']['val']['cindex'])['miss6']}), flush=True)
    cache.write_atomic(a.out / 'run_meta.json', json.dumps(run_meta, indent=2, ensure_ascii=False, sort_keys=True).encode())


def load_results(out: Path):
    run_meta = json.loads((out / 'run_meta.json').read_text())
    results = {}
    for name, h in sorted(run_meta['files'].items()):
        blob = (out / 'val_runs' / name).read_bytes()
        if hashlib.sha256(blob).hexdigest() != h:
            raise PermissionError(f'{name} 与 run_meta.json 的哈希不符')
        if name.endswith('.json'):
            s = json.loads(blob)
            results[(s['cancer'], s['fold'])] = s
    return run_meta, results


def cmd_report(a):
    run_meta, results = load_results(a.out)
    cfg, cfg_sha = contract.load_config()
    if run_meta.get('verified') is not True or not run_meta.get('source', {}).get('commit'):
        raise PermissionError('该运行未经过源码身份门与缓存核对，拒绝生成报告')
    if run_meta['config_sha256'] != cfg_sha:
        raise PermissionError('运行时的 config 与当前 config.yaml 不同，拒绝生成报告')
    if REPORT_REQUIRE_FULL and (run_meta['cancers'] != cfg['backbone']['cancers'] or run_meta['folds'] != cfg['backbone']['folds']):
        raise PermissionError('报告只接受 config 全集的运行')
    if REPORT_REQUIRE_FULL and run_meta['max_epochs'] != cfg['train']['max_epochs']:
        raise PermissionError('冒烟运行（--max-epochs）不能生成报告')
    if set(results) != {(c, k) for c in run_meta['cancers'] for k in run_meta['folds']}:
        raise PermissionError('结果文件缺折或多折')
    digest = hashlib.sha256(json.dumps(run_meta['files'], sort_keys=True).encode()).hexdigest()
    meta = {'cache_manifest_sha256': run_meta['cache_manifest_sha256'], 'config_sha256': run_meta['config_sha256'],
            'commit': run_meta['source'].get('commit'), 'results_digest': digest}
    write_report(results, run_meta['cancers'], run_meta['folds'], a.out / 'val_ablation_report_v1.md', meta)
    print(a.out / 'val_ablation_report_v1.md')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--cache', required=True, type=Path)
    r.add_argument('--out', required=True, type=Path)
    r.add_argument('--cancers', default='BLCA,BRCA,LUAD,LGG,UCEC')
    r.add_argument('--folds', default='0,1,2,3,4')
    r.add_argument('--max-epochs', type=int, default=None, help='只用于冒烟；开发期运行不传（取 config 的 200）')
    r.add_argument('--expected-commit', required=True, help='源码身份门：干净且 commit 相等')
    r.add_argument('--cache-manifest-sha256', required=True, help='已冻结的缓存 manifest.json 摘要')
    r.add_argument('--no-interp', action='store_true')
    p = sub.add_parser('report')
    p.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    {'run': cmd_run, 'report': cmd_report}[a.cmd](a)


if __name__ == '__main__':
    main()
