#!/usr/bin/env python3
"""eval_frozen_test.py 的黑盒契约测试。"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
SCRIPT = TASK_DIR / "adapters" / "eval_frozen_test.py"
WORK_DIR = TASK_DIR / "scratch" / "e_eval_frozen_contract"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_zip_csv(path: Path, rows: list[dict[str, object]]) -> None:
    csv_path = path.with_suffix("")
    write_csv(csv_path, list(rows[0]), rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(csv_path, arcname=csv_path.name)
    csv_path.unlink()


def parse_result(stdout: str) -> dict[str, object]:
    prefix = "ASSERT_BINS_JSON="
    matches = [line[len(prefix) :] for line in stdout.splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise AssertionError(f"未找到唯一 {prefix} 行:\n{stdout}")
    return json.loads(matches[0])


class AssertBinsContractTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        WORK_DIR.mkdir(parents=True)
        self.labels = WORK_DIR / "labels.csv"
        self.full = WORK_DIR / "full.csv.zip"
        self.trainval = WORK_DIR / "trainval.csv.zip"
        self.leaky_trainval = WORK_DIR / "trainval_leaky.csv.zip"

        patient_ids = [f"TCGA-AA-{index:04d}" for index in range(1, 11)]
        splits = ["train"] * 4 + ["valid"] * 4 + ["test"] * 2
        survival = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
        label_rows = [
            {
                "patient_id": patient_id,
                "cancer_type": "BLCA",
                "split": split,
                "survival_months": months,
                "censorship": 0,
            }
            for patient_id, split, months in zip(patient_ids, splits, survival)
        ]
        write_csv(self.labels, list(label_rows[0]), label_rows)

        full_rows = [
            {
                "case_id": patient_id,
                "slide_id": f"{patient_id}-01Z-00-DX1.svs",
                "survival_months": months,
                "censorship": 0,
                "age": 60,
                "site": "synthetic",
                "is_female": 0,
                "oncotree_code": "BLCA",
                "train": 0,
                "GENE_mut": float(index),
            }
            for index, (patient_id, months) in enumerate(zip(patient_ids, survival), start=1)
        ]
        write_zip_csv(self.full, full_rows)
        write_zip_csv(self.trainval, full_rows[:8])
        write_zip_csv(self.leaky_trainval, full_rows[:9])

    def run_assert(
        self, trainval: Path, full: Path | None = None, labels: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            "--assert-bins",
            "--lib",
            "MCAT",
            "--cancer",
            "BLCA",
            "--labels",
            str(labels or self.labels),
            "--adapted-trainval-csv",
            str(trainval),
            "--adapted-full-csv",
            str(full or self.full),
        ]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(command, cwd=TASK_DIR, env=env, text=True, capture_output=True)

    def test_assert_bins_uses_only_trainval_uncensored_patients(self) -> None:
        first = self.run_assert(self.trainval)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        first_result = parse_result(first.stdout)
        self.assertEqual(first_result["status"], "PASS")
        self.assertEqual(first_result["n_trainval"], 8)
        self.assertEqual(first_result["n_test"], 2)
        self.assertEqual(first_result["n_bin_source_uncensored"], 8)

        changed_rows: list[dict[str, object]] = []
        with zipfile.ZipFile(self.full) as archive:
            member = archive.namelist()[0]
            with archive.open(member) as raw:
                reader = csv.DictReader(line.decode("utf-8") for line in raw)
                changed_rows = [dict(row) for row in reader]
        changed_rows[-2]["survival_months"] = "4500"
        changed_rows[-1]["survival_months"] = "5000"
        changed_full = WORK_DIR / "full_changed_test.csv.zip"
        write_zip_csv(changed_full, changed_rows)

        with self.labels.open(newline="", encoding="utf-8") as handle:
            changed_labels = [dict(row) for row in csv.DictReader(handle)]
        changed_labels[-2]["survival_months"] = "4500"
        changed_labels[-1]["survival_months"] = "5000"
        changed_labels_path = WORK_DIR / "labels_changed_test.csv"
        write_csv(changed_labels_path, list(changed_labels[0]), changed_labels)

        second = self.run_assert(self.trainval, changed_full, changed_labels_path)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        second_result = parse_result(second.stdout)
        self.assertEqual(first_result["qcut_edges"], second_result["qcut_edges"])
        self.assertEqual(first_result["applied_bins"], second_result["applied_bins"])

    def test_assert_bins_rejects_test_patient_in_trainval(self) -> None:
        completed = self.run_assert(self.leaky_trainval)
        self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("trainval 含 test 病人", completed.stdout + completed.stderr)

    def test_regular_sksurv_import_precedes_vendor_fallback(self) -> None:
        fake_root = WORK_DIR / "fake_normal_dependency"
        package = fake_root / "sksurv"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "metrics.py").write_text(
            "def concordance_index_censored(*args, **kwargs):\n"
            "    return (0.123, 0, 0, 0, 0)\n",
            encoding="utf-8",
        )
        probe = (
            "import importlib.util,sys; "
            f"spec=importlib.util.spec_from_file_location('eval_frozen_probe', {str(SCRIPT)!r}); "
            "module=importlib.util.module_from_spec(spec); "
            "sys.modules[spec.name]=module; "
            "spec.loader.exec_module(module); "
            "fn,source=module._import_concordance_index(); "
            "print(source, fn(None,None,None)[0])"
        )
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(fake_root)
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=TASK_DIR,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(completed.stdout.strip(), "environment 0.123")


if __name__ == "__main__":
    unittest.main(verbosity=2)
