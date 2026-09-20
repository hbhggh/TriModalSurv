#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation/20260916-080006
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
p="$v/candidate-v2/project"
export PYTHONPATH="$p/src:$p"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
mkdir "$v/real-r2"
for kind in I01 I02; do
 for mode in old new; do
 "$py" -B "$v/real_parity_worker-r2.py" --mode "$mode" --kind "$kind" --root "$p" --oracles "$v/oracles" --data /home/wuhao/npj_fixed_eval_20260915_HpSkli/assets --checkpoints "$v/checkpoints" --out "$v/real-r2/$kind-$mode" > "$v/real-r2/$kind-$mode.log" 2>&1
 done
done
"$py" -B "$p/docs/refactor/20260916-080006-full-project/compare_real.py" "$v/real-r2"
