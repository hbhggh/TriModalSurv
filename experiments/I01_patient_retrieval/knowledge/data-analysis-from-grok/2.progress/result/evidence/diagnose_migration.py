"""只读定位跨GPU差异；不放宽门禁、不计算C-index、不改结果。"""
import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]
old=root/'evidence/tako-parity-preserved'
new=root/'evidence/acceleration-parity'
stats={k:dict(max_abs=0.,arrays_over_1e6=0,elements_over_1e6=0) for k in ('logits','risk_b')}
bad_audits=[];bad_other=[];worst=[];count=0;order=0;tie_changes=0
for p in sorted(old.glob('*/*/accelerated/*.npz')):
    q=new/p.relative_to(old)
    with np.load(p,allow_pickle=False) as a,np.load(q,allow_pickle=False) as b:
        for k in a.files:
            if k in stats:
                d=np.abs(a[k].astype(np.float64)-b[k].astype(np.float64)); m=float(d.max())
                stats[k]['max_abs']=max(stats[k]['max_abs'],m)
                stats[k]['arrays_over_1e6']+=int((d>1e-6).any())
                stats[k]['elements_over_1e6']+=int((d>1e-6).sum())
                if k=='logits':worst.append((m,str(p.relative_to(old))))
            elif not np.array_equal(a[k],b[k]):bad_other.append((str(p),k))
        x=a['risk_b'];y=b['risk_b']
        dx=x[:,None]-x[None,:];dy=y[:,None]-y[None,:]
        ix=np.triu_indices(len(x),1)
        order+=int((np.sign(dx[ix])!=np.sign(dy[ix])).sum())
        tie_changes+=int(((np.abs(dx[ix])<=1e-8)!=(np.abs(dy[ix])<=1e-8)).sum())
    count+=1
for p in old.glob('*/*/accelerated/*.json'):
    if p.name!='cell.json' and json.loads(p.read_text())!=json.loads((new/p.relative_to(old)).read_text()):
        bad_audits.append(str(p))
report={'prediction_files':count,'stats':stats,'audit_mismatches':bad_audits,
        'other_array_mismatches':bad_other,'risk_pair_order_changes':order,
        'risk_tie_changes_1e8':tie_changes,'worst_logits':sorted(worst,reverse=True)[:8],
        'gate_changed':False,'metrics_computed':False}
with (root/'evidence/migration-difference-diagnostic.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
