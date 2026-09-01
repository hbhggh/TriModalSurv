#!/usr/bin/env python3
"""Round 3 任务 G：MCAT 真 batch 回归与 CPU 冒烟。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import torch


TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_ROOT = REPO_ROOT / "baselines" / "MCAT"
VENDOR = TASK_DIR / "scratch" / "e_sksurv_vendor"

sys.path.insert(0, str(LIB_ROOT))
if VENDOR.is_dir():
    sys.path.insert(0, str(VENDOR))


def _install_optional_dependency_shims() -> None:
    """测试路径不用 vision/graph，只隔离两库的未使用顶层依赖。"""
    try:
        __import__("torchvision")
    except (ImportError, RuntimeError):
        torchvision = types.ModuleType("torchvision")
        torchvision.transforms = types.ModuleType("torchvision.transforms")
        sys.modules["torchvision"] = torchvision
        sys.modules["torchvision.transforms"] = torchvision.transforms

    try:
        __import__("torch_geometric")
    except ImportError:
        torch_geometric = types.ModuleType("torch_geometric")
        torch_geometric_data = types.ModuleType("torch_geometric.data")
        torch_geometric_data.Batch = type("Batch", (), {})
        torch_geometric.data = torch_geometric_data
        sys.modules["torch_geometric"] = torch_geometric
        sys.modules["torch_geometric.data"] = torch_geometric_data


_install_optional_dependency_shims()

from models.model_coattn import MCAT_Surv  # noqa: E402
from utils import utils as mcat_utils  # noqa: E402


OMIC_SIZES = [3, 4, 5, 6, 7, 8]
PATH_DIM = 8


CLI_HELP_CODE = r"""
import runpy
import sys
import types

