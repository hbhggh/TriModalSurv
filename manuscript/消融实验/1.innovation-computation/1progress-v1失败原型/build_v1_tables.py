"""v1 原型检索（patient-fixed-padmask-v2）结果表的只读取数与对拍脚本。

只读 tako-formal 归档的 75 个原始 JSON，生成复盘文档 §4 的表 A/B/C（Markdown，stdout），
并与 v1 历史报告「癌症为单位.md」逐条对拍到 6 位小数。不训练、不重评测、不写任何实验目录。

运行：
    PYTHONDONTWRITEBYTECODE=1 python3 build_v1_tables.py            # 表 A/B/C（Markdown）
    PYTHONDONTWRITEBYTECODE=1 python3 build_v1_tables.py --latex > v1-table1.tex   # 仿 Table 1 的 LaTeX
"""

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
I01 = ROOT / "experiments/I01_patient_retrieval/results"
FORMAL = I01 / "archive/legacy-tako-formal-20260915/raw/tako-formal/evidence/formal"
REPORT = I01 / "原因分析-ai-prompt&md/癌症为单位.md"

PROTOCOL = "patient-fixed-padmask-v2"
CANCERS = ["BRCA", "UCEC", "LUAD", "BLCA", "LGG"]  # 与 4.progress Table 1 列序一致
SEEDS = [123, 132, 213, 231, 321]
GRIDS = ["rna_100", "text_100", "both_100", "none"]
ARMS = ["m0real", "m1", "retrieval"]
ARM_NAME = {"m0real": "不补偿", "m1": "均值补偿", "retrieval": "v1 检索"}

# 4.progress S0-force（用户所说的 v2）的癌种 overall，取自 4progress-claude交接/实验先验知识与公式说明.md §3
V2_OVERALL = {"BRCA": 0.667270, "UCEC": 0.630369, "LUAD": 0.587039, "BLCA": 0.578982, "LGG": 0.738872}


def load():
    c = {}
    for arm in ARMS:
        for cancer in CANCERS:
            for seed in SEEDS:
                d = json.loads((FORMAL / f"{arm}_{cancer}_s{seed}.json").read_text())
                assert d["protocol_id"] == PROTOCOL, (arm, cancer, seed, d["protocol_id"])
                assert (d["arm"], d["cancer"], d["seed"]) == (arm, cancer, seed)
                assert sorted(d["grids"]) == sorted(GRIDS), (arm, cancer, seed)
                for g in GRIDS:
                    c[cancer, seed, g, arm] = float(d["grids"][g]["cindex_B"])
    assert len(c) == 300
    return c


def check_report(c):
    """与历史报告按癌种展开的 100 行（×3 臂）逐条对拍到 6 位。"""
    text = re.sub(r"<[^>]+>|★", "", REPORT.read_text())
    cancer, n = None, 0
    for line in text.splitlines():
        m = re.match(r"### (\w+)$", line.strip())
        if m:
            cancer = m.group(1) if m.group(1) in CANCERS else None
            continue
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if cancer and len(cells) >= 5 and cells[0].isdigit() and cells[1] in GRIDS:
            seed, g = int(cells[0]), cells[1]
            for arm, shown in zip(["retrieval", "m1", "m0real"], cells[2:5]):
                assert f"{c[cancer, seed, g, arm]:.6f}" == shown, (cancer, seed, g, arm, shown)
                n += 1
    assert n == 300, n
    return n


def header():
    cols = [f"{cancer}/{ARM_NAME[a]}" for cancer in CANCERS for a in ARMS]
    return "| 场景 | " + " | ".join(cols) + " |\n| --- |" + " --- |" * len(cols)


def fmt_group(means, sds=None):
    """means: 同癌三臂原值；按原值取最大值加粗（并列全部加粗）。"""
    best = max(means)
    out = []
    for i, v in enumerate(means):
        s = f"{v:.6f}" + (f" ± {sds[i]:.4f}" if sds else "")
        out.append(f"**{s}**" if v == best else s)
    return out


