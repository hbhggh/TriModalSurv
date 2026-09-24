"""CPU 合成数据端到端：assets → preflight → smoke（bcmbert200 档案），以及各道门的拒绝路径。

合成一个 LUAD 队列：train 6 人（T5 缺 Text）、valid 2 人、test 4 人（Q2 缺 RNA、Q3 缺 Text），
形状与正式口径相同（img 128×1536、text 200×768、rna 2048×256）。历史证据用本测试生成的替身，
所以只能跑 assets/preflight/smoke；replay/test 必须用锁定的真实证据，不在本地运行。
"""
import csv
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip('torch')

from experiments.I05_text_encoder_bcmbert import evaluate  # noqa: E402
from experiments.I05_text_encoder_bcmbert import model as encoder_model  # noqa: E402
from experiments.I05_text_encoder_bcmbert.extract_text_features import sha256_file  # noqa: E402

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
CANCER = 'LUAD'
SPLITS = {'train': [f'T{i}' for i in range(6)], 'valid': ['V0', 'V1'], 'test': [f'Q{i}' for i in range(4)]}
NO_TEXT = {'T5', 'Q3'}
NO_RNA = {'Q2'}
COMMIT = 'c0ffee' * 6 + 'c0fe'


def _cache_name(modality, split):
    return f'{modality}_sur_{split}_all_{CANCER}.pkl'


def _dump(path, value):
    with Path(path).open('wb') as handle:
        pickle.dump(value, handle, protocol=4)


@pytest.fixture(scope='module')
def config():
    return evaluate.load_config(EXPERIMENT_DIR / 'config.yaml')


IDENTITY = {'source': 'git', 'commit': COMMIT, 'branch': None, 'dirty': False, 'allow_dirty': False}


@pytest.fixture(scope='module', autouse=True)
def injected_test_identity(tmp_path_factory):
    """源码身份与 CPU 放行只经测试注入（CLI 无旁路）：本模块的合成运行使用固定的干净身份 COMMIT。

    冻结的 run worktree 里有真实 GIT_STAMP.json，会与注入的假身份冲突（生产逻辑正确地拒跑）；
    所以 GIT_STAMP 核对改看一个空目录，测试结果与是否在冻结工作树里运行无关。
    """
    import functools
    no_stamp = tmp_path_factory.mktemp('no_git_stamp')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(evaluate, 'source_identity', lambda closure, *, allow_dirty: dict(IDENTITY))
        patch.setattr(evaluate, 'resolve_expected_commit',
                      functools.partial(evaluate.resolve_expected_commit, repo_root=no_stamp))
        patch.setattr(evaluate, 'ALLOW_CPU_FOR_SYNTHETIC_TESTS', True)
        yield


@pytest.fixture(scope='module')
def synthetic(tmp_path_factory, config):
    root = tmp_path_factory.mktemp('i05_e2e')
    run_root = root / 'run'
    data = run_root / 'data'
    features = data / 'text_embeddings_bcmbert200'
    cache = run_root / 'tmp_sur_cache'
    # 与 README 的运行根布局一致：新特征目录是指向运行根外可变资产根的软链。
    external = root / 'mutable' / 'text_embeddings_bcmbert200'
    for directory in (external, data, cache):
        directory.mkdir(parents=True)
    features.symlink_to(external, target_is_directory=True)
    rng = np.random.default_rng(0)
    rows, patients = [], {}
    for split, ids in SPLITS.items():
        caches = {'img': {}, 'rna': {}, 'text': {}}
        for index, pid in enumerate(ids):
            rows.append({'patient_id': pid, 'cancer_type': CANCER, 'split': split,
                         'survival_months': 5 + 7 * index, 'censorship': index % 2, 'text': f'report {pid}'})
            caches['img'][pid] = rng.normal(size=(128, 1536)).astype(np.float32)
            if pid not in NO_RNA:
                caches['rna'][pid] = rng.normal(size=(2048, 256)).astype(np.float32)
            if pid not in NO_TEXT:
                text = np.zeros((200, 768), np.float32)
                length = 20 + 30 * index
                text[:length] = rng.normal(size=(length, 768)).astype(np.float32) + 0.1
                caches['text'][pid] = text
                _dump(features / f'{pid}.pkl', text)
                patients[pid] = {'cancer': CANCER, 'split': split, 'sha256': sha256_file(features / f'{pid}.pkl')}
        for modality, value in caches.items():
            _dump(cache / _cache_name(modality, split), value)
    with (data / 'TCGA_9523_ex12.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (data / 'missing_manifest_v1.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['patient_id', 'cancer'])
        writer.writeheader()
        writer.writerows({'patient_id': pid, 'cancer': CANCER} for pid in SPLITS['test'])
    (features / 'manifest.json').write_text(json.dumps({
        'status': 'complete', 'partial': False, 'encoder': encoder_model.spec_from_config(config, 'bcmbert200').as_dict(),
        'patients': patients}))

    # 训练前资产锁：先跑 assets 阶段锁定内容，之后才“开始训练”（写 run record）。
    early = {'root': root, 'run_root': run_root}
    assert evaluate.main(_argv(early, 'assets', 'bcmbert200', 'exec', *_legacy(early, 'lock'))) == 0
    lock = root / 'exec' / 'runs' / 'assets' / evaluate.ASSETS_LOCK
    assert json.loads(lock.read_text())['commit'] == COMMIT

    up = evaluate.Upstream(config)
    checkpoint_root = root / 'weights'
    ucfg = evaluate.build_upstream_config(config, run_root=run_root, checkpoint_root=checkpoint_root,
                                          execution_root=root / 'unused', device='cpu', gpu_id=None,
                                          retrieval_backend='reference', batch_size=2, cpu_threads=1)
    torch.manual_seed(0)
    network = up.rt.build_model(ucfg, CANCER, 'cpu')
    checkpoint = up.i01.checkpoint_path(checkpoint_root, CANCER, 123)
    checkpoint.parent.mkdir(parents=True)
    torch.save(network.state_dict(), checkpoint)
    state_sha = up.i01.strict_e0_load(network, checkpoint, expected_file_sha=sha256_file(checkpoint))
    record = _start_training_record(checkpoint_root / 'results', 'run1', config, run_root, network, checkpoint)
    (record / 'audit' / 'completion.json').write_text(json.dumps(
        {'status': 'complete', 'checkpoint': {'sha256': sha256_file(checkpoint)}}))
    return {'root': root, 'run_root': run_root, 'checkpoint_root': checkpoint_root, 'checkpoint': checkpoint,
            'lock': lock,
            'state_sha': state_sha, 'record': record}


