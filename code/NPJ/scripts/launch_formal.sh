#!/usr/bin/env bash
set -uo pipefail

usage() {
    echo "Usage: $0 <gpu_id> <absolute_log_path> -- <python main_survival.py full command>" >&2
    exit 64
}

if [[ $# -lt 4 ]]; then
    usage
fi

gpu_id=$1
log_path=$2
shift 2

if [[ $log_path != /* ]]; then
    echo "FORMAL_LAUNCH_ERROR: log path must be absolute" >&2
    exit 64
fi
if [[ $1 != "--" ]]; then
    usage
fi
shift
if [[ $# -eq 0 ]]; then
    usage
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repo_dir=$(cd "$script_dir/.." && pwd -P)
gpu_config=${GPU_CONFIG:-$repo_dir/config/gpu_train.yaml}
python_bin=${PYTHON_BIN:-python}
gate_script=$script_dir/gpu_util_gate.py

if [[ ! -d $(dirname "$log_path") ]]; then
    echo "FORMAL_LAUNCH_ERROR: log parent directory does not exist" >&2
    exit 73
fi
: >> "$log_path"

policy_json=$("$python_bin" "$gate_script" --config "$gpu_config" --policy-json 2>> "$log_path")
policy_status=$?
if [[ $policy_status -ne 0 ]]; then
    echo "FORMAL_GATE_ERROR: cannot read GPU policy" >> "$log_path"
    exit 3
fi
warmup_sec=$(
    "$python_bin" -c 'import json,sys; print(json.loads(sys.argv[1]).get("gpu_util_warmup_sec"))' "$policy_json"
)
min_percent=$(
    "$python_bin" -c 'import json,sys; print(json.loads(sys.argv[1]).get("gpu_util_min_percent"))' "$policy_json"
)
allow_low=$(
    "$python_bin" -c 'import json,sys; print("1" if json.loads(sys.argv[1]).get("allow_low_gpu_util") is True else "0")' "$policy_json"
)
low_reason=$(
    "$python_bin" -c 'import json,sys; print(str(json.loads(sys.argv[1]).get("low_gpu_util_reason", "")).strip())' "$policy_json"
)
if [[ $warmup_sec == "None" || $min_percent == "None" ]]; then
    echo "FORMAL_GATE_ERROR: gpu_util_warmup_sec and gpu_util_min_percent are required" >> "$log_path"
    exit 3
fi

export FORMAL_RUN=1
export CUDA_VISIBLE_DEVICES=$gpu_id
setsid "$@" >> "$log_path" 2>&1 &
training_pid=$!
training_pgid=$training_pid
echo "FORMAL_LAUNCH_PID=$training_pid PGID=$training_pgid GPU=$gpu_id" >> "$log_path"

gate_output=$(
    "$python_bin" "$gate_script" \
        --gpu "$gpu_id" \
        --warmup "$warmup_sec" \
        --interval 5 \
        --min "$min_percent" \
        --watch-pid "$training_pid" 2>&1
)
gate_status=$?
printf '%s\n' "$gate_output" >> "$log_path"

terminate_training() {
    kill -TERM -- "-$training_pgid" 2>/dev/null \
        || kill -TERM "$training_pid" 2>/dev/null \
        || true
    wait "$training_pid" 2>/dev/null || true
}

if [[ $gate_status -eq 0 ]]; then
    wait "$training_pid"
    exit $?
fi

if [[ $gate_status -eq 4 ]]; then
    wait "$training_pid"
    training_status=$?
    if [[ $training_status -eq 0 ]]; then
        echo "FORMAL_GATE_EARLY_COMPLETE" >> "$log_path"
        exit 0
    fi
    echo "FORMAL_TRAINING_FAILED EXIT_CODE=$training_status" >> "$log_path"
    exit "$training_status"
fi

if [[ $gate_status -eq 3 ]]; then
    echo "FORMAL_GATE_ERROR: sampling failed; terminating PGID=$training_pgid" >> "$log_path"
    terminate_training
    exit 3
fi

if [[ $allow_low == "1" && -n $low_reason ]]; then
    echo "FORMAL_GATE_WAIVER=1 REASON=$low_reason" >> "$log_path"
    wait "$training_pid"
    exit $?
fi

if [[ $allow_low == "1" ]]; then
    echo "FORMAL_GATE_REJECTED: allow_low_gpu_util=true but low_gpu_util_reason is empty" >> "$log_path"
else
    echo "FORMAL_GATE_REJECTED: utilization below contract minimum" >> "$log_path"
fi
terminate_training
exit 2
