#!/usr/bin/env bash
set -euo pipefail
validation_root=/home/wuhao/NPJ/refactor-validation/20260916-002337
project_root="$validation_root/project"
py=/home/wuhao/miniconda3/envs/tcga_env/bin/python
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$project_root/src:$project_root"
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
mkdir "$validation_root/scratch"
export TMPDIR="$validation_root/scratch"
cd "$project_root"
"$py" -B -m pytest -q experiments/I01_patient_retrieval/tests > "$validation_root/pytest.log" 2>&1
"$py" -B docs/refactor/20260916-002337/verify_i01_parity.py \
  --legacy-root "$project_root/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ" \
  --project-root "$project_root" \
  --data-root /home/wuhao/npj_fixed_eval_20260915_HpSkli/assets \
  --out-dir "$validation_root/parity-blca-s123-first32" > "$validation_root/parity.log" 2>&1
"$py" -B -m experiments.I01_patient_retrieval.evaluate \
  --data-root /home/wuhao/npj_fixed_eval_20260915_HpSkli/assets \
  --out-dir "$validation_root/preflight-blca-s123" \
  --cancers BLCA --seeds 123 --stage preflight --device cpu > "$validation_root/preflight.log" 2>&1
printf 'VALIDATION_COMPLETE\n'
