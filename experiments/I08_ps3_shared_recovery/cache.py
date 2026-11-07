"""I08 Step 1：冻结 I07 前向一次，导出 7 种 present 视角的 pooled 静态缓存（handoff v1 §2、§7 Step 2）。

- 只加载、只前向 train 与 val（load_fold(parts=('train', 'val'))，并在入口与写出前各断言一次）；test 分割从不读取。
- ckpt：i07-ps3-20261011 的 tri 臂 best.pt；字节只读一次，sha256 必须等于仓库内 checkpoint-sha256.txt 的登记值，
  再从同一份字节解析（V43）；run.json 的 config 经 I07 contract.check_config。骨架 eval()、全部 requires_grad=False，
  过 contract.check_frozen。
- D0 守卫（写出前，逐患者最大绝对误差 < 1e-6）：① 缓存 p^F 拼接过冻结风险头 = I07 完整前向风险；
  ② 每种缺失模式下 p^Ω 可见位 + 缺失位填 0 过风险头 = I07 缺失前向（fill=0）风险；③ 同一视角两次前向逐值相等（确定性）。
- 每个 (癌种, 折) 一个 npz；manifest.json 记录每个 npz 的 sha256、ckpt / run.json 哈希、源码身份与 D0 误差。
  读取（load_fold_cache）同样只读一次字节、按 manifest 核对后从这份字节解析。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

from experiments.I07_ps3style_backbone import contract as i07_contract
from experiments.I07_ps3style_backbone.data import load_fold
from experiments.I07_ps3style_backbone.model import MODALITIES

from . import contract
from .contract import PATTERNS, VIEWS, targets, visible

SPLITS = ('train', 'val')
D0_TOL = 1e-6
EXP = Path(__file__).resolve().parent
ROOT = EXP.parents[1]
I07_EXP = ROOT / 'experiments' / 'I07_ps3style_backbone'
CKPT_LIST = I07_EXP / 'results' / 'i07-ps3-20261011' / 'checkpoint-sha256.txt'
SOURCES = [EXP / f for f in ('__init__.py', 'contract.py', 'config.yaml', 'cache.py', 'operators.py', 'losses.py',
                             'train_eval.py', 'interpretability.py')] + \
          [I07_EXP / f for f in ('model.py', 'data.py', 'survival.py', 'contract.py', 'provenance.py', 'train.py')]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def source_identity(expected_commit: str) -> dict:
    """I08 + 所用 I07 源码的身份门：有 .git 读 HEAD，否则读 GIT_STAMP.json；dirty 或 commit 不符即拒绝。"""
    if str(ROOT / 'src') not in sys.path:
        sys.path.insert(0, str(ROOT / 'src'))
    from trimodalsurv import gitstamp
    from trimodalsurv.config import file_fingerprint
    ident = gitstamp.require_git_identity([file_fingerprint(p) for p in SOURCES], allow_dirty=False, root=ROOT)
    if ident.get('commit') is None or ident.get('dirty') or ident.get('allow_dirty'):
        raise PermissionError(f'需要干净的源码身份：{ident.get("commit")} dirty={ident.get("dirty")}')
    if not expected_commit or expected_commit != ident['commit']:
        raise PermissionError(f'--expected-commit {expected_commit!r} 与当前源码身份 {ident["commit"]} 不同，拒绝')
    return {'commit': ident['commit'], 'dirty': ident['dirty'], 'source': ident.get('source')}


def registered_ckpts(path=CKPT_LIST) -> dict:
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            h, rel = line.split()
            out[rel] = h
    return out


def load_backbone(run_dir: Path, meta, rel: str, registry: dict, device):
    """返回 (冻结的 I07 tri 模型, {'ckpt': sha, 'run': sha})。ckpt 哈希必须等于登记值。"""
    from experiments.I07_ps3style_backbone.train import build_model
    blob, run_blob = (run_dir / 'best.pt').read_bytes(), (run_dir / 'run.json').read_bytes()
    h = {'ckpt': sha256(blob), 'run': sha256(run_blob)}
    if registry.get(rel) != h['ckpt']:
        raise PermissionError(f'{rel} 的 sha256 {h["ckpt"]} 与 checkpoint-sha256.txt 登记值 {registry.get(rel)} 不同')
    run = json.loads(run_blob)
    if run.get('arm') != 'tri':
        raise ValueError(f'{rel} 不是 tri 臂')
    cfg = i07_contract.check_config(run['config'])
    model = build_model(meta, 'tri', cfg).to(device)
    model.load_state_dict(torch.load(io.BytesIO(blob), map_location=device, weights_only=True))
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    contract.check_frozen(model)
    return model, h


@torch.no_grad()
def export_split(model, part):
    """返回 (arrays, d0)：arrays 键 'p__<view>__<m>'、'risk_full'、'risk_zero__<pattern>'、'time'、'event'、'patient_ids'。"""
    d = model.d
    dev = part.time.device
    out, d0 = {}, {}
    full = model(part)
    i07_contract.check_output(full, len(part), MODALITIES)
    again = model(part)
    d0['determinism_full'] = float((again['risk'] - full['risk']).abs().max())
    head_full = model.risk(torch.cat([full['pooled'][m] for m in MODALITIES], dim=-1)).squeeze(-1)
    d0['full_head_vs_i07'] = float((head_full - full['risk']).abs().max())
    for m in MODALITIES:
        out[f'p__full__{m}'] = full['pooled'][m]
    out['risk_full'] = full['risk']
    for pat in PATTERNS:
        vis, tgt = visible(pat), targets(pat)
        zeros = {u: torch.zeros(d, device=dev) for u in tgt}
        o = model(part, present=vis, fill=zeros)
        i07_contract.check_output(o, len(part), vis)
        mine = model.risk(contract.assemble_head_in(pat, o['pooled'],
                                                    {u: torch.zeros(len(part), d, device=dev) for u in tgt})).squeeze(-1)
        d0[f'zero_head_vs_i07__{pat}'] = float((mine - o['risk']).abs().max())
        for m in vis:
            out[f'p__{pat}__{m}'] = o['pooled'][m]
        out[f'risk_zero__{pat}'] = o['risk']
    worst = max(d0.values())
    if not worst < D0_TOL:
        raise AssertionError(f'D0 守卫失败：最大误差 {worst} ≥ {D0_TOL}：{d0}')
    arrays = {k: v.float().cpu().numpy() for k, v in out.items()}
    arrays['time'] = part.time.cpu().numpy()
    arrays['event'] = part.event.cpu().numpy()
    arrays['patient_ids'] = np.array(part.patient_ids)
    return arrays, d0


def export_fold(model, parts: dict):
    if set(parts) != set(SPLITS):
        raise PermissionError(f'缓存只允许 train / val 分割，实际 {sorted(parts)}（test_access: false）')
    tr, va = set(parts['train'].patient_ids), set(parts['val'].patient_ids)
    if tr & va:
        raise AssertionError('train 与 val 患者重叠')
    arrays, d0 = {}, {}
    for s in SPLITS:
        a, d = export_split(model, parts[s])
        arrays.update({f'{s}__{k}': v for k, v in a.items()})
        d0.update({f'{s}__{k}': v for k, v in d.items()})
    W = model.risk.weight.detach().float().cpu().numpy().reshape(-1)
    arrays['head_w'] = W
    arrays['head_b'] = model.risk.bias.detach().float().cpu().numpy().reshape(1)
    return arrays, d0


def npz_bytes(arrays: dict) -> bytes:
    buf = io.BytesIO()
    np.savez(buf, **arrays)
    return buf.getvalue()


def write_atomic(path: Path, blob: bytes):
    """唯一临时名写入后硬链接发布；目标已存在即失败（G6），不覆盖。"""
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    tmp.write_bytes(blob)
    try:
        os.link(tmp, path)
    finally:
        tmp.unlink()


def fold_name(cancer, fold):
    return f'{cancer}_fold{fold}.npz'


def load_fold_cache(cache_dir: Path, cancer: str, fold: int, manifest: dict | None = None):
    """读 npz 字节一次、核对 manifest 中的 sha256 后从同一份字节解析。返回 {键: np.ndarray}。"""
    cache_dir = Path(cache_dir)
    manifest = manifest or json.loads((cache_dir / 'manifest.json').read_text())
    name = fold_name(cancer, fold)
    blob = (cache_dir / name).read_bytes()
    want = manifest['files'].get(name, {}).get('sha256')
    if sha256(blob) != want:
        raise PermissionError(f'{name} 的 sha256 与 manifest 不符')
    with np.load(io.BytesIO(blob), allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    bad = [k for k in arrays if k.startswith('test')]
    if bad:
        raise PermissionError(f'缓存含 test 键：{bad[:3]}')
    return arrays


def fold_tensors(arrays: dict):
    """npz → {'train'|'val': {'p': {view: {m: Tensor}}, 'time', 'event', 'ids', 'risk_full', 'risk_zero': {pat: T}}, 'head_w', 'head_b'}。"""
    out = {}
    for s in SPLITS:
        p = {v: {} for v in VIEWS}
        for v in VIEWS:
            for m in (MODALITIES if v == 'full' else visible(v)):
                p[v][m] = torch.from_numpy(arrays[f'{s}__p__{v}__{m}']).float()
        out[s] = {'p': p, 'time': torch.from_numpy(arrays[f'{s}__time']).float(),
                  'event': torch.from_numpy(arrays[f'{s}__event']).float(),
                  'ids': [str(x) for x in arrays[f'{s}__patient_ids']],
                  'risk_full': torch.from_numpy(arrays[f'{s}__risk_full']).float(),
                  'risk_zero': {pat: torch.from_numpy(arrays[f'{s}__risk_zero__{pat}']).float() for pat in PATTERNS}}
    out['head_w'] = torch.from_numpy(arrays['head_w']).float()
    out['head_b'] = torch.from_numpy(arrays['head_b']).float()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assets', required=True, type=Path)
    ap.add_argument('--runs', required=True, type=Path, help='I07 i07-ps3-20261011 的 runs 根（<癌>/fold<k>/tri/best.pt）')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cancers', default='BLCA,BRCA,LUAD,LGG,UCEC')
    ap.add_argument('--folds', default='0,1,2,3,4')
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--expected-commit', required=True)
    a = ap.parse_args(argv)
    ident = source_identity(a.expected_commit)
    cfg, cfg_sha = contract.load_config()
    if cfg['train']['test_access'] is not False or cfg['features']['splits'] != list(SPLITS):
        raise PermissionError('config 不允许访问 test')
    a.out.mkdir(parents=True, exist_ok=False)          # 不覆盖已有缓存目录
    registry = registered_ckpts()
    manifest = {'source': ident, 'config_sha256': cfg_sha, 'splits': list(SPLITS), 'views': list(VIEWS),
                'backbone_run': cfg['backbone']['results_run'], 'd0_tol': D0_TOL, 'files': {}}
    torch.use_deterministic_algorithms(False)
    for cancer in [c for c in a.cancers.split(',') if c]:
        for fold in [int(k) for k in a.folds.split(',') if k]:
            parts, meta = load_fold(a.assets, cancer, fold, device=a.device, parts=SPLITS)
            rel = f'{cancer}/fold{fold}/tri/best.pt'
            model, h = load_backbone(a.runs / cancer / f'fold{fold}' / 'tri', meta, rel, registry, a.device)
            arrays, d0 = export_fold(model, parts)
            blob = npz_bytes(arrays)
            name = fold_name(cancer, fold)
            write_atomic(a.out / name, blob)
            manifest['files'][name] = {'sha256': sha256(blob), 'ckpt_sha256': h['ckpt'], 'run_sha256': h['run'],
                                       'assets_fp': meta['assets_fp'], 'n': {s: len(parts[s]) for s in SPLITS},
                                       'd0_max_abs': max(d0.values()), 'd0': d0}
            print(json.dumps({'fold': name, 'n': manifest['files'][name]['n'], 'd0_max_abs': max(d0.values())}),
                  flush=True)
            del model, parts
            if a.device.startswith('cuda'):
                torch.cuda.empty_cache()
    write_atomic(a.out / 'manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode())
    print('cache: done', len(manifest['files']))


if __name__ == '__main__':
    main()
