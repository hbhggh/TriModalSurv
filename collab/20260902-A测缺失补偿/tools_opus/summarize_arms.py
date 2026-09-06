#!/usr/bin/env python3
"""通用臂对比汇总：读多臂评测 JSON 目录 → 逐 seed 表（主口径 cindex_B）+ 严格 > 胜负计数。

用法:
  summarize_arms.py --arm E0=<dir>[,<dir2>...] --arm E1=<dir> [--grids none,rna_100,text_100]
                    [--base E0] [--metric cindex_B] [--out table.md] [--tie-eps 1e-6]
                    [--legacy-winloss] [--pairwise-grid both_100 --pairwise-out pair.md]

JSON 命名 <prefix>_<CANCER>_s<seed>.json；格点结构与 eval_missing 输出一致。
臂身份只来自 --arm NAME=dir 的 NAME（JSON 的 arm 字段与文件名前缀均不可信）。

退出码: 0 正常 / 2 CONFLICT 或 CKPT_MISMATCH / 3 目录缺失或无可解析 json。
"""
import argparse
import json
import os
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

CANCERS = ["BLCA", "BRCA", "LUAD", "LGG", "UCEC"]
SEEDS = [123, 132, 213, 231, 321]
NA = "\u2014"  # em dash

FNAME_RX = re.compile(
    r"^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$"
)


def _resolve_dir(d):
    """相对路径优先按 cwd 解析；cwd 下不存在时回退 ROOT（脚本所在战役目录）。"""
    p = pathlib.Path(d)
    if p.is_absolute() or p.is_dir():
        return p
    alt = ROOT / d
    if alt.is_dir():
        return alt
    return p


def _die(msg, code):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load_dir(d):
    """加载单目录 → {(cancer, seed): {"grids": {grid: rec}, "checkpoint": str}}。"""
    path = _resolve_dir(d)
    out = {}
    names = sorted(os.listdir(path)) if path.is_dir() else []
    for n in names:
        if not n.endswith(".json"):
            continue
        p = os.path.join(str(path), n)
        m = FNAME_RX.match(n)
        if not m:
            print("SKIP %s" % p, file=sys.stderr)
            continue
        with open(p, encoding="utf-8") as fh:
            j = json.load(fh)
        g = j.get("grids") or {}
        rows = g if isinstance(g, list) else [dict(v, grid=k) for k, v in g.items()]
        out[(m.group("cancer"), int(m.group("seed")))] = {
            "grids": {r["grid"]: r for r in rows},
            "checkpoint": j.get("checkpoint"),
        }
    if not out:
        _die("ERROR: no result json in %s" % d, 3)
    return out


def load_arm(name, spec):
    """多目录按 (cancer, seed) 做 grids 级合并；冲突即 exit 2。"""
    dirs = [x for x in spec.split(",") if x != ""]
    if not dirs:
        _die("ERROR: no result json in %s" % spec, 3)
    merged = {}          # (cancer, seed) -> {grid: rec}
    ckpt = {}            # (cancer, seed) -> (checkpoint, dir)
    origin = {}          # (cancer, seed, grid) -> dir
    for d in dirs:
        cur = load_dir(d)
        for key, payload in cur.items():
            c, s = key
            if key in ckpt:
                prev_ck, prev_dir = ckpt[key]
                if payload["checkpoint"] != prev_ck:
                    _die(
                        "CKPT_MISMATCH arm=%s cancer=%s seed=%s dir1=%s dir2=%s ckpt1=%s ckpt2=%s"
                        % (name, c, s, prev_dir, d, prev_ck, payload["checkpoint"]),
                        2,
                    )
            else:
                ckpt[key] = (payload["checkpoint"], d)
            slot = merged.setdefault(key, {})
            for grid, rec in payload["grids"].items():
                if grid in slot:
                    _die(
                        "CONFLICT arm=%s cancer=%s seed=%s grid=%s dir1=%s dir2=%s"
                        % (name, c, s, grid, origin[(c, s, grid)], d),
                        2,
                    )
                slot[grid] = rec
                origin[(c, s, grid)] = d
    return merged


def get_val(store, cancer, seed, grid, metric):
    return store.get((cancer, seed), {}).get(grid, {}).get(metric)


def pair_stats(vals, base_vals, tie_eps):
    """返回 (pairs, w, l, t, delta_median or None)。仅双方非缺的 seed 参与配对。"""
    pairs = [(x, y) for x, y in zip(vals, base_vals) if x is not None and y is not None]
    w = sum(1 for x, y in pairs if x - y > tie_eps)
    t = sum(1 for x, y in pairs if abs(x - y) <= tie_eps)
    lo = sum(1 for x, y in pairs if y - x > tie_eps)
    d = statistics.median([x - y for x, y in pairs]) if pairs else None
    return pairs, w, lo, t, d


def med_or_none(vals):
    kept = [v for v in vals if v is not None]
    return statistics.median(kept) if kept else None


