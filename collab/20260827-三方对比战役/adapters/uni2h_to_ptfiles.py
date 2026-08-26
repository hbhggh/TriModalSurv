#!/usr/bin/env python3
"""逐成员转换 UNI2-h TCGA-<C>.tar.gz 的 [1,N,1536] h5 为 pt_files/*.pt。"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


PATIENT_RE = re.compile(r"^(TCGA-[A-Za-z0-9]{2}-[A-Za-z0-9]{4})")


def require_dependencies():
    try:
        import h5py
        import torch
    except ImportError as exc:
        raise RuntimeError("此脚本需要现有环境中的 h5py 和 torch；请使用已配置的训练环境运行。") from exc
    return h5py, torch


def slide_id_from_name(name: str) -> str:
    """仅去掉 .h5，保留 TCGA 文件名中点号后的 UUID，以匹配库 CSV 的 slide_id。"""
    basename = Path(name).name
    if not basename.lower().endswith(".h5"):
        raise ValueError(f"不是 .h5 文件: {name}")
    return basename[:-3]


def patient_id_from_slide(slide_id: str) -> str:
    match = PATIENT_RE.match(slide_id)
    if not match:
        raise ValueError(f"无法从切片名解析 TCGA 病人 ID: {slide_id}")
    return match.group(1)


def load_feature_tensor(h5_path: Path, source_name: str):
    h5py, torch = require_dependencies()
    with h5py.File(h5_path, "r") as handle:
        if "features" not in handle:
            raise ValueError(f"{source_name} 缺少 features 数据集")
        features = handle["features"][:]
    if features.ndim != 3 or features.shape[0] != 1 or features.shape[2] != 1536:
        raise ValueError(
            f"{source_name} 的 features 必须为 [1, N, 1536]，实际为 {tuple(features.shape)}"
        )
    if features.shape[1] < 1:
        raise ValueError(f"{source_name} 的 N 必须大于 0，实际为 {features.shape[1]}")
    return torch.as_tensor(features[0], dtype=torch.float32)


def iter_directory_h5(src: Path):
    for h5_path in sorted(src.rglob("*.h5")):
        yield h5_path.name, h5_path, None


def convert(src: Path, out: Path, tmp_dir: Path | None, overwrite: bool) -> tuple[int, set[str], set[tuple[int, int]]]:
    _, torch = require_dependencies()
    if not src.exists():
        raise FileNotFoundError(f"找不到输入: {src}")
    output_dir = out / "pt_files"
    output_dir.mkdir(parents=True, exist_ok=True)
    if tmp_dir is not None:
        tmp_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    patients: set[str] = set()
    dimensions: set[tuple[int, int]] = set()
    seen_slide_ids: set[str] = set()

    def save_one(source_name: str, h5_path: Path) -> None:
        nonlocal written
        slide_id = slide_id_from_name(source_name)
        patient_id = patient_id_from_slide(slide_id)
        if slide_id in seen_slide_ids:
            raise ValueError(f"同一次输入中存在重复 slide_id: {slide_id}")
        seen_slide_ids.add(slide_id)
        tensor = load_feature_tensor(h5_path, source_name)
        destination = output_dir / f"{slide_id}.pt"
        if destination.exists() and not overwrite:
            raise FileExistsError(f"输出已存在（如需覆盖请加 --overwrite）: {destination}")
        torch.save(tensor, destination)
        written += 1
        patients.add(patient_id)
        dimensions.add(tuple(tensor.shape))

    if src.is_dir():
        for source_name, h5_path, _ in iter_directory_h5(src):
            save_one(source_name, h5_path)
    elif tarfile.is_tarfile(src):
        with tarfile.open(src, "r:*") as archive:
            for member in archive:
                if not member.isfile() or not member.name.lower().endswith(".h5"):
                    continue
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"无法读取 tar 成员: {member.name}")
                temporary_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        suffix=".h5", dir=str(tmp_dir) if tmp_dir else None, delete=False
                    ) as temporary:
                        temporary_path = Path(temporary.name)
                        shutil.copyfileobj(source, temporary)
                    save_one(member.name, temporary_path)
                finally:
                    try:
                        source.close()
                    finally:
                        if temporary_path is not None:
                            temporary_path.unlink(missing_ok=True)
    else:
        raise ValueError(f"输入必须是 h5 目录或 tar/tar.gz: {src}")
    return written, patients, dimensions


def run_selftest() -> int:
    h5py, _ = require_dependencies()
    import numpy as np

    with tempfile.TemporaryDirectory(prefix="uni2h_to_ptfiles_selftest_") as temp:
        temp_path = Path(temp)
        source_h5 = temp_path / "TCGA-AB-1234-01Z-00-DX1.12345678-1234-1234-1234-123456789ABC.h5"
        with h5py.File(source_h5, "w") as handle:
            handle.create_dataset("features", data=np.zeros((1, 50, 1536), dtype=np.float32))
        archive_path = temp_path / "TCGA-BLCA.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(source_h5, arcname=f"nested/{source_h5.name}")
        temp_members = temp_path / "temporary_members"
        written, patients, dimensions = convert(archive_path, temp_path / "out", temp_members, overwrite=False)
        if written != 1 or len(patients) != 1 or dimensions != {(50, 1536)} or list(temp_members.iterdir()):
            raise AssertionError("selftest 自检失败")
        print("SELFTEST PASS: [1, 50, 1536] -> FloatTensor [50, 1536]；临时成员已清理")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, help="TCGA-<C>.tar.gz 或包含 h5 的目录")
    parser.add_argument("--cancer", help="癌种代码，仅用于运行记录")
    parser.add_argument("--out", type=Path, help="输出根目录；结果写入 <out>/pt_files/")
    parser.add_argument("--tmp-dir", type=Path, help="逐成员临时 h5 的目录；每个成员读取后立即删除")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--selftest", action="store_true", help="生成合成 [1,50,1536] h5 并验证转换")
    args = parser.parse_args()

    try:
        if args.selftest:
            return run_selftest()
        if args.src is None or args.out is None or not args.cancer:
            parser.error("普通转换必须提供 --src、--cancer、--out")
        written, patients, dimensions = convert(args.src, args.out, args.tmp_dir, args.overwrite)
        dimension_text = ", ".join(f"[{n}, {d}]" for n, d in sorted(dimensions)) or "无"
        print(f"癌种: {args.cancer}")
        print(f"切片数: {written}")
        print(f"病人数: {len(patients)}")
        print(f"维度自检: {dimension_text}（FloatTensor）")
        print(f"输出目录: {args.out / 'pt_files'}")
        return 0
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError, tarfile.TarError, OSError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
