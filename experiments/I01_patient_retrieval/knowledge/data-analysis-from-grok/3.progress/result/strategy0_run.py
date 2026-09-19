"""strategy0 正式入口：valid 冻结一次、LUAD test 一次，其余格只读复用。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
ARMS = ("strategy0", "m1", "m0real")
UPSTREAM_BASELINES = ("retrieval", "m1", "m0real")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def write_json_new(path: Path, value: object) -> None:
    """排他写入；已有文件只能由读取路径验证，不能被本轮覆盖。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    os.link(temporary, path)
    temporary.unlink()


def freeze_valid_switch(a_mean: float, b_mean: float) -> dict:
    """仅使用未舍入 valid 均值冻结唯一开关。"""
    for name, value in (("a_mean", a_mean), ("b_mean", b_mean)):
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
    return {"a_mean": float(a_mean), "b_mean": float(b_mean),
            "b_minus_a": float(b_mean - a_mean), "enabled": bool(b_mean > a_mean),
            "decision_rule": "B 未舍入均值严格大于 A 才启用"}


def load_config(path: Path) -> tuple[dict, dict]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "protocol_id": "patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-v1",
        "base_protocol_id": "patient-fixed-padmask-v2-infer-rules1to5-v1",
        "cancers": ["BLCA", "BRCA", "LGG", "LUAD", "UCEC"],
        "seeds": [123, 132, 213, 231, 321],
        "grids": ["none", "rna_100", "text_100", "both_100"],
        "prototype_k": 128,
        "model": {"network_type": "NPJC", "compensator": "none"},
        "numerics": {"norm_epsilon": 1e-12, "logit_atol": 1e-6,
                     "logit_rtol": 0, "risk_clamp": 1e-6},
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"锁定配置不符: {key}")
    profiles = config.get("execution", {}).get("profiles", {})
    active = config.get("execution", {}).get("active_profile")
    if active not in profiles:
        raise ValueError("active_profile 未在集中配置中声明")
    profile = profiles[active]
    needed = {"upstream_root", "upstream_runtime_config", "execution_root", "device", "gpu_ids"}
    if set(profile) != needed or profile["device"] not in ("cpu", "cuda"):
        raise ValueError("运行 profile 不完整")
    if profile["device"] == "cuda" and (not profile["gpu_ids"] or
                                         not all(type(item) is int and item >= 0 for item in profile["gpu_ids"])):
        raise ValueError("CUDA profile 必须给出候选物理 GPU 编号")
    return config, profile


def _load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_upstream(upstream_root: Path, upstream_runtime_config: Path):
    """仅从上游目录导入运行时；本轮目录不修改其 sys.path 下的任何文件。"""
    upstream_root = Path(upstream_root).resolve()
    upstream_config = Path(upstream_runtime_config).resolve()
    if not upstream_config.is_file():
        raise FileNotFoundError(f"missing upstream runtime config: {upstream_config}")
    runtime = _load_path("_strategy0_upstream_runtime", upstream_root / "runtime.py")
    inference = _load_path("_strategy0_upstream_inference_runtime", upstream_root / "inference.py")
    config = runtime.load_config(upstream_config)
    runtime.setup_imports(config)
    return runtime, inference, config


def verify_upstream_source(config: dict, profile: dict) -> dict:
    root = Path(profile["upstream_root"]).resolve()
    actual = {}
    for relative, expected in config["upstream"]["source_sha256"].items():
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"upstream source missing: {relative}")
        digest = file_sha256(path)
        if digest != expected:
            raise ValueError(f"上游来源指纹变化: {relative}")
        actual[relative] = digest
    complete = json.loads((root / "runs/test/complete.json").read_text(encoding="utf-8"))
    if complete.get("run_fingerprint") != config["upstream"]["test_fingerprint"]:
        raise ValueError("上游 test 指纹不符")
    return actual


