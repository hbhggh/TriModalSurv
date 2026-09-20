"""早停边界与真实训练循环：防止只保存最佳模型却没有停止。"""
import sys
import json
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiments.I02_population_prototypes import train as main
from experiments.I02_population_prototypes import runtime
from experiments.I02_population_prototypes.tests.population_smoke import SyntheticConfig, synthetic_dataset


def _parse_author_args(argv):
    return main.parsing_args(list(argv) + ['--bin_mode', 'author'])


def stopper(patience=15):
    assert hasattr(runtime, 'PopulationEarlyStopping'), '尚未实现 population 早停计数'
    return runtime.PopulationEarlyStopping(patience)


def test_fifteen_non_improvements_stop_and_ties_count():
    state = stopper()
    assert not state.update(.6, 0)['should_stop']
    for epoch in range(1, 15):
        assert not state.update(.6, epoch)['should_stop']
    report = state.update(.5, 15)
    assert report == dict(epoch=16, best_epoch=1, best_cindex=.6,
                          bad_epochs=15, patience=15, should_stop=True)


def test_improvement_resets_counter_and_disabled_keeps_running():
    state = stopper(2)
    assert not state.update(0., 0)['should_stop']
    assert not state.update(0., 1)['should_stop']
    assert state.update(.1, 2)['bad_epochs'] == 0
    assert not state.update(.1, 3)['should_stop']
    assert state.update(.09, 4)['should_stop']
    disabled = stopper(0)
    for epoch in range(20):
        assert not disabled.update(.6, epoch)['should_stop']


def test_invalid_patience_and_nonfinite_metric_fail():
    for patience in (-1, 1.5, True):
        with pytest.raises(ValueError, match='patience'):
            stopper(patience)
    for score in (float('nan'), float('inf'), float('-inf')):
        with pytest.raises(ValueError, match='finite'):
            stopper().update(score, 0)


def test_cli_early_stopping_is_population_only_and_opt_in():
    base = ['--network_type', 'NPJC', '--compensator', 'population', '--prototype-k', '8']
    args = _parse_author_args(base + ['--epochs', '100', '--early-stopping-patience', '15'])
    assert args.epochs == 100 and args.early_stopping_patience == 15
    assert _parse_author_args([]).early_stopping_patience == 0
    with pytest.raises(SystemExit):
        _parse_author_args(['--early-stopping-patience', '15'])
    with pytest.raises(SystemExit):
        _parse_author_args(base + ['--early-stopping-patience', '-1'])


@pytest.mark.parametrize('patience,max_epochs,expected_epochs,scores', [
    (15, 100, 16, None), (0, 2, 2, None), (15, 2, 2, None),
    (2, 10, 5, [.6, .5, .7, .6, .6]),
])
def test_real_main_stops_and_reloads_best_checkpoint(tmp_path, patience, max_epochs, expected_epochs, scores):
    torch.set_num_threads(1)
    main.set_seed(19)
    label_path = tmp_path / 'synthetic-label.csv'
    label_path.write_text('patient_id,split\nsynthetic,fixture\n')
    config_path = tmp_path / 'synthetic-model.json'
    config_path.write_text(json.dumps({'fixture': 'SyntheticConfig', 'feature_dim': 4,
                                      'pred_dim': 4, 'n_token': 3}))

    class FixtureConfig(SyntheticConfig):
        def __init__(self, path):
            super().__init__(path)
            for name, modality in self.obj.modality.items():
                modality.path = str(tmp_path / f'synthetic-{name}')

    args = _parse_author_args([
        '--network_type', 'NPJC', '--compensator', 'population', '--prototype-k', '2',
        '--hidden_size', '16', '--epochs', str(max_epochs), '--early-stopping-patience', str(patience),
        '--batch_size', '4', '--num_workers', '0', '--cancer_types', 'A_B_UNUSED',
        '--result_path', str(tmp_path / 'out'), '--cpt_name', 'earlystop',
        '--report_label_path', str(label_path), '--model_config', str(config_path),
        '--run_record_root', str(tmp_path / 'run-records'),
        '--gpu_config', str(ROOT.parents[1] / 'configs/gpu_train.yaml'), '--seed', '19',
    ])
    datasets = tuple(synthetic_dataset(s, n) for s, n in [('train', 13), ('valid', 9), ('test', 7)])
    original_pass, original_save, original_load = main.finetune_epoch, torch.save, main.load_population_checkpoint
    epochs, saved, loaded = [], [], []

    def controlled_validation(*a, **kw):
        result = original_pass(*a, **kw)
        if not kw['training']:
            epochs.append(a[4])
            # 仅控制验证分数，模型训练、全量建库、保存及重载仍走生产代码。
            result['c-index'] = result['metric'] = .6 if scores is None else scores[a[4]]
        return result

    def record_save(state, *a, **kw):
        saved.append({k: v.detach().cpu().clone() for k, v in state.items()})
        return original_save(state, *a, **kw)

    def verify_load(model, path, accelerator):
        original_load(model, path, accelerator)
        state = accelerator.unwrap_model(model).state_dict()
        assert all(torch.equal(value.cpu(), saved[-1][key]) for key, value in state.items())
        loaded.append(True)

    with patch.object(main, 'YmlConfig', FixtureConfig), \
         patch.object(main, 'get_dataset_tcga_sur', lambda *a, **k: datasets), \
         patch.object(main, 'finetune_epoch', controlled_validation), \
         patch.object(torch, 'save', record_save), \
         patch.object(main, 'load_population_checkpoint', verify_load):
        main.main(args)
    assert epochs == list(range(expected_epochs))
    assert len(saved) == (1 if scores is None else 2) and loaded == [True]
    if scores is not None:
        assert any(not torch.equal(value, saved[0][key]) for key, value in saved[1].items())
    assert len(list(Path(args.result_path).rglob('*.pth'))) == 1

    run_dirs = list((tmp_path / 'run-records').iterdir())
    assert len(run_dirs) == 1
    run = run_dirs[0]
    data_manifest = json.loads((run / 'data_manifest.json').read_text())
    inputs = {item['path']: item['sha256'] for item in data_manifest['inputs']}
    assert inputs[str(label_path.resolve())] == hashlib.sha256(label_path.read_bytes()).hexdigest()
    sources = json.loads((run / 'source_manifest.json').read_text())['files']
    assert any(item['path'] == str(config_path.resolve()) and
               item['sha256'] == hashlib.sha256(config_path.read_bytes()).hexdigest() for item in sources)
    completion = json.loads((run / 'audit/completion.json').read_text())
    assert completion['status'] == 'complete'
    checkpoint = Path(completion['checkpoint']['path'])
    assert completion['checkpoint']['sha256'] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    source_paths = {item['path'] for item in sources}
    assert str((ROOT / 'model.py').resolve()) in source_paths
    assert str((ROOT.parents[1] / 'src/trimodalsurv/models/npjc.py').resolve()) in source_paths
    csv_entries = [item for item in completion['artifacts'] if item['source']['path'].endswith('.csv')]
    assert len(csv_entries) == 1
    csv_entry = csv_entries[0]
    assert csv_entry['source']['sha256'] == csv_entry['copy']['sha256']
    assert Path(csv_entry['copy']['path']).parent == run / 'raw'
    assert hashlib.sha256(Path(csv_entry['copy']['path']).read_bytes()).hexdigest() == csv_entry['copy']['sha256']
