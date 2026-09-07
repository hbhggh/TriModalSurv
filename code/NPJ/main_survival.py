import random
import json
import torch
from torch.utils.data import TensorDataset, DataLoader, random_split, Subset
import torch.nn.functional as F
import argparse
import sys
from transformers import BertTokenizer
from transformers import BertModel, AdamW
from transformers import get_linear_schedule_with_warmup
import torch.nn as nn
from sksurv.metrics import concordance_index_censored
from sklearn.metrics import f1_score, accuracy_score
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import os
from pathlib import Path
import matplotlib.pyplot as plt
import yaml

from accelerate import Accelerator
from torchmetrics import Precision, Recall, F1Score, Accuracy
from tqdm import tqdm
from sksurv.metrics import concordance_index_censored

from model.fusion_model import * 
from model.compensator import CAPRecall, MissingBank
from loc_utils.common_tools import *
from loc_utils_3yr.tcga_dataset import get_dataset_tcga_sur
from loc_utils_3yr.loss_func import NLLSurvLoss, PairwiseRankingLoss
from loc_utils_3yr.model_util import *
import warnings
warnings.filterwarnings('ignore')

GPU_CONFIG_DEFAULTS = {
    'batch_size': None,
    'gradient_accumulation_steps': 1,
    'num_workers': 4,
    'pin_memory': True,
    'persistent_workers': True,
    'prefetch_factor': 4,
    'non_blocking': True,
    'concurrent_runs': 1,
    'gpu_util_warmup_sec': 120,
    'gpu_util_min_percent': 50,
    'gpu_util_target_percent': 80,
    'allow_low_gpu_util': False,
    'low_gpu_util_reason': '',
}


def parsing_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch_size', type=int, default=None)
    parser.add_argument('--num_workers', type=int, default=None)
    parser.add_argument('--gpu_config', type=str, default='config/gpu_train.yaml')
    parser.add_argument('--lr', type=float, default=5e-4)
    parser.add_argument('--cpt_name', type=str, default="tcga")
    parser.add_argument('--result_path', type=str, default="out")
    parser.add_argument('--report_label_path', type=str, default="data/TCGA_9523sample_label_Censorship.csv")
    parser.add_argument('--model_config', type=str, default='model/config/multimodal_early_fusion.yml')
    parser.add_argument('--cancer_type', type=str, default='None')
    parser.add_argument('--train', default=True, type=str2bool)
    parser.add_argument('--task_type', type=str, default='surv')  # 
    parser.add_argument('--network_type', type=str, default="DEMainModalityMILMoE")  # 
    parser.add_argument('--hidden_size', type=int, default=256)  # 
    parser.add_argument('--cancer_types', default='None', type=str)
    parser.add_argument('--n_image_tokens', type=int, default=128) 
    parser.add_argument('--pretrain_path', type=str, default='', help='Path to pre-trained model checkpoint')
    parser.add_argument('--finetune_head_only', action='store_true', help='Only finetune the head; freeze the rest of the model')
    parser.add_argument('--simulate_missing_modality',type=str,default='')
    parser.add_argument('--compensator', choices=['none', 'capr', 'bank'], default='none')
    # 指挥官小修（NPJ-D 消融，2026-09-06）：mean = MainModalityMoE 去 GatedFusion 的等权均值对照臂
    parser.add_argument('--fusion_type', choices=['gate', 'mean'], default='gate')
    parser.add_argument('--modality_dropout', type=float, default=0.0)
    parser.add_argument('--consistency_lambda', type=float, default=0.1)

    return parser.parse_args(argv)


def _resolve_config_path(config_path):
    path = Path(config_path).expanduser()
    if path.is_absolute() or path.exists():
        return path
    repo_relative = Path(__file__).resolve().parent / path
    return repo_relative if repo_relative.exists() else path


