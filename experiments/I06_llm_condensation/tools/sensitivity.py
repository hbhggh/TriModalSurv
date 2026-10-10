#!/usr/bin/env python3
"""I06 敏感性（研究计划书 4.9，只报告）：剔除带退回 / 截断标记的患者后，从逐患者预测重算 test C-index 与 Overall 判定。

标记 = 冻结文本中 status 属于 condense.CAPPED_STATUSES（退回原文或截断）的记录；两臂冻结文件的 sha256 必须等于
freeze manifest 登记值。每个候选只剔除其所用臂的标记患者；某行剔除集为空时取原值，否则用 I05 验真脚本的
numpy C-index 在剩余患者上重算。输出患者级清单（patient_id、癌种、划分、臂、状态）、每档案每癌 test 人数与剔除
名单、改变的行数与最大差，以及剔除前后的逐候选严格胜 k/5 与胜者。raw（冻结文本、逐患者预测）只在本地，输出不含路径。

用法:
python3 experiments/I06_llm_condensation/tools/sensitivity.py --frozen-dir <冻结文本目录> \\
    --raw-dir experiments/I06_llm_condensation/results/<run_id>/raw --out <evidence>/sensitivity.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

TOOLS_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = TOOLS_DIR.parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I05_text_encoder_bcmbert.tools import verify_results as vr  # noqa: E402
from experiments.I06_llm_condensation import condense  # noqa: E402
from experiments.I06_llm_condensation.tools import render_results as rr  # noqa: E402

FREEZE_MANIFEST = EXPERIMENT_DIR / 'results' / 'i06-condense-20260926' / 'evidence' / 'freeze-manifest.json'


def flagged_patients(frozen_dir, manifest: dict) -> dict:
    """{臂: {patient_id: {cancer, split, status}}}；冻结文件哈希必须等于 freeze manifest 登记值。"""
    out = {}
    for arm, spec in manifest['frozen_texts'].items():
        data = (Path(frozen_dir) / spec['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise ValueError(f'{arm}: 冻结文本哈希与 freeze manifest 登记值不符')
        records = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
        out[arm] = {r['patient_id']: {'cancer': r['cancer'], 'split': r['split'], 'status': r['status']}
                    for r in records if r['status'] in condense.CAPPED_STATUSES}
    return out


def load_predictions(test_dir: Path, row: dict):
    # LUAD 的 strategy0 预测写在 <癌种>/<seed>/<场景>.strategy0/，prediction_file 相对 seed 目录记录（同 verify_results）
    base = test_dir / row['cell'] if '/' not in row['prediction_file'] else test_dir / Path(row['cell']).parent
    with np.load(base / row['prediction_file'], allow_pickle=False) as data:
        return data['patient_ids'].tolist(), data['time'], data['censorship'], data['risk_b']


def recompute(test_dir, complete: dict, excluded: set) -> dict:
    """逐行剔除后重算。返回 strategy0 的 {(癌种, seed, 场景): C-index}、每癌 test 患者与剔除名单、改变的行数与最大差。"""
    values, cancers, changed, max_diff = {}, {}, 0, 0.0
    for row in complete['rows']:
        ids, time, censorship, risk = load_predictions(Path(test_dir), row)
        known = cancers.setdefault(row['cancer'], {'ids': set(ids), 'excluded': sorted(set(ids) & excluded)})
        if known['ids'] != set(ids):
            raise ValueError(f"{row['cell']}: 同一癌种各行的 test 患者集合不一致")
        keep = np.array([pid not in excluded for pid in ids], dtype=bool)
        value = row['c_index_b']
        if not keep.all():
            event = (1 - np.asarray(censorship)[keep]).astype(bool)
            value = vr.concordance_numpy(event, np.asarray(time)[keep], np.asarray(risk)[keep])
            changed += 1
            max_diff = max(max_diff, abs(value - row['c_index_b']))
        if row['protocol'] == 'strategy0':
            values[(row['cancer'], int(row['seed']), row['grid'])] = value
    per_cancer = {c: {'n_test': len(v['ids']), 'n_excluded': len(v['excluded']), 'excluded': v['excluded']}
                  for c, v in sorted(cancers.items())}
    return {'values': values, 'per_cancer': per_cancer, 'rows': len(complete['rows']), 'rows_changed': changed,
            'max_abs_diff': max_diff}


def run(frozen_dir, raw_dir, freeze_manifest=FREEZE_MANIFEST, i06_config=None) -> dict:
    i06 = i06_config or json.loads(rr.I06_CONFIG.read_text(encoding='utf-8'))
    config = rr.i05r.load_config()
    manifest = json.loads(Path(freeze_manifest).read_text(encoding='utf-8'))
    flagged = flagged_patients(frozen_dir, manifest)
    base, _ = rr.i05r.load_baseline(REPO_ROOT / config['legacy']['test_complete'], config)
    order = i06['candidate_tie_order']
    main_values, after_values, profiles = {}, {}, {}
    for name in order:
        spec = i06['candidates'][name]
        test_dir = Path(raw_dir) / spec['profile'] / 'test'
        raw = (test_dir / 'complete.json').read_bytes()
        complete = json.loads(raw)
        result = recompute(test_dir, complete, set(flagged[spec['arm']]))
        main_values[name] = rr.protocol_values(complete, config, 'strategy0', label=name)
        after_values[name] = result.pop('values')
        profiles[spec['profile']] = {'candidate': name, 'arm': spec['arm'],
                                     'complete_sha256': hashlib.sha256(raw).hexdigest(), **result}
    main = rr.decide(main_values, base, config, order)
    after = rr.decide(after_values, base, config, order)
    return {
        'rule': '剔除冻结文本 status ∈ ' + '/'.join(condense.CAPPED_STATUSES) + ' 的患者（按候选所用臂），逐行重算 test C-index，'
                '再按 Overall 口径重做判定（研究计划书 4.9，只报告）',
        'freeze_manifest_sha256': hashlib.sha256(Path(freeze_manifest).read_bytes()).hexdigest(),
        'frozen_texts': {arm: {'path': spec['path'], 'sha256': spec['sha256'], 'n_flagged': len(flagged[arm])}
                         for arm, spec in sorted(manifest['frozen_texts'].items())},
        'flagged_patients': [{'arm': arm, 'patient_id': pid, **info}
                             for arm in sorted(flagged) for pid, info in sorted(flagged[arm].items())],
        'profiles': profiles,
        'k_main': {n: main['candidates'][n]['k'] for n in order},
        'k_after_exclusion': {n: after['candidates'][n]['k'] for n in order},
        'winner_main': main['winner'], 'winner_after_exclusion': after['winner'],
        'test_patients_excluded': sum(c['n_excluded'] for p in profiles.values() for c in p['per_cancer'].values()),
        'identical_to_main': all(p['rows_changed'] == 0 for p in profiles.values()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--frozen-dir', type=Path, required=True, help='含两臂冻结文本（frozen-*.jsonl）的目录')
    parser.add_argument('--raw-dir', type=Path, required=True, help='含 <档案>/test/{complete.json, 逐患者 npz} 的目录')
    parser.add_argument('--freeze-manifest', type=Path, default=FREEZE_MANIFEST)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(args.frozen_dir, args.raw_dir, args.freeze_manifest)
    with args.out.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ('test_patients_excluded', 'identical_to_main', 'k_main',
                                              'k_after_exclusion', 'winner_after_exclusion')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
