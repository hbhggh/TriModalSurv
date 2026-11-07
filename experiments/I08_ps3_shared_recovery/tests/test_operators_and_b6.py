"""I08 算子单测（handoff v1 §3、§7 Step 3）：正交性、α_max=0 精确退化、B6 防自查询泄漏（反事实扰动）、
L_cons 梯度流向、Ridge 精确留一、门控统计、B3 / B5 公式、风险头拼接与 I07 缺失前向逐值一致。"""
import copy

import pytest
import torch

from experiments.I07_ps3style_backbone import data
from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.tests.test_train import small_model, write_assets
from experiments.I08_ps3_shared_recovery import contract, losses
from experiments.I08_ps3_shared_recovery import operators as op
from experiments.I08_ps3_shared_recovery.contract import PATTERNS, targets, visible

D, R = 24, 4


def synth(n=40, seed=0, d=D):
    """合成 pooled：三模态共享一个低维因子 + 模态特有噪声；缺失视角 = 完整视角 + 小偏移（模拟注意力上下文变化）。"""
    g = torch.Generator().manual_seed(seed)
    f = torch.randn(n, 3, generator=g)
    p = {'full': {}}
    for i, m in enumerate(MODALITIES):
        A = torch.randn(3, d, generator=g)
        p['full'][m] = f @ A + 0.3 * torch.randn(n, d, generator=g) + i
    for pat in PATTERNS:
        p[pat] = {m: p['full'][m] + 0.05 * torch.randn(n, d, generator=g) for m in visible(pat)}
    time = torch.rand(n, generator=g) * 100 + 1
    event = (torch.rand(n, generator=g) < 0.6).float()
    return p, time, event


def build(p, r=R, trainable=True, seed=0):
    mu_full, mu_pat = op.train_stats(p)
    x = op.center(p, mu_full, mu_pat)
    basis = op.SharedBasis({m: op.pca_basis(x['full'][m], r) for m in MODALITIES}, trainable=trainable)
    g = torch.Generator().manual_seed(seed)
    head = op.Head(torch.randn(3 * p['full']['rna'].shape[1], generator=g) * 0.1, torch.tensor(0.2))
    model = op.Recovery(basis, r, mu_full, head)
    with torch.no_grad():                                   # 让 B1 非零，避免恒等式被零初始化平凡满足
        for lin in model.b1.maps.values():
            lin.weight.copy_(torch.randn(lin.weight.shape, generator=g) * 0.3)
            lin.bias.copy_(torch.randn(lin.bias.shape, generator=g) * 0.1)
    return model, x


def total_loss(out, x, time, event, lam_m=0.1, lam_c=1.0):
    return (losses.cox_missing_mean(out['risk'], time, event) + losses.anchor_loss(x['full'], out['U'])
            + lam_m * losses.modal_loss(out['z_full']) + lam_c * losses.cons_loss(out['z_hat'], out['z_full']))


# ---------------------------------------------------------------- A1

@pytest.mark.parametrize('wd', [0.0, 0.01])
def test_orthogonality_before_and_after_training(wd):
    p, t, e = synth()
    model, x = build(p)
    for m in MODALITIES:
        assert op.orth_error(model.basis.U(m)) < 1e-5
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2, weight_decay=wd)
    U_before = model.basis.U('rna').detach().clone()
    for _ in range(200):
        loss = total_loss(model(x, p), x, t, e)
        opt.zero_grad()
        loss.backward()
        opt.step()
    for m in MODALITIES:
        assert op.orth_error(model.basis.U(m)) < 1e-5, m
    assert float((model.basis.U('rna') - U_before).abs().max()) > 1e-4      # U 确实被训练动了


def test_pca_init_and_a5_frozen():
    p, _, _ = synth()
    model, x = build(p, trainable=False)
    assert not any('basis' in n for n, _ in model.named_parameters())       # A5 不进优化器
    U = model.basis.U('wsi')
    assert op.orth_error(U) < 1e-5
    # PCA 主方向：投影方差单调不增
    var = (x['full']['wsi'] @ U).var(0)
    assert bool((var[:-1] >= var[1:] - 1e-5).all())


def test_param_count_matches_contract():
    p, _, _ = synth(d=256, n=60)
    model, _ = build(p, r=32)
    n_b = sum(v.numel() for v in model.b1.parameters())
    assert n_b == contract.n_params(256, 32)['B'] == 12576


