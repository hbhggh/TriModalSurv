"""I07 接口契约（用户 2026-10-11 裁决 A：契约按 I07 实际形状写死，超参数集中在 config.yaml）。

无论谁来改代码，都只能在这份契约里填空；不符合即在入口报错，不静默继续。

输入（data.Part，三模态形状不同，不压成一个 [B, M, F] 张量，否则会丢掉 token 级跨模态注意力）：
  patient_ids  list[str]           长度 N，不重复
  wsi          float32 [N, 128, 1536]
  wsi_mask     bool    [N, 128]    True = 真实 token；每人至少 1 个
  rna          float32 [N, G]      G = 基因数（已按训练集 z-score）
  text         float32 [N, F, 768] F = 该癌种字段数
  text_nm      bool    [N, F]      True = not mentioned
  time         float32 [N]         生存/随访月数，有限且 ≥ 0
  event        float32 [N]         只取 0/1；1 = 死亡（观察到事件）。全仓库不用 censorship 记法（与 event 反号）
输出（PS3Style.forward）：dict，键恰为 {'risk', 'pooled'}
  risk    float [N]，有限；越大 = 预后越差（Cox 部分似然与 Harrell C-index 都按这个方向）
  pooled  {模态: 有限浮点 [N, d]}，只含本次实际输入的模态，各模态 d 相同
超参数：config.yaml，键恰为 CONFIG_TYPES，类型严格（YAML 里 1e-4 会被读成字符串，必须写 1.0e-4）。
"""
from __future__ import annotations

import dataclasses
import hashlib
import math
from pathlib import Path

import torch

WSI_TOKENS, WSI_DIM, TEXT_DIM = 128, 1536, 768
PART_FIELDS = ('patient_ids', 'wsi', 'wsi_mask', 'rna', 'text', 'text_nm', 'time', 'event')
OUTPUT_KEYS = frozenset({'risk', 'pooled'})
CONFIG_PATH = Path(__file__).resolve().parent / 'config.yaml'
CONFIG_TYPES = {'d': int, 'lr': float, 'weight_decay': float, 'batch_size': int, 'epochs': int, 'dropout': float,
                'seed': int}
EPOCH_CHOICES = (50, 100)


class ContractError(ValueError):
    pass


def _need(ok, msg):
    if not ok:
        raise ContractError(msg)


def _tensor(name, x, dtype, shape):
    _need(isinstance(x, torch.Tensor), f'{name} 必须是 torch.Tensor，实际 {type(x).__name__}')
    _need(x.dtype == dtype, f'{name} 的 dtype 必须是 {dtype}，实际 {x.dtype}')
    _need(x.dim() == len(shape) and all(s is None or a == s for a, s in zip(x.shape, shape)),
          f'{name} 的形状必须是 {list(shape)}（None 为任意），实际 {list(x.shape)}')


def check_part(part, n_genes=None, n_fields=None):
    """在训练 / 评估入口核对一个数据部分；只在入口调用（含一次设备同步），不进 step 热循环。"""
    names = tuple(f.name for f in dataclasses.fields(part))
    _need(names == PART_FIELDS, f'Part 字段必须是 {PART_FIELDS}，实际 {names}')
    n = len(part.patient_ids)
    _need(n > 0 and len(set(part.patient_ids)) == n, 'patient_ids 为空或有重复')
    _tensor('wsi', part.wsi, torch.float32, (n, WSI_TOKENS, WSI_DIM))
    _tensor('wsi_mask', part.wsi_mask, torch.bool, (n, WSI_TOKENS))
    _tensor('rna', part.rna, torch.float32, (n, n_genes))
    _tensor('text', part.text, torch.float32, (n, n_fields, TEXT_DIM))
    _tensor('text_nm', part.text_nm, torch.bool, (n, part.text.shape[1]))
    _tensor('time', part.time, torch.float32, (n,))
    _tensor('event', part.event, torch.float32, (n,))
    _need(bool(part.wsi_mask.any(1).all()), 'wsi_mask 有病人没有任何真实 token')
    for name in ('wsi', 'rna', 'text', 'time'):
        _need(bool(torch.isfinite(getattr(part, name)).all()), f'{name} 含 NaN / Inf')
    _need(bool((part.time >= 0).all()), 'time 有负值')
    _need(bool(((part.event == 0) | (part.event == 1)).all()), 'event 只能取 0/1（1 = 死亡）')


def check_output(out, n, modalities):
    """核对一次前向的输出；在验证与评估处调用（epoch 边界，非 step 热循环）。"""
    _need(isinstance(out, dict) and set(out) == OUTPUT_KEYS, f'模型输出必须是键为 {sorted(OUTPUT_KEYS)} 的 dict')
    risk = out['risk']
    _need(isinstance(risk, torch.Tensor) and risk.is_floating_point() and tuple(risk.shape) == (n,),
          f'risk 必须是浮点 [N={n}]，实际 {getattr(risk, "shape", type(risk))}')
    _need(bool(torch.isfinite(risk).all()), 'risk 含 NaN / Inf')
    pooled = out['pooled']
    _need(isinstance(pooled, dict) and set(pooled) == set(modalities),
          f'pooled 的模态必须是 {sorted(modalities)}，实际 {sorted(pooled) if isinstance(pooled, dict) else type(pooled).__name__}')
    dims = set()
    for m, v in pooled.items():
        _need(isinstance(v, torch.Tensor) and v.is_floating_point() and v.dim() == 2 and v.shape[0] == n,
              f'pooled[{m}] 必须是浮点 [N={n}, d]，实际 {getattr(v, "shape", type(v).__name__)}')
        _need(bool(torch.isfinite(v).all()), f'pooled[{m}] 含 NaN / Inf')
        dims.add(v.shape[1])
    _need(len(dims) == 1, f'pooled 各模态的 d 不一致：{sorted(dims)}')


def check_config(cfg):
    _need(isinstance(cfg, dict) and set(cfg) == set(CONFIG_TYPES),
          f'超参数键必须恰为 {sorted(CONFIG_TYPES)}，实际 {sorted(cfg) if isinstance(cfg, dict) else type(cfg).__name__}')
    for k, t in CONFIG_TYPES.items():
        v = cfg[k]
        _need(type(v) is t, f'超参数 {k} 必须是 {t.__name__}，实际 {type(v).__name__}（{v!r}）')
        if t is float:
            _need(math.isfinite(v), f'超参数 {k} 不是有限数')
    _need(cfg['epochs'] in EPOCH_CHOICES, f'epochs 只能取 {EPOCH_CHOICES}')
    _need(cfg['d'] > 0 and cfg['batch_size'] > 1 and 0.0 <= cfg['dropout'] < 1.0 and cfg['lr'] > 0
          and cfg['weight_decay'] >= 0, f'超参数取值越界：{cfg}')
    return cfg


def load_config(path=CONFIG_PATH):
    """返回 (cfg, sha256)。"""
    import yaml
    raw = Path(path).read_bytes()
    return check_config(yaml.safe_load(raw)), hashlib.sha256(raw).hexdigest()
