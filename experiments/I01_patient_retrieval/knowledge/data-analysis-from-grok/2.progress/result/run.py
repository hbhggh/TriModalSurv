"""集中配置驱动的零训练入口：report/preflight/smoke/valid/test。

默认report；正式阶段须有用户授权及绑定源码的Claude审核或真实用户豁免记录。
本入口不包含optimizer、backward、checkpoint保存或缓存重建路径。
"""
from __future__ import annotations

import argparse
import copy
import gc
import json
import uuid
from pathlib import Path

import numpy as np

import runtime as rt
from selection import build_candidates, choose_validation
from reporting import render_reports


def smoke_specs(config):
    """冒烟代表值由配置指定，不按任何C-index选择。"""
    desired = config['smoke']
    result = []
    for protocol in [*config['rules'], 'combo']:
        candidates = [s for s in build_candidates(config) if s['protocol'] == protocol]
        chosen = next(s for s in candidates if all(
            number not in s['enabled_rules'] or s[field] == desired[field]
            for number, field in ((3, 'lambda'), (4, 'alpha'), (5, 'w'))))
        result.append(chosen)
    return result


def _safe_name(value):
    if not value or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.' for c in value):
        raise ValueError('单元文件名含不安全字符')
    return value


def evaluate_cell(config, bank, source, model, specs, ids, *, cancer, seed, grid,
                  directory, fingerprint, checkpoint_sha, compute_metric):
    """同格所有臂共用患者/权重，并在写结果前完成一致性诊断。"""
    import torch
    from inference import prepare_batch, forward_with_pool_weights
    from trimodalsurv.evaluation.common import dual_risk_from_logits
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError('不得覆盖已存在的单元目录')
    candidate_ids = [s['candidate_id'] for s in specs]
    if len(set(candidate_ids)) != len(candidate_ids) or 'm0real' not in candidate_ids:
        raise ValueError('单元缺参考或候选ID重复')
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('患者列表为空或重复')
    if compute_metric and source.split not in ('valid', 'test'):
        raise ValueError('指标只允许显式valid/test')
    logits = {s['candidate_id']: [] for s in specs}
    audits = {s['candidate_id']: [] for s in specs}
    diagnostic = rt.CompleteDiagnostic(config['numerics']['logit_atol'], config['numerics']['logit_rtol'])
    batch_size = config['runtime']['batch_size']
    for offset in range(0, len(ids), batch_size):
        batch_ids = ids[offset:offset + batch_size]
        raw, natural = source.batch(batch_ids, grid)
        current = {}
        for spec in specs:
            inputs, audit, weights = prepare_batch(bank, batch_ids, raw, natural, spec,
                grid=grid, query_split=source.split, numerics=config['numerics'])
            value = forward_with_pool_weights(model, inputs, cancer,
                config['runtime']['device'], weights,
                non_blocking=config['runtime']['non_blocking'])
            current[spec['candidate_id']] = value
            logits[spec['candidate_id']].append(value)
            audits[spec['candidate_id']].extend(audit)
        diagnostic.check(raw['rna_valid'] & raw['text_valid'], current)
    time = np.asarray([float(source.labels[p]['survival_months']) for p in ids], np.float32)
    censor = np.asarray([float(source.labels[p]['censorship']) for p in ids], np.float32)
    rows, artifacts = [], {}
    directory.mkdir(parents=True, exist_ok=False)
    for spec in specs:
        key = _safe_name(spec['candidate_id'])
        values = np.concatenate(logits[key])
        risk = dual_risk_from_logits(torch.from_numpy(values))[1].cpu().numpy()
        if not np.isfinite(risk).all():
            raise ValueError('非有限B口径风险')
        row = {'split': source.split, 'protocol': spec['protocol'], 'candidate_id': key,
               'cancer': cancer, 'seed': seed, 'grid': grid, 'n_patients': len(ids),
               'checkpoint_sha256': checkpoint_sha, 'run_fingerprint': fingerprint,
               **diagnostic.result()}
        if compute_metric:
            from sksurv.metrics import concordance_index_censored
            score = float(concordance_index_censored((1 - censor).astype(bool), time, risk)[0])
            if not np.isfinite(score):
                raise ValueError('C-index不可计算，阻断完整汇总')
            row['c_index_b'] = score
        name = key + '.npz'
        # 非object数组，后续可allow_pickle=False读出。
        with (directory / name).open('xb') as stream:
            np.savez_compressed(stream, patient_ids=np.asarray(ids), logits=values,
                                risk_b=risk, time=time, censorship=censor)
        artifacts[name] = rt.file_sha256(directory / name)
        audit_name = key + '.audit.json'
        rt.write_json_new(directory / audit_name, {'spec': spec, 'patients': audits[key],
                          'split': source.split, 'grid': grid, 'run_fingerprint': fingerprint})
        artifacts[audit_name] = rt.file_sha256(directory / audit_name)
        row['prediction_file'], row['audit_file'] = name, audit_name
        rows.append(row)
    payload = {'run_fingerprint': fingerprint, 'rows': rows, 'artifacts': artifacts,
               'metrics_computed': compute_metric}
    rt.write_json_new(directory / 'cell.json', payload)
    return payload


