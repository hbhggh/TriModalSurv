"""strategy0 的无参数批内路由。

此文件只选择复用哪个已经冻结的推理路径；不改模型、权重、缓存或患者库。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent


def _load_router():
    path = ROOT / "strategy0.py"
    name = "_strategy0_router"
    module = sys.modules.get(name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load strategy0 router: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _bool_vector(value: object, *, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 1:
        raise ValueError(f"{name}: invalid shape")
    if array.dtype != np.bool_:
        raise ValueError(f"{name}: invalid boolean vector")
    return array


def partition_routes(
    cancer: str,
    grid: str,
    rna_valid: object,
    text_valid: object,
    *,
    enabled: bool,
) -> dict[str, list[int]]:
    """按原 batch 行号归类；空组也显式保留，禁止后续默默漏患者。"""
    rna = _bool_vector(rna_valid, name="rna_valid")
    text = _bool_vector(text_valid, name="text_valid")
    if rna.shape != text.shape:
        raise ValueError("rna_valid/text_valid: invalid shape")
    router = _load_router()
    result = {"upstream_combo": [], "m1": [], "m0real": []}
    for index in range(rna.size):
        route = router.validate_route(router.route_patient(
            cancer, grid, bool(rna[index]), bool(text[index]), enabled=enabled,
        ))
        result[route].append(index)
    if sum(len(indices) for indices in result.values()) != rna.size:
        raise RuntimeError("strategy0 route partition lost a patient")
    return result


def _slice_mapping(values: dict, indices: list[int]) -> dict:
    return {key: np.asarray(value)[indices].copy() for key, value in values.items()}


def _annotate(record: dict, *, route: str, enabled: bool) -> dict:
    result = dict(record)
    result["strategy0_route"] = route
    result["strategy0_enabled"] = bool(enabled)
    result["strategy0_lambda"] = None if route in ("m1", "m0real") else 1.0
    return result


def prepare_strategy0_batch(
    prepare_batch,
    baseline_spec,
    bank,
    ids,
    raw: dict,
    natural: dict,
    combo_spec: dict,
    *,
    grid: str,
    query_split: str,
    numerics: dict,
    enabled: bool,
):
    """复用上游 `prepare_batch`，并把子批结果严格写回原患者位置。

    m1/m0real 路由不传 combo 参数，因此填值、mask 与 pooling 均来自固定基线的
    原始实现；组合路由保持原 `combo_spec` 不变。
    """
    patient_ids = list(ids)
    if not patient_ids or len(patient_ids) != len(set(patient_ids)):
        raise ValueError("empty or duplicate patient IDs")
    batch_size = len(patient_ids)
    for name in ("rna_valid", "text_valid"):
        if name not in raw:
            raise ValueError(f"raw missing {name}")
    routes = partition_routes(
        bank.cancer, grid, raw["rna_valid"], raw["text_valid"], enabled=enabled,
    )
    if sum(len(indices) for indices in routes.values()) != batch_size:
        raise RuntimeError("strategy0 route batch size mismatch")

    merged_inputs = None
    merged_audit: list[dict | None] = [None] * batch_size
    merged_weights = np.empty((batch_size, 3), dtype=np.float64)
    for route, indices in routes.items():
        if not indices:
            continue
        spec = combo_spec if route == "upstream_combo" else baseline_spec(route)
        local_raw = _slice_mapping(raw, indices)
        local_natural = _slice_mapping(natural, indices)
        local_inputs, local_audit, local_weights = prepare_batch(
            bank, [patient_ids[index] for index in indices], local_raw, local_natural, spec,
            grid=grid, query_split=query_split, numerics=numerics,
        )
        if len(local_audit) != len(indices) or np.asarray(local_weights).shape != (len(indices), 3):
            raise ValueError("upstream preparation returned malformed batch")
        if merged_inputs is None:
            merged_inputs = {
                key: np.empty((batch_size, *np.asarray(value).shape[1:]), dtype=np.asarray(value).dtype)
                for key, value in local_inputs.items()
            }
        if set(merged_inputs) != set(local_inputs):
            raise ValueError("upstream preparation changed input key set across routes")
        for local_index, original_index in enumerate(indices):
            for key, value in local_inputs.items():
                merged_inputs[key][original_index] = np.asarray(value)[local_index]
            merged_audit[original_index] = _annotate(
                local_audit[local_index], route=route, enabled=enabled,
            )
            merged_weights[original_index] = np.asarray(local_weights)[local_index]
    if merged_inputs is None or any(record is None for record in merged_audit):
        raise RuntimeError("strategy0 preparation lost a patient")
    return merged_inputs, list(merged_audit), merged_weights