def choose_idle_gpu(gpu_ids: list[int]) -> int:
    """连续两次只接受无 compute PID 的 GPU；util/显存都不是空闲证明。"""
    for gpu_id in gpu_ids:
        checks = []
        for _ in range(2):
            output = subprocess.run(
                ["nvidia-smi", "-i", str(gpu_id), "--query-compute-apps=pid",
                 "--format=csv,noheader,nounits"], check=True, text=True,
                capture_output=True,
            ).stdout.strip()
            checks.append(output)
        if all(not item for item in checks):
            return gpu_id
    raise RuntimeError("候选 GPU 均存在计算 PID；按协议等待，不抢占")


def configure_upstream_runtime(upstream_config: dict, profile: dict) -> tuple[dict, dict]:
    result = copy.deepcopy(upstream_config)
    if profile["device"] == "cpu":
        result["runtime"]["device"] = "cpu"
        return result, {"device": "cpu", "gpu_gate": "NOT_RUN"}
    gpu_id = choose_idle_gpu(list(profile["gpu_ids"]))
    result["runtime"]["device"] = "cuda"
    result["runtime"]["gpu_id"] = gpu_id
    result["runtime"]["require_idle_gpu"] = True
    return result, {"device": "cuda", "gpu_id": gpu_id, "gpu_gate": "TWO_IDLE_PID_CHECKS"}


def upstream_row(upstream_root: Path, *, stage: str, cancer: str, seed: int, grid: str,
                 candidate_id: str) -> tuple[dict, Path]:
    cell = Path(upstream_root) / "runs" / stage / cancer / str(seed) / grid / "cell.json"
    payload = json.loads(cell.read_text(encoding="utf-8"))
    records = [row for row in payload.get("rows", []) if row.get("candidate_id") == candidate_id]
    if len(records) != 1:
        raise ValueError(f"upstream {stage}/{cancer}/{seed}/{grid}: candidate 不唯一或缺失")
    row = dict(records[0])
    row["source_cell_sha256"] = file_sha256(cell)
    return row, cell


def _cell_directory(execution_root: Path, stage: str, seed: int, grid: str) -> Path:
    return execution_root / "runs" / stage / "LUAD" / str(seed) / grid


def _write_cell(directory: Path, *, row: dict, patient_ids: list[str], logits: np.ndarray,
                risk: np.ndarray, time: np.ndarray, censor: np.ndarray, audit: list[dict],
                run_fingerprint: str) -> dict:
    if directory.exists():
        raise FileExistsError(f"拒绝重跑或覆盖已存在单元: {directory}")
    directory.mkdir(parents=True, exist_ok=False)
    prediction_name = "strategy0.npz"
    audit_name = "strategy0.audit.json"
    with (directory / prediction_name).open("xb") as stream:
        np.savez_compressed(stream, patient_ids=np.asarray(patient_ids), logits=logits,
                            risk_b=risk, time=time, censorship=censor)
    write_json_new(directory / audit_name, {"patients": audit, "split": row["split"],
                                            "grid": row["grid"], "run_fingerprint": run_fingerprint,
                                            "candidate_id": "strategy0"})
    row = dict(row)
    row["prediction_file"] = prediction_name
    row["audit_file"] = audit_name
    artifacts = {prediction_name: file_sha256(directory / prediction_name),
                 audit_name: file_sha256(directory / audit_name)}
    payload = {"run_fingerprint": run_fingerprint, "rows": [row], "artifacts": artifacts,
               "metrics_computed": True}
    write_json_new(directory / "cell.json", payload)
    return row


