#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

import yaml


def load_policy(config_path):
    try:
        with Path(config_path).open("r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"cannot read GPU config {config_path}: {exc}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"GPU config must be a mapping: {config_path}")
    return config


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--gpu")
    parser.add_argument("--warmup", type=float)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--min", dest="min_percent", type=float)
    parser.add_argument("--watch-pid", type=int)
    parser.add_argument("--policy-json", action="store_true")
    return parser.parse_args(argv)


def sample_gpu(gpu_id):
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used",
        "--format=csv,noheader,nounits",
        "-i",
        str(gpu_id),
    ]
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"nvidia-smi failed ({completed.returncode}): {detail}")
    line = completed.stdout.strip().splitlines()
    if len(line) != 1:
        raise RuntimeError(f"unexpected nvidia-smi output: {completed.stdout!r}")
    fields = [field.strip() for field in line[0].split(",")]
    if len(fields) != 2:
        raise RuntimeError(f"unexpected nvidia-smi row: {line[0]!r}")
    try:
        return float(fields[0]), float(fields[1])
    except ValueError as exc:
        raise RuntimeError(f"non-numeric nvidia-smi row: {line[0]!r}") from exc


def process_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_gate(gpu_id, warmup, interval, min_percent, watch_pid=None):
    if warmup < 0:
        raise ValueError("warmup must be >= 0")
    if interval <= 0:
        raise ValueError("interval must be > 0")
    utilities = []
    memories = []
    early_exit = False
    deadline = time.monotonic() + warmup
    while True:
        if watch_pid is not None and not process_is_alive(watch_pid):
            early_exit = True
            break
        if utilities and time.monotonic() >= deadline:
            break
        utilization, memory_used = sample_gpu(gpu_id)
        utilities.append(utilization)
        memories.append(memory_used)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))

    util_median = statistics.median(utilities) if utilities else None
    result = {
        "util_median": util_median,
        "mem_peak_mib": max(memories) if memories else None,
        "samples": len(utilities),
        "pass": not early_exit and util_median >= min_percent,
        "early_exit": early_exit,
    }
    print(json.dumps(result, separators=(",", ":")))
    if early_exit:
        return 4
    return 0 if result["pass"] else 2


def main(argv=None):
    args = parse_args(argv)
    try:
        policy = load_policy(args.config) if args.config else {}
        if args.policy_json:
            print(
                json.dumps(
                    {
                        "gpu_util_warmup_sec": policy.get(
                            "gpu_util_warmup_sec"
                        ),
                        "gpu_util_min_percent": policy.get(
                            "gpu_util_min_percent"
                        ),
                        "allow_low_gpu_util": policy.get(
                            "allow_low_gpu_util", False
                        ),
                        "low_gpu_util_reason": policy.get(
                            "low_gpu_util_reason", ""
                        ),
                    },
                    separators=(",", ":"),
                )
            )
            return 0

        if shutil.which("nvidia-smi") is None:
            raise RuntimeError("nvidia-smi not found in PATH")
        if args.gpu is None:
            raise ValueError("--gpu is required")
        if args.watch_pid is not None and args.watch_pid < 1:
            raise ValueError("--watch-pid must be a positive integer")
        warmup = (
            args.warmup
            if args.warmup is not None
            else policy.get("gpu_util_warmup_sec")
        )
        min_percent = (
            args.min_percent
            if args.min_percent is not None
            else policy.get("gpu_util_min_percent")
        )
        if warmup is None or min_percent is None:
            raise ValueError("--warmup/--min or a complete --config is required")
        return run_gate(
            args.gpu,
            float(warmup),
            args.interval,
            float(min_percent),
            watch_pid=args.watch_pid,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"GPU_UTIL_GATE_ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
