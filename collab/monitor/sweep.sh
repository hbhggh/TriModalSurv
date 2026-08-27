#!/bin/bash
# Routine 巡检的机械采集层：聚合 mac 后台任务 / landau 状态 / 监视器产物。只读。
set -u
NOW=$(date +%s)
echo "== [A] mac 侧 Claude 后台任务 output（24h 内活跃，含所有会话）=="
find /private/tmp/claude-501 -maxdepth 4 -path "*/tasks/*.output" -mmin -1440 2>/dev/null | while read -r f; do
  m=$(stat -f %m "$f" 2>/dev/null || echo 0)
  age=$(( (NOW - m) / 60 ))
  sid=$(echo "$f" | awk -F/ '{print $(NF-2)}' | cut -c1-8)
  tail_txt=$(tail -c 300 "$f" 2>/dev/null | tr '\n' ' ' | tail -c 110)
  printf "task=%s sess=%s idle=%dmin tail: %s\n" "$(basename "$f" .output)" "$sid" "$age" "$tail_txt"
done
echo ""
echo "== [B] landau status.json =="
ssh -o ConnectTimeout=10 -o BatchMode=yes landau 'cat /home/wuhao/NPJ/jobs/status.json 2>/dev/null' 2>/dev/null || echo "CHANNEL_DOWN"
echo ""
echo "== [C] ALERT.md =="
cat "/Users/wuhao/Desktop/TriModalSurv/collab/monitor/ALERT.md" 2>/dev/null || echo "(无 ALERT)"
echo ""
echo "== [D] 当日 cron 判定最后一节 =="
tail -12 "/Users/wuhao/Desktop/TriModalSurv/collab/monitor/$(date +%Y%m%d)-status.md" 2>/dev/null || echo "(今日尚无记录)"
