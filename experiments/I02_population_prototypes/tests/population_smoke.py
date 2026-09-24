"""真实 main/NPJ-C 合成短验收；默认两进程，--single-gpu 显式单卡。

仅替换磁盘数据来源和小型配置；模型、优化器、DDP、建库、评测和保存均为生产路径。
"""
import argparse
import json
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
import torch.distributed as dist

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.I02_population_prototypes import train as main
from trimodalsurv.data.tcga_dataset import TCGASurDataset
from experiments.I02_population_prototypes.model import PopulationPrototypeBank


def _parse_author_args(argv):
    return main.parsing_args(list(argv) + ['--bin_mode', 'author'])


def synthetic_dataset(split, size):
    ds = TCGASurDataset.__new__(TCGASurDataset)
    ds.split = split
    ds.selected_pids = [f'{split}-{i}' for i in range(size)]
    ds.modalities = ['img', 'rna', 'text']
    ds.filter_cancer_type = ['A' if i % 2 == 0 else 'B' for i in range(size)]
    ds.cls_label = [0] * size
    ds.survival_months = np.arange(1, size + 1, dtype=np.float32)
    ds.survival_months_bin = np.arange(size) % 4
    ds.censorship = np.asarray([float(i % 3 == 0) for i in range(size)])
    ds.fallback_shapes = {m: (3, 4) for m in ds.modalities}
    ds.dict_data = {m: {} for m in ds.modalities}
    for i, pid in enumerate(ds.selected_pids):
        vector = np.array([1 + i / 10, 1, 0, 0] if i % 2 == 0
                          else [0, 0, 1 + i / 10, 1], dtype=np.float32)
        for offset, modality in enumerate(ds.modalities):
            ds.dict_data[modality][pid] = np.tile(vector + offset, (3, 1))
    del ds.dict_data['rna'][ds.selected_pids[1]]
    del ds.dict_data['text'][ds.selected_pids[2]]
    ds.missing_set, ds.missing_mode = {ds.selected_pids[3]}, 'rna'
    ds.simulate_missing_set, ds.simulate_missing_modality = set(), []
    ds.modality_dropout = .4 if split == 'train' else 0.
    ds.modality_dropout_rngs = {(p, m): random.Random(i + 7)
                              for i, p in enumerate(ds.selected_pids)
                              for m in ('rna', 'text')}
    return ds


