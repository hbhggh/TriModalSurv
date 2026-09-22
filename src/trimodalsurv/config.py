"""公共默认 → 实验配置 → 显式 CLI；从实际模型生成审计配置。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def read_config(path):
    """项目默认文件使用 JSON 兼容 YAML；普通 YAML 由 PyYAML 读取。"""
    text = Path(path).read_text(encoding='utf-8')
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        import yaml
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError('配置必须是 mapping')
    return value


def merge_config(base, overlay):
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_config(defaults_path, experiment_path, cli=None):
    """CLI Namespace 只能包含显式传入项（argparse.SUPPRESS）。"""
    values = vars(cli) if isinstance(cli, argparse.Namespace) else dict(cli or {})
    return merge_config(merge_config(read_config(defaults_path), read_config(experiment_path)), values)


def file_fingerprint(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'path': str(path), 'sha256': digest.hexdigest()}


def actual_model_spec(model):
    """读取实际层对象；不把历史声明或默认值当作实际构造证据。"""
    layers = model.backbone.layers if hasattr(model.backbone, "layers") else model.backbone
    first = layers[0]
    hidden = int(first.self_attn.embed_dim)
    dropouts = {float(model.m_projector[mm][2].p) for mm in model.modalities}
    if len(dropouts) != 1:
        raise ValueError('模态投影 dropout 不一致')
    spec = {
        'network_type': type(model).__name__,
        'compensator': 'none' if model.compensator is None else type(model.compensator).__name__,
        'hidden_size': hidden,
        'pred_dim': int(model.logits_dim),
        'dropout_rate': next(iter(dropouts)),
        'mlp_ratio': int(first.linear1.out_features // hidden),
        'n_backbone': len(layers),
        'n_head': int(first.self_attn.num_heads),
        'modality_order': list(model.modalities),
    }
    if hasattr(model, 'fusion'):
        spec['fusion'] = type(model.fusion).__name__
    return spec


def _jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def resolved_config(args, model, *, inputs, checkpoints, sources):
    spec = actual_model_spec(model)
    parameters = [(key, list(value.shape), str(value.dtype)) for key, value in model.state_dict().items()]
    schema_sha = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
    actual = vars(args) if isinstance(args, argparse.Namespace) or hasattr(args, '__dict__') else args
    return _jsonable({
        'schema_version': 1,
        'runtime': dict(actual),
        'model': spec,
        'model_input_dimensions': {mm: int(model.m_projector[mm][0].in_features) for mm in model.modalities},
        'model_parameter_schema_sha256': schema_sha,
        'inputs': inputs,
        'checkpoints': checkpoints,
        'source_fingerprints': sources,
        'historical_training': {'status': '未记录', 'learning_rate': '未记录',
                                'epochs': '未记录', 'batch_size': '未记录', 'optimizer': '未记录'},
    })


def write_resolved_config(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(_jsonable(value), handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def runtime_source_fingerprints(args, *, experiment_dir=None):
    """冻结活动源码闭包与实际配置；不依赖 Git 是否已提交。"""
    root = Path(__file__).resolve().parents[2]
    paths = set((root / 'src').rglob('*.py'))
    paths.update((root / 'scripts').glob('*.py'))
    # 所有活动实验的 Python 文件形成保守超集，涵盖组合工厂与生命周期。
    for directory in (root / 'experiments').glob('*'):
        if directory.is_dir() and directory.name != '_template':
            paths.update(path for path in directory.glob('*.py'))
    if experiment_dir is not None:
        paths.update(Path(experiment_dir).glob('*.py'))
    for name in ('config', 'model_config', 'gpu_config'):
        value = getattr(args, name, None)
        if value:
            paths.add(Path(value).resolve())
    entry = Path(sys.argv[0])
    if entry.is_file():
        paths.add(entry.resolve())
    return [file_fingerprint(path) for path in sorted(paths)]


def run_record_root(args, *, experiment_dir=None):
    explicit = getattr(args, 'run_record_root', None)
    if explicit:
        return Path(explicit).expanduser().resolve()
    if experiment_dir is not None:
        return Path(experiment_dir).resolve() / 'results'
    config = getattr(args, 'config', None)
    if config:
        parent = Path(config).resolve().parent
        if parent.parent.name == 'experiments':
            return parent / 'results'
    # 无实验身份的通用入口不猜测创新 ID；与显式输出目录并置。
    return Path(args.result_path).resolve() / 'results'


def start_run_record(root, payload, *, checkpoint_path, modalities=None, run_id=None):
    """只在真实启动时调用；目录独占，失败留下 pending，不伪装成功。"""
    from . import gitstamp
    # 入口已过拒跑门的身份随 payload['git'] 传入；未传的调用方只记录、不拒绝。
    git = dict(payload.get('git') or gitstamp.git_identity(payload.get('source_fingerprints') or []))
    run_id = run_id or gitstamp.new_run_id(git)
    if Path(run_id).name != run_id or run_id in {'.', '..'}:
        raise ValueError('run_id 必须是单个目录名')
    target = Path(root).resolve() / run_id
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    for name in ('raw', 'logs', 'audit'):
        (target / name).mkdir()
    git['recorded_at_utc'] = datetime.now(timezone.utc).isoformat()
    write_resolved_config(target / 'git.json', git)
    write_resolved_config(target / 'resolved_config.yaml', payload)
    write_resolved_config(target / 'source_manifest.json', {'files': payload['source_fingerprints']})
    write_resolved_config(target / 'data_manifest.json', {
        'inputs': payload['inputs'], 'modalities': modalities or {},
        'feature_content_hash_status': '未扫描特征内容；仅记录实际输入位置和标签指纹',
    })
    write_resolved_config(target / 'checkpoint_manifest.json', {
        'status': 'pending', 'path': str(Path(checkpoint_path).resolve()),
        'completion_manifest': 'audit/completion.json',
        'note': '本文件为启动记录；仅 completion.json 能证明正常结束及 checkpoint 内容',
    })
    with (target / 'analysis.md').open('x', encoding='utf-8') as handle:
        handle.write('# 本次运行记录\n\n状态见 `audit/completion.json`。缺少完成证据表示尚未正常结束。\n'
                     '旧 checkpoint 输出路径保持不变；本目录记录真实配置、来源及最终产物指纹。\n'
                     '此页不生成科研结论，指标解释须基于本次原始结果。\n')
    gitstamp.watch_run(target)
    return target


def _ledger_metrics(metrics):
    # 完成记录禁止 NaN；非有限值改写成字符串，指标异常不应让已跑完的运行在收尾时失败。
    clean = {}
    for key, value in (metrics or {}).items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            clean[str(key)] = str(value)
        else:
            clean[str(key)] = number if math.isfinite(number) else repr(number)
    return clean


def finalize_run_record(run_dir, *, checkpoint_path, artifacts=(), metrics=None):
    """正常结束时写一次完成证据；checkpoint 缺失或重复提交均拒绝。"""
    target = Path(run_dir)
    checkpoint = file_fingerprint(checkpoint_path)
    copied = []
    # 复制小型原始结果到独占 run；checkpoint 只留原位和 hash，不复制大权重。
    for index, artifact in enumerate(artifacts):
        source = Path(artifact).resolve()
        destination = target / 'raw' / f'{index:02d}-{source.name}'
        before = file_fingerprint(source)
        with source.open('rb') as reader, destination.open('xb') as writer:
            import shutil
            shutil.copyfileobj(reader, writer)
        after = file_fingerprint(destination)
        if before['sha256'] != after['sha256']:
            raise RuntimeError(f'产物复制校验失败: {source}')
        copied.append({'source': before, 'copy': after})
    write_resolved_config(target / 'audit' / 'completion.json', {
        'status': 'complete', 'checkpoint': checkpoint, 'artifacts': copied,
        'metrics': _ledger_metrics(metrics),
        'finished_at_utc': datetime.now(timezone.utc).isoformat(),
    })
    from . import gitstamp
    ledger = gitstamp.unwatch_run(target)
    try:
        gitstamp.append_ledger(gitstamp.ledger_row(target), path=ledger)
    except OSError as error:
        # 账本只是索引，run 目录才是信源；记账失败不得把已完成的运行变成失败。
        print(f'[git-stamp] 账本追加失败（可用 scripts/git_stamp.py --rebuild-ledger 重建）: {error}', file=sys.stderr)


def training_artifact_paths(task_path):
    """与 checkpoint 同一 seed/配置身份；不采用跨 seed 的癌种级文件名。"""
    task = Path(task_path)
    return {'predictions': task.parent / f'test_pred_and_label_{task.name}.csv',
            'metrics': task.parent / f'{task.name}_results.json',
            'plots': task.parent / f'{task.name}_plots'}


def preflight_training_outputs(task_path, checkpoint_path, *, training, sidecar):
    paths = training_artifact_paths(task_path)
    candidates = list(paths.values()) + [Path(sidecar)]
    if training:
        candidates.append(Path(checkpoint_path))
    conflicts = [str(path) for path in candidates if path.exists() or path.is_symlink()]
    if conflicts:
        raise FileExistsError(f'拒绝覆盖已有运行产物: {conflicts}')
    return paths
