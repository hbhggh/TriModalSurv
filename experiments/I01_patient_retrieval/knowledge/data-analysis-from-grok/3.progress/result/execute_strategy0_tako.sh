#!/usr/bin/env bash
# strategy0：已锁定配置的唯一远端执行入口；无训练、无参数覆盖。
set -euo pipefail

cd /home/wuhao/npj_strategy0_luad_20260917/result
runtime_python=/home/wuhao/miniconda3/envs/tcga_env/bin/python
export PYTHONPATH=/home/wuhao/npj_rules15_accel_20260916_Ob6fjB/repo:/home/wuhao/npj_rules15_accel_20260916_Ob6fjB/repo/src
export PYTHONDONTWRITEBYTECODE=1
mkdir -p evidence
trap 'task_exit=$?; printf "%s\n" "$task_exit" > evidence/process-exit.txt' EXIT
"$runtime_python" -B strategy0_run.py --config config.tako.json > evidence/strategy0.log 2>&1
