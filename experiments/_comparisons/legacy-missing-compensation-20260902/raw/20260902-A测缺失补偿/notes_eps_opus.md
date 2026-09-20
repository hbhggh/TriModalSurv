# 单 ε · A/B 首单执行档案（engine = opus）

契约：`plan.md` §「单 ε · A/B 首单契约」（第 151 行起）。所有 `<engine>` = `opus`。

## ① 环境（2026-09-04 10:12:08 JST）

```
$ date '+%Y-%m-%d %H:%M:%S %Z'
2026-09-04 10:10:41 JST
$ python3 --version
Python 3.9.6
$ python3 -c "import matplotlib,numpy,pandas;print(...)"
matplotlib 3.5.1
numpy 1.22.3
pandas 1.4.2
$ shasum -a 256 tools_opus/summarize_arms.py
99f20a614be891071172ed41db0e31fcae57dd3cd45bdfbd5150cbccd2bbfc07  tools_opus/summarize_arms.py
```

起点脚本 sha256 与契约 ε1 钉死值 `99f20a614be891071172ed41db0e31fcae57dd3cd45bdfbd5150cbccd2bbfc07` **一致**（改前自校验通过）。

### 只读文件 sha256 自查（改前基线，交付前会复查一次）

```
$ shasum -a 256 table_npjc_E0_E1.md table_gate_4arms.md table_npjc_E0_vs_S5.md a_test_report.md result.md r2_numbers.txt s5_full_reference.csv missing_manifest_v1.csv
52c6f36e41e00f4759e5bc6b5a7e031427b40980e2c41b9ac8270974212ab4bc  table_npjc_E0_E1.md
9c11ef9e3bcb7c6141008377bfba0f2a741770b6ce7b657d3444dadd9898f30f  table_gate_4arms.md
a6668233d04c00409c54d9ad8ebccffb5e3385cfbee3a23ab3bd3d3c1598c1c2  table_npjc_E0_vs_S5.md
3eeaba9fb45d59e49d56e4db95aa2a1888483bf666f82726ccecb3974188b622  a_test_report.md
5abd55371cb3d30416e24bd50ea82c3dcb20fc0b7b25bd712746474b43b7dd16  result.md
01a50796556d915efd319386f67a6a4ec870e339024bfd6623489c6b7e89874b  r2_numbers.txt
49045d39cf4ca7915861815370209857fe0bcf06dde9d3ae81288e40796b9436  s5_full_reference.csv
c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156  missing_manifest_v1.csv
```

逐条与契约 ε1 列表比对：8/8 **一致**。

### 输入盘点

| 目录 | 可解析 json 数 | 不匹配文件名正则者 |
|---|---|---|
| results_npjc/e0 | 25 | — |
| results_npjc/e1 | 25 | — |
| results_npjc_both/e0 | 25 | — |
| results_npjc_both/e1 | 25 | — |
| results_npjc_e0d | 25 | `runs_state_snapshot.json`（将打 SKIP 跳过） |
| results_gate/m0real | 25 | — |
| results_gate/m1 | 25 | — |
| results_gate/m1b | 25 | — |
| results_gate/m2 | 25 | — |

`results_npjc_e0d` 目录存在 → 图 2 与 E0d 表均按三臂出。

## ② 验收命令与原样 stdout · 第一批 summarize_arms（2026-09-04 10:16:42 JST）

