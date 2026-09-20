"""实验组合必须保持公共模型类型和checkpoint键。"""
from types import SimpleNamespace
import pytest
from experiments.I03_npj_d_dm_e1.model import build_model, NPJC, MainModalityMoE, CAPRecall

@pytest.mark.parametrize('arm', ['D', 'Dm', 'E1'])
def test_historical_composition_has_no_wrapper_prefix(arm):
    model = build_model(arm, device='cpu', modalities={m: SimpleNamespace(feature_dim=4)
        for m in ('img', 'text', 'rna')}, hidden_size=8, cancer_types=['BLCA'])
    assert isinstance(model, NPJC if arm == 'E1' else MainModalityMoE)
    assert all(not key.startswith('model.') for key in model.state_dict())
    if arm == 'E1':
        assert isinstance(model.compensator, CAPRecall)
    else:
        assert model.compensator is None
        assert not list(model.fusion.parameters())
