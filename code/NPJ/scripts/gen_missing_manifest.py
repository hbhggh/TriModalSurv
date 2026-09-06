#!/usr/bin/env python3
"""为五个癌种的 test split 生成固定、嵌套的缺失模态 manifest。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple


CANCERS: Tuple[str, ...] = ("BLCA", "BRCA", "LUAD", "LGG", "UCEC")
MODES: Tuple[str, ...] = ("rna", "text", "both")
RATES: Tuple[int, ...] = (25, 50, 75)
GRID_COLUMNS: Tuple[str, ...] = tuple(
    f"{mode}_{rate}" for mode in MODES for rate in RATES
)
OUTPUT_COLUMNS: Tuple[str, ...] = ("patient_id", "cancer", *GRID_COLUMNS)
TRUE_VALUES = {"1", "true"}
FALSE_VALUES = {"0", "false", ""}


def _required_columns(fieldnames: Iterable[str] | None, required: Set[str], role: str) -> None:
    available = set(fieldnames or ())
    missing = sorted(required - available)
    if missing:
        raise ValueError(f"{role} 缺少必需列: {', '.join(missing)}")


def read_test_patients(labels_path: Path) -> Dict[str, List[str]]:
    """读取五癌 test 患者，并按癌种和 patient_id 固定排序。"""
    patients = {cancer: [] for cancer in CANCERS}
    seen: Set[str] = set()
    with labels_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _required_columns(
            reader.fieldnames,
            {"patient_id", "cancer_type", "split"},
            "labels CSV",
        )
        for line_number, row in enumerate(reader, start=2):
            patient_id = (row.get("patient_id") or "").strip()
            cancer = (row.get("cancer_type") or "").strip().upper()
            split = (row.get("split") or "").strip().lower()
            if cancer not in patients or split != "test":
                continue
            if not patient_id:
                raise ValueError(f"labels CSV 第 {line_number} 行 patient_id 为空")
            if patient_id in seen:
                raise ValueError(f"labels CSV 的目标 test 患者重复: {patient_id}")
            seen.add(patient_id)
            patients[cancer].append(patient_id)

    empty_cancers = [cancer for cancer, values in patients.items() if not values]
    if empty_cancers:
        raise ValueError(f"以下癌种没有 test 患者: {', '.join(empty_cancers)}")
    for values in patients.values():
        values.sort()
    return patients


def _mode_rng(seed: int, cancer: str, mode: str) -> random.Random:
    """为每个癌种和模式派生独立、跨进程稳定的随机流。"""
    key = f"{seed}\0{cancer}\0{mode}".encode("utf-8")
    derived_seed = int.from_bytes(hashlib.sha256(key).digest(), "big")
    return random.Random(derived_seed)


def build_manifest_rows(
    patients_by_cancer: Mapping[str, Sequence[str]],
    seed: int,
) -> Tuple[List[Dict[str, object]], Dict[str, Dict[str, int]]]:
    """按同一乱序前缀构造嵌套名单和逐癌计数。"""
    rows: List[Dict[str, object]] = []
    stats: Dict[str, Dict[str, int]] = {}

    for cancer in CANCERS:
        patients = list(patients_by_cancer[cancer])
        memberships: Dict[str, Set[str]] = {}
        stats[cancer] = {}
        for mode in MODES:
            shuffled = patients.copy()
            _mode_rng(seed, cancer, mode).shuffle(shuffled)
            for rate in RATES:
                grid = f"{mode}_{rate}"
                count = len(patients) * rate // 100
                memberships[grid] = set(shuffled[:count])
                stats[cancer][grid] = count

        for patient_id in patients:
            row: Dict[str, object] = {
                "patient_id": patient_id,
                "cancer": cancer,
            }
            row.update(
                {grid: int(patient_id in memberships[grid]) for grid in GRID_COLUMNS}
            )
            rows.append(row)

    return rows, stats


def write_manifest(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=OUTPUT_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_bool(value: object, *, context: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{context} 不是布尔值: {value!r}")


def verify_manifest(manifest_path: Path, labels_path: Path) -> Dict[str, Dict[str, int]]:
    """验证患者范围、癌种、嵌套性和逐癌比例误差。"""
    expected_by_cancer = read_test_patients(labels_path)
    expected_cancer = {
        patient_id: cancer
        for cancer, patients in expected_by_cancer.items()
        for patient_id in patients
    }
    selected: Dict[str, Dict[str, Set[str]]] = {
        cancer: {grid: set() for grid in GRID_COLUMNS} for cancer in CANCERS
    }
    seen: Set[str] = set()

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OUTPUT_COLUMNS:
            raise ValueError(
                "manifest 列不符合契约: "
                f"实际={reader.fieldnames!r}, 预期={list(OUTPUT_COLUMNS)!r}"
            )
        for line_number, row in enumerate(reader, start=2):
            patient_id = (row.get("patient_id") or "").strip()
            cancer = (row.get("cancer") or "").strip().upper()
            if patient_id in seen:
                raise ValueError(f"manifest 患者重复: {patient_id}")
            seen.add(patient_id)
            if patient_id not in expected_cancer:
                raise ValueError(f"manifest 含非目标 test 患者: {patient_id}")
            if expected_cancer[patient_id] != cancer:
                raise ValueError(
                    f"manifest 癌种不匹配: {patient_id} 实际={cancer} "
                    f"预期={expected_cancer[patient_id]}"
                )
            for grid in GRID_COLUMNS:
                if _parse_bool(row[grid], context=f"第 {line_number} 行 {grid}"):
                    selected[cancer][grid].add(patient_id)

    expected_patients = set(expected_cancer)
    if seen != expected_patients:
        missing = sorted(expected_patients - seen)
        extra = sorted(seen - expected_patients)
        raise ValueError(
            f"manifest 患者集合不等于五癌 test 集合: missing={missing[:5]}, extra={extra[:5]}"
        )

    counts: Dict[str, Dict[str, int]] = {}
    for cancer in CANCERS:
        n_test = len(expected_by_cancer[cancer])
        counts[cancer] = {}
        for mode in MODES:
            sets = [selected[cancer][f"{mode}_{rate}"] for rate in RATES]
            if not sets[0] <= sets[1] <= sets[2]:
                raise ValueError(f"{cancer}/{mode} 不满足 25% ⊂ 50% ⊂ 75% 嵌套")
            for rate, members in zip(RATES, sets):
                grid = f"{mode}_{rate}"
                count = len(members)
                if abs(count - n_test * rate / 100.0) > 1.0:
                    raise ValueError(
                        f"{cancer}/{grid} 比例误差超过 1 人: count={count}, n={n_test}"
                    )
                counts[cancer][grid] = count
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True, type=Path, help="标签 CSV")
    parser.add_argument("--seed", required=True, type=int, help="固定随机种子")
    parser.add_argument("--out", required=True, type=Path, help="manifest 输出 CSV")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="写出后验证嵌套、人数误差及 test 患者范围",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    patients = read_test_patients(args.labels)
    rows, counts = build_manifest_rows(patients, args.seed)
    write_manifest(args.out, rows)
    digest = file_sha256(args.out)

    if args.verify:
        verified_counts = verify_manifest(args.out, args.labels)
        if verified_counts != counts:
            raise ValueError("生成计数与重新读取验证计数不一致")
        print("VERIFY_OK")

    stats_path = Path(f"{args.out}.stats.json")
    stats_payload = {
        "seed": args.seed,
        "labels": str(args.labels),
        "manifest": str(args.out),
        "manifest_sha256": digest,
        "n_test": {cancer: len(patients[cancer]) for cancer in CANCERS},
        "counts": counts,
    }
    with stats_path.open("w", encoding="utf-8") as handle:
        json.dump(stats_payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    print(f"STATS_JSON={stats_path}")
    print(f"SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
