"""I08 接口契约：A1 + B1/B6-LOO/B5/B3 + C1 接在冻结的 I07 pooled 与风险头之间（故事线 A-1 v1，interface.md；
规范：主目录 患者级动态恢复_v1.handoff.md 第五节）。

只定义"填空的格子"，不含训练逻辑。之后的实现在入口与 epoch 边界调用这里的检查，违约即报错，不静默继续：
  check_config      config.yaml 的键、类型、取值（嵌套逐节核对）
  patterns          六种缺失模式 Ω 及其缺失目标 u，顺序固定为 I07 的 MODALITIES
  n_params          A / B 参数量（r = 32 时 24,576 + 12,576 = 37,152）
  check_tensor      按 config.tensors 的符号形状核对张量（B 任意，d、r、k 代入）
  assemble_head_in  按 rna|wsi|text 拼接：可见位用 p^Ω 原样，缺失位用 p̂；顺序错、漏位、多位都报错
  check_frozen      I07 必须 eval() 且全部参数 requires_grad=False
  check_b6_no_self_leak  B6 检索：查询与 train 同一患者的相似度必须是 -inf，Top-K 邻居不得含自身
"""
from __future__ import annotations

import hashlib
import itertools
import math
from pathlib import Path

import torch

from experiments.I07_ps3style_backbone.model import MODALITIES

CONFIG_PATH = Path(__file__).resolve().parent / 'config.yaml'
VIEWS = ('full',) + tuple('+'.join(c) for k in (1, 2) for c in itertools.combinations(MODALITIES, k))
PATTERNS = VIEWS[1:]                                   # 六种缺失模式 = 可见模态集合 Ω
DTYPES = {'float32': torch.float32}

# 嵌套 schema：节 → {键: 类型}。list 的元素类型另在 _check_values 里核对。
SCHEMA = {
    'backbone': {'experiment': str, 'results_run': str, 'arm': str, 'frozen': bool, 'modalities': list, 'd': int,
                 'head_in': int, 'cancers': list, 'folds': list},
    'position': {'insert_after': str, 'insert_before': str, 'full_route': str, 'visible_route': str,
                 'missing_route': str},
    'features': {'dtype': str, 'views': list, 'splits': list, 'mean_source': str, 'input_mean': str},
    'operator_A': {'name': str, 'r': int, 'per_modality': bool, 'parametrization': str, 'init': str,
                   'orth_tol': float},
    'operator_B': {'name': str, 'patterns': list, 'input_order': str, 'bias': bool, 'residual_generation': bool},
    'operator_B_variants': {'active': str, 'coupling_mode': str, 'B6_LOO': dict, 'B6_Naive': dict, 'B3': dict,
                            'B5': dict},
    'operator_C': {'name': str, 'inference': bool, 'lambda_modal': float, 'lambda_cons': float, 'cos_eps': float,
                   'stop_grad_target': bool},
    'loss': {'cox': str, 'lambda_anchor': float},
    'train': {'optimizer': str, 'lr': float, 'weight_decay': float, 'batch': str, 'max_epochs': int,
              'select_metric': str, 'seed': int, 'candidates': dict, 'ridge_alphas': list, 'ridge_default': float,
              'test_access': bool},
    'interpretability': {'bootstrap_n': int, 'bootstrap_frac': float, 'seed': int, 'mechanism_ridge': float},
    'controls': list,
    'ablations': list,
    'tensors': dict,
}
FIXED = {   # 由故事线约束钉死的取值；改它们等于改研究口径，须新版本 index + 审查
    ('backbone', 'experiment'): 'I07_ps3style_backbone', ('backbone', 'arm'): 'tri', ('backbone', 'frozen'): True,
    ('backbone', 'modalities'): list(MODALITIES),
    ('position', 'insert_after'): 'pooled', ('position', 'insert_before'): 'risk_head',
    ('position', 'full_route'): 'bypass', ('position', 'visible_route'): 'passthrough',
    ('position', 'missing_route'): 'recovered',
    ('features', 'dtype'): 'float32', ('features', 'views'): list(VIEWS), ('features', 'splits'): ['train', 'val'],
    ('features', 'mean_source'): 'train', ('features', 'input_mean'): 'pattern',
    ('operator_A', 'per_modality'): True, ('operator_A', 'parametrization'): 'orthogonal',
    ('operator_B', 'patterns'): list(PATTERNS), ('operator_B', 'input_order'): 'modalities',
    ('operator_B', 'residual_generation'): False,
    ('operator_C', 'inference'): False, ('operator_C', 'stop_grad_target'): True,
    ('loss', 'cox'): 'missing_pattern_mean', ('train', 'batch'): 'full',
    ('train', 'select_metric'): 'val_cox_missing_mean', ('train', 'test_access'): False,
    ('controls',): ['zero', 'train_mean', 'ridge_full_B0', 'ridge_risk_residual_C0'],
    ('ablations',): ['wo_A', 'wo_B', 'wo_C_for_B1', 'wo_L_modal_for_B1', 'wo_L_cons_for_B1', 'wo_C_for_B6',
                     'pca32_A5_for_B6', 'B3_direct_neighbor', 'B5_map_precision', 'B5_direct_coord',
                     'B6_naive_no_loo_or_gate', 'B6_loo_exact_hat'],
    ('operator_B_variants', 'coupling_mode'): 'plugin_after_b1',
    ('operator_B_variants', 'B6_LOO', 'exclude_self_in_train'): True,
    ('operator_B_variants', 'B6_LOO', 'supported_residual_modes'): ['in_fold_masked', 'exact_loo_hat'],
    ('operator_B_variants', 'B6_LOO', 'supported_sim_modes'): ['per_modality_mean_cos', 'concat_cos'],
    ('operator_B_variants', 'B6_LOO', 'gate_delta_source'): 'train_loo_nn_median',
    ('operator_B_variants', 'B6_Naive'): {'gate': 'none', 'self_mask_in_gate_stats': False},
    ('operator_B_variants', 'B3', 'exclude_self_in_train'): True,
    ('operator_B_variants', 'B5', 'modes'): ['B5_MapPrecision', 'B5_DirectCoord'],
}
B_VARIANTS = ('B1', 'B3', 'B5_MapPrecision', 'B5_DirectCoord', 'B6_Naive', 'B6_LOO')
B6_SPEC = {'residual_mode': str, 'supported_residual_modes': list, 'ridge_lam_for_hat': float, 'sim_mode': str,
           'supported_sim_modes': list, 'exclude_self_in_train': bool, 'K': int, 'tau': float, 'alpha_max': float,
           'gate_delta_source': str, 'gate_gamma_mode': str, 'candidates': dict}
