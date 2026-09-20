#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
cd "$v"
mkdir candidate-v7
tar -xf candidate-v7.tar -C candidate-v7
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v7/project/src:$v/candidate-v7/project"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
cd "$v/candidate-v7/project"
"$py" -B -m pytest --collect-only -q > "$v/new-v7-collect.log" 2>&1
"$py" -B -m pytest -q > "$v/new-v7-tests.log" 2>&1
"$py" -B "$v/cli_preflight.py" "$v/candidate-v7/project" "$v/cli-preflight-v7.json"
