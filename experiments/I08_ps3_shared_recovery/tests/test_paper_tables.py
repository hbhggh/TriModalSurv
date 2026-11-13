"""Paper-table generator guards: single-column hyperparameter rule and zero-hallucination provenance.

Two layers (see handoff-论文生成.md §0.2 G0 and §4–5):
  * Synthetic mutation tests (always run): a comparator row reading a tuned key, Ours reading ``@default``,
    a dual ``X`` / ``X@default`` pair, a stray number in a note, or a tampered ledger JSON must all be rejected.
  * Real-ledger tests (skipped only when the ledger directory is absent): the generator output obeys the
    rules, every I08 number is re-derived here by an independent implementation that reads the raw
    fold JSONs, and the files on disk equal the in-memory build (pytest never writes ``tables/``).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

from experiments.I08_ps3_shared_recovery.tools import generate_paper_tables as gpt

REPO = Path(__file__).resolve().parents[3]
I08_DIR = REPO / gpt.I08_RES_REL
I07_DIR = REPO / gpt.I07_RES_REL
OUT_DIR = REPO / gpt.OUT_REL

CANCERS_I08 = ("BLCA", "BRCA", "LUAD", "LGG", "UCEC")
CANCERS_PRIME = ("UCEC", "LUAD", "LGG", "BRCA", "BLCA")
PATTERNS = ("rna", "wsi", "text", "rna+wsi", "rna+text", "wsi+text")
EXPECTED_FILES = (
    "table1.tex", "table2.tex", "table3.tex", "table4.tex",
    "table_s1.tex", "table_s2.tex", "table_s3.tex", "table_s4.tex", "table_s5.tex",
    "paper_tables_preview.md",
)
RULE_FILES = ("table1.tex", "table2.tex", "table3.tex", "table4.tex", "table_s1.tex", "table_s2.tex", "table_s3.tex")
KEY_RE = re.compile(r"\\texttt\{(M\d+(?:-[abc]|-base)?(?:/b)?(?:@default)?)\}")

needs_ledger = pytest.mark.skipif(
    not (I08_DIR / "run_meta.json").exists() or not (I07_DIR / "render" / "results.md").exists(),
    reason="ledger results directory absent on this machine",
)


# ---------------------------------------------------------------------------------------------
# Independent output-level auditor (does not use the generator's metric code)
# ---------------------------------------------------------------------------------------------

def _raw_runs(i08_dir: Path) -> dict:
    return {(c, f): json.loads((i08_dir / "val_runs" / f"{c}_fold{f}.json").read_text(encoding="utf-8"))
            for c in CANCERS_I08 for f in range(5)}


def _ci(runs, key, c, f, p):
    return runs[(c, f)]["methods"][key]["val"]["cindex"][p]


def _macro(runs, key, what):
    """5-cancer macro of the 5-fold mean; ``what`` is a pattern, 'full', '1mod', '2mod' or 'miss6'."""
    groups = {"1mod": PATTERNS[:3], "2mod": PATTERNS[3:], "miss6": PATTERNS}
    pats = groups.get(what, (what,))
    per_c = [np.mean([np.mean([_ci(runs, key, c, f, p) for p in pats]) for f in range(5)]) for c in CANCERS_I08]
    return float(np.mean(per_c))


def _per_cancer_miss6(runs, key, c):
    return float(np.mean([np.mean([_ci(runs, key, c, f, p) for p in PATTERNS]) for f in range(5)]))


def _data_rows(tex: str):
    for line in tex.splitlines():
        s = line.strip()
        if s.endswith("\\\\") and "&" in s and not s.startswith(("\\textbf{Method", "\\textbf{Variant", "\\multicolumn")):
            yield s


def _cells(row: str):
    return [c.strip() for c in row[:-2].split("&")]


def _first_num(cell: str):
    m = re.search(r"[+-]?\d+\.\d+", cell)
    return m.group(0) if m else None


def audit_single_column_keys(tex: str) -> list:
    """Every I08 row label key must be Ours (M6-a) or an @default / no-grid key; no X and X@default pair."""
    errors, keys = [], set()
    for row in _data_rows(tex):
        found = KEY_RE.findall(_cells(row)[0] + " " + (_cells(row)[1] if len(_cells(row)) > 1 else ""))
        for k in found:
            k = k.replace("/b", "")
            keys.add(k)
            if not (k == "M6-a" or k.endswith("@default") or k in ("M0-a", "M0-b", "M9-base")):
                errors.append(f"tuned key {k!r} on a comparator row: {row[:80]}")
    for k in keys:
        if k.endswith("@default") and k[: -len("@default")] in keys:
            errors.append(f"dual column {k[:-8]!r} and {k!r}")
    return errors


SEMANTICS = {
    # filename: (columns, decimals) for rows that carry an M-key label
    "table3.tex": (list(PATTERNS) + ["1mod", "2mod", "miss6"], 4),
    "table4.tex": (["1mod", "2mod", "miss6"], 4),
    "table_s3.tex": (list(PATTERNS) + ["1mod", "2mod", "miss6"], 4),
    "table2.tex": (["full", "rna+text", "wsi+text", "rna+wsi", "wsi", "rna", "text", "miss6"], 4),
    "table_s2.tex": ([f"cancer:{c}" for c in CANCERS_I08] + ["miss6"], 4),
    "table1.tex": ([f"cancer:{c}" for c in CANCERS_PRIME] + ["miss6"], 3),
}


def audit_values(name: str, tex: str, runs, semantics=None) -> list:
    """Recompute every number of every M-key row from the raw fold JSONs and compare the rendered string."""
    cols, dec = (semantics or SEMANTICS)[name]
    errors, checked = [], 0
    for row in _data_rows(tex):
        cells = _cells(row)
        keys = KEY_RE.findall(cells[0] + " " + (cells[1] if len(cells) > 1 else ""))
        if not keys:
            continue
        key = keys[-1].replace("/b", "")
        nums = [c for c in cells if _first_num(c) is not None and not re.search(r"\\checkmark|\\times|\\circ", c)]
        nums = [n for n in nums if not KEY_RE.search(n)][: len(cols)]
        if len(nums) < len(cols):
            errors.append(f"{name}: row for {key} has {len(nums)} numeric cells, expected {len(cols)}")
            continue
        for col, cell in zip(cols, nums):
            if col.startswith("cancer:"):
                exp = _per_cancer_miss6(runs, key, col.split(":")[1])
            else:
                exp = _macro(runs, key, col)
            if _first_num(cell).lstrip("+") != f"{exp:.{dec}f}":
                errors.append(f"{name}: {key} {col} shows {_first_num(cell)} but ledger gives {exp:.{dec}f}")
            checked += 1
    if checked == 0:
        errors.append(f"{name}: no ledger-backed numeric cell found")
    return errors


def audit_i07_avg_sd(table1: str, i07_dir: Path) -> list:
    """The I07 rows' Avg SD must be the sample SD (n-1) of the five cohort means, computed, not typed."""
    errors = []
    arms = {"Standalone WSI-only": "wsi", "Standalone RNA-only": "rna", "Standalone Text-only": "text",
            "Bypass (I07 Test)": "tri", "Bypass (\\texttt{I07} Test)": "tri"}
    seen = set()
    for row in _data_rows(table1):
        label = _cells(row)[0]
        arm = next((a for k, a in arms.items() if k in label), None)
        if arm is None:
            continue
        seen.add(arm)
        means = []
        for c in CANCERS_PRIME:
            v = [json.loads((i07_dir / "runs" / c / f"fold{f}" / arm / "test_metrics.json").read_text())["c_index"]["full"]
                 for f in range(5)]
            means.append(np.mean(v))
        exp = f"{np.mean(means):.3f}$\\pm${np.std(means, ddof=1):.3f}"
        if _cells(row)[-1] != exp:
            errors.append(f"I07 {arm} Avg shows {_cells(row)[-1]!r}, computed {exp!r}")
    for arm in ("wsi", "rna", "text", "tri"):
        if arm not in seen:
            errors.append(f"I07 {arm} row missing from table1")
    return errors