def evaluate_luad_stage(runtime, inference, up_config: dict, *, stage: str, enabled: bool,
                        execution_root: Path, asset_report: dict, run_fingerprint: str) -> list[dict]:
    """对 LUAD 的20格执行一次真实前向；每个格只有 strategy0 一臂。"""
    import torch
    from sksurv.metrics import concordance_index_censored
    from experiments.I01_patient_retrieval.evaluate import checkpoint_path, strict_e0_load
    from trimodalsurv.evaluation.common import dual_risk_from_logits
    from strategy0_inference import prepare_strategy0_batch

    if stage not in ("valid", "test"):
        raise ValueError("strategy0 only supports valid/test")
    split = stage
    rows = []
    bank, source = runtime.load_cancer(up_config, "LUAD", split)
    combo = {"protocol": "combo", "candidate_id": "combo-l1-a1-w0p5", "enabled_rules": [1, 2, 3, 4, 5],
             "lambda": 1.0, "alpha": 1.0, "w": 0.5, "ucec_exception": True}
    expected = asset_report["reports"]["LUAD"]["checkpoints"]
    ids = list(source.ids)
    for seed in up_config["seeds"]:
        model = runtime.build_model(up_config, "LUAD", up_config["runtime"]["device"])
        checkpoint = checkpoint_path(Path(up_config["paths"]["checkpoint_root"]), "LUAD", seed)
        loaded_state = strict_e0_load(model, checkpoint, expected_file_sha=expected[str(seed)]["sha256"])
        if loaded_state != expected[str(seed)]["state_sha256"]:
            raise ValueError(f"LUAD/{seed}: state_dict 与 preflight 不符")
        before = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
        for grid in up_config["grids"]:
            all_logits, all_audit = [], []
            complete_count, complete_max = 0, None
            upstream_combo, _ = upstream_row(
                Path(up_config["paths"]["execution_root"]), stage=stage, cancer="LUAD", seed=seed,
                grid=grid, candidate_id="combo-l1-a1-w0p5",
            )
            upstream_npz = Path(up_config["paths"]["execution_root"]) / "runs" / stage / "LUAD" / str(seed) / grid / upstream_combo["prediction_file"]
            with np.load(upstream_npz, allow_pickle=False) as source_npz:
                expected_ids = source_npz["patient_ids"].tolist()
                expected_logits = source_npz["logits"].copy()
            if expected_ids != ids:
                raise ValueError("上游预测患者顺序不符")
            for offset in range(0, len(ids), up_config["runtime"]["batch_size"]):
                batch_ids = ids[offset:offset + up_config["runtime"]["batch_size"]]
                raw, natural = source.batch(batch_ids, grid)
                inputs, audit, weights = prepare_strategy0_batch(
                    inference.prepare_batch, runtime.baseline_spec, bank, batch_ids, raw, natural, combo,
                    grid=grid, query_split=split, numerics=up_config["numerics"], enabled=enabled,
                )
                logits = inference.forward_with_pool_weights(
                    model, inputs, "LUAD", up_config["runtime"]["device"], weights,
                    non_blocking=up_config["runtime"]["non_blocking"],
                )
                complete = raw["rna_valid"] & raw["text_valid"]
                if complete.any():
                    reference = expected_logits[offset:offset + len(batch_ids)]
                    diff = float(np.max(np.abs(logits[complete] - reference[complete])))
                    if not np.allclose(logits[complete], reference[complete],
                                       atol=up_config["numerics"]["logit_atol"], rtol=0):
                        raise ValueError(f"完整输入 logits 与上游组合不一致: {diff}")
                    complete_count += int(complete.sum())
                    complete_max = diff if complete_max is None else max(complete_max, diff)
                all_logits.append(logits)
                all_audit.extend(audit)
            logits = np.concatenate(all_logits)
            risk = dual_risk_from_logits(torch.from_numpy(logits))[1].cpu().numpy()
            time = np.asarray([float(source.labels[pid]["survival_months"]) for pid in ids], np.float32)
            censor = np.asarray([float(source.labels[pid]["censorship"]) for pid in ids], np.float32)
            score = float(concordance_index_censored((1 - censor).astype(bool), time, risk)[0])
            directory = _cell_directory(execution_root, stage, seed, grid)
            row = {"split": split, "protocol": "strategy0", "candidate_id": "strategy0",
                   "cancer": "LUAD", "seed": seed, "grid": grid, "n_patients": len(ids),
                   "checkpoint_sha256": expected[str(seed)]["sha256"], "run_fingerprint": run_fingerprint,
                   "c_index_b": score, "n_complete_checked": complete_count,
                   "complete_max_logit_abs_diff": complete_max,
                   "complete_logit_atol": up_config["numerics"]["logit_atol"],
                   "strategy0_enabled": bool(enabled)}
            rows.append(_write_cell(directory, row=row, patient_ids=ids, logits=logits, risk=risk,
                                    time=time, censor=censor, audit=all_audit,
                                    run_fingerprint=run_fingerprint))
            print(f"{stage} LUAD/{seed}/{grid}: strategy0 完成", flush=True)
        if any(not torch.equal(old, model.state_dict()[name].detach().cpu()) for name, old in before.items()):
            raise ValueError("评测前向改变了 E0 state_dict")
        del model
    return rows


