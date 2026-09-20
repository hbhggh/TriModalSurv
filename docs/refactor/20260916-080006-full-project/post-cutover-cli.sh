#!/usr/bin/env bash
set -euo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/home/wuhao/miniconda3/envs/tcga_env/bin/python -B "$v/cli_preflight.py" "$v/candidate-v8/project" "$v/cli-post-cutover.json"
