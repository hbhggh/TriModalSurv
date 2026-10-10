#!/bin/bash
# I06 正式实验（landau）。代码 = run worktree（S）的 git archive + GIT_STAMP.json（commit = S）。
# 用法：bash i06_formal.sh <stage> [gpus] [per_gpu] [profile...]
# stage: setup | assets | train | preflight | test
# 特征与缓存复用冒烟阶段已校验的可变资产（按内容哈希，Git 工作流第 7 条）；资产锁在 S 上重写，早于全部正式训练。
set -euo pipefail
S_COMMIT=c5aa9ea2f62ba82fb625b00fdab05c67dde7f835
BASE=$HOME/i06_formal_c5aa9ea
SMOKE=$HOME/i06_smoke_e57d932
NPJDATA=$HOME/NPJ/data
ENVS=$HOME/miniconda3/envs
TRAIN_PY=$ENVS/tcga_env/bin/python
STAGE=${1:?stage}
GPUS=${2:-0,1}
PER_GPU=${3:-1}
shift $(( $# < 3 ? $# : 3 ))
PROFILES=${*:-"a1struct a1summ a2struct a2summ"}

ts() { date '+%F %T %Z'; }
echo "[$(ts)] stage=$STAGE gpus=$GPUS per_gpu=$PER_GPU profiles=$PROFILES S=$S_COMMIT"
cd "$BASE"

case $STAGE in
setup)
  sha256sum -c SHA256SUMS
  for p in $PROFILES; do
    R=$BASE/run_$p
    [ -e "$R" ] && { echo "已存在，拒绝覆盖: $R"; exit 1; }
    mkdir -p "$R"
    tar -xzf code-c5aa9ea.tar.gz -C "$R"
    cp GIT_STAMP.json "$R/"
    mkdir "$R/data"
    for f in TCGA_9523_ex12.csv missing_manifest_v1.csv tcga-dataset_uni2 RNA_embedding_selfmade text_embeddings_parsed; do
      ln -s "$NPJDATA/$f" "$R/data/$f"
    done
    ln -s "$SMOKE/mutable/$p/text_embeddings_$p" "$R/data/text_embeddings_$p"
    ln -s "$SMOKE/mutable/$p/tmp_sur_cache" "$R/tmp_sur_cache"
    echo "[$(ts)] $p：正式运行根就绪（特征 $(ls "$SMOKE/mutable/$p/text_embeddings_$p" | wc -l) 个文件，缓存 $(ls "$SMOKE/mutable/$p/tmp_sur_cache" | wc -l) 个）"
  done
  ;;
assets)
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    $TRAIN_PY experiments/I05_text_encoder_bcmbert/evaluate.py --profile $p --stage assets --run-root . --execution-root "$BASE/exec/$p"
    cd "$BASE"
  done
  ;;
train)
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    O=$BASE/out/$p
    $TRAIN_PY scripts/train_launcher.py --plan experiments/I05_text_encoder_bcmbert/train_plan_$p.yaml \
      --model-config experiments/I05_text_encoder_bcmbert/model_config_$p.yml --python $TRAIN_PY \
      --result-path "$O/out" --state-file "$O/runs_state.json" --logs-dir "$O/launcher_logs" --gpus $GPUS --per_gpu $PER_GPU
    echo "[$(ts)] $p：正式训练完成"
    cd "$BASE"
  done
  ;;
preflight)
  G=${GPUS%%,*}
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    $TRAIN_PY experiments/I05_text_encoder_bcmbert/evaluate.py --profile $p --stage preflight --run-root . \
      --checkpoint-root "$BASE/out/$p/out" --execution-root "$BASE/exec/$p" \
      --assets-lock "$BASE/exec/$p/runs/assets/assets-lock.json"
    cd "$BASE"
  done
  ;;
test)
  G=${GPUS%%,*}
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    $TRAIN_PY experiments/I05_text_encoder_bcmbert/evaluate.py --profile $p --stage test --run-root . \
      --checkpoint-root "$BASE/out/$p/out" --execution-root "$BASE/exec/$p" \
      --assets-lock "$BASE/exec/$p/runs/assets/assets-lock.json" \
      --replay-record "$SMOKE/exec/replay/runs/replay/replay-comparison.json" \
      --review-record "$BASE/gates/review-$p.json" --user-approval-record "$BASE/gates/approval-$p.json" --gpu-id $G
    echo "[$(ts)] $p：test 完成"
    cd "$BASE"
  done
  ;;
*) echo "未知 stage: $STAGE"; exit 2 ;;
esac
echo "[$(ts)] STAGE_DONE $STAGE"
