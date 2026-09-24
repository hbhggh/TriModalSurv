"""I05 配置、源码锁、冻结规格与训练清单的契约测试（纯本地，不需要数据）。"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_DIR.parents[1]

from experiments.I05_text_encoder_bcmbert import evaluate, model  # noqa: E402


@pytest.fixture(scope='module')
def config():
    return evaluate.load_config(EXPERIMENT_DIR / 'config.yaml')


@pytest.fixture(scope='module')
def launcher():
    spec = importlib.util.spec_from_file_location('_i05_train_launcher', REPO_ROOT / 'scripts' / 'train_launcher.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_encoder_lock_matches_user_decision(config):
    spec = model.spec_from_config(config)
    assert spec.model_id == 'NeuML/bioclinical-modernbert-base-embeddings'
    assert spec.revision == '048ad4491de0fb4e2695bfe4705da67caf4804b8'
    assert (spec.max_length, spec.hidden_size) == (200, 768)
    assert config['shapes']['text'] == [200, 768]


def test_encoder_lock_rejects_any_drift(config):
    drifted = json.loads(json.dumps(config))
    drifted['text_encoder']['revision'] = 'main'
    with pytest.raises(ValueError):
        model.spec_from_config(drifted)
    drifted = json.loads(json.dumps(config))
    drifted['text_encoder']['pad_rows'] = 'keep'
    with pytest.raises(ValueError):
        model.spec_from_config(drifted)


def test_upstream_pins_equal_current_files(config):
    actual = evaluate.verify_pins(config)
    assert set(actual) == set(config['upstream']['source_sha256'])


def test_pin_mismatch_is_refused(config):
    broken = json.loads(json.dumps(config))
    first = next(iter(broken['upstream']['source_sha256']))
    broken['upstream']['source_sha256'][first] = '0' * 64
    with pytest.raises(ValueError):
        evaluate.verify_pins(broken)


def test_frozen_spec_equals_historical_selection_lock(config):
    spec = evaluate.frozen_spec(config)
    assert spec['candidate_id'] == 'combo-l1-a1-w0p5'
    assert (spec['lambda'], spec['alpha'], spec['w'], spec['ucec_exception']) == (1.0, 1.0, 0.5, True)
    assert spec['enabled_rules'] == [1, 2, 3, 4, 5]


def test_route_table_matches_s0_force_module(config):
    route = evaluate._load_module('_i05_route_test', REPO_ROOT / config['upstream']['route_module'])
    evaluate.check_route_table(route, config)
    s0 = json.loads((REPO_ROOT / 'experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/'
                     '4.progress/luad_m1_force/config.yaml').read_text())
    assert config['s0_force']['luad_route'] == s0['s0_force']['luad_route']
    assert config['frozen_combo_spec']['candidate_id'] == s0['upstream']['combo_candidate_id']


def test_model_config_changes_only_text_path():
    yaml = pytest.importorskip('yaml')
    default = yaml.safe_load((REPO_ROOT / 'configs/models/surv_multimodal_mainmoe_uni2.yml').read_text())
    ours = yaml.safe_load((EXPERIMENT_DIR / 'model_config.yml').read_text())
    assert ours['modality']['text']['path'] == 'data/text_embeddings_bcmbert200'
    ours['modality']['text']['path'] = default['modality']['text']['path']
    assert ours == default


def test_train_plan_is_25_seed_major_runs(config, launcher):
    runs = launcher.load_plan(EXPERIMENT_DIR / 'train_plan.yaml')
    assert len(runs) == 25 and len({run.name for run in runs}) == 25
    assert {(run.cancer, run.seed) for run in runs} == {(c, s) for c in config['cancers'] for s in config['seeds']}
    for run in runs:
        assert (run.arm, run.network_type, run.compensator) == ('e0_bcmbert200', 'NPJC', 'none')
        assert run.extra_args == ('--bin_mode', 'author')
    seeds = [run.seed for run in runs]
    assert seeds == sorted(seeds)
    assert [run.cancer for run in runs[:5]] == config['display_cancer_order']


def test_plan_parses_identically_without_pyyaml(launcher):
    yaml = pytest.importorskip('yaml')
    for name in ('train_plan.yaml', 'train_plan_smoke.yaml'):
        text = (EXPERIMENT_DIR / name).read_text(encoding='utf-8')
        assert launcher._simple_yaml_load(text) == yaml.safe_load(text)


def test_smoke_plan_is_isolated_from_formal_names(launcher):
    smoke = launcher.load_plan(EXPERIMENT_DIR / 'train_plan_smoke.yaml')
    formal = {run.name for run in launcher.load_plan(EXPERIMENT_DIR / 'train_plan.yaml')}
    assert len(smoke) == 1 and smoke[0].name not in formal and smoke[0].arm != 'e0_bcmbert200'


def test_seeds_locked_by_user(config, launcher, tmp_path):
    """用户锁定：实验种子必须是 123、132、213、231、321，正式清单、冒烟与渲染都只能用这一组。"""
    locked = [123, 132, 213, 231, 321]
    assert config['seeds'] == locked and list(evaluate.REQUIRED_SEEDS) == locked
    assert config['smoke']['seed'] in locked
    assert sorted({run.seed for run in launcher.load_plan(EXPERIMENT_DIR / 'train_plan.yaml')}) == sorted(locked)
    assert [run.seed for run in launcher.load_plan(EXPERIMENT_DIR / 'train_plan_smoke.yaml')] == [123]
    from experiments.I05_text_encoder_bcmbert.tools import check_launch_contract, render_encoder_tables
    assert list(check_launch_contract.SEEDS) == locked and list(render_encoder_tables.REQUIRED_SEEDS) == locked
    for seeds in ([123, 132, 213, 231], [123, 132, 213, 231, 322], [321, 231, 213, 132, 123]):
        altered = json.loads(json.dumps(config))
        altered['seeds'] = seeds
        path = tmp_path / 'altered.yaml'
        path.write_text(json.dumps(altered))
        with pytest.raises(ValueError, match='种子'):
            evaluate.load_config(path)
        with pytest.raises(ValueError, match='种子'):
            render_encoder_tables.load_config(path)


def test_profiles_and_protocol_ids(config):
    assert set(config['profiles']) == set(evaluate.PROFILES)
    assert len(set(config['protocol_ids'].values())) == 3
    assert config['profiles']['bcmbert200'] == {'text_cache': 'new', 'checkpoints': 'new'}
    assert config['profiles']['legacy-replay'] == {'text_cache': 'legacy', 'checkpoints': 'legacy'}


def test_legacy_evidence_pins(config):
    legacy = evaluate.load_legacy(config)
    assert not legacy['overridden']
    complete = evaluate.load_legacy_test_complete(config)
    assert len(complete['rows']) == 300


def test_identity_closure_works_with_stamp_only_checkout(config, tmp_path):
    """服务器只有 GIT_STAMP.json、没有 .git：身份门只能核对 stamp 覆盖的文件（Post-Mortem 9）。"""
    import hashlib
    import shutil
    from trimodalsurv import gitstamp
    from trimodalsurv.config import file_fingerprint
    closure = evaluate.identity_closure(config, repo_root=tmp_path)
    assert closure and all(path.name.endswith(gitstamp.STAMP_SUFFIXES) for path in closure)
    pinned = set(config['upstream']['source_sha256'])
    excluded = sorted(p for p in pinned if not p.endswith(gitstamp.STAMP_SUFFIXES))
    assert excluded == ['experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/2.progress/result/'
                        'runs/valid/selection-lock.json']  # 仍由 verify_pins 锁定
    relatives = [f'experiments/I05_text_encoder_bcmbert/{name}' for name in evaluate.I05_SOURCES] + sorted(pinned)
    for relative in relatives:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(evaluate.REPO_ROOT / relative, target)
    files = {rel: hashlib.sha256((tmp_path / rel).read_bytes()).hexdigest()
             for rel in relatives if rel.endswith(gitstamp.STAMP_SUFFIXES)}  # 与 build_stamp 的后缀规则一致
    (tmp_path / gitstamp.STAMP_NAME).write_text(json.dumps({'commit': 'a' * 40, 'branch': 'train/x', 'files': files}))
    good = gitstamp.git_identity([file_fingerprint(path) for path in closure], root=tmp_path)
    assert good['source'] == 'stamp' and good['dirty'] is False
    everything = gitstamp.git_identity([file_fingerprint(tmp_path / rel) for rel in relatives], root=tmp_path)
    assert everything['dirty'] is True and everything['dirty_files'] == excluded  # 复现修复前的误判