def _load_or_reserve_campaign(path, payload):
    """完成格可续读；改配置、代码、资产或环境的恢复一律拒绝。"""
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise ValueError('运行目录已绑定另一套配置或指纹，禁止覆盖/重跑')
    else:
        rt.write_json_new(path, payload)


def _manifest(source, config, cancer):
    from trimodalsurv.evaluation.common import masked_modalities
    return [{'patient_id': pid, 'cancer': cancer, 'split': source.split, 'grid': grid,
             'natural_valid': {mm: source.features[mm].get(pid) is not None for mm in ('rna', 'text')},
             'artificial_masked': sorted(masked_modalities(grid))}
            for pid in source.ids for grid in config['grids']]


def _historical_comparison(config, rows):
    """新读数永不写回旧JSON；数值差异只作为可比性阻断证据。"""
    root = config['paths'].get('legacy_results_root')
    if not root or not Path(root).is_dir():
        return {'status': 'BLOCKED', 'reason': '历史结果路径不可用'}
    old = {}
    for path in sorted(Path(root).rglob('*.json')):
        value = json.loads(path.read_text())
        if (isinstance(value, dict) and value.get('protocol_id') == config['base_protocol_id']
                and value.get('arm') == 'retrieval'):
            for grid, result in value.get('grids', {}).items():
                if grid not in config['grids']:
                    continue
                key = (value['cancer'], int(value['seed']), grid)
                if key in old:
                    return {'status': 'BLOCKED', 'reason': '历史格点重复'}
                old[key] = result.get('cindex_B')
    differences = []
    for row in rows:
        if row['protocol'] != 'retrieval':
            continue
        key = (row['cancer'], row['seed'], row['grid'])
        score = old.get(key)
        if score is None:
            return {'status': 'BLOCKED', 'reason': '历史结果schema或格点缺失，需只读核验'}
        differences.append({'cancer': key[0], 'seed': key[1], 'grid': key[2],
                            'historical': score, 'current': row['c_index_b'],
                            'delta': row['c_index_b'] - score})
    return {'status': 'IDENTICAL' if all(r['delta'] == 0 for r in differences) else 'DIFFERENT',
            'cells': differences, 'historical_json_modified': False}


def with_history_boundary(reports, comparison):
    status = comparison['status']
    boundary = ('历史检索重放数值一致；不代表新规则已获独立确认。' if status == 'IDENTICAL' else
                '历史重放存在差异或证据阻塞，不可直接声称与历史结果可比；本批内部同权重比较仍单独保留。')
    note = (f'> 历史可比性：{status}。{boundary} '
            f'{comparison.get("reason", "")} 证据：`runs/test/complete.json` 的 historical_comparison。\n\n')
    return {name: note + body for name,body in reports.items()}