def audit_prime_rows(table1: str) -> list:
    errors = []
    for name in gpt.PRIME_TABLE_II_NAMES:
        if not any(_cells(r)[0].startswith(name + "$^\\dagger$") for r in _data_rows(table1)):
            errors.append(f"PRIME Table II row {name!r} missing")
    return errors


def audit_preview_pipes(md: str) -> list:
    """E52: every Markdown table row has the same pipe count as its header."""
    errors, header = [], None
    for i, line in enumerate(md.splitlines(), 1):
        if line.startswith("|"):
            n = line.count("|")
            if header is None:
                header = n
            elif n != header:
                errors.append(f"preview line {i}: {n} pipes vs header {header}")
        else:
            header = None
    return errors


def audit_directory(tables: dict, runs, i07_dir: Path, semantics=None) -> dict:
    """Run every output-level check; returns {check_name: [errors]}."""
    res = {"missing_files": [f for f in EXPECTED_FILES if f not in tables]}
    res["forbidden_tokens"] = [f"{n}: {t}" for n, txt in tables.items() for t in gpt.FORBIDDEN_TOKENS if t in txt]
    res["single_column_keys"] = [f"{n}: {e}" for n in RULE_FILES if n in tables for e in audit_single_column_keys(tables[n])]
    res["values"] = [e for n in (semantics or SEMANTICS) if n in tables for e in audit_values(n, tables[n], runs, semantics)]
    res["i07_avg_sd"] = audit_i07_avg_sd(tables["table1.tex"], i07_dir) if "table1.tex" in tables else ["no table1"]
    res["prime_rows"] = audit_prime_rows(tables["table1.tex"]) if "table1.tex" in tables else ["no table1"]
    res["preview_pipes"] = audit_preview_pipes(tables.get("paper_tables_preview.md", ""))
    res["user_paths"] = [n for n, txt in tables.items() if any(p in txt for p in ("/" + "Users/", "/" + "home/"))]
    return res