lib_root, vendor, main_path, *main_args = sys.argv[1:]
sys.path.insert(0, lib_root)
sys.path.insert(0, vendor)
torchvision = types.ModuleType("torchvision")
torchvision.transforms = types.ModuleType("torchvision.transforms")
sys.modules["torchvision"] = torchvision
sys.modules["torchvision.transforms"] = torchvision.transforms
torch_geometric = types.ModuleType("torch_geometric")
torch_geometric_data = types.ModuleType("torch_geometric.data")
torch_geometric_data.Batch = type("Batch", (), {})
torch_geometric.data = torch_geometric_data
sys.modules["torch_geometric"] = torch_geometric
sys.modules["torch_geometric.data"] = torch_geometric_data
sys.argv = [main_path, *main_args]
runpy.run_path(main_path, run_name="__main__")
"""


def make_items(count: int) -> list[tuple[object, ...]]:
    generator = torch.Generator().manual_seed(20260827)
    items = []
    for index in range(count):
        path = torch.randn(3 + index, PATH_DIM, generator=generator)
        omics = [
            torch.randn(size, generator=generator) for size in OMIC_SIZES
        ]
        items.append(
            (
                path,
                *omics,
                index % 4,
                float(index + 1),
                float(index % 2),
            )
        )
    return items


def build_model() -> MCAT_Surv:
    torch.manual_seed(123)
    model = MCAT_Surv(
        fusion="concat",
        omic_sizes=OMIC_SIZES,
        n_classes=4,
        path_input_dim=PATH_DIM,
        dropout=0.25,
    )
    return model.cpu()


class ListDataset(torch.utils.data.Dataset):
    def __init__(self, items: list[tuple[object, ...]]):
        self.items = items
        self.slide_data = pd.DataFrame(
            {"slide_id": [f"MCAT-PATIENT-{index}" for index in range(len(items))]}
        )

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> tuple[object, ...]:
        return self.items[index]


class MCATBatchRegression(unittest.TestCase):
    def require_collator(self):
        self.assertTrue(
            hasattr(mcat_utils, "collate_MIL_survival_sig_batched"),
            "缺少 MCAT batched signature collator；该断言应在生产改造前 RED。",
        )
        return mcat_utils.collate_MIL_survival_sig_batched

    def test_cli_exposes_batched_collate_switch(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                CLI_HELP_CODE,
                str(LIB_ROOT),
                str(VENDOR),
                str(LIB_ROOT / "main.py"),
                "--help",
            ],
            cwd=LIB_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--batched_collate", completed.stdout)

    def test_cli_sets_gc4_for_batch_size_eight(self):
        with tempfile.TemporaryDirectory(prefix="g_mcat_cli_", dir=TASK_DIR / "scratch") as tmp:
            tmp_path = Path(tmp)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    CLI_HELP_CODE,
                    str(LIB_ROOT),
                    str(VENDOR),
                    str(LIB_ROOT / "main.py"),
                    "--batched_collate",
                    "--batch_size",
                    "8",
                    "--gc",
                    "99",
                    "--k_start",
                    "0",
                    "--k_end",
                    "0",
                    "--results_dir",
                    str(tmp_path / "results"),
                    "--data_root_dir",
                    str(tmp_path / "features"),
                    "--which_splits",
                    "5foldcv",
                    "--split_dir",
                    "tcga_blca",
                    "--model_type",
                    "mcat",
                    "--mode",
                    "coattn",
                    "--fusion",
                    "concat",
                    "--apply_sig",
                ],
                cwd=LIB_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "batched_collate: batch_size=8, gc=4, effective_samples=32",
            completed.stdout,
        )
        print("MCAT_CLI_GC_PASS batch_size=8 gc=4 effective_samples=32")

    def test_batched_collator_pads_paths_and_stacks_patient_fields(self):
        collate = self.require_collator()
        batch = collate(make_items(8))

        self.assertEqual(len(batch), 11)
        paths, path_mask, *rest = batch
        self.assertEqual(tuple(paths.shape), (8, 10, PATH_DIM))
        self.assertEqual(path_mask.dtype, torch.bool)
        expected_mask = torch.arange(10).unsqueeze(0) >= torch.arange(3, 11).unsqueeze(1)
        self.assertTrue(torch.equal(path_mask, expected_mask))
        for omic, width in zip(rest[:6], OMIC_SIZES):
            self.assertEqual(tuple(omic.shape), (8, width))
            self.assertEqual(omic.dtype, torch.float32)
        label, event_time, censorship = rest[6:]
        self.assertEqual(tuple(label.shape), (8,))
        self.assertEqual(label.dtype, torch.long)
        self.assertEqual(tuple(event_time.shape), (8,))
        self.assertEqual(event_time.dtype, torch.float32)
        self.assertEqual(tuple(censorship.shape), (8,))
        self.assertEqual(censorship.dtype, torch.float32)

    def test_bs1_new_path_matches_official_path_allclose(self):
        collate = self.require_collator()
        item = make_items(1)[0]
        old_batch = mcat_utils.collate_MIL_survival_sig([item])
        new_batch = collate([item])
        model = build_model().eval()

        with torch.inference_mode():
            old_output = model(
                x_path=old_batch[0],
                **{f"x_omic{i}": old_batch[i] for i in range(1, 7)},
            )
            new_output = model(
                x_path=new_batch[0],
                path_mask=new_batch[1],
                **{f"x_omic{i}": new_batch[i + 1] for i in range(1, 7)},
            )

        max_abs = 0.0
        for old_tensor, new_tensor in zip(old_output[:2], new_output[:2]):
            max_abs = max(
                max_abs, torch.max(torch.abs(old_tensor - new_tensor)).item()
            )
            self.assertTrue(
                torch.allclose(old_tensor, new_tensor, atol=1e-5, rtol=1e-5),
                f"bs=1 新旧路径不等价：max_abs={torch.max(torch.abs(old_tensor - new_tensor)).item()}",
            )
        self.assertTrue(torch.equal(old_output[2], new_output[2]))
        for key in ("coattn", "path", "omic"):
            self.assertTrue(
                torch.allclose(
                    old_output[3][key], new_output[3][key], atol=1e-5, rtol=1e-5
                ),
                f"bs=1 attention[{key}] 不等价",
            )
        print(f"MCAT_BS1_ALLCLOSE_PASS atol=1e-5 max_abs={max_abs:.9g}")

    def test_bs8_matches_eight_independent_forwards_allclose(self):
        collate = self.require_collator()
        items = make_items(8)
        batch = collate(items)
        model = build_model().eval()

        with torch.inference_mode():
            batched = model(
                x_path=batch[0],
                path_mask=batch[1],
                **{f"x_omic{i}": batch[i + 1] for i in range(1, 7)},
            )
            singles = []
            for item in items:
                old_batch = mcat_utils.collate_MIL_survival_sig([item])
                singles.append(
                    model(
                        x_path=old_batch[0],
                        **{f"x_omic{i}": old_batch[i] for i in range(1, 7)},
                    )
                )

        max_abs = 0.0
        for output_index in (0, 1):
            expected = torch.cat([output[output_index] for output in singles], dim=0)
            max_abs = max(
                max_abs,
                torch.max(torch.abs(batched[output_index] - expected)).item(),
            )
            self.assertTrue(
                torch.allclose(batched[output_index], expected, atol=1e-5, rtol=1e-5),
                f"bs=8 output[{output_index}] 与逐样本前向不一致；max_abs="
                f"{torch.max(torch.abs(batched[output_index] - expected)).item()}",
            )
        expected_labels = torch.cat([output[2] for output in singles], dim=0)
        self.assertTrue(torch.equal(batched[2], expected_labels))
        print(f"MCAT_BS8_ALLCLOSE_PASS atol=1e-5 max_abs={max_abs:.9g}")

    def test_validation_loader_really_uses_batch_size_eight(self):
        self.require_collator()
        loader = mcat_utils.get_split_loader(
            ListDataset(make_items(8)),
            training=False,
            testing=False,
            mode="coattn",
            batch_size=8,
            batched_collate=True,
        )
        batch = next(iter(loader))
        self.assertEqual(tuple(batch[0].shape[:2]), (8, 10))

    def test_cpu_bs8_training_smoke_steps_final_partial_window(self):
        collate = self.require_collator()
        from utils import core_utils  # 延迟导入，确保 RED 命中目标 API。

        self.assertTrue(
            hasattr(core_utils, "train_loop_survival_coattn_batched"),
            "缺少白名单内的 MCAT batched 训练循环。",
        )
        model = build_model().train()
        optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)
        before = model.classifier.weight.detach().clone()
        batch = collate(make_items(8))
        core_utils.train_loop_survival_coattn_batched(
            0,
            model,
            [batch],
            optimizer,
            4,
            loss_fn=mcat_utils.NLLSurvLoss(alpha=0.0),
            gc=4,
        )
        self.assertFalse(torch.equal(before, model.classifier.weight.detach()))

    def test_batched_summary_emits_all_eight_patients(self):
        from utils import core_utils

        dataset = ListDataset(make_items(8))
        loader = mcat_utils.get_split_loader(
            dataset,
            training=False,
            mode="coattn",
            batch_size=8,
            batched_collate=True,
        )
        results, c_index = core_utils.summary_survival_coattn_batched(
            build_model().eval(), loader, 4
        )
        self.assertEqual(list(results), dataset.slide_data["slide_id"].tolist())
        self.assertTrue(np.isfinite(c_index))


if __name__ == "__main__":
    unittest.main(verbosity=2)
