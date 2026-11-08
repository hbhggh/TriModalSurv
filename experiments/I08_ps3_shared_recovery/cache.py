"""I08 Step 1：冻结 I07 前向一次，导出 7 种 present 视角的 pooled 静态缓存（handoff v1 §2、§7 Step 2）。

- 只加载、只前向 train 与 val。资产经 TrainValReader 读取（Codex 首审 finding 1）：AssetReader 核对完整性后立即剔除 test 行
  ——splits / cohort 只留本折 train/val 患者，RNA / 文本 npz 按行重建，test 患者的 WSI 文件拒绝读取；I07 load_fold
  收到的字节里没有任何 test 患者的 id、标签或特征。残留边界：癌种级共享文件（splits.csv、cohort.csv、rna_*.npz、
  text_*.npz）为做 sha256 完整性核对仍整份读入内存，test 行在核对后即被丢弃、不被解析进任何数据结构。
- ckpt：i07-ps3-20261011 的 tri 臂 best.pt 与 run.json；字节只读一次，sha256 必须都等于 i07_registry.py 的登记值
  （.py 受源码身份门保护，finding 2），再从同一份字节解析（V43）；run.json 的 config 经 I07 contract.check_config。
  骨架 eval()、全部 requires_grad=False，过 contract.check_frozen。
- manifest 记录导出所依赖源码的逐文件 sha256（CACHE_SOURCES）与 config 的缓存相关视图哈希；train_eval 运行前逐项核对
  （finding 3）。
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

import csv
import numpy as np
import torch

from experiments.I07_ps3style_backbone import contract as i07_contract
from experiments.I07_ps3style_backbone.data import load_fold
from experiments.I07_ps3style_backbone.model import MODALITIES

from . import contract, i07_registry
from .contract import PATTERNS, VIEWS, targets, visible

SPLITS = ('train', 'val')
D0_TOL = 1e-6
EXP = Path(__file__).resolve().parent
ROOT = EXP.parents[1]
I07_EXP = ROOT / 'experiments' / 'I07_ps3style_backbone'
CKPT_LIST = I07_EXP / 'results' / 'i07-ps3-20261011' / 'checkpoint-sha256.txt'
# 缓存内容依赖的源码：manifest 记录其逐文件 sha256，train_eval 运行时要求与当前文件逐一相等
CACHE_SOURCES = [EXP / f for f in ('__init__.py', 'contract.py', 'cache.py', 'i07_registry.py')] + \
                [I07_EXP / f for f in ('model.py', 'data.py', 'survival.py', 'contract.py', 'provenance.py', 'train.py')]
SOURCES = CACHE_SOURCES + [EXP / f for f in ('config.yaml', 'operators.py', 'losses.py', 'train_eval.py',
                                             'interpretability.py')]
MANIFEST_KEYS = {'source', 'source_files', 'config_sha256', 'config_cache_view_sha256', 'splits', 'views',
                 'backbone_run', 'd0_tol', 'files'}
FILE_KEYS = {'sha256', 'ckpt_sha256', 'run_sha256', 'assets_fp', 'n', 'd0_max_abs', 'd0'}


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


def source_files() -> dict:
    """{仓库相对路径: sha256}，缓存依赖源码的当前指纹。"""
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in CACHE_SOURCES}


def config_cache_view_sha(cfg) -> str:
    """config 中决定缓存内容的部分（backbone、features）的哈希；其他节改动不使缓存失效。"""
    return sha256(json.dumps({k: cfg[k] for k in ('backbone', 'features')}, sort_keys=True).encode())


class TrainValReader:
    """包住 I07 AssetReader：完整性核对之后立即剔除 test 行，再交给 I07 load_fold（finding 1）。
    reads 记录每次请求（sub, rel），供测试核对。"""

    def __init__(self, reader, cancer: str, fold: int):
        self.inner, self.cancer, self.fold = reader, cancer, int(fold)
        self.fingerprint = reader.fingerprint
        self.reads = []
        rows = self._csv(reader.read('splits', 'splits.csv'))
        mine = [r for r in rows if r['cancer'] == cancer and int(r['fold']) == self.fold and r['part'] in SPLITS]
        self.allowed = {r['patient_id'] for r in mine}
        if not mine or {r['part'] for r in mine} != set(SPLITS):
            raise ValueError(f'{cancer} 折 {fold} 没有完整的 train / val 划分')
        self._splits = self._dump(rows[0].keys() if rows else [], mine)

    @staticmethod
    def _csv(blob):
        return list(csv.DictReader(io.StringIO(blob.decode('utf-8'), newline='')))

    @staticmethod
    def _dump(fields, rows):
        buf = io.StringIO(newline='')
        w = csv.DictWriter(buf, fieldnames=list(fields), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue().encode('utf-8')

    def _npz_rows(self, blob):
        with np.load(io.BytesIO(blob), allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        pids = [str(x) for x in arrays['patient_ids']]
        keep = np.array([i for i, p in enumerate(pids) if p in self.allowed], dtype=np.int64)
        n = len(pids)
        out = {k: (v[keep] if v.ndim >= 1 and v.shape[0] == n else v) for k, v in arrays.items()}
        buf = io.BytesIO()
        np.savez(buf, **out)
        return buf.getvalue()

    def read(self, sub: str, rel: str) -> bytes:
        self.reads.append((sub, rel))
        if sub == 'splits' and rel == 'splits.csv':
            return self._splits
        if sub == 'wsi_tokens':
            pid = Path(rel).stem
            if not rel.startswith(f'{self.cancer}/') or pid not in self.allowed:
                raise PermissionError(f'拒绝读取 train/val 以外的 WSI：{rel}')
            return self.inner.read(sub, rel)
        blob = self.inner.read(sub, rel)
        if sub == 'cohort' and rel == 'cohort.csv':
            rows = self._csv(blob)
            return self._dump(rows[0].keys(), [r for r in rows if r['patient_id'] in self.allowed])
        if sub in ('rna', 'text') and rel.endswith('.npz'):
            return self._npz_rows(blob)
        return blob


def registered_ckpts(path=CKPT_LIST) -> dict:
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            h, rel = line.split()
            out[rel] = h
    return out


def load_backbone(run_dir: Path, meta, rel: str, device, registry=None):
    """返回 (冻结的 I07 tri 模型, {'ckpt': sha, 'run': sha})。best.pt 与 run.json 的哈希都必须等于 i07_registry 登记值。"""
    from experiments.I07_ps3style_backbone.train import build_model
    registry = i07_registry.TRI if registry is None else registry
    blob, run_blob = (run_dir / 'best.pt').read_bytes(), (run_dir / 'run.json').read_bytes()
    h = {'ckpt': sha256(blob), 'run': sha256(run_blob)}
    want = registry.get(rel)
    if want is None or (h['ckpt'], h['run']) != tuple(want):
        raise PermissionError(f'{rel} 的 best.pt / run.json 哈希 {h} 与 i07_registry 登记值 {want} 不同')
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


def _git(*args):
    import subprocess
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True)


def verify_cache_manifest(manifest: dict, cfg: dict):
    """train_eval 使用缓存前的完整核对（Codex 首审 finding 3）：schema、导出源码身份与逐文件指纹、config 缓存视图、
    划分 / 视角、癌×折集合恰为 config 全集、每折 ckpt / run.json 哈希等于 i07_registry、D0 误差。任一不符即拒绝。"""
    def need(ok, msg):
        if not ok:
            raise PermissionError(f'缓存 manifest 核对失败：{msg}')
    need(isinstance(manifest, dict) and set(manifest) == MANIFEST_KEYS, f'键必须恰为 {sorted(MANIFEST_KEYS)}')
    src = manifest['source']
    need(isinstance(src, dict) and isinstance(src.get('commit'), str) and len(src['commit']) == 40
         and src.get('dirty') is False, f'导出源码身份无效：{src}')
    anc = _git('merge-base', '--is-ancestor', src['commit'], 'HEAD')
    need(anc.returncode == 0, f'导出 commit {src["commit"][:12]} 不是当前 HEAD 的祖先（{anc.stderr.strip()}）')
    need(manifest['source_files'] == source_files(), '导出时的缓存相关源码与当前文件不一致（须重新导出）')
    need(manifest['config_cache_view_sha256'] == config_cache_view_sha(cfg), 'config 的 backbone / features 已变化')
    need(manifest['splits'] == list(SPLITS) and manifest['views'] == list(VIEWS), '划分或视角不符')
    need(manifest['backbone_run'] == i07_registry.BACKBONE_RUN == cfg['backbone']['results_run'], 'backbone_run 不符')
    need(manifest['d0_tol'] == D0_TOL, 'd0_tol 不符')
    want = {fold_name(c, k): f'{c}/fold{k}/tri/best.pt' for c in cfg['backbone']['cancers'] for k in cfg['backbone']['folds']}
    need(set(manifest['files']) == set(want), f'癌×折集合必须恰为 config 全集（{len(want)} 个）')
    for name, rel in want.items():
        e = manifest['files'][name]
        need(isinstance(e, dict) and set(e) == FILE_KEYS, f'{name} 的键不对')
        need((e['ckpt_sha256'], e['run_sha256']) == tuple(i07_registry.TRI[rel]), f'{name} 的 ckpt / run.json 哈希与登记不符')
        need(isinstance(e['d0_max_abs'], float) and e['d0_max_abs'] < D0_TOL, f'{name} 的 D0 误差 {e["d0_max_abs"]}')
        need(set(e['n']) == set(SPLITS) and all(isinstance(v, int) and v > 0 for v in e['n'].values()), f'{name} 的 n 不对')
    return True


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
    if cfg['backbone']['results_run'] != i07_registry.BACKBONE_RUN:
        raise PermissionError('config 的 backbone.results_run 与 i07_registry 不符')
    a.out.mkdir(parents=True, exist_ok=False)          # 不覆盖已有缓存目录
    manifest = {'source': ident, 'source_files': source_files(), 'config_sha256': cfg_sha,
                'config_cache_view_sha256': config_cache_view_sha(cfg), 'splits': list(SPLITS), 'views': list(VIEWS),
                'backbone_run': cfg['backbone']['results_run'], 'd0_tol': D0_TOL, 'files': {}}
    from experiments.I07_ps3style_backbone.provenance import AssetReader
    torch.use_deterministic_algorithms(False)
    for cancer in [c for c in a.cancers.split(',') if c]:
        for fold in [int(k) for k in a.folds.split(',') if k]:
            reader = TrainValReader(AssetReader(a.assets), cancer, fold)
            parts, meta = load_fold(a.assets, cancer, fold, device=a.device, parts=SPLITS, reader=reader)
            rel = f'{cancer}/fold{fold}/tri/best.pt'
            model, h = load_backbone(a.runs / cancer / f'fold{fold}' / 'tri', meta, rel, a.device)
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