def build_main_table(D, arms, grids, base, metric, tie_eps, legacy):
    lines = ["# \u81c2\u5bf9\u6bd4\uff08\u4e3b\u53e3\u5f84 %s\uff1b\u5bf9\u7167\u81c2 %s\uff09" % (metric, base), ""]
    for grid in grids:
        lines += [
            "## \u683c\u70b9 %s" % grid,
            "",
            "| \u764c\u79cd | \u81c2 | " + " | ".join("s%d" % s for s in SEEDS)
            + " | \u4e2d\u4f4d | vs " + base + " \u4e25\u683c\u80dc\u8d1f |",
            "|" + "---|" * (len(SEEDS) + 4),
        ]
        for c in CANCERS:
            for arm in arms:
                vals = [get_val(D[arm], c, s, grid, metric) for s in SEEDS]
                cells = ["%.4f" % v if v is not None else NA for v in vals]
                med = med_or_none(vals)
                wl = ""
                if arm != base:
                    bv = [get_val(D[base], c, s, grid, metric) for s in SEEDS]
                    pairs, w, lo, t, d = pair_stats(vals, bv, tie_eps)
                    if legacy:
                        lw = sum(1 for x, y in pairs if x > y)
                        wl = "%d:%d" % (lw, len(pairs) - lw)
                        if pairs:
                            wl += " (\u0394\u4e2d\u4f4d %+.4f)" % d
                    elif pairs:
                        wl = "%d:%d:%d (\u0394\u4e2d\u4f4d %+.4f)" % (w, lo, t, d)
                head = "| %s | %s | " % (c, arm) + " | ".join(cells)
                head += " | %.4f |" % med if med is not None else " | %s |" % NA
                lines.append(head + " %s |" % wl)
        lines.append("")
    missing = [
        (arm, c, s)
        for arm in arms
        for c in CANCERS
        for s in SEEDS
        if (c, s) not in D[arm]
    ]
    lines.append(
        "\u7f3a\u683c\uff1a%d" % len(missing) + (" \u2192 %r" % (missing[:8],) if missing else "")
    )
    return "\n".join(lines)


def build_pairwise(D, arms, grid, base, metric, tie_eps):
    lines = [
        "# \u683c\u70b9 %s \u914d\u5bf9\u6bd4\u8f83\uff08\u4e3b\u53e3\u5f84 %s\uff1b\u5bf9\u7167\u81c2 %s\uff1b5 seeds\uff1b"
        "\u80dc:\u8d1f:\u5e73\uff0c|\u0394|\u2264%r \u8bb0\u5e73\uff09" % (grid, metric, base, tie_eps),
        "",
    ]
    for arm in arms:
        if arm == base:
            continue
        lines += [
            "## %s vs %s" % (arm, base),
            "",
            "| \u764c\u79cd | %s \u4e2d\u4f4d | %s \u4e2d\u4f4d | \u80dc:\u8d1f:\u5e73 | \u914d\u5bf9\u0394\u4e2d\u4f4d |"
            % (base, arm),
            "|---|---|---|---|---|",
        ]
        tw = tl = tt = tn = 0
        for c in CANCERS:
            vals = [get_val(D[arm], c, s, grid, metric) for s in SEEDS]
            bv = [get_val(D[base], c, s, grid, metric) for s in SEEDS]
            pairs, w, lo, t, d = pair_stats(vals, bv, tie_eps)
            tw += w
            tl += lo
            tt += t
            tn += len(pairs)
            mb = med_or_none(bv)
            ma = med_or_none(vals)
            lines.append(
                "| %s | %s | %s | %d:%d:%d | %s |"
                % (
                    c,
                    "%.4f" % mb if mb is not None else NA,
                    "%.4f" % ma if ma is not None else NA,
                    w,
                    lo,
                    t,
                    "%+.4f" % d if d is not None else NA,
                )
            )
        lines.append(
            "| \u5408\u8ba1 | %s | %s | %d:%d:%d / %d | %s |" % (NA, NA, tw, tl, tt, tn, NA)
        )
        lines.append("")
    # 契约 ε3.4 明文「文件无末尾换行」：丢掉最后一个臂块尾部的空行（臂块之间的空行保留）
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True, help="name=dir[,dir2,...]")
    ap.add_argument("--grids", default="none,rna_100,text_100")
    ap.add_argument("--base", default=None, help="\u5bf9\u7167\u81c2\u540d\uff08\u9ed8\u8ba4\u7b2c\u4e00\u4e2a\uff09")
    ap.add_argument("--metric", default="cindex_B")
    ap.add_argument("--out", default=None)
    ap.add_argument("--tie-eps", dest="tie_eps", type=float, default=1e-6)
    ap.add_argument("--legacy-winloss", dest="legacy_winloss", action="store_true")
    ap.add_argument("--pairwise-grid", dest="pairwise_grid", default=None)
    ap.add_argument("--pairwise-out", dest="pairwise_out", default=None)
    a = ap.parse_args()

    if (a.pairwise_grid is None) != (a.pairwise_out is None):
        ap.error("--pairwise-grid and --pairwise-out must be given together")

    arms = {}
    for x in a.arm:
        name, spec = x.split("=", 1)
        arms[name] = spec
    base = a.base or list(arms)[0]
    if base not in arms:
        ap.error("--base %s not among --arm names %s" % (base, list(arms)))
    grids = a.grids.split(",")

    D = {name: load_arm(name, spec) for name, spec in arms.items()}

    txt = build_main_table(D, list(arms), grids, base, a.metric, a.tie_eps, a.legacy_winloss)
    print(txt)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)

    if a.pairwise_grid:
        ptxt = build_pairwise(D, list(arms), a.pairwise_grid, base, a.metric, a.tie_eps)
        with open(a.pairwise_out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(ptxt)


if __name__ == "__main__":
    main()