def reused_test_rows(config: dict, profile: dict, luad_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """构成可报告的300格三臂矩阵；检索参考单列留证据而不混入三臂报告。"""
    root = Path(profile["upstream_root"])
    luad_index = {(row["seed"], row["grid"]): row for row in luad_rows}
    if len(luad_index) != 20:
        raise ValueError("LUAD 新 test 必须恰为20格")
    reported, retrieval = [], []
    for cancer in config["cancers"]:
        for seed in config["seeds"]:
            for grid in config["grids"]:
                for arm in UPSTREAM_BASELINES:
                    source, source_cell = upstream_row(root, stage="test", cancer=cancer, seed=seed,
                                                       grid=grid, candidate_id=arm)
                    source["source"] = "2.progress/reused-fixed-baseline"
                    source["source_cell_sha256"] = file_sha256(source_cell)
                    if arm == "retrieval":
                        retrieval.append(source)
                    else:
                        reported.append(source)
                if cancer == "LUAD":
                    reported.append(luad_index[(seed, grid)])
                else:
                    source, source_cell = upstream_row(root, stage="test", cancer=cancer, seed=seed,
                                                       grid=grid, candidate_id=config["upstream"]["combo_candidate_id"])
                    source["source_protocol"] = source["protocol"]
                    source["source_candidate_id"] = source["candidate_id"]
                    source["protocol"] = "strategy0"
                    source["candidate_id"] = "strategy0"
                    source["strategy0_enabled"] = False
                    source["source"] = "2.progress/reused-upstream-combo"
                    source["source_cell_sha256"] = file_sha256(source_cell)
                    reported.append(source)
    if len(reported) != 300 or len(retrieval) != 100:
        raise RuntimeError("复用矩阵不完整")
    return reported, retrieval


def _mean(rows: list[dict]) -> float:
    if not rows:
        raise ValueError("empty selection rows")
    return float(np.mean([row["c_index_b"] for row in rows], dtype=np.float64))


def _write_reports(config: dict, execution_root: Path, freeze: dict, rows: list[dict], test_fingerprint: str):
    from strategy0_reporting import render_reports
    reports = render_reports(rows, config=config, freeze=freeze, test_fingerprint=test_fingerprint)
    for name, body in reports.items():
        path = execution_root / name
        if path.exists():
            raise FileExistsError(f"拒绝覆盖已有报告: {path}")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(body)
            stream.write("\n")


def _postcondition(config: dict, execution_root: Path, *, source_hashes: dict, assets: dict,
                   freeze: dict, rows: list[dict], test_fingerprint: str, gpu_record: dict):
    from strategy0_reporting import summarize
    summary = summarize(rows, cancers=config["cancers"], seeds=config["seeds"], grids=config["grids"])
    outcome = "是" if summary["wins"] == 4 else "否"
    content = ["# strategy0：后置验收", "", "| 验收项 | 证据位置 | 状态 |",
               "| --- | --- | --- |",
               "| 上游2.progress未改 | `evidence/source-hashes.json` 与 `precondition.md` | 是 |",
               "| 25权重、45缓存、split通过核验 | `evidence/preflight.json` | 是 |",
               "| valid仅决定唯一开关 | `frozen-routing.json` | 是 |",
               "| test只执行一次LUAD 20格 | `runs/test/LUAD/*/*/cell.json` | 是 |",
               "| 固定m1/m0与非LUAD组合复用上游 | `runs/test/reused-matrix.json` | 是 |",
               "| 无训练、无checkpoint、无缓存写入 | `evidence/preflight.json` 与执行入口 | 是 |",
               "| 主表100格、人工缺失75格与三份报告 | 三份根目录MD | 是 |",
               f"| 严格癌种胜率达到4/5 | `癌症为单位.md` | {outcome} |", "",
               "## 效果目标", "", f"- 严格胜率：**{summary['wins']}/5**。",
               "- 未胜癌种：" + ("、".join(summary["non_wins"]) if summary["non_wins"] else "无") + "。",
               "- valid开关：" + ("启用" if freeze["enabled"] else "关闭") + "；本轮不根据test改规则。",
               "- 探索性声明：本轮受已见test启发；LUAD若有变化只能归因于固定路由换填，不可作为患者检索机制成立的证据。", "",
               "## 指纹", "", f"- test 运行指纹：`{test_fingerprint}`。",
               f"- GPU记录：`{json.dumps(gpu_record, ensure_ascii=False, sort_keys=True)}`。",
               f"- 上游来源数量：{len(source_hashes)}；资产数量：{len(assets)}。", ""]
    path = execution_root / "postcondition.md"
    if path.exists():
        raise FileExistsError("拒绝覆盖 postcondition")
    with path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(content))
        stream.write("\n")


