#!/usr/bin/env python3
"""把 labels_424.csv 的 train/valid 划分转换为 MCAT/PORPOISE 的 train/val 两列。"""
from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path


SUPPORTED_CANCERS = {"BLCA", "BRCA", "LUAD", "LGG", "UCEC"}
SUPPORTED_LIBRARIES = {"MCAT", "PORPOISE"}


def read_case_ids(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name and not name.endswith("/")]
        if len(names) != 1:
            raise ValueError(f"{path} 应恰有一个非目录 CSV 成员，实际为 {names}")
        with archive.open(names[0]) as raw:
            reader = csv.DictReader((line.decode("utf-8-sig") for line in raw))
            if not reader.fieldnames or "case_id" not in reader.fieldnames:
                raise ValueError(f"{path} 缺少 case_id 列")
            return {row["case_id"].strip() for row in reader if row.get("case_id", "").strip()}


def read_labels(path: Path, cancer: str) -> dict[str, list[str]]:
    required = {"patient_id", "cancer_type", "split"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"标签 CSV 必须包含列: {', '.join(sorted(required))}")
        groups = {"train": [], "valid": [], "test": []}
        patient_splits: dict[str, str] = {}
        for row in reader:
            if row["cancer_type"].strip().upper() != cancer:
                continue
            split = row["split"].strip().lower()
            patient_id = row["patient_id"].strip()
            if split not in groups:
                raise ValueError(f"{cancer} 存在无效 split: {split!r}")
            if not patient_id:
                raise ValueError(f"{cancer} 存在空 patient_id")
            previous_split = patient_splits.get(patient_id)
            if previous_split == split:
                raise ValueError(f"{cancer} 存在重复 patient_id: {patient_id}（split={split}）")
            if previous_split is not None:
                raise ValueError(
                    f"{cancer} patient_id 跨 split 重叠: {patient_id}（{previous_split} 与 {split}）"
                )
            patient_splits[patient_id] = split
            groups[split].append(patient_id)
    if not any(groups.values()):
        raise ValueError(f"标签 CSV 中没有 cancer_type == {cancer} 的病人")
    return groups


def intersect_and_write_missing(out_dir: Path, cancer: str, groups: dict[str, list[str]], library_cases: set[str]) -> dict[str, list[str]]:
    kept: dict[str, list[str]] = {}
    for split in ("train", "valid", "test"):
        requested = groups[split]
        requested_set = set(requested)
        missing = sorted(requested_set - library_cases)
        intersection = [patient_id for patient_id in requested if patient_id in library_cases]
        kept[split] = intersection
        missing_path = out_dir / f"missing_{cancer}_{split}.csv"
        with missing_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["patient_id"])
            writer.writerows([[patient_id] for patient_id in missing])
        print(
            f"{cancer} {split}: 我们={len(requested_set)} | 库={len(library_cases)} | "
            f"交集={len(requested_set & library_cases)} | 缺失={len(missing)} | 缺失清单={missing_path}"
        )
    return kept


def write_splits(out_dir: Path, kept: dict[str, list[str]]) -> Path:
    # Round 2 冻结 test：训练列只放 our train，验证列只放 our valid。
    train = kept["train"]
    val = kept["valid"]
    split_path = out_dir / "splits_0.csv"
    with split_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["train", "val"])
        writer.writeheader()
        for index in range(max(len(train), len(val))):
            writer.writerow({
                "train": train[index] if index < len(train) else "",
                "val": val[index] if index < len(val) else "",
            })
    return split_path


def default_training_csv(adapted_csv: Path) -> Path:
    suffix = "_adapted.csv.zip"
    if not adapted_csv.name.endswith(suffix):
        raise ValueError(
            "未传 --training-csv，且 --adapted-csv 文件名不以 "
            f"{suffix!r} 结尾，无法推导 trainval 产物"
        )
    return adapted_csv.with_name(
        f"{adapted_csv.name[:-len(suffix)]}_adapted_trainval.csv.zip"
    )


def validate_adapted_contract(
    groups: dict[str, list[str]],
    adapted_cases: set[str],
    training_cases: set[str],
) -> None:
    label_cases = {patient_id for split in groups.values() for patient_id in split}
    unknown = sorted(adapted_cases - label_cases)
    if unknown:
        raise ValueError(f"完整 adapted CSV 含 labels 之外的患者: {unknown[:10]}")
    test_cases = set(groups["test"])
    leaked_test = sorted(training_cases & test_cases)
    if leaked_test:
        raise ValueError(f"训练 CSV 含 test 患者，存在冻结测试泄漏: {leaked_test[:10]}")
    expected_training = adapted_cases & (set(groups["train"]) | set(groups["valid"]))
    missing = sorted(expected_training - training_cases)
    extra = sorted(training_cases - expected_training)
    if missing or extra:
        raise ValueError(
            "训练 CSV 患者集合必须精确等于完整 adapted CSV 中的 train∪valid；"
            f"缺失={missing[:10]}，额外={extra[:10]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", required=True, choices=sorted(SUPPORTED_LIBRARIES), help="MCAT 或 PORPOISE")
    parser.add_argument("--cancer", required=True, help="BLCA/BRCA/LUAD/LGG/UCEC")
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument(
        "--adapted-csv",
        required=True,
        type=Path,
        help="build_outcome_table.py 生成的完整 adapted CSV（用于三 split 交集审计）",
    )
    parser.add_argument(
        "--training-csv",
        type=Path,
        help="排除 test 的训练 CSV；默认由 --adapted-csv 文件名推导 *_adapted_trainval.csv.zip",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    cancer = args.cancer.strip().upper()
    if cancer not in SUPPORTED_CANCERS:
        parser.error(f"不支持的癌种 {args.cancer!r}；仅支持 {', '.join(sorted(SUPPORTED_CANCERS))}")
    if not args.labels.is_file():
        parser.error(f"找不到 labels 文件: {args.labels}")
    if not args.adapted_csv.is_file():
        parser.error(f"找不到完整 adapted CSV: {args.adapted_csv}")

    try:
        args.out.mkdir(parents=True, exist_ok=True)
        groups = read_labels(args.labels, cancer)
        training_csv = args.training_csv or default_training_csv(args.adapted_csv)
        if not training_csv.is_file():
            raise FileNotFoundError(f"找不到排除 test 的训练 CSV: {training_csv}")
        print(f"完整 adapted CSV: {args.adapted_csv}")
        print(f"训练期 trainval CSV: {training_csv}")
        adapted_cases = read_case_ids(args.adapted_csv)
        training_cases = read_case_ids(training_csv)
        validate_adapted_contract(groups, adapted_cases, training_cases)
        kept = intersect_and_write_missing(args.out, cancer, groups, adapted_cases)
        split_path = write_splits(args.out, kept)
        print(f"已写入 splits: {split_path}")
        print(
            f"映射: train=our train ({len(kept['train'])})，"
            f"val=our valid ({len(kept['valid'])})；our test ({len(kept['test'])}) 未写入训练 split"
        )
        return 0
    except (FileNotFoundError, ValueError, zipfile.BadZipFile) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
