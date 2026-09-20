"""从旧评测器抽取的通用纯函数与原子状态写入。"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Mapping, Set, Tuple
MASKABLE_MODALITIES = ("rna", "text")

def grid_parts(grid: str) -> Tuple[str | None, int]:
    if grid == "none":
        return None, 0
    try:
        mode, rate_text = grid.rsplit("_", 1)
        rate = int(rate_text)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"无效缺失格点: {grid!r}") from exc
    if mode not in {"rna", "text", "both"} or rate not in {25, 50, 75, 100}:
        raise ValueError(f"无效缺失格点: {grid!r}")
    return mode, rate



def masked_modalities(grid: str) -> Tuple[str, ...]:
    mode, _ = grid_parts(grid)
    if mode is None:
        return ()
    if mode == "both":
        return MASKABLE_MODALITIES
    return (mode,)



def grid_sha256(grid: str, patient_ids: Iterable[str], members: Set[str]) -> str:
    allowed = set(patient_ids)
    digest = hashlib.sha256()
    for patient_id in sorted(allowed & members):
        for modality in masked_modalities(grid):
            digest.update(f"{patient_id}\t{modality}\n".encode("utf-8"))
    return digest.hexdigest()



def dual_risk_from_logits(logits):
    """复现 A=raw cumprod 与 B=sigmoid+clamp cumprod 两种风险。"""
    import torch

    if not torch.is_tensor(logits) or logits.ndim != 2:
        raise ValueError("logits 必须是二维 torch.Tensor")
    risk_a = -torch.sum(torch.cumprod(1.0 - logits, dim=1), dim=1)
    hazards_b = torch.clamp(torch.sigmoid(logits), 1e-6, 1.0 - 1e-6)
    risk_b = -torch.sum(torch.cumprod(1.0 - hazards_b, dim=1), dim=1)
    return risk_a, risk_b



def strip_data_parallel_prefix(state_dict: Mapping[str, object]) -> Dict[str, object]:
    normalized: Dict[str, object] = {}
    for key, value in state_dict.items():
        normalized_key = key[7:] if key.startswith("module.") else key
        if normalized_key in normalized:
            raise ValueError(f"checkpoint key 去除 module. 后冲突: {normalized_key}")
        normalized[normalized_key] = value
    return normalized



def extract_state_dict(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise TypeError("checkpoint 必须是 state_dict 或包含 state_dict 的映射")
    for key in ("state_dict", "model_state_dict"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            return nested
    return payload



def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _atomic_json_dump(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise

