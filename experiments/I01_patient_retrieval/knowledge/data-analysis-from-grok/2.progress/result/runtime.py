"""本轮零训练评测的共享契约：只读资产、显式 split、运行门与冻结证据。"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import platform
import sys
import uuid
from pathlib import Path

import numpy as np

BASELINES = ('m0real', 'm1', 'retrieval')
ROOT = Path(__file__).resolve().parent


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def write_json_new(path, value):
    """先序列化再排他写入；不覆盖历史或已完成单元。"""
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        stream.write(body + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    # 同目录硬链接为原子且不覆盖的发布；失败时保留临时证据，没有半写完成标记。
    os.link(temporary, path)
    temporary.unlink()


def read_verified_json(path, expected_sha):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError('文件指纹变化，禁止复用冻结证据')
    return json.loads(data)


def validate_config(config):
    """固定科学协议是边界，不接受CLI悄悄换参数。"""
    expected = {
        'schema_version': 1,
        'protocol_id': 'patient-fixed-padmask-v2-infer-rules1to5-v1',
        'base_protocol_id': 'patient-fixed-padmask-v2',
        'prototype_k': 128,
        'cancers': ['BLCA', 'BRCA', 'LGG', 'LUAD', 'UCEC'],
        'seeds': [123, 132, 213, 231, 321],
        'grids': ['none', 'rna_100', 'text_100', 'both_100'],
        'rules': ['01_text100_skip_compensate', '02_wsi_meanpool_key',
                  '03_shrinkage_lambda', '04_wsi_rna_joint_sim', '05_imputed_token_downweight'],
        'search': {'lambda_grid': [0, .25, .5, .75, 1],
                   'alpha_grid': [.5, 1, 2], 'weight_grid': [.2, .3, .5]},
        'numerics': {'norm_epsilon': 1e-12, 'logit_atol': 1e-6,
                     'logit_rtol': 0, 'risk_clamp': 1e-6},
        'shapes': {'img': [128, 1536], 'text': [200, 768], 'rna': [2048, 256]},
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f'锁定配置不符: {key}')
    allowed = set(expected) | {'model', 'runtime', 'smoke', 'paths', 'authorization',
                               'baseline_source_sha256'}
    if set(config) != allowed:
        raise ValueError(f'未知或缺失配置字段: {set(config) ^ allowed}')
    model = config['model']
    if model != {'network_type': 'NPJC', 'compensator': 'none', 'hidden_size': 256,
                 'pred_dim': 4, 'dropout_rate': .1, 'mlp_ratio': 4,
                 'n_backbone': 1, 'n_head': 4, 'modality_order': ['img', 'text', 'rna']}:
        raise ValueError('禁止改变模型结构或增加compensator')
    runtime = config['runtime']
    if runtime.get('retrieval_backend', 'reference') not in ('reference', 'gpu_cached'):
        raise ValueError('非法检索计算后端')
    if runtime.get('retrieval_backend') == 'gpu_cached' and runtime['device'] != 'cuda':
        raise ValueError('gpu_cached 正式运行须使用 CUDA')
    if runtime['stage'] not in ('report', 'preflight', 'smoke', 'valid', 'test'):
        raise ValueError('非法阶段')
    if runtime['device'] not in ('cpu', 'cuda') or runtime['forward_dtype'] != 'float32':
        raise ValueError('只支持锁定的FP32推理')
    if any(type(runtime[k]) is not int or runtime[k] < 1 for k in ('batch_size', 'cpu_threads')):
        raise ValueError('非法batch_size/cpu_threads')
    if runtime['num_workers'] != 0 or runtime['persistent_workers']:
        raise ValueError('冻结缓存直接分批，无DataLoader worker')
    if config['smoke']['seed'] not in config['seeds'] or config['smoke']['base_ids'] < 1:
        raise ValueError('非法冒烟配置')
    return config


def load_config(path):
    # JSON是YAML的合法子集；使用显式文件，不依赖环境里是否安装PyYAML。
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    return validate_config(value)


def setup_imports(config):
    repo = Path(config['paths']['repo_root']).resolve()
    sys.path[:0] = [str(repo / 'src'), str(repo), str(ROOT)]


def science_config(config):
    """阶段/目录不影响科研身份；计算精度和batch配置仍绑定冻结记录。"""
    keys = ('protocol_id', 'base_protocol_id', 'cancers', 'seeds', 'grids',
            'prototype_k', 'rules', 'search', 'numerics', 'shapes', 'model')
    result = {key: copy.deepcopy(config[key]) for key in keys}
    result['runtime'] = {k: v for k, v in config['runtime'].items() if k != 'stage'}
    return result


def source_hashes(config):
    repo = Path(config['paths']['repo_root'])
    result = {}
    for relative, expected in config['baseline_source_sha256'].items():
        actual = file_sha256(repo / relative)
        if actual != expected:
            raise ValueError(f'公共源码已改变: {relative}')
    for path in sorted((repo / 'src' / 'trimodalsurv').rglob('*.py')):
        # AppleDouble及隐藏目录不是执行源码，不能混入跨平台审计指纹。
        if any(part.startswith('.') for part in path.relative_to(repo / 'src' / 'trimodalsurv').parts):
            continue
        result['repo/' + path.relative_to(repo).as_posix()] = file_sha256(path)
    for name in ('model.py', 'evaluate.py', 'config.yaml'):
        relative = 'experiments/I01_patient_retrieval/' + name
        result['repo/' + relative] = file_sha256(repo / relative)
    # 只绑定可执行实现及规则配置，不把随执行更新的报告/日志放进源码指纹。
    for path in sorted(ROOT.glob('*.py')):
        if path.name.startswith('.'):
            continue
        result['rules/' + path.name] = file_sha256(path)
    for folder in config['rules']:
        for name in ('model.py', 'config.yaml'):
            path = ROOT / folder / name
            result['rules/' + folder + '/' + name] = file_sha256(path)
    return result


def require_authorization(config, stage, sources):
    if stage not in ('valid', 'test'):
        return True
    if config['authorization'].get('formal_approved') is not True:
        raise ValueError('正式 valid/test 未获用户明确授权')
    paths = config['paths']
    if config['authorization'].get('review_waived_by_user') is True:
        # 用户明确豁免必须单独留痕；绝不伪装为Claude的PASS。
        if not paths.get('review_waiver_record') or not paths.get('user_approval_record'):
            raise ValueError('缺少用户豁免或正式授权记录')
        waiver = json.loads(Path(paths['review_waiver_record']).read_text())
        approval_path = Path(paths['user_approval_record'])
        if (waiver.get('authority') != 'user'
                or waiver.get('decision') != 'WAIVE_CLAUDE_REVIEW'
                or waiver.get('protocol_id') != config['protocol_id']
                or stage not in waiver.get('stages', [])
                or waiver.get('source_hashes') != sources
                or waiver.get('approval_sha256') != file_sha256(approval_path)
                or not approval_path.read_text().strip()):
            raise ValueError('用户豁免未绑定当前协议、阶段、源码或授权')
        return True
    if not paths.get('review_record') or not paths.get('user_approval_record'):
        raise ValueError('正式运行缺少Claude审查记录或用户授权记录')
    review = json.loads(Path(paths['review_record']).read_text())
    approval = Path(paths['user_approval_record']).read_text().strip()
    if review.get('reviewer') != 'Claude' or review.get('decision') != 'PASS' or not approval:
        raise ValueError('正式运行审核/授权未通过')
    if review.get('source_hashes') != sources:
        raise ValueError('审核对应源码指纹已改变，需要重审')
    return True


def check_output_boundary(output, protected_roots, execution_root):
    output = Path(output).resolve()
    execution_root = Path(execution_root).resolve()
    if output == execution_root or not output.is_relative_to(execution_root):
        raise ValueError('输出必须是本轮execution_root的独立子目录')
    for item in protected_roots:
        if item is None:
            continue
        protected = Path(item).resolve()
        if output == protected or output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('输出侵入或覆盖受保护资产目录')


def baseline_spec(arm):
    if arm not in BASELINES:
        raise ValueError('非法固定参考')
    return {'protocol': arm, 'candidate_id': arm, 'enabled_rules': [],
            'lambda': 1., 'alpha': 0., 'w': 1., 'ucec_exception': False}


def read_split_labels(path, cancer):
    from experiments.I01_patient_retrieval.model import validate_splits
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        needed = {'patient_id', 'cancer_type', 'split', 'survival_months', 'censorship'}
        if not needed.issubset(reader.fieldnames or []):
            raise ValueError('标签CSV缺字段')
        rows = list(reader)
    ids = [r['patient_id'] for r in rows]
    if len(ids) != len(set(ids)) or any(not x.strip() for x in ids):
        raise ValueError('标签患者ID重复或为空')
    selected = [r for r in rows if r['cancer_type'] == cancer]
    if any(r['split'] not in ('train', 'valid', 'test') for r in selected):
        raise ValueError('非法split')
    per_split = {s: [r for r in selected if r['split'] == s] for s in ('train', 'valid', 'test')}
    splits = validate_splits({s: [r['patient_id'] for r in value] for s, value in per_split.items()})
    if not all(splits.values()):
        raise ValueError('癌种存在空split')
    return splits, per_split


class QuerySource:
    """独立valid/test消费者，拒绝将旧test硬编码带入选参。"""

    def __init__(self, bank, features, labels, split, grids):
        from experiments.I01_patient_retrieval.model import _numeric
        if split not in ('valid', 'test'):
            raise ValueError('只允许valid/test查询')
        self.bank, self.features, self.split, self.grids = bank, features, split, tuple(grids)
        self.labels = {r['patient_id']: r for r in labels}
        self.ids = sorted(self.labels)
        if len(self.ids) != len(labels) or set(self.ids) != set(bank.splits[split]):
            raise ValueError('查询标签与显式split不一致')
        allowed = set(self.ids)
        for mm, data in features.items():
            if not isinstance(data, dict) or not set(data).issubset(allowed):
                raise ValueError('查询缓存跨split或schema错误')
        for pid in self.ids:
            if features['img'].get(pid) is None:
                raise ValueError('缺WSI，禁止跳患者')
            bank.validate_query(pid, features['img'][pid], query_split=split)
            time, censor = float(self.labels[pid]['survival_months']), float(self.labels[pid]['censorship'])
            if not np.isfinite(time) or time < 0 or censor not in (0, 1):
                raise ValueError('非法生存标签')
            for mm in ('rna', 'text'):
                if features[mm].get(pid) is not None:
                    _numeric(features[mm][pid], context=f'{mm}/{pid}', shape=bank.shapes[mm])

    def batch(self, ids, grid):
        from trimodalsurv.evaluation.common import masked_modalities
        if grid not in self.grids or len(ids) != len(set(ids)) or not set(ids).issubset(self.ids):
            raise ValueError('非法query batch或场景')
        raw = {'img': np.stack([self.features['img'][pid] for pid in ids]),
               'img_valid': np.ones(len(ids), dtype=bool)}
        natural = {}
        for mm in ('rna', 'text'):
            natural[mm] = np.asarray([self.features[mm].get(pid) is not None for pid in ids])
            valid = natural[mm] & (mm not in masked_modalities(grid))
            raw[mm + '_valid'] = valid
            raw[mm] = np.stack([np.asarray(self.features[mm][pid], dtype=np.float32) if valid[i]
                               else np.zeros(self.bank.shapes[mm], dtype=np.float32)
                               for i, pid in enumerate(ids)])
        return raw, natural


class CompleteDiagnostic:
    """一位完整患者只计一次；没检查绝不写零误差。"""

    def __init__(self, atol, rtol):
        self.atol, self.rtol = atol, rtol
        self.count, self.maximum = 0, None

    def check(self, complete, logits_by_candidate):
        complete = np.asarray(complete, dtype=bool)
        if not complete.any():
            return
        reference = logits_by_candidate['m0real']
        others = [v for k, v in logits_by_candidate.items() if k != 'm0real']
        if not others:
            raise ValueError('缺少对照输出，不能计为完成检查')
        maximum = max(float(np.max(np.abs(v[complete] - reference[complete]))) for v in others)
        if any(not np.isfinite(v).all() or not np.allclose(
                v[complete], reference[complete], atol=self.atol, rtol=self.rtol) for v in others):
            raise ValueError(f'完整输入logits一致性失败: {maximum}')
        self.maximum = maximum if self.maximum is None else max(self.maximum, maximum)
        self.count += int(complete.sum())

    def result(self):
        return {'n_complete_checked': self.count, 'complete_max_logit_abs_diff': self.maximum,
                'complete_logit_atol': self.atol}


def build_model(config, cancer, device='cpu'):
    from types import SimpleNamespace
    from trimodalsurv.models.npjc import NPJC
    spec = config['model']
    modalities = {mm: SimpleNamespace(feature_dim=config['shapes'][mm][-1])
                  for mm in spec['modality_order']}
    return NPJC(device, modalities, hidden_size=spec['hidden_size'], pred_dim=spec['pred_dim'],
                dropout_rate=spec['dropout_rate'], mlp_ratio=spec['mlp_ratio'],
                n_backbone=spec['n_backbone'], n_head=spec['n_head'],
                cancer_types=[cancer], compensator=None).to(device).eval()


def environment():
    import torch
    import sksurv
    return {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__,
            'torch': torch.__version__, 'sksurv': sksurv.__version__,
            'cuda_runtime': torch.version.cuda}


def smoke_ids(source, config):
    from experiments.I01_patient_retrieval.model import valid_row_mask
    chosen = source.ids[:config['smoke']['base_ids']]
    for pattern in ((True, True), (True, False), (False, True), (False, False)):
        found = next((pid for pid in source.ids if tuple(source.features[mm].get(pid) is not None
                        for mm in ('rna', 'text')) == pattern), None)
        if found is not None:
            chosen.append(found)
    if config['smoke']['include_all_padded']:
        chosen += [pid for pid in source.ids if not valid_row_mask(source.features['img'][pid], context=pid).all()]
    return sorted(set(chosen))


def verify_cell(directory, expected_fingerprint, *, expected=None):
    directory = Path(directory).resolve()
    payload = json.loads((directory / 'cell.json').read_text())
    if payload.get('run_fingerprint') != expected_fingerprint or not payload.get('rows'):
        raise ValueError('已完成单元属于不同运行或没有结果')
    for name, expected_sha in payload.get('artifacts', {}).items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or not path.is_file() or file_sha256(path) != expected_sha:
            raise ValueError('已完成单元工件损坏或路径越界')
    if not payload.get('artifacts'):
        raise ValueError('缺少单元工件清单')
    if expected is not None:
        specs = {s['candidate_id']: s for s in expected['specs']}
        rows = payload['rows']
        if len(rows) != len(specs) or {r.get('candidate_id') for r in rows} != set(specs):
            raise ValueError('完成单元的候选全集不符')
        if payload.get('metrics_computed') is not expected['compute_metric']:
            raise ValueError('完成单元的指标阶段不符')
        used_artifacts, diagnostics = set(), set()
        for row in rows:
            spec = specs[row['candidate_id']]
            fields = {k: expected[k] for k in ('cancer','seed','grid','split')}
            fields.update(protocol=spec['protocol'], checkpoint_sha256=expected['checkpoint_sha'],
                          n_patients=len(expected['ids']), run_fingerprint=expected_fingerprint)
            if any(row.get(k) != v for k,v in fields.items()):
                raise ValueError('完成单元身份、患者数或权重不符')
            if ('c_index_b' in row) != expected['compute_metric']:
                raise ValueError('冒烟混入指标或正式格缺指标')
            if expected['compute_metric'] and (not np.isfinite(row['c_index_b']) or not 0 <= row['c_index_b'] <= 1):
                raise ValueError('非法C-index')
            count, maximum = row.get('n_complete_checked'), row.get('complete_max_logit_abs_diff')
            if type(count) is not int or not 0 <= count <= len(expected['ids']):
                raise ValueError('非法完整患者检查人数')
            if (count == 0 and maximum is not None) or (count > 0 and
                    (maximum is None or not np.isfinite(maximum) or not 0 <= maximum <= 1e-6)):
                raise ValueError('非法完整患者检查误差')
            if row.get('complete_logit_atol') != 1e-6:
                raise ValueError('完整患者检查阈值不符')
            if 'n_complete_expected' in expected and count != expected['n_complete_expected']:
                raise ValueError('完整患者检查人数与输入实际可用性不符')
            diagnostics.add((count, maximum))
            for field in ('prediction_file','audit_file'):
                name = row.get(field)
                if name not in payload['artifacts'] or name in used_artifacts:
                    raise ValueError('预测/审计工件缺失或跨候选重复使用')
                used_artifacts.add(name)
            with np.load(directory / row['prediction_file'], allow_pickle=False) as predictions:
                if (predictions['patient_ids'].tolist() != expected['ids'] or
                    predictions['logits'].shape != (len(expected['ids']),4) or
                    not all(np.isfinite(predictions[k]).all() for k in ('logits','risk_b','time','censorship'))):
                    raise ValueError('预测内容与患者全集不符')
            audit = json.loads((directory / row['audit_file']).read_text())
            if (audit.get('spec') != spec or audit.get('split') != expected['split'] or
                audit.get('grid') != expected['grid'] or audit.get('run_fingerprint') != expected_fingerprint or
                [r.get('patient_id') for r in audit.get('patients',[])] != expected['ids']):
                raise ValueError('审计内容与候选/患者全集不符')
        if used_artifacts != set(payload['artifacts']) or len(diagnostics) != 1:
            raise ValueError('工件全集或同格一致性诊断不符')
    return payload


def validate_selection_lock(lock, config, sources, assets, env):
    if lock.get('stage') != 'valid':
        raise ValueError('选择锁必须来自valid')
    expected = {'science_config': science_config(config), 'source_hashes': sources,
                'asset_hashes': assets, 'environment': env}
    for key, value in expected.items():
        if lock.get(key) != value:
            raise ValueError(f'选择锁与当前运行不一致: {key}')


def protected_roots(config):
    paths = config['paths']
    return [paths.get('checkpoint_root'), *paths['cache_roots'].values()]


def stage_directory(config, stage):
    root = Path(config['paths']['execution_root']).resolve()
    target = root / 'runs' / stage
    check_output_boundary(target, protected_roots(config), root)
    return target


def asset_files(config):
    paths = config['paths']
    required = ('checkpoint_root', 'label', 'manifest', 'legacy_reference')
    if any(not paths.get(k) for k in required) or any(not paths['cache_roots'].get(s)
            for s in ('train', 'valid', 'test')):
        raise ValueError('资产路径未配置；禁止冷构建或自动训练')
    result = {'labels': Path(paths['label']), 'manifest': Path(paths['manifest']),
              'legacy_preflight': Path(paths['legacy_reference'])}
    for cancer in config['cancers']:
        for seed in config['seeds']:
            name = f'tcga_uni2_img_1536text_768rna_256_NPJC_{cancer}_surv.pth'
            result[f'checkpoint/{cancer}/{seed}'] = Path(paths['checkpoint_root']) / str(seed) / name
        for split in ('train', 'valid', 'test'):
            for mm in config['shapes']:
                name = f'{mm}_sur_{split}_all_{cancer}.pkl'
                result[f'cache/{split}/{name}'] = Path(paths['cache_roots'][split]) / name
    if paths.get('valid_source_manifest'):
        result['valid_source_manifest'] = Path(paths['valid_source_manifest'])
    for key, path in result.items():
        if not path.is_file():
            raise FileNotFoundError(f'缺少既有资产 {key}: {path}')
    return result


def hash_assets(config):
    return {key: file_sha256(path) for key, path in asset_files(config).items()}


def load_cancer(config, cancer, split):
    from experiments.I01_patient_retrieval.model import FixedPatientBank
    from experiments.I01_patient_retrieval.evaluate import load_cache, validate_manifest
    splits, per_split = read_split_labels(config['paths']['label'], cancer)
    validate_manifest(Path(config['paths']['manifest']), cancer, splits['test'])
    train, _ = load_cache(Path(config['paths']['cache_roots']['train']), cancer, 'train', splits['train'])
    bank = FixedPatientBank(cancer, splits, train, expected_shapes=config['shapes'])
    del train
    features, _ = load_cache(Path(config['paths']['cache_roots'][split]), cancer, split, splits[split])
    if config['runtime'].get('retrieval_backend', 'reference') == 'gpu_cached':
        from acceleration import RetrievalCache
        bank.retrieval_accelerator = RetrievalCache(bank, device=config['runtime']['device'],
            epsilon=config['numerics']['norm_epsilon'])
    return bank, QuerySource(bank, features, per_split[split], split, config['grids'])


def preflight(config, hashes):
    """只检查资产和权重，不算valid/test的C-index。"""
    import gc
    from experiments.I01_patient_retrieval.evaluate import strict_e0_load, checkpoint_path, load_cache
    legacy = json.loads(Path(config['paths']['legacy_reference']).read_text())
    if legacy.get('protocol_id') != config['base_protocol_id'] or legacy.get('failures'):
        raise ValueError('历史前置核验不是合法v2证据')
    source_manifest = None
    if config['paths'].get('valid_source_manifest'):
        source_manifest = json.loads(Path(config['paths']['valid_source_manifest']).read_text())
    reports = {}
    for cancer in config['cancers']:
        old = legacy['reports'][cancer]
        old_provenance = old['provenance']
        if hashes['labels'] != old_provenance['label_sha256'] or hashes['manifest'] != old_provenance['manifest_sha256']:
            raise ValueError('标签或历史test manifest与v2不一致')
        for name, expected in old_provenance['cache_hashes'].items():
            split = 'train' if '_sur_train_' in name else 'test'
            if hashes[f'cache/{split}/{name}'] != expected:
                raise ValueError(f'历史缓存已变: {name}')
        if source_manifest is not None:
            for mm in config['shapes']:
                name = f'{mm}_sur_valid_all_{cancer}.pkl'
                if hashes[f'cache/valid/{name}'] != source_manifest['sha256'][name]:
                    raise ValueError(f'valid副本与landau来源不一致: {name}')
        model = build_model(config, cancer)
        states = set()
        checkpoints = {}
        for seed in config['seeds']:
            checkpoint = checkpoint_path(Path(config['paths']['checkpoint_root']), cancer, seed)
            old_checkpoint = old['checkpoints'][str(seed)]
            actual = hashes[f'checkpoint/{cancer}/{seed}']
            if actual != old_checkpoint['sha256']:
                raise ValueError(f'{cancer}/{seed}: 不同于历史E0文件')
            state_sha = strict_e0_load(model, checkpoint, expected_file_sha=actual)
            if state_sha != old_checkpoint['state_sha256'] or state_sha in states:
                raise ValueError('E0内容/seed映射冲突或跨seed重复')
            states.add(state_sha)
            checkpoints[str(seed)] = {'sha256': actual, 'state_sha256': state_sha, 'strict_load': True}
        del model
        bank, valid = load_cancer(config, cancer, 'valid')
        if bank.fingerprint != old_provenance['bank']['fingerprint']:
            raise ValueError('train患者库与历史v2内容不一致')
        valid_report = {'n': len(valid.ids), 'natural_missing': {
            m: sum(valid.features[m].get(pid) is None for pid in valid.ids) for m in ('rna', 'text')}}
        padded_valid = [pid for pid in valid.ids if not
            bank.validate_query(pid, valid.features['img'][pid], 'valid')[1].all()]
        del valid
        _, labels = read_split_labels(config['paths']['label'], cancer)
        test_features, _ = load_cache(Path(config['paths']['cache_roots']['test']), cancer, 'test', bank.splits['test'])
        test = QuerySource(bank, test_features, labels['test'], 'test', config['grids'])
        reports[cancer] = {'checkpoints': checkpoints, 'bank': bank.metadata(),
                           'valid': valid_report, 'valid_padded_count': len(padded_valid),
                           'test': {'n': len(test.ids), 'natural_missing': {
                               m: sum(test.features[m].get(pid) is None for pid in test.ids) for m in ('rna', 'text')}}}
        del test, test_features, bank
        gc.collect()
        print(f'preflight {cancer}: 5权重、3 split资产内容通过；未计算C-index', flush=True)
    return {'status': 'ASSETS_VERIFIED', 'protocol_id': config['protocol_id'], 'reports': reports,
            'asset_hashes': hashes, 'no_metrics_computed': True}


def verify_gpu(config):
    """必须先看PID，不用util=0推断空卡。CPU验证不宣称GPU门通过。"""
    if config['runtime']['device'] == 'cpu':
        return {'device': 'cpu', 'gpu_gate': 'NOT_RUN'}
    import subprocess
    index = config['runtime'].get('gpu_id')
    if type(index) is not int or index < 0:
        raise ValueError('cuda必须在config明确物理gpu_id')
    output = subprocess.run(['nvidia-smi', '-i', str(index), '--query-compute-apps=pid',
                             '--format=csv,noheader,nounits'], check=True, capture_output=True, text=True).stdout.strip()
    if output:
        raise ValueError('目标GPU存在其他计算进程，禁止抢占')
    os.environ['CUDA_VISIBLE_DEVICES'] = str(index)
    return {'device': 'cuda', 'gpu_id': index, 'gpu_gate': 'IDLE_BEFORE_LAUNCH'}


def save_generated_reports(reports, destination):
    marker = '<!-- GENERATED: zero-training-rules1to5; results only from frozen run -->\n'
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name, body in reports.items():
        path = destination / name
        if path.parent.resolve() != destination.resolve() or path.suffix != '.md':
            raise ValueError('报告文件名越界')
        if path.exists() and not path.read_text().startswith(marker):
            raise ValueError(f'拒绝覆盖非本工具生成的报告: {path}')
        temporary = path.with_suffix('.md.tmp')
        with temporary.open('x', encoding='utf-8') as handle:
            handle.write(marker + body)
        temporary.replace(path)
