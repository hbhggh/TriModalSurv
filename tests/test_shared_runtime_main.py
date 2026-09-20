"""公共 main 的 CPU 产物事务验收；受控 epoch/预测，不是数值对拍。

真正执行 main、模型构造、checkpoint 保存/严格重载、绘图、CSV、结果 JSON、
运行来源和完成记录。数据与分数使用合成替身；数值等价另由 epoch parity 验证。
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import torch
from torch.utils.data import TensorDataset

from trimodalsurv.training import runtime
from trimodalsurv.config import training_artifact_paths


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CPUAccelerator:
    """仅为隔离 Accelerate 全局混精度状态；不替换 main 的产物分支。"""
    is_main_process = True

    def __init__(self, **kwargs):
        assert kwargs == {'mixed_precision': 'bf16'}

    def prepare(self, *objects):
        return objects


@pytest.fixture
def main_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    monkeypatch.setattr(torch.cuda, 'device_count', lambda: 0)
    monkeypatch.delenv('FORMAL_RUN', raising=False)
    label = tmp_path / 'synthetic-label.csv'
    label.write_text('patient_id,split\nsynthetic,fixture\n')
    config = tmp_path / 'synthetic-model.json'
    config.write_text(json.dumps({'fixture': '4-dimensional, 3-modalities'}))
    gpu = tmp_path / 'gpu.json'
    gpu.write_text(json.dumps({'pin_memory': False, 'persistent_workers': False}))

    class FixtureConfig:
        def __init__(self, path):
            assert Path(path) == config
            self.obj = SimpleNamespace(
                modality={name: SimpleNamespace(feature_dim=4, path=str(tmp_path / name))
                          for name in ('img', 'rna', 'text')},
                task_type='surv', img_select='random',
                network=SimpleNamespace(pred_dim=4, n_token=3))

        def parse_to_modality(self, value):
            return value

    def args(seed=123):
        return runtime.parsing_args([
            '--network_type', 'NPJC', '--compensator', 'none', '--bin_mode', 'author',
            '--hidden_size', '16', '--epochs', '1', '--batch_size', '2', '--num_workers', '0',
            '--cancer_types', 'A', '--seed', str(seed), '--cpt_name', 'artifact-contract',
            '--report_label_path', str(label), '--model_config', str(config), '--gpu_config', str(gpu),
            '--result_path', str(tmp_path / 'out'), '--run_record_root', str(tmp_path / 'records')])

    monkeypatch.setattr(runtime, 'YmlConfig', FixtureConfig)
    monkeypatch.setattr(runtime, 'Accelerator', CPUAccelerator)
    return args, FixtureConfig, label


def test_real_main_artifact_transaction_two_seeds(tmp_path, main_fixture):
    args_factory, config_factory, label = main_fixture
    torch.set_num_threads(1)
    produced = []
    for seed in (123, 132):
        args = args_factory(seed)
        runtime.set_seed(seed)
        calls = []
        dataset = TensorDataset(torch.zeros(2, 1))

        def controlled_epoch(model, criterion, optimizer, loader, epoch, **kwargs):
            calls.append(kwargs['training'])
            manifests = list((tmp_path / 'records').glob('*/checkpoint_manifest.json'))
            pending = [p for p in manifests if not (p.parent / 'audit/completion.json').exists()]
            assert len(pending) == 1
            assert json.loads(pending[0].read_text())['status'] == 'pending'
            # 稳定触发真实 checkpoint 保存；本测试不声称优化数值等价。
            return {'loss': 0.4, 'c-index': 0.6, 'metric': 0.6}

        def controlled_prediction(*objects, **kwargs):
            return ({'loss': 0.3, 'c-index': 0.6, 'metric': 0.6},
                    {'patient_id': ['synthetic-0', 'synthetic-1'], 'idx': [0, 1],
                     'cancer_type': ['A', 'A'], 'risk': [-1.0, -2.0],
                     'time': [1.0, 2.0], 'censorship': [0.0, 1.0]})

        original_csv = runtime.pd.DataFrame.to_csv
        csv_modes = []

        def csv_with_mode_check(frame, *positional, **kwargs):
            csv_modes.append(kwargs.get('mode'))
            return original_csv(frame, *positional, **kwargs)

        with patch.object(runtime, 'get_dataset_tcga_sur', return_value=(dataset, dataset, dataset)), \
             patch.object(runtime, 'finetune_epoch', controlled_epoch), \
             patch.object(runtime, 'prediction', controlled_prediction), \
             patch.object(runtime.pd.DataFrame, 'to_csv', csv_with_mode_check):
            runtime.main(args)
        assert calls == [True, False]
        assert csv_modes == ['x']
        dumper = runtime.ModelDumper(args.result_path, seed, args.cpt_name,
            config_factory(args.model_config).obj.modality, args, config_factory(args.model_config))
        paths = training_artifact_paths(dumper.task_path_str)
        assert paths['predictions'].parent.name == str(seed)
        assert paths['predictions'].name == f'test_pred_and_label_{Path(dumper.task_path_str).name}.csv'
        assert (paths['plots'] / 'training_curves.png').is_file()
        assert json.loads(paths['metrics'].read_text()) == {'loss': 0.3, 'c-index': 0.6}
        with pytest.raises(FileExistsError):
            dumper.dump_results({'must_not_overwrite': 1})
        completions = [json.loads(path.read_text()) for path in (tmp_path / 'records').glob('*/audit/completion.json')]
        completion = next(value for value in completions if value['checkpoint']['path'] == str(dumper.model_path.resolve()))
        assert completion['status'] == 'complete'
        assert completion['checkpoint']['sha256'] == _sha(dumper.model_path)
        assert len(completion['artifacts']) == 2
        for entry in completion['artifacts']:
            assert entry['source']['sha256'] == entry['copy']['sha256'] == _sha(entry['copy']['path'])
        produced.append(set(paths.values()))
        # 已有运行应在构建 Dataset 前失败，不能再开训练再发现冲突。
        with patch.object(runtime, 'get_dataset_tcga_sur', side_effect=AssertionError('must not load data')):
            with pytest.raises(FileExistsError):
                runtime.main(args_factory(seed))
    assert produced[0].isdisjoint(produced[1])


@pytest.mark.parametrize('kind', ['predictions', 'metrics', 'plots'])
def test_real_main_rejects_existing_artifact_before_data(tmp_path, main_fixture, kind):
    args_factory, config_factory, _ = main_fixture
    args = args_factory()
    config = config_factory(args.model_config)
    dumper = runtime.ModelDumper(args.result_path, args.seed, args.cpt_name, config.obj.modality, args, config)
    path = training_artifact_paths(dumper.task_path_str)[kind]
    if kind == 'plots':
        path.mkdir()
    else:
        path.write_text('preserved')
    with patch.object(runtime, 'get_dataset_tcga_sur', side_effect=AssertionError('must not load data')):
        with pytest.raises(FileExistsError, match='拒绝覆盖已有运行产物'):
            runtime.main(args)
    assert not (tmp_path / 'records').exists()
    assert path.is_dir() if kind == 'plots' else path.read_text() == 'preserved'
