"""S0-force 报告包装：复用固定矩阵排版，并强制写出泄漏与平局边界。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_reference_reporting(path: Path):
    spec = importlib.util.spec_from_file_location("_s0_force_reference_reporting", Path(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载参考报告模块：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def mandatory_disclosure(freeze: dict) -> str:
    """C7–C9：每份结果报告开头共享的不可删除声明。"""
    return "\n".join([
        "## 强制路由、泄漏与解释边界",
        "",
        f"- valid A={float(freeze['a_mean']):.6f}、B={float(freeze['b_mean']):.6f}、valid B−A={float(freeze['b_minus_a']):+.6f}；valid 反对仍**强制启用** `enabled=true`。",
        "- 路由由已见 test 启发，因此本轮存在 **test 泄漏**；不是盲测、不是独立确认。",
        "- LUAD 的 `rna_100` 与 `both_100` 是固定 **m1** 的精确副本，`text_100` 是固定 **m0real** 的精确副本；这些平局不能算作患者检索胜利。",
        "- 若 LUAD 或五癌胜率改善，只能归因于“LUAD 按场景切换到固定 m1/m0real”；不得写成患者检索机制成立。",
        f"- **{int(freeze['current_wins'])}/5仅为探索性反事实**，不是效果验收；上游 3.progress 的历史记录仅作对照。",
        f"- LUAD 对 m1 的四场景等权差仅为 {float(freeze['luad_delta_m1']):+.6f}，应视为近似平局、不稳；不能据此作机制优越性声称。",
        f"- LUAD test 的 `none` 中“缺 RNA → m1”分支实际触发{int(freeze['none_m1_route_count'])}次；本轮相对 3.progress 的变化只来自 `rna_100`／`both_100` 改走 m1，`text_100` 未变。",
        "- 标题“LUAD-m1-force 组合”仅标识本轮协议；非 LUAD 的80格原样复用 2.progress 冻结组合。",
        "",
    ])


def _rename_strategy0(body: str) -> str:
    """只替换展示名称，底层三臂键仍保持固定矩阵的 strategy0/m1/m0real。"""
    body = body.replace(
        "- 执行验收与效果目标分开：即使文件、哈希和矩阵完整，`4/5`目标未达也必须如实写为未达。",
        "- 执行验收与效果目标分开：严格胜率由本次冻结矩阵动态计算；即使达到既定数量目标，也不构成患者检索机制成立的证据。",
    ).replace(
        "- strategy0关闭时，LUAD沿用冻结组合；不得把上游复用误写成新的路由收益。",
        "- 本轮冻结配置为 `enabled=true`；LUAD 的路由收益只能与固定 m1/m0real 等价关系一起解释，非 LUAD 仍是上游复用。",
    )
    return body.replace("strategy0组合", "LUAD-m1-force 组合").replace("strategy0", "LUAD-m1-force")


def _none_m1_route_count(luad_route_counts: dict | None) -> int:
    """只统计 LUAD/none 中真实被路由为 m1 的患者，不把其他场景混入。"""
    if not luad_route_counts:
        return 0
    return sum(
        int(counts.get("m1", 0))
        for cell, counts in luad_route_counts.items()
        if str(cell).endswith("/none")
    )


def render_reports(*, rows: list[dict], config: dict, freeze: dict, test_fingerprint: str,
                   reference_reporting_path: Path, luad_route_counts: dict | None = None) -> dict[str, str]:
    """生成三份完整表格；数值统计仍由 3.progress 同一报告代码计算。"""
    reference = _load_reference_reporting(reference_reporting_path)
    base = reference.render_reports(rows, config=config, freeze=freeze, test_fingerprint=test_fingerprint)
    summary = reference.summarize(
        rows, cancers=tuple(config["cancers"]), seeds=tuple(config["seeds"]), grids=tuple(config["grids"]),
    )
    display_freeze = dict(freeze)
    display_freeze.update({
        "current_wins": summary["wins"],
        "luad_delta_m1": summary["cancer_means"]["LUAD"]["strategy0"] - summary["cancer_means"]["LUAD"]["m1"],
        "none_m1_route_count": _none_m1_route_count(luad_route_counts),
    })
    disclosure = mandatory_disclosure(display_freeze)
    return {
        name: "# " + name.removesuffix(".md") + "\n\n" + disclosure + _rename_strategy0(body)
        for name, body in base.items()
    }
