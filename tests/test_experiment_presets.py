"""真实公共训练工厂与实验预设合同，不启动训练或读取患者数据。"""
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from trimodalsurv.training import runtime
from experiments.I03_npj_d_dm_e1.model import build_model
from experiments.I04_cap4_multi_prototypes.train import load_model as capl_load_model
from experiments.I04_cap4_multi_prototypes.model import CAPRecallMulti

ROOT = Path(__file__).resolve().parents[1]
I03 = ROOT / 'experiments/I03_npj_d_dm_e1/config.yaml'
I04 = ROOT / 'experiments/I04_cap4_multi_prototypes/config.yaml'
MODALITIES = {name: SimpleNamespace(feature_dim=size) for name, size in {'img': 8, 'rna': 4, 'text': 6}.items()}


def parse(config, preset, *extra):
    return runtime.parsing_args(['--config', str(config), '--preset', preset, *extra])


@pytest.mark.parametrize('arm', ['D', 'Dm', 'E1'])
def test_i03_actual_runtime_factory_matches_experiment(arm):
    args = parse(I03, arm)
    actual = runtime.load_model(args.network_type, 'cpu', MODALITIES,
        args.hidden_size, 4, compensator=args.compensator, fusion_type=args.fusion_type)
    expected = build_model(arm, device='cpu', modalities=MODALITIES)
    assert type(actual) is type(expected)
    assert type(actual.compensator) is type(expected.compensator)
    assert type(getattr(actual, 'fusion', None)) is type(getattr(expected, 'fusion', None))
    assert {k: (v.shape, v.dtype) for k, v in actual.state_dict().items()} == {
        k: (v.shape, v.dtype) for k, v in expected.state_dict().items()}
    assert args.hidden_size == 256 and args.bin_mode == 'author'


@pytest.mark.parametrize('preset,slots', [('dq0', None), ('dq_capl1', 1), ('dq_capl8', 8), ('dq_capl32', 32)])
def test_i04_actual_factory_from_preset(preset, slots):
    args = parse(I04, preset)
    actual = capl_load_model(args.network_type, 'cpu', MODALITIES, args.hidden_size,
        4, compensator=args.compensator, fusion_type=args.fusion_type,
        proto_per_bin=args.proto_per_bin)
    assert args.bin_mode == 'train_quantile' and args.hidden_size == 256
    assert type(actual.fusion).__name__ == 'MeanFusion'
    if slots is None:
        assert actual.compensator is None
    else:
        assert isinstance(actual.compensator, CAPRecallMulti)
        expected = CAPRecallMulti(('text', 'rna'), 256, n_bins=4, proto_per_bin=slots, ema=0.99)
        assert {k: v.shape for k, v in actual.compensator.state_dict().items()} == {
            k: v.shape for k, v in expected.state_dict().items()}


def test_explicit_cli_wins_without_default_arm():
    args = parse(I03, 'E1', '--modality_dropout', '0', '--train', 'false')
    assert args.modality_dropout == 0 and args.train is False
    with pytest.raises(ValueError, match='必须显式 --preset'):
        runtime.parsing_args(['--config', str(I03)])
    with pytest.raises(ValueError, match='必须显式 --preset'):
        parse(I03, 'unknown')


@pytest.mark.parametrize('mutation', ['top', 'model', 'preset', 'pred_dim', 'choice'])
def test_invalid_config_is_rejected(tmp_path, mutation):
    doc = json.loads(I03.read_text())
    if mutation == 'top': doc['typo'] = 1
    if mutation == 'model': doc['model']['typo'] = 1
    if mutation == 'preset': doc['presets']['D']['typo'] = 1
    if mutation == 'pred_dim': doc['model']['pred_dim'] = 17
    if mutation == 'choice': doc['presets']['D']['compensator'] = 'typo'
    target = tmp_path / 'config.json'
    target.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        parse(target, 'D')


def test_explicit_missing_checkout_config_has_clear_error(tmp_path):
    with pytest.raises(ValueError, match='完整 repo checkout'):
        parse(I03, 'D', '--model_config', str(tmp_path / 'absent.yml'))


def test_missing_network_mapping_has_clear_error(tmp_path):
    target = tmp_path / 'model.json'
    target.write_text('{}')
    with pytest.raises(ValueError, match='network 配置映射'):
        parse(I03, 'D', '--model_config', str(target))


def test_i02_missing_checkout_config_has_clear_error(tmp_path):
    from experiments.I02_population_prototypes.train import parsing_args
    with pytest.raises(ValueError, match='完整 repo checkout'):
        parsing_args(['--bin_mode', 'author', '--model_config', str(tmp_path / 'absent.yml')])


def test_i02_rejects_non_population_before_any_side_effect():
    from experiments.I02_population_prototypes.train import main
    with pytest.raises(ValueError, match='I02 train requires population'):
        main(SimpleNamespace(compensator='none'))


def test_i02_has_one_effective_parameter_section(tmp_path):
    from experiments.I02_population_prototypes.train import parsing_args
    path = ROOT / 'experiments/I02_population_prototypes/config.yaml'
    doc = json.loads(path.read_text())
    assert set(doc) == {'experiment', 'provenance', 'runtime'}
    args = parsing_args(['--config', str(path)])
    assert args.hidden_size == 256 and args.epochs == 100 and args.prototype_k == 8
    doc['training'] = {'epochs': 3}
    bad = tmp_path / 'ambiguous.json'
    bad.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='生效参数仅放 runtime'):
        parsing_args(['--config', str(bad)])