```
$ export PYTHONDONTWRITEBYTECODE=1
$ shasum -a 256 tools_opus/summarize_arms.py            # 起步自校验（改前）
99f20a614be891071172ed41db0e31fcae57dd3cd45bdfbd5150cbccd2bbfc07  tools_opus/summarize_arms.py

$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0 --arm E1=results_npjc/e1 --legacy-winloss | diff - <(cat table_npjc_E0_E1.md; echo) && echo REPLAY_OK
REPLAY_OK

$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --grids none,rna_100,text_100,both_100 --out table_npjc_E0_E1_4grids_opus.md --pairwise-grid both_100 --pairwise-out table_both100_E1_vs_E0_opus.md > /dev/null && echo TABLE4_OK
TABLE4_OK

$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --arm E0d=results_npjc_e0d --grids none,rna_100,text_100,both_100 --out table_npjc_E0_E1_E0d_4grids_opus.md > /dev/null && echo TABLE_E0D_OK
SKIP results_npjc_e0d/runs_state_snapshot.json
TABLE_E0D_OK
（`SKIP` 行走 stderr，未污染 stdout；见 ④ 歧义 A1）

$ python3 tools_opus/summarize_arms.py --arm m0real=results_gate/m0real --arm m1=results_gate/m1 --arm m1b=results_gate/m1b --arm m2=results_gate/m2 --grids none,rna_100 | grep -c ":[1-9] (Δ中位"
1
（期望 ≥1，实得 1 → 平局逻辑有正样本）

$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0,results_npjc/e0 --arm E1=results_npjc/e1 > /dev/null 2>&1; echo "CONFLICT_EXIT=$?"
CONFLICT_EXIT=2
（stderr 首行：`CONFLICT arm=E0 cancer=BLCA seed=123 grid=none dir1=results_npjc/e0 dir2=results_npjc/e0`）

$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/nonexistent --arm E1=results_npjc/e1 > /dev/null 2>&1; echo "MISSING_EXIT=$?"
MISSING_EXIT=3
（stderr：`ERROR: no result json in results_npjc/nonexistent`）
```

### CKPT_MISMATCH 通道自测（契约无对应验收命令，自补）

用临时目录复制 `results_npjc_both/e0/e0_BLCA_s123.json` 并改 `checkpoint` 为 `/fake/other.pth`，与 `results_npjc/e0` 合并：

```
exit= 2
CKPT_MISMATCH arm=E0 cancer=BLCA seed=123 dir1=results_npjc/e0 dir2=<tmp> ckpt1=/home/wuhao/NPJ/out/123/tcga_uni2_img_1536text_768rna_256_NPJC_BLCA_surv.pth ckpt2=/fake/other.pth
```

临时夹具写在会话 scratchpad（仓库外）并当场 `rmtree` 删除，仓库内无落盘（见 ④ 歧义 A6）。

### 逐格断言（4grids 表 vs 留档表，内联不落盘）

```
SECTION none: OK (10 rows)
SECTION rna_100: OK (10 rows)
SECTION text_100: OK (10 rows)
ALL SECTIONS OK
```

### 缺格计数

```
$ grep -c "^缺格：0$" table_npjc_E0_E1_4grids_opus.md table_npjc_E0_E1_E0d_4grids_opus.md
table_npjc_E0_E1_4grids_opus.md:1
table_npjc_E0_E1_E0d_4grids_opus.md:1
```

### 三份表字节属性

| 文件 | 字节 | 末尾换行 | CRLF | BOM |
|---|---|---|---|---|
| table_npjc_E0_E1_4grids_opus.md | 3933 | 无 | 无 | 无 |
| table_npjc_E0_E1_E0d_4grids_opus.md | 5849 | 无 | 无 | 无 |
| table_both100_E1_vs_E0_opus.md | 484 | 无 | 无 | 无 |

**返工 1 次**：配对表首版末尾多一个换行（每臂块尾部空行 + `"\n".join` 所致），与 ε3.4「文件无末尾换行」冲突；改为落盘前弹出末尾空行元素，臂块之间的空行保留（见 ④ 歧义 A2）。

## ② 验收命令与原样 stdout · 第二批 figures + 收尾（2026-09-04 10:24:38 JST）

以下为 ε5 全部 14 条命令的**最终一次**连续实跑（脚本已定稿，`<engine>`=opus）。原样 stdout：

