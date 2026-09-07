#!/bin/bash
# Dm 全量：125 任务，GPU 奇偶分配，xargs -P 10；产物 /home/wuhao/npjd_eval_dm/
set -u
OUT=/home/wuhao/npjd_eval_dm; mkdir -p "$OUT"; i=0; : > /home/wuhao/NPJ/dm_tasks.txt
for C in BLCA BRCA LUAD LGG UCEC; do for SD in 123 132 213 231 321 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do echo "$C $SD $((i%2))" >> /home/wuhao/NPJ/dm_tasks.txt; i=$((i+1)); done; done
echo "DM_START $(date '+%F %T') tasks=$(wc -l < /home/wuhao/NPJ/dm_tasks.txt)"
xargs -P 10 -L 1 bash -c 'bash /home/wuhao/NPJ/eval_dm_one.sh $0 $1 $2' < /home/wuhao/NPJ/dm_tasks.txt
echo "DM_DONE $(date '+%F %T') json=$(ls $OUT/dm_*.json 2>/dev/null | wc -l)"
