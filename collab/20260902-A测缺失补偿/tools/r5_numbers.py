#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r5 对账：E0m（E0 ckpt + 评测期均值盲补，NPJC 上）加入后的同底座判别。预注册规则（2026-09-06 用户裁决）：
逐癌配对、同底座 E1 vs E0m；both_100 与单模态缺失分开报；每癌 胜:负:平 + 配对Δ中位；|Δ中位|<0.02 为噪声带；不设跨癌合计阈值。
用法：cd 战役目录 && python3 tools/r5_numbers.py > r5_numbers.txt"""
import json, glob, os, re, statistics as st
C5=["BLCA","BRCA","LUAD","LGG","UCEC"]; S=[123,132,213,231,321]; EPS=1e-6; G4=["none","rna_100","text_100","both_100"]
PAT=re.compile(r"^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$")
def load(dirs, metric="cindex_B"):
    out={}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d,"*.json"))):
            m=PAT.match(os.path.basename(p))
            if not m: continue
            for g,v in json.load(open(p,encoding="utf-8"))["grids"].items(): out[(m["cancer"],int(m["seed"]),g)]=v[metric]
    return out
def V(D,c,s,g): return D[(c,s,g)]
def cmp(x,y,g,c):
    d=[V(x,c,s,g)-V(y,c,s,g) for s in S]; w=sum(v>EPS for v in d); l=sum(v<-EPS for v in d); t=sum(abs(v)<=EPS for v in d); md=st.median(d)
    band="超带正" if md>=0.02 else ("超带负" if md<=-0.02 else "带内")
    return w,l,t,md,band
for metric in ("cindex_B","cindex_A"):
    E0=load(["results_npjc/e0","results_npjc_both/e0"],metric); E1=load(["results_npjc/e1","results_npjc_both/e1"],metric)
    E0d=load(["results_npjc_e0d"],metric); E0m=load(["results_npjc_e0m"],metric)
    n_e0m=len({k[:2] for k in E0m}); print(f"### [{metric}] E0m 覆盖 (cancer,seed) = {n_e0m}/25；格点 = {sorted({k[2] for k in E0m})}")
    if n_e0m<25: print("  E0m 不完整，跳过该口径"); continue
    for name,(x,y) in {"E0m_vs_E0（均值填 vs 不填充）":(E0m,E0),"E1_vs_E0m（原型 vs 均值填，同底座；预注册主判定）":(E1,E0m),"E1_vs_E0（参考）":(E1,E0),"E0m_vs_E0d（均值填 vs 仅 dropout）":(E0m,E0d)}.items():
        print(f"### [{metric}] {name}")
        for g in G4:
            row=[]; 
            for c in C5:
                w,l,t,md,band=cmp(x,y,g,c); row.append(f"{c}={w}:{l}:{t}({md:+.4f},{band})")
            print(f"  [{g}] "+"  ".join(row))
        tot=[sum(cmp(x,y,'both_100',c)[i] for c in C5) for i in range(3)]; print(f"  both_100 合计 {tot[0]}:{tot[1]}:{tot[2]} / 25（仅供参考，不作判定）")
    print(f"### [{metric}] 各臂中位")
    for name,D in {"E0":E0,"E0m":E0m,"E0d":E0d,"E1":E1}.items():
        for g in G4: print(f"  {name} [{g}] "+"  ".join(f"{c}={st.median([V(D,c,s,g) for s in S]):.4f}" for c in C5))
    print(f"### [{metric}] 预注册判定（E1 vs E0m）：按癌种 × 格点给出 超带正 / 带内 / 超带负")
    for c in C5:
        print(f"  {c}: "+"  ".join(f"{g}:{cmp(E1,E0m,g,c)[4]}({cmp(E1,E0m,g,c)[3]:+.3f})" for g in G4))
    # 一致性：E0m 在 none 格点必须与 E0 完全相同（填充不触发）
    diff_none=max(abs(V(E0m,c,s,"none")-V(E0,c,s,"none")) for c in C5 for s in S); print(f"### [{metric}] 自检：E0m none 与 E0 none 最大|Δ| = {diff_none:.2e}（BLCA test 无自然缺失应为 0；BRCA/LUAD/LGG/UCEC test 有自然缺失，均值填在 none 也生效，非零属预期）")
    for c in C5: print(f"  {c} none 最大|E0m−E0| = {max(abs(V(E0m,c,s,'none')-V(E0,c,s,'none')) for s in S):.2e}")
