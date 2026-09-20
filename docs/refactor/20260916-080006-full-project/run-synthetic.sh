#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v2/project/src:$v/candidate-v2/project"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
mkdir "$v/synthetic-r1"
for case in npjc gate mean capr bank capl population; do
 oracle="$v/oracles/root"
 if [ "$case" = population ]; then oracle="$v/oracles/684e"; fi
 for mode in old new; do
 "$py" -B "$v/synthetic_parity_worker.py" --mode "$mode" --case "$case" --root "$v/candidate-v2/project" --oracle "$oracle" --out "$v/synthetic-r1/$case-$mode"
 done
done
"$py" -B "$v/compare_synthetic.py" "$v/synthetic-r1"
