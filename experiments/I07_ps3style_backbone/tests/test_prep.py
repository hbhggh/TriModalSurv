"""I07 Phase 0 数据准备：只测会导致算错或泄漏的地方。"""
import csv
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from experiments.I06_llm_condensation.model import fields_for
from experiments.I07_ps3style_backbone.prep import cohort, io_utils, rna_genes, splits, text_fields, wsi_tokens


# ---------- 病人 ID 与标签 ----------

def test_norm_pid_truncates_and_rejects_garbage():
    assert io_utils.norm_pid('tcga-2f-a9ko-01z') == 'TCGA-2F-A9KO'
    with pytest.raises(ValueError):
        io_utils.norm_pid('ABC')


def write_labels(path, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['patient_id', 'cancer_type', 'survival_months', 'censorship'])
        w.writeheader()
        w.writerows(rows)


def test_labels_reject_bad_censorship_and_duplicates(tmp_path):
    p = tmp_path / 'l.csv'
    write_labels(p, [{'patient_id': 'TCGA-AA-0001', 'cancer_type': 'BLCA', 'survival_months': 3, 'censorship': 2}])
    with pytest.raises(ValueError):
        cohort.load_labels(p)
    write_labels(p, [{'patient_id': 'TCGA-AA-0001', 'cancer_type': 'BLCA', 'survival_months': 3, 'censorship': 0},
                     {'patient_id': 'TCGA-AA-0001-01', 'cancer_type': 'BLCA', 'survival_months': 4, 'censorship': 1}])
    with pytest.raises(ValueError):
        cohort.load_labels(p)


# ---------- 人群清单 ----------

def test_cohort_is_intersection_with_sorted_dx_slides(tmp_path):
    wsi = tmp_path / 'wsi' / 'BLCA'
    wsi.mkdir(parents=True)
    for n in ['TCGA-AA-0001.TCGA-AA-0001-01Z-00-DX2.pkl', 'TCGA-AA-0001.TCGA-AA-0001-01Z-00-DX1.pkl',
              'TCGA-AA-0002.TCGA-AA-0002-01Z-00-DX1.pkl', 'TCGA-AA-0003.TCGA-AA-0003-01Z-00-DX1.pkl']:
        (wsi / n).write_bytes(b'x')
    labels = {'BLCA': {'TCGA-AA-0001': (5.0, 0), 'TCGA-AA-0002': (6.0, 1), 'TCGA-AA-0003': (7.0, 0),
                       'TCGA-AA-0004': (8.0, 0)}}
    rna = {'TCGA-AA-0001': ('d/a.tsv', 'm'), 'TCGA-AA-0002': ('d/b.tsv', 'm'), 'TCGA-AA-0004': ('d/c.tsv', 'm')}
    text_ok = {('BLCA', 'TCGA-AA-0001'), ('BLCA', 'TCGA-AA-0003'), ('BLCA', 'TCGA-AA-0004')}
    rows, summary = cohort.build(labels, tmp_path / 'wsi', rna, text_ok, cancers=('BLCA',))
    assert [r['patient_id'] for r in rows] == ['TCGA-AA-0001']
    assert rows[0]['slides'].split(';') == sorted(rows[0]['slides'].split(';'))
    assert rows[0]['event'] == 1
    assert summary['BLCA'] == {'labels': 4, 'no_wsi': 1, 'no_rna': 1, 'no_text': 1, 'kept': 1, 'events': 1}


def test_cohort_rejects_non_dx_slide(tmp_path):
    d = tmp_path / 'BLCA'
    d.mkdir()
    (d / 'TCGA-AA-0001.TCGA-AA-0001-01Z-00-TS1.pkl').write_bytes(b'x')
    with pytest.raises(ValueError):
        cohort.find_slides(tmp_path, 'BLCA', 'TCGA-AA-0001')


# ---------- 分折 ----------

def make_cohort(n=200, seed=0):
    rng = np.random.default_rng(seed)
    pids = [f'TCGA-AA-{i:04d}' for i in range(n)]
    ev = (rng.random(n) < 0.3).astype(int)
    return pids, ev


