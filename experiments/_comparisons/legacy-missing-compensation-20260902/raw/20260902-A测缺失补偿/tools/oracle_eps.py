# -*- coding: utf-8 -*-
"""指挥官独立 oracle（与 summarize_arms 无共享代码）：直接读 JSON 算 W:L:T / 配对Δ中位 / 各臂中位。
用法：cd 战役目录 && python3 oracle_eps.py  → 打印并可 --json 输出字典。"""
import json, glob, os, re, statistics as st, sys
C5=["BLCA","BRCA","LUAD","LGG","UCEC"]; S=[123,132,213,231,321]; EPS=1e-6
PAT=re.compile(r"^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$")
def load_dirs(dirs, metric="cindex_B"):
    out={}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d,"*.json"))):
            m=PAT.match(os.path.basename(p))
            if not m: continue
            key=(m["cancer"], int(m["seed"])); doc=json.load(open(p,encoding="utf-8"))
            for g,v in doc["grids"].items():
                if (key,g) in out and out[(key,g)]!=v[metric]: raise SystemExit(f"oracle conflict {key} {g}")
                out[(key,g)]=v[metric]
    return out
def wlt(a,b,grid):
    d=[a[((c,s),grid)]-b[((c,s),grid)] for c in [None] for s in S] if False else None
def compare(a,b,grid,c):
    d=[a[((c,s),grid)]-b[((c,s),grid)] for s in S if ((c,s),grid) in a and ((c,s),grid) in b]
    w=sum(x>EPS for x in d); l=sum(x<-EPS for x in d); t=sum(abs(x)<=EPS for x in d)
    return w,l,t,(st.median(d) if d else None)
def med(a,grid,c):
    v=[a[((c,s),grid)] for s in S if ((c,s),grid) in a]; return st.median(v) if v else None
E0=load_dirs(["results_npjc/e0","results_npjc_both/e0"]); E1=load_dirs(["results_npjc/e1","results_npjc_both/e1"]); E0d=load_dirs(["results_npjc_e0d"])
G4=["none","rna_100","text_100","both_100"]
res={}
for name,(x,y) in {"E1_vs_E0":(E1,E0),"E0d_vs_E0":(E0d,E0),"E1_vs_E0d":(E1,E0d)}.items():
    for g in G4:
        for c in C5:
            w,l,t,d=compare(x,y,g,c); res[f"{name}|{g}|{c}"]=[w,l,t,round(d,4) if d is not None else None]
for name,a in {"E0":E0,"E1":E1,"E0d":E0d}.items():
    for g in G4:
        for c in C5: res[f"med|{name}|{g}|{c}"]=round(med(a,g,c),4)
if "--json" in sys.argv: print(json.dumps(res,ensure_ascii=False,sort_keys=True)); sys.exit()
for name in ["E1_vs_E0","E0d_vs_E0","E1_vs_E0d"]:
    print(f"### {name} (W:L:T, Δ中位)")
    for g in G4:
        print(f"[{g}] "+"  ".join(f"{c}={res[f'{name}|{g}|{c}'][0]}:{res[f'{name}|{g}|{c}'][1]}:{res[f'{name}|{g}|{c}'][2]}({res[f'{name}|{g}|{c}'][3]:+.4f})" for c in C5))
    tot=[sum(res[f"{name}|both_100|{c}"][i] for c in C5) for i in range(3)]; print(f"  both_100 合计 {tot[0]}:{tot[1]}:{tot[2]} / 25")
print("### 中位（B）")
for name in ["E0","E0d","E1"]:
    for g in G4: print(f"{name} [{g}] "+"  ".join(f"{c}={res[f'med|{name}|{g}|{c}']:.4f}" for c in C5))
