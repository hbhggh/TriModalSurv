import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "trimodalsurv"
import matplotlib.pyplot as plt
import sys

sys.dont_write_bytecode = True  # 坑 S1：任何 import 都不得在源码旁落 .pyc

import argparse
import os
import pathlib
import statistics

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import summarize_arms as SA  # noqa: E402  加载/合并逻辑单一来源

ROOT = pathlib.Path(__file__).resolve().parents[1]

CANCERS = SA.CANCERS          # BLCA, BRCA, LUAD, LGG, UCEC（固定序，LUAD 在 LGG 前）
SEEDS = SA.SEEDS              # 123, 132, 213, 231, 321
MODES = ["rna", "text", "both"]
RATES = [0, 25, 50, 75, 100]
GRIDS4 = ["none", "rna_100", "text_100", "both_100"]

DISPLAY = {
    "m0real": "M0-real",
    "m1": "M1",
    "m1b": "M1b",
    "m2": "M2",
    "e0": "E0",
    "e1": "E1",
    "e0d": "E0d",
}
COLOR = {
    "m0real": "#4C72B0",
    "m1": "#DD8452",
    "m1b": "#55A868",
    "m2": "#C44E52",
    "e0": "#4C72B0",
    "e0d": "#55A868",
    "e1": "#C44E52",
}

GATE_CAPTION = (
    "Metric: c-index B (sigmoid-corrected, sksurv). Line = median of 5 seeds "
    "(123/132/213/231/321); band = min-max range across seeds. "
    "Grids: none = full modalities."
)
NPJC_CAPTION = (
    "Metric: c-index B (sigmoid-corrected, sksurv). Dots = 5 seeds "
    "(123/132/213/231/321); horizontal bar = median."
)


def grid_for(mode, rate):
    return "none" if rate == 0 else "%s_%d" % (mode, rate)


def seed_values(store, cancer, grid, metric):
    """返回该 (cancer, grid) 下 5 seeds 的值列表（缺值为 None，顺序 = SEEDS）。"""
    return [SA.get_val(store, cancer, s, grid, metric) for s in SEEDS]


def stat3(vals):
    kept = [v for v in vals if v is not None]
    if not kept:
        return float("nan"), float("nan"), float("nan")
    return statistics.median(kept), min(kept), max(kept)


def figure_gate(D, arms, out_dir, metric):
    fig, axes = plt.subplots(5, 3, figsize=(13.5, 16), dpi=150, sharex=True, sharey="row")
    for r, cancer in enumerate(CANCERS):
        for c, mode in enumerate(MODES):
            ax = axes[r][c]
            for arm in arms:
                med, lo, hi = [], [], []
                for rate in RATES:
                    m, a, b = stat3(seed_values(D[arm], cancer, grid_for(mode, rate), metric))
                    med.append(m)
                    lo.append(a)
                    hi.append(b)
                kw = {"label": DISPLAY[arm]} if (r == 0 and c == 0) else {}
                ax.plot(RATES, med, marker="o", linewidth=1.6, color=COLOR[arm], **kw)
                ax.fill_between(RATES, lo, hi, alpha=0.15, color=COLOR[arm])
            ax.set_title("%s | %s missing" % (cancer, mode))
            if c == 0:
                ax.set_ylabel("c-index (B)")
            if r == len(CANCERS) - 1:
                ax.set_xlabel("missing rate (%)")
            ax.set_xticks(RATES)
    fig.suptitle(
        "Gate-version arms under test-time missingness "
        "(manifest v1, 5 cancers x 5 seeds)"
    )
    fig.tight_layout(rect=[0, 0.055, 1, 0.975])
    fig.legend(loc="lower center", ncol=4, frameon=False)
    fig.text(0.5, 0.0, GATE_CAPTION, ha="center", va="bottom", fontsize=8)
    save(fig, out_dir, "gate_missing_curves")


