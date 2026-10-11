"""评估入口自行核对测试授权（节点一复审 high）：直接调用无摘要被拒、篡改资产内容被拒、授权后替换 ckpt 被拒、正常路径放行。"""
import hashlib
import json
import shutil

import numpy as np
import pytest
import torch

from experiments.I07_ps3style_backbone import data, evaluate, launch, provenance, train
from experiments.I07_ps3style_backbone.prep.io_utils import write_manifest
from experiments.I07_ps3style_backbone.tests.test_train import CFG, write_assets

COMMIT = 'c' * 40
EVAL_CFG = dict(CFG, epochs=50)  # 评估入口按 contract 校验 run.json 的 config，epochs 只能 50/100
CFG_SHA = 'e' * 64  # 测试里代替 config.yaml 的哈希；env 把 train.DEFAULTS / CONFIG_SHA256 换成这一套


@pytest.fixture(scope='module')
def base(tmp_path_factory):
    root = tmp_path_factory.mktemp('base')
    assets, runs = root / 'assets', root / 'runs'
    write_assets(assets)
    for sub, name in provenance.ASSET_MANIFESTS:
        write_manifest(assets / sub, name, {})
    parts, meta = data.load_fold(assets, 'BLCA', 0, parts=('train', 'val'))
    torch.manual_seed(0)
    model = train.build_model(meta, 'tri', EVAL_CFG)
    rd = launch.run_dir(runs, 'BLCA', 0, 'tri')
    res = train.train(model, parts['train'], parts['val'], EVAL_CFG, rd, log=lambda *_: None)
    (rd / 'run.json').write_text(json.dumps({'config': EVAL_CFG, 'config_sha256': CFG_SHA,
                                             'git': {'commit': COMMIT, 'dirty': False},
                                             'assets_fp': provenance.asset_fingerprint(assets), **res}))
    return root


@pytest.fixture
def env(base, tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, 'identity', lambda: {'commit': COMMIT, 'dirty': False, 'source': 'test'})
    monkeypatch.setattr(train, 'DEFAULTS', dict(EVAL_CFG, epochs=50))
    monkeypatch.setattr(train, 'CONFIG_SHA256', CFG_SHA)
    root = tmp_path / 'w'
    shutil.copytree(base, root)
    assets, runs = root / 'assets', root / 'runs'
    return assets, runs, authorize(assets, runs)


def authorize(assets, runs):
    """按当前 ckpt / run.json / 资产生成授权参数（模拟 launch digest → evaluate）。"""
    items = launch.plan(['BLCA'], [0], ['tri'])
    ck = launch.ckpt_hashes(runs, items)['BLCA/0/tri']
    digest = launch.digest(runs, items, assets, COMMIT)
    return ['--assets', str(assets), '--runs', str(runs), '--cancer', 'BLCA', '--fold', '0', '--arm', 'tri',
            '--device', 'cpu', '--expected-commit', COMMIT, '--auth-digest', digest, '--ckpt-sha256', ck['ckpt'],
            '--run-sha256', ck['run'], '--plan-cancers', 'BLCA', '--plan-folds', '0', '--plan-arms', 'tri']


def test_authorized_path_writes_metrics(env):
    assets, runs, args = env
    evaluate.main(args)
    m = json.loads((launch.run_dir(runs, 'BLCA', 0, 'tri') / 'test_metrics.json').read_text())
    assert 'full' in m['c_index'] and 'only_wsi__zero' in m['c_index']


def test_direct_call_without_digest_is_refused(env):
    _, _, args = env
    i = args.index('--auth-digest')
    with pytest.raises(SystemExit):
        evaluate.main(args[:i] + args[i + 2:])
    args[i + 1] = 'f' * 64
    with pytest.raises(PermissionError, match='授权摘要'):
        evaluate.main(args)


def test_tampered_asset_content_is_refused(env):
    assets, runs, args = env
    f = next((assets / 'wsi_tokens' / 'BLCA').glob('*.npz'))
    with np.load(f) as z:
        tok, mask = z['tokens'].copy(), z['mask']
    tok[0, 0] += 1.0
    np.savez(f, tokens=tok, mask=mask)
    with pytest.raises(ValueError, match='wsi_tokens'):
        evaluate.main(args)
    assert not (launch.run_dir(runs, 'BLCA', 0, 'tri') / 'test_metrics.json').exists()