B3_SPEC = {'K': int, 'tau': float, 'sim_mode': str, 'exclude_self_in_train': bool}
B5_SPEC = {'modes': list, 'var_eps': float}
GAMMA_MODES = ('iqr_scaled', 'fixed_10')
SELF_LEAK_MAX = -1e8        # 自查询位的相似度必须 ≤ 此值（-inf 或被压到极小）
TENSOR_NAMES = ('p_full', 'p_vis', 'mu_full', 'mu_pattern', 'U', 'z_vis', 'z_full', 'b_in', 'R', 'bias', 'e_pool',
                'sim_mat', 'attn_w', 'alpha_gate', 'z_hat', 'p_hat', 'head_in', 'risk')
SYMBOLS = ('B', 'd', 'r', 'k*r', 'head_in', 'N_tr', 'K', 1)   # 1 是整数字面量（YAML [B, 1] 读成 int）


class ContractError(ValueError):
    pass


def _need(ok, msg):
    if not ok:
        raise ContractError(msg)


def _typed(v, t):
    return type(v) is t


def _get(cfg, path):
    v = cfg
    for k in path:
        v = v[k]
    return v


def check_config(cfg):
    _need(isinstance(cfg, dict) and set(cfg) == set(SCHEMA),
          f'config 顶层键必须恰为 {sorted(SCHEMA)}，实际 {sorted(cfg) if isinstance(cfg, dict) else type(cfg).__name__}')
    for sec, spec in SCHEMA.items():
        if isinstance(spec, dict):
            _need(isinstance(cfg[sec], dict) and set(cfg[sec]) == set(spec),
                  f'{sec} 的键必须恰为 {sorted(spec)}，实际 {sorted(cfg[sec]) if isinstance(cfg[sec], dict) else cfg[sec]!r}')
            for k, t in spec.items():
                v = cfg[sec][k]
                _need(_typed(v, t), f'{sec}.{k} 必须是 {t.__name__}，实际 {type(v).__name__}（{v!r}）')
                if t is float:
                    _need(math.isfinite(v), f'{sec}.{k} 不是有限数')
        else:
            _need(_typed(cfg[sec], spec), f'{sec} 必须是 {spec.__name__}')
    for path, want in FIXED.items():
        _need(_get(cfg, path) == want, f'{".".join(path)} 被钉死为 {want!r}，实际 {_get(cfg, path)!r}')
    _check_values(cfg)
    return cfg


