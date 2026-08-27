#!/bin/bash
# 第二层：状态采集器（landau cron 每 10 分钟，flock 单实例由 crontab 行保证）
# 只做：读 jobs/*/job.json → kill -0 → log mtime → flags → 写 jobs/status.json
# 兜底：无 job.json 的在途任务用 pgrep -f 合成条目（四类）
export PATH=/usr/bin:/bin:/usr/local/bin
python3 - <<'PY'
import glob, json, os, subprocess, time

JOBS = "/home/wuhao/NPJ/jobs"
os.makedirs(JOBS, exist_ok=True)
now = time.time()
out = {"ts": time.strftime("%F %T"), "host": "landau", "jobs": []}

def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False

def log_tail(path, n=3):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 4000))
            lines = f.read().decode("utf-8", "replace").replace("\r", "\n").splitlines()
            return [l for l in lines if l.strip()][-n:]
    except Exception:
        return []

def dup_count(pattern):
    try:
        r = subprocess.run(["pgrep", "-fc", pattern], capture_output=True, text=True)
        return int(r.stdout.strip() or 0)
    except Exception:
        return -1

seen_pids = set()
for jf in sorted(glob.glob(f"{JOBS}/*/job.json")):
    try:
        j = json.load(open(jf))
    except Exception:
        continue
    jd = os.path.dirname(jf)
    flags = {k: os.path.exists(f"{jd}/{k}.flag") for k in ("running", "done", "fail")}
    a = alive(j.get("pid", -1))
    if a:
        seen_pids.add(int(j["pid"]))
    log = j.get("log", "")
    age = int(now - os.path.getmtime(log)) if log and os.path.exists(log) else -1
    if a:
        state = "stalled" if age >= 0 and age > 1200 else "running"
    elif flags["done"]:
        state = "done"
    elif flags["fail"]:
        state = "failed"
    else:
        state = "gone"
    out["jobs"].append({"id": j["id"], "pid": j.get("pid"), "alive": a, "log": log,
                        "log_mtime_age_s": age, "flags": flags, "state": state,
                        "log_tail3": log_tail(log)})

# pgrep 兜底：四类已知任务模式（未经 jobrun 启动的在途任务）
FALLBACK = {"gdc_fetch": "gdc_fetch_star_counts.py",
            "npj_train": "main_survival.py",
            "uni2_convert": "convert_uni2h_to_npj.py",
            "bulkrnabert": "bulkrnabert"}
for label, pat in FALLBACK.items():
    try:
        r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
        pids = [int(p) for p in r.stdout.split() if p.strip()]
    except Exception:
        pids = []
    pids = [p for p in pids if p not in seen_pids]
    if pids:
        out["jobs"].append({"id": f"_adhoc_{label}", "pid": pids[0], "alive": True, "log": "",
                            "log_mtime_age_s": -1, "flags": {}, "state": "running",
                            "dup_count": len(pids), "log_tail3": []})

tmp = f"{JOBS}/status.json.tmp"
json.dump(out, open(tmp, "w"), ensure_ascii=False, indent=1)
os.replace(tmp, f"{JOBS}/status.json")
print(f"keeper: {len(out['jobs'])} jobs @ {out['ts']}")
PY
