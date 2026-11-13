#!/usr/bin/env bash
# export_framework_pdf.sh — 把 Fig. 1 的 framework.html 无损导出为纯矢量 PDF 与 300 DPI 预览 PNG
#
# 用法: export_framework_pdf.sh [选项]
#   --html PATH       输入 HTML（默认 <仓库根>/manuscript/bmc_initial_draft/figures/framework.html）
#   --out-dir DIR     输出目录（默认与输入 HTML 同目录）
#   --name NAME       输出文件名主干（默认 framework → NAME.pdf / NAME.png）
#   --page-px WxH     HTML 画布像素尺寸，用于核对 Chrome 打印页面（默认 1600x980）
#   --margin PT       pdfcrop 四边留白，单位 pt（默认 4）
#   --dpi N           预览 PNG 分辨率（默认 300）
#   --budget-ms N     Chrome --virtual-time-budget，等 KaTeX 等资源加载（默认 3000）
#   --timeout S       Chrome 打印超时秒数（默认 120）
#   --force           允许覆盖已存在的 NAME.pdf / NAME.png（默认拒绝）
#   -h, --help        显示本帮助
#
# 流水线（handoff-论文生成.md 第 3.4 节；坑 V29 / E35 / G6）:
#   1. Chrome Headless --print-to-pdf（隔离的临时 profile）→ 临时目录 raw.pdf
#   2. 校验 raw.pdf：恰好 1 页；MediaBox = 画布 px × 0.75 pt（±1 pt）；内容 bbox 非空
#   3. pdfcrop 裁白边 → 临时目录 NAME.pdf；校验 1 页、尺寸不大于 raw + 2×margin、bbox 非空
#   4. gs png16m 渲染 NAME.png；校验像素尺寸 ≈ pt/72×dpi（±2 px）
#   5. 全部通过后才 mv 到输出目录；任何一步失败以非零退出，保留临时目录现场
#
# 退出码: 0 成功；1 导出或校验失败；2 用法错误（参数、输入不存在、拒绝覆盖、缺工具）
#
# 环境变量（可覆盖工具路径）:
#   CHROME_BIN   默认 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
#   PDFCROP_BIN  默认 /Library/TeX/texbin/pdfcrop
#   GS_BIN       默认 /usr/local/bin/gs
#
# 导出后仍须按 V29 / E35 读 PNG，放大检查左、中、右、底四块区域，机器校验不能替代目视验收。
set -euo pipefail

usage() { awk 'NR > 1 { if ($0 ~ /^#/) { sub(/^# ?/, ""); print } else exit }' "${BASH_SOURCE[0]}"; }
die_usage() { echo "export_framework_pdf.sh: $*" >&2; exit 2; }

# ---- 1. 参数解析先于任何副作用（坑 G2） ----
HTML=""
OUT_DIR=""
NAME="framework"
PAGE_PX="1600x980"
MARGIN="4"
DPI="300"
BUDGET_MS="3000"
TIMEOUT_S="120"
FORCE=0

need_val() { [ "$#" -ge 2 ] || die_usage "选项 $1 需要一个值"; }
while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --html) need_val "$@"; HTML="$2"; shift 2 ;;
    --out-dir) need_val "$@"; OUT_DIR="$2"; shift 2 ;;
    --name) need_val "$@"; NAME="$2"; shift 2 ;;
    --page-px) need_val "$@"; PAGE_PX="$2"; shift 2 ;;
    --margin) need_val "$@"; MARGIN="$2"; shift 2 ;;
    --dpi) need_val "$@"; DPI="$2"; shift 2 ;;
    --budget-ms) need_val "$@"; BUDGET_MS="$2"; shift 2 ;;
    --timeout) need_val "$@"; TIMEOUT_S="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) die_usage "未知参数 '${1}'（用 --help 查看用法）" ;;
  esac
done