def _check_values(cfg):
    bb, A, C, tr = cfg['backbone'], cfg['operator_A'], cfg['operator_C'], cfg['train']
    _need(bb['d'] > 0 and bb['head_in'] == bb['d'] * len(MODALITIES), f'head_in 必须等于 3·d，实际 {bb["head_in"]}')
    _need(all(_typed(f, int) for f in bb['folds']) and sorted(set(bb['folds'])) == bb['folds'], 'folds 必须是升序不重复的 int')
    _need(all(_typed(c, str) for c in bb['cancers']) and len(set(bb['cancers'])) == len(bb['cancers']), 'cancers 重复')
    _need(0 < A['r'] < bb['d'], f'r 必须在 (0, d) 内，实际 {A["r"]}')
    _need(0 < A['orth_tol'] < 1e-2 and 0 < C['cos_eps'] < 1e-3, 'orth_tol / cos_eps 越界')
    for k in ('lambda_modal', 'lambda_cons'):
        _need(C[k] >= 0, f'operator_C.{k} 必须 ≥ 0')
    _need(cfg['loss']['lambda_anchor'] >= 0, 'lambda_anchor 必须 ≥ 0')
    _need(tr['lr'] > 0 and tr['weight_decay'] >= 0 and tr['max_epochs'] > 0, 'train 取值越界')
    cand = tr['candidates']
    _need(set(cand) == {'r', 'lambda_modal'}, f'candidates 只允许 r 与 lambda_modal，实际 {sorted(cand)}')
    _need(all(_typed(x, int) and 0 < x < bb['d'] for x in cand['r']), 'candidates.r 必须是 (0, d) 内的 int')
    _need(all(_typed(x, float) and x >= 0 for x in cand['lambda_modal']), 'candidates.lambda_modal 必须是 ≥0 的 float')
    _need(A['r'] in cand['r'] and C['lambda_modal'] in cand['lambda_modal'], '默认 r / lambda_modal 必须在候选网格内')
    ra = tr['ridge_alphas']
    _need(len(ra) > 0 and all(_typed(x, float) and x > 0 for x in ra), 'ridge_alphas 必须是 >0 的 float 列表')
    _need(tr['ridge_default'] in ra, 'ridge_default 必须在 ridge_alphas 内')
    _check_b_variants(cfg['operator_B_variants'], A['r'])
    it = cfg['interpretability']
    _need(it['bootstrap_n'] > 0 and 0.0 < it['bootstrap_frac'] < 1.0 and it['mechanism_ridge'] > 0,
          'interpretability 取值越界')
    ts = cfg['tensors']
    _need(tuple(ts) == TENSOR_NAMES, f'tensors 必须按顺序恰为 {TENSOR_NAMES}，实际 {tuple(ts)}')
    for name, s in ts.items():
        _need(isinstance(s, dict) and set(s) == {'shape', 'dtype', 'at', 'grad'}, f'tensors.{name} 键不对')
        _need(isinstance(s['shape'], list) and all(any(x == y and type(x) is type(y) for y in SYMBOLS) for x in s['shape']),
              f'tensors.{name}.shape 只能用符号 {SYMBOLS}，实际 {s["shape"]}')
        _need(s['dtype'] in DTYPES and _typed(s['grad'], bool) and _typed(s['at'], str), f'tensors.{name} 取值不对')


