"""Validation-only candidate construction and selection for zero-training rules 1--5."""

from __future__ import annotations

import copy
import math
from collections import defaultdict
from statistics import fmean
from typing import Any, Iterable


_BASELINES = ("retrieval", "m1", "m0real")
_REQUIRED_ROW_FIELDS = {
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
}


def _locked_axes(config: dict[str, Any]) -> tuple[list[str], list[int], list[str]]:
    cancers = list(config.get("cancers", ()))
    seeds = list(config.get("seeds", ()))
    grids = list(config.get("grids", ()))
    if len(cancers) != 5 or len(set(cancers)) != 5 or not all(isinstance(x, str) for x in cancers):
        raise ValueError("config.cancers must contain five unique strings")
    if len(seeds) != 5 or len(set(seeds)) != 5 or not all(type(x) is int for x in seeds):
        raise ValueError("config.seeds must contain five unique integers")
    if len(grids) != 4 or len(set(grids)) != 4 or set(grids) != {
        "none",
        "rna_100",
        "text_100",
        "both_100",
    }:
        raise ValueError("config.grids must be the four locked scenarios")
    return cancers, seeds, grids


def _finite_grid(config: dict[str, Any], name: str, expected: int) -> list[float]:
    values = list(config.get("search", {}).get(name, ()))
    if len(values) != expected or len(set(values)) != expected:
        raise ValueError(f"config.search.{name} must contain {expected} unique values")
    converted = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"config.search.{name} contains a non-number")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"config.search.{name} contains a non-finite value")
        converted.append(number)
    return converted


def _number_token(value: float) -> str:
    return format(value, ".12g").replace("-", "m").replace(".", "p")


def _candidate(
    protocol: str,
    candidate_id: str,
    enabled_rules: list[int],
    *,
    lambda_value: float = 1.0,
    alpha: float = 0.0,
    w: float = 1.0,
    ucec_exception: bool = False,
) -> dict[str, Any]:
    return {
        "protocol": protocol,
        "candidate_id": candidate_id,
        "enabled_rules": enabled_rules,
        "lambda": float(lambda_value),
        "alpha": float(alpha),
        "w": float(w),
        "ucec_exception": bool(ucec_exception),
    }


