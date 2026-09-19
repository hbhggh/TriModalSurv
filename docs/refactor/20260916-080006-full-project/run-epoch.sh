#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
for mode in old new; do
 "$py" -B "$v/epoch_parity_worker.py" "$mode" "$v/candidate-v2/project" "$v/oracles/root" "$v/epoch-$mode"
done
"$py" -B - <<'PYCODE'
from pathlib import Path
import json,torch
b=Path('/home/wuhao/NPJ/refactor-validation-20260916-080006');x,y=[torch.load(b/('epoch-'+m)/'tensors.pt',weights_only=True) for m in ['old','new']]
assert x.keys()==y.keys();diff=0
for k,v in x.items():torch.testing.assert_close(v,y[k],atol=1e-6,rtol=0);diff=max(diff,float((v-y[k]).abs().max()))
a,c=[json.loads((b/('epoch-'+m)/'metrics.json').read_text()) for m in ['old','new']];assert a==c
with (b/'epoch-parity.json').open('x') as f:json.dump({'status':'PASS','tensor_checks':len(x),'max_abs':diff,'metrics':a,'scope':'synthetic one batch, transparent model wrapper; no real training'},f,indent=2)
print('EPOCH_PARITY_PASS')
PYCODE
