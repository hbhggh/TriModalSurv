#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""绝对数值表：D / Dm / E1 三臂 × 5 癌 × 4 格点 × 25 seed 的 test c-index 逐值（不含相对关系）。
用法：cd collab/20260906-NPJ-D消融 && python3 tools/abs_table.py > table_npjd_D_Dm_E1_absolute_25seed.md"""
import json, glob, os, re, statistics as st, pathlib, datetime
HERE = pathlib.Path(__file__).resolve().parents[1]; A = HERE.parent / "20260902-A测缺失补偿"
C5 = ["BLCA","BRCA","LUAD","LGG","UCEC"]; G4 = [("none","完整模态"),("rna_100","缺 RNA 100%"),("text_100","缺文本 100%"),("both_100","全缺 100%（RNA + 文本）")]
SEEDS = [123,132,213,231,321] + list(range(1,21))
PAT = re.compile(r"^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$")
def load(dirs):
    out = {}
    for d in dirs:
        for p in sorted(glob.glob(str(d / "*.json"))):
            m = PAT.match(os.path.basename(p))
            if not m: continue
            j = json.load(open(p, encoding="utf-8"))
            for g, v in j["grids"].items():
                for met in ("cindex_A","cindex_B"):
                    k = (met, m["cancer"], int(m["seed"]), g)
                    if k in out and out[k] != v[met]: raise SystemExit(f"CONFLICT {k} {p}")
                    out[k] = v[met]
    return out
ARMS = [("D", "NPJ-D：NPJ-A 去 GatedFusion，等权均值融合；其余全同（无跨 token attention、无模态嵌入、无 modality dropout、无一致性 loss；缺失 = 零特征→常量 token 照常参与平均）", load([HERE/"results_npjd_d0"])),
        ("Dm", "同一 D ckpt，评测期把缺失模态特征替换为训练集逐元素均值（零训练）", load([HERE/"results_npjd_dm"])),
        ("E1", "NPJ-C + CAP-Recall 原型召回（modality dropout 0.15、一致性 loss λ=0.1）；原 5 seed + 补训 seed 1–20", load([A/"results_npjc/e1", A/"results_npjc_both/e1", HERE/"results_npjc_e1_25"]))]
for name, _, X in ARMS:
    miss = [(c,s,g) for c in C5 for s in SEEDS for g,_ in G4 if ("cindex_B",c,s,g) not in X]
    if miss: raise SystemExit(f"MISSING {name}: {miss[:5]}")
print(f"# NPJ-D 线三臂绝对数值表（test c-index；5 癌 × 4 格点 × 25 seed；生成 {datetime.date.today().isoformat()}）\n")
print("本表只列绝对数值，不含任何相对 D 的胜负或差值。数值为冻结 test 集上的 c-index（每癌种单独训练与评测；test 集 n：BLCA 138、BRCA 383、LUAD 172、LGG 166、UCEC 198）。缺失格点按固定 manifest（SHA c789eae9…）对 test 集施加 100% 遮挡；训练期不施加 manifest。B 口径 = sigmoid 修正读数（报告主口径）；A 口径 = 作者 raw logits 读数（训练与 ckpt 选择用它），见附录。\n")
print("| 臂 | 定义 | 结果目录 |\n|---|---|---|")
for name, desc, _ in ARMS:
    d = {"D": "`results_npjd_d0/`（125 JSON）", "Dm": "`results_npjd_dm/`（125 JSON）", "E1": "`../20260902-A测缺失补偿/results_npjc{,_both}/e1/`（原 5 seed）+ `results_npjc_e1_25/`（seed 1–20）"}[name]
    print(f"| {name} | {desc} | {d} |")
print("\nseed 顺序：s123、s132、s213、s231、s321（S5 原有）→ s1…s20（本轮新增）。每行末尾给出该臂 25 个 seed 的中位 / 最小 / 最大（绝对量汇总，非相对关系）。\n")
def block(met, title):
    print(f"\n{title}\n")
    for g, gl in G4:
        print(f"### 格点 {g}（{gl}）\n")
        print("| 癌种 | 臂 | " + " | ".join(f"s{s}" for s in SEEDS) + " | 中位 | 最小 | 最大 |")
        print("|---|---|" + "---|" * (len(SEEDS) + 3))
        for c in C5:
            for name, _, X in ARMS:
                v = [X[(met, c, s, g)] for s in SEEDS]
                print(f"| {c} | {name} | " + " | ".join(f"{x:.4f}" for x in v) + f" | {st.median(v):.4f} | {min(v):.4f} | {max(v):.4f} |")
        print()
block("cindex_B", "## 一、B 口径（sigmoid 修正；主口径）")
block("cindex_A", "## 附录、A 口径（作者 raw logits）")
print("\n来源：`tools/abs_table.py` 直接读取评测 JSON 生成；与 `r6_numbers.txt`「各臂中位」节及 `table_npjd_D_Dm_E1_*_{A,B}.md` 的逐值一致。")
