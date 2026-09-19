#!/usr/bin/env bash
# 用户批准的等价加速重跑；对拍、前置或任一阶段失败即停。
set -euo pipefail
cd /home/wuhao/npj_rules15_accel_20260916_Ob6fjB/result
runtime_python=/home/wuhao/miniconda3/envs/tcga_env/bin/python
export PYTHONPATH=/home/wuhao/npj_rules15_accel_20260916_Ob6fjB/repo:/home/wuhao/npj_rules15_accel_20260916_Ob6fjB/repo/src
export PYTHONDONTWRITEBYTECODE=1
trap 'task_exit=$?; printf "%s\n" "$task_exit" > evidence/tako-resume-process-exit.txt' EXIT
"$runtime_python" -B -c 'import json,runtime as r; from pathlib import Path; c=r.load_config("evidence/accel-valid.yaml"); p=json.loads(Path("evidence/acceleration-parity/complete.json").read_text()); assert p["status"]=="PASS" and len(p["reports"])==20 and p["source_hashes"]==r.source_hashes(c) and p["asset_hashes"]==r.hash_assets(c); r.require_authorization(c,"valid",r.source_hashes(c))'
for task_stage in preflight smoke valid test; do
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$task_stage" >> evidence/tako-resume-stages.log
    "$runtime_python" -B run.py --config "evidence/accel-${task_stage}.yaml" > "evidence/tako-resume-${task_stage}.log" 2>&1
done

"$runtime_python" -B evidence/audit_formal_results.py --root /home/wuhao/npj_rules15_accel_20260916_Ob6fjB/result --config evidence/accel-test.yaml > evidence/tako-resume-final-audit.log 2>&1