def test_ckpt_replaced_after_authorization_is_refused(env):
    _, runs, args = env
    p = launch.run_dir(runs, 'BLCA', 0, 'tri') / 'best.pt'
    sd = torch.load(p, weights_only=True)
    sd['risk.weight'] = sd['risk.weight'] * 2
    torch.save(sd, p)
    with pytest.raises(PermissionError, match='ckpt 哈希'):
        evaluate.main(args)


def test_item_outside_authorized_plan_is_refused(env):
    _, _, args = env
    args[args.index('--plan-arms') + 1] = 'wsi'
    with pytest.raises(PermissionError, match='授权清单'):
        evaluate.main(args)


def test_launch_passes_ckpt_hash_and_digest_to_children(env, capsys):
    assets, runs, args = env
    digest = args[args.index('--auth-digest') + 1]
    launch.main(['evaluate', '--assets', str(assets), '--runs', str(runs), '--cancers', 'BLCA', '--folds', '0',
                 '--arms', 'tri', '--expected-commit', COMMIT, '--auth-digest', digest, '--dry-run'])
    out = capsys.readouterr().out
    sha = hashlib.sha256((launch.run_dir(runs, 'BLCA', 0, 'tri') / 'best.pt').read_bytes()).hexdigest()
    run_sha = hashlib.sha256((launch.run_dir(runs, 'BLCA', 0, 'tri') / 'run.json').read_bytes()).hexdigest()
    assert f'--ckpt-sha256 {sha}' in out and f'--auth-digest {digest}' in out and f'--run-sha256 {run_sha}' in out


def test_asset_replaced_after_manifest_read_is_refused(env, monkeypatch):
    """第 3 轮 high 1：manifest 读入（摘要据此通过）之后再替换数据文件，加载时按同一份 manifest 核对字节而拒绝。"""
    assets, runs, args = env
    real = provenance.AssetReader.__init__

    def init_then_tamper(self, root):
        real(self, root)
        f = next((assets / 'wsi_tokens' / 'BLCA').glob('*.npz'))
        with np.load(f) as z:
            tok, mask = z['tokens'].copy(), z['mask']
        tok[0, 0] += 1.0
        np.savez(f, tokens=tok, mask=mask)

    monkeypatch.setattr(provenance.AssetReader, '__init__', init_then_tamper)
    with pytest.raises(ValueError, match='与 manifest 不符'):
        evaluate.main(args)
    assert not (launch.run_dir(runs, 'BLCA', 0, 'tri') / 'test_metrics.json').exists()


def edit_run(runs, **kw):
    p = launch.run_dir(runs, 'BLCA', 0, 'tri') / 'run.json'
    run = json.loads(p.read_text())
    run.update(kw)
    p.write_text(json.dumps(run))


def test_run_json_edited_after_authorization_is_refused(env):
    """第 3 轮 high 2：授权后改 run.json（如 best_epoch），哈希不符而拒绝。"""
    _, runs, args = env
    edit_run(runs, best_epoch=1)
    with pytest.raises(PermissionError, match='run.json'):
        evaluate.main(args)


@pytest.mark.parametrize('kw', [{'config': dict(EVAL_CFG, lr=1e-3)}, {'config_sha256': 'f' * 64},
                                {'config': dict(EVAL_CFG, epochs=100)}])
def test_run_config_differs_from_config_yaml_is_refused_even_if_reauthorized(env, kw):
    """即使改完 run.json 后重新授权，超参数或 config 哈希与当前 config.yaml 不同也拒绝（epochs 50/100 之外的字段不许变）。"""
    assets, runs, _ = env
    edit_run(runs, **kw)
    args = authorize(assets, runs)
    if kw.get('config', {}).get('epochs') == 100:
        evaluate.main(args)  # 欠拟合预案：epochs 改 100 是唯一允许的差异
        return
    with pytest.raises(PermissionError, match='config'):
        evaluate.main(args)
