from pathlib import Path
import sys,json,importlib.util
from types import SimpleNamespace
import torch
mode,project,oracle,out=sys.argv[1:];project,oracle,out=map(Path,[project,oracle,out]);out.mkdir(parents=True,exist_ok=False)
torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(123)
if mode=='old':
 sys.path[:0]=[str(oracle),str(oracle/'tests')]
 from test_mean_fusion import install_stubs
 install_stubs()
 import main_survival as runtime
else:
 sys.path[:0]=[str(project/'src'),str(project)]
 from trimodalsurv.training import runtime
modalities={k:SimpleNamespace(feature_dim=v) for k,v in [('img',12),('text',8),('rna',6)]}
model=runtime.load_model('NPJC','cpu',modalities,16,4,cancer_types=['BLCA'])
# 原运行器通过已包装模型的module读取cancer_type；两侧使用同一透明测试包装。
class Wrapper(torch.nn.Module):
 def __init__(self,m):super().__init__();self.module=m
 def forward(self,*args,**kwargs):return self.module(*args,**kwargs)
model=Wrapper(model);captured={}
class CPUAccelerator:
 def backward(self,loss):
  loss.backward()
  for k,p in model.named_parameters():
   if p.grad is not None:captured['grad/'+k]=p.grad.detach().clone()
batch={k:torch.randn(8,3,v.feature_dim) for k,v in modalities.items()}
batch.update(survival_months=torch.arange(8).float()+1,survival_months_bin=torch.arange(8)%4,censorship=torch.arange(8)%2,cancer_type=['BLCA']*8)
for k in modalities:batch[k+'_valid']=torch.ones(8)
optimizer=torch.optim.Adam(model.parameters(),lr=1e-4)
torch.manual_seed(123)
metrics=runtime.finetune_epoch(model,runtime.NLLSurvLoss(),optimizer,[batch],0,accelerator=CPUAccelerator(),device='cpu')
for k,p in model.state_dict().items():captured['step/'+k]=p.detach().clone()
torch.save(captured,out/'tensors.pt');(out/'metrics.json').write_text(json.dumps({k:float(v) for k,v in metrics.items()}));print('EPOCH_ONE_STEP_PASS',mode)
