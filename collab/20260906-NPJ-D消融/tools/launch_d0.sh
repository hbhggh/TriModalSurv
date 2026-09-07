#!/bin/bash
# NPJ-D（d0）全量：5 癌 × 25 seed = 125 run，launcher 托管，完成即评测 4 格点（jobrun 包裹）
set -u
source /home/wuhao/miniconda3/etc/profile.d/conda.sh; conda activate tcga_env
cd /home/wuhao/NPJ
PY=$(which python)
python scripts/train_launcher.py --arms d0 --cancers BLCA,BRCA,LUAD,LGG,UCEC --seeds 123,132,213,231,321,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20 --gpus 0,1 --per_gpu 6 --cpt-name tcga_uni2_d0 --result-path /home/wuhao/NPJ/out_d0 --python "$PY" --eval_grids none,rna_100,text_100,both_100 --eval_workers 6 --eval_out /home/wuhao/npjd_eval_d0 --eval_manifest data/missing_manifest_v1.csv "$@"
echo "LAUNCHER_D0_EXIT=$?"
