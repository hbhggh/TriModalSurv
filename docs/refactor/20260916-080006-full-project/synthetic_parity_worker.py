"""固定合成输入的单实现CPU回归；无患者数据、无正式训练。"""
from pathlib import Path
import argparse,importlib.util,json,sys,random
from types import SimpleNamespace

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['old','new'],required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--oracle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case',choices=['npjc','gate','mean','capr','bank','capl','population'],required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 import numpy as np,torch
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 torch.manual_seed(123);np.random.seed(123);random.seed(123)
 if a.mode=='old':
  sys.path[:0]=[str(a.oracle),str(a.oracle/'tests')];load('old_fixture',a.oracle/'tests/test_mean_fusion.py').install_stubs()
  from model.fusion_model import MainModalityMoE,NPJC
  from model.compensator import CAPRecall,MissingBank
  if a.case=='capl':from model.compensator import CAPRecallMulti
  if a.case=='population':from model.population_prototypes import PopulationPrototypeBank
  from loc_utils_3yr.loss_func import NLLSurvLoss
 else:
  sys.path[:0]=[str(a.root/'src'),str(a.root)]
  from trimodalsurv.models.fusion import MainModalityMoE
  from trimodalsurv.models.npjc import NPJC
  from trimodalsurv.models.compensator import CAPRecall,MissingBank
  from experiments.I04_cap4_multi_prototypes.model import CAPRecallMulti
  from experiments.I02_population_prototypes.model import PopulationPrototypeBank
  from trimodalsurv.training.loss_func import NLLSurvLoss
 dimensions={'img':12,'text':8,'rna':6};modalities={k:SimpleNamespace(feature_dim=v) for k,v in dimensions.items()};dim=16
 comp=None
 if a.case=='capr':comp=CAPRecall(dim=dim)
 if a.case=='bank':comp=MissingBank(dim=dim)
 if a.case=='capl':
  comp=CAPRecallMulti(dim=dim,proto_per_bin=2)
  comp.init_prototypes({k:torch.randn(16,dim) for k in ['text','rna']},torch.arange(16)%4,123)
 if a.case=='population':
  comp=PopulationPrototypeBank(2,dim,123);comp.update_memory_bank(*[torch.randn(16,dim) for _ in range(3)])
 cls=NPJC if a.case in ['npjc','population'] else MainModalityMoE
 kwargs={'fusion_type':'gate' if a.case=='gate' else 'mean'} if cls is MainModalityMoE else {}
 model=cls('cpu',modalities,dim,pred_dim=4,dropout_rate=.1,n_head=4,mlp_ratio=2,n_backbone=1,cancer_types=['BLCA'],compensator=comp,**kwargs)
 inputs={k:torch.randn(8,3,v) for k,v in dimensions.items()}
 for k in dimensions:inputs[k+'_valid']=torch.ones(8)
 inputs['rna_valid'][::2]=0;inputs['text_valid'][1::3]=0;inputs['bin_labels']=torch.arange(8)%4
 if a.case in ['capr','capl']:
  for k in ['rna','text']:inputs[k+'_orig']=inputs[k].clone();inputs[k+'_dropped']=1-inputs[k+'_valid']
 y=torch.arange(8)%4;t=torch.arange(8,dtype=torch.float32)+1;c=torch.arange(8)%2
 initial={k:v.detach().clone() for k,v in model.state_dict().items()};torch.save(initial,a.out/'initial.pt');model.load_state_dict(torch.load(a.out/'initial.pt',weights_only=True),strict=True)
 optimizer=torch.optim.Adam(model.parameters(),lr=1e-4)
 calls=[];hook=comp.register_forward_hook(lambda *args:calls.append('call')) if comp else None
 model.train();torch.manual_seed(123);out=model(inputs,cancer_type=['BLCA']*8);loss=NLLSurvLoss()(out[0],y,t,c)
 if len(out)>2:loss=loss+.1*out[2].mean()
 loss.backward();result={'logits':out[0].detach(),'loss':loss.detach()};none_grads=[]
 for k,v in model.named_parameters():
  if v.grad is None:none_grads.append(k)
  else:result['grad/'+k]=v.grad.detach().clone()
 train_calls=len(calls);optimizer.step()
 for k,v in model.state_dict().items():result['step/'+k]=v.detach().clone()
 model.eval()
 with torch.inference_mode():result['eval_logits']=model(inputs,cancer_type=['BLCA']*8)[0]
 if a.case=='population':assert train_calls==0 and len(calls)==1
 if hook:hook.remove()
 torch.save(model.state_dict(),a.out/'reload.pt');model.load_state_dict(torch.load(a.out/'reload.pt',weights_only=True),strict=True)
 for k,v in result.items():assert not v.is_floating_point() or torch.isfinite(v).all(),k
 torch.save(result,a.out/'tensors.pt')
 (a.out/'evidence.json').write_text(json.dumps({'case':a.case,'none_gradients':none_grads,'train_comp_calls':train_calls,'eval_comp_calls':len(calls)-train_calls,'seed':123,'synthetic_only':True,'single_optimizer_step':True,'strict_reload':True},indent=2))
 print('SYNTHETIC_WORKER_PASS',a.case,a.mode)
if __name__=='__main__':main()
