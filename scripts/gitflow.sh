#!/usr/bin/env bash
# gitflow.sh — 科研 Git 工作流助手（策略一：先 Squash 后跑 × Worktree）
#
# 子命令（在哪个目录运行有要求，脚本会检查）:
#   init               主目录: 从 MAIN 建长期开发分支 DEV 及其 worktree
#   candidate          dev worktree: CI 退出码 + 干净树 → 打印候选 H 与 review 摘要
#   squash "<msg>"     主目录: DEV squash 进 MAIN 得 S，校验树一致，DEV 归位到 S
#   freeze <run_id>    主目录: 给 MAIN 打 tag TAG_PREFIX<run_id>，建 run worktree（分支 RUN_BRANCH_PREFIX<run_id>，或 detached），写 stamp
#   cleanup <run_id>   任意目录: 核对 tag TAG_PREFIX<run_id> 存在、run worktree HEAD 等于该 tag 的提交、
#                      检出 RUN_BRANCH_PREFIX<run_id>（前缀为空则须 detached）、该提交仍在 MAIN 上且树干净
#                      → 删 worktree 与 run 分支（tag 保留）；任一不符即拒绝并保留现场，不 -D、不 --force
#   status             任意目录: worktree 列表 + graph + run tag
#   help | -h | --help 任意目录（含仓库外）: 打印本说明
#
# 环境变量（括号内为默认值）:
#   MAIN_BRANCH (main)   DEV_BRANCH (dev)   TAG_PREFIX (run/)
#   RUN_BRANCH_PREFIX (train/)   run worktree 的分支前缀；设为空串 RUN_BRANCH_PREFIX= 则用 detached HEAD
#   WT_ROOT     (<主目录>.worktrees)   worktree 存放目录
#   CI_CMD      (scripts/ci.sh，其次 ./ci.sh)   候选门禁命令，只看退出码
#   STAMP_CMD   (有 scripts/git_stamp.py 就用它，否则内置最小 stamp 写到 WT_ROOT/run-<id>.GIT_STAMP.json)
#   PYTHON_BIN  (python3)
set -euo pipefail

MAIN_BRANCH="${MAIN_BRANCH:-main}"
DEV_BRANCH="${DEV_BRANCH:-dev}"
TAG_PREFIX="${TAG_PREFIX:-run/}"
RUN_BRANCH_PREFIX="${RUN_BRANCH_PREFIX-train/}"   # 用 - 而不是 :- ，显式空串表示 detached

die() { echo "gitflow: $*" >&2; exit 1; }
log() { echo "[gitflow] $*"; }

# 帮助先于仓库探测与 cd，且按脚本绝对路径读取：scripts/ 里用相对路径、仓库外用绝对路径都能看
SCRIPT_PATH="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]:-$0}")"
usage() { awk 'NR > 1 { if ($0 ~ /^#/) print; else exit }' "$SCRIPT_PATH"; }
case "${1:-help}" in help|-h|--help) usage; exit 0 ;; esac

# 注意：macOS 自带 bash 3.2 在 UTF-8 locale 下会把紧跟 $var 的全角标点首字节并入变量名（set -u 下直接崩），
# 变量后面紧跟中文或全角标点时一律写成 ${var}。
repo_top="$(git rev-parse --show-toplevel 2>/dev/null)" || die "不在 git 仓库内"
cd "$repo_top"
common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)"
main_dir="$(dirname "$common_dir")"
WT_ROOT="${WT_ROOT:-${main_dir}.worktrees}"

current_branch() { git symbolic-ref -q --short HEAD || echo detached; }

worktree_of_branch() {   # 某分支被检出在哪个目录
  git worktree list --porcelain | awk -v want="refs/heads/$1" '
    $1=="worktree"{path=$2} $1=="branch" && $2==want{print path}'
}

require_branch() {
  [ "$(current_branch)" = "$1" ] || die "请在检出 '$1' 的目录里运行（当前: $(current_branch) @ ${repo_top}）"
}

require_clean() {
  if [ -n "$(git status --porcelain)" ]; then
    echo "gitflow: $1 工作树不干净，先 commit 或 restore：" >&2
    git status --short >&2
    exit 1
  fi
}

run_ci() {
  local ci="${CI_CMD:-}"
  if [ -z "$ci" ]; then
    if   [ -x scripts/ci.sh ]; then ci=scripts/ci.sh
    elif [ -x ./ci.sh ];       then ci=./ci.sh
    else die "找不到 CI 命令：设置 CI_CMD 或提供 scripts/ci.sh"; fi
  fi
  log "CI: $ci"
  if $ci; then log "CI PASS (exit 0)"; else die "CI FAIL (exit $?)，不进入候选"; fi
}

cmd_init() {
  local existing; existing="$(worktree_of_branch "$DEV_BRANCH")"
  [ -z "$existing" ] || die "'$DEV_BRANCH' 已检出在 ${existing}，无需 init"
  mkdir -p "$WT_ROOT"
  local dev_dir="$WT_ROOT/$DEV_BRANCH"
  if git show-ref --verify --quiet "refs/heads/$DEV_BRANCH"; then
    git worktree add "$dev_dir" "$DEV_BRANCH"
  else
    git worktree add -b "$DEV_BRANCH" "$dev_dir" "$MAIN_BRANCH"
  fi
  log "开发 worktree: ${dev_dir}（分支 ${DEV_BRANCH}）"
  log "以后所有代码修改都在这个目录做；主目录只保留 $MAIN_BRANCH"
}

cmd_candidate() {
  require_branch "$DEV_BRANCH"
  run_ci
  require_clean "$DEV_BRANCH"
  local h; h="$(git rev-parse --short HEAD)"
  echo
  echo "H = $h  ($(git log -1 --format=%s))"
  echo "--- commits since $MAIN_BRANCH:"; git log --oneline "$MAIN_BRANCH..HEAD"
  echo "--- files changed:";              git diff --stat "$MAIN_BRANCH..HEAD"
  echo
  log "候选就绪。Review 通过后到主目录运行: scripts/gitflow.sh squash \"<commit message>\""
}

cmd_squash() {
  local msg="${1:-}"; [ -n "$msg" ] || die "用法: gitflow.sh squash \"feat(ID): ...\""
  require_branch "$MAIN_BRANCH"
  require_clean "$MAIN_BRANCH"
  local dev_dir; dev_dir="$(worktree_of_branch "$DEV_BRANCH")"
  [ -n "$dev_dir" ] || die "'$DEV_BRANCH' 没有 worktree，先 init"
  [ -z "$(git -C "$dev_dir" status --porcelain)" ] || die "dev worktree 不干净，先在 dev 里 candidate"
  [ "$(git rev-parse "$DEV_BRANCH")" != "$(git rev-parse "$MAIN_BRANCH")" ] || die "$DEV_BRANCH 与 $MAIN_BRANCH 相同，没有可 squash 的内容"
  git merge-base --is-ancestor "$MAIN_BRANCH" "$DEV_BRANCH" || die "$DEV_BRANCH 不包含 $MAIN_BRANCH 的最新 commit（main 被绕过推进了）；先在 dev 里合并 main 再来"
  local h; h="$(git rev-parse --short "$DEV_BRANCH")"
  git merge --squash "$DEV_BRANCH" >/dev/null
  git commit -q -m "$msg" -m "Squash of $DEV_BRANCH (H = $h)."
  local s; s="$(git rev-parse --short HEAD)"
  git diff --quiet "$DEV_BRANCH" "$MAIN_BRANCH" || die "S 与 H 源码树不一致，停下来检查"
  git -C "$dev_dir" reset --keep "$MAIN_BRANCH" >/dev/null
  log "S = ${s}（H = $h 已被吸收，$DEV_BRANCH 已归位到 S）"
  git log --graph --oneline --decorate --all -n 5
  log "下一步: scripts/gitflow.sh freeze <run_id>"
}

cmd_freeze() {
  local run_id="${1:-}"; [ -n "$run_id" ] || die "用法: gitflow.sh freeze <run_id>"
  require_branch "$MAIN_BRANCH"
  local tag="${TAG_PREFIX}${run_id}" run_dir="$WT_ROOT/run-$run_id"
  ! git show-ref --verify --quiet "refs/tags/$tag" || die "tag $tag 已存在；同一版本重跑也要换新 run_id"
  [ ! -e "$run_dir" ] || die "$run_dir 已存在"
  mkdir -p "$WT_ROOT"
  local run_branch="${RUN_BRANCH_PREFIX}${run_id}"
  if [ -n "$RUN_BRANCH_PREFIX" ]; then
    ! git show-ref --verify --quiet "refs/heads/$run_branch" || die "分支 $run_branch 已存在"
  fi
  git tag "$tag" "$MAIN_BRANCH"
  if [ -n "$RUN_BRANCH_PREFIX" ]; then
    git worktree add -b "$run_branch" "$run_dir" "$MAIN_BRANCH" >/dev/null
  else
    git worktree add --detach "$run_dir" "$MAIN_BRANCH" >/dev/null
  fi
  (
    cd "$run_dir"
    [ -z "$(git status --porcelain)" ] || die "run worktree 创建后不干净，异常"
    commit="$(git rev-parse HEAD)"
    branch_now="$(git symbolic-ref -q --short HEAD || echo detached)"
    if [ -n "${STAMP_CMD:-}" ]; then
      log "stamp: $STAMP_CMD"; $STAMP_CMD
    elif [ -f scripts/git_stamp.py ]; then
      log "stamp: scripts/git_stamp.py"; "${PYTHON_BIN:-python3}" scripts/git_stamp.py
    else
      stamp="$WT_ROOT/run-$run_id.GIT_STAMP.json"
      printf '{ "run_id": "%s", "commit": "%s", "tag": "%s", "branch": "%s", "dirty": false,\n  "worktree": "%s", "date": "%s" }\n' \
        "$run_id" "$commit" "$tag" "$branch_now" "$run_dir" "$(date +%Y-%m-%dT%H:%M:%S)" > "$stamp"
      log "stamp: 内置最小版 → $stamp"
    fi
    echo
    echo "run worktree : $run_dir"
    echo "HEAD         : $commit  (tag $tag = $MAIN_BRANCH)"
    echo "分支         : $branch_now  ← 只读，禁止 commit；cleanup 会核对 HEAD 仍等于 tag ${tag}、检出不变"
    echo "规则         : 只从这里同步/运行；禁止修改；结果写到 worktree 之外"
  )
}