# ---------------------------------------------------------------- C1 梯度

def test_lcons_gradient_flows_to_U_R_b_but_not_target():
    p, _, _ = synth()
    model, x = build(p)
    out = model(x, p)
    pat, u = 'rna+wsi', 'text'
    loss = losses.cons_loss({(pat, u): out['z_hat'][(pat, u)]}, out['z_full'])
    # 输入侧：U_m（m ∈ Ω）、R、b 必须有非零梯度
    R_w, R_b = model.b1.weights(pat, u)
    grads = torch.autograd.grad(loss, [R_w, R_b] + [model.basis.lins[m].parametrizations.weight.original
                                                    for m in visible(pat)], allow_unused=True)
    for g in grads:
        assert g is not None and float(g.abs().max()) > 0
    # 目标侧 stop_grad：对目标 z^F_u 本身求导为 0（或不可达）
    zt = out['z_full'][u]
    g_t, = torch.autograd.grad(losses.cons_loss({(pat, u): out['z_hat'][(pat, u)]}, {u: zt}), [zt], allow_unused=True)
    assert g_t is None or float(g_t.abs().max()) == 0.0
    # 反例：若不停梯度，目标会收到梯度（证明上面的断言能区分两种实现）
    g_bad, = torch.autograd.grad((out['z_hat'][(pat, u)] - zt).pow(2).mean(), [zt], retain_graph=True)
    assert float(g_bad.abs().max()) > 0


def test_lmodal_and_anchor_values():
    z = {m: torch.ones(5, 3) for m in MODALITIES}
    assert float(losses.modal_loss(z)) == pytest.approx(0.0, abs=1e-7)
    z['wsi'] = -z['wsi']
    assert float(losses.modal_loss(z)) == pytest.approx(4.0 / 3.0, abs=1e-6)   # 三对中两对 cos = -1
    U = {m: torch.eye(4)[:, :2] for m in MODALITIES}
    xf = {m: torch.tensor([[1.0, 2.0, 3.0, 4.0]]) for m in MODALITIES}
    assert float(losses.anchor_loss(xf, U)) == pytest.approx((9 + 16) / 4)


# ---------------------------------------------------------------- 风险头拼接与 I07 一致

@pytest.fixture(scope='module')
def val_part(tmp_path_factory):
    root = tmp_path_factory.mktemp('i08ops')
    write_assets(root)
    parts, _ = data.load_fold(root, 'BLCA', 0, parts=('train', 'val'))
    return parts['val']


def test_missing_risk_equals_i07_zero_fill(val_part):
    m = small_model()
    head = op.Head(m.risk.weight.detach(), m.risk.bias.detach())
    n = len(val_part)
    for pat in PATTERNS:
        vis = visible(pat)
        with torch.no_grad():
            out = m(val_part, present=vis, fill={u: torch.zeros(m.d) for u in targets(pat)})
            mine = op.missing_risk(head, pat, out['pooled'], {u: torch.zeros(n, m.d) for u in targets(pat)})
        assert float((mine - out['risk']).abs().max()) < 1e-6, pat


# ---------------------------------------------------------------- 检索与 B6

def fixed_latent(p, model, x):
    with torch.no_grad():
        return model(x, p)


def test_alpha_zero_is_exactly_b1():
    """α_max = 0：B6 的 z_hat、p_hat、risk 与 B1 逐值严格相等（差 == 0.0）。"""
    p, _, _ = synth()
    model, x = build(p)
    out = fixed_latent(p, model, x)
    ids = [f'P{i}' for i in range(len(p['full']['rna']))]
    for pat in PATTERNS:
        zv = out['z_vis'][pat]
        ret = op.retrieve(zv, zv, 5, 0.1, 'per_modality_mean_cos', ids, ids)
        st = op.gate_stats(zv)
        alpha = op.gate_alpha(ret['s1'], 0.0, st['delta'], st['gamma'])
        U = out['U']
        p_hat_b1, p_hat_b6 = {}, {}
        for u in targets(pat):
            zb1 = out['z_hat'][(pat, u)]
            e = op.residual_pool_in_fold(out['z_full'][u], zb1)
            zb6 = op.b6_correct(zb1, e, ret['idx'], ret['attn_w'], alpha)
            assert float((zb6 - zb1).abs().max()) == 0.0
            p_hat_b1[u] = model.mu_full[u] + zb1 @ U[u].T
            p_hat_b6[u] = model.mu_full[u] + zb6 @ U[u].T
            assert float((p_hat_b6[u] - p_hat_b1[u]).abs().max()) == 0.0
        r1 = op.missing_risk(model.head, pat, p[pat], p_hat_b1)
        r6 = op.missing_risk(model.head, pat, p[pat], p_hat_b6)
        assert float((r6 - r1).abs().max()) == 0.0
        assert torch.equal(r1, out['risk'][pat])


