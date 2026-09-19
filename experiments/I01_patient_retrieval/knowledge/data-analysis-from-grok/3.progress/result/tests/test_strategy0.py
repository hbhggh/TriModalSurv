"""strategy0 路由契约；每条断言针对一个会改变评测语义的错误分支。"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "strategy0.py"


def load_strategy0():
    spec = importlib.util.spec_from_file_location("strategy0_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Strategy0RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODULE.is_file():
            raise AssertionError("RED: 缺少 strategy0 路由实现")
        # 保存为 staticmethod，避免 unittest 实例访问时隐式注入 self。
        cls.route = staticmethod(load_strategy0().route_patient)

    def test_luad_enabled_route_table(self):
        cases = [
            ("text_100", True, True, "m0real"),
            ("text_100", False, False, "m0real"),
            ("rna_100", True, True, "m1"),
            ("both_100", True, True, "m1"),
            ("none", False, True, "m1"),
            ("none", False, False, "m1"),
            ("none", True, False, "upstream_combo"),
            ("none", True, True, "upstream_combo"),
        ]
        for grid, rna_valid, text_valid, expected in cases:
            with self.subTest(grid=grid, rna=rna_valid, text=text_valid):
                self.assertEqual(
                    self.route("LUAD", grid, rna_valid, text_valid, enabled=True), expected
                )

    def test_disabled_switch_and_non_luad_never_change_upstream_combo(self):
        self.assertEqual(
            self.route("LUAD", "both_100", True, True, enabled=False), "upstream_combo"
        )
        self.assertEqual(
            self.route("BLCA", "rna_100", False, True, enabled=True), "upstream_combo"
        )

    def test_invalid_grid_and_non_boolean_validity_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "grid"):
            self.route("LUAD", "rna_50", True, True, enabled=True)
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.route("LUAD", "none", 1, True, enabled=True)


if __name__ == "__main__":
    unittest.main()
