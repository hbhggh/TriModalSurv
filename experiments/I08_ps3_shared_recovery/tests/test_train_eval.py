"""I08 train_eval 端到端冒烟（合成缓存）：12 组方法齐全、α_max=0 格点与 M2 逐值相同、Full 直通、报告可生成、
结果哈希绑定、不写 test。"""
import json

import numpy as np
import pytest
import torch

from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I08_ps3_shared_recovery import cache, contract, train_eval
from experiments.I08_ps3_shared_recovery.contract import PATTERNS, VIEWS, targets, visible

D = 40


def synth_arrays(seed, n_tr=60, n_va=24):
    g = np.random.default_rng(seed)
    w = g.normal(size=3 * D).astype(np.float32) * 0.2
    b = np.array([0.1], dtype=np.float32)
    A = {m: g.normal(size=(4, D)) for m in MODALITIES}
    arrays = {'head_w': w, 'head_b': b}
    for s, n, off in (('train', n_tr, 0), ('val', n_va, 1000)):
        f = g.normal(size=(n, 4))
        pf = {m: (f @ A[m] + 0.5 * g.normal(size=(n, D))).astype(np.float32) for m in MODALITIES}
        time = g.uniform(1, 100, n).astype(np.float32)
        event = (f[:, 0] + 0.5 * g.normal(size=n) > 0).astype(np.float32)
        arrays[f'{s}__time'], arrays[f'{s}__event'] = time, event
        arrays[f'{s}__patient_ids'] = np.array([f'P{off + i}' for i in range(n)])
        for m in MODALITIES:
            arrays[f'{s}__p__full__{m}'] = pf[m]
        arrays[f'{s}__risk_full'] = (np.concatenate([pf[m] for m in MODALITIES], 1) @ w + b).astype(np.float32)
        for pat in PATTERNS:
            pv = {m: (pf[m] + 0.1 * g.normal(size=(n, D))).astype(np.float32) for m in visible(pat)}
            for m, v in pv.items():
                arrays[f'{s}__p__{pat}__{m}'] = v
            hin = np.concatenate([pv[m] if m in pv else np.zeros((n, D), np.float32) for m in MODALITIES], 1)
            arrays[f'{s}__risk_zero__{pat}'] = (hin @ w + b).astype(np.float32)
    return arrays


@pytest.fixture(scope='module')
def cfg():
    return contract.load_config()[0]


@pytest.fixture(scope='module')
def fold_run(cfg):
    ft = cache.fold_tensors(synth_arrays(0))
    return train_eval.run_fold(ft, cfg, max_epochs=4)


def test_all_methods_present(fold_run):
    summary, preds, _ = fold_run
    want = set(train_eval.METHODS) | {'M9-base'}
    assert want <= set(summary['methods'])
    for n in ('M1-a', 'M1-b', 'M2', 'M3', 'M4-a', 'M4-b', 'M5', 'M6-a', 'M6-b', 'M7', 'M8', 'M9', 'M10-a', 'M10-b', 'M10-c'):
        assert n + '@default' in summary['methods'], n
    for n, d in preds.items():
        assert set(d) == set(PATTERNS)


def test_full_column_is_i07_bypass(fold_run):
    summary, _, ex = fold_run
    fulls = {round(m['val']['cindex']['full'], 12) for m in summary['methods'].values()}
    assert len(fulls) == 1


def test_m0a_equals_m0b_cindex(fold_run):
    s = fold_run[0]['methods']
    for p in PATTERNS:
        assert s['M0-a']['val']['cindex'][p] == pytest.approx(s['M0-b']['val']['cindex'][p], abs=1e-12)


def test_alpha_zero_grid_point_reproduces_m2_exactly(fold_run, cfg):
    _, _, ex = fold_run
    plugin = ex['plugins_def']['in_fold']
    r0 = plugin.b6(10, 0.1, 0.0)
    for p in PATTERNS:
        assert float((r0[p] - plugin.L['val']['risk'][p]).abs().max()) == 0.0
    r1 = plugin.b6(10, 0.1, 0.5)
    assert any(float((r1[p] - plugin.L['val']['risk'][p]).abs().max()) > 0 for p in PATTERNS)


def test_shared_basis_across_stage2b(fold_run):
    """M3–M6 的基座是同一个 M2 选中配置（固定坐标系）。"""
    s = fold_run[0]['methods']
    for n in ('M3', 'M4-a', 'M4-b', 'M5', 'M6-a', 'M6-b'):
        assert s[n]['base'] == s['M2']['hparams'], n


def test_interpretability_fields(fold_run):
    it = fold_run[0]['interpretability']
    assert set(it['mechanism']) == set(MODALITIES)
    assert 0 <= it['stability']['jaccard_mean'] <= 1
    assert len(it['faithfulness']['abs_dh_top1']) == 24 * 6
    assert len(it['utility']['dE']) == 24 * 6


def test_cli_run_and_report(tmp_path, cfg):
    cdir = tmp_path / 'cache'
    cdir.mkdir()
    man = {'files': {}}
    for c in ('BLCA', 'BRCA'):
        blob = cache.npz_bytes(synth_arrays(hash(c) % 1000))
        name = cache.fold_name(c, 0)
        (cdir / name).write_bytes(blob)
        man['files'][name] = {'sha256': cache.sha256(blob)}
    (cdir / 'manifest.json').write_text(json.dumps(man))
    out = tmp_path / 'res'
    train_eval.main(['run', '--cache', str(cdir), '--out', str(out), '--cancers', 'BLCA,BRCA', '--folds', '0',
                     '--max-epochs', '3'])
    train_eval.main(['report', '--out', str(out)])
    md = (out / 'val_ablation_report_v1.md').read_text()
    for h in ('表 1', '表 2', '表 3', '表 4', '表 5', 'M6-a@default', 'M10-c'):
        assert h in md, h
    assert not any('test' in p.name for p in (out / 'val_runs').iterdir())
    with pytest.raises(FileExistsError):                                    # 不覆盖已有结果目录
        train_eval.main(['run', '--cache', str(cdir), '--out', str(out), '--cancers', 'BLCA', '--folds', '0',
                         '--max-epochs', '2'])
    # 篡改结果文件 → 报告拒绝
    f = out / 'val_runs' / 'BLCA_fold0.json'
    f.write_text(f.read_text().replace('"fold": 0', '"fold": 0 '))
    with pytest.raises(PermissionError):
        train_eval.main(['report', '--out', str(out)])
