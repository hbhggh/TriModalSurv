"""Generate the I08 manuscript tables (Tables 1-4, S1-S5) and a Markdown preview from ledgered results.

Layout follows handoff-论文生成.md v1.1 §4-5 (Table 1 mirrors PRIME Table II, Table 2 mirrors PRIME Table IV,
Table 3 is the 6-row progressive ablation, Table 4 the slot A / slot B operator comparison).

Data sources (nothing is transcribed by hand; every number cell is registered with its source):
  * I08 validation ledger ``results/val_dev-5c508587``: 25 fold JSONs bound by sha256 to ``run_meta.json``,
    whose own sha256, source commit, config sha256 and cache-manifest sha256 are pinned below. Only the
    ``val`` entries are read; any key containing ``test`` aborts the build (test_access: false).
  * I07 ledger ``results/i07-ps3-20261011``: per-fold ``test_metrics.json`` (full-input C-index only),
    cross-checked against the tracked ``render/results.md``.
  * PRIME (Prime.pdf) Table II (p. 6) and Table IV (p. 8), quoted verbatim as constants;
    ``--verify-prime-text`` re-checks them against ``pdftotext -layout`` output of those pages.

Single-column hyperparameter rule (handoff §0.2 G0.3): in Tables 1-4 and S1-S3 only Ours reads the
validation-selected key ``M6-a``; every other I08 row reads ``<ID>@default`` or a key without a grid
(``M0-a``, ``M0-b``, ``M9-base``). ``check_single_column`` enforces it on the registered cells, and
``audit_number_tokens`` rejects any decimal or ``a/b`` token in an output that no registered cell produced.

Usage (from the repository root, protomasksurv-exp1 interpreter):
  python -m experiments.I08_ps3_shared_recovery.tools.generate_paper_tables            # build, audit, write
  python -m experiments.I08_ps3_shared_recovery.tools.generate_paper_tables --check    # build, audit, diff only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[3]
I08_RES_REL = Path("experiments/I08_ps3_shared_recovery/results/val_dev-5c508587")
I07_RES_REL = Path("experiments/I07_ps3style_backbone/results/i07-ps3-20261011")
OUT_REL = Path("manuscript/bmc_initial_draft/tables")
GENERATOR_REL = "experiments/I08_ps3_shared_recovery/tools/generate_paper_tables.py"

LEDGER_PIN = {
    "run_meta_sha256": "f35c2c95fc89fea606dd4b4c98198ae4524d5604f17a5d35778bb5d8b2683e9f",
    "source_commit": "5c508587deec0c88e0b85ca7e162a90ae7ba5185",
    "config_sha256": "3afdcb16e9b080a3f92e20802f3d19be3bbb0b29815e8169b3f108c3ed5f4085",
    "cache_manifest_sha256": "b52767a8c5f871f164762b2b180237002bf3a02adb0040a13d757ab1a75e1f6f",
}

CANCERS_I08 = ("BLCA", "BRCA", "LUAD", "LGG", "UCEC")
CANCERS_PRIME = ("UCEC", "LUAD", "LGG", "BRCA", "BLCA")
FOLDS = (0, 1, 2, 3, 4)
ONE_MOD = ("rna", "wsi", "text")
TWO_MOD = ("rna+wsi", "rna+text", "wsi+text")
PATTERNS = ONE_MOD + TWO_MOD
AGG = {"1mod": ONE_MOD, "2mod": TWO_MOD, "miss6": PATTERNS}

OURS_KEY = "M6-a"
NO_GRID_KEYS = frozenset({"M0-a", "M0-b", "M9-base"})
RULE_TABLES = frozenset({"table1.tex", "table2.tex", "table3.tex", "table4.tex",
                         "table_s1.tex", "table_s2.tex", "table_s3.tex"})
FORBIDDEN_TOKENS = ("0.66" + "26", "f4b3" + "0740", "Dr" + "Fuse", "Red" + "Core", "M3" + "Care",
                    "Med" + "Fuse", "Sha" + "Spec", "summary.json", "per_fold_metrics.csv")

# Regression locks: 6-Missing Avg values stated in handoff §1-5. Asserted against the ledger, never printed.
HANDOFF_MISS6 = {
    "M6-a": "0.6657", "M0-a": "0.6519", "M0-b": "0.6519", "M7@default": "0.6406", "M10-a@default": "0.6559",
    "M10-b@default": "0.6567", "M10-c@default": "0.6561", "M2@default": "0.6565", "M8@default": "0.6579",
    "M9@default": "0.6586", "M1-a@default": "0.6423", "M1-b@default": "0.6394", "M3@default": "0.6526",
    "M4-a@default": "0.6567", "M4-b@default": "0.6473", "M5@default": "0.6589", "M6-b@default": "0.6583",
}


class LedgerError(RuntimeError):
    """The ledger on disk is not the pinned, val-only result set."""


class SingleColumnViolation(AssertionError):
    """A table row reads a key that the single-column hyperparameter rule forbids."""


class ProvenanceError(AssertionError):
    """An output number cannot be traced to a registered source cell."""


# ---------------------------------------------------------------------------------------------
# PRIME constants (verbatim from Prime.pdf; values strings copied from `pdftotext -layout`)
# ---------------------------------------------------------------------------------------------

def _pm(s: str) -> List[Tuple[float, float]]:
    return [tuple(float(x) for x in tok.split("±")) for tok in s.split()]


def _t2(name, pdf_name, mods, values, group):
    v = _pm(values)
    assert len(v) == 6, name
    return {"name": name, "pdf_name": pdf_name, "mods": mods, "cohorts": v[:5], "avg": v[5], "group": group}


PRIME_TABLE_II = [
    _t2("Img-only", "Img-only", (1, 0, 0), "0.668±0.083 0.599±0.056 0.670±0.100 0.615±0.087 0.547±0.060 0.620±0.052", "uni"),
    _t2("RNA-only", "RNA-only", (0, 1, 0), "0.598±0.094 0.510±0.057 0.764±0.056 0.498±0.065 0.526±0.043 0.579±0.110", "uni"),
    _t2("Text-only", "Text-only", (0, 0, 1), "0.676±0.066 0.553±0.028 0.703±0.097 0.556±0.030 0.532±0.025 0.604±0.079", "uni"),
    _t2("ABMIL", "ABMIL", (1, 0, 0), "0.637±0.049 0.604±0.066 0.692±0.056 0.617±0.092 0.537±0.035 0.617±0.056", "uni"),
    _t2("SNN", "SNN", (0, 1, 0), "0.571±0.070 0.520±0.065 0.719±0.073 0.466±0.103 0.536±0.053 0.563±0.096", "uni"),
    _t2("Early", "Early", (1, 1, 1), "0.692±0.045 0.557±0.075 0.736±0.060 0.593±0.050 0.557±0.033 0.627±0.082", "multi"),
    _t2("Late", "Late", (1, 1, 1), "0.686±0.068 0.575±0.088 0.709±0.048 0.594±0.024 0.528±0.022 0.618±0.076", "multi"),
    _t2("CrossAttn", "CrossAttn", (1, 1, 1), "0.677±0.058 0.559±0.097 0.688±0.088 0.572±0.047 0.556±0.037 0.610±0.066", "multi"),
    _t2("TensorFusion", "TensorFusion", (1, 1, 1), "0.686±0.078 0.521±0.048 0.734±0.056 0.604±0.057 0.552±0.049 0.620±0.089", "multi"),
    _t2("MAGGate", "MAGGate", (1, 1, 1), "0.698±0.049 0.553±0.079 0.713±0.053 0.616±0.035 0.538±0.034 0.624±0.080", "multi"),
    _t2("MulT", "MulT", (1, 1, 1), "0.677±0.031 0.562±0.079 0.718±0.086 0.576±0.056 0.564±0.030 0.619±0.073", "multi"),
    _t2("MCAT", "MCAT", (1, 1, 0), "0.649±0.041 0.589±0.042 0.727±0.055 0.501±0.077 0.533±0.026 0.600±0.091", "multi"),
    _t2("Porpoise", "Porpoise", (1, 1, 0), "0.663±0.088 0.631±0.067 0.633±0.059 0.603±0.068 0.559±0.025 0.618±0.039", "multi"),
    _t2("PathOmics", "PathOmics", (1, 1, 0), "0.609±0.131 0.609±0.042 0.644±0.070 0.572±0.069 0.563±0.023 0.599±0.033", "multi"),
    _t2("Song", "Song", (1, 1, 1), "0.699±0.061 0.514±0.054 0.684±0.062 0.621±0.056 0.557±0.068 0.615±0.080", "multi"),
    _t2("PRIME Scratch (FT)", "Scratch (FT)", (1, 1, 1), "0.684±0.039 0.574±0.056 0.716±0.064 0.573±0.028 0.565±0.038 0.623±0.072", "multi"),
    _t2("PRIME Scratch (LP)", "Scratch (LP)", (1, 1, 1), "0.684±0.071 0.599±0.056 0.611±0.085 0.560±0.041 0.523±0.033 0.595±0.060", "multi"),
    _t2("PRIME Pretrained (FT)", "Pretrained (FT)", (1, 1, 1), "0.692±0.048 0.590±0.051 0.730±0.079 0.643±0.034 0.549±0.055 0.641±0.073", "multi"),
    _t2("PRIME Pretrained (LP)", "Pretrained (LP)", (1, 1, 1), "0.699±0.055 0.578±0.051 0.780±0.050 0.622±0.066 0.584±0.041 0.653±0.086", "multi"),
]
PRIME_TABLE_II_NAMES = tuple(r["name"] for r in PRIME_TABLE_II)

# Table IV, Task-1 (overall survival) rows; columns Full, LI, LR, LT, OI, OR, OT.
PRIME_TABLE_IV = [
    {"name": n, "pdf_name": n, "cells": _pm(v)} for n, v in (
        ("Scratch (FT)", "0.623±0.072 0.608±0.069 0.631±0.068 0.607±0.051 0.607±0.050 0.540±0.085 0.606±0.066"),
        ("Pretrained (LP)", "0.653±0.086 0.612±0.086 0.641±0.086 0.619±0.090 0.603±0.058 0.564±0.084 0.611±0.077"),
        ("Pretrained (LP+Missing)", "0.653±0.089 0.623±0.085 0.639±0.085 0.636±0.087 0.611±0.055 0.571±0.063 0.610±0.089"),
    )
]

_PM_TOKEN = re.compile(r"\d\.\d{3}±\d\.\d{3}")

# Verbatim `pdftotext -layout` lines of Prime.pdf p. 6 (Table II) and p. 8 (Table IV), table blocks only.
# The extract is a separate, hash-pinned artifact; build() checks every constant against it unconditionally,
# and tests re-extract it from the PDF (pinned by sha256) whenever the PDF is available on the machine.
PRIME_EXTRACT_REL = Path("experiments/I08_ps3_shared_recovery/tools/prime_tables_extract.txt")
PRIME_EXTRACT_SHA256 = "1929dc62f6baaff56f05fd4bae9393be4bbecea8c4e87eb5f91e20b77dff0994"
PRIME_PDF_SHA256 = "91f7f376f3ab2643f747126bb280bdeb335a4cfa9ec70709c01d427436cea135"
PRIME_PDF_PAGES = (6, 8)
PRIME_OWN_ROWS = ("Scratch (FT)", "Scratch (LP)", "Pretrained (FT)", "Pretrained (LP)")  # labelled "PRIME ..." in our tables


def verify_prime_text(text: str) -> None:
    """Constants must equal the PDF rows in order: all 19 Table II rows, then the first 3 (Task-1) Table IV rows."""
    if "TABLE II" not in text or "TABLE IV" not in text:
        raise ProvenanceError("PRIME text lacks the TABLE II / TABLE IV headers")
    block2, block4 = text.split("TABLE II", 1)[1].split("TABLE IV", 1)
    rows2 = [ln for ln in block2.splitlines() if _PM_TOKEN.search(ln)]
    rows4 = [ln for ln in block4.splitlines() if _PM_TOKEN.search(ln)][: len(PRIME_TABLE_IV)]
    problems = []
    for rows, consts, getter in ((rows2, PRIME_TABLE_II, lambda r: list(r["cohorts"]) + [r["avg"]]),
                                 (rows4, PRIME_TABLE_IV, lambda r: r["cells"])):
        if len(rows) != len(consts):
            problems.append(f"{len(rows)} PDF rows vs {len(consts)} constants")
            continue
        for ln, r in zip(rows, consts):
            want = [f"{m:.3f}±{s:.3f}" for m, s in getter(r)]
            if _PM_TOKEN.findall(ln) != want:
                problems.append(f"{r['pdf_name']}: values")
    # Row metadata used by the outputs (method name, modality marks, group) must also come from the PDF rows.
    head = next((ln for ln in block2.splitlines() if ln.split() == ["Img", "RNA", "Text"]), None)
    if head is None:
        problems.append("Table II modality header (Img / RNA / Text) not found")
    elif len(rows2) == len(PRIME_TABLE_II):
        cols = [head.index(t) for t in ("Img", "RNA", "Text")]
        for ln, r in zip(rows2, PRIME_TABLE_II):
            first = min(i for i in (ln.find("✓"), _PM_TOKEN.search(ln).start()) if i >= 0)
            method = re.sub(r"\s*\[\d+\]$", "", ln[:first].strip())
            marks = [0, 0, 0]
            for i, ch in enumerate(ln[:_PM_TOKEN.search(ln).start()]):
                if ch == "✓":
                    marks[min(range(3), key=lambda j: abs(cols[j] - i))] += 1
            mods = tuple(marks)
            name = f"PRIME {method}" if method in PRIME_OWN_ROWS else method
            group = "uni" if sum(mods) == 1 else "multi"
            for field_, got, exp in (("pdf_name", r["pdf_name"], method), ("name", r["name"], name),
                                     ("mods", tuple(r["mods"]), mods), ("group", r["group"], group)):
                if got != exp:
                    problems.append(f"Table II {method}: {field_} {got!r} != PDF {exp!r}")
    if len(rows4) == len(PRIME_TABLE_IV):
        if not any(ln.split()[0] == "Task-1" for ln in rows4 if ln.split()):
            problems.append("Table IV: the first three rows are not the Task-1 block")
        for ln, r in zip(rows4, PRIME_TABLE_IV):
            method = re.sub(r"^\s*Task-1\s+", "", ln[:_PM_TOKEN.search(ln).start()]).strip()
            if r["pdf_name"] != method or r["name"] != method:
                problems.append(f"Table IV {method}: name {r['name']!r} / pdf_name {r['pdf_name']!r}")
    if problems:
        raise ProvenanceError(f"PRIME constants differ from the PDF rows: {problems}")


def load_prime_extract(repo_root: Path) -> str:
    raw = (repo_root / PRIME_EXTRACT_REL).read_bytes()
    if _sha256(raw) != PRIME_EXTRACT_SHA256:
        raise ProvenanceError("PRIME extract differs from the pinned pdftotext output")
    text = raw.decode("utf-8")
    verify_prime_text(text)
    return text


def verify_extract_against_pdf(pdf: Path, repo_root: Path = REPO_ROOT) -> None:
    """Re-run pdftotext on the pinned PDF and require every non-empty extract line verbatim in its output."""
    import subprocess
    if _sha256(Path(pdf).read_bytes()) != PRIME_PDF_SHA256:
        raise ProvenanceError("Prime.pdf differs from the pinned PDF")
    out = []
    for page in PRIME_PDF_PAGES:
        out += subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
                              check=True, capture_output=True, text=True).stdout.splitlines()
    pdf_lines = {ln.rstrip() for ln in out}
    missing = [ln for ln in load_prime_extract(repo_root).splitlines() if ln.strip() and ln.rstrip() not in pdf_lines]
    if missing:
        raise ProvenanceError(f"{len(missing)} extract lines are not in the PDF text, e.g. {missing[0].strip()[:60]!r}")


# ---------------------------------------------------------------------------------------------
# Ledger loading (hash binding and val-only guard)
# ---------------------------------------------------------------------------------------------

def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _reject_test_content(obj, where: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "test" in str(k).lower():
                raise LedgerError(f"test-split content key {k!r} found in {where} (test_access: false)")
            if isinstance(v, (dict, list)):
                _reject_test_content(v, where)
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                _reject_test_content(v, where)


def load_ledger(i08_dir: Path, expected_run_meta_sha256: str = LEDGER_PIN["run_meta_sha256"]) -> Dict[Tuple[str, int], dict]:
    """Return {(cancer, fold): fold JSON} after binding every file to the pinned run_meta.json."""
    i08_dir = Path(i08_dir)
    raw = (i08_dir / "run_meta.json").read_bytes()
    if _sha256(raw) != expected_run_meta_sha256:
        raise LedgerError("run_meta.json sha256 differs from the pinned ledger")
    meta = json.loads(raw)
    expect = {
        "source commit": (meta.get("source", {}).get("commit"), LEDGER_PIN["source_commit"]),
        "source dirty": (meta.get("source", {}).get("dirty"), False),
        "verified": (meta.get("verified"), True),
        "config sha256": (meta.get("config_sha256"), LEDGER_PIN["config_sha256"]),
        "cache manifest sha256": (meta.get("cache_manifest_sha256"), LEDGER_PIN["cache_manifest_sha256"]),
        "cancers": (sorted(meta.get("cancers", [])), sorted(CANCERS_I08)),
        "folds": (meta.get("folds"), list(FOLDS)),
    }
    for what, (got, want) in expect.items():
        if got != want:
            raise LedgerError(f"run_meta {what}: {got!r} != {want!r}")
    runs: Dict[Tuple[str, int], dict] = {}
    for c in CANCERS_I08:
        for f in FOLDS:
            name = f"{c}_fold{f}.json"
            b = (i08_dir / "val_runs" / name).read_bytes()
            if meta["files"].get(name) != _sha256(b):
                raise LedgerError(f"{name} sha256 does not match run_meta.json")
            d = json.loads(b)
            if d.get("cancer") != c or d.get("fold") != f:
                raise LedgerError(f"{name} identity fields mismatch")
            _reject_test_content(d, name)
            runs[(c, f)] = d
    report = (i08_dir / "val_ablation_report_v1.md").read_text(encoding="utf-8")
    for token in (LEDGER_PIN["source_commit"], LEDGER_PIN["config_sha256"], LEDGER_PIN["cache_manifest_sha256"]):
        if token not in report:
            raise LedgerError(f"report header does not carry {token[:12]}")
    return runs


# ---------------------------------------------------------------------------------------------
# I08 statistics
# ---------------------------------------------------------------------------------------------

class I08Stats:
    def __init__(self, runs: Dict[Tuple[str, int], dict]):
        self.runs = runs
        self._check_invariants()

    def _ci(self, key: str, c: str, f: int) -> dict:
        return self.runs[(c, f)]["methods"][key]["val"]["cindex"]

    def _check_invariants(self) -> None:
        for (c, f), d in self.runs.items():
            m = d["methods"]
            for p in ("full",) + PATTERNS:
                if m["M0-a"]["val"]["cindex"][p] != m["M0-b"]["val"]["cindex"][p]:
                    raise AssertionError(f"M0-a and M0-b differ at {c}/{f}/{p}; the M0-a/b label is invalid")
            for k, v in m.items():
                if v["val"]["cindex"]["full"] != m["M0-a"]["val"]["cindex"]["full"]:
                    raise AssertionError(f"Full C-index of {k} differs from the D0 bypass at {c}/{f}")
            if m[OURS_KEY]["base"]["r"] != 32:
                raise AssertionError(f"M6-a did not lock r=32 at {c}/{f}")
            for k in m:
                if k.endswith("@default") and k[: -len("@default")] not in m:
                    raise AssertionError(f"{k} has no tuned sibling")
            for k in NO_GRID_KEYS:
                if f"{k}@default" in m:
                    raise AssertionError(f"{k} is treated as grid-free but {k}@default exists")

    def fold(self, key: str, c: str, f: int, what: str) -> float:
        ci = self._ci(key, c, f)
        return float(np.mean([ci[p] for p in AGG.get(what, (what,))]))

    def cancer_mean(self, key: str, c: str, what: str) -> float:
        return float(np.mean([self.fold(key, c, f, what) for f in FOLDS]))

    def cancer_sd(self, key: str, c: str, what: str) -> float:
        return float(np.std([self.fold(key, c, f, what) for f in FOLDS], ddof=1))

    def macro_mean(self, key: str, what: str) -> float:
        return float(np.mean([self.cancer_mean(key, c, what) for c in CANCERS_I08]))

    def macro_sd(self, key: str, what: str) -> float:
        return float(np.std([self.cancer_mean(key, c, what) for c in CANCERS_I08], ddof=1))

    def paired(self, a: str, b: str) -> dict:
        d = np.array([self.fold(a, c, f, "miss6") - self.fold(b, c, f, "miss6") for c in CANCERS_I08 for f in FOLDS])
        if np.all(d == 0):
            p1 = p2 = 1.0
        else:
            p1 = float(stats.wilcoxon(d, alternative="greater").pvalue)
            p2 = float(stats.wilcoxon(d, alternative="two-sided").pvalue)
        return {"mean": float(d.mean()), "wins": int((d > 0).sum()), "ties": int((d == 0).sum()), "n": int(d.size),
                "p_one": p1, "p_two": p2}

    def hparam(self, key: str, path: Sequence[str]):
        vals = set()
        for d in self.runs.values():
            v = d["methods"][key]
            for p in path:
                v = v[p]
            vals.add(json.dumps(v))
        if len(vals) != 1:
            raise AssertionError(f"{key}.{'.'.join(path)} is not constant across folds: {vals}")
        return json.loads(vals.pop())

    def interp_config(self) -> dict:
        """Hyperparameters of the interpretability tables (per-fold best_epoch / orth_err are excluded)."""
        def hp(cfg):
            b = cfg["base"]
            return {"K": cfg["K"], "tau": cfg["tau"], "alpha_max": cfg["alpha_max"], "residual_mode": cfg["residual_mode"],
                    "base": {"r": b["r"], "lambda_modal": b["lambda_modal"], "lambda_cons": b["lambda_cons"]}}
        vals = {json.dumps(hp(d["interpretability"]["config"]), sort_keys=True) for d in self.runs.values()}
        if len(vals) != 1:
            raise AssertionError(f"interpretability hyperparameters differ across folds: {vals}")
        return json.loads(vals.pop())


# ---------------------------------------------------------------------------------------------
# I07 ledger (test rows of the frozen backbone, cross-checked with the tracked results.md)
# ---------------------------------------------------------------------------------------------

I07_ARMS = {"完整三模态": "tri", "独立纯 WSI": "wsi", "独立纯 RNA": "rna", "独立纯文本": "text"}

# I07 verification ledger (tracked in git): verify_report.json pins the commit, the output manifest hash and every
# per-run metric; output_manifest.json pins the sha256 of every test_metrics.json (Codex round-3 finding R3-1).
I07_PIN = {
    "verify_report_sha256": "e9dd2f2ca305ebb45fc1ccb66c9922da32faf4830826f0bbd34ccdbd7e8b57b7",
    "commit": "3d01b19f44b76f0500a57278b5944406b9ae93d9",
    "output_manifest_sha256": "d4a6ce1d2d43820bc771ded802830c84c2534f3c1f7113b0826b7c3267d70850",
}


def _load_i07_verified(i07_dir: Path) -> Tuple[dict, dict]:
    """Return (verify_report, manifest) after binding both to the pinned I07 verification ledger."""
    raw = (i07_dir / "verify" / "verify_report.json").read_bytes()
    if _sha256(raw) != I07_PIN["verify_report_sha256"]:
        raise LedgerError("I07 verify_report.json differs from the pinned verification ledger")
    report = json.loads(raw)
    if report.get("commit") != I07_PIN["commit"] or report.get("output_manifest_sha256") != I07_PIN["output_manifest_sha256"]:
        raise LedgerError("I07 verify_report commit / manifest hash differ from the pin")
    man_raw = (i07_dir / "verify" / "output_manifest.json").read_bytes()
    if _sha256(man_raw) != I07_PIN["output_manifest_sha256"]:
        raise LedgerError("I07 output_manifest.json differs from the hash recorded in verify_report.json")
    return report, json.loads(man_raw)


def load_i07(i07_dir: Path) -> Dict[str, dict]:
    report, manifest = _load_i07_verified(i07_dir)
    md = (i07_dir / "render" / "results.md").read_text(encoding="utf-8")
    sec = md.split("## 结果（屏蔽列为零填充）", 1)[1].split("\n## ", 1)[0]
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in sec.splitlines() if ln.strip().startswith("|")]
    header = rows[0]
    col = {arm: header.index(name) for name, arm in I07_ARMS.items()}
    body = {r[0]: r for r in rows[2:]}
    out: Dict[str, dict] = {}
    for arm, j in col.items():
        cohorts = {}
        for c in CANCERS_PRIME:
            v = []
            for f in FOLDS:
                rel = f"{c}/fold{f}/{arm}/test_metrics.json"
                b = (i07_dir / "runs" / rel).read_bytes()  # read once: hash-check and parse the same bytes (V43)
                if manifest.get(rel) != _sha256(b):
                    raise LedgerError(f"I07 {rel} sha256 does not match output_manifest.json")
                x = json.loads(b)["c_index"]["full"]
                if x != report["metrics"][f"{c}/fold{f}/{arm}"]["full"]:
                    raise LedgerError(f"I07 {rel}: C-index differs from verify_report.json")
                v.append(x)
            m, s = float(np.mean(v)), float(np.std(v))  # population SD, the convention of results.md
            if body[c][j] != f"{m:.3f} ± {s:.3f}":
                raise LedgerError(f"I07 {c}/{arm}: test_metrics.json gives {m:.3f} ± {s:.3f}, results.md {body[c][j]!r}")
            cohorts[c] = (m, s)
        means = [cohorts[c][0] for c in CANCERS_PRIME]
        avg = (float(np.mean(means)), float(np.std(means, ddof=1)))
        if abs(avg[0] - report["macro"]["full"][arm]) > 1e-12:
            raise LedgerError(f"I07 macro {arm}: {avg[0]!r} differs from verify_report.json")
        if body["五癌宏平均"][j] != f"{avg[0]:.3f}":
            raise LedgerError(f"I07 macro {arm}: {avg[0]:.3f} vs results.md {body['五癌宏平均'][j]!r}")
        out[arm] = {"cohorts": cohorts, "avg": avg}
    return out


# ---------------------------------------------------------------------------------------------
# Provenance registry and rules
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CellRecord:
    table: str
    role: str      # ours | comparator | reference
    kind: str      # i08_val | i08_stat | i08_interp | i07_test | prime | prime_derived | config
    key: str
    metric: str
    text: str      # always render_value(fmt, value, bold); audit_records() rejects anything else
    fmt: str = ""
    value: tuple = ()
    bold: bool = False


# ---- Typed values and fixed formatters ------------------------------------------------------
# A record never carries free text: it stores the typed value and the name of a fixed formatter, and
# its text must equal the formatter's output. Each kind may only use the formatters listed for it.
ALLOWED_FMTS = {
    "i08_val": {"f3", "f4", "pm3.3", "pm4.3", "pm4.4"},
    "i08_stat": {"+f4", "frac", "int", "p"},
    "i08_interp": {"f1", "f4", "f5", "+f4", "+f5", "int", "p"},
    "i07_test": {"pm3.3"},
    "prime": {"pm3.3"},
    "prime_derived": {"f3"},
    "config": {"int", "g"},
}


def _real(x) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) or not np.isfinite(x):
        raise ProvenanceError(f"non-numeric or non-finite value {x!r}")
    return float(x)


def _int(x) -> int:
    if isinstance(x, bool) or not isinstance(x, (int, np.integer)):
        raise ProvenanceError(f"expected an integer, got {x!r}")
    return int(x)


def render_value(fmt: str, value: tuple, bold: bool = False) -> str:
    v = tuple(value)
    m_f = re.fullmatch(r"(\+?)f(\d)", fmt)
    m_pm = re.fullmatch(r"pm(\d)\.(\d)", fmt)
    arity = 2 if (m_pm or fmt == "frac") else 1
    if len(v) != arity:
        raise ProvenanceError(f"format {fmt!r} takes {arity} value(s), got {v!r}")
    if m_f:
        text = f"{_real(v[0]):{m_f.group(1)}.{m_f.group(2)}f}"
    elif m_pm:
        text = f"{_real(v[0]):.{m_pm.group(1)}f}$\\pm${_real(v[1]):.{m_pm.group(2)}f}"
    elif fmt == "frac":
        text = f"{_int(v[0])}/{_int(v[1])}"
    elif fmt == "int":
        text = f"{_int(v[0])}"
    elif fmt == "p":
        text = fmt_p(_real(v[0]))
    elif fmt == "g":
        text = f"{_real(v[0]):g}"
    else:
        raise ProvenanceError(f"unknown format {fmt!r}")
    return f"\\textbf{{{text}}}" if bold else text


def audit_records(records: Sequence[CellRecord]) -> None:
    """Each record's text must be exactly its fixed formatter applied to its typed value."""
    bad = []
    for i, r in enumerate(records):
        try:
            if r.fmt not in ALLOWED_FMTS.get(r.kind, ()):
                raise ProvenanceError(f"format {r.fmt!r} not allowed for kind {r.kind!r}")
            if r.text != render_value(r.fmt, r.value, r.bold):
                raise ProvenanceError(f"text {r.text!r} is not the formatted value {r.value!r}")
        except ProvenanceError as e:
            bad.append(f"#{i} {r.table}/{r.key}/{r.metric}: {e}")
    if bad:
        raise ProvenanceError("records with free or mismatched text: " + "; ".join(bad[:5]))


