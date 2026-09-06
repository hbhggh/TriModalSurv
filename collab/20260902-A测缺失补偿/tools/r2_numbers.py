#!/usr/bin/env python3
"""r2 对账脚本（从会话记录逐字恢复，2026-09-04）。在战役目录下运行：python3 tools/r2_numbers.py | tee r2_numbers.txt
原始执行方式：cd 战役目录 && python3 - <<EOF | tee r2_numbers.txt。数字来源见 a_test_report.md r2/r3。"""
import csv, json, glob, os, statistics as st
C5 = ["BLCA","BRCA","LUAD","LGG","UCEC"]; S = [123,132,213,231,321]
def g(p):
    d = json.load(open(p)); x = d.get("grids", d); rows = x if isinstance(x, list) else [dict(v, grid=k) for k, v in x.items()]
    return {r["grid"]: r for r in rows}
def load(arm):
    out = {}
    for p in glob.glob(f"results_npjc/{arm}/*.json"):
        n = os.path.basename(p)[:-5]; c = n.split("_")[1]; s = int(n.rsplit("_s",1)[1]); out[(c,s)] = g(p)
    return out
E0, E1 = load("e0"), load("e1")
s5 = {"NPJ_B":{}, "NPJ_A":{}, "MCAT":{}, "PORPOISE":{}}
for r in csv.DictReader(open("s5_full_reference.csv")):
    k = (r["cancer"], int(r["seed"]))
    if r["method"] == "NPJ": s5["NPJ_B"][k] = float(r["cindex_B"]); s5["NPJ_A"][k] = float(r["cindex_A"])
    else: s5[r["method"]][k] = float(r["cindex_A"])
def wl(a, b, eps=1e-6):
    d = [a[s]-b[s] for s in S]; return f"{sum(x>eps for x in d)}:{sum(x<-eps for x in d)}:{sum(abs(x)<=eps for x in d)}", st.median(d)
def med(v): return st.median([v[s] for s in S])
print("### 一、E0 vs S5 NPJ-B（完整模态 B）：胜:负:平 | 配对Δ中位 | 各臂中位 S5→E0（中位差）")
tot_w = tot_l = tot_t = 0; lines = ["| 癌种 | E0 vs S5 胜:负:平 | 配对Δ中位 | S5 中位 → E0 中位（中位差） |", "|---|---|---|---|"]
for c in C5:
    e0 = {s: E0[(c,s)]["none"]["cindex_B"] for s in S}; sb = {s: s5["NPJ_B"][(c,s)] for s in S}
    r, dm = wl(e0, sb); w,l,t = map(int, r.split(":")); tot_w+=w; tot_l+=l; tot_t+=t
    line = f"| {c} | {r} | {dm:+.4f} | {med(sb):.4f} → {med(e0):.4f} ({med(e0)-med(sb):+.4f}) |"; print(line); lines.append(line)
print(f"合计 胜:负:平 = {tot_w}:{tot_l}:{tot_t} / 25")
open("table_npjc_E0_vs_S5.md","w").write("# E0（NPJ-C）vs S5 NPJ-B 完整模态（B 口径，逐 seed 严格 >，|Δ|≤1e-6 记平）\n\n" + "\n".join(lines) + f"\n\n合计 胜:负:平 = {tot_w}:{tot_l}:{tot_t} / 25\n")
print("\n### 二、E1 vs E0 三格点：胜:负:平 | 配对Δ中位")
for grid in ["none","rna_100","text_100"]:
    print(f"[{grid}] " + "  ".join(f"{c}={wl({s:E1[(c,s)][grid]['cindex_B'] for s in S},{s:E0[(c,s)][grid]['cindex_B'] for s in S})[0]}({wl({s:E1[(c,s)][grid]['cindex_B'] for s in S},{s:E0[(c,s)][grid]['cindex_B'] for s in S})[1]:+.4f})" for c in C5))