# ---------------------------------------------------------------------------------------------
# Synthetic mutation tests (rule checker and provenance checker reject wrong protocols)
# ---------------------------------------------------------------------------------------------

def _rec(key, role, table="table3.tex", text="0.6500"):
    return gpt.CellRecord(table=table, role=role, kind="i08_val", key=key, metric="miss6", text=text)


def test_rule_accepts_protocol():
    gpt.check_single_column([_rec("M6-a", "ours"), _rec("M7@default", "comparator"), _rec("M0-a", "comparator"),
                             _rec("M9-base", "comparator")])


@pytest.mark.parametrize("records", [
    [_rec("M7", "comparator")],                                     # tuned comparator
    [_rec("M6-a@default", "ours")],                                 # Ours at default
    [_rec("M2", "ours")],                                           # Ours is not M6-a
    [_rec("M6-a", "comparator")],                                   # tuned Ours used as a comparator
    [_rec("M2", "comparator"), _rec("M2@default", "comparator")],   # dual column (also tuned)
    [_rec("M6-a", "ours"), _rec("M6-a@default", "comparator")],     # dual column for Ours
])
def test_rule_rejects_wrong_protocol(records):
    with pytest.raises(gpt.SingleColumnViolation):
        gpt.check_single_column(records)


def test_rule_ignores_tables_outside_scope():
    # S4/S5 are mechanism tables evaluated on the fixed default M2 base; they are not method comparisons.
    gpt.check_single_column([_rec("M2", "reference", table="table_s4.tex")])


def test_paired_stat_records_are_checked():
    ok = gpt.CellRecord("table3.tex", "ours", "i08_stat", "M6-a|M7@default", "mean_diff", "+0.0252")
    gpt.check_single_column([ok])
    bad = gpt.CellRecord("table3.tex", "ours", "i08_stat", "M6-a|M7", "mean_diff", "+0.0252")
    with pytest.raises(gpt.SingleColumnViolation):
        gpt.check_single_column([bad])


def test_template_audit_rejects_unregistered_numbers():
    """Codex round-1 finding 2: integers, exponents and copies of a registered number must all be rejected."""
    records = [gpt.CellRecord("table3.tex", "ours", "i08_val", "M6-a", "miss6", "\\textbf{0.6657}"),
               gpt.CellRecord("table3.tex", "ours", "i08_stat", "M6-a|M0-a", "p_one", "=1.25\\times10^{-4}")]
    s0, s1 = gpt.sentinel(0), gpt.sentinel(1)
    ok = f"\\texttt{{M6-a}} & {s0} \\\\ one-sided $p{s1}$ over 256-$d$ features"
    gpt.audit_template("table3.tex", ok, records)
    bad = {
        "new decimal": ok + " 0.6626",
        "integer count": ok + " ($n=7555$)",
        "hyperparameter": ok + " $K=11$",
        "rewritten exponent": ok + " $p=1.25\\times10^{-3}$",
        "copied number": ok + " 0.6657",
        "fraction": ok + " 22/25",
        "duplicated sentinel": ok + f" {s0}",
        "missing sentinel": ok.replace(s1, ""),
    }
    for what, tpl in bad.items():
        with pytest.raises(gpt.ProvenanceError):
            gpt.audit_template("table3.tex", tpl, records)
            pytest.fail(f"audit accepted: {what}")


