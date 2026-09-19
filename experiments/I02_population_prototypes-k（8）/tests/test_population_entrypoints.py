"""入口行为测试：防止新模式参数丢失或与其他补全叠加。"""
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.I02_population_prototypes import train as main


def _parse_author_args(argv):
    return main.parsing_args(list(argv) + ['--bin_mode', 'author'])


def test_training_cli_requires_explicit_population_k():
    args = _parse_author_args(['--network_type', 'NPJC', '--compensator', 'population', '--prototype-k', '2'])
    assert args.prototype_k == 2 and args.compensator == 'population'
    with pytest.raises(SystemExit):
        _parse_author_args(['--network_type', 'NPJC', '--compensator', 'population'])
    with pytest.raises(SystemExit):
        _parse_author_args(['--network_type', 'NPJC', '--compensator', 'population', '--prototype-k', '0'])


def test_model_factory_population_scope_and_seed():
    assert 'prototype_k' in inspect.signature(main.load_model).parameters, '模型工厂尚未接收人群簇数'
    modalities = {m: SimpleNamespace(feature_dim=4) for m in ('img', 'rna', 'text')}
    kwargs = dict(device='cpu', modalities=modalities, hidden_size=8, pred_dim=4,
                  compensator='population', prototype_k=2, seed=17, cancer_types=['A'])
    model = main.load_model(network_type='NPJC', **kwargs)
    assert model.compensator.prototypes['wsi'].shape == (2, 8)
    with pytest.raises(ValueError, match='NPJC'):
        main.load_model(network_type='MainModalityMoE', **kwargs)
    # 未套 DataParallel/DDP 的 CPU/单进程路径也必须把癌种送入正确 head。
    model.train()
    batch = {m: torch.ones(2, 3, 4) for m in modalities}
    batch.update(rna_valid=torch.zeros(2), text_valid=torch.zeros(2))
    outputs = main._forward_survival_model(model, batch, ['A', 'A'], True)
    assert outputs[0].shape == (2, 4)


def test_output_identity_includes_k_and_legacy_suffix_stays_same():
    for mode, k, suffix in [('population', 2, '_population_k2'), ('population', 5, '_population_k5'), ('capr', None, '_capr'), ('none', None, '')]:
        args = SimpleNamespace(compensator=mode, prototype_k=k, cpt_name='test', result_path='out')
        main._append_compensator_suffix(args)
        main._append_compensator_suffix(args)
        assert args.result_path == 'out' + suffix
        assert args.cpt_name == 'test' + suffix


def test_population_artifact_paths_isolate_distinct_cpt_names(tmp_path):
    assert hasattr(main, '_population_artifact_paths'), (
        'population CSV/plots 尚未从 ModelDumper.task_path_str 派生'
    )
    modalities = {
        name: SimpleNamespace(feature_dim=4)
        for name in ('img', 'rna', 'text')
    }
    model_config = SimpleNamespace(obj=SimpleNamespace(modality=modalities))

    def make_dumper(cpt_name):
        args = SimpleNamespace(
            network_type='NPJC', cancer_types='A_B', task_type='surv',
            pretrain_path='', finetune_head_only=False,
            simulate_missing_modality='',
        )
        return main.ModelDumper(
            tmp_path / 'out', 19, cpt_name, modalities, args, model_config
        )

    alpha_csv, alpha_plots = main._population_artifact_paths(
        make_dumper('alpha')
    )
    beta_csv, beta_plots = main._population_artifact_paths(
        make_dumper('beta')
    )

    assert alpha_csv == tmp_path / 'out/19/test_pred_and_label_alpha_img_4rna_4text_4_NPJC_A_B_surv.csv'
    assert alpha_plots == tmp_path / 'out/19/alpha_img_4rna_4text_4_NPJC_A_B_surv_plots'
    assert beta_csv == tmp_path / 'out/19/test_pred_and_label_beta_img_4rna_4text_4_NPJC_A_B_surv.csv'
    assert beta_plots == tmp_path / 'out/19/beta_img_4rna_4text_4_NPJC_A_B_surv_plots'
    assert alpha_csv != beta_csv
    assert alpha_plots != beta_plots


def eval_module():
    from experiments.I02_population_prototypes import evaluate
    return evaluate


def test_eval_cli_population_does_not_allow_mean_prefill(monkeypatch):
    module = eval_module()
    base = ['eval_missing.py', '--bin_mode', 'author', '--arm', 'm0real', '--cancer', 'BLCA', '--seed', '1',
            '--ckpt', 'fake.pth', '--manifest', 'manifest.csv', '--label', 'label.csv',
            '--out-dir', 'out', '--compensator', 'population', '--network_type', 'NPJC', '--prototype-k', '2']
    monkeypatch.setattr(sys, 'argv', base)
    args = module.parse_args()
    assert args.prototype_k == 2
    bad = list(base)
    bad[bad.index('m0real')] = 'm1'
    monkeypatch.setattr(sys, 'argv', bad)
    with pytest.raises(SystemExit):
        module.parse_args()


def test_population_eval_refuses_to_overwrite_existing_json(tmp_path):
    module = eval_module()
    assert hasattr(module, '_write_evaluation_result'), (
        'population eval 尚无目标 JSON 防覆盖写入边界'
    )
    output = tmp_path / 'm0real_BLCA_s19_population_k2.json'
    sentinel = '{"existing": true}\n'
    output.write_text(sentinel, encoding='utf-8')
    args = SimpleNamespace(compensator='population')

    with pytest.raises(FileExistsError, match='exists|存在|overwrite|覆盖'):
        module._write_evaluation_result(args, output, {'replacement': True})

    assert output.read_text(encoding='utf-8') == sentinel


def test_legacy_eval_keeps_existing_json_overwrite_behavior(tmp_path):
    module = eval_module()
    assert hasattr(module, '_write_evaluation_result'), (
        'eval JSON 写入尚未提供可验证的生产边界'
    )
    output = tmp_path / 'm0real_BLCA_s19.json'
    output.write_text('{"existing": true}\n', encoding='utf-8')
    args = SimpleNamespace(compensator='none')

    module._write_evaluation_result(args, output, {'replacement': True})

    assert json.loads(output.read_text(encoding='utf-8')) == {
        'replacement': True
    }
