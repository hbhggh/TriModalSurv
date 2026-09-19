#!/usr/bin/env bash
# 迁移后重新核验；失败即停，绝不覆盖 tako 历史证据。
set -euo pipefail
cd /tmp/npj_rules15_migrate_20260916_ZDKqbH/npj_rules15_accel_20260916_Ob6fjB/result
runtime_python=/home/wuhao/miniconda3/envs/tcga_env/bin/python
export PYTHONPATH=/tmp/npj_rules15_migrate_20260916_ZDKqbH/npj_rules15_accel_20260916_Ob6fjB/repo:/tmp/npj_rules15_migrate_20260916_ZDKqbH/npj_rules15_accel_20260916_Ob6fjB/repo/src
export PYTHONDONTWRITEBYTECODE=1
trap 'task_exit=$?; printf "%s\n" "$task_exit" > evidence/hitode-process-exit.txt' EXIT
"$runtime_python" -B -c 'import json,runtime as r; from pathlib import Path; c=r.load_config("evidence/hitode-valid.yaml"); p=json.loads(Path("evidence/tako-parity-preserved/complete.json").read_text()); assert p["status"]=="PASS" and p["source_hashes"]==r.source_hashes(c) and p["asset_hashes"]==r.hash_assets(c); r.require_authorization(c,"valid",r.source_hashes(c))'
printf '%s regression\n' "$(date -u +%FT%TZ)" >> evidence/hitode-stages.log
"$runtime_python" -B -m unittest discover -s tests -v > evidence/hitode-regression.log 2>&1
printf '%s preflight\n' "$(date -u +%FT%TZ)" >> evidence/hitode-stages.log
"$runtime_python" -B run.py --config evidence/hitode-preflight.yaml > evidence/hitode-preflight.log 2>&1
printf '%s migration-parity\n' "$(date -u +%FT%TZ)" >> evidence/hitode-stages.log
"$runtime_python" -B evidence/verify_acceleration.py --config evidence/hitode-valid.yaml > evidence/hitode-parity.log 2>&1
"$runtime_python" -B evidence/verify_migration.py > evidence/hitode-crossgpu-parity.log 2>&1
for task_stage in smoke valid test; do
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$task_stage" >> evidence/hitode-stages.log
    "$runtime_python" -B run.py --config "evidence/hitode-${task_stage}.yaml" > "evidence/hitode-${task_stage}.log" 2>&1
done
printf '%s audit\n' "$(date -u +%FT%TZ)" >> evidence/hitode-stages.log
"$runtime_python" -B evidence/audit_formal_results.py --root "/tmp/npj_rules15_migrate_20260916_ZDKqbH/npj_rules15_accel_20260916_Ob6fjB/result" --config evidence/hitode-test.yaml > evidence/hitode-final-audit.log 2>&1
