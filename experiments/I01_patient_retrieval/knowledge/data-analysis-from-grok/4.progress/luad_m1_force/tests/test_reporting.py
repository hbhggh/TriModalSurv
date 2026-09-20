"""报告的强制声称边界：防止将 S0-force 写成检索机制成立。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


REPORTING_PATH = Path(__file__).resolve().parents[1] / "reporting.py"


def load_reporting():
    if not REPORTING_PATH.is_file():
        raise AssertionError(f"缺少待实现的报告模块：{REPORTING_PATH}")
    spec = importlib.util.spec_from_file_location("luad_m1_force_reporting", REPORTING_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("无法加载 luad_m1_force/reporting.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestForcedDisclosure(unittest.TestCase):
    def test_disclosure_covers_leakage_fixed_baselines_and_non_claim(self):
        """C7–C9：所有报告开头必须同时包含三类限制，而非只写泛化警告。"""
        reporting = load_reporting()
        freeze = {
            "a_mean": 0.65404181184669,
            "b_mean": 0.6452264808362369,
            "b_minus_a": -0.008815331010453065,
            "enabled": True,
            "current_wins": 2,
            "luad_delta_m1": 0.0000351,
            "none_m1_route_count": 0,
        }
        text = reporting.mandatory_disclosure(freeze)
        for required in (
            "valid B−A=-0.008815",
            "强制启用",
            "test 泄漏",
            "rna_100",
            "both_100",
            "m1",
            "text_100",
            "m0real",
            "2/5仅为探索性反事实",
            "+0.000035",
            "触发0次",
            "患者检索机制成立",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("4/5", text)
        self.assertNotIn("3/5", text)

    def test_rename_removes_impossible_disabled_branch_and_static_target(self):
        """强制开启协议不能保留“关闭时”或写死4/5目标的历史结论。"""
        reporting = load_reporting()
        legacy = "\n".join([
            "- 执行验收与效果目标分开：即使文件、哈希和矩阵完整，`4/5`目标未达也必须如实写为未达。",
            "- strategy0关闭时，LUAD沿用冻结组合；不得把上游复用误写成新的路由收益。",
        ])
        text = reporting._rename_strategy0(legacy)
        self.assertNotIn("关闭时", text)
        self.assertNotIn("4/5", text)
        self.assertIn("enabled=true", text)


if __name__ == "__main__":
    unittest.main()