```
$ export PYTHONDONTWRITEBYTECODE=1

### 1
$ shasum -a 256 tools_opus/summarize_arms.py
25829408f508aa14e6cb8f552a815e7718215c4e93fb5b99105d31a2f557171a  tools_opus/summarize_arms.py
（改后指纹；改前 = 契约钉死值 99f20a61…，见 ①）

### 2
$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0 --arm E1=results_npjc/e1 --legacy-winloss | diff - <(cat table_npjc_E0_E1.md; echo) && echo REPLAY_OK
REPLAY_OK

### 3
$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --grids none,rna_100,text_100,both_100 --out table_npjc_E0_E1_4grids_opus.md --pairwise-grid both_100 --pairwise-out table_both100_E1_vs_E0_opus.md > /dev/null && echo TABLE4_OK
TABLE4_OK

### 4
$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --arm E0d=results_npjc_e0d --grids none,rna_100,text_100,both_100 --out table_npjc_E0_E1_E0d_4grids_opus.md > /dev/null && echo TABLE_E0D_OK
SKIP results_npjc_e0d/runs_state_snapshot.json
TABLE_E0D_OK

### 5
$ python3 tools_opus/summarize_arms.py --arm m0real=results_gate/m0real --arm m1=results_gate/m1 --arm m1b=results_gate/m1b --arm m2=results_gate/m2 --grids none,rna_100 | grep -c ":[1-9] (Δ中位"
1

### 6
$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/e0,results_npjc/e0 --arm E1=results_npjc/e1 > /dev/null 2>&1; echo "CONFLICT_EXIT=$?"
CONFLICT_EXIT=2

### 7
$ python3 tools_opus/summarize_arms.py --arm E0=results_npjc/nonexistent --arm E1=results_npjc/e1 > /dev/null 2>&1; echo "MISSING_EXIT=$?"
MISSING_EXIT=3

### 8
$ python3 tools_opus/plot_missing_curves.py --out figures_opus && A=$(shasum -a 256 figures_opus/*) && python3 tools_opus/plot_missing_curves.py --out figures_opus && B=$(shasum -a 256 figures_opus/*) && [ "$A" = "$B" ] && echo DETERMINISTIC_OK
SKIP /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/results_npjc_e0d/runs_state_snapshot.json
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/gate_missing_curves.png
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/gate_missing_curves.svg
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/npjc_e0_e1_4grids.png
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/npjc_e0_e1_4grids.svg
SKIP /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/results_npjc_e0d/runs_state_snapshot.json
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/gate_missing_curves.png
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/gate_missing_curves.svg
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/npjc_e0_e1_4grids.png
WROTE /Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/figures_opus/npjc_e0_e1_4grids.svg
DETERMINISTIC_OK

### 9
$ grep -l "dc:date" figures_opus/*.svg; echo "DATE_LEAK_FILES_ABOVE(expect none)"
DATE_LEAK_FILES_ABOVE(expect none)

### 10
$ for f in figures_opus/*.png; do python3 -c 'import sys,struct;d=open(sys.argv[1],"rb").read();w,h=struct.unpack(">II",d[16:24]);print(sys.argv[1],w,h,len(d));assert len(d)>=50000' "$f"; done
figures_opus/gate_missing_curves.png 2025 2400 730188
figures_opus/npjc_e0_e1_4grids.png 2400 600 122714

### 11
$ for f in figures_opus/*.svg; do python3 -c 'import sys,os;s=os.path.getsize(sys.argv[1]);print(sys.argv[1],s);assert s>=20000' "$f"; done
figures_opus/gate_missing_curves.svg 208054
figures_opus/npjc_e0_e1_4grids.svg 128620

### 12
$ python3 -c 'import sys;[compile(open(p,"rb").read(),p,"exec") for p in sys.argv[1:]];print("COMPILE_OK")' tools_opus/summarize_arms.py tools_opus/plot_missing_curves.py
COMPILE_OK

### 13
$ grep -c "^缺格：0$" table_npjc_E0_E1_4grids_opus.md table_npjc_E0_E1_E0d_4grids_opus.md
table_npjc_E0_E1_4grids_opus.md:1
table_npjc_E0_E1_E0d_4grids_opus.md:1

### 14
$ find . -name "__pycache__" -o -name "*.pyc" | wc -l
       0
```

### 逐格断言（最终一次；内联 python3 -c，不落盘）

```
SECTION none: OK (10 rows)
SECTION rna_100: OK (10 rows)
SECTION text_100: OK (10 rows)
ALL SECTIONS OK
```

### 平局逻辑正样本落点（命令 5 计数到的那一行）

```
| BLCA | m1 | 0.5985 | 0.6341 | 0.6183 | 0.6103 | 0.6251 | 0.6183 | 0:0:5 (Δ中位 +0.0000) |
```

格点 `none`（0% 遮挡）下 M1 的测试期均值盲补不生效，5 seeds 与 M0-real 逐值全等 → 新规则记 `0:0:5`；旧写法会记成 `0:5`（平局计负）。这正是本单胜负口径修正要拿到的行为差（对应坑 V23）。

