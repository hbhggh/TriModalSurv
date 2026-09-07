#!/bin/bash
# E1（NPJ-C + CAP）补 20 个 seed：5 癌 × 20 = 100 run；幂等跳过已有 5 seed；完成即评测进 npjc_eval_v2/e1（与既有 25 json 同目录）
set -u
source /home/wuhao/miniconda3/etc/profile.d/conda.sh; conda activate tcga_env
cd /home/wuhao/NPJ
PY=$(which python)
python scripts/train_launcher.py --arms e1 --cancers BLCA,BRCA,LUAD,LGG,UCEC --seeds 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20 --gpus 0,1 --per_gpu 6 --cpt-name tcga_uni2 --result-path /home/wuhao/NPJ/out --python "$PY" --eval_grids none,rna_100,text_100,both_100 --eval_workers 6 --eval_out /home/wuhao/npjc_eval_e1_25 --eval_manifest data/missing_manifest_v1.csv "$@"
echo "LAUNCHER_E1_EXIT=$?"
