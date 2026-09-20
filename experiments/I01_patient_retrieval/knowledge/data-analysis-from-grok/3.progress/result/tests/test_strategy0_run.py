"""strategy0 冻结规则：只允许 valid 的严格优势开启，不接受四舍五入平局。"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "strategy0_run.py"


def load_module():
    if not MODULE.is_file():
        raise AssertionError("RED: 缺少 strategy0_run.py")
    spec = importlib.util.spec_from_file_location("strategy0_run_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Strategy0FreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_module()

    def test_valid_switch_is_disabled_for_the_observed_lower_b_score(self):
        freeze = self.core.freeze_valid_switch(0.65404181184669, 0.6452264808362369)
        self.assertFalse(freeze["enabled"])
        self.assertAlmostEqual(freeze["b_minus_a"], -0.008815331010453065)

    def test_strict_improvement_not_rounded_display_controls_switch(self):
        self.assertTrue(self.core.freeze_valid_switch(0.6, 0.6000000000000001)["enabled"])
        self.assertFalse(self.core.freeze_valid_switch(0.6, 0.6)["enabled"])


if __name__ == "__main__":
    unittest.main()
