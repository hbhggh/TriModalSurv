"""规则 1：text_100 默认整场走 m0real。"""
from __future__ import annotations


def should_skip_compensation(*, grid: str, cancer: str, ucec_exception: bool) -> bool:
    """返回该患者是否必须保持原始缺失，不调用任何补偿。"""
    if not isinstance(grid, str) or not isinstance(cancer, str):
        raise ValueError("grid/cancer 必须是字符串")
    return grid == "text_100" and not (cancer == "UCEC" and bool(ucec_exception))
