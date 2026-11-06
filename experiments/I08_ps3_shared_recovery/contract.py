"""I08 接口契约：A1 + B1 + C1 接在冻结的 I07 pooled 与风险头之间（故事线 A-1 v1，interface.md）。

只定义"填空的格子"，不含训练逻辑。之后的实现在入口与 epoch 边界调用这里的检查，违约即报错，不静默继续：
  check_config      config.yaml 的键、类型、取值（嵌套逐节核对）
  patterns          六种缺失模式 Ω 及其缺失目标 u，顺序固定为 I07 的 MODALITIES
  n_params          A / B 参数量（r = 32 时 24,576 + 12,576 = 37,152）
  check_tensor      按 config.tensors 的符号形状核对张量（B 任意，d、r、k 代入）
  assemble_head_in  按 rna|wsi|text 拼接：可见位用 p^Ω 原样，缺失位用 p̂；顺序错、漏位、多位都报错
  check_frozen      I07 必须 eval() 且全部参数 requires_grad=False
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
    'operator_C': {'name': str, 'inference': bool, 'lambda_modal': float, 'lambda_cons': float, 'cos_eps': float,
                   'stop_grad_target': bool},
    'loss': {'cox': str, 'lambda_anchor': float},
    'train': {'optimizer': str, 'lr': float, 'weight_decay': float, 'batch': str, 'max_epochs': int,
              'select_metric': str, 'seed': int, 'candidates': dict, 'test_access': bool},
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
    ('ablations',): ['wo_A', 'wo_B', 'wo_C'],
}
TENSOR_NAMES = ('p_full', 'p_vis', 'mu_full', 'mu_pattern', 'U', 'z_vis', 'z_full', 'b_in', 'R', 'bias', 'z_hat',
                'p_hat', 'head_in', 'risk')
SYMBOLS = ('B', 'd', 'r', 'k*r', 'head_in')


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
    ts = cfg['tensors']
    _need(tuple(ts) == TENSOR_NAMES, f'tensors 必须按顺序恰为 {TENSOR_NAMES}，实际 {tuple(ts)}')
    for name, s in ts.items():
        _need(isinstance(s, dict) and set(s) == {'shape', 'dtype', 'at', 'grad'}, f'tensors.{name} 键不对')
        _need(isinstance(s['shape'], list) and all(x in SYMBOLS for x in s['shape']),
              f'tensors.{name}.shape 只能用符号 {SYMBOLS}，实际 {s["shape"]}')
        _need(s['dtype'] in DTYPES and _typed(s['grad'], bool) and _typed(s['at'], str), f'tensors.{name} 取值不对')


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


def tensor_shape(cfg, name, k=None):
    """把 config.tensors[name].shape 的符号代入成具体形状；B 记为 None（任意）。"""
    sub = {'B': None, 'd': cfg['backbone']['d'], 'r': cfg['operator_A']['r'], 'head_in': cfg['backbone']['head_in']}
    shape = cfg['tensors'][name]['shape']
    if 'k*r' in shape:
        _need(k in (1, 2), f'{name} 的形状含 k，必须给出 k ∈ {{1, 2}}，实际 {k!r}')
        sub['k*r'] = k * sub['r']
    return tuple(sub[s] for s in shape)


def check_tensor(cfg, name, x, k=None):
    """入口 / epoch 边界调用（含一次设备同步），不进 step 热循环。"""
    want = tensor_shape(cfg, name, k)
    dtype = DTYPES[cfg['tensors'][name]['dtype']]
    _need(isinstance(x, torch.Tensor), f'{name} 必须是 torch.Tensor，实际 {type(x).__name__}')
    _need(x.dtype == dtype, f'{name} 的 dtype 必须是 {dtype}，实际 {x.dtype}')
    _need(x.dim() == len(want) and all(w is None or a == w for a, w in zip(x.shape, want)),
          f'{name} 的形状必须是 {list(want)}（None 为任意），实际 {list(x.shape)}')
    _need(bool(torch.isfinite(x).all()), f'{name} 含 NaN / Inf')


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
