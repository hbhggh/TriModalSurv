"""零训练推理规则 1--5 的行为契约。"""
from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def _resolve_repo_root(result_root: Path, *, pythonpath: str | None = None) -> Path:
    """定位含原 I01 实现的仓库，不依赖交付目录固定深度。"""
    marker = Path("experiments/I01_patient_retrieval/model.py")
    candidates = []
    search_path = os.environ.get("PYTHONPATH", "") if pythonpath is None else pythonpath
    for raw in search_path.split(os.pathsep):
        if raw.strip():
            candidates.append(Path(raw).expanduser())

    config_path = Path(result_root) / "config.yaml"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        configured = config.get("paths", {}).get("repo_root")
        if configured:
            candidates.append(Path(configured).expanduser())

    resolved_result = Path(result_root).resolve()
    candidates.extend((resolved_result, *resolved_result.parents))
    checked = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in checked:
            continue
        checked.append(resolved)
        if (resolved / marker).is_file():
            return resolved
    raise FileNotFoundError(
        "无法定位仓库根；请设置 PYTHONPATH 或 config.paths.repo_root: "
        + ", ".join(str(path) for path in checked)
    )


REPO = _resolve_repo_root(ROOT)
INFERENCE_PATH = ROOT / "inference.py"
BASE_MODEL_PATH = REPO / "experiments/I01_patient_retrieval/model.py"


def load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"无法构造模块: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture(cancer: str = "BLCA"):
    tile = lambda value: np.tile(np.asarray(value, dtype=np.float32), (128, 1))
    features = {
        "img": {"A": tile([3, 1]), "B": tile([1, 3]), "C": tile([-1, -1])},
        "rna": {
            "A": np.tile(np.asarray([1, 0], np.float32), (2, 1)),
            "B": np.tile(np.asarray([0, 1], np.float32), (2, 1)),
            "C": np.tile(np.asarray([-1, -1], np.float32), (2, 1)),
        },
        "text": {
            "A": np.full((3, 2), 10, np.float32),
            "B": np.full((3, 2), 20, np.float32),
            "C": np.full((3, 2), 30, np.float32),
        },
    }
    splits = {"train": ["C", "B", "A"], "valid": ["V"], "test": ["Q", "R"]}
    base = load_path("_rules_base_bank", BASE_MODEL_PATH)
    bank = base.FixedPatientBank(cancer, splits, features)
    query = tile([4, 1])
    return bank, features, query


def raw_batch(query, *, rna_valid=True, text_valid=False, query_rna=None):
    rna = np.tile(np.asarray([0, 1], np.float32), (2, 1)) if query_rna is None else query_rna
    return {
        "img": query[None].copy(),
        "img_valid": np.asarray([True]),
        "text": np.zeros((1, 3, 2), np.float32),
        "text_valid": np.asarray([text_valid]),
        "rna": rna[None].copy(),
        "rna_valid": np.asarray([rna_valid]),
    }


def candidate(enabled, *, protocol="candidate", lambda_=1.0, alpha=0.0, w=1.0,
              ucec_exception=False):
    return {
        "protocol": protocol,
        "candidate_id": "synthetic-test",
        "enabled_rules": list(enabled),
        "lambda": lambda_,
        "alpha": alpha,
        "w": w,
        "ucec_exception": ucec_exception,
    }


NUMERICS = {"norm_epsilon": 1e-12, "logit_atol": 1e-6, "logit_rtol": 0,
            "risk_clamp": 1e-6}


class RulesNumpyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not INFERENCE_PATH.is_file():
            raise AssertionError("推理核心 inference.py 尚不存在")
        cls.core = load_path("_rules_inference", INFERENCE_PATH)

    def prepare(self, bank, raw, natural, spec, *, grid="text_100", split="test"):
        return self.core.prepare_batch(
            bank, ["Q"], raw, natural, spec, grid=grid,
            query_split=split, numerics=NUMERICS,
        )

    def test_repo_resolution_uses_pythonpath_without_assuming_result_depth(self):
        with TemporaryDirectory() as temp_dir:
            shallow_result = Path(temp_dir) / "mirror/result"
            shallow_result.mkdir(parents=True)
            resolved = _resolve_repo_root(shallow_result, pythonpath=str(REPO))
            self.assertEqual(resolved, REPO.resolve())

            (shallow_result / "config.yaml").write_text(
                json.dumps({"paths": {"repo_root": str(REPO)}}), encoding="utf-8"
            )
            self.assertEqual(
                _resolve_repo_root(shallow_result, pythonpath=""), REPO.resolve()
            )

        with TemporaryDirectory() as temp_dir:
            isolated_result = Path(temp_dir) / "result"
            isolated_result.mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "PYTHONPATH.*repo_root"):
                _resolve_repo_root(isolated_result, pythonpath="")

    def test_dynamic_rule_loader_registers_real_modules(self):
        expected = {
            1: "should_skip_compensation",
            2: "meanpool_wsi_score",
            3: "shrink_feature",
            4: "joint_similarity",
            5: "build_pool_weights",
        }
        for number, symbol in expected.items():
            with self.subTest(rule=number):
                module = self.core.load_rule(number)
                self.assertIs(sys.modules[module.__name__], module)
                self.assertTrue(callable(getattr(module, symbol)))

    def test_non_blocking_is_an_optional_keyword_only_forward_contract(self):
        public = inspect.signature(self.core.forward_with_pool_weights).parameters
        weighted = inspect.signature(self.core.load_rule(5).weighted_forward).parameters
        for parameters in (public, weighted):
            self.assertIn("non_blocking", parameters)
            self.assertEqual(parameters["non_blocking"].kind, inspect.Parameter.KEYWORD_ONLY)
            self.assertIs(parameters["non_blocking"].default, False)

    def test_disabled_candidate_is_exact_original_retrieval_and_split_is_explicit(self):
        bank, _, query = fixture()
        raw = raw_batch(query)
        natural = {"rna": np.asarray([True]), "text": np.asarray([True])}
        before = copy.deepcopy(raw)
        inputs, audit, weights = self.prepare(
            bank, raw, natural, candidate([], w=0.2), split="test"
        )
        expected, masks, records = bank.compensate(
            ["Q"], raw["img"], {mm: raw[mm] for mm in ("rna", "text")},
            {mm: raw[f"{mm}_valid"] for mm in ("rna", "text")},
            "retrieval", query_split="test",
        )
        np.testing.assert_array_equal(inputs["text"], expected["text"])
        np.testing.assert_array_equal(inputs["text_valid"], masks["text"])
        self.assertEqual(audit[0]["donor_id"], records[0]["donor_id"])
        np.testing.assert_array_equal(weights, [[1.0, 1.0, 1.0]])
        for key in raw:
            np.testing.assert_array_equal(raw[key], before[key])

    def test_rule1_skips_entire_text100_scenario_except_locked_ucec_exception(self):
        bank, _, query = fixture("BLCA")
        raw = raw_batch(query, rna_valid=False, text_valid=False)
        natural = {"rna": np.asarray([False]), "text": np.asarray([True])}
        inputs, audit, weights = self.prepare(bank, raw, natural, candidate([1]))
        self.assertFalse(inputs["rna_valid"][0])
        self.assertFalse(inputs["text_valid"][0])
        self.assertIsNone(audit[0]["donor_id"])
        self.assertEqual(audit[0]["route"], "rule1_m0real")
        np.testing.assert_array_equal(weights, [[1.0, 0.0, 0.0]])

        ucec, _, query = fixture("UCEC")
        inputs, audit, _ = self.prepare(
            ucec, raw_batch(query, rna_valid=False, text_valid=False), natural,
            candidate([1], ucec_exception=True),
        )
        self.assertTrue(inputs["rna_valid"][0] and inputs["text_valid"][0])
        self.assertEqual(audit[0]["donor_id"], "A")

    def test_rule2_mean_key_is_permutation_invariant_and_rejects_own_degeneracy(self):
        bank, _, query = fixture()
        query[:64] = [5, 1]
        query[64:] = [3, 1]
        natural = {"rna": np.asarray([True]), "text": np.asarray([True])}
        _, first, _ = self.prepare(bank, raw_batch(query), natural, candidate([2]))
        _, second, _ = self.prepare(bank, raw_batch(query[::-1].copy()), natural, candidate([2]))
        self.assertEqual(first[0]["donor_id"], second[0]["donor_id"])
        self.assertAlmostEqual(first[0]["score_wsi"], second[0]["score_wsi"], places=14)

        # 展平签名不退化，但有效行 mean 恰等于 train mean；规则 2 必须单独报错。
        degenerate = query.copy()
        degenerate[:64] = [2, 1]
        degenerate[64:] = [0, 1]
        bank.validate_query("Q", degenerate, query_split="test")
        with self.assertRaisesRegex(ValueError, "meanpool.*norm"):
            self.prepare(bank, raw_batch(degenerate), natural, candidate([2]))

    def test_rule2_real_padding_preserves_cache_and_valid_row_permutation(self):
        bank, features, query = fixture()
        features = copy.deepcopy(features)
        features["img"]["A"][75:] = 0
        features["img"]["B"][124:] = 0
        base = load_path("_rules_base_bank_padding", BASE_MODEL_PATH)
        padded_bank = base.FixedPatientBank("BLCA", bank.splits, features)
        query[:48] = [5, 1]
        query[48:96] = [3, 1]
        query[96:] = 0
        permuted = query.copy()
        permuted[:96] = permuted[:96][::-1]
        cache_before = copy.deepcopy(features)
        query_before = query.copy()
        natural = {"rna": np.asarray([True]), "text": np.asarray([True])}

        inputs, first, _ = self.prepare(
            padded_bank, raw_batch(query), natural, candidate([2])
        )
        _, second, _ = self.prepare(
            padded_bank, raw_batch(permuted), natural, candidate([2])
        )
        self.assertEqual(first[0]["donor_id"], second[0]["donor_id"])
        self.assertAlmostEqual(first[0]["score_wsi"], second[0]["score_wsi"], places=14)
        self.assertEqual(first[0]["query_valid_rows"], 96)
        np.testing.assert_array_equal(inputs["img"][0], query_before)
        np.testing.assert_array_equal(query, query_before)
        for mm in cache_before:
            for patient_id in cache_before[mm]:
                np.testing.assert_array_equal(features[mm][patient_id], cache_before[mm][patient_id])

    def test_rule3_lambda_endpoints_and_both_missing_share_one_donor(self):
        bank, features, query = fixture()
        raw = raw_batch(query, rna_valid=False, text_valid=False)
        natural = {"rna": np.asarray([False]), "text": np.asarray([False])}
        zero, audit0, _ = self.prepare(
            bank, raw, natural, candidate([3], lambda_=0.0), grid="both_100"
        )
        np.testing.assert_allclose(zero["rna"][0], bank.means["rna"], rtol=0, atol=0)
        np.testing.assert_allclose(zero["text"][0], bank.means["text"], rtol=0, atol=0)
        one, audit1, _ = self.prepare(
            bank, raw, natural, candidate([3], lambda_=1.0), grid="both_100"
        )
        self.assertEqual(audit0[0]["donor_id"], audit1[0]["donor_id"])
        donor = audit1[0]["donor_id"]
        np.testing.assert_array_equal(one["rna"][0], features["rna"][donor])
        np.testing.assert_array_equal(one["text"][0], features["text"][donor])
        self.assertEqual(audit1[0]["imputed"], {"text": True, "rna": True})

    def test_rule3_extreme_scale_endpoints_are_exact_copies_with_requested_dtype(self):
        rule3 = self.core.load_rule(3)
        mean = np.asarray([1e20, -1e20], dtype=np.float64)
        donor = np.asarray([1.0, -1.0], dtype=np.float32)
        zero = rule3.shrink_feature(mean, donor, 0.0, output_dtype=np.float32)
        one = rule3.shrink_feature(mean, donor, 1.0, output_dtype=np.float32)
        self.assertEqual(zero.dtype, np.float32)
        self.assertEqual(one.dtype, np.float32)
        np.testing.assert_array_equal(zero, mean.astype(np.float32))
        np.testing.assert_array_equal(one, donor)

    def test_rule4_joint_score_uses_natural_query_rna_and_complete_donors(self):
        bank, features, query = fixture()
        natural = {"rna": np.asarray([True]), "text": np.asarray([True])}
        _, audit, _ = self.prepare(
            bank, raw_batch(query), natural, candidate([4], alpha=2.0)
        )
        self.assertEqual(audit[0]["donor_id"], "B")
        self.assertAlmostEqual(audit[0]["score_rna"], 1.0, places=14)

        features = copy.deepcopy(features)
        del features["text"]["B"]
        base = load_path("_rules_base_bank_no_b", BASE_MODEL_PATH)
        restricted = base.FixedPatientBank("BLCA", bank.splits, features)
        _, audit, _ = self.prepare(
            restricted, raw_batch(query), natural, candidate([4], alpha=2.0)
        )
        self.assertEqual(audit[0]["donor_id"], "A")
        self.assertEqual(audit[0]["candidate_count"], 2)

        # RNA 天然不可用时不得拿填值或零占位作查询，规则 4 退回原 WSI 检索。
        absent = {"rna": np.asarray([False]), "text": np.asarray([True])}
        _, audit, _ = self.prepare(
            bank, raw_batch(query, rna_valid=False, text_valid=False), absent,
            candidate([4], alpha=2.0),
        )
        self.assertEqual(audit[0]["donor_id"], "A")
        self.assertIsNone(audit[0]["score_rna"])

    def test_rule5_changes_only_final_pool_weights_not_boolean_masks(self):
        bank, _, query = fixture()
        raw = raw_batch(query)
        natural = {"rna": np.asarray([True]), "text": np.asarray([True])}
        inputs, audit, weights = self.prepare(bank, raw, natural, candidate([5], w=0.3))
        self.assertEqual(inputs["text_valid"].dtype, np.bool_)
        self.assertTrue(inputs["text_valid"][0])
        np.testing.assert_allclose(weights, [[1.0, 0.3, 1.0]], rtol=0, atol=1e-15)
        self.assertEqual(audit[0]["pool_weights"], [1.0, 0.3, 1.0])

        _, _, baseline_weights = self.prepare(
            bank, raw, natural, candidate([], protocol="retrieval", w=0.2)
        )
        np.testing.assert_array_equal(baseline_weights, [[1.0, 1.0, 1.0]])

    def test_mixed_natural_missing_batch_matches_patientwise_partitions(self):
        bank, _, query = fixture("UCEC")
        raw = {
            "img": np.stack([query, query]),
            "img_valid": np.asarray([True, True]),
            "text": np.zeros((2, 3, 2), np.float32),
            "text_valid": np.asarray([False, False]),
            "rna": np.stack([
                np.tile(np.asarray([0, 1], np.float32), (2, 1)),
                np.zeros((2, 2), np.float32),
            ]),
            "rna_valid": np.asarray([True, False]),
        }
        natural = {"rna": np.asarray([True, False]), "text": np.asarray([True, True])}
        spec = candidate(
            [1, 2, 3, 4, 5], lambda_=0.5, alpha=2.0, w=0.3,
            ucec_exception=True,
        )
        all_inputs, all_audit, all_weights = self.core.prepare_batch(
            bank, ["Q", "R"], raw, natural, spec, grid="text_100",
            query_split="test", numerics=NUMERICS,
        )
        parts = []
        for row, patient_id in enumerate(("Q", "R")):
            part_raw = {key: np.asarray(value)[row:row + 1].copy() for key, value in raw.items()}
            part_natural = {key: value[row:row + 1].copy() for key, value in natural.items()}
            parts.append(self.core.prepare_batch(
                bank, [patient_id], part_raw, part_natural, spec, grid="text_100",
                query_split="test", numerics=NUMERICS,
            ))
        for key in all_inputs:
            np.testing.assert_array_equal(
                all_inputs[key], np.concatenate([part[0][key] for part in parts], axis=0)
            )
        self.assertEqual(all_audit, [parts[0][1][0], parts[1][1][0]])
        np.testing.assert_array_equal(
            all_weights, np.concatenate([part[2] for part in parts], axis=0)
        )


