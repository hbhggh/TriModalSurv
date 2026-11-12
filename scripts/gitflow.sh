#!/usr/bin/env bash
# gitflow.sh — 科研 Git 工作流助手（单主干 × 按需 worktree；用户裁决 2026-11-12）
#
# 子命令（在哪个目录运行有要求，脚本会检查）:
#   candidate          任意 worktree: 跑 CI（只看退出码）→ 代码范围干净门 → 打印候选 H = <短哈希> 与摘要
#   freeze <run_id> [--no-worktree] [--link-assets <relpath>...]
#                      主目录（检出 MAIN）: 先解析参数、校验链接路径、过代码范围干净门，全部通过后才给 MAIN 打 tag
#                      TAG_PREFIX<run_id>，建 run worktree WT_ROOT/run-<run_id>（分支 RUN_BRANCH_PREFIX<run_id>，
#                      前缀为空则 detached），写 stamp；任何一步拒绝都不留下 tag、分支或目录
#     --no-worktree    只打 tag，并在主目录生成 stamp；不建 worktree 与分支（不能与 --link-assets 同用）
#     --link-assets    把主目录里的重资产（相对路径；须在主目录存在、在待检出的提交里不存在）用符号链接挂进新 worktree，
#                      链接指向主目录原位，登记在该 worktree 的 git 管理目录里；收尾只摘链接本身，不碰目标
#   cleanup <run_id>   任意目录: 核对 tag TAG_PREFIX<run_id> 存在、run worktree HEAD 等于该 tag 的提交、
#                      检出 RUN_BRANCH_PREFIX<run_id>（前缀为空则须 detached）、该提交仍在 MAIN 上；
#                      再查未提交改动、未跟踪文件与被 .gitignore 隐藏的文件（只扣除登记过且仍指向主目录原位的链接；
#                      被忽略文件只放行根目录 GIT_STAMP.json、.DS_Store、__pycache__/*.pyc）
#                      → 全部通过才摘链接、删 worktree 与 run 分支（tag 保留）；任一不符即拒绝并保留现场，不 -D、不 --force
#   wt-add <name> [--link-assets <relpath>...]
#                      任意目录: 从 MAIN 建并行 worktree WT_ROOT/wt-<name>，分支 WT_BRANCH_PREFIX<name>；
#                      name 须以 ASCII 字母或数字开头，其后只含字母、数字与 . _ - ；目录或分支已存在即拒绝
#   wt-rm <name>       任意目录: 核对该 worktree 检出的正是 WT_BRANCH_PREFIX<name> 且该分支已合入 MAIN，
#                      再按 cleanup 同样的规则检查剩余项 → 摘链接、删 worktree、git branch -d（不 -D、不 --force）
#   status             任意目录: 当前分支、worktree 列表、最近的 run tag、代码范围是否干净
#   help | -h | --help 任意目录（含仓库外）: 打印本说明
#
# 环境变量（括号内为默认值）:
#   MAIN_BRANCH (main)   TAG_PREFIX (run/)
#   RUN_BRANCH_PREFIX (train/)   run worktree 的分支前缀；设为空串 RUN_BRANCH_PREFIX= 则用 detached HEAD
#   WT_BRANCH_PREFIX  (wt/)      wt-add 建的分支前缀
#   CODE_PATHS  (src configs scripts tests experiments pyproject.toml conftest.py)
#               代码范围，空格分隔；candidate / freeze 只要求这些路径下没有未提交改动与未跟踪文件
#   WT_ROOT     (<主目录>.worktrees)   worktree 存放目录
#   CI_CMD      (scripts/ci.sh，其次 ./ci.sh)   候选门禁命令，只看退出码
#   STAMP_CMD   (有 scripts/git_stamp.py 就用它，否则内置最小 stamp 写到 WT_ROOT/run-<id>.GIT_STAMP.json)
#   PYTHON_BIN  (python3)
set -euo pipefail

MAIN_BRANCH="${MAIN_BRANCH:-main}"
TAG_PREFIX="${TAG_PREFIX:-run/}"
RUN_BRANCH_PREFIX="${RUN_BRANCH_PREFIX-train/}"   # 用 - 而不是 :- ，显式空串表示 detached
WT_BRANCH_PREFIX="${WT_BRANCH_PREFIX:-wt/}"
CODE_PATHS="${CODE_PATHS:-src configs scripts tests experiments pyproject.toml conftest.py}"
LINK_REGISTRY_NAME="gitflow-linked-assets"   # 登记文件名，放在各 worktree 的 git 管理目录里，不落在工作树

die() { echo "gitflow: $*" >&2; exit 1; }
log() { echo "[gitflow] $*"; }

# 帮助与子命令名先于仓库探测与 cd 处理（坑 G2），且按脚本绝对路径读取：scripts/ 里用相对路径、仓库外用绝对路径都能看
SCRIPT_PATH="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]:-$0}")"
usage() { awk 'NR > 1 { if ($0 ~ /^#/) print; else exit }' "$SCRIPT_PATH"; }
cmd="${1:-help}"
case "$cmd" in
  help|-h|--help) usage; exit 0 ;;
  candidate|freeze|cleanup|wt-add|wt-rm|status) shift ;;
  *) die "未知子命令 '${cmd}'（gitflow.sh help）" ;;
esac