def execute(config_path: Path):
    config, profile = load_config(config_path)
    execution_root = Path(profile["execution_root"]).resolve()
    if execution_root != ROOT.resolve() and profile["device"] == "cpu":
        # 允许远端副本使用同一源码，但本机交付目录必须来自本根；这条保护防误写上游。
        if Path(profile["upstream_root"]).resolve() == execution_root:
            raise ValueError("execution_root 不能等于上游只读目录")
    source_hashes = verify_upstream_source(config, profile)
    runtime, inference, upstream_config = load_upstream(
        Path(profile["upstream_root"]), Path(profile["upstream_runtime_config"])
    )
    up_config, gpu_record = configure_upstream_runtime(upstream_config, profile)
    if up_config["runtime"]["device"] == "cuda":
        # 上游 verify_gpu 再作一次 PID 核验，并绑定 CUDA_VISIBLE_DEVICES。
        runtime.verify_gpu(up_config)
    assets = runtime.hash_assets(up_config)
    preflight_path = execution_root / "evidence" / "preflight.json"
    if preflight_path.exists():
        asset_report = json.loads(preflight_path.read_text(encoding="utf-8"))
        if asset_report.get("asset_hashes") != assets or asset_report.get("source_hashes") != source_hashes:
            raise ValueError("已有 preflight 不对应当前资产或来源")
    else:
        asset_report = runtime.preflight(up_config, assets)
        asset_report.update({"source_hashes": source_hashes, "gpu": gpu_record,
                             "strategy0_protocol_id": config["protocol_id"]})
        write_json_new(preflight_path, asset_report)
    runtime_source = runtime.source_hashes(up_config)
    run_common = {"protocol_id": config["protocol_id"], "upstream_test_fingerprint": config["upstream"]["test_fingerprint"],
                  "source_hashes": source_hashes, "runtime_source_hashes": runtime_source,
                  "asset_hashes": assets, "gpu": gpu_record}

    valid_a = []
    for seed in config["seeds"]:
        for grid in config["grids"]:
            row, _ = upstream_row(Path(profile["upstream_root"]), stage="valid", cancer="LUAD", seed=seed,
                                  grid=grid, candidate_id=config["upstream"]["combo_candidate_id"])
            valid_a.append(row)
    valid_fingerprint = digest_json({**run_common, "stage": "valid", "candidate": "strategy0-B"})
    valid_complete = execution_root / "runs" / "valid" / "complete.json"
    if valid_complete.exists():
        valid_payload = json.loads(valid_complete.read_text(encoding="utf-8"))
        if valid_payload.get("run_fingerprint") != valid_fingerprint:
            raise ValueError("已有 valid 不对应冻结来源/资产")
        valid_b = valid_payload["rows"]
    else:
        valid_b = evaluate_luad_stage(runtime, inference, up_config, stage="valid", enabled=True,
                                      execution_root=execution_root, asset_report=asset_report,
                                      run_fingerprint=valid_fingerprint)
        write_json_new(valid_complete, {"stage": "valid", "run_fingerprint": valid_fingerprint,
                                        "source_hashes": source_hashes, "asset_hashes": assets,
                                        "rows": valid_b, "a_rows": valid_a})
    if len(valid_b) != 20:
        raise ValueError("valid B 必须恰为20格")
    freeze = freeze_valid_switch(_mean(valid_a), _mean(valid_b))
    freeze.update({"stage": "valid", "a_source": "2.progress/runs/valid",
                   "run_fingerprint": valid_fingerprint, "source_hashes": source_hashes,
                   "asset_hashes": assets})
    freeze_path = execution_root / "frozen-routing.json"
    if freeze_path.exists():
        if json.loads(freeze_path.read_text(encoding="utf-8")) != freeze:
            raise ValueError("冻结路由已存在且与本次 valid 不同，拒绝test")
    else:
        write_json_new(freeze_path, freeze)

    test_fingerprint = digest_json({**run_common, "stage": "test", "frozen_enabled": freeze["enabled"],
                                    "valid_fingerprint": valid_fingerprint})
    test_complete = execution_root / "runs" / "test" / "complete.json"
    if test_complete.exists():
        raise FileExistsError("test 已存在；禁止二次执行")
    luad_rows = evaluate_luad_stage(runtime, inference, up_config, stage="test", enabled=freeze["enabled"],
                                    execution_root=execution_root, asset_report=asset_report,
                                    run_fingerprint=test_fingerprint)
    if runtime.hash_assets(up_config) != assets or verify_upstream_source(config, profile) != source_hashes:
        raise ValueError("执行期间资产或上游来源变化，禁止汇总")
    rows, retrieval = reused_test_rows(config, profile, luad_rows)
    write_json_new(execution_root / "runs" / "test" / "reused-matrix.json",
                   {"reported_rows": rows, "retrieval_reference_rows": retrieval,
                    "source": "2.progress", "upstream_test_fingerprint": config["upstream"]["test_fingerprint"]})
    write_json_new(test_complete, {"stage": "test", "status": "COMPLETED", "run_fingerprint": test_fingerprint,
                                   "source_hashes": source_hashes, "asset_hashes": assets,
                                   "rows": rows, "luad_executed_rows": luad_rows,
                                   "retrieval_reference_rows": retrieval, "frozen_enabled": freeze["enabled"],
                                   "state_dict_unchanged": True})
    _write_reports(config, execution_root, freeze, rows, test_fingerprint)
    _postcondition(config, execution_root, source_hashes=source_hashes, assets=assets, freeze=freeze,
                   rows=rows, test_fingerprint=test_fingerprint, gpu_record=gpu_record)
    return {"valid": freeze, "test_fingerprint": test_fingerprint, "rows": len(rows)}


def main():
    parser = argparse.ArgumentParser(description="strategy0：固定路由零训练评测")
    parser.add_argument("--config", required=True, help="集中配置JSON；不接受临时科学参数")
    args = parser.parse_args()
    result = execute(Path(args.config))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
