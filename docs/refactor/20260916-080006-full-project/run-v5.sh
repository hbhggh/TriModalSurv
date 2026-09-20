#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
cd "$v"
mkdir candidate-v5
tar -xf candidate-v5.tar -C candidate-v5
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v5/project/src:$v/candidate-v5/project"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
cd "$v/candidate-v5/project"
"$py" -B -m pytest --collect-only -q > "$v/new-v5-collect.log" 2>&1
"$py" -B -m pytest -q > "$v/new-v5-tests.log" 2>&1
"$py" -B "$v/cli_preflight.py" "$v/candidate-v5/project" "$v/cli-preflight-v5.json"
