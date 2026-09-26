"""I06 的四个特征档案（A1 = NeuML + 冻结浓缩文本；A2 = Qwen3-Embedding + 冻结浓缩文本）。替身后端，不需要 transformers。"""
import csv
import hashlib
import json
import pickle

import numpy as np
import pytest

from experiments.I05_text_encoder_bcmbert import evaluate
from experiments.I05_text_encoder_bcmbert import extract_text_features as extract
from experiments.I05_text_encoder_bcmbert import model
from experiments.I05_text_encoder_bcmbert.tests.fakes import FakeModel, FakeTokenizer

NEW = ('a1struct', 'a1summ', 'a2struct', 'a2summ')


@pytest.fixture(scope='module')
def config():
    return evaluate.load_config()


# ----------------------------------------------------------------------------- 规格锁

def test_a1_profiles_share_bcmbert8192_spec_and_a2_profiles_are_qwen(config):
    """v3.12（用户裁决 2026-09-26）：解开 200 上限，A1 与 B2（bcmbert8192）逐项同规格，唯一差别是文本内容。"""
    for profile in ('a1struct', 'a1summ'):
        assert model.spec_from_config(config, profile) == model.spec_from_config(config, 'bcmbert8192')
        assert model.LOCKED_BATCH_SIZE[profile] == model.LOCKED_BATCH_SIZE['bcmbert8192'] == 1
        assert config['text_encoders'][profile]['feature_dir'] == f'data/text_embeddings_{profile}'
    for profile in ('a2struct', 'a2summ'):
        spec = model.spec_from_config(config, profile)
        assert isinstance(spec, model.QwenSpec) and spec.revision == model.QWEN_REVISION
        assert (spec.hidden_size, spec.output_dim, spec.pooling, spec.normalize) == (1024, 768, 'last_token', True)
        assert (spec.max_length, spec.truncation) == (8192, False)
    assert {config['text_encoders'][p]['text_source'] for p in NEW} == {'frozen:struct', 'frozen:summary'}


def test_qwen_spec_tampering_is_rejected(config):
    bad = json.loads(json.dumps(config))
    bad['text_encoders']['a2struct']['output_dim'] = 1024
    with pytest.raises(ValueError, match='锁定值不一致'):
        model.spec_from_config(bad, 'a2struct')


# ----------------------------------------------------------------------------- Qwen 编码

class FakeQwenTokenizer:
    def __call__(self, texts, *, truncation=False, padding=False, return_tensors=None, **_):
        ids = [[(sum(map(ord, w)) % 997) + 3 for w in t.split()] + [2] for t in texts]  # 末尾一个 eos
        if return_tensors == 'pt':
            import torch
            return {'input_ids': torch.tensor(ids), 'attention_mask': torch.ones(len(ids), len(ids[0]), dtype=torch.long)}
        return {'input_ids': ids, 'attention_mask': [[1] * len(x) for x in ids]}


class FakeQwenModel:
    def __init__(self, hidden=1024):
        self.table = np.random.default_rng(1).normal(size=(1000, hidden)).astype(np.float32)

    def eval(self):
        return self

    def __call__(self, *, input_ids, attention_mask):
        import torch
        from types import SimpleNamespace
        return SimpleNamespace(last_hidden_state=torch.from_numpy(self.table[input_ids.cpu().numpy()]))


def test_last_token_mrl_l2_takes_last_token_truncates_and_normalizes():
    hidden = np.zeros((1, 3, 1024), dtype=np.float32)
    hidden[0, -1, :768] = 2.0
    hidden[0, -1, 768:] = 99.0  # 截掉的维度不得影响结果
    hidden[0, 0] = 50.0         # 非最后一个 token 不得影响结果
    vec = model.last_token_mrl_l2(hidden, output_dim=768)
    assert vec.shape == (768,) and vec.dtype == np.float32
    np.testing.assert_allclose(vec, np.full(768, 1 / np.sqrt(768)), rtol=1e-6)
    with pytest.raises(ValueError):
        model.last_token_mrl_l2(np.zeros((2, 3, 1024)), output_dim=768)


def test_qwen_encoder_broadcasts_normalized_vector_and_refuses_overlong():
    enc = model.QwenTextEncoder(FakeQwenTokenizer(), FakeQwenModel(), spec=model.QwenSpec())
    feats, counts = enc.encode_with_counts(['grade 2 carcinoma', 'margins negative'])
    assert counts == [4, 3]
    for feat in feats:
        model.check_feature(feat, context='t', rows=200, hidden_size=768)
        assert np.isclose(np.linalg.norm(feat[0].astype(np.float64)), 1.0, atol=1e-6)
    short = model.QwenTextEncoder(FakeQwenTokenizer(), FakeQwenModel(), spec=model.QwenSpec(max_length=3))
    with pytest.raises(ValueError, match='拒绝截断'):
        short.encode(['one two three four'])


