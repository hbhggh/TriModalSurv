"""I02 协调入口：保留每轮训练→建库→验证→严格早停/重载。"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from accelerate import Accelerator
from accelerate.utils import DistributedDataParallelKwargs
from sksurv.metrics import concordance_index_censored
from trimodalsurv.training import runtime as shared
from trimodalsurv.training.common_tools import set_seed, str2bool
from trimodalsurv.data.tcga_dataset import get_dataset_tcga_sur
from trimodalsurv.training.loss_func import NLLSurvLoss
from .model import PopulationPrototypeBank
from .runtime import (validate_population_splits, make_population_loader,
    update_population_memory, ordered_patient_outputs, main_process_call,
    save_population_checkpoint, load_population_checkpoint, PopulationEarlyStopping)
YmlConfig = shared.YmlConfig
ModelDumper = shared.ModelDumper
resolve_gpu_config = shared.resolve_gpu_config
build_dataloader_kwargs = shared.build_dataloader_kwargs
validate_formal_contract = shared.validate_formal_contract
_print_resolved_gpu_config = shared._print_resolved_gpu_config
_unpack_survival_batch = shared._unpack_survival_batch
_model_compensator = shared._model_compensator
probe_batch_size = shared.probe_batch_size
plot_metrics = shared.plot_metrics

def load_model(network_type, device, modalities, hidden_size, pred_dim,
               dropout_rate=0.1, mlp_ratio=4, n_token=16, n_backbone=1,
               n_head=4, num_experts=4, topk=2, cancer_types=None,
               compensator='none', fusion_type='gate', prototype_k=None, seed=123):
    if compensator == 'population':
        if network_type != 'NPJC' or not {'img', 'rna', 'text'}.issubset(modalities):
            raise ValueError('population requires NPJC with img, rna and text')
        from trimodalsurv.models.npjc import NPJC
        bank = PopulationPrototypeBank(prototype_k, hidden_size, seed)
        return NPJC(device, modalities, hidden_size, dropout_rate, pred_dim,
                    mlp_ratio, n_backbone, n_head, cancer_types=cancer_types,
                    compensator=bank)
    return shared.load_model(network_type, device, modalities, hidden_size,
        pred_dim, dropout_rate, mlp_ratio, n_token, n_backbone, n_head,
        num_experts, topk, cancer_types, compensator, fusion_type)

def finetune_epoch(model, criterion, optimizer, dataloader, epoch, training=True,
                   device='cpu', accelerator=None, task_type='surv',
                   consistency_lambda=0., gradient_accumulation_steps=1,
                   non_blocking=False):
    if gradient_accumulation_steps < 1:
        raise ValueError('gradient_accumulation_steps must be >= 1')
    return _population_pass(model, criterion, optimizer, dataloader, training,
        device, accelerator, gradient_accumulation_steps, non_blocking)

def prediction(model, criterion, dataloader, epoch=0, training=False,
               device='cpu', accelerator=None, task_type='surv', non_blocking=False):
    return _population_pass(model, criterion, None, dataloader, False,
        device, accelerator, non_blocking=non_blocking, return_predictions=True)

def parsing_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None)
    parser.add_argument('--run_record_root', default=None)
    parser.add_argument('--dry_run', action='store_true')
    parser.add_argument('--bin_mode', choices=['author'], required=True)
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--early-stopping-patience', type=int, default=0,
                        help='population 验证 C-index 早停耐心值；0 为禁用')
    parser.add_argument('--batch_size', type=int, default=None)
    parser.add_argument('--num_workers', type=int, default=None)
    parser.add_argument('--gpu_config', type=str, default=str(Path(__file__).resolve().parents[2] / 'configs/gpu_train.yaml'))
    parser.add_argument('--lr', type=float, default=5e-4)
    parser.add_argument('--cpt_name', type=str, default="tcga")
    parser.add_argument('--result_path', type=str, default=str(Path(__file__).resolve().parents[2] / 'out'))
    parser.add_argument('--report_label_path', type=str, default=str(Path(__file__).resolve().parents[2] / 'data/TCGA_9523sample_label_Censorship.csv'))
    parser.add_argument('--model_config', type=str, default=str(Path(__file__).resolve().parents[2] / 'configs/models/surv_multimodal_mainmoe_uni2.yml'))
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
    parser.add_argument('--compensator', choices=['none', 'capr', 'bank', 'population'], default='none')
    parser.add_argument('--prototype-k', type=int, default=None, help='跨患者人群簇数，仅 population 使用，无默认值')
    # 指挥官小修（NPJ-D 消融，2026-09-06）：mean = MainModalityMoE 去 GatedFusion 的等权均值对照臂
    parser.add_argument('--fusion_type', choices=['gate', 'mean'], default='gate')
    parser.add_argument('--modality_dropout', type=float, default=0.0)
    parser.add_argument('--consistency_lambda', type=float, default=0.1)

    preliminary = argparse.ArgumentParser(add_help=False)
    preliminary.add_argument('--config')
    config_args, _ = preliminary.parse_known_args(argv)
    if config_args.config is not None:
        from trimodalsurv.config import read_config
        content = read_config(config_args.config)
        if 'runtime' in content:
            extra = set(content) - {'experiment', 'provenance', 'runtime'}
            if extra:
                raise ValueError(f'未知实验配置字段: {sorted(extra)}；生效参数仅放 runtime')
        overrides = content.get('runtime', content)
        unknown = set(overrides) - {a.dest for a in parser._actions}
        if unknown:
            raise ValueError(f'未知运行配置字段: {sorted(unknown)}')
        parser.set_defaults(**overrides)
        if overrides.get('bin_mode') == 'author':
            next(a for a in parser._actions if a.dest == 'bin_mode').required = False
    args = parser.parse_args(argv)
    if args.bin_mode != 'author':
        parser.error('I02 requires explicit author bin_mode')
    for name in ('config', 'gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path', 'run_record_root'):
        value = getattr(args, name, None)
        if value:
            setattr(args, name, str(Path(value).expanduser().resolve()))
    for name in ('gpu_config', 'model_config'):
        value = getattr(args, name)
        if not value or not Path(value).is_file():
            raise ValueError(f'缺少 {name}: {value}；运行入口须使用完整 repo checkout，或显式提供配置路径')
    if args.early_stopping_patience < 0:
        parser.error('--early-stopping-patience must be nonnegative')
    if args.early_stopping_patience and (args.compensator != 'population' or args.task_type != 'surv'):
        parser.error('--early-stopping-patience requires population survival')
    if args.compensator == 'population':
        if args.network_type != 'NPJC':
            parser.error('population requires --network_type NPJC')
        if args.prototype_k is None or args.prototype_k < 1:
            parser.error('population requires a positive --prototype-k')
    elif args.prototype_k is not None:
        parser.error('--prototype-k requires --compensator population')
    return args


def _append_compensator_suffix(args):
    compensator = getattr(args, 'compensator', 'none')
    if compensator == 'none':
        return
    suffix = f"_{compensator}"
    if compensator == 'population':
        if getattr(args, 'prototype_k', None) is None or args.prototype_k < 1:
            raise ValueError('population requires a positive prototype_k')
        suffix += f'_k{args.prototype_k}'
    if not args.cpt_name.endswith(suffix):
        args.cpt_name += suffix
    if not args.result_path.endswith(suffix):
        args.result_path += suffix


def _forward_survival_model(model, inputs, cancer_type, training):
    if isinstance(_model_compensator(model), PopulationPrototypeBank):
        return model(inputs, cancer_type=cancer_type)
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


def _population_artifact_paths(model_dumper):
    """Derive population-only CSV and plot paths from the full run identity."""
    task_path = Path(model_dumper.task_path_str)
    csv_path = task_path.parent / f'test_pred_and_label_{task_path.name}.csv'
    plots_path = task_path.parent / f'{task_path.name}_plots'
    return csv_path, plots_path


def _population_pass(model, criterion, optimizer, dataloader, training, device,
                     accelerator, gradient_accumulation_steps=1, non_blocking=False,
                     return_predictions=False):
    """population 专用全局指标路径；旧实验计算方式不在此修改。"""
    model.train(training)
    pieces = []
    if training:
        optimizer.zero_grad()
    for batch_index, batch in enumerate(dataloader):
        x, times, bins, censors, cancers, idx, _ = _unpack_survival_batch(batch, device, non_blocking)
        with torch.set_grad_enabled(training):
            logits = _forward_survival_model(model, x, cancers, training)[0]
            if training:
                loss = criterion(logits, bins, times, censors)
                accelerator.backward(loss / gradient_accumulation_steps)
                if ((batch_index + 1) % gradient_accumulation_steps == 0
                        or batch_index + 1 == len(dataloader)):
                    optimizer.step()
                    optimizer.zero_grad()
        pieces.append(accelerator.gather({
            'idx': idx.to(device), 'logits': logits.detach(), 'times': times,
            'bins': bins, 'censors': censors,
        }))
    full = ordered_patient_outputs(pieces, len(dataloader.dataset))
    with torch.no_grad():
        loss = criterion(full['logits'], full['bins'], full['times'], full['censors']).item()
        risk = -torch.cumprod(1 - full['logits'].sigmoid(), dim=1).sum(dim=1).cpu().numpy()
    times, censors = full['times'].cpu().numpy(), full['censors'].cpu().numpy()
    c_index = concordance_index_censored((1 - censors).astype(bool), times, risk)[0]
    metrics = {'loss': loss, 'c-index': c_index, 'metric': c_index}
    if not np.isfinite(c_index) or not np.isfinite(loss):
        raise ValueError('Population loss and metric must be finite')
    if not return_predictions:
        return metrics
    dataset = dataloader.dataset
    indices = full['idx'].cpu().numpy()
    cancers = np.array([dataset.filter_cancer_type[i] for i in indices])
    for cancer in sorted(set(cancers)):
        mask = cancers == cancer
        metrics[f'{cancer}_c-index'] = concordance_index_censored(
            (1 - censors[mask]).astype(bool), times[mask], risk[mask])[0]
    return metrics, {'risk': risk, 'time': times, 'censorship': censors,
                     'cancer_type': cancers, 'idx': indices,
                     'patient_id': np.array([dataset.selected_pids[i] for i in indices])}


def main(args):
    if args.compensator != 'population':
        raise ValueError('I02 train requires population')
    if getattr(args, 'dry_run', False):
        from trimodalsurv.config import actual_model_spec
        cfg = YmlConfig(args.model_config)
        modalities = {k: cfg.parse_to_modality(v) for k, v in cfg.obj.modality.items()}
        model = load_model(args.network_type, 'cpu', modalities, args.hidden_size,
            cfg.obj.network.pred_dim, n_token=cfg.obj.network.n_token,
            cancer_types=args.cancer_types.split('_') if args.cancer_types != 'None' else None,
            compensator=args.compensator, prototype_k=args.prototype_k, seed=args.seed)
        print(json.dumps({'runtime': vars(args), 'model': actual_model_spec(model)}, sort_keys=True))
        return
    _append_compensator_suffix(args)
    population = getattr(args, 'compensator', 'none') == 'population'
    accelerator = None
    if population:
        accelerator = Accelerator(mixed_precision='no', kwargs_handlers=[
            DistributedDataParallelKwargs(find_unused_parameters=True)])
    device = accelerator.device if population else torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    gpu_config = resolve_gpu_config(args)
    model_config = YmlConfig(args.model_config)
    model_dumper = ModelDumper(args.result_path, args.seed, args.cpt_name, model_config.obj.modality, args, model_config)
    from trimodalsurv.config import preflight_training_outputs
    preflight_training_outputs(model_dumper.task_path_str, model_dumper.model_path,
        training=args.train, sidecar=model_dumper.task_path_str + '.resolved.json')

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
        seed=args.seed, bin_mode=args.bin_mode
    )
    if population:
        validate_population_splits(train_dataset, valid_dataset, test_dataset)

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
        fusion_type=args.fusion_type,
        prototype_k=getattr(args, 'prototype_k', None), seed=args.seed,
    )
    if not population and torch.cuda.device_count() > 1:
        print(f"✅ Using {torch.cuda.device_count()} GPUs for training (DataParallel)")
    if not population:
        model = nn.DataParallel(model)
    model.to(device)

    criterion = NLLSurvLoss(alpha=0.0, eps=1e-7).to(device)
    if gpu_config['batch_size'] is None:
        if population:
            raise ValueError('population requires an explicit per-rank batch_size; no distributed auto-probe')
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
    if not population:
        accelerator = Accelerator(mixed_precision='bf16')

    # Accelerator包装
    model, optimizer, train_loader, valid_loader, test_loader = accelerator.prepare(
        model, optimizer, train_loader, valid_loader, test_loader
    )
    bank_loader = None
    if population and args.train:
        bank_loader = accelerator.prepare(make_population_loader(
            train_dataset, args.batch_size, loader_kwargs, seed=args.seed))


    from trimodalsurv.config import (resolved_config, write_resolved_config, file_fingerprint,
        runtime_source_fingerprints, run_record_root, start_run_record, finalize_run_record)
    target = Path(model_dumper.task_path_str + '.resolved.json')
    run_record = None
    def persist_configuration():
        nonlocal run_record
        target.parent.mkdir(parents=True, exist_ok=True)
        unwrapped = accelerator.unwrap_model(model)
        payload = resolved_config(args, unwrapped,
            inputs=[file_fingerprint(args.report_label_path), file_fingerprint(args.model_config), file_fingerprint(args.gpu_config)],
            checkpoints=[], sources=runtime_source_fingerprints(args, experiment_dir=Path(__file__).parent))
        payload['effective_gpu_config'] = gpu_config
        payload['execution'] = {'precision': 'float32', 'optimizer': 'Adam', 'weight_decay': 1,
                                'prototype_k': args.prototype_k, 'train_compensation': False}
        payload['historical_training'] = {'status': '本次实际运行配置；不推填历史训练参数'}
        write_resolved_config(target, payload)
        run_record = start_run_record(run_record_root(args, experiment_dir=Path(__file__).parent),
            payload, checkpoint_path=model_dumper.model_path,
            modalities={key: {'path': str(Path(value.path).resolve()), 'feature_dim': value.feature_dim}
                        for key, value in modality_config.items()})
    main_process_call(accelerator, persist_configuration)
    best_metric = float('-inf') if population else 0
    early_stopper = PopulationEarlyStopping(getattr(args, 'early_stopping_patience', 0)) if population else None
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
            if population:
                bank_report = update_population_memory(model, bank_loader, accelerator)
                accelerator.print('POPULATION_BANK=' + json.dumps(bank_report, sort_keys=True))

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

            if population:
                best_metric = save_population_checkpoint(
                    model, model_dumper.model_path, valid_metric['c-index'], best_metric, accelerator)
                # rank 0 产生停止信号并广播，所有 rank 同轮退出后严格重载最佳库/模型。
                stop_report = main_process_call(
                    accelerator, lambda: early_stopper.update(valid_metric['c-index'], epoch))
                accelerator.print('POPULATION_EARLY_STOPPING=' + json.dumps(stop_report, sort_keys=True))
                if stop_report['should_stop']:
                    break
            elif valid_metric['metric'] > best_metric:
                best_metric = valid_metric['metric']
                model_dumper.dump(model)

        # 绘制曲线
        if population:
            _, plots_path = _population_artifact_paths(model_dumper)
            def save_population_plots():
                plots_path.mkdir(exist_ok=False)
                plot_metrics(train_losses, val_losses, val_metrics, save_dir=str(plots_path))
            main_process_call(accelerator, save_population_plots)
        else:
            plot_metrics(train_losses, val_losses, val_metrics, save_dir='./plots')

    # ========== 测试 ==========
    if population:
        load_population_checkpoint(model, model_dumper.model_path, accelerator)
    else:
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
    if population:
        def save_population_results():
            output, _ = _population_artifact_paths(model_dumper)
            pd.DataFrame({
                'patient_id': test_pred_info['patient_id'], 'idx': test_pred_info['idx'],
                'cancer_type': test_pred_info['cancer_type'], 'risk': test_pred_info['risk'],
                'survival_time': test_pred_info['time'], 'censorship': test_pred_info['censorship'],
            }).to_csv(output, index=False, mode='x')
            model_dumper.dump_results({k: v for k, v in test_metric.items() if k != 'metric'})
            finalize_run_record(run_record, checkpoint_path=model_dumper.model_path,
                artifacts=[output, model_dumper.task_path_str + '_results.json'])
        main_process_call(accelerator, save_population_results)
        return


if __name__ == '__main__':
    args = parsing_args()
    set_seed(args.seed)
    main(args)
