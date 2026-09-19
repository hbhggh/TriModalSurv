"""strategy0：由 valid 冻结开关控制的 LUAD 单患者推理路由。"""
from __future__ import annotations


_GRIDS = frozenset(("none", "rna_100", "text_100", "both_100"))
_ROUTES = frozenset(("upstream_combo", "m1", "m0real"))


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be boolean")
    return value


def route_patient(
    cancer: str,
    grid: str,
    rna_valid: bool,
    text_valid: bool,
    *,
    enabled: bool,
) -> str:
    """返回该患者应复用的冻结上游臂，绝不在此处做参数搜索。"""
    if grid not in _GRIDS:
        raise ValueError("invalid grid")
    rna_valid = _boolean(rna_valid, "rna_valid")
    text_valid = _boolean(text_valid, "text_valid")
    enabled = _boolean(enabled, "enabled")
    if not isinstance(cancer, str) or not cancer:
        raise ValueError("cancer must be non-empty")

    if not enabled or cancer != "LUAD":
        return "upstream_combo"
    if grid == "text_100":
        return "m0real"
    if grid in ("rna_100", "both_100"):
        return "m1"
    if not rna_valid:
        return "m1"
    return "upstream_combo"


def validate_route(route: str) -> str:
    if route not in _ROUTES:
        raise ValueError("invalid strategy0 route")
    return route