# ----------------------------------------------------------------------------- 提取：冻结文本来源

def _write_labels(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['patient_id', 'cancer_type', 'split', 'survival_months',
                                                    'censorship', 'text'])
        writer.writeheader()
        writer.writerows(rows)


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@pytest.fixture()
def world(tmp_path):
    rows = [{'patient_id': 'P1', 'cancer_type': 'LUAD', 'split': 'train', 'survival_months': 10, 'censorship': 0,
             'text': 'raw report one with many words about the lung adenocarcinoma'},
            {'patient_id': 'P2', 'cancer_type': 'LUAD', 'split': 'test', 'survival_months': 5, 'censorship': 1,
             'text': 'raw report two'}]
    labels = tmp_path / 'labels.csv'
    _write_labels(labels, rows)
    reference = tmp_path / 'text_embeddings_parsed'
    reference.mkdir()
    for pid in ('P1', 'P2'):
        with (reference / f'{pid}.pkl').open('wb') as handle:
            pickle.dump(np.ones((200, 768), dtype=np.float32), handle, protocol=4)
    frozen = tmp_path / 'frozen-struct.jsonl'
    condensed = {'P1': 'Histologic type: adenocarcinoma. Margins: negative.', 'P2': 'Lymph nodes: 0/3.'}
    with frozen.open('w', encoding='utf-8') as handle:
        for pid, split in (('P1', 'train'), ('P2', 'test')):
            text = condensed[pid]
            handle.write(json.dumps({'patient_id': pid, 'cancer': 'LUAD', 'split': split, 'text': text,
                                     'text_sha256': _sha(text), 'status': 'ok'}) + '\n')
    return tmp_path, labels, reference, frozen, condensed


def _extract(root, labels, reference, frozen, profile, out_name, *, sha=None, backend=None, frozen_args=True):
    argv = ['extract', '--labels', str(labels), '--reference-dir', str(reference), '--out-dir',
            str(root / out_name), '--cancers', 'LUAD', '--profile', profile, '--device', 'cpu']
    if frozen_args:
        argv += ['--frozen-texts', str(frozen), '--frozen-sha256', sha or extract.sha256_file(frozen)]
    extract.main(argv, backend=backend or (FakeTokenizer(), FakeModel(), None))
    return json.loads((root / out_name / 'manifest.json').read_text())


def test_a1_extract_encodes_frozen_condensed_text_not_label_text(world):
    root, labels, reference, frozen, condensed = world
    manifest = _extract(root, labels, reference, frozen, 'a1struct', 'a1')
    assert manifest['text_source']['kind'] == 'frozen' and manifest['text_source']['arm'] == 'struct'
    assert manifest['text_source']['sha256'] == extract.sha256_file(frozen)
    assert manifest['patients']['P1']['text_sha256'] == _sha(condensed['P1'])
    spec = model.spec_from_config(evaluate.load_config(), 'a1struct')
    expected = model.FrozenTextEncoder(FakeTokenizer(), FakeModel(), spec=spec).encode([condensed['P1']])[0]
    np.testing.assert_array_equal(extract.load_feature(root / 'a1' / 'P1.pkl'), expected)


def test_a2_extract_uses_qwen_encoder_on_frozen_text(world):
    root, labels, reference, frozen, condensed = world
    manifest = _extract(root, labels, reference, frozen, 'a2struct', 'a2',
                        backend=(FakeQwenTokenizer(), FakeQwenModel(), None))
    assert manifest['encoder']['pooling'] == 'last_token' and manifest['batching']['batch_size'] == 1
    feat = extract.load_feature(root / 'a2' / 'P2.pkl')
    assert feat.shape == (200, 768) and np.isclose(np.linalg.norm(feat[0].astype(np.float64)), 1.0, atol=1e-6)


def test_frozen_text_gates_patient_set_hash_and_source(world):
    root, labels, reference, frozen, _ = world
    with pytest.raises(ValueError, match='哈希不符'):
        _extract(root, labels, reference, frozen, 'a1struct', 'x1', sha='0' * 64)
    with pytest.raises(ValueError, match='必须给出 --frozen-texts'):
        _extract(root, labels, reference, frozen, 'a1summ', 'x2', frozen_args=False)
    with pytest.raises(ValueError, match='不接受 --frozen-texts'):
        _extract(root, labels, reference, frozen, 'bcmbert200', 'x3')
    short = root / 'frozen-short.jsonl'
    short.write_text(frozen.read_text(encoding='utf-8').splitlines()[0] + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='患者集合'):
        _extract(root, labels, reference, short, 'a1struct', 'x4')


