"""verify_outputs 的独立 C-index 与 survival.c_index 口径一致（含风险并列与时间并列）。"""
import json

import numpy as np

from experiments.I07_ps3style_backbone import survival, verify_outputs


def test_independent_harrell_matches_survival_c_index():
    rng = np.random.default_rng(3)
    for _ in range(20):
        n = 40
        risk = rng.integers(0, 6, n).astype(float)      # 大量风险并列
        time = rng.integers(1, 10, n).astype(float)     # 大量时间并列
        event = rng.integers(0, 2, n).astype(float)
        event[0] = 1
        time[0] = 0.5                                   # 保证有可比较对
        assert verify_outputs.harrell(risk.tolist(), time.tolist(), event.tolist()) == survival.c_index(risk, time, event)


# ---------- 节点二复审 high：入库 CSV 必须直接进 results_digest，任何改动复核即失败 ----------

import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

VERIFY = Path(__file__).resolve().parents[1] / 'results' / 'i07-ps3-20261011' / 'verify'


@pytest.fixture
def copy(tmp_path):
    d = tmp_path / 'verify'
    shutil.copytree(VERIFY, d)
    return d


def edit_csv(d, line_no, col, value):
    lines = (d / 'preds_test_all.csv').read_text().splitlines()
    cells = lines[line_no].split(',')
    cells[col] = value(cells[col])
    lines[line_no] = ','.join(cells)
    (d / 'preds_test_all.csv').write_text('\n'.join(lines) + '\n')


def test_committed_verify_artifacts_recheck(copy):
    report = verify_outputs.recheck(copy)
    assert report['runs'] == 100 and len(report['metrics']) == 100


@pytest.mark.parametrize('mutate', [
    lambda d: edit_csv(d, 1, 7, lambda v: repr(float(v) + 1e-9)),          # 改一个风险分
    lambda d: edit_csv(d, 2, 5, lambda v: repr(float(v) + 1.0)),           # 改一个生存时间
    lambda d: (d / 'preds_test_all.csv').write_text(
        ''.join((d / 'preds_test_all.csv').read_text().splitlines(keepends=True)[:-1])),  # 删最后一行
])
def test_any_csv_edit_fails_recheck_even_if_report_hash_is_updated(copy, mutate):
    """同时把报告里的 CSV 哈希改成新值，复核仍须失败（指标或 results_digest 对不上）。"""
    mutate(copy)
    rp = copy / 'verify_report.json'
    report = json.loads(rp.read_text())
    report['preds_test_all_sha256'] = verify_outputs.sha(copy / 'preds_test_all.csv')
    rp.write_text(json.dumps(report))
    with pytest.raises(SystemExit, match='核对失败'):
        verify_outputs.recheck(copy)


def test_report_digest_edit_fails_recheck(copy):
    rp = copy / 'verify_report.json'
    report = json.loads(rp.read_text())
    report['results_digest'] = 'f' * 64
    rp.write_text(json.dumps(report))
    with pytest.raises(SystemExit, match='results_digest'):
        verify_outputs.recheck(copy)
