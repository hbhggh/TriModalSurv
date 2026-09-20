"""S0-force 冻结与非 LUAD 复用审计的测试先行契约。"""

from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest


RUN_PATH = Path(__file__).resolve().parents[1] / "run.py"


def load_run():
    if not RUN_PATH.is_file():
        raise AssertionError(f"缺少待实现的运行封装：{RUN_PATH}")
    spec = importlib.util.spec_from_file_location("luad_m1_force_run", RUN_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("无法加载 luad_m1_force/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestS0ForceFreezeAndReuse(unittest.TestCase):
    def test_choose_shared_gpu_requires_two_low_utilization_and_memory_samples(self):
        """防止共享门禁误选一次低负载、但第二次繁忙或显存不足的 GPU。"""
        core = load_run()
        samples = {
            0: iter(((0.0, 8191), (0.0, 8191))),
            1: iter(((74.9, 18000), (74.8, 17900))),
        }

        def read_sample(gpu_id):
            return next(samples[gpu_id])

        self.assertTrue(hasattr(core, "choose_shared_gpu"), "缺少共享 GPU 双采样门禁")
        gpu_id, record = core.choose_shared_gpu(
            [0, 1], max_utilization_percent=75.0, min_free_memory_mib=8192,
            sample_reader=read_sample,
        )
        self.assertEqual(gpu_id, 1)
        self.assertEqual(record, [(74.9, 18000), (74.8, 17900)])

    def test_choose_shared_gpu_rejects_exact_75_percent_and_insufficient_memory(self):
        """防止把边界 75% 或低于容量阈值的卡误当作用户允许的共享卡。"""
        core = load_run()
        samples = {
            0: iter(((75.0, 30000), (0.0, 30000))),
            1: iter(((0.0, 8191), (0.0, 8191))),
        }

        def read_sample(gpu_id):
            return next(samples[gpu_id])

        with self.assertRaises(RuntimeError):
            core.choose_shared_gpu(
                [0, 1], max_utilization_percent=75.0, min_free_memory_mib=8192,
                sample_reader=read_sample,
            )

    def test_shared_runtime_disables_only_idle_pid_guard_and_preserves_input_config(self):
        """防止共享门禁仍触发上游 PID 拒绝，或原地修改上游运行配置。"""
        core = load_run()
        upstream = {"runtime": {"device": "cpu", "gpu_id": None, "require_idle_gpu": True}}
        profile = {"device": "cuda", "gpu_ids": [1]}
        policy = {
            "utilization_lt_percent": 75.0,
            "min_free_memory_mib": 8192,
            "consecutive_samples": 2,
            "sample_interval_seconds": 0.0,
        }
        samples = iter(((0.0, 18000), (0.0, 17900)))

        configured, record = core.configure_shared_gpu_runtime(
            upstream, profile, policy, sample_reader=lambda _gpu_id: next(samples),
        )
        self.assertEqual(upstream, {"runtime": {"device": "cpu", "gpu_id": None, "require_idle_gpu": True}})
        self.assertEqual(configured["runtime"], {"device": "cuda", "gpu_id": 1, "require_idle_gpu": False})
        self.assertEqual(record["gpu_gate"], "USER_AUTHORIZED_TWO_SHARED_GPU_SAMPLES")
        self.assertEqual(record["samples"], [(0.0, 18000), (0.0, 17900)])

    def test_force_freeze_records_negative_valid_without_veto(self):
        """valid B<A 必须原样留档，但绝不能关闭 S0-force。"""
        core = load_run()
        freeze = core.force_freeze(0.65404181184669, 0.6452264808362369)
        self.assertIs(freeze["enabled"], True)
        self.assertAlmostEqual(freeze["b_minus_a"], -0.008815331010453065)
        self.assertIn("强制启用", freeze["decision_rule"])
        self.assertIn("valid", freeze["decision_rule"])

    def test_non_luad_reuse_is_marked_not_applicable_not_false(self):
        """C2：上游复用行没有开启/关闭语义，必须显式标记 null。"""
        core = load_run()
        original = {"cancer": "BLCA", "protocol": "strategy0", "candidate_id": "strategy0"}
        result = core.annotate_reused_combo_row(original)
        self.assertIsNone(result["strategy0_enabled"])
        self.assertEqual(result["strategy0_route"], "upstream_combo")
        self.assertEqual(original, {"cancer": "BLCA", "protocol": "strategy0", "candidate_id": "strategy0"})

    def test_luad_cannot_be_relabelled_as_non_luad_reuse(self):
        """LUAD 必须保留真实执行行，禁止用复用标记掩盖路由是否生效。"""
        core = load_run()
        with self.assertRaises(ValueError):
            core.annotate_reused_combo_row({"cancer": "LUAD"})

    def test_remote_asset_hashes_must_match_reference_preflight(self):
        """C6：远端“文件存在”不足，74项资产哈希必须与参考预检一致。"""
        core = load_run()
        expected = {"checkpoint/LUAD/123": "a", "cache/test/img_sur_test_all_LUAD.pkl": "b"}
        self.assertTrue(hasattr(core, "assert_asset_hashes_match"), "缺少资产哈希一致性断言")
        self.assertTrue(core.assert_asset_hashes_match(expected, dict(expected)))
        with self.assertRaises(ValueError):
            core.assert_asset_hashes_match(expected, {"checkpoint/LUAD/123": "changed"})

    def test_reference_router_source_hashes_are_checked_before_import(self):
        """C3：3.progress 的被复用执行代码必须逐文件匹配登记 SHA。"""
        core = load_run()
        self.assertTrue(hasattr(core, "verify_reference_source_hashes"), "缺少参考路由来源哈希核验")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = b"route source"
            source = root / "strategy0.py"
            source.write_bytes(payload)
            expected = {"strategy0.py": hashlib.sha256(payload).hexdigest()}
            self.assertTrue(core.verify_reference_source_hashes(root, expected))
            with self.assertRaises(ValueError):
                core.verify_reference_source_hashes(root, {"strategy0.py": "changed"})


if __name__ == "__main__":
    unittest.main()
