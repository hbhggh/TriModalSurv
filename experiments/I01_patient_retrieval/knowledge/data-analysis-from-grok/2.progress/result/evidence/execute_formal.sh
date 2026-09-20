#!/usr/bin/env bash
# 仅本次用户授权的零训练批次；任一阶段失败即停，不自动重启。
set -euo pipefail
cd /home/wuhao/npj_rules15_formal_20260916_R0Q4Fg/result
runtime_python=/home/wuhao/miniconda3/envs/tcga_env/bin/python
export PYTHONPATH=/home/wuhao/npj_rules15_formal_20260916_R0Q4Fg/repo:/home/wuhao/npj_rules15_formal_20260916_R0Q4Fg/repo/src
export PYTHONDONTWRITEBYTECODE=1
trap 'task_exit=$?; printf "%s\n" "$task_exit" > evidence/formal-process-exit.txt' EXIT
"$runtime_python" -B evidence/formal_gpu_probe.py --config evidence/formal-smoke.yaml > evidence/formal-gpu-probe.log 2>&1
for task_stage in preflight smoke valid test; do
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$task_stage" >> evidence/formal-stages.log
    "$runtime_python" -B run.py --config "evidence/formal-${task_stage}.yaml" > "evidence/formal-${task_stage}.log" 2>&1
done
