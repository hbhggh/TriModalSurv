#!/usr/bin/env python3
"""MCAT/PORPOISE frozen test 合成全链黑盒测试。"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import torch


TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_DIR.parents[1]
SCRIPT = TASK_DIR / "adapters" / "eval_frozen_test.py"
ASSET_HELPER = TASK_DIR / "scratch" / "e_make_synthetic_frozen_assets.py"
WORK_DIR = TASK_DIR / "scratch" / "e_eval_frozen_synthetic"
VENDOR_DIR = TASK_DIR / "scratch" / "e_sksurv_vendor"


def spread_sample(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    ordered = (
        frame.sort_values("survival_months")
        .drop_duplicates("survival_months", keep="first")
        .reset_index(drop=True)
    )
    if len(ordered) < count:
        raise AssertionError(f"候选病人不足: need={count}, actual={len(ordered)}")
    indices = np.linspace(0, len(ordered) - 1, num=count, dtype=int)
    return ordered.iloc[indices].copy()


def write_zip(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    archive_name = path.name.removesuffix(".zip")
    frame.to_csv(
        path,
        index=False,
        compression={"method": "zip", "archive_name": archive_name},
    )


class FrozenEvaluationIntegrationTest(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        WORK_DIR.mkdir(parents=True)

        labels = pd.read_csv(TASK_DIR / "labels_424.csv")
        labels["cancer_type"] = labels["cancer_type"].str.upper()
        labels["split"] = labels["split"].str.lower()
        blca = labels.loc[(labels["cancer_type"] == "BLCA") & (labels["censorship"] == 0)].copy()
        train = spread_sample(blca.loc[blca["split"] == "train"], 8)
        valid = spread_sample(blca.loc[blca["split"] == "valid"], 4)
        lower = min(train["survival_months"].min(), valid["survival_months"].min())
        upper = max(train["survival_months"].max(), valid["survival_months"].max())
        test_pool = blca.loc[
            (blca["split"] == "test")
            & (blca["survival_months"] >= lower)
            & (blca["survival_months"] <= upper)
        ]
        test = spread_sample(test_pool, 4)
        selected_labels = pd.concat([train, valid, test], ignore_index=True)
        cls.patient_ids = set(selected_labels["patient_id"])
        cls.test_ids = set(test["patient_id"])
        cls.labels_path = WORK_DIR / "labels_synthetic_subset.csv"
        selected_labels.to_csv(cls.labels_path, index=False)

        for lib in ("MCAT", "PORPOISE"):
            source = (
                TASK_DIR
                / "scratch"
                / "r2_outcome"
                / "adapted_csv"
                / f"{lib}_tcga_BLCA_adapted.csv.zip"
            )
            full = pd.read_csv(source, low_memory=False)
            full = full.loc[full["case_id"].isin(cls.patient_ids)].copy()
            if set(full["case_id"]) != cls.patient_ids:
                raise AssertionError(f"{lib} 合成子集病人不完整")
            split_map = selected_labels.set_index("patient_id")["split"]
            trainval = full.loc[full["case_id"].map(split_map).isin(["train", "valid"])].copy()

            lib_dir = WORK_DIR / lib.lower()
            cls._lib_dir(lib).mkdir(parents=True, exist_ok=True)
            write_zip(full, cls._full_csv(lib))
            write_zip(trainval, cls._trainval_csv(lib))

            pt_dir = cls._features_root(lib) / "pt_files"
            pt_dir.mkdir(parents=True)
            test_rows = full.loc[full["case_id"].isin(cls.test_ids)]
            for index, slide_id in enumerate(sorted(test_rows["slide_id"].unique())):
                generator = torch.Generator().manual_seed(1000 + index)
                features = torch.randn((3, 1536), generator=generator, dtype=torch.float32)
                features = features + (index / 100.0)
                torch.save(features, pt_dir / f"{slide_id.rstrip('.svs')}.pt")

            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONPATH"] = str(REPO_ROOT / "baselines" / lib)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ASSET_HELPER),
                    "--lib",
                    lib,
                    "--trainval-csv",
                    str(cls._trainval_csv(lib)),
                    "--features-root",
                    str(cls._features_root(lib)),
                    "--ckpt",
                    str(cls._checkpoint(lib)),
                ],
                cwd=TASK_DIR,
                env=env,
                text=True,
                capture_output=True,
            )
            if completed.returncode != 0:
                raise AssertionError(completed.stdout + completed.stderr)

    @classmethod
    def _lib_dir(cls, lib: str) -> Path:
        return WORK_DIR / lib.lower()

    @classmethod
    def _full_csv(cls, lib: str) -> Path:
        return cls._lib_dir(lib) / f"{lib}_synthetic_full.csv.zip"

    @classmethod
    def _trainval_csv(cls, lib: str) -> Path:
        return cls._lib_dir(lib) / f"{lib}_synthetic_trainval.csv.zip"

    @classmethod
    def _features_root(cls, lib: str) -> Path:
        return cls._lib_dir(lib) / "synthetic_features"

    @classmethod
    def _checkpoint(cls, lib: str) -> Path:
        return cls._lib_dir(lib) / "s_0_checkpoint.pt"

    @classmethod
    def _output(cls, lib: str) -> Path:
        return cls._lib_dir(lib) / "frozen_output.json"

    def run_evaluation(self, lib: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(REPO_ROOT / "baselines" / lib)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--lib",
                lib,
                "--cancer",
                "BLCA",
                "--ckpt",
                str(self._checkpoint(lib)),
                "--adapted-full-csv",
                str(self._full_csv(lib)),
                "--labels",
                str(self.labels_path),
                "--features-root",
                str(self._features_root(lib)),
                "--out",
                str(self._output(lib)),
            ],
            cwd=TASK_DIR,
            env=env,
            text=True,
            capture_output=True,
        )

    def assert_successful_evaluation(self, lib: str) -> None:
        completed = self.run_evaluation(lib)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(self._output(lib).is_file())
        result = json.loads(self._output(lib).read_text(encoding="utf-8"))
        self.assertEqual(result["lib"], lib)
        self.assertEqual(result["cancer"], "BLCA")
        self.assertEqual(result["n_test"], len(self.test_ids))
        self.assertEqual(len(result["patients"]), len(self.test_ids))
        self.assertEqual({row["patient_id"] for row in result["patients"]}, self.test_ids)
        self.assertTrue(math.isfinite(result["c_index"]))
        self.assertGreaterEqual(result["c_index"], 0.0)
        self.assertLessEqual(result["c_index"], 1.0)
        self.assertTrue(all(math.isfinite(row["risk"]) for row in result["patients"]))
        self.assertTrue(result["test_excluded_from_bins"])
        self.assertEqual(result["path_input_dim"], 1536)
        self.assertIn("datasets/dataset_survival.py", result["dataset_module"])
        self.assertEqual(result["sksurv_import_source"], "scratch/e_sksurv_vendor fallback")
        self.assertTrue(result["dataset_utils_import_shimmed"])
        if lib == "MCAT":
            self.assertEqual(result["model_class"], "MCAT_Surv")
            self.assertEqual(len(result["model_config"]["omic_sizes"]), 6)
            self.assertTrue(all(value > 0 for value in result["model_config"]["omic_sizes"]))
        else:
            self.assertEqual(result["model_class"], "PorpoiseMMF")
            self.assertGreater(result["model_config"]["omic_input_dim"], 0)
            self.assertEqual(result["model_config"]["fusion"], "concat")

    def test_mcat_frozen_evaluation(self) -> None:
        self.assert_successful_evaluation("MCAT")

    def test_porpoise_frozen_evaluation(self) -> None:
        self.assert_successful_evaluation("PORPOISE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
