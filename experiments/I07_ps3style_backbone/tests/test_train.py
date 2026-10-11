"""I07 Phase 1：只测会导致算错或泄漏的地方（研究计划书 v0.2 第 3 节 Phase 1）。"""
import csv
import itertools
import json

import numpy as np
import pytest
import torch

from experiments.I07_ps3style_backbone import data, evaluate, model as model_mod, provenance, survival, train

from experiments.I07_ps3style_backbone.prep.io_utils import write_manifest  # noqa: E402

torch.set_num_threads(1)


# ---------- Cox 损失与 C-index ----------

def cox_brute(risk, time, event):
    risk, time, event = (np.asarray(x, dtype=np.float64) for x in (risk, time, event))
    total = 0.0
    for i in np.flatnonzero(event == 1):
        rs = time >= time[i]
        total += risk[i] - np.log(np.exp(risk[rs]).sum())
    return -total / max(event.sum(), 1)


def test_cox_loss_matches_brute_force_with_ties():
    rng = np.random.default_rng(0)
    r = rng.normal(size=12)
    t = np.array([5, 3, 3, 8, 1, 3, 9, 2, 2, 7, 6, 4], float)
    e = np.array([1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1], float)
    got = survival.cox_loss(torch.tensor(r), torch.tensor(t), torch.tensor(e)).item()
    assert np.isclose(got, cox_brute(r, t, e))


def test_cox_loss_zero_events_is_zero_with_zero_grad():
    r = torch.randn(5, requires_grad=True)
    loss = survival.cox_loss(r, torch.arange(5.0), torch.zeros(5))
    loss.backward()
    assert loss.item() == 0 and torch.all(r.grad == 0)


def test_c_index_direction_ties_and_no_pairs():
    t, e = [1, 2, 3, 4], [1, 1, 1, 0]
    assert survival.c_index([4, 3, 2, 1], t, e) == 1.0
    assert survival.c_index([1, 2, 3, 4], t, e) == 0.0
    assert survival.c_index([1, 1, 1, 1], t, e) == 0.5
    with pytest.raises(ValueError):
        survival.c_index([1, 2], [1, 2], [0, 0])


# ---------- 合成资产 ----------

N_PER = {'train': 70, 'val': 10, 'test': 20}
PATHWAYS = [[0, 1], [2, 3, 4], [5]]
N_FIELDS = 4


def write_assets(root, seed=0, test_override=None):
    rng = np.random.default_rng(seed)
    pids = [f'TCGA-AA-{i:04d}' for i in range(sum(N_PER.values()))]
    parts = ['train'] * N_PER['train'] + ['val'] * N_PER['val'] + ['test'] * N_PER['test']
    for d in ('cohort', 'splits', 'rna', 'text', 'wsi_tokens/BLCA'):
        (root / d).mkdir(parents=True, exist_ok=True)
    time = rng.uniform(1, 100, len(pids))
    event = rng.integers(0, 2, len(pids))
    rna = rng.normal(size=(len(pids), 6)).astype(np.float32)
    txt = rng.normal(size=(len(pids), N_FIELDS, 768)).astype(np.float32)
    nm = rng.random((len(pids), N_FIELDS)) < 0.3
    if test_override:
        for i, part in enumerate(parts):
            if part == 'test':
                time[i], event[i] = 999.0, 1 - event[i]
                rna[i] += 50.0
                txt[i] *= -3
    with open(root / 'cohort' / 'cohort.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cancer', 'patient_id', 'survival_months', 'event'])
        w.writerows(['BLCA', p, time[i], event[i]] for i, p in enumerate(pids))
    with open(root / 'splits' / 'splits.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cancer', 'fold', 'patient_id', 'part'])
        w.writerows(['BLCA', 0, p, parts[i]] for i, p in enumerate(pids))
    np.savez(root / 'rna' / 'rna_BLCA.npz', patient_ids=np.array(pids), X=rna)
    (root / 'rna' / 'genes.json').write_text(json.dumps({'genes': [f'G{i}' for i in range(6)],
                                                          'pathways': {f'P{i}': p for i, p in enumerate(PATHWAYS)}}))
    np.savez(root / 'text' / 'text_BLCA.npz', patient_ids=np.array(pids), emb=txt, not_mentioned=nm,
             field_keys=np.array([f'f{i}' for i in range(N_FIELDS)]))
    for i, p in enumerate(pids):
        tok = rng.normal(size=(128, 1536)).astype(np.float32)
        mask = np.zeros(128, bool)
        mask[:100] = True
        tok[~mask] = 0
        if test_override and parts[i] == 'test':
            tok *= 7
        np.savez(root / 'wsi_tokens' / 'BLCA' / f'{p}.npz', tokens=tok, mask=mask)
    for sub, name in provenance.ASSET_MANIFESTS:  # load_fold 只按 manifest 读取
        write_manifest(root / sub, name, {})
    return pids


