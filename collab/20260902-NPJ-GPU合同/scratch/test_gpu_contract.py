#!/usr/bin/env python3
import argparse
import ast
import contextlib
import copy
import importlib.util
import importlib.machinery
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
import yaml


ROOT = Path(__file__).resolve().parents[3]
NPJ = ROOT / "NPJ"
MAIN_PATH = NPJ / "main_survival.py"
FUSION_PATH = NPJ / "model" / "fusion_model.py"
GPU_CONFIG_PATH = NPJ / "config" / "gpu_train.yaml"
LAUNCH_PATH = NPJ / "scripts" / "launch_formal.sh"
GATE_PATH = NPJ / "scripts" / "gpu_util_gate.py"


def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _install_main_import_stubs():
    class _Unused:
        def __init__(self, *args, **kwargs):
            pass

    class _Accelerator:
        def __init__(self, *args, **kwargs):
            pass

        def backward(self, loss):
            loss.backward()

        def prepare(self, *values):
            return values

    class _DummyConfig:
        def __init__(self, *args, **kwargs):
            self.obj = types.SimpleNamespace()

    def _str2bool(value):
        if isinstance(value, bool):
            return value
        if value.lower() in {"yes", "true", "t", "y", "1"}:
            return True
        if value.lower() in {"no", "false", "f", "n", "0"}:
            return False
        raise argparse.ArgumentTypeError("Boolean value expected.")

    transformers = _module(
        "transformers",
        BertTokenizer=_Unused,
        BertModel=_Unused,
        AdamW=_Unused,
        get_linear_schedule_with_warmup=lambda *args, **kwargs: None,
    )
    transformers.__all__ = [
        "BertTokenizer",
        "BertModel",
        "AdamW",
        "get_linear_schedule_with_warmup",
    ]

    sksurv = _module("sksurv")
    sksurv.__path__ = []
    _module(
        "sksurv.metrics",
        concordance_index_censored=lambda *args, **kwargs: (0.5,),
    )
    _module("accelerate", Accelerator=_Accelerator)
    _module(
        "torchmetrics",
        Precision=_Unused,
        Recall=_Unused,
        F1Score=_Unused,
        Accuracy=_Unused,
    )
    _module("tqdm", tqdm=lambda iterable, **kwargs: iterable)

    matplotlib = _module("matplotlib")
    matplotlib.__path__ = []
    _module("matplotlib.pyplot")

    model = _module("model")
    model.__path__ = []
    fusion = _module("model.fusion_model")
    fusion.__all__ = []
    _module(
        "model.compensator",
        CAPRecall=_Unused,
        MissingBank=_Unused,
    )

    loc_utils = _module("loc_utils")
    loc_utils.__path__ = []
    common_tools = _module(
        "loc_utils.common_tools",
        str2bool=_str2bool,
        YmlConfig=_DummyConfig,
        set_seed=lambda seed: torch.manual_seed(seed),
    )
    common_tools.__all__ = ["str2bool", "YmlConfig", "set_seed"]

    loc_utils_3yr = _module("loc_utils_3yr")
    loc_utils_3yr.__path__ = []
    _module(
        "loc_utils_3yr.tcga_dataset",
        get_dataset_tcga_sur=lambda *args, **kwargs: None,
    )
    _module(
        "loc_utils_3yr.loss_func",
        NLLSurvLoss=_Unused,
        PairwiseRankingLoss=_Unused,
    )
    model_util = _module("loc_utils_3yr.model_util", ModelDumper=_Unused)
    model_util.__all__ = ["ModelDumper"]


