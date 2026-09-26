#!/usr/bin/env python3
"""从标签 CSV 导出 LLM 浓缩用的纯文本清单（只含 patient_id / cancer / split / text / text_sha256）。

浓缩、核验、抽样代码只读这份清单，从结构上保证"不看生存标签"：
- 目标患者 = B1（I05 bcmbert200）特征 manifest 里的患者（2506 人），与 B1 的有文本患者集合逐人相同；
- 每人的癌种、split 与 manifest 一致，原文的 text_sha256 与 manifest 逐人相同（哈希规则复用 I05）；
- 标签 CSV 与 B1 manifest 的 sha256 都锁在 config.yaml 里，不符即拒绝；
- 输出只写 5 列，任何生存列都不会写出；输出文件已存在即失败（不覆盖）。

在 landau 上经 jobrun.sh 运行；输出按校验和传到浓缩客户端所在机器。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I05_text_encoder_bcmbert.extract_text_features import read_labels, sha256_text  # noqa: E402

DEFAULT_CONFIG = EXPERIMENT_DIR / 'config.yaml'
BARCODE = re.compile(r'TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}', re.IGNORECASE)
DATE = re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:19|20)\d{2}-\d{2}-\d{2}\b')


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path=DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_b1_manifest(config, *, repo_root=REPO_ROOT) -> dict:
    """读取仓库里的 B1 特征 manifest，并按 config 锁定的 sha256 核对。"""
    section = config['b1_feature_manifest']
    path = Path(repo_root) / section['path']
    if sha256_file(path) != section['sha256']:
        raise ValueError(f'B1 特征 manifest 与锁定哈希不一致: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def build_rows(records: dict, manifest: dict, *, cancers) -> list:
    """按 B1 manifest 的患者逐人核对并生成导出行；任何不一致都直接报错。"""
    patients = manifest['patients']
    rows = []
    for pid in sorted(patients):
        expected = patients[pid]
        if expected['cancer'] not in cancers:
            continue
        record = records.get(pid)
        if record is None:
            raise ValueError(f'{pid}: 在 B1 manifest 中但不在标签 CSV 中')
        if (record['cancer'], record['split']) != (expected['cancer'], expected['split']):
            raise ValueError(f'{pid}: 癌种或 split 与 B1 manifest 不一致')
        text = record['text']
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'{pid}: 原文为空')
        digest = sha256_text(text)
        if digest != expected['text_sha256']:
            raise ValueError(f'{pid}: 原文 text_sha256 与 B1 manifest 不一致')
        rows.append({'patient_id': pid, 'cancer': record['cancer'], 'split': record['split'],
                     'text': text, 'text_sha256': digest})
    return rows


def text_stats(rows) -> dict:
    """只统计份数，不写出任何文本：报告正文里出现 TCGA 条码或日期的份数（写进局限）。"""
    return {'n': len(rows),
            'with_tcga_barcode': sum(bool(BARCODE.search(row['text'])) for row in rows),
            'with_date': sum(bool(DATE.search(row['text'])) for row in rows),
            'per_cancer_split': {f"{cancer}/{split}": n for (cancer, split), n in
                                 sorted(Counter((row['cancer'], row['split']) for row in rows).items())}}


def export(labels_path, out_path, *, config, repo_root=REPO_ROOT, manifest=None) -> dict:
    """导出纯文本清单与摘要记录。``manifest`` 只供测试注入（代码层面，不对应任何命令行参数）。"""
    labels_path, out_path = Path(labels_path), Path(out_path)
    labels_sha = sha256_file(labels_path)
    if manifest is None:
        if labels_sha != config['labels']['sha256']:
            raise ValueError('标签 CSV 与锁定哈希不一致')
        manifest = load_b1_manifest(config, repo_root=repo_root)
    records, _ = read_labels(labels_path, text_column=config['labels']['text_column'],
                             cancers=tuple(config['cancers']))
    rows = build_rows(records, manifest, cancers=tuple(config['cancers']))
    columns = config['export_columns']
    if any(list(row) != columns for row in rows):
        raise AssertionError('导出行的列与 config.export_columns 不一致')
    with out_path.open('x', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + '\n')
    summary = {'schema_version': 1, 'columns': columns, 'labels_sha256': labels_sha,
               'b1_manifest_sha256': config['b1_feature_manifest']['sha256'],
               'output': out_path.name, 'output_sha256': sha256_file(out_path), **text_stats(rows)}
    summary_path = out_path.with_name(out_path.name + '.summary.json')
    with summary_path.open('x', encoding='utf-8') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return summary


def read_export(path, *, config) -> list:
    """浓缩与核验代码读取纯文本清单的唯一入口：列必须恰好是 export_columns，出现其他列即拒绝。"""
    columns = config['export_columns']
    rows = []
    with Path(path).open(encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            if list(row) != columns:
                raise ValueError(f'纯文本清单的列不符（可能混入了标签列）: {sorted(row)}')
            if sha256_text(row['text']) != row['text_sha256']:
                raise ValueError(f"{row['patient_id']}: text_sha256 与正文不符")
            rows.append(row)
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--labels', type=Path, required=True, help='标签 CSV（sha256 须等于 config 锁定值）')
    parser.add_argument('--out', type=Path, required=True, help='输出 JSONL（已存在即失败）')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    summary = export(args.labels, args.out, config=load_config(args.config))
    print(json.dumps({k: summary[k] for k in ('n', 'output_sha256', 'with_tcga_barcode', 'with_date')},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
