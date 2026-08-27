#!/bin/bash
# S4 单元：一个方法 × 一个癌种 × 5 seeds 串行（由 jobrun.sh 托管调用）
# 用法: s4_run_method_cancer.sh <gpu_id> <mcat|porpoise|npj> <blca|brca|luad|lgg|ucec>
set -u
GPU=$1; M=$2; C=$3
source /home/wuhao/miniconda3/etc/profile.d/conda.sh
conda activate tcga_env
SEEDS="123 132 213 231 321"
FAIL=0
if [ "$M" = npj ]; then
  cd /home/wuhao/NPJ
  CU=$(echo $C | tr a-z A-Z)
  for sd in $SEEDS; do
    CUDA_VISIBLE_DEVICES=$GPU python main_survival.py \
      --model_config model/config/surv_multimodal_mainmoe_uni2.yml \
      --lr 1e-4 --epochs 50 --batch_size 32 --cpt_name tcga_uni2 \
      --report_label_path data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv \
      --cancer_types $CU --network_type MainModalityMoE --seed $sd \
      || { FAIL=$((FAIL+1)); echo "SEED_${sd}_FAILED"; [ $FAIL -ge 2 ] && { echo "TWO_FAILS_STOP_${M}_${C}"; exit 1; }; }
  done
else
  RUN=/home/wuhao/baselines/s4_${M}_${C}
  cd $RUN
  if [ "$M" = mcat ]; then
    EXTRA="--model_type mcat --mode coattn --fusion concat --apply_sig --gc 32"
    REPO=/home/wuhao/baselines/MCAT
  else
    EXTRA="--model_type porpoise_mmf --mode pathomic --fusion concat --apply_mutsig --gc 1"
    REPO=/home/wuhao/baselines/PORPOISE
  fi
  for sd in $SEEDS; do
    CUDA_VISIBLE_DEVICES=$GPU PYTHONPATH=$REPO python $REPO/main.py \
      --seed $sd --k 1 --k_start 0 --k_end 1 --max_epochs 20 \
      --data_root_dir /home/wuhao/baselines/features \
      --which_splits custom424r2 --split_dir tcga_${C} \
      --results_dir $RUN/results --path_input_dim 1536 --batch_size 1 $EXTRA \
      || { FAIL=$((FAIL+1)); echo "SEED_${sd}_FAILED"; [ $FAIL -ge 2 ] && { echo "TWO_FAILS_STOP_${M}_${C}"; exit 1; }; }
  done
fi
echo "S4_${M}_${C}_ALL_SEEDS_DONE"