# 注意：macOS 自带 bash 3.2 在 UTF-8 locale 下会把紧跟 $var 的全角标点首字节并入变量名（set -u 下直接崩），
# 变量后面紧跟中文或全角标点时一律写成 ${var}（坑 G3）。不在 $(...) 里写 case（坑 E37）。
repo_top="$(git rev-parse --show-toplevel 2>/dev/null)" || die "不在 git 仓库内"
cd "$repo_top"
here="$(pwd -P)"
common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)"
[ "$(basename "$common_dir")" = .git ] || die "仓库的 git 目录 ${common_dir} 不叫 .git，推不出主目录；本脚本只支持标准布局"
main_dir="$(dirname "$common_dir")"   # 物理路径：链接目标与「合法链接」判定都以它为准
WT_ROOT="${WT_ROOT:-${main_dir}.worktrees}"
case "$WT_ROOT" in /*) ;; *) WT_ROOT="${here}/${WT_ROOT}" ;; esac   # 收尾会 cd 到主目录，相对路径先定死

read -r -a CODE_PATH_LIST <<< "$CODE_PATHS" || true   # here-string 必有换行，read 正常返回 0；|| true 只防空串
[ "${#CODE_PATH_LIST[@]}" -gt 0 ] || die "CODE_PATHS 为空，无法界定代码范围"

current_branch() { git symbolic-ref -q --short HEAD || echo detached; }

# ---------- 名字与路径的形式校验（全部是纯字符串判断，没有副作用） ----------

valid_name() {   # run_id / wt 名：ASCII 字母或数字开头，其后只含字母、数字与 . _ -
  local alnum='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  case "$1" in
    ''|[!$alnum]*|*[!$alnum._-]*) return 1 ;;
  esac
  return 0
}

BAD_REASON=""
relpath_ok() {   # 规范相对路径返回 0；否则把原因放进 BAD_REASON 并返回 1
  local p="$1" rest comp
  BAD_REASON=""
  if [ -z "$p" ]; then BAD_REASON="空路径"; return 1; fi
  case "$p" in
    /*) BAD_REASON="是绝对路径，须写成相对主目录的路径"; return 1 ;;
    */) BAD_REASON="末尾带斜杠，请写成不带斜杠的形式"; return 1 ;;
    *[[:cntrl:]]*) BAD_REASON="含换行或控制字符"; return 1 ;;
    *'"'*|*'\'*) BAD_REASON="含双引号或反斜杠（git 会转义这类路径，收尾时对不上）"; return 1 ;;
  esac
  rest="$p"
  while :; do
    comp="${rest%%/*}"
    case "$comp" in
      '') BAD_REASON="含空分量（连续斜杠）"; return 1 ;;
      .|..) BAD_REASON="含 '${comp}' 分量"; return 1 ;;
      .[gG][iI][tT]) BAD_REASON="含 .git 分量"; return 1 ;;
    esac
    [ "$rest" != "$comp" ] || break
    rest="${rest#*/}"
  done
  return 0
}

# ---------- 代码范围干净门 ----------

code_dirty() {   # $1 worktree 顶层；输出 CODE_PATHS 下的未提交改动与未跟踪文件（逐个文件）
  git -c core.quotePath=false -C "$1" status --porcelain --untracked-files=all -- "${CODE_PATH_LIST[@]}"
}

require_code_clean() {   # $1 worktree 顶层
  local dirty
  dirty="$(code_dirty "$1")" || die "git status 失败，无法判断代码范围是否干净"
  if [ -n "$dirty" ]; then
    {
      echo "gitflow: 代码范围不干净（CODE_PATHS: ${CODE_PATHS}），先 commit 或 restore 这些路径："
      printf '%s\n' "$dirty"
    } >&2
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

# ---------- --link-assets：校验、建链、登记 ----------

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# 逐级对照待检出提交里的树：路径本身不得已存在；上级只能是目录；同一级里只差大小写的名字一律拒绝
# （macOS 默认文件系统不分大小写：worktree 里检出的是提交里的拼写，链接却按用户的拼写登记，收尾时会永远对不上）
check_against_commit() {   # $1 commit sha，$2 relpath（已过 relpath_ok）
  local commit="$1" p="$2" prefix="" rest="$2" comp treeish listing lowered lc n ln found typ
  while :; do
    comp="${rest%%/*}"
    if [ -z "$prefix" ]; then treeish="${commit}^{tree}"; else treeish="${commit}:${prefix%/}"; fi
    listing="$(git -c core.quotePath=false ls-tree --name-only "$treeish")" \
      || die "列不出提交 ${commit:0:7} 里 '${prefix:-./}' 的内容，无法校验 --link-assets 路径 '${p}'"
    lowered="$(printf '%s\n' "$listing" | tr '[:upper:]' '[:lower:]')" || die "大小写转换失败"
    lc="$(lower "$comp")"
    found=0
    while IFS= read -r n && IFS= read -r ln <&3; do
      [ -n "$n" ] || continue
      if [ "$n" = "$comp" ]; then found=1; continue; fi
      if [ "$ln" = "$lc" ]; then
        die "--link-assets 路径 '${p}' 的 '${prefix}${comp}' 与提交 ${commit:0:7} 里的 '${prefix}${n}' 只差大小写；请按提交里的拼写写"
      fi
    done <<< "$listing" 3<<< "$lowered"
    [ "$found" = 1 ] || return 0   # 提交里没有这一级，更深的层级也不会有
    if [ "$rest" = "$comp" ]; then
      die "--link-assets 路径 '${p}' 在待检出的提交 ${commit:0:7} 里已存在（链接会盖住已跟踪内容）"
    fi
    typ="$(git cat-file -t "${commit}:${prefix}${comp}")" || die "读不到提交 ${commit:0:7} 里的 '${prefix}${comp}'"
    [ "$typ" = tree ] || die "--link-assets 路径 '${p}' 的上级 '${prefix}${comp}' 在提交 ${commit:0:7} 里是 ${typ}，不是目录"
    prefix="${prefix}${comp}/"
    rest="${rest#*/}"
  done
}

prefix_case_conflict() {   # 两条路径的共同上级只差大小写（如 A/x 与 a/y）时返回 0
  local a="$1" b="$2" ca cb
  while :; do
    case "$a" in */*) ;; *) return 1 ;; esac
    case "$b" in */*) ;; *) return 1 ;; esac
    ca="${a%%/*}"; cb="${b%%/*}"
    if [ "$ca" != "$cb" ]; then
      if [ "$(lower "$ca")" = "$(lower "$cb")" ]; then return 0; fi
      return 1
    fi
    a="${a#*/}"; b="${b#*/}"
  done
}