def _comparator_ok(key: str) -> bool:
    return key != OURS_KEY and (key in NO_GRID_KEYS or key.endswith("@default"))


def check_single_column(records: Sequence[CellRecord]) -> None:
    errors = []
    keys_by_table: Dict[str, set] = {}
    for r in records:
        if r.table not in RULE_TABLES or r.kind not in ("i08_val", "i08_stat"):
            continue
        if r.kind == "i08_stat":
            keys = r.key.split("|")
            if r.role == "ours" and keys[0] != OURS_KEY:
                errors.append(f"{r.table}: Ours statistic must be anchored on {OURS_KEY}, got {keys[0]!r}")
            for i, k in enumerate(keys):
                if not (_comparator_ok(k) or (k == OURS_KEY and i == 0 and r.role == "ours")):
                    errors.append(f"{r.table}: statistic {r.key!r} reads {k!r}; only {OURS_KEY} (as Ours) or "
                                  "@default / grid-free keys allowed")
        else:
            keys = [r.key]
            if r.role == "ours" and r.key != OURS_KEY:
                errors.append(f"{r.table}: Ours row reads {r.key!r}, must read {OURS_KEY!r}")
            if r.role != "ours" and not _comparator_ok(r.key):
                errors.append(f"{r.table}: {r.role} row reads {r.key!r}; only @default or grid-free keys allowed")
        keys_by_table.setdefault(r.table, set()).update(keys)
    for t, keys in keys_by_table.items():
        for k in keys:
            if k.endswith("@default") and k[: -len("@default")] in keys:
                errors.append(f"{t}: dual columns {k[:-8]!r} and {k!r}")
    if errors:
        raise SingleColumnViolation("; ".join(sorted(set(errors))))


