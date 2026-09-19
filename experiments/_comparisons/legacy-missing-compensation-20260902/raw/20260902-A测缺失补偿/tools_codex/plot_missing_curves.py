import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "trimodalsurv"
import matplotlib.pyplot as plt

import argparse
import os
import pathlib
import statistics

from summarize_arms import CANCERS, SEEDS, load_arm


DISPLAY_NAMES = {
    "m0real": "M0-real",
    "m1": "M1",
    "m1b": "M1b",
    "m2": "M2",
    "e0": "E0",
    "e1": "E1",
    "e0d": "E0d",
}

GATE_COLORS = {
    "m0real": "#4C72B0",
    "m1": "#DD8452",
    "m1b": "#55A868",
    "m2": "#C44E52",
}

NPJC_COLORS = {
    "e0": "#4C72B0",
    "e0d": "#55A868",
    "e1": "#C44E52",
}


def _seed_values(data, cancer, grid, metric):
    return [
        data.get((cancer, seed), {}).get(grid, {}).get(metric)
        for seed in SEEDS
    ]


def _present(values):
    return [value for value in values if value is not None]


def _load_gate(root):
    return {
        arm: load_arm(arm, [str(root / "results_gate" / arm)])
        for arm in GATE_COLORS
    }


def _load_npjc(root):
    data = {
        "e0": load_arm(
            "e0",
            [str(root / "results_npjc" / "e0"), str(root / "results_npjc_both" / "e0")],
        ),
        "e1": load_arm(
            "e1",
            [str(root / "results_npjc" / "e1"), str(root / "results_npjc_both" / "e1")],
        ),
    }
    e0d_dir = root / "results_npjc_e0d"
    if e0d_dir.is_dir():
        data["e0d"] = load_arm("e0d", [str(e0d_dir)])
    else:
        print("SKIPPED: results_npjc_e0d missing")
    return data


def _save_figure(fig, out_dir, stem):
    fig.savefig(out_dir / f"{stem}.png", dpi=150)
    fig.savefig(
        out_dir / f"{stem}.svg",
        format="svg",
        metadata={"Date": None},
    )
    plt.close(fig)


def plot_gate_missing_curves(data, out_dir, metric):
    fig, axes = plt.subplots(
        5,
        3,
        figsize=(13.5, 16),
        dpi=150,
        sharex=True,
        sharey="row",
    )
    modes = ["rna", "text", "both"]
    x_values = [0, 25, 50, 75, 100]
    legend_handles = []

    for row_index, cancer in enumerate(CANCERS):
        for column_index, mode in enumerate(modes):
            axis = axes[row_index, column_index]
            for arm, color in GATE_COLORS.items():
                medians = []
                minima = []
                maxima = []
                for rate in x_values:
                    grid = "none" if rate == 0 else f"{mode}_{rate}"
                    values = _present(_seed_values(data[arm], cancer, grid, metric))
                    medians.append(statistics.median(values))
                    minima.append(min(values))
                    maxima.append(max(values))
                (line,) = axis.plot(
                    x_values,
                    medians,
                    color=color,
                    marker="o",
                    linewidth=1.6,
                    label=DISPLAY_NAMES[arm],
                )
                axis.fill_between(
                    x_values,
                    minima,
                    maxima,
                    color=color,
                    alpha=0.15,
                )
                if row_index == 0 and column_index == 0:
                    legend_handles.append(line)
            axis.set_title(f"{cancer} | {mode} missing")
            if column_index == 0:
                axis.set_ylabel("c-index (B)")
            if row_index == len(CANCERS) - 1:
                axis.set_xlabel("missing rate (%)")

    fig.suptitle(
        "Gate-version arms under test-time missingness (manifest v1, 5 cancers x 5 seeds)"
    )
    fig.legend(
        legend_handles,
        [handle.get_label() for handle in legend_handles],
        loc="lower center",
        ncol=4,
        frameon=False,
    )
    fig.text(
        0.5,
        0.0,
        "Metric: c-index B (sigmoid-corrected, sksurv). Line = median of 5 seeds "
        "(123/132/213/231/321); band = min-max range across seeds. Grids: none = full modalities.",
        ha="center",
        va="bottom",
        fontsize=8,
    )
    fig.tight_layout(rect=[0.0, 0.05, 1.0, 0.97])
    _save_figure(fig, out_dir, "gate_missing_curves")


def plot_npjc_4grids(data, out_dir, metric):
    fig, axes = plt.subplots(1, 5, figsize=(16, 4), dpi=150)
    grids = ["none", "rna_100", "text_100", "both_100"]
    arms = ["e0", "e0d", "e1"] if "e0d" in data else ["e0", "e1"]
    offsets = [-0.24, 0.0, 0.24] if len(arms) == 3 else [-0.15, 0.15]
    legend_handles = []

    for cancer_index, cancer in enumerate(CANCERS):
        axis = axes[cancer_index]
        for arm, offset in zip(arms, offsets):
            color = NPJC_COLORS[arm]
            for grid_index, grid in enumerate(grids):
                values = _present(_seed_values(data[arm], cancer, grid, metric))
                scatter = axis.scatter(
                    [grid_index + offset] * len(values),
                    values,
                    s=18,
                    alpha=0.75,
                    color=color,
                    label=DISPLAY_NAMES[arm] if grid_index == 0 else None,
                )
                median = statistics.median(values)
                axis.hlines(
                    median,
                    grid_index + offset - 0.1,
                    grid_index + offset + 0.1,
                    color=color,
                    linewidth=2,
                )
                if cancer_index == 0 and grid_index == 0:
                    legend_handles.append(scatter)
        axis.set_title(cancer)
        axis.set_xticks(range(len(grids)))
        axis.set_xticklabels(grids, rotation=25, ha="right")
        if cancer_index == 0:
            axis.set_ylabel("c-index (B)")

    if "e0d" in data:
        title = (
            "NPJ-C arms across 4 missingness grids (E0 = NPJ-C; E1 = NPJ-C + CAP-Recall; "
            "E0d = E0 + modality dropout 0.15, no recall)"
        )
    else:
        title = (
            "NPJ-C arms across 4 missingness grids "
            "(E0 = NPJ-C; E1 = NPJ-C + CAP-Recall)"
        )
    fig.suptitle(title)
    fig.legend(
        legend_handles,
        [handle.get_label() for handle in legend_handles],
        loc="lower center",
        ncol=3,
        frameon=False,
    )
    fig.text(
        0.5,
        0.0,
        "Metric: c-index B (sigmoid-corrected, sksurv). Dots = 5 seeds "
        "(123/132/213/231/321); horizontal bar = median.",
        ha="center",
        va="bottom",
        fontsize=8,
    )
    fig.tight_layout(rect=[0.0, 0.12, 1.0, 0.91])
    _save_figure(fig, out_dir, "npjc_e0_e1_4grids")


def build_parser():
    root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(root))
    parser.add_argument("--out", default=None)
    parser.add_argument("--metric", default="cindex_B")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    out_dir = pathlib.Path(args.out) if args.out else root / "figures"
    os.makedirs(out_dir, exist_ok=True)
    gate_data = _load_gate(root)
    npjc_data = _load_npjc(root)
    plot_gate_missing_curves(gate_data, out_dir, args.metric)
    plot_npjc_4grids(npjc_data, out_dir, args.metric)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