### E0d 目录缺席分支实测（契约无对应验收命令，自补）

在会话 scratchpad（仓库外）搭一个只含 `results_gate/`、`results_npjc/`、`results_npjc_both/` 三个符号链接的临时 root，跑 `--root <tmp> --out <tmp>/figs`：

```
WROTE <TMP>/figs/gate_missing_curves.png
WROTE <TMP>/figs/gate_missing_curves.svg
SKIPPED: results_npjc_e0d missing
WROTE <TMP>/figs/npjc_e0_e1_4grids.png
WROTE <TMP>/figs/npjc_e0_e1_4grids.svg
```

产出的 2 臂版 SVG 全文不含 `E0d`（`mentions E0d: False`），即 suptitle / 图例 / 图注均未提 E0d，符合 ε4。临时目录用后逐文件删除，仓库内零落盘。

### 只读文件 sha256 交付前复查

```
52c6f36e41e00f4759e5bc6b5a7e031427b40980e2c41b9ac8270974212ab4bc  table_npjc_E0_E1.md
9c11ef9e3bcb7c6141008377bfba0f2a741770b6ce7b657d3444dadd9898f30f  table_gate_4arms.md
a6668233d04c00409c54d9ad8ebccffb5e3385cfbee3a23ab3bd3d3c1598c1c2  table_npjc_E0_vs_S5.md
3eeaba9fb45d59e49d56e4db95aa2a1888483bf666f82726ccecb3974188b622  a_test_report.md
5abd55371cb3d30416e24bd50ea82c3dcb20fc0b7b25bd712746474b43b7dd16  result.md
01a50796556d915efd319386f67a6a4ec870e339024bfd6623489c6b7e89874b  r2_numbers.txt
49045d39cf4ca7915861815370209857fe0bcf06dde9d3ae81288e40796b9436  s5_full_reference.csv
c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156  missing_manifest_v1.csv
99f20a614be891071172ed41db0e31fcae57dd3cd45bdfbd5150cbccd2bbfc07  tools/summarize_arms.py
```

契约钉死的 8 条全部**未变**；起点副本源 `tools/summarize_arms.py` 亦未变（仍为起点指纹）。

### 越界扫描（对指挥官 10:09 基线 baseline.sha256，495 个文件）

```
$ shasum -a 256 -c baseline.sha256 | grep -v ": OK$"
./notes.md: FAILED
./tools_codex/summarize_arms.py: FAILED
./tools_opus/summarize_arms.py: FAILED
```

三条失配中：`notes.md` 为指挥官侧、`tools_codex/summarize_arms.py` 为并行 codex 引擎侧，均非本单所写（本单全程未打开过这两个路径）；`tools_opus/summarize_arms.py` 是本单白名单内的正常增强。其余 492 个文件逐字节不变。

另用 `find . -newermt "2026-09-04 10:10:00"` 复核：白名单外新增/修改仅 `notes.md`、`notes_eps_codex.md`、`tools_codex/summarize_arms.py` 三个他方文件。`figures/`（`--out` 的契约默认目标）仍是空目录，本单从未写入。

## ③ 断言结果表（2026-09-04 10:25:08 JST）