def _start_training_record(results_root, run_id, config, run_root, network, checkpoint, profile='bcmbert200'):
    """用训练端真实的 resolved_config() 与 start_run_record() 写 run record（bcmbert200 档案）。

    模态路径按 training/runtime.py 的做法在运行根下 resolve（软链被解析到可变资产根）。
    """
    import argparse
    from trimodalsurv import gitstamp
    from trimodalsurv.config import file_fingerprint, resolved_config, start_run_record
    contract = config['training_contract']
    runtime = {**contract['runtime'], 'seed': 123, 'cancer_types': CANCER}
    inputs = [file_fingerprint(run_root / 'data/TCGA_9523_ex12.csv'),
              file_fingerprint(evaluate.REPO_ROOT / contract['model_config'][profile]),
              file_fingerprint(evaluate.REPO_ROOT / contract['gpu_config'])]
    payload = resolved_config(argparse.Namespace(**runtime), network, inputs=inputs, checkpoints=[], sources=[])
    payload['git'] = {'source': 'git', 'commit': COMMIT, 'branch': None, 'dirty': False}
    text = str((run_root / contract['text_path'][profile]).resolve())
    assert text != str(run_root / contract['text_path'][profile])  # 软链确实被解析
    target = start_run_record(results_root, payload, checkpoint_path=checkpoint, run_id=run_id,
                              modalities={'text': {'path': text, 'feature_dim': 768}})
    gitstamp.unwatch_run(target)  # 本测试不走 finalize，避免退出时记 crash
    return target


def _legacy(synthetic, name, *, text='fake', checkpoint='fake'):
    """按需生成历史证据替身：text 缓存哈希可设为"与现文件相同"来模拟陈旧缓存。"""
    run_root = synthetic['run_root']
    cache = run_root / 'tmp_sur_cache'
    actual = {_cache_name(m, s): sha256_file(cache / _cache_name(m, s))
              for m in ('img', 'text', 'rna') for s in ('train', 'valid', 'test')}
    if text == 'fake':
        actual.update({_cache_name('text', s): 'f' * 64 for s in ('train', 'valid', 'test')})
    ckpt = ({'sha256': sha256_file(synthetic['checkpoint']), 'state_sha256': synthetic['state_sha']}
            if checkpoint == 'actual' else {'sha256': '0' * 64, 'state_sha256': '1' * 64})
    report = {
        'provenance': {'label_sha256': sha256_file(run_root / 'data/TCGA_9523_ex12.csv'),
                       'manifest_sha256': sha256_file(run_root / 'data/missing_manifest_v1.csv'),
                       'cache_hashes': {k: v for k, v in actual.items() if '_valid_' not in k},
                       'bank': {'available_counts': {'rna': 6, 'text': 5}}},
        'natural_test_missing': {'rna': 1, 'text': 1},
        'splits': {'train': 6, 'valid': 2, 'test': 4},
        'checkpoints': {'123': ckpt},
    }
    preflight = synthetic['root'] / f'{name}-preflight.json'
    valid = synthetic['root'] / f'{name}-valid.json'
    # 替身证据里的历史 text 患者集合摘要（正式运行取 config.legacy.text_keys_sha256）
    text_keys = {_cache_name('text', s): hashlib.sha256('\n'.join(sorted(p for p in ids if p not in NO_TEXT)).encode())
                 .hexdigest() for s, ids in SPLITS.items()}
    preflight.write_text(json.dumps({'reports': {CANCER: report}, 'text_keys_sha256': text_keys}))
    valid.write_text(json.dumps({'sha256': {k: v for k, v in actual.items() if '_valid_' in k}}))
    return preflight, valid


