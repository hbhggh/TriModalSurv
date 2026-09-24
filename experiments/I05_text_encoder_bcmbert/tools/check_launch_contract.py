#!/usr/bin/env python3
"""发车契约核对（坑 D16）：I05 清单与既有 e0 臂的 launcher dry-run 命令逐参对比。

只允许 ``--model_config`` 与 ``--result_path`` 两项取值不同；其余参数（lr、epochs、batch、hidden、
bin_mode、网络、补偿、标签、GPU 配置、seed、癌种）必须逐字相同。dry-run 零副作用：不预热、不写状态、不起进程。
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = TOOLS_DIR.parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
LAUNCHER = REPO_ROOT / 'scripts' / 'train_launcher.py'
ALLOWED = ('--model_config', '--result_path')
REQUIRED = {'--network_type': 'NPJC', '--compensator': 'none', '--hidden_size': '256', '--lr': '0.0001',
            '--epochs': '50', '--batch_size': '32', '--bin_mode': 'author'}
CANCERS = ('BLCA', 'BRCA', 'LGG', 'LUAD', 'UCEC')
SEEDS = (123, 132, 213, 231, 321)


def dry_run(python, extra, scratch: Path, tag: str) -> list:
    command = [python, str(LAUNCHER), *extra, '--result-path', str(scratch / f'{tag}_out'),
               '--state-file', str(scratch / f'{tag}_state.json'), '--logs-dir', str(scratch / f'{tag}_logs'),
               '--dry_run']
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f'{tag} dry-run 失败（exit {completed.returncode}）:\n{completed.stderr[-2000:]}')
    runs = []
    for line in completed.stdout.splitlines():
        if not line.startswith('DRY_RUN index='):
            continue
        head, _, tail = line.partition(' command=')
        fields = dict(token.split('=', 1) for token in head.split()[1:])
        runs.append({'name': fields['name'], 'arm': fields['arm'], 'cancer': fields['cancer'],
                     'seed': int(fields['seed']), 'checkpoint': fields['checkpoint'], 'command': shlex.split(tail)})
    for path in (scratch / f'{tag}_logs', scratch / f'{tag}_state.json'):
        if path.exists():
            raise RuntimeError(f'dry-run 产生了副作用: {path}')
    return runs


def _value(command, flag):
    return command[command.index(flag) + 1] if flag in command else None


def compare(i05_runs, e0_runs) -> dict:
    by_i05 = {(run['cancer'], run['seed']): run for run in i05_runs}
    by_e0 = {(run['cancer'], run['seed']): run for run in e0_runs}
    expected = {(cancer, seed) for cancer in CANCERS for seed in SEEDS}
    problems = []
    if set(by_i05) != expected or len(i05_runs) != len(expected):
        problems.append('I05 清单不是恰好 5 癌 × 5 seed')
    if set(by_e0) != expected:
        problems.append('e0 对照不是恰好 5 癌 × 5 seed')
    differences = {}
    for key in sorted(expected & set(by_i05) & set(by_e0)):
        new, old = by_i05[key]['command'], by_e0[key]['command']
        if len(new) != len(old):
            problems.append(f'{key}: 命令长度不同')
            continue
        changed = sorted({new[index - 1] for index in range(len(new)) if new[index] != old[index]})
        differences[f'{key[0]}_s{key[1]}'] = changed
        if not set(changed) <= set(ALLOWED):
            problems.append(f'{key}: 出现不允许的差异 {changed}')
        for flag, value in REQUIRED.items():
            if _value(new, flag) != value:
                problems.append(f'{key}: {flag} 应为 {value}，实际 {_value(new, flag)}')
        if Path(by_i05[key]['checkpoint']).name != Path(by_e0[key]['checkpoint']).name:
            problems.append(f'{key}: ckpt 文件名与 e0 不同')
        if Path(by_i05[key]['checkpoint']).parent.parent == Path(by_e0[key]['checkpoint']).parent.parent:
            problems.append(f'{key}: ckpt 根目录与 e0 相同，会被幂等跳过或拒写')
    order = [(run['seed'], run['cancer']) for run in i05_runs]
    seed_major = [seed for seed, _ in order] == sorted(seed for seed, _ in order)
    first_block_distinct = len({cancer for _, cancer in order[:5]}) == 5
    if not (seed_major and first_block_distinct):
        problems.append('I05 清单不是 seed 主序')
    return {'ok': not problems, 'problems': problems, 'n_i05': len(i05_runs), 'n_e0': len(e0_runs),
            'allowed_differences': list(ALLOWED), 'observed_differences': differences,
            'seed_major_order': seed_major}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--plan', type=Path, default=EXPERIMENT_DIR / 'train_plan.yaml')
    parser.add_argument('--model-config', type=Path, default=EXPERIMENT_DIR / 'model_config.yml')
    parser.add_argument('--out', type=Path, help='把对比报告写成 JSON')
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='i05-dryrun-') as directory:
        scratch = Path(directory)
        i05 = dry_run(args.python, ['--plan', str(args.plan), '--model-config', str(args.model_config)], scratch, 'i05')
        e0 = dry_run(args.python, ['--arms', 'e0', '--cancers', ','.join(CANCERS),
                                   '--seeds', ','.join(map(str, SEEDS))], scratch, 'e0')
        report = compare(i05, e0)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