print("\n### 三、vs 三方（完整模态；骨架 B 口径，baseline sksurv 口径）：中位 & 逐 seed 胜:负:平")
print("| 癌种 | MCAT中位 | PORP中位 | S5-B中位 | E0中位 | E1中位 | E0 vs MCAT | E0 vs PORP | E1 vs MCAT | E1 vs PORP | test n 骨架/baseline |")
ntest = {"BLCA":(138,138),"BRCA":(383,347),"LUAD":(172,167),"LGG":(166,163),"UCEC":(198,190)}
for c in C5:
    e0 = {s: E0[(c,s)]["none"]["cindex_B"] for s in S}; e1 = {s: E1[(c,s)]["none"]["cindex_B"] for s in S}
    m = {s: s5["MCAT"][(c,s)] for s in S}; p = {s: s5["PORPOISE"][(c,s)] for s in S}; sb = {s: s5["NPJ_B"][(c,s)] for s in S}
    print(f"| {c} | {med(m):.4f} | {med(p):.4f} | {med(sb):.4f} | {med(e0):.4f} | {med(e1):.4f} | {wl(e0,m)[0]} | {wl(e0,p)[0]} | {wl(e1,m)[0]} | {wl(e1,p)[0]} | {ntest[c][0]}/{ntest[c][1]} |")
print("\n### 四、A 口径行（完整模态中位）")
for arm, D in [("E0", E0), ("E1", E1)]:
    print(f"{arm}_A: " + "  ".join(f"{c}={st.median([D[(c,s)]['none']['cindex_A'] for s in S]):.4f}" for c in C5) + " | S5_NPJ_A: " + "  ".join(f"{c}={med({s:s5['NPJ_A'][(c,s)] for s in S}):.4f}" for c in C5) if arm=="E0" else f"{arm}_A: " + "  ".join(f"{c}={st.median([D[(c,s)]['none']['cindex_A'] for s in S]):.4f}" for c in C5))
print("LGG A口径: E0_A中位 vs MCAT中位:", f"{st.median([E0[('LGG',s)]['none']['cindex_A'] for s in S]):.4f} vs {med({s:s5['MCAT'][('LGG',s)] for s in S}):.4f}")
print("\n### 五、UCEC 5-seed 极差（完整模态 B）")
for name, v in [("S5 NPJ-B", {s:s5["NPJ_B"][("UCEC",s)] for s in S}), ("E0", {s:E0[("UCEC",s)]["none"]["cindex_B"] for s in S}), ("E1", {s:E1[("UCEC",s)]["none"]["cindex_B"] for s in S})]:
    vals = [v[s] for s in S]; print(f"{name}: range={max(vals)-min(vals):.4f} (max {max(vals):.4f} min {min(vals):.4f})")
print("\n### 六、异常 seed 扫描（偏离同臂同癌其余 4 seed 中位 > 0.08）")
for arm, D in [("E0",E0),("E1",E1)]:
    for c in C5:
        for grid in ["none","rna_100","text_100"]:
            for s in S:
                others = [D[(c,o)][grid]["cindex_B"] for o in S if o != s]; dev = D[(c,s)][grid]["cindex_B"] - st.median(others)
                if abs(dev) > 0.08: print(f"  {arm} {c} s{s} {grid}: {D[(c,s)][grid]['cindex_B']:.4f} 偏离 {dev:+.4f}")
print("\n### 七、E1 BRCA 剔除 s123 后 vs E0 配对Δ中位（敏感性）")
for grid in ["none","rna_100","text_100"]:
    d = [E1[("BRCA",s)][grid]["cindex_B"] - E0[("BRCA",s)][grid]["cindex_B"] for s in S if s != 123]
    print(f"  {grid}: 4-seed Δ中位 {st.median(d):+.4f}, 负数个数 {sum(x<0 for x in d)}/4")
print("\n### 八、E0 遮单模态反升（B 中位）")
for c in C5:
    print(f"  {c}: none {med({s:E0[(c,s)]['none']['cindex_B'] for s in S}):.4f}  rna_100 {med({s:E0[(c,s)]['rna_100']['cindex_B'] for s in S}):.4f}  text_100 {med({s:E0[(c,s)]['text_100']['cindex_B'] for s in S}):.4f}")