def _argv(synthetic, stage, profile, execution, preflight, valid, *extra):
    argv = ['--profile', profile, '--stage', stage, '--run-root', str(synthetic['run_root']),
            '--execution-root', str(synthetic['root'] / execution), '--cancers', CANCER,
            '--legacy-preflight', str(preflight), '--legacy-valid-source', str(valid), '--device', 'cpu',
            '--retrieval-backend', 'reference', '--batch-size', '2', '--cpu-threads', '1', *extra]
    if stage != 'assets':
        argv += ['--checkpoint-root', str(synthetic['checkpoint_root']), '--seeds', '123',
                 '--expected-commit', COMMIT]
        if profile != 'legacy-replay':
            argv += ['--assets-lock', str(synthetic['lock'])]
    return argv


def test_bcmbert200_assets_preflight_smoke(synthetic):
    preflight, valid = _legacy(synthetic, 'new')
    for stage in ('assets', 'preflight', 'smoke'):
        assert evaluate.main(_argv(synthetic, stage, 'bcmbert200', 'exec', preflight, valid)) == 0
    runs = synthetic['root'] / 'exec' / 'runs'
    assets = json.loads((runs / 'assets' / 'assets.json').read_text())
    files = assets['assets']['cancers'][CANCER]['files']
    assert {files[_cache_name('text', s)]['status'] for s in ('train', 'valid', 'test')} == {'new'}
    assert {files[_cache_name('img', s)]['status'] for s in ('train', 'valid', 'test')} == {'identical'}
    ready = json.loads((runs / 'preflight' / 'preflight.json').read_text())
    assert ready['status'] == 'READY_SYNTHETIC' and ready['checkpoints'][CANCER]['123']['run_record'] == 'run1'
    assert ready['checkpoints'][CANCER]['123']['training']['text_path'] == 'data/text_embeddings_bcmbert200'
    assert ready['run_root_layout'] == {'frozen_worktree': False}
    assert ready['assets_lock']['locked_at_utc'] < ready['checkpoints'][CANCER]['123']['recorded_at_utc']
    assert {files[_cache_name('text', s)]['content_sha256'] for s in ('train', 'valid', 'test')}
    smoke = json.loads((runs / 'smoke' / 'complete.json').read_text())
    assert smoke['status'] == 'SMOKE_PASS_SYNTHETIC' and smoke['metrics_computed'] is False
    assert sorted((row['grid'], row['protocol']) for row in smoke['rows']) == sorted(
        (grid, protocol) for grid in ('none', 'rna_100', 'text_100', 'both_100')
        for protocol in ('strategy0', 'm1', 'm0real'))
    assert smoke['luad_route_counts'] == {'123/none': {'upstream_combo': 3, 'm1': 1}, '123/rna_100': {'m1': 4},
                                          '123/text_100': {'m0real': 4}, '123/both_100': {'m1': 4}}
    cell = runs / 'smoke' / CANCER / '123'
    with np.load(cell / 'none.strategy0' / 'strategy0.npz') as s0, np.load(cell / 'none' / 'm1.npz') as m1, \
            np.load(cell / 'none' / 'combo-l1-a1-w0p5.npz') as combo:
        ids = s0['patient_ids'].tolist()
        for row, pid in enumerate(ids):
            source = m1 if pid in NO_RNA else combo
            np.testing.assert_array_equal(s0['logits'][row], source['logits'][row])
            assert s0['risk_b'][row] == source['risk_b'][row]
    # 同一配置续跑：逐格核验已有工件后得到相同结果，不覆盖。
    assert evaluate.main(_argv(synthetic, 'smoke', 'bcmbert200', 'exec', preflight, valid)) == 0


def test_stale_text_cache_is_refused(synthetic):
    preflight, valid = _legacy(synthetic, 'stale', text='actual')
    with pytest.raises(ValueError, match='新特征没有生效'):
        evaluate.main(_argv(synthetic, 'assets', 'bcmbert200', 'exec-stale', preflight, valid))


def test_legacy_profiles_and_checkpoint_gates(synthetic, monkeypatch):
    same, same_valid = _legacy(synthetic, 'same', text='actual', checkpoint='actual')
    for stage in ('assets', 'preflight'):
        assert evaluate.main(_argv(synthetic, stage, 'legacy-replay', 'exec-legacy', same, same_valid)) == 0
    with pytest.raises(ValueError, match='仍是历史 E0 权重'):
        evaluate.main(_argv(synthetic, 'preflight', 'legacytext-rerun', 'exec-rerun', same, same_valid))
    fake, fake_valid = _legacy(synthetic, 'commit')
    argv = _argv(synthetic, 'preflight', 'bcmbert200', 'exec-commit', fake, fake_valid)
    # 替身证据不再打开 commit 覆盖：CLI 给别的 commit 直接拒绝。
    mismatched = list(argv)
    mismatched[mismatched.index('--expected-commit') + 1] = '0' * 40
    with pytest.raises(ValueError, match='与当前源码身份'):
        evaluate.main(mismatched)
    # 当前源码身份换成别的 commit 后，run record 的 commit 不再是冻结 commit。
    monkeypatch.setattr(evaluate, 'source_identity', lambda closure, *, allow_dirty: {**IDENTITY, 'commit': '0' * 40})
    index = argv.index('--expected-commit')
    with pytest.raises(ValueError, match='不是冻结的'):
        evaluate.main(argv[:index] + argv[index + 2:])


