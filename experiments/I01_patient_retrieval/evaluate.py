#!/usr/bin/env python3
"""NPJ-C 固定患者库三臂评测；由 eval_missing.py --patient-fixed 调用。

只读既有 pickle 缓存（仅限可信的本项目缓存），绝不触发 dataset 冷构建。
默认仅 preflight；smoke 不产 C-index；formal 必须提供人工互审记录。
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import io
import json
import pickle
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
from experiments.I01_patient_retrieval.model import FixedPatientBank, PROTOCOL_ID, _numeric, validate_splits, valid_row_mask
from trimodalsurv.evaluation.common import file_sha256, grid_sha256, masked_modalities, extract_state_dict, strip_data_parallel_prefix, _atomic_json_dump, dual_risk_from_logits
from trimodalsurv.config import resolve_config, actual_model_spec, resolved_config, write_resolved_config

ARMS = ('m0real', 'm1', 'retrieval')
CANCERS = ('BLCA', 'BRCA', 'LGG', 'LUAD', 'UCEC')
SEEDS = (123, 132, 213, 231, 321)
GRIDS = ('none', 'rna_100', 'text_100', 'both_100')
SHAPES = {'img': (128, 1536), 'text': (200, 768), 'rna': (2048, 256)}
MODEL_SPEC = {'network_type': 'NPJC', 'compensator': 'none', 'hidden_size': 256,
              'pred_dim': 4, 'dropout_rate': 0.1, 'mlp_ratio': 4, 'n_backbone': 1, 'n_head': 4,
              'modality_order': ['img', 'text', 'rna']}


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def write_json_new(path, value):
    # 排他创建：中途失败的目录保留作诊断，禁止复用或覆盖。
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def read_labels(path, cancer):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'patient_id', 'cancer_type', 'split', 'survival_months', 'censorship'}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError('label CSV 缺少必要字段')
        rows = list(reader)
    ids = [row['patient_id'] for row in rows]
    if len(ids) != len(set(ids)) or any(not pid.strip() for pid in ids):
        raise ValueError('label CSV 患者 ID 重复或为空')
    selected = [row for row in rows if row['cancer_type'] == cancer]
    if any(row['split'] not in ('train', 'valid', 'test') for row in selected):
        raise ValueError(f'{cancer}: 非法 split')
    splits = validate_splits({split: [r['patient_id'] for r in selected if r['split'] == split]
                             for split in ('train', 'valid', 'test')})
    if not all(splits.values()):
        raise ValueError(f'{cancer}: 空 split')
    return splits, [r for r in selected if r['split'] == 'test']


def validate_manifest(path, cancer, test_ids):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'patient_id', 'cancer'}.issubset(reader.fieldnames or ()):
            raise ValueError('manifest 缺少 patient_id/cancer')
        rows = list(reader)
    ids = [row['patient_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('manifest 患者重复')
    available = {row['patient_id'] for row in rows if row['cancer'] == cancer}
    if not set(test_ids).issubset(available):
        raise ValueError(f'{cancer}: manifest 未覆盖全部 test 患者')


def load_cache(cache_root, cancer, split, patient_ids):
    result, hashes = {}, {}
    allowed = set(patient_ids)
    for mm in SHAPES:
        path = cache_root / f'{mm}_sur_{split}_all_{cancer}.pkl'
        if not path.is_file():
            raise FileNotFoundError(f'缺少冻结缓存，禁止冷重建: {path}')
        hashes[path.name] = file_sha256(path)
        with path.open('rb') as handle:
            data = pickle.load(handle)
        if not isinstance(data, dict) or not set(data).issubset(allowed):
            raise ValueError(f'{path}: 缓存 schema 或 split 交叉错误')
        result[mm] = data
    return result, hashes


class CachedPatients:
    """显式保留全部 test 患者，不沿用旧 dataset 的缺 WSI 静默跳过行为。"""

    def __init__(self, bank, features, labels):
        self.bank, self.features = bank, features
        self.labels = {row['patient_id']: row for row in labels}
        self.ids = sorted(self.labels)
        if len(self.ids) != len(labels) or set(self.ids) != set(bank.splits['test']):
            raise ValueError('test 标签重复或与 split 不一致')
        for pid in self.ids:
            if features['img'].get(pid) is None:
                raise ValueError(f'{pid}: 缺少 test WSI，禁止跳过')
            bank.validate_query(pid, features['img'][pid])
            row = self.labels[pid]
            time, censor = float(row['survival_months']), float(row['censorship'])
            if not np.isfinite(time) or time < 0 or censor not in (0, 1):
                raise ValueError(f'{pid}: 非法 survival/censorship')
            for mm in ('rna', 'text'):
                value = features[mm].get(pid)
                if value is not None:
                    _numeric(value, context=f'{mm}/{pid}', shape=bank.shapes[mm])

    def batch(self, ids, grid):
        if grid not in GRIDS or len(ids) != len(set(ids)) or not set(ids).issubset(self.ids):
            raise ValueError('非法 grid 或 batch 患者')
        raw = {'img': np.stack([self.features['img'][pid] for pid in ids]),
               'img_valid': np.ones(len(ids), dtype=bool)}
        natural = {}
        for mm in ('rna', 'text'):
            natural[mm] = np.array([self.features[mm].get(pid) is not None for pid in ids])
            valid = natural[mm] & (mm not in masked_modalities(grid))
            raw[mm + '_valid'] = valid
            raw[mm] = np.stack([np.asarray(self.features[mm][pid], dtype=np.float32) if valid[i]
                               else np.zeros(self.bank.shapes[mm], dtype=np.float32)
                               for i, pid in enumerate(ids)])
        return raw, natural


def prepare_batch(bank, ids, raw, natural, arm):
    filled, masks, audit = bank.compensate(ids, raw['img'], {m: raw[m] for m in ('rna', 'text')},
                                         {m: raw[m + '_valid'] for m in ('rna', 'text')}, arm)
    inputs = dict(raw)
    for mm in ('rna', 'text'):
        inputs[mm], inputs[mm + '_valid'] = filled[mm], masks[mm]
    for i, record in enumerate(audit):
        record['natural_valid'] = {mm: bool(natural[mm][i]) for mm in ('rna', 'text')}
        record['fusion_valid'] = {mm: bool(masks[mm][i]) for mm in ('rna', 'text')}
    return inputs, audit


def build_model(cancer, dimensions, device):
    # 与 main_survival.load_model(NPJC, compensator='none') 的构造逐项相同；
    # 不导入训练入口，不实例化 CAP，也不新增投影或对齐层。
    from trimodalsurv.models.npjc import NPJC
    modalities = {mm: SimpleNamespace(feature_dim=dimensions[mm]) for mm in MODEL_SPEC['modality_order']}
    model = NPJC(device, modalities, hidden_size=256, pred_dim=4, dropout_rate=0.1,
                 mlp_ratio=4, n_backbone=1, n_head=4, cancer_types=[cancer], compensator=None)
    return model.to(device).eval()


def strict_e0_load(model, path, *, expected_file_sha=None):
    import torch
    # 对同一份内存快照算 hash 并反序列化，消除检查与加载之间换文件的窗口。
    checkpoint_bytes = path.read_bytes()
    actual_sha = hashlib.sha256(checkpoint_bytes).hexdigest()
    if expected_file_sha is not None and actual_sha != expected_file_sha:
        raise ValueError('checkpoint 在核验与加载之间发生变化')
    payload = torch.load(io.BytesIO(checkpoint_bytes), map_location='cpu', weights_only=True)
    state = strip_data_parallel_prefix(extract_state_dict(payload))
    if any('compensator' in key.lower() or 'cap' in key.lower() for key in state):
        raise ValueError(f'{path}: 不允许 CAP/compensator 权重')
    for key, value in state.items():
        if not torch.is_tensor(value) or not torch.isfinite(value).all():
            raise ValueError(f'{path}/{key}: 非有限或非 tensor 权重')
    model.load_state_dict(state, strict=True)
    if model.compensator is not None:
        raise ValueError('模型必须 compensator=None')
    digest = hashlib.sha256()
    for key in sorted(state):
        value = state[key].detach().cpu().contiguous()
        digest.update(json.dumps([key, str(value.dtype), list(value.shape)]).encode())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def forward_numpy(model, inputs, cancer, device):
    import torch
    with torch.inference_mode():
        tensors = {key: torch.as_tensor(value).to(device=device, dtype=torch.float32)
                   for key, value in inputs.items()}
        logits = model(tensors, cancer_type=[cancer] * len(inputs['img']))[0]
        if logits.ndim != 2 or logits.shape[1] != 4 or not torch.isfinite(logits).all():
            raise ValueError('模型 logits 形状错误或非有限')
        return logits.detach().cpu().numpy()


def checkpoint_path(root, cancer, seed):
    return root / str(seed) / f'tcga_uni2_img_1536text_768rna_256_NPJC_{cancer}_surv.pth'


def preflight_cancer(args, cancer):
    model = build_model(cancer, {mm: shape[-1] for mm, shape in SHAPES.items()}, 'cpu')
    checkpoints = {}
    states_seen = set()
    for seed in args.seeds:
        path = checkpoint_path(args.checkpoint_root, cancer, seed)
        raw_sha = file_sha256(path)
        state_sha = strict_e0_load(model, path, expected_file_sha=raw_sha)
        if state_sha in states_seen:
            raise ValueError(f'{cancer}/{seed}: 跨 seed 重复骨干权重')
        states_seen.add(state_sha)
        checkpoints[str(seed)] = {'path': str(path), 'sha256': raw_sha,
                                  'state_sha256': state_sha, 'strict_load': True}
    diagnostic_dir = args.out_dir / 'diagnostics'
    diagnostic_dir.mkdir(exist_ok=True)
    checkpoint_report = diagnostic_dir / f'checkpoints_{cancer}.json'
    if checkpoint_report.exists():
        if json.loads(checkpoint_report.read_text()) != checkpoints:
            raise ValueError(f'{cancer}: checkpoint 核验前后不一致')
    else:
        write_json_new(checkpoint_report, checkpoints)
    splits, labels = read_labels(args.label, cancer)
    validate_manifest(args.manifest, cancer, splits['test'])
    train, train_hashes = load_cache(args.data_root / 'tmp_sur_cache', cancer, 'train', splits['train'])
    bank = FixedPatientBank(cancer, splits, train, expected_shapes=SHAPES)
    del train
    test, test_hashes = load_cache(args.data_root / 'tmp_sur_cache', cancer, 'test', splits['test'])
    source = CachedPatients(bank, test, labels)
    source_paths = sorted((ROOT / 'src/trimodalsurv').rglob('*.py')) + [
        Path(__file__), Path(__file__).with_name('model.py'), Path(__file__).with_name('config.yaml'),
        ROOT / 'configs/refactor_defaults.yaml']
    configured_path = getattr(args, 'config', None)
    if configured_path is not None and configured_path not in source_paths:
        source_paths.append(Path(configured_path))
    source_hashes = {(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)): file_sha256(path)
                     for path in source_paths}
    provenance = {'migration_source_commit': '6a04a0bf5c283a57e90207899ddffe3867fd5e0a',
                  'bank': bank.metadata(), 'label_sha256': file_sha256(args.label),
                  'manifest_sha256': file_sha256(args.manifest), 'cache_hashes': {**train_hashes, **test_hashes},
                  'source_hashes': source_hashes, 'model': actual_model_spec(model)}
    fingerprint = json_digest(provenance)
    report = {'status': 'READY', 'cancer': cancer, 'splits': {k: len(v) for k, v in splits.items()},
              'natural_test_missing': {mm: sum(test[mm].get(pid) is None for pid in source.ids)
                                       for mm in ('rna', 'text')},
              'checkpoints': checkpoints, 'comparison_fingerprint': fingerprint, 'provenance': provenance}
    if getattr(args, 'run_layout', False):
        resolved = resolved_config(args, model, inputs={key: value for key, value in provenance.items()
                                                    if key not in ('model', 'source_hashes')},
                                   checkpoints=checkpoints, sources=source_hashes)
        resolved_path = args.out_dir / 'audit' / f'resolved_config_{cancer}.json'
        if resolved_path.exists():
            if json.loads(resolved_path.read_text()) != resolved:
                raise ValueError('实际配置在 preflight 后变化')
        else:
            write_resolved_config(resolved_path, resolved)
    return bank, source, model, report


def smoke_ids(source):
    # 只按天然缺失类型选样本，与风险、标签、预测分数无关。
    chosen = []
    for pattern in ((True, True), (True, False), (False, True), (False, False)):
        found = next((pid for pid in source.ids if tuple(source.features[m].get(pid) is not None
                                                       for m in ('rna', 'text')) == pattern), None)
        if found is not None:
            chosen.append(found)
    padded = [pid for pid in source.ids
              if not valid_row_mask(source.features['img'][pid], context=pid).all()]
    return sorted(set(chosen + source.ids[:4] + padded))


def evaluate_unit(args, bank, source, model, report, seed):
    import torch
    from trimodalsurv.evaluation.common import dual_risk_from_logits
    if args.stage == 'formal':
        from sksurv.metrics import concordance_index_censored

    path = checkpoint_path(args.checkpoint_root, bank.cancer, seed)
    expected = report['checkpoints'][str(seed)]
    loaded_state_sha = strict_e0_load(model, path, expected_file_sha=expected['sha256'])
    if loaded_state_sha != expected['state_sha256']:
        raise ValueError('实际加载的 state_dict 与 preflight 不一致')
    model.to(args.device).eval()
    state_before = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    ids = smoke_ids(source) if args.stage == 'smoke' else source.ids
    times = np.array([float(source.labels[pid]['survival_months']) for pid in ids], dtype=np.float32)
    censor = np.array([float(source.labels[pid]['censorship']) for pid in ids], dtype=np.float32)
    all_results = {arm: {} for arm in ARMS}
    for grid in GRIDS:
        outputs, audits = {arm: [] for arm in ARMS}, {arm: [] for arm in ARMS}
        complete_max_abs_diff = None
        n_complete_checked = 0
        for start in range(0, len(ids), args.batch_size):
            batch_ids = ids[start:start + args.batch_size]
            raw, natural = source.batch(batch_ids, grid)
            complete = raw['rna_valid'] & raw['text_valid']
            for arm in ARMS:
                inputs, records = prepare_batch(bank, batch_ids, raw, natural, arm)
                logits = forward_numpy(model, inputs, bank.cancer, args.device)
                if arm == 'm0real':
                    unfilled_logits = logits
                elif complete.any():
                    delta = float(np.max(np.abs(unfilled_logits[complete] - logits[complete])))
                    complete_max_abs_diff = delta if complete_max_abs_diff is None else max(complete_max_abs_diff, delta)
                    # 含天然缺失的 batch 在三臂会走不同 nested/dense mask 路径；
                    # 只容许 FP32 舍入，不容许参数或有效输入变化。
                    if not np.allclose(unfilled_logits[complete], logits[complete], rtol=0, atol=1e-6):
                        raise ValueError(f'完整输入三臂 logits 不一致: max_abs_diff={delta}')
                outputs[arm].append(logits)
                audits[arm].extend(records)
            # 两个填补臂均完成对拍后，每位完整患者只计一次。
            n_complete_checked += int(np.count_nonzero(complete))
        for arm in ARMS:
            logits = np.concatenate(outputs[arm])
            risk = dual_risk_from_logits(torch.from_numpy(logits))[1].numpy()
            prefix = f'{arm}_{bank.cancer}_s{seed}_{grid}'
            artifact_dir = args.out_dir / ('raw' if getattr(args, 'run_layout', False) else 'artifacts')
            artifact_dir.mkdir(exist_ok=True)
            prediction_path = artifact_dir / f'{prefix}.npz'
            audit_dir = args.out_dir / 'audit' if getattr(args, 'run_layout', False) else artifact_dir
            audit_path = audit_dir / f'{prefix}.json'
            with prediction_path.open('xb') as handle:
                np.savez_compressed(handle, patient_id=np.asarray(ids), logits=logits, risk_B=risk,
                                    survival_months=times, censorship=censor)
            write_json_new(audit_path, audits[arm])
            result = {'n_test': len(ids),
                      'n_complete_checked': n_complete_checked,
                      'complete_max_logit_abs_diff': complete_max_abs_diff,
                      'complete_logit_atol': 1e-6,
                      'grid_sha': grid_sha256(grid, ids, set(ids) if grid != 'none' else set()),
                      'predictions_file': str(prediction_path.relative_to(args.out_dir)),
                      'predictions_sha256': file_sha256(prediction_path),
                      'audit_file': str(audit_path.relative_to(args.out_dir)), 'audit_sha256': file_sha256(audit_path)}
            if args.stage == 'formal':
                score = float(concordance_index_censored((1 - censor).astype(bool), times, risk)[0])
                if not np.isfinite(score):
                    raise ValueError('非有限 C-index；禁止剔除或替换 seed')
                result['cindex_B'] = score
            all_results[arm][grid] = result
    for key, value in model.state_dict().items():
        if not torch.equal(value.detach().cpu(), state_before[key]):
            raise ValueError(f'推理修改了骨干权重: {key}')
    for arm in ARMS:
        payload = {'arm': arm, 'cancer': bank.cancer, 'seed': seed, 'protocol_id': PROTOCOL_ID,
                   'checkpoint_sha256': report['checkpoints'][str(seed)]['sha256'],
                   'comparison_fingerprint': report['comparison_fingerprint'], 'grids': all_results[arm],
                   'stage': args.stage, 'device': args.device, 'batch_size': args.batch_size,
                   'review_record_sha256': file_sha256(args.review_record) if args.review_record else None}
        destination = args.out_dir if args.stage == 'formal' else args.out_dir / 'smoke'
        destination.mkdir(exist_ok=True)
        write_json_new(destination / f'{arm}_{bank.cancer}_s{seed}.json', payload)


def parser():
    p = argparse.ArgumentParser(description=__doc__, argument_default=argparse.SUPPRESS)
    p.add_argument('--data-root', required=True, type=Path)
    p.add_argument('--checkpoint-root', type=Path)
    p.add_argument('--label', type=Path)
    p.add_argument('--manifest', type=Path)
    p.add_argument('--out-dir', required=True, type=Path)
    p.add_argument('--cancers', nargs='+', choices=CANCERS, default=argparse.SUPPRESS)
    p.add_argument('--seeds', nargs='+', type=int, choices=SEEDS, default=argparse.SUPPRESS)
    p.add_argument('--stage', choices=('preflight', 'smoke', 'formal'), default=argparse.SUPPRESS)
    p.add_argument('--review-record', type=Path, help='formal 必须提供真实互审记录；文件存在不代表自动获批')
    p.add_argument('--device', choices=('cpu', 'cuda'), default=argparse.SUPPRESS)
    p.add_argument('--batch-size', type=int, default=argparse.SUPPRESS)
    p.add_argument('--cpu-threads', type=int, default=argparse.SUPPRESS)
    p.add_argument('--config', type=Path, help='实验配置；显式 CLI 最后覆盖')
    p.add_argument('--formal-approved', action='store_true', help='确认已有 Claude 审查通过且用户批准本次正式评测')
    return p


def resolve_args(argv=None):
    cli = parser().parse_args(argv)
    config_path = getattr(cli, 'config', Path(__file__).with_name('config.yaml'))
    config = resolve_config(ROOT / 'configs/refactor_defaults.yaml', config_path, cli)
    config['config'] = config_path
    allowed = set(vars(parser().parse_args(['--data-root', '.', '--out-dir', '.']))) | {
        'data_root', 'out_dir', 'checkpoint_root', 'label', 'manifest', 'review_record',
        'cancers', 'seeds', 'stage', 'device', 'batch_size', 'cpu_threads', 'config',
        'formal_approved', 'experiment', 'protocol_id', 'model', 'bin_mode'}
    if set(config) - allowed:
        raise ValueError(f'未知配置字段: {sorted(set(config) - allowed)}')
    if config.get('bin_mode') != 'author':
        raise ValueError('I01 历史协议要求显式 bin_mode=author')
    if config.get('model') != MODEL_SPEC or config.get('protocol_id') != PROTOCOL_ID:
        raise ValueError('I01 模型或协议与锁定配置不一致')
    if type(config['formal_approved']) is not bool:
        raise ValueError('formal_approved 必须为布尔值')
    if config['stage'] not in ('preflight', 'smoke', 'formal') or config['device'] not in ('cpu', 'cuda'):
        raise ValueError('非法 stage/device')
    if not config['cancers'] or not set(config['cancers']).issubset(CANCERS):
        raise ValueError('非法癌种配置')
    if not config['seeds'] or not set(config['seeds']).issubset(SEEDS):
        raise ValueError('非法 seed 配置')
    for key in ('batch_size', 'cpu_threads'):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f'{key} 必须为正整数')
    for key in ('data_root', 'out_dir', 'checkpoint_root', 'label', 'manifest', 'review_record', 'config'):
        if config.get(key) is not None:
            config[key] = Path(config[key]).resolve()
    return argparse.Namespace(**config)


def main(argv=None):
    args = resolve_args(argv)
    if len(args.cancers) != len(set(args.cancers)) or len(args.seeds) != len(set(args.seeds)):
        raise ValueError('癌种或 seed 重复')
    if args.batch_size < 1 or args.cpu_threads < 1:
        raise ValueError('batch-size/cpu-threads 必须为正')
    if args.stage == 'formal':
        if set(args.cancers) != set(CANCERS) or set(args.seeds) != set(SEEDS):
            raise ValueError('formal 必须完整五癌 × 五 seed，不得静默删单元')
        if not args.formal_approved or args.review_record is None or not args.review_record.is_file():
            raise ValueError('formal 需要互审记录，冒烟通过不能自行发车')
    args.data_root = args.data_root.resolve()
    args.checkpoint_root = (args.checkpoint_root or args.data_root / 'out').resolve()
    args.label = (args.label or args.data_root / 'data/TCGA_9523_ex12.csv').resolve()
    args.manifest = (args.manifest or args.data_root / 'data/missing_manifest_v1.csv').resolve()
    args.out_dir = args.out_dir.resolve()
    protected = (args.data_root / 'tmp_sur_cache', args.data_root / 'data', args.checkpoint_root)
    if any(args.out_dir == path.resolve() or args.out_dir.is_relative_to(path.resolve()) for path in protected):
        raise ValueError('输出目录不得位于原缓存、原数据或 checkpoint 目录内')
    # --out-dir 是本次唯一 run 目录，存在即拒绝，保留历史调用语义。
    args.out_dir.mkdir(parents=True, exist_ok=False)
    args.run_layout = True
    for name in ('raw', 'logs', 'audit'):
        (args.out_dir / name).mkdir()
    write_json_new(args.out_dir / 'logs' / 'invocation.json',
                   {'argv': argv, 'stage': args.stage, 'out_dir': str(args.out_dir)})
    diagnostic_dir = args.out_dir / 'diagnostics'
    diagnostic_dir.mkdir()
    status_path = diagnostic_dir / 'campaign_status.json'
    write_json_new(status_path, {'stage': args.stage, 'status': 'RUNNING'})
    import torch
    torch.set_num_threads(args.cpu_threads)
    torch.manual_seed(0)  # 仅构造时；模型 eval 且最终权重全部严格覆盖。
    reports, failures = {}, {}
    for cancer in args.cancers:
        try:
            bank, source, model, report = preflight_cancer(args, cancer)
            reports[cancer] = report
            if args.stage == 'smoke':
                for seed in args.seeds:
                    evaluate_unit(args, bank, source, model, report, seed)
            del bank, source, model
            gc.collect()
        except Exception as error:
            failures[cancer] = f'{type(error).__name__}: {error}'
            print(f'BLOCKED {cancer}: {failures[cancer]}', flush=True)
        else:
            print(f'READY {cancer} ({args.stage})', flush=True)
    preflight = {'stage': args.stage, 'protocol_id': PROTOCOL_ID, 'reports': reports, 'failures': failures,
                 'torch_version': torch.__version__, 'numpy_version': np.__version__}
    diagnostic_dir = args.out_dir / 'diagnostics'
    diagnostic_dir.mkdir(exist_ok=True)
    write_json_new(diagnostic_dir / 'preflight.json', preflight)
    resolved_reports = {cancer: json.loads((args.out_dir / 'audit' / f'resolved_config_{cancer}.json').read_text())
                        for cancer in reports}
    write_resolved_config(args.out_dir / 'resolved_config.yaml',
                          {'schema_version': 1, 'status': 'FAILED' if failures else 'RESOLVED',
                           'cancers': resolved_reports, 'failures': failures})
    write_json_new(args.out_dir / 'source_manifest.json',
                   {'source_commit': '6a04a0bf5c283a57e90207899ddffe3867fd5e0a',
                    'cancers': {c: r['provenance']['source_hashes'] for c, r in reports.items()},
                    'failures': failures})
    write_json_new(args.out_dir / 'data_manifest.json',
                   {'cancers': {c: {k: v for k, v in r['provenance'].items()
                                    if k not in ('source_hashes', 'model', 'migration_source_commit')}
                                for c, r in reports.items()}, 'failures': failures})
    write_json_new(args.out_dir / 'checkpoint_manifest.json',
                   {'cancers': {c: r['checkpoints'] for c, r in reports.items()}, 'failures': failures})
    def write_analysis(status, errors):
        boundary = ('仅核验资产、缓存、split 和严格载入；未执行预测，不构成预测对拍通过。'
                    if args.stage == 'preflight' else
                    '仅执行冒烟与输入/权重边界检查，不产出正式 C-index。'
                    if args.stage == 'smoke' else '正式推理评测；结论仍须人工审查。')
        text = f'# I01 运行检查\n\n- 阶段：{args.stage}\n- 状态：{status}\n- 边界：{boundary}\n'
        text += f'- 资产报告癌种：{list(reports)}\n'
        if errors:
            text += '\n## 失败记录\n\n' + '\n'.join(f'- {key}: {value}' for key, value in errors.items()) + '\n'
        with (args.out_dir / 'analysis.md').open('x', encoding='utf-8') as handle:
            handle.write(text)
    if failures:
        write_analysis('FAILED', failures)
        _atomic_json_dump(status_path, {'stage': args.stage, 'status': 'FAILED', 'failures': failures})
        return 2
    if args.stage == 'formal':
        # 所有单元都通过核验才前向；一次只保留一个癌种的库，五 seed 复用。
        try:
            for cancer in args.cancers:
                bank, source, model, current = preflight_cancer(args, cancer)
                if current != reports[cancer]:
                    raise ValueError(f'{cancer}: preflight 后资产发生变化')
                for seed in args.seeds:
                    evaluate_unit(args, bank, source, model, current, seed)
                del bank, source, model
                gc.collect()
        except Exception as error:
            write_analysis('FAILED', {'formal': f'{type(error).__name__}: {error}'})
            _atomic_json_dump(status_path, {'stage': args.stage, 'status': 'FAILED',
                                           'error': f'{type(error).__name__}: {error}'})
            raise
    write_analysis('COMPLETED', {})
    _atomic_json_dump(status_path, {'stage': args.stage, 'status': 'COMPLETED'})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
