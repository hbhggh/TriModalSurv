#!/usr/bin/env python3
"""Validate and summarize fixed-bank patient-retrieval evaluation units."""

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from pathlib import Path


ARMS = ("m0real", "m1", "retrieval")
CANCERS = ("BLCA", "BRCA", "LGG", "LUAD", "UCEC")
SEEDS = (123, 132, 213, 231, 321)
GRIDS = ("none", "rna_100", "text_100", "both_100")
MISSING_GRIDS = ("rna_100", "text_100", "both_100")
PROTOCOL_ID = "patient-fixed-padmask-v2"
OUTPUT_NAMES = ("summary.json", "per_cell.csv", "paired_deltas.csv", "report.md")
UNIT_NAME = re.compile(r"^(m0real|m1|retrieval)_(BLCA|BRCA|LGG|LUAD|UCEC)_s(123|132|213|231|321)\.json$")
REQUIRED_UNIT_FIELDS = {
    "arm",
    "cancer",
    "seed",
    "checkpoint_sha256",
    "comparison_fingerprint",
    "protocol_id",
    "grids",
}
REQUIRED_GRID_FIELDS = {
    "cindex_B",
    "n_test",
    "n_complete_checked",
    "complete_max_logit_abs_diff",
    "complete_logit_atol",
    "grid_sha",
    "predictions_file",
    "predictions_sha256",
    "audit_file",
    "audit_sha256",
}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_string(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _artifact_path(base_dir, relative_value, label):
    _require_string(relative_value, label)
    relative = Path(relative_value)
    if relative.is_absolute():
        raise ValueError(f"{label} must be relative")
    base = base_dir.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as error:
        raise ValueError(f"{label} escapes input directory") from error
    if not candidate.is_file():
        raise ValueError(f"{label} does not exist: {relative_value}")
    return candidate


def validate_complete_diagnostics(grid, grid_name, *, allow_legacy=False):
    """人数/误差是同一项检查的契约；旧证据只能标未知，不能升级为通过。"""
    if 'n_complete_checked' not in grid:
        if allow_legacy:
            return {'status': 'legacy_unknown', 'n_complete_checked': None,
                    'complete_max_logit_abs_diff': None}
        raise ValueError('missing n_complete_checked')
    count = grid['n_complete_checked']
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= grid['n_test']:
        raise ValueError('invalid n_complete_checked')
    if grid_name != 'none' and count != 0:
        raise ValueError('artificial missing grid cannot have complete checks')
    if grid.get('complete_logit_atol') != 1e-6:
        raise ValueError('invalid complete_logit_atol')
    if 'complete_max_logit_abs_diff' not in grid:
        raise ValueError('missing complete_max_logit_abs_diff')
    delta = grid['complete_max_logit_abs_diff']
    if count == 0:
        if delta is not None:
            raise ValueError('complete_max_logit_abs_diff must be null when no checks ran')
    elif (isinstance(delta, bool) or not isinstance(delta, (int, float))
          or not math.isfinite(delta) or not 0 <= delta <= 1e-6):
        raise ValueError('invalid complete_max_logit_abs_diff for checked samples')
    return {'status': 'checked' if count else 'not_checked',
            'n_complete_checked': count, 'complete_max_logit_abs_diff': delta}


def _validate_grid(grid, unit_path, grid_name):
    if not isinstance(grid, dict):
        raise ValueError(f"{unit_path.name}:{grid_name} must be an object")
    missing = REQUIRED_GRID_FIELDS - set(grid)
    if missing:
        raise ValueError(f"{unit_path.name}:{grid_name} missing fields: {sorted(missing)}")

    cindex = grid["cindex_B"]
    if isinstance(cindex, bool) or not isinstance(cindex, (int, float)):
        raise ValueError(f"{unit_path.name}:{grid_name} cindex_B must be numeric")
    cindex = float(cindex)
    if not math.isfinite(cindex) or not 0.0 <= cindex <= 1.0:
        raise ValueError(f"{unit_path.name}:{grid_name} cindex_B must be finite in [0, 1]")

    n_test = grid["n_test"]
    if isinstance(n_test, bool) or not isinstance(n_test, int) or n_test <= 0:
        raise ValueError(f"{unit_path.name}:{grid_name} n_test must be a positive integer")
    validate_complete_diagnostics(grid, grid_name)
    _require_string(grid["grid_sha"], f"{unit_path.name}:{grid_name} grid_sha")

    for file_key, hash_key in (
        ("predictions_file", "predictions_sha256"),
        ("audit_file", "audit_sha256"),
    ):
        artifact = _artifact_path(unit_path.parent, grid[file_key], f"{unit_path.name}:{grid_name} {file_key}")
        expected_hash = grid[hash_key]
        _require_string(expected_hash, f"{unit_path.name}:{grid_name} {hash_key}")
        if _sha256(artifact) != expected_hash:
            raise ValueError(f"{unit_path.name}:{grid_name} {file_key} sha256 mismatch")
    grid["cindex_B"] = cindex



RUN_MANIFESTS = frozenset(('source_manifest.json', 'data_manifest.json', 'checkpoint_manifest.json'))


def _validate_run_manifest(path):
    """仅识别新入口的三个已知文件；验证 schema 后才从单元枚举排除。"""
    def require(condition):
        if not condition:
            raise ValueError(f"invalid manifest schema: {path.name}")

    def digest(value, length=64):
        return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{' + str(length) + r'}', value) is not None

    def hashes(value):
        return (isinstance(value, dict) and bool(value)
                and all(isinstance(key, str) and bool(key) and digest(item) for key, item in value.items()))

    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid manifest schema: {path.name}: {error}") from error
    fields = {'cancers', 'failures'}
    if path.name == 'source_manifest.json':
        fields.add('source_commit')
    require(isinstance(payload, dict) and set(payload) == fields)
    require(payload['failures'] == {})
    require(isinstance(payload['cancers'], dict) and set(payload['cancers']) == set(CANCERS))
    if path.name == 'source_manifest.json':
        require(digest(payload['source_commit'], 40))
    for value in payload['cancers'].values():
        require(isinstance(value, dict))
        if path.name == 'source_manifest.json':
            require(hashes(value))
        elif path.name == 'data_manifest.json':
            require(set(value) == {'bank', 'label_sha256', 'manifest_sha256', 'cache_hashes'})
            require(isinstance(value['bank'], dict) and bool(value['bank']))
            require(digest(value['label_sha256']) and digest(value['manifest_sha256']))
            require(hashes(value['cache_hashes']))
        else:
            require(set(value) == {str(seed) for seed in SEEDS})
            for checkpoint in value.values():
                require(isinstance(checkpoint, dict) and set(checkpoint) == {
                    'path', 'sha256', 'state_sha256', 'strict_load'})
                require(isinstance(checkpoint['path'], str) and bool(checkpoint['path']))
                require(digest(checkpoint['sha256']) and digest(checkpoint['state_sha256']))
                require(checkpoint['strict_load'] is True)


def _load_units(input_dir):
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")

    units = {}
    for unit_path in sorted(input_dir.glob("*.json")):
        if unit_path.name in RUN_MANIFESTS:
            _validate_run_manifest(unit_path)
            continue
        match = UNIT_NAME.fullmatch(unit_path.name)
        if match is None:
            raise ValueError(f"unknown unit filename: {unit_path.name}")
        try:
            payload = json.loads(unit_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot read unit {unit_path.name}: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError(f"{unit_path.name} must contain a JSON object")
        missing = REQUIRED_UNIT_FIELDS - set(payload)
        if missing:
            raise ValueError(f"{unit_path.name} missing fields: {sorted(missing)}")

        filename_identity = (match.group(1), match.group(2), int(match.group(3)))
        identity = (payload["arm"], payload["cancer"], payload["seed"])
        if identity != filename_identity:
            raise ValueError(f"{unit_path.name} identity does not match filename")
        if identity in units:
            raise ValueError(f"duplicate unit identity: {identity}")
        if payload["protocol_id"] != PROTOCOL_ID:
            raise ValueError(f"{unit_path.name} has unsupported protocol_id")
        _require_string(payload["checkpoint_sha256"], f"{unit_path.name} checkpoint_sha256")
        _require_string(payload["comparison_fingerprint"], f"{unit_path.name} comparison_fingerprint")
        grids = payload["grids"]
        if not isinstance(grids, dict) or set(grids) != set(GRIDS):
            raise ValueError(f"{unit_path.name} grids must be exactly {list(GRIDS)}")
        for grid_name in GRIDS:
            _validate_grid(grids[grid_name], unit_path, grid_name)
        units[identity] = payload

    expected = {(arm, cancer, seed) for arm in ARMS for cancer in CANCERS for seed in SEEDS}
    actual = set(units)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"unit set incomplete or unknown; missing={missing}, unknown={unknown}")
    return units


def _validate_campaign_status(input_dir):
    status_path = Path(input_dir) / "diagnostics" / "campaign_status.json"
    if not status_path.is_file():
        raise ValueError(f"missing campaign status: {status_path}")
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read campaign status: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("campaign status must be a JSON object")
    if payload.get("stage") != "formal" or payload.get("status") != "COMPLETED":
        raise ValueError(
            "campaign is not a completed formal run: "
            f"stage={payload.get('stage')!r}, status={payload.get('status')!r}"
        )


def _validate_pairing(units):
    for cancer in CANCERS:
        cancer_fingerprints = set()
        cancer_checkpoints = []
        for seed in SEEDS:
            paired = [units[(arm, cancer, seed)] for arm in ARMS]
            checkpoints = {unit["checkpoint_sha256"] for unit in paired}
            fingerprints = {unit["comparison_fingerprint"] for unit in paired}
            if len(checkpoints) != 1 or len(fingerprints) != 1:
                raise ValueError(f"paired hashes mismatch for {cancer} seed {seed}")
            cancer_checkpoints.append(next(iter(checkpoints)))
            cancer_fingerprints.update(fingerprints)
            for grid_name in GRIDS:
                n_tests = {unit["grids"][grid_name]["n_test"] for unit in paired}
                grid_hashes = {unit["grids"][grid_name]["grid_sha"] for unit in paired}
                check_metadata = {tuple(unit['grids'][grid_name][key] for key in (
                    'n_complete_checked', 'complete_max_logit_abs_diff', 'complete_logit_atol'))
                    for unit in paired}
                if len(n_tests) != 1 or len(grid_hashes) != 1 or len(check_metadata) != 1:
                    raise ValueError(f"paired grid metadata mismatch for {cancer} seed {seed} {grid_name}")
        if len(cancer_fingerprints) != 1:
            raise ValueError(f"comparison_fingerprint differs across seeds for {cancer}")
        if len(set(cancer_checkpoints)) != len(SEEDS):
            raise ValueError(f"checkpoint_sha256 reused across seeds for {cancer}")


def _mean(values):
    return statistics.fmean(values)


def _sample_std(values):
    return statistics.stdev(values)


def _build_summary(units):
    per_cell = []
    cell_lookup = {}
    for cancer in CANCERS:
        for grid_name in GRIDS:
            for arm in ARMS:
                values = [units[(arm, cancer, seed)]["grids"][grid_name]["cindex_B"] for seed in SEEDS]
                cell = {
                    "cancer": cancer,
                    "grid": grid_name,
                    "arm": arm,
                    "n_seeds": len(values),
                    "mean": _mean(values),
                    "sample_std": _sample_std(values),
                }
                per_cell.append(cell)
                cell_lookup[(cancer, grid_name, arm)] = cell

    contrasts = []
    paired_rows = []
    for cancer in CANCERS:
        for grid_name in GRIDS:
            for baseline in ("m1", "m0real"):
                contrast_name = f"retrieval-minus-{baseline}"
                deltas = []
                for seed in SEEDS:
                    delta = (
                        units[("retrieval", cancer, seed)]["grids"][grid_name]["cindex_B"]
                        - units[(baseline, cancer, seed)]["grids"][grid_name]["cindex_B"]
                    )
                    deltas.append(delta)
                wins = sum(delta > 0.0 for delta in deltas)
                ties = sum(delta == 0.0 for delta in deltas)
                losses = sum(delta < 0.0 for delta in deltas)
                contrast = {
                    "cancer": cancer,
                    "grid": grid_name,
                    "contrast": contrast_name,
                    "seeds": list(SEEDS),
                    "deltas": deltas,
                    "mean": _mean(deltas),
                    "sample_std": _sample_std(deltas),
                    "wins": wins,
                    "ties": ties,
                    "losses": losses,
                }
                contrasts.append(contrast)
                for seed, delta in zip(SEEDS, deltas):
                    paired_rows.append(
                        {
                            "cancer": cancer,
                            "grid": grid_name,
                            "contrast": contrast_name,
                            "seed": seed,
                            "delta": delta,
                            "mean": contrast["mean"],
                            "sample_std": contrast["sample_std"],
                            "wins": wins,
                            "ties": ties,
                            "losses": losses,
                        }
                    )

    overview_arms = {
        arm: _mean([cell_lookup[(cancer, grid_name, arm)]["mean"] for cancer in CANCERS for grid_name in MISSING_GRIDS])
        for arm in ARMS
    }
    overview_contrasts = {}
    for baseline in ("m1", "m0real"):
        contrast_name = f"retrieval-minus-{baseline}"
        overview_contrasts[contrast_name] = _mean(
            [
                item["mean"]
                for item in contrasts
                if item["grid"] in MISSING_GRIDS and item["contrast"] == contrast_name
            ]
        )

    worst_missing = []
    for cancer in CANCERS:
        for arm in ARMS:
            worst = min(
                (cell_lookup[(cancer, grid_name, arm)] for grid_name in MISSING_GRIDS),
                key=lambda item: item["mean"],
            )
            worst_missing.append(
                {"cancer": cancer, "arm": arm, "grid": worst["grid"], "mean": worst["mean"]}
            )

    summary = {
        "protocol_id": PROTOCOL_ID,
        "unit_count": len(units),
        "arms": list(ARMS),
        "cancers": list(CANCERS),
        "seeds": list(SEEDS),
        "grids": list(GRIDS),
        "per_cell": per_cell,
        "contrasts": contrasts,
        "overview_missing_only": {"grids": list(MISSING_GRIDS), "arms": overview_arms, "contrasts": overview_contrasts},
        "worst_missing_grid": worst_missing,
    }
    return summary, paired_rows


def _write_csv(path, fieldnames, rows):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _render_report(summary):
    lines = [
        "# Patient fixed-bank evaluation summary",
        "",
        f"Protocol: `{PROTOCOL_ID}`; validated units: {summary['unit_count']}.",
        "",
        "## Missing-grid macro overview",
        "",
        "The macro overview equally weights five cancers and three missing grids; `none` is excluded.",
        "",
        "| arm | mean cindex_B |",
        "|---|---:|",
    ]
    for arm in ARMS:
        lines.append(f"| {arm} | {summary['overview_missing_only']['arms'][arm]:.6f} |")
    lines.extend(["", "| contrast | mean paired delta |", "|---|---:|"])
    for name, value in summary["overview_missing_only"]["contrasts"].items():
        lines.append(f"| {name} | {value:.6f} |")
    lines.extend(["", "## 无额外人工遮挡（`none`，保留天然缺失）", "",
                  "天然缺失仍按三臂各自规则处理；该场景不表示所有患者模态齐全。", "",
                  "| cancer | arm | mean | sample std |", "|---|---|---:|---:|"])
    for cell in summary["per_cell"]:
        if cell["grid"] == "none":
            lines.append(f"| {cell['cancer']} | {cell['arm']} | {cell['mean']:.6f} | {cell['sample_std']:.6f} |")
    lines.extend(["", "## Worst missing grid by cancer and arm", "", "| cancer | arm | grid | mean |", "|---|---|---|---:|"])
    for item in summary["worst_missing_grid"]:
        lines.append(f"| {item['cancer']} | {item['arm']} | {item['grid']} | {item['mean']:.6f} |")
    lines.extend(["", "This report is descriptive only and does not perform significance testing.", ""])
    return "\n".join(lines)


def summarize(input_dir, output_dir):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    existing = [name for name in OUTPUT_NAMES if (output_dir / name).exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite existing outputs: {existing}")

    _validate_campaign_status(input_dir)
    units = _load_units(input_dir)
    _validate_pairing(units)
    summary, paired_rows = _build_summary(units)

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "summary.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    _write_csv(
        output_dir / "per_cell.csv",
        ("cancer", "grid", "arm", "n_seeds", "mean", "sample_std"),
        summary["per_cell"],
    )
    _write_csv(
        output_dir / "paired_deltas.csv",
        ("cancer", "grid", "contrast", "seed", "delta", "mean", "sample_std", "wins", "ties", "losses"),
        paired_rows,
    )
    with (output_dir / "report.md").open("x", encoding="utf-8") as handle:
        handle.write(_render_report(summary))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, help="默认写入本次 run 的 analysis 目录")
    args = parser.parse_args(argv)
    summarize(args.input_dir, args.out_dir or args.input_dir / "analysis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