def test_feature_manifest_must_match_cache(synthetic, tmp_path):
    preflight, valid = _legacy(synthetic, 'tamper')
    manifest_path = synthetic['run_root'] / 'data/text_embeddings_bcmbert200/manifest.json'
    original = manifest_path.read_text()
    manifest = json.loads(original)
    manifest['patients']['T0']['sha256'] = '0' * 64
    manifest_path.write_text(json.dumps(manifest))
    try:
        with pytest.raises(ValueError, match='manifest 哈希不符'):
            evaluate.main(_argv(synthetic, 'assets', 'bcmbert200', 'exec-tamper', preflight, valid))
    finally:
        manifest_path.write_text(original)


def test_outputs_cannot_touch_protected_dirs(synthetic):
    preflight, valid = _legacy(synthetic, 'protect')
    argv = _argv(synthetic, 'assets', 'bcmbert200', 'exec-protect', preflight, valid)
    argv[argv.index('--execution-root') + 1] = str(synthetic['run_root'] / 'tmp_sur_cache' / 'out')
    with pytest.raises(ValueError, match='受保护目录'):
        evaluate.main(argv)


@pytest.mark.parametrize('overrides', [{'lr': 5e-4}, {'batch_size': 64}, {'cancer_types': 'BRCA'},
                                       {'allow_dirty': True}, {'epochs': 30}])
def test_training_record_must_match_approved_recipe(synthetic, overrides):
    path = synthetic['record'] / 'resolved_config.yaml'
    preflight, valid = _legacy(synthetic, 'recipe')
    original = path.read_text()
    resolved = json.loads(original)
    resolved['runtime'].update(overrides)
    path.write_text(json.dumps(resolved))
    try:
        with pytest.raises(ValueError, match='训练参数与获审配方不符'):
            evaluate.main(_argv(synthetic, 'preflight', 'bcmbert200', 'exec-recipe-' + next(iter(overrides)),
                                preflight, valid))
    finally:
        path.write_text(original)


@pytest.mark.parametrize('field, value, match', [
    ('text_path', 'data/text_embeddings_parsed', 'Text 目录'),
    ('text_path', 'data/text_embeddings_bcmbert200', 'Text 目录'),  # 未解析的逻辑串不是训练端真实格式
    ('model_config', 'configs/models/surv_multimodal_mainmoe_uni2.yml', 'model_config 不是获审文件'),
    ('label', 'other', '训练标签与历史标签不同'),
])
def test_training_record_binds_inputs_and_text_path(synthetic, config, field, value, match):
    record = synthetic['record']
    legacy = {'preflight': json.loads(_legacy(synthetic, 'inputs')[0].read_text())}
    resolved = json.loads((record / 'resolved_config.yaml').read_text())
    manifest = json.loads((record / 'data_manifest.json').read_text())
    if field == 'text_path':
        manifest['modalities']['text']['path'] = (value if not value.endswith('parsed')
                                                  else str((synthetic['run_root'] / value).resolve()))
    elif field == 'model_config':
        from trimodalsurv.config import file_fingerprint
        resolved['inputs'][1] = file_fingerprint(evaluate.REPO_ROOT / value)
        resolved['inputs'][1]['path'] = resolved['inputs'][1]['path'].replace('surv_multimodal_mainmoe_uni2.yml',
                                                                              'model_config.yml')
    else:
        resolved['inputs'][0]['sha256'] = '0' * 64
    fake = synthetic['root'] / f'record-{field}-{value.replace("/", "_")}'
    fake.mkdir()
    (fake / 'resolved_config.yaml').write_text(json.dumps(resolved))
    (fake / 'data_manifest.json').write_text(json.dumps(manifest))
    kwargs = dict(profile='bcmbert200', cancer=CANCER, seed=123, run_root=synthetic['run_root'])
    good = evaluate.check_training_record(record, config, legacy, **kwargs)
    assert good['text_path'] == 'data/text_embeddings_bcmbert200' and good['text_path_matches_run_root']
    assert str(synthetic['root']) not in json.dumps(good)  # 不回传绝对路径
    with pytest.raises(ValueError, match=match):
        evaluate.check_training_record(fake, config, legacy, **kwargs)


