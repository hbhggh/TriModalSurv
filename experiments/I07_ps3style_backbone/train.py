"""I07 训练：一个 (癌种, 折, 臂) 一次运行。研究计划书 v0.2 第 1、4.1、5 节。

- 臂：tri（三模态）/ wsi / rna / text（同一网络只输入一个模态）。
- AdamW lr=1e-4 wd=1e-5、cosine、bs=64、drop_last、50 epoch（PS3 原值；欠拟合预案只能把 --epochs 改成 100）。
- 每个 epoch 结束在**整个验证集**上一次算 Cox 损失，严格变小时保存 best.pt（V7：初值 +inf，首个有限值即保存）。
- 超参数来自 config.yaml（contract.load_config 校验键与类型），run.json 记录其 sha256。
- 逐 epoch 写 curves.csv（epoch, train_loss, val_loss, lr, is_best）。
- 本文件不接触 test：入口只加载 train / val（load_fold(parts=...)），train() 也只接收这两部分（V31，节点一 high 1）。
- 入口最前面做源码身份门：commit 已知、dirty=false 且等于 --expected-commit，否则拒绝（节点一 high 3）。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

import torch

from .contract import EPOCH_CHOICES, check_config, check_output, load_config
from .data import load_fold
from .model import PS3Style
from . import provenance
from .survival import cox_loss

ARMS = {'tri': ('rna', 'wsi', 'text'), 'wsi': ('wsi',), 'rna': ('rna',), 'text': ('text',)}
DEFAULTS, CONFIG_SHA256 = load_config()  # config.yaml，键与类型由 contract 强制


def build_model(meta, arm, cfg):
    return PS3Style(meta['pathways'], meta['n_fields'], d=cfg['d'], modalities=ARMS[arm], dropout=cfg['dropout'])


def val_loss(model, part):
    model.eval()
    with torch.no_grad():
        out = model(part)
        check_output(out, len(part), model.modalities)
        return float(cox_loss(out['risk'], part.time, part.event))


def train(model, train_part, val_part, cfg, out_dir: Path, log=print):
    """只用 train / val。返回 {'best_epoch', 'best_val_loss'}。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    g = torch.Generator(device='cpu').manual_seed(cfg['seed'])
    opt = torch.optim.AdamW(model.parameters(), lr=cfg['lr'], weight_decay=cfg['weight_decay'])
    n = len(train_part)
    steps_per_epoch = n // cfg['batch_size']
    if steps_per_epoch < 1:
        raise ValueError(f'训练集只有 {n} 人，不足一个 batch')
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg['epochs'] * steps_per_epoch)
    best, best_epoch, rows = math.inf, None, []
    for epoch in range(1, cfg['epochs'] + 1):
        model.train()
        perm = torch.randperm(n, generator=g).to(train_part.time.device)
        losses = []
        for s in range(steps_per_epoch):
            batch = train_part.index(perm[s * cfg['batch_size']:(s + 1) * cfg['batch_size']])
            loss = cox_loss(model(batch)['risk'], batch.time, batch.event)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            losses.append(loss.detach())
        tr = float(torch.stack(losses).mean())
        vl = val_loss(model, val_part)
        if not math.isfinite(tr) or not math.isfinite(vl):
            raise FloatingPointError(f'epoch {epoch} 损失非有限：train={tr} val={vl}')
        is_best = vl < best
        if is_best:
            best, best_epoch = vl, epoch
            torch.save(model.state_dict(), out_dir / 'best.pt')
        rows.append({'epoch': epoch, 'train_loss': tr, 'val_loss': vl, 'lr': sched.get_last_lr()[0], 'is_best': int(is_best)})
        log(f'epoch {epoch:3d} train {tr:.4f} val {vl:.4f}{"  *" if is_best else ""}')
    with open(out_dir / 'curves.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return {'best_epoch': best_epoch, 'best_val_loss': best}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assets', required=True, type=Path)
    ap.add_argument('--cancer', required=True)
    ap.add_argument('--fold', required=True, type=int)
    ap.add_argument('--arm', required=True, choices=sorted(ARMS))
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--epochs', type=int, default=DEFAULTS['epochs'], choices=EPOCH_CHOICES)
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--expected-commit', required=True)
    a = ap.parse_args(argv)
    ident = provenance.require_clean(a.expected_commit)
    out = a.out / a.cancer / f'fold{a.fold}' / a.arm
    if (out / 'run.json').exists():
        raise FileExistsError(f'已有完成的运行，拒绝覆盖：{out}')
    cfg = check_config(dict(DEFAULTS, epochs=a.epochs))
    torch.manual_seed(cfg['seed'] + a.fold)
    parts, meta = load_fold(a.assets, a.cancer, a.fold, device=a.device, parts=('train', 'val'))
    model = build_model(meta, a.arm, cfg).to(a.device)
    t0 = time.time()
    res = train(model, parts['train'], parts['val'], cfg, out)
    run = {'cancer': a.cancer, 'fold': a.fold, 'arm': a.arm, 'config': cfg, 'config_sha256': CONFIG_SHA256, 'device': a.device,
           'n': {k: len(v) for k, v in parts.items()}, 'git': {'commit': ident['commit'], 'dirty': ident['dirty'], 'source': ident.get('source')},
           'assets': str(a.assets), 'assets_fp': meta['assets_fp'],
           'seconds': round(time.time() - t0, 1), **res}
    (out / 'run.json').write_text(json.dumps(run, indent=2, ensure_ascii=False))
    print(json.dumps(res))


if __name__ == '__main__':
    main()