def _check_b_variants(bv, r):
    _need(bv['active'] in B_VARIANTS, f'operator_B_variants.active 只能取 {B_VARIANTS}，实际 {bv["active"]!r}')
    b6 = bv['B6_LOO']
    _need(isinstance(b6, dict) and set(b6) == set(B6_SPEC), f'B6_LOO 的键必须恰为 {sorted(B6_SPEC)}')
    for k, t in B6_SPEC.items():
        _need(_typed(b6[k], t), f'B6_LOO.{k} 必须是 {t.__name__}，实际 {type(b6[k]).__name__}（{b6[k]!r}）')
    _need(b6['residual_mode'] in b6['supported_residual_modes'], 'B6_LOO.residual_mode 不在支持列表')
    _need(b6['sim_mode'] in b6['supported_sim_modes'], 'B6_LOO.sim_mode 不在支持列表')
    _need(b6['gate_gamma_mode'] in GAMMA_MODES, f'gate_gamma_mode 只能取 {GAMMA_MODES}')
    _need(b6['ridge_lam_for_hat'] > 0, 'ridge_lam_for_hat 必须 > 0')
    cand = b6['candidates']
    _need(set(cand) == {'K', 'tau', 'alpha_max'}, f'B6_LOO.candidates 只允许 K / tau / alpha_max，实际 {sorted(cand)}')
    _need(all(_typed(x, int) and x >= 1 for x in cand['K']), 'candidates.K 必须是 ≥1 的 int')
    _need(all(_typed(x, float) and x > 0 for x in cand['tau']), 'candidates.tau 必须是 >0 的 float')
    _need(all(_typed(x, float) and x >= 0 for x in cand['alpha_max']), 'candidates.alpha_max 必须是 ≥0 的 float')
    _need(0.0 in cand['alpha_max'], 'candidates.alpha_max 必须含 0.0（精确退化回 B1 的保底格点）')
    for k in ('K', 'tau', 'alpha_max'):
        _need(b6[k] in cand[k], f'B6_LOO.{k} 的默认值 {b6[k]!r} 必须在 candidates.{k} 内')
    b3 = bv['B3']
    _need(isinstance(b3, dict) and set(b3) == set(B3_SPEC), f'B3 的键必须恰为 {sorted(B3_SPEC)}')
    for k, t in B3_SPEC.items():
        _need(_typed(b3[k], t), f'B3.{k} 必须是 {t.__name__}')
    _need(b3['K'] >= 1 and b3['tau'] > 0 and b3['sim_mode'] in b6['supported_sim_modes'], 'B3 取值越界')
    b5 = bv['B5']
    _need(isinstance(b5, dict) and set(b5) == set(B5_SPEC), f'B5 的键必须恰为 {sorted(B5_SPEC)}')
    _need(_typed(b5['var_eps'], float) and 0 < b5['var_eps'] < 1e-2, 'B5.var_eps 越界')


def check_b6_no_self_leak(sim_mat, query_ids, train_ids, topk_idx=None):
    """B6 / B3 检索守卫：query 与 train 同一 patient_id 的位置 (i, j) 上相似度必须 ≤ -1e8（-inf），
    且给出 topk_idx 时，每个查询的邻居下标绝不指向自身。没有重叠患者时只核对形状。"""
    _need(isinstance(sim_mat, torch.Tensor) and sim_mat.dim() == 2, 'sim_mat 必须是二维张量')
    _need(tuple(sim_mat.shape) == (len(query_ids), len(train_ids)),
          f'sim_mat 形状 {list(sim_mat.shape)} 与 query/train 患者数 ({len(query_ids)}, {len(train_ids)}) 不符')
    _need(len(set(train_ids)) == len(train_ids), 'train_ids 有重复')
    col = {p: j for j, p in enumerate(train_ids)}
    pairs = [(i, col[p]) for i, p in enumerate(query_ids) if p in col]
    for i, j in pairs:
        v = float(sim_mat[i, j])
        _need(v <= SELF_LEAK_MAX, f'自查询泄漏：查询 {query_ids[i]} 与自身的相似度为 {v}，未被置为 -inf')
    if topk_idx is not None:
        _need(isinstance(topk_idx, torch.Tensor) and topk_idx.dim() == 2 and topk_idx.shape[0] == len(query_ids),
              'topk_idx 必须是 [B, K] 张量')
        for i, j in pairs:
            _need(not bool((topk_idx[i] == j).any()), f'自查询泄漏：查询 {query_ids[i]} 的 Top-K 邻居包含自身')
    return len(pairs)