def test_frozen_worktree_requires_external_mutable_assets(config, tmp_path):
    run_root, external = tmp_path / 'run', tmp_path / 'mutable'
    (run_root / 'data').mkdir(parents=True)
    (run_root / 'tmp_sur_cache').mkdir()
    assert evaluate.check_run_root_layout(run_root, config, profile='bcmbert200') == {'frozen_worktree': False}
    (run_root / 'GIT_STAMP.json').write_text('{}')
    with pytest.raises(ValueError, match='冻结工作树内'):
        evaluate.check_run_root_layout(run_root, config, profile='bcmbert200')
    (run_root / 'tmp_sur_cache').rmdir()
    (external / 'cache').mkdir(parents=True)
    (run_root / 'tmp_sur_cache').symlink_to(external / 'cache', target_is_directory=True)
    assert evaluate.check_run_root_layout(run_root, config, profile='bcmbert200') == {
        'frozen_worktree': True, 'cache_dir_external': True, 'feature_dir_external': None}
    (run_root / 'data/text_embeddings_bcmbert200').mkdir()
    with pytest.raises(ValueError, match='冻结工作树内'):
        evaluate.check_run_root_layout(run_root, config, profile='bcmbert200')
    (run_root / 'data/text_embeddings_bcmbert200').rmdir()
    (external / 'features').mkdir()
    (run_root / 'data/text_embeddings_bcmbert200').symlink_to(external / 'features', target_is_directory=True)
    report = evaluate.check_run_root_layout(run_root, config, profile='bcmbert200')
    assert report['feature_dir_external'] is True
    assert str(tmp_path) not in json.dumps(report)  # 不记录绝对路径（仓库公开）


def test_expected_commit_is_bound_to_current_source_identity(tmp_path):
    current = 'a' * 40
    clean = {'source': 'git', 'commit': current, 'dirty': False, 'allow_dirty': False}
    assert evaluate.resolve_expected_commit(None, clean, repo_root=tmp_path) == (current, 'git')
    assert evaluate.resolve_expected_commit(current, clean, repo_root=tmp_path)[0] == current
    with pytest.raises(ValueError, match='与当前源码身份'):
        evaluate.resolve_expected_commit('b' * 40, clean, repo_root=tmp_path)
    for broken in ({**clean, 'commit': None}, {**clean, 'dirty': True}, {**clean, 'allow_dirty': True}):
        with pytest.raises(ValueError, match='干净的冻结源码身份'):
            evaluate.resolve_expected_commit(None, broken, repo_root=tmp_path)
    (tmp_path / 'GIT_STAMP.json').write_text(json.dumps({'commit': 'b' * 40}))
    with pytest.raises(ValueError, match='GIT_STAMP.json'):
        evaluate.resolve_expected_commit(None, clean, repo_root=tmp_path)
    (tmp_path / 'GIT_STAMP.json').write_text(json.dumps({'commit': current}))
    assert evaluate.resolve_expected_commit(current, clean, repo_root=tmp_path)[0] == current
    with pytest.raises(TypeError):  # 已删除合成例外分支
        evaluate.resolve_expected_commit('c' * 40, clean, synthetic=True)


def test_legacy_override_opens_no_bypass(synthetic, monkeypatch):
    """替身证据参数不能打开任何旁路（Codex 候选复核 r3 finding 2）：dirty 身份照样拒，CPU 未经测试注入照样拒。"""
    preflight, valid = _legacy(synthetic, 'bypass')
    monkeypatch.setattr(evaluate, 'source_identity', lambda closure, *, allow_dirty: {**IDENTITY, 'allow_dirty': True})
    with pytest.raises(ValueError, match='干净的冻结源码身份'):
        evaluate.main(_argv(synthetic, 'preflight', 'bcmbert200', 'exec-bypass', preflight, valid, '--allow-dirty'))
    monkeypatch.setattr(evaluate, 'source_identity', lambda closure, *, allow_dirty: dict(IDENTITY))
    monkeypatch.setattr(evaluate, 'ALLOW_CPU_FOR_SYNTHETIC_TESTS', False)
    with pytest.raises(ValueError, match='GPU|CPU'):
        evaluate.main(_argv(synthetic, 'smoke', 'bcmbert200', 'exec-bypass-cpu', preflight, valid))


def _preflight_with_lock(synthetic, name, lock):
    preflight, valid = _legacy(synthetic, name)
    argv = _argv(synthetic, 'preflight', 'bcmbert200', f'exec-{name}', preflight, valid)
    index = argv.index('--assets-lock')
    if lock is None:
        return argv[:index] + argv[index + 2:]
    argv[index + 1] = str(lock)
    return argv


def test_assets_lock_is_required_and_bound(synthetic, tmp_path):
    """新 ckpt 的数据身份：必须有训练前资产锁，锁早于训练、绑定本轮 commit，且当前内容等于锁。"""
    with pytest.raises(ValueError, match='--assets-lock'):
        evaluate.main(_preflight_with_lock(synthetic, 'nolock', None))
    original = json.loads(synthetic['lock'].read_text())
    cases = {
        'late': ({**original, 'locked_at_utc': '2999-01-01T00:00:00+00:00'}, '晚于训练启动'),
        'othercommit': ({**original, 'commit': '0' * 40}, 'commit 与本轮不同'),
        'forged': ({**original, 'view': {**original['view'], 'label_sha256': '0' * 64}}, '与其摘要不符'),
    }
    for name, (lock, match) in cases.items():
        path = tmp_path / f'{name}.json'
        path.write_text(json.dumps(lock))
        with pytest.raises(ValueError, match=match):
            evaluate.main(_preflight_with_lock(synthetic, f'lock-{name}', path))


