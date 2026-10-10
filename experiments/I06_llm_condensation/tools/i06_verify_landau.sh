#!/bin/bash
# I06 结果独立验真的 landau 一路（节点二；照 I05 的 verify-tako-sksurv-ckpt）：sksurv 从逐患者预测重算全部 C-index，
# 并现场读取每个档案 25 个 checkpoint 原件计算 sha256，与 complete.json 逐行记录比对。
# 用法：bash i06_verify.sh [profile...]；工具 = run worktree 快照（S）里的 I05 verify_results.py。
# 只读：不改 exec/ 与 out/；只在 verify/<档案>/ 下建符号链接与报告，已存在即拒绝覆盖。
# 独立文件而非 i06_formal.sh 的新阶段：test 运行期间改写正在执行的 bash 脚本会打乱其读取位置。
set -uo pipefail
BASE=$HOME/i06_formal_c5aa9ea
PY=$HOME/miniconda3/envs/tcga_env/bin/python
PROFILES=${*:-"a1struct a1summ a2struct a2summ"}
rc=0
for p in $PROFILES; do
  V=$BASE/verify/$p
  [ -e "$V" ] && { echo "已存在，拒绝覆盖: $V"; exit 1; }
  [ -f "$BASE/exec/$p/runs/test/complete.json" ] || { echo "$p：test 尚未完成"; exit 1; }
  mkdir -p "$V/raw/formal_eval/runs" "$V/raw/logs"
  ln -s "$BASE/exec/$p/runs/test" "$V/raw/formal_eval/runs/test"
  (cd "$BASE/out/$p/out" && sha256sum */*_NPJC_*_surv.pth) > "$V/raw/logs/checkpoint-sha256.txt"
  [ "$(wc -l < "$V/raw/logs/checkpoint-sha256.txt")" -eq 25 ] || { echo "$p：checkpoint 不是 25 个"; exit 1; }
  if (cd "$BASE/run_$p" && $PY experiments/I05_text_encoder_bcmbert/tools/verify_results.py --result-dir "$V" \
        --checkpoint-root "$BASE/out/$p/out" --out "$V/verify-landau-sksurv-ckpt.json"); then
    echo "$p：验真通过"
  else
    echo "$p：验真未通过"; rc=1
  fi
done
exit $rc