def test_prime_constants_are_internally_consistent():
    # Table II: Avg mean and Avg SD (n-1 across cohorts) must be reproducible from the five cohort means.
    assert len(gpt.PRIME_TABLE_II) == 19
    for row in gpt.PRIME_TABLE_II:
        means = [m for m, _ in row["cohorts"]]
        assert abs(np.mean(means) - row["avg"][0]) <= 0.0011, row["name"]
        assert abs(np.std(means, ddof=1) - row["avg"][1]) <= 0.0011, row["name"]
    assert [r["name"] for r in gpt.PRIME_TABLE_IV] == ["Scratch (FT)", "Pretrained (LP)", "Pretrained (LP+Missing)"]
    for name in ("DrFuse", "RedCore", "M3Care", "MedFuse", "ShaSpec"):
        assert all(name not in r["name"] for r in gpt.PRIME_TABLE_II + gpt.PRIME_TABLE_IV)


def _synthetic_prime_text(task2_first=False):
    lines = ["TABLE II", " " * 24 + "Img     RNA     Text"]
    for r in gpt.PRIME_TABLE_II:
        vals = " ".join(f"{m:.3f}±{s:.3f}" for m, s in list(r["cohorts"]) + [r["avg"]])
        marks = list(" " * 24)
        for flag, col in zip(r["mods"], (24, 32, 40)):
            marks += list(" " * (col - len(marks))) + (["✓"] if flag else [" "])
        lines.append(("  " + r["pdf_name"]).ljust(24) + "".join(marks[24:]).ljust(24) + vals)
    lines.append("TABLE IV")
    task2 = "  Scratch (FT)  " + " ".join(["0.656±0.064"] * 7)
    if task2_first:
        lines.append(task2)
    for r in gpt.PRIME_TABLE_IV:
        lines.append(f"  Task-1  {r['pdf_name']}  " + " ".join(f"{m:.3f}±{s:.3f}" for m, s in r["cells"]))
    lines.append(task2)
    return "\n".join(lines)


def test_prime_text_verifier_detects_typo_and_wrong_row():
    text = _synthetic_prime_text()
    gpt.verify_prime_text(text)
    with pytest.raises(gpt.ProvenanceError):
        gpt.verify_prime_text(text.replace("0.595±0.060", "0.596±0.060"))
    with pytest.raises(gpt.ProvenanceError):  # a Task-2 row in the Task-1 position must not be accepted
        gpt.verify_prime_text(_synthetic_prime_text(task2_first=True))


@needs_ledger
@pytest.mark.parametrize("field_,bad", [("name", "Img-only (ours)"), ("mods", (1, 1, 1)), ("group", "multi"),
                                        ("pdf_name", "ABMIL")])
def test_build_rejects_prime_row_metadata_drift(monkeypatch, field_, bad):
    """Codex round-2 finding 1: method name, modality marks and group must match the PDF row, not only the values."""
    import copy
    rows = copy.deepcopy(gpt.PRIME_TABLE_II)
    rows[0][field_] = bad
    monkeypatch.setattr(gpt, "PRIME_TABLE_II", rows)
    with pytest.raises(gpt.ProvenanceError):
        gpt.build(repo_root=REPO)


@needs_ledger
def test_build_rejects_prime_table_iv_name_drift(monkeypatch):
    import copy
    rows = copy.deepcopy(gpt.PRIME_TABLE_IV)
    rows[1]["name"] = "Pretrained (LP+Missing)"
    monkeypatch.setattr(gpt, "PRIME_TABLE_IV", rows)
    with pytest.raises(gpt.ProvenanceError):
        gpt.build(repo_root=REPO)


