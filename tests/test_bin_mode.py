"""分箱协议单测（验收 ⓪，CPU、无数据、<5 s）。

用法（先 `export PYTHONDONTWRITEBYTECODE=1`，cwd = NPJ 仓根）：
    python3 tests/test_bin_mode.py            # 独立运行，逐条打印断言结果
    python3 -m pytest tests/test_bin_mode.py  # pytest 亦可

补丁前快照路径由环境变量 ``NPJ_DATASET_BASELINE`` 指定（默认取本单 scratchpad 快照）。

真实 `TCGASurDataset` 需要 img/text/rna 特征目录才能构造（无特征时 selected_pids 为空、
`pd.cut` 直接抛错），本机无这些数据，因此按 plan.md 允许的降级口径测两件事：
 (1) 把 `__init__` 里 **author 分箱段** 与 **新增 train_quantile 段** 的源码原文抽出来，
     注入合成 `self` 后 exec —— 测的是真正会跑的那几行，不是复写的等价物；
 (2) 抽出的纯函数 `compute_quantile_edges` / `assign_bins` 直接单测。
"""

import os
import sys
import textwrap
import types
import unittest
from pathlib import Path

NPJ_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for _path in (str(NPJ_ROOT), str(TESTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from tests.test_mean_fusion import install_stubs  # noqa: E402

install_stubs()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from trimodalsurv.data.tcga_dataset import (  # noqa: E402
    TCGASurDataset,
    assign_bins,
    compute_quantile_edges,
    get_dataset_tcga_sur,
)

DEFAULT_BASELINE = Path(
    "/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/"
    "d9b60c11-2928-47a3-b644-ee7a4e66f22c/scratchpad/capl_before/"
    "loc_utils_3yr/tcga_dataset.py"
)
PATCHED = NPJ_ROOT / "src" / "trimodalsurv" / "data" / "tcga_dataset.py"

AUTHOR_START = "        survival_months_array = np.array(self.survival_months)"
AUTHOR_END = "        self.survival_months_bin = np.nan_to_num(self.survival_months_bin, nan=3).astype(int)"
NEW_START = "        # 指挥官小修（ProSurv-CAP4 派单 v2，2026-09-07）：新增 train_quantile 分箱协议。"
NEW_END = "        self.fallback_shapes = {'text': (200, 768), 'rna': (2048, 256)}"

# 含 NaN、重复值、0 与大值的合成生存月数
SYNTHETIC_MONTHS = [
    0.0, 12.0, 12.0, 12.0, 3.5, 60.0, 120.0, float("nan"), 24.0, 24.0,
    7.25, 99.9, float("nan"), 36.0, 1.0,
]
SYNTHETIC_CENSOR = [0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]


def _baseline_path() -> Path:
    return Path(os.environ.get("NPJ_DATASET_BASELINE", str(DEFAULT_BASELINE)))


def _extract_block(source_path: Path, start: str, end: str, *, inclusive_end=True) -> str:
    lines = source_path.read_text(encoding="utf-8").splitlines()
    try:
        first = lines.index(start)
    except ValueError as error:
        raise AssertionError(f"{source_path} 中找不到起始行: {start!r}") from error
    for offset in range(first + 1, len(lines)):
        if lines[offset] == end:
            last = offset if inclusive_end else offset - 1
            return "\n".join(lines[first:last + 1]) + "\n"
    raise AssertionError(f"{source_path} 中找不到结束行: {end!r}")


def _author_block(source_path: Path) -> str:
    return _extract_block(source_path, AUTHOR_START, AUTHOR_END)


def _new_block() -> str:
    return _extract_block(PATCHED, NEW_START, NEW_END, inclusive_end=False)


def _run_block(block_source: str, namespace: dict):
    from trimodalsurv.data import tcga_dataset as module

    scope = {
        "np": np,
        "pd": pd,
        "compute_quantile_edges": module.compute_quantile_edges,
        "assign_bins": module.assign_bins,
    }
    scope.update(namespace)
    exec(textwrap.dedent(block_source), scope)  # noqa: S102 — 执行的是被测源码原文
    return scope


def _fake_self(months=None, censorship=None):
    return types.SimpleNamespace(
        survival_months=list(SYNTHETIC_MONTHS if months is None else months),
        censorship=list(SYNTHETIC_CENSOR if censorship is None else censorship),
    )


# --------------------------------------------------------------------------
# ⓪-1 author 分箱段：源码原文未改动，且逐位输出相同
# --------------------------------------------------------------------------
def test_author_block_source_text_identical():
    baseline = _baseline_path()
    if not baseline.is_file():
        raise unittest.SkipTest(f"基线快照不存在: {baseline}（设 NPJ_DATASET_BASELINE 指定）")
    assert _author_block(baseline) == _author_block(PATCHED), "author 分箱段源码原文被改动"


def test_author_block_output_bitwise_identical():
    baseline = _baseline_path()
    if not baseline.is_file():
        raise unittest.SkipTest(f"基线快照不存在: {baseline}（设 NPJ_DATASET_BASELINE 指定）")

    before_self = _fake_self()
    after_self = _fake_self()
    _run_block(_author_block(baseline), {"self": before_self})
    _run_block(_author_block(PATCHED), {"self": after_self})

    before = before_self.survival_months_bin
    after = after_self.survival_months_bin
    assert before.dtype == after.dtype, f"dtype 不同: {before.dtype} vs {after.dtype}"
    assert np.array_equal(before, after), f"分箱结果不同: {before.tolist()} vs {after.tolist()}"
    assert set(np.unique(after).tolist()) <= {0, 1, 2, 3}, f"分箱越界: {np.unique(after).tolist()}"


def test_author_mode_ignores_bin_edges():
    """bin_mode='author' 时新块不读取 bin_edges_override（传入非法值也不报错、不改结果）。"""
    fake = _fake_self()
    _run_block(_author_block(PATCHED), {"self": fake})
    author_only = np.array(fake.survival_months_bin, copy=True)
    scope = _run_block(
        _new_block(),
        {
            "self": fake,
            "bin_mode": "author",
            "split": "train",
            "bin_edges_override": "非法值-不应被读取",
            "survival_months_array": np.array(fake.survival_months),
        },
    )
    del scope
    assert fake.bin_mode == "author"
    assert fake.bin_edges is None, f"author 模式不应产生 bin_edges: {fake.bin_edges}"
    assert np.array_equal(fake.survival_months_bin, author_only), "author 模式分箱被新块改写"


def test_unknown_bin_mode_rejected():
    fake = _fake_self()
    try:
        _run_block(
            _new_block(),
            {
                "self": fake,
                "bin_mode": "quantile",
                "split": "train",
                "bin_edges_override": None,
                "survival_months_array": np.array(fake.survival_months),
            },
        )
    except ValueError as error:
        assert "bin_mode" in str(error), error
    else:
        raise AssertionError("未知 bin_mode 应当抛 ValueError")


# --------------------------------------------------------------------------
# ⓪-2 train_quantile：边界、入箱、异常
# --------------------------------------------------------------------------
def test_quantile_edges_match_manual():
    months = np.array(SYNTHETIC_MONTHS, dtype=float)
    censor = np.array(SYNTHETIC_CENSOR, dtype=float)
    edges = compute_quantile_edges(months, censor)
    uncensored = months[censor == 0]
    uncensored = uncensored[np.isfinite(uncensored)]
    manual = np.quantile(uncensored, [0.25, 0.5, 0.75])
    assert edges.shape == (3,), edges.shape
    assert np.array_equal(edges, manual), f"{edges.tolist()} vs {manual.tolist()}"


def test_quantile_edges_reject_all_censored():
    months = np.array(SYNTHETIC_MONTHS, dtype=float)
    try:
        compute_quantile_edges(months, np.ones_like(months))
    except ValueError as error:
        assert "未删失" in str(error), error
    else:
        raise AssertionError("censorship 全 1 应当抛 ValueError")

    # 不触发侧（坑 V31）：恰好 4 名未删失可以算
    edges = compute_quantile_edges(
        np.array([1.0, 2.0, 3.0, 4.0, 5.0]), np.array([0, 0, 0, 0, 1])
    )
    assert np.array_equal(edges, np.quantile(np.array([1.0, 2.0, 3.0, 4.0]), [0.25, 0.5, 0.75]))

    try:
        compute_quantile_edges(np.array([1.0, 2.0, 3.0]), np.array([0, 0, 0]))
    except ValueError:
        pass
    else:
        raise AssertionError("未删失只有 3 人应当抛 ValueError")


def test_assign_bins_right_open_and_manual():
    edges = np.array([10.0, 20.0, 30.0])
    months = np.array([0.0, 9.999, 10.0, 15.0, 20.0, 29.5, 30.0, 100.0, np.nan])
    bins = assign_bins(months, edges)
    manual = np.digitize(months, edges, right=False).astype(int)
    assert np.array_equal(bins, manual), f"{bins.tolist()} vs {manual.tolist()}"
    # 右开区间：等于边界的月数落入右箱
    assert bins.tolist()[:8] == [0, 0, 1, 1, 2, 2, 3, 3], bins.tolist()
    # NaN 与 author 路径的 nan->3 一致
    assert bins.tolist()[8] == 3, bins.tolist()
    assert bins.dtype == np.dtype(int), bins.dtype


def test_train_quantile_block_train_and_valid_paths():
    fake_train = _fake_self()
    months = np.array(fake_train.survival_months, dtype=float)
    _run_block(
        _new_block(),
        {
            "self": fake_train,
            "bin_mode": "train_quantile",
            "split": "train",
            "bin_edges_override": None,
            "survival_months_array": months,
        },
    )
    manual_edges = compute_quantile_edges(months, np.array(SYNTHETIC_CENSOR, dtype=float))
    assert np.array_equal(fake_train.bin_edges, manual_edges), fake_train.bin_edges
    assert np.array_equal(
        fake_train.survival_months_bin, assign_bins(months, manual_edges)
    ), fake_train.survival_months_bin.tolist()

    # valid/test：传入 train 的边界后逐位与手算一致（不重算分位）
    valid_months = np.array([0.5, 13.0, 41.0, np.nan, 12.0])
    fake_valid = _fake_self(months=valid_months.tolist(), censorship=[1, 1, 1, 1, 1])
    _run_block(
        _new_block(),
        {
            "self": fake_valid,
            "bin_mode": "train_quantile",
            "split": "valid",
            "bin_edges_override": manual_edges,
            "survival_months_array": valid_months,
        },
    )
    assert np.array_equal(fake_valid.bin_edges, manual_edges)
    assert np.array_equal(
        fake_valid.survival_months_bin, np.digitize(valid_months, manual_edges, right=False)
    ), fake_valid.survival_months_bin.tolist()


def test_train_quantile_block_rejects_bad_edges():
    months = np.array(SYNTHETIC_MONTHS, dtype=float)

    # train 传入 bin_edges → ValueError
    try:
        _run_block(
            _new_block(),
            {
                "self": _fake_self(),
                "bin_mode": "train_quantile",
                "split": "train",
                "bin_edges_override": np.array([1.0, 2.0, 3.0]),
                "survival_months_array": months,
            },
        )
    except ValueError as error:
        assert "bin_edges" in str(error), error
    else:
        raise AssertionError("train split 传入 bin_edges 应当抛 ValueError")

    # valid 不传 bin_edges → ValueError
    try:
        _run_block(
            _new_block(),
            {
                "self": _fake_self(),
                "bin_mode": "train_quantile",
                "split": "test",
                "bin_edges_override": None,
                "survival_months_array": months,
            },
        )
    except ValueError as error:
        assert "bin_edges" in str(error), error
    else:
        raise AssertionError("test split 缺 bin_edges 应当抛 ValueError")

    # 边界个数不是 3 → ValueError
    try:
        _run_block(
            _new_block(),
            {
                "self": _fake_self(),
                "bin_mode": "train_quantile",
                "split": "valid",
                "bin_edges_override": np.array([1.0, 2.0]),
                "survival_months_array": months,
            },
        )
    except ValueError as error:
        assert "3" in str(error), error
    else:
        raise AssertionError("边界个数错误应当抛 ValueError")


# --------------------------------------------------------------------------
# ⓪-3 签名：新增关键字参数在参数表最后且默认值保持 author 路径
# --------------------------------------------------------------------------
def test_signatures_default_to_author():
    import inspect

    for function in (TCGASurDataset.__init__, get_dataset_tcga_sur):
        parameters = list(inspect.signature(function).parameters)
        assert parameters[-2:] == ["bin_mode", "bin_edges"], (function, parameters)
        defaults = inspect.signature(function).parameters
        assert defaults["bin_mode"].default == "author", function
        assert defaults["bin_edges"].default is None, function


TESTS = [
    test_author_block_source_text_identical,
    test_author_block_output_bitwise_identical,
    test_author_mode_ignores_bin_edges,
    test_unknown_bin_mode_rejected,
    test_quantile_edges_match_manual,
    test_quantile_edges_reject_all_censored,
    test_assign_bins_right_open_and_manual,
    test_train_quantile_block_train_and_valid_paths,
    test_train_quantile_block_rejects_bad_edges,
    test_signatures_default_to_author,
]


def _main() -> int:
    failures = 0
    skipped = 0
    for test in TESTS:
        try:
            test()
        except unittest.SkipTest as skip:
            skipped += 1
            print(f"SKIP {test.__name__}: {skip}")
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {type(error).__name__}: {error}")
        else:
            print(f"PASS {test.__name__}")
    verdict = "ALL_PASS" if failures == 0 else f"FAILURES={failures}"
    print(f"RESULT={verdict} SKIPPED={skipped}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