# ---- Template audit ------------------------------------------------------------------------
# Builders never write a registered number into the text: Reg returns a sentinel that is replaced by the
# record text only when the output is resolved. The audit runs on the unresolved template and requires
# (a) every sentinel of the output exactly once and (b) no digit at all outside sentinels, except method /
# operator identifiers, LaTeX layout arguments and the exact structural phrases listed below. Integers,
# exponents and copies of an existing number therefore cannot enter an output without a registered source.

_SENT = re.compile("\x01(\\d+)\x02")
_IDENT = re.compile(r"(?<![A-Za-z0-9])(?:M\d+(?:-(?:a|b|c|base))?|[ABC]\d|I0[78]|PS3)(?![0-9])")
_LAYOUT = re.compile(r"\\(?:label|ref)\{[^{}]*\}|\\multicolumn\{\d+\}|\\cmidrule\(lr\)\{\d+-\d+\}|p\{\d+mm\}|"
                     r"\\setlength\{\\tabcolsep\}\{\d+pt\}|\\textcircled\{[123]\}")
STRUCTURAL_PHRASES = (
    "256-$d$", "32-$d$", "224-$d$", "PCA-32", "Orthogonal-32",  # d = 256 and r = 32 (asserted on the ledger)
    "Group 1", "Group 2", "Group 3", "Table 1", "Table 2", "Eq. (8)", "Task-1", "5-fold",
    "1-Mod", "2-Mod", "6-Missing", "Top-1", "s_{(1)}", "R^2", "_2^2", "$D_0$", "sha256",
    GENERATOR_REL, I08_RES_REL.name, LEDGER_PIN["source_commit"][:8], LEDGER_PIN["run_meta_sha256"][:12],
)
_FILE_NAME = re.compile(r"table(?:_s)?\d\.tex")


