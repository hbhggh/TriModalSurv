"""NPJ-C 零训练推理规则 1--5 的共享核心。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
RULE_DIRS = {
    1: "01_text100_skip_compensate",
    2: "02_wsi_meanpool_key",
    3: "03_shrinkage_lambda",
    4: "04_wsi_rna_joint_sim",
    5: "05_imputed_token_downweight",
}
MODALITIES = ("rna", "text")
POOL_ORDER = ("img", "text", "rna")
BASELINES = ("retrieval", "m1", "m0real")
GRIDS = ("none", "rna_100", "text_100", "both_100")
_RULE_CACHE = {}


def load_rule(number: int):
    """按文件路径加载数字前缀目录，并在 exec_module 前注册模块。"""
    if number not in RULE_DIRS:
        raise ValueError(f"unknown rule: {number}")
    if number in _RULE_CACHE:
        return _RULE_CACHE[number]
    path = ROOT / RULE_DIRS[number] / "model.py"
    name = f"_i01_infer_rule_{number}_{RULE_DIRS[number]}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load rule module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    _RULE_CACHE[number] = module
    return module


def _bool_vector(value, batch_size: int, *, context: str) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != (batch_size,) or not np.isin(array, [0, 1]).all():
        raise ValueError(f"{context}: invalid boolean vector")
    return array.astype(bool, copy=True)


def _validate_inputs(bank, ids, raw, natural, spec, grid, query_split, numerics):
    patient_ids = list(ids)
    if not patient_ids or len(patient_ids) != len(set(patient_ids)):
        raise ValueError("empty or duplicate patient IDs")
    if grid not in GRIDS:
        raise ValueError(f"unknown grid: {grid}")
    if not isinstance(query_split, str) or query_split not in bank.splits:
        raise ValueError("query_split must be explicit and declared")
    required_raw = {"img", "img_valid", "rna", "rna_valid", "text", "text_valid"}
    if not required_raw.issubset(raw):
        raise ValueError(f"raw missing keys: {sorted(required_raw - set(raw))}")
    if set(natural) != set(MODALITIES):
        raise ValueError("natural must contain rna/text")
    batch_size = len(patient_ids)
    img = np.asarray(raw["img"])
    if img.shape != (batch_size, *bank.shapes["img"]) or not np.isfinite(img).all():
        raise ValueError("img: invalid batch feature shape or values")
    _bool_vector(raw["img_valid"], batch_size, context="img_valid")
    if not _bool_vector(raw["img_valid"], batch_size, context="img_valid").all():
        raise ValueError("NPJ-C rule evaluation requires valid WSI for every query")
    for mm in MODALITIES:
        value = np.asarray(raw[mm])
        if value.shape != (batch_size, *bank.shapes[mm]) or not np.isfinite(value).all():
            raise ValueError(f"{mm}: invalid batch feature shape or values")
        current = _bool_vector(raw[f"{mm}_valid"], batch_size, context=f"{mm}_valid")
        present = _bool_vector(natural[mm], batch_size, context=f"natural/{mm}")
        if np.any(current & ~present):
            raise ValueError(f"{mm}: artificial valid cannot exceed natural availability")
    if not isinstance(spec, dict):
        raise ValueError("candidate spec must be a dict")
    enabled = tuple(spec.get("enabled_rules", ()))
    if len(enabled) != len(set(enabled)) or any(type(rule) is not int or rule not in RULE_DIRS
                                                for rule in enabled):
        raise ValueError("enabled_rules must be unique integers in 1..5")
    if not isinstance(spec.get("protocol"), str) or not isinstance(spec.get("candidate_id"), str):
        raise ValueError("candidate spec lacks protocol/candidate_id")
    if not isinstance(numerics, dict):
        raise ValueError("numerics must be a dict")
    epsilon = float(numerics.get("norm_epsilon", np.nan))
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("invalid norm_epsilon")
    return patient_ids, enabled, epsilon


def _flatten_wsi_score(signature, donor_key, query_mask, donor_mask, *, epsilon: float) -> float:
    common = np.asarray(query_mask) & np.asarray(donor_mask)
    if not common.any():
        raise ValueError("empty valid-row overlap")
    query = np.asarray(signature)[common].astype(np.float64, copy=False).reshape(-1)
    donor = np.asarray(donor_key)[common].astype(np.float64, copy=False).reshape(-1)
    qnorm, dnorm = float(np.linalg.norm(query)), float(np.linalg.norm(donor))
    if any(not np.isfinite(norm) or norm <= epsilon for norm in (qnorm, dnorm)):
        raise ValueError("invalid common-row centered norm")
    score = float(np.sum(query * donor, dtype=np.float64) / (qnorm * dnorm))
    if not np.isfinite(score):
        raise ValueError("nonfinite masked cosine")
    return score


def _custom_retrieve(bank, patient_id, query_wsi, missing, *, query_split, enabled,
                     grid, query_rna, natural_rna, alpha, epsilon):
    accelerator = getattr(bank, 'retrieval_accelerator', None)
    if accelerator is not None:
        return accelerator.custom_retrieve(patient_id, query_wsi, missing,
            query_split=query_split, enabled=enabled, grid=grid, query_rna=query_rna,
            natural_rna=natural_rna, alpha=alpha, epsilon=epsilon)
    signature, query_mask = bank.validate_query(patient_id, query_wsi, query_split=query_split)
    joint_active = 4 in enabled and grid == "text_100" and bool(natural_rna)
    candidates = []
    for index, donor_id in enumerate(bank.patient_ids):
        if donor_id == patient_id or not all(donor_id in bank._features[mm] for mm in missing):
            continue
        if joint_active and not all(donor_id in bank._features[mm] for mm in MODALITIES):
            continue
        candidates.append((index, donor_id))
    if not candidates:
        raise ValueError(f"{patient_id}: empty candidate set for {missing}")

    rule2 = load_rule(2) if 2 in enabled else None
    rule4 = load_rule(4) if joint_active else None
    scored = []
    for index, donor_id in candidates:
        if rule2 is not None:
            score_wsi = rule2.meanpool_wsi_score(
                query_wsi, bank._features["img"][donor_id], query_mask,
                bank.row_masks[index], bank.mean, epsilon=epsilon,
            )
        else:
            score_wsi = _flatten_wsi_score(
                signature, bank.keys[index], query_mask, bank.row_masks[index], epsilon=epsilon,
            )
        score_rna = None
        similarity = score_wsi
        if joint_active:
            score_rna = rule4.token_mean_cosine(
                query_rna, bank._features["rna"][donor_id], epsilon=epsilon,
            )
            similarity = rule4.joint_similarity(score_wsi, score_rna, alpha)
        scored.append((similarity, score_wsi, score_rna, index, donor_id))

    # bank.patient_ids 已排序；argmax 对完全并列稳定选择最前 patient ID。
    selected = int(np.argmax([row[0] for row in scored]))
    similarity, score_wsi, score_rna, index, donor_id = scored[selected]
    return {
        "donor_id": donor_id,
        "similarity": similarity,
        "score_wsi": score_wsi,
        "score_rna": score_rna,
        "candidate_count": len(candidates),
        "query_valid_rows": int(query_mask.sum()),
        "donor_valid_rows": bank.valid_row_counts[donor_id],
        "common_valid_rows": int(np.count_nonzero(query_mask & bank.row_masks[index])),
        "padding_strategy": getattr(bank, "metadata")()["padding_strategy"],
        "values": {mm: bank._features[mm][donor_id].copy() for mm in missing},
    }


def _enrich_audit(records, natural, fusion, imputed, route):
    result = []
    for row, record in enumerate(records):
        enriched = dict(record)
        enriched.setdefault("score_wsi", enriched.get("similarity"))
        enriched.setdefault("score_rna", None)
        enriched["natural_valid"] = {mm: bool(natural[mm][row]) for mm in MODALITIES}
        enriched["original_valid"] = {mm: bool(record["original_valid"][mm]) for mm in MODALITIES}
        enriched["fusion_valid"] = {mm: bool(fusion[mm][row]) for mm in MODALITIES}
        enriched["imputed"] = {mm: bool(imputed[mm][row]) for mm in ("text", "rna")}
        enriched["route"] = route
        result.append(enriched)
    return result


def prepare_batch(bank, ids, raw, natural, spec, *, grid, query_split, numerics):
    """准备不修改原输入的 NPJC batch、逐患者审计和最终 pooling 权重。"""
    patient_ids, enabled, epsilon = _validate_inputs(
        bank, ids, raw, natural, spec, grid, query_split, numerics
    )
    batch_size = len(patient_ids)
    inputs = {key: np.array(value, copy=True) for key, value in raw.items()}
    original = {mm: _bool_vector(raw[f"{mm}_valid"], batch_size, context=mm)
                for mm in MODALITIES}
    natural_masks = {mm: _bool_vector(natural[mm], batch_size, context=f"natural/{mm}")
                     for mm in MODALITIES}

    protocol = spec["protocol"]
    baseline = not enabled and protocol in BASELINES
    if not enabled:
        arm = protocol if baseline else "retrieval"
        filled, fusion, records = bank.compensate(
            patient_ids, raw["img"], {mm: raw[mm] for mm in MODALITIES},
            {mm: raw[f"{mm}_valid"] for mm in MODALITIES}, arm,
            query_split=query_split,
        )
        for mm in MODALITIES:
            inputs[mm] = filled[mm]
            inputs[f"{mm}_valid"] = fusion[mm].astype(bool, copy=False)
        imputed = {mm: (~original[mm]) & fusion[mm] for mm in MODALITIES}
        audit = _enrich_audit(records, natural_masks, fusion, imputed, arm)
        downweight = False
        pool_w = 1.0
    else:
        skip = 1 in enabled and load_rule(1).should_skip_compensation(
            grid=grid, cancer=bank.cancer, ucec_exception=bool(spec.get("ucec_exception", False))
        )
        if skip:
            filled, fusion, records = bank.compensate(
                patient_ids, raw["img"], {mm: raw[mm] for mm in MODALITIES},
                {mm: raw[f"{mm}_valid"] for mm in MODALITIES}, "m0real",
                query_split=query_split,
            )
            for mm in MODALITIES:
                inputs[mm] = filled[mm]
                inputs[f"{mm}_valid"] = fusion[mm].astype(bool, copy=False)
            imputed = {mm: np.zeros(batch_size, dtype=bool) for mm in MODALITIES}
            audit = _enrich_audit(records, natural_masks, fusion, imputed, "rule1_m0real")
        else:
            values = {mm: np.array(raw[mm], copy=True) for mm in MODALITIES}
            fusion = {mm: original[mm].copy() for mm in MODALITIES}
            imputed = {mm: np.zeros(batch_size, dtype=bool) for mm in MODALITIES}
            records = []
            for row, patient_id in enumerate(patient_ids):
                _, query_mask = bank.validate_query(
                    patient_id, raw["img"][row], query_split=query_split
                )
                missing = tuple(mm for mm in MODALITIES if not fusion[mm][row])
                record = {
                    "patient_id": patient_id,
                    "original_valid": {mm: bool(original[mm][row]) for mm in MODALITIES},
                    "donor_id": None,
                    "similarity": None,
                    "score_wsi": None,
                    "score_rna": None,
                    "candidate_count": 0,
                    "query_valid_rows": int(query_mask.sum()),
                    "donor_valid_rows": None,
                    "common_valid_rows": None,
                    "padding_strategy": bank.metadata()["padding_strategy"],
                }
                route = "complete"
                if missing:
                    joint_active = 4 in enabled and grid == "text_100" and natural_masks["rna"][row]
                    if 2 in enabled or joint_active:
                        selected = _custom_retrieve(
                            bank, patient_id, raw["img"][row], missing,
                            query_split=query_split, enabled=enabled, grid=grid,
                            query_rna=raw["rna"][row], natural_rna=natural_masks["rna"][row],
                            alpha=float(spec.get("alpha", 0.0)), epsilon=epsilon,
                        )
                    else:
                        selected = bank.retrieve(
                            patient_id, raw["img"][row], missing, query_split=query_split
                        )
                        selected = dict(selected)
                        selected["score_wsi"] = selected["similarity"]
                        selected["score_rna"] = None
                    for mm in missing:
                        donor = selected["values"][mm]
                        if 3 in enabled:
                            donor = load_rule(3).shrink_feature(
                                bank.means[mm], donor, float(spec.get("lambda", 1.0)),
                                output_dtype=values[mm].dtype,
                            )
                        values[mm][row] = donor
                        fusion[mm][row] = True
                        imputed[mm][row] = True
                    record.update({key: selected[key] for key in (
                        "donor_id", "similarity", "score_wsi", "score_rna", "candidate_count",
                        "query_valid_rows", "donor_valid_rows", "common_valid_rows",
                        "padding_strategy",
                    )})
                    route = "retrieval_joint" if joint_active else (
                        "retrieval_meanpool" if 2 in enabled else "retrieval"
                    )
                record["natural_valid"] = {mm: bool(natural_masks[mm][row]) for mm in MODALITIES}
                record["fusion_valid"] = {mm: bool(fusion[mm][row]) for mm in MODALITIES}
                record["imputed"] = {mm: bool(imputed[mm][row]) for mm in ("text", "rna")}
                record["route"] = route
                records.append(record)
            for mm in MODALITIES:
                inputs[mm] = values[mm]
                inputs[f"{mm}_valid"] = fusion[mm].astype(bool, copy=False)
            audit = records
        downweight = 5 in enabled
        pool_w = float(spec.get("w", 1.0)) if downweight else 1.0

    original_all = {"img": _bool_vector(raw["img_valid"], batch_size, context="img_valid"),
                    "text": original["text"], "rna": original["rna"]}
    fusion_all = {"img": original_all["img"], "text": fusion["text"], "rna": fusion["rna"]}
    imputed_all = {"img": np.zeros(batch_size, dtype=bool),
                   "text": imputed["text"], "rna": imputed["rna"]}
    pool_weights = load_rule(5).build_pool_weights(
        original_all, fusion_all, imputed_all, w=pool_w, downweight=downweight,
    )
    for row, record in enumerate(audit):
        record["pool_weights"] = pool_weights[row].tolist()
    return inputs, audit, pool_weights


def forward_with_pool_weights(model, inputs, cancer, device, pool_weights, *,
                              non_blocking=False) -> np.ndarray:
    """以 fp32/inference_mode 执行规则 5 的无参数 weighted pooling。"""
    import torch

    if model.training:
        raise ValueError("model must already be eval()")
    floating = [parameter for parameter in model.parameters() if parameter.is_floating_point()]
    if any(parameter.dtype != torch.float32 for parameter in floating):
        raise ValueError("model parameters must be fp32")
    with torch.inference_mode():
        logits = load_rule(5).weighted_forward(
            model, inputs, cancer, device, np.asarray(pool_weights, dtype=np.float64),
            non_blocking=bool(non_blocking),
        )
    if logits.ndim != 2 or logits.shape[1] != 4 or not torch.isfinite(logits).all():
        raise ValueError("model logits must be finite [B, 4]")
    return logits.detach().to(dtype=torch.float32).cpu().numpy()