@pytest.mark.parametrize('mode', ['in_fold_masked', 'exact_loo_hat'])
def test_counterfactual_own_residual_has_zero_effect(mode):
    """train 检索：改动患者 i 自身的残差 e_i，i 自己的 B6 输出变化严格为 0.0；改动 i 的某个邻居则必须有变化。"""
    p, _, _ = synth(n=30)
    model, x = build(p)
    out = fixed_latent(p, model, x)
    ids = [f'P{i}' for i in range(30)]
    pat, u = 'wsi', 'rna'
    zv = out['z_vis'][pat]
    zb1 = out['z_hat'][(pat, u)]
    if mode == 'in_fold_masked':
        e = op.residual_pool_in_fold(out['z_full'][u], zb1)
    else:
        e = op.residual_pool_exact_loo(op.b_in_of(zv, pat), out['z_full'][u], 1.0)
    ret = op.retrieve(zv, zv, 5, 0.1, 'per_modality_mean_cos', ids, ids)
    alpha = op.gate_alpha(ret['s1'], 1.0, 0.0, 10.0)
    base = op.b6_correct(zb1, e, ret['idx'], ret['attn_w'], alpha)
    assert torch.isneginf(torch.diagonal(ret['sim'])).all()
    for i in range(30):
        e2 = e.clone()
        e2[i] += 1000.0
        new = op.b6_correct(zb1, e2, ret['idx'], ret['attn_w'], alpha)
        assert float((new[i] - base[i]).abs().max()) == 0.0, i
        j = int(ret['idx'][i, 0])                       # 最近邻：改它必须改变 i 的输出（测试能区分泄漏）
        e3 = e.clone()
        e3[j] += 1000.0
        assert float((op.b6_correct(zb1, e3, ret['idx'], ret['attn_w'], alpha)[i] - base[i]).abs().max()) > 0
    # 反例：不做自掩码时，i 的最近邻就是它自己，改 e_i 会改变 i 的输出（守卫与测试都必须能抓到）
    sim = op.similarity(zv, zv)
    idx, w, _ = op.topk_attention(sim, 5, 0.1)
    assert bool((idx[:, 0] == torch.arange(30)).all())
    with pytest.raises(contract.ContractError):
        contract.check_b6_no_self_leak(sim, ids, ids, idx)


def test_val_queries_need_no_mask_and_ids_align():
    p, _, _ = synth(n=30)
    model, x = build(p)
    out = fixed_latent(p, model, x)
    zv = out['z_vis']['rna']
    q = {m: v[:4] + 0.01 for m, v in zv.items()}
    ret = op.retrieve(q, zv, 5, 0.1, 'per_modality_mean_cos', ['V0', 'V1', 'V2', 'V3'], [f'P{i}' for i in range(30)])
    assert torch.isfinite(ret['sim']).all()
    # 查询里混入一个 train 患者（id 相同、顺序不同）：只屏蔽它自己那一格
    ret2 = op.retrieve({m: v[[7, 3]] for m, v in zv.items()}, zv, 5, 0.1, 'per_modality_mean_cos',
                       ['P7', 'P3'], [f'P{i}' for i in range(30)])
    assert torch.isneginf(ret2['sim'][0, 7]) and torch.isneginf(ret2['sim'][1, 3])
    assert int(torch.isneginf(ret2['sim']).sum()) == 2


def test_similarity_modes():
    a = {'rna': torch.tensor([[1.0, 0.0]]), 'wsi': torch.tensor([[10.0, 0.0]])}
    b = {'rna': torch.tensor([[0.0, 1.0]]), 'wsi': torch.tensor([[10.0, 0.0]])}
    assert float(op.similarity(a, b)) == pytest.approx(0.5)               # (0 + 1) / 2：逐模态等权
    c = float(op.similarity(a, b, 'concat_cos'))                           # 高范数 wsi 主导
    assert c == pytest.approx(100.0 / (101 ** 0.5 * 101 ** 0.5))
    with pytest.raises(ValueError):
        op.similarity(a, {'rna': b['rna']})


