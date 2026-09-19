from pathlib import Path
import sys,json,hashlib,re
from types import SimpleNamespace
import torch
from trimodalsurv.models.npjc import NPJC
from experiments.I02_population_prototypes.model import PopulationPrototypeBank
torch.set_num_threads(1)
root=Path(sys.argv[1]);out=Path(sys.argv[2]);files=sorted(root.rglob('*.pth'));assert len(files)==25
rows=[]
for p in files:
 cancer=re.search(r'NPJ[C]_([A-Z]+)_surv',p.name).group(1)
 modalities={k:SimpleNamespace(feature_dim=v) for k,v in [('img',1536),('text',768),('rna',256)]}
 m=NPJC('cpu',modalities,256,dropout_rate=.1,pred_dim=4,mlp_ratio=4,n_backbone=1,n_head=4,cancer_types=[cancer],compensator=PopulationPrototypeBank(8,256,123))
 data=p.read_bytes();state=torch.load(p,map_location='cpu',weights_only=True);m.load_state_dict(state,strict=True)
 assert bool(m.compensator.ready) and bool((m.compensator.counts>0).all())
 assert all(not t.is_floating_point() or torch.isfinite(t).all() for t in state.values())
 rows.append({'path':str(p),'relative':str(p.relative_to(root)),'bytes':len(data),'md5':hashlib.md5(data).hexdigest(),'sha256':hashlib.sha256(data).hexdigest(),'cancer':cancer,'strict':True,'keys':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in state.items()}})
with out.open('x') as f:json.dump({'status':'PASS','count':len(rows),'weights_only':True,'files':rows},f,indent=2)
print('CHECKPOINT_25_STRICT_PASS')
