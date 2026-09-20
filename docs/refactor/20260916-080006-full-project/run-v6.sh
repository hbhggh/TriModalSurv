#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
cd "$v"
mkdir candidate-v6
tar -xf candidate-v6.tar -C candidate-v6
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v6/project/src:$v/candidate-v6/project"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
cd "$v/candidate-v6/project"
"$py" -B -m pytest --collect-only -q > "$v/new-v6-collect.log" 2>&1
"$py" -B -m pytest -q > "$v/new-v6-tests.log" 2>&1
"$py" -B "$v/cli_preflight.py" "$v/candidate-v6/project" "$v/cli-preflight-v6.json"