def test_assets_replaced_after_training_are_refused(synthetic):
    """同一路径、训练后替换内容：check_assets 自洽地通过，但与训练前资产锁不同，必须拒绝。"""
    manifest_path = synthetic['run_root'] / 'data/text_embeddings_bcmbert200/manifest.json'
    original = manifest_path.read_text()
    manifest_path.write_text(json.dumps({**json.loads(original), 'regenerated': True}))
    try:
        with pytest.raises(ValueError, match='训练前资产锁不同'):
            evaluate.main(_preflight_with_lock(synthetic, 'replaced', synthetic['lock']))
    finally:
        manifest_path.write_text(original)


# ----------------------------------------------------------------------------- A0（bcmbert8192）


PINNED_MODEL_FILES = json.loads((EXPERIMENT_DIR / 'config.yaml').read_text())['text_encoders']['bcmbert8192'][
    'model_files_sha256']


def _write_8192_features(directory, source_cache_dir, run_root, *, manifest_overrides=None, swap=None):
    """在 directory 写 8192 档的广播特征与 schema 2 manifest；返回 {split: {pid: array}}。

    swap=(旧, 新)：同一 split 内用「新」患者顶替「旧」患者（人数不变的身份漂移，用于负例）。"""
    rng = np.random.default_rng(8192)
    patients, per_split = {}, {}
    for split in SPLITS:
        with (source_cache_dir / _cache_name('text', split)).open('rb') as handle:
            pids = sorted(pickle.load(handle))
        if swap and swap[0] in pids:
            pids = sorted(set(pids) - {swap[0]} | {swap[1]})
        per_split[split] = {}
        for pid in pids:
            array = np.tile(rng.normal(size=(1, 768)).astype(np.float32) + 0.2, (200, 1))
            _dump(directory / f'{pid}.pkl', array)
            per_split[split][pid] = array
            patients[pid] = {'cancer': CANCER, 'split': split, 'sha256': sha256_file(directory / f'{pid}.pkl')}
    refs = sorted(path.stem for path in (run_root / 'data/text_embeddings_parsed').glob('*.pkl'))
    manifest = {'schema_version': 2, 'status': 'complete', 'partial': False, 'profile': 'bcmbert8192',
                'slot_rows': 200, 'batching': {'batch_size': 1, 'padding': 'longest', 'truncation': False},
                'encoder': encoder_model.LOCKED_SPECS['bcmbert8192'].as_dict(), 'patients': patients,
                'labels': {'sha256': sha256_file(run_root / 'data/TCGA_9523_ex12.csv'), 'text_column': 'text'},
                'reference_dir': {'n_files': len(refs), 'listing_sha256': hashlib.sha256('\n'.join(refs).encode()).hexdigest()},
                'extractor': {'files': evaluate.extractor_source_hashes(),
                              'git': {'source': 'stamp', 'commit': COMMIT, 'dirty': False}},
                'model_files': dict(PINNED_MODEL_FILES)}
    manifest.update(manifest_overrides or {})
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    return per_split


def _build_8192_root(base, name, *, text_cache_from_200=False, manifest_overrides=None, swap=None, forge_refs=False):
    """兄弟运行根：data/ 复制两个 CSV、旧 Text 特征目录（只需文件名），text_embeddings_bcmbert8192 软链到外部目录，
    全新 tmp_sur_cache。forge_refs：连旧 Text 特征目录也按 swap 改名（只有与历史 text 缓存逐人比对才能发现）。"""
    import shutil
    root = base['root']
    run_root = root / name
    external = root / f'mutable-{name}' / 'text_embeddings_bcmbert8192'
    (run_root / 'data').mkdir(parents=True)
    external.mkdir(parents=True)
    for csv_name in ('TCGA_9523_ex12.csv', 'missing_manifest_v1.csv'):
        shutil.copyfile(base['run_root'] / 'data' / csv_name, run_root / 'data' / csv_name)
    references = run_root / 'data' / 'text_embeddings_parsed'
    references.mkdir()
    old_cache = base['run_root'] / 'tmp_sur_cache'
    for split in SPLITS:
        with (old_cache / _cache_name('text', split)).open('rb') as handle:
            for pid in pickle.load(handle):
                if not (forge_refs and pid == swap[0]):
                    (references / f'{pid}.pkl').write_bytes(b'')
    if forge_refs:
        (references / f'{swap[1]}.pkl').write_bytes(b'')
    (run_root / 'data' / 'text_embeddings_bcmbert8192').symlink_to(external, target_is_directory=True)
    cache = run_root / 'tmp_sur_cache'
    cache.mkdir()
    features = _write_8192_features(external, old_cache, run_root, manifest_overrides=manifest_overrides, swap=swap)
    for split in SPLITS:
        for modality in ('img', 'rna'):
            shutil.copyfile(old_cache / _cache_name(modality, split), cache / _cache_name(modality, split))
        if text_cache_from_200:  # 模拟沿用 bcmbert200 的 text 缓存（坑 D2）
            shutil.copyfile(old_cache / _cache_name('text', split), cache / _cache_name('text', split))
        else:
            _dump(cache / _cache_name('text', split), features[split])
    return run_root


