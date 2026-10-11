"""I07 Phase 0 / A4：RNA 通路输入。

每个病人：GDC STAR-Counts 的 tpm_unstranded → 同一 gene_name 的多行 TPM 相加（如 _PAR_Y）→ 只保留 50 个
MSigDB Hallmark 基因集（v2023.2）里的基因 → log2(1+TPM)。按基因 z-score **不在这里做**，训练时按折只用训练部分拟合。
输出 genes.json（基因顺序、每条通路的基因下标、GENCODE 里找不到的基因）与逐癌种 rna_<cancer>.npz。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .io_utils import atomic_save_npz, atomic_write_json, require_new_dir, sha256_file, write_manifest

DEFAULT_GMT = Path(__file__).resolve().parents[1] / 'assets' / 'msigdb' / 'h.all.v2023.2.Hs.symbols.gmt'


def read_gmt(path: Path) -> dict:
    sets = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        name, _desc, *genes = line.split('\t')
        if name in sets:
            raise ValueError(f'基因集重名：{name}')
        sets[name] = [g for g in genes if g]
    return sets


def read_tpm(path: Path) -> pd.Series:
    """gene_name → TPM（同名多行相加）；跳过 N_unmapped 等统计行。"""
    df = pd.read_csv(path, sep='\t', comment='#', usecols=['gene_id', 'gene_name', 'tpm_unstranded'])
    df = df[~df['gene_id'].astype(str).str.startswith('N_')]
    if df['tpm_unstranded'].isna().any() or not np.isfinite(df['tpm_unstranded'].to_numpy()).all():
        raise ValueError(f'{path} 的 TPM 含 NaN/Inf')
    if (df['tpm_unstranded'] < 0).any():
        raise ValueError(f'{path} 的 TPM 为负')
    return df.groupby('gene_name', sort=True)['tpm_unstranded'].sum()


def gene_layout(sets: dict, available: set) -> dict:
    """基因顺序 = Hallmark 基因并集中在 GENCODE 里出现的、按字母排序；记录缺失基因。"""
    union = sorted({g for gs in sets.values() for g in gs})
    genes = [g for g in union if g in available]
    index = {g: i for i, g in enumerate(genes)}
    pathways = {name: [index[g] for g in gs if g in index] for name, gs in sets.items()}
    empty = [n for n, idx in pathways.items() if not idx]
    if empty:
        raise ValueError(f'通路没有任何可用基因：{empty}')
    return {'genes': genes, 'pathways': pathways, 'missing_genes': [g for g in union if g not in available]}


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort', required=True, type=Path, help='cohort 目录（含 cohort.csv 与 rna_md5.json）')
    ap.add_argument('--rna-root', required=True, type=Path)
    ap.add_argument('--gmt', type=Path, default=DEFAULT_GMT)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    out = require_new_dir(a.out)
    with open(a.cohort / 'cohort.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    md5 = json.loads((a.cohort / 'rna_md5.json').read_text(encoding='utf-8'))
    sets = read_gmt(a.gmt)
    if len(sets) != 50:
        raise ValueError(f'Hallmark 基因集应为 50 个，实际 {len(sets)}')
    layout, symbols = None, None
    for cancer in sorted({r['cancer'] for r in rows}):
        sub = [r for r in rows if r['cancer'] == cancer]
        X = []
        for r in sub:
            path = a.rna_root / r['rna_file']
            if md5_file(path) != md5[f'{cancer}/{r["patient_id"]}']:
                raise ValueError(f'md5 不符：{path}')
            tpm = read_tpm(path)
            if layout is None:
                symbols = set(tpm.index)
                layout = gene_layout(sets, symbols)
            elif set(tpm.index) != symbols:
                raise ValueError(f'{path} 的基因名集合与第一个文件不同（基因模型版本不一致？）')
            X.append(np.log2(1.0 + tpm.reindex(layout['genes']).to_numpy(dtype=np.float64)))
        X = np.stack(X).astype(np.float32)
        assert np.isfinite(X).all()
        atomic_save_npz(out / f'rna_{cancer}.npz', patient_ids=np.array([r['patient_id'] for r in sub]), X=X)
    atomic_write_json(out / 'genes.json', layout)
    write_manifest(out, 'rna', {'gmt': str(a.gmt), 'gmt_sha256': sha256_file(a.gmt), 'value': 'log2(1+tpm_unstranded)',
                                'n_genes': len(layout['genes']), 'n_missing': len(layout['missing_genes'])})
    print(f'genes={len(layout["genes"])} missing={len(layout["missing_genes"])}')


if __name__ == '__main__':
    main()