class RulesTorchTests(unittest.TestCase):
    def test_w1_forward_matches_original_npjc(self):
        try:
            import torch
        except ModuleNotFoundError as error:
            self.fail(f"真实 NPJC parity 未执行：缺少 torch（禁止 skip）：{error}")
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        core = load_path("_rules_inference_torch", INFERENCE_PATH)
        from trimodalsurv.models.npjc import NPJC

        torch.manual_seed(7)
        modalities = {mm: SimpleNamespace(feature_dim=2) for mm in ("img", "text", "rna")}
        model = NPJC(
            "cpu", modalities, hidden_size=8, pred_dim=4, dropout_rate=0.0,
            mlp_ratio=2, n_backbone=1, n_head=2, cancer_types=["BLCA"], compensator=None,
        ).eval()
        state_before = {key: value.detach().clone() for key, value in model.state_dict().items()}
        rng = np.random.default_rng(4)
        inputs = {
            "img": rng.normal(size=(2, 128, 2)).astype(np.float32),
            "img_valid": np.ones(2, dtype=bool),
            "text": rng.normal(size=(2, 3, 2)).astype(np.float32),
            "text_valid": np.asarray([True, False]),
            "rna": rng.normal(size=(2, 2, 2)).astype(np.float32),
            "rna_valid": np.ones(2, dtype=bool),
        }
        tensors = {key: torch.as_tensor(value, dtype=torch.float32) for key, value in inputs.items()}
        with torch.inference_mode():
            expected = model(tensors, cancer_type=["BLCA", "BLCA"])[0].cpu().numpy()
        weights = np.asarray([[1, 1, 1], [1, 0, 1]], dtype=np.float64)
        to_calls = []
        original_as_tensor = torch.as_tensor

        class ToProxy:
            def __init__(self, tensor):
                self.tensor = tensor

            def to(self, *args, **kwargs):
                to_calls.append(dict(kwargs))
                return self.tensor.to(*args, **kwargs)

        def as_tensor_spy(value, *args, **kwargs):
            tensor = original_as_tensor(value, *args, **kwargs)
            return tensor if kwargs else ToProxy(tensor)

        with patch.object(torch, "as_tensor", side_effect=as_tensor_spy):
            actual = core.forward_with_pool_weights(
                model, inputs, "BLCA", "cpu", weights, non_blocking=True
            )
        self.assertEqual(len(to_calls), len(inputs))
        self.assertTrue(all(call.get("non_blocking") is True for call in to_calls))
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-6)
        downweighted = weights.copy()
        downweighted[0, 1] = 0.3
        changed = core.forward_with_pool_weights(model, inputs, "BLCA", "cpu", downweighted)
        self.assertFalse(np.allclose(changed[0], actual[0], rtol=0, atol=1e-7))
        for key, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, state_before[key]), key)


if __name__ == "__main__":
    unittest.main()
