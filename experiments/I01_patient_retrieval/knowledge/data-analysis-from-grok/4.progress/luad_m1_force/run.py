"""S0-force 的执行封装。

复用 3.progress 已经验证过的 LUAD 批内分流与上游 2.progress 推理；本文件只把
冻结规则改成强制启用，并把非 LUAD 的复用开关标为“不适用”。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROTOCOL_ID = "patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-force-v1"
LEGACY_STRATEGY0_PROTOCOL_ID = "patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-v1"
REQUIRED_CANCERS = ("BLCA", "BRCA", "LGG", "LUAD", "UCEC")
REQUIRED_SEEDS = (123, 132, 213, 231, 321)
REQUIRED_GRIDS = ("none", "rna_100", "text_100", "both_100")


def _load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_gpu_sample(gpu_id: int) -> tuple[float, int]:
    """读取物理卡瞬时利用率与可用显存；不以 PID 是否存在作为共享卡否决条件。"""
    output = subprocess.run(
        ["nvidia-smi", "-i", str(gpu_id), "--query-gpu=utilization.gpu,memory.free",
         "--format=csv,noheader,nounits"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    fields = [item.strip() for item in output.split(",")]
    if len(fields) != 2:
        raise ValueError(f"GPU{gpu_id} 状态格式异常：{output!r}")
    utilization, free_memory = float(fields[0]), int(fields[1])
    if not math.isfinite(utilization) or utilization < 0 or free_memory < 0:
        raise ValueError(f"GPU{gpu_id} 状态数值异常：{output!r}")
    return utilization, free_memory


def choose_shared_gpu(
    gpu_ids: list[int], *, max_utilization_percent: float, min_free_memory_mib: int,
    required_samples: int = 2, sample_interval_seconds: float = 0.0,
    sample_reader=_read_gpu_sample, sleep_fn=time.sleep,
) -> tuple[int, list[tuple[float, int]]]:
    """按用户授权选择低负载共享卡：每次采样都必须利用率严格低于阈值且显存足够。"""
    if not gpu_ids or not all(type(gpu_id) is int and gpu_id >= 0 for gpu_id in gpu_ids):
        raise ValueError("共享 GPU 候选编号不合法")
    if not isinstance(max_utilization_percent, (int, float)) or not math.isfinite(max_utilization_percent):
        raise ValueError("共享 GPU 利用率阈值不合法")
    if not (0 < float(max_utilization_percent) <= 100) or type(min_free_memory_mib) is not int or min_free_memory_mib <= 0:
        raise ValueError("共享 GPU 利用率或显存阈值不合法")
    if type(required_samples) is not int or required_samples != 2:
        raise ValueError("共享 GPU 必须恰好连续采样两次")
    if not isinstance(sample_interval_seconds, (int, float)) or sample_interval_seconds < 0:
        raise ValueError("共享 GPU 采样间隔不合法")
    for gpu_id in gpu_ids:
        samples: list[tuple[float, int]] = []
        for sample_index in range(required_samples):
            sample = sample_reader(gpu_id)
            if not isinstance(sample, tuple) or len(sample) != 2:
                raise ValueError(f"GPU{gpu_id} 采样返回格式不合法")
            utilization, free_memory = float(sample[0]), int(sample[1])
            if not math.isfinite(utilization) or utilization < 0 or free_memory < 0:
                raise ValueError(f"GPU{gpu_id} 采样数值不合法")
            samples.append((utilization, free_memory))
            if sample_index + 1 < required_samples and sample_interval_seconds:
                sleep_fn(float(sample_interval_seconds))
        if all(utilization < float(max_utilization_percent) and free_memory >= min_free_memory_mib
               for utilization, free_memory in samples):
            return gpu_id, samples
    raise RuntimeError("候选 GPU 未同时满足两次利用率与显存共享门禁")


def configure_shared_gpu_runtime(
    upstream_config: dict, profile: dict, policy: dict, *, sample_reader=_read_gpu_sample,
    sleep_fn=time.sleep,
) -> tuple[dict, dict]:
    """只覆盖运行门禁：固定科研配置不变，允许用户授权的低负载共享 GPU。"""
    required_policy = {"utilization_lt_percent", "min_free_memory_mib", "consecutive_samples", "sample_interval_seconds"}
    if not isinstance(policy, dict) or set(policy) != required_policy:
        raise ValueError("共享 GPU 门禁配置不完整")
    if profile.get("device") != "cuda":
        raise ValueError("共享 GPU 门禁只允许 CUDA profile")
    gpu_id, samples = choose_shared_gpu(
        list(profile["gpu_ids"]), max_utilization_percent=policy["utilization_lt_percent"],
        min_free_memory_mib=policy["min_free_memory_mib"], required_samples=policy["consecutive_samples"],
        sample_interval_seconds=policy["sample_interval_seconds"], sample_reader=sample_reader, sleep_fn=sleep_fn,
    )
    result = copy.deepcopy(upstream_config)
    result["runtime"]["device"] = "cuda"
    result["runtime"]["gpu_id"] = gpu_id
    result["runtime"]["require_idle_gpu"] = False
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    return result, {
        "device": "cuda", "gpu_id": gpu_id,
        "gpu_gate": "USER_AUTHORIZED_TWO_SHARED_GPU_SAMPLES", "samples": samples,
        "utilization_lt_percent": policy["utilization_lt_percent"],
        "min_free_memory_mib": policy["min_free_memory_mib"],
    }


def force_freeze(a_mean: float, b_mean: float) -> dict[str, object]:
    """记录 valid 的负向证据，但不允许它关闭本轮唯一的强制路由。"""
    for name, value in (("a_mean", a_mean), ("b_mean", b_mean)):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} 必须是有限数值")
    return {
        "a_mean": float(a_mean),
        "b_mean": float(b_mean),
        "b_minus_a": float(b_mean - a_mean),
        "enabled": True,
        "decision_rule": "S0-force强制启用；valid仅审计，不以 B>A 否决",
        "scientific_boundary": "valid B<A 仍强制开启；本轮是受已见test启发的探索性反事实，存在test泄漏。",
    }


def annotate_reused_combo_row(row: dict) -> dict:
    """C2：非 LUAD 没有开关状态，`null` 表示不适用而不是关闭。"""
    if row.get("cancer") == "LUAD":
        raise ValueError("LUAD 必须使用真实执行行，不能重标为上游复用")
    result = dict(row)
    result["strategy0_route"] = "upstream_combo"
    result["strategy0_enabled"] = None
    result["source"] = "2.progress/reused-upstream-combo"
    return result


def _mean(rows: list[dict]) -> float:
    if not rows:
        raise ValueError("均值输入为空")
    return sum(float(row["c_index_b"]) for row in rows) / len(rows)


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_asset_hashes_match(expected: dict, actual: dict) -> bool:
    """C6：资产来源必须是逐项哈希相同，不接受仅文件存在或数量相同。"""
    if not isinstance(expected, dict) or not isinstance(actual, dict) or expected != actual:
        raise ValueError("远端资产哈希与参考预检不一致")
    return True


def verify_reference_source_hashes(reference_root: Path, expected: dict[str, str]) -> bool:
    """C3：导入 3.progress 的任何执行代码前，逐文件核对预登记 SHA。"""
    if not isinstance(expected, dict) or not expected:
        raise ValueError("参考来源哈希清单为空")
    root = Path(reference_root)
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != digest:
            raise ValueError(f"3.progress 参考来源哈希不符：{relative}")
    return True


def load_config(path: Path) -> tuple[dict, dict]:
    """config.yaml 采用 JSON 兼容 YAML，避免引入新解析依赖。"""
    config = _read_json(path)
    if config.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("协议名不符")
    if tuple(config.get("cancers", ())) != REQUIRED_CANCERS:
        raise ValueError("癌种范围不符")
    if tuple(config.get("seeds", ())) != REQUIRED_SEEDS:
        raise ValueError("seed 范围不符")
    if tuple(config.get("grids", ())) != REQUIRED_GRIDS:
        raise ValueError("场景范围不符")
    if config.get("prototype_k") != 128 or config.get("model") != {"network_type": "NPJC", "compensator": "none"}:
        raise ValueError("K 或模型身份不符")
    force = config.get("s0_force")
    if not isinstance(force, dict) or force.get("enabled") is not True:
        raise ValueError("S0-force 配置必须写死 enabled=true")
    if force.get("valid_decision") != "audit_only":
        raise ValueError("valid 只能审计，不能关闭路由")
    shared_policy = config.get("shared_gpu_policy")
    required_policy = {"utilization_lt_percent", "min_free_memory_mib", "consecutive_samples", "sample_interval_seconds"}
    if not isinstance(shared_policy, dict) or set(shared_policy) != required_policy:
        raise ValueError("共享 GPU 门禁必须在集中配置中完整声明")
    if (not isinstance(shared_policy["utilization_lt_percent"], (int, float)) or
            not math.isfinite(shared_policy["utilization_lt_percent"]) or
            not (0 < float(shared_policy["utilization_lt_percent"]) <= 100) or
            type(shared_policy["min_free_memory_mib"]) is not int or shared_policy["min_free_memory_mib"] <= 0 or
            shared_policy["consecutive_samples"] != 2 or
            not isinstance(shared_policy["sample_interval_seconds"], (int, float)) or
            shared_policy["sample_interval_seconds"] < 0):
        raise ValueError("共享 GPU 门禁数值不合法")
    execution = config.get("execution", {})
    active = execution.get("active_profile")
    profiles = execution.get("profiles", {})
    if active not in profiles:
        raise ValueError("active_profile 未声明")
    profile = profiles[active]
    required_profile = {"upstream_root", "upstream_runtime_config", "strategy0_reference_root", "execution_root", "device", "gpu_ids"}
    if set(profile) != required_profile:
        raise ValueError("execution profile 字段不完整")
    if profile["device"] not in ("cpu", "cuda"):
        raise ValueError("device 不合法")
    if profile["device"] == "cuda" and not profile["gpu_ids"]:
        raise ValueError("CUDA profile 必须声明候选 GPU")
    return config, profile


def _load_reference_core(reference_root: Path):
    """只读导入 3.progress 已验证的执行器，绝不修改其文件。"""
    reference_root = Path(reference_root).resolve()
    required = ("strategy0.py", "strategy0_inference.py", "strategy0_run.py")
    if any(not (reference_root / name).is_file() for name in required):
        raise FileNotFoundError("3.progress 路由实现不完整")
    if str(reference_root) not in sys.path:
        sys.path.insert(0, str(reference_root))
    return _load_path("_s0_force_reference_core", reference_root / "strategy0_run.py")


def _assert_route_parity(reference_root: Path) -> None:
    """确认复用的 enabled=true 路由与本轮 model.py 完全同构。"""
    model = _load_path("_s0_force_model", ROOT / "model.py")
    reference = _load_path("_s0_force_reference_router", Path(reference_root) / "strategy0.py")
    for cancer in REQUIRED_CANCERS:
        for grid in REQUIRED_GRIDS:
            for rna_valid in (False, True):
                for text_valid in (False, True):
                    actual = model.route_patient(cancer=cancer, grid=grid, rna_valid=rna_valid,
                                                 text_valid=text_valid)
                    expected = reference.route_patient(cancer, grid, rna_valid, text_valid, enabled=True)
                    if actual["route"] != expected:
                        raise ValueError("本轮路由与 3.progress enabled=true 分支不一致")


def _assert_new_execution_root(execution_root: Path, *, upstream_root: Path, reference_root: Path) -> None:
    execution_root = Path(execution_root).resolve()
    for protected in (Path(upstream_root).resolve(), Path(reference_root).resolve()):
        if execution_root == protected or protected in execution_root.parents:
            raise ValueError("执行根不得等于或位于 2.progress/3.progress 只读目录内")


def _valid_reference_rows(config: dict, profile: dict) -> list[dict]:
    ref_root = Path(profile["strategy0_reference_root"])
    complete = ref_root / "runs" / "valid" / "complete.json"
    expected = config["valid_reuse"]
    if _sha256(complete) != expected["complete_sha256"]:
        raise ValueError("3.progress valid complete 哈希不符")
    payload = _read_json(complete)
    if payload.get("run_fingerprint") != expected["run_fingerprint"]:
        raise ValueError("3.progress valid 指纹不符")
    rows = list(payload.get("rows", ()))
    if len(rows) != 20 or any(row.get("cancer") != "LUAD" or row.get("strategy0_enabled") is not True for row in rows):
        raise ValueError("只允许复用原本 enabled=true 的 LUAD valid B")
    return rows


def _reused_matrix(core, config: dict, profile: dict, luad_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """复用 2.progress 的 80 格组合和全部固定基线，并落实 C2。"""
    reported, retrieval = core.reused_test_rows(config, profile, luad_rows)
    result = []
    for row in reported:
        if row.get("protocol") == "strategy0" and row.get("cancer") != "LUAD":
            result.append(annotate_reused_combo_row(row))
        else:
            result.append(row)
    if len(result) != 300 or len(retrieval) != 100:
        raise ValueError("复用矩阵不完整")
    return result, retrieval


def _compare_luad_fixed_routes(core, upstream_root: Path, execution_root: Path, rows: list[dict]) -> dict[str, dict[str, int]]:
    """C1：m1/m0 路由必须逐 logit、逐 C-index 等价于固定基线；none 记录计数。"""
    import numpy as np

    audit_counts: dict[str, dict[str, int]] = {}
    index = {(row["seed"], row["grid"]): row for row in rows}
    if len(index) != 20:
        raise ValueError("LUAD 新 test 必须为20格")
    for seed in REQUIRED_SEEDS:
        for grid in REQUIRED_GRIDS:
            actual_row = index[(seed, grid)]
            cell_dir = Path(execution_root) / "runs" / "test" / "LUAD" / str(seed) / grid
            audit = _read_json(cell_dir / actual_row["audit_file"])["patients"]
            counts = dict(Counter(record["strategy0_route"] for record in audit))
            audit_counts[f"{seed}/{grid}"] = counts
            if any(record.get("strategy0_enabled") is not True for record in audit):
                raise ValueError("LUAD 实际审计存在未强制启用记录")
            baseline = "m1" if grid in ("rna_100", "both_100") else "m0real" if grid == "text_100" else None
            if baseline is None:
                continue
            if set(counts) != {baseline}:
                raise ValueError(f"LUAD/{seed}/{grid} 路由未完全落到固定 {baseline}")
            expected_row, _ = core.upstream_row(Path(upstream_root), stage="test", cancer="LUAD", seed=seed,
                                                grid=grid, candidate_id=baseline)
            if float(actual_row["c_index_b"]) != float(expected_row["c_index_b"]):
                raise ValueError(f"LUAD/{seed}/{grid} C-index 未与固定 {baseline} 完全一致")
            with np.load(cell_dir / actual_row["prediction_file"], allow_pickle=False) as actual, np.load(
                Path(upstream_root) / "runs" / "test" / "LUAD" / str(seed) / grid / expected_row["prediction_file"],
                allow_pickle=False,
            ) as expected:
                if not np.array_equal(actual["patient_ids"], expected["patient_ids"]) or not np.array_equal(actual["logits"], expected["logits"]):
                    raise ValueError(f"LUAD/{seed}/{grid} logits 未与固定 {baseline} 完全一致")
    return audit_counts


def execute(config_path: Path) -> dict:
    """运行 valid 审计、强制冻结和唯一一次 LUAD test；不写 postcondition。"""
    config, profile = load_config(config_path)
    execution_root = Path(profile["execution_root"]).resolve()
    upstream_root = Path(profile["upstream_root"]).resolve()
    reference_root = Path(profile["strategy0_reference_root"]).resolve()
    _assert_new_execution_root(execution_root, upstream_root=upstream_root, reference_root=reference_root)
    verify_reference_source_hashes(reference_root, config["strategy0_reference_sha256"])
    _assert_route_parity(reference_root)
    core = _load_reference_core(reference_root)
    source_hashes = core.verify_upstream_source(config, profile)
    runtime, inference, upstream_config = core.load_upstream(upstream_root, Path(profile["upstream_runtime_config"]))
    if profile["device"] == "cuda":
        up_config, gpu_record = configure_shared_gpu_runtime(
            upstream_config, profile, config["shared_gpu_policy"],
        )
    else:
        up_config, gpu_record = core.configure_upstream_runtime(upstream_config, profile)
    assets = runtime.hash_assets(up_config)
    reference_assets = _read_json(reference_root / "evidence" / "preflight.json").get("asset_hashes")
    assert_asset_hashes_match(reference_assets, assets)
    asset_report = runtime.preflight(up_config, assets)
    asset_report.update({"source_hashes": source_hashes, "gpu": gpu_record, "protocol_id": PROTOCOL_ID})
    core.write_json_new(execution_root / "evidence" / "preflight.json", asset_report)

    valid_a = [core.upstream_row(upstream_root, stage="valid", cancer="LUAD", seed=seed, grid=grid,
                                 candidate_id=config["upstream"]["combo_candidate_id"])[0]
               for seed in REQUIRED_SEEDS for grid in REQUIRED_GRIDS]
    valid_b = _valid_reference_rows(config, profile)
    freeze = force_freeze(_mean(valid_a), _mean(valid_b))
    freeze.update({"protocol_id": PROTOCOL_ID, "stage": "valid", "a_source": "2.progress/runs/valid",
                   "b_source": "3.progress/runs/valid (enabled=true)", "source_hashes": source_hashes,
                   "asset_hashes": assets})
    core.write_json_new(execution_root / "runs" / "valid" / "complete.json", {
        "stage": "valid", "status": "REUSED_ENABLED_TRUE_AUDIT_ONLY", "rows": valid_b, "a_rows": valid_a,
        "source_complete_sha256": config["valid_reuse"]["complete_sha256"], "freeze": freeze,
    })
    core.write_json_new(execution_root / "frozen-routing.json", freeze)

    run_fingerprint = core.digest_json({"protocol_id": PROTOCOL_ID, "stage": "test", "force_enabled": True,
                                        "source_hashes": source_hashes, "asset_hashes": assets,
                                        "valid_source_sha256": config["valid_reuse"]["complete_sha256"]})
    luad_rows = core.evaluate_luad_stage(runtime, inference, up_config, stage="test", enabled=True,
                                         execution_root=execution_root, asset_report=asset_report,
                                         run_fingerprint=run_fingerprint)
    audit_counts = _compare_luad_fixed_routes(core, upstream_root, execution_root, luad_rows)
    if runtime.hash_assets(up_config) != assets or core.verify_upstream_source(config, profile) != source_hashes:
        raise ValueError("执行期间资产或上游来源变化，禁止汇总")
    rows, retrieval = _reused_matrix(core, config, profile, luad_rows)
    core.write_json_new(execution_root / "runs" / "test" / "reused-matrix.json", {
        "reported_rows": rows, "retrieval_reference_rows": retrieval, "source": "2.progress",
        "upstream_test_fingerprint": config["upstream"]["test_fingerprint"], "luad_route_counts": audit_counts,
    })
    core.write_json_new(execution_root / "runs" / "test" / "complete.json", {
        "stage": "test", "status": "COMPLETED", "run_fingerprint": run_fingerprint,
        "source_hashes": source_hashes, "asset_hashes": assets, "rows": rows,
        "luad_executed_rows": luad_rows, "retrieval_reference_rows": retrieval,
        "frozen_enabled": True, "state_dict_unchanged": True, "luad_route_counts": audit_counts,
    })
    reporting = _load_path("_s0_force_reporting", ROOT / "reporting.py")
    reports = reporting.render_reports(
        rows=rows, config=config, freeze=freeze, test_fingerprint=run_fingerprint,
        reference_reporting_path=reference_root / "strategy0_reporting.py",
        luad_route_counts=audit_counts,
    )
    for name, body in reports.items():
        report_path = execution_root / name
        with report_path.open("x", encoding="utf-8") as stream:
            stream.write(body)
            stream.write("\n")
    return {"freeze": freeze, "test_fingerprint": run_fingerprint, "rows": len(rows), "gpu": gpu_record}


def main() -> None:
    parser = argparse.ArgumentParser(description="S0-force：仅 LUAD 路由的零训练评测")
    parser.add_argument("--config", required=True, help="集中配置；禁止临时覆盖科学参数")
    args = parser.parse_args()
    print(json.dumps(execute(Path(args.config)), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
