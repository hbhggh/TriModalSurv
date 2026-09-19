"""固定32患者的零训练重构回归；旧/新实现同进程、同CPU、同输入。"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, platform, sys, traceback


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()


def dump(path,value):
    with path.open('x') as f: json.dump(value,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--legacy-root',type=Path,required=True);p.add_argument('--project-root',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args(); args.out_dir.mkdir(parents=True,exist_ok=False)
    for folder in ['raw','audit','logs']: (args.out_dir/folder).mkdir()
    import numpy as np
    import torch,yaml
    torch.set_num_threads(4);torch.manual_seed(0)
    sys.path[:0]=[str(args.legacy_root/'scripts'),str(args.legacy_root)]
    spec=importlib.util.spec_from_file_location('legacy_i01_eval',args.legacy_root/'scripts/eval_patient_retrieval.py')
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    sys.path[:0]=[str(args.project_root/'src'),str(args.project_root)]
    from experiments.I01_patient_retrieval import evaluate as new
    from eval_missing import dual_risk_from_logits as old_risk
    cancer='BLCA';seed=123;device='cpu'
    label=args.data_root/'data/TCGA_9523_ex12.csv';manifest=args.data_root/'data/missing_manifest_v1.csv'
    splits,labels=old.read_labels(label,cancer)
    assert (splits,labels)==new.read_labels(label,cancer)
    old.validate_manifest(manifest,cancer,splits['test']);new.validate_manifest(manifest,cancer,splits['test'])
    train,train_hash=old.load_cache(args.data_root/'tmp_sur_cache',cancer,'train',splits['train'])
    test,test_hash=old.load_cache(args.data_root/'tmp_sur_cache',cancer,'test',splits['test'])
    old_bank=old.FixedPatientBank(cancer,splits,train,expected_shapes=old.SHAPES)
    new_bank=new.FixedPatientBank(cancer,splits,train,expected_shapes=new.SHAPES)
    assert old_bank.metadata()==new_bank.metadata()
    old_source=old.CachedPatients(old_bank,test,labels);new_source=new.CachedPatients(new_bank,test,labels)
    ids=old_source.ids[:32];assert len(ids)==32 and ids==new_source.ids[:32]
    models=[m.build_model(cancer,{k:s[-1] for k,s in m.SHAPES.items()},device) for m in [old,new]]
    ckpt=old.checkpoint_path(args.data_root/'out',cancer,seed);ckpt_hash=digest(ckpt)
    state_hash=[m.strict_e0_load(model,ckpt,expected_file_sha=ckpt_hash) for m,model in zip([old,new],models)]
    assert state_hash[0]==state_hash[1]
    frozen=[{k:v.detach().clone() for k,v in model.state_dict().items()} for model in models]
    a_model=models[1]; layer=a_model.backbone.layers[0]
    actual_model={'network_type':type(a_model).__name__,'compensator':'none' if a_model.compensator is None else type(a_model.compensator).__name__,'hidden_size':a_model.m_projector['img'][0].out_features,'pred_dim':a_model.logits_dim,'dropout_rate':a_model.m_projector['img'][2].p,'n_backbone':len(a_model.backbone.layers),'n_head':layer.self_attn.num_heads,'mlp_ratio':layer.linear1.out_features//layer.linear1.in_features,'modality_order':list(a_model.modalities)}
    assert actual_model==old.MODEL_SPEC
    config={'kind':'refactor_parity','model':actual_model,'runtime':{'cancer':cancer,'seed':seed,'device':device,'precision':'float32','cpu_threads':torch.get_num_threads(),'batch_size':len(ids),'patient_selection':'sorted test IDs, first 32','arms':list(old.ARMS),'grids':list(old.GRIDS)},'tolerance':{'atol':1e-6,'rtol':0},'protocol_id':new.PROTOCOL_ID,'checkpoint_sha256':ckpt_hash,'bank_fingerprint':new_bank.fingerprint,'historical_training_parameters':{'status':'not_recorded_here','note':'本文件记录本次推理实际构造参数，不反推历史训练参数'},'parameter_sources':{'model':'loaded model attributes','runtime':'this executed harness; fixed user-approved scope'}}
    with (args.out_dir/'resolved_config.yaml').open('x') as f:yaml.safe_dump(config,f,allow_unicode=True,sort_keys=False)
    cells=[]
    for grid in old.GRIDS:
        raws=[source.batch(ids,grid) for source in [old_source,new_source]]
        for k,v in raws[0][0].items():np.testing.assert_array_equal(v,raws[1][0][k])
        for arm in old.ARMS:
            prepared=[m.prepare_batch(bank,ids,*raw,arm) for m,bank,raw in zip([old,new],[old_bank,new_bank],raws)]
            assert prepared[0][1]==prepared[1][1]
            for key,value in prepared[0][0].items():np.testing.assert_array_equal(value,prepared[1][0][key])
            captured=[{},{}];handles=[]
            for i,model in enumerate(models):
                for mm,projector in model.m_projector.items():
                    def hook(mod,ins,outs,i=i,mm=mm):captured[i][mm]=(ins[0].detach().clone(),outs.detach().clone())
                    handles.append(projector.register_forward_hook(hook))
            logits=[m.forward_numpy(model,inputs[0],cancer,device) for m,model,inputs in zip([old,new],models,prepared)]
            for h in handles:h.remove()
            intermediate_max=0.0
            for mm in captured[0]:
                for a,b in zip(captured[0][mm],captured[1][mm]):
                    assert a.shape==b.shape and torch.isfinite(a).all() and torch.isfinite(b).all()
                    torch.testing.assert_close(a,b,atol=1e-6,rtol=0)
                    intermediate_max=max(intermediate_max,float((a-b).abs().max()))
            np.testing.assert_allclose(logits[0],logits[1],atol=1e-6,rtol=0)
            risks=[old_risk(torch.from_numpy(logits[0])),new.dual_risk_from_logits(torch.from_numpy(logits[1]))]
            risk_max=0.0
            for a,b in zip(*risks):
                assert torch.isfinite(a).all() and torch.isfinite(b).all()
                torch.testing.assert_close(a,b,atol=1e-6,rtol=0);risk_max=max(risk_max,float((a-b).abs().max()))
            prefix=f'{arm}_{grid}'
            np.savez_compressed(args.out_dir/'raw'/f'{prefix}.npz',patient_id=np.array(ids),legacy_logits=logits[0],migrated_logits=logits[1],legacy_risk_B=risks[0][1].numpy(),migrated_risk_B=risks[1][1].numpy())
            dump(args.out_dir/'raw'/f'{prefix}.json',prepared[1][1])
            cell={'arm':arm,'grid':grid,'patients':len(ids),'donor_mask_input_exact':True,'max_logit_abs_diff':float(np.max(np.abs(logits[0]-logits[1]))),'max_risk_abs_diff':risk_max,'max_projector_abs_diff':intermediate_max}
            cells.append(cell);print(json.dumps(cell),flush=True)
    for model,state in zip(models,frozen):
        for key,v in state.items():assert torch.equal(v,model.state_dict()[key])
    assert digest(ckpt)==ckpt_hash
    for name,value in {**train_hash,**test_hash}.items():assert digest(args.data_root/'tmp_sur_cache'/name)==value
    sources={}
    for module in list(sys.modules.values()):
        f=getattr(module,'__file__',None)
        if f and Path(f).is_file() and Path(f).suffix=='.py':
            f=Path(f).resolve()
            if f.is_relative_to(args.legacy_root.resolve()) or f.is_relative_to(args.project_root.resolve()):sources[str(f)]=digest(f)
    dump(args.out_dir/'source_manifest.json',{'files':sources,'harness_sha256':digest(__file__),'snapshot_commit':'6a04a0bf5c283a57e90207899ddffe3867fd5e0a'})
    dump(args.out_dir/'data_manifest.json',{'label_sha256':digest(label),'missing_manifest_sha256':digest(manifest),'cache_hashes':{**train_hash,**test_hash},'selected_patient_ids':ids,'bank':new_bank.metadata(),'source_unchanged_after':True})
    dump(args.out_dir/'checkpoint_manifest.json',{'path':str(ckpt),'sha256':ckpt_hash,'state_sha256':state_hash[0],'strict_load_old_and_new':True})
    dump(args.out_dir/'audit/parity.json',{'status':'PASS','zero_training':True,'device':device,'patient_count':len(ids),'cell_count':len(cells),'bank_exact':True,'weights_unchanged':True,'tolerance':{'atol':1e-6,'rtol':0},'cells':cells})
    (args.out_dir/'environment.txt').write_text(f'Python {sys.version}\nTorch {torch.__version__}\nNumPy {np.__version__}\n{platform.platform()}\ncommand: {sys.argv!r}\n')
    (args.out_dir/'analysis.md').write_text('# I01 重构兼容性回归\n\nBLCA seed123，按ID排序的前32个test患者，完整合法train库，3臂×4格点，CPU FP32，零训练。\n\n旧、新实现 strict E0 加载、donor、mask、填补输入、库指纹一致；投影输入/输出、logits、A/B风险全部通过 atol=1e-6、rtol=0。逐格差异见 [parity.json](audit/parity.json)。\n\n只验证固定回归范围；没有重算正式C-index，不能据此声称五癌五seed或GPU行为已验证。\n')
    print('PARITY_PASS',flush=True)

if __name__=='__main__':
    main()
