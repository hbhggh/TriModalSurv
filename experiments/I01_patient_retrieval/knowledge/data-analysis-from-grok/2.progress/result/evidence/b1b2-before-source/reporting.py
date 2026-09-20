"""Pure Markdown reporting for the frozen zero-training inference experiment."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import fmean
from typing import Any, Iterable


_FILENAMES = (
    "零训练改推理1-5实验结果.md",
    "seed单位-实验结果.md",
    "癌症为单位.md",
)
_BASELINES = ("retrieval", "m1", "m0real")
_THREE_ARMS = ("combo", "m1", "m0real")
_LABELS = {"combo": "组合规则", "retrieval": "原检索", "m1": "均值填补", "m0real": "不补偿"}
_RED_OPEN = '<span style="color:#c62828"><strong>'
_RED_CLOSE = "</strong></span>"


def _axes(config: dict[str, Any]) -> tuple[list[str], list[int], list[str]]:
    cancers = list(config.get("cancers", ()))
    seeds = list(config.get("seeds", ()))
    grids = list(config.get("grids", ()))
    if len(cancers) != 5 or len(set(cancers)) != 5:
        raise ValueError("config.cancers must contain five unique values")
    if len(seeds) != 5 or len(set(seeds)) != 5 or not all(type(x) is int for x in seeds):
        raise ValueError("config.seeds must contain five unique integers")
    if len(grids) != 4 or set(grids) != {"none", "rna_100", "text_100", "both_100"}:
        raise ValueError("config.grids must contain the four locked scenarios")
    return cancers, seeds, grids


def _boundary_lines(protocol_id: str, fingerprint: str | None = None) -> list[str]:
    lines = [
        f"协议：`{protocol_id}`；指标：B 口径 C-index，越大越好。",
    ]
    if fingerprint is not None:
        lines.append(f"冻结 test 单批指纹：`{fingerprint}`。")
    lines.extend(
        [
            "",
            "- `none`＝无额外人工遮挡，保留天然缺失；不是完整数据，也不是第四种人工缺失。",
            "- 排名、标红和 Δ 使用未舍入原值；展示保留六位，Δ 先用原值相减再舍入，并列原值全部标红。",
            "- 本轮是受历史 test 启发的探索性评测，不是新的盲测；结果只能描述该冻结协议，不能证明检索机制。",
            "- 四场景等权，不按患者数加权；人工缺失另报告 75 格（排除 `none`）。",
        ]
    )
    return lines


def _red(text: str) -> str:
    return f"{_RED_OPEN}{text}{_RED_CLOSE}"


def _fmt(value: float, *, red: bool = False, star: bool = False) -> str:
    text = f"{value:.6f}"
    if star:
        text += " ★"
    return _red(text) if red else text


def _delta(value: float) -> str:
    return f"{value:+.6f}"


def _triple_cells(values: dict[str, float]) -> tuple[list[str], str]:
    maximum = max(values.values())
    winners = [arm for arm in _THREE_ARMS if values[arm] == maximum]
    cells = [_fmt(values[arm], red=arm in winners, star=arm in winners) for arm in _THREE_ARMS]
    winner_text = "、".join(_LABELS[arm] for arm in winners)
    if len(winners) > 1:
        winner_text += "（并列）"
    return cells, _red(f"{winner_text} ★")


def _comparison_row(prefix: list[str], values: dict[str, float]) -> str:
    cells, winner = _triple_cells(values)
    return "| " + " | ".join(
        [
            *prefix,
            *cells,
            winner,
            _delta(values["combo"] - values["m1"]),
            _delta(values["combo"] - values["m0real"]),
        ]
    ) + " |"


def _table_header(prefix: list[str]) -> list[str]:
    columns = [
        *prefix,
        "组合规则",
        "均值填补",
        "不补偿",
        "本组三臂最佳",
        "组合−均值",
        "组合−不补偿",
    ]
    return ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]


def _selection_contract(selection: dict[str, Any], config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(selection, dict) or selection.get("schema_version") != 1:
        raise ValueError("selection must use schema_version=1")
    selected = selection.get("selected")
    expected_protocols = set(config.get("rules", ())) | {"combo"}
    if not isinstance(selected, dict) or set(selected) != expected_protocols:
        raise ValueError("selection.selected must contain five rule protocols and combo")
    candidates = selection.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 58:
        raise ValueError("selection.candidates must contain the full 58-candidate valid ledger")
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("valid candidate ledger contains a non-dict entry")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in candidate_by_id:
            raise ValueError("valid candidate ledger candidate_id values must be non-empty and unique")
        if candidate.get("protocol") not in expected_protocols:
            raise ValueError("valid candidate ledger contains an unknown protocol")
        candidate_by_id[candidate_id] = candidate
    candidate_ids = []
    for protocol, spec in selected.items():
        if not isinstance(spec, dict) or spec.get("protocol") != protocol:
            raise ValueError("selection.selected contains a malformed spec")
        candidate_id = spec.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("selected candidate_id must be non-empty")
        candidate_ids.append(candidate_id)
        ledger = candidate_by_id.get(candidate_id)
        if ledger is None:
            raise ValueError("selected candidate_id is absent from the valid candidate ledger")
        if ledger.get("protocol") != protocol:
            raise ValueError("selected protocol does not match its valid candidate ledger entry")
        if list(ledger.get("enabled_rules", ())) != list(spec.get("enabled_rules", ())):
            raise ValueError("selected enabled_rules do not match the valid candidate ledger")
        for name in ("lambda", "alpha", "w"):
            if float(ledger.get(name)) != float(spec.get(name)):
                raise ValueError(f"selected {name} does not match the valid candidate ledger")
        if bool(ledger.get("ucec_exception_enabled")) != bool(spec.get("ucec_exception")):
            raise ValueError("selected UCEC exception does not match the valid candidate ledger")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("selected candidate_id values must be unique")
    return selected


def _validate_completed(
    rows: list[dict[str, Any]], selection: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[tuple[str, str, int, str], dict[str, Any]], str]:
    selected = _selection_contract(selection, config)
    cancers, seeds, grids = _axes(config)
    identities = {protocol: spec["candidate_id"] for protocol, spec in selected.items()}
    identities.update({name: name for name in _BASELINES})
    required = {
        "split",
        "protocol",
        "candidate_id",
        "cancer",
        "seed",
        "grid",
        "c_index_b",
        "n_patients",
        "checkpoint_sha256",
        "n_complete_checked",
        "complete_max_logit_abs_diff",
        "complete_logit_atol",
        "run_fingerprint",
    }
    index: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    fingerprints: set[str] = set()
    checkpoint_by_unit: dict[tuple[str, int], set[str]] = defaultdict(set)
    units_by_checkpoint: dict[str, set[tuple[str, int]]] = defaultdict(set)
    patients_by_cell: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    diagnostics_by_cell: dict[tuple[str, int, str], set[tuple[int, float | None]]] = defaultdict(set)
    expected_atol = float(config.get("numerics", {}).get("logit_atol", 1e-6))
    for position, row in enumerate(rows):
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError(f"test_rows[{position}] does not match the metric schema")
        protocol = row["protocol"]
        if protocol not in identities or row["candidate_id"] != identities[protocol]:
            raise ValueError("test_rows contains an unknown protocol/candidate identity")
        if row["split"] != "test":
            raise ValueError("completed reports require only split=test")
        if row["cancer"] not in cancers or type(row["seed"]) is not int or row["seed"] not in seeds:
            raise ValueError("test_rows contains an illegal cancer or seed")
        if row["grid"] not in grids:
            raise ValueError("test_rows contains an illegal grid")
        value = row["c_index_b"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("C-index must be numeric")
        if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError("C-index must be finite and in [0, 1]")
        n_patients = row["n_patients"]
        if type(n_patients) is not int or n_patients <= 0:
            raise ValueError("n_patients must be a positive integer")
        checkpoint = row["checkpoint_sha256"]
        if not isinstance(checkpoint, str) or not checkpoint:
            raise ValueError("checkpoint_sha256 must be non-empty")
        n_checked = row["n_complete_checked"]
        diff = row["complete_max_logit_abs_diff"]
        if type(n_checked) is not int or n_checked < 0:
            raise ValueError("n_complete_checked must be a non-negative integer")
        if n_checked > n_patients:
            raise ValueError("n_complete_checked cannot exceed n_patients")
        if n_checked == 0:
            if diff is not None:
                raise ValueError("zero complete checks require null max diff")
        elif (
            isinstance(diff, bool)
            or not isinstance(diff, (int, float))
            or not math.isfinite(float(diff))
            or float(diff) < 0.0
            or float(diff) > expected_atol
        ):
            raise ValueError("complete-logit parity is invalid or exceeds tolerance")
        if float(row["complete_logit_atol"]) != expected_atol:
            raise ValueError("complete_logit_atol does not match config")
        fingerprint = row["run_fingerprint"]
        if not isinstance(fingerprint, str) or not fingerprint:
            raise ValueError("run_fingerprint must be non-empty")
        fingerprints.add(fingerprint)
        key = (protocol, row["cancer"], row["seed"], row["grid"])
        if key in index:
            raise ValueError(f"duplicate completed metric cell: {key}")
        index[key] = row
        unit = (row["cancer"], row["seed"])
        checkpoint_by_unit[unit].add(checkpoint)
        units_by_checkpoint[checkpoint].add(unit)
        cell = (row["cancer"], row["seed"], row["grid"])
        patients_by_cell[cell].add(n_patients)
        diagnostics_by_cell[cell].add((n_checked, diff))
    expected_keys = {
        (protocol, cancer, seed, grid)
        for protocol in identities
        for cancer in cancers
        for seed in seeds
        for grid in grids
    }
    if set(index) != expected_keys:
        raise ValueError(
            "completed reports require exactly 9 protocols x 100 cells "
            f"(missing={len(expected_keys - set(index))}, extra={len(set(index) - expected_keys)})"
        )
    if len(fingerprints) != 1:
        raise ValueError("completed reports require one frozen test batch fingerprint")
    if any(len(values) != 1 for values in checkpoint_by_unit.values()):
        raise ValueError("checkpoint_sha256 differs inside a cancer-seed unit")
    if any(len(values) != 1 for values in patients_by_cell.values()):
        raise ValueError("n_patients differs across protocols for one metric cell")
    if any(len(units) != 1 for units in units_by_checkpoint.values()):
        raise ValueError("one checkpoint_sha256 is reused by different cancer-seed units")
    if any(len(values) != 1 for values in diagnostics_by_cell.values()):
        raise ValueError(
            "n_complete_checked or complete_max_logit_abs_diff differs across protocols for one cell"
        )
    return index, next(iter(fingerprints))


def _value(index: dict[tuple[str, str, int, str], dict[str, Any]], arm: str, cancer: str, seed: int, grid: str) -> float:
    return float(index[(arm, cancer, seed, grid)]["c_index_b"])


def _means(
    index: dict[tuple[str, str, int, str], dict[str, Any]],
    cells: Iterable[tuple[str, int, str]],
) -> dict[str, float]:
    frozen_cells = list(cells)
    return {
        arm: fmean(_value(index, arm, cancer, seed, grid) for cancer, seed, grid in frozen_cells)
        for arm in _THREE_ARMS
    }


def _empty_table(config: dict[str, Any], order: str) -> list[str]:
    cancers, seeds, grids = _axes(config)
    lines = [
        "| 癌种 | Seed | 场景 | 组合规则 | 均值填补 | 不补偿 | 状态 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if order == "seed":
        cells = ((cancer, seed, grid) for seed in seeds for cancer in cancers for grid in grids)
    else:
        cells = ((cancer, seed, grid) for cancer in cancers for seed in seeds for grid in grids)
    lines.extend(
        f"| {cancer} | {seed} | {grid} | — | — | — | 未跑 |"
        for cancer, seed, grid in cells
    )
    return lines


def _render_unfinished(config: dict[str, Any], status: str, blocker: str | None) -> dict[str, str]:
    protocol_id = str(config.get("protocol_id", ""))
    reason = blocker or "未提供阻塞原因"
    titles = {
        _FILENAMES[0]: "# 零训练改推理 1–5 实验结果",
        _FILENAMES[1]: "# Seed 单位实验结果",
        _FILENAMES[2]: "# 癌症为单位实验结果",
    }
    reports = {}
    for filename, title in titles.items():
        order = "seed" if filename == _FILENAMES[1] else "cancer"
        lines = [
            title,
            "",
            f"协议：`{protocol_id}`。",
            f"状态：`{status}`；阻塞：{reason}。",
            "",
            "以下为锁定的 100 格全量空表；没有运行结果，不写入合成数字或置信区间。",
            "",
            *_empty_table(config, order),
            "",
            "边界：`none` 保留天然缺失；本研究是探索性评测，未跑状态不能证明检索机制。",
        ]
        reports[filename] = "\n".join(lines) + "\n"
    return reports


def _render_root(
    index: dict[tuple[str, str, int, str], dict[str, Any]],
    selection: dict[str, Any],
    config: dict[str, Any],
    fingerprint: str,
) -> str:
    cancers, seeds, grids = _axes(config)
    all_cells = [(c, s, g) for c in cancers for s in seeds for g in grids]
    missing_cells = [(c, s, g) for c in cancers for s in seeds for g in grids if g != "none"]
    lines = ["# 零训练改推理 1–5 实验结果", "", *_boundary_lines(config["protocol_id"], fingerprint)]

    lines.extend(["", "## valid 选择与冻结参数", ""])
    lines.extend(
        [
            "| 协议 | candidate_id | 启用规则 | λ | α | w | UCEC/text 检索例外 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    selected = selection["selected"]
    for protocol in [*config["rules"], "combo"]:
        spec = selected[protocol]
        enabled_rules = list(spec.get("enabled_rules", []))
        if 1 not in enabled_rules:
            ucec_label = "不适用"
        elif spec.get("ucec_exception"):
            ucec_label = "启用"
        else:
            ucec_label = "固定 m0real"
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                protocol,
                spec["candidate_id"],
                ",".join(str(x) for x in spec.get("enabled_rules", [])),
                format(float(spec.get("lambda", 1.0)), ".12g"),
                format(float(spec.get("alpha", 0.0)), ".12g"),
                format(float(spec.get("w", 1.0)), ".12g"),
                ucec_label,
            )
        )

    lines.extend(["", "## 总体三臂比较（100格）", "", *_table_header(["范围"])])
    lines.append(_comparison_row(["五癌×五seed×四场景等权"], _means(index, all_cells)))
    lines.extend(["", "## 75格人工缺失另表", "", *_table_header(["范围"])])
    lines.append(_comparison_row(["排除none的75格等权"], _means(index, missing_cells)))

    retrieval_mean = fmean(
        _value(index, "retrieval", cancer, seed, grid) for cancer, seed, grid in all_cells
    )
    lines.extend(
        [
            "",
            "## 五个单点与原检索",
            "",
            "每个 valid 锁定单点各占一行；这里只做描述性 test 汇总。",
            "",
            "| 单点协议 | candidate_id | Test均值 | 相对原检索Δ |",
            "| --- | --- | --- | --- |",
        ]
    )
    for protocol in config["rules"]:
        mean_value = fmean(
            _value(index, protocol, cancer, seed, grid) for cancer, seed, grid in all_cells
        )
        lines.append(
            f"| {protocol} | {selected[protocol]['candidate_id']} | {mean_value:.6f} | {_delta(mean_value - retrieval_mean)} |"
        )

    lines.extend(["", "## 四场景三臂比较", "", *_table_header(["场景"])])
    for grid in grids:
        cells = [(cancer, seed, grid) for cancer in cancers for seed in seeds]
        lines.append(_comparison_row([grid], _means(index, cells)))

    scenario_means = []
    for cancer in cancers:
        for grid in grids:
            cells = [(cancer, seed, grid) for seed in seeds]
            values = _means(index, cells)
            scenario_means.append((values["combo"], cancer, grid, values))
    _, worst_cancer, worst_grid, worst_values = min(
        scenario_means, key=lambda item: (item[0], item[1], item[2])
    )
    lines.extend(["", "## 最差场景", "", *_table_header(["癌种", "场景"])])
    lines.append(_comparison_row([worst_cancer, worst_grid], worst_values))

    lines.extend(
        [
            "",
            "## valid全部58个候选",
            "",
            "该表来自 valid 选择结果，只用于说明冻结依据；不与 test 重新选参。",
            "",
            "| 协议 | candidate_id | λ | α | w | raw均值 | routed均值 | Δm1 | Δm0real | 双基线可行 | UCEC例外 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in selection["candidates"]:
        def number(name: str) -> str:
            value = item.get(name)
            return "—" if value is None else f"{float(value):.6f}"

        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                item.get("protocol", "—"),
                item["candidate_id"],
                format(float(item.get("lambda", 1.0)), ".12g"),
                format(float(item.get("alpha", 0.0)), ".12g"),
                format(float(item.get("w", 1.0)), ".12g"),
                number("raw_mean"),
                number("routed_mean"),
                number("mean_delta_m1"),
                number("mean_delta_m0real"),
                "是" if item.get("feasible_vs_both") else "否",
                "启用" if item.get("ucec_exception_enabled") else "固定m0real/不适用",
            )
        )
    return "\n".join(lines) + "\n"


def _render_seed(
    index: dict[tuple[str, str, int, str], dict[str, Any]],
    config: dict[str, Any],
    fingerprint: str,
) -> str:
    cancers, seeds, grids = _axes(config)
    all_cells = [(c, s, g) for c in cancers for s in seeds for g in grids]
    seed_values = {}
    for seed in seeds:
        seed_values[seed] = _means(
            index, [(cancer, seed, grid) for cancer in cancers for grid in grids]
        )
    absolute_seed = min(seeds, key=lambda seed: (-seed_values[seed]["combo"], seed))
    delta_seed = min(
        seeds,
        key=lambda seed: (
            -(
                seed_values[seed]["combo"]
                - (seed_values[seed]["m1"] + seed_values[seed]["m0real"]) / 2.0
            ),
            seed,
        ),
    )
    lines = ["# Seed 单位实验结果", "", *_boundary_lines(config["protocol_id"], fingerprint)]
    lines.extend(["", "## 总体三臂比较", "", *_table_header(["范围"])])
    lines.append(_comparison_row(["全部100格等权"], _means(index, all_cells)))
    lines.extend(
        [
            "",
            "## Seed 绝对分与相对增益分开报告",
            "",
            f"组合规则绝对 C-index 最高：seed {absolute_seed}，均值 {seed_values[absolute_seed]['combo']:.6f}。",
            "组合规则相对两条基线平均 Δ 最大：seed {}，Δ {}。".format(
                delta_seed,
                _delta(
                    seed_values[delta_seed]["combo"]
                    - (seed_values[delta_seed]["m1"] + seed_values[delta_seed]["m0real"]) / 2.0
                ),
            ),
            "",
            "| 组合绝对排名 | Seed | 组合规则 | 均值填补 | 不补偿 | 平均Δ(两基线) |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for rank, seed in enumerate(sorted(seeds, key=lambda x: (-seed_values[x]["combo"], x)), 1):
        values = seed_values[seed]
        average_delta = values["combo"] - (values["m1"] + values["m0real"]) / 2.0
        lines.append(
            f"| {rank} | {seed} | {values['combo']:.6f} | {values['m1']:.6f} | {values['m0real']:.6f} | {_delta(average_delta)} |"
        )
    lines.extend(["", "## 按 Seed 展开的全部100格", ""])
    for seed in seeds:
        lines.extend([f"### Seed {seed}", "", *_table_header(["癌种", "场景"])])
        for cancer in cancers:
            for grid in grids:
                values = {arm: _value(index, arm, cancer, seed, grid) for arm in _THREE_ARMS}
                lines.append(_comparison_row([cancer, grid], values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_cancer(
    index: dict[tuple[str, str, int, str], dict[str, Any]],
    config: dict[str, Any],
    fingerprint: str,
) -> str:
    cancers, seeds, grids = _axes(config)
    all_cells = [(c, s, g) for c in cancers for s in seeds for g in grids]
    cancer_values = {
        cancer: _means(index, [(cancer, seed, grid) for seed in seeds for grid in grids])
        for cancer in cancers
    }
    scenario_values = {
        (cancer, grid): _means(index, [(cancer, seed, grid) for seed in seeds])
        for cancer in cancers
        for grid in grids
    }
    absolute_cancer = min(cancers, key=lambda c: (-cancer_values[c]["combo"], c))
    delta_cancer = min(
        cancers,
        key=lambda c: (
            -(
                cancer_values[c]["combo"]
                - (cancer_values[c]["m1"] + cancer_values[c]["m0real"]) / 2.0
            ),
            c,
        ),
    )
    absolute_scenario = min(
        scenario_values,
        key=lambda key: (-scenario_values[key]["combo"], key[0], key[1]),
    )
    delta_scenario = min(
        scenario_values,
        key=lambda key: (
            -(
                scenario_values[key]["combo"]
                - (scenario_values[key]["m1"] + scenario_values[key]["m0real"]) / 2.0
            ),
            key[0],
            key[1],
        ),
    )
    lines = ["# 癌症为单位实验结果", "", *_boundary_lines(config["protocol_id"], fingerprint)]
    lines.extend(["", "## 总体三臂比较", "", *_table_header(["范围"])])
    lines.append(_comparison_row(["全部100格等权"], _means(index, all_cells)))
    lines.extend(
        [
            "",
            "## 癌种与癌种×场景：绝对分和相对增益分开报告",
            "",
            f"癌种绝对 C-index 最高：{absolute_cancer}，均值 {cancer_values[absolute_cancer]['combo']:.6f}。",
            "癌种相对两条基线平均 Δ 最大：{}，Δ {}。".format(
                delta_cancer,
                _delta(
                    cancer_values[delta_cancer]["combo"]
                    - (cancer_values[delta_cancer]["m1"] + cancer_values[delta_cancer]["m0real"]) / 2.0
                ),
            ),
            "癌种×场景绝对 C-index 最高：{} / {}，均值 {:.6f}。".format(
                *absolute_scenario, scenario_values[absolute_scenario]["combo"]
            ),
            "癌种×场景相对两条基线平均 Δ 最大：{} / {}，Δ {}。".format(
                *delta_scenario,
                _delta(
                    scenario_values[delta_scenario]["combo"]
                    - (
                        scenario_values[delta_scenario]["m1"]
                        + scenario_values[delta_scenario]["m0real"]
                    )
                    / 2.0
                ),
            ),
            "",
            "## 五癌总体排名",
            "",
            *_table_header(["组合绝对排名", "癌种"]),
        ]
    )
    for rank, cancer in enumerate(
        sorted(cancers, key=lambda c: (-cancer_values[c]["combo"], c)), 1
    ):
        lines.append(_comparison_row([str(rank), cancer], cancer_values[cancer]))
    lines.extend(["", "## 癌种×场景排名", "", *_table_header(["组合绝对排名", "癌种", "场景"])])
    for rank, key in enumerate(
        sorted(scenario_values, key=lambda x: (-scenario_values[x]["combo"], x[0], x[1])), 1
    ):
        lines.append(_comparison_row([str(rank), key[0], key[1]], scenario_values[key]))
    lines.extend(["", "## 按癌种展开的全部100格", ""])
    for cancer in cancers:
        lines.extend([f"### {cancer}", "", *_table_header(["Seed", "场景"])])
        for seed in seeds:
            for grid in grids:
                values = {arm: _value(index, arm, cancer, seed, grid) for arm in _THREE_ARMS}
                lines.append(_comparison_row([str(seed), grid], values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_reports(
    test_rows: list[dict[str, Any]],
    selection: dict[str, Any],
    config: dict[str, Any],
    *,
    status: str,
    blocker: str | None = None,
) -> dict[str, str]:
    """Render all three reports without reading or writing external state."""

    _axes(config)
    if not isinstance(config.get("protocol_id"), str) or not config["protocol_id"]:
        raise ValueError("config.protocol_id must be non-empty")
    if status != "completed":
        if test_rows:
            raise ValueError("unfinished reporting requires test_rows=[]")
        return _render_unfinished(config, status, blocker)
    index, fingerprint = _validate_completed(test_rows, selection, config)
    return {
        _FILENAMES[0]: _render_root(index, selection, config, fingerprint),
        _FILENAMES[1]: _render_seed(index, config, fingerprint),
        _FILENAMES[2]: _render_cancer(index, config, fingerprint),
    }


__all__ = ["render_reports"]