validate_link_paths() {   # $1 待检出提交的 sha，其余为 relpath；有问题直接 die（此时尚未产生任何副作用）
  local commit="$1"; shift
  [ "$#" -gt 0 ] || die "--link-assets 至少要给一个相对路径"
  git cat-file -e "${commit}^{commit}" 2>/dev/null || die "无法读取待检出的提交 ${commit}"
  local p q lp lq i j seen rc tab
  tab="$(printf '\t')"
  for p in "$@"; do
    relpath_ok "$p" || die "--link-assets 路径 '${p}' 不合法：${BAD_REASON}"
    [ -e "${main_dir}/${p}" ] || die "--link-assets 路径 '${p}' 在主目录 ${main_dir} 里不存在"
    # 含非 ASCII 字符时，确认 git 显示这条路径的写法与输入逐字相同：macOS 上 git 会把 NFD 分解形式预组合成 NFC，
    # 按 NFD 登记的链接在收尾时会永远对不上。check-ignore -n -v 原样回显 git 眼中的路径（退出码 0/1 都正常）
    case "$p" in
      *[![:ascii:]]*)
        rc=0
        seen="$(git -C "$main_dir" -c core.quotePath=false check-ignore --no-index -n -v -- "$p" 2>/dev/null)" || rc=$?
        [ "$rc" -le 1 ] || die "--link-assets 路径 '${p}' 含非 ASCII 字符，且 git 无法解析它（例如穿过了主目录里的符号链接），无法确认写法"
        seen="${seen##*"$tab"}"
        [ "$seen" = "$p" ] || die "--link-assets 路径 '${p}' 的 Unicode 写法与 git 显示的 '${seen}' 不一致（多为 NFD 分解形式）；请改用 git 显示的写法"
        ;;
    esac
    check_against_commit "$commit" "$p"
  done
  # 同一次调用里的路径不得重复、不得互为祖先：否则后建的链接会穿过先建的链接写进主目录。
  # 按大小写不敏感比较（理由同上）
  local -a arr=("$@") low=()
  for p in "$@"; do low+=("$(lower "$p")"); done
  i=0
  while [ "$i" -lt "${#arr[@]}" ]; do
    j=$((i + 1))
    while [ "$j" -lt "${#arr[@]}" ]; do
      p="${arr[$i]}"; q="${arr[$j]}"; lp="${low[$i]}"; lq="${low[$j]}"
      [ "$lp" != "$lq" ] || die "--link-assets 路径 '${p}' 与 '${q}' 重复"
      case "$lq" in "$lp"/*) die "--link-assets 路径 '${p}' 是 '${q}' 的上级，不能同时链接" ;; esac
      case "$lp" in "$lq"/*) die "--link-assets 路径 '${q}' 是 '${p}' 的上级，不能同时链接" ;; esac
      if prefix_case_conflict "$p" "$q"; then die "--link-assets 路径 '${p}' 与 '${q}' 的上级只差大小写"; fi
      j=$((j + 1))
    done
    i=$((i + 1))
  done
}

link_registry() {   # $1 worktree；输出登记文件路径（在该 worktree 的 git 管理目录里）
  local gd
  gd="$(git -C "$1" rev-parse --absolute-git-dir)" || return 1
  printf '%s/%s\n' "$gd" "$LINK_REGISTRY_NAME"
}

make_links() {   # $1 新建的 worktree，其余为已校验的 relpath
  local wt="$1"; shift
  local reg p dest
  reg="$(link_registry "$wt")" || die "取不到 ${wt} 的 git 管理目录，未建链接"
  if [ -e "$reg" ] || [ -L "$reg" ]; then die "登记文件 ${reg} 已存在（异常），未建链接"; fi
  : > "$reg"
  for p in "$@"; do
    dest="${wt}/${p}"
    if [ -e "$dest" ] || [ -L "$dest" ]; then die "${dest} 已存在（异常），未建这条链接"; fi
    mkdir -p -- "$(dirname -- "$dest")"
    ln -s -- "${main_dir}/${p}" "$dest"
    printf '%s\n' "$p" >> "$reg"   # 建成之后才登记：登记过的都是 gitflow 亲手建的链接
    log "链接: ${p} -> ${main_dir}/${p}"
  done
}

legit_link() {   # $1 worktree，$2 登记的 relpath：仍是符号链接、值与「主目录物理路径/relpath」逐字相等、各级上级都不是链接
  local wt="$1" p="$2" anc
  relpath_ok "$p" || return 1
  [ -L "${wt}/${p}" ] || return 1
  [ "$(readlink "${wt}/${p}")" = "${main_dir}/${p}" ] || return 1
  anc="$p"
  while :; do
    case "$anc" in */*) anc="${anc%/*}" ;; *) break ;; esac
    [ ! -L "${wt}/${anc}" ] || return 1
  done
  return 0
}

