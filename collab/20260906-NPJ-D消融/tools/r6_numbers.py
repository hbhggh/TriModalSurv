#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r6 对账（NPJ-D 底座，25 seed）：E1 vs D（系统级对比）、E1 vs Dm（原型 vs 均值填）、Dm vs D（填充 vs 常量 token）、D vs S5 NPJ（5 seed 交集）、E0(C) vs D（5 seed 交集）。
预注册规则：逐癌配对（同 seed），4 格点分报，胜:负:平 + 配对Δ中位，|Δ中位|<0.02 噪声带，A/B 双读数，不做跨癌投票。
用法：cd collab/20260906-NPJ-D消融 && python3 tools/r6_numbers.py > r6_numbers.txt"""
import json, glob, os, re, csv, statistics as st, pathlib
HERE=pathlib.Path(__file__).resolve().parents[1]; A=HERE.parent/"20260902-A测缺失补偿"; S5=HERE.parent/"20260827-三方对比战役"
C5=["BLCA","BRCA","LUAD","LGG","UCEC"]; EPS=1e-6; G4=["none","rna_100","text_100","both_100"]
SEEDS25=[123,132,213,231,321]+list(range(1,21)); SEEDS5=[123,132,213,231,321]
PAT=re.compile(r"^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$")
def load(dirs, metric):
    out={}
    for d in dirs:
        for p in sorted(glob.glob(str(d/"*.json"))):
            m=PAT.match(os.path.basename(p))
            if not m: continue
            for g,v in json.load(open(p,encoding="utf-8"))["grids"].items():
                k=(m["cancer"],int(m["seed"]),g)
                if k in out and abs(out[k]-v[metric])>0: raise SystemExit(f"CONFLICT {k} {p}")
                out[k]=v[metric]
    return out
def seeds_of(D,c,g): return sorted({s for (cc,s,gg) in D if cc==c and gg==g})
def cmp(x,y,c,g):
    ss=[s for s in seeds_of(x,c,g) if (c,s,g) in y]
    d=[x[(c,s,g)]-y[(c,s,g)] for s in ss]
    if not d: return "—"
    w=sum(v>EPS for v in d); l=sum(v<-EPS for v in d); t=sum(abs(v)<=EPS for v in d); md=st.median(d)
    band="超带正" if md>=0.02 else ("超带负" if md<=-0.02 else "带内")
    return f"{w}:{l}:{t}({md:+.4f},{band},n={len(d)})"
for metric in ("cindex_B","cindex_A"):
    D=load([HERE/"results_npjd_d0"],metric); Dm=load([HERE/"results_npjd_dm"],metric)
    E1=load([A/"results_npjc/e1",A/"results_npjc_both/e1",HERE/"results_npjc_e1_25"],metric)
    E0=load([A/"results_npjc/e0",A/"results_npjc_both/e0"],metric)
    s5={}
    col="cindex_B" if metric=="cindex_B" else "cindex_A"
    for r in csv.DictReader(open(A/"s5_full_reference.csv")):  # 指挥官小修 2026-09-07：该 csv 实际位于 A 测目录
        if r["method"]=="NPJ": s5[(r["cancer"],int(r["seed"]),"none")]=float(r[col])
    print(f"### [{metric}] 覆盖：D {len({k[:2] for k in D})}/125  Dm {len({k[:2] for k in Dm})}/125  E1 {len({k[:2] for k in E1})}/125（含原 5 seed）  E0 {len({k[:2] for k in E0})}/25")
    for name,(x,y) in {"E1_vs_D（系统级对比，25 seed）":(E1,D),"E1_vs_Dm（原型 vs 均值填，预注册护栏）":(E1,Dm),"Dm_vs_D（均值填 vs 常量 token）":(Dm,D),"E0(C)_vs_D（attention 效应，5 seed 交集）":(E0,D)}.items():
        print(f"### [{metric}] {name}")
        for g in G4: print(f"  [{g}] "+"  ".join(f"{c}={cmp(x,y,c,g)}" for c in C5))
    print(f"### [{metric}] D_vs_S5-NPJ（去 gate、无 attention；完整模态；5 seed 交集）")
    print("  [none] "+"  ".join(f"{c}={cmp(D,s5,c,'none')}" for c in C5))
    print(f"### [{metric}] 各臂中位（D/Dm/E1 用各自全部 seed）")
    for name,X in {"D":D,"Dm":Dm,"E1":E1,"E0":E0}.items():
        for g in G4:
            print(f"  {name} [{g}] "+"  ".join(f"{c}={st.median([X[(c,s,g)] for s in seeds_of(X,c,g)]):.4f}(n={len(seeds_of(X,c,g))})" if seeds_of(X,c,g) else f"{c}=—" for c in C5))
    print(f"### [{metric}] 自检：Dm none 与 D none 最大|Δ|（BLCA 无自然缺失应为 0；其余癌非零属预期）")
    for c in C5:
        ss=[s for s in seeds_of(D,c,"none") if (c,s,"none") in Dm]
        print(f"  {c}: {max(abs(Dm[(c,s,'none')]-D[(c,s,'none')]) for s in ss) if ss else float('nan'):.2e} (n={len(ss)})")
    print(f"### [{metric}] 异常 seed（偏离同臂同癌其余 seed 中位 > 0.08）")
    for name,X in {"D":D,"E1":E1}.items():
        for c in C5:
            for g in G4:
                ss=seeds_of(X,c,g)
                for s in ss:
                    o=[X[(c,t,g)] for t in ss if t!=s]
                    if o and abs(X[(c,s,g)]-st.median(o))>0.08: print(f"  {name} {c} s{s} {g}: {X[(c,s,g)]:.4f} 偏离 {X[(c,s,g)]-st.median(o):+.4f}")
