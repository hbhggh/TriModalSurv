"""方案 A 编码器包装与特征提取流程（替身后端，不需要 transformers 与数据）。"""
import csv
import json
import pickle
from pathlib import Path

import numpy as np
import pytest

from experiments.I05_text_encoder_bcmbert import extract_text_features as extract
from experiments.I05_text_encoder_bcmbert import model
from experiments.I05_text_encoder_bcmbert.tests.fakes import FakeModel, FakeTokenizer


def test_masked_mean_broadcast_ignores_pads():
    hidden = np.zeros((2, 5, 3), dtype=np.float32)
    hidden[0, :3] = [[1, 2, 3], [3, 4, 5], [5, 6, 7]]
    hidden[0, 3:] = 1e6  # pad 位的隐藏状态不得进入均值
    hidden[1] = np.arange(15, dtype=np.float32).reshape(5, 3)
    mask = np.array([[1, 1, 1, 0, 0], [1, 1, 1, 1, 1]])
    out, counts = model.masked_mean_broadcast(hidden, mask)
    assert out.dtype == np.float32 and out.shape == (2, 5, 3) and counts.tolist() == [3, 5]
    np.testing.assert_array_equal(out[0], np.tile([3, 4, 5], (5, 1)).astype(np.float32))
    np.testing.assert_allclose(out[1], np.tile(hidden[1].mean(axis=0), (5, 1)))
    # NPJ-C 在槽内做无 mask 的 mean(dim=1)：结果恰等于有效 token 的均值
    np.testing.assert_allclose(out[0].mean(axis=0), [3, 4, 5])


def test_masked_mean_broadcast_rejects_left_padding_bad_mask_and_short():
    hidden = np.ones((1, 4, 2), dtype=np.float32)
    for mask in ([[0, 1, 1, 1]], [[1, 2, 0, 0]], [[1, 1, 0]], [[1, 1, 0, 0]]):
        with pytest.raises(ValueError):
            model.masked_mean_broadcast(hidden, np.array(mask))


@pytest.mark.parametrize('mutate, message', [
    (lambda a: a.astype(np.float64), 'float32'),
    (lambda a: a[:100], '形状'),
    (lambda a: np.where(np.arange(200)[:, None] == 0, np.nan, a).astype(np.float32), '非有限'),
    (lambda a: np.zeros_like(a), '全零'),
    (lambda a: np.concatenate([a[:150], np.zeros((50, 768), np.float32)]), '各行不相同'),
])
def test_check_feature_rejects_bad_arrays(mutate, message):
    good = np.tile(np.linspace(-1, 1, 768, dtype=np.float32), (200, 1))
    assert model.check_feature(good, context='ok') is None
    with pytest.raises(ValueError, match=message):
        model.check_feature(mutate(good), context='bad')


def test_transformers_version_gate():
    assert model.transformers_version_ok('4.48.0')
    assert model.transformers_version_ok('4.52.4')
    assert model.transformers_version_ok('5.0.0.dev0')
    assert not model.transformers_version_ok('4.47.1')


def test_frozen_encoder_fills_slot_with_broadcast_mean():
    encoder = model.FrozenTextEncoder(FakeTokenizer(), FakeModel(), batch_size=2)
    texts = ['grade 3 invasive carcinoma', ' '.join(['word'] * 400), 'tumor free margins']
    features, counts = encoder.encode_with_counts(texts)
    assert [f.shape for f in features] == [(200, 768)] * 3
    assert all(f.dtype == np.float32 for f in features)
    for index, feature in enumerate(features):
        model.check_feature(feature, context=str(index))
    assert counts == [6, 200, 5]
    assert encoder.token_lengths(texts) == [6, 402, 5]
    np.testing.assert_array_equal(encoder.encode(texts)[0], features[0])
    with pytest.raises(ValueError):
        encoder.encode(['   '])


def _write_labels(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['patient_id', 'cancer_type', 'split', 'survival_months',
                                                    'censorship', 'text'])
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture()
def workspace(tmp_path):
    rows = [
        {'patient_id': 'P1', 'cancer_type': 'LUAD', 'split': 'train', 'survival_months': 10, 'censorship': 0,
         'text': 'adenocarcinoma of lung grade 2'},
        {'patient_id': 'P2', 'cancer_type': 'LUAD', 'split': 'test', 'survival_months': 5, 'censorship': 1,
         'text': 'poorly differentiated tumor'},
        {'patient_id': 'P3', 'cancer_type': 'LUAD', 'split': 'valid', 'survival_months': 7, 'censorship': 0,
         'text': 'report without old feature'},
        {'patient_id': 'P4', 'cancer_type': 'BRCA', 'split': 'train', 'survival_months': 3, 'censorship': 0,
         'text': 'ductal carcinoma'},
    ]
    labels = tmp_path / 'labels.csv'
    _write_labels(labels, rows)
    reference = tmp_path / 'text_embeddings_parsed'
    reference.mkdir()
    old = np.ones((200, 768), dtype=np.float32)
    for pid in ('P1', 'P2', 'P4'):
        with (reference / f'{pid}.pkl').open('wb') as handle:
            pickle.dump(old, handle, protocol=4)
    return tmp_path, labels, reference


