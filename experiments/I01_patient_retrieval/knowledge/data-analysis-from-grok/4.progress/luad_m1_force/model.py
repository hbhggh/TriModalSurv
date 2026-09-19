"""S0-force 的零参数患者级路由。

只决定复用哪条已经冻结的推理路径；不读取或修改权重、缓存、split、患者库。
"""

from __future__ import annotations


_GRIDS = frozenset(("none", "rna_100", "text_100", "both_100"))
_ROUTES = frozenset(("upstream_combo", "m1", "m0real"))


def _boolean(value: object, name: str) -> bool:
    """拒绝 0/1 等伪布尔值，防止冻结配置静默回到旧门禁。"""
    if type(value) is not bool:
        raise ValueError(f"{name} 必须是 JSON 布尔值")
    return value


def validate_frozen_force(freeze: dict) -> bool:
    """S0-force 唯一允许的状态是 enabled=true，valid 不拥有否决权。"""
    if not isinstance(freeze, dict):
        raise ValueError("冻结配置必须是对象")
    if freeze.get("enabled") is not True:
        raise ValueError("S0-force 冻结配置必须 enabled=true")
    return True


def route_patient(
    *,
    cancer: str,
    grid: str,
    rna_valid: bool,
    text_valid: bool,
) -> dict[str, object]:
    """返回单患者复用路径与审计字段。

    非 LUAD 没有 strategy0 开关语义，因此 `strategy0_enabled=null`，绝不把它写成
    `false`。LUAD 强制路由严格沿用 3.progress 的分支，但不再接收可关闭的 enabled。
    """
    if not isinstance(cancer, str) or not cancer:
        raise ValueError("cancer 必须是非空字符串")
    if grid not in _GRIDS:
        raise ValueError("invalid grid")
    rna_valid = _boolean(rna_valid, "rna_valid")
    text_valid = _boolean(text_valid, "text_valid")

    if cancer != "LUAD":
        return {"route": "upstream_combo", "strategy0_enabled": None}

    # text_100 整场景固定 m0real，优先于患者天然缺失状态。
    if grid == "text_100":
        route = "m0real"
    # 人工遮挡 RNA 的场景固定 m1；both_100 同时让两种缺失位走 m1。
    elif grid in ("rna_100", "both_100"):
        route = "m1"
    # none 仅保留天然 RNA 缺失／双缺时的 m1；仅缺 Text 与完整患者沿用组合。
    elif not rna_valid:
        route = "m1"
    else:
        route = "upstream_combo"

    if route not in _ROUTES:
        raise RuntimeError("未知 S0-force 路由")
    return {"route": route, "strategy0_enabled": True}

