#!/bin/bash
# 第三层：mac 端机械判定（mac cron 每 20 分钟）。只读 landau 的 status.json，按七行规则判定，
# 写 YYYYMMDD-status.md；命中报警写 ALERT.md + macOS 通知。当前 AUTO_RESTART=off：绝不拉起。
set -u
MON="/Users/wuhao/Desktop/TriModalSurv/collab/monitor"
. "$MON/rules.env" 2>/dev/null || true
TS=$(date +'%F %T')
MD="$MON/$(date +%Y%m%d)-status.md"
STATE_CACHE="$MON/.last_status.json"
STALL_CACHE="$MON/.stall_counts"

raw=$(ssh -o ConnectTimeout=10 -o BatchMode=yes landau 'cat /home/wuhao/NPJ/jobs/status.json 2>/dev/null' 2>/dev/null)
if [ -z "$raw" ]; then
  {
    echo ""
    echo "## $TS — CHANNEL_DOWN"
    echo "ssh 不可达或 status.json 缺失。按规则：通道断 ≠ 任务死亡，沿用上次状态，不判死、不拉起。"
    [ -f "$STATE_CACHE" ] && echo "上次状态时间：$(python3 -c "import json;print(json.load(open('$STATE_CACHE'))['ts'])" 2>/dev/null)"
  } >> "$MD"
  exit 0
fi
printf '%s' "$raw" > "$STATE_CACHE"

python3 - "$MD" "$TS" "$MON" "$STALL_CACHE" "${STALL_ALERT_ROUNDS:-2}" <<'PY'
import json, os, subprocess, sys

md, ts, mon, stall_cache, stall_rounds = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
st = json.load(open(f"{mon}/.last_status.json"))
stalls = {}
if os.path.exists(stall_cache):
    for line in open(stall_cache):
        if ":" in line:
            k, v = line.strip().rsplit(":", 1)
            stalls[k] = int(v)

alerts, lines = [], []
for j in st.get("jobs", []):
    jid, state = j.get("id", "?"), j.get("state", "?")
    dup = j.get("dup_count", 1)
    tail = " | ".join(j.get("log_tail3", [])[-1:])[:120]
    lines.append(f"- `{jid}` state=**{state}** pid={j.get('pid')} log_age={j.get('log_mtime_age_s')}s dup={dup} {tail}")
    if state == "stalled":
        stalls[jid] = stalls.get(jid, 0) + 1
        if stalls[jid] >= stall_rounds:
            alerts.append(f"{jid}: stalled 连续 {stalls[jid]} 轮（日志无更新）")
    else:
        stalls.pop(jid, None)
    if state == "failed":
        alerts.append(f"{jid}: 确认失败（fail.flag 存在）——AUTO_RESTART=off，仅报警")
    if state == "gone":
        alerts.append(f"{jid}: 异常退出（无 flag）——日志尾部已在 status 记录")
    if isinstance(dup, int) and dup > 1 and not jid.startswith("_adhoc_gdc"):
        alerts.append(f"{jid}: 检测到 {dup} 个同类进程（疑似重复派单）——不自动杀，待人工裁定")

with open(stall_cache, "w") as f:
    for k, v in stalls.items():
        f.write(f"{k}:{v}\n")

with open(md, "a") as f:
    f.write(f"\n## {ts} — {'ALERT' if alerts else 'OK'}（{len(st.get('jobs', []))} 任务，landau 时刻 {st.get('ts')}）\n")
    f.writelines(l + "\n" for l in lines)
    if alerts:
        f.write("\n**报警**：\n" + "".join(f"- {a}\n" for a in alerts))

if alerts:
    with open(f"{mon}/ALERT.md", "w") as f:
        f.write(f"# ALERT {ts}\n\n" + "".join(f"- {a}\n" for a in alerts) + "\n处置建议：打开 Claude Code 会话，让 Claude 读本文件与当日 status.md 后按白名单规则决策。\n")
    subprocess.run(["osascript", "-e",
                    f'display notification "{len(alerts)} 个任务报警，详见 collab/monitor/ALERT.md" with title "landau 任务监视器"'],
                   capture_output=True)
else:
    # 全绿时清掉旧 ALERT，避免误导
    ap = f"{mon}/ALERT.md"
    if os.path.exists(ap):
        os.remove(ap)
print("check done:", "ALERT" if alerts else "OK")
PY
