#!/usr/bin/env bash
# codex_review.sh — Claude 自动发起一次 Codex 只读对抗审查（只看核心逻辑），结果原样落盘为 JSON
#
# 用法: scripts/codex_review.sh <输出目录> [--base <ref>] [补充焦点 ...]
#   不给 --base：审查工作树未提交改动（--scope working-tree）
#   给 --base  ：审查当前分支相对 <ref> 的提交（--scope branch），如 dev 候选用 --base main
#   输出       ：<输出目录>/codex-review.json（companion --json 原文）；已存在则拒绝，不覆盖
#   退出码     ：0 = 审查已完成并落盘（不代表 PASS，结论看 result.verdict）；1 = 调用失败；2 = 用法错误
#
# 环境变量:
#   CODEX_MODEL      (gpt-5.6-sol)
#   CODEX_COMPANION  (自动取 ~/.claude/plugins/cache/openai-codex/codex/ 下最新版本的 scripts/codex-companion.mjs)
set -euo pipefail

usage() { awk 'NR > 1 { if ($0 ~ /^#/) print; else exit }' "${BASH_SOURCE[0]:-$0}"; }
fail() { echo "codex_review: $*" >&2; exit 2; }

# 参数先于任何副作用处理
out="" base="" extra=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --base) [ $# -ge 2 ] || fail "--base 需要一个 ref"; base="$2"; shift 2 ;;
    -*) fail "未知参数 '${1}'（codex_review.sh --help）" ;;
    *) if [ -z "$out" ]; then out="$1"; else extra="${extra:+$extra }$1"; fi; shift ;;
  esac
done
[ -n "$out" ] || fail "缺少输出目录（codex_review.sh --help）"
[ ! -e "$out/codex-review.json" ] || fail "${out}/codex-review.json 已存在，不覆盖；换一个输出目录"

repo="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "不在 git 仓库内"
companion="${CODEX_COMPANION:-}"
if [ -z "$companion" ]; then
  latest="$(ls -d "$HOME"/.claude/plugins/cache/openai-codex/codex/*/ 2>/dev/null | sort -V | tail -1)"
  companion="${latest}scripts/codex-companion.mjs"
fi
[ -f "$companion" ] || { echo "codex_review: 找不到 companion：${companion}" >&2; exit 1; }

focus="只审核心逻辑：正确性与边界条件、数据划分与泄漏、mask / loss / risk 口径、provenance 与可复现性、破坏性或不可逆操作、测试是否真的覆盖了所声称的行为。不要报告语法、风格、命名、注释、格式等不影响正确性的问题。${extra:+ 补充焦点：$extra}"
if [ -n "$base" ]; then scope=(--scope branch --base "$base"); else scope=(--scope working-tree); fi

mkdir -p "$out"
# 每次调用用唯一临时文件：失败现场各自保留，不被下次重试截断；只有通过校验的输出才定名为正式文件
tmp="$(mktemp "$out/.codex-review.XXXXXX")"
echo "[codex_review] companion: ${companion}"
echo "[codex_review] repo: ${repo}  ${scope[*]}  model: ${CODEX_MODEL:-gpt-5.6-sol}"
node "$companion" adversarial-review --wait --cwd "$repo" "${scope[@]}" \
  --model "${CODEX_MODEL:-gpt-5.6-sol}" --json "$focus" > "$tmp" \
  || { echo "codex_review: companion 退出码非 0，原始输出留在 ${tmp}" >&2; exit 1; }
# result 按 companion 自带的 schemas/review-output.schema.json 逐字段校验（必需字段、枚举、类型、范围、finding 结构）
schema="$(dirname "$companion")/../schemas/review-output.schema.json"
[ -f "$schema" ] || { echo "codex_review: 找不到审查 schema：${schema}；原始输出留在 ${tmp}" >&2; exit 1; }
node -e '
  const fs = require("fs");
  let d;
  try { d = JSON.parse(fs.readFileSync(process.argv[1], "utf8")); }
  catch (e) { console.error(`codex_review: 输出不是合法 JSON（${e.message}）`); process.exit(1); }
  const schema = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const errs = [];
  const kind = v => Array.isArray(v) ? "array" : v === null ? "null" : Number.isInteger(v) ? "integer" : typeof v;
  const check = (v, s, at) => {
    const k = kind(v);
    if (s.type && !(s.type === k || (s.type === "number" && k === "integer"))) return errs.push(`${at} 类型应为 ${s.type}，实为 ${k}`);
    if (s.enum && !s.enum.includes(v)) errs.push(`${at} 取值 ${JSON.stringify(v)} 不在 ${JSON.stringify(s.enum)}`);
    if (s.minLength !== undefined && v.length < s.minLength) errs.push(`${at} 为空`);
    if (s.minimum !== undefined && v < s.minimum) errs.push(`${at} 小于 ${s.minimum}`);
    if (s.maximum !== undefined && v > s.maximum) errs.push(`${at} 大于 ${s.maximum}`);
    if (k === "object") {
      for (const r of s.required || []) if (!(r in v)) errs.push(`${at}.${r} 缺失`);
      for (const [key, val] of Object.entries(v)) {
        if (s.properties && s.properties[key]) check(val, s.properties[key], `${at}.${key}`);
        else if (s.additionalProperties === false) errs.push(`${at}.${key} 不在 schema 中`);
      }
    }
    if (k === "array" && s.items) v.forEach((x, i) => check(x, s.items, `${at}[${i}]`));
  };
  if (d && d.parseError) errs.push(`parseError: ${d.parseError}`);
  else if (!d || kind(d.result) !== "object") errs.push("缺少 result");
  else check(d.result, schema, "result");
  if (errs.length) { console.error(`codex_review: 审查输出不符合 schema（${errs.slice(0, 5).join("；")}）`); process.exit(1); }
  const r = d.result;
  console.log(`[codex_review] verdict: ${r.verdict}  findings: ${r.findings.length}`);
  for (const f of r.findings) console.log(`  - [${f.severity}] ${f.title}`);
' "$tmp" "$schema" || { echo "codex_review: 未生成正式结论，原始输出留在 ${tmp}" >&2; exit 1; }
# 原子发布：硬链接在目标已存在时直接失败，不存在「先查后写」的并发窗口；只有发布成功才删临时文件
ln "$tmp" "$out/codex-review.json" 2>/dev/null \
  || { echo "codex_review: ${out}/codex-review.json 已被写入，不覆盖；本次输出留在 ${tmp}" >&2; exit 1; }
rm -f "$tmp"
echo "[codex_review] 已落盘: ${out}/codex-review.json"