regenerable() {   # 被忽略、但可以随 worktree 一起删的派生物：根目录 GIT_STAMP.json、.DS_Store、__pycache__/ 里的 .pyc
  local p="$1" base dir
  [ "$p" != GIT_STAMP.json ] || return 0
  base="${p##*/}"
  [ "$base" != .DS_Store ] || return 0
  case "$p" in */*) dir="${p%/*}" ;; *) return 1 ;; esac
  [ "${dir##*/}" = __pycache__ ] || return 1
  case "$base" in ?*.pyc) return 0 ;; esac
  return 1
}

# collect_leftovers <worktree> <git 出错时报错的结尾>
# 结果放进全局数组：LEGIT（合法链接）、BROKEN（登记过但已不合法）、LEFT_STATUS（未提交/未跟踪）、LEFT_IGNORED（被忽略）
# 只扣除合法链接本身，比较一律逐字相等；git 出错即 die，绝不当成「干净」
collect_leftovers() {
  local wt="$1" tail="$2" reg raw line p q ok i j
  LEGIT=(); BROKEN=(); LEFT_STATUS=(); LEFT_IGNORED=()
  local -a registered=()
  reg="$(link_registry "$wt")" || die "取不到 ${wt} 的 git 管理目录，无法核对链接。${tail}"
  if [ -e "$reg" ] || [ -L "$reg" ]; then
    { [ -f "$reg" ] && [ -r "$reg" ]; } || die "登记文件 ${reg} 不可读，无法核对链接。${tail}"
    raw="$(cat -- "$reg")" || die "读登记文件 ${reg} 失败。${tail}"
    while IFS= read -r line; do
      [ -z "$line" ] || registered+=("$line")
    done <<< "$raw"
  fi
  # 登记里重复或互为上级的条目一律当作不合法（gitflow 自己不会这样登记）
  local -a nested=()
  i=0
  while [ "$i" -lt "${#registered[@]}" ]; do
    j=0
    while [ "$j" -lt "${#registered[@]}" ]; do
      if [ "$i" != "$j" ]; then
        p="${registered[$i]}"; q="${registered[$j]}"
        if [ "$p" = "$q" ]; then nested+=("$p"); fi
        case "$p" in "$q"/*) nested+=("$p") ;; esac
        case "$q" in "$p"/*) nested+=("$p") ;; esac
      fi
      j=$((j + 1))
    done
    i=$((i + 1))
  done
  for p in ${registered[@]+"${registered[@]}"}; do
    ok=1
    for q in ${nested[@]+"${nested[@]}"}; do
      if [ "$p" = "$q" ]; then ok=0; break; fi
    done
    if [ "$ok" = 1 ] && legit_link "$wt" "$p"; then LEGIT+=("$p"); else BROKEN+=("$p"); fi
  done
  # 以 / 结尾的忽略规则不匹配符号链接，链接会以 ?? 出现；含空格的路径 porcelain 会加双引号
  raw="$(git -c core.quotePath=false -C "$wt" status --porcelain --untracked-files=all)" \
    || die "在 ${wt} 里 git status 失败，无法核对。${tail}"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    ok=0
    for p in ${LEGIT[@]+"${LEGIT[@]}"}; do
      if [ "$line" = "?? ${p}" ] || [ "$line" = "?? \"${p}\"" ]; then ok=1; break; fi
    done
    [ "$ok" = 1 ] || LEFT_STATUS+=("$line")
  done <<< "$raw"
  # status --porcelain 看不见被 .gitignore 隐藏的文件，而 worktree remove 会一并删掉它们（坑 G5）；
  # 逐个枚举被忽略的文件（status --ignored 会把整个目录折叠成一行）
  raw="$(git -c core.quotePath=false -C "$wt" ls-files --others --ignored --exclude-standard)" \
    || die "在 ${wt} 里 git ls-files 失败，无法核对被忽略的文件。${tail}"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    ok=0
    for p in ${LEGIT[@]+"${LEGIT[@]}"}; do
      if [ "$line" = "$p" ]; then ok=1; break; fi
    done
    if [ "$ok" = 0 ] && ! regenerable "$line"; then LEFT_IGNORED+=("$line"); fi
  done <<< "$raw"
  return 0
}

has_leftovers() { [ "${#BROKEN[@]}" -gt 0 ] || [ "${#LEFT_STATUS[@]}" -gt 0 ] || [ "${#LEFT_IGNORED[@]}" -gt 0 ]; }

describe_leftovers() {   # $1 worktree；写到 stderr
  local wt="$1" p
  if [ "${#LEFT_STATUS[@]}" -gt 0 ]; then
    echo "  未提交改动或未跟踪文件（结果不该写在这里）："
    printf '    %s\n' "${LEFT_STATUS[@]}"
  fi
  if [ "${#LEFT_IGNORED[@]}" -gt 0 ]; then
    echo "  被 .gitignore 隐藏的文件（worktree remove 会把它们一起删掉）："
    printf '    %s\n' "${LEFT_IGNORED[@]}"
  fi
  if [ "${#BROKEN[@]}" -gt 0 ]; then
    echo "  登记过、但已不是指向主目录原位的链接（被换目标、换成真实文件或目录、或已删除）："
    for p in "${BROKEN[@]}"; do
      if [ ! -e "${wt}/${p}" ] && [ ! -L "${wt}/${p}" ]; then
        echo "    ${p}    （已不存在；确认无误后可按登记补回再收尾: ln -s '${main_dir}/${p}' '${wt}/${p}'）"
      else
        echo "    ${p}"
      fi
    done
  fi
}

relink() {   # $1 worktree，其余 relpath：把已摘掉的链接按登记原样补回（收尾中途失败时用）
  local wt="$1" p; shift
  for p in "$@"; do
    if [ ! -e "${wt}/${p}" ] && [ ! -L "${wt}/${p}" ] && [ -d "$(dirname -- "${wt}/${p}")" ]; then
      ln -s -- "${main_dir}/${p}" "${wt}/${p}" || echo "gitflow: 补回链接 ${wt}/${p} 失败，请手动 ln -s ${main_dir}/${p} ${wt}/${p}" >&2
    fi
  done
}

require_own_worktree() {   # $1 目录：必须是本仓库某个 worktree 的顶层，且不是主目录
  local dir="$1" phys top cdir
  phys="$(cd "$dir" && pwd -P)" || die "进不了 ${dir}。不删，保留现场"
  top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || die "${dir} 不是可用的 git worktree。不删"
  top="$(cd "$top" && pwd -P)" || die "进不了 ${top}。不删，保留现场"
  [ "$top" = "$phys" ] || die "${dir} 不是 worktree 顶层（git 认的顶层是 ${top}）。不删，保留现场"
  cdir="$(cd "$dir" && cd "$(git rev-parse --git-common-dir)" && pwd -P)" || die "取不到 ${dir} 的 git 目录。不删"
  [ "$cdir" = "$common_dir" ] || die "${dir} 属于另一个仓库（${cdir}）。不删，保留现场"
  [ "$phys" != "$main_dir" ] || die "${dir} 是主目录，不能当 worktree 删除。不删"
}

# finish_removal <worktree> <描述>：身份核对已由调用方完成。先查完全部剩余项，有任何一项就拒绝且不动任何东西；
# 全部通过后才逐个摘合法链接（rm -- 路径，不带尾斜杠、不加 -r，摘前再判一次），再 worktree remove（不加 --force）与 prune
finish_removal() {
  local wt="$1" what="$2" p
  cd "$main_dir"   # 防止人站在被删的 worktree 里运行；后续 git 命令都以主目录为准
  collect_leftovers "$wt" "不删，保留现场"
  if has_leftovers; then
    {
      echo "gitflow: ${what} 不干净，不删，保留现场（也不要 --force）；先看: git -C ${wt} status"
      describe_leftovers "$wt"
      echo "  需要的产物先移到 worktree 之外；链接只摘链接本身，目标在主目录原位"
    } >&2
    exit 1
  fi
  local -a removed=()
  for p in ${LEGIT[@]+"${LEGIT[@]}"}; do
    if ! legit_link "$wt" "$p"; then
      relink "$wt" ${removed[@]+"${removed[@]}"}
      die "链接 ${wt}/${p} 在核对之后被改动，停止（已摘的链接已补回）。不删，保留现场"
    fi
    if ! rm -- "${wt}/${p}"; then
      relink "$wt" ${removed[@]+"${removed[@]}"}
      die "摘链接 ${wt}/${p} 失败（已摘的链接已补回）。不删，保留现场"
    fi
    removed+=("$p")
  done
  if ! git worktree remove "$wt"; then   # 不加 --force：上面已核对干净，git 这里再兜一次
    relink "$wt" ${removed[@]+"${removed[@]}"}
    die "git worktree remove 拒绝删除 ${wt}（链接已按登记补回）。不删，保留现场；先看: git worktree list --porcelain"
  fi
  git worktree prune
  if [ "${#removed[@]}" -gt 0 ]; then log "已摘链接 ${#removed[@]} 个（目标在主目录原位，未触碰）"; fi
}

# ---------- 子命令 ----------

cmd_candidate() {
  [ "$#" -eq 0 ] || die "candidate 不接受参数（收到 '${1}'）"
  run_ci
  require_code_clean "$here"
  local h subject outside n
  h="$(git rev-parse --short HEAD)"
  subject="$(git log -1 --format=%s)"
  outside="$(git -c core.quotePath=false status --porcelain)" || outside=""
  n=0
  if [ -n "$outside" ]; then n="$(printf '%s\n' "$outside" | wc -l | tr -d ' ')"; fi
  echo
  echo "H = ${h}  (${subject})"
  echo "分支: $(current_branch) @ ${here}"
  echo "--- 最近 5 个提交:"; git --no-pager log --oneline -n 5
  echo "--- 代码范围外的未提交改动（不阻塞）: ${n} 项"
  echo
  log "候选就绪。互审与冒烟通过后到主目录运行: scripts/gitflow.sh freeze <run_id>"
}

parse_link_args() {   # 解析 [--no-worktree] [--link-assets <relpath>...]；$1 = 是否允许 --no-worktree（1/0），其余为参数
  local allow_nowt="$1"; shift
  local mode=""
  OPT_NO_WT=0; OPT_LINK=0; LINK_PATHS=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --no-worktree)
        [ "$allow_nowt" = 1 ] || die "不认识的选项 '${1}'"
        OPT_NO_WT=1; mode="" ;;
      --link-assets) OPT_LINK=1; mode=link ;;
      -*) die "不认识的选项 '${1}'" ;;
      *)
        [ "$mode" = link ] || die "多余的参数 '${1}'"
        LINK_PATHS+=("$1") ;;
    esac
    shift
  done
  if [ "$OPT_NO_WT" = 1 ] && [ "$OPT_LINK" = 1 ]; then die "--no-worktree 与 --link-assets 不能同时使用"; fi
  return 0
}

write_stamp() {   # $1 目录 $2 run_id $3 commit $4 tag $5 分支 $6 worktree 描述
  local dir="$1" run_id="$2" commit="$3" tag="$4" branch_now="$5" where="$6" stamp
  (
    cd "$dir"
    if [ -n "${STAMP_CMD:-}" ]; then
      log "stamp: $STAMP_CMD"; $STAMP_CMD
    elif [ -f scripts/git_stamp.py ]; then
      log "stamp: scripts/git_stamp.py"; "${PYTHON_BIN:-python3}" scripts/git_stamp.py
    else
      stamp="${WT_ROOT}/run-${run_id}.GIT_STAMP.json"
      printf '{ "run_id": "%s", "commit": "%s", "tag": "%s", "branch": "%s", "dirty": false,\n  "worktree": "%s", "date": "%s" }\n' \
        "$run_id" "$commit" "$tag" "$branch_now" "$where" "$(date +%Y-%m-%dT%H:%M:%S)" > "$stamp"
      log "stamp: 内置最小版 -> ${stamp}"
    fi
  )
}

cmd_freeze() {
  [ "$#" -gt 0 ] || die "用法: gitflow.sh freeze <run_id> [--no-worktree] [--link-assets <relpath>...]"
  local run_id="$1"; shift
  valid_name "$run_id" || die "run_id '${run_id}' 不合法：须以 ASCII 字母或数字开头，其后只含字母、数字与 . _ -"
  # 1. 解析全部参数（未知选项即拒绝）
  parse_link_args 1 "$@"
  # 2. 位置与分支
  [ "$here" = "$main_dir" ] || die "freeze 须在主目录 ${main_dir} 运行（当前: ${here}）"
  [ "$(current_branch)" = "$MAIN_BRANCH" ] || die "请在检出 '${MAIN_BRANCH}' 的主目录里运行（当前: $(current_branch) @ ${here}）"
  local commit
  commit="$(git rev-parse -q --verify "refs/heads/${MAIN_BRANCH}^{commit}")" || die "取不到 ${MAIN_BRANCH} 的提交"
  local tag="${TAG_PREFIX}${run_id}" run_dir="${WT_ROOT}/run-${run_id}" run_branch="${RUN_BRANCH_PREFIX}${run_id}"
  # 3. 校验 --link-assets 各路径
  if [ "$OPT_LINK" = 1 ]; then validate_link_paths "$commit" ${LINK_PATHS[@]+"${LINK_PATHS[@]}"}; fi
  # 4. 代码范围干净门
  require_code_clean "$main_dir"
  # 5. 目标不得已存在
  git check-ref-format "refs/tags/${tag}" || die "tag 名 ${tag} 不是合法的 git 引用名"
  ! git show-ref --verify --quiet "refs/tags/${tag}" || die "tag ${tag} 已存在；同一版本重跑也要换新 run_id"
  if [ "$OPT_NO_WT" = 0 ]; then
    if [ -e "$run_dir" ] || [ -L "$run_dir" ]; then die "${run_dir} 已存在"; fi
    if [ -n "$RUN_BRANCH_PREFIX" ]; then
      git check-ref-format "refs/heads/${run_branch}" || die "分支名 ${run_branch} 不是合法的 git 引用名"
      ! git show-ref --verify --quiet "refs/heads/${run_branch}" || die "分支 ${run_branch} 已存在"
    fi
  fi
  # ---- 以上全部通过，从这里起才产生副作用 ----
  mkdir -p "$WT_ROOT"
  git tag "$tag" "$commit"
  if [ "$OPT_NO_WT" = 1 ]; then
    write_stamp "$main_dir" "$run_id" "$commit" "$tag" "$MAIN_BRANCH" "$main_dir"
    echo
    echo "tag          : ${tag} = ${commit}（${MAIN_BRANCH}）"
    echo "worktree     : 未建（--no-worktree）；同步源码请从该 tag 的干净快照打包（git archive ${tag}）"
    return 0
  fi
  if [ -n "$RUN_BRANCH_PREFIX" ]; then
    git worktree add -b "$run_branch" "$run_dir" "$commit" >/dev/null \
      || die "已打 tag ${tag}，但建 run worktree 失败；排查后可 git tag -d ${tag} 再重试"
  else
    git worktree add --detach "$run_dir" "$commit" >/dev/null \
      || die "已打 tag ${tag}，但建 run worktree 失败；排查后可 git tag -d ${tag} 再重试"
  fi
  local fresh
  fresh="$(git -c core.quotePath=false -C "$run_dir" status --porcelain --untracked-files=all)" \
    || die "run worktree ${run_dir} 建好后 git status 失败，异常"
  [ -z "$fresh" ] || die "run worktree 创建后不干净，异常"
  if [ "$OPT_LINK" = 1 ]; then
    make_links "$run_dir" ${LINK_PATHS[@]+"${LINK_PATHS[@]}"}
    # 扣除登记的链接后必须仍然干净；同时证明 cleanup 将来认得出这些链接
    collect_leftovers "$run_dir" "异常"
    if has_leftovers; then
      { echo "gitflow: run worktree 建链接后扣除登记的链接仍不干净，异常（cleanup 将认不出这些链接）："; describe_leftovers "$run_dir"; } >&2
      exit 1
    fi
  fi
  local branch_now
  branch_now="$(git -C "$run_dir" symbolic-ref -q --short HEAD || echo detached)"
  write_stamp "$run_dir" "$run_id" "$commit" "$tag" "$branch_now" "$run_dir"
  echo
  echo "run worktree : ${run_dir}"
  echo "HEAD         : ${commit}  (tag ${tag} = ${MAIN_BRANCH})"
  echo "分支         : ${branch_now}  ← 只读，禁止 commit；cleanup 会核对 HEAD 仍等于 tag ${tag}、检出不变"
  if [ "$OPT_LINK" = 1 ]; then
    echo "链接         : ${LINK_PATHS[*]}  ← 指向主目录原位；经链接写入会直接落到主目录"
  fi
  echo "规则         : 只从这里同步/运行；禁止修改；结果写到 worktree 之外"
}

cmd_cleanup() {
  local run_id="${1:-}"; [ -n "$run_id" ] || die "用法: gitflow.sh cleanup <run_id>"
  local run_dir="${WT_ROOT}/run-${run_id}" tag="${TAG_PREFIX}${run_id}"
  [ -d "$run_dir" ] || die "$run_dir 不存在"
  # 冻结身份以 freeze 打的 tag 为准。只核对「HEAD 仍在 MAIN 上」不够：切到 MAIN 上更早的提交也能通过，
  # tag 却仍指着原冻结提交。任一核对不符都拒绝、保留现场供排查；不 -D、不 --force。
  local frozen head head_ref want_ref=""
  frozen="$(git rev-parse -q --verify "refs/tags/${tag}^{commit}")" \
    || die "tag ${tag} 不存在，无法核对 run worktree 是否仍是冻结版本。不删，保留现场 ${run_dir}"
  head="$(git -C "$run_dir" rev-parse -q --verify HEAD)" \
    || die "${run_dir} 不是可用的 git worktree。不删"
  require_own_worktree "$run_dir"
  [ "$head" = "$frozen" ] \
    || die "run worktree HEAD ${head:0:7} 不等于 tag ${tag} 的 ${frozen:0:7}（实验期间源码被切换或有 commit 混入，该 run 结果 invalid）。不删，保留现场；先看: git -C ${run_dir} reflog -n 10"
  head_ref="$(git -C "$run_dir" symbolic-ref -q HEAD || true)"   # 空 = detached
  [ -z "$RUN_BRANCH_PREFIX" ] || want_ref="refs/heads/${RUN_BRANCH_PREFIX}${run_id}"
  local have="${head_ref#refs/heads/}" want="${want_ref#refs/heads/}"
  [ "$head_ref" = "$want_ref" ] \
    || die "run worktree 检出的是 '${have:-detached HEAD}'，应为 '${want:-detached HEAD}'（RUN_BRANCH_PREFIX='${RUN_BRANCH_PREFIX}' 须与 freeze 时一致）。不删，保留现场 ${run_dir}"
  git merge-base --is-ancestor "$frozen" "$MAIN_BRANCH" \
    || die "tag ${tag} 的 ${frozen:0:7} 不在 ${MAIN_BRANCH} 上（${MAIN_BRANCH} 被改写？）。不删，保留现场 ${run_dir}"
  finish_removal "$run_dir" "run worktree ${run_dir}"
  if [ -n "$head_ref" ]; then
    # -d 按主目录的检出（或上游）判断是否已合入；被拒就照实报告，不升级成 -D
    git branch -d "$have" >/dev/null \
      || die "已删 ${run_dir}，但分支 ${have} 未能 -d 删除：到检出 ${MAIN_BRANCH} 的主目录运行 git branch -d ${have}，不要 -D"
    log "已删除 ${run_dir} 与分支 ${have}；tag ${tag} 保留"
  else
    log "已删除 ${run_dir}；tag ${tag} 保留"
  fi
  git worktree list
}

cmd_wt_add() {
  [ "$#" -gt 0 ] || die "用法: gitflow.sh wt-add <name> [--link-assets <relpath>...]"
  local name="$1"; shift
  valid_name "$name" || die "名字 '${name}' 不合法：须以 ASCII 字母或数字开头，其后只含字母、数字与 . _ -"
  parse_link_args 0 "$@"
  local branch="${WT_BRANCH_PREFIX}${name}" dir="${WT_ROOT}/wt-${name}" commit
  git check-ref-format "refs/heads/${branch}" || die "分支名 ${branch} 不是合法的 git 引用名"
  commit="$(git rev-parse -q --verify "refs/heads/${MAIN_BRANCH}^{commit}")" || die "取不到 ${MAIN_BRANCH} 的提交"
  if [ -e "$dir" ] || [ -L "$dir" ]; then die "${dir} 已存在"; fi
  ! git show-ref --verify --quiet "refs/heads/${branch}" || die "分支 ${branch} 已存在"
  if [ "$OPT_LINK" = 1 ]; then validate_link_paths "$commit" ${LINK_PATHS[@]+"${LINK_PATHS[@]}"}; fi
  # ---- 以上全部通过，从这里起才产生副作用 ----
  mkdir -p "$WT_ROOT"
  git worktree add -b "$branch" "$dir" "$commit" >/dev/null
  local fresh
  fresh="$(git -c core.quotePath=false -C "$dir" status --porcelain --untracked-files=all)" \
    || die "worktree ${dir} 建好后 git status 失败，异常"
  [ -z "$fresh" ] || die "worktree ${dir} 创建后不干净，异常"
  if [ "$OPT_LINK" = 1 ]; then
    make_links "$dir" ${LINK_PATHS[@]+"${LINK_PATHS[@]}"}
    collect_leftovers "$dir" "异常"
    if has_leftovers; then
      { echo "gitflow: worktree 建链接后扣除登记的链接仍不干净，异常（wt-rm 将认不出这些链接）："; describe_leftovers "$dir"; } >&2
      exit 1
    fi
  fi
  echo
  echo "worktree : ${dir}"
  echo "分支     : ${branch}（从 ${MAIN_BRANCH} ${commit:0:7} 建）"
  if [ "$OPT_LINK" = 1 ]; then
    echo "链接     : ${LINK_PATHS[*]}  ← 指向主目录原位；经链接写入会直接落到主目录"
  fi
  echo "收尾     : 在主目录 git merge --ff-only ${branch}，再 scripts/gitflow.sh wt-rm ${name}"
}

cmd_wt_rm() {
  [ "$#" -eq 1 ] || die "用法: gitflow.sh wt-rm <name>"
  local name="$1"
  valid_name "$name" || die "名字 '${name}' 不合法：须以 ASCII 字母或数字开头，其后只含字母、数字与 . _ -"
  local branch="${WT_BRANCH_PREFIX}${name}" dir="${WT_ROOT}/wt-${name}" head_ref have
  [ -d "$dir" ] || die "${dir} 不存在"
  git -C "$dir" rev-parse -q --verify HEAD >/dev/null || die "${dir} 不是可用的 git worktree。不删"
  require_own_worktree "$dir"
  head_ref="$(git -C "$dir" symbolic-ref -q HEAD || true)"   # 空 = detached
  have="${head_ref#refs/heads/}"
  [ "$head_ref" = "refs/heads/${branch}" ] \
    || die "${dir} 检出的是 '${have:-detached HEAD}'，应为 '${branch}'。不删，保留现场"
  git merge-base --is-ancestor "refs/heads/${branch}" "refs/heads/${MAIN_BRANCH}" \
    || die "分支 ${branch} 还没合入 ${MAIN_BRANCH}（先在主目录 git merge --ff-only ${branch}）。不删，保留现场 ${dir}"
  finish_removal "$dir" "worktree ${dir}"
  git branch -d "$branch" >/dev/null \
    || die "已删 ${dir}，但分支 ${branch} 未能 -d 删除：到检出 ${MAIN_BRANCH} 的主目录运行 git branch -d ${branch}，不要 -D"
  log "已删除 ${dir} 与分支 ${branch}"
  git worktree list
}

cmd_status() {
  [ "$#" -eq 0 ] || die "status 不接受参数（收到 '${1}'）"
  echo "=== 当前 ==="
  echo "分支: $(current_branch) @ ${here}（主目录: ${main_dir}；主干: ${MAIN_BRANCH}）"
  echo "=== worktrees ==="; git worktree list
  echo "=== 最近的 run tag（新到旧，至多 10 个）==="
  git for-each-ref --sort=-creatordate --count=10 \
    --format='%(refname:short)  %(objectname:short)  %(creatordate:short)' "refs/tags/${TAG_PREFIX}*"
  if [ -n "$RUN_BRANCH_PREFIX" ]; then
    echo "=== run 分支（非空 = 实验进行中）==="; git --no-pager branch --list "${RUN_BRANCH_PREFIX}*"
  fi
  echo "=== 并行 worktree 分支 ==="; git --no-pager branch --list "${WT_BRANCH_PREFIX}*"
  echo "=== 代码范围（当前 worktree；CODE_PATHS: ${CODE_PATHS}）==="
  local dirty
  if dirty="$(code_dirty "$here")"; then
    if [ -z "$dirty" ]; then echo "干净"; else echo "不干净："; printf '%s\n' "$dirty"; fi
  else
    echo "（git status 失败，无法判断）"
  fi
}

case "$cmd" in
  candidate) cmd_candidate "$@" ;;
  freeze)    cmd_freeze "$@" ;;
  cleanup)   cmd_cleanup "$@" ;;
  wt-add)    cmd_wt_add "$@" ;;
  wt-rm)     cmd_wt_rm "$@" ;;
  status)    cmd_status "$@" ;;
esac