def test_record_audit_rejects_free_text():
    """Codex round-2 finding 2: numbers hidden inside a record's text, or text that is not the formatted value."""
    good = gpt.CellRecord("table3.tex", "ours", "i08_val", "M6-a", "miss6@macro", "0.6657", "f4", (0.66570,))
    gpt.audit_records([good])
    import dataclasses
    variants = {
        "extra integer": dataclasses.replace(good, text="0.6657 and n=7555"),
        "extra exponent": dataclasses.replace(good, text="0.6657 p=1.25\\times10^{-3}"),
        "second number": dataclasses.replace(good, text="0.6657 / 0.6519"),
        "text not from value": dataclasses.replace(good, text="0.6658"),
        "format not allowed for kind": dataclasses.replace(good, fmt="int", value=(1,), text="1"),
        "unknown format": dataclasses.replace(good, fmt="raw"),
        "wrong arity": dataclasses.replace(good, value=(0.6657, 0.1)),
        "non-numeric value": dataclasses.replace(good, value=("0.6657",)),
        "no format (free text)": dataclasses.replace(good, fmt=""),
    }
    for what, rec in variants.items():
        with pytest.raises(gpt.ProvenanceError):
            gpt.audit_records([rec])
            pytest.fail(f"record audit accepted: {what}")


def test_reg_add_takes_typed_values_only():
    import inspect
    params = list(inspect.signature(gpt.Reg.add).parameters)
    assert params[:7] == ["self", "role", "kind", "key", "metric", "fmt", "value"] and "text" not in params


@needs_ledger
def test_i08_values_are_rechecked_against_ledger():
    s = gpt.I08Stats(gpt.load_ledger(I08_DIR))
    m = s.macro_mean("M6-a", "miss6")
    ok = gpt.CellRecord("table3.tex", "ours", "i08_val", "M6-a", "miss6@macro", f"{m:.4f}", "f4", (m,))
    gpt.recheck_i08_values([ok], s)
    foreign = gpt.CellRecord("table3.tex", "ours", "i08_val", "M6-a", "miss6@macro", "0.6700", "f4", (0.67,))
    with pytest.raises(gpt.ProvenanceError):
        gpt.recheck_i08_values([foreign], s)


@needs_ledger
def test_build_rejects_prime_constant_drift(monkeypatch):
    """Codex round-1 finding 1: build() itself must reject a PRIME constant that differs from the pinned extract."""
    import copy
    rows = copy.deepcopy(gpt.PRIME_TABLE_II)
    rows[0]["avg"] = (0.999, rows[0]["avg"][1])
    monkeypatch.setattr(gpt, "PRIME_TABLE_II", rows)
    with pytest.raises(gpt.ProvenanceError):
        gpt.build(repo_root=REPO)


def test_prime_extract_is_pinned(tmp_path):
    src = (REPO / gpt.PRIME_EXTRACT_REL).read_text(encoding="utf-8")
    gpt.load_prime_extract(REPO)
    dst = tmp_path / gpt.PRIME_EXTRACT_REL
    dst.parent.mkdir(parents=True)
    dst.write_text(src.replace("0.620±0.052", "0.999±0.052"), encoding="utf-8")
    with pytest.raises(gpt.ProvenanceError):
        gpt.load_prime_extract(tmp_path)


def _prime_pdf():
    import os
    rel = Path("vscode 重构") / "Template_refactor" / "科研" / "论文阅读" / "Prime" / "Prime.pdf"
    cands = [Path(os.environ["PRIME_PDF"])] if os.environ.get("PRIME_PDF") else []
    cands += [REPO.parents[0] / rel, REPO.parents[1] / rel]
    return next((c for c in cands if c.exists()), None)


@pytest.mark.skipif(_prime_pdf() is None or shutil.which("pdftotext") is None,
                    reason="Prime.pdf or pdftotext not available on this machine")
def test_prime_extract_reproduced_from_pdf():
    gpt.verify_extract_against_pdf(_prime_pdf(), REPO)


# ---------------------------------------------------------------------------------------------
# Ledger binding (tamper and test-split guards) on a temporary copy of the real ledger
# ---------------------------------------------------------------------------------------------

def _copy_ledger(tmp_path: Path) -> Path:
    dst = tmp_path / "ledger"
    (dst / "val_runs").mkdir(parents=True)
    for f in ("run_meta.json", "val_ablation_report_v1.md"):
        shutil.copy2(I08_DIR / f, dst / f)
    for p in (I08_DIR / "val_runs").glob("*.json"):
        shutil.copy2(p, dst / "val_runs" / p.name)
    return dst


def _rewrite(path: Path, mutate) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    mutate(d)
    path.write_text(json.dumps(d), encoding="utf-8")