def test_qwen_model_file_lock_rejects_mismatch():
    locked = {'model.safetensors': 'a' * 64, 'tokenizer.json': 'b' * 64}
    extract.check_model_files('a2struct', {**locked, 'vocab.json': 'c' * 64}, locked)
    with pytest.raises(ValueError, match='Qwen 模型文件'):
        extract.check_model_files('a2struct', {**locked, 'model.safetensors': 'd' * 64}, locked)


# ----------------------------------------------------------------------------- 评测器：manifest 的文本来源绑定

def _good_manifest(config, profile, text_source):
    section = config['text_encoders'][profile]
    spec = model.spec_from_config(config, profile)
    return {'status': 'complete', 'partial': False, 'schema_version': 2, 'profile': profile, 'slot_rows': 200,
            'batching': {'batch_size': section['batch_size']}, 'encoder': spec.as_dict(),
            'extractor': {'files': evaluate.extractor_source_hashes(), 'git': {'commit': 'x' * 40, 'dirty': False}},
            'model_files': dict(section['model_files_sha256']), 'text_source': text_source, 'patients': {}}


@pytest.mark.parametrize('profile,arm', [('a1struct', 'struct'), ('a2summ', 'summary')])
def test_feature_manifest_binds_frozen_arm(config, tmp_path, profile, arm):
    feature_dir = tmp_path / config['text_encoders'][profile]['feature_dir']
    feature_dir.mkdir(parents=True)
    path = feature_dir / 'manifest.json'
    path.write_text(json.dumps(_good_manifest(config, profile, {'kind': 'frozen', 'arm': arm})))
    evaluate._feature_manifest(config, tmp_path, profile)
    other = 'summary' if arm == 'struct' else 'struct'
    for wrong in ({'kind': 'frozen', 'arm': other}, {'kind': 'labels'}):
        path.write_text(json.dumps(_good_manifest(config, profile, wrong)))
        with pytest.raises(ValueError, match='冻结的'):
            evaluate._feature_manifest(config, tmp_path, profile)


# ----------------------------------------------------------------------------- 训练记录：I06 必须实际跳过 test

def _record(tmp_path, name, runtime):
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / 'resolved_config.yaml').write_text(json.dumps({'runtime': runtime, 'inputs': []}))
    return run_dir


def test_i06_training_record_requires_actual_skip_test(config, tmp_path):
    """Codex 节点一 finding 2：只看清单 YAML 不够，评测门按实际 resolved_config 的 runtime 核对 skip_test。"""
    runtime = {**config['training_contract']['runtime'], 'seed': 123, 'cancer_types': 'LUAD'}
    legacy = {'preflight': {'reports': {'LUAD': {'provenance': {'label_sha256': 'x' * 64}}}}}
    kwargs = dict(cancer='LUAD', seed=123, run_root=tmp_path)
    for profile in NEW:
        for i, bad in enumerate((runtime, {**runtime, 'skip_test': False})):
            with pytest.raises(ValueError, match=r"训练参数与获审配方不符: \['skip_test'\]"):
                evaluate.check_training_record(_record(tmp_path, f'{profile}-bad{i}', bad), config, legacy,
                                               profile=profile, **kwargs)
        good = _record(tmp_path, f'{profile}-good', {**runtime, 'skip_test': True})
        with pytest.raises(ValueError, match='model_config'):  # 参数门已通过，停在下一道门
            evaluate.check_training_record(good, config, legacy, profile=profile, **kwargs)
    with pytest.raises(ValueError, match='model_config'):  # 已收官的 I05 档案不追溯 skip_test
        evaluate.check_training_record(_record(tmp_path, 'bcmbert200', runtime), config, legacy,
                                       profile='bcmbert200', **kwargs)


def test_runtime_digest_ignores_gpu_id_but_binds_runtime(config, tmp_path):
    """round2 R1：授权绑定的 runtime 摘要换卡不变，换检索后端 / batch 即变。"""
    runtime = config['runtime']

    def digest(**kw):
        args = dict(device='cuda', gpu_id=0, retrieval_backend=runtime['retrieval_backend'],
                    batch_size=runtime['batch_size'], cpu_threads=runtime['cpu_threads'])
        args.update(kw)
        return evaluate.runtime_digest(evaluate.build_upstream_config(
            config, run_root=tmp_path, checkpoint_root=None, execution_root=tmp_path, **args))
    assert digest() == digest(gpu_id=3)
    other = 'reference' if runtime['retrieval_backend'] != 'reference' else 'gpu_cached'
    assert digest() != digest(retrieval_backend=other)
    assert digest() != digest(batch_size=int(runtime['batch_size']) + 1)
