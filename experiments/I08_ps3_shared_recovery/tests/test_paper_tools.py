"""论文工具脚本自测：Anti-AI / 关键数字门禁与 Fig. 1 矢量导出脚本。

- check_anti_ai_and_numbers.py：每条规则一个违规样例 + 一个近似但合法的放行样例。
- export_framework_pdf.sh：只测不启动 Chrome 的部分（语法、可执行位、参数、拒绝覆盖、缺工具）；
  真实导出需设 I08_RUN_CHROME_EXPORT=1（本机有 Chrome / pdfcrop / gs 时）。
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
CHECKER_PATH = TOOLS / "check_anti_ai_and_numbers.py"
EXPORT_PATH = TOOLS / "export_framework_pdf.sh"


def _load_checker():
    name = "i08_check_anti_ai_and_numbers"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, CHECKER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # 坑 E4：dataclass 需要模块已注册
    spec.loader.exec_module(mod)
    return mod


chk = _load_checker()

DOC_HEAD = "\\documentclass{article}\n\\usepackage{booktabs}\n\\begin{document}\n"
DOC_TAIL = "\n\\end{document}\n"


def _run(tmp_path: Path, body: str, *extra: str, tables: dict[str, str] | None = None,
         wrap: bool = True, capsys=None) -> tuple[int, list]:
    """写临时 tex，跑 main(--json)，返回 (退出码, findings 列表)。"""
    tex = tmp_path / "doc.tex"
    tex.write_text((DOC_HEAD + body + DOC_TAIL) if wrap else body, encoding="utf-8")
    tdir = tmp_path / "tables"
    tdir.mkdir(exist_ok=True)
    for name, content in (tables or {"t.tex": "0.6657 & 22/25 \\\\\n"}).items():
        (tdir / name).write_text(content, encoding="utf-8")
    rc = chk.main([str(tex), "--tables-dir", str(tdir), "--json", *extra])
    import json
    out = capsys.readouterr().out
    return rc, json.loads(out)["findings"]


def _rules(findings, severity="error"):
    return sorted(f["rule"] for f in findings if f["severity"] == severity)


# ---------------------------------------------------------------------------
# 干净样例：数学、表格占位、注释、范围、所有格、转义百分号全部放行
# ---------------------------------------------------------------------------
CLEAN_BODY = r"""
\section{Methods}
The shared subspace has rank $r=32$, and the residual uses $1 - H_{jj}^{\Omega}$ with $\lambda_{\text{hat}}=1.0$.
The trainable map holds 4.71\% of the parameters, and Cox's partial likelihood is unchanged.
Its gain was 0.6657 on 22/25 folds over pages 10--30 (Table~\ref{tab:main}).
% ---------------------------------------------------------------- notes
% Notably, this comment line is not prose and may say pivotal --- freely.
We avoid a loss landscape argument and cite prior work \cite{foster2020harnessing}.
\begin{equation}
  \hat{z} = U^\top (x - \mu) --- y
