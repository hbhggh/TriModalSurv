"""I07 发车器（用户 2026-10-10 裁决：train_launcher 写死 NPJ 入口，I07 自带发车器，守同样的规矩；由 jobrun.sh 托管）。

子命令：
  train     清单 = 癌 × 折 × 臂；每卡并发上限；run.json 已存在即跳过（幂等）；每个运行独立日志；状态写 campaign.json。
  digest    测试授权摘要 = 每个运行的 best.pt 与 run.json + 五份资产 manifest + 源码 commit + 评测协议（provenance.auth_digest；坑 V35，节点一 high 2）。
  evaluate  必须传 --auth-digest，且与重算的摘要一致才执行；逐运行写 test_metrics.json。
三个子命令都先过源码身份门（commit 已知、dirty=false、等于 --expected-commit；节点一 high 3），
train / digest / evaluate 都按 manifest 逐文件校验资产内容。
GPU 合同：模型很小、数据常驻显存，利用率达不到门禁时必须显式 --allow-low-gpu-util "<理由>"，理由写入 campaign.json。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CANCERS = ('BLCA', 'BRCA', 'LUAD', 'LGG', 'UCEC')
ARMS = ('tri', 'wsi', 'rna', 'text')
CODE_ROOT = Path(__file__).resolve().parents[2]

from . import provenance  # noqa: E402


def plan(cancers, folds, arms):
    return [(c, k, a) for c in cancers for k in folds for a in arms]


def run_dir(runs: Path, c, k, a) -> Path:
    return runs / c / f'fold{k}' / a


def ckpt_hashes(runs: Path, items) -> dict:
    """{'c/k/a': {'ckpt': best.pt 的 sha256, 'run': run.json 的 sha256}}（第 3 轮 high 2：run.json 一并绑定）。"""
    out = {}
    for c, k, a in sorted(items):
        d = run_dir(runs, c, k, a)
        for f in ('best.pt', 'run.json'):
            if not (d / f).exists():
                raise FileNotFoundError(f'缺 {f}：{d}')
        out[f'{c}/{k}/{a}'] = {'ckpt': hashlib.sha256((d / 'best.pt').read_bytes()).hexdigest(),
                               'run': hashlib.sha256((d / 'run.json').read_bytes()).hexdigest()}
    return out


def digest(runs: Path, items, assets: Path, commit: str) -> str:
    return provenance.auth_digest(ckpt_hashes(runs, items), provenance.asset_fingerprint(assets), commit)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _save(path: Path, state):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def schedule(jobs, gpus, per_gpu, make_cmd, state, state_path, poll=2.0):
    """jobs: [(key, out_dir)]；同一张卡同时最多 per_gpu 个。返回失败的 key 列表。"""
    slots = [g for g in gpus for _ in range(per_gpu)]
    pending, active, failed = list(jobs), {}, []
    while pending or active:
        free = [s for s in range(len(slots)) if s not in active]
        while pending and free:
            s = free.pop(0)
            key, log = pending.pop(0)
            log.parent.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(slots[s]))
            fh = open(log, 'a')
            p = subprocess.Popen(make_cmd(key), cwd=CODE_ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
            active[s] = (key, p, fh)
            state['runs'][key] = {'status': 'running', 'gpu': slots[s], 'start': _now()}
            _save(state_path, state)
        time.sleep(poll)
        for s, (key, p, fh) in list(active.items()):
            if p.poll() is None:
                continue
            fh.close()
            ok = p.returncode == 0
            state['runs'][key].update(status='done' if ok else 'failed', returncode=p.returncode, end=_now())
            if not ok:
                failed.append(key)
            _save(state_path, state)
            del active[s]
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['train', 'digest', 'evaluate'])
    ap.add_argument('--assets', required=True, type=Path)
    ap.add_argument('--runs', required=True, type=Path)
    ap.add_argument('--cancers', default=','.join(CANCERS))
    ap.add_argument('--folds', default='0,1,2,3,4')
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--gpus', default='0')
    ap.add_argument('--per-gpu', type=int, default=2)
    ap.add_argument('--epochs', type=int, default=50, choices=[50, 100])
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--allow-low-gpu-util', default='', help='利用率达不到门禁时必须写理由')
    ap.add_argument('--auth-digest', default='')
    ap.add_argument('--expected-commit', required=True)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    cancers = [c for c in a.cancers.split(',') if c]
    if set(cancers) - set(CANCERS):
        raise SystemExit(f'未知癌种：{cancers}')
    arms = [x for x in a.arms.split(',') if x]
    folds = [int(x) for x in a.folds.split(',') if x]
    items = plan(cancers, folds, arms)
    gpus = [g for g in a.gpus.split(',') if g]
    ident = provenance.require_clean(a.expected_commit)
    provenance.verify_assets(a.assets)

    if a.command == 'digest':
        print(digest(a.runs, items, a.assets, ident['commit']))
        return
    if a.command == 'train':
        if not a.allow_low_gpu_util:
            raise SystemExit('I07 模型很小、数据常驻显存，GPU 利用率达不到 50% 门禁；请用 --allow-low-gpu-util "<理由>" 显式豁免')
        todo = [(f'{c}/{k}/{x}', run_dir(a.runs, c, k, x)) for c, k, x in items
                if not (run_dir(a.runs, c, k, x) / 'run.json').exists()]

        def cmd(key):
            c, k, x = key.split('/')
            return [a.python, '-m', 'experiments.I07_ps3style_backbone.train', '--assets', str(a.assets),
                    '--cancer', c, '--fold', k, '--arm', x, '--out', str(a.runs), '--epochs', str(a.epochs),
                    '--device', 'cuda', '--expected-commit', a.expected_commit]
    else:
        ck = ckpt_hashes(a.runs, items)
        expect = provenance.auth_digest(ck, provenance.asset_fingerprint(a.assets), ident['commit'])
        if a.auth_digest != expect:
            raise SystemExit(f'授权摘要不符：授权 {a.auth_digest!r}，当前 {expect}（ckpt、资产或代码变过都必须重新授权）')
        todo = [(f'{c}/{k}/{x}', run_dir(a.runs, c, k, x)) for c, k, x in items
                if not (run_dir(a.runs, c, k, x) / 'test_metrics.json').exists()]

        def cmd(key):
            c, k, x = key.split('/')
            return [a.python, '-m', 'experiments.I07_ps3style_backbone.evaluate', '--assets', str(a.assets),
                    '--runs', str(a.runs), '--cancer', c, '--fold', k, '--arm', x, '--device', 'cuda',
                    '--expected-commit', a.expected_commit, '--auth-digest', a.auth_digest, '--ckpt-sha256', ck[key]['ckpt'],
                    '--run-sha256', ck[key]['run'],
                    '--plan-cancers', ','.join(cancers), '--plan-folds', ','.join(map(str, folds)),
                    '--plan-arms', ','.join(arms)]
    print(f'{a.command}: 清单 {len(items)} 个，待运行 {len(todo)} 个')
    if a.dry_run:
        for key, _ in todo:
            print(' '.join(cmd(key)))
        return
    a.runs.mkdir(parents=True, exist_ok=True)
    state_path = a.runs / f'campaign_{a.command}.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'runs': {}}
    state.setdefault('meta', []).append({'start': _now(), 'argv': sys.argv, 'allow_low_gpu_util': a.allow_low_gpu_util,
                                         'auth_digest': a.auth_digest or None, 'commit': ident['commit']})
    jobs = [(key, d / f'{a.command}.log') for key, d in todo]
    failed = schedule(jobs, gpus, a.per_gpu, cmd, state, state_path)
    print(f'{a.command}: 完成，失败 {len(failed)} 个 {failed[:5]}')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