class SyntheticConfig:
    def __init__(self, _):
        self.obj = SimpleNamespace(
            modality={m: SimpleNamespace(feature_dim=4) for m in ('img', 'rna', 'text')},
            task_type='surv', img_select='random',
            network=SimpleNamespace(pred_dim=4, n_token=3),
        )
    def parse_to_modality(self, value):
        return value


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--early-stop-smoke', action='store_true', help='验证100轮上限被patience15在第16轮截断')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--cpu', action='store_true', help='仅CPU功能预检，不替代两GPU验收')
    mode.add_argument('--single-gpu', action='store_true', help='单卡冒烟，不替代两GPU验收')
    opts = parser.parse_args()
    if not opts.cpu:
        assert torch.cuda.is_available(), 'GPU acceptance requires CUDA'
        expected_ranks = 1 if opts.single_gpu else 2
        assert int(os.environ.get('WORLD_SIZE', '1')) == expected_ranks, 'Unexpected rank count'
        if opts.single_gpu:
            assert torch.cuda.device_count() == 1, 'Single GPU smoke requires one visible GPU'
    torch.set_num_threads(1)
    main.set_seed(19)
    args = _parse_author_args([
        '--network_type', 'NPJC', '--compensator', 'population', '--prototype-k', '2',
        '--hidden_size', '16', '--epochs', '2', '--batch_size', '4', '--num_workers', '0',
        '--cancer_types', 'A_B_UNUSED', '--result_path', str(opts.out), '--cpt_name', 'synthetic',
        '--gpu_config', str(ROOT.parents[1] / 'configs/gpu_train.yaml'), '--seed', '19',
    ])
    expected_epochs = 16 if opts.early_stop_smoke else 2
    if opts.early_stop_smoke:
        args.epochs, args.early_stopping_patience = 100, 15
    datasets = tuple(synthetic_dataset(s, n) for s, n in (('train', 13), ('valid', 9), ('test', 7)))
    updates, reports, saved_states, contexts = [], [], [], []
    original_update = PopulationPrototypeBank.update_memory_bank
    original_collect = main.update_population_memory
    original_save = torch.save
    original_pass = main.finetune_epoch

    def controlled_pass(*a, **kw):
        result = original_pass(*a, **kw)
        if opts.early_stop_smoke and not kw['training']:
            result['c-index'] = result['metric'] = .6
        return result

    def count_update(bank, *vectors):
        updates.append(len(vectors[0]))
        return original_update(bank, *vectors)

    def check_collect(model, loader, accelerator):
        report = original_collect(model, loader, accelerator)
        assert report['train_patients'] == 13 and report['complete_patients'] == 10
        assert sum(report['counts']) == 10
        bank = accelerator.unwrap_model(model).compensator
        for value in bank.buffers():
            gathered = accelerator.gather(value.reshape(1, -1))
            for rank in range(accelerator.num_processes):
                assert torch.equal(gathered[0], gathered[rank]), 'Banks diverged across ranks'
        reports.append(report)
        contexts.append((model, loader, accelerator))
        return report

    def count_save(value, *save_args, **kwargs):
        saved_states.append(1)
        return original_save(value, *save_args, **kwargs)

    with patch.object(main, 'YmlConfig', SyntheticConfig), \
         patch.object(main, 'get_dataset_tcga_sur', lambda *a, **k: datasets), \
         patch.object(PopulationPrototypeBank, 'update_memory_bank', count_update), \
         patch.object(main, 'update_population_memory', check_collect), \
         patch.object(main, 'finetune_epoch', controlled_pass), \
         patch.object(torch, 'save', count_save):
        main.main(args)

    rank = dist.get_rank() if dist.is_initialized() else 0
    assert len(reports) == expected_epochs
    if opts.single_gpu:
        assert contexts[-1][2].num_processes == 1
    assert updates == ([10] * expected_epochs if rank == 0 else [])
    assert (len(saved_states) >= 1) if rank == 0 else (not saved_states)
    if opts.early_stop_smoke:
        assert len(saved_states) == (1 if rank == 0 else 0)
    state_files = list(Path(args.result_path).glob('19/*.pth'))
    assert len(state_files) == 1
    state = torch.load(state_files[0], map_location='cpu', weights_only=True)
    assert not any(key.startswith('module.') for key in state)
    # 独立单进程前向核对聚合输出；不复用生产风险/聚合 helper 作为答案。
    model, loader, accelerator = contexts[-1]
    clone = main.load_model('NPJC', accelerator.device,
        SyntheticConfig(None).obj.modality, 16, 4, cancer_types=['A', 'B', 'UNUSED'],
        compensator='population', prototype_k=2, seed=19).to(accelerator.device).eval()
    clone.load_state_dict(state, strict=True)
    batch = next(iter(torch.utils.data.DataLoader(datasets[2], batch_size=7)))
    inputs = {k: v.to(accelerator.device) for k, v in batch.items()
              if k in ('img', 'rna', 'text', 'img_valid', 'rna_valid', 'text_valid')}
    with torch.no_grad():
        logits = clone(inputs, cancer_type=batch['cancer_type'])[0]
        expected_risk = -torch.cumprod(1 - logits.sigmoid(), dim=1).sum(1).cpu().numpy()
    # rank0 的建库异常必须传到所有卡，且旧库保持不变。
    bank = accelerator.unwrap_model(model).compensator
    before = {k: v.clone() for k, v in bank.state_dict().items()}
    def fail_update(*_args, **_kwargs):
        raise ValueError('injected rank0 KMeans failure')
    with patch.object(PopulationPrototypeBank, 'update_memory_bank', fail_update):
        try:
            original_collect(model, loader, accelerator)
        except RuntimeError as exc:
            assert 'injected rank0 KMeans failure' in str(exc)
        else:
            raise AssertionError('rank0 failure did not propagate')
    assert all(torch.equal(v, before[k]) for k, v in bank.state_dict().items())
    if rank == 0:
        import pandas as pd
        smoke_config = SyntheticConfig(None)
        smoke_dumper = main.ModelDumper(
            args.result_path, args.seed, args.cpt_name,
            smoke_config.obj.modality, args, smoke_config,
        )
        csv_path, _ = main._population_artifact_paths(smoke_dumper)
        assert csv_path.is_file()
        frame = pd.read_csv(csv_path)
        assert frame['patient_id'].tolist() == datasets[2].selected_pids
        assert frame['idx'].tolist() == list(range(7))
        np.testing.assert_allclose(frame['risk'].to_numpy(), expected_risk, atol=1e-6, rtol=1e-6)
        from sksurv.metrics import concordance_index_censored
        expected_cindex = concordance_index_censored(
            (1 - datasets[2].censorship).astype(bool), datasets[2].survival_months, expected_risk)[0]
        metrics = json.loads(next(Path(args.result_path).rglob('*_results.json')).read_text())
        assert metrics['c-index'] == expected_cindex
        result = {'status': 'passed', 'device': 'cpu' if opts.cpu else torch.cuda.get_device_name(),
                  'world_size': dist.get_world_size() if dist.is_initialized() else 1,
                  'dtype': 'float32', 'epochs': expected_epochs, 'reports': reports,
                  'early_stopping_verified': opts.early_stop_smoke,
                  'checkpoint_files': 1, 'checkpoint_writes_rank0': len(saved_states),
                  'test_patients': len(frame),
                  'global_metrics_match_single_process': True,
                  'rank0_failure_handled': True,
                  'rank0_failure_propagated': (dist.is_initialized() and dist.get_world_size() > 1),
                  'scope': 'single_gpu_smoke' if opts.single_gpu else 'distributed_smoke',
                  'peak_memory_bytes': torch.cuda.max_memory_allocated() if not opts.cpu else 0}
        output = Path(args.result_path) / 'smoke_summary.json'
        output.write_text(json.dumps(result, indent=2) + '\n')
        print('POPULATION_SMOKE_PASS=' + json.dumps(result), flush=True)
    if dist.is_initialized():
        dist.barrier()
        dist.destroy_process_group()


if __name__ == '__main__':
    run()
