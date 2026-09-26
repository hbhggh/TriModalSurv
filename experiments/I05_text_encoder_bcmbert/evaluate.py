#!/usr/bin/env python3
"""I05 冻结方法推理器：在新 Text 特征与新 ckpt 上复算原型检索方法（S0-force）四场景三臂。

方法完全冻结，不重新选参：
- 臂 = [m0real, m1, 历史选参锁里的 combo 原样（combo-l1-a1-w0p5，λ=1、α=1、w=0.5、UCEC 例外开）]；
- strategy0 = 非 LUAD 取 combo；LUAD 按 4.progress 的 ``route_patient`` 逐患者从 combo/m1/m0real
  组合已存的 logits 与 B 口径风险（不重算，避免跨设备浮点差），再算 C-index。

只调用 2.progress 已锁定的实现（runtime / run.evaluate_cell / inference）、I01 的 strict_e0_load，
以及 4.progress 的路由函数。所有上游源码按 config.yaml 的 sha256 锁核对，不符即拒绝；不训练、不冷建缓存。

阶段：assets（训练前核资产）→ preflight（加查 ckpt）→ smoke（子集患者、不算 C-index）→
replay（legacy-replay 档案，逐值比对历史 300 行）→ test（需回放 PASS、Codex PASS 与用户授权记录）。
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import importlib.util
import json
import subprocess
import sys
import uuid
from collections import Counter
from pathlib import Path

import numpy as np

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I05_text_encoder_bcmbert import gpu_policy  # noqa: E402
from experiments.I05_text_encoder_bcmbert import model as encoder_model  # noqa: E402
from experiments.I05_text_encoder_bcmbert import extract_text_features as extractor  # noqa: E402
from experiments.I05_text_encoder_bcmbert.extract_text_features import (  # noqa: E402
    cache_content_digest, load_feature, sha256_file, write_json_exclusive)

DEFAULT_CONFIG = EXPERIMENT_DIR / 'config.yaml'
STAGES = ('assets', 'preflight', 'smoke', 'replay', 'test')
PROFILES = ('bcmbert200', 'bcmbert8192', 'legacy-replay', 'legacytext-rerun',
            'a1struct', 'a1summ', 'a2struct', 'a2summ')  # 后四个为 I06（LLM 浓缩）档案
MODALITIES = ('img', 'text', 'rna')
SPLITS = ('train', 'valid', 'test')
REPORTED_PROTOCOLS = ('strategy0', 'm1', 'm0real')
# 用户锁定（2026-09-23）：BioClinical ModernBERT 实验的种子必须是这五个，与 Table 1 对照同一组。
REQUIRED_SEEDS = (123, 132, 213, 231, 321)
ROUTES = ('upstream_combo', 'm1', 'm0real')
REPLAY_TIERS = ('same-host', 'cross-hardware')
PASSING_REPLAY = ('IDENTICAL', 'PASS_WITH_FLOAT_DIFFS')
I05_SOURCES = ('evaluate.py', 'model.py', 'extract_text_features.py', 'gpu_policy.py', 'config.yaml')
AUDIT_FIELDS = ('donor_id', 'fusion_valid', 'imputed', 'pool_weights', 'route')


# ----------------------------------------------------------------------------- 通用

def digest_json(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reserve_json(path, value):
    """已存在则必须逐字段相同（可续跑），否则拒绝；不存在则排他写入。"""
    path = Path(path)
    if path.exists():
        if read_json(path) != json.loads(json.dumps(value, allow_nan=False)):
            raise ValueError(f'{path} 已绑定另一套配置或结果，拒绝覆盖')
        return
    write_json_exclusive(path, value)


def cache_path(cache_dir, modality, split, cancer) -> Path:
    return Path(cache_dir) / f'{modality}_sur_{split}_all_{cancer}.pkl'


def load_cache_dict(path) -> dict:
    import pickle
    with Path(path).open('rb') as handle:
        value = pickle.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f'{path}: 缓存必须是 {{patient_id: array}} 映射')
    return value


def cache_keys(path) -> set:
    value = load_cache_dict(path)
    keys = set(value)
    del value
    return keys


# ----------------------------------------------------------------------------- 配置与锁

def load_config(path=DEFAULT_CONFIG) -> dict:
    config = read_json(path)
    required = {'protocol_ids', 'profiles', 'cancers', 'seeds', 'grids', 'text_encoders', 'shapes', 'model',
                'numerics', 'frozen_combo_spec', 's0_force', 'runtime', 'gpu_policy', 'smoke', 'assets',
                'upstream', 'legacy', 'training_contract'}
    missing = required - set(config)
    if missing:
        raise ValueError(f'config 缺少字段: {sorted(missing)}')
    if set(config['profiles']) != set(PROFILES) or set(config['protocol_ids']) != set(PROFILES):
        raise ValueError(f'config 的资产档案必须恰为 {" / ".join(PROFILES)}')
    check_profile_contract(config)
    expected_names = {cache_path('.', 'text', split, cancer).name for cancer in config['cancers'] for split in SPLITS}
    if set(config['legacy'].get('text_keys_sha256') or {}) != expected_names:
        raise ValueError('legacy.text_keys_sha256 必须恰好固定五癌 × 三 split 的历史 text 患者集合摘要')
    if tuple(config['seeds']) != REQUIRED_SEEDS or config['smoke']['seed'] not in REQUIRED_SEEDS:
        raise ValueError('I05 的实验种子必须是 123、132、213、231、321（用户锁定）')
    gpu_policy.validate_policy(config['gpu_policy'])
    if config['runtime']['device'] != 'cuda':
        raise ValueError('I05 实验的默认设备必须是 cuda')
    return config


def verify_pins(config, repo_root=REPO_ROOT) -> dict:
    """上游源码与证据文件逐个核对 sha256；任何一个变了都拒绝运行。"""
    pins = config['upstream']['source_sha256']
    for relative, expected in config['upstream']['baseline_source_sha256'].items():
        if pins.get(relative) != expected:
            raise ValueError(f'baseline_source_sha256 与 source_sha256 不一致: {relative}')
    actual = {}
    for relative, expected in sorted(pins.items()):
        path = Path(repo_root) / relative
        if not path.is_file():
            raise FileNotFoundError(f'锁定的上游文件不存在: {relative}')
        value = sha256_file(path)
        if value != expected:
            raise ValueError(f'上游源码已改变，拒绝运行: {relative}')
        actual[relative] = value
    return actual


def frozen_spec(config, repo_root=REPO_ROOT) -> dict:
    """冻结 combo 规格必须与历史 valid 选参锁里的 combo 逐字段相同。"""
    lock = read_json(Path(repo_root) / config['upstream']['selection_lock'])
    selected = lock['selection']['selected']['combo']
    if selected != config['frozen_combo_spec']:
        raise ValueError('config.frozen_combo_spec 与历史选参锁不一致')
    return copy.deepcopy(selected)


def check_route_table(route_module, config) -> None:
    """路由函数的行为必须与 config 里抄录的 S0-force 路由表一致。"""
    table = config['s0_force']['luad_route']
    cases = {
        'text_100': ('text_100', True, True), 'rna_100': ('rna_100', True, True),
        'both_100': ('both_100', True, True), 'none_rna_missing': ('none', False, True),
        'none_both_missing': ('none', False, False), 'none_text_only_or_complete': ('none', True, False),
    }
    for name, (grid, rna_valid, text_valid) in cases.items():
        route = route_module.route_patient(cancer='LUAD', grid=grid, rna_valid=rna_valid,
                                           text_valid=text_valid)['route']
        if route != table[name]:
            raise ValueError(f'路由函数与冻结路由表不一致: {name}')
    complete = route_module.route_patient(cancer='LUAD', grid='none', rna_valid=True, text_valid=True)['route']
    if complete != table['none_text_only_or_complete']:
        raise ValueError('完整 LUAD 患者在 none 下必须走组合')
    for cancer in config['cancers']:
        if cancer != 'LUAD':
            for grid in config['grids']:
                if route_module.route_patient(cancer=cancer, grid=grid, rna_valid=True,
                                              text_valid=True)['route'] != 'upstream_combo':
                    raise ValueError('非 LUAD 必须一律走组合')


def i05_source_hashes() -> dict:
    return {f'i05/{name}': sha256_file(EXPERIMENT_DIR / name) for name in I05_SOURCES}


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'无法加载模块: {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Upstream:
    """只读导入已锁定的上游实现，并核对导入到的正是锁定的文件。"""

    def __init__(self, config, repo_root=REPO_ROOT):
        root = (Path(repo_root) / config['upstream']['inference_root']).resolve()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import runtime as rt  # noqa: E402  2.progress/result/runtime.py
        import run as up_run  # noqa: E402  2.progress/result/run.py
        import inference  # noqa: E402  2.progress/result/inference.py
        for module, name in ((rt, 'runtime.py'), (up_run, 'run.py'), (inference, 'inference.py')):
            if Path(module.__file__).resolve() != root / name:
                raise ImportError(f'导入的 {name} 不是锁定的上游文件: {module.__file__}')
        from experiments.I01_patient_retrieval import evaluate as i01
        from trimodalsurv.evaluation.common import dual_risk_from_logits
        self.rt, self.run, self.inference, self.i01 = rt, up_run, inference, i01
        self.dual_risk_from_logits = dual_risk_from_logits
        self.route = _load_module('_i05_s0_force_route', Path(repo_root) / config['upstream']['route_module'])


def build_upstream_config(config, *, run_root, checkpoint_root, execution_root, device, gpu_id,
                          retrieval_backend, batch_size, cpu_threads, repo_root=REPO_ROOT) -> dict:
    """组装 2.progress 实现需要的配置形状；科学参数全部取自 I05 config，不接受 CLI 改动。"""
    run_root = Path(run_root)
    cache_dir = run_root / config['assets']['cache_dir']
    return {
        'grids': list(config['grids']), 'shapes': copy.deepcopy(config['shapes']),
        'numerics': copy.deepcopy(config['numerics']), 'model': copy.deepcopy(config['model']),
        'rules': list(config['upstream']['rules']), 'smoke': copy.deepcopy(config['smoke']),
        'runtime': {'stage': 'test', 'device': device, 'batch_size': int(batch_size), 'cpu_threads': int(cpu_threads),
                    'forward_dtype': 'float32', 'num_workers': 0, 'pin_memory': False,
                    'persistent_workers': False, 'prefetch_factor': None, 'non_blocking': True,
                    'retrieval_backend': retrieval_backend, 'gpu_id': gpu_id},
        'paths': {'repo_root': str(repo_root), 'label': str(run_root / config['assets']['label']),
                  'manifest': str(run_root / config['assets']['manifest']),
                  'checkpoint_root': str(checkpoint_root) if checkpoint_root else None,
                  'cache_roots': {split: str(cache_dir) for split in SPLITS},
                  'execution_root': str(execution_root)},
        'baseline_source_sha256': copy.deepcopy(config['upstream']['baseline_source_sha256']),
    }


# ----------------------------------------------------------------------------- 历史证据

def load_legacy(config, *, repo_root=REPO_ROOT, preflight_override=None, valid_override=None) -> dict:
    legacy = config['legacy']
    preflight_path = Path(preflight_override) if preflight_override else Path(repo_root) / legacy['preflight']
    valid_path = Path(valid_override) if valid_override else Path(repo_root) / legacy['valid_source']
    if preflight_override is None and sha256_file(preflight_path) != legacy['preflight_sha256']:
        raise ValueError('legacy-preflight.json 与锁定哈希不一致')
    if valid_override is None and sha256_file(valid_path) != legacy['valid_source_sha256']:
        raise ValueError('valid-source.json 与锁定哈希不一致')
    preflight = read_json(preflight_path)
    overridden = preflight_override is not None or valid_override is not None
    # 历史 text 患者集合摘要（复审 round2）：正式运行只取 config 固定值；替身证据只用于 _SYNTHETIC 合成运行
    text_keys = preflight.get('text_keys_sha256', {}) if overridden else legacy['text_keys_sha256']
    return {'preflight': preflight, 'valid': read_json(valid_path),
            'preflight_sha256': sha256_file(preflight_path), 'valid_sha256': sha256_file(valid_path),
            'text_keys_sha256': text_keys, 'overridden': overridden}


def load_legacy_test_complete(config, repo_root=REPO_ROOT) -> dict:
    path = Path(repo_root) / config['legacy']['test_complete']
    if sha256_file(path) != config['legacy']['test_complete_sha256']:
        raise ValueError('历史 test complete.json 与锁定哈希不一致')
    payload = read_json(path)
    if payload.get('run_fingerprint') != config['legacy']['test_run_fingerprint']:
        raise ValueError('历史 test 指纹不符')
    return payload


def legacy_cache_sha(legacy, cancer, modality, split):
    name = cache_path('.', modality, split, cancer).name
    if split == 'valid':
        return legacy['valid']['sha256'].get(name)
    return legacy['preflight']['reports'][cancer]['provenance']['cache_hashes'].get(name)


def _model_config_text_path(path) -> str:
    """不依赖 PyYAML，读出 model config 里 modality.text.path 的原样字符串。"""
    section = None
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key = line.strip().split(':', 1)[0]
        if indent == 0:
            section = 'modality' if key == 'modality' else None
        elif section == 'modality' and indent == 2:
            section = 'modality.text' if key == 'text' else 'modality'
        elif section == 'modality.text' and key == 'path':
            return line.split(':', 1)[1].strip()
    raise ValueError(f'{path} 里找不到 modality.text.path')


def check_profile_contract(config, repo_root=REPO_ROOT) -> None:
    """每个新特征档案在三处（编码器锁、训练契约、model config 文件）必须指向同一个 Text 目录。"""
    profiles, encoders = config['profiles'], config['text_encoders']
    contract = config['training_contract']
    new_text = {name for name, value in profiles.items() if value['text_cache'] == 'new'}
    new_ckpt = {name for name, value in profiles.items() if value['checkpoints'] == 'new'}
    if set(encoders) != new_text:
        raise ValueError(f'text_encoders 的档案 {sorted(encoders)} 必须恰为新特征档案 {sorted(new_text)}')
    if set(contract['model_config']) != new_ckpt or set(contract['text_path']) != new_ckpt:
        raise ValueError(f'training_contract 的 model_config / text_path 必须恰为新训练档案 {sorted(new_ckpt)}')
    for name, section in sorted(encoders.items()):
        locked = set(section.get('model_files_sha256') or {})
        if name in encoder_model.LOCKED_QWEN_SPECS:
            # Qwen 档案按 revision 锁定；权重与分词器两个 LFS 文件另按 sha256 锁定，其余文件只在 manifest 记录
            if not {'model.safetensors', 'tokenizer.json'} <= locked <= set(extractor.QWEN_MODEL_FILES):
                raise ValueError(f'{name}: model_files_sha256 必须至少锁定 model.safetensors 与 tokenizer.json')
        elif locked != set(extractor.MODEL_FILES):
            raise ValueError(f'{name}: model_files_sha256 必须恰好固定 {len(extractor.MODEL_FILES)} 个模型文件的哈希')
        source = section.get('text_source', 'labels')
        if source != 'labels' and source not in ('frozen:struct', 'frozen:summary'):
            raise ValueError(f'{name}: 未知的 text_source {source!r}')
    feature_dirs = [encoders[name]['feature_dir'] for name in sorted(encoders)]
    if len(set(feature_dirs)) != len(feature_dirs):
        raise ValueError('不同档案的 feature_dir 必须互不相同（缓存键不含特征路径，混用会静默命中，坑 D2）')
    for name in sorted(new_ckpt):
        text_path = contract['text_path'][name]
        if name in encoders:
            encoder_model.spec_from_config(config, name)
            if text_path != encoders[name]['feature_dir']:
                raise ValueError(f'{name}: training_contract.text_path {text_path} != feature_dir {encoders[name]["feature_dir"]}')
        declared = _model_config_text_path(Path(repo_root) / contract['model_config'][name])
        if declared != text_path:
            raise ValueError(f'{name}: model config 的 text.path {declared} != training_contract.text_path {text_path}')


# ----------------------------------------------------------------------------- 资产门

def extractor_source_hashes() -> dict:
    """当前代码树里提取器源码闭包的 sha256，键与 manifest.extractor.files 相同（相对仓库根）。"""
    prefix = EXPERIMENT_DIR.relative_to(REPO_ROOT).as_posix()
    return {f'{prefix}/{name}': sha256_file(EXPERIMENT_DIR / name) for name in extractor.SOURCE_FILES}


def _feature_manifest(config, run_root, profile, spec_check=True):
    section = config['text_encoders'][profile]
    feature_dir = Path(run_root) / section['feature_dir']
    manifest_path = feature_dir / 'manifest.json'
    manifest = read_json(manifest_path)
    if manifest.get('status') != 'complete' or manifest.get('partial') is not False:
        raise ValueError('新特征 manifest 未完成或是冒烟用的部分提取')
    if spec_check:
        expected = encoder_model.spec_from_config(config, profile).as_dict()
        actual = {key: manifest['encoder'].get(key) for key in expected}
        if actual != expected:
            raise ValueError(f'新特征 manifest 的编码器设置与锁定值不一致: {actual}')
    schema = int(manifest.get('schema_version', 1))
    if schema < int(section['manifest_min_schema']):
        raise ValueError(f'{profile} 要求特征 manifest schema ≥ {section["manifest_min_schema"]}，实际 {schema}')
    if schema >= 2:
        batching = manifest.get('batching') or {}
        if (manifest.get('profile') != profile or batching.get('batch_size') != section['batch_size']
                or manifest.get('slot_rows') != encoder_model.SLOT_ROWS):
            raise ValueError(f'新特征 manifest 的档案、batching 或槽位行数与 {profile} 不符')
        # 生成身份（Codex 首审 finding 2）：特征必须由与当前代码逐字节相同的干净提取器、
        # 在锁定 revision 的锁定模型文件上生成；旧版 / dirty 提取器或被换过的权重都拒绝。
        source = manifest.get('extractor') or {}
        if source.get('files') != extractor_source_hashes():
            raise ValueError('新特征 manifest 的提取器源码与当前代码不同（旧版或改过的提取器），拒绝')
        if (source.get('git') or {}).get('dirty') is not False:
            raise ValueError('新特征 manifest 的提取器不是干净源码身份（dirty 或无 commit），拒绝')
        if profile in encoder_model.LOCKED_QWEN_SPECS:
            recorded_files = manifest.get('model_files') or {}
            if not recorded_files or any(recorded_files.get(name) != digest
                                         for name, digest in section['model_files_sha256'].items()):
                raise ValueError('新特征 manifest 的模型文件哈希与 config 锁定值不同，拒绝')
        elif manifest.get('model_files') != section['model_files_sha256']:
            raise ValueError('新特征 manifest 的模型文件哈希与 config 锁定值不同，拒绝')
        source = section.get('text_source', 'labels')
        recorded = manifest.get('text_source') or {'kind': 'labels'}
        if source == 'labels' and recorded.get('kind') != 'labels':
            raise ValueError(f'{profile} 的文本应来自标签 CSV，manifest 记录的却是 {recorded}')
        if source != 'labels' and (recorded.get('kind'), recorded.get('arm')) != ('frozen', source.split(':', 1)[1]):
            raise ValueError(f'{profile} 的文本应来自冻结的 {source} 文本，manifest 记录的是 {recorded}')
    return feature_dir, manifest, sha256_file(manifest_path)


def _expected_text_patients(config, run_root, profile, manifest, label_sha) -> dict:
    """由冻结输入独立推出每位新特征患者的 (癌种, split)（Codex 首审 finding 3）。

    manifest 的标签哈希必须等于冻结标签；manifest 的患者集合必须恰为「五癌标签 ∩ 旧 Text 特征目录」，
    且逐人的癌种 / split 等于冻结标签。返回 {patient_id: (cancer, split)}，供逐 split 推出 text 缓存的期望患者。
    """
    section = config['text_encoders'][profile]
    if (manifest.get('labels') or {}).get('sha256') != label_sha:
        raise ValueError('新特征 manifest 的标签哈希与冻结标签不同：特征可能按别的 split 生成，拒绝')
    records, _ = extractor.read_labels(Path(run_root) / config['assets']['label'],
                                       text_column=section['text_column'], cancers=tuple(config['cancers']))
    refs = extractor.reference_ids(Path(run_root) / section['reference_feature_dir'])
    listing = hashlib.sha256('\n'.join(refs).encode()).hexdigest()
    if (manifest.get('reference_dir') or {}).get('listing_sha256') != listing:
        raise ValueError('新特征 manifest 记录的旧 Text 特征目录清单与运行根不同，拒绝')
    targets = set(extractor.plan_targets(records, refs)['targets'])
    patients = manifest['patients']
    if set(patients) != targets:
        extra, missing = sorted(set(patients) - targets), sorted(targets - set(patients))
        raise ValueError(f'新特征 manifest 的患者集合不等于「标签 ∩ 旧 Text 特征」：多 {extra[:5]}，少 {missing[:5]}')
    for pid, entry in patients.items():
        label = records[pid]
        if (entry.get('cancer'), entry.get('split')) != (label['cancer'], label['split']):
            raise ValueError(f'{pid}: 新特征 manifest 的癌种或 split 与冻结标签不符')
    return {pid: (records[pid]['cancer'], records[pid]['split']) for pid in targets}


def check_assets(config, legacy, *, run_root, profile, cancers, legacy_cache_dir=None) -> dict:
    """训练前的资产门：标签、manifest、img/rna 缓存与历史相同；text 缓存按档案要求核对。"""
    kind = config['profiles'][profile]['text_cache']
    run_root = Path(run_root)
    cache_dir = run_root / config['assets']['cache_dir']
    label_sha = sha256_file(run_root / config['assets']['label'])
    manifest_sha = sha256_file(run_root / config['assets']['manifest'])
    report = {'profile': profile, 'text_cache': kind, 'label_sha256': label_sha, 'manifest_sha256': manifest_sha,
              'cancers': {}}
    feature_dir = feature_manifest = labelled = None
    if kind == 'new':
        feature_dir, feature_manifest, report['feature_manifest_sha256'] = _feature_manifest(config, run_root, profile)
        if int(feature_manifest.get('schema_version', 1)) >= 2:
            labelled = _expected_text_patients(config, run_root, profile, feature_manifest, label_sha)
            report['feature_extractor_commit'] = feature_manifest['extractor']['git'].get('commit')
    for cancer in cancers:
        legacy_report = legacy['preflight']['reports'][cancer]
        provenance = legacy_report['provenance']
        if label_sha != provenance['label_sha256'] or manifest_sha != provenance['manifest_sha256']:
            raise ValueError(f'{cancer}: 标签或缺失 manifest 与历史不一致')
        files = {}
        for split in SPLITS:
            for modality in MODALITIES:
                path = cache_path(cache_dir, modality, split, cancer)
                if not path.is_file():
                    raise FileNotFoundError(f'缺少缓存，禁止冷建: {path.name}')
                actual, expected = sha256_file(path), legacy_cache_sha(legacy, cancer, modality, split)
                if expected is None:
                    raise ValueError(f'历史记录缺少 {path.name} 的哈希')
                if modality == 'text' and kind == 'new':
                    if actual == expected:
                        raise ValueError(f'{path.name} 与历史 text 缓存逐字节相同：新特征没有生效（坑 D2）')
                    status = 'new'
                elif actual == expected:
                    status = 'identical'
                elif legacy_cache_dir is not None and cache_content_digest(load_cache_dict(path)) == \
                        cache_content_digest(load_cache_dict(cache_path(legacy_cache_dir, modality, split, cancer))):
                    status = 'content_identical'
                else:
                    raise ValueError(f'{path.name} 与历史冻结缓存不一致')
                files[path.name] = {'sha256': actual, 'status': status}
                if status == 'new':
                    files[path.name]['content_sha256'] = cache_content_digest(load_cache_dict(path))
        img_keys = {split: cache_keys(cache_path(cache_dir, 'img', split, cancer)) for split in SPLITS}
        counts = {}
        text_keys = {}
        rna_keys = {}
        for split in SPLITS:
            rna_keys[split] = cache_keys(cache_path(cache_dir, 'rna', split, cancer)) & img_keys[split]
            text = load_cache_dict(cache_path(cache_dir, 'text', split, cancer))
            text_keys[split] = set(text)
            if kind == 'new':
                if labelled is not None:
                    # 期望集合由冻结输入推出：有 WSI（历史缓存）、有旧 Text 特征、冻结标签的癌种与 split 相符
                    expected_keys = {pid for pid in img_keys[split] if labelled.get(pid) == (cancer, split)}
                else:
                    expected_keys = {pid for pid in img_keys[split] if pid in feature_manifest['patients']}
                if text_keys[split] != expected_keys:
                    raise ValueError(f'{cancer}/{split}: text 缓存患者集合与"有 WSI 且有新特征"的集合不一致')
                if labelled is not None:
                    # 硬门，不依赖任何参数：患者集合必须等于历史 text 缓存（config 固定的集合摘要）
                    name = cache_path('.', 'text', split, cancer).name
                    digest = hashlib.sha256('\n'.join(sorted(text_keys[split])).encode()).hexdigest()
                    if digest != legacy['text_keys_sha256'].get(name):
                        raise ValueError(f'{cancer}/{split}: text 缓存患者集合与历史 text 缓存逐人不同')
                for pid, value in text.items():
                    entry = feature_manifest['patients'][pid]
                    if entry['cancer'] != cancer or entry['split'] != split:
                        raise ValueError(f'{pid}: 新特征 manifest 的癌种或 split 与标签不符')
                    feature_path = feature_dir / f'{pid}.pkl'
                    if sha256_file(feature_path) != entry['sha256']:
                        raise ValueError(f'{pid}: 特征文件与 manifest 哈希不符')
                    feature = load_feature(feature_path)
                    array = np.asarray(value)
                    if array.shape != feature.shape or not np.array_equal(array, feature):
                        raise ValueError(f'{pid}: text 缓存条目与特征文件不一致')
            del text
            counts[split] = {'img': len(img_keys[split]), 'rna': len(rna_keys[split]), 'text': len(text_keys[split])}
        splits = legacy_report['splits']
        if counts['test']['img'] != splits['test']:
            raise ValueError(f'{cancer}: test WSI 人数与历史不一致')
        test_missing = {'rna': counts['test']['img'] - counts['test']['rna'],
                        'text': counts['test']['img'] - counts['test']['text']}
        if test_missing != legacy_report['natural_test_missing']:
            raise ValueError(f'{cancer}: test 天然缺失人数 {test_missing} 与历史 '
                             f"{legacy_report['natural_test_missing']} 不一致")
        available = provenance['bank']['available_counts']
        if {'rna': counts['train']['rna'], 'text': counts['train']['text']} != available:
            raise ValueError(f'{cancer}: train 可用人数与历史患者库不一致')
        report['cancers'][cancer] = {'files': files, 'counts': counts, 'test_natural_missing': test_missing}
    return report


# ----------------------------------------------------------------------------- ckpt 门

# 测试注入点：只能由测试 monkeypatch，任何 CLI 参数都不能打开（Codex 候选复核 r3 finding 2）。
ALLOW_CPU_FOR_SYNTHETIC_TESTS = False


def identity_closure(config, repo_root=REPO_ROOT) -> list:
    """交给源码身份门的文件：只含 GIT_STAMP 覆盖的源码后缀（.py/.yaml/.yml/.sh）。

    stamp 不记录其他文件（如 selection-lock.json），只有 stamp 的服务器上它们会被误判为 dirty；
    这些锁定文件仍由 verify_pins 按 sha256 逐字节核对，保护强度不变。
    """
    from trimodalsurv.gitstamp import STAMP_SUFFIXES
    root = Path(repo_root)
    paths = [root / 'experiments' / EXPERIMENT_DIR.name / name for name in I05_SOURCES] + \
        [root / relative for relative in config['upstream']['source_sha256']]
    return [path for path in paths if path.name.endswith(STAMP_SUFFIXES)]


def source_identity(closure, *, allow_dirty) -> dict:
    """当前源码身份：有 .git 读 HEAD，否则读 GIT_STAMP.json；dirty 且未放行即拒。测试经 monkeypatch 替换本函数。"""
    from trimodalsurv import gitstamp
    from trimodalsurv.config import file_fingerprint
    return gitstamp.require_git_identity([file_fingerprint(path) for path in closure],
                                         allow_dirty=allow_dirty, root=REPO_ROOT)


def resolve_expected_commit(explicit, identity, *, repo_root=REPO_ROOT):
    """期望 commit 只能是当前源码身份；--expected-commit 与 GIT_STAMP.json 只作核对，任一不等即拒。无例外分支。"""
    current = identity.get('commit')
    if current is None or identity.get('dirty') or identity.get('allow_dirty'):
        raise ValueError('需要干净的冻结源码身份：commit 已知、dirty=false、未放行 dirty')
    stamp = Path(repo_root) / 'GIT_STAMP.json'
    if stamp.is_file() and read_json(stamp).get('commit') != current:
        raise ValueError('GIT_STAMP.json 的 commit 与当前源码身份不同')
    if explicit and explicit != current:
        raise ValueError(f'--expected-commit {explicit[:12]} 与当前源码身份 {current[:12]} 不同，拒绝')
    return current, identity.get('source')


# ----------------------------------------------------------------------------- 训练前资产锁

ASSETS_LOCK = 'assets-lock.json'


def assets_lock_view(assets) -> dict:
    """资产锁只比内容。训练会无条件重写缓存（坑 D15），所以 text 新缓存按内容摘要比；
    img/rna 已由 check_assets 证明等价于历史冻结件，记为 matches_legacy；新特征由 manifest 哈希绑定
    （check_assets 逐人核对特征文件等于 manifest）。"""
    files = {}
    for cancer, info in assets['cancers'].items():
        files[cancer] = {name: entry.get('content_sha256') or ('matches_legacy' if entry['status'] in
                                                                ('identical', 'content_identical') else entry['sha256'])
                         for name, entry in sorted(info['files'].items())}
    return {'profile': assets['profile'], 'label_sha256': assets['label_sha256'],
            'manifest_sha256': assets['manifest_sha256'],
            'feature_manifest_sha256': assets.get('feature_manifest_sha256'), 'files': files}


def write_assets_lock(stage_dir, *, protocol_id, profile, commit, assets) -> dict:
    """训练前在 assets 阶段只写一次；再次运行只核对不覆盖。"""
    from datetime import datetime, timezone
    view = assets_lock_view(assets)
    digest = digest_json(view)
    path = Path(stage_dir) / ASSETS_LOCK
    if path.exists():
        lock = read_json(path)
        if (lock.get('assets_lock_sha256') != digest or lock.get('commit') != commit
                or lock.get('protocol_id') != protocol_id or lock.get('profile') != profile):
            raise ValueError('已有资产锁与当前资产、源码或协议不同；资产锁只写一次，不覆盖')
        return lock
    lock = {'protocol_id': protocol_id, 'profile': profile, 'commit': commit, 'assets_lock_sha256': digest,
            'view': view, 'locked_at_utc': datetime.now(timezone.utc).isoformat()}
    write_json_exclusive(path, lock)
    return lock


def check_assets_lock(lock_path, *, protocol_id, profile, commit, assets, checkpoints) -> dict:
    """新训练 ckpt 的数据身份（Codex 候选复核 r3 finding 1）：训练用的特征与缓存内容 = 训练前锁定的内容 = 当前内容。

    锁必须早于每个 run record 的 recorded_at_utc；当前资产逐癌等于锁；锁的 commit、协议、档案与本轮相同。
    残余：训练期间替换后又恢复原内容无法由前后两次核对发现，见研究计划书风险登记。
    """
    from datetime import datetime
    if lock_path is None:
        raise ValueError('新训练 ckpt 需要 --assets-lock（训练前 assets 阶段写出的资产锁）')
    lock = read_json(lock_path)
    if (lock.get('protocol_id') != protocol_id or lock.get('profile') != profile or lock.get('commit') != commit):
        raise ValueError('资产锁的协议、档案或 commit 与本轮不同')
    view = lock.get('view') or {}
    if digest_json(view) != lock.get('assets_lock_sha256'):
        raise ValueError('资产锁内容与其摘要不符')
    current = assets_lock_view(assets)
    same_top = all(view.get(key) == current[key] for key in current if key != 'files')
    same_files = all(view.get('files', {}).get(cancer) == files for cancer, files in current['files'].items())
    if not (same_top and same_files):
        raise ValueError('当前资产内容与训练前资产锁不同：训练后特征或缓存被替换')
    locked = datetime.fromisoformat(lock['locked_at_utc'])
    early = sorted(f'{cancer}/{seed}' for cancer, entries in checkpoints.items() for seed, entry in entries.items()
                   if 'recorded_at_utc' in entry and datetime.fromisoformat(entry['recorded_at_utc']) <= locked)
    if early:
        raise ValueError(f'资产锁晚于训练启动，不能证明训练所用内容: {early}')
    return {'assets_lock_sha256': sha256_file(lock_path), 'locked_at_utc': lock['locked_at_utc']}


def find_run_record(checkpoint_root, checkpoint_sha) -> Path:
    """在训练结果根的 run 目录里找 completion.json 指纹等于该 ckpt 的唯一记录。"""
    matches = []
    for completion in sorted((Path(checkpoint_root) / 'results').glob('*/audit/completion.json')):
        data = read_json(completion)
        if data.get('status') == 'complete' and data.get('checkpoint', {}).get('sha256') == checkpoint_sha:
            matches.append(completion.parents[1])
    if len(matches) != 1:
        raise ValueError(f'ckpt {checkpoint_sha[:12]} 对应的完成运行记录有 {len(matches)} 份，必须恰为 1 份')
    return matches[0]


def check_training_record(run_dir, config, legacy, *, profile, cancer, seed, run_root, repo_root=REPO_ROOT) -> dict:
    """训练身份门：run 的实际参数、模型配置、标签、GPU 配置与 Text 路径必须等于获审配方（唯一变量是 Text）。"""
    contract = config['training_contract']
    resolved = read_json(Path(run_dir) / 'resolved_config.yaml')
    runtime = resolved.get('runtime', {})
    # I06 档案另要求 skip_test=true（Codex 节点一 finding 2）：用实际记录证明训练时没有在 test 上预测
    expected = {**contract['runtime'], **contract.get('runtime_by_profile', {}).get(profile, {}),
                'seed': seed, 'cancer_types': cancer}
    mismatched = sorted(key for key, value in expected.items() if runtime.get(key) != value)
    if mismatched:
        raise ValueError(f'{cancer}/{seed}: 训练参数与获审配方不符: {mismatched}')
    inputs = {Path(item['path']).name: item['sha256'] for item in resolved.get('inputs', [])}
    model_config = Path(repo_root) / contract['model_config'][profile]
    gpu_config = Path(repo_root) / contract['gpu_config']
    label_sha = legacy['preflight']['reports'][cancer]['provenance']['label_sha256']
    if inputs.get(model_config.name) != sha256_file(model_config):
        raise ValueError(f'{cancer}/{seed}: 训练所用 model_config 不是获审文件')
    if inputs.get(gpu_config.name) != sha256_file(gpu_config):
        raise ValueError(f'{cancer}/{seed}: 训练所用 gpu_config 不是获审文件')
    if label_sha not in inputs.values():
        raise ValueError(f'{cancer}/{seed}: 训练标签与历史标签不同')
    # 训练入口在写记录前把模态路径 resolve 成绝对路径（training/runtime.py 的 modality.path 赋值，软链已解析），
    # 所以与本运行根下同一逻辑路径的解析结果比较。只回传逻辑路径与布尔结论，不落绝对路径（仓库公开）。
    logical = contract['text_path'][profile]
    recorded = read_json(Path(run_dir) / 'data_manifest.json').get('modalities', {}).get('text', {}).get('path', '')
    if recorded != str((Path(run_root) / logical).resolve()):
        raise ValueError(f'{cancer}/{seed}: 训练读取的 Text 目录不是本运行根的 {logical}（解析后的实际目录不同）')
    return {'resolved_config_sha256': sha256_file(Path(run_dir) / 'resolved_config.yaml'),
            'text_path': logical, 'text_path_matches_run_root': True}


def check_checkpoints(up, ucfg, config, legacy, *, profile, cancers, seeds, checkpoint_root, commit, run_root) -> dict:
    kind = config['profiles'][profile]['checkpoints']
    result = {}
    for cancer in cancers:
        model = up.rt.build_model(ucfg, cancer, 'cpu')
        legacy_checkpoints = legacy['preflight']['reports'][cancer]['checkpoints']
        states, entries = set(), {}
        for seed in seeds:
            path = up.i01.checkpoint_path(Path(checkpoint_root), cancer, seed)
            if not path.is_file():
                raise FileNotFoundError(f'缺少 ckpt: {cancer}/{seed}')
            file_sha = sha256_file(path)
            state = up.i01.strict_e0_load(model, path, expected_file_sha=file_sha)
            old = legacy_checkpoints[str(seed)]
            entry = {'sha256': file_sha, 'state_sha256': state, 'strict_load': True}
            if kind == 'legacy':
                if file_sha != old['sha256'] or state != old['state_sha256']:
                    raise ValueError(f'{cancer}/{seed}: 不是历史 E0 权重')
            else:
                if file_sha == old['sha256'] or state == old['state_sha256']:
                    raise ValueError(f'{cancer}/{seed}: 仍是历史 E0 权重，新训练未生效')
                run_dir = find_run_record(checkpoint_root, file_sha)
                git = read_json(run_dir / 'git.json')
                if git.get('dirty') is not False:
                    raise ValueError(f'{cancer}/{seed}: 训练运行记录 dirty，结果不得进论文')
                if commit is None or git.get('commit') != commit:
                    raise ValueError(f'{cancer}/{seed}: 训练 commit {git.get("commit")} 不是冻结的 {commit}')
                if not git.get('recorded_at_utc'):
                    raise ValueError(f'{cancer}/{seed}: 训练运行记录缺少 recorded_at_utc')
                entry.update(run_record=run_dir.name, commit=git['commit'], recorded_at_utc=git['recorded_at_utc'],
                             training=check_training_record(run_dir, config, legacy, profile=profile,
                                                            cancer=cancer, seed=seed, run_root=run_root))
            if state in states:
                raise ValueError(f'{cancer}: 跨 seed 出现重复权重')
            states.add(state)
            entries[str(seed)] = entry
        result[cancer] = entries
        del model
        gc.collect()
    return result


# ----------------------------------------------------------------------------- strategy0

def luad_routes(route_module, ids, natural, grid) -> list:
    """按天然可得性（不是遮挡后的掩码）给每位 LUAD 患者定路由。"""
    return [route_module.route_patient(cancer='LUAD', grid=grid, rna_valid=bool(natural[pid]['rna']),
                                       text_valid=bool(natural[pid]['text']))['route'] for pid in ids]


def compose_strategy0(ids, arrays, routes) -> dict:
    """逐患者组合已存的 logits 与 risk_b；arrays 键为 combo/m1/m0real。"""
    key = {'upstream_combo': 'combo', 'm1': 'm1', 'm0real': 'm0real'}
    ids = list(ids)
    if len(routes) != len(ids) or any(route not in key for route in routes):
        raise ValueError('路由列表与患者不符或含未知路由')
    reference = arrays['m1']
    for name, value in arrays.items():
        if np.asarray(value['patient_ids']).tolist() != ids:
            raise ValueError(f'{name}: 患者顺序不一致')
        if (np.asarray(value['logits']).shape != (len(ids), 4)
                or np.asarray(value['risk_b']).shape != (len(ids),)):
            raise ValueError(f'{name}: 预测形状不符')
        for field in ('time', 'censorship'):
            if not np.array_equal(value[field], reference[field]):
                raise ValueError(f'{name}: {field} 与其他臂不一致')
    logits = np.stack([np.asarray(arrays[key[route]]['logits'])[row] for row, route in enumerate(routes)])
    risk = np.asarray([np.asarray(arrays[key[route]]['risk_b'])[row] for row, route in enumerate(routes)],
                      dtype=np.asarray(reference['risk_b']).dtype)
    return {'patient_ids': np.asarray(ids), 'logits': logits, 'risk_b': risk,
            'time': np.asarray(reference['time']), 'censorship': np.asarray(reference['censorship'])}


def c_index_b(time, censorship, risk) -> float:
    """与 run.evaluate_cell 完全相同的 B 口径 C-index 调用。"""
    from sksurv.metrics import concordance_index_censored
    score = float(concordance_index_censored((1 - np.asarray(censorship)).astype(bool), np.asarray(time),
                                             np.asarray(risk))[0])
    if not np.isfinite(score):
        raise ValueError('C-index 不可计算')
    return score


def derive_strategy0(up, *, cancer, seed, grid, relative, cell_dir, payload, ids, natural, combo_id,
                     fingerprint, compute_metric, scorer=c_index_b):
    by_candidate = {row['candidate_id']: row for row in payload['rows']}
    combo = by_candidate[combo_id]
    if cancer != 'LUAD':
        row = dict(combo)
        row.update(protocol='strategy0', candidate_id='strategy0', source_candidate_id=combo_id,
                   source_protocol='combo', strategy0_route='upstream_combo', strategy0_enabled=None,
                   source='I05/frozen-combo', cell=relative)
        return row, None
    routes = luad_routes(up.route, ids, natural, grid)
    counts = dict(Counter(routes))
    s0_dir = Path(cell_dir).parent / f'{grid}.strategy0'
    record_path = s0_dir / 'strategy0.json'
    if record_path.exists():
        record = read_json(record_path)
        for name, expected in record['artifacts'].items():
            if sha256_file(s0_dir / name) != expected:
                raise ValueError(f'{relative}: strategy0 工件损坏')
        if record['run_fingerprint'] != fingerprint or record['route_counts'] != counts:
            raise ValueError(f'{relative}: 已有 strategy0 记录属于另一次运行')
        return record['row'], counts
    arrays = {}
    for name, candidate in (('combo', combo_id), ('m1', 'm1'), ('m0real', 'm0real')):
        with np.load(Path(cell_dir) / by_candidate[candidate]['prediction_file'], allow_pickle=False) as data:
            arrays[name] = {key: data[key] for key in data.files}
    composed = compose_strategy0(ids, arrays, routes)
    s0_dir.mkdir(parents=True, exist_ok=False)
    with (s0_dir / 'strategy0.npz').open('xb') as stream:
        np.savez_compressed(stream, **composed)
    audit = {'candidate_id': 'strategy0', 'grid': grid, 'split': 'test', 'run_fingerprint': fingerprint,
             'patients': [{'patient_id': pid, 'strategy0_route': route, 'strategy0_enabled': True,
                           'natural_valid': natural[pid],
                           'source_candidate_id': combo_id if route == 'upstream_combo' else route}
                          for pid, route in zip(ids, routes)]}
    write_json_exclusive(s0_dir / 'strategy0.audit.json', audit)
    row = {key: combo[key] for key in ('split', 'cancer', 'seed', 'grid', 'n_patients', 'checkpoint_sha256',
                                       'run_fingerprint', 'n_complete_checked', 'complete_max_logit_abs_diff',
                                       'complete_logit_atol')}
    row.update(protocol='strategy0', candidate_id='strategy0', strategy0_enabled=True,
               strategy0_route_counts=counts, source='I05/luad-s0-force', cell=relative,
               prediction_file=f'{grid}.strategy0/strategy0.npz', audit_file=f'{grid}.strategy0/strategy0.audit.json')
    if compute_metric:
        row['c_index_b'] = scorer(composed['time'], composed['censorship'], composed['risk_b'])
    write_json_exclusive(record_path, {
        'run_fingerprint': fingerprint, 'row': row, 'route_counts': counts,
        'artifacts': {name: sha256_file(s0_dir / name) for name in ('strategy0.npz', 'strategy0.audit.json')}})
    return row, counts


# ----------------------------------------------------------------------------- 单元执行

def run_cells(up, ucfg, config, *, stage, directory, cancers, seeds, specs, checkpoints, fingerprint,
              compute_metric, combo_id):
    import torch
    rows, reference_rows, route_counts, natural_missing = [], [], {}, {}
    for cancer in cancers:
        bank, source = up.rt.load_cancer(ucfg, cancer, 'test')
        natural = {pid: {mm: source.features[mm].get(pid) is not None for mm in ('rna', 'text')}
                   for pid in source.ids}
        natural_missing[cancer] = {mm: sum(not value[mm] for value in natural.values()) for mm in ('rna', 'text')}
        ids = up.rt.smoke_ids(source, ucfg) if stage == 'smoke' else list(source.ids)
        for seed in seeds:
            model = before = None
            expected = checkpoints[cancer][str(seed)]
            for grid in config['grids']:
                relative = f'{cancer}/{seed}/{grid}'
                cell_dir = Path(directory) / relative
                expected_cell = {
                    'cancer': cancer, 'seed': seed, 'grid': grid, 'split': 'test', 'ids': ids, 'specs': specs,
                    'checkpoint_sha': expected['sha256'], 'compute_metric': compute_metric,
                    'n_complete_expected': sum(all(natural[pid][mm] for mm in ('rna', 'text')) for pid in ids)
                    if grid == 'none' else 0}
                if (cell_dir / 'cell.json').exists():
                    payload = up.rt.verify_cell(cell_dir, fingerprint, expected=expected_cell)
                else:
                    if cell_dir.exists():
                        quarantine = Path(directory) / 'incomplete' / (relative.replace('/', '-') + '-' + uuid.uuid4().hex)
                        quarantine.parent.mkdir(parents=True, exist_ok=True)
                        cell_dir.rename(quarantine)
                    if model is None:
                        model = up.rt.build_model(ucfg, cancer, ucfg['runtime']['device'])
                        path = up.i01.checkpoint_path(Path(ucfg['paths']['checkpoint_root']), cancer, seed)
                        state = up.i01.strict_e0_load(model, path, expected_file_sha=expected['sha256'])
                        if state != expected['state_sha256']:
                            raise ValueError('实际加载的权重不同于前置核验')
                        model.to(ucfg['runtime']['device']).eval()
                        before = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
                    payload = up.run.evaluate_cell(ucfg, bank, source, model, specs, ids, cancer=cancer, seed=seed,
                                                   grid=grid, directory=cell_dir, fingerprint=fingerprint,
                                                   checkpoint_sha=expected['sha256'], compute_metric=compute_metric)
                    up.rt.verify_cell(cell_dir, fingerprint, expected=expected_cell)
                by_candidate = {row['candidate_id']: row for row in payload['rows']}
                for arm in ('m1', 'm0real'):
                    rows.append({**by_candidate[arm], 'cell': relative})
                reference_rows.append({**by_candidate[combo_id], 'cell': relative})
                s0_row, counts = derive_strategy0(up, cancer=cancer, seed=seed, grid=grid, relative=relative,
                                                  cell_dir=cell_dir, payload=payload, ids=ids, natural=natural,
                                                  combo_id=combo_id, fingerprint=fingerprint,
                                                  compute_metric=compute_metric)
                rows.append(s0_row)
                if counts is not None:
                    route_counts[f'{seed}/{grid}'] = counts
                print(f'{stage} {relative}: {len(ids)} 名患者完成', flush=True)
            if model is not None:
                if any(not torch.equal(value.detach().cpu(), before[key]) for key, value in model.state_dict().items()):
                    raise ValueError('前向改变了 state_dict，禁止提交结果')
                del model, before
        del bank, source
        gc.collect()
    return rows, reference_rows, route_counts, natural_missing


# ----------------------------------------------------------------------------- 回放比对

def _index_rows(rows):
    return {(row['cancer'], int(row['seed']), row['grid'], row['protocol']): float(row['c_index_b'])
            for row in rows if row['protocol'] in REPORTED_PROTOCOLS}


def artifact_parity(stage_dir, legacy_2p, legacy_4p, *, cancers, seeds, grids, combo_id, atol=1e-6) -> dict:
    """跨硬件时逐 logit、逐审计字段比对历史工件：logits ≤ atol，donor/mask/路由完全一致。"""
    maximum, mismatches, details = 0.0, 0, []
    for cancer in cancers:
        for seed in seeds:
            for grid in grids:
                pairs = [(Path(stage_dir) / cancer / str(seed) / grid / f'{candidate}.npz',
                          Path(legacy_2p) / cancer / str(seed) / grid / f'{candidate}.npz') for candidate in
                         ('m0real', 'm1', combo_id)]
                if cancer == 'LUAD':
                    pairs.append((Path(stage_dir) / cancer / str(seed) / f'{grid}.strategy0' / 'strategy0.npz',
                                  Path(legacy_4p) / cancer / str(seed) / grid / 'strategy0.npz'))
                for new_path, old_path in pairs:
                    with np.load(new_path, allow_pickle=False) as new, np.load(old_path, allow_pickle=False) as old:
                        if new['patient_ids'].tolist() != old['patient_ids'].tolist():
                            mismatches += 1
                            details.append({'file': str(new_path.relative_to(stage_dir)), 'reason': '患者顺序不一致'})
                            continue
                        difference = float(np.max(np.abs(new['logits'].astype(np.float64) - old['logits'])))
                    maximum = max(maximum, difference)
                    new_audit = read_json(new_path.with_suffix('.audit.json'))['patients']
                    old_audit = read_json(old_path.with_suffix('.audit.json'))['patients']
                    fields = ('strategy0_route',) if new_path.name == 'strategy0.npz' else AUDIT_FIELDS
                    if [[record.get(field) for field in fields] for record in new_audit] != \
                            [[record.get(field) for field in fields] for record in old_audit]:
                        mismatches += 1
                        details.append({'file': str(new_path.relative_to(stage_dir)), 'reason': 'donor/mask/路由不一致'})
    return {'ok': mismatches == 0 and maximum <= atol, 'max_logit_abs_diff': maximum, 'atol': atol,
            'audit_mismatches': mismatches, 'details': details[:20]}


def compare_replay(new_rows, legacy_rows, *, tier, parity=None) -> dict:
    """按事先分档的容差比对回放（坑 I01-R15-06）：同主机须逐值相同；跨硬件看工件级一致。"""
    if tier not in REPLAY_TIERS:
        raise ValueError(f'未知回放分档: {tier}')
    new, old = _index_rows(new_rows), _index_rows(legacy_rows)
    if set(new) != set(old):
        return {'status': 'FAIL', 'tier': tier, 'reason': '格点集合与历史不一致',
                'missing': len(set(old) - set(new)), 'extra': len(set(new) - set(old))}
    differences = [{'cancer': key[0], 'seed': key[1], 'grid': key[2], 'protocol': key[3], 'legacy': old[key],
                    'replay': new[key], 'delta': new[key] - old[key]} for key in sorted(new) if new[key] != old[key]]
    parity_report = None
    if not differences:
        status = 'IDENTICAL'
    elif tier == 'same-host':
        status = 'FAIL'
    else:
        parity_report = parity() if parity is not None else {'ok': False, 'reason': '未提供工件级比对'}
        status = 'PASS_WITH_FLOAT_DIFFS' if parity_report['ok'] else 'FAIL'
    return {'status': status, 'tier': tier, 'n_rows': len(new), 'n_different': len(differences),
            'max_abs_delta': max((abs(item['delta']) for item in differences), default=0.0),
            'differences': differences, 'artifact_parity': parity_report}


# ----------------------------------------------------------------------------- 门

REBIND_KIND = 'review_rebind'


def _is_sha1(value) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(char in '0123456789abcdef' for char in value)


def check_review_rebind(rebind_record, *, review_record, review_commit, commit) -> str:
    """审查发生在候选 H、正式运行在 squash 后的 S（Codex 首审 finding 1）：换绑记录由
    tools/rebind_review.py 在有 .git 的机器上生成，证明 tree(H) == tree(S) 并绑定这份审查记录。
    服务器上没有 .git，无法重算 tree；因此换绑记录的 sha256 还必须写进用户授权记录。返回其 sha256。"""
    if rebind_record is None:
        raise ValueError('审查记录绑定的 commit 与冻结 commit 不同：需要 --review-rebind-record（tree(H)=tree(S) 的换绑记录）')
    rebind = read_json(rebind_record)
    expected = {'kind': REBIND_KIND, 'review_record_sha256': sha256_file(review_record),
                'review_commit': review_commit, 'commit': commit}
    mismatched = sorted(key for key, value in expected.items() if rebind.get(key) != value)
    if mismatched:
        raise ValueError(f'换绑记录与本次审查记录或冻结 commit 不符: {mismatched}')
    tree, review_tree = rebind.get('commit_tree'), rebind.get('review_tree')
    if not (_is_sha1(tree) and _is_sha1(review_tree)) or tree != review_tree:
        raise ValueError('换绑记录没有证明 tree(审查 commit) == tree(冻结 commit)，需要在冻结 commit 上重审')
    return sha256_file(rebind_record)


def runtime_digest(ucfg) -> str:
    """评测 runtime 的规范化摘要（不含阶段名与物理卡号）；正式 test 授权绑定它。"""
    return digest_json({key: value for key, value in ucfg['runtime'].items() if key not in ('stage', 'gpu_id')})


def check_test_gates(*, replay_record, review_record, approval_record, source_digest, protocol_id, commit,
                     checkpoints_digest=None, assets_lock_sha256=None, runtime_sha256=None,
                     rebind_record=None) -> dict:
    """test 阶段必须同时具备：同源码的回放 PASS、Codex 审查 PASS、用户授权。审查记录不由 Claude 代写。

    审查记录的 commit 可以是候选 H（审查先于 squash），此时必须附 H→S 换绑记录，且用户授权记录要引用它。
    用户授权还绑定本轮 ckpt 集合摘要与资产锁（Codex I06 节点一 finding 1）：换一套 ckpt 必须重新授权；
    runtime 也写进授权且 test 禁止 CLI 覆盖（round2 R1），ckpt、源码、runtime 全部锁定后重跑 test 结果相同，
    不产生择优空间。"""
    if not (replay_record and review_record and approval_record):
        raise ValueError('test 需要 --replay-record、--review-record、--user-approval-record 三份记录')
    replay = read_json(replay_record)
    if replay.get('status') not in PASSING_REPLAY or replay.get('source_hashes_sha256') != source_digest:
        raise ValueError('回放未通过，或回放记录对应的源码与当前不同')
    review = read_json(review_record)
    if review.get('reviewer') != 'Codex' or review.get('decision') != 'PASS':
        raise ValueError('需要 reviewer=Codex、decision=PASS 的审查记录')
    if review.get('source_hashes_sha256') != source_digest or review.get('protocol_id') != protocol_id:
        raise ValueError('审查记录绑定的源码或协议与当前不同，需要重审')
    review_commit = review.get('commit')
    if not _is_sha1(review_commit):
        raise ValueError('审查记录缺少完整的 commit')
    rebind_sha = None
    if review_commit != commit:
        rebind_sha = check_review_rebind(rebind_record, review_record=review_record, review_commit=review_commit,
                                         commit=commit)
    elif rebind_record is not None:
        raise ValueError('审查记录已直接绑定冻结 commit，不应再给换绑记录')
    approval = read_json(approval_record)
    expected = {'authority': 'user', 'decision': 'APPROVE_FORMAL_TEST', 'stage': 'test', 'protocol_id': protocol_id,
                'source_hashes_sha256': source_digest, 'commit': commit,
                'review_record_sha256': sha256_file(review_record), 'rebind_record_sha256': rebind_sha,
                'checkpoints_sha256': checkpoints_digest, 'assets_lock_sha256': assets_lock_sha256,
                'runtime_sha256': runtime_sha256}
    mismatched = sorted(key for key, value in expected.items() if approval.get(key) != value)
    if mismatched or not str(approval.get('approved_at', '')).strip():
        raise ValueError(f'用户授权记录不属于本轮正式评测: {mismatched or ["approved_at"]}')
    return {'replay_record_sha256': sha256_file(replay_record), 'review_record_sha256': sha256_file(review_record),
            'rebind_record_sha256': rebind_sha, 'user_approval_sha256': sha256_file(approval_record)}


# ----------------------------------------------------------------------------- 入口

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--run-root', type=Path, required=True, help='含 data/ 与 tmp_sur_cache/ 的运行根')
    parser.add_argument('--execution-root', type=Path, required=True, help='输出根，须在运行根与 ckpt 根之外')
    parser.add_argument('--checkpoint-root', type=Path, help='训练 --result-path；preflight 起必填')
    parser.add_argument('--cancers', nargs='+', help='仅 assets/preflight/smoke 可取子集')
    parser.add_argument('--seeds', nargs='+', type=int, help='仅 preflight/smoke 可取子集')
    parser.add_argument('--device', choices=('cpu', 'cuda'), help='实验必须 cuda；cpu 只用于替身证据的本地合成测试')
    parser.add_argument('--gpu-id', type=int)
    parser.add_argument('--retrieval-backend', choices=('reference', 'gpu_cached'))
    parser.add_argument('--batch-size', type=int)
    parser.add_argument('--cpu-threads', type=int)
    parser.add_argument('--expected-commit', help='只作核对：必须等于当前源码身份（.git HEAD 或 GIT_STAMP.json），不能改写它')
    parser.add_argument('--assets-lock', type=Path,
                        help='训练前 assets 阶段写出的 assets-lock.json；新训练 ckpt 的档案从 preflight 起必需')
    parser.add_argument('--legacy-preflight', type=Path, help='只允许 assets/preflight/smoke 覆盖')
    parser.add_argument('--legacy-valid-source', type=Path, help='只允许 assets/preflight/smoke 覆盖')
    parser.add_argument('--legacy-cache-dir', type=Path, help='img/rna 字节不同时按内容比对的历史缓存目录')
    parser.add_argument('--replay-tier', choices=REPLAY_TIERS)
    parser.add_argument('--replay-record', type=Path)
    parser.add_argument('--review-record', type=Path)
    parser.add_argument('--review-rebind-record', type=Path,
                        help='审查记录绑定候选 H 时必需：tools/rebind_review.py 生成的 tree(H)=tree(S) 换绑记录')
    parser.add_argument('--user-approval-record', type=Path)
    parser.add_argument('--allow-dirty', action='store_true', help='只允许非正式阶段；结果不得进论文')
    return parser


def _validate_args(args, config):
    full = args.stage in ('replay', 'test')
    if args.stage == 'replay' and args.profile != 'legacy-replay':
        raise ValueError('replay 只接受 legacy-replay 档案')
    if args.stage == 'test' and args.profile == 'legacy-replay':
        raise ValueError('legacy-replay 档案只用于回放，不产生正式结果')
    if args.stage == 'replay' and args.replay_tier is None:
        raise ValueError('replay 必须显式给出 --replay-tier')
    if full and (args.cancers or args.seeds):
        raise ValueError('replay/test 必须完整五癌五 seed，不得取子集')
    overrides = [flag for flag, value in (('--retrieval-backend', args.retrieval_backend),
                                          ('--batch-size', args.batch_size), ('--cpu-threads', args.cpu_threads))
                 if value is not None]
    if args.stage == 'test' and overrides:  # Codex I06 节点一 round2 R1：一份授权只对应一套锁定 runtime
        raise ValueError(f'正式 test 不接受 runtime 覆盖参数（只用 config 锁定值）: {overrides}')
    if args.stage == 'assets' and args.seeds:
        raise ValueError('assets 不涉及 seed')
    if full and (args.legacy_preflight or args.legacy_valid_source):
        raise ValueError('replay/test 不得覆盖历史证据路径')
    if full and args.allow_dirty:
        raise ValueError('replay/test 不得放行 dirty')
    if args.stage != 'assets' and args.checkpoint_root is None:
        raise ValueError('preflight 起必须提供 --checkpoint-root')
    cancers = args.cancers or list(config['cancers'])
    seeds = args.seeds or list(config['seeds'])
    if not set(cancers) <= set(config['cancers']) or len(set(cancers)) != len(cancers):
        raise ValueError('非法或重复的癌种')
    if not set(seeds) <= set(config['seeds']) or len(set(seeds)) != len(seeds):
        raise ValueError('非法或重复的 seed')
    if args.stage == 'smoke' and config['smoke']['seed'] not in seeds:
        raise ValueError('smoke 的 seed 必须包含 config.smoke.seed')
    device = args.device or config['runtime']['device']
    synthetic = args.legacy_preflight is not None or args.legacy_valid_source is not None
    if args.stage in ('smoke', 'replay', 'test') and not (synthetic and ALLOW_CPU_FOR_SYNTHETIC_TESTS):
        gpu_policy.require_gpu(device)
        if args.gpu_id is None:
            raise ValueError('GPU 运行必须用 --gpu-id 指定物理卡号（先用 tools/gpu_survey.py 选卡）')
    return cancers, seeds


def _protect_outputs(run_root, execution_root, checkpoint_root, config):
    protected = [run_root / config['assets']['cache_dir'], run_root / 'data']
    if checkpoint_root is not None:
        protected.append(checkpoint_root)
    for item in protected:
        item = item.resolve()
        if execution_root == item or execution_root.is_relative_to(item) or item.is_relative_to(execution_root):
            raise ValueError(f'输出根不得位于或包含受保护目录: {item}')


def check_run_root_layout(run_root, config, *, profile) -> dict:
    """冻结 run worktree 只读：可变资产（缓存、新特征）必须经符号链接落在工作树之外。

    以 GIT_STAMP.json 或 .git 识别冻结工作树；合成测试根没有这两个标记，不受此门约束。
    只记录布尔结论，不记录解析后的绝对路径（仓库公开）。
    """
    run_root = Path(run_root).resolve()
    frozen = (run_root / 'GIT_STAMP.json').exists() or (run_root / '.git').exists()
    report = {'frozen_worktree': frozen}
    if not frozen:
        return report
    encoder = config['text_encoders'].get(profile)
    checks = [('cache_dir', config['assets']['cache_dir'])]
    if encoder is not None:  # legacy 档案不读新特征目录
        checks.append(('feature_dir', encoder['feature_dir']))
    else:
        report['feature_dir_external'] = None
    for key, relative in checks:
        path = run_root / relative
        if not path.exists():  # 缺失的必需资产由 check_assets 报错
            report[f'{key}_external'] = None
            continue
        target = path.resolve()
        if target == run_root or target.is_relative_to(run_root):
            raise ValueError(f'{relative} 解析后仍在冻结工作树内；须改为指向外部可变资产根的符号链接')
        report[f'{key}_external'] = True
    return report


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    cancers, seeds = _validate_args(args, config)
    verify_pins(config)
    spec = frozen_spec(config)
    if config['profiles'][args.profile]['text_cache'] == 'new':
        encoder_model.spec_from_config(config, args.profile)
    identity = source_identity(identity_closure(config), allow_dirty=args.allow_dirty)
    commit, commit_source = resolve_expected_commit(args.expected_commit, identity)
    up = Upstream(config)
    check_route_table(up.route, config)
    run_root, execution_root = args.run_root.resolve(), args.execution_root.resolve()
    checkpoint_root = args.checkpoint_root.resolve() if args.checkpoint_root else None
    _protect_outputs(run_root, execution_root, checkpoint_root, config)
    layout = check_run_root_layout(run_root, config, profile=args.profile)
    runtime = config['runtime']
    device = args.device or runtime['device']
    ucfg = build_upstream_config(config, run_root=run_root, checkpoint_root=checkpoint_root,
                                 execution_root=execution_root, device=device, gpu_id=args.gpu_id,
                                 retrieval_backend=args.retrieval_backend or runtime['retrieval_backend'],
                                 batch_size=args.batch_size or runtime['batch_size'],
                                 cpu_threads=args.cpu_threads or runtime['cpu_threads'])
    stage_dir = execution_root / 'runs' / args.stage
    up.rt.check_output_boundary(stage_dir, [checkpoint_root, run_root / config['assets']['cache_dir']],
                                execution_root)
    legacy = load_legacy(config, preflight_override=args.legacy_preflight,
                         valid_override=args.legacy_valid_source)
    source_hashes = {**up.rt.source_hashes(ucfg), **i05_source_hashes()}
    source_digest = digest_json(source_hashes)
    protocol_id = config['protocol_ids'][args.profile]
    assets = check_assets(config, legacy, run_root=run_root, profile=args.profile, cancers=cancers,
                          legacy_cache_dir=args.legacy_cache_dir)
    new_checkpoints = config['profiles'][args.profile]['checkpoints'] != 'legacy'

    def status(name):  # 替身历史证据的输出永远带 _SYNTHETIC，不能冒充正式放行
        return name + ('_SYNTHETIC' if legacy['overridden'] else '')

    base = {'protocol_id': protocol_id, 'profile': args.profile, 'cancers': cancers,
            'source_hashes_sha256': source_digest, 'assets_sha256': digest_json(assets),
            'legacy_overridden': legacy['overridden'], 'run_root_layout': layout,
            'git': {key: identity.get(key) for key in ('source', 'commit', 'branch', 'dirty', 'allow_dirty')}}
    if args.stage == 'assets':
        reserve_json(stage_dir / 'assets.json', {**base, 'status': status('ASSETS_VERIFIED'), 'assets': assets})
        lock = (write_assets_lock(stage_dir, protocol_id=protocol_id, profile=args.profile, commit=commit,
                                  assets=assets) if new_checkpoints else None)
        print(json.dumps({'stage': 'assets', 'status': status('ASSETS_VERIFIED'), 'profile': args.profile,
                          'assets_lock_sha256': lock and lock['assets_lock_sha256']}, ensure_ascii=False))
        return 0
    checkpoints = check_checkpoints(up, ucfg, config, legacy, profile=args.profile, cancers=cancers, seeds=seeds,
                                    checkpoint_root=checkpoint_root, commit=commit, run_root=run_root)
    assets_lock = (check_assets_lock(args.assets_lock, protocol_id=protocol_id, profile=args.profile, commit=commit,
                                     assets=assets, checkpoints=checkpoints) if new_checkpoints else None)
    base.update(seeds=seeds, checkpoints=checkpoints, assets_lock=assets_lock, expected_commit=commit,
                expected_commit_source=commit_source,
                frozen_combo_spec=spec, s0_force=config['s0_force'], shapes=config['shapes'],
                grids=config['grids'], numerics=config['numerics'], model=config['model'],
                runtime={key: value for key, value in ucfg['runtime'].items() if key != 'stage'})
    if args.stage == 'preflight':
        reserve_json(stage_dir / 'preflight.json', {**base, 'status': status('READY'), 'assets': assets,
                                                    'source_hashes': source_hashes})
        print(json.dumps({'stage': 'preflight', 'status': status('READY'), 'source_hashes_sha256': source_digest,
                          'checkpoints_sha256': digest_json(checkpoints),
                          'assets_lock_sha256': assets_lock and assets_lock['assets_lock_sha256'],
                          'runtime_sha256': runtime_digest(ucfg)},
                         ensure_ascii=False))
        return 0
    gates = None
    if args.stage == 'test':
        gates = check_test_gates(replay_record=args.replay_record, review_record=args.review_record,
                                 approval_record=args.user_approval_record, source_digest=source_digest,
                                 protocol_id=protocol_id, commit=commit, checkpoints_digest=digest_json(checkpoints),
                                 assets_lock_sha256=assets_lock and assets_lock['assets_lock_sha256'],
                                 runtime_sha256=runtime_digest(ucfg), rebind_record=args.review_rebind_record)
    compute_metric = args.stage != 'smoke'
    if device == 'cuda':
        # I05 的选卡规则（空闲卡优先，其次利用率 < 70% 的在用卡）取代上游只认空闲卡的门禁。
        device_record = gpu_policy.gate(args.gpu_id, config['gpu_policy'])
    else:
        if not (legacy['overridden'] and ALLOW_CPU_FOR_SYNTHETIC_TESTS):
            raise ValueError('禁止 CPU 运行（用户锁定）；CPU 只留给测试注入的合成运行')
        device_record = {'device': 'cpu', 'gpu_gate': 'SYNTHETIC_TEST_ONLY'}
    import torch
    torch.set_num_threads(ucfg['runtime']['cpu_threads'])
    environment = up.rt.environment() if compute_metric else {'numpy': np.__version__, 'torch': torch.__version__}
    specs = [up.rt.baseline_spec('m0real'), up.rt.baseline_spec('m1'), spec]
    campaign = {**base, 'stage': args.stage, 'specs': specs, 'environment': environment}
    fingerprint = digest_json(campaign)
    reserve_json(stage_dir / 'campaign.json', campaign)
    rows, reference_rows, route_counts, natural_missing = run_cells(
        up, ucfg, config, stage=args.stage, directory=stage_dir, cancers=cancers, seeds=seeds, specs=specs,
        checkpoints=checkpoints, fingerprint=fingerprint, compute_metric=compute_metric,
        combo_id=spec['candidate_id'])
    if args.stage in ('replay', 'test'):
        legacy_test = load_legacy_test_complete(config)
        for cancer in cancers:
            if natural_missing[cancer] != legacy['preflight']['reports'][cancer]['natural_test_missing']:
                raise ValueError(f'{cancer}: 运行中天然缺失人数与历史不一致')
        if route_counts != legacy_test['luad_route_counts']:
            raise ValueError('LUAD 路由计数与历史不一致：天然缺失口径发生了变化')
    verify_pins(config)
    if {**up.rt.source_hashes(ucfg), **i05_source_hashes()} != source_hashes:
        raise ValueError('运行期间源码发生变化')
    summary = {'stage': args.stage, 'profile': args.profile, 'protocol_id': protocol_id,
               'status': status('SMOKE_PASS' if args.stage == 'smoke' else 'COMPLETED'), 'run_fingerprint': fingerprint,
               'rows': rows, 'reference_rows': reference_rows, 'luad_route_counts': route_counts,
               'natural_test_missing': natural_missing, 'source_hashes_sha256': source_digest,
               'source_hashes': source_hashes, 'checkpoints': checkpoints, 'device': device_record,
               'metrics_computed': compute_metric, 'state_dict_unchanged': True, 'gates': gates}
    reserve_json(stage_dir / 'complete.json', summary)
    if args.stage == 'replay':
        legacy_test = load_legacy_test_complete(config)
        comparison = compare_replay(
            rows, legacy_test['rows'], tier=args.replay_tier,
            parity=lambda: artifact_parity(stage_dir, REPO_ROOT / config['legacy']['artifacts_2progress'],
                                           REPO_ROOT / config['legacy']['artifacts_4progress'], cancers=cancers,
                                           seeds=seeds, grids=config['grids'], combo_id=spec['candidate_id']))
        comparison.update(source_hashes_sha256=source_digest, protocol_id=protocol_id, run_fingerprint=fingerprint)
        reserve_json(stage_dir / 'replay-comparison.json', comparison)
        print(json.dumps({'stage': 'replay', 'status': comparison['status'],
                          'n_different': comparison['n_different']}, ensure_ascii=False))
        return 0 if comparison['status'] in PASSING_REPLAY else 2
    print(json.dumps({'stage': args.stage, 'status': summary['status'], 'rows': len(rows)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
