#!/bin/bash
# E0m 全量：25 任务，GPU 按行奇偶分配，xargs -P 10；产物 /home/wuhao/npjc_eval_e0m/
set -u
OUT=/home/wuhao/npjc_eval_e0m; mkdir -p "$OUT"
i=0; : > /home/wuhao/NPJ/e0m_tasks.txt
for C in BLCA BRCA LUAD LGG UCEC; do for SD in 123 132 213 231 321; do echo "$C $SD $((i%2))" >> /home/wuhao/NPJ/e0m_tasks.txt; i=$((i+1)); done; done
echo "E0M_START $(date '+%F %T')"
xargs -P 10 -L 1 bash -c 'bash /home/wuhao/NPJ/eval_e0m_one.sh $0 $1 $2' < /home/wuhao/NPJ/e0m_tasks.txt
echo "E0M_DONE $(date '+%F %T') json=$(ls $OUT/e0m_*.json 2>/dev/null | wc -l)"
