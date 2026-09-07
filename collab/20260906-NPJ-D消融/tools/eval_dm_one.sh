#!/bin/bash
# Dm 单任务：D ckpt（MainModalityMoE, fusion mean）+ 评测期均值盲补（--arm m1；D 不读 valid，无需 mark-valid）
# 用法: eval_dm_one.sh <CANCER> <seed> <gpu> [grids] [outdir]
set -u
C=$1; SD=$2; GPU=$3; GRIDS=${4:-none,rna_100,text_100,both_100}; OUT=${5:-/home/wuhao/npjd_eval_dm}
source /home/wuhao/miniconda3/etc/profile.d/conda.sh; conda activate tcga_env; export OMP_NUM_THREADS=2
cd /home/wuhao/NPJ; mkdir -p "$OUT"
CK="/home/wuhao/NPJ/out_d0/${SD}/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_${C}_surv.pth"
FINAL="$OUT/dm_${C}_s${SD}.json"
[ -f "$FINAL" ] && { echo "SKIP dm $C $SD"; exit 0; }
[ -f "$CK" ] || { echo "NOCKPT dm $C $SD"; exit 0; }
CUDA_VISIBLE_DEVICES=$GPU python scripts/eval_missing.py --arm m1 --network_type MainModalityMoE --fusion_type mean --cancer "$C" --seed "$SD" --ckpt "$CK" --manifest data/missing_manifest_v1.csv --grids "$GRIDS" --label data/TCGA_9523_ex12.csv --out-dir "$OUT" > "$OUT/dm_${C}_s${SD}.log" 2>&1
EC=$?
[ $EC -eq 0 ] && mv "$OUT/m1_${C}_s${SD}.json" "$FINAL" 2>/dev/null
[ $EC -eq 0 ] && echo "OK dm $C $SD" || echo "EVALFAIL dm $C $SD ec=$EC"