def resolve_gpu_config(args, cuda_available=None):
    config_path = _resolve_config_path(args.gpu_config)
    try:
        with config_path.open('r', encoding='utf-8') as config_file:
            loaded = yaml.safe_load(config_file) or {}
    except OSError as exc:
        raise RuntimeError(f'Unable to read GPU config {config_path}: {exc}') from exc
    if not isinstance(loaded, dict):
        raise ValueError(f'GPU config must be a mapping: {config_path}')

    config = dict(GPU_CONFIG_DEFAULTS)
    config.update(loaded)
    if args.batch_size is not None:
        config['batch_size'] = args.batch_size
        config['batch_size_source'] = 'cli'
    elif config['batch_size'] is not None:
        config['batch_size_source'] = 'yaml'
    else:
        available = torch.cuda.is_available() if cuda_available is None else cuda_available
        if not available:
            raise RuntimeError(
                'batch_size is unset and CUDA is unavailable; GPU batch probing cannot run'
            )
        config['batch_size_source'] = 'probe'

    if args.num_workers is not None:
        config['num_workers'] = args.num_workers

    integer_positive = (
        'gradient_accumulation_steps',
        'prefetch_factor',
        'concurrent_runs',
    )
    for key in integer_positive:
        if not isinstance(config[key], int) or config[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if not isinstance(config['num_workers'], int) or config['num_workers'] < 0:
        raise ValueError('num_workers must be a non-negative integer')
    if config['batch_size'] is not None and (
        not isinstance(config['batch_size'], int) or config['batch_size'] < 1
    ):
        raise ValueError('batch_size must be null or a positive integer')
    for key in ('pin_memory', 'persistent_workers', 'non_blocking'):
        if not isinstance(config[key], bool):
            raise ValueError(f'{key} must be boolean')
    return config


def validate_formal_contract(config, environ=None):
    environment = os.environ if environ is None else environ
    if environment.get('FORMAL_RUN') != '1':
        return
    if config['batch_size'] == 1 and not environment.get(
        'BATCH_SIZE_BLOCKED_REASON', ''
    ).strip():
        print(
            'GPU_CONTRACT_VIOLATION: FORMAL_RUN batch_size=1 requires '
            'non-empty BATCH_SIZE_BLOCKED_REASON',
            file=sys.stderr,
        )
        raise SystemExit(3)


def build_dataloader_kwargs(config):
    kwargs = {
        'num_workers': config['num_workers'],
        'pin_memory': config['pin_memory'],
    }
    if config['num_workers'] > 0:
        kwargs['persistent_workers'] = config['persistent_workers']
        kwargs['prefetch_factor'] = config['prefetch_factor']
    return kwargs


def _print_resolved_gpu_config(config):
    print('RESOLVED_GPU_CONFIG=' + json.dumps(config, sort_keys=True))

def load_model(network_type, device, modalities, hidden_size, pred_dim, dropout_rate=0.1, mlp_ratio=4, 
               n_token=16, n_backbone=1, n_head=4, num_experts=4, topk=2,
               cancer_types=None, compensator='none', fusion_type='gate'):
    print (cancer_types,"cancer_types")
    # 指挥官小修（NPJ-D 消融，2026-09-06）：fusion_type 仅 MainModalityMoE 支持
    if fusion_type != 'gate' and network_type != 'MainModalityMoE':
        raise ValueError(
            f"fusion_type={fusion_type!r} requires network_type='MainModalityMoE', "
            f"got network_type={network_type!r}"
        )
    if compensator != 'none' and network_type not in {
        'MainModalityMoE', 'NPJC'
    }:
        raise ValueError(
            f"compensator={compensator!r} requires network_type in "
            "{'MainModalityMoE', 'NPJC'}"
        )
    compensator_modalities = tuple(
        modality for modality in ('text', 'rna') if modality in modalities
    )
    if compensator == 'none':
        compensator_module = None
    elif not compensator_modalities:
        raise ValueError("A compensator requires text and/or rna modality")
    elif compensator == 'capr':
        compensator_module = CAPRecall(
            modalities=compensator_modalities,
            dim=hidden_size,
        )
    elif compensator == 'bank':
        compensator_module = MissingBank(
            modalities=compensator_modalities,
            dim=hidden_size,
        )
    else:
        raise ValueError(f"Unsupported compensator: {compensator}")

    if network_type == 'MainModalityMoE':
        return MainModalityMoE(
            device, modalities, hidden_size, dropout_rate, pred_dim, mlp_ratio, 
            n_token, n_backbone, n_head, num_experts, topk,
            cancer_types=cancer_types, compensator=compensator_module,
            fusion_type=fusion_type
        )
    elif network_type == 'NPJC':
        return NPJC(
            device, modalities, hidden_size, dropout_rate, pred_dim, mlp_ratio,
            n_backbone, n_head, cancer_types=cancer_types,
            compensator=compensator_module,
        )
    elif network_type == 'MainModalityDeformableMoE':
        return MainModalityDeformableMoE(device, modalities, hidden_size, dropout_rate, pred_dim, mlp_ratio, n_token, n_backbone, n_head)
    else:
        raise ValueError(f"Unsupported network type: {network_type}")

def _unwrap_model(model):
    unwrapped = model
    seen = set()
    while hasattr(unwrapped, 'module') and id(unwrapped) not in seen:
        seen.add(id(unwrapped))
        unwrapped = unwrapped.module
    return unwrapped

def _model_compensator(model):
    return getattr(_unwrap_model(model), 'compensator', None)

def _append_compensator_suffix(args):
    compensator = getattr(args, 'compensator', 'none')
    if compensator == 'none':
        return
    suffix = f"_{compensator}"
    if not args.cpt_name.endswith(suffix):
        args.cpt_name += suffix
    if not args.result_path.endswith(suffix):
        args.result_path += suffix


def _unpack_survival_batch(dbatch, device, non_blocking=False):
    dbatch = dict(dbatch)
    survival_months = dbatch.pop('survival_months').to(
        device, non_blocking=non_blocking
    )
    survival_months_bin = dbatch.pop('survival_months_bin').to(
        device, non_blocking=non_blocking
    )
    censorship = dbatch.pop('censorship').to(
        device, non_blocking=non_blocking
    )
    dbatch.pop('label', None)
    patient_id = dbatch.pop('patient_id', None)
    cancer_type = dbatch.pop('cancer_type')
    idx = dbatch.pop('idx', None)
    inputs = {
        key: value.to(
            device,
            dtype=torch.float,
            non_blocking=non_blocking,
        )
        for key, value in dbatch.items()
    }
    return (
        inputs,
        survival_months,
        survival_months_bin,
        censorship,
        cancer_type,
        idx,
        patient_id,
    )


def _forward_survival_model(model, inputs, cancer_type, training):
    if (
        hasattr(model, 'module')
        and model.module.__class__.__name__ == 'CrossAttnFusionWithLearnableMissing'
    ):
        return model(inputs, training=training)
    if (
        hasattr(model, 'module')
        and 'cancer_type' in model.module.forward.__code__.co_varnames
    ):
        return model(inputs, cancer_type=cancer_type)
    return model(inputs)


def _batch_shape_summary(sample):
    if not isinstance(sample, dict):
        return {'sample': type(sample).__name__}
    return {
        key: list(value.shape) if torch.is_tensor(value) else type(value).__name__
        for key, value in sample.items()
    }


def _is_cuda_oom(exc):
    return isinstance(exc, RuntimeError) and 'out of memory' in str(exc).lower()


def probe_batch_size(
    train_dataset,
    model,
    criterion,
    device,
    consistency_lambda=0.0,
    non_blocking=True,
    candidates=(32, 64, 128, 256),
    steps=2,
):
    if len(train_dataset) == 0:
        raise RuntimeError('Batch probe cannot run on an empty train dataset')

    original_training = model.training
    cpu_rng_state = torch.get_rng_state()
    cuda_rng_state = torch.cuda.get_rng_state_all()
    buffer_state = {
        name: buffer.detach().clone() for name, buffer in model.named_buffers()
    }
    selected = None
    selected_peak_mib = 0.0
    model.train(True)
    try:
        for candidate in candidates:
            repeated_indices = [
                index % len(train_dataset) for index in range(candidate * steps)
            ]
            probe_loader = DataLoader(
                Subset(train_dataset, repeated_indices),
                batch_size=candidate,
                shuffle=False,
                num_workers=0,
                pin_memory=False,
            )
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats(device)
            try:
                for step_index, dbatch in enumerate(probe_loader):
                    if step_index >= steps:
                        break
                    (
                        inputs,
                        survival_months,
                        survival_months_bin,
                        censorship,
                        cancer_type,
                        _,
                        _,
                    ) = _unpack_survival_batch(dbatch, device, non_blocking)
                    if _model_compensator(model) is not None:
                        inputs['bin_labels'] = survival_months_bin
                    outputs = _forward_survival_model(
                        model, inputs, cancer_type, training=True
                    )
                    hazard = outputs[0] if isinstance(outputs, tuple) else outputs
                    loss = criterion(
                        hazard,
                        survival_months_bin,
                        survival_months,
                        censorship,
                    )
                    if (
                        consistency_lambda != 0
                        and isinstance(outputs, tuple)
                        and len(outputs) > 2
                    ):
                        consistency = outputs[2]
                        if consistency.ndim > 0:
                            consistency = consistency.mean()
                        loss = loss + consistency_lambda * consistency
                    loss.backward()
                    model.zero_grad(set_to_none=True)
                selected = candidate
                selected_peak_mib = (
                    torch.cuda.max_memory_allocated(device) / (1024 * 1024)
                )
            except RuntimeError as exc:
                model.zero_grad(set_to_none=True)
                torch.cuda.empty_cache()
                if not _is_cuda_oom(exc):
                    raise
                if selected is None:
                    shapes = _batch_shape_summary(train_dataset[0])
                    print(
                        'BATCH_PROBE_ERROR: batch_size=32 OOM; '
                        f'sample_shapes={json.dumps(shapes, sort_keys=True)}',
                        file=sys.stderr,
                    )
                    raise RuntimeError('Batch probe failed: batch_size=32 OOM') from exc
                break
            finally:
                torch.cuda.empty_cache()
    finally:
        model.train(original_training)
        torch.set_rng_state(cpu_rng_state)
        torch.cuda.set_rng_state_all(cuda_rng_state)
        with torch.no_grad():
            for name, buffer in model.named_buffers():
                buffer.copy_(buffer_state[name])
        model.zero_grad(set_to_none=True)
        torch.cuda.empty_cache()

    print(
        f'BATCH_PROBE_RESULT={selected} PEAK_MEM={selected_peak_mib:.1f}MiB'
    )
    return selected

def plot_metrics(train_losses, val_losses, val_metrics, save_dir=None):
    epochs = np.arange(1, len(train_losses) + 1)
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(epochs, train_losses, label='Train Loss')
    plt.plot(epochs, val_losses, label='Val Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Loss Curve')
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(epochs, val_metrics, label='Validation C-Index')
    best_idx = np.argmax(val_metrics)
    plt.scatter(epochs[best_idx], val_metrics[best_idx], color='red')
    plt.text(epochs[best_idx], val_metrics[best_idx], f'Best {val_metrics[best_idx]:.2f}', ha='center')
    plt.xlabel('Epoch')
    plt.ylabel('C-Index')
    plt.title('Validation Metric')
    plt.legend()

    plt.tight_layout()
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        plt.savefig(os.path.join(save_dir, 'training_curves.png'))
        print(f"✅ Saved training curves at {save_dir}/training_curves.png")
    plt.close()

def finetune_epoch(
    model, 
    criterion, 
    optimizer, 
    dataloader, 
    epoch, 
    training=True, 
    device='cpu', 
    accelerator=None, 
    task_type='surv',
    consistency_lambda=0.0,
    gradient_accumulation_steps=1,
    non_blocking=False,
):
    if gradient_accumulation_steps < 1:
        raise ValueError('gradient_accumulation_steps must be >= 1')
    model.train(training)
    pbar = tqdm(dataloader, leave=False)
    losses = []
    all_hazards = []
    all_times = []
    all_censors = []

    if training:
        optimizer.zero_grad()
    total_batches = len(dataloader)
    for batch_index, dbatch in enumerate(pbar):
        (
            x,
            survival_months,
            survival_months_bin,
            censorship,
            cancer_type,
            _,
            _,
        ) = _unpack_survival_batch(dbatch, device, non_blocking)
        if _model_compensator(model) is not None:
            x['bin_labels'] = survival_months_bin

        with torch.set_grad_enabled(training):
            outputs = _forward_survival_model(model, x, cancer_type, training)
            hazard = outputs[0] if isinstance(outputs, tuple) else outputs
            surv = torch.cumprod(1 - hazard, dim=1)
            risk = -torch.sum(surv, dim=1)  # [B]
            # loss_rank_criterion = PairwiseRankingLoss()
            # loss_rank = loss_rank_criterion(risk, survival_months, censorship)
            loss_nll = criterion(hazard, survival_months_bin, survival_months, censorship)
            # loss = loss_nll + 0.2 * loss_rank
            loss = criterion(hazard, survival_months_bin, survival_months, censorship)
            if (
                training
                and consistency_lambda != 0
                and isinstance(outputs, tuple)
                and len(outputs) > 2
            ):
                consistency = outputs[2]
                if consistency.ndim > 0:
                    consistency = consistency.mean()
                loss = loss + consistency_lambda * consistency
            if training:
                backward_loss = (
                    loss
                    if gradient_accumulation_steps == 1
                    else loss / gradient_accumulation_steps
                )
                accelerator.backward(backward_loss)
                should_step = (
                    (batch_index + 1) % gradient_accumulation_steps == 0
                    or batch_index + 1 == total_batches
                )
                if should_step:
                    optimizer.step()
                    optimizer.zero_grad()

        losses.append(loss.detach())
        all_hazards.append(hazard.detach())
        all_times.append(survival_months.detach())
        all_censors.append(censorship.detach())

    loss_values = torch.stack(losses).cpu().tolist()
    all_hazards = torch.cat(all_hazards).cpu()
    all_times = torch.cat(all_times).cpu()
    all_censors = torch.cat(all_censors).cpu()

    survival = torch.cumprod(1 - all_hazards, dim=1)
    risk = -torch.sum(survival, dim=1).numpy()

    c_index = concordance_index_censored(
        (1 - all_censors.numpy()).astype(bool),
        all_times.numpy(),
        risk
    )[0]

    return {'loss': np.mean(loss_values), 'c-index': c_index, 'metric': c_index}


def prediction(model, 
               criterion, 
               dataloader, 
               epoch, 
               training=False, 
               device='cpu', 
               accelerator=None, 
               task_type='surv',
               non_blocking=False):
    model.train(training)
    pbar = tqdm(dataloader)
    losses = []
    all_hazards = []
    all_times = []
    all_censors = []
    all_cancer_types = []
    all_indices = []

    all_patient_ids = []

    for dbatch in pbar:
        (
            x,
            survival_months,
            survival_months_bin,
            censorship,
            cancer_type,
            idx,
            patient_id,
        ) = _unpack_survival_batch(dbatch, device, non_blocking)
        if patient_id is None:
            patient_id = [None] * len(idx)

        with torch.no_grad():
            outputs = _forward_survival_model(model, x, cancer_type, training)
            hazard = outputs[0] if isinstance(outputs, tuple) else outputs
        loss = criterion(hazard, survival_months_bin, survival_months, censorship)

        losses.append(loss.detach())
        all_hazards.append(hazard.detach())
        all_times.append(survival_months.detach())
        all_censors.append(censorship.detach())
        all_cancer_types.extend(cancer_type)
        all_indices.append(idx.detach())
        if isinstance(patient_id, list):
            all_patient_ids.extend(patient_id)
        else:
            all_patient_ids.extend([p for p in patient_id])

    loss_values = torch.stack(losses).cpu().tolist()
    all_hazards = torch.cat(all_hazards).cpu()
    all_times = torch.cat(all_times).cpu()
    all_censors = torch.cat(all_censors).cpu()
    all_indices = torch.cat(all_indices).cpu().tolist()

    survival = torch.cumprod(1 - all_hazards, dim=1)
    risk = -torch.sum(survival, dim=1).numpy()

    report_metrics = {
        'loss': np.mean(loss_values),
        'c-index': concordance_index_censored(
            (1 - all_censors.numpy()).astype(bool),
            all_times.numpy(),
            risk
        )[0],
        'metric': None  # To be overwritten below
    }
    report_metrics['metric'] = report_metrics['c-index']

    cancer_spc_dict = {}
    for idx, cancer in zip(all_indices, all_cancer_types):
        cancer_spc_dict.setdefault(cancer, []).append(idx)

    for cancer_type, idx_list in cancer_spc_dict.items():
        hazards_cancer = all_hazards[idx_list]
        survival_cancer = torch.cumprod(1 - hazards_cancer, dim=1)
        risk_cancer = -torch.sum(survival_cancer, dim=1).numpy()

        censorships_cancer = all_censors[idx_list].numpy()
        event_times_cancer = all_times[idx_list].numpy()

        c_index_cancer = concordance_index_censored(
            (1 - censorships_cancer).astype(bool),
            event_times_cancer,
            risk_cancer
        )[0]

        report_metrics[f"{cancer_type}_c-index"] = c_index_cancer

    return report_metrics, {
        'risk': risk,
        'time': all_times.numpy(),
        'censorship': all_censors.numpy(),
        'cancer_type': np.array(all_cancer_types),
        'idx': np.array(all_indices),
        'patient_id': np.array(all_patient_ids)
    }




def main(args):
    _append_compensator_suffix(args)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    gpu_config = resolve_gpu_config(args)
    model_config = YmlConfig(args.model_config)

    # 解析modalities
    modality_config = {k: model_config.parse_to_modality(v) for k, v in model_config.obj.modality.items()}

    # 读取数据集
    simulate_missing_modality = args.simulate_missing_modality if args.simulate_missing_modality != '' else None
    train_dataset, valid_dataset, test_dataset = get_dataset_tcga_sur(
        args.report_label_path,
        modalities=modality_config, 
        task_type=model_config.obj.task_type,
        img_select=model_config.obj.img_select,
        n_image_tokens=args.n_image_tokens,
        cancer_types=args.cancer_types,
        network_type=args.network_type,
        simulate_missing_modality=simulate_missing_modality,
        modality_dropout=getattr(args, 'modality_dropout', 0.0),
        seed=args.seed
    )

    # 初始化模型
    model = load_model(
        network_type=args.network_type,
        device=device,
        modalities=modality_config,
        hidden_size=args.hidden_size,
        pred_dim=model_config.obj.network.pred_dim,
        n_token=model_config.obj.network.n_token,
        cancer_types=args.cancer_types.split('_') if args.cancer_types != 'None' else None,
        compensator=getattr(args, 'compensator', 'none'),
        fusion_type=args.fusion_type
    )
    if torch.cuda.device_count() > 1:
        print(f"✅ Using {torch.cuda.device_count()} GPUs for training (DataParallel)")
    model = nn.DataParallel(model)
    model.to(device)

    criterion = NLLSurvLoss(alpha=0.0, eps=1e-7).to(device)
    if gpu_config['batch_size'] is None:
        gpu_config['batch_size'] = probe_batch_size(
            train_dataset,
            model,
            criterion,
            device,
            consistency_lambda=getattr(args, 'consistency_lambda', 0.1),
            non_blocking=gpu_config['non_blocking'],
        )

    args.batch_size = gpu_config['batch_size']
    args.num_workers = gpu_config['num_workers']
    _print_resolved_gpu_config(gpu_config)
    validate_formal_contract(gpu_config)

    loader_kwargs = build_dataloader_kwargs(gpu_config)
    train_loader = DataLoader(
        train_dataset,
        shuffle=True,
        batch_size=args.batch_size,
        **loader_kwargs,
    )
    valid_loader = DataLoader(
        valid_dataset,
        shuffle=False,
        batch_size=args.batch_size,
        **loader_kwargs,
    )
    test_loader = DataLoader(
        test_dataset,
        shuffle=False,
        batch_size=args.batch_size,
        **loader_kwargs,
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1)
    accelerator = Accelerator(mixed_precision='bf16')

    # Accelerator包装
    model, optimizer, train_loader, valid_loader, test_loader = accelerator.prepare(
        model, optimizer, train_loader, valid_loader, test_loader
    )

    model_dumper = ModelDumper(args.result_path, args.seed, args.cpt_name, model_config.obj.modality, args, model_config)

    best_metric = 0
    train_losses, val_losses, val_metrics = [], [], []

    # ========== 训练 ==========
    if args.train:
        for epoch in range(args.epochs):
            train_metric = finetune_epoch(
                model,
                criterion,
                optimizer,
                train_loader,
                epoch,
                training=True,
                device=device,
                accelerator=accelerator,
                task_type=args.task_type,
                consistency_lambda=getattr(args, 'consistency_lambda', 0.1),
                gradient_accumulation_steps=gpu_config['gradient_accumulation_steps'],
                non_blocking=gpu_config['non_blocking'],
            )
            # print(f"[Train] Epoch {epoch}: {train_metric}")

            valid_metric = finetune_epoch(
                model,
                criterion,
                optimizer,
                valid_loader,
                epoch,
                training=False,
                device=device,
                accelerator=accelerator,
                task_type=args.task_type,
                consistency_lambda=getattr(args, 'consistency_lambda', 0.1),
                gradient_accumulation_steps=gpu_config['gradient_accumulation_steps'],
                non_blocking=gpu_config['non_blocking'],
            )
            # print(f"[Valid] Epoch {epoch}: {valid_metric}")

            train_losses.append(train_metric['loss'])
            val_losses.append(valid_metric['loss'])
            val_metrics.append(valid_metric['c-index'])

            if valid_metric['metric'] > best_metric:
                best_metric = valid_metric['metric']
                model_dumper.dump(model)

        # 绘制曲线
        plot_metrics(train_losses, val_losses, val_metrics, save_dir='./plots')

    # ========== 测试 ==========
    model.load_state_dict(torch.load(model_dumper.model_path))
    test_metric, test_pred_info = prediction(
        model,
        criterion,
        test_loader,
        epoch=0,
        training=False,
        device=device,
        accelerator=accelerator,
        task_type=args.task_type,
        non_blocking=gpu_config['non_blocking'],
    )

    # 保存为csv
    network = args.network_type
    cancer_types_str = args.cancer_types.replace("_", "-") if args.cancer_types != "None" else "all"
    save_pred_csv = os.path.join(
        args.result_path, 
        f"test_pred_and_label_{network}_{cancer_types_str}.csv"
    )
    df_save = pd.DataFrame({
        'patient_id': test_pred_info['patient_id'],
        'idx': test_pred_info['idx'],
        'cancer_type': test_pred_info['cancer_type'],
        'risk': test_pred_info['risk'],
        'survival_time': test_pred_info['time'],
        'censorship': test_pred_info['censorship']
    })
    df_save.to_csv(save_pred_csv, index=False)
    print(f"✅ Test prediction and label saved at {save_pred_csv}")

    # 打印并整理dump
    dump_dict = {}
    for kk in test_metric:
        if kk != "metric":
            dump_dict[kk] = test_metric[kk]
            print(f"{kk}: {dump_dict[kk]:.2f}")

    # model_dumper.dump_json(test_metric)
    model_dumper.dump_results(dump_dict)



if __name__ == '__main__':
    args = parsing_args()
    print("Training Arguments:", args)
    set_seed(args.seed)
    main(args)
