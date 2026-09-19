"""正式结果只读验收：须两阶段全部完成；不启动前向或重新选参。"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from statistics import fmean
import numpy as np
import torch
from sksurv.metrics import concordance_index_censored


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def audit(root, config_path):
    cfg=read(config_path)
    sys.path.insert(0,str(root))
    import runtime as rt
    rt.validate_config(cfg)
    axes=[(c,s,g) for c in cfg['cancers'] for s in cfg['seeds'] for g in cfg['grids']]
    valid=read(root/'runs/valid/complete.json')
    test=read(root/'runs/test/complete.json')
    lock_path=root/'runs/valid/selection-lock.json'
    check(sha(lock_path)==valid['selection_lock_sha256'],'锁文件SHA改变')
    lock=read(lock_path)
    check(lock['stage']=='valid','选择不是valid')
    check(rt.source_hashes(cfg)==lock['source_hashes'],'当前源码不同于冻结源码')
    check(rt.hash_assets(cfg)==lock['asset_hashes'],'当前权重/缓存等资产不同于冻结版本')
    check(read(root/'runs/test/campaign.json')['selection_lock_sha256']==sha(lock_path),'test锁引用不同')
    selected=lock['selection']['selected']
    check(len(selected)==6,'没有冻结六协议')
    with Path(cfg['paths']['label']).open() as f:
        labels=list(csv.DictReader(f))
    indexed={(r['cancer_type'],r['split'],r['patient_id']):r for r in labels}
    baseline_names={'retrieval','m1','m0real'}
    metrics={}; checked_arrays=0; audited_patients=0
    for stage,complete,per_cell in [('valid',valid,61),('test',test,9)]:
        check(complete['status']=='COMPLETED' and complete['metrics_computed'],stage+'未完成')
        check(complete['asset_hashes_unchanged'] and complete['state_dict_unchanged'],stage+'资产变化')
        check(len(complete['cells'])==100 and len(complete['rows'])==100*per_cell,stage+'矩阵不完整')
        campaign=read(root/f'runs/{stage}/campaign.json')
        check(campaign['source_hashes']==lock['source_hashes'],stage+'源码不一致')
        check(campaign['asset_hashes']==lock['asset_hashes'],stage+'资产不一致')
        check(campaign['science_config']==lock['science_config'],stage+'科研配置漂移')
        specs={s['candidate_id']:s for s in campaign['specs']}
        check(len(specs)==per_cell,stage+'候选数错误')
        merged=[]; matrix={}
        for cancer,seed,grid in axes:
            rel=f'{cancer}/{seed}/{grid}'
            cell_dir=root/f'runs/{stage}'/rel
            check(sha(cell_dir/'cell.json')==complete['cells'][rel],'格点SHA错误')
            cell=read(cell_dir/'cell.json')
            check(len(cell['rows'])==per_cell,'单格协议不全')
            check({r['candidate_id'] for r in cell['rows']}==set(specs),'候选身份不全')
            manifest=read(root/f'runs/{stage}/{cancer}-{stage}-manifest.json')['patients']
            entries={r['patient_id']:r for r in manifest if r['grid']==grid}
            ids=sorted(k[2] for k in indexed if k[:2]==(cancer,stage))
            check(set(entries)==set(ids),'manifest漏患者')
            expected_checked=sum(all(e['natural_valid'].values()) for e in entries.values()) if grid=='none' else 0
            diagnostics=set()
            for name,h in cell['artifacts'].items():
                check(sha(cell_dir/name)==h,'工件SHA错误:'+name)
            for row in cell['rows']:
                cid=row['candidate_id']; spec=specs[cid]
                check(row['split']==stage and (row['cancer'],row['seed'],row['grid'])==(cancer,seed,grid),'格点身份错误')
                check(row['run_fingerprint']==complete['run_fingerprint'],'运行指纹错误')
                check(row['n_complete_checked']==expected_checked,'完整患者检查计数错误')
                diff=row['complete_max_logit_abs_diff']
                check(diff is None if not expected_checked else 0<=diff<=1e-6,'完整输入误差错误')
                diagnostics.add((expected_checked,diff))
                with np.load(cell_dir/row['prediction_file'],allow_pickle=False) as pred:
                    check(pred['patient_ids'].tolist()==ids,'预测患者全集错误')
                    check(row['n_patients']==len(ids),'患者数错误')
                    times=np.array([float(indexed[(cancer,stage,p)]['survival_months']) for p in ids],np.float32)
                    cens=np.array([float(indexed[(cancer,stage,p)]['censorship']) for p in ids],np.float32)
                    check(np.array_equal(pred['time'],times) and np.array_equal(pred['censorship'],cens),'标签与split不一致')
                    logits=torch.from_numpy(pred['logits'])
                    risk=-(1-logits.sigmoid().clamp(1e-6,1-1e-6)).cumprod(dim=1).sum(dim=1)
                    check(np.array_equal(risk.numpy(),pred['risk_b']),'B风险重算不一致')
                    score=float(concordance_index_censored((1-cens).astype(bool),times,risk.numpy())[0])
                    check(score==row['c_index_b'],'C-index重算不一致')
                record=read(cell_dir/row['audit_file'])
                check(record['spec']==spec and record['split']==stage,'审计协议或split错误')
                check(record['run_fingerprint']==complete['run_fingerprint'],'审计指纹错误')
                check([a['patient_id'] for a in record['patients']]==ids,'审计患者不全')
                for a in record['patients']:
                    pid=a['patient_id']; donor=a.get('donor_id')
                    check(a['natural_valid']==entries[pid]['natural_valid'],'天然缺失标记不一致')
                    if donor is not None:
                        check(donor!=pid and (cancer,'train',donor) in indexed,'供体不在同癌train或自检索')
                        check(a['candidate_count']>0 and np.isfinite(a['similarity']),'候选/相似度错误')
                    for pos,m in [(1,'text'),(2,'rna')]:
                        orig=entries[pid]['natural_valid'][m] and m not in entries[pid]['artificial_masked']
                        check(a['original_valid'][m]==orig,'原始有效标记错误')
                        check(a['imputed'][m]==(not orig and a['fusion_valid'][m]),'填补有效标记错误')
                        weight=(spec['w'] if 5 in spec['enabled_rules'] and a['imputed'][m] else 1.) if a['fusion_valid'][m] else 0.
                        check(a['pool_weights'][pos]==weight,'pooling权重错误')
                    audited_patients+=1
                key=(row['protocol'],cid,cancer,seed,grid)
                check(key not in matrix,'重复读数')
                matrix[key]=score
                checked_arrays+=1
            check(len(diagnostics)==1,'同格诊断不一致')
            merged.extend(cell['rows'])
        check(merged==complete['rows'],stage+'汇总不是原格点记录')
        metrics[stage]=matrix
    # 独立从valid原始读数重算条件路由、全局均值、平局排序，禁止读取test选参。
    vm=metrics['valid']; candidate_scores={}
    baseline={p:fmean(vm[(p,p,*cell)] for cell in axes) for p in baseline_names}
    v_specs=read(root/'runs/valid/campaign.json')['specs']
    candidates=[s for s in v_specs if s['protocol'] not in baseline_names]
    check(len(candidates)==58 and sum(s['protocol']=='combo' for s in candidates)==45,'valid网格错误')
    for spec in candidates:
        cid=spec['candidate_id']; p=spec['protocol']; rule1=1 in spec['enabled_rules']
        exception=rule1 and fmean(vm[(p,cid,'UCEC',seed,'text_100')] for seed in cfg['seeds'])>fmean(vm[('m0real','m0real','UCEC',seed,'text_100')] for seed in cfg['seeds'])
        routed=[vm[('m0real','m0real',*cell)] if rule1 and cell[2]=='text_100' and not(cell[0]=='UCEC' and exception) else vm[(p,cid,*cell)] for cell in axes]
        mean=fmean(routed)
        candidate_scores[cid]=(mean,exception,mean>=baseline['m1'] and mean>=baseline['m0real'])
    for protocol,spec in selected.items():
        choices=[s for s in candidates if s['protocol']==protocol]
        feasible=[s for s in choices if candidate_scores[s['candidate_id']][2]]
        winner=min(feasible or choices,key=lambda s:(-candidate_scores[s['candidate_id']][0],s['lambda'],s['w'],s['alpha'],s['candidate_id']))
        check(winner['candidate_id']==spec['candidate_id'],'冻结赢家不符独立valid重算')
        check(spec['ucec_exception']==candidate_scores[spec['candidate_id']][1],'UCEC例外判定错误')
    for row in lock['selection']['candidates']:
        check(row['routed_mean']==candidate_scores[row['candidate_id']][0],'候选表均值不符')
    means={}
    for p in [*selected,*sorted(baseline_names)]:
        cid=selected[p]['candidate_id'] if p in selected else p
        vals={cell:metrics['test'][(p,cid,*cell)] for cell in axes}
        means[p]={'four_scenarios':fmean(vals.values()),
                  'three_missing':fmean(v for k,v in vals.items() if k[2]!='none'),
                  'by_scenario':{g:fmean(v for k,v in vals.items() if k[2]==g) for g in cfg['grids']}}
    return {'status':'PASS','valid_records':6100,'test_records':900,
            'prediction_scores_recomputed':checked_arrays,'patient_audits_checked':audited_patients,
            'selection_independently_verified':True,'selected':selected,'means':means,
            'historical_comparison':test['historical_comparison']['status'],
            'source_hashes':lock['source_hashes'],'asset_hashes':lock['asset_hashes']}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--config',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.root,args.config),ensure_ascii=False,indent=2))
