#!/usr/bin/env bash
set -uo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
cd "$v" || exit 2
mkdir candidate-v1 || exit 3
tar -xf candidate-v1.tar -C candidate-v1 || exit 4
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$v/candidate-v1/project/src:$v/candidate-v1/project"
cd "$v/candidate-v1/project" || exit 5
/home/wuhao/miniconda3/envs/tcga_env/bin/python -B -m pytest -q tests experiments/I01_patient_retrieval/tests > "$v/new-v1-tests.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$v/new-v1-tests.exit"
exit "$rc"
