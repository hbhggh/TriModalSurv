#!/bin/bash
# 第一层：任务启动包装。用法: jobrun.sh <job_id> <gpu标签> <log绝对路径> -- <command...>
# 效果: setsid 脱管启动；写 jobs/<id>/job.json；结束按退出码写 done.flag / fail.flag(含退出码+末50行日志)
set -u
JOBS=/home/wuhao/NPJ/jobs
job_id=$1; gpu=$2; log=$3; shift 3
[ "${1:-}" = "--" ] && shift
jd=$JOBS/$job_id
mkdir -p "$jd" "$(dirname "$log")"
rm -f "$jd/done.flag" "$jd/fail.flag" "$jd/running.flag"

cmd="$*"
setsid nohup bash -c "
  trap '' HUP
  touch '$jd/running.flag'
  $cmd >> '$log' 2>&1
  ec=\$?
  rm -f '$jd/running.flag'
  if [ \$ec -eq 0 ]; then
    date +'%F %T' > '$jd/done.flag'
  else
    { echo \"exit_code=\$ec at \$(date +'%F %T')\"; echo '--- last 50 log lines ---'; tail -50 '$log'; } > '$jd/fail.flag'
  fi
" > /dev/null 2>&1 < /dev/null &
wpid=$!
esc_cmd=$(printf '%s' "$cmd" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
cat > "$jd/job.json" <<J
{"id":"$job_id","pid":$wpid,"pgid":$wpid,"cmd":$esc_cmd,"start_ts":"$(date +'%F %T')","gpu":"$gpu","log":"$log","cwd":"$PWD"}
J
echo "job $job_id started pid=$wpid log=$log"