def sentinel(i: int) -> str:
    return f"\x01{i}\x02"


def audit_template(name: str, template: str, records: Sequence[CellRecord]) -> None:
    ids = [int(x) for x in _SENT.findall(template)]
    expected = set(range(len(records))) if name.endswith(".md") else {i for i, r in enumerate(records) if r.table == name}
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup or set(ids) != expected:
        raise ProvenanceError(f"{name}: sentinels duplicated {dup[:5]}, missing {sorted(expected - set(ids))[:5]}, "
                              f"foreign {sorted(set(ids) - expected)[:5]}")
    rest = _LAYOUT.sub("", _SENT.sub("", template)).replace("~", " ")
    for phrase in STRUCTURAL_PHRASES:
        rest = rest.replace(phrase, "")
    rest = _IDENT.sub("", _FILE_NAME.sub("", rest))
    stray = [m.start() for m in re.finditer(r"\d", rest)]
    if stray:
        ctx = sorted({rest[max(0, i - 25): i + 15].replace("\n", " ") for i in stray[:5]})
        raise ProvenanceError(f"{name}: unregistered digits in template: {ctx}")


def resolve(template: str, records: Sequence[CellRecord], md: bool = False) -> str:
    return _SENT.sub(lambda m: tex2md(records[int(m.group(1))].text) if md else records[int(m.group(1))].text, template)


class Reg:
    """Formats a number from its source and records it; builders only ever see the returned sentinel."""

    def __init__(self, table: str, s: I08Stats, records: List[CellRecord]):
        self.table, self.s, self.records = table, s, records

    def add(self, role, kind, key, metric, fmt, value, bold=False) -> str:
        value = tuple(value)
        self.records.append(CellRecord(self.table, role, kind, key, metric, render_value(fmt, value, bold),
                                       fmt, value, bold))
        return sentinel(len(self.records) - 1)

    def val(self, key, role, what, cancer=None, dec=4, sd_dec=None, bold=False) -> str:
        m = self.s.cancer_mean(key, cancer, what) if cancer else self.s.macro_mean(key, what)
        if sd_dec is None:
            fmt, value = f"f{dec}", (m,)
        else:
            sd = self.s.cancer_sd(key, cancer, what) if cancer else self.s.macro_sd(key, what)
            fmt, value = f"pm{dec}.{sd_dec}", (m, sd)
        return self.add(role, "i08_val", key, f"{what}@{cancer or 'macro'}", fmt, value, bold)

    def diff(self, key, ref, what, cancer=None) -> str:
        if cancer:
            d = self.s.cancer_mean(key, cancer, what) - self.s.cancer_mean(ref, cancer, what)
        else:
            d = self.s.macro_mean(key, what) - self.s.macro_mean(ref, what)
        return self.add("ours" if key == OURS_KEY else "comparator", "i08_stat", f"{key}|{ref}",
                        f"diff:{what}@{cancer or 'macro'}", "+f4", (d,))

    def paired(self, key, ref, fields=("mean", "wins", "ties", "p_one", "p_two")) -> dict:
        """Registers only the requested statistics: every registered cell must appear in the output exactly once."""
        pr = self.s.paired(key, ref)
        k, role = f"{key}|{ref}", ("ours" if key == OURS_KEY else "comparator")
        spec = {"mean": ("+f4", (pr["mean"],)), "wins": ("frac", (pr["wins"], pr["n"])), "ties": ("int", (pr["ties"],)),
                "p_one": ("p", (pr["p_one"],)), "p_two": ("p", (pr["p_two"],))}
        out = {f: self.add(role, "i08_stat", k, f, *spec[f]) for f in fields}
        out["raw"] = pr
        return out


def recheck_i08_values(records: Sequence[CellRecord], s: "I08Stats") -> None:
    """i08_val values are recomputed from the ledger by key and metric, so a record cannot carry a foreign value."""
    for r in records:
        if r.kind != "i08_val":
            continue
        what, scope = r.metric.split("@")
        cancer = None if scope == "macro" else scope
        want = [s.cancer_mean(r.key, cancer, what) if cancer else s.macro_mean(r.key, what)]
        if len(r.value) == 2:
            want.append(s.cancer_sd(r.key, cancer, what) if cancer else s.macro_sd(r.key, what))
        if list(r.value) != want:
            raise ProvenanceError(f"{r.table}: value of {r.key}/{r.metric} differs from the ledger")


def fmt_p(p: float) -> str:
    if p == 0.0:
        return "<10^{-300}"  # float64 underflow: the exact p is below the smallest representable double
    mant, exp = f"{p:.2e}".split("e")
    return f"={mant}\\times10^{{{int(exp)}}}"


# ---------------------------------------------------------------------------------------------
# Table document model (renders LaTeX booktabs and a Markdown preview from the same cells)
# ---------------------------------------------------------------------------------------------

HEADER_COMMENT = f"% Auto-generated by {GENERATOR_REL}. Do not edit by hand."
LABEL_NUMBERS = {"tab:overall_comparison": "1", "tab:missing_robustness": "2", "tab:progressive_ablation": "3",
                 "tab:operator_comparison": "4"}


def tex2md(s: str) -> str:
    for a, b in (("$\\pm$", "±"), ("$^\\dagger$", "†"), ("$\\checkmark$", "✓"), ("$\\times$", "×"),
                 ("$\\circ$", "○"), ("\\&", "&"), ("\\%", "%"), ("~", " "), ("--", "–"), ("\\,", " "), ("\\ ", " ")):
        s = s.replace(a, b)
    s = re.sub(r"\\texttt\{([^{}]*)\}", r"`\1`", s)
    s = re.sub(r"\\textit\{([^{}]*)\}", r"*\1*", s)
    s = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", s)
    s = re.sub(r"\\ref\{([^{}]*)\}", lambda m: LABEL_NUMBERS.get(m.group(1), m.group(1)), s)
    s = s.replace("\\textcircled{1}", "①").replace("\\textcircled{2}", "②").replace("\\textcircled{3}", "③")
    if "|" in s:
        raise AssertionError(f"pipe character in Markdown cell (E52): {s!r}")
    return s


@dataclass
class Doc:
    name: str
    caption: str
    label: str
    colspec: str
    header: List[str]
    items: list = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    rotate: bool = False  # landscape float (rotating sidewaystable) for long-label tables

    def row(self, cells: Sequence[str]) -> None:
        assert len(cells) == len(self.header), (self.label, len(cells), len(self.header))
        self.items.append(("row", list(cells)))

    def rule(self, r: str = "\\midrule") -> None:
        self.items.append(("rule", r))

    def group(self, text: str) -> None:
        self.items.append(("group", text))

    def tabular(self) -> List[str]:
        # Landscape floats are wide enough unscaled; sn-jnl wraps sidewaystable in threeparttable, which breaks
        # under \resizebox (see the main.tex Post-Mortem), so only portrait tables are scaled to the line width.
        n = len(self.header)
        head = ["{\\footnotesize\\setlength{\\tabcolsep}{4pt}"] if self.rotate else ["\\resizebox{\\linewidth}{!}{%"]
        out = head + [f"\\begin{{tabular}}{{{self.colspec}}}", "\\toprule",
               " & ".join(self.header) + " \\\\", "\\midrule"]
        for kind, x in self.items:
            if kind == "row":
                out.append(" & ".join(x) + " \\\\")
            elif kind == "rule":
                out.append(x)
            else:
                out.append(f"\\multicolumn{{{n}}}{{l}}{{\\textit{{{x}}}}} \\\\")
        return out + ["\\bottomrule", "\\end{tabular}" + ("}" if self.rotate else "%"), *([] if self.rotate else ["}"])]

    def tex(self) -> str:
        return render_float([self], self.caption, self.label, rotate=self.rotate)

    def md(self, title: Optional[str] = None) -> List[str]:
        n = len(self.header)
        lines = [f"### {title or tex2md(self.caption)}", "", "| " + " | ".join(tex2md(h) for h in self.header) + " |",
                 "| :--- |" + " :---: |" * (n - 1)]
        for kind, x in self.items:
            if kind == "row":
                lines.append("| " + " | ".join(tex2md(c) for c in x) + " |")
            elif kind == "group":
                lines.append(f"| **{tex2md(x)}** |" + " |" * (n - 1))
        if self.notes:
            lines += ["", "> Notes: " + tex2md(" ".join(self.notes))]
        return lines


def render_float(panels: Sequence[Doc], caption: str, label: str, rotate: bool = False) -> str:
    """One numbered float; several panels share it so that the table counter advances exactly once."""
    env, place = ("sidewaystable", "[p]") if rotate else ("table*", "[!t]")
    out = [f"\\begin{{{env}}}{place}", "\\centering", f"\\caption{{{caption}}}", f"\\label{{{label}}}"]
    for i, p in enumerate(panels):
        if len(panels) > 1:
            out += (["\\par\\medskip"] if i else []) + [f"\\par\\textit{{{p.caption}}}\\par\\smallskip"]
        out += p.tabular()
    notes = [n for p in panels for n in p.notes]
    if notes:
        out += ["\\par\\smallskip", "\\begin{minipage}{\\linewidth}\\footnotesize",
                "\\textit{Notes:} " + " ".join(dict.fromkeys(notes)), "\\end{minipage}"]
    out.append(f"\\end{{{env}}}")
    return "\n".join(out)


def _mark(flag: int) -> str:
    return "$\\checkmark$" if flag else "$\\times$"


def _bold_flags(values: Dict[str, float], dec: int) -> Dict[str, bool]:
    best = max(round(v, dec) for v in values.values())
    return {k: round(v, dec) == best for k, v in values.items()}


# ---------------------------------------------------------------------------------------------
# Row specs (key, label, role). Roles are explicit so that a mutated key cannot change its role.
# ---------------------------------------------------------------------------------------------

