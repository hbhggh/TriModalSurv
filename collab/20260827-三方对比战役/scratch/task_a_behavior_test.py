#!/usr/bin/env python3
"""任务 A 的最小端到端行为测试；仅使用临时目录，不改生产数据。"""
import csv
import io
import importlib.util
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
ADAPTERS = HERE / "adapters"
MAKE_SPLITS = ADAPTERS / "make_splits.py"
UNI2H = ADAPTERS / "uni2h_to_ptfiles.py"


def first_case_ids(zip_path: Path, count: int) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(archive.namelist()[0]) as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle))
            case_ids = list(dict.fromkeys(row["case_id"] for row in reader))
    if len(case_ids) < count:
        raise AssertionError(f"测试 CSV 只有 {len(case_ids)} 个唯一 case_id，至少需要 {count} 个")
    return case_ids[:count]


def first_case_id(zip_path: Path) -> str:
    return first_case_ids(zip_path, 1)[0]


class MakeSplitsBehavior(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(MAKE_SPLITS), *args],
            cwd=HERE,
            capture_output=True,
            text=True,
        )

    def write_labels(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["patient_id", "cancer_type", "split", "survival_months", "censorship"],
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_blca_maps_train_and_valid_to_train_and_writes_missing_lists(self) -> None:
        mcat_csv = REPO / "baselines/MCAT/dataset_csv/tcga_blca_all_clean.csv.zip"
        known_train, known_valid, known_test = first_case_ids(mcat_csv, 3)
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            labels = temp_path / "labels.csv"
            out = temp_path / "out"
            self.write_labels(labels, [
                {"patient_id": known_train, "cancer_type": "BLCA", "split": "train", "survival_months": 1, "censorship": 0},
                {"patient_id": known_valid, "cancer_type": "BLCA", "split": "valid", "survival_months": 2, "censorship": 1},
                {"patient_id": known_test, "cancer_type": "BLCA", "split": "test", "survival_months": 3, "censorship": 0},
                {"patient_id": "TCGA-ZZ-9999", "cancer_type": "BLCA", "split": "test", "survival_months": 4, "censorship": 1},
            ])
            result = self.run_script("--lib", "MCAT", "--cancer", "BLCA", "--labels", str(labels), "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with (out / "splits_0.csv").open(newline="") as handle:
                split_rows = list(csv.DictReader(handle))
            self.assertEqual([row["train"] for row in split_rows if row["train"]], [known_train, known_valid])
            self.assertEqual([row["val"] for row in split_rows if row["val"]], [known_test])
            missing = (out / "missing_BLCA_test.csv").read_text()
            self.assertIn("TCGA-ZZ-9999", missing)
            self.assertIn("交集", result.stdout)

    def test_lgg_uses_gbmlgg_archive_and_filters_lgg_labels(self) -> None:
        lgg_csv = REPO / "baselines/MCAT/dataset_csv/tcga_gbmlgg_all_clean.csv.zip"
        known = first_case_id(lgg_csv)
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            labels = temp_path / "labels.csv"
            out = temp_path / "out"
            self.write_labels(labels, [
                {"patient_id": known, "cancer_type": "LGG", "split": "train", "survival_months": 1, "censorship": 0},
                {"patient_id": "TCGA-ZZ-9999", "cancer_type": "GBM", "split": "test", "survival_months": 2, "censorship": 1},
            ])
            result = self.run_script("--lib", "MCAT", "--cancer", "LGG", "--labels", str(labels), "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("tcga_gbmlgg_all_clean.csv.zip", result.stdout)
            with (out / "splits_0.csv").open(newline="") as handle:
                split_rows = list(csv.DictReader(handle))
            self.assertEqual(split_rows[0]["train"], known)

    def test_invalid_cancer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            labels = Path(temp) / "labels.csv"
            self.write_labels(labels, [])
            result = self.run_script("--lib", "MCAT", "--cancer", "KIRC", "--labels", str(labels), "--out", str(Path(temp) / "out"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("不支持", result.stderr + result.stdout)

    def test_duplicate_patient_within_split_is_rejected(self) -> None:
        mcat_csv = REPO / "baselines/MCAT/dataset_csv/tcga_blca_all_clean.csv.zip"
        known = first_case_id(mcat_csv)
        with tempfile.TemporaryDirectory() as temp:
            labels = Path(temp) / "labels.csv"
            row = {"patient_id": known, "cancer_type": "BLCA", "split": "train", "survival_months": 1, "censorship": 0}
            self.write_labels(labels, [row, row])
            result = self.run_script("--lib", "MCAT", "--cancer", "BLCA", "--labels", str(labels), "--out", str(Path(temp) / "out"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("重复 patient_id", result.stderr + result.stdout)

    def test_patient_overlap_across_splits_is_rejected(self) -> None:
        mcat_csv = REPO / "baselines/MCAT/dataset_csv/tcga_blca_all_clean.csv.zip"
        known = first_case_id(mcat_csv)
        with tempfile.TemporaryDirectory() as temp:
            labels = Path(temp) / "labels.csv"
            self.write_labels(labels, [
                {"patient_id": known, "cancer_type": "BLCA", "split": "train", "survival_months": 1, "censorship": 0},
                {"patient_id": known, "cancer_type": "BLCA", "split": "valid", "survival_months": 1, "censorship": 0},
            ])
            result = self.run_script("--lib", "MCAT", "--cancer", "BLCA", "--labels", str(labels), "--out", str(Path(temp) / "out"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("跨 split", result.stderr + result.stdout)


class Uni2HBehavior(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(UNI2H), *args],
            cwd=HERE,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def require_test_dependencies():
        import h5py
        import numpy as np
        import torch
        return h5py, np, torch

    @staticmethod
    def load_uni2h_module():
        spec = importlib.util.spec_from_file_location("task_a_uni2h", UNI2H)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def write_tar(self, tar_path: Path, entries: list[tuple[str, tuple[int, ...], float]]) -> None:
        h5py, np, _ = self.require_test_dependencies()
        with tarfile.open(tar_path, "w:gz") as archive:
            for index, (slide_id, shape, value) in enumerate(entries):
                h5_path = tar_path.parent / f"source_{index}.h5"
                with h5py.File(h5_path, "w") as handle:
                    handle.create_dataset("features", data=np.full(shape, value, dtype=np.float32))
                archive.add(h5_path, arcname=f"nested/{slide_id}.h5")
                h5_path.unlink()

    def test_tar_h5_is_float_tensor_and_temporary_extraction_is_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            source = temp_path / "TCGA-BLCA.tar.gz"
            slide_id = "TCGA-AB-1234-01Z-00-DX1.195576CF-B739-4BD9-B15B-4A70AE287D3E"
            self.write_tar(source, [(slide_id, (1, 50, 1536), 0.0)])
            out = temp_path / "out"
            tmp_dir = temp_path / "temporary_members"
            tmp_dir.mkdir()
            result = self.run_script("--src", str(source), "--cancer", "BLCA", "--out", str(out), "--tmp-dir", str(tmp_dir))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            _, _, torch = self.require_test_dependencies()
            tensor = torch.load(out / "pt_files" / f"{slide_id}.pt", weights_only=True)
            self.assertEqual(tuple(tensor.shape), (50, 1536))
            self.assertEqual(tensor.dtype, torch.float32)
            self.assertEqual(list(tmp_dir.iterdir()), [])
            self.assertIn("切片数: 1", result.stdout)
            self.assertIn("病人数: 1", result.stdout)
            self.assertIn("[50, 1536]", result.stdout)

    def test_illegal_feature_dimensions_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            source = temp_path / "TCGA-BLCA.tar.gz"
            self.write_tar(source, [("TCGA-AB-1234-01Z-00-DX1", (50, 1536), 0.0)])
            result = self.run_script("--src", str(source), "--cancer", "BLCA", "--out", str(temp_path / "out"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("[1, N, 1536]", result.stderr + result.stdout)

    def test_copy_failure_removes_temporary_member(self) -> None:
        """旧实现会在 copyfileobj 抛错时跳过 unlink；此测试应在旧代码下 RED。"""
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            source = temp_path / "TCGA-BLCA.tar.gz"
            self.write_tar(source, [("TCGA-AB-1234-01Z-00-DX1", (1, 50, 1536), 0.0)])
            tmp_dir = temp_path / "temporary_members"
            tmp_dir.mkdir()
            module = self.load_uni2h_module()
            with mock.patch.object(module.shutil, "copyfileobj", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    module.convert(source, temp_path / "out", tmp_dir, overwrite=False)
            self.assertEqual(list(tmp_dir.iterdir()), [])

    def test_invalid_slide_name_leaves_no_pt_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            source = temp_path / "TCGA-BLCA.tar.gz"
            self.write_tar(source, [("NOT-A-TCGA-SLIDE", (1, 50, 1536), 0.0)])
            out = temp_path / "out"
            result = self.run_script("--src", str(source), "--cancer", "BLCA", "--out", str(out))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("无法从切片名解析", result.stderr + result.stdout)
            self.assertEqual(list((out / "pt_files").glob("*.pt")), [])

    def test_duplicate_slide_id_is_rejected_even_with_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            source = temp_path / "TCGA-BLCA.tar.gz"
            slide_id = "TCGA-AB-1234-01Z-00-DX1.195576CF-B739-4BD9-B15B-4A70AE287D3E"
            self.write_tar(source, [
                (slide_id, (1, 50, 1536), 1.0),
                (slide_id, (1, 50, 1536), 2.0),
            ])
            result = self.run_script(
                "--src", str(source), "--cancer", "BLCA", "--out", str(temp_path / "out"), "--overwrite"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("重复 slide_id", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