def load_config(path=CONFIG_PATH):
    """返回 (cfg, sha256)。"""
    import yaml
    raw = Path(path).read_bytes()
    return check_config(yaml.safe_load(raw)), hashlib.sha256(raw).hexdigest()


def visible(pattern):
    _need(pattern in PATTERNS, f'未知缺失模式 {pattern!r}，只允许 {PATTERNS}')
    return tuple(pattern.split('+'))


def targets(pattern):
    """该模式下要恢复的缺失模态 u，按 MODALITIES 顺序。"""
    vis = visible(pattern)
    return tuple(m for m in MODALITIES if m not in vis)


def n_params(d, r):
    """A：每模态 d·r；B：每个 (Ω, u) 一个 R ∈ R^{r × k·r} 加 bias r。"""
    a = len(MODALITIES) * d * r
    b = sum(len(targets(p)) * (r * len(visible(p)) * r + r) for p in PATTERNS)
    return {'A': a, 'B': b, 'total': a + b}


def tensor_shape(cfg, name, k=None, n_tr=None, K=None, r=None):
    """把 config.tensors[name].shape 的符号代入成具体形状；B 记为 None（任意）。
    r 缺省取 operator_A.r（候选网格里的其他 r 须显式传入）；含 N_tr / K 的张量必须给出 n_tr / K。"""
    rr = cfg['operator_A']['r'] if r is None else r
    sub = {'B': None, 'd': cfg['backbone']['d'], 'r': rr, 'head_in': cfg['backbone']['head_in'], 1: 1}
    shape = cfg['tensors'][name]['shape']
    if 'k*r' in shape:
        _need(k in (1, 2), f'{name} 的形状含 k，必须给出 k ∈ {{1, 2}}，实际 {k!r}')
        sub['k*r'] = k * rr
    if 'N_tr' in shape:
        _need(_typed(n_tr, int) and n_tr > 1, f'{name} 的形状含 N_tr，必须给出 n_tr > 1，实际 {n_tr!r}')
        sub['N_tr'] = n_tr
    if 'K' in shape:
        _need(_typed(K, int) and K >= 1, f'{name} 的形状含 K，必须给出 K ≥ 1，实际 {K!r}')
        sub['K'] = K
    return tuple(sub[s] for s in shape)


def check_tensor(cfg, name, x, k=None, n_tr=None, K=None, r=None, allow_neg_inf=False):
    """入口 / epoch 边界调用（含一次设备同步），不进 step 热循环。allow_neg_inf 只给 sim_mat（自查询位为 -inf）。"""
    want = tensor_shape(cfg, name, k, n_tr, K, r)
    dtype = DTYPES[cfg['tensors'][name]['dtype']]
    _need(isinstance(x, torch.Tensor), f'{name} 必须是 torch.Tensor，实际 {type(x).__name__}')
    _need(x.dtype == dtype, f'{name} 的 dtype 必须是 {dtype}，实际 {x.dtype}')
    _need(x.dim() == len(want) and all(w is None or a == w for a, w in zip(x.shape, want)),
          f'{name} 的形状必须是 {list(want)}（None 为任意），实际 {list(x.shape)}')
    ok = torch.isfinite(x) | (torch.isneginf(x) if allow_neg_inf else torch.zeros_like(x, dtype=torch.bool))
    _need(bool(ok.all()), f'{name} 含 NaN / Inf')


def assemble_head_in(pattern, p_vis, p_hat):
    """按 rna|wsi|text 拼风险头输入：可见位用 p^Ω（原样，W1-4），缺失位用 p̂。键必须恰好对上 Ω 与 u。"""
    vis, tgt = visible(pattern), targets(pattern)
    _need(set(p_vis) == set(vis), f'{pattern}：p_vis 的模态必须恰为 {vis}，实际 {sorted(p_vis)}')
    _need(set(p_hat) == set(tgt), f'{pattern}：p_hat 的模态必须恰为 {tgt}，实际 {sorted(p_hat)}')
    return torch.cat([p_vis[m] if m in vis else p_hat[m] for m in MODALITIES], dim=-1)


def check_frozen(backbone):
    _need(not backbone.training, 'I07 骨架必须处于 eval()（dropout 关闭），否则 p^Ω 随机')
    live = [n for n, p in backbone.named_parameters() if p.requires_grad]
    _need(not live, f'I07 骨架有参数未冻结：{live[:5]}')
