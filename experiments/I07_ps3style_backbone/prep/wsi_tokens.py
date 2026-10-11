"""I07 Phase 0 / A3：每个病人 128 个 WSI token（UNI2-h 1536 维）+ mask。

沿用 NPJ loader 的规则（tcga_dataset.py:79-88）：病人有 n 张切片时每张切片各做 MiniBatchKMeans 取 128//n 个中心；
patch 数不足时原样保留全部 patch。与 NPJ 的差别：切片按文件名排序；不足 128 的位置补零，并在 mask 里标 False，
补零位不进入注意力（GPU 合同第 3 条）。
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans

from .io_utils import atomic_save_npz, require_new_dir, write_manifest

N_TOKENS = 128
DIM = 1536
KMEANS_SEED = 42  # 与 NPJ 一致
N_INIT = 3


def slide_centers(x: np.ndarray, k: int) -> np.ndarray:
    """一张切片的 k 个中心；patch 数 ≤ k 时原样返回全部 patch（不聚类、不重复）。"""
    if x.ndim != 2 or x.shape[1] != DIM:
        raise ValueError(f'切片特征形状非法：{x.shape}')
    if not np.isfinite(x).all():
        raise ValueError('切片特征含 NaN/Inf')
    if len(x) <= k:
        return x.astype(np.float32)
    km = MiniBatchKMeans(n_clusters=k, random_state=KMEANS_SEED, n_init=N_INIT)
    km.fit(x)
    return km.cluster_centers_.astype(np.float32)


def patient_tokens(slide_arrays) -> tuple:
    """多张切片 → (tokens[128, DIM] float32, mask[128] bool)。"""
    n = len(slide_arrays)
    if n == 0:
        raise ValueError('病人没有切片')
    k = N_TOKENS // n
    if k < 1:
        raise ValueError(f'切片数 {n} 超过 token 数 {N_TOKENS}')
    parts = [slide_centers(x, k) for x in slide_arrays]
    real = np.concatenate(parts, axis=0)
    assert len(real) <= N_TOKENS
    tokens = np.zeros((N_TOKENS, DIM), dtype=np.float32)
    mask = np.zeros(N_TOKENS, dtype=bool)
    tokens[:len(real)] = real
    mask[:len(real)] = True
    return tokens, mask


def load_slide(path: Path) -> np.ndarray:
    return pd.read_pickle(path).values.astype(np.float32)


def valid_existing(path: Path, slides) -> bool:
    """续跑时复用已有文件前做内容校验（坑 D7）。"""
    try:
        with np.load(path, allow_pickle=False) as z:
            return (z['tokens'].shape == (N_TOKENS, DIM) and z['tokens'].dtype == np.float32
                    and z['mask'].shape == (N_TOKENS,) and z['mask'].dtype == bool and bool(z['mask'].any())
                    and np.isfinite(z['tokens']).all() and list(z['slides']) == list(slides))
    except Exception:
        return False


def run(cohort_rows, wsi_root: Path, out: Path, shard=0, n_shards=1, resume=False):
    done = 0
    for i, r in enumerate(cohort_rows):
        if i % n_shards != shard:
            continue
        slides = r['slides'].split(';')
        dst = out / r['cancer'] / f'{r["patient_id"]}.npz'
        if dst.exists():
            if not resume:
                raise FileExistsError(f'已存在，拒绝覆盖（续跑请加 --resume）：{dst}')
            if valid_existing(dst, slides):
                continue
        arrays = [load_slide(Path(wsi_root) / r['cancer'] / s) for s in slides]
        tokens, mask = patient_tokens(arrays)
        atomic_save_npz(dst, tokens=tokens, mask=mask, slides=np.array(slides))
        done += 1
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort', required=True, type=Path)
    ap.add_argument('--wsi-root', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--shard', type=int, default=0)
    ap.add_argument('--n-shards', type=int, default=1)
    ap.add_argument('--resume', action='store_true', help='允许在已有输出上续跑（逐文件校验后跳过）')
    ap.add_argument('--init', action='store_true', help='发车前运行一次：要求输出目录为空并创建')
    ap.add_argument('--finalize', action='store_true', help='全部分片完成后：核对覆盖率并写清单')
    a = ap.parse_args(argv)
    with open(a.cohort, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if a.finalize:
        missing = [r['patient_id'] for r in rows
                   if not valid_existing(a.out / r['cancer'] / f'{r["patient_id"]}.npz', r['slides'].split(';'))]
        if missing:
            raise SystemExit(f'{len(missing)} 个病人缺少有效的 WSI token，例如 {missing[:3]}')
        write_manifest(a.out, 'wsi_tokens', {'cohort': str(a.cohort), 'n_tokens': N_TOKENS, 'dim': DIM,
                                             'kmeans_seed': KMEANS_SEED, 'n_init': N_INIT})
        print(f'finalize ok: {len(rows)} 个病人')
        return
    if a.init:
        require_new_dir(a.out)
        print(f'init ok: {a.out}')
        return
    if not a.out.is_dir():
        raise SystemExit(f'输出目录不存在，先运行 --init：{a.out}')
    n = run(rows, a.wsi_root, a.out, a.shard, a.n_shards, a.resume)
    print(f'shard {a.shard}/{a.n_shards}: 新写 {n} 个病人')


if __name__ == '__main__':
    main()
