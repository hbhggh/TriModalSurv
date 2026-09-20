import copy
import importlib.util
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "selection.py"


def load_selection():
    if not MODULE_PATH.is_file():
        raise AssertionError(f"RED: selection module is missing: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("zero_train_selection", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_config():
    return {
        "protocol_id": "patient-fixed-padmask-v2-infer-rules1to5-v1",
        "cancers": ["BLCA", "BRCA", "LGG", "LUAD", "UCEC"],
        "seeds": [123, 132, 213, 231, 321],
        "grids": ["none", "rna_100", "text_100", "both_100"],
        "rules": [
            "01_text100_skip_compensate",
            "02_wsi_meanpool_key",
            "03_shrinkage_lambda",
            "04_wsi_rna_joint_sim",
            "05_imputed_token_downweight",
        ],
        "search": {
            "lambda_grid": [0.0, 0.25, 0.5, 0.75, 1.0],
            "alpha_grid": [0.5, 1.0, 2.0],
            "weight_grid": [0.2, 0.3, 0.5],
        },
        "numerics": {"logit_atol": 1e-6},
    }


def metric_row(protocol, candidate_id, cancer, seed, grid, value, split="valid"):
    return {
        "split": split,
        "protocol": protocol,
        "candidate_id": candidate_id,
        "cancer": cancer,
        "seed": seed,
        "grid": grid,
        "c_index_b": value,
        "n_patients": 20 + len(cancer),
        "checkpoint_sha256": f"sha-{cancer}-{seed}",
        "n_complete_checked": 3,
        "complete_max_logit_abs_diff": 0.0,
        "complete_logit_atol": 1e-6,
        "synthetic": True,
    }


def all_rows(specs, config, value_fn=None):
    rows = []
    for spec in specs:
        for cancer in config["cancers"]:
            for seed in config["seeds"]:
                for grid in config["grids"]:
                    value = 0.58 if value_fn is None else value_fn(spec, cancer, seed, grid)
                    rows.append(
                        metric_row(
                            spec["protocol"], spec["candidate_id"], cancer, seed, grid, value
                        )
                    )
    return rows


def baseline_rows(config, values=None):
    values = values or {"retrieval": 0.57, "m1": 0.60, "m0real": 0.59}
    specs = [
        {
            "protocol": name,
            "candidate_id": name,
        }
        for name in ("retrieval", "m1", "m0real")
    ]
    return all_rows(specs, config, lambda spec, _c, _s, _g: values[spec["protocol"]])


class BuildCandidatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = load_selection()

    def test_builds_13_single_points_and_45_joint_points(self):
        config = make_config()
        first = self.selection.build_candidates(config)
        second = self.selection.build_candidates(copy.deepcopy(config))

        self.assertEqual(first, second)
        self.assertEqual(len(first), 58)
        self.assertEqual(len({item["candidate_id"] for item in first}), 58)
        self.assertEqual(sum(item["protocol"] == "combo" for item in first), 45)
        self.assertEqual(sum(item["protocol"] != "combo" for item in first), 13)

        by_protocol = {}
        for item in first:
            by_protocol.setdefault(item["protocol"], []).append(item)
            self.assertEqual(
                set(item),
                {
                    "protocol",
                    "candidate_id",
                    "enabled_rules",
                    "lambda",
                    "alpha",
                    "w",
                    "ucec_exception",
                },
            )
        self.assertEqual(
            [len(by_protocol[name]) for name in config["rules"]], [1, 1, 5, 3, 3]
        )
        self.assertTrue(by_protocol[config["rules"][0]][0]["ucec_exception"])
        self.assertTrue(all(item["ucec_exception"] for item in by_protocol["combo"]))


class ChooseValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = load_selection()

    def setUp(self):
        self.config = make_config()
        self.specs = self.selection.build_candidates(self.config)
        self.baselines = baseline_rows(self.config)

    def test_routes_rule1_text_cells_and_locks_ucec_exception_from_valid_only(self):
        rule1_protocol = self.config["rules"][0]

        def values(spec, cancer, _seed, grid):
            if spec["protocol"] == rule1_protocol and cancer == "UCEC" and grid == "text_100":
                return 0.61
            if spec["protocol"] == "combo" and cancer == "UCEC" and grid == "text_100":
                return 0.58
            if 1 in spec["enabled_rules"] and cancer != "UCEC" and grid == "text_100":
                return 0.99
            return 0.58

        result = self.selection.choose_validation(
            all_rows(self.specs, self.config, values), self.specs, self.baselines, self.config
        )

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(set(result["selected"]), set(self.config["rules"]) | {"combo"})
        self.assertTrue(result["selected"][rule1_protocol]["ucec_exception"])
        self.assertFalse(result["selected"]["combo"]["ucec_exception"])

        rule1_score = next(
            item
            for item in result["candidates"]
            if item["candidate_id"] == result["selected"][rule1_protocol]["candidate_id"]
        )
        combo_score = next(
            item
            for item in result["candidates"]
            if item["candidate_id"] == result["selected"]["combo"]["candidate_id"]
        )
        self.assertTrue(rule1_score["ucec_exception_enabled"])
        self.assertFalse(combo_score["ucec_exception_enabled"])
        self.assertLess(rule1_score["routed_mean"], 0.70)
        self.assertAlmostEqual(combo_score["ucec_text_routed_mean"], 0.59)

    def test_exact_ties_use_small_lambda_then_small_w_then_small_alpha(self):
        rows = all_rows(self.specs, self.config, lambda _spec, _c, _s, _g: 0.62)
        result = self.selection.choose_validation(rows, self.specs, self.baselines, self.config)

        self.assertEqual(result["selected"][self.config["rules"][2]]["lambda"], 0.0)
        self.assertEqual(result["selected"][self.config["rules"][3]]["alpha"], 0.5)
        self.assertEqual(result["selected"][self.config["rules"][4]]["w"], 0.2)
        combo = result["selected"]["combo"]
        self.assertEqual((combo["lambda"], combo["w"], combo["alpha"]), (0.0, 0.2, 0.5))

    def test_rejects_wrong_split_missing_duplicate_nonfinite_and_out_of_range(self):
        rows = all_rows(self.specs, self.config)
        mutations = []

        wrong_split = copy.deepcopy(rows)
        wrong_split[0]["split"] = "test"
        mutations.append(wrong_split)
        mutations.append(copy.deepcopy(rows[:-1]))
        duplicate = copy.deepcopy(rows)
        duplicate[-1] = copy.deepcopy(duplicate[0])
        mutations.append(duplicate)
        nonfinite = copy.deepcopy(rows)
        nonfinite[0]["c_index_b"] = math.nan
        mutations.append(nonfinite)
        out_of_range = copy.deepcopy(rows)
        out_of_range[0]["c_index_b"] = 1.01
        mutations.append(out_of_range)

        for bad_rows in mutations:
            with self.subTest(kind=len(bad_rows), first=bad_rows[0]["c_index_b"]):
                with self.assertRaises(ValueError):
                    self.selection.choose_validation(
                        bad_rows, self.specs, self.baselines, self.config
                    )

    def test_requires_three_complete_baselines_and_shared_cell_provenance(self):
        rows = all_rows(self.specs, self.config)
        with self.assertRaises(ValueError):
            self.selection.choose_validation(
                rows, self.specs, self.baselines[:-1], self.config
            )

        bad_baselines = copy.deepcopy(self.baselines)
        bad_baselines[0]["checkpoint_sha256"] = "different"
        with self.assertRaises(ValueError):
            self.selection.choose_validation(rows, self.specs, bad_baselines, self.config)

        bad_patients = copy.deepcopy(self.baselines)
        bad_patients[0]["n_patients"] += 1
        with self.assertRaises(ValueError):
            self.selection.choose_validation(rows, self.specs, bad_patients, self.config)

        reused_rows = copy.deepcopy(rows)
        reused_baselines = copy.deepcopy(self.baselines)
        for row in [*reused_rows, *reused_baselines]:
            if row["cancer"] == "BLCA" and row["seed"] == 132:
                row["checkpoint_sha256"] = "sha-BLCA-123"
        with self.assertRaises(ValueError):
            self.selection.choose_validation(
                reused_rows, self.specs, reused_baselines, self.config
            )

        checked_over_total = copy.deepcopy(self.baselines)
        checked_over_total[0]["n_complete_checked"] = checked_over_total[0]["n_patients"] + 1
        with self.assertRaises(ValueError):
            self.selection.choose_validation(rows, self.specs, checked_over_total, self.config)

        inconsistent_checked = copy.deepcopy(self.baselines)
        inconsistent_checked[0]["n_complete_checked"] = 0
        inconsistent_checked[0]["complete_max_logit_abs_diff"] = None
        with self.assertRaises(ValueError):
            self.selection.choose_validation(rows, self.specs, inconsistent_checked, self.config)

        inconsistent_diff = copy.deepcopy(self.baselines)
        inconsistent_diff[0]["complete_max_logit_abs_diff"] = 5e-7
        with self.assertRaises(ValueError):
            self.selection.choose_validation(rows, self.specs, inconsistent_diff, self.config)

    def test_rejects_a_candidate_set_other_than_the_locked_58_specs(self):
        shortened = self.specs[:-1]
        with self.assertRaises(ValueError):
            self.selection.choose_validation(
                all_rows(shortened, self.config), shortened, self.baselines, self.config
            )


if __name__ == "__main__":
    unittest.main()
