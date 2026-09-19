from pathlib import Path
import json,sys,torch
base=Path(sys.argv[1]);rows=[]
for case in ['npjc','gate','mean','capr','bank','capl','population']:
 old,new=[base/(case+'-'+m) for m in ['old','new']]
 assert json.loads((old/'evidence.json').read_text())==json.loads((new/'evidence.json').read_text())
 max_diff=0;keys=0
 for artifact in ['initial.pt','tensors.pt']:
  x,y=[torch.load(p/artifact,map_location='cpu',weights_only=True) for p in [old,new]];assert x.keys()==y.keys()
  for k,v in x.items():
   w=y[k];assert v.shape==w.shape and v.dtype==w.dtype
   if v.is_floating_point():
    assert torch.isfinite(v).all() and torch.isfinite(w).all();torch.testing.assert_close(v,w,atol=1e-6,rtol=0);max_diff=max(max_diff,float((v-w).abs().max()))
   else:assert torch.equal(v,w)
   keys+=1
 rows.append({'case':case,'tensor_checks':keys,'max_abs':max_diff})
with (base/'synthetic-parity.json').open('x') as f:json.dump({'status':'PASS','atol':1e-6,'rtol':0,'cases':rows},f,indent=2)
print('SYNTHETIC_PARITY_PASS',len(rows))