def test_gate_stats_and_alpha_range():
    p, _, _ = synth(n=30)
    model, x = build(p)
    zv = fixed_latent(p, model, x)['z_vis']['rna+text']
    st = op.gate_stats(zv)
    sim = op.similarity(zv, zv).clone()
    sim.fill_diagonal_(float('-inf'))
    s1 = sim.max(1).values.double()
    assert st['delta'] == pytest.approx(float(s1.median() if len(s1) % 2 else s1.quantile(0.5)), abs=1e-6)
    assert 5.0 <= st['gamma'] <= 30.0
    a = op.gate_alpha(torch.linspace(-1, 1, 50), 0.5, st['delta'], st['gamma'])
    assert a.shape == (50, 1) and float(a.min()) >= 0 and float(a.max()) <= 0.5
    assert torch.equal(op.gate_alpha(torch.linspace(-1, 1, 5), 0.5, 0.0, 10.0, gated=False), torch.full((5, 1), 0.5))
    st_nomask = op.gate_stats(zv, exclude_self=False)
    assert st_nomask['delta'] == pytest.approx(1.0, abs=1e-5)             # 不掩码时最近邻永远是自己
    assert op.gate_stats(zv, gamma_mode='fixed_10')['gamma'] == 10.0


def test_topk_rejects_K_beyond_anchors():
    sim = torch.rand(3, 4)
    sim.fill_diagonal_(float('-inf'))
    op.topk_attention(sim, 3, 0.1)
    with pytest.raises(ValueError):
        op.topk_attention(sim, 4, 0.1)


# ---------------------------------------------------------------- Ridge 精确留一

@pytest.mark.parametrize('n,p_dim', [(25, 6), (12, 30)])          # 原始与对偶形式
def test_ridge_loo_matches_brute_force(n, p_dim):
    g = torch.Generator().manual_seed(3)
    X = torch.randn(n, p_dim, generator=g, dtype=torch.float64)
    Y = torch.randn(n, 3, generator=g, dtype=torch.float64)
    e, _ = op.ridge_loo_residuals(X, Y, 0.7)
    for j in range(n):
        keep = [i for i in range(n) if i != j]
        fit = op.ridge_fit(X[keep], Y[keep], 0.7)
        brute = Y[j] - op.ridge_predict(fit, X[j:j + 1])[0]
        assert torch.allclose(e[j].double(), brute, atol=1e-5), j


def test_ridge_dual_equals_primal():
    g = torch.Generator().manual_seed(4)
    X = torch.randn(20, 15, generator=g, dtype=torch.float64)
    Y = torch.randn(20, 2, generator=g, dtype=torch.float64)
    f1 = op.ridge_fit(X, Y, 2.0)
    Xp = torch.cat([X, torch.zeros(20, 10, dtype=torch.float64)], 1)       # 加零列 → p > n，走对偶
    f2 = op.ridge_fit(Xp, Y, 2.0)
    assert not f2['primal']
    assert torch.allclose(op.ridge_predict(f1, X), op.ridge_predict(f2, Xp), atol=1e-9)
    assert torch.allclose(op.ridge_hat_diag(f1), op.ridge_hat_diag(f2), atol=1e-9)


# ---------------------------------------------------------------- B3 / B5

def test_b3_and_b5_formulas():
    zt = torch.tensor([[1.0, 0.0], [0.0, 1.0], [5.0, 5.0]])
    idx = torch.tensor([[0, 1]])
    w = torch.tensor([[0.25, 0.75]])
    assert torch.allclose(op.b3_aggregate(zt, idx, w), torch.tensor([[0.25, 0.75]]))
    zq = {'rna': torch.tensor([[2.0, 0.0]]), 'wsi': torch.tensor([[0.0, 2.0]])}
    maps = {'rna': lambda z: z, 'wsi': lambda z: 2 * z}
    out = op.b5_map_precision(zq, maps, {'rna': 1.0, 'wsi': 0.5}, 1.0)     # τ = 1, 2
    assert torch.allclose(out, (1 * zq['rna'] + 2 * 2 * zq['wsi']) / (1 + 1 + 2))
    out2 = op.b5_direct_coord(zq, {'rna': 2.0, 'wsi': 2.0}, 1.0)           # τ = 0.5, 0.5
    assert torch.allclose(out2, (0.5 * zq['rna'] + 0.5 * zq['wsi']) / 2.0)
