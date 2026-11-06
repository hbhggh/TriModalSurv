"""I08 接口契约：config 键/类型/钉死值、缺失模式枚举、参数量、符号形状、风险头拼接顺序、I07 冻结。"""
import copy

import pytest
import torch

from experiments.I07_ps3style_backbone import data
from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.tests.test_train import small_model, write_assets
from experiments.I08_ps3_shared_recovery import contract


@pytest.fixture(scope='module')
def cfg():
    c, sha = contract.load_config()
    assert len(sha) == 64
    return c


@pytest.fixture(scope='module')
def val_part(tmp_path_factory):
    root = tmp_path_factory.mktemp('i08')
    write_assets(root)
    parts, _ = data.load_fold(root, 'BLCA', 0, parts=('train', 'val'))
    return parts['val']


def test_real_config_passes(cfg):
    assert cfg['operator_A']['r'] == 32 and cfg['backbone']['d'] == 256


def test_six_patterns_and_targets_follow_i07_order():
    assert contract.PATTERNS == ('rna', 'wsi', 'text', 'rna+wsi', 'rna+text', 'wsi+text')
    assert contract.targets('wsi') == ('rna', 'text')
    assert contract.targets('rna+text') == ('wsi',)
    with pytest.raises(contract.ContractError):
        contract.visible('text+rna')            # 顺序反了就是另一个键，必须拒绝


def test_param_count_matches_storyline():
    assert contract.n_params(256, 32) == {'A': 24576, 'B': 12576, 'total': 37152}


@pytest.mark.parametrize('path,bad', [
    (('operator_C', 'lambda_cons'), 1),                 # int 冒充 float
    (('operator_A', 'r'), 64),                          # 不在候选网格
    (('position', 'visible_route'), 'recovered'),       # 违反 W1-4
    (('features', 'mean_source'), 'train+val'),         # 均值混入 val
    (('train', 'test_access'), True),
    (('backbone', 'modalities'), ['wsi', 'rna', 'text']),
    (('backbone', 'head_in'), 512),
    (('operator_C', 'stop_grad_target'), False),
])
def test_config_violations_are_rejected(cfg, path, bad):
    c = copy.deepcopy(cfg)
    sec = c
    for k in path[:-1]:
        sec = sec[k]
    sec[path[-1]] = bad
    with pytest.raises(contract.ContractError):
        contract.check_config(c)


def test_extra_or_missing_keys_are_rejected(cfg):
    c = copy.deepcopy(cfg)
    c['operator_B']['gate'] = True
    with pytest.raises(contract.ContractError):
        contract.check_config(c)
    c = copy.deepcopy(cfg)
    del c['tensors']['z_hat']
    with pytest.raises(contract.ContractError):
        contract.check_config(c)


def test_symbolic_shapes(cfg):
    assert contract.tensor_shape(cfg, 'U') == (256, 32)
    assert contract.tensor_shape(cfg, 'R', k=2) == (32, 64)
    assert contract.tensor_shape(cfg, 'head_in') == (None, 768)
    with pytest.raises(contract.ContractError):
        contract.tensor_shape(cfg, 'b_in')                      # 含 k 却没给 k
    contract.check_tensor(cfg, 'z_hat', torch.zeros(5, 32))
    for bad in (torch.zeros(5, 16), torch.zeros(5, 32, dtype=torch.float64), torch.full((5, 32), float('nan'))):
        with pytest.raises(contract.ContractError):
            contract.check_tensor(cfg, 'z_hat', bad)


def test_assembled_head_input_reproduces_i07_masked_forward(val_part):
    """可见位 = I07 在 present=Ω 下的 pooled 原样；缺失位放常数时，frozen 风险头输出必须与 I07 自己的 fill 路径逐值一致。
    这钉住了拼接顺序（rna|wsi|text）和"可见位用 p^Ω 而不是 p^F"两件事。"""
    m = small_model()
    d = m.d
    for pattern in contract.PATTERNS:
        vis, tgt = contract.visible(pattern), contract.targets(pattern)
        fill = {u: torch.randn(d) for u in tgt}
        with torch.no_grad():
            out = m(val_part, present=vis, fill=fill)
            n = len(val_part.patient_ids)
            p_hat = {u: fill[u].expand(n, -1) for u in tgt}
            risk = m.risk(contract.assemble_head_in(pattern, out['pooled'], p_hat)).squeeze(-1)
        assert torch.allclose(risk, out['risk'], atol=1e-6), pattern


def test_assemble_rejects_wrong_keys():
    x = torch.zeros(2, 4)
    with pytest.raises(contract.ContractError):
        contract.assemble_head_in('rna', {'rna': x}, {'wsi': x})              # 漏了 text
    with pytest.raises(contract.ContractError):
        contract.assemble_head_in('rna', {'rna': x, 'wsi': x}, {'wsi': x, 'text': x})  # 可见位多给


def test_check_frozen():
    m = small_model()
    with pytest.raises(contract.ContractError):
        contract.check_frozen(m)                         # 参数仍 requires_grad
    for p in m.parameters():
        p.requires_grad_(False)
    contract.check_frozen(m.eval())
    with pytest.raises(contract.ContractError):
        contract.check_frozen(m.train())


def test_views_match_i07_present_sets():
    assert contract.VIEWS[0] == 'full'
    assert all(set(contract.visible(p)) <= set(MODALITIES) for p in contract.PATTERNS)
