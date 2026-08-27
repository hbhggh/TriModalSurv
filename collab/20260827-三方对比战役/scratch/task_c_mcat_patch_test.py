#!/usr/bin/env python3
"""任务 C 的 MCAT 最小补丁行为测试。"""

from __future__ import annotations

import argparse
import contextlib
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import types
import unittest

import pandas as pd
import torch
import torch.nn.modules.linear as torch_linear


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[1]
MCAT_ROOT = REPO_ROOT / "baselines" / "MCAT"
PYTHON = Path("/Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python")
BLCA_CSV = MCAT_ROOT / "dataset_csv" / "tcga_blca_all_clean.csv.zip"
BLCA_SPLIT = TASK_ROOT / "scratch" / "splits_mcat_blca" / "splits_0.csv"


def install_inprocess_import_stubs() -> None:
    """只替代当前环境缺失、且本自测不会调用的导入边界。"""
    torchvision = types.ModuleType("torchvision")
    transforms = types.ModuleType("torchvision.transforms")
    torchvision.transforms = transforms
    sys.modules.setdefault("torchvision", torchvision)
    sys.modules.setdefault("torchvision.transforms", transforms)

    torch_geometric = types.ModuleType("torch_geometric")
    torch_geometric_data = types.ModuleType("torch_geometric.data")

    class Batch:
        pass

    torch_geometric_data.Batch = Batch
    torch_geometric.data = torch_geometric_data
    sys.modules.setdefault("torch_geometric", torch_geometric)
    sys.modules.setdefault("torch_geometric.data", torch_geometric_data)

    sksurv = types.ModuleType("sksurv")
    sksurv_metrics = types.ModuleType("sksurv.metrics")

    def concordance_index_censored(*_args, **_kwargs):
        raise RuntimeError("测试桩不应在本自测中被调用")

    sksurv_metrics.concordance_index_censored = concordance_index_censored
    sksurv.metrics = sksurv_metrics
    sys.modules.setdefault("sksurv", sksurv)
    sys.modules.setdefault("sksurv.metrics", sksurv_metrics)


def write_subprocess_import_stubs(root: Path) -> None:
    files = {
        "sitecustomize.py": (
            "import torch.nn as nn\n"
            "import torch.nn.modules.linear as linear\n"
            "if not hasattr(linear, '_LinearWithBias'):\n"
            "    linear._LinearWithBias = nn.Linear\n"
        ),
        "torchvision/__init__.py": "from . import transforms\n",
        "torchvision/transforms.py": "",
        "torch_geometric/__init__.py": "from . import data\n",
        "torch_geometric/data/__init__.py": "class Batch:\n    pass\n",
        "sksurv/__init__.py": "from . import metrics\n",
        "sksurv/metrics.py": (
            "def concordance_index_censored(*args, **kwargs):\n"
            "    raise RuntimeError('test stub must not be called')\n"
        ),
    }
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


@contextlib.contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


install_inprocess_import_stubs()
if not hasattr(torch_linear, "_LinearWithBias"):
    torch_linear._LinearWithBias = torch.nn.Linear
sys.path.insert(0, str(MCAT_ROOT))

from datasets.dataset_survival import Generic_MIL_Survival_Dataset, Generic_Split
from models.model_coattn import MCAT_Surv
from utils import core_utils


class ParserBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory(
            prefix="task_c_help_", dir=TASK_ROOT / "scratch"
        )
        runtime = Path(cls.tempdir.name)
        stubs = runtime / "import_stubs"
        write_subprocess_import_stubs(stubs)
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        path_parts = [str(stubs), str(MCAT_ROOT)]
        if existing_pythonpath:
            path_parts.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(path_parts)
        env["PYTHONPYCACHEPREFIX"] = str(runtime / "pycache")
        cls.help_run = subprocess.run(
            [str(PYTHON), "main.py", "--help"],
            cwd=MCAT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if cls.help_run.returncode != 0:
            raise RuntimeError(
                f"main.py --help 未到达 parser，exit={cls.help_run.returncode}\n"
                f"{cls.help_run.stdout}"
            )

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def test_help_exposes_inst_loss(self):
        self.assertIn("--inst_loss", self.help_run.stdout)

    def test_help_exposes_testing(self):
        self.assertIn("--testing", self.help_run.stdout)

    def test_help_exposes_path_input_dim(self):
        self.assertIn("--path_input_dim", self.help_run.stdout)


class GenericSplitBehaviorTests(unittest.TestCase):
    def make_slide_data(self) -> tuple[pd.DataFrame, list[str]]:
        metadata = ["case_id", "slide_id", "label"]
        slide_data = pd.DataFrame(
            {
                "case_id": ["TCGA-XX-0001"],
                "slide_id": ["TCGA-XX-0001"],
                "label": [0],
                "gene_a": [1.0],
            }
        )
        return slide_data, metadata

    def test_coattn_split_does_not_require_cluster_pickle(self):
        slide_data, metadata = self.make_slide_data()
        with tempfile.TemporaryDirectory(
            prefix="task_c_coattn_", dir=TASK_ROOT / "scratch"
        ) as data_dir:
            split = Generic_Split(
                slide_data,
                metadata=metadata,
                mode="coattn",
                data_dir=data_dir,
                label_col="survival_months",
                patient_dict={"TCGA-XX-0001": ["slide.svs"]},
                num_classes=2,
            )
        self.assertEqual(len(split), 1)
        self.assertFalse(hasattr(split, "fname2ids"))

    def test_cluster_split_still_loads_cluster_pickle(self):
        slide_data, metadata = self.make_slide_data()
        expected = {"slide.pt": [0, 1]}
        with tempfile.TemporaryDirectory(
            prefix="task_c_cluster_", dir=TASK_ROOT / "scratch"
        ) as data_dir:
            with (Path(data_dir) / "fast_cluster_ids.pkl").open("wb") as handle:
                pickle.dump(expected, handle)
            split = Generic_Split(
                slide_data,
                metadata=metadata,
                mode="cluster",
                data_dir=data_dir,
                label_col="survival_months",
                patient_dict={"TCGA-XX-0001": ["slide.svs"]},
                num_classes=2,
            )
        self.assertEqual(split.fname2ids, expected)


class SignaturePathBehaviorTests(unittest.TestCase):
    def test_apply_sig_reads_repository_signature_directory(self):
        with tempfile.TemporaryDirectory(
            prefix="task_c_sig_", dir=TASK_ROOT / "scratch"
        ) as data_dir, working_directory(MCAT_ROOT):
            dataset = Generic_MIL_Survival_Dataset(
                csv_path=BLCA_CSV,
                mode="coattn",
                apply_sig=True,
                data_dir=data_dir,
                shuffle=False,
                seed=1,
                print_info=False,
                patient_strat=False,
                n_bins=4,
                label_col="survival_months",
                ignore=[],
            )
        self.assertIsNotNone(dataset.signatures)
        self.assertEqual(len(dataset.signatures.columns), 6)


class ModelDimensionBehaviorTests(unittest.TestCase):
    @staticmethod
    def forward(dim: int, explicit: bool):
        torch.manual_seed(7)
        kwargs = {
            "fusion": "concat",
            "omic_sizes": [2, 2, 2, 2, 2, 2],
            "n_classes": 4,
        }
        if explicit:
            kwargs["path_input_dim"] = dim
        model = MCAT_Surv(**kwargs)
        model.eval()
        inputs = {f"x_omic{i}": torch.randn(2) for i in range(1, 7)}
        with torch.no_grad():
            output = model(x_path=torch.randn(50, dim), **inputs)
        return model, output

    def test_default_model_keeps_1024_input_and_forwards(self):
        model, output = self.forward(1024, explicit=False)
        self.assertEqual(model.wsi_net[0].in_features, 1024)
        self.assertEqual(tuple(output[0].shape), (1, 4))

    def test_explicit_1536_model_input_forwards(self):
        model, output = self.forward(1536, explicit=True)
        self.assertEqual(model.wsi_net[0].in_features, 1536)
        self.assertEqual(tuple(output[0].shape), (1, 4))


class CorePropagationBehaviorTests(unittest.TestCase):
    def test_train_passes_path_input_dim_to_mcat_constructor(self):
        captured: dict[str, object] = {}

        class StopAfterConstructor(Exception):
            pass

        class RecordingMCAT:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                raise StopAfterConstructor

        class MinimalSplit:
            def __init__(self, slide_id: str):
                self.slide_data = pd.DataFrame({"slide_id": [slide_id]})

            def __len__(self):
                return len(self.slide_data)

        original_model = core_utils.MCAT_Surv
        core_utils.MCAT_Surv = RecordingMCAT
        try:
            with tempfile.TemporaryDirectory(
                prefix="task_c_core_", dir=TASK_ROOT / "scratch"
            ) as results_dir:
                args = argparse.Namespace(
                    results_dir=results_dir,
                    log_data=False,
                    task_type="survival",
                    bag_loss="nll_surv",
                    alpha_surv=0.0,
                    reg_type="None",
                    drop_out=True,
                    n_classes=4,
                    fusion="concat",
                    model_type="mcat",
                    omic_sizes=[2, 2, 2, 2, 2, 2],
                    path_input_dim=1536,
                )
                with self.assertRaises(StopAfterConstructor):
                    core_utils.train(
                        (MinimalSplit("train"), MinimalSplit("val")), 0, args
                    )
        finally:
            core_utils.MCAT_Surv = original_model

        self.assertEqual(captured.get("path_input_dim"), 1536)


class OfficialBlcaMiniSmokeTests(unittest.TestCase):
    def test_official_blca_dataset_and_model_forward_for_both_dimensions(self):
        self.assertTrue(BLCA_SPLIT.is_file(), f"缺少 A1 split: {BLCA_SPLIT}")
        with tempfile.TemporaryDirectory(
            prefix="task_c_blca_", dir=TASK_ROOT / "scratch"
        ) as data_dir, working_directory(MCAT_ROOT):
            pt_dir = Path(data_dir) / "pt_files"
            pt_dir.mkdir(parents=True)
            dataset = Generic_MIL_Survival_Dataset(
                csv_path=BLCA_CSV,
                mode="coattn",
                apply_sig=True,
                data_dir=data_dir,
                shuffle=False,
                seed=1,
                print_info=False,
                patient_strat=False,
                n_bins=4,
                label_col="survival_months",
                ignore=[],
            )
            train_split, _ = dataset.return_splits(
                from_id=False, csv_path=BLCA_SPLIT
            )
            case_id = train_split.slide_data.loc[0, "case_id"]
            slide_ids = dataset.patient_dict[case_id]
            self.assertEqual(len(slide_ids), 1)
            slide_id = slide_ids[0]
            pt_path = pt_dir / f"{slide_id.rstrip('.svs')}.pt"

            for dim, explicit in ((1024, False), (1536, True)):
                torch.save(torch.randn(50, dim), pt_path)
                sample = train_split[0]
                model_kwargs = {
                    "fusion": "concat",
                    "omic_sizes": train_split.omic_sizes,
                    "n_classes": 4,
                }
                if explicit:
                    model_kwargs["path_input_dim"] = dim
                model = MCAT_Surv(**model_kwargs)
                model.eval()
                omics = {
                    f"x_omic{i}": sample[i].float() for i in range(1, 7)
                }
                with torch.no_grad():
                    hazards, survival, prediction, _ = model(
                        x_path=sample[0].float(), **omics
                    )
                self.assertEqual(tuple(hazards.shape), (1, 4))
                self.assertEqual(tuple(survival.shape), (1, 4))
                self.assertEqual(tuple(prediction.shape), (1, 1))
                print(
                    f"MCAT MINI FORWARD PASS: path_dim={dim}, "
                    f"bag={tuple(sample[0].shape)}, hazards={tuple(hazards.shape)}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