\end{equation}
\begin{table}[t]
\caption{Overall C-index.}
\begin{tabular}{lcc}
\toprule
Method & BLCA & BRCA \\
\midrule
Mean imputation & --- & — \\
\bottomrule
\end{tabular}
\end{table}
"""


def test_clean_document_passes(tmp_path, capsys):
    rc, findings = _run(tmp_path, CLEAN_BODY, capsys=capsys)
    assert _rules(findings) == [], findings
    assert rc == 0


# ---------------------------------------------------------------------------
# 违规样例：逐规则
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sentence,rule", [
    ("We delve into the data.", "LEX"),
    ("This is a pivotal step.", "LEX"),
    ("The results underscore the need for care.", "LEX"),
    ("We harnessed three modalities.", "LEX"),
    ("Recovery plays a crucial role here.", "LEX"),
    ("These findings shed light on recovery.", "LEX"),
    ("This work paves the way for recovery.", "LEX"),
    ("The clinical landscape is complex.", "LEX"),
    ("The fusion is seamless.", "LEX"),
    ("The gain is small---but stable.", "DASH"),
    ("The gain is small\u2014but stable.", "DASH"),
    ("The gain is small\\textemdash but stable.", "DASH"),
    ("The model improved the C-index, highlighting its value.", "ING-TAIL"),
    ("The model improved the C-index, demonstrating the superiority of the design.", "ING-TAIL"),
    ("The model improved, thereby showcasing robustness.", "ING-TAIL"),
    ("It recovers not only RNA but also text.", "NOT-ONLY"),
    ("We don't retrain the Cox layer.", "CONTRACT"),
    ("It\u2019s a linear map.", "CONTRACT"),
    ("The gate can't be trained.", "CONTRACT"),
])
def test_rule_violations_are_caught(tmp_path, capsys, sentence, rule):
    rc, findings = _run(tmp_path, sentence, capsys=capsys)
    assert rule in _rules(findings), findings
    assert rc == 1


def test_consecutive_paragraph_starters(tmp_path, capsys):
    body = "Importantly, the gate is fixed.\n\nNotably, the map is linear.\n"
    rc, findings = _run(tmp_path, body, capsys=capsys)
    assert _rules(findings) == ["STARTER"]
    assert rc == 1
    # 同段相邻句同样拦截
    rc, findings = _run(tmp_path, "Notably, A holds. It is worth noting that B holds.", capsys=capsys)
    assert _rules(findings) == ["STARTER"]


def test_single_starter_is_allowed(tmp_path, capsys):
    body = "Notably, the gate is fixed.\n\nThe map is linear.\n\nNotably, the bypass is exact.\n"
    rc, findings = _run(tmp_path, body, capsys=capsys)
    assert _rules(findings) == [] and rc == 0


def test_long_sentence_warns_and_strict_fails(tmp_path, capsys):
    long_sentence = " ".join(["word"] * 40) + "."
    rc, findings = _run(tmp_path, long_sentence, capsys=capsys)
    assert _rules(findings, "warning") == ["LONG"]
    assert rc == 0
    rc, findings = _run(tmp_path, long_sentence, "--strict", capsys=capsys)
    assert _rules(findings) == ["LONG"] and rc == 1


def test_inline_math_counts_as_one_word(tmp_path, capsys):
    # 30 个普通词 + 一段很长的行内数学：数学只算 1 个词，不触发 32 词告警
    sentence = " ".join(["word"] * 30) + r" $a_{1} + a_{2} + a_{3} + a_{4} + a_{5} + a_{6} + a_{7}$."
    rc, findings = _run(tmp_path, sentence, capsys=capsys)
    assert _rules(findings, "warning") == []


def test_escaped_percent_does_not_swallow_prose(tmp_path, capsys):
    # 守卫：\% 不是注释起点；若误当注释，后面的违规词会被吞掉
    rc, findings = _run(tmp_path, r"It uses 4.71\% of the parameters, a pivotal saving.", capsys=capsys)
    assert _rules(findings) == ["LEX"]


def test_path_with_username_is_caught_even_in_comments(tmp_path, capsys):
    leak = "/" + "Users" + "/alice/project/fig.pdf"
    rc, findings = _run(tmp_path, f"Plain text.\n% see {leak}\n", capsys=capsys)
    assert _rules(findings) == ["PATH"] and rc == 1
    leak2 = "/" + "home" + "/bob/data"
    rc, findings = _run(tmp_path, f"Data are in \\texttt{{{leak2}}}.", capsys=capsys)
    assert _rules(findings) == ["PATH"]
    rc, findings = _run(tmp_path, r"Figures live in \texttt{figures/framework.pdf}.", capsys=capsys)
    assert _rules(findings) == []


@pytest.mark.parametrize("text", ["296,448 parameters.", "$296{,}448$ parameters.", "296\\,448 parameters."])
def test_stale_number_is_caught(tmp_path, capsys, text):
    rc, findings = _run(tmp_path, text, capsys=capsys)
    assert "STALE-NUM" in _rules(findings) and rc == 1


def test_trace_number_requires_table_or_allowlist(tmp_path, capsys):
    rc, findings = _run(tmp_path, "The C-index was $0.6657$ on 22/25 folds.", capsys=capsys)
    assert _rules(findings) == [] and rc == 0
    rc, findings = _run(tmp_path, "The C-index was 0.6658 on 21/25 folds.", capsys=capsys)
    assert _rules(findings) == ["TRACE-NUM", "TRACE-NUM"] and rc == 1
    rc, findings = _run(tmp_path, "The C-index was 0.6658 on 21/25 folds.",
                        "--allow-number", "0.6658", "--allow-number", "21/25", capsys=capsys)
    assert _rules(findings) == [] and rc == 0


def test_trace_number_reads_bold_and_signed_table_cells(tmp_path, capsys):
    tables = {"t.tex": r"\textbf{0.6657} & $+0.0138$ & 37{,}152 \\" + "\n"}
    rc, findings = _run(tmp_path, "The gain was $+0.0138$ (0.6657).", tables=tables, capsys=capsys)
    assert _rules(findings) == []


def test_baseline_detects_changed_numbers_math_and_keys(tmp_path, capsys):
    base = tmp_path / "base.tex"
    original = DOC_HEAD + r"Gain $+0.0138$ in $r=32$ (Table~\ref{tab:a}) \cite{k1}." + DOC_TAIL
    base.write_text(original, encoding="utf-8")
    tables = {"t.tex": "$+0.0138$ & 0.0139 \\\\\n"}
    rc, findings = _run(tmp_path, original, "--baseline", str(base), wrap=False, tables=tables, capsys=capsys)
    assert _rules(findings) == [] and rc == 0
    for changed in (
        original.replace("0.0138", "0.0139"),
        original.replace("r=32", "r = 16"),
        original.replace("tab:a", "tab:b"),
    ):
        rc, findings = _run(tmp_path, changed, "--baseline", str(base), wrap=False, tables=tables,
                            capsys=capsys)
        assert "TRACE-NUM" not in _rules(findings)
        assert "BASELINE" in _rules(findings) and rc == 1, changed


def test_usage_errors_exit_2(tmp_path):
    assert chk.main([str(tmp_path / "missing.tex")]) == 2
    tex = tmp_path / "a.tex"
    tex.write_text("x", encoding="utf-8")
    assert chk.main([str(tex), "--tables-dir", str(tmp_path / "no_tables")]) == 2
    assert chk.main([str(tex), str(tex), "--baseline", str(tex)]) == 2
    assert chk.main(["--bogus-flag", str(tex)]) == 2


def test_checker_cli_is_executable_and_exit_codes(tmp_path):
    assert os.access(CHECKER_PATH, os.X_OK)
    tex = tmp_path / "a.tex"
    tex.write_text("We delve into it.\n", encoding="utf-8")
    tdir = tmp_path / "tables"
    tdir.mkdir()
    (tdir / "t.tex").write_text("0.6657\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(CHECKER_PATH), str(tex), "--tables-dir", str(tdir)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "[LEX]" in r.stdout
    r = subprocess.run([sys.executable, str(CHECKER_PATH), "--help"], capture_output=True, text=True)
    assert r.returncode == 0


# ---------------------------------------------------------------------------
# 两个脚本共同：无本机用户名路径（坑 I05-04）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", [CHECKER_PATH, EXPORT_PATH, Path(__file__)])
def test_no_username_paths_in_tools(path):
    text = path.read_text(encoding="utf-8")
    assert ("/" + "Users" + "/") not in text
    assert ("/" + "home" + "/") not in text


# ---------------------------------------------------------------------------
# export_framework_pdf.sh
# ---------------------------------------------------------------------------
def _sh(*args, env=None, cwd=None):
    e = dict(os.environ)
    e.update(env or {})
    e.setdefault("LANG", "en_US.UTF-8")  # 坑 G3：UTF-8 locale 下跑 bash 3.2
    return subprocess.run(["/bin/bash", str(EXPORT_PATH), *args], capture_output=True, text=True,
                          env=e, cwd=cwd)


def test_export_script_is_executable_and_parses():
    assert os.access(EXPORT_PATH, os.X_OK)
    r = subprocess.run(["/bin/bash", "-n", str(EXPORT_PATH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_export_help_and_unknown_args(tmp_path):
    r = _sh("--help", cwd=tmp_path)
    assert r.returncode == 0 and "--print-to-pdf" in r.stdout
    r = _sh("--bogus", cwd=tmp_path)
    assert r.returncode == 2 and "未知参数" in r.stderr
    r = _sh("--html", cwd=tmp_path)
    assert r.returncode == 2
    r = _sh("--page-px", "1600by980", cwd=tmp_path)
    assert r.returncode == 2
    assert list(tmp_path.iterdir()) == []  # 参数错误不产生任何副作用（坑 G2）


def test_export_missing_input_and_missing_tools(tmp_path):
    r = _sh("--html", str(tmp_path / "nope.html"), "--out-dir", str(tmp_path))
    assert r.returncode == 2 and "不存在" in r.stderr
    html = tmp_path / "fig.html"
    html.write_text("<html></html>", encoding="utf-8")
    r = _sh("--html", str(html), "--out-dir", str(tmp_path), env={"CHROME_BIN": str(tmp_path / "no-chrome")})
    assert r.returncode == 2 and "找不到可执行工具" in r.stderr


def test_export_refuses_to_overwrite_without_force(tmp_path):
    html = tmp_path / "fig.html"
    html.write_text("<html></html>", encoding="utf-8")
    (tmp_path / "framework.pdf").write_bytes(b"keep-me")
    r = _sh("--html", str(html), "--out-dir", str(tmp_path))
    assert r.returncode == 2 and "--force" in r.stderr
    assert (tmp_path / "framework.pdf").read_bytes() == b"keep-me"


TEST_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: 1600px 980px; margin: 0; }
* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
html, body { margin: 0; padding: 0; background: #FFFFFF; }
#root { width: 1600px; height: HEIGHTpx; overflow: hidden; background: #FFFFFF; }
</style></head><body><div id="root"><svg width="1600" height="980" xmlns="http://www.w3.org/2000/svg">
<rect x="40" y="60" width="600" height="400" rx="16" fill="#E8EEF5" stroke="#444" stroke-dasharray="8 6"/>
<text x="60" y="110" font-size="28">Tri-Modal Feature Encoding</text></svg></div></body></html>
"""


@pytest.mark.skipif(os.environ.get("I08_RUN_CHROME_EXPORT") != "1",
                    reason="真实 Chrome 导出默认不跑；设 I08_RUN_CHROME_EXPORT=1 开启")
def test_export_real_chrome_roundtrip(tmp_path):
    ok = tmp_path / "ok"
    bad = tmp_path / "bad"
    ok.mkdir()
    bad.mkdir()
    (tmp_path / "fig.html").write_text(TEST_HTML.replace("HEIGHT", "980"), encoding="utf-8")
    (tmp_path / "overflow.html").write_text(TEST_HTML.replace("HEIGHT", "2200"), encoding="utf-8")
    r = _sh("--html", str(tmp_path / "fig.html"), "--out-dir", str(ok))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (ok / "framework.pdf").stat().st_size > 0 and (ok / "framework.png").stat().st_size > 0
    r = _sh("--html", str(tmp_path / "overflow.html"), "--out-dir", str(bad))
    assert r.returncode == 1 and "页数" in r.stderr
    assert list(bad.iterdir()) == []
