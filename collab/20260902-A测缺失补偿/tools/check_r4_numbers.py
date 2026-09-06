# -*- coding: utf-8 -*-
"""r4 草稿数字对账：解析报告第二节/二b 的 W:L:T (Δ) 单元并与 oracle JSON 逐格比对。用法：python3 check_r4_numbers.py <report.md> <oracle.json>"""
import re,sys,json
rep=open(sys.argv[1],encoding="utf-8").read(); O=json.load(open(sys.argv[2]))
C5=["BLCA","BRCA","LUAD","LGG","UCEC"]; G4=["none","rna_100","text_100","both_100"]
def block(title_regex):
    m=re.search(title_regex,rep)
    if not m: return None
    sub=rep[m.end():]; rows={}
    for line in sub.split("\n"):
        if line.startswith("## ") or line.startswith("**(b)"): break
        mm=re.match(r"^\|\s*\**([A-Z]{3,4})\**\s*\|(.*)\|\s*$",line)
        if mm and mm[1] in C5:
            cells=[re.sub(r"\*","",c).strip() for c in mm[2].split("|")]
            rows[mm[1]]=[re.match(r"^(\d+):(\d+):(\d+) \(([+−-]\d\.\d{4})\)$",c) for c in cells[:4]]
    return rows
checks=[("E1_vs_E0", r"## 二、CAP-Recall：E1 vs E0"),("E0d_vs_E0", r"\*\*\(a\) 训练协议本身：E0d vs E0"),("E1_vs_E0d", r"\*\*\(b\) 召回项的方向：E1 vs E0d")]
bad=0;n=0
for name,rx in checks:
    rows=block(rx)
    if rows is None: print("BLOCK_NOT_FOUND",name); bad+=1; continue
    for c in C5:
        for gi,g in enumerate(G4):
            m=rows.get(c,[None]*4)[gi]; o=O[f"{name}|{g}|{c}"]; n+=1
            if not m: print("CELL_UNPARSED",name,c,g); bad+=1; continue
            d=float(m[4].replace("−","-"))
            if [int(m[1]),int(m[2]),int(m[3])]!=o[:3] or abs(d-o[3])>5e-5: print("MISMATCH",name,c,g,m.group(0),o); bad+=1
# 合计行
for name,exp in [("E1_vs_E0","17:8:0"),("E0d_vs_E0","15:10:0"),("E1_vs_E0d","16:9:0")]:
    tot=[sum(O[f"{name}|both_100|{c}"][i] for c in C5) for i in range(3)]
    s=f"{tot[0]}:{tot[1]}:{tot[2]}"; n+=1
    if s!=exp or (s+" / 25") not in rep: print("TOTAL_MISMATCH",name,s,exp); bad+=1
print(f"R4_NUMBER_CHECK cells={n} bad={bad} "+("OK" if bad==0 else "FAIL"))