cmd_cleanup() {
  local run_id="${1:-}"; [ -n "$run_id" ] || die "用法: gitflow.sh cleanup <run_id>"
  local run_dir="$WT_ROOT/run-$run_id" tag="${TAG_PREFIX}${run_id}"
  [ -d "$run_dir" ] || die "$run_dir 不存在"
  # 冻结身份以 freeze 打的 tag 为准。只核对「HEAD 仍在 MAIN 上」不够：切到 MAIN 上更早的提交也能通过，
  # tag 却仍指着原冻结提交。任一核对不符都拒绝、保留现场供排查；不 -D、不 --force。
  local frozen head head_ref want_ref=""
  frozen="$(git rev-parse -q --verify "refs/tags/${tag}^{commit}")" \
    || die "tag ${tag} 不存在，无法核对 run worktree 是否仍是冻结版本。不删，保留现场 ${run_dir}"
  head="$(git -C "$run_dir" rev-parse -q --verify HEAD)" \
    || die "${run_dir} 不是可用的 git worktree。不删"
  [ "$head" = "$frozen" ] \
    || die "run worktree HEAD ${head:0:7} 不等于 tag ${tag} 的 ${frozen:0:7}（实验期间源码被切换或有 commit 混入，该 run 结果 invalid）。不删，保留现场；先看: git -C ${run_dir} reflog -n 10"
  head_ref="$(git -C "$run_dir" symbolic-ref -q HEAD || true)"   # 空 = detached
  [ -z "$RUN_BRANCH_PREFIX" ] || want_ref="refs/heads/${RUN_BRANCH_PREFIX}${run_id}"
  local have="${head_ref#refs/heads/}" want="${want_ref#refs/heads/}"
  [ "$head_ref" = "$want_ref" ] \
    || die "run worktree 检出的是 '${have:-detached HEAD}'，应为 '${want:-detached HEAD}'（RUN_BRANCH_PREFIX='${RUN_BRANCH_PREFIX}' 须与 freeze 时一致）。不删，保留现场 ${run_dir}"
  git merge-base --is-ancestor "$frozen" "$MAIN_BRANCH" \
    || die "tag ${tag} 的 ${frozen:0:7} 不在 ${MAIN_BRANCH} 上（${MAIN_BRANCH} 被改写？）。不删，保留现场 ${run_dir}"
  [ -z "$(git -C "$run_dir" status --porcelain)" ] \
    || die "run worktree 不干净（有未提交改动或未跟踪文件；结果不该写在这里）。不删，保留现场，也不要 --force；先看: git -C ${run_dir} status"
  git worktree remove "$run_dir"   # 不加 --force：上面已核对干净，git 这里再兜一次
  git worktree prune
  if [ -n "$head_ref" ]; then
    # -d 按当前检出（或上游）判断是否已合入；被拒就照实报告，不升级成 -D
    git branch -d "$have" >/dev/null \
      || die "已删 ${run_dir}，但分支 ${have} 未能 -d 删除：到检出 ${MAIN_BRANCH} 的主目录运行 git branch -d ${have}，不要 -D"
    log "已删除 ${run_dir} 与分支 ${have}；tag ${tag} 保留"
  else
    log "已删除 ${run_dir}；tag ${tag} 保留"
  fi
  git worktree list
}

cmd_status() {
  echo "=== worktrees ==="; git worktree list
  echo "=== graph (最近 15) ==="; git log --graph --oneline --decorate --all -n 15
  echo "=== run tags ==="; git tag -l "${TAG_PREFIX}*"
  if [ -n "$RUN_BRANCH_PREFIX" ]; then echo "=== run branches（非空 = 实验进行中）==="; git branch --list "${RUN_BRANCH_PREFIX}*"; fi
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  init)      cmd_init ;;
  candidate) cmd_candidate ;;
  squash)    cmd_squash "$@" ;;
  freeze)    cmd_freeze "$@" ;;
  cleanup)   cmd_cleanup "$@" ;;
  status)    cmd_status ;;
  *) die "未知子命令 '$cmd'（gitflow.sh help）" ;;
esac
