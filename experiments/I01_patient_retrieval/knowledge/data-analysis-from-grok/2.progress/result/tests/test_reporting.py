import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "reporting.py"
EXPECTED_FILES = {
    "零训练改推理1-5实验结果.md",
    "seed单位-实验结果.md",
    "癌症为单位.md",
}


def load_reporting():
    if not MODULE_PATH.is_file():
        raise AssertionError(f"RED: reporting module is missing: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("zero_train_reporting", MODULE_PATH)
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
        "rules": ["rule1", "rule2", "rule3", "rule4", "rule5"],
        "numerics": {"logit_atol": 1e-6},
    }


def make_selection():
    selected = {}
    protocols = ["rule1", "rule2", "rule3", "rule4", "rule5", "combo"]
    for index, protocol in enumerate(protocols):
        selected[protocol] = {
            "protocol": protocol,
            "candidate_id": f"valid-candidate-{index:02d}",
            "enabled_rules": [index + 1] if index < 5 else [1, 2, 3, 4, 5],
            "lambda": 0.25 if protocol in {"rule3", "combo"} else 1.0,
            "alpha": 0.5 if protocol in {"rule4", "combo"} else 0.0,
            "w": 0.2 if protocol in {"rule5", "combo"} else 1.0,
            "ucec_exception": protocol in {"rule1", "combo"},
        }
    candidates = []
    for index in range(58):
        if index < len(protocols):
            spec = selected[protocols[index]]
        else:
            spec = {
                "protocol": "combo",
                "candidate_id": f"valid-candidate-{index:02d}",
                "enabled_rules": [1, 2, 3, 4, 5],
                "lambda": 0.5,
                "alpha": 1.0,
                "w": 0.3,
                "ucec_exception": False,
            }
        candidates.append(
            {
                "protocol": spec["protocol"],
                "candidate_id": spec["candidate_id"],
                "enabled_rules": spec["enabled_rules"],
                "raw_mean": 0.50 + index / 1000,
                "routed_mean": 0.49 + index / 1000,
                "mean_delta_m1": -0.01,
                "mean_delta_m0real": -0.02,
                "feasible_vs_both": False,
                "ucec_exception_enabled": spec["ucec_exception"],
                "lambda": spec["lambda"],
                "alpha": spec["alpha"],
                "w": spec["w"],
            }
        )
    return {"selected": selected, "candidates": candidates, "schema_version": 1}