def execute(config):
    rt.validate_config(config)
    stage = config['runtime']['stage']
    # 先拒绝未授权正式阶段，避免为了报错而读取资产或初始化设备。
    if stage in ('valid', 'test') and not config['authorization']['formal_approved']:
        raise ValueError('正式valid/test尚未获用户授权')
    if stage == 'report':
        rt.save_generated_reports(render_reports([], {}, config, status='未跑',
            blocker='正式valid选参与test尚未放行；此处无实验分数。'), config['paths']['execution_root'])
        return {'status': 'NOT_RUN'}
    rt.setup_imports(config)
    sources = rt.source_hashes(config)
    rt.require_authorization(config, stage, sources)
    device_record = rt.verify_gpu(config)
    import torch
    torch.set_num_threads(config['runtime']['cpu_threads'])
    env, assets = rt.environment(), rt.hash_assets(config)
    common = {'science_config': rt.science_config(config), 'source_hashes': sources,
              'asset_hashes': assets, 'environment': env}
    directory = rt.stage_directory(config, stage)
    directory.mkdir(parents=True, exist_ok=True)
    preflight_dir = rt.stage_directory(config, 'preflight')
    if stage == 'preflight':
        campaign = {'stage': stage, **common}
        _load_or_reserve_campaign(directory / 'campaign.json', campaign)
        path = directory / 'complete.json'
        if path.exists():
            payload = json.loads(path.read_text())
            if payload.get('asset_hashes') != assets or payload.get('source_hashes') != sources:
                raise ValueError('旧preflight不对应当前指纹')
            return payload
        payload = rt.preflight(config, assets)
        if rt.hash_assets(config) != assets:
            raise ValueError('前置检查期间资产发生变化')
        payload.update(source_hashes=sources, environment=env, device=device_record)
        rt.write_json_new(path, payload)
        return payload
    if not (preflight_dir / 'complete.json').is_file():
        raise ValueError('真实运行前必须完成独立preflight')
    preflight = json.loads((preflight_dir / 'complete.json').read_text())
    if preflight['asset_hashes'] != assets or preflight['source_hashes'] != sources:
        raise ValueError('preflight指纹变化，须重新核验')
    selection = None
    lock_sha = None
    if stage == 'test':
        freeze_dir = rt.stage_directory(config, 'valid')
        valid_complete = json.loads((freeze_dir / 'complete.json').read_text())
        lock_sha = valid_complete['selection_lock_sha256']
        lock = rt.read_verified_json(freeze_dir / 'selection-lock.json', lock_sha)
        rt.validate_selection_lock(lock, config, sources, assets, env)
        selection = lock['selection']
        specs = list(selection['selected'].values())
    elif stage == 'valid':
        specs = build_candidates(config)
    else:
        specs = smoke_specs(config)
    specs = [rt.baseline_spec(arm) for arm in rt.BASELINES] + specs
    campaign = {'stage': stage, **common, 'specs': specs, 'selection_lock_sha256': lock_sha}
    fingerprint = rt.digest_json(campaign)
    _load_or_reserve_campaign(directory / 'campaign.json', campaign)
    # 即便complete存在也逐格验证工件；不只凭“文件存在”宣布通过。
    rows = []
    cells = {}
    from experiments.I01_patient_retrieval.evaluate import strict_e0_load, checkpoint_path
    for cancer in config['cancers']:
        split = 'test' if stage == 'test' else 'valid'
        bank, source = rt.load_cancer(config, cancer, split)
        manifest_path = directory / f'{cancer}-{split}-manifest.json'
        _load_or_reserve_campaign(manifest_path, {'patients': _manifest(source, config, cancer)})
        ids = rt.smoke_ids(source, config) if stage == 'smoke' else source.ids
        seeds = [config['smoke']['seed']] if stage == 'smoke' else config['seeds']
        for seed in seeds:
            model = None
            before = None
            expected = preflight['reports'][cancer]['checkpoints'][str(seed)]
            for grid in config['grids']:
                relative = f'{cancer}/{seed}/{grid}'
                cell_dir = directory / relative
                expected_cell = {'cancer':cancer,'seed':seed,'grid':grid,'split':split,
                    'ids':ids,'specs':specs,'checkpoint_sha':expected['sha256'],
                    'compute_metric':stage != 'smoke', 'n_complete_expected':sum(
                        all(source.features[m].get(pid) is not None for m in ('rna','text'))
                        for pid in ids) if grid == 'none' else 0}
                if (cell_dir / 'cell.json').exists():
                    payload = rt.verify_cell(cell_dir, fingerprint, expected=expected_cell)
                else:
                    if cell_dir.exists():
                        # 仅隔离没有完成标志的本轮残片，不覆盖已完成单元。
                        quarantine = directory / 'incomplete' / (relative.replace('/', '-') + '-' + uuid.uuid4().hex)
                        quarantine.parent.mkdir(parents=True, exist_ok=True)
                        cell_dir.rename(quarantine)
                    if model is None:
                        model = rt.build_model(config, cancer, config['runtime']['device'])
                        path = checkpoint_path(Path(config['paths']['checkpoint_root']), cancer, seed)
                        state = strict_e0_load(model, path, expected_file_sha=expected['sha256'])
                        if state != expected['state_sha256']:
                            raise ValueError('实际加载权重不同于前置证据')
                        before = {key: val.detach().cpu().clone() for key, val in model.state_dict().items()}
                    payload = evaluate_cell(config, bank, source, model, specs, ids, cancer=cancer,
                        seed=seed, grid=grid, directory=cell_dir, fingerprint=fingerprint,
                        checkpoint_sha=expected['sha256'], compute_metric=stage != 'smoke')
                    rt.verify_cell(cell_dir, fingerprint, expected=expected_cell)
                rows.extend(payload['rows'])
                cells[relative] = rt.file_sha256(cell_dir / 'cell.json')
                print(f'{stage} {relative}: {len(ids)}患者 × {len(specs)}协议，'
                      + ('不计算C-index' if stage == 'smoke' else '完成'), flush=True)
            if model is not None and any(not torch.equal(v.detach().cpu(), before[k]) for k,v in model.state_dict().items()):
                raise ValueError('前向改变state_dict，禁止提交结果')
            del model, before
        del bank, source
        gc.collect()
    if rt.hash_assets(config) != assets or rt.source_hashes(config) != sources:
        raise ValueError('执行前后资产或代码指纹改变')
    summary = {'stage': stage, 'status': 'SMOKE_PASS' if stage == 'smoke' else 'COMPLETED',
               'run_fingerprint': fingerprint, 'cells': cells, 'rows': rows,
               'asset_hashes_unchanged': True, 'state_dict_unchanged': True,
               'source_hashes': sources, 'device': device_record,
               'metrics_computed': stage != 'smoke'}
    if stage == 'valid':
        selection = choose_validation([r for r in rows if r['protocol'] not in rt.BASELINES],
                    build_candidates(config), [r for r in rows if r['protocol'] in rt.BASELINES], config)
        lock = {'stage': 'valid', **common, 'selection': selection, 'run_fingerprint': fingerprint}
        _load_or_reserve_campaign(directory / 'selection-lock.json', lock)
        summary['selection_lock_sha256'] = rt.file_sha256(directory / 'selection-lock.json')
    elif stage == 'test':
        summary['historical_comparison'] = _historical_comparison(config, rows)
        rt.save_generated_reports(with_history_boundary(
            render_reports(rows, selection, config, status='completed'), summary['historical_comparison']),
                                  config['paths']['execution_root'])
    _load_or_reserve_campaign(directory / 'complete.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description='零训练推理；所有参数只从config读取')
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    result = execute(rt.load_config(args.config))
    print(json.dumps({k:v for k,v in result.items() if k in ('status','stage','metrics_computed')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
