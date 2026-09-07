#!/bin/bash
# E0m 单任务评测（landau 侧）：E0 ckpt（NPJC，无补偿器）+ 评测期均值盲补（--arm m1）+ 填充位标 valid（--m1-mark-valid）
# 用法: eval_e0m_one.sh <CANCER> <seed> <gpu> [grids] [outdir]
set -u
C=$1; SD=$2; GPU=$3; GRIDS=${4:-none,rna_100,text_100,both_100}; OUT=${5:-/home/wuhao/npjc_eval_e0m}
source /home/wuhao/miniconda3/etc/profile.d/conda.sh; conda activate tcga_env; export OMP_NUM_THREADS=2
cd /home/wuhao/NPJ; mkdir -p "$OUT"
CK="/home/wuhao/NPJ/out/${SD}/tcga_uni2_img_1536text_768rna_256_NPJC_${C}_surv.pth"
FINAL="$OUT/e0m_${C}_s${SD}.json"
[ -f "$FINAL" ] && { echo "SKIP e0m $C $SD"; exit 0; }
[ -f "$CK" ] || { echo "NOCKPT e0m $C $SD"; exit 0; }
CUDA_VISIBLE_DEVICES=$GPU python scripts/eval_missing.py --arm m1 --network_type NPJC --m1-mark-valid --cancer "$C" --seed "$SD" --ckpt "$CK" --manifest data/missing_manifest_v1.csv --grids "$GRIDS" --label data/TCGA_9523_ex12.csv --out-dir "$OUT" > "$OUT/e0m_${C}_s${SD}.log" 2>&1
EC=$?
[ $EC -eq 0 ] && mv "$OUT/m1_${C}_s${SD}.json" "$FINAL" 2>/dev/null
[ $EC -eq 0 ] && echo "OK e0m $C $SD" || echo "EVALFAIL e0m $C $SD ec=$EC"
