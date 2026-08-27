#!/usr/bin/env python3
"""逐成员转换 UNI2-h TCGA-<C>.tar.gz 的 [1,N,1536] h5 为 pt_files/*.pt。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path


PATIENT_RE = re.compile(r"^(TCGA-[A-Za-z0-9]{2}-[A-Za-z0-9]{4})")
MANIFEST_NAME = "manifest.csv"
MANIFEST_FIELDS = [
    "source_member",
    "slide_id",
    "patient_id",
    "output_file",
    "shape",
    "dtype",
    "sha256",
]


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


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(staging_dir: Path, entries: list[dict[str, str]]) -> None:
    manifest_path = staging_dir / MANIFEST_NAME
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(entries)
        handle.flush()
        os.fsync(handle.fileno())


def load_saved_tensor(path: Path, torch):
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        return torch.load(path, map_location="cpu")


def validate_staging(staging_dir: Path, torch) -> list[dict[str, str]]:
    manifest_path = staging_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(f"staging 缺少 manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MANIFEST_FIELDS:
            raise ValueError(
                f"manifest 字段错误: 期望 {MANIFEST_FIELDS}，实际 {reader.fieldnames}"
            )
        entries = list(reader)
    if not entries:
        raise ValueError("manifest 无成员；written == 0，拒绝发布")

    expected_files: set[str] = set()
    for entry in entries:
        output_file = entry["output_file"]
        if Path(output_file).name != output_file or not output_file.endswith(".pt"):
            raise ValueError(f"manifest 含非法输出文件名: {output_file}")
        if output_file in expected_files:
            raise ValueError(f"manifest 含重复输出文件: {output_file}")
        expected_files.add(output_file)

        output_path = staging_dir / output_file
        if not output_path.is_file():
            raise ValueError(f"manifest 成员不存在: {output_path}")
        actual_checksum = sha256_file(output_path)
        if actual_checksum != entry["sha256"]:
            raise ValueError(
                f"checksum 不一致: {output_file}，manifest={entry['sha256']}，实际={actual_checksum}"
            )

        try:
            expected_shape = tuple(int(value) for value in json.loads(entry["shape"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"manifest shape 非法: {entry['shape']}") from exc
        tensor = load_saved_tensor(output_path, torch)
        if not isinstance(tensor, torch.Tensor):
            raise ValueError(f"输出不是 torch.Tensor: {output_file}")
        if tensor.dtype != torch.float32:
            raise ValueError(f"输出 dtype 必须为 float32: {output_file}，实际 {tensor.dtype}")
        if tuple(tensor.shape) != expected_shape:
            raise ValueError(
                f"输出 shape 与 manifest 不一致: {output_file}，"
                f"manifest={expected_shape}，实际={tuple(tensor.shape)}"
            )
        if tensor.ndim != 2 or tensor.shape[0] < 1 or tensor.shape[1] != 1536:
            raise ValueError(f"输出必须为 [N,1536] 且 N>0: {output_file}，实际 {tuple(tensor.shape)}")
        if entry["dtype"] != "float32":
            raise ValueError(f"manifest dtype 非法: {output_file}，实际 {entry['dtype']}")

    actual_files = {path.name for path in staging_dir.glob("*.pt") if path.is_file()}
    if actual_files != expected_files:
        raise ValueError(
            f"staging 成员集合与 manifest 不一致: manifest={sorted(expected_files)}，"
            f"实际={sorted(actual_files)}"
        )
    unexpected = {
        path.name
        for path in staging_dir.iterdir()
        if path.name != MANIFEST_NAME and path.name not in expected_files
    }
    if unexpected:
        raise ValueError(f"staging 含 manifest 外成员: {sorted(unexpected)}")
    return entries


def publish_staging(staging_dir: Path, output_dir: Path, overwrite: bool) -> None:
    if path_exists(output_dir) and not overwrite:
        raise FileExistsError(f"输出目录已存在（如需整套替换请加 --overwrite）: {output_dir}")

    backup_dir: Path | None = None
    if path_exists(output_dir):
        backup_dir = output_dir.parent / f".pt_files.backup-{uuid.uuid4().hex}"
        os.replace(output_dir, backup_dir)
    try:
        os.replace(staging_dir, output_dir)
    except BaseException:
        if backup_dir is not None and path_exists(backup_dir):
            os.replace(backup_dir, output_dir)
        raise
    if backup_dir is not None:
        remove_path(backup_dir)


def convert(src: Path, out: Path, tmp_dir: Path | None, overwrite: bool) -> tuple[int, set[str], set[tuple[int, int]]]:
    _, torch = require_dependencies()
    if not src.exists():
        raise FileNotFoundError(f"找不到输入: {src}")
    output_dir = out / "pt_files"
    out.mkdir(parents=True, exist_ok=True)
    if path_exists(output_dir) and not overwrite:
        raise FileExistsError(f"输出目录已存在（如需整套替换请加 --overwrite）: {output_dir}")
    if tmp_dir is not None:
        tmp_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=".pt_files.staging-", dir=out))

    written = 0
    patients: set[str] = set()
    dimensions: set[tuple[int, int]] = set()
    seen_slide_ids: set[str] = set()
    manifest_entries: list[dict[str, str]] = []

    def save_one(source_name: str, h5_path: Path) -> None:
        nonlocal written
        slide_id = slide_id_from_name(source_name)
        patient_id = patient_id_from_slide(slide_id)
        if slide_id in seen_slide_ids:
            raise ValueError(f"同一次输入中存在重复 slide_id: {slide_id}")
        seen_slide_ids.add(slide_id)
        tensor = load_feature_tensor(h5_path, source_name)
        destination = staging_dir / f"{slide_id}.pt"
        torch.save(tensor, destination)
        manifest_entries.append(
            {
                "source_member": source_name,
                "slide_id": slide_id,
                "patient_id": patient_id,
                "output_file": destination.name,
                "shape": json.dumps(list(tensor.shape), separators=(",", ":")),
                "dtype": "float32",
                "sha256": sha256_file(destination),
            }
        )
        written += 1
        patients.add(patient_id)
        dimensions.add(tuple(tensor.shape))

    try:
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

        if written == 0:
            raise ValueError("输入中未找到任何 .h5 成员；written == 0，拒绝发布")
        write_manifest(staging_dir, manifest_entries)
        validated_entries = validate_staging(staging_dir, torch)
        if len(validated_entries) != written:
            raise ValueError(
                f"manifest 成员数与 written 不一致: manifest={len(validated_entries)}，written={written}"
            )
        publish_staging(staging_dir, output_dir, overwrite=overwrite)
        return written, patients, dimensions
    finally:
        if path_exists(staging_dir):
            remove_path(staging_dir)


def run_selftest() -> int:
    h5py, torch = require_dependencies()
    import numpy as np

    scratch_root = Path(__file__).resolve().parents[1] / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)

    def write_h5(path: Path, shape: tuple[int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(path, "w") as handle:
            handle.create_dataset("features", data=np.zeros(shape, dtype=np.float32))

    def assert_no_transaction_leftovers(root: Path) -> None:
        leftovers = sorted(
            [*root.glob(".pt_files.staging-*"), *root.glob(".pt_files.backup-*")]
        )
        if leftovers:
            raise AssertionError(f"事务临时目录未清理: {leftovers}")

    with tempfile.TemporaryDirectory(
        prefix="uni2h_to_ptfiles_selftest_", dir=scratch_root
    ) as temp:
        temp_path = Path(temp)
        source_h5 = temp_path / "TCGA-AB-1234-01Z-00-DX1.12345678-1234-1234-1234-123456789ABC.h5"
        write_h5(source_h5, (1, 50, 1536))
        archive_path = temp_path / "TCGA-BLCA.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(source_h5, arcname=f"nested/{source_h5.name}")
        temp_members = temp_path / "temporary_members"
        normal_out = temp_path / "normal_out"
        written, patients, dimensions = convert(
            archive_path, normal_out, temp_members, overwrite=False
        )
        final_tensor = load_saved_tensor(normal_out / "pt_files" / f"{source_h5.stem}.pt", torch)
        manifest_rows = validate_staging(normal_out / "pt_files", torch)
        if (
            written != 1
            or len(patients) != 1
            or dimensions != {(50, 1536)}
            or tuple(final_tensor.shape) != (50, 1536)
            or len(manifest_rows) != 1
            or list(temp_members.iterdir())
        ):
            raise AssertionError("正常事务发布自检失败")
        assert_no_transaction_leftovers(normal_out)
        print(
            "SELFTEST PASS: normal publish + manifest "
            "[1,50,1536] -> FloatTensor [50,1536]；临时成员已清理"
        )

        failing_src = temp_path / "failing_src"
        write_h5(
            failing_src / "TCGA-EF-0001-01Z-00-DX1.11111111-1111-1111-1111-111111111111.h5",
            (1, 3, 1536),
        )
        write_h5(
            failing_src / "TCGA-EF-0002-01Z-00-DX1.22222222-2222-2222-2222-222222222222.h5",
            (1, 3, 1024),
        )
        failing_out = temp_path / "failing_out"
        try:
            convert(failing_src, failing_out, None, overwrite=False)
        except ValueError as exc:
            if "1024" not in str(exc):
                raise AssertionError(f"半途失败未命中第二个非法成员: {exc}") from exc
        else:
            raise AssertionError("半途失败输入应拒绝转换")
        if path_exists(failing_out / "pt_files"):
            raise AssertionError("半途失败后不应留下最终 pt_files")
        assert_no_transaction_leftovers(failing_out)
        print("SELFTEST PASS: mid-conversion failure leaves no final pt_files")

        empty_src = temp_path / "empty_src"
        empty_src.mkdir()
        empty_out = temp_path / "empty_out"
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--src",
                str(empty_src),
                "--cancer",
                "TEST",
                "--out",
                str(empty_out),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode == 0 or "written == 0" not in completed.stdout:
            raise AssertionError(
                f"written == 0 应非零退出，实际 exit={completed.returncode}: {completed.stdout}"
            )
        if path_exists(empty_out / "pt_files"):
            raise AssertionError("written == 0 后不应留下最终 pt_files")
        assert_no_transaction_leftovers(empty_out)
        print(
            f"SELFTEST PASS: written==0 exits {completed.returncode}; "
            f"{completed.stdout.strip()}"
        )

        overwrite_out = temp_path / "overwrite_out"
        old_src = temp_path / "old_src"
        old_h5 = old_src / "TCGA-GH-0001-01Z-00-DX1.33333333-3333-3333-3333-333333333333.h5"
        write_h5(old_h5, (1, 2, 1536))
        convert(old_src, overwrite_out, None, overwrite=False)
        new_src = temp_path / "new_src"
        new_h5 = new_src / "TCGA-IJ-0002-01Z-00-DX1.44444444-4444-4444-4444-444444444444.h5"
        write_h5(new_h5, (1, 4, 1536))
        convert(new_src, overwrite_out, None, overwrite=True)
        final_dir = overwrite_out / "pt_files"
        final_pt_names = sorted(path.name for path in final_dir.glob("*.pt"))
        overwrite_manifest = validate_staging(final_dir, torch)
        if final_pt_names != [f"{new_h5.stem}.pt"]:
            raise AssertionError(f"overwrite 未整套替换: {final_pt_names}")
        if len(overwrite_manifest) != 1 or overwrite_manifest[0]["slide_id"] != new_h5.stem:
            raise AssertionError("overwrite manifest 未整套替换")
        assert_no_transaction_leftovers(overwrite_out)
        print("SELFTEST PASS: --overwrite replaces the whole pt_files set atomically")
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
        print(f"manifest: {args.out / 'pt_files' / MANIFEST_NAME}")
        return 0
    except (
        AssertionError,
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        ValueError,
        tarfile.TarError,
        OSError,
    ) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
