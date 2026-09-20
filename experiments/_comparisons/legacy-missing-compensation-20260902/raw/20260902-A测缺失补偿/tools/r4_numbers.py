# -*- coding: utf-8 -*-
"""r4 对账脚本（指挥官独立实现，与 summarize_arms.py 无共享代码）：E0/E0d/E1 四格点 W:L:T、配对Δ中位、各臂中位、异常 seed、极差、both_100 跌幅、敏感性。
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
# ---- r4 附加派生量（异常 seed / 极差 / 跌幅 / 敏感性）----
A={"E0":E0,"E0d":E0d,"E1":E1}
def V(D,c,s,g): return D[((c,s),g)]
print("### 异常 seed 扫描（偏离同臂同癌其余 4 seed 中位 > 0.08；4 格点）")
for arm,D in A.items():
    for c in C5:
        for g in G4:
            for s in S:
                o=[V(D,c,x,g) for x in S if x!=s]; dev=V(D,c,s,g)-st.median(o)
                if abs(dev)>0.08: print(f"  {arm} {c} s{s} {g}: {V(D,c,s,g):.4f} 偏离 {dev:+.4f}")
print("### 5-seed 极差（none / both_100）")
for c in ["UCEC","LGG"]:
    for arm,D in A.items():
        for g in ["none","both_100"]:
            v=[V(D,c,s,g) for s in S]; print(f"  {c} {arm} [{g}] range={max(v)-min(v):.4f} (max {max(v):.4f} min {min(v):.4f})")
print("### both_100 相对 none 的中位跌幅（各臂）")
for arm,D in A.items():
    print("  "+arm+": "+"  ".join(f"{c}={st.median([V(D,c,s,'both_100') for s in S])-st.median([V(D,c,s,'none') for s in S]):+.4f}" for c in C5))
print("### E1 BRCA 剔除 s123 后 vs E0d 配对Δ中位（敏感性，4 格点）")
for g in G4:
    d=[V(E1,"BRCA",s,g)-V(E0d,"BRCA",s,g) for s in S if s!=123]; print(f"  {g}: 4-seed Δ中位 {st.median(d):+.4f}, 负数 {sum(x<0 for x in d)}/4")
print("### 平局明细（|Δ|≤1e-6）")
for name,(x,y) in {"E1_vs_E0":(E1,E0),"E0d_vs_E0":(E0d,E0),"E1_vs_E0d":(E1,E0d)}.items():
    for g in G4:
        for c in C5:
            for s in S:
                if abs(V(x,c,s,g)-V(y,c,s,g))<=EPS: print(f"  {name} {c} s{s} {g}: {V(x,c,s,g):.6f} vs {V(y,c,s,g):.6f}")
# ---- r4 复核追加（decision-reviewer 第 1 轮引用量，机械化留档）----
def comp(x,y,g,c,excl=()):
    d=[V(x,c,s,g)-V(y,c,s,g) for s in S if s not in excl]
    return f"{sum(v>EPS for v in d)}:{sum(v<-EPS for v in d)}:{sum(abs(v)<=EPS for v in d)}({st.median(d):+.4f})"
print("### 九、剔除敏感性（协议=E0d−E0，召回=E1−E0d，总=E1−E0）")
print("  LGG both_100 剔 s213: 协议", comp(E0d,E0,"both_100","LGG",(213,)), " 召回", comp(E1,E0d,"both_100","LGG",(213,)), " 总", comp(E1,E0,"both_100","LGG",(213,)))
print("  BLCA 剔 s213 E1 vs E0d: none", comp(E1,E0d,"none","BLCA",(213,)), " both_100", comp(E1,E0d,"both_100","BLCA",(213,)))
print("  BRCA 剔 s321 E0d vs E0 both_100:", comp(E0d,E0,"both_100","BRCA",(321,)), " LGG 剔 s213 E0d vs E0 text_100:", comp(E0d,E0,"text_100","LGG",(213,)))
print("### 十、both_100 相对 none 的配对Δ中位（同臂逐 seed 差；参考：各臂中位之差见'跌幅'节）")
for arm,D in A.items():
    print("  "+arm+": "+"  ".join(f"{c}={st.median([V(D,c,s,'both_100')-V(D,c,s,'none') for s in S]):+.4f}" for c in C5))
print("### 十一、E0 遮单模态的配对Δ中位（grid − none，逐 seed）与胜负")
for c in C5:
    print(f"  {c}: rna_100 {comp(E0,E0,'rna_100',c) if False else ''}", end="")
    for g in ["rna_100","text_100"]:
        d=[V(E0,c,s,g)-V(E0,c,s,"none") for s in S]
        print(f"{g}={sum(v>EPS for v in d)}:{sum(v<-EPS for v in d)}:{sum(abs(v)<=EPS for v in d)}({st.median(d):+.4f})  ", end="")
    print()
print("### 十二、跨骨架方向：gate 版 M2 vs M0-real（table_gate_4arms 同口径）与 NPJ-C E1 vs E0 的配对Δ中位")
G=load_dirs(["results_gate/m0real"]); M2=load_dirs(["results_gate/m2"]); M1=load_dirs(["results_gate/m1"])
for g in ["none","rna_100","text_100","both_100"]:
    print(f"  [{g}] "+"  ".join(f"{c}: M2={st.median([V(M2,c,s,g)-V(G,c,s,g) for s in S]):+.4f} E1={st.median([V(E1,c,s,g)-V(E0,c,s,g) for s in S]):+.4f}" for c in C5))
print("### 十三、gate 版 both_100：M1 盲补 / M2 召回 vs M0-real 配对Δ中位与胜负（r3 W1 证据）")
for c in C5:
    print(f"  {c}: M1", comp(M1,G,"both_100",c), " M2", comp(M2,G,"both_100",c))
print("### 十四、E0d vs E0 |Δ中位|≥0.02 的格点清单")
for g in G4:
    for c in C5:
        d=st.median([V(E0d,c,s,g)-V(E0,c,s,g) for s in S])
        if abs(d)>=0.02: print(f"  {c} {g}: {d:+.4f}")
print("  |Δ|<0.02 格点数 =", sum(1 for g in G4 for c in C5 if abs(st.median([V(E0d,c,s,g)-V(E0,c,s,g) for s in S]))<0.02), "/ 20")
print("### 十五、平局精确值")
print("  E0 BRCA s231 none:", repr(V(E0,"BRCA",231,"none")), " E0d:", repr(V(E0d,"BRCA",231,"none")))
# ---- 第 4 轮复核追加 ----
print("### 十六、分量不可加：逐 seed 协议(E0d−E0) / 召回(E1−E0d) 与 Pearson r；分量和−实际(E1−E0) 的缺口")
def pear(a,b):
    ma=sum(a)/len(a); mb=sum(b)/len(b); num=sum((x-ma)*(y-mb) for x,y in zip(a,b)); den=(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**0.5
    return num/den if den else float("nan")
for c,g in [("UCEC","none"),("LGG","text_100"),("UCEC","both_100"),("LGG","both_100")]:
    p=[V(E0d,c,s,g)-V(E0,c,s,g) for s in S]; r=[V(E1,c,s,g)-V(E0d,c,s,g) for s in S]
    print(f"  {c} {g}: 协议={['%+.3f'%x for x in p]} 召回={['%+.3f'%x for x in r]} r={pear(p,r):+.2f}")
gaps=[]
for g in G4:
    for c in C5:
        p=st.median([V(E0d,c,s,g)-V(E0,c,s,g) for s in S]); r=st.median([V(E1,c,s,g)-V(E0d,c,s,g) for s in S]); t=st.median([V(E1,c,s,g)-V(E0,c,s,g) for s in S]); gaps.append(abs(p+r-t))
print(f"  |分量和−实际| 20 格点: min={min(gaps):.4f} max={max(gaps):.4f}")
print("### 十七、E0d vs E0 三癌（BLCA/BRCA/LUAD）12 格点 max|Δ中位|")
print("  ", f"{max(abs(st.median([V(E0d,c,s,g)-V(E0,c,s,g) for s in S])) for g in G4 for c in ['BLCA','BRCA','LUAD']):.4f}")
