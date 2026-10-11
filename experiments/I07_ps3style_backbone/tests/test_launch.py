"""I07 发车器与 provenance 门：授权摘要绑定 ckpt / 资产 / commit、身份门 fail-closed、资产逐文件校验、幂等跳过、每卡并发上限。"""
import json
import sys

import pytest

from experiments.I07_ps3style_backbone import launch, provenance, train


def make_runs(root, items, content=b'w'):
    for c, k, a in items:
        d = launch.run_dir(root, c, k, a)
        d.mkdir(parents=True, exist_ok=True)
        (d / 'best.pt').write_bytes(content + f'{c}{k}{a}'.encode())
        (d / 'run.json').write_text(json.dumps({'key': f'{c}{k}{a}'}))


def make_assets(root):
    for sub, name in provenance.ASSET_MANIFESTS:
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / 'data.bin').write_bytes(sub.encode())
        sha = provenance._sha(d / 'data.bin')
        (d / f'{name}.manifest.json').write_text(json.dumps({'params': {}, 'files': {'data.bin': sha}}))


@pytest.fixture
def clean_identity(monkeypatch):
    monkeypatch.setattr(provenance, 'identity', lambda: {'commit': 'c' * 40, 'dirty': False, 'source': 'test'})
    return 'c' * 40


def test_auth_digest_binds_ckpt_run_json_assets_and_commit(tmp_path):
    runs, assets = tmp_path / 'runs', tmp_path / 'assets'
    items = launch.plan(['BLCA'], [0, 1], ['tri'])
    make_runs(runs, items)
    make_assets(assets)
    d0 = launch.digest(runs, items, assets, 'a' * 40)
    assert launch.digest(runs, items, assets, 'b' * 40) != d0
    m = assets / 'splits' / 'splits.manifest.json'
    m.write_text(m.read_text() + ' ')
    d1 = launch.digest(runs, items, assets, 'a' * 40)
    assert d1 != d0
    (launch.run_dir(runs, 'BLCA', 1, 'tri') / 'best.pt').write_bytes(b'retrained')
    d2 = launch.digest(runs, items, assets, 'a' * 40)
    assert d2 != d1
    (launch.run_dir(runs, 'BLCA', 0, 'tri') / 'run.json').write_text('{"best_epoch": 1}')
    assert launch.digest(runs, items, assets, 'a' * 40) != d2


def test_evaluate_rejects_wrong_auth_digest(tmp_path, clean_identity):
    runs, assets = tmp_path / 'runs', tmp_path / 'assets'
    items = launch.plan(['BLCA'], [0], ['tri'])
    make_runs(runs, items)
    make_assets(assets)
    good = launch.digest(runs, items, assets, clean_identity)
    args = ['evaluate', '--assets', str(assets), '--runs', str(runs), '--cancers', 'BLCA', '--folds', '0', '--arms', 'tri',
            '--expected-commit', clean_identity, '--dry-run']
    with pytest.raises(SystemExit, match='授权摘要不符'):
        launch.main(args + ['--auth-digest', 'x' * 64])
    launch.main(args + ['--auth-digest', good])


def test_verify_assets_catches_modified_file(tmp_path):
    make_assets(tmp_path)
    provenance.verify_assets(tmp_path)
    (tmp_path / 'wsi_tokens' / 'data.bin').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='wsi_tokens'):
        provenance.verify_assets(tmp_path)


@pytest.mark.parametrize('ident', [{'commit': 'c' * 40, 'dirty': True}, {'commit': None, 'dirty': False},
                                   {'commit': 'c' * 40, 'dirty': False, 'allow_dirty': True}])
def test_require_clean_refuses_dirty_unknown_and_allowed_dirty(monkeypatch, ident):
    monkeypatch.setattr(provenance, 'identity', lambda: ident)
    with pytest.raises(PermissionError):
        provenance.require_clean('c' * 40)


def test_require_clean_refuses_mismatched_expected_commit(clean_identity):
    with pytest.raises(PermissionError):
        provenance.require_clean('d' * 40)
    assert provenance.require_clean(clean_identity)['commit'] == clean_identity


def test_train_entry_refuses_before_any_side_effect(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, 'identity', lambda: {'commit': 'c' * 40, 'dirty': True})
    out = tmp_path / 'runs'
    with pytest.raises(PermissionError):
        train.main(['--assets', str(tmp_path / 'none'), '--cancer', 'BLCA', '--fold', '0', '--arm', 'tri',
                    '--out', str(out), '--expected-commit', 'c' * 40, '--device', 'cpu'])
    assert not out.exists()


def test_train_requires_low_util_reason_and_skips_done(tmp_path, capsys, clean_identity):
    assets = tmp_path / 'assets'
    make_assets(assets)
    base = ['train', '--assets', str(assets), '--runs', str(tmp_path / 'runs'), '--cancers', 'BLCA', '--folds', '0',
            '--expected-commit', clean_identity]
    with pytest.raises(SystemExit, match='allow-low-gpu-util'):
        launch.main(base)
    done = launch.run_dir(tmp_path / 'runs', 'BLCA', 0, 'tri')
    done.mkdir(parents=True)
    (done / 'run.json').write_text('{}')
    launch.main(base + ['--allow-low-gpu-util', 'test', '--dry-run'])
    out = capsys.readouterr().out
    assert '清单 4 个，待运行 3 个' in out and '--arm tri' not in out and f'--expected-commit {clean_identity}' in out


def test_schedule_respects_per_gpu_limit(tmp_path):
    marker = tmp_path / 'm'
    marker.mkdir()
    code = ('import os,time,pathlib;g=os.environ["CUDA_VISIBLE_DEVICES"];d=pathlib.Path(r"%s");'
            'f=d/f"{g}-{os.getpid()}";f.touch();n=len(list(d.glob(g+"-*")));'
            '(d/("max"+g)).write_text(str(max(n,int((d/("max"+g)).read_text()) if (d/("max"+g)).exists() else 0)));'
            'time.sleep(0.3);f.unlink()') % marker
    jobs = [(f'j{i}', tmp_path / f'j{i}.log') for i in range(6)]
    state = {'runs': {}}
    failed = launch.schedule(jobs, ['0', '1'], 1, lambda k: [sys.executable, '-c', code], state,
                             tmp_path / 'state.json', poll=0.05)
    assert failed == [] and all(v['status'] == 'done' for v in state['runs'].values())
    assert int((marker / 'max0').read_text()) == 1 and int((marker / 'max1').read_text()) == 1
