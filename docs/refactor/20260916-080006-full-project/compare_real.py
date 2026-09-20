from pathlib import Path
import argparse,json
import torch
p=argparse.ArgumentParser();p.add_argument('base',type=Path);a=p.parse_args();all_rows=[]
for kind in ['I01','I02']:
 old=a.base/(kind+'-old');new=a.base/(kind+'-new')
 x=json.loads((old/'evidence.json').read_text());y=json.loads((new/'evidence.json').read_text())
 x.pop('mode');y.pop('mode');assert x==y,'IDs/bank/inputs/checkpoint metadata mismatch'
 tensors=[torch.load(z/'tensors.pt',map_location='cpu',weights_only=True) for z in [old,new]]
 assert tensors[0].keys()==tensors[1].keys()
 for key,values in tensors[0].items():
  assert values.keys()==tensors[1][key].keys()
  diffs={}
  for name,left in values.items():
   right=tensors[1][key][name];assert left.shape==right.shape and left.dtype==right.dtype
   if left.is_floating_point():
    assert torch.isfinite(left).all() and torch.isfinite(right).all();torch.testing.assert_close(left,right,atol=1e-6,rtol=0);diffs[name]=float((left-right).abs().max())
   else:assert torch.equal(left,right);diffs[name]=0
  all_rows.append({'experiment':kind,'cell':key,'max_abs':max(diffs.values()),'details':diffs})
with (a.base/'real-parity.json').open('x') as f:json.dump({'status':'PASS','atol':1e-6,'rtol':0,'patients':32,'cells':all_rows},f,indent=2)
print('REAL_PARITY_PASS',len(all_rows))