TABLE1_GROUP3 = [
    ("M0-a", "PS3-style Backbone + Zero / Mean-Fill (\\texttt{M0-a/b})", "comparator"),
    ("M1-a@default", "Full-Space 256-$d$ Ridge Imputation (\\texttt{B0}, \\texttt{M1-a@default})", "comparator"),
    ("M7@default", "\\texttt{w/o A1}: Full-Space 256-$d$ \\texttt{B6-LOO} (\\texttt{M7@default})", "comparator"),
    ("M6-a", "\\textbf{TriModalSurv (Ours, \\texttt{M6-a})}", "ours"),
]
TABLE2_ROWS = [
    ("M0-a", "Zero / Train-Mean Placeholder (\\texttt{M0-a/b})", "comparator"),
    ("M1-a@default", "Full-Space 256-$d$ Ridge (\\texttt{B0}, \\texttt{M1-a@default})", "comparator"),
    ("M1-b@default", "Risk-Residual 256-$d$ Ridge (\\texttt{C0}, \\texttt{M1-b@default})", "comparator"),
    ("M7@default", "\\texttt{w/o A1}: Full-Space 256-$d$ \\texttt{B6-LOO} (\\texttt{M7@default})", "comparator"),
    ("M6-a", "\\textbf{TriModalSurv (Ours: \\texttt{A1 + B6-LOO + C1}, \\texttt{M6-a})}", "ours"),
]
TABLE3_ROWS = [
    ("M0-a", "Backbone + Zero / Train-Mean (\\texttt{M0-a/b})", "comparator"),
    ("M7@default", "\\texttt{w/o A1}: 256-$d$ Full-Space \\texttt{B6-LOO} (\\texttt{M7@default})", "comparator"),
    ("M10-a@default", "\\texttt{A1 + B1} (w/o \\texttt{C1}, w/o \\texttt{B6}; \\texttt{M10-a@default})", "comparator"),
    ("M2@default", "\\texttt{A1 + B1 + C1} (w/o \\texttt{B6}; \\texttt{M2@default})", "comparator"),
    ("M8@default", "\\texttt{A1 + B6-LOO} (w/o \\texttt{C1}; \\texttt{M8@default})", "comparator"),
    ("M6-a", "\\textbf{\\texttt{A1 + B6-LOO + C1} (Ours, \\texttt{M6-a})}", "ours"),
]
TABLE3_PAIRED = ("M0-a", "M7@default", "M2@default")
TABLE4_BLOCK_A = [
    ("M7@default", "\\texttt{w/o A}: 256-$d$ Full Space (\\texttt{M7@default})", "comparator"),
    ("M9@default", "\\texttt{A5}: Frozen Unsupervised PCA-32 (\\texttt{M9@default})", "comparator"),
    ("M6-a", "\\textbf{\\texttt{A1}: Trainable Cayley Orthogonal-32 (Ours, \\texttt{M6-a})}", "ours"),
]
TABLE4_BLOCK_B = [
    ("M0-b", "\\texttt{w/o B}: Train-Mean Placeholder (\\texttt{M0-b})", "comparator"),
    ("M1-a@default", "\\texttt{B0}: 256-$d$ Closed-Form Ridge (\\texttt{M1-a@default})", "comparator"),
    ("M1-b@default", "\\texttt{C0}: 256-$d$ Risk-Residual Ridge (\\texttt{M1-b@default})", "comparator"),
    ("M4-b@default", "\\texttt{B5-DirectCoord}: Precision Shrinkage on Raw $z$ (\\texttt{M4-b@default})", "comparator"),
    ("M3@default", "\\texttt{B3}: Direct Top-$K$ Neighbor Feature Aggregation (\\texttt{M3@default})", "comparator"),
    ("M2@default", "\\texttt{B1}: Global Pattern-Specific Linear Map (\\texttt{M2@default})", "comparator"),
    ("M4-a@default", "\\texttt{B5-MapPrecision}: Precision Shrinkage on Mapped $z$ (\\texttt{M4-a@default})", "comparator"),
    ("M5@default", "\\texttt{B6-Naive}: Raw Residual Retrieval w/o LOO Leverage \\& IQR Gate (\\texttt{M5@default})", "comparator"),
    ("M6-a", "\\textbf{\\texttt{B6-LOO}: Hat-Debiased Residual Retrieval + IQR Gate (Ours, \\texttt{M6-a})}", "ours"),
]
SINGLE_COLUMN_METHODS = [
    ("M0-a", "\\texttt{M0-a/b}: Zero / Train-Mean Placeholder", "comparator"),
    ("M1-a@default", "\\texttt{M1-a@default}: \\texttt{B0} (256-$d$ Closed-Form Ridge)", "comparator"),
    ("M1-b@default", "\\texttt{M1-b@default}: \\texttt{C0} (256-$d$ Risk-Residual Ridge)", "comparator"),
    ("M7@default", "\\texttt{M7@default}: 256-$d$ \\texttt{B6-LOO} (w/o \\texttt{A1})", "comparator"),
    ("M10-a@default", "\\texttt{M10-a@default}: \\texttt{A1 + B1} (w/o \\texttt{C1})", "comparator"),
    ("M10-c@default", "\\texttt{M10-c@default}: \\texttt{A1 + B1} + $\\mathcal{L}_{\\mathrm{modal}}$", "comparator"),
    ("M10-b@default", "\\texttt{M10-b@default}: \\texttt{A1 + B1} + $\\mathcal{L}_{\\mathrm{cons}}$", "comparator"),
    ("M2@default", "\\texttt{M2@default}: \\texttt{A1 + B1 + C1}", "comparator"),
    ("M3@default", "\\texttt{M3@default}: \\texttt{A1 + B3 + C1}", "comparator"),
    ("M4-b@default", "\\texttt{M4-b@default}: \\texttt{A1 + B5-DirectCoord + C1}", "comparator"),
    ("M4-a@default", "\\texttt{M4-a@default}: \\texttt{A1 + B5-MapPrecision + C1}", "comparator"),
    ("M9-base", "\\texttt{M9-base}: \\texttt{A5} (Frozen PCA-32) + \\texttt{B1}", "comparator"),
    ("M9@default", "\\texttt{M9@default}: \\texttt{A5} (Frozen PCA-32) + \\texttt{B6-LOO}", "comparator"),
    ("M8@default", "\\texttt{M8@default}: \\texttt{A1 + B6-LOO} (w/o \\texttt{C1})", "comparator"),
    ("M5@default", "\\texttt{M5@default}: \\texttt{A1 + B6-Naive + C1}", "comparator"),
    ("M6-b@default", "\\texttt{M6-b@default}: \\texttt{A1 + B6-LOO} (closed-form exact-Hat pool) + \\texttt{C1}", "comparator"),
    ("M6-a", "\\textbf{Ours (\\texttt{M6-a}): \\texttt{A1 + B6-LOO + C1}}", "ours"),
]
TABLE_S1B_METHODS = TABLE1_GROUP3
TABLE_S3_PANEL_A = [  # (key, label prefix, role, path of the C1 weights in the fold JSON or None)
    ("M10-a@default", "\\texttt{M10-a@default}: \\texttt{A1 + B1}", "comparator", ("hparams",)),
    ("M10-c@default", "\\texttt{M10-c@default}: \\texttt{A1 + B1} + $\\mathcal{L}_{\\mathrm{modal}}$", "comparator", ("hparams",)),
    ("M10-b@default", "\\texttt{M10-b@default}: \\texttt{A1 + B1} + $\\mathcal{L}_{\\mathrm{cons}}$", "comparator", ("hparams",)),
    ("M2@default", "\\texttt{M2@default}: \\texttt{A1 + B1 + C1}", "comparator", ("hparams",)),
    ("M8@default", "\\texttt{M8@default}: \\texttt{A1 + B6-LOO} (w/o \\texttt{C1})", "comparator", None),
    ("M6-a", "\\textbf{Ours (\\texttt{M6-a}): \\texttt{A1 + B6-LOO + C1}}", "ours", ("base",)),
]
TABLE_S3_PANEL_B = [
    ("M5@default", "\\texttt{M5@default}: \\texttt{B6-Naive} (raw \\texttt{B1} residual pool, no leverage scaling, no IQR gate)", "comparator"),
    ("M6-b@default", "\\texttt{M6-b@default}: closed-form Ridge exact-Hat LOO pool + IQR gate", "comparator"),
    ("M6-a", "\\textbf{Ours (\\texttt{M6-a}): in-fold \\texttt{B1} Hat-leverage debiased pool + IQR gate}", "ours"),
]

PAT_HEAD = ["\\textbf{\\texttt{rna}}", "\\textbf{\\texttt{wsi}}", "\\textbf{\\texttt{text}}", "\\textbf{\\texttt{rna+wsi}}",
            "\\textbf{\\texttt{rna+text}}", "\\textbf{\\texttt{wsi+text}}"]
AVG_HEAD = ["\\textbf{1-Mod Avg}", "\\textbf{2-Mod Avg}", "\\textbf{6-Missing Avg}"]
PROTOCOL_NOTE = ("Hyperparameter protocol: Ours (\\texttt{M6-a}) uses hyperparameters selected on the validation folds, and "
                 "the same validation folds are used for reporting, so its numbers are optimistic relative to the other rows; "
                 "every other row uses fixed default hyperparameters (\\texttt{@default}) or has no hyperparameter grid.")


def _metric_rows(doc: Doc, reg: Reg, spec, cols: Sequence[str], label_cols=1, prefix_cells=None) -> None:
    """Rows of macro values for ``cols`` (patterns / 1mod / 2mod / miss6); bold = column maximum (4 d.p.)."""
    flags = {c: _bold_flags({k: reg.s.macro_mean(k, c) for k, *_ in spec}, 4) for c in cols}
    for i, (key, label, role, *_) in enumerate(spec):
        cells = [reg.val(key, role, c, bold=flags[c][key]) for c in cols]
        lead = ([prefix_cells[i]] if prefix_cells else []) + [label]
        doc.row(lead + cells)


# ---------------------------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------------------------