def test_splits_disjoint_cover_and_each_patient_tested_once():
    pids, ev = make_cohort()
    res = splits.split_cancer(pids, ev)
    rows = [('X', k, p, part) for k, p, part in res]
    splits.check(rows, [{'cancer': 'X', 'patient_id': p} for p in pids])
    for k in range(5):
        parts = [part for kk, _, part in res if kk == k]
        n = len(parts)
        assert abs(parts.count('test') / n - 0.2) < 0.02
        assert abs(parts.count('val') / n - 0.1) < 0.02


def test_splits_stratified_and_order_independent():
    pids, ev = make_cohort()
    res = splits.split_cancer(pids, ev)
    perm = np.random.default_rng(1).permutation(len(pids))
    res2 = splits.split_cancer([pids[i] for i in perm], [ev[i] for i in perm])
    assert sorted(res) == sorted(res2)
    rate = ev.mean()
    evmap = dict(zip(pids, ev))
    for k in range(5):
        test = [evmap[p] for kk, p, part in res if kk == k and part == 'test']
        assert abs(np.mean(test) - rate) < 0.05


def test_split_check_catches_leak():
    pids, ev = make_cohort(50)
    res = splits.split_cancer(pids, ev)
    leaked = [('X', k, p, 'train' if (k == 0 and part == 'test' and p == res[-1][1]) else part)
              for k, p, part in res]
    with pytest.raises(AssertionError):
        splits.check(leaked + [('X', 0, pids[0], 'val')], [{'cancer': 'X', 'patient_id': p} for p in pids])


# ---------- WSI token ----------

