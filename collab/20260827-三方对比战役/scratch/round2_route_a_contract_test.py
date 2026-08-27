#!/usr/bin/env python3
"""Round 2 路 A 的端到端合成契约测试。"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
ADAPTERS = TASK_DIR / "adapters"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_zip_csv(path: Path, member: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", newline="", encoding="utf-8", suffix=".csv", dir=path.parent, delete=False
    ) as handle:
        tmp_csv = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(tmp_csv, arcname=member)
    finally:
        tmp_csv.unlink(missing_ok=True)


def read_zip_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise AssertionError(f"ZIP 成员数错误: {members}")
        with archive.open(members[0]) as raw:
            lines = (line.decode("utf-8-sig") for line in raw)
            reader = csv.DictReader(lines)
            return list(reader.fieldnames or []), list(reader)


class RouteARound2ContractTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="route_a_round2_", dir=TASK_DIR / "scratch")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.out = self.root / "out"
        self.labels = self.root / "labels.csv"
        label_rows = [
            {"patient_id": "TCGA-AA-0001", "cancer_type": "BLCA", "split": "train", "survival_months": "10", "censorship": "0"},
            {"patient_id": "TCGA-AA-0002", "cancer_type": "BLCA", "split": "valid", "survival_months": "20.5", "censorship": "1"},
            {"patient_id": "TCGA-AA-0003", "cancer_type": "BLCA", "split": "test", "survival_months": "31", "censorship": "0"},
        ]
        write_csv(
            self.labels,
            ["patient_id", "cancer_type", "split", "survival_months", "censorship"],
            label_rows,
        )

        fields = [
            "case_id", "slide_id", "site", "survival_months", "censorship", "gene_rnaseq"
        ]
        rows = [
            {"case_id": "TCGA-AA-0001", "slide_id": "TCGA-AA-0001-01.svs", "site": "A", "survival_months": "9.85", "censorship": "0", "gene_rnaseq": "1.1"},
            {"case_id": "TCGA-AA-0001", "slide_id": "TCGA-AA-0001-02.svs", "site": "A", "survival_months": "9.85", "censorship": "0", "gene_rnaseq": "1.2"},
            {"case_id": "TCGA-AA-0002", "slide_id": "TCGA-AA-0002-01.svs", "site": "B", "survival_months": "20.21", "censorship": "1", "gene_rnaseq": "2.1"},
            {"case_id": "TCGA-AA-0003", "slide_id": "TCGA-AA-0003-01.svs", "site": "C", "survival_months": "30", "censorship": "0", "gene_rnaseq": "3.1"},
            {"case_id": "TCGA-AA-9999", "slide_id": "TCGA-AA-9999-01.svs", "site": "X", "survival_months": "99", "censorship": "1", "gene_rnaseq": "9.9"},
        ]
        write_zip_csv(
            self.repo / "baselines/MCAT/dataset_csv/tcga_blca_all_clean.csv.zip",
            "tcga_blca_all_clean.csv",
            fields,
            rows,
        )
        # 模拟 PORPOISE mutsig 的误导性内部成员名：后缀是 .csv.zip，但内容是 CSV。
        write_zip_csv(
            self.repo / "baselines/PORPOISE/datasets_csv_mutsig/tcga_blca_all_clean.csv.zip",
            "./tcga_blca_all_clean.csv.zip",
            fields,
            rows,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, script: str, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(ADAPTERS / script), *map(str, args)],
            cwd=TASK_DIR,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            expect,
            msg=f"command failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return completed

    def test_build_split_and_eval_dry_run_contract(self) -> None:
        self.run_cli(
            "build_outcome_table.py",
            "--labels", self.labels,
            "--out", self.out,
            "--repo-root", self.repo,
            "--libs", "MCAT", "PORPOISE",
            "--cancers", "BLCA",
        )

        self.assertEqual(
            (self.out / "outcome_table.csv").read_text(encoding="utf-8").splitlines()[0],
            "patient_id,survival_months,censorship",
        )
        full = self.out / "adapted_csv/MCAT_tcga_BLCA_adapted.csv.zip"
        trainval = self.out / "adapted_csv/MCAT_tcga_BLCA_adapted_trainval.csv.zip"
        porpoise = self.out / "adapted_csv/PORPOISE_tcga_BLCA_adapted.csv.zip"
        self.assertTrue(full.is_file())
        self.assertTrue(trainval.is_file())
        self.assertTrue(porpoise.is_file())
        self.assertTrue((self.out / "outcome_audit_BLCA.csv").is_file())

        fields, rows = read_zip_rows(full)
        self.assertEqual(
            fields,
            ["case_id", "slide_id", "site", "survival_months", "censorship", "gene_rnaseq"],
        )
        self.assertEqual(len(rows), 4)  # 保留双切片，过滤非 labels 病人。
        by_case = {row["case_id"]: row for row in rows}
        self.assertEqual(by_case["TCGA-AA-0001"]["survival_months"], "10")
        self.assertEqual(by_case["TCGA-AA-0002"]["survival_months"], "20.5")
        self.assertEqual(by_case["TCGA-AA-0003"]["survival_months"], "31")
        self.assertEqual(by_case["TCGA-AA-0003"]["gene_rnaseq"], "3.1")

        _, trainval_rows = read_zip_rows(trainval)
        self.assertEqual({row["case_id"] for row in trainval_rows}, {"TCGA-AA-0001", "TCGA-AA-0002"})

        split_out = self.root / "splits"
        self.run_cli(
            "make_splits.py",
            "--lib", "MCAT",
            "--cancer", "BLCA",
            "--labels", self.labels,
            "--adapted-csv", full,
            "--training-csv", trainval,
            "--out", split_out,
        )
        with (split_out / "splits_0.csv").open(newline="", encoding="utf-8") as handle:
            split_rows = list(csv.DictReader(handle))
        self.assertEqual([row["train"] for row in split_rows if row["train"]], ["TCGA-AA-0001"])
        self.assertEqual([row["val"] for row in split_rows if row["val"]], ["TCGA-AA-0002"])
        self.assertNotIn("TCGA-AA-0003", {value for row in split_rows for value in row.values()})

        dry = self.run_cli(
            "eval_frozen_test.py",
            "--lib", "MCAT",
            "--cancer", "BLCA",
            "--labels", self.labels,
            "--adapted-csv", full,
            "--training-csv", trainval,
            "--split-csv", split_out / "splits_0.csv",
            "--dry-run",
        )
        payload = json.loads(dry.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["status"], "dry_run_pass")
        self.assertEqual(payload["n_test"], 1)
        self.assertTrue(payload["forward_skipped"])
        self.assertIsNone(payload["c_index"])

        bad = self.run_cli(
            "make_splits.py",
            "--lib", "MCAT",
            "--cancer", "BLCA",
            "--labels", self.labels,
            "--adapted-csv", full,
            "--training-csv", full,
            "--out", self.root / "bad_splits",
            expect=2,
        )
        self.assertIn("test", bad.stderr.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
