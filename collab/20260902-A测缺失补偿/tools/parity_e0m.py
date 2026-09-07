#!/usr/bin/env python3
"""E0m 对拍：A) 开关关闭时 gate 版 m1 输出与既有 results_gate/m1 逐位一致；B) 开关开启时 E0 ckpt 在 none 格点与既有 results_npjc/e0 逐位一致。
用法：python3 parity_e0m.py <new_m1_off.json> <ref_gate_m1.json> <new_e0m.json> <ref_e0.json>"""
import json,sys
def grids(p): return json.load(open(p))["grids"]
a,b,c,d=[grids(p) for p in sys.argv[1:5]]
bad=0
for g in a:
    for k in ("cindex_A","cindex_B","n_test","grid_sha"):
        if a[g][k]!=b[g][k]: print("PARITY_A_DIFF",g,k,a[g][k],b[g][k]); bad+=1
print("PARITY_A grids compared:",list(a))
for k in ("cindex_A","cindex_B","n_test"):
    if c["none"][k]!=d["none"][k]: print("PARITY_B_DIFF none",k,c["none"][k],d["none"][k]); bad+=1
print("PARITY_B none compared; other grids (fill active) must DIFFER from E0:", {g: round(c[g]["cindex_B"]-d[g]["cindex_B"],4) for g in c if g!="none" and g in d})
print("PARITY_PASS" if bad==0 else f"PARITY_FAIL bad={bad}")
sys.exit(0 if bad==0 else 1)