def table_a(c):
    lines = [header()]
    overall = {}
    for g in GRIDS:
        row = []
        for cancer in CANCERS:
            vals = [[c[cancer, s, g, a] for s in SEEDS] for a in ARMS]
            row += fmt_group([statistics.mean(v) for v in vals], [statistics.stdev(v) for v in vals])
        lines.append(f"| {g} | " + " | ".join(row) + " |")
    row = []
    for cancer in CANCERS:
        o = [statistics.mean(c[cancer, s, g, a] for s in SEEDS for g in GRIDS) for a in ARMS]
        overall[cancer] = dict(zip(ARMS, o))
        row += fmt_group(o)
    lines.append("| overall | " + " | ".join(row) + " |")
    return "\n".join(lines), overall


def table_b(c, seed):
    lines = [header()]
    for g in GRIDS:
        row = []
        for cancer in CANCERS:
            row += fmt_group([c[cancer, seed, g, a] for a in ARMS])
        lines.append(f"| {g} | " + " | ".join(row) + " |")
    row = []
    for cancer in CANCERS:
        row += fmt_group([statistics.mean(c[cancer, seed, g, a] for g in GRIDS) for a in ARMS])
    lines.append("| overall | " + " | ".join(row) + " |")
    return "\n".join(lines)


def table_c(c, overall):
    lines = [
        "| 癌种 | 不补偿 | 均值补偿 | v1 检索 | v1 严格胜两条基线 | v2 S0-force | v2 严格胜两条基线 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    w1 = w2 = 0
    for cancer in CANCERS:
        o = overall[cancer]
        base = max(o["m0real"], o["m1"])
        win1 = o["retrieval"] > o["m0real"] and o["retrieval"] > o["m1"]
        # v2 的 overall 取自已核验的六位展示值；其基线与 v1 同一批 checkpoint、同值
        win2 = V2_OVERALL[cancer] > round(base, 6)
        w1 += win1
        w2 += win2
        lines.append(
            f"| {cancer} | {o['m0real']:.6f} | {o['m1']:.6f} | {o['retrieval']:.6f} | {'胜' if win1 else '负'}"
            f" | {V2_OVERALL[cancer]:.6f} | {'胜' if win2 else '负'} |"
        )
    tot = {a: statistics.mean(c[k] for k in c if k[3] == a) for a in ARMS}
    lines.append(
        f"| **五癌 100 组等权** | {tot['m0real']:.6f} | {tot['m1']:.6f} | {tot['retrieval']:.6f} | **{w1}/5**"
        f" | 0.640506 | **{w2}/5** |"
    )
    return "\n".join(lines), tot, w1, w2


LATEX_ROWS = [("rna_100", "RNA masked"), ("text_100", "Text masked"), ("both_100", "Both masked"), ("none", "None")]

LATEX_HEAD = r"""\documentclass[11pt,a4paper]{article}
\usepackage[landscape,margin=15mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{booktabs}
\usepackage{caption}
\captionsetup{skip=6pt}
\pagestyle{empty}
\begin{document}
% 由 build_v1_tables.py --latex 从 75 个原始 JSON 生成；版式仿 main.tex Table 1（tab:prototype-compensation）。
% main.tex 中为 sidewaystable；此处用横向页面 + table 等价渲染。
\begin{table}[htbp]
\centering
\caption{Comparison of three compensation strategies across five cancers
under four modality-availability settings for the v1 prototype retrieval
(protocol \texttt{patient-fixed-padmask-v2}). Entries are test C-indices
averaged over five seeds; \emph{Overall} is the equally weighted mean of the
four settings of a cohort. Proto.\,v1 denotes the unconditional Top-1 patient
retrieval of v1.}
\label{tab:prototype-compensation-v1}
\scriptsize
\setlength{\tabcolsep}{2pt}
\renewcommand{\arraystretch}{1.35}
\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}l*{15}{c}@{}}
\toprule
 & \multicolumn{3}{c}{BRCA} & \multicolumn{3}{c}{UCEC}
 & \multicolumn{3}{c}{LUAD} & \multicolumn{3}{c}{BLCA}
 & \multicolumn{3}{c}{LGG} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-10}
\cmidrule(lr){11-13}\cmidrule(lr){14-16}
Scenario""" + "\n" + "\n".join([r" & No comp. & Mean & Proto.\,v1"] * 5) + r" \\" + "\n\\midrule"

LATEX_TAIL = r"""\bottomrule
\end{tabular*}
\par\smallskip
\begin{minipage}{\linewidth}
\scriptsize
Scenarios: RNA masked, Text masked and Both masked remove the RNA profile,
the pathology report or both for all test patients (\texttt{rna\_100},
\texttt{text\_100}, \texttt{both\_100}); None (\texttt{none}) adds no
artificial mask but retains naturally occurring missingness and is therefore
not a complete-data condition. Overall is an average and not a fifth
experimental scenario. Strategies: No comp., no compensation (m0real), missing
modalities are masked; Mean, mean imputation (m1), a missing modality is
replaced by the element-wise training mean of the same cohort; Proto.\,v1, the
v1 retrieval (\texttt{retrieval}): the training patient with the highest cosine
similarity between row-order-flattened, centred WSI features over commonly
valid rows is selected (Top-1), and its raw RNA/Text features replace the
missing ones with full validity weight, without routing, shrinkage or
down-weighting. Bold marks the highest unrounded value among the three
strategies within a cohort and row; ties are all bold. The three strategies use
the same 25 frozen networks; no model was retrained and no statistical test was
performed. Macro-average over five cohorts, five seeds and four settings:
Proto.\,v1 %s, Mean %s, No comp.\ %s; Proto.\,v1 was higher than both
references in %d of five cohorts (BRCA and UCEC).
\end{minipage}
\end{table}
\end{document}"""


def latex(c):
    def row(label, means_by_cancer):
        cells = []
        for means in means_by_cancer:
            best = max(means)
            cells += [rf"\textbf{{{v:.6f}}}" if v == best else f"{v:.6f}" for v in means]
        return f"{label} & " + " & ".join(cells) + r" \\"

    body = [row(name, [[statistics.mean(c[k, s, g, a] for s in SEEDS) for a in ARMS] for k in CANCERS])
            for g, name in LATEX_ROWS]
    body.append(r"\midrule")
    body.append(row("Overall", [[statistics.mean(c[k, s, g, a] for s in SEEDS for g in GRIDS) for a in ARMS]
                                for k in CANCERS]))
    tot = {a: statistics.mean(c[key] for key in c if key[3] == a) for a in ARMS}
    wins = sum(
        all(statistics.mean(c[k, s, g, "retrieval"] for s in SEEDS for g in GRIDS)
            > statistics.mean(c[k, s, g, b] for s in SEEDS for g in GRIDS) for b in ("m0real", "m1"))
        for k in CANCERS
    )
    tail = LATEX_TAIL % (f"{tot['retrieval']:.6f}", f"{tot['m1']:.6f}", f"{tot['m0real']:.6f}", wins)
    return LATEX_HEAD + "\n" + "\n".join(body) + "\n" + tail


def main():
    c = load()
    if "--latex" in sys.argv:
        check_report(c)
        print(latex(c))
        return
    n = check_report(c)
    a, overall = table_a(c)
    ctab, tot, w1, w2 = table_c(c, overall)
    assert f"{tot['retrieval']:.6f}" == "0.628964", tot
    assert f"{tot['m1']:.6f}" == "0.631825", tot
    assert f"{tot['m0real']:.6f}" == "0.630751", tot
    assert (w1, w2) == (2, 4), (w1, w2)
    print("<!-- 表 A -->\n" + a + "\n")
    for s in SEEDS:
        print(f"<!-- 表 B seed {s} -->\n" + table_b(c, s) + "\n")
    print("<!-- 表 C -->\n" + ctab + "\n")
    print(f"<!-- CHECK: 75 JSON, 300 values, report match {n}/300, overall "
          f"{tot['retrieval']:.6f}/{tot['m1']:.6f}/{tot['m0real']:.6f}, wins v1={w1}/5 v2={w2}/5 -->")


if __name__ == "__main__":
    main()
