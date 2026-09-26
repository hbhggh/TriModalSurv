#!/usr/bin/env python3
"""I05 Text 特征：只读核验（audit）与提取（extract）。

audit 只读，不写数据目录：统计标签 CSV 的报告列、旧 Text 特征的患者集合与行形态、
新分词器下的 token 长度（可选），以及历史缓存文件的哈希，供 Phase 0 裁决。

extract 只为旧 Text 特征目录已有的患者生成新特征，保证天然缺失口径不变：
旧有而原文缺失即整体失败；原文有而旧无则不生成。每人一个 ``{pid}.pkl``
（float32 ``[200, 768]``，pickle protocol 4），排他写入、回读复验，最后写 ``manifest.json``。
正式运行须从 main 冻结的 run worktree 经 jobrun.sh 启动（AGENTS.md）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pickle
import platform
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I05_text_encoder_bcmbert import gpu_policy  # noqa: E402
from experiments.I05_text_encoder_bcmbert import model as encoder_model  # noqa: E402

CANCERS = ('BLCA', 'BRCA', 'LGG', 'LUAD', 'UCEC')
SPLITS = ('train', 'valid', 'test')
MODALITIES = ('img', 'text', 'rna')
PICKLE_PROTOCOL = 4
DEFAULT_CONFIG = EXPERIMENT_DIR / 'config.yaml'
SOURCE_FILES = ('extract_text_features.py', 'model.py', 'gpu_policy.py', 'config.yaml')
MODEL_FILES = ('config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
               'special_tokens_map.json', 'modules.json', 'sentence_bert_config.json', '1_Pooling/config.json')
# Qwen3-Embedding 快照里逐个记录哈希的文件；其中 config.text_encoders.<a2 档案>.model_files_sha256 锁定的子集必须相符
QWEN_MODEL_FILES = ('config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'vocab.json',
                    'merges.txt', 'modules.json', '1_Pooling/config.json', 'config_sentence_transformers.json',
                    'generation_config.json')


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_config(path=DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_labels(path, *, text_column: str, cancers=CANCERS):
    """读取五癌标签行；患者 ID 必须唯一（坑 D1），split 只能是 train/valid/test。"""
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        required = {'patient_id', 'cancer_type', 'split'}
        if not required.issubset(columns):
            raise ValueError(f'标签 CSV 缺少字段: {sorted(required - set(columns))}')
        rows = list(reader)
    ids = [row['patient_id'] for row in rows]
    if len(ids) != len(set(ids)) or any(not pid.strip() for pid in ids):
        raise ValueError('标签 CSV 的 patient_id 重复或为空')
    has_text = text_column in columns
    records = {}
    for row in rows:
        if row['cancer_type'] not in cancers:
            continue
        if row['split'] not in SPLITS:
            raise ValueError(f"{row['patient_id']}: 非法 split {row['split']!r}")
        records[row['patient_id']] = {'cancer': row['cancer_type'], 'split': row['split'],
                                      'text': row.get(text_column) if has_text else None}
    return records, {'columns': columns, 'has_text_column': has_text, 'text_column': text_column,
                     'rows_total': len(rows), 'rows_selected': len(records)}


def reference_ids(reference_dir) -> list[str]:
    reference_dir = Path(reference_dir)
    if not reference_dir.is_dir():
        raise FileNotFoundError(f'旧 Text 特征目录不存在: {reference_dir}')
    return sorted(path.stem for path in reference_dir.glob('*.pkl'))


def _has_text(record) -> bool:
    text = record.get('text')
    return isinstance(text, str) and bool(text.strip())


def plan_targets(records: dict, ref_ids) -> dict:
    """目标患者 = 五癌标签 ∩ 旧特征目录。原文有而旧无的患者不生成，天然缺失口径不变。"""
    ref = set(ref_ids)
    targets = sorted(pid for pid in records if pid in ref)
    counts = defaultdict(Counter)
    for pid in targets:
        counts[records[pid]['cancer']][records[pid]['split']] += 1
    return {
        'targets': targets,
        'missing_text': sorted(pid for pid in targets if not _has_text(records[pid])),
        'text_without_reference': sorted(pid for pid, record in records.items()
                                         if pid not in ref and _has_text(record)),
        'reference_outside_labels': len(ref - set(records)),
        'counts': {cancer: dict(sorted(value.items())) for cancer, value in sorted(counts.items())},
    }


def load_feature(path) -> np.ndarray:
    with Path(path).open('rb') as handle:
        value = pickle.load(handle)
    if not isinstance(value, np.ndarray):
        raise ValueError(f'{path}: 不是 ndarray（{type(value).__name__}）')
    return value


def row_stats(array: np.ndarray) -> dict:
    """旧特征的行形态：非零行数、不同行数、零行是否只在尾部、各非零行是否全同。"""
    rows = np.ascontiguousarray(array)
    nonzero = np.any(rows != 0, axis=1)
    count = int(nonzero.sum())
    unique = len({row.tobytes() for row in rows[nonzero]})
    return {'n_rows': int(rows.shape[0]), 'n_nonzero_rows': count, 'n_unique_nonzero_rows': unique,
            'zero_rows_are_suffix': bool(nonzero[:count].all() and not nonzero[count:].any()),
            'nonzero_rows_identical': bool(count > 1 and unique == 1)}


def summarize(values) -> dict:
    values = np.asarray(list(values), dtype=np.float64)
    if values.size == 0:
        return {'n': 0}
    quantiles = np.quantile(values, [0, 0.25, 0.5, 0.75, 1])
    return {'n': int(values.size), 'mean': float(values.mean()), 'min': float(quantiles[0]),
            'p25': float(quantiles[1]), 'median': float(quantiles[2]), 'p75': float(quantiles[3]),
            'max': float(quantiles[4])}


def cache_content_digest(value: dict) -> str:
    """缓存 dict 的内容摘要：按患者 ID 排序，逐条纳入 dtype、形状与字节；与 pickle 协议无关。"""
    if not isinstance(value, dict):
        raise ValueError('缓存必须是 {patient_id: array} 映射')
    digest = hashlib.sha256()
    for pid in sorted(value):
        array = np.ascontiguousarray(np.asarray(value[pid]))
        digest.update(json.dumps([pid, str(array.dtype), list(array.shape)]).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def environment() -> dict:
    record = {'python': sys.version.split()[0], 'platform': platform.platform(), 'numpy': np.__version__}
    for name in ('torch', 'transformers', 'huggingface_hub'):
        try:
            module = __import__(name)
        except ImportError:
            record[name] = None
        else:
            record[name] = getattr(module, '__version__', 'unknown')
    try:
        import torch
        record['cuda_available'] = bool(torch.cuda.is_available())
        record['cuda_device'] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except ImportError:
        record['cuda_available'] = None
    return record


def source_identity() -> dict:
    """提取器自身的源码指纹与 git 身份（有 .git 读 HEAD，否则读 GIT_STAMP.json）。"""
    from trimodalsurv import gitstamp
    from trimodalsurv.config import file_fingerprint
    fingerprints = [file_fingerprint(EXPERIMENT_DIR / name) for name in SOURCE_FILES]
    identity = gitstamp.git_identity(fingerprints, root=REPO_ROOT)
    files = {Path(item['path']).relative_to(REPO_ROOT).as_posix(): item['sha256'] for item in fingerprints}
    return {'files': files, 'git': identity}


def write_json_exclusive(path, value) -> None:
    """先序列化、再排他发布；目标已存在即拒绝，不覆盖历史证据。"""
    path = Path(path)
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)
    temporary.unlink()


def write_pickle_exclusive(path, array: np.ndarray) -> str:
    """排他写入单个特征文件（临时文件 + 硬链接发布），返回文件 sha256。"""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'拒绝覆盖已有特征: {path}')
    payload = pickle.dumps(array, protocol=PICKLE_PROTOCOL)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('xb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)
    temporary.unlink()
    return hashlib.sha256(payload).hexdigest()


def _check_output_dir(out_dir: Path, reference_dir: Path) -> None:
    out_resolved, reference_resolved = out_dir.resolve(), reference_dir.resolve()
    if (out_resolved == reference_resolved or out_resolved.is_relative_to(reference_resolved)
            or reference_resolved.is_relative_to(out_resolved)):
        raise ValueError('输出目录不得等于、位于或包含旧 Text 特征目录')
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f'输出目录非空，拒绝覆盖: {out_dir}')


def _limit_targets(targets, records, limit):
    if limit is None:
        return list(targets)
    if limit < 1:
        raise ValueError('--limit 必须为正')
    chosen, seen = [], Counter()
    for pid in targets:
        cancer = records[pid]['cancer']
        if seen[cancer] < limit:
            chosen.append(pid)
            seen[cancer] += 1
    return chosen


def audit_reference(reference_dir, targets, records) -> dict:
    per_cancer = defaultdict(list)
    shapes, dtypes, nonfinite = Counter(), Counter(), 0
    per_patient = {}
    for pid in targets:
        array = load_feature(Path(reference_dir) / f'{pid}.pkl')
        shapes[str(tuple(array.shape))] += 1
        dtypes[str(array.dtype)] += 1
        if not np.isfinite(np.asarray(array, dtype=np.float64)).all():
            nonfinite += 1
        stats = row_stats(array)
        per_patient[pid] = stats
        per_cancer[records[pid]['cancer']].append(stats)
    summary = {}
    for cancer, items in sorted(per_cancer.items()):
        total = len(items)
        summary[cancer] = {
            'n': total,
            'nonzero_rows': summarize(item['n_nonzero_rows'] for item in items),
            'unique_nonzero_rows': summarize(item['n_unique_nonzero_rows'] for item in items),
            'fraction_all_rows_nonzero': sum(item['n_nonzero_rows'] == item['n_rows'] for item in items) / total,
            'fraction_zero_rows_suffix': sum(item['zero_rows_are_suffix'] for item in items) / total,
            'fraction_nonzero_rows_identical': sum(item['nonzero_rows_identical'] for item in items) / total,
        }
    return {'shapes': dict(shapes), 'dtypes': dict(dtypes), 'nonfinite_patients': nonfinite,
            'per_cancer': summary, 'per_patient': per_patient}


def audit_caches(cache_dir, cancers, legacy_preflight=None, legacy_valid=None) -> dict:
    """历史缓存逐文件哈希；给出旧记录时顺带比对，供播种前核验。"""
    expected = {}
    if legacy_preflight is not None:
        for cancer in cancers:
            expected.update(legacy_preflight['reports'][cancer]['provenance']['cache_hashes'])
    if legacy_valid is not None:
        expected.update(legacy_valid['sha256'])
    result = {}
    for cancer in cancers:
        for split in SPLITS:
            for modality in MODALITIES:
                name = f'{modality}_sur_{split}_all_{cancer}.pkl'
                path = Path(cache_dir) / name
                if not path.is_file():
                    result[name] = {'exists': False}
                    continue
                value = sha256_file(path)
                with path.open('rb') as handle:
                    content = pickle.load(handle)
                result[name] = {'exists': True, 'sha256': value, 'n_keys': len(content),
                                'content_digest': cache_content_digest(content),
                                'matches_legacy': (value == expected[name]) if name in expected else None}
                del content
    return result


def cmd_audit(args, *, tokenizer=None) -> dict:
    config = load_config(args.config)
    records, label_meta = read_labels(args.labels, text_column=args.text_column, cancers=tuple(args.cancers))
    refs = reference_ids(args.reference_dir)
    plan = plan_targets(records, refs)
    report = {
        'schema_version': 1, 'stage': 'phase0-audit', 'read_only': True,
        'labels': {'path': Path(args.labels).as_posix(), 'sha256': sha256_file(args.labels), **label_meta},
        'reference_dir': {'path': Path(args.reference_dir).as_posix(), 'n_files': len(refs)},
        'targets': {'n': len(plan['targets']), 'counts': plan['counts'],
                    'missing_text': plan['missing_text'],
                    'n_text_without_reference': len(plan['text_without_reference']),
                    'reference_outside_labels': plan['reference_outside_labels']},
        'reference_features': audit_reference(args.reference_dir, plan['targets'], records),
        'environment': environment(),
        'profile': args.profile,
        'encoder': encoder_model.spec_from_config(config, args.profile).as_dict(),
    }
    if tokenizer is None and args.with_tokenizer:
        from transformers import AutoTokenizer
        from huggingface_hub import snapshot_download
        spec = encoder_model.spec_from_config(config, args.profile)
        snapshot = snapshot_download(repo_id=spec.model_id, revision=spec.revision,
                                     allow_patterns=['tokenizer*', 'special_tokens_map.json', 'config.json'])
        tokenizer = AutoTokenizer.from_pretrained(snapshot)
    if tokenizer is not None and label_meta['has_text_column']:
        texts = [records[pid]['text'] for pid in plan['targets'] if _has_text(records[pid])]
        ids = [pid for pid in plan['targets'] if _has_text(records[pid])]
        lengths = [len(item) for item in tokenizer(texts, add_special_tokens=True, truncation=False,
                                                    padding=False)['input_ids']]
        per_patient = report['reference_features']['per_patient']
        short = [(pid, length) for pid, length in zip(ids, lengths) if length < encoder_model.MAX_LENGTH]
        report['token_lengths'] = {
            'summary': summarize(lengths),
            'fraction_truncated_at_200': sum(length > encoder_model.MAX_LENGTH for length in lengths) / len(lengths),
            'profile_max_length': encoder_model.LOCKED_SPECS[args.profile].max_length,
            'n_over_profile_max_length': sum(length > encoder_model.LOCKED_SPECS[args.profile].max_length
                                             for length in lengths),
            'n_short_reports': len(short),
            'short_reports_with_all_old_rows_nonzero': sum(
                per_patient[pid]['n_nonzero_rows'] == per_patient[pid]['n_rows'] for pid, _ in short),
        }
    if args.cache_dir:
        preflight = json.loads(Path(args.legacy_preflight).read_text()) if args.legacy_preflight else None
        valid = json.loads(Path(args.legacy_valid_source).read_text()) if args.legacy_valid_source else None
        report['caches'] = audit_caches(args.cache_dir, tuple(args.cancers), preflight, valid)
    features = report['reference_features']['per_cancer']
    hints = []
    if not label_meta['has_text_column']:
        hints.append(f'标签 CSV 没有 {args.text_column!r} 列：原文不可得，停下裁决数据来源。')
    if plan['missing_text']:
        hints.append(f"{len(plan['missing_text'])} 名旧特征患者缺报告原文：extract 会拒绝运行。")
    if any(item['fraction_nonzero_rows_identical'] > 0.5 for item in features.values()):
        hints.append('多数旧特征各非零行完全相同：旧槽位不像 token 级，停下重新裁决 A/B。')
    if any(item['fraction_all_rows_nonzero'] > 0.99 for item in features.values()):
        hints.append('旧特征几乎全部 200 行非零：需对照 token 长度判断旧 pad 位是否为零。')
    if report.get('token_lengths', {}).get('short_reports_with_all_old_rows_nonzero'):
        hints.append('存在短报告但旧特征 200 行全非零：旧 pad 位可能不为零，停下裁决 pad 语义。')
    report['decision_hints'] = hints
    if args.out:
        write_json_exclusive(args.out, report)
    return report


def frozen_text_source(args, text_source: str, targets, records) -> tuple:
    """I06 档案的文本来源：LLM 浓缩后冻结的文本清单（经 I06 freeze.read_frozen 读取并核对哈希）。

    患者集合门（无条件）：清单里属于本次癌种的患者必须与「标签 ∩ 旧 Text 特征」的目标患者逐人相同，
    癌种与 split 与冻结标签一致。返回 ({patient_id: 文本}, 写进 manifest 的来源记录)。
    """
    kind, _, arm = text_source.partition(':')
    if kind != 'frozen' or arm not in ('struct', 'summary'):
        raise ValueError(f'未知的文本来源 {text_source!r}')
    if not args.frozen_texts or not args.frozen_sha256:
        raise ValueError('该档案的文本来自冻结的浓缩文本，必须给出 --frozen-texts 与 --frozen-sha256')
    from experiments.I06_llm_condensation.freeze import read_frozen  # 延迟导入，避免与 I06 循环导入
    frozen = read_frozen(args.frozen_texts, expected_sha256=args.frozen_sha256)
    cancers = set(args.cancers)
    in_scope = {pid for pid, row in frozen.items() if row['cancer'] in cancers}
    if in_scope != set(targets):
        extra, missing = sorted(in_scope - set(targets)), sorted(set(targets) - in_scope)
        raise ValueError(f'冻结文本的患者集合与「标签 ∩ 旧 Text 特征」不同：多 {extra[:5]}，少 {missing[:5]}')
    for pid in targets:
        if (frozen[pid]['cancer'], frozen[pid]['split']) != (records[pid]['cancer'], records[pid]['split']):
            raise ValueError(f'{pid}: 冻结文本的癌种或 split 与标签不符')
    statuses = Counter(frozen[pid]['status'] for pid in targets)
    return ({pid: frozen[pid]['text'] for pid in targets},
            {'kind': 'frozen', 'arm': arm, 'file': Path(args.frozen_texts).name, 'sha256': args.frozen_sha256,
             'statuses': dict(sorted(statuses.items()))})


def check_model_files(profile, model_files: dict, locked: dict) -> None:
    """NeuML 档案：快照里的模型文件哈希必须与 config 逐个相同（全集）；Qwen 档案：锁定子集必须相符，其余只记录。"""
    if profile in encoder_model.LOCKED_QWEN_SPECS:
        mismatched = sorted(name for name, digest in locked.items() if model_files.get(name) != digest)
        if mismatched:
            raise ValueError(f'下载到的 Qwen 模型文件与 config 锁定的 sha256 不同: {mismatched}，拒绝提取')
    elif model_files != locked:
        raise ValueError('下载到的模型文件与 config 锁定的 sha256 不同，拒绝提取')


def resolve_batch_size(cli, locked: int) -> int:
    """批大小由档案锁定；CLI 给了不同的值就拒绝，而不是覆盖（它决定补齐组成与浮点复现）。"""
    if cli is not None and int(cli) != int(locked):
        raise ValueError(f'--batch-size {cli} 与档案锁定的 {locked} 不同；不要传 --batch-size')
    return int(locked)


def cmd_extract(args, *, backend=None) -> dict:
    config = load_config(args.config)
    spec = encoder_model.spec_from_config(config, args.profile)
    section = config['text_encoders'][args.profile]
    batch_size = resolve_batch_size(args.batch_size, section['batch_size'])
    out_dir, reference_dir = Path(args.out_dir), Path(args.reference_dir)
    _check_output_dir(out_dir, reference_dir)
    records, label_meta = read_labels(args.labels, text_column=args.text_column, cancers=tuple(args.cancers))
    if not label_meta['has_text_column']:
        raise ValueError(f'标签 CSV 没有 {args.text_column!r} 列，无法提取')
    refs = reference_ids(reference_dir)
    plan = plan_targets(records, refs)
    if plan['missing_text']:
        raise ValueError(f"{len(plan['missing_text'])} 名旧特征患者缺报告原文，拒绝提取: {plan['missing_text'][:10]}")
    text_source = section.get('text_source', 'labels')
    source_record = {'kind': 'labels', 'column': args.text_column}
    if text_source != 'labels':
        texts_by_pid, source_record = frozen_text_source(args, text_source, plan['targets'], records)
        records = {pid: ({**record, 'text': texts_by_pid[pid]} if pid in texts_by_pid else record)
                   for pid, record in records.items()}
    elif args.frozen_texts or args.frozen_sha256:
        raise ValueError(f'{args.profile} 的文本来自标签 CSV，不接受 --frozen-texts / --frozen-sha256')
    qwen = args.profile in encoder_model.LOCKED_QWEN_SPECS
    targets = _limit_targets(plan['targets'], records, args.limit)
    if not targets:
        raise ValueError('没有可提取的目标患者')
    device_record = {'device': args.device, 'gpu_gate': 'INJECTED_TEST_BACKEND'}
    if backend is None:
        # 用户锁定：真实提取必须在 GPU 上跑，并按「空闲卡优先、其次利用率 < 70%」复核卡号。
        gpu_policy.require_gpu(args.device)
        device_record = gpu_policy.gate(args.gpu_id, config['gpu_policy'])
        loader = encoder_model.load_qwen_backend if qwen else encoder_model.load_backend
        tokenizer, model, snapshot = loader(spec, device=args.device, cache_dir=args.hf_cache_dir,
                                            local_files_only=args.local_files_only)
    else:
        tokenizer, model, snapshot = backend
    model_files = {}
    if snapshot is not None:
        for name in (QWEN_MODEL_FILES if qwen else MODEL_FILES):
            candidate = Path(snapshot) / name
            if candidate.is_file():
                model_files[name] = sha256_file(candidate)
        # 先于任何编码：锁定 revision 下的模型文件必须等于 config 固定的哈希（Codex 首审 finding 2）
        check_model_files(args.profile, model_files, section['model_files_sha256'])
    encoder = encoder_model.build_encoder(args.profile, spec, tokenizer, model, device=args.device,
                                          batch_size=batch_size)
    targets = sorted(targets, key=lambda pid: (records[pid]['cancer'], pid))
    texts = [records[pid]['text'] for pid in targets]
    lengths = encoder.token_lengths(texts)
    out_dir.mkdir(parents=True, exist_ok=True)
    patients = {}
    chunk = max(batch_size * 4, 64)  # 只影响进度打印粒度，不影响编码的批次组成
    for start in range(0, len(targets), chunk):
        batch_ids = targets[start:start + chunk]
        features, valid_counts = encoder.encode_with_counts(texts[start:start + chunk])
        for offset, (pid, array, count) in enumerate(zip(batch_ids, features, valid_counts)):
            encoder_model.check_feature(array, context=pid, rows=encoder_model.SLOT_ROWS,
                                        hidden_size=encoder_model.output_dim(spec))
            path = out_dir / f'{pid}.pkl'
            digest = write_pickle_exclusive(path, array)
            reloaded = load_feature(path)
            if (reloaded.dtype != np.float32 or reloaded.shape != array.shape
                    or not np.array_equal(reloaded, array) or sha256_file(path) != digest):
                raise ValueError(f'{pid}: 回读复验失败')
            length = lengths[start + offset]
            if not spec.truncation and count != length:
                raise ValueError(f'{pid}: 不截断档案的有效 token 数 {count} != 全文 token 数 {length}')
            patients[pid] = {'cancer': records[pid]['cancer'], 'split': records[pid]['split'],
                             'sha256': digest, 'n_valid_tokens': count, 'n_tokens_untruncated': length,
                             'truncated': bool(length > spec.max_length),
                             'text_sha256': sha256_text(records[pid]['text'])}
        print(f'extract {min(start + chunk, len(targets))}/{len(targets)}', flush=True)
    counts = defaultdict(Counter)
    for record in patients.values():
        counts[record['cancer']][record['split']] += 1
    manifest = {
        'schema_version': 2, 'status': 'complete', 'partial': args.limit is not None,
        'experiment': config['experiment'], 'profile': args.profile, 'slot_rows': encoder_model.SLOT_ROWS,
        # padding / truncation 取自代码实际使用的 spec，而不是抄 config
        'encoder': {**spec.as_dict(), 'base_model': section['base_model'], 'padding_side': section['padding_side'],
                    'special_tokens': section['special_tokens'], 'pad_rows': section['pad_rows'],
                    'dtype': section['dtype']},
        'batching': {'batch_size': batch_size, 'padding': spec.padding, 'truncation': spec.truncation,
                     'order': 'sorted by (cancer, patient_id)'},
        'pickle_protocol': PICKLE_PROTOCOL,
        'labels': {'path': Path(args.labels).as_posix(), 'sha256': sha256_file(args.labels),
                   'text_column': args.text_column},
        'text_source': source_record,
        'reference_dir': {'path': reference_dir.as_posix(), 'n_files': len(refs),
                          'listing_sha256': hashlib.sha256('\n'.join(refs).encode()).hexdigest()},
        'not_generated_text_without_reference': len(plan['text_without_reference']),
        'extractor': source_identity(),
        'environment': environment(),
        'device': device_record,
        'model_files': model_files,
        'counts': {cancer: dict(sorted(value.items())) for cancer, value in sorted(counts.items())},
        'truncation': {'n': len(lengths), 'n_truncated': sum(length > spec.max_length for length in lengths),
                       'token_length': summarize(lengths)},
        'patients': patients,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    write_json_exclusive(out_dir / 'manifest.json', manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('audit', 'extract'):
        item = sub.add_parser(name)
        item.add_argument('--profile', choices=(encoder_model.ALL_PROFILES if name == 'extract'
                                                else tuple(encoder_model.LOCKED_SPECS)),
                          required=(name == 'extract'), default=None if name == 'extract' else 'bcmbert200',
                          help='特征档案（config.text_encoders）；extract 必须显式给出')
        item.add_argument('--labels', type=Path, required=True, help='标签 CSV（默认运行口径 data/TCGA_9523_ex12.csv）')
        item.add_argument('--reference-dir', type=Path, required=True, help='旧 Text 特征目录 data/text_embeddings_parsed')
        item.add_argument('--text-column', default='text')
        item.add_argument('--cancers', nargs='+', default=list(CANCERS), choices=CANCERS)
    audit = sub.choices['audit']
    audit.add_argument('--out', type=Path, help='审计 JSON 输出路径（不存在才写）')
    audit.add_argument('--with-tokenizer', action='store_true', help='按锁定 revision 加载分词器统计 token 长度')
    audit.add_argument('--cache-dir', type=Path, help='历史缓存目录，逐文件哈希')
    audit.add_argument('--legacy-preflight', type=Path)
    audit.add_argument('--legacy-valid-source', type=Path)
    extract = sub.choices['extract']
    extract.add_argument('--out-dir', type=Path, required=True, help='新特征目录（档案的 feature_dir 所指向的外部目录）')
    extract.add_argument('--device', default='cuda', help='真实提取必须 cuda；cpu 只用于注入替身后端的测试')
    extract.add_argument('--gpu-id', type=int, help='物理卡号，先用 tools/gpu_survey.py 选卡')
    extract.add_argument('--batch-size', type=int, default=None, help='由档案锁定；给出不同值即拒绝')
    extract.add_argument('--limit', type=int, help='冒烟：每癌只取前 N 人，manifest 标 partial')
    extract.add_argument('--frozen-texts', type=Path, help='I06 档案必填：freeze.py 产出的冻结文本清单')
    extract.add_argument('--frozen-sha256', help='I06 档案必填：冻结文本清单的 sha256（取自 freeze manifest）')
    extract.add_argument('--hf-cache-dir')
    extract.add_argument('--local-files-only', action='store_true')
    return parser


def main(argv=None, *, backend=None, tokenizer=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == 'audit':
        report = cmd_audit(args, tokenizer=tokenizer)
        print(json.dumps({'targets': report['targets']['n'], 'decision_hints': report['decision_hints']},
                         ensure_ascii=False))
    else:
        manifest = cmd_extract(args, backend=backend)
        print(json.dumps({'patients': len(manifest['patients']), 'partial': manifest['partial'],
                          'counts': manifest['counts']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
