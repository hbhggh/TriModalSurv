#!/bin/bash
# S4.1 并行 lane 队列：一条 lane = 一串 方法:癌种 单元（同卡多 lane 并发由多个 jobrun 实现）
# 用法: s4_queue_par.sh <gpu_id> <lane名> "<m:c> <m:c> ..."
set -u
GPU=$1; LANE=$2; QUEUE=$3
UNITS_DIR=/home/wuhao/NPJ/jobs/s4_units
mkdir -p $UNITS_DIR
for u in $QUEUE; do
  M=${u%%:*}; C=${u##*:}
  [ -f "$UNITS_DIR/${M}_${C}.done" ] && { echo "[$LANE] skip ${M}_${C} (done)"; continue; }
  echo "===== [$LANE] UNIT ${M}_${C} start $(date +%F_%T) GPU=$GPU ====="
  bash /home/wuhao/NPJ/s4_run_method_cancer.sh $GPU $M $C
  if [ $? -eq 0 ]; then date +%F_%T > "$UNITS_DIR/${M}_${C}.done"; else date +%F_%T > "$UNITS_DIR/${M}_${C}.failed"; echo "[$LANE] UNIT ${M}_${C} FAILED，停该线继续下一单元"; fi
done
echo "S4_LANE_${LANE}_FINISHED"
