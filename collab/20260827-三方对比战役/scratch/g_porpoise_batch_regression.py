#!/usr/bin/env python3
"""Round 3 任务 G：PORPOISE 真 batch 回归与 CPU 冒烟。"""

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
LIB_ROOT = REPO_ROOT / "baselines" / "PORPOISE"
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

from models.model_porpoise import PorpoiseMMF  # noqa: E402
from utils import utils as porpoise_utils  # noqa: E402


PATH_DIM = 8
OMIC_DIM = 12


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


def make_items(count: int) -> list[tuple[torch.Tensor, ...]]:
    generator = torch.Generator().manual_seed(20260827)
    items = []
    for index in range(count):
        items.append(
            (
                torch.randn(3 + index, PATH_DIM, generator=generator),
                torch.randn(1, OMIC_DIM, generator=generator),
                torch.tensor([index % 4], dtype=torch.float32),
                torch.tensor([float(index + 1)], dtype=torch.float32),
                torch.tensor([float(index % 2)], dtype=torch.float32),
            )
        )
    return items


def build_model() -> PorpoiseMMF:
    torch.manual_seed(123)
    model = PorpoiseMMF(
        omic_input_dim=OMIC_DIM,
        path_input_dim=PATH_DIM,
        fusion="concat",
        n_classes=4,
        dropinput=0.0,
    )
    return model.cpu()


class ListDataset(torch.utils.data.Dataset):
    def __init__(self, items: list[tuple[torch.Tensor, ...]]):
        self.items = items
        self.slide_data = pd.DataFrame(
            {"slide_id": [f"PORPOISE-PATIENT-{index}" for index in range(len(items))]}
        )

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, ...]:
        return self.items[index]