def build_table1(s: I08Stats, i07: dict, records: list) -> Doc:
    reg = Reg("table1.tex", s, records)
    doc = Doc("table1.tex",
              "Overall survival prediction (C-index) on five TCGA cohorts. Values are mean $\\pm$ SD over five folds "
              "within each cohort; Avg.\\ is the mean $\\pm$ SD of the five cohort means.",
              "tab:overall_comparison", "l ccc ccccc c",
              ["\\textbf{Method}", "\\textbf{Img}", "\\textbf{RNA}", "\\textbf{Text}"]
              + [f"\\textbf{{{c}}}" for c in CANCERS_PRIME] + ["\\textbf{Avg.}"])

    def prime_row(r):
        cells = [reg.add("reference", "prime", r["name"], f"II:{c}", "pm3.3", (m, sd))
                 for c, (m, sd) in zip(CANCERS_PRIME, r["cohorts"])]
        cells.append(reg.add("reference", "prime", r["name"], "II:avg", "pm3.3", tuple(r["avg"])))
        doc.row([r["name"] + "$^\\dagger$"] + [_mark(x) for x in r["mods"]] + cells)

    def i07_row(arm, label, mods):
        d = i07[arm]
        cells = [reg.add("reference", "i07_test", arm, f"test:{c}", "pm3.3", tuple(d["cohorts"][c]))
                 for c in CANCERS_PRIME]
        cells.append(reg.add("reference", "i07_test", arm, "test:avg", "pm3.3", tuple(d["avg"])))
        doc.row([label] + [_mark(x) for x in mods] + cells)

    doc.group("Group 1: Unimodal baselines")
    for r in PRIME_TABLE_II:
        if r["group"] == "uni":
            prime_row(r)
    i07_row("wsi", "Standalone WSI-only (\\texttt{I07} Test)", (1, 0, 0))
    i07_row("rna", "Standalone RNA-only (\\texttt{I07} Test)", (0, 1, 0))
    i07_row("text", "Standalone Text-only (\\texttt{I07} Test)", (0, 0, 1))
    doc.rule()
    doc.group("Group 2: Complete-modality multimodal fusion and pretraining reference")
    for r in PRIME_TABLE_II:
        if r["group"] == "multi":
            prime_row(r)
    i07_row("tri", "PS3-style Backbone / TriModalSurv Bypass (\\texttt{I07} Test)", (1, 1, 1))
    cells = [reg.val("M0-a", "reference", "full", cancer=c, dec=3, sd_dec=3) for c in CANCERS_PRIME]
    cells.append(reg.val("M0-a", "reference", "full", dec=3, sd_dec=3))
    doc.row(["PS3-style Backbone / TriModalSurv Bypass (\\texttt{I07} Val $D_0$)"] + [_mark(1)] * 3 + cells)
    doc.rule()
    doc.group("Group 3: Incomplete-modality evaluation (mean over six missing-modality patterns, same 5-fold validation split)")
    cols = list(CANCERS_PRIME) + [None]
    flags = {}
    for c in cols:
        vals = {k: (s.cancer_mean(k, c, "miss6") if c else s.macro_mean(k, "miss6")) for k, _, _ in TABLE1_GROUP3}
        flags[c] = _bold_flags(vals, 3)
    for key, label, role in TABLE1_GROUP3:
        cells = [reg.val(key, role, "miss6", cancer=c, dec=3, sd_dec=3, bold=flags[c][key]) for c in cols]
        doc.row([label] + ["$\\circ$"] * 3 + cells)
    doc.notes = [
        "$\\checkmark$ / $\\times$: modality available / unavailable; $\\circ$: averaged over the six missing-modality "
        "patterns of Table~\\ref{tab:missing_robustness}.",
        "Rows marked $^\\dagger$ are quoted from PRIME Table~II (5-fold cross-validation test results on PRIME's own "
        "cohort splits); they were not rerun on our splits.",
        "Rows marked \\texttt{I07} Test are models of this study evaluated on the held-out test folds of our 5-fold split, "
        "as recorded in their result ledger (per-cohort SD: population SD over folds): in Group~1, separately trained "
        "single-modality models; in Group~2, the frozen tri-modal PS3-style backbone.",
        "The \\texttt{I07} Val $D_0$ row and Group~3 are computed on the validation folds of the same split "
        "(per-cohort SD: sample SD over folds). With all three modalities present, TriModalSurv applies the "
        "complete-modality identity bypass $D_0$ and returns the backbone prediction unchanged, so the bypass rows "
        "are not credited to TriModalSurv and are not bolded.",
        "Avg.: SD is the sample SD across the five cohort means. Bold: best value per column within Group~3.",
        PROTOCOL_NOTE,
    ]
    return doc


T2_COLS = [("full", "\\textbf{Full}"), ("rna+text", "\\textbf{LI} (RNA+Text)"), ("wsi+text", "\\textbf{LR} (WSI+Text)"),
           ("rna+wsi", "\\textbf{LT} (WSI+RNA)"), ("wsi", "\\textbf{OI} (WSI)"), ("rna", "\\textbf{OR} (RNA)"),
           ("text", "\\textbf{OT} (Text)")]


def build_table2(s: I08Stats, records: list, summary: dict) -> Doc:
    reg = Reg("table2.tex", s, records)
    doc = Doc("table2.tex",
              "Robustness to modalities missing at inference time (overall survival, C-index).",
              "tab:missing_robustness", "l c cccccc c",
              ["\\textbf{Method}"] + [h for _, h in T2_COLS] + ["\\textbf{6-Missing Avg}"])
    doc.group("External reference: PRIME Table~IV, Task-1 overall survival, 5-fold CV test$^\\dagger$")
    for r in PRIME_TABLE_IV:
        cells = [reg.add("reference", "prime", r["name"], f"IV:{i}", "pm3.3", (m, sd)) for i, (m, sd) in enumerate(r["cells"])]
        avg = float(np.mean([m for m, _ in r["cells"][1:]]))
        cells.append(reg.add("reference", "prime_derived", r["name"], "IV:mean_of_six", "f3", (avg,)))
        doc.row([f"PRIME {r['name']}$^\\dagger$"] + cells)
    doc.rule()
    doc.group("Controlled comparison on the frozen PS3-style backbone, same 5-fold validation split")
    keys = [k for k, _, _ in TABLE2_ROWS]
    flags = {c: _bold_flags({k: s.macro_mean(k, c) for k in keys}, 4) for c, _ in T2_COLS[1:]}
    flags["miss6"] = _bold_flags({k: s.macro_mean(k, "miss6") for k in keys}, 4)
    for key, label, role in TABLE2_ROWS:
        cells = [reg.val(key, role, "full", sd_dec=3)]
        cells += [reg.val(key, role, c, sd_dec=3, bold=flags[c][key]) for c, _ in T2_COLS[1:]]
        cells.append(reg.val(key, role, "miss6", bold=flags["miss6"][key]))
        doc.row([label] + cells)
    summary["ours_best_patterns_table2"] = sum(flags[c][OURS_KEY] for c, _ in T2_COLS[1:])
    doc.notes = [
        "LI / LR / LT: image / RNA / text left out (the other two modalities visible); OI / OR / OT: only image / RNA / "
        "text visible.",
        "$^\\dagger$: quoted from PRIME Table~IV (Task-1; models trained on complete data, modalities removed only at "
        "test time; mean $\\pm$ SD over 5-fold CV on PRIME's splits). Their 6-Missing Avg column is not reported by "
        "PRIME; we computed it as the mean of the six missing-pattern means.",
        "Lower block: mean over the five cohorts (each cohort averaged over its five validation folds) $\\pm$ sample SD "
        "across cohorts. The Full column is identical for every row because of the identity bypass $D_0$ and is not "
        "bolded. Bold: best value per missing-pattern column within the lower block.",
        PROTOCOL_NOTE,
    ]
    return doc


def build_table3(s: I08Stats, records: list, summary: dict) -> Doc:
    reg = Reg("table3.tex", s, records)
    doc = Doc("table3.tex",
              "Progressive ablation of the three core operators (\\texttt{A1}, \\texttt{C1}, \\texttt{B6-LOO}) over the "
              "six missing-modality patterns (five-cohort macro-average validation C-index).",
              "tab:progressive_ablation", "l cccccc ccc",
              ["\\textbf{Variant}"] + PAT_HEAD + AVG_HEAD)
    _metric_rows(doc, reg, TABLE3_ROWS, list(PATTERNS) + ["1mod", "2mod", "miss6"])
    parts = []
    for ref in TABLE3_PAIRED:
        pr = reg.paired(OURS_KEY, ref)
        summary[f"vs_{ref}"] = pr["raw"]
        parts.append(f"vs.\\ \\texttt{{{ref}}}: mean gain ${pr['mean']}$, ${pr['wins']}$ strict wins, ${pr['ties']}$ ties, "
                     f"one-sided $p{pr['p_one']}$ (two-sided $p{pr['p_two']}$)")
    n_splits = reg.add("reference", "config", "ledger", "n_splits", "int", (len(s.runs),))
    doc.notes = [
        f"Paired comparison of Ours over the {n_splits} cohort$\\times$fold validation splits (6-Missing Avg per split; "
        "Wilcoxon signed-rank test, zero differences discarded): " + "; ".join(parts) + ".",
        "Bold: best value per column.",
        PROTOCOL_NOTE,
    ]
    return doc


def build_table4(s: I08Stats, records: list) -> Doc:
    reg = Reg("table4.tex", s, records)
    doc = Doc("table4.tex",
              "Operator comparison within the subspace slot (Block~A) and the dynamic recovery slot (Block~B) "
              "(five-cohort macro-average validation C-index).",
              "tab:operator_comparison", "l ccc", ["\\textbf{Slot \\& Operator Variant}"] + AVG_HEAD)
    doc.group("Block A: subspace decomposition slot (all rows paired with \\texttt{B6-LOO})")
    _metric_rows(doc, reg, TABLE4_BLOCK_A, ["1mod", "2mod", "miss6"])
    doc.rule()
    doc.group("Block B: dynamic recovery operator slot")
    _metric_rows(doc, reg, TABLE4_BLOCK_B, ["1mod", "2mod", "miss6"])
    doc.notes = [
        "Block~B: \\texttt{M0-b}, \\texttt{M1-a@default} and \\texttt{M1-b@default} act in the 256-$d$ pooled space; "
        "all other rows act in the 32-$d$ \\texttt{A1} subspace trained with \\texttt{C1}.",
        "Bold: best value per column within each block.",
        PROTOCOL_NOTE,
    ]
    return doc


S1_FLOAT = ("Validation C-index of all evaluated methods by missing-modality pattern (Panel~A) and of the Table~1 "
            "Group~3 methods by cohort and pattern (Panel~B).", "tab:supp_s1_patterns")


def build_table_s1(s: I08Stats, records: list) -> List[Doc]:
    reg = Reg("table_s1.tex", s, records)
    a = Doc("table_s1.tex",
            "Panel A: per-pattern validation C-index (five-cohort macro-average) for all evaluated methods.",
            "tab:supp_s1_patterns", "l cccccc ccc c",
            ["\\textbf{Method / Variant}"] + PAT_HEAD + AVG_HEAD + ["\\textbf{$\\Delta$ vs.\\ \\texttt{M0-a/b} (wins)}"])
    cols = list(PATTERNS) + ["1mod", "2mod", "miss6"]
    flags = {c: _bold_flags({k: s.macro_mean(k, c) for k, _, _ in SINGLE_COLUMN_METHODS}, 4) for c in cols}
    for key, label, role in SINGLE_COLUMN_METHODS:
        cells = [reg.val(key, role, c, bold=flags[c][key]) for c in cols]
        if key == "M0-a":
            delta = "reference"
        else:
            pr = reg.paired(key, "M0-a", fields=("mean", "wins"))
            delta = f"${pr['mean']}$ (${pr['wins']}$)"
        a.row([label] + cells + [delta])
    n_splits = reg.add("reference", "config", "ledger", "n_splits", "int", (len(s.runs),))
    a.notes = [f"$\\Delta$: mean paired difference of 6-Missing Avg against \\texttt{{M0-a/b}} over the {n_splits} cohort$\\times$fold "
               "validation splits, with strict wins in parentheses. Bold: best value per column.", PROTOCOL_NOTE]

    b = Doc("table_s1.tex",
            "Panel B: cohort $\\times$ pattern validation C-index (mean $\\pm$ sample SD over "
            "five folds).",
            "tab:supp_s1_cohort_patterns", "ll cccccc c",
            ["\\textbf{Method}", "\\textbf{Cohort}"] + PAT_HEAD + ["\\textbf{6-Missing Avg}"])
    for i, (key, label, role) in enumerate(TABLE_S1B_METHODS):
        if i:
            b.rule("\\cmidrule(lr){1-9}")
        for j, c in enumerate(CANCERS_I08):
            cells = [reg.val(key, role, p, cancer=c, sd_dec=4) for p in PATTERNS + ("miss6",)]
            b.row([label if j == 0 else "", c] + cells)
    b.notes = [PROTOCOL_NOTE]
    return [a, b]


