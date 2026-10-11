"""I07 测试折评估：加载 best.pt，在 test 上算 C-index。研究计划书 v0.2 第 2、4 节。

- 单模态臂（wsi / rna / text）：只有一种模式 full。
- 三模态臂 tri：full；以及骨架内屏蔽单模态 only_wsi / only_rna / only_text，各两种填充：
  zero（零向量，主基线）与 train_mean（该折**训练部分**上该模态池化向量的均值，参照）。
- 每次运行写 test_metrics.json 与逐病人 preds_test.npz（risk、time、event、patient_ids）。
- 入口先过源码身份门，并要求 run.json 记录的 commit 与资产指纹等于当前值（ckpt 必须由同一代码、同一资产训练）。
- 入口自行核对测试授权（节点一复审 high；第 3 轮 high 1、2）：best.pt 与 run.json 各只读一次，sha256 必须等于
  --ckpt-sha256 / --run-sha256；用这两份字节的哈希与 AssetReader 的 manifest 指纹在完整清单上重算授权摘要，必须等于
  --auth-digest；run.json 的超参数与 config 哈希必须等于当前 config.yaml（epochs 只许 50/100）；权重与 run.json 从已核对
  的字节解析，数据经同一个 AssetReader 读一次、核对后解析，没有先查后读的窗口。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import torch

from .contract import check_config, check_output
from .data import load_fold
from .model import MODALITIES
from .survival import c_index
from . import launch, provenance
from . import train as train_mod
from .train import ARMS, build_model


def train_means(model, train_part):
    """该折训练部分上每个模态池化向量的均值（只用训练集）。"""
    model.eval()
    with torch.no_grad():
        pooled = model(train_part)['pooled']
    return {m: v.mean(0) for m, v in pooled.items()}


def predict(model, part, present=None, fill=None):
    model.eval()
    with torch.no_grad():
        out = model(part, present=present, fill=fill)
    check_output(out, len(part), present or model.modalities)
    return out['risk'].float().cpu().numpy()


def evaluate(model, parts, arm):
    test = parts['test']
    t, e = test.time.cpu().numpy(), test.event.cpu().numpy()
    preds = {'full': predict(model, test)}
    if arm == 'tri':
        means = train_means(model, parts['train'])
        d = next(iter(means.values())).shape[0]
        dev = test.time.device
        for keep in MODALITIES:
            absent = [m for m in MODALITIES if m != keep]
            preds[f'only_{keep}__zero'] = predict(model, test, (keep,), {m: torch.zeros(d, device=dev) for m in absent})
            preds[f'only_{keep}__train_mean'] = predict(model, test, (keep,), {m: means[m] for m in absent})
    metrics = {k: c_index(v, t, e) for k, v in preds.items()}
    return metrics, preds, t, e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assets', required=True, type=Path)
    ap.add_argument('--runs', required=True, type=Path)
    ap.add_argument('--cancer', required=True)
    ap.add_argument('--fold', required=True, type=int)
    ap.add_argument('--arm', required=True, choices=sorted(ARMS))
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--expected-commit', required=True)
    ap.add_argument('--auth-digest', required=True)
    ap.add_argument('--ckpt-sha256', required=True)
    ap.add_argument('--run-sha256', required=True)
    ap.add_argument('--plan-cancers', required=True)
    ap.add_argument('--plan-folds', required=True)
    ap.add_argument('--plan-arms', required=True)
    a = ap.parse_args(argv)
    ident = provenance.require_clean(a.expected_commit)
    items = launch.plan([c for c in a.plan_cancers.split(',') if c], [int(k) for k in a.plan_folds.split(',') if k],
                        [x for x in a.plan_arms.split(',') if x])
    if (a.cancer, a.fold, a.arm) not in items:
        raise PermissionError('本次评估的 (癌种, 折, 臂) 不在授权清单内')
    reader = provenance.AssetReader(a.assets)
    run_dir = launch.run_dir(a.runs, a.cancer, a.fold, a.arm)
    if (run_dir / 'test_metrics.json').exists():
        raise FileExistsError(f'已有测试结果，拒绝覆盖：{run_dir}')
    run_blob, blob = (run_dir / 'run.json').read_bytes(), (run_dir / 'best.pt').read_bytes()
    mine = {'ckpt': hashlib.sha256(blob).hexdigest(), 'run': hashlib.sha256(run_blob).hexdigest()}
    if mine['ckpt'] != a.ckpt_sha256:
        raise PermissionError('best.pt 与授权时的 ckpt 哈希不同，拒绝评估')
    if mine['run'] != a.run_sha256:
        raise PermissionError('run.json 与授权时的哈希不同，拒绝评估')
    hashes = launch.ckpt_hashes(a.runs, items)
    hashes[f'{a.cancer}/{a.fold}/{a.arm}'] = mine
    if provenance.auth_digest(hashes, reader.fingerprint, ident['commit']) != a.auth_digest:
        raise PermissionError('重算的授权摘要与 --auth-digest 不同，拒绝评估')
    run = json.loads(run_blob)
    if run['git'].get('commit') != ident['commit'] or run['git'].get('dirty'):
        raise PermissionError(f'ckpt 的训练 commit {run["git"].get("commit")} 与当前 {ident["commit"]} 不同或 dirty，拒绝评估')
    if run.get('assets_fp') != reader.fingerprint:
        raise PermissionError('ckpt 训练时的资产指纹与当前资产不同，拒绝评估')
    cfg = check_config(run['config'])
    if run.get('config_sha256') != train_mod.CONFIG_SHA256 or cfg != dict(train_mod.DEFAULTS, epochs=cfg['epochs']):
        raise PermissionError('run.json 的超参数或 config 哈希与当前 config.yaml 不同，拒绝评估')
    parts, meta = load_fold(a.assets, a.cancer, a.fold, device=a.device, reader=reader)
    model = build_model(meta, a.arm, cfg).to(a.device)
    model.load_state_dict(torch.load(io.BytesIO(blob), map_location=a.device, weights_only=True))
    metrics, preds, t, e = evaluate(model, parts, a.arm)
    np.savez(run_dir / 'preds_test.npz', patient_ids=np.array(parts['test'].patient_ids), time=t, event=e,
             **{k: v for k, v in preds.items()})
    (run_dir / 'test_metrics.json').write_text(json.dumps({'cancer': a.cancer, 'fold': a.fold, 'arm': a.arm,
                                                           'best_epoch': run['best_epoch'], 'c_index': metrics},
                                                          indent=2))
    print(json.dumps(metrics))


if __name__ == '__main__':
    main()
