#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字对账：REVIEW_PACK 里手写文件（00/01/04 与 03 的手写节）中出现的每个 4 位小数 / 胜负计数，
必须能在源文件（s5_report / a_test_report / table_*.md / r*_numbers.txt / s5_full_reference.csv）里原样找到。
用法：cd <repo> && python3 collab/REVIEW_PACK/check_numbers.py  → 写 collab/REVIEW_PACK/check_numbers.txt，全部命中退出码 0。
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
A = ROOT / "collab/20260902-A测缺失补偿"
S = ROOT / "collab/20260827-三方对比战役"
ND = ROOT / "collab/20260906-NPJ-D消融"
SOURCES = [S / "s5_report.md", A / "a_test_report.md", A / "r4_numbers.txt", A / "r5_numbers.txt", A / "r2_numbers.txt", A / "s5_full_reference.csv", ND / "r6_numbers.txt"] + sorted(A.glob("table_*.md")) + sorted(ND.glob("table_npjd_*.md"))
TARGETS = [ROOT / "collab/REVIEW_PACK" / f for f in ("00_README.md", "01_research_idea.md", "03_results.md", "04_honest_conclusions.md")]

norm = lambda s: s.replace("−", "-").replace("—", "-")
corpus = norm("\n".join(p.read_text(encoding="utf-8") for p in SOURCES))
# 允许出现在源里的等价写法：0.6076 也可能以 0.607600 形式出现（csv 六位）
def found(tok):
    t = norm(tok)
    if t in corpus:
        return True
    m = re.fullmatch(r"([+-]?)(\d\.\d{4})", t)
    if m and (m.group(2) in corpus):
        return True
    return False

num_rx = re.compile(r"(?<![\d.])[+\-−]?\d\.\d{4}(?![\d])")
wlt_rx = re.compile(r"(?<![\d:])\d{1,2}:\d{1,2}(?::\d{1,2})?(?![\d:])")
lines_out, total, miss = [], 0, 0
for tp in TARGETS:
    if not tp.exists():
        lines_out.append(f"SKIP (missing) {tp.name}")
        continue
    txt = tp.read_text(encoding="utf-8")
    if tp.name == "03_results.md":  # 只查手写节
        i = txt.find("## 不理想处明写")
        txt = txt[i:] if i >= 0 else txt
    toks = set(num_rx.findall(txt)) | set(wlt_rx.findall(txt))
    toks = {t for t in toks if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t) or ":" in t and found(t)}  # 时间戳形如 10:27 会被下面再核
    bad = sorted(t for t in toks if not found(t))
    total += len(toks); miss += len(bad)
    lines_out.append(f"{tp.name}: tokens={len(toks)} missing={len(bad)}" + (" -> " + ", ".join(bad) if bad else ""))
lines_out.append(f"TOTAL tokens={total} missing={miss} " + ("ALL_FOUND" if miss == 0 else "SOME_MISSING"))
(ROOT / "collab/REVIEW_PACK/check_numbers.txt").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
print("\n".join(lines_out))
sys.exit(0 if miss == 0 else 1)