@pytest.fixture(scope='module')
def assets(tmp_path_factory):
    clean = tmp_path_factory.mktemp('clean')
    dirty = tmp_path_factory.mktemp('dirty')
    write_assets(clean)
    write_assets(dirty, test_override=True)
    return clean, dirty


def test_rna_zscore_uses_train_only(assets):
    clean, dirty = assets
    a, _ = data.load_fold(clean, 'BLCA', 0)
    b, _ = data.load_fold(dirty, 'BLCA', 0)
    for part in ('train', 'val'):
        assert torch.equal(a[part].rna, b[part].rna)
    assert torch.allclose(a['train'].rna.mean(0), torch.zeros(6), atol=1e-5)


# ---------- 模型的 mask ----------

def small_model(arm='tri'):
    torch.manual_seed(0)
    m = model_mod.PS3Style(PATHWAYS, N_FIELDS, d=32, modalities=train.ARMS[arm], dropout=0.0)
    return m.eval()


def test_padded_wsi_tokens_do_not_affect_output(assets):
    parts, _ = data.load_fold(assets[0], 'BLCA', 0)
    p = parts['val']
    m = small_model()
    with torch.no_grad():
        r1 = m(p)['risk']
        p.wsi[~p.wsi_mask] = 123.0
        r2 = m(p)['risk']
    assert torch.allclose(r1, r2, atol=1e-6)


def test_absent_modality_inputs_do_not_affect_masked_prediction(assets):
    parts, _ = data.load_fold(assets[0], 'BLCA', 0)
    p = parts['val']
    m = small_model()
    fill = {'rna': torch.zeros(32), 'text': torch.zeros(32)}
    with torch.no_grad():
        r1 = m(p, present=('wsi',), fill=fill)['risk']
        p.rna += 9.0
        p.text *= -2
        p.text_nm = ~p.text_nm
        r2 = m(p, present=('wsi',), fill=fill)['risk']
    assert torch.allclose(r1, r2, atol=1e-6)
    with pytest.raises(ValueError):
        m(p, present=('wsi',))


def test_single_modality_arm_ignores_other_modalities(assets):
    parts, _ = data.load_fold(assets[0], 'BLCA', 0)
    p = parts['val']
    m = small_model('text')
    with torch.no_grad():
        r1 = m(p)['risk']
        p.wsi *= 5
        p.rna += 3
        r2 = m(p)['risk']
    assert torch.allclose(r1, r2, atol=1e-6)


# ---------- 训练与评估不碰 test ----------

CFG = dict(train.DEFAULTS, d=32, epochs=3, batch_size=16, dropout=0.0)


def run_training(root, tmp):
    parts, meta = data.load_fold(root, 'BLCA', 0)
    torch.manual_seed(1)
    m = train.build_model(meta, 'tri', CFG)
    res = train.train(m, parts['train'], parts['val'], CFG, tmp, log=lambda *_: None)
    return res, (tmp / 'curves.csv').read_text(), m, parts


