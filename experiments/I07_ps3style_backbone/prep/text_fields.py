"""I07 Phase 0 / A5：病理报告逐字段向量。

字段表与字段名取 I06 `model.fields_for(cancer)`（BLCA 14 / BRCA 16 / LUAD 13 / LGG 15 / UCEC 13），字段值取
I06 结构化浓缩的 payload（full-struct.nolimit.jsonl）。每个字段写成一句 "字段名: 值"，用冻结的
NeuML/bioclinical-modernbert-base-embeddings 编码，按其 sentence-transformers 配置做 mean pooling（768 维，无归一化）。
值为 "not mentioned"（或空）的字段不编码：向量置零、not_mentioned=True，训练时由可学习的 [NOT_MENTIONED] 代替。
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from experiments.I06_llm_condensation.model import NOT_MENTIONED, fields_for

from .io_utils import atomic_save_npz, require_new_dir, write_manifest

DIM = 768
MAX_LENGTH = 512


def field_value(field, payload: dict):
    """返回 (句子或 None)；None 表示 not mentioned。缺字段直接报错（I06 schema 要求全字段）。"""
    if field.key not in payload:
        raise KeyError(f'payload 缺字段 {field.key}')
    v = payload[field.key]
    if field.kind == 'pairs':
        if not isinstance(v, list):
            raise TypeError(f'{field.key} 应为列表')
        items = [f'{p["name"]}: {p["result"]}' for p in v if str(p.get('name', '')).strip()]
        text = '; '.join(items)
    else:
        if not isinstance(v, str):
            raise TypeError(f'{field.key} 应为字符串')
        text = v
    text = text.strip()
    if not text or text.lower() == NOT_MENTIONED:
        return None
    return f'{field.label}: {text}'


def patient_sentences(cancer: str, payload: dict):
    return [field_value(f, payload) for f in fields_for(cancer)]


class NeuMLEncoder:
    def __init__(self, snapshot: Path, device: str = 'cpu', batch_size: int = 64):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
        self.model = AutoModel.from_pretrained(snapshot, local_files_only=True).to(device).eval()
        self.device, self.batch_size = device, batch_size
        self.n_truncated = 0

    def __call__(self, sentences):
        torch = self.torch
        out = []
        for i in range(0, len(sentences), self.batch_size):
            chunk = sentences[i:i + self.batch_size]
            full = self.tok(chunk, truncation=False)['input_ids']
            self.n_truncated += sum(len(ids) > MAX_LENGTH for ids in full)
            enc = self.tok(chunk, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors='pt').to(self.device)
            with torch.no_grad():
                h = self.model(**enc).last_hidden_state
            m = enc['attention_mask'].unsqueeze(-1).to(h.dtype)
            out.append(((h * m).sum(1) / m.sum(1).clamp(min=1)).float().cpu().numpy())
        return np.concatenate(out, axis=0) if out else np.zeros((0, DIM), np.float32)


def encode_cancer(cancer, pids, payloads, encoder):
    """返回 (emb[n, F, DIM] float32, not_mentioned[n, F] bool)。"""
    keys = [f.key for f in fields_for(cancer)]
    sents = [patient_sentences(cancer, payloads[p]) for p in pids]
    flat = [(i, j, s) for i, row in enumerate(sents) for j, s in enumerate(row) if s is not None]
    vecs = encoder([s for _, _, s in flat])
    emb = np.zeros((len(pids), len(keys), DIM), dtype=np.float32)
    nm = np.ones((len(pids), len(keys)), dtype=bool)
    for (i, j, _), v in zip(flat, vecs):
        emb[i, j] = v
        nm[i, j] = False
    if not np.isfinite(emb).all():
        raise ValueError('文本向量含 NaN/Inf')
    return emb, nm, keys


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort', required=True, type=Path)
    ap.add_argument('--text-jsonl', required=True, type=Path)
    ap.add_argument('--model-snapshot', required=True, type=Path)
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    out = require_new_dir(a.out)
    with open(a.cohort, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    payloads = {}
    with open(a.text_jsonl, encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            if rec.get('status') == 'ok':
                payloads[(rec['cancer'], rec['patient_id'][:12].upper())] = rec['payload']
    enc = NeuMLEncoder(a.model_snapshot, a.device)
    stats = {}
    for cancer in sorted({r['cancer'] for r in rows}):
        pids = [r['patient_id'] for r in rows if r['cancer'] == cancer]
        emb, nm, keys = encode_cancer(cancer, pids, {p: payloads[(cancer, p)] for p in pids}, enc)
        atomic_save_npz(out / f'text_{cancer}.npz', patient_ids=np.array(pids), emb=emb, not_mentioned=nm,
                        field_keys=np.array(keys))
        stats[cancer] = {'n': len(pids), 'n_fields': len(keys), 'not_mentioned_rate': float(nm.mean())}
    write_manifest(out, 'text', {'model_snapshot': str(a.model_snapshot), 'pooling': 'mean', 'max_length': MAX_LENGTH,
                                 'n_truncated': enc.n_truncated, 'stats': stats, 'text_jsonl': str(a.text_jsonl)})
    print(json.dumps(stats, indent=1), 'n_truncated', enc.n_truncated)


if __name__ == '__main__':
    main()
