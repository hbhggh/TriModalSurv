#!/usr/bin/env python3
"""跨四台云端服务器只读选卡（在 Mac 本机运行；依赖已配置的 SSH 别名与认证，坑 E31）。

每台主机连续采样若干次 nvidia-smi，按 I05 的 GPU 规则分类：先列所有空闲卡（无计算进程），
没有空闲卡时再列利用率每次都低于 70% 的在用卡；显存余量低于下限的卡不列入。只读，不启动任何任务。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = TOOLS_DIR.parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I05_text_encoder_bcmbert import gpu_policy  # noqa: E402

SEPARATOR = '---I05-APPS---'


def remote_sample(host: str, runner=subprocess.run) -> dict:
    command = ' '.join(gpu_policy.GPU_QUERY) + f'; echo {SEPARATOR}; ' + ' '.join(gpu_policy.APP_QUERY)
    completed = runner(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host, command],
                       check=True, capture_output=True, text=True, timeout=60)
    gpu_text, _, app_text = completed.stdout.partition(SEPARATOR)
    return gpu_policy.merge_sample(gpu_text, app_text)


def survey(policy: dict, *, hosts=None, runner=subprocess.run, sleep_fn=time.sleep) -> dict:
    gpu_policy.validate_policy(policy)
    report, idle, shared = {}, [], []
    for host in hosts or policy['hosts']:
        try:
            samples = gpu_policy.collect(lambda: remote_sample(host, runner), policy, sleep_fn)
        except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as error:
            report[host] = {'reachable': False, 'error': f'{type(error).__name__}: {error}'}
            continue
        classes = gpu_policy.classify(samples, policy)
        report[host] = {'reachable': True, 'gpus': {str(k): v for k, v in classes.items()}}
        for index in gpu_policy.rank(classes):
            entry = {'host': host, 'gpu_id': index, **classes[index]}
            (idle if classes[index]['class'] == 'idle' else shared).append(entry)
    idle.sort(key=lambda e: (-e['min_memory_free_mib'], e['host'], e['gpu_id']))
    shared.sort(key=lambda e: (e['max_utilization'], -e['min_memory_free_mib'], e['host'], e['gpu_id']))
    candidates = idle if idle else shared
    return {'hosts': report, 'idle': idle, 'shared_below_threshold': shared,
            'recommended': candidates[0] if candidates else None,
            'rule': '空闲卡优先；没有空闲卡时才用利用率低于阈值的在用卡',
            'shared_utilization_lt_percent': policy['shared_utilization_lt_percent'],
            'min_free_memory_mib': policy['min_free_memory_mib']}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', type=Path, default=EXPERIMENT_DIR / 'config.yaml')
    parser.add_argument('--hosts', nargs='+', help='缺省为 config.gpu_policy.hosts')
    args = parser.parse_args(argv)
    policy = json.loads(args.config.read_text(encoding='utf-8'))['gpu_policy']
    report = survey(policy, hosts=args.hosts)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['recommended'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
