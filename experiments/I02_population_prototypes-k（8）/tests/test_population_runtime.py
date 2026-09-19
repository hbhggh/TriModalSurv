"""训练集建库边界与分布式收集契约；不加载真实 TCGA 数据。"""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def runtime():
    assert importlib.util.find_spec('experiments.I02_population_prototypes.runtime') is not None, (
        '缺少 population_runtime：尚无训练患者全量建库与分布式收集实现'
    )
    return importlib.import_module('experiments.I02_population_prototypes.runtime')


def dataset(split='train', ids=('a', 'b', 'c')):
    from trimodalsurv.data.tcga_dataset import TCGASurDataset
    ds = TCGASurDataset.__new__(TCGASurDataset)
    ds.split = split
    ds.selected_pids = list(ids)
    ds.modalities = ['img', 'rna', 'text']
    ds.dict_data = {m: {p: np.ones((2, 4)) * (i + 1)
                       for i, p in enumerate(ids)} for m in ds.modalities}
    ds.fallback_shapes = {m: (2, 4) for m in ds.modalities}
    ds.missing_set, ds.missing_mode = {'b'}, 'rna'
    ds.simulate_missing_set, ds.simulate_missing_modality = set(), []
    ds.modality_dropout = 1.0
    ds.modality_dropout_rngs = {}  # 建库不触碰随机 dropout。
    return ds


def test_train_view_keeps_fixed_mask_and_does_not_call_training_getitem():
    rt = runtime()
    ds = dataset()
    view = rt.PopulationTrainView(ds)
    assert len(view) == 3
    assert view[0]['rna_valid'].item() is True
    assert view[1]['rna_valid'].item() is False
    assert view[0]['idx'].item() == 0
    assert torch.equal(view[0]['rna'], torch.ones(2, 4))
    assert ds.modality_dropout == 1.0 and ds.modality_dropout_rngs == {}
    with pytest.raises(ValueError, match='train'):
        rt.PopulationTrainView(dataset('test'))


def test_split_integrity_rejects_duplicates_and_overlap():
    rt = runtime()
    rt.validate_population_splits(dataset(), dataset('valid', ('d',)), dataset('test', ('e',)))
    with pytest.raises(ValueError, match='duplicate'):
        rt.validate_population_splits(dataset(ids=('a', 'a')), dataset('valid', ('d',)), dataset('test', ('e',)))
    with pytest.raises(ValueError, match='overlap'):
        rt.validate_population_splits(dataset(), dataset('valid', ('a',)), dataset('test', ('e',)))


def test_global_outputs_deduplicate_padding_sort_and_require_coverage():
    rt = runtime()
    pieces = [{'idx': torch.tensor([2, 0]), 'hazard': torch.tensor([[3.], [1.]])},
              {'idx': torch.tensor([1, 0]), 'hazard': torch.tensor([[2.], [1.]])}]
    merged = rt.ordered_patient_outputs(pieces, 3)
    assert merged['idx'].tolist() == [0, 1, 2]
    assert merged['hazard'].flatten().tolist() == [1., 2., 3.]
    with pytest.raises(ValueError, match='coverage'):
        rt.ordered_patient_outputs(pieces, 4)


def test_bank_loader_does_not_consume_global_torch_rng():
    rt = runtime()
    before = torch.random.get_rng_state().clone()
    loader = rt.make_population_loader(dataset(), 2, {'num_workers': 0}, seed=7)
    batches = list(loader)
    assert torch.equal(before, torch.random.get_rng_state())
    assert torch.cat([b['idx'] for b in batches]).tolist() == [0, 1, 2]


def test_update_uses_complete_patients_restores_mode_and_rebuilds():
    rt = runtime()
    from experiments.I02_population_prototypes.model import PopulationPrototypeBank
    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.compensator = PopulationPrototypeBank(k=1, dim=4)
        def encode_patient_modalities(self, batch):
            assert not self.training and not torch.is_grad_enabled()
            return ({m: batch[m].mean(1) for m in ('img', 'rna', 'text')},
                    {m: batch[m + '_valid'] for m in ('img', 'rna', 'text')})
    from accelerate import Accelerator
    accelerator = Accelerator(cpu=True)
    model = Encoder().train()
    loader = rt.make_population_loader(dataset(), 2, {'num_workers': 0}, seed=3)
    rng_before = torch.random.get_rng_state().clone()
    report = rt.update_population_memory(model, loader, accelerator)
    assert model.training
    assert torch.equal(rng_before, torch.random.get_rng_state())
    assert report['train_patients'] == 3 and report['complete_patients'] == 2
    for prototype in model.compensator.prototypes.values():
        torch.testing.assert_close(prototype, torch.full((1, 4), 2.))


def test_checkpoint_zero_metric_saves_unwrapped_strictly_and_nan_fails(tmp_path):
    rt = runtime()
    from accelerate import Accelerator
    from experiments.I02_population_prototypes.model import PopulationPrototypeBank
    accelerator = Accelerator(cpu=True)
    model = PopulationPrototypeBank(k=1, dim=2)
    model.update_memory_bank(torch.ones(2, 2), torch.ones(2, 2), torch.ones(2, 2))
    path = tmp_path / 'bank.pth'
    best = rt.save_population_checkpoint(model, path, 0.0, float('-inf'), accelerator)
    assert best == 0.0 and path.is_file()
    clone = PopulationPrototypeBank(k=1, dim=2)
    rt.load_population_checkpoint(clone, path, accelerator)
    assert clone.ready.item()
    assert all(not k.startswith('module.') for k in torch.load(path, weights_only=True))
    with pytest.raises(RuntimeError, match='finite'):
        rt.save_population_checkpoint(model, path, float('nan'), best, accelerator)


def test_checkpoint_reload_accepts_accelerate_indexed_cpu(tmp_path, monkeypatch):
    rt = runtime()
    from accelerate import Accelerator
    model = torch.nn.Linear(2, 1)
    path = tmp_path / 'cpu.pth'
    torch.save(model.state_dict(), path)
    accelerator = Accelerator(cpu=True)
    # Accelerate 的 MULTI_CPU 返回 cpu:0；torch.load 不接受此 storage 标签。
    monkeypatch.setattr(accelerator.state, 'device', torch.device('cpu:0'))
    clone = torch.nn.Linear(2, 1)
    rt.load_population_checkpoint(clone, path, accelerator)
    torch.testing.assert_close(clone.weight, model.weight)


def test_new_run_refuses_to_overwrite_existing_checkpoint(tmp_path):
    rt = runtime()
    from accelerate import Accelerator
    accelerator = Accelerator(cpu=True)
    path = tmp_path / 'existing.pth'
    model = torch.nn.Linear(2, 1)
    torch.save(model.state_dict(), path)
    original = path.read_bytes()
    with pytest.raises(RuntimeError, match='existing checkpoint'):
        rt.save_population_checkpoint(model, path, .5, float('-inf'), accelerator)
    assert path.read_bytes() == original
