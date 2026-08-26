#!/usr/bin/env python3
"""把 labels_424.csv 的 4:2:4 划分转换为 MCAT/PORPOISE 的 train/val 两列。"""
from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path


SUPPORTED_CANCERS = {"BLCA", "BRCA", "LUAD", "LGG", "UCEC"}
LIBRARY_DIRS = {"MCAT": "dataset_csv", "PORPOISE": "datasets_csv"}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def dataset_zip(lib: str, cancer: str) -> Path:
    """返回库内对应癌种的官方 CSV；LGG 复用合并的 gbmlgg 队列。"""
    library_cancer = "gbmlgg" if cancer == "LGG" else cancer.lower()
    path = repository_root() / "baselines" / lib / LIBRARY_DIRS[lib] / f"tcga_{library_cancer}_all_clean.csv.zip"
    if not path.is_file():
        raise FileNotFoundError(f"找不到 {lib} 的数据集 CSV: {path}")
    return path


def read_case_ids(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"{path} 应恰有一个 CSV 成员，实际为 {names}")
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
    # 两个 baseline 都在每个 epoch 消费 val 并以其作最终报告，故 train 合并 our train+valid，val 放 our test。
    train = kept["train"] + kept["valid"]
    val = kept["test"]
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lib", required=True, choices=sorted(LIBRARY_DIRS), help="MCAT 或 PORPOISE")
    parser.add_argument("--cancer", required=True, help="BLCA/BRCA/LUAD/LGG/UCEC")
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    cancer = args.cancer.strip().upper()
    if cancer not in SUPPORTED_CANCERS:
        parser.error(f"不支持的癌种 {args.cancer!r}；仅支持 {', '.join(sorted(SUPPORTED_CANCERS))}")
    if not args.labels.is_file():
        parser.error(f"找不到 labels 文件: {args.labels}")

    try:
        args.out.mkdir(parents=True, exist_ok=True)
        source_zip = dataset_zip(args.lib, cancer)
        print(f"库 CSV: {source_zip}")
        library_cases = read_case_ids(source_zip)
        groups = read_labels(args.labels, cancer)
        kept = intersect_and_write_missing(args.out, cancer, groups, library_cases)
        split_path = write_splits(args.out, kept)
        print(f"已写入 splits: {split_path}")
        print("映射: train=train+valid，val=test（val 被 baseline 的逐 epoch 验证消费）")
        return 0
    except (FileNotFoundError, ValueError, zipfile.BadZipFile) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
