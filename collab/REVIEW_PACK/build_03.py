#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机械化生成 03_results.md：从既有报告/留档表逐节原文抽取（不重排、不改数字），并标注来源。
用法：cd <repo> && python3 collab/REVIEW_PACK/build_03.py
"""
import pathlib, re, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
S5 = ROOT / "collab/20260827-三方对比战役/s5_report.md"
AT = ROOT / "collab/20260902-A测缺失补偿/a_test_report.md"
R4 = ROOT / "collab/20260902-A测缺失补偿/r4_numbers.txt"
GATE = ROOT / "collab/20260902-A测缺失补偿/table_gate_4arms.md"
OUT = ROOT / "collab/REVIEW_PACK/03_results.md"


def read(p):
    return p.read_text(encoding="utf-8").split("\n")


def section(lines, start_prefix, level="## "):
    """返回从以 start_prefix 开头的标题行起，到下一个同级或更高级标题前的原文。"""
    out, on = [], False
    for ln in lines:
        if ln.startswith(start_prefix):
            on = True
        elif on and ln.startswith("#") and (len(ln) - len(ln.lstrip("#"))) <= (len(level) - 1):
            break
        if on:
            out.append(ln)
    if not out:
        raise SystemExit(f"SECTION_NOT_FOUND: {start_prefix}")
    return out


def r4_block(lines, header_prefix):
    out, on = [], False
    for ln in lines:
        if ln.startswith("### ") and ln.startswith(header_prefix):
            on = True
        elif on and ln.startswith("### "):
            break
        if on:
            out.append(ln)
    if not out:
        raise SystemExit(f"R4_BLOCK_NOT_FOUND: {header_prefix}")
    return out


s5, at, r4, gate = read(S5), read(AT), read(R4), read(GATE)
rel = lambda p: str(p.relative_to(ROOT))
blocks = []
blocks.append(f"""# 03. 结果（逐表原文抄录；生成时间 {datetime.date.today().isoformat()}）

**本文件由 `collab/REVIEW_PACK/build_03.py` 机械抽取生成**：每个区块是源文件对应章节的逐字复制（含其自带的口径说明），区块标题标明来源文件与章节；抽取脚本不重算、不重排、不改数字。手写部分只有本文件末尾的「不理想处明写」与「数字冲突」两节。
判定规则速查：逐 seed 严格 `>` 计数（胜:负:平，|Δ|≤1e-6 记平），配对Δ中位 = 逐 seed 差的中位；|配对Δ中位|<0.02 为噪声带；**全部未做统计推断**。

---
""")

blocks.append(f"## [源: `{rel(S5)}` §数据口径注记]\n")
blocks += section(s5, "## 数据口径注记")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(S5)}` §逐 seed 判定矩阵（test c-index，5 癌 × 5 seed，MCAT / PORPOISE / NPJ-A / NPJ-B 逐值）]\n")
blocks += section(s5, "## 逐 seed 判定矩阵")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(S5)}` §逐 seed 胜负计数（NPJ-A vs baseline）]\n")
blocks += section(s5, "## 逐 seed 胜负计数")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(S5)}` §判定结论（S5 报告原文）]\n")
blocks += section(s5, "## 判定结论")
blocks.append("\n---\n")

blocks.append(f"## [源: `{rel(AT)}` §实验臂]\n")
blocks += section(at, "## 实验臂")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §一 E0 vs S5 NPJ-B（完整模态）]\n")
blocks += section(at, "## 一、")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §二 E1 vs E0（4 格点）]\n")
blocks += section(at, "## 二、")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §二 b E0d 消融（E0d vs E0，E1 vs E0d）]\n")
blocks += section(at, "## 二 b、")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §二 c E0m 同底座判别（原型 vs 均值填；预注册规则）]\n")
blocks += section(at, "## 二 c、")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §二 d NPJ-D 底座 25-seed 系统级对比 + 填充护栏（r6；预注册规则）]\n")
blocks += section(at, "## 二 d、")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §三 与 S5 三方对照（完整模态中位 + A 口径行）]\n")
blocks += section(at, "## 三、")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(AT)}` §四 机理证据（含 gate 版 M1 盲补对照）]\n")
blocks += section(at, "## 四、")
blocks.append("\n---\n")

R6 = ROOT / "collab/20260906-NPJ-D消融/r6_numbers.txt"
r6 = read(R6)
blocks.append(f"## [源: `{rel(R6)}` r6 派生量留档（B 口径主判定五节 + 自检 + 异常 seed；脚本 `tools/r6_numbers.py` 生成）]\n")
for hp in ["### [cindex_B] 覆盖", "### [cindex_B] E1_vs_D", "### [cindex_B] E1_vs_Dm", "### [cindex_B] Dm_vs_D", "### [cindex_B] E0(C)_vs_D", "### [cindex_B] D_vs_S5", "### [cindex_B] 各臂中位", "### [cindex_B] 自检", "### [cindex_B] 异常 seed"]:
    blocks += r4_block(r6, hp)
    blocks.append("")
blocks.append("\n---\n")
blocks.append(f"## [源: `{rel(R4)}` 派生量留档（脚本 `tools/r4_numbers.py` 生成）]\n")
for hp in ["### 中位（B）", "### 异常 seed 扫描", "### 5-seed 极差", "### both_100 相对 none 的中位跌幅", "### 十、", "### 十三、", "### 十四、", "### 平局明细"]:
    blocks += r4_block(r4, hp)
    blocks.append("")
blocks.append("\n---\n")

blocks.append(f"## [源: `{rel(GATE)}` gate 版四臂（M0-real / M1 / M1b / M2）格点 none 与 both_100（其余 11 格点见原表）]\n")
blocks += section(gate, "## 格点 none")
blocks += section(gate, "## 格点 both_100")
blocks.append("\n---\n")

blocks.append("""## 不理想处明写（手写，数字均出自上文区块）