def build_table_s2(s: I08Stats, records: list, summary: dict) -> Doc:
    reg = Reg("table_s2.tex", s, records)
    doc = Doc("table_s2.tex",
              "Cohort-level 6-Missing Avg validation C-index (mean over six patterns and five folds).",
              "tab:supp_s2_cohorts", "p{56mm} ccccc c c",
              ["\\textbf{Method / Variant}"] + [f"\\textbf{{{c}}}" for c in CANCERS_I08]
              + ["\\textbf{6-Missing Avg}", "\\textbf{Above ref.}"], rotate=True)
    cols = list(CANCERS_I08) + [None]
    flags = {c: _bold_flags({k: (s.cancer_mean(k, c, "miss6") if c else s.macro_mean(k, "miss6"))
                             for k, _, _ in SINGLE_COLUMN_METHODS}, 4) for c in cols}
    for key, label, role in SINGLE_COLUMN_METHODS:
        cells = [reg.val(key, role, "miss6", cancer=c, bold=flags[c][key]) for c in cols]
        if key == "M0-a":
            n_txt = "reference"
        else:
            n = sum(s.cancer_mean(key, c, "miss6") > s.cancer_mean("M0-a", c, "miss6") for c in CANCERS_I08)
            n_txt = reg.add(role, "i08_stat", f"{key}|M0-a", "cohorts_above", "frac", (int(n), len(CANCERS_I08)))
            if role == "ours":
                summary["cohorts_improved"] = f"{n}/{len(CANCERS_I08)}"
        doc.row([label] + cells + [n_txt])
        if role == "ours":
            doc.row(["\\quad $\\Delta$ of Ours vs.\\ the reference row"]
                    + [f"${reg.diff(key, 'M0-a', 'miss6', cancer=c)}$" for c in cols] + [""])
    doc.notes = ["Above ref.: number of cohorts in which the row is above the reference row \\texttt{M0-a/b}. "
                 "$\\Delta$: difference of Ours from \\texttt{M0-a/b} in each cohort, computed from the unrounded means, "
                 "so it can differ in the last digit from the difference of the displayed values. "
                 "Bold: best value per column.", PROTOCOL_NOTE]
    return doc


def build_table_s3(s: I08Stats, records: list) -> Doc:
    reg = Reg("table_s3.tex", s, records)
    doc = Doc("table_s3.tex",
              "Decomposition of the \\texttt{C1} loss terms (Panel~A) and of the \\texttt{B6} "
              "residual-pool construction (Panel~B) (five-cohort macro-average validation C-index).",
              "tab:supp_s3_c1_b6", "p{58mm} cccccc ccc",
              ["\\textbf{Configuration}"] + PAT_HEAD + AVG_HEAD, rotate=True)
    cols = list(PATTERNS) + ["1mod", "2mod", "miss6"]
    labels = []
    for key, label, role, path in TABLE_S3_PANEL_A:
        if path is None:
            labels.append(label)
            continue
        lm = s.hparam(key, path + ("lambda_modal",))
        lc = s.hparam(key, path + ("lambda_cons",))
        lm_t = reg.add(role, "config", key, "lambda_modal", "g", (lm,))
        lc_t = reg.add(role, "config", key, "lambda_cons", "g", (lc,))
        labels.append(f"{label} ($\\lambda_m={lm_t}$, $\\lambda_c={lc_t}$)")
    spec_a = [(k, lab, role) for (k, _, role, _), lab in zip(TABLE_S3_PANEL_A, labels)]
    doc.group("Panel A: \\texttt{C1} loss terms")
    _metric_rows(doc, reg, spec_a, cols)
    doc.rule()
    doc.group("Panel B: \\texttt{B6} residual-pool construction")
    _metric_rows(doc, reg, TABLE_S3_PANEL_B, cols)
    doc.notes = [
        "All rows keep the anchor loss $\\mathcal{L}_{\\mathrm{anchor}}$. $\\lambda_m$ and $\\lambda_c$ are read from the "
        "per-fold records. In Panel~B, \\texttt{M6-b@default} keeps the gradient-trained \\texttt{B1} base predictor but "
        "builds its residual pool from an auxiliary closed-form Ridge fit, whereas Ours divides the in-fold \\texttt{B1} "
        "training residuals by the Hat-matrix leverage factor of Eq.~(8); \\texttt{M5@default} uses the raw in-fold "
        "\\texttt{B1} residuals without leverage scaling and without the IQR gate. Bold: best value per column within "
        "each panel.",
        PROTOCOL_NOTE,
    ]
    return doc


def _interp_summary(runs) -> Tuple[List[dict], dict]:
    interp = [runs[(c, f)]["interpretability"] for c in CANCERS_I08 for f in FOLDS]
    mech = []
    for u in ONE_MOD:
        rows = [r["mechanism"][u] for r in interp]
        m = {k: float(np.nanmean([x[k] for x in rows])) for k in rows[0]}
        m["modality"] = u
        mech.append(m)
    t1 = np.concatenate([r["faithfulness"]["abs_dh_top1"] for r in interp])
    rd = np.concatenate([r["faithfulness"]["abs_dh_rand"] for r in interp])
    wil = stats.wilcoxon(t1, rd, alternative="greater")
    s1 = np.concatenate([r["utility"]["s1"] for r in interp])
    al = np.concatenate([r["utility"]["alpha"] for r in interp])
    dE = np.concatenate([r["utility"]["dE"] for r in interp])
    rs1, ps1 = stats.spearmanr(s1, dE)
    ral, pal = stats.spearmanr(al, dE)
    hi = [x for r in interp for x in r["utility"]["half_dC"]["high"] if x is not None]
    lo = [x for r in interp for x in r["utility"]["half_dC"]["low"] if x is not None]
    n_sub = {r["stability"]["n_subsamples"] for r in interp}
    frac = {r["stability"]["frac"] for r in interp}
    if len(n_sub) != 1 or len(frac) != 1:
        raise AssertionError("stability protocol differs across folds")
    jac = [r["stability"]["jaccard_mean"] for r in interp]
    cs = [r["stability"]["cos_mean"] for r in interp]
    return mech, {
        "n_folds": len(interp), "n_subsamples": n_sub.pop(), "frac": frac.pop(),
        "jaccard": (float(np.mean(jac)), float(np.std(jac))), "cos": (float(np.mean(cs)), float(np.std(cs))),
        "n_queries": int(t1.size), "top1_med": float(np.median(t1)), "rand_med": float(np.median(rd)),
        "W": float(wil.statistic), "p_W": float(wil.pvalue),
        "share": float(np.nanmean([r["faithfulness"]["top1_linear_share_mean"] for r in interp])),
        "rho_s1": (float(rs1), float(ps1)), "rho_al": (float(ral), float(pal)), "mean_dE": float(np.mean(dE)),
        "hi": (len(hi), float(np.mean(hi))), "lo": (len(lo), float(np.mean(lo))),
    }


def _cross_check_report(report: str, mech: List[dict], it: dict, s: I08Stats) -> None:
    """The ledger report is a second, independently rendered source; every reused number must agree with it."""
    for m in mech:
        line = (f"| {m['modality']} | {m['r2_sha']:.4f} | {m['r2_res']:.4f} | {m['cos_sha']:.4f} | {m['cos_res']:.4f} | "
                f"{m['energy_sha']:.4f} | {m['rho']:.4f} | {m['rho_random']:.4f} |")
        if line not in report:
            raise ProvenanceError(f"mechanism row differs from the ledger report: {line}")
    for needle in (f"{it['jaccard'][0]:.4f} ± {it['jaccard'][1]:.4f}", f"{it['cos'][0]:.4f} ± {it['cos'][1]:.4f}",
                   f"{it['top1_med']:.5f} / {it['rand_med']:.5f}", f"W={it['W']:.1f}",
                   f"ρ={it['rho_s1'][0]:.4f}, p={it['rho_s1'][1]:.2e}", f"ρ={it['rho_al'][0]:.4f}, p={it['rho_al'][1]:.2e}",
                   f"{it['mean_dE']:+.5f}", f"{it['hi'][1]:+.4f}", f"{it['lo'][1]:+.4f}", f"{it['share']:.4f}",
                   f"n={it['n_queries']}", f"{it['n_subsamples']}×{int(round(it['frac'] * 100))}%"):
        if needle not in report:
            raise ProvenanceError(f"interpretability value {needle!r} not found in the ledger report")
    by_key = {}
    for line in report.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 11 and cells[0] in HANDOFF_MISS6:
            by_key[cells[0]] = cells
    for key in HANDOFF_MISS6:
        got = (f"{s.macro_mean(key, '1mod'):.4f}", f"{s.macro_mean(key, '2mod'):.4f}", f"{s.macro_mean(key, 'miss6'):.4f}")
        row = by_key.get(key)
        if row is None or (row[2], row[3], row[5]) != got:
            raise ProvenanceError(f"{key}: recomputed {got} differs from the ledger report row {row}")


def build_table_s4(mech: List[dict], records: list, s: I08Stats) -> Doc:
    reg = Reg("table_s4.tex", s, records)
    ic = s.interp_config()
    n_splits = reg.add("reference", "config", "ledger", "n_splits", "int", (len(s.runs),))
    doc = Doc("table_s4.tex",
              "Cross-modal predictability and risk-weight retention of the 32-$d$ shared "
              "component $p^{\\mathrm{sha}}$ versus the 224-$d$ orthogonal complement $p^{\\mathrm{res}}$ (validation, "
              f"mean over the {n_splits} cohort$\\times$fold splits).",
              "tab:supp_s4_mechanism", "l cccc cc cc",
              ["\\textbf{Target modality $u$}", "$R^2_{\\mathrm{val}}(p^{\\mathrm{sha}})$", "$R^2_{\\mathrm{val}}(p^{\\mathrm{res}})$",
               "$\\cos(p^{\\mathrm{sha}})$", "$\\cos(p^{\\mathrm{res}})$", "Energy share $p^{\\mathrm{sha}}$",
               "Energy share $p^{\\mathrm{res}}$", "$\\rho_r(u)$", "Random $r/d$"])
    for m in mech:
        u = m["modality"]
        f = lambda k, v=None: "$" + reg.add("reference", "i08_interp", u, k, "f4", (m[k] if v is None else v,)) + "$"
        doc.row([f"\\texttt{{{u}}}", f("r2_sha"), f("r2_res"), f("cos_sha"), f("cos_res"), f("energy_sha"),
                 f("energy_res", 1.0 - m["energy_sha"]), f("rho"), f("rho_random")])
    ratios = [m["rho"] / m["rho_random"] for m in mech]
    lo_t = reg.add("reference", "i08_interp", "rho_ratio", "min", "f1", (min(ratios),))
    hi_t = reg.add("reference", "i08_interp", "rho_ratio", "max", "f1", (max(ratios),))
    r_t = reg.add("reference", "config", "base", "r", "int", (ic["base"]["r"],))
    lm_t = reg.add("reference", "config", "base", "lambda_modal", "g", (ic["base"]["lambda_modal"],))
    wsi = next(m for m in mech if m["modality"] == "wsi")
    w = lambda k: reg.add("reference", "i08_interp", "wsi", k, "f4", (wsi[k],))
    doc.notes = [
        f"Computed on the default \\texttt{{M2}} base ($r={r_t}$, $\\lambda_m={lm_t}$). For each target modality $u$, a "
        "closed-form Ridge regressor is fitted on the training fold from the other two visible modalities and evaluated "
        "on the validation fold. $\\rho_r(u)=\\lVert U_u^\\top w_u\\rVert_2^2/\\lVert w_u\\rVert_2^2$ is the share of the "
        f"frozen risk-head weight energy inside the subspace, ${lo_t}\\times$ to ${hi_t}\\times$ the random expectation $r/d$.",
        f"For WSI, $R^2_{{\\mathrm{{val}}}}(p^{{\\mathrm{{sha}}}})$ is negative (${w('r2_sha')}$), while its cosine "
        f"(${w('cos_sha')}$ vs.\\ ${w('cos_res')}$) and $\\rho_r$ (${w('rho')}$) stay concentrated in the shared subspace.",
    ]
    return doc


