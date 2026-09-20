"""strategy0 的三臂固定报告；所有数字只消费同一份冻结 test 行。"""
from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Iterable


ARMS = ("strategy0", "m1", "m0real")
LABELS = {"strategy0": "strategy0组合", "m1": "均值填补", "m0real": "不补偿"}
RED_OPEN = '<span style="color:#c62828"><strong>'
RED_CLOSE = "</strong></span>"


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("empty metric group")
    return float(fmean(values))


def _index_rows(rows: list[dict], *, cancers, seeds, grids):
    expected = {(arm, cancer, seed, grid) for arm in ARMS for cancer in cancers
                for seed in seeds for grid in grids}
    index = {}
    for row in rows:
        if row.get("protocol") not in ARMS or row.get("candidate_id") != row.get("protocol"):
            raise ValueError("unknown fixed-report arm")
        key = (row["protocol"], row["cancer"], row["seed"], row["grid"])
        if key in index:
            raise ValueError("duplicate test metric cell")
        index[key] = row
    if set(index) != expected:
        raise ValueError(f"requires exactly {len(expected)} test rows; found {len(index)}")
    return index


def summarize(rows: list[dict], *, cancers, seeds, grids) -> dict:
    """返回不四舍五入的 100/75 格汇总，以及五癌严格胜负。"""
    index = _index_rows(rows, cancers=cancers, seeds=seeds, grids=grids)
    def score(arm, cancer, seed, grid):
        return float(index[(arm, cancer, seed, grid)]["c_index_b"])

    all_cells = [(cancer, seed, grid) for cancer in cancers for seed in seeds for grid in grids]
    artificial_cells = [cell for cell in all_cells if cell[2] != "none"]
    by_arm = {arm: _mean(score(arm, *cell) for cell in all_cells) for arm in ARMS}
    artificial = {arm: _mean(score(arm, *cell) for cell in artificial_cells) for arm in ARMS}
    cancer_means = {
        cancer: {arm: _mean(score(arm, cancer, seed, grid) for seed in seeds for grid in grids)
                 for arm in ARMS}
        for cancer in cancers
    }
    cancer_wins = {cancer: (values["strategy0"] > values["m1"] and
                            values["strategy0"] > values["m0real"])
                   for cancer, values in cancer_means.items()}
    seed_means = {
        seed: {arm: _mean(score(arm, cancer, seed, grid) for cancer in cancers for grid in grids)
               for arm in ARMS}
        for seed in seeds
    }
    scenario_means = {
        (cancer, grid): {arm: _mean(score(arm, cancer, seed, grid) for seed in seeds)
                          for arm in ARMS}
        for cancer in cancers for grid in grids
    }
    best_absolute_seed = max(seeds, key=lambda seed: seed_means[seed]["strategy0"])
    best_absolute_scenario = max(scenario_means, key=lambda item: scenario_means[item]["strategy0"])
    gain = lambda values: ((values["strategy0"] - values["m1"]) +
                           (values["strategy0"] - values["m0real"])) / 2.0
    best_gain_seed = max(seeds, key=lambda seed: gain(seed_means[seed]))
    best_gain_scenario = max(scenario_means, key=lambda item: gain(scenario_means[item]))
    return {
        "index": index, "main_n": len(all_cells), "artificial_n": len(artificial_cells),
        "means": by_arm, "artificial_means": artificial, "cancer_means": cancer_means,
        "seed_means": seed_means, "scenario_means": scenario_means,
        "cancer_wins": cancer_wins, "wins": sum(cancer_wins.values()),
        "non_wins": [cancer for cancer in cancers if not cancer_wins[cancer]],
        "best_absolute_seed": best_absolute_seed, "best_absolute_scenario": best_absolute_scenario,
        "best_gain_seed": best_gain_seed, "best_gain_scenario": best_gain_scenario,
    }


def _red(text: str) -> str:
    return RED_OPEN + text + RED_CLOSE


def _fmt(value: float, *, winner: bool = False) -> str:
    text = f"{value:.6f}"
    return _red(text) if winner else text


def _row(prefix: list[str], values: dict[str, float]) -> str:
    maximum = max(values.values())
    winner = "、".join(LABELS[arm] for arm in ARMS if values[arm] == maximum)
    return "| " + " | ".join([
        *prefix,
        *[_fmt(values[arm], winner=values[arm] == maximum) for arm in ARMS],
        _red(winner),
        f"{values['strategy0'] - values['m1']:+.6f}",
        f"{values['strategy0'] - values['m0real']:+.6f}",
    ]) + " |"


def _header(prefix: list[str]) -> list[str]:
    cols = [*prefix, LABELS["strategy0"], LABELS["m1"], LABELS["m0real"],
            "三臂最佳", "strategy0−均值", "strategy0−不补偿"]
    return ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]