def make_test_rows(config, selection):
    identities = {
        protocol: spec["candidate_id"] for protocol, spec in selection["selected"].items()
    }
    identities.update({name: name for name in ("retrieval", "m1", "m0real")})
    rows = []
    for protocol, candidate_id in identities.items():
        for cancer in config["cancers"]:
            for seed in config["seeds"]:
                for grid in config["grids"]:
                    if protocol == "combo":
                        value = 0.70 if seed == 123 else 0.62
                        if cancer == "BLCA" and seed == 123 and grid == "none":
                            value = 0.60000049
                    elif protocol == "m1":
                        value = 0.69 if seed == 123 else 0.60
                        if cancer == "BLCA" and seed == 123 and grid == "none":
                            value = 0.60000041
                    elif protocol == "m0real":
                        value = 0.68 if seed == 123 else 0.59
                        if cancer == "BLCA" and seed == 123 and grid == "none":
                            value = 0.50
                        if cancer == "BRCA" and seed == 132 and grid == "rna_100":
                            value = 0.62
                    elif protocol == "retrieval":
                        value = 0.61
                    else:
                        value = 0.615 + int(protocol[-1]) / 1000
                    rows.append(
                        {
                            "split": "test",
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
                            "run_fingerprint": "one-frozen-test-batch",
                            "synthetic": True,
                        }
                    )
    return rows


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reporting = load_reporting()

    def setUp(self):
        self.config = make_config()
        self.selection = make_selection()

    def test_unfinished_status_requires_no_rows_and_renders_three_full_empty_tables(self):
        reports = self.reporting.render_reports(
            [], self.selection, self.config, status="blocked", blocker="等待正式授权"
        )
        self.assertEqual(set(reports), EXPECTED_FILES)
        for markdown in reports.values():
            self.assertIn(self.config["protocol_id"], markdown)
            self.assertIn("未跑", markdown)
            self.assertIn("等待正式授权", markdown)
            self.assertEqual(markdown.count("| 未跑 |"), 100)
            self.assertNotIn("synthetic", markdown.lower())

        with self.assertRaises(ValueError):
            self.reporting.render_reports(
                [{}], self.selection, self.config, status="blocked", blocker="x"
            )

    def test_completed_reports_cover_locked_sections_raw_ties_and_all_valid_candidates(self):
        rows = make_test_rows(self.config, self.selection)
        reports = self.reporting.render_reports(
            rows, self.selection, self.config, status="completed"
        )
        self.assertEqual(set(reports), EXPECTED_FILES)
        for markdown in reports.values():
            self.assertIn(self.config["protocol_id"], markdown)
            self.assertIn("none", markdown)
            self.assertIn("天然缺失", markdown)
            self.assertIn("探索性", markdown)
            self.assertIn("不能证明检索机制", markdown)
            self.assertIn("one-frozen-test-batch", markdown)

        root = reports["零训练改推理1-5实验结果.md"]
        self.assertIn("75格人工缺失", root)
        self.assertIn("五个单点", root)
        self.assertIn("最差场景", root)
        self.assertIn("valid全部58个候选", root)
        for index in range(58):
            self.assertIn(f"valid-candidate-{index:02d}", root)
        rule2_line = next(line for line in root.splitlines() if line.startswith("| rule2 |"))
        self.assertTrue(rule2_line.endswith("| 不适用 |"), rule2_line)
        rule1_line = next(line for line in root.splitlines() if line.startswith("| rule1 |"))
        self.assertTrue(rule1_line.endswith("| 启用 |"), rule1_line)

        seed = reports["seed单位-实验结果.md"]
        self.assertIn("绝对 C-index 最高", seed)
        self.assertIn("相对两条基线平均 Δ 最大", seed)
        cancer = reports["癌症为单位.md"]
        self.assertIn("癌种绝对 C-index 最高", cancer)
        self.assertIn("癌种相对两条基线平均 Δ 最大", cancer)
        self.assertIn("癌种×场景绝对 C-index 最高", cancer)

        precise_row = next(
            line
            for line in seed.splitlines()
            if line.startswith("| BLCA | none |") and "0.600000" in line
        )
        self.assertIn("<strong>0.600000 ★</strong>", precise_row)
        self.assertIn("+0.000000", precise_row)

    def test_completed_rejects_missing_mixed_batch_and_provenance_mismatch(self):
        rows = make_test_rows(self.config, self.selection)
        bad_sets = [copy.deepcopy(rows[:-1])]
        mixed = copy.deepcopy(rows)
        mixed[0]["run_fingerprint"] = "other-batch"
        bad_sets.append(mixed)
        bad_hash = copy.deepcopy(rows)
        bad_hash[0]["checkpoint_sha256"] = "other-sha"
        bad_sets.append(bad_hash)
        bad_n = copy.deepcopy(rows)
        bad_n[0]["n_patients"] += 1
        bad_sets.append(bad_n)
        reused = copy.deepcopy(rows)
        for row in reused:
            if row["cancer"] == "BLCA" and row["seed"] == 132:
                row["checkpoint_sha256"] = "sha-BLCA-123"
        bad_sets.append(reused)
        negative_diff = copy.deepcopy(rows)
        negative_diff[0]["complete_max_logit_abs_diff"] = -1e-7
        bad_sets.append(negative_diff)
        checked_over_total = copy.deepcopy(rows)
        checked_over_total[0]["n_complete_checked"] = checked_over_total[0]["n_patients"] + 1
        bad_sets.append(checked_over_total)
        inconsistent_checked = copy.deepcopy(rows)
        inconsistent_checked[0]["n_complete_checked"] = 0
        inconsistent_checked[0]["complete_max_logit_abs_diff"] = None
        bad_sets.append(inconsistent_checked)
        inconsistent_diff = copy.deepcopy(rows)
        inconsistent_diff[0]["complete_max_logit_abs_diff"] = 5e-7
        bad_sets.append(inconsistent_diff)

        for bad_rows in bad_sets:
            with self.subTest(rows=len(bad_rows)):
                with self.assertRaises(ValueError):
                    self.reporting.render_reports(
                        bad_rows, self.selection, self.config, status="completed"
                    )

    def test_completed_rejects_selected_not_bound_to_valid_candidate_ledger(self):
        rows = make_test_rows(self.config, self.selection)
        missing_id = copy.deepcopy(self.selection)
        missing_id["selected"]["rule2"]["candidate_id"] = "not-in-valid-ledger"
        bad_parameter = copy.deepcopy(self.selection)
        bad_parameter["selected"]["rule3"]["lambda"] = 0.75
        bad_exception = copy.deepcopy(self.selection)
        bad_exception["selected"]["combo"]["ucec_exception"] = False

        for bad_selection in (missing_id, bad_parameter, bad_exception):
            bad_rows = make_test_rows(self.config, bad_selection)
            with self.subTest(candidate=bad_selection["selected"]):
                with self.assertRaises(ValueError):
                    self.reporting.render_reports(
                        bad_rows, bad_selection, self.config, status="completed"
                    )


if __name__ == "__main__":
    unittest.main()
