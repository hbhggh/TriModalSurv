#!/usr/bin/env python3
"""汇总多个评测臂的逐 seed 指标，并生成可选的配对比较表。"""

import argparse
import json
import pathlib
import re
import statistics
import sys


CANCERS = ["BLCA", "BRCA", "LUAD", "LGG", "UCEC"]
SEEDS = [123, 132, 213, 231, 321]
FILENAME_RE = re.compile(
    r"^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$"
)


class LoadError(Exception):
    """带契约退出码的输入错误。"""

    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code


def _grid_rows(payload):
    grids = payload.get("grids")
    if isinstance(grids, dict):
        return dict(grids)
    if isinstance(grids, list):
        return {row["grid"]: row for row in grids}
    return {}


def load_arm(arm, directories):
    """按 (cancer, seed) 合并若干目录中的 grid，并拒绝冲突。"""
    merged = {}
    checkpoints = {}
    checkpoint_dirs = {}
    grid_dirs = {}

    for directory_text in directories:
        directory = pathlib.Path(directory_text)
        if not directory.is_dir():
            raise LoadError(f"ERROR: no result json in {directory_text}", 3)

        parsed = []
        for path in sorted(directory.glob("*.json")):
            match = FILENAME_RE.match(path.name)
            if match is None:
                print(f"SKIP {path}")
                continue
            parsed.append((path, match))

        if not parsed:
            raise LoadError(f"ERROR: no result json in {directory_text}", 3)

        for path, match in parsed:
            cancer = match.group("cancer")
            seed = int(match.group("seed"))
            key = (cancer, seed)
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            checkpoint = payload.get("checkpoint")
            if key in checkpoints and checkpoints[key] != checkpoint:
                raise LoadError(
                    "CKPT_MISMATCH "
                    f"arm={arm} cancer={cancer} seed={seed} "
                    f"dir1={checkpoint_dirs[key]} dir2={directory_text}",
                    2,
                )
            checkpoints.setdefault(key, checkpoint)
            checkpoint_dirs.setdefault(key, directory_text)

            target = merged.setdefault(key, {})
            for grid, row in _grid_rows(payload).items():
                grid_key = (cancer, seed, grid)
                if grid in target:
                    raise LoadError(
                        "CONFLICT "
                        f"arm={arm} cancer={cancer} seed={seed} grid={grid} "
                        f"dir1={grid_dirs[grid_key]} dir2={directory_text}",
                        2,
                    )
                target[grid] = row
                grid_dirs[grid_key] = directory_text
    return merged


def parse_arm_specs(specs):
    arms = {}
    for spec in specs:
        name, separator, directories = spec.partition("=")
        if not separator or not name or not directories:
            raise LoadError(f"ERROR: invalid --arm {spec}", 3)
        arms[name] = directories.split(",")
    return arms


def _values(data, arm, cancer, grid, metric):
    return [
        data[arm].get((cancer, seed), {}).get(grid, {}).get(metric)
        for seed in SEEDS
    ]


def _median(values):
    present = [value for value in values if value is not None]
    return statistics.median(present) if present else None


def _pair_stats(values, base_values, tie_eps):
    pairs = [
        (value, base_value)
        for value, base_value in zip(values, base_values)
        if value is not None and base_value is not None
    ]
    differences = [value - base_value for value, base_value in pairs]
    wins = sum(difference > tie_eps for difference in differences)
    ties = sum(abs(difference) <= tie_eps for difference in differences)
    losses = sum(difference < -tie_eps for difference in differences)
    delta = statistics.median(differences) if differences else None
    return wins, losses, ties, delta, len(pairs)


