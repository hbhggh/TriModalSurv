"""单实现独立进程：固定BLCA32患者，不训练、不改缓存。"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['old','new'],required=True);p.add_argument('--kind',choices=['I01','I02'],required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--oracles',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--checkpoints',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 a.out.mkdir(parents=True,exist_ok=False)
 import numpy as np,torch,random
 torch.set_num_threads(1);torch.manual_seed(123);np.random.seed(123);random.seed(123);torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 sys.path[:0]=[str(a.root/'src'),str(a.root)]
 if a.mode=='old':
  oldroot=a.oracles/('774f' if a.kind=='I01' else '684e');sys.path[:0]=[str(oldroot/'tests'),str(oldroot/'scripts'),str(oldroot)]
  load('legacy_fixture',oldroot/'tests/test_mean_fusion.py').install_stubs()
  if a.kind=='I01':ev=load('legacy_i01',oldroot/'scripts/eval_patient_retrieval.py')
  else:
   # 数据适配器来自固定774f；模型/填补算子来自实际684e。
   from model.fusion_model import NPJC
   from model.population_prototypes import PopulationPrototypeBank
   retrievalroot=a.oracles/'774f';sys.path[:0]=[str(retrievalroot/'scripts'),str(retrievalroot)]
   load('model.patient_retrieval_bank',retrievalroot/'model/patient_retrieval_bank.py')
   ev=load('legacy_i01',retrievalroot/'scripts/eval_patient_retrieval.py')
 else:
  from experiments.I01_patient_retrieval import evaluate as ev
  if a.kind=='I02':
   from trimodalsurv.models.npjc import NPJC
   from experiments.I02_population_prototypes.model import PopulationPrototypeBank
 label=a.data/'data/TCGA_9523_ex12.csv';manifest=a.data/'data/missing_manifest_v1.csv'
 splits,labels=ev.read_labels(label,'BLCA');ev.validate_manifest(manifest,'BLCA',splits['test'])
 train,th=ev.load_cache(a.data/'tmp_sur_cache','BLCA','train',splits['train']);test,vh=ev.load_cache(a.data/'tmp_sur_cache','BLCA','test',splits['test'])
 bank=ev.FixedPatientBank('BLCA',splits,train,expected_shapes=ev.SHAPES);source=ev.CachedPatients(bank,test,labels);ids=source.ids[:32];assert len(ids)==32
 if a.kind=='I01':
  model=ev.build_model('BLCA',{k:s[-1] for k,s in ev.SHAPES.items()},'cpu');ckpt=ev.checkpoint_path(a.data/'out','BLCA',123)
 else:
  from types import SimpleNamespace
  modalities={k:SimpleNamespace(feature_dim=ev.SHAPES[k][-1]) for k in ['img','text','rna']}
  model=NPJC('cpu',modalities,256,dropout_rate=.1,pred_dim=4,mlp_ratio=4,n_backbone=1,n_head=4,cancer_types=['BLCA'],compensator=PopulationPrototypeBank(8,256,123)).eval()
  matches=[p for p in a.checkpoints.rglob('*.pth') if 'BLCA' in p.name and '123' in p.parts];assert len(matches)==1,matches;ckpt=matches[0]
 checkpoint_hash=sha(ckpt)
 if a.kind=='I01':
  # 沿用既有strict_e0_load显式DataParallel前缀合同，不改权重文件。
  ev.strict_e0_load(model,ckpt,expected_file_sha=checkpoint_hash)
  state={k:v.detach().clone() for k,v in model.state_dict().items()}
 else:
  state=torch.load(ckpt,map_location='cpu',weights_only=True);model.load_state_dict(state,strict=True)
 model.eval()
 cells={};meta={'kind':a.kind,'mode':a.mode,'seed':123,'threads':1,'device':'cpu','dtype':'float32','ids':ids,'bank':bank.metadata(),'cache_hashes':{**th,**vh},'label_sha256':sha(label),'manifest_sha256':sha(manifest),'checkpoint_sha256':checkpoint_hash,'strict_load':True,'cells':{}}
 for grid in ev.GRIDS:
  raw,natural=source.batch(ids,grid)
  for arm in (ev.ARMS if a.kind=='I01' else ['population']):
   if a.kind=='I01':inputs,audit=ev.prepare_batch(bank,ids,raw,natural,arm)
   else:inputs,audit=raw,[]
   key=arm+'_'+grid;captured={};handles=[]
   for mm,projector in model.m_projector.items():
    def hook(mod,ins,outs,mm=mm):captured['projector_in_'+mm]=ins[0].detach().clone();captured['projector_out_'+mm]=outs.detach().clone()
    handles.append(projector.register_forward_hook(hook))
   if a.kind=='I02':
    def hook_comp(mod,ins,outs):
     for k,v in outs[0].items():captured['filled_'+k]=v.detach().clone()
     # Population forward mutates valids in place; capture after call.
     for k,v in ins[1].items():captured['filled_valid_'+k]=v.detach().clone()
    handles.append(model.compensator.register_forward_hook(hook_comp))
   logits=ev.forward_numpy(model,inputs,'BLCA','cpu')
   for h in handles:h.remove()
   captured['logits']=torch.from_numpy(logits)
   hazard=torch.sigmoid(captured['logits']).clamp(1e-6,1-1e-6)
   captured['risk_A']=-torch.cumprod(1-captured['logits'],dim=1).sum(dim=1)
   captured['risk_B']=-torch.cumprod(1-hazard,dim=1).sum(dim=1)
   cells[key]=captured
   meta['cells'][key]={'audit':audit,'input_fingerprints':{k:hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest() for k,v in inputs.items()}}
   print(key,flush=True)
 for k,v in state.items():assert torch.equal(v,model.state_dict()[k]),k
 assert sha(ckpt)==checkpoint_hash
 for k,v in {**th,**vh}.items():assert sha(a.data/'tmp_sur_cache'/k)==v
 torch.save(cells,a.out/'tensors.pt');(a.out/'evidence.json').write_text(json.dumps(meta,indent=2,sort_keys=True))
 imports={name:str(Path(m.__file__).resolve()) for name,m in list(sys.modules.items()) if getattr(m,'__file__',None) and (name.startswith('trimodalsurv') or name.startswith('experiments') or name.startswith('model.'))}
 (a.out/'imports.json').write_text(json.dumps(imports,indent=2))
 print('WORKER_PASS',flush=True)
if __name__=='__main__':main()