| # | 断言 | 期望 | 实得 | 判定 |
|---|---|---|---|---|
| 1 | 起点脚本 sha256（改前） | 99f20a61…bfc07 | 一致 | OK |
| 2 | 旧写法字节重放 vs table_npjc_E0_E1.md | REPLAY_OK（diff 空） | REPLAY_OK | OK |
| 3 | 4 格点主表 + both_100 配对表生成 | TABLE4_OK | TABLE4_OK | OK |
| 4 | 加 E0d 的 4 格点表生成 | TABLE_E0D_OK | TABLE_E0D_OK | OK |
| 5 | gate 四臂平局单元格计数 | ≥1 | 1 | OK |
| 6 | 同一目录重复传入 → CONFLICT | exit 2 | CONFLICT_EXIT=2 | OK |
| 7 | 目录不存在 → ERROR | exit 3 | MISSING_EXIT=3 | OK |
| 8 | 出图连跑两次四文件字节一致 | DETERMINISTIC_OK | DETERMINISTIC_OK | OK |
| 9 | SVG 无 dc:date | 无命中文件 | 无命中文件 | OK |
| 10 | PNG 像素尺寸与体积 | 2025x2400 / 2400x600，≥50000B | 2025 2400 730188 / 2400 600 122714 | OK |
| 11 | SVG 体积 | ≥20000B | 208054 / 128620 | OK |
| 12 | 两脚本内存 compile | COMPILE_OK | COMPILE_OK | OK |
| 13 | 两张表各含一行 `缺格：0` | 各 1 | 各 1 | OK |
| 14 | 无 __pycache__ / *.pyc | 0 | 0 | OK |
| 15 | 逐格断言（none/rna_100/text_100 前 8 段逐字相等；对照臂末列两空格；非对照臂 W、L、Δ 相等且 T=0） | SECTION xxx: OK (10 rows) ×3 + ALL SECTIONS OK | 同左 | OK |
| 16 | 只读文件 8 条 sha256 交付前不变 | 全部一致 | 全部一致 | OK |
| 17 | CKPT_MISMATCH 通道（自补） | exit 2 + 消息 | exit 2 + `CKPT_MISMATCH arm=E0 …` | OK |
| 18 | E0d 目录缺席分支（自补） | 打 SKIPPED、2 臂图、图注不提 E0d | 同左 | OK |
| 19 | 越界扫描（495 文件基线） | 白名单外零改动 | 仅他方 3 文件失配，本单零越界 | OK |
| 20 | 三张表末尾无换行 / 无 CRLF / 无 BOM | 全满足 | 全满足 | OK |

FAIL：0 条。

### 产物清单（唯一可写范围内）

| 路径 | 说明 | 字节 |
|---|---|---|
| tools_opus/summarize_arms.py | 增强版汇总器（多目录合并、胜:负:平、配对表、退出码契约） | 9875 |
| tools_opus/plot_missing_curves.py | 新建出图脚本（图 1 gate 曲线、图 2 NPJ-C 四格点） | 6649 |
| figures_opus/gate_missing_curves.png | 图 1 位图 2025x2400 | 730188 |
| figures_opus/gate_missing_curves.svg | 图 1 矢量 | 208054 |
| figures_opus/npjc_e0_e1_4grids.png | 图 2 位图 2400x600 | 122714 |
| figures_opus/npjc_e0_e1_4grids.svg | 图 2 矢量 | 128620 |
| table_npjc_E0_E1_4grids_opus.md | E0/E1 × 4 格点主表 | 3933 |
| table_npjc_E0_E1_E0d_4grids_opus.md | E0/E1/E0d × 4 格点主表 | 5849 |
| table_both100_E1_vs_E0_opus.md | both_100 配对比较表 | 484 |
| notes_eps_opus.md | 本文件 | — |

## ④ 歧义与自行裁决（2026-09-04 10:25:58 JST）

契约未覆盖之处一律按"最保守/不破坏既有字节契约"取默认，逐条如下。

**A1 · `SKIP <path>` 走哪个流。** ε1 只说"打印"。裁决：**stderr**。理由：ε5 命令 2 用 stdout 做字节重放 diff，任何 SKIP 落 stdout 都可能击穿字节契约（`results_npjc_e0d/` 里就有一个 `runs_state_snapshot.json`）；且 ε3.1 的 `CONFLICT`/`ERROR` 明文走 stderr，同族保持一致。

**A2 · 配对表末尾的自相矛盾。** ε3.4 既规定每个臂块以"空行"结尾，又规定"文件无末尾换行"——最后一个臂块同时满足二者不可能。裁决：**以"文件无末尾换行"为硬约束**（与主表留档 `table_npjc_E0_E1.md` 的无末尾换行一致，也是可 diff 的那一条），落盘前弹出末尾空行元素；多个非对照臂时臂块之间的空行照常保留。此为返工 1。

**A3 · 配对表是否同时打 stdout。** 未定。裁决：**只写文件，不打 stdout**。ε3.3 的"stdout 打印全文"针对主表；把配对表混进 stdout 会污染主表字节流。

**A4 · 配对表 0 配对时的 Δ 单元格。** 契约只说中位缺值用 `—`。裁决：Δ 无定义时同样用 `—`。（本单实际 25/25 配对齐全，未触发。）

