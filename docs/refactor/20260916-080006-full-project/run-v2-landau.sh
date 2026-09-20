#!/usr/bin/env bash
set -uo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
cd "$v" || exit 2
mkdir candidate-v2 || exit 3
tar -xf candidate-v2.tar -C candidate-v2 || exit 4
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v2/project/src:$v/candidate-v2/project"
cd "$v/candidate-v2/project" || exit 5
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
"$py" -B -m pytest --collect-only -q > "$v/new-v2-collect.log" 2>&1
"$py" -B -m pytest -q > "$v/new-v2-tests.log" 2>&1
rc=$?;printf '%s\n' "$rc" > "$v/new-v2-tests.exit";exit "$rc"