def figure_npjc(D, arms, out_dir, metric, has_e0d):
    fig, axes = plt.subplots(1, 5, figsize=(16, 4), dpi=150)
    offsets = [-0.24, 0.0, 0.24] if len(arms) == 3 else [-0.15, 0.15]
    for i, cancer in enumerate(CANCERS):
        ax = axes[i]
        for arm, off in zip(arms, offsets):
            xs, ys = [], []
            for pos, grid in enumerate(GRIDS4):
                vals = seed_values(D[arm], cancer, grid, metric)
                kept = [v for v in vals if v is not None]
                xs.extend([pos + off] * len(kept))
                ys.extend(kept)
                if kept:
                    ax.hlines(
                        statistics.median(kept),
                        pos + off - 0.1,
                        pos + off + 0.1,
                        linewidth=2,
                        color=COLOR[arm],
                    )
            kw = {"label": DISPLAY[arm]} if i == 0 else {}
            ax.scatter(xs, ys, s=18, alpha=0.75, color=COLOR[arm], **kw)
        ax.set_title(cancer)
        ax.set_xticks(range(len(GRIDS4)))
        ax.set_xticklabels(GRIDS4)
        # 默认 10pt 下 text_100/both_100 两标签在 97px 刻度间距内首尾相接，缩到 8pt 保证可读
        ax.tick_params(axis="x", labelsize=8)
        ax.set_xlim(-0.5, len(GRIDS4) - 0.5)
        if i == 0:
            ax.set_ylabel("c-index (B)")
    tail = (
        "E0 = NPJ-C; E1 = NPJ-C + CAP-Recall; E0d = E0 + modality dropout 0.15, no recall"
        if has_e0d
        else "E0 = NPJ-C; E1 = NPJ-C + CAP-Recall"
    )
    fig.suptitle("NPJ-C arms across 4 missingness grids (%s)" % tail)
    fig.tight_layout(rect=[0, 0.16, 1, 0.90])
    fig.legend(loc="lower center", ncol=3, frameon=False)
    fig.text(0.5, 0.0, NPJC_CAPTION, ha="center", va="bottom", fontsize=8)
    save(fig, out_dir, "npjc_e0_e1_4grids")


def save(fig, out_dir, stem):
    png = os.path.join(out_dir, stem + ".png")
    svg = os.path.join(out_dir, stem + ".svg")
    fig.savefig(png, dpi=150)                                   # 禁止 bbox_inches="tight"
    fig.savefig(svg, format="svg", metadata={"Date": None})     # 去掉 dc:date
    plt.close(fig)
    print("WROTE %s" % png)
    print("WROTE %s" % svg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=None)
    ap.add_argument("--metric", default="cindex_B")
    a = ap.parse_args()

    root = pathlib.Path(a.root).resolve()
    out_dir = os.path.abspath(a.out) if a.out else str(root / "figures")
    os.makedirs(out_dir, exist_ok=True)

    gate_arms = ["m0real", "m1", "m1b", "m2"]
    D = {arm: SA.load_arm(arm, str(root / "results_gate" / arm)) for arm in gate_arms}
    figure_gate(D, gate_arms, out_dir, a.metric)

    npjc = {
        "e0": [root / "results_npjc" / "e0", root / "results_npjc_both" / "e0"],
        "e1": [root / "results_npjc" / "e1", root / "results_npjc_both" / "e1"],
    }
    e0d_dir = root / "results_npjc_e0d"
    has_e0d = e0d_dir.is_dir()
    if has_e0d:
        npjc["e0d"] = [e0d_dir]
    else:
        print("SKIPPED: results_npjc_e0d missing")
    N = {k: SA.load_arm(k, ",".join(str(p) for p in v)) for k, v in npjc.items()}
    order = ["e0", "e0d", "e1"] if has_e0d else ["e0", "e1"]
    figure_npjc(N, order, out_dir, a.metric, has_e0d)


if __name__ == "__main__":
    main()
