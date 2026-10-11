"""I07 Phase 0 / A1：三模态完整人群清单。

人群 = 标签表（五癌）∩ 有 DX 切片的 UNI2-h 特征 ∩ 有 STAR-Counts 文件 ∩ I06 结构化浓缩 status=ok。
输出 cohort.csv（每行一个病人）与 cohort_summary.json（逐癌种人数与各排除原因人数）。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from .io_utils import CANCERS, atomic_write_json, atomic_write_text, norm_pid, require_new_dir, write_manifest

COLUMNS = ('cancer', 'patient_id', 'survival_months', 'censorship', 'event', 'slides', 'rna_file')


def load_labels(path: Path, cancers=CANCERS) -> dict:
    """{cancer: {pid: (survival_months, censorship)}}；时间须有限且 ≥0，censorship 只能是 0/1（坑 D3）。"""
    out = {c: {} for c in cancers}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            cancer = row['cancer_type'].strip()
            if cancer not in out:
                continue
            pid = norm_pid(row['patient_id'])
            t = float(row['survival_months'])
            c = float(row['censorship'])
            if not math.isfinite(t) or t < 0:
                raise ValueError(f'{pid} 生存时间非法：{t}')
            if c not in (0.0, 1.0):
                raise ValueError(f'{pid} censorship 非 0/1：{c}')
            if pid in out[cancer]:
                raise ValueError(f'{cancer} 标签表中病人重复：{pid}')
            out[cancer][pid] = (t, int(c))
    return out


def find_slides(wsi_root: Path, cancer: str, pid: str) -> list:
    """该病人的 DX 切片特征文件名（排序后，保证跨机器顺序一致）。"""
    d = Path(wsi_root) / cancer
    names = sorted(p.name for p in d.glob(f'{pid}.*.pkl'))
    bad = [n for n in names if '-DX' not in n.split('.')[1]]
    if bad:
        raise ValueError(f'{pid} 存在非 DX 切片：{bad}')
    return names


def load_rna_manifests(paths) -> dict:
    """{pid: 相对于 RNA 根目录的文件路径}；同一病人出现在两份清单里就报错。"""
    out = {}
    for mpath in paths:
        mpath = Path(mpath)
        with open(mpath, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                pid = norm_pid(row['patient_id'])
                rel = f'{mpath.parent.name}/{row["file_name"].strip()}'
                if pid in out:
                    raise ValueError(f'病人 {pid} 在多份 RNA 清单中出现')
                out[pid] = (rel, row['md5'].strip())
    return out


def load_text_ok(path: Path) -> dict:
    """{(cancer, pid)} 中 status=ok 且有 payload 的病人。"""
    ok = set()
    with open(path, encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            if rec.get('status') == 'ok' and isinstance(rec.get('payload'), dict):
                ok.add((rec['cancer'], norm_pid(rec['patient_id'])))
    return ok


def build(labels, wsi_root, rna, text_ok, rna_root=None, cancers=CANCERS):
    rows, summary = [], {}
    for cancer in cancers:
        s = {'labels': len(labels[cancer]), 'no_wsi': 0, 'no_rna': 0, 'no_text': 0, 'kept': 0, 'events': 0}
        for pid in sorted(labels[cancer]):
            slides = find_slides(wsi_root, cancer, pid)
            miss = []
            if not slides:
                miss.append('no_wsi')
            if pid not in rna or (rna_root is not None and not (Path(rna_root) / rna[pid][0]).is_file()):
                miss.append('no_rna')
            if (cancer, pid) not in text_ok:
                miss.append('no_text')
            for m in miss:
                s[m] += 1
            if miss:
                continue
            t, c = labels[cancer][pid]
            rows.append({'cancer': cancer, 'patient_id': pid, 'survival_months': repr(t), 'censorship': c,
                         'event': 1 - c, 'slides': ';'.join(slides), 'rna_file': rna[pid][0]})
            s['kept'] += 1
            s['events'] += 1 - c
        summary[cancer] = s
    pids = [(r['cancer'], r['patient_id']) for r in rows]
    assert len(pids) == len(set(pids)), '人群清单内病人重复'
    return rows, summary


def to_csv(rows) -> str:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--labels', required=True, type=Path)
    ap.add_argument('--wsi-root', required=True, type=Path)
    ap.add_argument('--rna-root', required=True, type=Path, help='各 RNA 清单所在目录的父目录')
    ap.add_argument('--rna-manifest', required=True, action='append', type=Path)
    ap.add_argument('--text-jsonl', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    out = require_new_dir(a.out)
    rna = load_rna_manifests(a.rna_manifest)
    rows, summary = build(load_labels(a.labels), a.wsi_root, rna, load_text_ok(a.text_jsonl), rna_root=a.rna_root)
    atomic_write_text(out / 'cohort.csv', to_csv(rows))
    atomic_write_json(out / 'rna_md5.json', {f'{r["cancer"]}/{r["patient_id"]}': rna[r['patient_id']][1] for r in rows})
    atomic_write_json(out / 'cohort_summary.json', summary)
    write_manifest(out, 'cohort', {k: str(v) for k, v in vars(a).items()})
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
