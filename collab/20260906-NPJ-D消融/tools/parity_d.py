#!/usr/bin/env python3
"""NPJ-D 部署对拍：gate 路径逐位不变。用法：parity_d.py <new_gate.json> <ref_m0real.json>；比较 new 里所有格点的 cindex_A/B/n_test/grid_sha 与 ref 相同格点。"""
import json,sys
a=json.load(open(sys.argv[1]))["grids"]; b=json.load(open(sys.argv[2]))["grids"]; bad=0
for g in a:
    for k in ("cindex_A","cindex_B","n_test","grid_sha"):
        if a[g][k]!=b[g][k]: print("DIFF",g,k,a[g][k],b[g][k]); bad+=1
print("grids:",list(a)); print("PARITY_PASS" if bad==0 else f"PARITY_FAIL bad={bad}"); sys.exit(0 if bad==0 else 1)
