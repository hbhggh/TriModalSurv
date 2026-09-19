#!/usr/bin/env bash
set -uo pipefail
v=/home/wuhao/NPJ/refactor-validation-20260916-080006
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$v" || exit 2
tar -xf old-oracles.tar || exit 3
for source in root 684e 774f; do
 cd "$v/oracles/$source" || exit 4
 "$py" -B -m pytest --import-mode=importlib -p no:cacheprovider --collect-only -q tests > "$v/old-$source-collect.log" 2>&1
 printf '%s\n' "$?" > "$v/old-$source-collect.exit"
 "$py" -B -m pytest --import-mode=importlib -p no:cacheprovider -q tests > "$v/old-$source-tests.log" 2>&1
 printf '%s\n' "$?" > "$v/old-$source-tests.exit"
done