def test_training_and_selection_never_touch_test(assets, tmp_path):
    clean, dirty = assets
    r1, c1, m1, _ = run_training(clean, tmp_path / 'a')
    r2, c2, m2, _ = run_training(dirty, tmp_path / 'b')
    assert r1 == r2 and c1 == c2
    for (k, v1), v2 in zip(m1.state_dict().items(), m2.state_dict().values()):
        assert torch.equal(v1, v2), k
    rows = list(csv.DictReader(c1.splitlines()))
    assert [int(r['epoch']) for r in rows] == [1, 2, 3]
    best = min(rows, key=lambda r: float(r['val_loss']))
    assert int(best['epoch']) == r1['best_epoch'] and int(best['is_best']) == 1


def test_train_mean_fill_uses_train_part_only(assets, tmp_path):
    clean, dirty = assets
    _, _, m1, p1 = run_training(clean, tmp_path / 'a')
    _, _, m2, p2 = run_training(dirty, tmp_path / 'b')
    a, b = evaluate.train_means(m1, p1['train']), evaluate.train_means(m2, p2['train'])
    for k in a:
        assert torch.equal(a[k], b[k])
    metrics, preds, _, _ = evaluate.evaluate(m1, p1, 'tri')
    assert set(metrics) == {'full'} | {f'only_{m}__{f}' for m, f in itertools.product(('rna', 'wsi', 'text'),
                                                                                     ('zero', 'train_mean'))}
    assert all(0.0 <= v <= 1.0 for v in metrics.values())


# ---------- 拟合判定（研究计划书第 5 节，规则冻结）----------

from experiments.I07_ps3style_backbone import render  # noqa: E402


def curves(train_loss, val_loss):
    return [{'epoch': i + 1, 'train_loss': t, 'val_loss': v} for i, (t, v) in enumerate(zip(train_loss, val_loss))]


def test_fit_labels_follow_frozen_rules():
    ep = np.arange(50)
    tr = 3.0 - 0.02 * ep
    assert render.fit_label(curves(tr, 3.0 - 0.01 * ep)) == 'underfit'           # 验证损失到最后还在降
    v = np.r_[3.0 - 0.05 * ep[:20], 2.0 + 0.02 * (ep[20:] - 19)]
    assert render.fit_label(curves(tr, v)) == 'overfit'                           # 第 20 个 epoch 最低，之后升 >10%
    assert render.fit_label(curves(np.full(50, 3.0), np.full(50, 3.0))) == 'failed'  # 训练损失几乎不降
    tr_nan = tr.copy()
    tr_nan[5] = np.nan
    assert render.fit_label(curves(tr_nan, 3.0 - 0.01 * ep)) == 'failed'
    v = np.r_[3.0 - 0.03 * ep[:35], np.full(15, 1.98)]
    assert render.fit_label(curves(tr, v)) == 'normal'                            # 第 35 个 epoch 后走平


# ---------- 训练入口不读 test（节点一首审 high 1）----------

def test_train_load_reads_no_test_files(assets, monkeypatch):
    clean, _ = assets
    test_pids = {r['patient_id'] for r in csv.DictReader(open(clean / 'splits' / 'splits.csv')) if r['part'] == 'test'}
    opened = []
    real = provenance.AssetReader.read
    monkeypatch.setattr(provenance.AssetReader, 'read', lambda self, sub, rel: (opened.append(f'{sub}/{rel}'), real(self, sub, rel))[1])
    parts, _ = data.load_fold(clean, 'BLCA', 0, parts=('train', 'val'))
    assert set(parts) == {'train', 'val'}
    assert any(path.startswith('wsi_tokens/') for path in opened)  # 监视点确实覆盖了数据读取
    assert not any(pid in path for path in opened for pid in test_pids)
    assert not test_pids & {p for part in parts.values() for p in part.patient_ids}
    with pytest.raises(ValueError):
        data.load_fold(clean, 'BLCA', 0, parts=('val', 'test'))
