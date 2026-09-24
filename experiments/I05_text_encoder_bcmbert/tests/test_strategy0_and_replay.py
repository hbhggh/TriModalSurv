"""strategy0 组合逻辑用历史产物逐值复现；回放比对与正式门的判定规则。"""
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.I05_text_encoder_bcmbert import evaluate

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_DIR.parents[1]


@pytest.fixture(scope='module')
def config():
    return evaluate.load_config(EXPERIMENT_DIR / 'config.yaml')


@pytest.fixture(scope='module')
def route(config):
    return evaluate._load_module('_i05_route_history', REPO_ROOT / config['upstream']['route_module'])


def _load(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def test_luad_composition_reproduces_historical_s0_force(config, route):
    """用 2.progress 的 combo/m1/m0real 逐患者组合，20 个 LUAD 单元必须逐值等于 4.progress 的 strategy0。"""
    p2 = REPO_ROOT / config['legacy']['artifacts_2progress']
    p4 = REPO_ROOT / config['legacy']['artifacts_4progress']
    manifest = json.loads((p2 / 'LUAD-test-manifest.json').read_text())['patients']
    natural = {}
    for record in manifest:
        natural.setdefault(record['patient_id'], record['natural_valid'])
    legacy = evaluate.load_legacy_test_complete(config)
    combo_id = config['frozen_combo_spec']['candidate_id']
    counts = {}
    for seed in config['seeds']:
        for grid in config['grids']:
            cell = p2 / 'LUAD' / str(seed) / grid
            arrays = {'combo': _load(cell / f'{combo_id}.npz'), 'm1': _load(cell / 'm1.npz'),
                      'm0real': _load(cell / 'm0real.npz')}
            ids = arrays['m1']['patient_ids'].tolist()
            routes = evaluate.luad_routes(route, ids, natural, grid)
            composed = evaluate.compose_strategy0(ids, arrays, routes)
            history = _load(p4 / 'LUAD' / str(seed) / grid / 'strategy0.npz')
            assert history['patient_ids'].tolist() == ids
            np.testing.assert_array_equal(composed['logits'], history['logits'])
            np.testing.assert_array_equal(composed['risk_b'], history['risk_b'])
            counts[f'{seed}/{grid}'] = {name: routes.count(name) for name in set(routes)}
    assert counts == legacy['luad_route_counts']


def test_non_luad_strategy0_is_the_frozen_combo(config):
    """历史 Table 1 的非 LUAD Proto.† 就是 2.progress 冻结组合的 C-index。"""
    legacy = evaluate.load_legacy_test_complete(config)
    upstream = json.loads((REPO_ROOT / config['legacy']['artifacts_2progress'] / 'complete.json').read_text())
    combo_id = config['frozen_combo_spec']['candidate_id']
    combo = {(r['cancer'], r['seed'], r['grid']): r['c_index_b'] for r in upstream['rows']
             if r['candidate_id'] == combo_id}
    checked = 0
    for row in legacy['rows']:
        if row['protocol'] == 'strategy0' and row['cancer'] != 'LUAD':
            assert row['c_index_b'] == combo[(row['cancer'], row['seed'], row['grid'])]
            checked += 1
    assert checked == 80


def test_compose_rejects_misaligned_arms():
    base = {'patient_ids': np.array(['A', 'B']), 'logits': np.zeros((2, 4), np.float32),
            'risk_b': np.zeros(2, np.float32), 'time': np.ones(2, np.float32), 'censorship': np.zeros(2, np.float32)}
    arrays = {name: dict(base) for name in ('combo', 'm1', 'm0real')}
    with pytest.raises(ValueError):
        evaluate.compose_strategy0(['A', 'B'], arrays, ['upstream_combo'])
    with pytest.raises(ValueError):
        evaluate.compose_strategy0(['A', 'B'], arrays, ['upstream_combo', 'retrieval'])
    shuffled = {**arrays, 'm1': {**base, 'patient_ids': np.array(['B', 'A'])}}
    with pytest.raises(ValueError):
        evaluate.compose_strategy0(['A', 'B'], shuffled, ['m1', 'm1'])
    different_time = {**arrays, 'm0real': {**base, 'time': np.array([1, 2], np.float32)}}
    with pytest.raises(ValueError):
        evaluate.compose_strategy0(['A', 'B'], different_time, ['m0real', 'm0real'])


def test_replay_identical_on_history(config):
    rows = evaluate.load_legacy_test_complete(config)['rows']
    report = evaluate.compare_replay(rows, rows, tier='same-host')
    assert report['status'] == 'IDENTICAL' and report['n_rows'] == 300 and report['n_different'] == 0


def test_replay_tiers(config):
    rows = evaluate.load_legacy_test_complete(config)['rows']
    changed = json.loads(json.dumps(rows))
    changed[0]['c_index_b'] += 1e-9
    assert evaluate.compare_replay(changed, rows, tier='same-host')['status'] == 'FAIL'
    passing = evaluate.compare_replay(changed, rows, tier='cross-hardware', parity=lambda: {'ok': True})
    assert passing['status'] == 'PASS_WITH_FLOAT_DIFFS' and passing['n_different'] == 1
    failing = evaluate.compare_replay(changed, rows, tier='cross-hardware', parity=lambda: {'ok': False})
    assert failing['status'] == 'FAIL'
    assert evaluate.compare_replay(rows[:-1], rows, tier='same-host')['status'] == 'FAIL'
    with pytest.raises(ValueError):
        evaluate.compare_replay(rows, rows, tier='anything')


def test_artifact_parity_detects_logit_and_route_changes(tmp_path):
    def cell(root, cancer, seed, grid, name, logits, records):
        directory = root / cancer / str(seed) / grid
        directory.mkdir(parents=True, exist_ok=True)
        np.savez(directory / f'{name}.npz', patient_ids=np.array(['A']), logits=logits)
        (directory / f'{name}.audit.json').write_text(json.dumps({'patients': records}))

    record = [{'donor_id': 'D', 'fusion_valid': {'rna': True}, 'imputed': {'rna': False},
               'pool_weights': [1, 1, 1], 'route': 'retrieval'}]
    base = np.zeros((1, 4), np.float32)
    old, new = tmp_path / 'old', tmp_path / 'new'
    for root in (old, new):
        for name in ('m0real', 'm1', 'combo'):
            cell(root, 'BLCA', 123, 'none', name, base, record)
    kwargs = dict(cancers=['BLCA'], seeds=[123], grids=['none'], combo_id='combo')
    assert evaluate.artifact_parity(new, old, tmp_path / 'p4', **kwargs)['ok']
    cell(new, 'BLCA', 123, 'none', 'm1', base + 5e-7, record)
    report = evaluate.artifact_parity(new, old, tmp_path / 'p4', **kwargs)
    assert report['ok'] and 0 < report['max_logit_abs_diff'] <= 1e-6
    cell(new, 'BLCA', 123, 'none', 'm1', base + 1e-3, record)
    assert not evaluate.artifact_parity(new, old, tmp_path / 'p4', **kwargs)['ok']
    cell(new, 'BLCA', 123, 'none', 'm1', base, [{**record[0], 'donor_id': 'E'}])
    assert not evaluate.artifact_parity(new, old, tmp_path / 'p4', **kwargs)['ok']


def test_test_gates(tmp_path):
    digest, protocol, commit = 'a' * 64, 'proto', 'c' * 40
    replay = tmp_path / 'replay.json'
    review = tmp_path / 'review.json'
    approval = tmp_path / 'approval.json'
    good_review = {'reviewer': 'Codex', 'decision': 'PASS', 'source_hashes_sha256': digest, 'protocol_id': protocol,
                   'commit': commit}
    replay.write_text(json.dumps({'status': 'IDENTICAL', 'source_hashes_sha256': digest}))
    review.write_text(json.dumps(good_review))

    def good_approval():
        return {'authority': 'user', 'decision': 'APPROVE_FORMAL_TEST', 'stage': 'test', 'protocol_id': protocol,
                'source_hashes_sha256': digest, 'commit': commit,
                'review_record_sha256': evaluate.sha256_file(review), 'approved_at': '2026-09-24T10:00:00+08:00'}

    approval.write_text(json.dumps(good_approval()))
    kwargs = dict(replay_record=replay, review_record=review, approval_record=approval, source_digest=digest,
                  protocol_id=protocol, commit=commit)
    assert set(evaluate.check_test_gates(**kwargs)) == {'replay_record_sha256', 'review_record_sha256',
                                                        'user_approval_sha256'}
    for field, value in (('reviewer', 'Claude'), ('decision', 'CONCERNS'), ('source_hashes_sha256', 'b' * 64),
                         ('protocol_id', 'other'), ('commit', 'd' * 40)):
        review.write_text(json.dumps({**good_review, field: value}))
        with pytest.raises(ValueError):
            evaluate.check_test_gates(**kwargs)
    review.write_text(json.dumps(good_review))
    replay.write_text(json.dumps({'status': 'FAIL', 'source_hashes_sha256': digest}))
    with pytest.raises(ValueError):
        evaluate.check_test_gates(**kwargs)
    replay.write_text(json.dumps({'status': 'IDENTICAL', 'source_hashes_sha256': digest}))
    # 结构化授权：任一字段不属于本轮（含旧审查记录的哈希、缺审批时间）都拒绝。
    for field, value in (('authority', 'claude'), ('decision', 'APPROVE'), ('stage', 'smoke'),
                         ('protocol_id', 'other'), ('source_hashes_sha256', 'b' * 64), ('commit', 'd' * 40),
                         ('review_record_sha256', '0' * 64), ('approved_at', '  ')):
        approval.write_text(json.dumps({**good_approval(), field: value}))
        with pytest.raises(ValueError, match='用户授权记录'):
            evaluate.check_test_gates(**kwargs)
    approval.write_text('用户授权 I05 正式评测')  # 旧式非空文本不再有效
    with pytest.raises(ValueError):
        evaluate.check_test_gates(**kwargs)
    approval.write_text(json.dumps(good_approval()))
    assert evaluate.check_test_gates(**kwargs)
    with pytest.raises(ValueError):
        evaluate.check_test_gates(**{**kwargs, 'review_record': None})


def test_argument_rules(config):
    parse = evaluate.build_parser().parse_args
    base = ['--run-root', '/r', '--execution-root', '/e']
    for argv in (['--profile', 'bcmbert200', '--stage', 'replay', '--replay-tier', 'same-host', '--checkpoint-root', '/c'],
                 ['--profile', 'legacy-replay', '--stage', 'test', '--checkpoint-root', '/c'],
                 ['--profile', 'legacy-replay', '--stage', 'replay', '--checkpoint-root', '/c'],
                 ['--profile', 'bcmbert200', '--stage', 'test', '--checkpoint-root', '/c', '--seeds', '123'],
                 ['--profile', 'bcmbert200', '--stage', 'test', '--checkpoint-root', '/c', '--allow-dirty'],
                 ['--profile', 'bcmbert200', '--stage', 'preflight']):
        with pytest.raises(ValueError):
            evaluate._validate_args(parse(argv + base), config)
    cancers, seeds = evaluate._validate_args(parse(['--profile', 'bcmbert200', '--stage', 'smoke', '--checkpoint-root',
                                                    '/c', '--cancers', 'LUAD', '--seeds', '123', '--gpu-id', '0']
                                                   + base), config)
    assert (cancers, seeds) == (['LUAD'], [123])


def test_experiment_stages_require_gpu(config, monkeypatch):
    """用户锁定：smoke/replay/test 必须在 GPU 上跑并指定卡号；CPU 只留给替身证据的本地合成测试。"""
    parse = evaluate.build_parser().parse_args
    base = ['--run-root', '/r', '--execution-root', '/e', '--checkpoint-root', '/c']
    for argv in (['--profile', 'bcmbert200', '--stage', 'smoke', '--device', 'cpu', '--gpu-id', '0'],
                 ['--profile', 'bcmbert200', '--stage', 'smoke'],
                 ['--profile', 'legacy-replay', '--stage', 'replay', '--replay-tier', 'same-host', '--device', 'cpu'],
                 ['--profile', 'bcmbert200', '--stage', 'test']):
        with pytest.raises(ValueError, match='GPU|CPU'):
            evaluate._validate_args(parse(argv + base), config)
    synthetic = ['--profile', 'bcmbert200', '--stage', 'smoke', '--device', 'cpu', '--legacy-preflight', '/p']
    with pytest.raises(ValueError, match='GPU|CPU'):  # 替身证据参数本身不放行 CPU
        evaluate._validate_args(parse(synthetic + base), config)
    monkeypatch.setattr(evaluate, 'ALLOW_CPU_FOR_SYNTHETIC_TESTS', True)  # 只有测试注入才放行
    evaluate._validate_args(parse(synthetic + base), config)
    for stage in ('assets', 'preflight'):
        evaluate._validate_args(parse(['--profile', 'bcmbert200', '--stage', stage] + base), config)