def test_extract_only_encodes_reference_patients(workspace):
    root, labels, reference = workspace
    out = root / 'text_embeddings_bcmbert200'
    extract.main(['extract', '--labels', str(labels), '--reference-dir', str(reference), '--out-dir', str(out),
                  '--cancers', 'LUAD', 'BRCA', '--batch-size', '2', '--device', 'cpu'],
                 backend=(FakeTokenizer(), FakeModel(), None))
    assert sorted(path.name for path in out.glob('*.pkl')) == ['P1.pkl', 'P2.pkl', 'P4.pkl']
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['status'] == 'complete' and manifest['partial'] is False
    assert manifest['encoder']['revision'] == model.REVISION
    assert manifest['not_generated_text_without_reference'] == 1
    assert manifest['counts'] == {'BRCA': {'train': 1}, 'LUAD': {'test': 1, 'train': 1}}
    for pid, entry in manifest['patients'].items():
        array = extract.load_feature(out / f'{pid}.pkl')
        assert entry['sha256'] == extract.sha256_file(out / f'{pid}.pkl')
        model.check_feature(array, context=pid)
        assert 3 <= entry['n_valid_tokens'] <= 200
        assert array.shape == (200, 768) and array.dtype == np.float32
    assert set(manifest['extractor']['files']) == {f'experiments/I05_text_encoder_bcmbert/{name}'
                                                    for name in extract.SOURCE_FILES}


def test_extract_refuses_missing_text_and_unsafe_outputs(workspace):
    root, labels, reference = workspace
    backend = (FakeTokenizer(), FakeModel(), None)
    with (reference / 'P3.pkl').open('wb') as handle:
        pickle.dump(np.ones((200, 768), np.float32), handle)
    rows = list(csv.DictReader(labels.open(encoding='utf-8')))
    rows[2]['text'] = '  '
    _write_labels(labels, rows)
    with pytest.raises(ValueError, match='缺报告原文'):
        extract.main(['extract', '--labels', str(labels), '--reference-dir', str(reference),
                      '--out-dir', str(root / 'new'), '--cancers', 'LUAD', '--device', 'cpu'], backend=backend)
    with pytest.raises(ValueError, match='旧 Text 特征目录'):
        extract.main(['extract', '--labels', str(labels), '--reference-dir', str(reference),
                      '--out-dir', str(reference / 'nested'), '--cancers', 'BRCA', '--device', 'cpu'],
                     backend=backend)
    busy = root / 'busy'
    busy.mkdir()
    (busy / 'keep.txt').write_text('x')
    with pytest.raises(FileExistsError):
        extract.main(['extract', '--labels', str(labels), '--reference-dir', str(reference),
                      '--out-dir', str(busy), '--cancers', 'BRCA', '--device', 'cpu'], backend=backend)


def test_extract_limit_marks_partial(workspace):
    root, labels, reference = workspace
    out = root / 'smoke'
    extract.main(['extract', '--labels', str(labels), '--reference-dir', str(reference), '--out-dir', str(out),
                  '--cancers', 'LUAD', '--limit', '1', '--device', 'cpu'],
                 backend=(FakeTokenizer(), FakeModel(), None))
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['partial'] is True and len(manifest['patients']) == 1


def test_duplicate_patient_ids_rejected(tmp_path):
    labels = tmp_path / 'labels.csv'
    _write_labels(labels, [{'patient_id': 'A', 'cancer_type': 'LUAD', 'split': 'train', 'survival_months': 1,
                            'censorship': 0, 'text': 'x'}] * 2)
    with pytest.raises(ValueError, match='重复'):
        extract.read_labels(labels, text_column='text')


def test_audit_reports_row_shapes_and_hints(workspace):
    root, labels, reference = workspace
    tiled = np.tile(np.arange(768, dtype=np.float32)[None] + 1, (200, 1))
    with (reference / 'P2.pkl').open('wb') as handle:
        pickle.dump(tiled, handle)
    padded = np.ones((200, 768), dtype=np.float32)
    padded[:, 0] = np.arange(200)
    padded[120:] = 0
    with (reference / 'P1.pkl').open('wb') as handle:
        pickle.dump(padded, handle)
    report = extract.cmd_audit(extract.build_parser().parse_args(
        ['audit', '--labels', str(labels), '--reference-dir', str(reference), '--cancers', 'LUAD']),
        tokenizer=FakeTokenizer())
    per_patient = report['reference_features']['per_patient']
    assert per_patient['P1']['n_nonzero_rows'] == 120 and per_patient['P1']['zero_rows_are_suffix']
    assert per_patient['P2']['nonzero_rows_identical']
    assert report['token_lengths']['n_short_reports'] == 2
    assert report['token_lengths']['short_reports_with_all_old_rows_nonzero'] == 1
    assert any('旧 pad 位可能不为零' in hint for hint in report['decision_hints'])
    assert report['read_only'] is True


def test_cache_content_digest_ignores_pickle_protocol():
    value = {'B': np.ones((2, 3), np.float32), 'A': np.zeros((1, 3), np.float32)}
    same = pickle.loads(pickle.dumps(dict(reversed(list(value.items()))), protocol=2))
    assert extract.cache_content_digest(value) == extract.cache_content_digest(same)
    changed = {**value, 'A': np.ones((1, 3), np.float32)}
    assert extract.cache_content_digest(value) != extract.cache_content_digest(changed)


def test_real_extraction_refuses_cpu_before_loading_model(workspace):
    """用户锁定：真实提取必须在 GPU 上运行；没有注入替身后端时，cpu 在加载模型之前就被拒绝。"""
    root, labels, reference = workspace
    with pytest.raises(ValueError, match='禁止使用 CPU'):
        extract.main(['extract', '--labels', str(labels), '--reference-dir', str(reference),
                      '--out-dir', str(root / 'cpu'), '--cancers', 'BRCA', '--device', 'cpu'])
    assert not (root / 'cpu').exists() or not any((root / 'cpu').iterdir())
