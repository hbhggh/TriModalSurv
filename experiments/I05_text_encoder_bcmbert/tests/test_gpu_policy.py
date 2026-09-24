"""用户锁定的 GPU 规则：必须用 GPU；空闲卡优先；没有空闲卡时才用利用率 < 70% 的在用卡。"""
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.I05_text_encoder_bcmbert import gpu_policy
from experiments.I05_text_encoder_bcmbert.tools import gpu_survey

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture()
def policy():
    return json.loads((EXPERIMENT_DIR / 'config.yaml').read_text(encoding='utf-8'))['gpu_policy']


def sample(*gpus):
    """gpus: (index, utilization, free_mib, n_processes)。"""
    return {index: {'index': index, 'uuid': f'GPU-{index}', 'utilization': float(util), 'memory_free_mib': free,
                    'memory_total_mib': 32768, 'n_processes': procs} for index, util, free, procs in gpus}


def fixed(*samples):
    queue = list(samples)
    return lambda: queue.pop(0) if len(queue) > 1 else queue[0]


def test_config_policy_is_the_user_rule(policy):
    gpu_policy.validate_policy(policy)
    assert policy['device'] == 'cuda' and policy['cpu_forbidden'] is True and policy['prefer'] == 'idle_first'
    assert policy['shared_utilization_lt_percent'] == 70.0
    assert policy['hosts'] == ['landau', 'tako', 'hitode', 'tetra']
    with pytest.raises(ValueError):
        gpu_policy.require_gpu('cpu')
    gpu_policy.require_gpu('cuda')


def test_parse_nvidia_smi_output():
    rows = gpu_policy.merge_sample('0, GPU-a, 12, 30000, 32768\n1, GPU-b, 0, 32000, 32768\n',
                                   'GPU-a, 1234\nGPU-a, 5678\n')
    assert rows[0]['n_processes'] == 2 and rows[1]['n_processes'] == 0
    assert rows[0]['utilization'] == 12.0 and rows[1]['memory_free_mib'] == 32000
    assert gpu_policy.parse_app_rows('No running processes found\n') == {}
    with pytest.raises(ValueError):
        gpu_policy.parse_gpu_rows('0, GPU-a, 12\n')


def test_classify_and_rank(policy):
    samples = [sample((0, 90, 20000, 1), (1, 40, 20000, 2), (2, 0, 30000, 0), (3, 10, 4000, 1)),
               sample((0, 85, 20000, 1), (1, 69, 20000, 2), (2, 0, 30000, 0), (3, 10, 4000, 1)),
               sample((0, 95, 20000, 1), (1, 20, 20000, 2), (2, 0, 30000, 0), (3, 10, 4000, 1))]
    classes = gpu_policy.classify(samples, policy)
    assert [classes[i]['class'] for i in range(4)] == ['busy', 'shared_ok', 'idle', 'busy']
    assert gpu_policy.rank(classes) == [2, 1]
    borderline = [sample((0, 69.9, 20000, 1)), sample((0, 70, 20000, 1)), sample((0, 10, 20000, 1))]
    assert gpu_policy.classify(borderline, policy)[0]['class'] == 'busy'


def test_gate_prefers_idle_then_shared_below_70(policy, monkeypatch):
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    no_sleep = lambda seconds: None
    idle_and_shared = fixed(sample((0, 30, 20000, 1), (1, 0, 30000, 0)))
    record = gpu_policy.gate(1, policy, sampler=idle_and_shared, sleep_fn=no_sleep)
    assert record['gpu_gate'] == 'idle' and os.environ['CUDA_VISIBLE_DEVICES'] == '1'
    with pytest.raises(RuntimeError, match='优先使用空闲卡'):
        gpu_policy.gate(0, policy, sampler=idle_and_shared, sleep_fn=no_sleep)
    only_shared = fixed(sample((0, 30, 20000, 1), (1, 80, 20000, 1)))
    assert gpu_policy.gate(0, policy, sampler=only_shared, sleep_fn=no_sleep)['gpu_gate'] == 'shared_ok'
    with pytest.raises(RuntimeError, match='不可用'):
        gpu_policy.gate(1, policy, sampler=only_shared, sleep_fn=no_sleep)
    spike = fixed(sample((0, 30, 20000, 1)), sample((0, 75, 20000, 1)), sample((0, 30, 20000, 1)))
    with pytest.raises(RuntimeError, match='不可用'):
        gpu_policy.gate(0, policy, sampler=spike, sleep_fn=no_sleep)
    with pytest.raises(ValueError):
        gpu_policy.gate(None, policy, sampler=only_shared, sleep_fn=no_sleep)


def test_survey_ranks_idle_across_hosts_before_shared(policy):
    outputs = {
        'landau': ('0, GPU-l0, 50, 20000, 32768\n1, GPU-l1, 10, 25000, 32768\n', 'GPU-l0, 1\nGPU-l1, 2\n'),
        'tako': ('0, GPU-t0, 0, 30000, 32768\n', ''),
        'hitode': ('0, GPU-h0, 95, 20000, 32768\n', 'GPU-h0, 3\n'),
    }

    def runner(command, **kwargs):
        host = command[5]
        if host == 'tetra':
            raise subprocess.CalledProcessError(255, command)
        gpu, apps = outputs[host]
        return SimpleNamespace(stdout=gpu + gpu_survey.SEPARATOR + '\n' + apps)

    report = gpu_survey.survey(policy, runner=runner, sleep_fn=lambda seconds: None)
    assert report['recommended'] == {**report['idle'][0]} and report['recommended']['host'] == 'tako'
    assert [(e['host'], e['gpu_id']) for e in report['shared_below_threshold']] == [('landau', 1), ('landau', 0)]
    assert report['hosts']['tetra']['reachable'] is False
    assert report['hosts']['hitode']['gpus']['0']['class'] == 'busy'

    def no_idle(command, **kwargs):
        host = command[5]
        if host != 'landau':
            raise subprocess.CalledProcessError(255, command)
        gpu, apps = outputs['landau']
        return SimpleNamespace(stdout=gpu + gpu_survey.SEPARATOR + '\n' + apps)

    fallback = gpu_survey.survey(policy, runner=no_idle, sleep_fn=lambda seconds: None)
    assert fallback['idle'] == [] and fallback['recommended']['gpu_id'] == 1