def render_main_table(arms, data, grids, base, metric, tie_eps, legacy_winloss):
    lines = [f"# 臂对比（主口径 {metric}；对照臂 {base}）", ""]
    for grid in grids:
        lines.extend(
            [
                f"## 格点 {grid}",
                "",
                "| 癌种 | 臂 | "
                + " | ".join(f"s{seed}" for seed in SEEDS)
                + f" | 中位 | vs {base} 严格胜负 |",
                "|" + "---|" * 9,
            ]
        )
        for cancer in CANCERS:
            for arm in arms:
                values = _values(data, arm, cancer, grid, metric)
                cells = [f"{value:.4f}" if value is not None else "—" for value in values]
                median = _median(values)
                median_cell = f"{median:.4f}" if median is not None else "—"
                winloss = ""
                if arm != base:
                    base_values = _values(data, base, cancer, grid, metric)
                    wins, losses, ties, delta, pair_count = _pair_stats(
                        values, base_values, tie_eps
                    )
                    if pair_count:
                        if legacy_winloss:
                            legacy_wins = sum(
                                value > base_value
                                for value, base_value in zip(values, base_values)
                                if value is not None and base_value is not None
                            )
                            winloss = (
                                f"{legacy_wins}:{pair_count - legacy_wins} "
                                f"(Δ中位 {delta:+.4f})"
                            )
                        else:
                            winloss = f"{wins}:{losses}:{ties} (Δ中位 {delta:+.4f})"
                lines.append(
                    f"| {cancer} | {arm} | "
                    + " | ".join(cells)
                    + f" | {median_cell} | {winloss} |"
                )
        lines.append("")

    missing = [
        (arm, cancer, seed)
        for arm in arms
        for cancer in CANCERS
        for seed in SEEDS
        if (cancer, seed) not in data[arm]
    ]
    lines.append(f"缺格：{len(missing)}" + (f" → {missing[:8]}" if missing else ""))
    return "\n".join(lines)


def render_pairwise_table(arms, data, grid, base, metric, tie_eps):
    lines = [
        f"# 格点 {grid} 配对比较（主口径 {metric}；对照臂 {base}；5 seeds；"
        f"胜:负:平，|Δ|≤{tie_eps!r} 记平）",
        "",
    ]
    for arm in arms:
        if arm == base:
            continue
        lines.extend(
            [
                f"## {arm} vs {base}",
                "",
                f"| 癌种 | {base} 中位 | {arm} 中位 | 胜:负:平 | 配对Δ中位 |",
                "|---|---|---|---|---|",
            ]
        )
        total_wins = total_losses = total_ties = total_pairs = 0
        for cancer in CANCERS:
            values = _values(data, arm, cancer, grid, metric)
            base_values = _values(data, base, cancer, grid, metric)
            wins, losses, ties, delta, pair_count = _pair_stats(
                values, base_values, tie_eps
            )
            total_wins += wins
            total_losses += losses
            total_ties += ties
            total_pairs += pair_count
            base_median = _median(base_values)
            arm_median = _median(values)
            base_cell = f"{base_median:.4f}" if base_median is not None else "—"
            arm_cell = f"{arm_median:.4f}" if arm_median is not None else "—"
            delta_cell = f"{delta:+.4f}" if delta is not None else "—"
            lines.append(
                f"| {cancer} | {base_cell} | {arm_cell} | "
                f"{wins}:{losses}:{ties} | {delta_cell} |"
            )
        lines.extend(
            [
                f"| 合计 | — | — | {total_wins}:{total_losses}:{total_ties} / "
                f"{total_pairs} | — |",
                "",
            ]
        )
    return "\n".join(lines).rstrip("\n")


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", action="append", required=True, help="NAME=dir[,dir2,...]")
    parser.add_argument("--grids", default="none,rna_100,text_100")
    parser.add_argument("--base", default=None, help="对照臂名（默认第一个）")
    parser.add_argument("--metric", default="cindex_B")
    parser.add_argument("--out", default=None)
    parser.add_argument("--tie-eps", type=float, default=1e-6)
    parser.add_argument("--legacy-winloss", action="store_true")
    parser.add_argument("--pairwise-grid", default=None)
    parser.add_argument("--pairwise-out", default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        arms = parse_arm_specs(args.arm)
        base = args.base or next(iter(arms))
        if base not in arms:
            raise LoadError(f"ERROR: unknown base arm {base}", 3)
        data = {arm: load_arm(arm, directories) for arm, directories in arms.items()}
    except LoadError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code

    text = render_main_table(
        arms,
        data,
        args.grids.split(","),
        base,
        args.metric,
        args.tie_eps,
        args.legacy_winloss,
    )
    print(text)
    if args.out:
        _write_text(args.out, text)
    if args.pairwise_grid and args.pairwise_out:
        pairwise = render_pairwise_table(
            arms, data, args.pairwise_grid, base, args.metric, args.tie_eps
        )
        _write_text(args.pairwise_out, pairwise)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
