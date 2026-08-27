#!/usr/bin/env python3
"""以 labels_424.csv 为唯一真源，构建统一结局表与两库 adapted dataset CSV。"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator, TextIO


SUPPORTED_CANCERS = ("BLCA", "BRCA", "LUAD", "LGG", "UCEC")
SUPPORTED_LIBS = ("MCAT", "PORPOISE")
SOURCE_DIRS = {"MCAT": "dataset_csv", "PORPOISE": "datasets_csv_mutsig"}
PATIENT_ID_RE = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}$")
OUTCOME_COLUMNS = ("survival_months", "censorship")
SCALE_FACTOR = Decimal("30.44") / Decimal("30")
SCALE_TOLERANCE = Decimal("0.0051")


@dataclass(frozen=True)
class Outcome:
    patient_id: str
    cancer: str
    split: str
    survival_text: str
    survival: Decimal
    censorship: int


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_decimal(value: str, *, field: str, context: str) -> Decimal:
    try:
        parsed = Decimal(value.strip())
    except (AttributeError, InvalidOperation) as exc:
        raise ValueError(f"{context} 的 {field} 不是有效数值: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"{context} 的 {field} 必须是有限数值: {value!r}")
    return parsed


def parse_censorship(value: str, *, context: str) -> int:
    parsed = parse_decimal(value, field="censorship", context=context)
    if parsed not in (Decimal(0), Decimal(1)):
        raise ValueError(f"{context} 的 censorship 必须是 0 或 1: {value!r}")
    return int(parsed)


def read_labels(path: Path) -> tuple[list[Outcome], dict[str, dict[str, Outcome]]]:
    required = {"patient_id", "cancer_type", "split", *OUTCOME_COLUMNS}
    outcomes: list[Outcome] = []
    by_cancer: dict[str, dict[str, Outcome]] = {cancer: {} for cancer in SUPPORTED_CANCERS}
    seen: dict[str, Outcome] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"labels 缺少必需列: {missing}")
        for line_number, row in enumerate(reader, start=2):
            patient_id = row["patient_id"].strip().upper()
            cancer = row["cancer_type"].strip().upper()
            split = row["split"].strip().lower()
            context = f"labels 第 {line_number} 行（{patient_id or '空 patient_id'}）"
            if not PATIENT_ID_RE.fullmatch(patient_id):
                raise ValueError(f"{context} 的 patient_id 不是 12 字符 TCGA barcode")
            if cancer not in by_cancer:
                continue  # labels_424 为 13 癌种全表；本战役只消费 SUPPORTED_CANCERS，其余行跳过
            if split not in {"train", "valid", "test"}:
                raise ValueError(f"{context} 的 split 不受支持: {split!r}")
            survival_text = row["survival_months"].strip()
            survival = parse_decimal(survival_text, field="survival_months", context=context)
            if survival < 0:
                raise ValueError(f"{context} 的 survival_months 不能为负数")
            censorship = parse_censorship(row["censorship"], context=context)
            outcome = Outcome(
                patient_id=patient_id,
                cancer=cancer,
                split=split,
                survival_text=survival_text,
                survival=survival,
                censorship=censorship,
            )
            if patient_id in seen:
                previous = seen[patient_id]
                raise ValueError(
                    f"patient_id 重复或跨癌种/split: {patient_id}（{previous.cancer}/{previous.split} 与 {cancer}/{split}）"
                )
            seen[patient_id] = outcome
            by_cancer[cancer][patient_id] = outcome
            outcomes.append(outcome)
    if not outcomes:
        raise ValueError("labels 为空")
    return outcomes, by_cancer


def source_zip(repo_root: Path, library: str, cancer: str) -> Path:
    source_cancer = "gbmlgg" if cancer == "LGG" else cancer.lower()
    path = (
        repo_root
        / "baselines"
        / library
        / SOURCE_DIRS[library]
        / f"tcga_{source_cancer}_all_clean.csv.zip"
    )
    if not path.is_file():
        raise FileNotFoundError(f"找不到 {library}/{cancer} 官方 CSV: {path}")
    return path


def zip_member(archive: zipfile.ZipFile, path: Path) -> str:
    members = [name for name in archive.namelist() if name and not name.endswith("/")]
    if len(members) != 1:
        raise ValueError(f"{path} 应恰有一个非目录成员，实际为 {members}")
    member = members[0]
    member_path = Path(member)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"{path} 含不安全 ZIP 成员名: {member!r}")
    return member


@contextmanager
def open_zip_reader(path: Path) -> Iterator[csv.DictReader]:
    with zipfile.ZipFile(path) as archive:
        member = zip_member(archive, path)
        with archive.open(member) as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text)
                if not reader.fieldnames:
                    raise ValueError(f"{path} 的 CSV 没有表头")
                required = {"case_id", "slide_id", *OUTCOME_COLUMNS}
                if not required.issubset(reader.fieldnames):
                    raise ValueError(f"{path} 缺少列: {sorted(required - set(reader.fieldnames))}")
                yield reader


def temporary_path(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False
    )
    handle.close()
    return Path(handle.name)


def write_csv_atomic(path: Path, fieldnames: list[str], rows: Iterator[dict[str, str]]) -> None:
    tmp = temporary_path(path)
    try:
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def decimal_text(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def collect_official_outcomes(
    source: Path,
) -> tuple[list[str], dict[str, tuple[Decimal, int]], set[str]]:
    official: dict[str, tuple[Decimal, int]] = {}
    case_ids: set[str] = set()
    with open_zip_reader(source) as reader:
        fieldnames = list(reader.fieldnames or [])
        for line_number, row in enumerate(reader, start=2):
            case_id = (row.get("case_id") or "").strip().upper()
            if not case_id:
                raise ValueError(f"{source} 第 {line_number} 行 case_id 为空")
            context = f"{source.name} 第 {line_number} 行（{case_id}）"
            value = (
                parse_decimal(row["survival_months"], field="survival_months", context=context),
                parse_censorship(row["censorship"], context=context),
            )
            previous = official.get(case_id)
            if previous is not None and previous != value:
                raise ValueError(f"{source} 同一患者 {case_id} 的官方结局跨 slide 不一致")
            official[case_id] = value
            case_ids.add(case_id)
    return fieldnames, official, case_ids


def write_adapted_zip(
    source: Path,
    target: Path,
    library: str,
    cancer: str,
    labels: dict[str, Outcome],
    *,
    include_test: bool,
) -> tuple[int, set[str]]:
    tmp = temporary_path(target)
    written_rows = 0
    written_cases: set[str] = set()
    member_name = target.name.removesuffix(".zip")
    try:
        with open_zip_reader(source) as reader:
            fieldnames = list(reader.fieldnames or [])
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                with archive.open(member_name, "w") as raw:
                    with io.TextIOWrapper(raw, encoding="utf-8", newline="") as text:
                        writer = csv.DictWriter(text, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in reader:
                            case_id = (row.get("case_id") or "").strip().upper()
                            outcome = labels.get(case_id)
                            if outcome is None or (not include_test and outcome.split == "test"):
                                continue
                            row["survival_months"] = outcome.survival_text
                            row["censorship"] = str(outcome.censorship)
                            writer.writerow(row)
                            written_rows += 1
                            written_cases.add(case_id)
        expected_cases = {
            patient_id
            for patient_id, outcome in labels.items()
            if include_test or outcome.split != "test"
        }
        # 这里只要求写入官方源中实际存在的 labels 病人；缺失者由 audit 明示。
        _, _, official_cases = collect_official_outcomes(source)
        expected_cases &= official_cases
        if written_cases != expected_cases:
            raise ValueError(
                f"{library}/{cancer} 写入患者集合不一致: "
                f"缺失={sorted(expected_cases - written_cases)}, 额外={sorted(written_cases - expected_cases)}"
            )
        verify_adapted_zip(
            source,
            tmp,
            labels,
            include_test=include_test,
            expected_cases=expected_cases,
        )
        tmp.replace(target)
        return written_rows, written_cases
    finally:
        if tmp.exists():
            tmp.unlink()


def verify_adapted_zip(
    source: Path,
    adapted: Path,
    labels: dict[str, Outcome],
    *,
    include_test: bool,
    expected_cases: set[str],
) -> None:
    seen_cases: set[str] = set()
    with open_zip_reader(source) as source_reader, open_zip_reader(adapted) as adapted_reader:
        if source_reader.fieldnames != adapted_reader.fieldnames:
            raise ValueError(f"{adapted} 的列名或列顺序与官方源不一致")
        adapted_iter = iter(adapted_reader)
        for source_row in source_reader:
            case_id = (source_row.get("case_id") or "").strip().upper()
            outcome = labels.get(case_id)
            if outcome is None or (not include_test and outcome.split == "test"):
                continue
            try:
                output_row = next(adapted_iter)
            except StopIteration as exc:
                raise ValueError(f"{adapted} 比预期更早结束") from exc
            for column in source_reader.fieldnames or []:
                if column == "survival_months":
                    if parse_decimal(
                        output_row[column], field=column, context=f"{adapted}:{case_id}"
                    ) != outcome.survival:
                        raise ValueError(f"{adapted} 的 {case_id} survival_months 未按 labels 覆盖")
                elif column == "censorship":
                    if parse_censorship(output_row[column], context=f"{adapted}:{case_id}") != outcome.censorship:
                        raise ValueError(f"{adapted} 的 {case_id} censorship 未按 labels 覆盖")
                elif output_row.get(column) != source_row.get(column):
                    raise ValueError(f"{adapted} 的非结局列 {column!r} 被改动（case_id={case_id}）")
            seen_cases.add(case_id)
        try:
            extra = next(adapted_iter)
        except StopIteration:
            extra = None
        if extra is not None:
            raise ValueError(f"{adapted} 含官方过滤序列之外的额外行: {extra.get('case_id')}")
    if seen_cases != expected_cases:
        raise ValueError(
            f"{adapted} 硬校验患者集合不一致: "
            f"缺失={sorted(expected_cases - seen_cases)}, 额外={sorted(seen_cases - expected_cases)}"
        )


def audit_rows(
    library: str,
    cancer: str,
    labels: dict[str, Outcome],
    official: dict[str, tuple[Decimal, int]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for patient_id in sorted(set(labels) | set(official)):
        outcome = labels.get(patient_id)
        old = official.get(patient_id)
        if outcome is None:
            status = "extra_official"
        elif old is None:
            status = "missing_official"
        else:
            status = "matched"
        old_survival = old[0] if old else None
        old_censorship = old[1] if old else None
        new_survival = outcome.survival if outcome else None
        scaled_expected = old_survival * SCALE_FACTOR if old_survival is not None else None
        scaled_residual = (
            new_survival - scaled_expected
            if new_survival is not None and scaled_expected is not None
            else None
        )
        direct_difference = (
            new_survival - old_survival
            if new_survival is not None and old_survival is not None
            else None
        )
        rows.append(
            {
                "library": library,
                "cancer": cancer,
                "patient_id": patient_id,
                "status": status,
                "split": outcome.split if outcome else "",
                "old_survival_months": decimal_text(old_survival),
                "new_survival_months": decimal_text(new_survival),
                "direct_difference": decimal_text(direct_difference),
                "scaled_expected_30_to_30_44": decimal_text(scaled_expected),
                "scaled_residual": decimal_text(scaled_residual),
                "scaled_match": (
                    str(abs(scaled_residual) <= SCALE_TOLERANCE).lower()
                    if scaled_residual is not None
                    else ""
                ),
                "old_censorship": "" if old_censorship is None else str(old_censorship),
                "new_censorship": "" if outcome is None else str(outcome.censorship),
                "censorship_changed": (
                    str(old_censorship != outcome.censorship).lower()
                    if old_censorship is not None and outcome is not None
                    else ""
                ),
            }
        )
    return rows


def write_outcome_table(path: Path, outcomes: list[Outcome]) -> None:
    rows = (
        {
            "patient_id": outcome.patient_id,
            "survival_months": outcome.survival_text,
            "censorship": str(outcome.censorship),
        }
        for outcome in outcomes
    )
    write_csv_atomic(path, ["patient_id", "survival_months", "censorship"], rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True, type=Path, help="labels_424.csv")
    parser.add_argument("--out", type=Path, default=Path("scratch"), help="输出根目录，默认 scratch/")
    parser.add_argument("--repo-root", type=Path, default=repository_root(), help=argparse.SUPPRESS)
    parser.add_argument("--libs", nargs="+", choices=SUPPORTED_LIBS, default=list(SUPPORTED_LIBS))
    parser.add_argument("--cancers", nargs="+", default=list(SUPPORTED_CANCERS))
    args = parser.parse_args()

    cancers = [cancer.strip().upper() for cancer in args.cancers]
    if len(cancers) != len(set(cancers)):
        parser.error("--cancers 不得重复")
    invalid = sorted(set(cancers) - set(SUPPORTED_CANCERS))
    if invalid:
        parser.error(f"不支持的癌种: {invalid}")
    if not args.labels.is_file():
        parser.error(f"找不到 labels 文件: {args.labels}")

    try:
        outcomes, by_cancer = read_labels(args.labels)
        for cancer in cancers:
            if not by_cancer[cancer]:
                raise ValueError(f"labels 中没有 {cancer} 患者")
        args.out.mkdir(parents=True, exist_ok=True)
        write_outcome_table(args.out / "outcome_table.csv", outcomes)

        audit_by_cancer: dict[str, list[dict[str, str]]] = {cancer: [] for cancer in cancers}
        summaries: list[dict[str, object]] = []
        for library in args.libs:
            for cancer in cancers:
                source = source_zip(args.repo_root, library, cancer)
                _, official, official_cases = collect_official_outcomes(source)
                labels_for_cancer = by_cancer[cancer]
                stem = f"{library}_tcga_{cancer}_adapted"
                full_path = args.out / "adapted_csv" / f"{stem}.csv.zip"
                trainval_path = args.out / "adapted_csv" / f"{stem}_trainval.csv.zip"
                full_rows, full_cases = write_adapted_zip(
                    source,
                    full_path,
                    library,
                    cancer,
                    labels_for_cancer,
                    include_test=True,
                )
                trainval_rows, trainval_cases = write_adapted_zip(
                    source,
                    trainval_path,
                    library,
                    cancer,
                    labels_for_cancer,
                    include_test=False,
                )
                audit = audit_rows(library, cancer, labels_for_cancer, official)
                audit_by_cancer[cancer].extend(audit)
                matched = [row for row in audit if row["status"] == "matched"]
                scaled_matches = sum(row["scaled_match"] == "true" for row in matched)
                exact_matches = sum(row["direct_difference"] in {"0", "0.0"} for row in matched)
                missing = sorted(set(labels_for_cancer) - official_cases)
                extra = sorted(official_cases - set(labels_for_cancer))
                summary = {
                    "library": library,
                    "cancer": cancer,
                    "labels": len(labels_for_cancer),
                    "matched": len(full_cases),
                    "missing_official": len(missing),
                    "extra_official": len(extra),
                    "slide_rows": full_rows,
                    "trainval_cases": len(trainval_cases),
                    "trainval_slide_rows": trainval_rows,
                    "exact_old_new": exact_matches,
                    "scaled_30_to_30_44_matches": scaled_matches,
                    "scaled_match_rate": scaled_matches / len(matched) if matched else math.nan,
                    "full_csv": str(full_path),
                    "trainval_csv": str(trainval_path),
                }
                summaries.append(summary)
                print(
                    f"[{library} {cancer}] labels={len(labels_for_cancer)} matched={len(full_cases)} "
                    f"missing={len(missing)} extra_official={len(extra)} slide_rows={full_rows} "
                    f"trainval_cases={len(trainval_cases)} exact={exact_matches}/{len(matched)} "
                    f"scaled_30_to_30.44={scaled_matches}/{len(matched)}"
                )

        audit_fields = [
            "library", "cancer", "patient_id", "status", "split",
            "old_survival_months", "new_survival_months", "direct_difference",
            "scaled_expected_30_to_30_44", "scaled_residual", "scaled_match",
            "old_censorship", "new_censorship", "censorship_changed",
        ]
        for cancer in cancers:
            audit_path = args.out / f"outcome_audit_{cancer}.csv"
            write_csv_atomic(audit_path, audit_fields, iter(audit_by_cancer[cancer]))
            print(f"[{cancer}] 审计文件: {audit_path}")
        print(json.dumps({"status": "pass", "summaries": summaries}, ensure_ascii=False, allow_nan=False))
        return 0
    except (FileNotFoundError, ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
