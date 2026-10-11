"""I07 接口契约（用户 2026-10-11 裁决 A）：形状、标签名与取值、风险方向、模型输出、config.yaml 键与类型，违约即报错。"""
import dataclasses

import pytest
import torch

from experiments.I07_ps3style_backbone import contract, data, provenance, survival, train
from experiments.I07_ps3style_backbone.tests.test_train import N_FIELDS, small_model, write_assets


@pytest.fixture(scope='module')
def assets(tmp_path_factory):
    root = tmp_path_factory.mktemp('contract')
    write_assets(root)
    return root


@pytest.fixture
def part(assets):
    parts, _ = data.load_fold(assets, 'BLCA', 0, parts=('train', 'val'))
    return parts['val']


def check(p):
    contract.check_part(p, n_genes=6, n_fields=N_FIELDS)


def test_valid_part_passes_and_fields_are_frozen(part):
    check(part)
    assert tuple(f.name for f in dataclasses.fields(data.Part)) == contract.PART_FIELDS


@pytest.mark.parametrize('mutate, msg', [
    (lambda p: setattr(p, 'wsi', p.wsi[:, :64]), 'wsi 的形状'),
    (lambda p: setattr(p, 'wsi', p.wsi.double()), 'wsi 的 dtype'),
    (lambda p: setattr(p, 'wsi_mask', p.wsi_mask.float()), 'wsi_mask 的 dtype'),
    (lambda p: p.wsi_mask[0].fill_(False), '没有任何真实 token'),
    (lambda p: setattr(p, 'rna', p.rna[:, :5]), 'rna 的形状'),
    (lambda p: setattr(p, 'text', p.text[:, :N_FIELDS - 1]), 'text 的形状'),
    (lambda p: setattr(p, 'text_nm', p.text_nm[:, :N_FIELDS - 1]), 'text_nm 的形状'),
    (lambda p: setattr(p, 'time', p.time[:, None]), 'time 的形状'),
    (lambda p: p.time.__setitem__(0, -1.0), 'time 有负值'),
    (lambda p: p.rna.__setitem__((0, 0), float('nan')), 'rna 含 NaN'),
    (lambda p: setattr(p, 'event', p.event + 1), 'event 只能取 0/1'),
    (lambda p: p.patient_ids.__setitem__(1, p.patient_ids[0]), '重复'),
])
def test_contract_violations_are_refused(part, mutate, msg):
    mutate(part)
    with pytest.raises(contract.ContractError, match=msg):
        check(part)


def test_no_censorship_convention_in_sources():
    """event = 1 表示死亡；censorship 与它反号，全部 I07 源码不得出现这种记法。"""
    for s in provenance.SOURCES:
        if s == 'contract.py':
            continue  # 契约里说明禁用它
        assert 'censor' not in (provenance.EXP / s).read_text(encoding='utf-8').lower(), s


def test_risk_direction_higher_means_worse():
    """风险越大预后越差：早死者风险高时 Cox 损失更小、C-index = 1。"""
    t = torch.tensor([1.0, 2.0, 3.0, 4.0, 5.0])
    e = torch.tensor([1.0, 1.0, 1.0, 1.0, 0.0])
    good, bad = -t, t
    assert survival.cox_loss(good, t, e) < survival.cox_loss(bad, t, e)
    assert survival.c_index(good.numpy(), t.numpy(), e.numpy()) == 1.0


def test_model_output_matches_contract(part):
    m = small_model()
    with torch.no_grad():
        out = m(part)
        contract.check_output(out, len(part), m.modalities)
        only = m(part, present=('wsi',), fill={'rna': torch.zeros(32), 'text': torch.zeros(32)})
    contract.check_output(only, len(part), ('wsi',))
    with pytest.raises(contract.ContractError, match='pooled'):
        contract.check_output(only, len(part), m.modalities)
    with pytest.raises(contract.ContractError, match='dict'):
        contract.check_output((out['risk'], out['pooled']), len(part), m.modalities)
    pooled = out['pooled']
    for bad, msg in [({**pooled, 'rna': pooled['rna'][:-1]}, r'pooled\[rna\] 必须是'),
                     ({**pooled, 'rna': pooled['rna'][:, :-1]}, 'd 不一致'),
                     ({**pooled, 'rna': pooled['rna'].tolist()}, r'pooled\[rna\] 必须是'),
                     ({**pooled, 'rna': pooled['rna'].clone().fill_(float('nan'))}, 'NaN'),
                     ({**pooled, 'rna': pooled['rna'].long()}, r'pooled\[rna\] 必须是')]:
        with pytest.raises(contract.ContractError, match=msg):
            contract.check_output({'risk': out['risk'], 'pooled': bad}, len(part), m.modalities)
    with pytest.raises(contract.ContractError, match='risk'):
        contract.check_output({'risk': out['risk'][:, None], 'pooled': out['pooled']}, len(part), m.modalities)


def test_config_yaml_is_the_frozen_plan_values():
    cfg, sha = contract.load_config()
    assert cfg == dict(d=256, lr=1e-4, weight_decay=1e-5, batch_size=64, epochs=50, dropout=0.25, seed=2026)
    assert train.DEFAULTS == cfg and train.CONFIG_SHA256 == sha and len(sha) == 64


@pytest.mark.parametrize('text, msg', [
    ('d: 256\nlr: 1e-4\nweight_decay: 1.0e-5\nbatch_size: 64\nepochs: 50\ndropout: 0.25\nseed: 2026\n', 'lr 必须是 float'),
    ('d: 256\nlr: 1.0e-4\nweight_decay: 1.0e-5\nbatch_size: 64\nepochs: 50\ndropout: 0.25\n', '键必须恰为'),
    ('d: 256\nlr: 1.0e-4\nweight_decay: 1.0e-5\nbatch_size: 64\nepochs: 50\ndropout: 0.25\nseed: 2026\nfoo: 1\n', '键必须恰为'),
    ('d: 256\nlr: 1.0e-4\nweight_decay: 1.0e-5\nbatch_size: 64\nepochs: 30\ndropout: 0.25\nseed: 2026\n', 'epochs 只能取'),
    ('d: 256.0\nlr: 1.0e-4\nweight_decay: 1.0e-5\nbatch_size: 64\nepochs: 50\ndropout: 0.25\nseed: 2026\n', 'd 必须是 int'),
    ('d: 256\nlr: 1.0e-4\nweight_decay: 1.0e-5\nbatch_size: true\nepochs: 50\ndropout: 0.25\nseed: 2026\n', 'batch_size 必须是 int'),
])
def test_bad_config_is_refused(tmp_path, text, msg):
    p = tmp_path / 'c.yaml'
    p.write_text(text)
    with pytest.raises(contract.ContractError, match=msg):
        contract.load_config(p)
