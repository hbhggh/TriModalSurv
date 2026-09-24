"""I05 的 GPU 规则（用户锁定 2026-09-23）：实验必须在 GPU 上运行，禁止 CPU。

选卡顺序：
1. 先用空闲卡：连续采样期间始终没有计算进程。
2. 本机没有空闲卡时，才可用正在使用、但每次采样利用率都低于 70% 的卡。
3. 两类卡都要求每次采样的显存余量不低于下限，避免挤掉别人的任务或自己 OOM。

跨服务器挑选由 ``tools/gpu_survey.py`` 在 Mac 本机经 SSH 别名完成（坑 E31）；本模块负责在运行的
那台机器上复核所选卡号，并设置 ``CUDA_VISIBLE_DEVICES``。
"""
from __future__ import annotations

import math
import os
import subprocess
import time

POLICY_KEYS = {'device', 'cpu_forbidden', 'hosts', 'prefer', 'shared_utilization_lt_percent',
               'min_free_memory_mib', 'samples', 'sample_interval_seconds'}
GPU_QUERY = ['nvidia-smi', '--query-gpu=index,uuid,utilization.gpu,memory.free,memory.total',
             '--format=csv,noheader,nounits']
APP_QUERY = ['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader']


def validate_policy(policy: dict) -> dict:
    if not isinstance(policy, dict) or set(policy) != POLICY_KEYS:
        raise ValueError(f'gpu_policy 字段必须恰为 {sorted(POLICY_KEYS)}')
    if policy['device'] != 'cuda' or policy['cpu_forbidden'] is not True or policy['prefer'] != 'idle_first':
        raise ValueError('gpu_policy 必须是 cuda、禁止 CPU、空闲卡优先')
    threshold = policy['shared_utilization_lt_percent']
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < float(threshold) <= 100:
        raise ValueError('共享卡利用率阈值不合法')
    if type(policy['min_free_memory_mib']) is not int or policy['min_free_memory_mib'] <= 0:
        raise ValueError('显存下限不合法')
    if type(policy['samples']) is not int or policy['samples'] < 2:
        raise ValueError('至少连续采样两次')
    if not isinstance(policy['sample_interval_seconds'], (int, float)) or policy['sample_interval_seconds'] < 0:
        raise ValueError('采样间隔不合法')
    if not policy['hosts'] or len(set(policy['hosts'])) != len(policy['hosts']):
        raise ValueError('主机列表为空或重复')
    return policy


def require_gpu(device: str) -> None:
    if device != 'cuda':
        raise ValueError('I05 实验必须在 GPU 上运行，禁止使用 CPU（用户锁定 2026-09-23）')


def parse_gpu_rows(text: str) -> list:
    rows = []
    for line in text.strip().splitlines():
        fields = [item.strip() for item in line.split(',')]
        if len(fields) != 5:
            raise ValueError(f'nvidia-smi GPU 行格式异常: {line!r}')
        utilization, free, total = float(fields[2]), int(fields[3]), int(fields[4])
        if not math.isfinite(utilization) or utilization < 0 or free < 0 or total <= 0:
            raise ValueError(f'nvidia-smi GPU 数值异常: {line!r}')
        rows.append({'index': int(fields[0]), 'uuid': fields[1], 'utilization': utilization,
                     'memory_free_mib': free, 'memory_total_mib': total})
    if not rows:
        raise ValueError('nvidia-smi 没有返回任何 GPU')
    return rows


def parse_app_rows(text: str) -> dict:
    """计算进程按 GPU uuid 计数。"""
    counts = {}
    for line in text.strip().splitlines():
        if not line.strip() or 'No running' in line:
            continue
        uuid = line.split(',')[0].strip()
        counts[uuid] = counts.get(uuid, 0) + 1
    return counts


def merge_sample(gpu_text: str, app_text: str) -> dict:
    """一次采样：{GPU 序号: 利用率、显存余量、计算进程数}。"""
    apps = parse_app_rows(app_text)
    return {row['index']: {**row, 'n_processes': apps.get(row['uuid'], 0)} for row in parse_gpu_rows(gpu_text)}


def local_sample(runner=subprocess.run) -> dict:
    gpu = runner(GPU_QUERY, check=True, capture_output=True, text=True).stdout
    apps = runner(APP_QUERY, check=True, capture_output=True, text=True).stdout
    return merge_sample(gpu, apps)


def collect(sampler, policy: dict, sleep_fn=time.sleep) -> list:
    samples = []
    for index in range(policy['samples']):
        samples.append(sampler())
        if index + 1 < policy['samples'] and policy['sample_interval_seconds']:
            sleep_fn(float(policy['sample_interval_seconds']))
    if len({tuple(sorted(sample)) for sample in samples}) != 1:
        raise RuntimeError('采样期间 GPU 列表发生变化')
    return samples


def classify(samples: list, policy: dict) -> dict:
    """逐卡判定：idle（无进程）、shared_ok（有进程但每次利用率 < 阈值）、busy；显存不足一律 busy。"""
    threshold, floor = float(policy['shared_utilization_lt_percent']), policy['min_free_memory_mib']
    result = {}
    for index in sorted(samples[0]):
        readings = [sample[index] for sample in samples]
        max_util = max(item['utilization'] for item in readings)
        min_free = min(item['memory_free_mib'] for item in readings)
        processes = max(item['n_processes'] for item in readings)
        if min_free < floor:
            status = 'busy'
        elif processes == 0:
            status = 'idle'
        elif max_util < threshold:
            status = 'shared_ok'
        else:
            status = 'busy'
        result[index] = {'class': status, 'max_utilization': max_util, 'min_memory_free_mib': min_free,
                         'max_processes': processes}
    return result


def rank(classes: dict) -> list:
    """空闲卡优先（显存余量大者先），其次低负载共享卡（利用率低者先）。"""
    idle = sorted((i for i, c in classes.items() if c['class'] == 'idle'),
                  key=lambda i: (-classes[i]['min_memory_free_mib'], i))
    shared = sorted((i for i, c in classes.items() if c['class'] == 'shared_ok'),
                    key=lambda i: (classes[i]['max_utilization'], -classes[i]['min_memory_free_mib'], i))
    return idle + shared


def gate(gpu_id: int, policy: dict, *, sampler=local_sample, sleep_fn=time.sleep) -> dict:
    """复核所选卡号是否符合规则；通过后设置 CUDA_VISIBLE_DEVICES。"""
    validate_policy(policy)
    if type(gpu_id) is not int or gpu_id < 0:
        raise ValueError('GPU 运行必须用 --gpu-id 指定物理卡号（先用 tools/gpu_survey.py 选卡）')
    classes = classify(collect(sampler, policy, sleep_fn), policy)
    if gpu_id not in classes:
        raise ValueError(f'本机没有 GPU{gpu_id}')
    status = classes[gpu_id]['class']
    idle = [index for index, item in classes.items() if item['class'] == 'idle']
    if status == 'shared_ok' and idle:
        raise RuntimeError(f'本机有空闲卡 {idle}，按规则必须优先使用空闲卡')
    if status not in ('idle', 'shared_ok'):
        raise RuntimeError(f"GPU{gpu_id} 不可用：利用率不低于 {policy['shared_utilization_lt_percent']}% "
                           '或显存余量不足')
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
    return {'device': 'cuda', 'gpu_id': gpu_id, 'gpu_gate': status, 'classes': {str(k): v for k, v in classes.items()},
            'shared_utilization_lt_percent': policy['shared_utilization_lt_percent'],
            'min_free_memory_mib': policy['min_free_memory_mib'], 'samples': policy['samples']}