@pytest.fixture(scope='module')
def synthetic_8192(synthetic, config):
    """A0 档案的端到端夹具：资产锁先于训练记录；ckpt 独立结果根。"""
    import shutil
    root = synthetic['root']
    run_root = _build_8192_root(synthetic, 'run8192')
    early = {'root': root, 'run_root': run_root}
    assert evaluate.main(_argv(early, 'assets', 'bcmbert8192', 'exec8192', *_legacy(early, 'lock8192'))) == 0
    lock = root / 'exec8192' / 'runs' / 'assets' / evaluate.ASSETS_LOCK
    assert json.loads(lock.read_text())['profile'] == 'bcmbert8192'
    up = evaluate.Upstream(config)
    checkpoint_root = root / 'weights8192'
    checkpoint = up.i01.checkpoint_path(checkpoint_root, CANCER, 123)
    checkpoint.parent.mkdir(parents=True)
    shutil.copyfile(synthetic['checkpoint'], checkpoint)
    ucfg = evaluate.build_upstream_config(config, run_root=run_root, checkpoint_root=checkpoint_root,
                                          execution_root=root / 'unused8192', device='cpu', gpu_id=None,
                                          retrieval_backend='reference', batch_size=2, cpu_threads=1)
    network = up.rt.build_model(ucfg, CANCER, 'cpu')
    record = _start_training_record(checkpoint_root / 'results', 'run8192', config, run_root, network, checkpoint,
                                    profile='bcmbert8192')
    (record / 'audit' / 'completion.json').write_text(json.dumps(
        {'status': 'complete', 'checkpoint': {'sha256': sha256_file(checkpoint)}}))
    return {'root': root, 'run_root': run_root, 'checkpoint_root': checkpoint_root, 'checkpoint': checkpoint,
            'lock': lock, 'state_sha': synthetic['state_sha'], 'record': record}


def test_bcmbert8192_assets_lock_preflight(synthetic_8192):
    preflight, valid = _legacy(synthetic_8192, 'new8192')
    assert evaluate.main(_argv(synthetic_8192, 'preflight', 'bcmbert8192', 'exec8192', preflight, valid)) == 0
    ready = json.loads((synthetic_8192['root'] / 'exec8192' / 'runs' / 'preflight' / 'preflight.json').read_text())
    assert ready['status'] == 'READY_SYNTHETIC' and ready['profile'] == 'bcmbert8192'
    assert ready['checkpoints'][CANCER]['123']['training']['text_path'] == 'data/text_embeddings_bcmbert8192'
    assets = ready['assets']
    assert assets['profile'] == 'bcmbert8192'
    files = assets['cancers'][CANCER]['files']
    assert {files[_cache_name('text', s)]['status'] for s in SPLITS} == {'new'}


def test_bcmbert8192_rejects_bcmbert200_text_cache(synthetic):
    run_root = _build_8192_root(synthetic, 'run8192-stale', text_cache_from_200=True)
    early = {'root': synthetic['root'], 'run_root': run_root}
    with pytest.raises(ValueError, match='text 缓存条目与特征文件不一致'):
        evaluate.main(_argv(early, 'assets', 'bcmbert8192', 'exec8192-stale', *_legacy(early, 'stale8192')))


@pytest.mark.parametrize('overrides', [{'profile': 'bcmbert200'}, {'schema_version': 1},
                                       {'batching': {'batch_size': 16, 'padding': 'longest', 'truncation': False}},
                                       {'slot_rows': 8192}])
def test_feature_manifest_profile_and_schema_gates(synthetic, overrides):
    name = 'run8192-gate-' + next(iter(overrides))
    run_root = _build_8192_root(synthetic, name, manifest_overrides=overrides)
    early = {'root': synthetic['root'], 'run_root': run_root}
    with pytest.raises(ValueError, match='manifest'):
        evaluate.main(_argv(early, 'assets', 'bcmbert8192', f'exec-{name}', *_legacy(early, name)))


def _assets_8192(synthetic, name, *extra, **build):
    run_root = _build_8192_root(synthetic, name, **build)
    early = {'root': synthetic['root'], 'run_root': run_root}
    return evaluate.main(_argv(early, 'assets', 'bcmbert8192', f'exec-{name}', *_legacy(early, name), *extra))


EXTRACTOR_FILES = {'experiments/I05_text_encoder_bcmbert/model.py': '0' * 64}


