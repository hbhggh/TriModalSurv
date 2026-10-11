"""I07 结果渲染：拟合判定、loss 曲线图、结果表（研究计划书 v0.2 第 4、4.1、5 节）。所有数字都由本脚本从运行目录生成（V23）。

拟合判定（2026-10-10 冻结，只用训练 / 验证损失）：
- 训练失败：训练损失下降不到初始值的 5%，或出现 NaN/Inf；
- 欠拟合：所选 epoch ≥ 0.9×总 epoch，且最后 10 个 epoch 验证损失的线性斜率 < 0；
- 过拟合：所选 epoch ≤ 0.5×总 epoch，且最后一个 epoch 的验证损失比最小值高 10% 以上，且最后 10 个 epoch 训练损失斜率 < 0；
- 其余为正常。某 癌种×臂 有 ≥3/5 折为欠拟合或训练失败 → 该格标注不可靠。
（50 epoch 时阈值即计划书写的 45 与 25。）
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

CANCERS = ('BLCA', 'BRCA', 'LUAD', 'LGG', 'UCEC')
ARMS = ('tri', 'wsi', 'rna', 'text')
N_FOLDS = 5
PRIME = {'full': 0.653, 'wsi': 0.620, 'rna': 0.579, 'text': 0.604,
         'only_wsi': 0.603, 'only_rna': 0.564, 'only_text': 0.611}


def slope(y):
    y = np.asarray(y, dtype=float)
    return float(np.polyfit(np.arange(len(y)), y, 1)[0])


def fit_label(rows) -> str:
    tr = [float(r['train_loss']) for r in rows]
    va = [float(r['val_loss']) for r in rows]
    n = len(rows)
    if not all(math.isfinite(x) for x in tr + va):
        return 'failed'
    if tr[-1] > tr[0] - 0.05 * abs(tr[0]):
        return 'failed'
    best = 1 + int(np.argmin(va))
    tail = min(10, n)
    if best >= math.ceil(0.9 * n) and slope(va[-tail:]) < 0:
        return 'underfit'
    if best <= 0.5 * n and va[-1] > 1.10 * min(va) and slope(tr[-tail:]) < 0:
        return 'overfit'
    return 'normal'


def read_rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def collect(runs: Path):
    """{(cancer, arm): [每折 dict]}；缺任何一折就报错（V5）。"""
    out = {}
    for cancer in CANCERS:
        for arm in ARMS:
            folds = []
            for k in range(N_FOLDS):
                d = runs / cancer / f'fold{k}' / arm
                curves = read_rows(d / 'curves.csv')
                run = json.loads((d / 'run.json').read_text())
                tm = json.loads((d / 'test_metrics.json').read_text()) if (d / 'test_metrics.json').exists() else None
                folds.append({'fold': k, 'curves': curves, 'label': fit_label(curves), 'best_epoch': run['best_epoch'],
                              'git': run['git'], 'c_index': tm['c_index'] if tm else None})
            out[(cancer, arm)] = folds
    commits = {f['git'].get('commit') for v in out.values() for f in v}
    if len(commits) != 1:
        raise ValueError(f'运行来自不同 commit：{commits}')
    return out


def fit_table(res) -> str:
    lines = ['| 癌种 | 臂 | 各折判定 | 各折所选 epoch | 可靠 |', '|---|---|---|---|---|']
    for (cancer, arm), folds in res.items():
        labels = [f['label'] for f in folds]
        bad = sum(lab in ('underfit', 'failed') for lab in labels)
        lines.append(f'| {cancer} | {arm} | {" / ".join(labels)} | {" / ".join(str(f["best_epoch"]) for f in folds)} '
                     f'| {"否（≥3/5 欠拟合或失败）" if bad >= 3 else "是"} |')
    return '\n'.join(lines)


def _cell(res, cancer, arm, key):
    vals = [f['c_index'][key] for f in res[(cancer, arm)]]
    return float(np.mean(vals)), float(np.std(vals))


def result_table(res, fill='zero') -> str:
    cols = [('完整三模态', 'tri', 'full'), ('独立纯 WSI', 'wsi', 'full'), ('独立纯 RNA', 'rna', 'full'),
            ('独立纯文本', 'text', 'full'), ('骨架屏蔽纯 WSI', 'tri', f'only_wsi__{fill}'),
            ('骨架屏蔽纯 RNA', 'tri', f'only_rna__{fill}'), ('骨架屏蔽纯文本', 'tri', f'only_text__{fill}')]
    lines = ['| 癌种 | ' + ' | '.join(c[0] for c in cols) + ' |', '|---' * (len(cols) + 1) + '|']
    means = {c: [] for c in cols}
    for cancer in CANCERS:
        cells = []
        for c in cols:
            m, s = _cell(res, cancer, c[1], c[2])
            means[c].append(m)
            cells.append(f'{m:.3f} ± {s:.3f}')
        lines.append(f'| {cancer} | ' + ' | '.join(cells) + ' |')
    lines.append('| 五癌宏平均 | ' + ' | '.join(f'{np.mean(means[c]):.3f}' for c in cols) + ' |')
    prime = [PRIME['full'], PRIME['wsi'], PRIME['rna'], PRIME['text'], PRIME['only_wsi'], PRIME['only_rna'],
             PRIME['only_text']]
    lines.append('| PRIME 参照（只引用） | ' + ' | '.join(f'{v:.3f}' for v in prime) + ' |')
    return '\n'.join(lines)


def macro_full(res) -> float:
    return float(np.mean([_cell(res, c, 'tri', 'full')[0] for c in CANCERS]))


def plot_curves(res, out: Path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    for (cancer, arm), folds in res.items():
        fig, ax = plt.subplots(figsize=(6, 4), dpi=120)
        for f in folds:
            ep = [int(r['epoch']) for r in f['curves']]
            line, = ax.plot(ep, [float(r['train_loss']) for r in f['curves']], '-', lw=1, label=f'fold{f["fold"]} train')
            ax.plot(ep, [float(r['val_loss']) for r in f['curves']], '--', lw=1, color=line.get_color(),
                    label=f'fold{f["fold"]} val ({f["label"]})')
            ax.axvline(f['best_epoch'], color=line.get_color(), lw=0.6, alpha=0.5)
        ax.set_xlabel('epoch')
        ax.set_ylabel('Cox loss')
        ax.set_title(f'{cancer} · {arm}')
        ax.legend(fontsize=6, ncol=2)
        fig.tight_layout()
        fig.savefig(out / f'curves_{cancer}_{arm}.png')
        plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--fit-only', action='store_true', help='只出拟合判定与曲线（冒烟 / 测试评估前用）')
    a = ap.parse_args(argv)
    res = collect(a.runs)
    plot_curves(res, a.out / 'curves')
    parts = ['## 拟合判定', fit_table(res)]
    if not a.fit_only:
        parts += ['## 结果（屏蔽列为零填充）', result_table(res, 'zero'),
                  '## 结果（屏蔽列为训练集均值填充）', result_table(res, 'train_mean'),
                  f'## 换骨架判定\n\n完整三模态五癌宏平均 = {macro_full(res):.4f}；阈值 0.627（严格低于即换骨架）→ '
                  f'**{"换骨架" if macro_full(res) < 0.627 else "保留骨架"}**']
    (a.out / 'results.md').write_text('\n\n'.join(parts) + '\n', encoding='utf-8')
    print((a.out / 'results.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
