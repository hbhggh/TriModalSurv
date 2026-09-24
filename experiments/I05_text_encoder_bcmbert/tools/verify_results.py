"""I05 结果独立验真（节点二）：不导入评测器，直接从逐患者预测重算全部 C-index 并核对。

核对项：
1. complete.json 的每一行都能找到对应的逐患者预测 npz，从 time/censorship/risk_b 重算 B 口径 C-index，
   与记录值比对（sksurv 可用时用 sksurv；另用按 sksurv 语义独立实现的纯 numpy 版本再算一遍）。
2. 同一单元格内各臂的患者顺序、time、censorship 一致，行记录的患者数与 npz 一致。
3. 每行的 checkpoint_sha256 与 checkpoint-sha256.txt 一致；给出 --checkpoint-root 时，逐个读取 25 个 .pth
   现场计算 sha256 再比对（只有这种模式才能声称核对了 checkpoint 本体）。
4. 从重算值重新做 Q 判定（none、strategy0、五 seed 均值，严格胜才计胜）。

用法:
python3 experiments/I05_text_encoder_bcmbert/tools/verify_results.py \\
    --result-dir "experiments/BioClinical ModernBERT/results/<run_id>" [--out report.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
CANCERS = ('LGG', 'BRCA', 'BLCA', 'LUAD', 'UCEC')
SEEDS = (123, 132, 213, 231, 321)
BASELINE = 'experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/runs/test/complete.json'
TIED_TOL = 1e-8  # 与 sksurv.metrics.concordance_index_censored 的默认 tied_tol 相同


def concordance_numpy(event, time, estimate) -> float:
    """按 sksurv concordance_index_censored 的语义独立实现（Harrell C，风险并列记 0.5）。"""
    event = np.asarray(event, dtype=bool)
    time = np.asarray(time, dtype=float)
    estimate = np.asarray(estimate, dtype=float)
    order = np.argsort(time, kind='mergesort')
    n = len(time)
    numerator = denominator = 0.0
    i = 0
    while i < n - 1:
        time_i = time[order[i]]
        end = i + 1
        while end < n and time[order[end]] == time_i:
            end += 1
        censored_same = ~event[order[i:end]]
        for j in range(i, end):
            if not event[order[j]]:
                continue
            mask = np.zeros(n, dtype=bool)
            mask[end:] = True
            mask[i:end] = censored_same  # 同一时刻的删失样本与该事件可比
            est_i = estimate[order[j]]
            est = estimate[order[mask]]
            ties = np.abs(est - est_i) <= TIED_TOL
            numerator += float((est < est_i)[~ties].sum()) + 0.5 * float(ties.sum())
            denominator += float(mask.sum())
        i = end
    if denominator == 0:
        raise ValueError('没有可比较的样本对')
    return numerator / denominator


def concordance_sksurv(event, time, estimate):
    try:
        from sksurv.metrics import concordance_index_censored
    except ImportError:
        return None
    return float(concordance_index_censored(np.asarray(event, bool), np.asarray(time), np.asarray(estimate))[0])


def load_checkpoint_hashes(path: Path) -> dict:
    hashes = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        digest, name = line.split(maxsplit=1)
        seed = int(name.split('/')[0])
        cancer = name.split('_NPJC_')[1].split('_')[0]
        hashes[(cancer, seed)] = digest
    return hashes


def strategy0_means(rows) -> dict:
    values = defaultdict(list)
    for row in rows:
        if row['protocol'] == 'strategy0' and row['grid'] == 'none':
            values[row['cancer']].append((row['seed'], row['value']))
    means = {}
    for cancer in CANCERS:
        items = sorted(values[cancer])
        if [seed for seed, _ in items] != list(SEEDS):
            raise ValueError(f'{cancer}: none/strategy0 的 seed 不是 {SEEDS}')
        means[cancer] = sum(value for _, value in items) / len(items)
    return means


def hash_checkpoints(root: Path) -> dict:
    """现场读取 <root>/<seed>/*_NPJC_<癌种>_surv.pth 计算 sha256。"""
    hashes = {}
    for seed in SEEDS:
        for path in sorted((Path(root) / str(seed)).glob('*_NPJC_*_surv.pth')):
            cancer = path.name.split('_NPJC_')[1].split('_')[0]
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b''):
                    digest.update(chunk)
            hashes[(cancer, seed)] = digest.hexdigest()
    return hashes


def verify(result_dir: Path, checkpoint_root: Path | None = None) -> dict:
    complete = json.loads((result_dir / 'raw/formal_eval/runs/test/complete.json').read_text(encoding='utf-8'))
    test_dir = result_dir / 'raw/formal_eval/runs/test'
    listed = load_checkpoint_hashes(result_dir / 'raw/logs/checkpoint-sha256.txt')
    actual = hash_checkpoints(checkpoint_root) if checkpoint_root else None
    ckpt = actual if actual is not None else listed
    report = {'n_rows': len(complete['rows']), 'status': complete['status'], 'mismatch_numpy': [],
              'mismatch_sksurv': [], 'label_mismatch': [], 'checkpoint_mismatch': [], 'sksurv_available': None,
              'max_abs_diff_numpy': 0.0, 'max_abs_diff_sksurv': 0.0}
    cells = defaultdict(dict)
    recomputed = []
    for row in complete['rows']:
        key = f"{row['cell']}/{row['prediction_file']}"
        # LUAD 的 strategy0 预测写在 <癌种>/<seed>/<场景>.strategy0/，prediction_file 相对 seed 目录记录
        base = test_dir / row['cell'] if '/' not in row['prediction_file'] else test_dir / Path(row['cell']).parent
        with np.load(base / row['prediction_file'], allow_pickle=False) as data:
            ids, time = data['patient_ids'].tolist(), data['time']
            censorship, risk = data['censorship'], data['risk_b']
        if len(ids) != row['n_patients']:
            report['label_mismatch'].append(f'{key}: 患者数 {len(ids)} != {row["n_patients"]}')
        event = (1 - np.asarray(censorship)).astype(bool)
        by_numpy = concordance_numpy(event, time, risk)
        by_sksurv = concordance_sksurv(event, time, risk)
        report['sksurv_available'] = by_sksurv is not None
        diff = abs(by_numpy - row['c_index_b'])
        report['max_abs_diff_numpy'] = max(report['max_abs_diff_numpy'], diff)
        if diff > 1e-12:
            report['mismatch_numpy'].append(f'{key}: {by_numpy} != {row["c_index_b"]}')
        if by_sksurv is not None:
            diff = abs(by_sksurv - row['c_index_b'])
            report['max_abs_diff_sksurv'] = max(report['max_abs_diff_sksurv'], diff)
            if by_sksurv != row['c_index_b']:
                report['mismatch_sksurv'].append(f'{key}: {by_sksurv} != {row["c_index_b"]}')
        cell = row['cell'].replace('.strategy0', '')
        reference = cells[cell].setdefault('labels', (ids, np.asarray(time).tolist(), np.asarray(censorship).tolist()))
        if reference != (ids, np.asarray(time).tolist(), np.asarray(censorship).tolist()):
            report['label_mismatch'].append(f'{key}: 与同单元格其他臂的患者或标签不一致')
        expected = ckpt.get((row['cancer'], row['seed']))
        if expected != row['checkpoint_sha256']:
            report['checkpoint_mismatch'].append(f"{row['cancer']}/{row['seed']}: {row['checkpoint_sha256'][:12]} != {str(expected)[:12]}")
        recomputed.append({**row, 'value': by_numpy})
    baseline = json.loads((REPO_ROOT / BASELINE).read_text(encoding='utf-8'))
    new = strategy0_means(recomputed)
    old = strategy0_means([{**row, 'value': row['c_index_b']} for row in baseline['rows']])
    deltas = {cancer: new[cancer] - old[cancer] for cancer in CANCERS}
    report.update(checkpoint_check='hashed_checkpoint_files' if actual is not None else 'listed_hashes_only',
                  checkpoint_list_matches_files=(actual == listed) if actual is not None else None)
    if actual is not None and actual != listed:
        report['checkpoint_mismatch'].append('现场计算的 ckpt 哈希与 checkpoint-sha256.txt 不一致')
    report.update(n_checkpoints=len(ckpt), q={
        'new_mean': new, 'baseline_mean': old, 'delta': deltas,
        'strict_wins': sum(delta > 0 for delta in deltas.values()),
        'met': sum(delta > 0 for delta in deltas.values()) >= 4})
    report['ok'] = not (report['mismatch_numpy'] or report['mismatch_sksurv'] or report['label_mismatch']
                        or report['checkpoint_mismatch']) and report['n_rows'] == 300 and len(ckpt) == 25
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--result-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--checkpoint-root', type=Path, help='含 <seed>/*.pth 的训练结果根；给出时现场计算 ckpt 哈希')
    args = parser.parse_args(argv)
    report = verify(args.result_dir, args.checkpoint_root)
    text = json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False)
    if args.out:
        with args.out.open('x', encoding='utf-8') as handle:
            handle.write(text + '\n')
    summary = {key: report[key] for key in ('ok', 'n_rows', 'n_checkpoints', 'checkpoint_check', 'sksurv_available',
                                             'max_abs_diff_numpy', 'max_abs_diff_sksurv')}
    summary['strict_wins'] = report['q']['strict_wins']
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