**A5 · `--pairwise-grid` 与 `--pairwise-out` 只给其一。** 未定。裁决：`ap.error(...)` 显式失败（argparse 标准退出码 2），不产半成品。与 ε3.1 的 CONFLICT 共用 2 号码，但属 argparse 惯例且无验收命令触发。

**A6 · CKPT_MISMATCH 无验收命令、消息字段未定。** 裁决：字段定为 `arm= cancer= seed= dir1= dir2= ckpt1= ckpt2=`，并自补一次合成用例证明通道确实会触发（临时夹具写会话 scratchpad，仓库外，用后删除；仓库内零落盘）。不实测就只有"代码看着对"，属坑 E1 那一类。

**A7 · 冲突时打第一条还是全部。** 契约措辞为单数。裁决：**打第一条即 exit**。`--arm E0=dir,dir` 会产生 75 条冲突，全打是噪音。

**A8 · `--arm` 目录的相对路径基准。** ε0 说脚本内部路径由 ROOT 推导，但目录来自命令行。裁决：**先按 cwd 解析，cwd 下不存在再回退 ROOT**。cwd == ROOT（本单全部命令都在战役目录下跑）时行为与旧脚本逐字不变，跨目录调用也不至于炸。

**A9 · 图 2 x 刻度标签字号。** ε4 未规定字号。默认 10pt 下刻度间距实测 97 px，`text_100` 与 `both_100` 两标签首尾相接（已裁图确认粘连）。裁决：按 ε4"布局参数允许微调、元素集合固定"，把 x 刻度标签缩到 **8pt**；figsize/dpi/像素尺寸/元素集合/文本内容全部不变。此为返工 2。

**A10 · `fig.legend(...)` 未给 handles。** 契约给的是裸调用；裸调用会从全部子图收集带 label 的 artist——图 1 会收成 4×15=60 条。裁决：**只在第 (0,0) 个子图（图 2 为第 1 个子图）给 `label=`**，其余不给，于是裸调用 `fig.legend(loc=..., ncol=..., frameon=False)` 恰好收到 4 条（图 1）/ 3 条（图 2），调用形式与契约逐字一致，图例条目也正确。图 2 每臂每子图合并成一次 `scatter`（4 刻度 × 5 seeds 一把画），保证一臂只产生一个图例 handle。

**A11 · `--out` 默认值指向白名单外。** ε4 规定默认 `<root>/figures`，而 `figures/` 不在本单白名单内。裁决：**保留契约规定的默认值**（改默认属于违背契约），但本单所有运行一律显式 `--out figures_opus`；交付前核实 `figures/` 仍为空目录。

**A12 · 防 `.pyc` 落盘。** ε5 要求 `__pycache__`/`*.pyc` 计数为 0，而 `plot_missing_curves.py` 要 import 同目录的 `summarize_arms`（会在 `tools_opus/` 旁生成 `__pycache__`）。裁决：脚本内显式 `sys.dont_write_bytecode = True` 再 import，不依赖调用方 `export PYTHONDONTWRITEBYTECODE=1`（坑 S1）。因 ε4 钉死前三行必须是 matplotlib 三行，该语句放在第 4 行 `import matplotlib.pyplot as plt` 之后、其余 import 之前。全程未用 `py_compile`，语法检查一律走内存 `compile()`。

**A13 · 图 1 x 轴刻度位置。** 契约给了数据点 `[0,25,50,75,100]` 但未说刻度。裁决：`ax.set_xticks([0,25,50,75,100])`，让刻度与数据点对齐（matplotlib 默认会给 0/20/40/… 与数据点错位）。

**A14 · `results_npjc_e0d/runs_state_snapshot.json`。** 不匹配 ε1 文件名正则。裁决：按契约打 `SKIP` 跳过，不计入任何臂的数据；E0d 仍是齐整的 25 个 (癌种, seed)。

**A15 · 加载器复用。** ε4 允许"import 同目录 summarize_arms 的加载函数或自行复制"。裁决：**import 复用**，使两条产物线（表 / 图）共用同一套目录合并、冲突检测与取值逻辑，杜绝表图口径漂移。

