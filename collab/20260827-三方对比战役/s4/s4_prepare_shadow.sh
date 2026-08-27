#!/bin/bash
# S4 影子运行目录构建（landau 端）：为 MCAT/PORPOISE × 5 癌各建独立运行目录
# adapted trainval CSV 顶官方名 + r2 splits + signatures 链接。幂等可重跑。
set -eu
BASE=/home/wuhao/baselines
STAGE=$BASE/s4_stage   # scp 上来的 CSV/splits 中转区
for LIB in mcat porpoise; do
  for C in blca brca luad lgg ucec; do
    CU=$(echo $C | tr a-z A-Z)
    RUN=$BASE/s4_${LIB}_${C}
    mkdir -p $RUN/splits/custom424r2/tcga_${C} $RUN/results
    cp $STAGE/splits/${LIB}_${CU}_splits_0.csv $RUN/splits/custom424r2/tcga_${C}/splits_0.csv
    if [ "$LIB" = mcat ]; then
      mkdir -p $RUN/dataset_csv
      cp $STAGE/csv/MCAT_tcga_${CU}_adapted_trainval.csv.zip $RUN/dataset_csv/tcga_${C}_all_clean.csv.zip
      ln -sfn $BASE/MCAT/datasets_csv_sig $RUN/datasets_csv_sig
    else
      mkdir -p $RUN/datasets_csv_mutsig
      cp $STAGE/csv/PORPOISE_tcga_${CU}_adapted_trainval.csv.zip $RUN/datasets_csv_mutsig/tcga_${C}_all_clean.csv.zip
    fi
    echo "shadow ready: $RUN"
  done
done
