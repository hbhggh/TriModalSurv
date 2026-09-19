"""strategy0 报告汇总只按完整 100 格，且胜率严格比较两基线。"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "strategy0_reporting.py"
CANCERS = ("BLCA", "BRCA", "LGG", "LUAD", "UCEC")
SEEDS = (123, 132, 213, 231, 321)
GRIDS = ("none", "rna_100", "text_100", "both_100")


def load_module():
    if not MODULE.is_file():
        raise AssertionError("RED: 缺少 strategy0_reporting.py")
    spec = importlib.util.spec_from_file_location("strategy0_reporting_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rows():
    result = []
    for cancer in CANCERS:
        for seed in SEEDS:
            for grid in GRIDS:
                # BRCA/LGG/UCEC 以严格优势胜，LUAD/BLCA 不胜：应返回3/5。
                combo = 0.70 if cancer in {"BRCA", "LGG", "UCEC"} else 0.60
                for protocol, value in (("strategy0", combo), ("m1", 0.65), ("m0real", 0.64)):
                    result.append({
                        "protocol": protocol, "candidate_id": protocol, "split": "test",
                        "cancer": cancer, "seed": seed, "grid": grid, "c_index_b": value,
                        "n_patients": 10, "checkpoint_sha256": f"sha-{cancer}-{seed}",
                        "n_complete_checked": 0 if grid != "none" else 10,
                        "complete_max_logit_abs_diff": None if grid != "none" else 0.0,
                        "complete_logit_atol": 1e-6, "run_fingerprint": "test-frozen",
                    })
    return result


class Strategy0ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_module()

    def test_summary_keeps_none_in_100_grid_main_metric_and_reports_strict_three_of_five(self):
        summary = self.core.summarize(rows(), cancers=CANCERS, seeds=SEEDS, grids=GRIDS)
        self.assertEqual(summary["main_n"], 100)
        self.assertEqual(summary["artificial_n"], 75)
        self.assertEqual(summary["wins"], 3)
        self.assertEqual(summary["non_wins"], ["BLCA", "LUAD"])
        self.assertEqual(summary["cancer_wins"]["LUAD"], False)

    def test_missing_one_cell_refuses_to_create_a_five_seed_conclusion(self):
        incomplete = rows()
        incomplete.pop()
        with self.assertRaisesRegex(ValueError, "exactly 300"):
            self.core.summarize(incomplete, cancers=CANCERS, seeds=SEEDS, grids=GRIDS)


if __name__ == "__main__":
    unittest.main()