is_uint() { case "$1" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }
PAGE_W_PX="${PAGE_PX%x*}"
PAGE_H_PX="${PAGE_PX#*x}"
is_uint "${PAGE_W_PX}" && is_uint "${PAGE_H_PX}" || die_usage "--page-px 须为 WxH 正整数，收到 '${PAGE_PX}'"
for pair in "margin:${MARGIN}" "dpi:${DPI}" "budget-ms:${BUDGET_MS}" "timeout:${TIMEOUT_S}"; do
  is_uint "${pair#*:}" || die_usage "--${pair%%:*} 须为非负整数，收到 '${pair#*:}'"
done
[ "${DPI}" -gt 0 ] || die_usage "--dpi 须大于 0"
case "${NAME}" in ''|*/*|.*) die_usage "--name 须为不含 / 且不以 . 开头的文件名主干，收到 '${NAME}'" ;; esac

# ---- 2. 解析路径与工具 ----
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_PATH}/../../.." && pwd)"
[ -n "${HTML}" ] || HTML="${REPO_ROOT}/manuscript/bmc_initial_draft/figures/framework.html"
[ -f "${HTML}" ] || die_usage "输入 HTML 不存在: ${HTML}"
HTML_ABS="$(cd "$(dirname "${HTML}")" && pwd)/$(basename "${HTML}")"
[ -n "${OUT_DIR}" ] || OUT_DIR="$(dirname "${HTML_ABS}")"
[ -d "${OUT_DIR}" ] || die_usage "输出目录不存在: ${OUT_DIR}"
OUT_DIR="$(cd "${OUT_DIR}" && pwd)"
OUT_PDF="${OUT_DIR}/${NAME}.pdf"
OUT_PNG="${OUT_DIR}/${NAME}.png"
if [ "${FORCE}" -ne 1 ]; then
  for f in "${OUT_PDF}" "${OUT_PNG}"; do
    [ ! -e "${f}" ] || die_usage "输出已存在，拒绝覆盖（确认要覆盖请加 --force）: ${f}"
  done
fi

CHROME_BIN="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PDFCROP_BIN="${PDFCROP_BIN:-/Library/TeX/texbin/pdfcrop}"
GS_BIN="${GS_BIN:-/usr/local/bin/gs}"
for tool in "${CHROME_BIN}" "${PDFCROP_BIN}" "${GS_BIN}"; do
  [ -x "${tool}" ] || die_usage "找不到可执行工具: ${tool}"
done
# pdfcrop 内部要从 PATH 找 pdftex 与 gs；非交互 shell 的 PATH 未必包含它们
export PATH="$(dirname "${PDFCROP_BIN}"):$(dirname "${GS_BIN}"):${PATH}"

# ---- 3. 临时工作区（坑 G6：先写临时文件、校验后再发布；S2：不递归强删） ----
TMP_BASE="${TMPDIR:-/tmp}"
WORK="$(mktemp -d "${TMP_BASE%/}/export_framework.XXXXXX")"
PROFILE="${WORK}/chrome-profile"
mkdir "${PROFILE}"
OK=0
cleanup() {
  if [ "${OK}" -eq 1 ]; then
    # 只删本脚本创建的已知文件；Chrome profile 是本次 mktemp 目录下的子目录，限定路径后整体删除
    rm -f "${WORK}/raw.pdf" "${WORK}/chrome.log"
    case "${PROFILE}" in "${WORK}"/chrome-profile) rm -rf "${PROFILE}" ;; esac
    rmdir "${WORK}" 2>/dev/null || true
  else
    echo "[export] 失败现场保留在: ${WORK}" >&2
  fi
}
trap cleanup EXIT

fail() { echo "[export] 校验失败: $*" >&2; exit 1; }
log() { echo "[export] $*"; }

# gs 查询：页数与第 1 页 MediaBox（输出 "N\n[x0 y0 x1 y1]"）
pdf_pages_and_box() {
  "${GS_BIN}" -q -dNODISPLAY -dNOSAFER --permit-file-read="$1" \
    -c "($1) (r) file runpdfbegin pdfpagecount = 1 pdfgetpage /MediaBox pget pop == quit"
}
# gs bbox 设备：返回第 1 页 HiResBoundingBox 的 "x0 y0 x1 y1"
pdf_content_bbox() {
  "${GS_BIN}" -q -dNOPAUSE -dBATCH -sDEVICE=bbox "$1" 2>&1 >/dev/null \
    | awk '/^%%HiResBoundingBox:/ { print $2, $3, $4, $5; exit }'
}
# 浮点比较：awk 返回 0 表示条件成立
fcheck() { awk "BEGIN { exit !($1) }"; }

check_pdf() {  # $1=文件 $2=标签；设置 PAGES BOX_W BOX_H
  local file="$1" label="$2" info box bbox
  [ -s "${file}" ] || fail "${label} 不存在或为空: ${file}"
  info="$(pdf_pages_and_box "${file}")" || fail "${label} 无法被 gs 解析"
  PAGES="$(printf '%s\n' "${info}" | sed -n 1p)"
  box="$(printf '%s\n' "${info}" | sed -n 2p | tr -d '[]')"
  [ "${PAGES}" = "1" ] || fail "${label} 页数为 ${PAGES}，应为 1（HTML 内容溢出画布会被分页）"
  set -- ${box}
  [ "$#" -eq 4 ] || fail "${label} MediaBox 无法解析: '${box}'"
  BOX_W="$(awk -v a="$1" -v b="$3" 'BEGIN { printf "%.3f", b - a }')"
  BOX_H="$(awk -v a="$2" -v b="$4" 'BEGIN { printf "%.3f", b - a }')"
  bbox="$(pdf_content_bbox "${file}")"
  [ -n "${bbox}" ] || fail "${label} 取不到内容 bbox"
  set -- ${bbox}
  fcheck "($3 - $1) > 1 && ($4 - $2) > 1" || fail "${label} 内容为空白（bbox = ${bbox}）"
  log "${label}: 1 页, MediaBox ${BOX_W} x ${BOX_H} pt, 内容 bbox ${bbox}"
}

# ---- 4. Chrome Headless 打印 ----
RAW="${WORK}/raw.pdf"
log "Chrome 打印: ${HTML_ABS}"
"${CHROME_BIN}" --headless=new --disable-gpu --no-pdf-header-footer \
  --no-first-run --no-default-browser-check --disable-extensions \
  --user-data-dir="${PROFILE}" \
  --virtual-time-budget="${BUDGET_MS}" \
  --print-to-pdf="${RAW}" \
  "file://${HTML_ABS}" >"${WORK}/chrome.log" 2>&1 &
CHROME_PID=$!
waited=0
while kill -0 "${CHROME_PID}" 2>/dev/null; do
  if [ "${waited}" -ge "${TIMEOUT_S}" ]; then
    kill "${CHROME_PID}" 2>/dev/null || true
    fail "Chrome 打印超过 ${TIMEOUT_S} 秒未结束（日志: ${WORK}/chrome.log）"
  fi
  sleep 1
  waited=$((waited + 1))
done
chrome_rc=0
wait "${CHROME_PID}" || chrome_rc=$?
# 退出码不可信（可能把请求转交给已运行实例后以 0 退出），只认产物
[ -s "${RAW}" ] || fail "Chrome 未产出 PDF（rc=${chrome_rc}，日志: ${WORK}/chrome.log）"

check_pdf "${RAW}" "raw.pdf"
EXP_W="$(awk -v w="${PAGE_W_PX}" 'BEGIN { printf "%.3f", w * 0.75 }')"
EXP_H="$(awk -v h="${PAGE_H_PX}" 'BEGIN { printf "%.3f", h * 0.75 }')"
fcheck "(${BOX_W} - ${EXP_W})^2 <= 1 && (${BOX_H} - ${EXP_H})^2 <= 1" \
  || fail "raw.pdf 页面 ${BOX_W} x ${BOX_H} pt 与画布 ${PAGE_PX} px 应得的 ${EXP_W} x ${EXP_H} pt 不符（检查 @page size）"
RAW_W="${BOX_W}"
RAW_H="${BOX_H}"

# ---- 5. pdfcrop 裁白边 ----
CROP="${WORK}/${NAME}.pdf"
log "pdfcrop 裁边 (margins ${MARGIN} pt)"
"${PDFCROP_BIN}" --margins "${MARGIN} ${MARGIN} ${MARGIN} ${MARGIN}" \
  --gscmd "${GS_BIN}" "${RAW}" "${CROP}" >"${WORK}/pdfcrop.log" 2>&1 \
  || fail "pdfcrop 失败（日志: ${WORK}/pdfcrop.log）"
rm -f "${WORK}/pdfcrop.log"
check_pdf "${CROP}" "${NAME}.pdf"
fcheck "${BOX_W} <= ${RAW_W} + 2 * ${MARGIN} + 1 && ${BOX_H} <= ${RAW_H} + 2 * ${MARGIN} + 1" \
  || fail "裁后尺寸 ${BOX_W} x ${BOX_H} pt 超过 raw ${RAW_W} x ${RAW_H} pt 加留白"
fcheck "${BOX_W} > 2 * ${MARGIN} + 10 && ${BOX_H} > 2 * ${MARGIN} + 10" \
  || fail "裁后尺寸 ${BOX_W} x ${BOX_H} pt 过小，疑似只剩留白"
CROP_W="${BOX_W}"
CROP_H="${BOX_H}"

# ---- 6. gs 300 DPI PNG ----
PNG="${WORK}/${NAME}.png"
log "gs 渲染 PNG (${DPI} DPI)"
"${GS_BIN}" -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r"${DPI}" \
  -dTextAlphaBits=4 -dGraphicsAlphaBits=4 \
  -sOutputFile="${PNG}" "${CROP}" || fail "gs 渲染 PNG 失败"
[ -s "${PNG}" ] || fail "PNG 未生成或为空"
dims="$(sips -g pixelWidth -g pixelHeight "${PNG}" 2>/dev/null | awk '/pixelWidth/ { w = $2 } /pixelHeight/ { h = $2 } END { print w, h }')"
set -- ${dims}
[ "$#" -eq 2 ] || fail "读不到 PNG 像素尺寸"
PNG_W="$1"
PNG_H="$2"
fcheck "(${PNG_W} - ${CROP_W} / 72 * ${DPI})^2 <= 4 && (${PNG_H} - ${CROP_H} / 72 * ${DPI})^2 <= 4" \
  || fail "PNG ${PNG_W} x ${PNG_H} px 与 ${CROP_W} x ${CROP_H} pt @ ${DPI} DPI 不符"
log "${NAME}.png: ${PNG_W} x ${PNG_H} px"

# ---- 7. 全部通过后发布：先拷到输出目录内的隐藏临时名，再同目录 rename ----
STAGE_PDF="${OUT_DIR}/.${NAME}.pdf.export-$$"
STAGE_PNG="${OUT_DIR}/.${NAME}.png.export-$$"
cp "${CROP}" "${STAGE_PDF}" && cp "${PNG}" "${STAGE_PNG}" \
  || { rm -f "${STAGE_PDF}" "${STAGE_PNG}"; fail "无法写入输出目录 ${OUT_DIR}"; }
mv -f "${STAGE_PDF}" "${OUT_PDF}"
mv -f "${STAGE_PNG}" "${OUT_PNG}"
rm -f "${CROP}" "${PNG}"
OK=1
log "完成: ${OUT_PDF}"
log "完成: ${OUT_PNG}"
log "下一步: 读 PNG 放大检查左、中、右、底四块（V29 / E35），确认零压线、零截断"
