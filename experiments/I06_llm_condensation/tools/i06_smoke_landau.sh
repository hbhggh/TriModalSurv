#!/bin/bash
# I06 候选 H 冒烟（landau）。用法：bash i06_smoke.sh <stage> [gpu]
# stage: setup | extract | prewarm | assets | smoke | replay
# 只判通 / 不崩（坑 V21）；冒烟产物不进账本主表。每个 stage 单独经 ~/NPJ/jobrun.sh 启动。
set -euo pipefail
H=e57d932b0411812e03d59338547f45b6183b3322
BASE=$HOME/i06_smoke_e57d932
NPJDATA=$HOME/NPJ/data
LEGACY_CACHE=$HOME/NPJ/tmp_sur_cache          # 只读来源：历史缓存（AGENTS.md：不改 tmp_sur_cache/）
E0_CKPT=$HOME/NPJ/_outputs/out                 # 只读来源：历史 E0 checkpoint
ENVS=$HOME/miniconda3/envs
TRAIN_PY=$ENVS/tcga_env/bin/python
PROFILES="a1struct a1summ a2struct a2summ"
CANCERS="BLCA BRCA LGG LUAD UCEC"
STAGE=${1:?stage}
GPU=${2:-1}

ts() { date '+%F %T %Z'; }
frozen_for() { case $1 in *struct) echo struct ;; *summ) echo summary ;; esac; }
py_for() { case $1 in a1*) echo $ENVS/i06-neuml/bin/python ;; a2*) echo $ENVS/i06-qwen/bin/python ;; esac; }

echo "[$(ts)] stage=$STAGE gpu=$GPU H=$H"
cd "$BASE"

case $STAGE in
setup)
  sha256sum -c SHA256SUMS
  for p in $PROFILES legacy; do
    R=$BASE/run_$p
    [ -e "$R" ] && { echo "已存在，拒绝覆盖: $R"; exit 1; }
    mkdir -p "$R"
    tar -xzf code-e57d932.tar.gz -C "$R"
    cp GIT_STAMP.json "$R/"
    mkdir "$R/data"
    for f in TCGA_9523_ex12.csv missing_manifest_v1.csv tcga-dataset_uni2 RNA_embedding_selfmade text_embeddings_parsed; do
      ln -s "$NPJDATA/$f" "$R/data/$f"
    done
    M=$BASE/mutable/$p
    mkdir -p "$M/tmp_sur_cache"
    ln -s "$M/tmp_sur_cache" "$R/tmp_sur_cache"
    if [ "$p" = legacy ]; then
      names=$(awk '{print $2}' $BASE/legacy_cache_hashes.sha256)
    else
      mkdir -p "$M/text_embeddings_$p"
      ln -s "$M/text_embeddings_$p" "$R/data/text_embeddings_$p"
      names=$(awk '{print $2}' $BASE/legacy_cache_hashes.sha256 | grep -E '^(img|rna)_')
    fi
    for n in $names; do cp --preserve=timestamps "$LEGACY_CACHE/$n" "$M/tmp_sur_cache/$n"; done
    (cd "$M/tmp_sur_cache" && grep -F -f <(printf '%s\n' $names) $BASE/legacy_cache_hashes.sha256 | sha256sum -c --quiet)
    echo "[$(ts)] $p：运行根就绪，缓存 $(ls "$M/tmp_sur_cache" | wc -l) 个（哈希全部通过）"
  done
  ;;
extract)
  for p in $PROFILES; do
    arm=$(frozen_for $p)
    fsha=$(awk -v f="frozen-$arm.jsonl" '$2==f {print $1}' SHA256SUMS)
    cd "$BASE/run_$p"
    $(py_for $p) experiments/I05_text_encoder_bcmbert/extract_text_features.py extract --profile $p \
      --labels data/TCGA_9523_ex12.csv --reference-dir data/text_embeddings_parsed \
      --frozen-texts "$BASE/frozen-$arm.jsonl" --frozen-sha256 "$fsha" \
      --out-dir "$BASE/mutable/$p/text_embeddings_$p" --device cuda --gpu-id $GPU --hf-cache-dir "$BASE/hf_cache"
    echo "[$(ts)] $p：特征提取完成，$(ls "$BASE/mutable/$p/text_embeddings_$p" | wc -l) 个文件"
    cd "$BASE"
  done
  ;;
prewarm)
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    for c in $CANCERS; do
      $TRAIN_PY scripts/train_launcher.py --_prewarm-cancer $c --model-config experiments/I05_text_encoder_bcmbert/model_config_$p.yml --label data/TCGA_9523_ex12.csv
    done
    echo "[$(ts)] $p：text 缓存预热完成，缓存共 $(ls "$BASE/mutable/$p/tmp_sur_cache" | wc -l) 个"
    cd "$BASE"
  done
  ;;
assets)
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    $TRAIN_PY experiments/I05_text_encoder_bcmbert/evaluate.py --profile $p --stage assets --run-root . --execution-root "$BASE/exec/$p"
    cd "$BASE"
  done
  ;;
smoke)
  for p in $PROFILES; do
    cd "$BASE/run_$p"
    O=$BASE/out/$p
    $TRAIN_PY scripts/train_launcher.py --plan experiments/I05_text_encoder_bcmbert/train_plan_smoke_$p.yaml \
      --model-config experiments/I05_text_encoder_bcmbert/model_config_$p.yml --python $TRAIN_PY \
      --result-path "$O/out" --state-file "$O/runs_state.json" --logs-dir "$O/launcher_logs" --gpus $GPU --per_gpu 1
    $TRAIN_PY experiments/I05_text_encoder_bcmbert/evaluate.py --profile $p --stage smoke --run-root . \
      --checkpoint-root "$O/out" --execution-root "$BASE/exec/$p/smoke" --cancers BLCA --seeds 123 \
      --assets-lock "$BASE/exec/$p/runs/assets/assets-lock.json" --gpu-id $GPU
    echo "[$(ts)] $p：冒烟训练与推理完成"
    cd "$BASE"
  done
  ;;
replay)
  cd "$BASE/run_legacy"
  $TRAIN_PY experiments/I05_text_encoder_bcmbert/evaluate.py --profile legacy-replay --stage replay --replay-tier cross-hardware \
    --run-root . --checkpoint-root "$E0_CKPT" --execution-root "$BASE/exec/replay" --gpu-id $GPU
  ;;
*) echo "未知 stage: $STAGE"; exit 2 ;;
esac
echo "[$(ts)] STAGE_DONE $STAGE"
