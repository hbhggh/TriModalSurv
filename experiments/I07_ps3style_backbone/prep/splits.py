"""I07 Phase 0 / A2：每个癌种内 5 折，每折按病人分 train/val/test = 70/10/20，按事件分层。

test 取 StratifiedKFold(5) 的第 k 折；其余 80% 再用 StratifiedShuffleSplit 分出全体 10%（= 剩余部分的 12.5%）
作验证集。病人按 ID 排序后再分，种子固定（计划书第 2 节：2026），结果与机器、文件顺序无关。
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit

from .io_utils import atomic_write_json, atomic_write_text, require_new_dir, sha256_file, write_manifest

N_FOLDS = 5
VAL_OF_REST = 0.125  # 10% / 80%
SEED = 2026
COLUMNS = ('cancer', 'fold', 'patient_id', 'part')


def split_cancer(pids, events, seed=SEED):
    """返回 [(fold, pid, part)]；pids 与 events 一一对应。"""
    order = np.argsort(np.asarray(pids))
    pids = np.asarray(pids)[order]
    events = np.asarray(events, dtype=int)[order]
    out = []
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
    for k, (rest_idx, test_idx) in enumerate(skf.split(pids, events)):
        sss = StratifiedShuffleSplit(n_splits=1, test_size=VAL_OF_REST, random_state=seed + 1 + k)
        tr_rel, va_rel = next(sss.split(rest_idx, events[rest_idx]))
        for part, idx in (('train', rest_idx[tr_rel]), ('val', rest_idx[va_rel]), ('test', test_idx)):
            out.extend((k, str(pids[i]), part) for i in idx)
    return out


def check(rows, cohort):
    """坑 D1：每折各部分两两不交且覆盖全部人群；每个病人恰好在一折当 test。"""
    by_cancer = {}
    for r in cohort:
        by_cancer.setdefault(r['cancer'], set()).add(r['patient_id'])
    for cancer, pids in by_cancer.items():
        test_count = {p: 0 for p in pids}
        for k in range(N_FOLDS):
            parts = {}
            for c, f, p, part in rows:
                if c == cancer and f == k:
                    if p in parts:
                        raise AssertionError(f'{cancer} 折 {k} 病人 {p} 出现两次')
                    parts[p] = part
            if set(parts) != pids:
                raise AssertionError(f'{cancer} 折 {k} 未覆盖全部人群')
            for p, part in parts.items():
                if part == 'test':
                    test_count[p] += 1
        bad = [p for p, n in test_count.items() if n != 1]
        if bad:
            raise AssertionError(f'{cancer} 有病人不是恰好一次作 test：{bad[:3]}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    out = require_new_dir(a.out)
    with open(a.cohort, newline='', encoding='utf-8') as f:
        cohort = list(csv.DictReader(f))
    rows, summary = [], {}
    for cancer in sorted({r['cancer'] for r in cohort}):
        sub = [r for r in cohort if r['cancer'] == cancer]
        res = split_cancer([r['patient_id'] for r in sub], [int(r['event']) for r in sub])
        ev = {r['patient_id']: int(r['event']) for r in sub}
        rows.extend((cancer, k, p, part) for k, p, part in res)
        summary[cancer] = {f'fold{k}': {part: {'n': sum(1 for kk, p, pp in res if kk == k and pp == part),
                                                'events': sum(ev[p] for kk, p, pp in res if kk == k and pp == part)}
                                         for part in ('train', 'val', 'test')} for k in range(N_FOLDS)}
    check(rows, cohort)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(COLUMNS)
    w.writerows(sorted(rows))
    atomic_write_text(out / 'splits.csv', buf.getvalue())
    atomic_write_json(out / 'splits_summary.json', summary)
    write_manifest(out, 'splits', {'cohort': str(a.cohort), 'cohort_sha256': sha256_file(a.cohort),
                                   'seed': SEED, 'n_folds': N_FOLDS, 'val_of_rest': VAL_OF_REST})


if __name__ == '__main__':
    main()