def load_main_module():
    _install_main_import_stubs()
    module_name = "gpu_contract_main_survival"
    spec = importlib.util.spec_from_file_location(module_name, MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.tqdm = lambda iterable, **kwargs: iterable
    module.concordance_index_censored = lambda *args, **kwargs: (0.5,)
    return module


class ToyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(2, 3)

    def forward(self, inputs):
        return torch.sigmoid(self.linear(inputs["img"]))


class ToyLoss(nn.Module):
    def forward(self, hazard, survival_bin, survival_months, censorship):
        target = survival_bin.float().unsqueeze(1).expand_as(hazard) / 3.0
        return ((hazard - target) ** 2).mean()


class ToyAccelerator:
    def backward(self, loss):
        loss.backward()


def toy_records():
    records = []
    for index in range(6):
        records.append(
            {
                "img": torch.tensor([index / 10.0, (index + 1) / 10.0]),
                "survival_months": torch.tensor(float(index + 1)),
                "survival_months_bin": torch.tensor(index % 3),
                "censorship": torch.tensor(index % 2),
                "label": torch.tensor(0),
                "patient_id": f"P{index}",
                "cancer_type": "BLCA",
                "idx": torch.tensor(index),
            }
        )
    return records


def legacy_finetune_epoch(
    model,
    criterion,
    optimizer,
    dataloader,
    training=True,
    device="cpu",
    accelerator=None,
):
    model.train(training)
    losses = []
    all_hazards = []
    all_times = []
    all_censors = []
    for original_batch in dataloader:
        dbatch = dict(original_batch)
        survival_months = dbatch.pop("survival_months").to(device)
        survival_months_bin = dbatch.pop("survival_months_bin").to(device)
        censorship = dbatch.pop("censorship").to(device)
        dbatch.pop("label", None)
        dbatch.pop("patient_id", None)
        dbatch.pop("cancer_type")
        dbatch.pop("idx", None)
        inputs = {key: value.to(device, dtype=torch.float) for key, value in dbatch.items()}
        with torch.set_grad_enabled(training):
            hazard = model(inputs)
            loss = criterion(
                hazard,
                survival_months_bin,
                survival_months,
                censorship,
            )
            if training:
                accelerator.backward(loss)
                optimizer.step()
                optimizer.zero_grad()
        losses.append(loss.item())
        all_hazards.append(hazard.detach().cpu())
        all_times.append(survival_months.cpu())
        all_censors.append(censorship.cpu())
    torch.cat(all_hazards)
    torch.cat(all_times)
    torch.cat(all_censors)
    return float(np.mean(losses))


def _production_forward():
    tree = ast.parse(FUSION_PATH.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "MainModalityMoE"
    )
    forward_node = copy.deepcopy(
        next(
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "forward"
        )
    )
    forward_node.name = "production_forward"
    module = ast.Module(body=[forward_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"torch": torch, "consistency_loss": lambda pairs: torch.tensor(0.0)}
    exec(compile(module, str(FUSION_PATH), "exec"), namespace)
    return namespace["production_forward"]


class CountingHead(nn.Module):
    def __init__(self, dim, bins):
        super().__init__()
        self.linear = nn.Linear(dim, bins)
        self.calls = 0

    def forward(self, inputs):
        self.calls += 1
        hazard = self.linear(inputs)
        return hazard, torch.cumprod(1 - hazard, dim=1)


class FirstFusion(nn.Module):
    def forward(self, values):
        return values[0]


class ForwardHarness(nn.Module):
    def __init__(self):
        super().__init__()
        self.m_projector = nn.ModuleDict({"img": nn.Identity()})
        self.fusion = FirstFusion()
        self.backbone = nn.Identity()
        self.surv_heads = nn.ModuleDict(
            {"BLCA": CountingHead(4, 3), "LUAD": CountingHead(4, 3)}
        )
        self.compensator = None


def legacy_head_forward(model, modalities, cancer_type):
    projected = model.m_projector["img"](modalities["img"])
    pooled = model.backbone(model.fusion([projected]).unsqueeze(1)).mean(dim=1)
    hazards = []
    survs = []
    for index, cancer in enumerate(cancer_type):
        hazard, surv = model.surv_heads[cancer](pooled[index].unsqueeze(0))
        hazards.append(hazard)
        survs.append(surv)
    return torch.cat(hazards, dim=0), torch.cat(survs, dim=0)


class ConfigAndLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = load_main_module()

    def test_gpu_yaml_has_contract_defaults(self):
        config = yaml.safe_load(GPU_CONFIG_PATH.read_text(encoding="utf-8"))
        batch = config["batch_size"]
        self.assertTrue(batch is None or batch > 1, batch)  # 合同：禁止默认为 1
        if config.get("allow_low_gpu_util"):
            self.assertTrue(str(config.get("low_gpu_util_reason", "")).strip())
        self.assertEqual(config["gradient_accumulation_steps"], 1)
        self.assertEqual(config["num_workers"], 4)
        self.assertIs(config["pin_memory"], True)
        self.assertIs(config["persistent_workers"], True)
        self.assertEqual(config["prefetch_factor"], 4)
        self.assertIs(config["non_blocking"], True)
        self.assertEqual(config["gpu_util_warmup_sec"], 120)
        self.assertEqual(config["gpu_util_min_percent"], 50)

    def test_cli_overrides_yaml_and_cpu_null_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "gpu.yaml"
            config_path.write_text(
                "batch_size: 7\nnum_workers: 3\ngradient_accumulation_steps: 1\n",
                encoding="utf-8",
            )
            args = self.main.parsing_args(
                ["--gpu_config", str(config_path), "--batch_size", "5", "--num_workers", "2"]
            )
            resolved = self.main.resolve_gpu_config(args, cuda_available=False)
            self.assertEqual(resolved["batch_size"], 5)
            self.assertEqual(resolved["batch_size_source"], "cli")
            self.assertEqual(resolved["num_workers"], 2)

            config_path.write_text(
                "batch_size: null\nnum_workers: 0\ngradient_accumulation_steps: 1\n",
                encoding="utf-8",
            )
            args = self.main.parsing_args(["--gpu_config", str(config_path)])
            with self.assertRaisesRegex(RuntimeError, "CUDA"):
                self.main.resolve_gpu_config(args, cuda_available=False)
            print("CPU_NULL_BATCH_REJECTED=1")

    def test_formal_batch_one_requires_reason_and_workers_zero_omits_worker_only_keys(self):
        config = {
            "batch_size": 1,
            "num_workers": 0,
            "pin_memory": True,
            "persistent_workers": True,
            "prefetch_factor": 4,
        }
        with self.assertRaises(SystemExit) as raised:
            self.main.validate_formal_contract(
                config,
                environ={"FORMAL_RUN": "1", "BATCH_SIZE_BLOCKED_REASON": ""},
            )
        self.assertEqual(raised.exception.code, 3)
        self.main.validate_formal_contract(
            config,
            environ={"FORMAL_RUN": "1", "BATCH_SIZE_BLOCKED_REASON": "model limitation"},
        )
        kwargs = self.main.build_dataloader_kwargs(config)
        self.assertNotIn("persistent_workers", kwargs)
        self.assertNotIn("prefetch_factor", kwargs)

    def test_accum_one_three_epoch_losses_are_bitwise_equal_to_head(self):
        torch.manual_seed(20260902)
        head_model = ToyModel()
        new_model = copy.deepcopy(head_model)
        criterion = ToyLoss()
        head_optimizer = torch.optim.SGD(head_model.parameters(), lr=0.05)
        new_optimizer = torch.optim.SGD(new_model.parameters(), lr=0.05)
        loader = DataLoader(toy_records(), batch_size=2, shuffle=False)

        head_losses = []
        new_losses = []
        for epoch in range(3):
            head_losses.append(
                legacy_finetune_epoch(
                    head_model,
                    criterion,
                    head_optimizer,
                    loader,
                    training=True,
                    accelerator=ToyAccelerator(),
                )
            )
            metric = self.main.finetune_epoch(
                new_model,
                criterion,
                new_optimizer,
                loader,
                epoch,
                training=True,
                device="cpu",
                accelerator=ToyAccelerator(),
                gradient_accumulation_steps=1,
                non_blocking=True,
            )
            new_losses.append(metric["loss"])

        print(f"HEAD_LOSSES={head_losses}")
        print(f"NEW_LOSSES={new_losses}")
        print(f"BITWISE_EQUAL={head_losses == new_losses}")
        self.assertEqual(head_losses, new_losses)

    def test_help_and_explicit_batch_two_cpu_smoke(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            self.main.parsing_args(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--gpu_config", output.getvalue())

        args = self.main.parsing_args(["--batch_size", "2", "--epochs", "1"])
        self.assertEqual(args.batch_size, 2)
        model = ToyModel()
        metric = self.main.finetune_epoch(
            model,
            ToyLoss(),
            torch.optim.SGD(model.parameters(), lr=0.05),
            DataLoader(toy_records(), batch_size=args.batch_size, shuffle=False),
            epoch=0,
            training=True,
            device="cpu",
            accelerator=ToyAccelerator(),
            gradient_accumulation_steps=1,
            non_blocking=True,
        )
        print(
            f"CPU_SMOKE batch_size={args.batch_size} epochs={args.epochs} "
            f"loss={metric['loss']}"
        )
        self.assertTrue(np.isfinite(metric["loss"]))

    def test_accumulation_steps_on_full_and_partial_windows(self):
        model = ToyModel()
        optimizer = torch.optim.SGD(model.parameters(), lr=0.05)
        original_step = optimizer.step
        step_count = 0

        def counted_step(*args, **kwargs):
            nonlocal step_count
            step_count += 1
            return original_step(*args, **kwargs)

        optimizer.step = counted_step
        metric = self.main.finetune_epoch(
            model,
            ToyLoss(),
            optimizer,
            DataLoader(toy_records(), batch_size=2, shuffle=False),
            epoch=0,
            training=True,
            device="cpu",
            accelerator=ToyAccelerator(),
            gradient_accumulation_steps=2,
            non_blocking=True,
        )
        print(f"ACCUM_STEPS=2 OPTIMIZER_STEPS={step_count}")
        self.assertEqual(step_count, 2)
        self.assertTrue(np.isfinite(metric["loss"]))


class SurvivalHeadFastPathTests(unittest.TestCase):
    def test_single_cancer_is_fast_and_allclose_to_legacy(self):
        torch.manual_seed(7)
        model = ForwardHarness().eval()
        legacy = copy.deepcopy(model)
        inputs = {"img": torch.randn(5, 4)}
        cancers = ["BLCA"] * 5
        expected = legacy_head_forward(legacy, inputs, cancers)
        actual = _production_forward()(model, inputs, cancers)
        print(
            "SURV_HEAD_SINGLE "
            f"hazard_max_diff={(actual[0] - expected[0]).abs().max().item()} "
            f"calls={model.surv_heads['BLCA'].calls}"
        )
        self.assertTrue(torch.allclose(actual[0], expected[0], atol=1e-6))
        self.assertTrue(torch.allclose(actual[1], expected[1], atol=1e-6))
        self.assertEqual(model.surv_heads["BLCA"].calls, 1)

    def test_mixed_cancer_falls_back_and_is_allclose(self):
        torch.manual_seed(8)
        model = ForwardHarness().eval()
        legacy = copy.deepcopy(model)
        inputs = {"img": torch.randn(4, 4)}
        cancers = ["BLCA", "LUAD", "BLCA", "LUAD"]
        expected = legacy_head_forward(legacy, inputs, cancers)
        actual = _production_forward()(model, inputs, cancers)
        print(
            "SURV_HEAD_MIXED "
            f"hazard_max_diff={(actual[0] - expected[0]).abs().max().item()} "
            f"blca_calls={model.surv_heads['BLCA'].calls} "
            f"luad_calls={model.surv_heads['LUAD'].calls}"
        )
        self.assertTrue(torch.allclose(actual[0], expected[0], atol=1e-6))
        self.assertTrue(torch.allclose(actual[1], expected[1], atol=1e-6))
        self.assertEqual(model.surv_heads["BLCA"].calls, 2)
        self.assertEqual(model.surv_heads["LUAD"].calls, 2)


class LaunchGateTests(unittest.TestCase):
    def _write_executable(self, path, content):
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        path.chmod(0o755)

    def _run_launch(
        self,
        util,
        allow,
        reason,
        warmup=0,
        training_command="sleep 3; exit 0",  # 须长于 gate 启动，避免误入早退放行分支
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            self._write_executable(
                temp / "nvidia-smi",
                f"""\
                #!/bin/sh
                echo "{util}, 2048"
                """,
            )
            self._write_executable(
                temp / "setsid",
                """\
                #!/bin/sh
                exec "$@"
                """,
            )
            config = temp / "gpu.yaml"
            config.write_text(
                yaml.safe_dump(
                    {
                        "gpu_util_warmup_sec": warmup,
                        "gpu_util_min_percent": 50,
                        "allow_low_gpu_util": allow,
                        "low_gpu_util_reason": reason,
                    }
                ),
                encoding="utf-8",
            )
            log_path = temp / "formal.log"
            env = os.environ.copy()
            env["PATH"] = f"{temp}:{env['PATH']}"
            env["GPU_CONFIG"] = str(config)
            env["PYTHON_BIN"] = sys.executable
            completed = subprocess.run(
                [
                    "bash",
                    str(LAUNCH_PATH),
                    "0",
                    str(log_path),
                    "--",
                    "bash",
                    "-c",
                    training_command,
                ],
                cwd=NPJ,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            return completed.returncode, completed.stdout, log_text

    def test_gate_four_launch_states(self):
        low_code, _, low_log = self._run_launch(10, False, "")
        high_code, _, high_log = self._run_launch(80, False, "")
        waived_code, _, waived_log = self._run_launch(10, True, "hardware baseline")
        empty_code, _, empty_log = self._run_launch(10, True, "")
        print(
            "GATE_CODES "
            f"low={low_code} high={high_code} waived={waived_code} "
            f"empty_reason={empty_code}"
        )
        self.assertEqual(low_code, 2, low_log)
        self.assertEqual(high_code, 0, high_log)
        self.assertEqual(waived_code, 0, waived_log)
        self.assertIn("hardware baseline", waived_log)
        self.assertEqual(empty_code, 2, empty_log)

    def test_training_early_success_is_allowed(self):
        code, _, log = self._run_launch(
            10,
            False,
            "",
            warmup=1.0,
            training_command="sleep 0.01; exit 0",
        )
        print(f"EARLY_SUCCESS_CODE={code}")
        print(
            "EARLY_SUCCESS_GATE="
            + next(line for line in log.splitlines() if '"early_exit"' in line)
        )
        self.assertEqual(code, 0, log)
        self.assertIn('"early_exit":true', log)
        self.assertIn("FORMAL_GATE_EARLY_COMPLETE", log)

    def test_training_early_failure_exit_code_is_preserved(self):
        code, _, log = self._run_launch(
            10,
            False,
            "",
            warmup=1.0,
            training_command="sleep 0.01; exit 7",
        )
        print(f"EARLY_FAILURE_CODE={code}")
        print(
            "EARLY_FAILURE_GATE="
            + next(line for line in log.splitlines() if '"early_exit"' in line)
        )
        self.assertEqual(code, 7, log)
        self.assertIn('"early_exit":true', log)
        self.assertIn("FORMAL_TRAINING_FAILED EXIT_CODE=7", log)

    def test_gate_missing_nvidia_smi_is_exit_three(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(GATE_PATH),
                "--gpu",
                "0",
                "--warmup",
                "0",
                "--interval",
                "0.01",
                "--min",
                "50",
            ],
            cwd=NPJ,
            env={"PATH": "/usr/bin:/bin"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, 3, completed.stdout)

    def test_launch_shell_syntax(self):
        completed = subprocess.run(
            ["bash", "-n", str(LAUNCH_PATH)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_launch_rejects_relative_log_path_with_exit_64(self):
        completed = subprocess.run(
            ["bash", str(LAUNCH_PATH), "0", "relative.log", "--", "true"],
            cwd=NPJ,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, 64, completed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