@pytest.mark.parametrize('name,overrides,match', [
    ('old-extractor', {'extractor': {'files': EXTRACTOR_FILES, 'git': {'commit': COMMIT, 'dirty': False}}}, '提取器源码'),
    ('dirty-extractor', 'dirty', '干净源码身份'),
    ('model-files', {'model_files': {**PINNED_MODEL_FILES, 'model.safetensors': '1' * 64}}, '模型文件哈希'),
    ('no-model-files', {'model_files': {}}, '模型文件哈希'),
    ('labels', {'labels': {'sha256': '2' * 64}}, '标签哈希'),
    ('listing', {'reference_dir': {'listing_sha256': '3' * 64}}, '清单'),
])
def test_feature_manifest_generation_identity_gates(synthetic, name, overrides, match):
    """Codex 首审 finding 2/3：旧版或 dirty 提取器、换过的模型文件、别的标签或旧特征清单生成的 manifest 都拒绝。"""
    if overrides == 'dirty':
        overrides = {'extractor': {'files': evaluate.extractor_source_hashes(),
                                   'git': {'commit': COMMIT, 'dirty': True}}}
    with pytest.raises(ValueError, match=match):
        _assets_8192(synthetic, f'run8192-id-{name}', manifest_overrides=overrides)


def test_feature_manifest_split_must_match_frozen_labels(synthetic):
    """manifest 自报的 split 与冻结标签不同即拒（缓存按同样的错误 split 自洽也没用）。"""
    run_root = _build_8192_root(synthetic, 'run8192-split')
    path = run_root / 'data/text_embeddings_bcmbert8192/manifest.json'
    manifest = json.loads(path.read_text())
    manifest['patients']['V0']['split'] = 'train'
    path.write_text(json.dumps(manifest))
    early = {'root': synthetic['root'], 'run_root': run_root}
    with pytest.raises(ValueError, match='冻结标签不符'):
        evaluate.main(_argv(early, 'assets', 'bcmbert8192', 'exec-split', *_legacy(early, 'split')))


def test_equal_count_patient_identity_drift_is_refused(synthetic):
    """等人数顶替：train 里用无旧 Text 的 T5 顶替 T0，manifest 与缓存自洽、各计数不变 → 仍须拒绝。"""
    with pytest.raises(ValueError, match='患者集合'):
        _assets_8192(synthetic, 'run8192-drift', swap=('T0', 'T5'))


def test_synced_reference_manifest_cache_tampering_is_refused_without_arguments(synthetic):
    """复审 round2：旧 Text 特征目录、manifest、新特征、缓存一起按等人数换名（T0→T5），标签与计数都自洽；
    不传任何额外参数，也必须由固定的历史 text 患者集合摘要拒绝。"""
    with pytest.raises(ValueError, match='历史 text 缓存逐人不同'):
        _assets_8192(synthetic, 'run8192-forged', swap=('T0', 'T5'), forge_refs=True)


def test_formal_runs_take_text_key_digests_from_config(config, tmp_path):
    """正式运行（不覆盖历史证据）只用 config 固定的 15 个摘要；配置缺项即拒绝加载。"""
    legacy = evaluate.load_legacy(config)
    assert legacy['text_keys_sha256'] == config['legacy']['text_keys_sha256'] and len(legacy['text_keys_sha256']) == 15
    broken = json.loads((EXPERIMENT_DIR / 'config.yaml').read_text())
    broken['legacy']['text_keys_sha256'].pop('text_sur_valid_all_LGG.pkl')
    path = tmp_path / 'config.yaml'
    path.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match='text_keys_sha256'):
        evaluate.load_config(path)


def test_bcmbert8192_training_record_must_point_to_8192_features(synthetic_8192, config):
    legacy = {'preflight': json.loads(_legacy(synthetic_8192, 'inputs8192')[0].read_text())}
    kwargs = dict(profile='bcmbert8192', cancer=CANCER, seed=123, run_root=synthetic_8192['run_root'])
    good = evaluate.check_training_record(synthetic_8192['record'], config, legacy, **kwargs)
    assert good['text_path'] == 'data/text_embeddings_bcmbert8192'
    # 同一份 8192 记录拿去当 bcmbert200 档案核对：Text 目录与 model_config 都对不上
    with pytest.raises(ValueError):
        evaluate.check_training_record(synthetic_8192['record'], config, legacy,
                                       **{**kwargs, 'profile': 'bcmbert200'})


def test_frozen_worktree_layout_checks_the_profiles_feature_dir(config, tmp_path):
    run_root, external = tmp_path / 'run', tmp_path / 'mutable'
    (run_root / 'data').mkdir(parents=True)
    (external / 'cache').mkdir(parents=True)
    (run_root / 'tmp_sur_cache').symlink_to(external / 'cache', target_is_directory=True)
    (run_root / 'GIT_STAMP.json').write_text('{}')
    (run_root / 'data/text_embeddings_bcmbert8192').mkdir()  # 8192 特征目录落在工作树内
    with pytest.raises(ValueError, match='冻结工作树内'):
        evaluate.check_run_root_layout(run_root, config, profile='bcmbert8192')
    # 200 档案不看 8192 的目录
    assert evaluate.check_run_root_layout(run_root, config, profile='bcmbert200')['feature_dir_external'] is None
    assert evaluate.check_run_root_layout(run_root, config, profile='legacytext-rerun') == {
        'frozen_worktree': True, 'feature_dir_external': None, 'cache_dir_external': True}

