"""S0-force 的最小路由契约：先于 model.py 编写。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODEL_PATH = Path(__file__).resolve().parents[1] / "model.py"


def load_model():
    if not MODEL_PATH.is_file():
        raise AssertionError(f"缺少待实现的路由模块：{MODEL_PATH}")
    spec = importlib.util.spec_from_file_location("luad_m1_force_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("无法加载 luad_m1_force/model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestS0ForceRoute(unittest.TestCase):
    def test_luad_route_table_when_forced_enabled(self):
        """强制开启时，LUAD 每一类场景/天然缺失都必须落到锁定分支。"""
        model = load_model()
        cases = [
            ("text_100", True, True, "m0real"),
            ("rna_100", True, True, "m1"),
            ("both_100", True, True, "m1"),
            ("none", False, True, "m1"),
            ("none", True, False, "upstream_combo"),
            ("none", False, False, "m1"),
            ("none", True, True, "upstream_combo"),
        ]
        for grid, rna_valid, text_valid, expected_route in cases:
            with self.subTest(grid=grid, rna_valid=rna_valid, text_valid=text_valid):
                routed = model.route_patient(
                    cancer="LUAD",
                    grid=grid,
                    rna_valid=rna_valid,
                    text_valid=text_valid,
                )
                self.assertEqual(routed["route"], expected_route)
                self.assertIs(routed["strategy0_enabled"], True)

    def test_non_luad_is_upstream_reuse_not_disabled_switch(self):
        """C2：非 LUAD 只复用上游组合，开关字段必须显式为不适用。"""
        model = load_model()
        routed = model.route_patient(
            cancer="BLCA",
            grid="rna_100",
            rna_valid=True,
            text_valid=True,
        )
        self.assertEqual(routed["route"], "upstream_combo")
        self.assertIsNone(routed["strategy0_enabled"])

    def test_force_freeze_rejects_false_or_missing_enabled(self):
        """冻结配置只能接受 JSON 布尔真，不能回退到 3.progress 的 valid 门禁。"""
        model = load_model()
        self.assertTrue(model.validate_frozen_force({"enabled": True}))
        for invalid in ({"enabled": False}, {}, {"enabled": 1}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    model.validate_frozen_force(invalid)


if __name__ == "__main__":
    unittest.main()