def build_candidates(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the locked 13 single-rule plus 45 joint candidate specs."""

    _locked_axes(config)
    rules = list(config.get("rules", ()))
    if len(rules) != 5 or len(set(rules)) != 5 or not all(isinstance(x, str) and x for x in rules):
        raise ValueError("config.rules must contain five unique rule directory names")
    lambdas = _finite_grid(config, "lambda_grid", 5)
    alphas = _finite_grid(config, "alpha_grid", 3)
    weights = _finite_grid(config, "weight_grid", 3)

    candidates = [
        _candidate(rules[0], "single-r1", [1], ucec_exception=True),
        _candidate(rules[1], "single-r2", [2]),
    ]
    candidates.extend(
        _candidate(
            rules[2],
            f"single-r3-l{_number_token(value)}",
            [3],
            lambda_value=value,
        )
        for value in lambdas
    )
    candidates.extend(
        _candidate(
            rules[3],
            f"single-r4-a{_number_token(value)}",
            [4],
            alpha=value,
        )
        for value in alphas
    )
    candidates.extend(
        _candidate(
            rules[4],
            f"single-r5-w{_number_token(value)}",
            [5],
            w=value,
        )
        for value in weights
    )
    candidates.extend(
        _candidate(
            "combo",
            "combo-l{}-a{}-w{}".format(
                _number_token(lambda_value), _number_token(alpha), _number_token(w)
            ),
            [1, 2, 3, 4, 5],
            lambda_value=lambda_value,
            alpha=alpha,
            w=w,
            ucec_exception=True,
        )
        for lambda_value in lambdas
        for alpha in alphas
        for w in weights
    )
    if len(candidates) != 58 or len({item["candidate_id"] for item in candidates}) != 58:
        raise AssertionError("internal candidate construction error")
    return candidates


def _validate_rows(
    rows: list[dict[str, Any]],
    identities: dict[str, str],
    config: dict[str, Any],
    *,
    split: str,
    label: str,
) -> dict[tuple[str, str, int, str], dict[str, Any]]:
    cancers, seeds, grids = _locked_axes(config)
    expected_keys = {
        (candidate_id, cancer, seed, grid)
        for candidate_id in identities
        for cancer in cancers
        for seed in seeds
        for grid in grids
    }
    indexed: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    expected_atol = float(config.get("numerics", {}).get("logit_atol", 1e-6))
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{label}[{position}] is not a dict")
        missing = _REQUIRED_ROW_FIELDS - row.keys()
        if missing:
            raise ValueError(f"{label}[{position}] missing fields: {sorted(missing)}")
        if row["split"] != split:
            raise ValueError(f"{label} must contain only split={split}")
        candidate_id = row["candidate_id"]
        if candidate_id not in identities or row["protocol"] != identities[candidate_id]:
            raise ValueError(f"{label} contains an unknown or mismatched candidate identity")
        if row["cancer"] not in cancers or type(row["seed"]) is not int or row["seed"] not in seeds:
            raise ValueError(f"{label} contains an illegal cancer or seed")
        if row["grid"] not in grids:
            raise ValueError(f"{label} contains an illegal grid")
        value = row["c_index_b"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} contains a non-numeric C-index")
        if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{label} C-index must be finite and in [0, 1]")
        n_patients = row["n_patients"]
        if type(n_patients) is not int or n_patients <= 0:
            raise ValueError(f"{label} n_patients must be a positive integer")
        if not isinstance(row["checkpoint_sha256"], str) or not row["checkpoint_sha256"]:
            raise ValueError(f"{label} checkpoint_sha256 must be non-empty")
        n_checked = row["n_complete_checked"]
        if type(n_checked) is not int or n_checked < 0:
            raise ValueError(f"{label} n_complete_checked must be a non-negative integer")
        if n_checked > n_patients:
            raise ValueError(f"{label} n_complete_checked cannot exceed n_patients")
        diff = row["complete_max_logit_abs_diff"]
        if n_checked == 0:
            if diff is not None:
                raise ValueError(f"{label} must use null complete diff when zero patients were checked")
        else:
            if (
                isinstance(diff, bool)
                or not isinstance(diff, (int, float))
                or not math.isfinite(float(diff))
                or float(diff) < 0.0
            ):
                raise ValueError(f"{label} complete diff must be finite when checks ran")
            if float(diff) > expected_atol:
                raise ValueError(f"{label} complete-logit parity exceeds the locked tolerance")
        row_atol = row["complete_logit_atol"]
        if not isinstance(row_atol, (int, float)) or float(row_atol) != expected_atol:
            raise ValueError(f"{label} complete_logit_atol does not match config")
        key = (candidate_id, row["cancer"], row["seed"], row["grid"])
        if key in indexed:
            raise ValueError(f"{label} contains a duplicate metric cell: {key}")
        indexed[key] = row
    actual_keys = set(indexed)
    if actual_keys != expected_keys:
        missing_count = len(expected_keys - actual_keys)
        extra_count = len(actual_keys - expected_keys)
        raise ValueError(
            f"{label} is not a complete grid: missing={missing_count}, extra={extra_count}"
        )
    return indexed


def _validate_shared_provenance(rows: Iterable[dict[str, Any]]) -> None:
    checkpoint_by_unit: dict[tuple[str, int], set[str]] = defaultdict(set)
    units_by_checkpoint: dict[str, set[tuple[str, int]]] = defaultdict(set)
    patients_by_cell: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    diagnostics_by_cell: dict[tuple[str, int, str], set[tuple[int, float | None]]] = defaultdict(set)
    for row in rows:
        unit = (row["cancer"], row["seed"])
        checkpoint = row["checkpoint_sha256"]
        checkpoint_by_unit[unit].add(checkpoint)
        units_by_checkpoint[checkpoint].add(unit)
        cell = (row["cancer"], row["seed"], row["grid"])
        patients_by_cell[cell].add(row["n_patients"])
        diagnostics_by_cell[cell].add(
            (row["n_complete_checked"], row["complete_max_logit_abs_diff"])
        )
    if any(len(values) != 1 for values in checkpoint_by_unit.values()):
        raise ValueError("checkpoint_sha256 is not shared by all arms/grids of a cancer-seed unit")
    if any(len(values) != 1 for values in patients_by_cell.values()):
        raise ValueError("n_patients differs across arms for the same metric cell")
    if any(len(units) != 1 for units in units_by_checkpoint.values()):
        raise ValueError("one checkpoint_sha256 is reused by different cancer-seed units")
    if any(len(values) != 1 for values in diagnostics_by_cell.values()):
        raise ValueError(
            "n_complete_checked or complete_max_logit_abs_diff differs across arms for one cell"
        )


def choose_validation(
    rows: list[dict[str, Any]],
    specs: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Validate all valid cells, route rule-1 text cells, and select six specs globally."""

    if not isinstance(specs, list) or not specs:
        raise ValueError("specs must be a non-empty list")
    locked_specs = build_candidates(config)
    locked_by_id = {item["candidate_id"]: item for item in locked_specs}
    provided_by_id = {
        item.get("candidate_id"): item for item in specs if isinstance(item, dict)
    }
    if len(specs) != 58 or provided_by_id != locked_by_id:
        raise ValueError("specs must be exactly the 58 candidates returned by build_candidates(config)")
    required_spec_fields = {
        "protocol",
        "candidate_id",
        "enabled_rules",
        "lambda",
        "alpha",
        "w",
        "ucec_exception",
    }
    identities: dict[str, str] = {}
    for spec in specs:
        if not isinstance(spec, dict) or set(spec) != required_spec_fields:
            raise ValueError("every candidate spec must match the locked schema exactly")
        candidate_id = spec["candidate_id"]
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in identities:
            raise ValueError("candidate_id values must be non-empty and unique")
        identities[candidate_id] = spec["protocol"]
    baseline_identities = {name: name for name in _BASELINES}
    candidate_index = _validate_rows(rows, identities, config, split="valid", label="rows")
    baseline_index = _validate_rows(
        baseline_rows, baseline_identities, config, split="valid", label="baseline_rows"
    )
    _validate_shared_provenance([*rows, *baseline_rows])

    cancers, seeds, grids = _locked_axes(config)
    baseline_means = {
        name: fmean(
            float(baseline_index[(name, cancer, seed, grid)]["c_index_b"])
            for cancer in cancers
            for seed in seeds
            for grid in grids
        )
        for name in _BASELINES
    }
    candidate_scores: list[dict[str, Any]] = []
    routed_rows: list[dict[str, Any]] = []
    score_by_id: dict[str, dict[str, Any]] = {}
    for spec in specs:
        candidate_id = spec["candidate_id"]
        has_rule1 = 1 in spec["enabled_rules"]
        candidate_ucec_text = [
            float(candidate_index[(candidate_id, "UCEC", seed, "text_100")]["c_index_b"])
            for seed in seeds
        ]
        m0_ucec_text = [
            float(baseline_index[("m0real", "UCEC", seed, "text_100")]["c_index_b"])
            for seed in seeds
        ]
        ucec_candidate_mean = fmean(candidate_ucec_text)
        ucec_m0real_mean = fmean(m0_ucec_text)
        ucec_enabled = bool(has_rule1 and ucec_candidate_mean > ucec_m0real_mean)
        raw_values: list[float] = []
        routed_values: list[float] = []
        ucec_routed_values: list[float] = []
        for cancer in cancers:
            for seed in seeds:
                for grid in grids:
                    original = candidate_index[(candidate_id, cancer, seed, grid)]
                    raw_value = float(original["c_index_b"])
                    raw_values.append(raw_value)
                    use_m0 = has_rule1 and grid == "text_100" and (
                        cancer != "UCEC" or not ucec_enabled
                    )
                    if use_m0:
                        source = baseline_index[("m0real", cancer, seed, grid)]
                        routed_value = float(source["c_index_b"])
                        routed_from = "m0real"
                    else:
                        source = original
                        routed_value = raw_value
                        routed_from = candidate_id
                    routed_values.append(routed_value)
                    if cancer == "UCEC" and grid == "text_100":
                        ucec_routed_values.append(routed_value)
                    routed = copy.deepcopy(source)
                    routed.update(
                        {
                            "protocol": spec["protocol"],
                            "candidate_id": candidate_id,
                            "c_index_b": routed_value,
                            "raw_c_index_b": raw_value,
                            "routed_from": routed_from,
                            "synthetic": bool(original.get("synthetic", False)),
                        }
                    )
                    routed_rows.append(routed)
        routed_mean = fmean(routed_values)
        score = {
            "protocol": spec["protocol"],
            "candidate_id": candidate_id,
            "enabled_rules": list(spec["enabled_rules"]),
            "lambda": float(spec["lambda"]),
            "alpha": float(spec["alpha"]),
            "w": float(spec["w"]),
            "raw_mean": fmean(raw_values),
            "routed_mean": routed_mean,
            "mean_delta_m1": routed_mean - baseline_means["m1"],
            "mean_delta_m0real": routed_mean - baseline_means["m0real"],
            "mean_delta_two_baselines": routed_mean
            - (baseline_means["m1"] + baseline_means["m0real"]) / 2.0,
            "feasible_vs_both": routed_mean >= baseline_means["m1"]
            and routed_mean >= baseline_means["m0real"],
            "ucec_candidate_mean": ucec_candidate_mean if has_rule1 else None,
            "ucec_m0real_mean": ucec_m0real_mean if has_rule1 else None,
            "ucec_text_routed_mean": fmean(ucec_routed_values),
            "ucec_exception_enabled": ucec_enabled,
        }
        candidate_scores.append(score)
        score_by_id[candidate_id] = score

    by_protocol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec in specs:
        by_protocol[spec["protocol"]].append(spec)
    expected_protocols = set(config["rules"]) | {"combo"}
    if set(by_protocol) != expected_protocols:
        raise ValueError("specs must contain exactly the five rule protocols and combo")
    selected: dict[str, dict[str, Any]] = {}
    for protocol in [*config["rules"], "combo"]:
        protocol_specs = by_protocol[protocol]
        feasible = [
            spec for spec in protocol_specs if score_by_id[spec["candidate_id"]]["feasible_vs_both"]
        ]
        pool = feasible or protocol_specs
        winner = min(
            pool,
            key=lambda spec: (
                -score_by_id[spec["candidate_id"]]["routed_mean"],
                float(spec["lambda"]),
                float(spec["w"]),
                float(spec["alpha"]),
                spec["candidate_id"],
            ),
        )
        locked = copy.deepcopy(winner)
        locked["ucec_exception"] = score_by_id[winner["candidate_id"]][
            "ucec_exception_enabled"
        ]
        selected[protocol] = locked

    return {
        "selected": selected,
        "candidates": candidate_scores,
        "routed_rows": routed_rows,
        "schema_version": 1,
    }


__all__ = ["build_candidates", "choose_validation"]
