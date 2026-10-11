"""I07 正式结果的输出核对（节点二首审 high：授权只绑定输入、未绑定输出）。只读结果，不训练、不评测。

对一个正式结果目录（runs/<癌>/fold<k>/<臂>/）逐项核对并产出可独立复算的证据：
1. 完整性：5 癌 × 5 折 × 4 臂 = 100 个运行，每个都有 run.json、test_metrics.json、preds_test.npz；
   run.json 的 commit 等于 --expected-commit 且 dirty=False；test_metrics 的 (cancer, fold, arm) 与路径一致。
2. 划分与标签：preds 的 patient_ids 恰为 splits.csv 中该 (癌, 折) 的 test 部分；time / event 与 cohort.csv 逐人一致。
3. 指标复算：用本文件独立实现的 Harrell C-index（逐对比较，不调用 survival.c_index）从逐病人风险分重算
   test_metrics.json 的每一项，必须完全相等；tri 必须恰有 full + only_{rna,wsi,text}__{zero,train_mean} 七项。
4. 填充等价：tri 的 train_mean 与 zero 风险分之差在同一次评估内的极差 ≤ 1e-5（常数偏移 → C-index 必然相同）。
5. 产出：output_manifest.json（每个 test_metrics.json 与 preds_test.npz 的 sha256）、preds_test_all.csv（全部逐病人
   风险分，长表）、verify_report.json（含逐运行指标与 results_digest）。
   results_digest = sha256(核对协议 + 授权摘要 + commit + 输出 manifest + preds_test_all.csv + 逐运行指标规范化 JSON)
   （节点二复审 high：入库 CSV 必须直接进摘要）。
--recheck <verify 目录>：只凭入库的 preds_test_all.csv、output_manifest.json 与 verify_report.json 复核——从 CSV
   独立重算全部 C-index、宏平均、填充差极差与 results_digest，逐项必须等于报告；CSV 任何改动都会失败。
任何一项不符即报错退出。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

CANCERS = ('BLCA', 'BRCA', 'LUAD', 'LGG', 'UCEC')
ARMS = ('tri', 'wsi', 'rna', 'text')
FOLDS = range(5)
TRI_KEYS = {'full'} | {f'only_{m}__{f}' for m, f in itertools.product(('rna', 'wsi', 'text'), ('zero', 'train_mean'))}
FILL_TOL = 1e-5
VERIFY_PROTOCOL = 'I07-verify-v1: 5x5x4 runs; splits/cohort; independent Harrell; fill offset spread <= 1e-5'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def canonical(metrics) -> str:
    return json.dumps(metrics, sort_keys=True, separators=(',', ':'))


def results_digest(auth, commit, manifest_sha, csv_sha, metrics) -> str:
    h = hashlib.sha256()
    h.update(f'protocol {VERIFY_PROTOCOL}\nauth {auth}\ncommit {commit}\noutputs {manifest_sha}\n'
             f'preds_csv {csv_sha}\nmetrics {hashlib.sha256(canonical(metrics).encode()).hexdigest()}\n'.encode())
    return h.hexdigest()


def macro_summary(metrics) -> dict:
    def macro(arm, key):
        return float(np.mean([np.mean([metrics[f'{c}/fold{k}/{arm}'][key] for k in FOLDS]) for c in CANCERS]))
    return {'full': {x: macro(x, 'full') for x in ARMS},
            'masked_zero': {m: macro('tri', f'only_{m}__zero') for m in ('wsi', 'rna', 'text')}}


def harrell(risk, time, event) -> float:
    """独立实现：逐对比较。可比较对 (i, j)：event_i = 1 且 time_i < time_j；risk_i > risk_j 记 1，相等记 0.5。"""
    conc, total = 0.0, 0
    n = len(risk)
    for i in range(n):
        if event[i] != 1:
            continue
        for j in range(n):
            if time[i] < time[j]:
                total += 1
                conc += 1.0 if risk[i] > risk[j] else 0.5 if risk[i] == risk[j] else 0.0
    if total == 0:
        raise ValueError('没有可比较的病人对')
    return conc / total


def check(cond, msg):
    if not cond:
        raise SystemExit(f'核对失败：{msg}')


def recheck(verify_dir: Path) -> dict:
    """只凭入库的 CSV、输出 manifest 与报告复核；返回报告。"""
    report = json.loads((verify_dir / 'verify_report.json').read_text())
    groups = {}
    with open(verify_dir / 'preds_test_all.csv', newline='') as f:
        for r in csv.DictReader(f):
            g = groups.setdefault((r['cancer'], int(r['fold']), r['arm'], r['mode']), {})
            check(r['patient_id'] not in g, f'CSV 中 {r["patient_id"]} 在同一组重复')
            g[r['patient_id']] = (float(r['time']), int(r['event']), float(r['risk']))
    metrics, spread = {}, 0.0
    for (c, k, x, mode), g in groups.items():
        pids = sorted(g)
        metrics.setdefault(f'{c}/fold{k}/{x}', {})[mode] = harrell([g[p][2] for p in pids], [g[p][0] for p in pids],
                                                                   [g[p][1] for p in pids])
        if mode.endswith('__train_mean'):
            z = groups.get((c, k, x, mode.replace('__train_mean', '__zero')), {})
            check(set(z) == set(g), f'{c}/fold{k} {mode} 与 zero 的病人不同')
            d = [g[p][2] - z[p][2] for p in pids]
            spread = max(spread, max(d) - min(d))
    check(metrics == report['metrics'], 'CSV 重算的逐运行 C-index 与报告不符')
    check(macro_summary(metrics) == report['macro'], 'CSV 重算的宏平均与报告不符')
    check(spread <= FILL_TOL, f'CSV 的填充差极差 {spread} 超过 {FILL_TOL}')
    csv_sha, man_sha = sha(verify_dir / 'preds_test_all.csv'), sha(verify_dir / 'output_manifest.json')
    check(csv_sha == report['preds_test_all_sha256'], 'preds_test_all.csv 的哈希与报告不符')
    check(man_sha == report['output_manifest_sha256'], 'output_manifest.json 的哈希与报告不符')
    check(results_digest(report['auth_digest'], report['commit'], man_sha, csv_sha, metrics) == report['results_digest'],
          'results_digest 复算不符')
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--recheck', type=Path, help='只凭入库 CSV 与报告复核的 verify 目录')
    ap.add_argument('--runs', type=Path)
    ap.add_argument('--cohort', type=Path)
    ap.add_argument('--splits', type=Path)
    ap.add_argument('--expected-commit')
    ap.add_argument('--auth-digest')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv)
    if a.recheck:
        report = recheck(a.recheck)
        print(f'复核通过：{len(report["metrics"])} 个运行，results_digest {report["results_digest"]}')
        return
    if not all((a.runs, a.cohort, a.splits, a.expected_commit, a.auth_digest, a.out)):
        ap.error('核对模式需要 --runs --cohort --splits --expected-commit --auth-digest --out')

    labels = {(r['cancer'], r['patient_id']): (float(r['survival_months']), int(r['event']))
              for r in csv.DictReader(open(a.cohort, newline='', encoding='utf-8'))}
    test_ids = {}
    for r in csv.DictReader(open(a.splits, newline='', encoding='utf-8')):
        if r['part'] == 'test':
            test_ids.setdefault((r['cancer'], int(r['fold'])), set()).add(r['patient_id'])

    found = sorted(str(p.parent.relative_to(a.runs)) for p in a.runs.glob('*/fold*/*/run.json'))
    expected = sorted(f'{c}/fold{k}/{x}' for c, k, x in itertools.product(CANCERS, FOLDS, ARMS))
    check(found == expected, f'运行清单不是 5×5×4：多出 {sorted(set(found) - set(expected))[:3]}，缺 {sorted(set(expected) - set(found))[:3]}')

    manifest, rows, metrics, max_spread = {}, [], {}, 0.0
    for c, k, x in itertools.product(CANCERS, FOLDS, ARMS):
        d = a.runs / c / f'fold{k}' / x
        rel = f'{c}/fold{k}/{x}'
        run = json.loads((d / 'run.json').read_text())
        check(run['git'].get('commit') == a.expected_commit and run['git'].get('dirty') is False, f'{rel} 的 run.json commit/dirty 不符')
        tm = json.loads((d / 'test_metrics.json').read_text())
        check((tm['cancer'], tm['fold'], tm['arm']) == (c, k, x), f'{rel} 的 test_metrics 身份与路径不符')
        check(tm['best_epoch'] == run['best_epoch'], f'{rel} 的 best_epoch 与 run.json 不符')
        z = np.load(d / 'preds_test.npz', allow_pickle=False)
        pids = [str(p) for p in z['patient_ids']]
        check(len(pids) == len(set(pids)) and set(pids) == test_ids[(c, k)], f'{rel} 的病人不等于该折 test 划分')
        t, e = z['time'].astype(np.float64), z['event'].astype(np.float64)
        for i, p in enumerate(pids):
            check((float(np.float32(labels[(c, p)][0])), float(labels[(c, p)][1])) == (float(t[i]), float(e[i])),
                  f'{rel} 病人 {p} 的 time/event 与 cohort 不符')
        keys = set(tm['c_index'])
        check(keys == (TRI_KEYS if x == 'tri' else {'full'}), f'{rel} 的指标项不符：{sorted(keys)}')
        for key in sorted(keys):
            r = z[key].astype(np.float64)
            check(harrell(r.tolist(), t.tolist(), e.tolist()) == tm['c_index'][key], f'{rel} 的 {key} 重算不一致')
            rows += [(c, k, x, key, p, repr(float(t[i])), int(e[i]), repr(float(r[i]))) for i, p in enumerate(pids)]
        if x == 'tri':
            for m in ('rna', 'wsi', 'text'):
                diff = z[f'only_{m}__train_mean'].astype(np.float64) - z[f'only_{m}__zero'].astype(np.float64)
                max_spread = max(max_spread, float(diff.max() - diff.min()))
        metrics[rel] = tm['c_index']
        manifest[f'{rel}/test_metrics.json'] = sha(d / 'test_metrics.json')
        manifest[f'{rel}/preds_test.npz'] = sha(d / 'preds_test.npz')
    check(max_spread <= FILL_TOL, f'填充差的极差 {max_spread} 超过 {FILL_TOL}')

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'output_manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
    with open(a.out / 'preds_test_all.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cancer', 'fold', 'arm', 'mode', 'patient_id', 'time', 'event', 'risk'])
        w.writerows(rows)
    man_sha, csv_sha = sha(a.out / 'output_manifest.json'), sha(a.out / 'preds_test_all.csv')
    report = {'verify_protocol': VERIFY_PROTOCOL, 'runs': len(expected),
              'metrics_recomputed': sum(len(v) for v in metrics.values()), 'max_fill_offset_spread': max_spread,
              'macro': macro_summary(metrics), 'auth_digest': a.auth_digest, 'commit': a.expected_commit,
              'output_manifest_sha256': man_sha, 'preds_test_all_sha256': csv_sha, 'metrics': metrics,
              'results_digest': results_digest(a.auth_digest, a.expected_commit, man_sha, csv_sha, metrics)}
    (a.out / 'verify_report.json').write_text(json.dumps(report, indent=1) + '\n')
    recheck(a.out)  # 写完立刻按复核口径自检：CSV 必须能独立复现报告
    print(json.dumps({k: v for k, v in report.items() if k != 'metrics'}, indent=1))


if __name__ == '__main__':
    main()