- 三方对比（S5）：NPJ 骨架（A 口径）对 MCAT / PORPOISE 只在 BLCA、BRCA 领先（各 5:0）；**LGG 对两 baseline 0:5 全败**（NPJ−MCAT 逐 seed 差中位 −0.1066，最大 −0.1415）；**UCEC 对 PORPOISE 0:5**；LUAD 1:4 / 2:3。原论文"全面优势"在本口径下不成立。
- 骨架 seed 方差大：LGG NPJ-B 5-seed 极差 0.1273、UCEC NPJ-B 0.1389（PORPOISE 同癌种 0.0302 / 0.0284）。
- 最低单格：S5 表 NPJ-B UCEC s123 = 0.5248；A 测表 E0d BRCA s321 both_100 = 0.4845；gate 版附录 BLCA m2 s213 = 0.4311、UCEC m2 s231 = 0.4803。最高单格：PORPOISE LGG s213 = 0.8370；创新臂最高 E0 LGG none s123 = s213 = 0.8081。
- CAP-Recall（E1 vs E0）：BLCA 四格点 1:4 全负、BRCA 四格点全负（缺文本 −0.0674）、LGG 单模态缺失时 0:5 / 2:3 / 0:5；只有 UCEC 20/20 全胜、LUAD 小幅偏正（噪声带内）；两模态全缺时 LGG 5:0（+0.0535）。
- 消融（E0d）：dropout 协议本身 20 格点中 16 格在噪声带；UCEC 系统性正向（3 格超带），LGG 缺文本 −0.0504（1:4）。
- 跨骨架：单模态 100% 缺失 6 个比较有 3 个反号；gate 版 both_100 的均值盲补 M1 五癌全正、LGG/UCEC/LUAD 上不低于学习式召回 M2。
- 同底座判别（E0m，r5）：原型相对均值填的增量只在 UCEC 成立（四格点 5:0）；LGG 全缺收益由任何填充解释（E0m vs E0 +0.0700，E1 vs E0m +0.0055 带内）；BLCA/BRCA 原型相对均值填仍为负；均值填在缺文本时 BRCA −0.0312、LGG −0.0390 超带负。
- NPJ-D 底座线（r6，25 seed）：E1 相对 D 在完整模态 BRCA/LGG/UCEC 超带负；"原型有效"（E1 vs Dm 超带正）仅 BLCA 缺文本/全缺；UCEC 全缺收益由均值填即可达到且更高（Dm vs D +0.0719，E1 vs Dm −0.0314）；LGG 缺文本 E1 0:25 全败（−0.0997）；D 在 BLCA 有 3 个 seed 完整模态 <0.5（不剔除）。去 gate 改等权均值本身相对 NPJ-A 改善 4/5 癌完整模态。
- 全部判定为方向判定，无置信区间。

## 数字冲突 / 口径提示（并排列出，不裁决）

- `a_test_report.md` 抬头写 `r4_numbers.txt`"十五节"，文件实际为**十七节**（第 4 轮复核后追加了十六、十七节）。
- S5 表中 NPJ-A/NPJ-B 为同一 ckpt 两种读数；baseline 只有单一读数。`a_test_report.md` §三 的 MCAT/PORPOISE 中位与 `s5_report.md` 逐 seed 值同源（`s5_full_reference.csv`）。
- baseline test n（BRCA 347 / LUAD 167 / LGG 163 / UCEC 190）小于骨架（383 / 172 / 166 / 198），逐 seed 对比为近似口径而非严格配对（S5 注记 2）。
- E0d vs E0 BRCA s231 完整模态两臂 cindex 完全相同（0.6859316452821619）记平局；ckpt 路径不同、其余三格点不同（`r4_numbers.txt` 平局明细）。
- E0/E1 评测 JSON 的 `arm` 字段均写 `m0real`（评测入口复用），臂身份以 ckpt 路径为准。
""")

OUT.write_text("\n".join(blocks), encoding="utf-8")
print("WROTE", rel(OUT), len("\n".join(blocks).split("\n")), "lines")