def _boundary(protocol_id: str, fingerprint: str) -> list[str]:
    return [
        f"协议：`{protocol_id}`；冻结 test 指纹：`{fingerprint}`。",
        "",
        "- 主表为五癌×五seed×四场景共100格等权平均；`none`保留天然缺失，不是完整数据。",
        "- 人工缺失表仅为75格（排除`none`），不替代主表。",
        "- 标红、排名与Δ均基于未四舍五入原值；展示六位，Δ先减后舍入。",
        "- 本轮是受既有test启发的探索性评测；若LUAD改善也只能归因于固定路由换填，不能证明患者检索机制成立。",
        "",
    ]


def render_reports(rows: list[dict], *, config: dict, freeze: dict, test_fingerprint: str) -> dict[str, str]:
    cancers, seeds, grids = tuple(config["cancers"]), tuple(config["seeds"]), tuple(config["grids"])
    summary = summarize(rows, cancers=cancers, seeds=seeds, grids=grids)
    index = summary["index"]
    def values(cancer, seed, grid):
        return {arm: float(index[(arm, cancer, seed, grid)]["c_index_b"]) for arm in ARMS}
    protocol = config["protocol_id"]
    top = _boundary(protocol, test_fingerprint)
    top.extend(["## valid冻结开关", "", "| A（上游组合） | B（strategy0变体） | B−A | 冻结开关 |",
                "| --- | --- | --- | --- |",
                f"| {freeze['a_mean']:.6f} | {freeze['b_mean']:.6f} | {freeze['b_minus_a']:+.6f} | "
                + ("启用" if freeze["enabled"] else "关闭") + " |", "",
                "## 汇总", "", *_header(["范围"]),
                _row(["100格主表（含none）"], summary["means"]),
                _row(["75格人工缺失（排除none）"], summary["artificial_means"]), "",
                "## 五癌严格胜负", "", "| 癌种 | strategy0 | m1 | m0real | 是否严格胜两基线 |",
                "| --- | --- | --- | --- |"])
    for cancer in cancers:
        values_c = summary["cancer_means"][cancer]
        top.append("| " + " | ".join([cancer, *(f"{values_c[arm]:.6f}" for arm in ARMS),
                                         "胜" if summary["cancer_wins"][cancer] else "未胜"]) + " |")
    top.extend(["", f"严格胜率：**{summary['wins']}/5**；未胜癌种："
                + ("、".join(summary["non_wins"]) if summary["non_wins"] else "无") + "。", "",
                "## 结论边界", "", "- 执行验收与效果目标分开：即使文件、哈希和矩阵完整，`4/5`目标未达也必须如实写为未达。",
                "- strategy0关闭时，LUAD沿用冻结组合；不得把上游复用误写成新的路由收益。", ""])

    seed = _boundary(protocol, test_fingerprint)
    seed.extend(["## 按 seed 展开", ""])
    for current_seed in seeds:
        seed.extend([f"### Seed {current_seed}", "", *_header(["癌种", "场景"])])
        for cancer in cancers:
            for grid in grids:
                seed.append(_row([cancer, grid], values(cancer, current_seed, grid)))
        seed.append("")
    seed.extend(["## seed结论", "",
                 f"strategy0绝对平均C-index最高的seed：`{summary['best_absolute_seed']}`。",
                 f"相对两基线平均Δ最大的seed：`{summary['best_gain_seed']}`。二者不混称，且不替代五seed结论。", ""])

    cancer_lines = _boundary(protocol, test_fingerprint)
    cancer_lines.extend(["## 按癌种展开", ""])
    for cancer in cancers:
        cancer_lines.extend([f"### {cancer}", "", *_header(["Seed", "场景"])])
        for current_seed in seeds:
            for grid in grids:
                cancer_lines.append(_row([str(current_seed), grid], values(cancer, current_seed, grid)))
        cancer_lines.append("")
    abs_cancer, abs_grid = summary["best_absolute_scenario"]
    gain_cancer, gain_grid = summary["best_gain_scenario"]
    cancer_lines.extend(["## 癌种结论", "",
                         f"strategy0绝对平均C-index最高的癌种×场景：`{abs_cancer}/{abs_grid}`。",
                         f"相对两基线平均Δ最大的癌种×场景：`{gain_cancer}/{gain_grid}`。二者不混称。",
                         f"五癌严格胜率：**{summary['wins']}/5**；未胜癌种："
                         + ("、".join(summary["non_wins"]) if summary["non_wins"] else "无") + "。", ""])
    return {"零训练改推理1-5实验结果.md": "\n".join(top),
            "seed单位-实验结果.md": "\n".join(seed),
            "癌症为单位.md": "\n".join(cancer_lines)}
