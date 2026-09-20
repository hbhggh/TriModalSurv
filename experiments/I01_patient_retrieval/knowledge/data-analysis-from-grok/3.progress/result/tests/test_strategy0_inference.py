"""strategy0 批内分流：先证明患者位置不会错位，再接原推理实现。"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "strategy0_inference.py"
UPSTREAM = ROOT.parent.parent / "2.progress" / "result"
BASE_MODEL = Path("/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/model.py")


def load_module():
    if not MODULE.is_file():
        raise AssertionError("RED: 缺少 strategy0_inference.py")
    spec = importlib.util.spec_from_file_location("strategy0_inference_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_bank_and_batch(*, rna_valid: bool, text_valid: bool):
    tile = lambda value: np.tile(np.asarray(value, dtype=np.float32), (128, 1))
    features = {
        "img": {"A": tile([3, 1]), "B": tile([1, 3]), "C": tile([-1, -1])},
        "rna": {pid: np.tile(np.asarray(value, np.float32), (2, 1)) for pid, value in {
            "A": [1, 0], "B": [0, 1], "C": [-1, -1]}.items()},
        "text": {pid: np.full((3, 2), value, np.float32) for pid, value in {
            "A": 10, "B": 20, "C": 30}.items()},
    }
    bank_module = load_path("_strategy0_base_bank", BASE_MODEL)
    bank = bank_module.FixedPatientBank(
        "LUAD", {"train": ["A", "B", "C"], "valid": ["V"], "test": ["Q"]}, features
    )
    raw = {
        "img": tile([4, 1])[None].copy(), "img_valid": np.asarray([True]),
        "rna": (np.tile(np.asarray([0, 1], np.float32), (2, 1)) if rna_valid else np.zeros((2, 2), np.float32))[None],
        "rna_valid": np.asarray([rna_valid]),
        "text": (np.full((3, 2), 7, np.float32) if text_valid else np.zeros((3, 2), np.float32))[None],
        "text_valid": np.asarray([text_valid]),
    }
    natural = {"rna": np.asarray([True]), "text": np.asarray([True])}
    return bank, raw, natural


def combo_spec():
    return {
        "protocol": "combo", "candidate_id": "combo-l1-a1-w0p5", "enabled_rules": [1, 2, 3, 4, 5],
        "lambda": 1.0, "alpha": 1.0, "w": 0.5, "ucec_exception": True,
    }


def baseline_spec(arm: str):
    return {"protocol": arm, "candidate_id": arm, "enabled_rules": [],
            "lambda": 1.0, "alpha": 0.0, "w": 1.0, "ucec_exception": False}


NUMERICS = {"norm_epsilon": 1e-12, "logit_atol": 1e-6, "logit_rtol": 0, "risk_clamp": 1e-6}


class Strategy0BatchRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_module()

    def test_luad_enabled_preserves_original_positions_for_m1_m0_and_combo(self):
        routes = self.core.partition_routes(
            "LUAD",
            "none",
            np.asarray([False, True, True, False]),
            np.asarray([True, False, True, False]),
            enabled=True,
        )
        self.assertEqual(routes, {
            "m1": [0, 3],
            "upstream_combo": [1, 2],
            "m0real": [],
        })

    def test_disabled_and_non_luad_are_single_original_combo_batch(self):
        validity = np.asarray([True, False, True])
        self.assertEqual(
            self.core.partition_routes("LUAD", "both_100", validity, validity, enabled=False),
            {"upstream_combo": [0, 1, 2], "m1": [], "m0real": []},
        )
        self.assertEqual(
            self.core.partition_routes("BLCA", "rna_100", validity, validity, enabled=True),
            {"upstream_combo": [0, 1, 2], "m1": [], "m0real": []},
        )

    def test_invalid_validity_vectors_are_rejected_before_any_model_call(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            self.core.partition_routes(
                "LUAD", "none", np.asarray([True]), np.asarray([True, False]), enabled=True
            )
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.core.partition_routes(
                "LUAD", "none", np.asarray([1, 0]), np.asarray([True, False]), enabled=True
            )

    def test_enabled_luad_m1_route_is_byte_identical_to_direct_fixed_m1_preparation(self):
        bank, raw, natural = make_bank_and_batch(rna_valid=False, text_valid=True)
        upstream = load_path("_strategy0_upstream_inference", UPSTREAM / "inference.py")
        actual = self.core.prepare_strategy0_batch(
            upstream.prepare_batch, baseline_spec, bank, ["Q"], raw, natural, combo_spec(),
            grid="rna_100", query_split="test", numerics=NUMERICS, enabled=True,
        )
        expected = upstream.prepare_batch(
            bank, ["Q"], raw, natural, baseline_spec("m1"),
            grid="rna_100", query_split="test", numerics=NUMERICS,
        )
        for key in expected[0]:
            np.testing.assert_array_equal(actual[0][key], expected[0][key])
        np.testing.assert_array_equal(actual[2], expected[2])
        self.assertEqual(actual[1][0]["strategy0_route"], "m1")
        self.assertEqual(actual[1][0]["route"], expected[1][0]["route"])

    def test_enabled_luad_text100_route_is_byte_identical_to_direct_fixed_m0(self):
        bank, raw, natural = make_bank_and_batch(rna_valid=True, text_valid=False)
        upstream = load_path("_strategy0_upstream_inference_m0", UPSTREAM / "inference.py")
        actual = self.core.prepare_strategy0_batch(
            upstream.prepare_batch, baseline_spec, bank, ["Q"], raw, natural, combo_spec(),
            grid="text_100", query_split="test", numerics=NUMERICS, enabled=True,
        )
        expected = upstream.prepare_batch(
            bank, ["Q"], raw, natural, baseline_spec("m0real"),
            grid="text_100", query_split="test", numerics=NUMERICS,
        )
        for key in expected[0]:
            np.testing.assert_array_equal(actual[0][key], expected[0][key])
        np.testing.assert_array_equal(actual[2], expected[2])
        self.assertEqual(actual[1][0]["strategy0_route"], "m0real")


if __name__ == "__main__":
    unittest.main()
