#!/usr/bin/env python3
"""SCI 学术版 Anti-AI 与关键数字门禁（handoff-论文生成.md 第 5.4.2 节；坑 V23 / I05-04）。

用法:
    check_anti_ai_and_numbers.py [FILE ...] [--tables-dir DIR] [--allow-number N ...]
                                 [--forbid-number N ...] [--baseline OLD.tex]
                                 [--max-words 32] [--strict] [--json]

不给 FILE 时默认检查 <仓库根>/manuscript/bmc_initial_draft/ 下存在的 main.tex 与 appendix.tex。

文体规则（只看「正文视图」：去掉 TeX 注释、数学、tabular 类表体、verbatim、引用/交叉引用键）:
    LEX       AI 高频套话词黑名单（不区分大小写，含屈折形式；landscape 在 loss/optimization 语境放行）
    DASH      正文长破折号 U+2014、LaTeX ``---`` 与 \\textemdash（数学减号、表内占位、``--`` 范围放行）
    ING-TAIL  逗号后的空洞 -ing 评价尾巴（highlighting / underscoring / showcasing /
              demonstrating the superiority of / paving the way ...）
    NOT-ONLY  ``not only ... but also`` 句式（出现即违规）
    CONTRACT  英文口语缩略（don't / can't / isn't / won't / it's / 're / 've / 'll ...，直撇号与弯撇号）
    STARTER   相邻段落（或同段相邻句）连续以 Importantly, / Notably, / Crucially, /
              It is worth noting that / This suggests that 起手
    LONG      超过 --max-words（默认 32）词的句子，默认只告警（--strict 时升级为违规）

数字与路径规则（看「原文视图」：保留数学，只去注释与引用键；PATH 连注释一起扫）:
    PATH      含用户名的本机绝对路径（macOS 用户主目录、Linux home 目录、Windows 用户目录）
    STALE-NUM 已作废的旧错数（默认 296,448，见 handoff 6.3 第 1 条），可用 --forbid-number 追加
    TRACE-NUM 正文里的关键数字（≥3 位小数的指标，或正文中的 a/b 胜场）必须能在 --tables-dir
              的 .tex 表格里找到，或在 --allow-number 白名单里（坑 V23：禁止手抄派生数字）
    BASELINE  给 --baseline 时，与旧版逐项比较数字多重集、数学片段多重集与 \\cite/\\ref/\\label/
              \\input/\\includegraphics 键多重集，任何增删即违规（润色不得改动公式、数字、引用键）

退出码: 0 无违规（告警不影响）；1 有违规；2 用法错误或输入不存在。
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DRAFT_DIR = REPO_ROOT / "manuscript" / "bmc_initial_draft"
DEFAULT_INPUTS = (DRAFT_DIR / "main.tex", DRAFT_DIR / "appendix.tex")
DEFAULT_TABLES_DIR = DRAFT_DIR / "tables"
DEFAULT_FORBIDDEN_NUMBERS = ("296,448",)
DEFAULT_MAX_WORDS = 32
PARA_MARK = "\u00b6"  # 正文视图里的段落分隔哨兵（替换已被抹掉的命令字符，长度不变）

# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------
_W = r"(?<![A-Za-z0-9])"  # 不用 \b：下划线后 \b 不成立（坑 E36）
_E = r"(?![A-Za-z0-9])"

LEXICAL_BLACKLIST: tuple[tuple[str, str], ...] = (
    ("delve", r"delv(?:e|es|ed|ing)"),
    ("pivotal", r"pivotal(?:ly)?"),
    ("underscore", r"underscor(?:e|es|ed|ing)"),
    ("intricate", r"intricate(?:ly)?|intricac(?:y|ies)"),
    ("tapestry", r"tapestr(?:y|ies)"),
    ("realm", r"realms?"),
    ("testament", r"testaments?"),
    ("seamless", r"seamless(?:ly)?"),
    ("paradigm shift", r"paradigm[\s-]+shifts?"),
    ("groundbreaking", r"ground[\s-]?breaking"),
    ("unprecedented", r"unprecedented(?:ly)?"),
    ("revolutionary", r"revolutionar(?:y|ily)|revolutioni[sz](?:e|es|ed|ing)"),
    ("harness", r"harness(?:es|ed|ing)?"),
    ("bolster", r"bolster(?:s|ed|ing)?"),
    ("foster", r"foster(?:s|ed|ing)?"),
    ("multifaceted", r"multi-?faceted"),
    ("meticulous", r"meticulous(?:ly|ness)?"),
    ("crucial role", r"crucial\s+roles?"),
    ("vital role", r"vital\s+roles?"),
    ("shed light on", r"sh(?:ed|eds|edding)\s+(?:new\s+|some\s+)?light\s+on"),
    ("pave the way", r"pav(?:e|es|ed|ing)\s+the\s+way"),
    ("treasure trove", r"treasure[\s-]+troves?"),
    (
        "landscape",
        r"(?<!loss\s)(?<!optimization\s)(?<!optimisation\s)(?<!objective\s)(?<!energy\s)(?<!error\s)"
        r"(?<!fitness\s)landscapes?",
    ),
)
LEXICAL_RES = tuple((name, re.compile(_W + "(?:" + pat + ")" + _E, re.IGNORECASE)) for name, pat in LEXICAL_BLACKLIST)

ING_TAIL_RE = re.compile(
    r",\s*(?:thereby\s+)?(?:highlighting|underscoring|showcasing|emphasi[sz]ing|underlining|reaffirming"
    r"|solidifying|cementing|paving\s+the\s+way|demonstrating\s+the\s+(?:superiority|effectiveness|efficacy"
    r"|robustness|potential|power|strength|value|advantages?|merits?|versatility|promise))" + _E,
    re.IGNORECASE,
)
NOT_ONLY_RE = re.compile(_W + r"not\s+only" + _E, re.IGNORECASE)
CONTRACTION_RE = re.compile(
    _W + r"(?:[A-Za-z]+n['\u2019]t|(?:it|that|there|here|what|who|let|he|she)['\u2019]s"
    r"|[A-Za-z]+['\u2019](?:re|ve|ll|d|m))" + _E,
    re.IGNORECASE,
)
STARTER_RE = re.compile(
    r"(?:Importantly\s*,|Notably\s*,|Crucially\s*,|It\s+is\s+worth\s+noting\s+that|This\s+suggests\s+that)"
    + _E
)
EMDASH_RE = re.compile(r"\u2014|-{3,}|\\textemdash" + _E + r"|\\emdash" + _E)
PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.])/(?:Users|home)/[A-Za-z0-9._-]+|(?<![A-Za-z])[A-Za-z]:\\+Users\\+[A-Za-z0-9._-]+"
)

# 数字：带符号、千分位（, 或 {,} 或 \,）、小数；分数 a/b
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9.])[+\-\u2212]?\d{1,3}(?:(?:,|\{,\}|\\,)\d{3})+(?:\.\d+)?(?![0-9])"
    r"|(?<![A-Za-z0-9.])[+\-\u2212]?\d+(?:\.\d+)?(?![0-9])"
)
KEY_DECIMAL_RE = re.compile(r"^\d+\.\d{3,}$")
FRACTION_RE = re.compile(r"(?<![A-Za-z0-9./])(\d{1,4})\s*/\s*(\d{1,4})(?![0-9/])")

ABBREVIATIONS = {
    "e.g", "i.e", "al", "fig", "figs", "eq", "eqs", "tab", "vs", "cf", "etc", "sec", "ref", "refs",
    "approx", "no", "resp", "ca", "st", "dr", "mr", "ms", "nos",
}

MATH_ENVS = (
    "equation", "align", "gather", "multline", "eqnarray", "displaymath", "math", "flalign", "alignat",
    "split", "subequations",
)
TABLE_BODY_ENVS = ("tabular", "tabularx", "tabulary", "longtable", "array", "tabu", "tblr")
VERBATIM_ENVS = ("verbatim", "lstlisting", "minted", "comment")
KEY_COMMANDS = (
    "cite", "citet", "citep", "citealt", "citealp", "citeauthor", "citeyear", "nocite", "parencite",
    "textcite", "autocite", "ref", "eqref", "autoref", "cref", "Cref", "pageref", "nameref", "label",
    "input", "include", "includegraphics", "url", "href", "bibliography", "bibliographystyle",
    "addbibresource", "usepackage", "RequirePackage", "documentclass", "newcommand", "renewcommand",
    "providecommand", "DeclareMathOperator", "hypersetup", "setlength", "setcounter", "graphicspath",
    "begin", "end",
)
REF_LIKE = {"ref", "eqref", "autoref", "cref", "Cref", "pageref", "nameref"}
BASELINE_KEY_COMMANDS = {
    "cite", "citet", "citep", "citealt", "citealp", "parencite", "textcite", "autocite", "ref", "eqref",
    "autoref", "cref", "Cref", "label", "input", "include", "includegraphics",
}
BREAK_COMMANDS = {
    "section", "subsection", "subsubsection", "paragraph", "subparagraph", "chapter", "part", "caption",
    "title", "abstract", "item", "par", "maketitle", "footnote", "bibitem", "newpage", "clearpage",
}


@dataclass
class Finding:
    path: str
    line: int
    col: int
    severity: str  # "error" | "warning"
    rule: str
    message: str
    excerpt: str


# ---------------------------------------------------------------------------
# TeX 视图：所有变换保持字符串长度不变，偏移量可直接映射回原文行列
# ---------------------------------------------------------------------------
def _blank(chars: list[str], start: int, end: int, token: str = "") -> None:
    for i in range(start, end):
        if chars[i] != "\n":
            chars[i] = " "
    for j, ch in enumerate(token):
        if start + j < end and chars[start + j] != "\n":
            chars[start + j] = ch


def _is_escaped(text: str, pos: int) -> bool:
    n = 0
    i = pos - 1
    while i >= 0 and text[i] == "\\":
        n += 1
        i -= 1
    return n % 2 == 1


def strip_comments(text: str) -> str:
    """把未转义 % 起到行尾的注释换成空格（\\% 不是注释）。"""
    chars = list(text)
    i = 0
    while i < len(chars):
        if text[i] == "%" and not _is_escaped(text, i):
            j = text.find("\n", i)
            j = len(text) if j < 0 else j
            _blank(chars, i, j)
            i = j
        else:
            i += 1
    return "".join(chars)


def _match_group(text: str, pos: int, open_ch: str, close_ch: str) -> int:
    """text[pos] == open_ch，返回匹配的 close_ch 之后的位置；不配对返回 -1。"""
    depth = 0
    i = pos
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t":
        pos += 1
    return pos


def _blank_envs(text: str, chars: list[str], envs: tuple[str, ...], token: str) -> None:
    names = "|".join(re.escape(e) for e in envs)
    begin_re = re.compile(r"\\begin\s*\{(" + names + r")(\*?)\}")
    pos = 0
    while True:
        m = begin_re.search(text, pos)
        if not m:
            return
        env = m.group(1) + m.group(2)
        end_re = re.compile(r"\\end\s*\{" + re.escape(env) + r"\}")
        e = end_re.search(text, m.end())
        stop = e.end() if e else len(text)
        _blank(chars, m.start(), stop, token)
        pos = stop


def _blank_inline_math(text: str, chars: list[str]) -> None:
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] in "[(" and not _is_escaped(text, i):
            closer = "\\]" if text[i + 1] == "[" else "\\)"
            j = text.find(closer, i + 2)
            j = n if j < 0 else j + 2
            _blank(chars, i, j, "X")
            i = j
            continue
        if ch == "$" and not _is_escaped(text, i):
            if text.startswith("$$", i):
                j = text.find("$$", i + 2)
                j = n if j < 0 else j + 2
            else:
                j = i + 1
                while j < n and not (text[j] == "$" and not _is_escaped(text, j)):
                    j += 1
                j = min(j + 1, n)
            _blank(chars, i, j, "X")
            i = j
            continue
        i += 1


def _blank_key_commands(text: str, chars: list[str], ref_token: bool) -> None:
    names = "|".join(sorted(KEY_COMMANDS, key=len, reverse=True))
    cmd_re = re.compile(r"\\(" + names + r")(?![A-Za-z@])\*?")
    for m in cmd_re.finditer(text):
        if _is_escaped(text, m.start()):
            continue
        name = m.group(1)
        stop = m.end()
        n_args = 1
        while True:
            p = _skip_ws(text, stop)
            if p < len(text) and text[p] == "[":
                q = _match_group(text, p, "[", "]")
                if q < 0:
                    break
                stop = q
                continue
            if p < len(text) and text[p] == "{" and n_args > 0:
                q = _match_group(text, p, "{", "}")
                if q < 0:
                    break
                stop = q
                n_args -= 1
                continue
            break
        token = "N" if (ref_token and name in REF_LIKE) else ""
        _blank(chars, m.start(), stop, token)
        if name in {"begin", "end"} and chars[m.start()] != "\n":
            chars[m.start()] = PARA_MARK


def _blank_remaining_commands(text: str, chars: list[str]) -> None:
    """抹掉其余命令名、单字符转义、花括号与 ~；保留参数正文。分节/标题类命令处插入段落哨兵。"""
    cmd_re = re.compile(r"\\([A-Za-z@]+)\*?|\\.")
    for m in cmd_re.finditer(text):
        if _is_escaped(text, m.start()):
            continue
        name = m.group(1)
        _blank(chars, m.start(), m.end())
        if name in BREAK_COMMANDS:
            chars[m.start()] = PARA_MARK
            if name in {"caption", "footnote", "section", "subsection", "subsubsection", "paragraph",
                        "title", "chapter"}:
                p = _skip_ws(text, m.end())
                if p < len(text) and text[p] == "{":
                    q = _match_group(text, p, "{", "}")
                    if q > 0:
                        chars[q - 1] = PARA_MARK
    for i, ch in enumerate(text):
        if ch in "{}~" and chars[i] == ch and not _is_escaped(text, i):
            chars[i] = " "


def prose_view(text: str) -> str:
    """文体规则用：去注释、verbatim、数学（留单词占位 X）、表体、键命令与命令名。"""
    stage = stage1_view(text)
    chars = list(stage)
    _blank_key_commands(stage, chars, ref_token=True)
    stage2 = "".join(chars)
    chars = list(stage2)
    _blank_remaining_commands(stage2, chars)
    return "".join(chars)


def _blank_outside_document(text: str, chars: list[str]) -> None:
    """有 \\begin{document} 时，导言区与 \\end{document} 之后都不是正文。"""
    b = re.search(r"\\begin\s*\{document\}", text)
    if b:
        _blank(chars, 0, b.end())
    e = re.search(r"\\end\s*\{document\}", text)
    if e:
        _blank(chars, e.start(), len(text))


def stage1_view(text: str) -> str:
    """去注释、导言区、verbatim、数学与表体，保留命令（DASH 规则在此视图上查 \\textemdash 与 ---）。"""
    t = strip_comments(text)
    chars = list(t)
    _blank_outside_document(t, chars)
    _blank_envs(t, chars, VERBATIM_ENVS, "")
    _blank_envs(t, chars, TABLE_BODY_ENVS, "")
    _blank_envs(t, chars, MATH_ENVS, "X")
    t = "".join(chars)
    chars = list(t)
    _blank_inline_math(t, chars)
    return "".join(chars)


def numbers_view(text: str, mask_tables: bool) -> str:
    """数字规则用：去注释与键命令参数，保留数学；mask_tables 时再去表体。"""
    t = strip_comments(text)
    chars = list(t)
    _blank_envs(t, chars, VERBATIM_ENVS, "")
    if mask_tables:
        _blank_outside_document(t, chars)
        _blank_envs(t, chars, TABLE_BODY_ENVS, "")
    t = "".join(chars)
    chars = list(t)
    _blank_key_commands(t, chars, ref_token=False)
    return "".join(chars)


def normalize_number(tok: str) -> str:
    tok = tok.replace("{,}", "").replace("\\,", "").replace(",", "")
    return tok.lstrip("+-\u2212")


# ---------------------------------------------------------------------------
# 段落与句子
# ---------------------------------------------------------------------------
_PARA_SPLIT_RE = re.compile(r"\n[ \t]*\n|" + PARA_MARK)
_SENT_END_RE = re.compile(r"[.!?](?=[\s)\"'\u201d]*(?:\s+[A-Z(\[\"'\u201c]|\s*$))")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-]*")


def paragraphs(prose: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for m in _PARA_SPLIT_RE.finditer(prose):
        if prose[start:m.start()].strip():
            spans.append((start, m.start()))
        start = m.end()
    if prose[start:].strip():
        spans.append((start, len(prose)))
    return spans


def sentences(prose: str, start: int, end: int) -> list[tuple[int, int]]:
    out = []
    seg_start = start
    for m in _SENT_END_RE.finditer(prose, start, end):
        before = prose[seg_start:m.start()]
        word = re.search(r"([A-Za-z.]+)$", before)
        if word and word.group(1).lower().rstrip(".") in ABBREVIATIONS:
            continue
        if word and len(word.group(1)) == 1 and word.group(1).isupper() and word.group(1) != "X":
            continue  # 姓名首字母 "A. Smith"
        out.append((seg_start, m.end()))
        seg_start = m.end()
    if prose[seg_start:end].strip():
        out.append((seg_start, end))
    return [(a + (len(prose[a:b]) - len(prose[a:b].lstrip())), b) for a, b in out if prose[a:b].strip()]


# ---------------------------------------------------------------------------
# 检查
# ---------------------------------------------------------------------------
class Checker:
    def __init__(self, path: Path, text: str, display: str):
        self.path = path
        self.text = text
        self.display = display
        self.line_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]
        self.findings: list[Finding] = []

    def loc(self, offset: int) -> tuple[int, int]:
        line = bisect.bisect_right(self.line_starts, offset)
        return line, offset - self.line_starts[line - 1] + 1

    def add(self, offset: int, severity: str, rule: str, message: str, end: int | None = None) -> None:
        line, col = self.loc(offset)
        line_text = self.text[self.line_starts[line - 1]:].split("\n", 1)[0]
        excerpt = line_text.strip()
        if len(excerpt) > 160:
            c = max(0, col - 60)
            excerpt = "..." + line_text[c:c + 140].strip() + "..."
        self.findings.append(Finding(self.display, line, col, severity, rule, message, excerpt))

    # 文体
    def check_style(self, max_words: int, strict: bool) -> None:
        stage1 = stage1_view(self.text)
        for m in EMDASH_RE.finditer(stage1):
            self.add(m.start(), "error", "DASH", f"正文破折号 {m.group(0)!r}，改用逗号、括号或独立短句")
        prose = prose_view(self.text)
        for name, rx in LEXICAL_RES:
            for m in rx.finditer(prose):
                self.add(m.start(), "error", "LEX", f"AI 套话词 {name!r}（命中 {m.group(0)!r}）")
        for m in ING_TAIL_RE.finditer(prose):
            self.add(m.start(), "error", "ING-TAIL", f"空洞 -ing 评价尾巴 {_squash(m.group(0))!r}，改用具体数字或因果句收尾")
        for m in NOT_ONLY_RE.finditer(prose):
            self.add(m.start(), "error", "NOT-ONLY", "禁用 'not only ... but also' 排比")
        for m in CONTRACTION_RE.finditer(prose):
            self.add(m.start(), "error", "CONTRACT", f"口语缩略 {m.group(0)!r}")

        prev_para_starter = False
        for p_start, p_end in paragraphs(prose):
            sents = sentences(prose, p_start, p_end)
            prev_sent_starter = False
            for idx, (s_start, s_end) in enumerate(sents):
                sent = prose[s_start:s_end]
                is_starter = bool(STARTER_RE.match(sent))
                if is_starter and ((idx == 0 and prev_para_starter) or (idx > 0 and prev_sent_starter)):
                    where = "相邻段落" if idx == 0 else "同段相邻句"
                    self.add(s_start, "error", "STARTER", f"{where}连续以 {_squash(STARTER_RE.match(sent).group(0))!r} 等机械起手")
                prev_sent_starter = is_starter
                n_words = len(_WORD_RE.findall(sent))
                if n_words > max_words:
                    self.add(s_start, "error" if strict else "warning", "LONG",
                             f"句子 {n_words} 词，超过 {max_words} 词，建议拆成单命题短句")
            prev_para_starter = bool(sents) and bool(STARTER_RE.match(prose[sents[0][0]:sents[0][1]]))

    # 路径（原文，连注释一起扫）
    def check_paths(self) -> None:
        for m in PATH_RE.finditer(self.text):
            self.add(m.start(), "error", "PATH", "含用户名的本机绝对路径，改用仓库相对路径或占位符")

    # 数字
    def number_tokens(self, mask_tables: bool) -> list[tuple[int, str, str]]:
        view = numbers_view(self.text, mask_tables)
        return [(m.start(), m.group(0), normalize_number(m.group(0))) for m in NUMBER_RE.finditer(view)]

    def check_stale(self, forbidden: set[str]) -> None:
        for off, raw, norm in self.number_tokens(mask_tables=False):
            if norm in forbidden:
                self.add(off, "error", "STALE-NUM", f"已作废的旧数字 {raw!r}")

    def check_trace(self, table_numbers: set[str], allow: set[str]) -> None:
        known = table_numbers | allow
        for off, raw, norm in self.number_tokens(mask_tables=True):
            if KEY_DECIMAL_RE.match(norm) and norm not in known:
                self.add(off, "error", "TRACE-NUM", f"关键数字 {raw!r} 在表格与白名单中都找不到（V23：须由脚本生成表回指）")
        prose = prose_view(self.text)
        for m in FRACTION_RE.finditer(prose):
            frac = f"{m.group(1)}/{m.group(2)}"
            if frac not in known:
                self.add(m.start(), "error", "TRACE-NUM", f"胜场/计数 {frac!r} 在表格与白名单中都找不到")

    def invariants(self) -> dict[str, Counter]:
        t = strip_comments(self.text)
        maths: Counter = Counter()
        for m in re.finditer(r"\$\$.*?\$\$|(?<!\\)\$.+?(?<!\\)\$|\\\[.*?\\\]|\\\(.*?\\\)", t, re.S):
            maths[_squash(m.group(0))] += 1
        names = "|".join(re.escape(e) for e in MATH_ENVS)
        for m in re.finditer(r"\\begin\{(" + names + r")(\*?)\}.*?\\end\{\1\2\}", t, re.S):
            maths[_squash(m.group(0))] += 1
        keys: Counter = Counter()
        cmd = "|".join(sorted(BASELINE_KEY_COMMANDS, key=len, reverse=True))
        for m in re.finditer(r"\\(" + cmd + r")(?![A-Za-z@])\*?(?:\s*\[[^\]]*\])*\s*\{([^}]*)\}", t):
            for k in m.group(2).split(","):
                keys[f"\\{m.group(1)}{{{k.strip()}}}"] += 1
        nums = Counter(norm for _, _, norm in self.number_tokens(mask_tables=False))
        return {"number": nums, "math": maths, "key": keys}


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def collect_table_numbers(tables_dir: Path) -> set[str]:
    out: set[str] = set()
    for p in sorted(tables_dir.glob("*.tex")):
        t = strip_comments(p.read_text(encoding="utf-8"))
        out.update(normalize_number(m.group(0)) for m in NUMBER_RE.finditer(t))
        out.update(f"{a}/{b}" for a, b in FRACTION_RE.findall(t))
    return out


def compare_baseline(cur: Checker, base: Checker) -> None:
    a, b = base.invariants(), cur.invariants()
    labels = {"number": "数字", "math": "数学片段", "key": "引用/交叉引用键"}
    for kind in ("number", "math", "key"):
        removed = a[kind] - b[kind]
        added = b[kind] - a[kind]
        for item, n in sorted(removed.items()):
            cur.findings.append(Finding(cur.display, 0, 0, "error", "BASELINE",
                                        f"相对旧版少了 {labels[kind]} ×{n}", item[:160]))
        for item, n in sorted(added.items()):
            cur.findings.append(Finding(cur.display, 0, 0, "error", "BASELINE",
                                        f"相对旧版多了 {labels[kind]} ×{n}", item[:160]))


def _display(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return p.name


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="SCI 学术版 Anti-AI 与关键数字门禁（handoff 5.4.2）。退出码 0 = 无违规，1 = 有违规，2 = 用法错误。",
    )
    ap.add_argument("files", nargs="*", type=Path, help="待检查的 .tex 文件（默认 main.tex 与 appendix.tex）")
    ap.add_argument("--tables-dir", type=Path, default=None,
                    help="TRACE-NUM 用的表格目录（默认 manuscript/bmc_initial_draft/tables；目录不存在或无 .tex 时只告警跳过）")
    ap.add_argument("--allow-number", action="append", default=[], metavar="N",
                    help="不在表格里但允许出现在正文的关键数字（可重复）")
    ap.add_argument("--forbid-number", action="append", default=[], metavar="N",
                    help="追加的已作废数字（默认已含 296,448）")
    ap.add_argument("--baseline", type=Path, default=None,
                    help="旧版 .tex；只允许配一个输入文件，比较数字、数学片段与引用键是否被改动")
    ap.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS, help="句长告警阈值（默认 32）")
    ap.add_argument("--strict", action="store_true", help="把 LONG 告警升级为违规")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出 findings")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:  # argparse 用法错误统一为 2
        return 0 if exc.code == 0 else 2
    files = list(args.files) or [p for p in DEFAULT_INPUTS if p.exists()]
    if not files:
        print("check_anti_ai_and_numbers: 未给输入文件，且默认的 main.tex / appendix.tex 都不存在", file=sys.stderr)
        return 2
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        print(f"check_anti_ai_and_numbers: 输入不存在: {', '.join(missing)}", file=sys.stderr)
        return 2
    if args.baseline is not None:
        if len(files) != 1:
            print("check_anti_ai_and_numbers: --baseline 只能配一个输入文件", file=sys.stderr)
            return 2
        if not args.baseline.is_file():
            print(f"check_anti_ai_and_numbers: 旧版不存在: {args.baseline}", file=sys.stderr)
            return 2
    if args.max_words < 1:
        print("check_anti_ai_and_numbers: --max-words 须为正整数", file=sys.stderr)
        return 2

    forbidden = {normalize_number(n) for n in (*DEFAULT_FORBIDDEN_NUMBERS, *args.forbid_number)}
    allow = {normalize_number(n) if "/" not in n else n.replace(" ", "") for n in args.allow_number}
    tables_dir = args.tables_dir if args.tables_dir is not None else DEFAULT_TABLES_DIR
    notes: list[str] = []
    table_numbers: set[str] | None = None
    if tables_dir.is_dir() and any(tables_dir.glob("*.tex")):
        table_numbers = collect_table_numbers(tables_dir)
    elif args.tables_dir is not None:
        print(f"check_anti_ai_and_numbers: 表格目录不存在或没有 .tex: {tables_dir}", file=sys.stderr)
        return 2
    else:
        notes.append(f"默认表格目录 {_display(tables_dir)} 不存在或没有 .tex，TRACE-NUM 已跳过")

    findings: list[Finding] = []
    for p in files:
        c = Checker(p, p.read_text(encoding="utf-8"), _display(p))
        c.check_style(args.max_words, args.strict)
        c.check_paths()
        c.check_stale(forbidden)
        if table_numbers is not None:
            c.check_trace(table_numbers, allow)
        if args.baseline is not None:
            compare_baseline(c, Checker(args.baseline, args.baseline.read_text(encoding="utf-8"),
                                        _display(args.baseline)))
        c.findings.sort(key=lambda f: (f.line, f.col, f.rule))
        findings.extend(c.findings)

    n_err = sum(f.severity == "error" for f in findings)
    n_warn = sum(f.severity == "warning" for f in findings)
    if args.json:
        print(json.dumps({"errors": n_err, "warnings": n_warn, "notes": notes,
                          "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            tag = "ERROR" if f.severity == "error" else "WARN "
            print(f"{f.path}:{f.line}:{f.col}: {tag} [{f.rule}] {f.message} | {f.excerpt}")
        for note in notes:
            print(f"NOTE: {note}")
        by_rule = Counter(f.rule for f in findings if f.severity == "error")
        summary = ", ".join(f"{k}={v}" for k, v in sorted(by_rule.items())) or "无"
        print(f"[check] {len(files)} 个文件：违规 {n_err}（{summary}），告警 {n_warn}")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