@needs_ledger
def test_ledger_loads_and_binds_hashes():
    runs = gpt.load_ledger(I08_DIR)
    assert len(runs) == 25


@needs_ledger
def test_ledger_rejects_tampered_fold_json(tmp_path):
    dst = _copy_ledger(tmp_path)
    _rewrite(dst / "val_runs" / "BLCA_fold0.json",
             lambda d: d["methods"]["M6-a"]["val"]["cindex"].__setitem__("rna", 0.99))
    with pytest.raises(gpt.LedgerError):
        gpt.load_ledger(dst)


@needs_ledger
def test_ledger_rejects_test_split_content(tmp_path):
    dst = _copy_ledger(tmp_path)
    target = dst / "val_runs" / "LGG_fold3.json"
    _rewrite(target, lambda d: d["methods"]["M0-a"].__setitem__("test", {"cindex": {"rna": 0.7}}))
    meta = json.loads((dst / "run_meta.json").read_text())
    meta["files"][target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (dst / "run_meta.json").write_text(json.dumps(meta))
    with pytest.raises(gpt.LedgerError, match="test"):
        gpt.load_ledger(dst, expected_run_meta_sha256=hashlib.sha256((dst / "run_meta.json").read_bytes()).hexdigest())


@needs_ledger
def test_ledger_rejects_wrong_source_commit(tmp_path):
    dst = _copy_ledger(tmp_path)
    meta = json.loads((dst / "run_meta.json").read_text())
    meta["source"]["commit"] = "f4b30740" + "0" * 32
    (dst / "run_meta.json").write_text(json.dumps(meta))
    with pytest.raises(gpt.LedgerError):
        gpt.load_ledger(dst, expected_run_meta_sha256=hashlib.sha256((dst / "run_meta.json").read_bytes()).hexdigest())


def _copy_i07(tmp_path: Path) -> Path:
    dst = tmp_path / "i07"
    for rel in ("verify/verify_report.json", "verify/output_manifest.json", "render/results.md"):
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(I07_DIR / rel, dst / rel)
    for p in (I07_DIR / "runs").glob("*/fold*/*/test_metrics.json"):
        out = dst / p.relative_to(I07_DIR)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
    return dst


def _shift_wsi_blca0(dst: Path, delta: float) -> tuple:
    """Shift BLCA fold0 WSI C-index; return (old, new) BLCA cell and macro strings in results.md convention."""
    def cell_and_macro(root):
        cohort = {}
        for c in CANCERS_PRIME:
            v = [json.loads((root / "runs" / c / f"fold{f}" / "wsi" / "test_metrics.json").read_text())["c_index"]["full"]
                 for f in range(5)]
            cohort[c] = v
        blca = cohort["BLCA"]
        return f"{np.mean(blca):.3f} ± {np.std(blca):.3f}", f"{np.mean([np.mean(v) for v in cohort.values()]):.3f}"
    before = cell_and_macro(dst)
    _rewrite(dst / "runs" / "BLCA" / "fold0" / "wsi" / "test_metrics.json",
             lambda d: d["c_index"].__setitem__("full", d["c_index"]["full"] + delta))
    return before, cell_and_macro(dst)


@needs_ledger
def test_i07_rejects_metric_drift_hidden_by_rounding(tmp_path):
    """Codex round-3 finding R3-1: a drift invisible in results.md (3 d.p.) must still be rejected."""
    dst = _copy_i07(tmp_path)
    gpt.load_i07(dst)
    before, after = _shift_wsi_blca0(dst, 1e-6)
    assert before == after  # results.md cross-check alone cannot see this drift
    with pytest.raises(gpt.LedgerError):
        gpt.load_i07(dst)


@needs_ledger
def test_i07_rejects_metric_and_results_md_tampered_together(tmp_path):
    """Codex round-3 scenario: change a test_metrics.json and update results.md consistently; must still fail."""
    dst = _copy_i07(tmp_path)
    (old_cell, old_macro), (new_cell, new_macro) = _shift_wsi_blca0(dst, 0.05)
    md_path = dst / "render" / "results.md"
    md = md_path.read_text(encoding="utf-8")
    head, rest = md.split("## 结果（屏蔽列为零填充）", 1)
    sec, tail = rest.split("\n## ", 1)
    lines = sec.splitlines()
    for i, ln in enumerate(lines):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells and cells[0] == "BLCA":
            lines[i] = ln.replace(old_cell, new_cell, 1)
        if cells and cells[0] == "五癌宏平均":
            cells[2] = new_macro  # column order: cohort, tri, wsi, ...
            lines[i] = "| " + " | ".join(cells) + " |"
    md_path.write_text(head + "## 结果（屏蔽列为零填充）" + "\n".join(lines) + "\n## " + tail, encoding="utf-8")
    with pytest.raises(gpt.LedgerError, match="output_manifest|verify_report"):
        gpt.load_i07(dst)


@needs_ledger
@pytest.mark.parametrize("target", ["verify/verify_report.json", "verify/output_manifest.json"])
def test_i07_rejects_tampered_verification_ledger(tmp_path, target):
    dst = _copy_i07(tmp_path)
    p = dst / target
    raw = p.read_bytes()
    i = raw.index(b'": "') + 4 if target.endswith("manifest.json") else raw.index(b"0.6")
    tampered = raw[:i] + (b"f" if raw[i:i + 1] != b"f" else b"e") + raw[i + 1:]
    assert tampered != raw
    p.write_bytes(tampered)
    with pytest.raises(gpt.LedgerError):
        gpt.load_i07(dst)


# ---------------------------------------------------------------------------------------------
# Real-ledger end-to-end tests
# ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built():
    if not (I08_DIR / "run_meta.json").exists():
        pytest.skip("ledger results directory absent on this machine")
    return gpt.build(repo_root=REPO)


@needs_ledger
def test_build_passes_independent_audit(built):
    res = audit_directory(built.outputs, _raw_runs(I08_DIR), I07_DIR)
    assert {k: v for k, v in res.items() if v} == {}


@needs_ledger
def test_mutated_row_spec_is_rejected(monkeypatch):
    rows = [list(r) for r in gpt.TABLE3_ROWS]
    i = next(j for j, r in enumerate(rows) if r[0] == "M7@default")
    rows[i][0] = "M7"
    monkeypatch.setattr(gpt, "TABLE3_ROWS", [tuple(r) for r in rows])
    with pytest.raises(gpt.SingleColumnViolation):
        gpt.build(repo_root=REPO)


@needs_ledger
def test_mutated_ours_spec_is_rejected(monkeypatch):
    rows = [tuple(r) if r[0] != "M6-a" else ("M6-a@default",) + tuple(r[1:]) for r in gpt.TABLE4_BLOCK_B]
    monkeypatch.setattr(gpt, "TABLE4_BLOCK_B", rows)
    with pytest.raises(gpt.SingleColumnViolation):
        gpt.build(repo_root=REPO)


@needs_ledger
def test_headline_numbers(built):
    s = built.summary
    assert s["ours_miss6"] == "0.6657"
    assert s["m0_miss6"] == "0.6519"
    assert s["cohorts_improved"] == "5/5"
    assert s["ours_best_patterns_table2"] == 6
    assert s["vs_M0-a"]["wins"] == 22 and s["vs_M0-a"]["n"] == 25
    assert s["vs_M7@default"]["wins"] == 18
    assert s["vs_M2@default"]["wins"] == 18 and s["vs_M2@default"]["ties"] == 3


@needs_ledger
def test_every_ledger_number_registered(built):
    for name, tpl in built.templates.items():
        gpt.audit_template(name, tpl, built.records)
    kinds = {r.kind for r in built.records}
    assert kinds <= {"i08_val", "i08_stat", "i08_interp", "i07_test", "prime", "prime_derived", "config"}


@needs_ledger
def test_disk_tables_equal_build(built):
    for name, content in built.outputs.items():
        path = OUT_DIR / name
        assert path.exists(), f"{name} not exported; run the generator"
        assert path.read_text(encoding="utf-8") == content, f"{name} on disk is stale; rerun the generator"


@needs_ledger
def test_one_float_per_file_and_landscape_tables(built):
    """Each \\input file holds exactly one numbered float; long-label S2/S3 are landscape (rotating package)."""
    for name, tex in built.outputs.items():
        if not name.endswith(".tex"):
            continue
        env = "sidewaystable" if name in ("table_s2.tex", "table_s3.tex") else "table*"
        assert tex.count("\\caption{") == 1, name
        assert tex.count(f"\\begin{{{env}}}") == 1 and tex.count(f"\\end{{{env}}}") == 1, name
        assert "\\textwidth" not in tex, name  # \linewidth follows the rotated frame