def build_table_s5(it: dict, records: list, s: I08Stats) -> Doc:
    reg = Reg("table_s5.tex", s, records)
    ic = s.interp_config()
    a = lambda k, fmt, *v: reg.add("reference", "i08_interp", "interp", k, fmt, v)
    c = lambda k, fmt, *v: reg.add("reference", "config", "interp", k, fmt, v)
    n_sub, pct = c("n_subsamples", "int", it["n_subsamples"]), c("frac_pct", "int", int(round(it["frac"] * 100)))
    nq, nf = a("n_queries", "int", it["n_queries"]), a("n_folds", "int", it["n_folds"])
    K, tau, amax = c("K", "int", ic["K"]), c("tau", "g", ic["tau"]), c("alpha_max", "g", ic["alpha_max"])
    r, lm = c("r", "int", ic["base"]["r"]), c("lambda_modal", "g", ic["base"]["lambda_modal"])
    doc = Doc("table_s5.tex",
              f"Stability, faithfulness and gate utility of the residual retrieval on the "
              f"validation folds (default \\texttt{{M2}} base, $r={r}$, $\\lambda_m={lm}$; default \\texttt{{B6-LOO}} "
              f"with $K={K}$, $\\tau={tau}$, $\\alpha_{{\\max}}={amax}$).",
              "tab:supp_s5_interpretability", "ll l",
              ["\\textbf{Check}", "\\textbf{Metric}", "\\textbf{Value}"])
    rows = [
        (f"\\textcircled{{1}} Stability ({n_sub} $\\times$ {pct}\\% train subsamples)",
         f"Top-$K$ neighbour Jaccard (mean $\\pm$ SD over {nf} folds)",
         "$" + a("jaccard", "f4", it["jaccard"][0]) + "\\pm" + a("jaccard_sd", "f4", it["jaccard"][1]) + "$"),
        ("\\textcircled{1} Stability", "Residual-correction direction cosine (mean $\\pm$ SD)",
         "$" + a("cos", "f4", it["cos"][0]) + "\\pm" + a("cos_sd", "f4", it["cos"][1]) + "$"),
        ("\\textcircled{2} Faithfulness (Top-1 erasure)",
         f"Median $\\lvert\\Delta h\\rvert$: Top-1 vs.\\ random other neighbour ($n={nq}$)",
         "$" + a("top1_med", "f5", it["top1_med"]) + "$ vs.\\ $" + a("rand_med", "f5", it["rand_med"]) + "$"),
        ("\\textcircled{2} Faithfulness", "Paired Wilcoxon, Top-1 $>$ random",
         "$W=" + a("W", "f1", it["W"]) + "$, one-sided $p" + a("p_W", "p", it["p_W"]) + "$"),
        ("\\textcircled{2} Faithfulness", "Mean Top-1 share of the linear risk correction",
         "$" + a("share", "f4", it["share"]) + "$"),
        ("\\textcircled{3} Gate utility", f"Spearman$(s_{{(1)}}, \\Delta\\mathcal{{E}})$ ($n={a('n_queries', 'int', it['n_queries'])}$)",
         "$\\rho=" + a("rho_s1", "f4", it["rho_s1"][0]) + "$, $p" + a("p_s1", "p", it["rho_s1"][1]) + "$"),
        ("\\textcircled{3} Gate utility", "Spearman$(\\alpha_i, \\Delta\\mathcal{E})$",
         "$\\rho=" + a("rho_al", "f4", it["rho_al"][0]) + "$, $p" + a("p_al", "p", it["rho_al"][1]) + "$"),
        ("\\textcircled{3} Gate utility", "Mean $\\Delta\\mathcal{E}$ (positive: \\texttt{B6} closer to the full-modality risk than \\texttt{B1})",
         "$" + a("mean_dE", "+f5", it["mean_dE"]) + "$"),
        ("\\textcircled{3} Half split, $\\Delta$C-index (\\texttt{B6} $-$ \\texttt{B1})",
         f"High-confidence half $s_{{(1)}}\\ge\\delta_\\Omega$ ($n={a('n_hi', 'int', it['hi'][0])}$ pattern$\\times$fold units)",
         "$" + a("dC_hi", "+f4", it["hi"][1]) + "$"),
        ("\\textcircled{3} Half split, $\\Delta$C-index (\\texttt{B6} $-$ \\texttt{B1})",
         f"Low-confidence half $s_{{(1)}}<\\delta_\\Omega$ ($n={a('n_lo', 'int', it['lo'][0])}$ pattern$\\times$fold units)",
         "$" + a("dC_lo", "+f4", it["lo"][1]) + "$"),
    ]
    for row in rows:
        doc.row(list(row))
    doc.notes = [
        "Faithfulness removes the highest-weight neighbour (Top-1) or a random other neighbour among the Top-$K$ and "
        "renormalises the softmax weights over the remaining neighbours. $\\Delta\\mathcal{E}$ is the reduction of the "
        "absolute risk error with respect to the full-modality risk when \\texttt{B6-LOO} replaces \\texttt{B1}. "
        "The table is computed on the default base and default retrieval parameters, not on the validation-selected "
        "configuration of Ours, so that the correction is never identically zero.",
    ]
    return doc


# ---------------------------------------------------------------------------------------------
# Build, audit, write
# ---------------------------------------------------------------------------------------------

@dataclass
class BuildResult:
    outputs: Dict[str, str]
    records: List[CellRecord]
    summary: dict
    templates: Dict[str, str]


def build(repo_root: Path = REPO_ROOT) -> BuildResult:
    repo_root = Path(repo_root)
    load_prime_extract(repo_root)
    i08_dir = repo_root / I08_RES_REL
    runs = load_ledger(i08_dir)
    report = (i08_dir / "val_ablation_report_v1.md").read_text(encoding="utf-8")
    s = I08Stats(runs)
    i07 = load_i07(repo_root / I07_RES_REL)
    mech, it = _interp_summary(runs)
    _cross_check_report(report, mech, it, s)

    for key, want in HANDOFF_MISS6.items():
        if f"{s.macro_mean(key, 'miss6'):.4f}" != want:
            raise ProvenanceError(f"{key}: ledger 6-Missing Avg {s.macro_mean(key, 'miss6'):.4f} != handoff {want}")

    records: List[CellRecord] = []
    summary = {"ours_miss6": f"{s.macro_mean(OURS_KEY, 'miss6'):.4f}", "m0_miss6": f"{s.macro_mean('M0-a', 'miss6'):.4f}"}
    docs: Dict[str, List[Doc]] = {
        "table1.tex": [build_table1(s, i07, records)],
        "table2.tex": [build_table2(s, records, summary)],
        "table3.tex": [build_table3(s, records, summary)],
        "table4.tex": [build_table4(s, records)],
        "table_s1.tex": build_table_s1(s, records),
        "table_s2.tex": [build_table_s2(s, records, summary)],
        "table_s3.tex": [build_table_s3(s, records)],
        "table_s4.tex": [build_table_s4(mech, records, s)],
        "table_s5.tex": [build_table_s5(it, records, s)],
    }
    check_single_column(records)

    floats = {name: (render_float(ds, *S1_FLOAT) if len(ds) > 1 else ds[0].tex()) for name, ds in docs.items()}
    templates = {name: HEADER_COMMENT + "\n" + body + "\n" for name, body in floats.items()}
    preview = [
        "# TriModalSurv paper tables (auto-generated preview)",
        "",
        f"> Generated by `{GENERATOR_REL}` from the validation ledger `{I08_RES_REL.name}` (source commit "
        f"`{LEDGER_PIN['source_commit'][:8]}`, run_meta sha256 `{LEDGER_PIN['run_meta_sha256'][:12]}`). Do not edit by hand.",
        "> Single-column protocol: Ours (`M6-a`) uses validation-selected hyperparameters; every other row uses `@default` "
        "or has no grid. test_access stays false: no I08 test split was read.",
        "",
    ]
    for name, ds in docs.items():
        if len(ds) > 1:
            preview += [f"## {name}: {tex2md(S1_FLOAT[0])}", ""]
            for d in ds:
                preview += d.md(title=f"{name}, {tex2md(d.caption)}") + [""]
        else:
            preview += ds[0].md(title=f"{name}: {tex2md(ds[0].caption)}") + [""]
    templates["paper_tables_preview.md"] = "\n".join(preview)

    audit_records(records)
    recheck_i08_values(records, s)
    for name, tpl in templates.items():
        audit_template(name, tpl, records)
    outputs = {name: resolve(tpl, records, md=name.endswith(".md")) for name, tpl in templates.items()}
    for name, text in outputs.items():
        for bad in FORBIDDEN_TOKENS:
            if bad in text:
                raise ProvenanceError(f"forbidden token {bad!r} in {name}")
        if any(p in text for p in ("/" + "Users/", "/" + "home/")):
            raise ProvenanceError(f"local absolute path in {name}")
        if "\u2014" in text or (name.endswith(".tex") and "---" in text):
            raise ProvenanceError(f"em dash in {name}")
    return BuildResult(outputs, records, summary, templates)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="build and audit only; report files that differ on disk")
    ap.add_argument("--verify-prime-pdf", type=Path, help="Prime.pdf: re-extract pp. 6 and 8 and compare with the pinned extract")
    args = ap.parse_args(argv)
    if args.verify_prime_pdf:
        verify_extract_against_pdf(args.verify_prime_pdf, REPO_ROOT)
        print("PRIME extract reproduced from", args.verify_prime_pdf.name)
    res = build(REPO_ROOT)
    out_dir = REPO_ROOT / OUT_REL
    if args.check:
        stale = [n for n, t in res.outputs.items() if not (out_dir / n).exists() or (out_dir / n).read_text(encoding="utf-8") != t]
        print("stale:", stale or "none")
        return 1 if stale else 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in res.outputs.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(res.outputs)} files to {OUT_REL}; {len(res.records)} registered cells")
    print(json.dumps(res.summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
