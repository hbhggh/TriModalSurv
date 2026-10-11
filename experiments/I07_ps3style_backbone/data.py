"""I07 数据加载：按 (癌种, 折) 读入 Phase 0 资产，组装 train/val/test 三部分张量。

- RNA 的按基因 z-score 只用该折 train 部分拟合（坑 D3 同类：统计量只来自训练集）。
- 每个部分组装后过 contract.check_part（形状、dtype、mask、event 只取 0/1）。
- 全部张量一次性放到目标设备；数据很小（单癌种 ≤ 约 700 MB），不需要逐样本 DataLoader。
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from .contract import check_part
from .provenance import AssetReader

PARTS = ('train', 'val', 'test')
STD_FLOOR = 1e-6


@dataclass
class Part:
    patient_ids: list
    wsi: torch.Tensor        # [N, 128, 1536]
    wsi_mask: torch.Tensor   # [N, 128] bool，True = 真实 token
    rna: torch.Tensor        # [N, G]，已按训练集 z-score
    text: torch.Tensor       # [N, F, 768]
    text_nm: torch.Tensor    # [N, F] bool，True = not mentioned
    time: torch.Tensor       # [N]
    event: torch.Tensor      # [N] 0/1

    def __len__(self):
        return len(self.patient_ids)

    def index(self, idx):
        return Part([self.patient_ids[i] for i in idx.tolist()], self.wsi[idx], self.wsi_mask[idx], self.rna[idx],
                    self.text[idx], self.text_nm[idx], self.time[idx], self.event[idx])


def csv_rows(blob: bytes):
    return list(csv.DictReader(io.StringIO(blob.decode('utf-8'), newline='')))


def npz(blob: bytes):
    return np.load(io.BytesIO(blob), allow_pickle=False)


def fold_parts(reader: AssetReader, cancer: str, fold: int) -> dict:
    rows = [r for r in csv_rows(reader.read('splits', 'splits.csv')) if r['cancer'] == cancer and int(r['fold']) == fold]
    if not rows:
        raise ValueError(f'splits.csv 中没有 {cancer} 折 {fold}')
    parts = {p: sorted(r['patient_id'] for r in rows if r['part'] == p) for p in PARTS}
    seen = [p for ps in parts.values() for p in ps]
    if len(seen) != len(set(seen)):
        raise AssertionError(f'{cancer} 折 {fold} 各部分有重叠')
    return parts


def zscore_fit(x_train: np.ndarray):
    mu = x_train.mean(axis=0)
    sd = x_train.std(axis=0)
    return mu, np.where(sd < STD_FLOOR, 1.0, sd)


def load_fold(assets: Path, cancer: str, fold: int, device='cpu', parts=PARTS, reader=None) -> tuple:
    """返回 ({部分名: Part}, meta)；所有文件经 AssetReader 读一次、按 manifest 核对后从同一份字节解析
    （reader 缺省时新建；meta['assets_fp'] 为这次读取所依据的 manifest 指纹）。只读取 parts 指定部分的病人（训练入口传 ('train', 'val')，不读 test，
    节点一首审 high 1）。z-score 永远只用 train 拟合，所以 parts 必须含 'train'。"""
    reader = reader or AssetReader(assets)
    wanted = tuple(parts)
    if 'train' not in wanted or set(wanted) - set(PARTS):
        raise ValueError(f'parts 必须含 train 且只能取 {PARTS}：{wanted}')
    parts = {k: v for k, v in fold_parts(reader, cancer, fold).items() if k in wanted}
    keep = {p for ps in parts.values() for p in ps}
    labels = {r['patient_id']: (float(r['survival_months']), int(r['event']))
              for r in csv_rows(reader.read('cohort', 'cohort.csv')) if r['cancer'] == cancer and r['patient_id'] in keep}
    with npz(reader.read('rna', f'rna_{cancer}.npz')) as z:
        rna_pids, rna_x = list(z['patient_ids']), z['X'].astype(np.float32)
    with npz(reader.read('text', f'text_{cancer}.npz')) as z:
        txt_pids, txt_emb, txt_nm, field_keys = list(z['patient_ids']), z['emb'], z['not_mentioned'], list(z['field_keys'])
    layout = json.loads(reader.read('rna', 'genes.json'))
    rna_row = {p: i for i, p in enumerate(rna_pids)}
    txt_row = {p: i for i, p in enumerate(txt_pids)}

    mu, sd = zscore_fit(rna_x[[rna_row[p] for p in parts['train']]])
    out = {}
    for name, pids in parts.items():
        wsi, wmask = [], []
        for p in pids:
            with npz(reader.read('wsi_tokens', f'{cancer}/{p}.npz')) as z:
                wsi.append(z['tokens'])
                wmask.append(z['mask'])
        rna = (rna_x[[rna_row[p] for p in pids]] - mu) / sd
        ti = [txt_row[p] for p in pids]
        out[name] = Part(
            patient_ids=list(pids),
            wsi=torch.from_numpy(np.stack(wsi)).to(device),
            wsi_mask=torch.from_numpy(np.stack(wmask)).to(device),
            rna=torch.from_numpy(rna.astype(np.float32)).to(device),
            text=torch.from_numpy(txt_emb[ti]).to(device),
            text_nm=torch.from_numpy(txt_nm[ti]).to(device),
            time=torch.tensor([labels[p][0] for p in pids], dtype=torch.float32, device=device),
            event=torch.tensor([labels[p][1] for p in pids], dtype=torch.float32, device=device),
        )
    for part in out.values():
        check_part(part, n_genes=len(layout['genes']), n_fields=len(field_keys))
    meta = {'pathways': list(layout['pathways'].values()), 'n_genes': len(layout['genes']),
            'n_fields': len(field_keys), 'field_keys': field_keys, 'rna_mu': mu, 'rna_sd': sd,
            'assets_fp': dict(reader.fingerprint)}
    return out, meta
