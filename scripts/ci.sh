#!/usr/bin/env bash
# ci.sh — 本地 CI 门禁：清缓存 → 跑测试 → 只以退出码说话
#
# 用法: scripts/ci.sh [-h|--help]
#   不接受其他参数：未知参数以退出码 2 结束，不清缓存、不跑测试；测试范围用 TEST_CMD 指定
#
# 环境变量:
#   PYTHON_BIN  解释器 (默认 python3)
#   TEST_CMD    测试命令；默认有 pytest 用 "pytest -q"，否则退回 "unittest discover -s tests"
set -euo pipefail

# 参数先于任何副作用（cd / 清缓存 / 测试）处理
for arg in "$@"; do
  case "$arg" in
    -h|--help) awk 'NR > 1 { if ($0 ~ /^#/) print; else exit }' "${BASH_SOURCE[0]:-$0}"; exit 0 ;;
    *) echo "ci.sh: 未知参数 '${arg}'（只接受 -h / --help；测试范围用 TEST_CMD 指定）" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"

# 同一秒内改源码且文件大小不变会命中过期 .pyc，先清掉
find . -path ./.git -prune -o -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

if [ -z "${TEST_CMD:-}" ]; then
  if "$PYTHON_BIN" -c 'import pytest' 2>/dev/null; then
    TEST_CMD="$PYTHON_BIN -m pytest -q"
  else
    TEST_CMD="$PYTHON_BIN -B -m unittest discover -s tests"
  fi
fi
echo "[ci] $TEST_CMD"
$TEST_CMD
echo "CI PASS"