def test_patient_tokens_multi_slide_padding_and_mask():
    rng = np.random.default_rng(0)
    slides = [rng.normal(size=(300, wsi_tokens.DIM)).astype(np.float32) for _ in range(3)]
    tok, mask = wsi_tokens.patient_tokens(slides)
    assert tok.shape == (128, wsi_tokens.DIM) and tok.dtype == np.float32
    assert mask.sum() == 3 * (128 // 3) == 126
    assert not mask[126:].any() and np.all(tok[126:] == 0)
    tok2, mask2 = wsi_tokens.patient_tokens(slides)
    assert np.array_equal(tok, tok2) and np.array_equal(mask, mask2)


def test_small_slide_keeps_raw_patches_and_rejects_nan():
    x = np.ones((10, wsi_tokens.DIM), np.float32)
    tok, mask = wsi_tokens.patient_tokens([x])
    assert mask.sum() == 10 and np.all(tok[:10] == 1)
    x[0, 0] = np.nan
    with pytest.raises(ValueError):
        wsi_tokens.patient_tokens([x])


def test_wsi_run_refuses_overwrite_and_resume_revalidates(tmp_path, monkeypatch):
    rows = [{'cancer': 'BLCA', 'patient_id': 'TCGA-AA-0001', 'slides': 's1.pkl'}]
    monkeypatch.setattr(wsi_tokens, 'load_slide', lambda p: np.ones((5, wsi_tokens.DIM), np.float32))
    assert wsi_tokens.run(rows, tmp_path, tmp_path / 'out') == 1
    with pytest.raises(FileExistsError):
        wsi_tokens.run(rows, tmp_path, tmp_path / 'out')
    assert wsi_tokens.run(rows, tmp_path, tmp_path / 'out', resume=True) == 0
    (tmp_path / 'out' / 'BLCA' / 'TCGA-AA-0001.npz').write_bytes(b'broken')
    assert wsi_tokens.run(rows, tmp_path, tmp_path / 'out', resume=True) == 1


# ---------- RNA ----------

TSV_HEAD = ('# gene-model: GENCODE v36\ngene_id\tgene_name\tgene_type\tunstranded\tstranded_first\tstranded_second'
            '\ttpm_unstranded\tfpkm_unstranded\tfpkm_uq_unstranded\nN_unmapped\t\t\t1\t1\t1\t\t\t\n')


def tsv(rows):
    return TSV_HEAD + ''.join(f'{gid}\t{name}\tprotein_coding\t1\t1\t1\t{tpm}\t1\t1\n' for gid, name, tpm in rows)


def test_read_tpm_sums_par_y_duplicates_and_skips_stats(tmp_path):
    p = tmp_path / 'a.tsv'
    p.write_text(tsv([('ENSG1.1', 'G1', 3.0), ('ENSG1.1_PAR_Y', 'G1', 1.0), ('ENSG2.1', 'G2', 7.0)]))
    s = rna_genes.read_tpm(p)
    assert dict(s) == {'G1': 4.0, 'G2': 7.0}


def test_rna_main_log2_order_missing_and_md5(tmp_path):
    gmt = tmp_path / 'h.gmt'
    gmt.write_text(''.join(f'SET{i}\turl\tG{i}\tZZMISSING\n' for i in range(50)))
    root = tmp_path / 'rna'
    (root / 'd').mkdir(parents=True)
    rows, md5 = [], {}
    for j, pid in enumerate(['TCGA-AA-0001', 'TCGA-AA-0002']):
        f = root / 'd' / f'{j}.tsv'
        f.write_text(tsv([(f'ENSG{i}', f'G{i}', float(i + j)) for i in range(50)]))
        rows.append({'cancer': 'BLCA', 'patient_id': pid, 'rna_file': f'd/{j}.tsv'})
        md5[f'BLCA/{pid}'] = hashlib.md5(f.read_bytes()).hexdigest()
    coh = tmp_path / 'coh'
    coh.mkdir()
    with open(coh / 'cohort.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['cancer', 'patient_id', 'rna_file'])
        w.writeheader()
        w.writerows(rows)
    (coh / 'rna_md5.json').write_text(json.dumps(md5))
    rna_genes.main(['--cohort', str(coh), '--rna-root', str(root), '--gmt', str(gmt), '--out', str(tmp_path / 'o')])
    layout = json.loads((tmp_path / 'o' / 'genes.json').read_text())
    assert layout['genes'] == sorted(f'G{i}' for i in range(50)) and layout['missing_genes'] == ['ZZMISSING']
    with np.load(tmp_path / 'o' / 'rna_BLCA.npz') as z:
        g = layout['genes'].index('G7')
        assert np.isclose(z['X'][1, g], np.log2(1 + 8.0))
    md5['BLCA/TCGA-AA-0002'] = '0' * 32
    (coh / 'rna_md5.json').write_text(json.dumps(md5))
    with pytest.raises(ValueError):
        rna_genes.main(['--cohort', str(coh), '--rna-root', str(root), '--gmt', str(gmt), '--out', str(tmp_path / 'o2')])


# ---------- 文本 ----------

def full_payload(cancer, **over):
    p = {f.key: ([] if f.kind == 'pairs' else 'not mentioned') for f in fields_for(cancer)}
    p.update(over)
    return p


def test_field_sentences_not_mentioned_pairs_and_missing_key():
    fields = fields_for('LUAD')
    p = full_payload('LUAD', histologic_grade='G2', ihc_molecular=[{'name': 'TTF-1', 'result': 'positive'}])
    sents = text_fields.patient_sentences('LUAD', p)
    assert len(sents) == len(fields) == 13
    keys = [f.key for f in fields]
    assert sents[keys.index('histologic_grade')] == 'Histologic grade: G2'
    assert sents[keys.index('ihc_molecular')].endswith('TTF-1: positive')
    assert sents[keys.index('tumor_size')] is None
    del p['tumor_size']
    with pytest.raises(KeyError):
        text_fields.patient_sentences('LUAD', p)


def test_encode_places_vectors_and_mask():
    calls = []

    def fake(sentences):
        calls.append(list(sentences))
        return np.arange(len(sentences) * 768, dtype=np.float32).reshape(-1, 768) + 1
    pays = {'A': full_payload('UCEC', histologic_grade='G3'), 'B': full_payload('UCEC')}
    emb, nm, keys = text_fields.encode_cancer('UCEC', ['A', 'B'], pays, fake)
    j = keys.index('histologic_grade')
    assert emb.shape == (2, 13, 768) and nm.shape == (2, 13)
    assert not nm[0, j] and nm[0].sum() == 12 and nm[1].all()
    assert np.all(emb[1] == 0) and np.all(emb[0, j] != 0)
    assert calls == [['Histologic grade: G3']]
