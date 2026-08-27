#!/bin/bash
# S4 单卡队列：按序执行本卡全部 方法×癌种 单元，单元级 flag 落盘
# 用法: s4_queue.sh 0   （GPU0: porpoise×5癌）
#       s4_queue.sh 1   （GPU1: mcat×5癌 → npj×5癌）
set -u
GPU=$1
UNITS_DIR=/home/wuhao/NPJ/jobs/s4_units
mkdir -p $UNITS_DIR
if [ "$GPU" = 0 ]; then
  QUEUE="porpoise:blca porpoise:brca porpoise:luad porpoise:lgg porpoise:ucec"
else
  QUEUE="mcat:blca mcat:brca mcat:luad mcat:lgg mcat:ucec npj:blca npj:brca npj:luad npj:lgg npj:ucec"
fi
for u in $QUEUE; do
  M=${u%%:*}; C=${u##*:}
  [ -f "$UNITS_DIR/${M}_${C}.done" ] && { echo "skip ${M}_${C} (done)"; continue; }
  echo "===== UNIT ${M}_${C} start $(date +%F_%T) GPU=$GPU ====="
  bash /home/wuhao/NPJ/s4_run_method_cancer.sh $GPU $M $C
  ec=$?
  if [ $ec -eq 0 ]; then
    date +%F_%T > "$UNITS_DIR/${M}_${C}.done"
  else
    date +%F_%T > "$UNITS_DIR/${M}_${C}.failed"
    echo "UNIT ${M}_${C} FAILED (ec=$ec)，按纪律停该线继续下一单元"
  fi
done
echo "S4_QUEUE_GPU${GPU}_FINISHED"
