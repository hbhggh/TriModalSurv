#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
cd "$v"
mkdir candidate-v3
tar -xf candidate-v3.tar -C candidate-v3
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v3/project/src:$v/candidate-v3/project"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
cd "$v/candidate-v3/project"
"$py" -B -m pytest -q > "$v/new-v3-tests.log" 2>&1
"$py" -B "$v/cli_preflight.py" "$v/candidate-v3/project" "$v/cli-preflight-v3.json"