## ⑤ 耗时与迭代次数（2026-09-04 10:26:35 JST）

- 起始 `2026-09-04 10:10:41 JST`（① 的实取时刻），收尾见本节标题时刻，全程约 25 分钟，单人单线程，无转派、无 SSH、无联网、无 pip。
- **返工 2 次**，均在交付前自查阶段发现，非验收命令失败：
  1. 配对表末尾多一个换行（见 A2）；
  2. 图 2 x 刻度标签在默认字号下粘连（见 A9）。
- 另有 1 次 shell 层失误（未计入返工，无产物影响）：向 notes 追加时用了**未加引号**的 heredoc 定界符，正文里的裸 ``` 触发命令替换，`(eval): parse error`，该次追加整体未执行（文件停在 121 行未被写脏）。改用 `<<'NOTESEOF'` 引号定界符后正常。
- 验收命令全部一次通过（无 FAIL 重跑）；出图脚本共跑 6 次（1 次首出 + 1 次字号修正 + 2 次确定性对拍 + 2 次最终 ε5 连跑）。

### Bug Post-Mortem 1

- **现象**：配对表 `table_both100_E1_vs_E0_opus.md` 首版 485 字节、末尾带换行，与 ε3.4「文件无末尾换行」不符。
- **根因**：按契约逐条把"每臂块尾随空行"实现成 `lines.append("")`，再 `"\n".join(lines)` —— 末尾那个空串元素等价于一个末尾换行。契约的"臂块尾空行"与"文件无末尾换行"在最后一个臂块上互斥，实现时只落实了前者。
- **修复**：join 之前 `while lines and lines[-1] == "": lines.pop()`；臂块之间的分隔空行不受影响。
- **Prevention Rule**：格式契约里"块级尾随空行"与"文件无末尾换行"同时出现时，以文件级约束为准，序列化前统一裁掉尾部空元素；落盘后必须用 `open(...,'rb').read().endswith(b'\n')` 实测，不靠肉眼看 Markdown。

### Bug Post-Mortem 2

- **现象**：图 2（1×5 子图、figsize 16×4）x 轴四个分类标签中 `text_100` 与 `both_100` 首尾相接、`rna_100` 首字被邻标签挤掉，缩略图上读成 `ma_100`。
- **根因**：只按契约核对了 figsize/dpi/像素尺寸与元素集合，没有核对可读性；默认 10pt 下单个标签约 83 px，而刻度间距实测仅 97 px，余量不足。
- **修复**：`ax.tick_params(axis="x", labelsize=8)`（属 ε4 允许的布局微调，元素集合与文本内容不变）；裁图复检确认标签之间恢复明显间隙。
- **Prevention Rule**：图形类交付除尺寸/哈希类机器断言外，必须至少对拥挤区域（刻度标签、图例、图注）做一次像素级裁图目视复检；把"刻度间距 px vs 标签估算宽度 px"当作可算的硬指标，而不是等出图后凭感觉。

### 交给指挥官的复核抓手

1. `shasum -a 256 -c baseline.sha256 | grep -v ": OK$"` —— 本单只应让 `./tools_opus/summarize_arms.py` 一条失配（另两条属他方）。
2. 命令 2（REPLAY_OK）证明旧口径字节级可重放；§② 的逐格断言证明新表在 none/rna_100/text_100 三节上与留档表**前 8 段逐字相同**，差异被严格限制在末列胜负单元格。
3. 结论侧数字请一律指回 `table_npjc_E0_E1_4grids_opus.md` / `table_npjc_E0_E1_E0d_4grids_opus.md` / `table_both100_E1_vs_E0_opus.md` 三份脚本生成物的具体行，不要手算（坑 V23）。
4. 平局规则已在配对表首行显式声明（`|Δ|≤1e-06 记平`），主表末列由 `胜:负` 升级为 `胜:负:平`。
5. 图 2 的 x 刻度标签在缩略图上易被读成 `ma_100`——这是 `rn` 连排在小字号下形似 `m` 的排版错觉，非渲染缺陷。SVG 源里 5 个子图的标签注释均为 `rna_100`（`grep -c 'rna_100' figures_opus/npjc_e0_e1_4grids.svg` = 5），请勿据缩略图报缺陷。

EPS_DONE