class PorpoiseBatchRegression(unittest.TestCase):
    def require_collator(self):
        self.assertTrue(
            hasattr(porpoise_utils, "collate_MIL_survival_batched"),
            "缺少 PORPOISE batched survival collator；该断言应在生产改造前 RED。",
        )
        return porpoise_utils.collate_MIL_survival_batched

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
        with tempfile.TemporaryDirectory(prefix="g_porpoise_cli_", dir=TASK_DIR / "scratch") as tmp:
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
                    "porpoise_mmf",
                    "--mode",
                    "pathomic",
                    "--fusion",
                    "concat",
                    "--apply_mutsig",
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
        print("PORPOISE_CLI_GC_PASS batch_size=8 gc=4 effective_samples=32")

    def test_batched_collator_pads_paths_and_stacks_patient_fields(self):
        collate = self.require_collator()
        paths, path_mask, omic, label, event_time, censorship = collate(make_items(8))
        self.assertEqual(tuple(paths.shape), (8, 10, PATH_DIM))
        self.assertEqual(path_mask.dtype, torch.bool)
        expected_mask = torch.arange(10).unsqueeze(0) >= torch.arange(3, 11).unsqueeze(1)
        self.assertTrue(torch.equal(path_mask, expected_mask))
        self.assertEqual(tuple(omic.shape), (8, OMIC_DIM))
        self.assertEqual(omic.dtype, torch.float32)
        self.assertEqual(tuple(label.shape), (8,))
        self.assertEqual(label.dtype, torch.long)
        self.assertEqual(tuple(event_time.shape), (8,))
        self.assertEqual(event_time.dtype, torch.float32)
        self.assertEqual(tuple(censorship.shape), (8,))
        self.assertEqual(censorship.dtype, torch.float32)

    def test_bs1_new_path_matches_official_path_allclose(self):
        collate = self.require_collator()
        item = make_items(1)[0]
        old_batch = porpoise_utils.collate_MIL_survival([item])
        new_batch = collate([item])
        model = build_model().eval()

        with torch.inference_mode():
            old_logits = model(x_path=old_batch[0], x_omic=old_batch[1])
            new_logits = model(
                x_path=new_batch[0], x_omic=new_batch[2], path_mask=new_batch[1]
            )
        self.assertTrue(
            torch.allclose(old_logits, new_logits, atol=1e-5, rtol=1e-5),
            f"bs=1 新旧路径不等价：max_abs={torch.max(torch.abs(old_logits - new_logits)).item()}",
        )
        print(
            "PORPOISE_BS1_ALLCLOSE_PASS atol=1e-5 max_abs="
            f"{torch.max(torch.abs(old_logits - new_logits)).item():.9g}"
        )

    def test_bs8_matches_eight_independent_forwards_allclose(self):
        collate = self.require_collator()
        items = make_items(8)
        batch = collate(items)
        model = build_model().eval()

        with torch.inference_mode():
            batched = model(x_path=batch[0], x_omic=batch[2], path_mask=batch[1])
            singles = []
            for item in items:
                old_batch = porpoise_utils.collate_MIL_survival([item])
                singles.append(model(x_path=old_batch[0], x_omic=old_batch[1]))
            expected = torch.cat(singles, dim=0)

        self.assertTrue(
            torch.allclose(batched, expected, atol=1e-5, rtol=1e-5),
            "bs=8 与逐样本前向不一致；max_abs="
            f"{torch.max(torch.abs(batched - expected)).item()}",
        )
        print(
            "PORPOISE_BS8_ALLCLOSE_PASS atol=1e-5 max_abs="
            f"{torch.max(torch.abs(batched - expected)).item():.9g}"
        )

    def test_validation_loader_really_uses_batch_size_eight(self):
        self.require_collator()
        loader = porpoise_utils.get_split_loader(
            ListDataset(make_items(8)),
            training=False,
            testing=False,
            mode="pathomic",
            batch_size=8,
            batched_collate=True,
        )
        batch = next(iter(loader))
        self.assertEqual(tuple(batch[0].shape[:2]), (8, 10))

    def test_cpu_bs8_training_smoke_steps_final_partial_window(self):
        collate = self.require_collator()
        from utils import core_utils
        from utils.loss_func import NLLSurvLoss

        model = build_model().train()
        optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)
        before = model.classifier_mm.weight.detach().clone()
        core_utils.train_loop_survival(
            0,
            model,
            [collate(make_items(8))],
            optimizer,
            4,
            loss_fn=NLLSurvLoss(alpha=0.0),
            gc=4,
            batched_collate=True,
        )
        self.assertFalse(torch.equal(before, model.classifier_mm.weight.detach()))

    def test_batched_summary_emits_all_eight_patients(self):
        from utils import core_utils

        dataset = ListDataset(make_items(8))
        loader = porpoise_utils.get_split_loader(
            dataset,
            training=False,
            mode="pathomic",
            batch_size=8,
            batched_collate=True,
        )
        results, c_index = core_utils.summary_survival(
            build_model().eval(), loader, 4, batched_collate=True
        )
        self.assertEqual(list(results), dataset.slide_data["slide_id"].tolist())
        self.assertTrue(np.isfinite(c_index))

    def test_batched_loss_dispatch_supports_ce_surv_contract(self):
        from utils import core_utils

        logits = torch.tensor(
            [[0.1, -0.2, 0.3, -0.4], [0.2, 0.0, -0.1, 0.4]],
            dtype=torch.float32,
            requires_grad=True,
        )
        labels = torch.tensor([0, 2], dtype=torch.long)
        event_time = torch.tensor([1.0, 2.0], dtype=torch.float32)
        censorship = torch.tensor([0.0, 1.0], dtype=torch.float32)
        try:
            loss, returned_logits = core_utils._porpoise_loss_and_logits(
                logits,
                porpoise_utils.CrossEntropySurvLoss(alpha=0.0),
                labels,
                event_time,
                censorship,
            )
        except TypeError as exc:
            self.fail(f"batched CE survival loss 调用了错误接口：{exc}")
        self.assertEqual(loss.dim(), 0)
        self.assertTrue(torch.isfinite(loss))
        self.assertIs(returned_logits, logits)
        risk = core_utils._porpoise_risk(
            logits, porpoise_utils.CrossEntropySurvLoss(alpha=0.0)
        )
        expected_risk = (
            -torch.cumprod(1 - torch.sigmoid(logits), dim=1).sum(dim=1)
        ).detach().numpy()
        self.assertEqual(risk.shape, (2,))
        self.assertTrue(torch.allclose(torch.from_numpy(risk), torch.from_numpy(expected_risk)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
