#!/bin/bash
# 指挥官独立复核：verify_eps.sh <engine>  （在战役目录内运行）
E="$1"; SP=/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/38e445d3-407a-4baf-8e22-1935f9bb64f1/scratchpad
cd "/Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿" || exit 1
export PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
T="tools_$E"; F="figures_$E"
echo "===== VERIFY $E @ $(date '+%H:%M:%S') ====="
echo "--- [1] baseline integrity (modified files) ---"
shasum -c baseline.sha256 2>/dev/null | grep -v ": OK$" | grep -v "^$" || echo "BASELINE_UNMODIFIED_OK"
echo "--- [1b] new/deleted files outside engine prefix (excluding commander-known) ---"
find . -type f -not -name ".DS_Store" | sort > "$SP/now_$E.list"
comm -13 baseline.list "$SP/now_$E.list" | grep -v -E "^\./(tools_$E/|figures_$E/|table_[A-Za-z0-9_]+_$E\.md$|notes_eps_$E\.md$)" | grep -v -E "^\./(tools_(opus|codex)/|figures_(opus|codex)/|table_[A-Za-z0-9_]+_(opus|codex)\.md$|notes_eps_(opus|codex)\.md$|baseline\.(list|sha256)$|ab_first_task\.md$)" || echo "NO_FOREIGN_NEW_FILES"
comm -23 baseline.list "$SP/now_$E.list" || echo "NO_DELETED_FILES"
echo "--- [1c] NPJ tree ---"; git -C /Users/wuhao/Desktop/TriModalSurv status --porcelain NPJ/ | head -3; echo "(npj status lines above; expect none)"
echo "--- [2] products ---"
for p in $T/summarize_arms.py $T/plot_missing_curves.py $F/gate_missing_curves.png $F/gate_missing_curves.svg $F/npjc_e0_e1_4grids.png $F/npjc_e0_e1_4grids.svg table_npjc_E0_E1_4grids_$E.md table_npjc_E0_E1_E0d_4grids_$E.md table_both100_E1_vs_E0_$E.md notes_eps_$E.md; do [ -f "$p" ] && echo "OK $p ($(stat -f %z "$p")B)" || echo "MISSING $p"; done
echo "--- [3] compile (in-memory) ---"
python3 -c 'import sys;[compile(open(p,"rb").read(),p,"exec") for p in sys.argv[1:]];print("COMPILE_OK")' $T/summarize_arms.py $T/plot_missing_curves.py
echo "--- [4] replay (legacy byte-identical) ---"
python3 $T/summarize_arms.py --arm E0=results_npjc/e0 --arm E1=results_npjc/e1 --legacy-winloss | diff - <(cat table_npjc_E0_E1.md; echo) > /dev/null && echo REPLAY_OK || echo REPLAY_FAIL
echo "--- [5] regenerate tables into scratch and diff vs delivered ---"
python3 $T/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --grids none,rna_100,text_100,both_100 --out "$SP/t4_$E.md" --pairwise-grid both_100 --pairwise-out "$SP/pw_$E.md" > /dev/null; echo "TABLE4_EXIT=$?"
cmp -s "$SP/t4_$E.md" table_npjc_E0_E1_4grids_$E.md && echo T4_DELIVERED_MATCHES_REGEN || echo T4_DELIVERED_DIFFERS
cmp -s "$SP/pw_$E.md" table_both100_E1_vs_E0_$E.md && echo PW_DELIVERED_MATCHES_REGEN || echo PW_DELIVERED_DIFFERS
python3 $T/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --arm E0d=results_npjc_e0d --grids none,rna_100,text_100,both_100 --out "$SP/t3_$E.md" > /dev/null; echo "TABLE_E0D_EXIT=$?"
cmp -s "$SP/t3_$E.md" table_npjc_E0_E1_E0d_4grids_$E.md && echo T3_DELIVERED_MATCHES_REGEN || echo T3_DELIVERED_DIFFERS
echo "--- [6] tie positive sample / conflict / missing exits ---"
echo "TIE_CELLS=$(python3 $T/summarize_arms.py --arm m0real=results_gate/m0real --arm m1=results_gate/m1 --arm m1b=results_gate/m1b --arm m2=results_gate/m2 --grids none,rna_100 | grep -c ':[1-9] (Δ中位')"
python3 $T/summarize_arms.py --arm E0=results_npjc/e0,results_npjc/e0 --arm E1=results_npjc/e1 > /dev/null 2>"$SP/conf_$E.err"; echo "CONFLICT_EXIT=$? stderr=$(head -c 120 "$SP/conf_$E.err")"
python3 $T/summarize_arms.py --arm E0=results_npjc/nonexistent --arm E1=results_npjc/e1 > /dev/null 2>"$SP/miss_$E.err"; echo "MISSING_EXIT=$? stderr=$(head -c 120 "$SP/miss_$E.err")"
echo "--- [7] cell-wise vs table_npjc_E0_E1.md ---"
python3 - "$E" <<'PY'
import re,sys
E=sys.argv[1]
def sections(path):
    sec={};cur=None
    for line in open(path,encoding="utf-8").read().split("\n"):
        if line.startswith("## 格点 "): cur=line.split()[-1]; sec[cur]=[]
        elif cur and line.startswith("| ") and not line.startswith("| 癌种"): sec[cur].append(line)
    return sec
ref=sections("table_npjc_E0_E1.md"); new=sections(f"table_npjc_E0_E1_4grids_{E}.md")
ok=True
for g in ["none","rna_100","text_100"]:
    r=ref[g]; n=new.get(g,[])
    if len(r)!=len(n) or len(r)!=10: print(f"SECTION {g}: ROWCOUNT ref={len(r)} new={len(n)}"); ok=False; continue
    rows=0
    for a,b in zip(r,n):
        ca=a.split("|")[1:-1]; cb=b.split("|")[1:-1]
        if len(ca)!=9 or len(cb)!=9: print(f"SECTION {g}: COLCOUNT {a[:40]}"); ok=False; continue
        if ca[:8]!=cb[:8]: print(f"SECTION {g}: CELLS differ: {a}\n  vs {b}"); ok=False; continue
        if ca[1].strip()=="E0":
            if not (ca[8]=="  " and cb[8]=="  "): print(f"SECTION {g}: base cell not blank: {repr(ca[8])} {repr(cb[8])}"); ok=False
        else:
            ma=re.match(r"^(\d+):(\d+) \(Δ中位 ([+-]\d\.\d{4})\)$",ca[8].strip()); mb=re.match(r"^(\d+):(\d+):(\d+) \(Δ中位 ([+-]\d\.\d{4})\)$",cb[8].strip())
            if not (ma and mb and ma[1]==mb[1] and ma[2]==mb[2] and mb[3]=="0" and ma[3]==mb[4]): print(f"SECTION {g}: WL differ: {repr(ca[8])} vs {repr(cb[8])}"); ok=False
        rows+=1
    if rows==10: print(f"SECTION {g}: OK (10 rows)")
print("ALL SECTIONS OK" if ok else "CELLWISE_FAIL")
PY
echo "--- [8] engine tables vs commander oracle ---"
python3 - "$E" "$SP/oracle_eps.json" <<'PY'
import re,sys,json
E=sys.argv[1]; O=json.load(open(sys.argv[2]))
def parse(path, base="E0"):
    out={};cur=None
    for line in open(path,encoding="utf-8").read().split("\n"):
        if line.startswith("## 格点 "): cur=line.split()[-1]
        elif cur and line.startswith("| ") and not line.startswith("| 癌种"):
            c=[x.strip() for x in line.split("|")[1:-1]]
            if c[1]!=base:
                m=re.match(r"^(\d+):(\d+):(\d+) \(Δ中位 ([+-]\d\.\d{4})\)$",c[8])
                out[(c[1],cur,c[0])]=(int(m[1]),int(m[2]),int(m[3]),float(m[4])) if m else None
                out[("med",c[1],cur,c[0])]=float(c[7])
            else: out[("med",base,cur,c[0])]=float(c[7])
    return out
bad=0;n=0
for path,arms in [(f"table_npjc_E0_E1_4grids_{E}.md",["E1"]),(f"table_npjc_E0_E1_E0d_4grids_{E}.md",["E1","E0d"])]:
    t=parse(path)
    for arm in arms:
        for g in ["none","rna_100","text_100","both_100"]:
            for c in ["BLCA","BRCA","LUAD","LGG","UCEC"]:
                o=O[f"{arm}_vs_E0|{g}|{c}"]; v=t.get((arm,g,c)); n+=1
                if v is None or list(v[:3])!=o[:3] or abs(v[3]-o[3])>5e-5: print(f"ORACLE_MISMATCH {path} {arm} {g} {c}: table={v} oracle={o}"); bad+=1
                for a2 in ["E0",arm]:
                    mo=O[f"med|{a2}|{g}|{c}"]; mv=t.get(("med",a2,g,c))
                    if mv is None or abs(mv-mo)>5e-5: print(f"ORACLE_MED_MISMATCH {path} {a2} {g} {c}: {mv} vs {mo}"); bad+=1
# pairwise table
pw=open(f"table_both100_E1_vs_E0_{E}.md",encoding="utf-8").read().split("\n")
tot=[sum(O[f"E1_vs_E0|both_100|{c}"][i] for c in ["BLCA","BRCA","LUAD","LGG","UCEC"]) for i in range(3)]
for line in pw:
    if line.startswith("| ") and not line.startswith("| 癌种"):
        c=[x.strip() for x in line.split("|")[1:-1]]
        if c[0]=="合计":
            exp=f"{tot[0]}:{tot[1]}:{tot[2]} / 25"
            if c[3]!=exp: print(f"PW_TOTAL_MISMATCH {c[3]} vs {exp}"); bad+=1
            n+=1; continue
        o=O[f"E1_vs_E0|both_100|{c[0]}"]; n+=1
        if c[3]!=f"{o[0]}:{o[1]}:{o[2]}" or abs(float(c[4])-o[3])>5e-5 or abs(float(c[1])-O[f"med|E0|both_100|{c[0]}"])>5e-5 or abs(float(c[2])-O[f"med|E1|both_100|{c[0]}"])>5e-5: print(f"PW_MISMATCH {line} vs {o}"); bad+=1
print(f"ORACLE_CHECK cells={n} mismatches={bad} " + ("ORACLE_OK" if bad==0 else "ORACLE_FAIL"))
PY
echo "--- [9] figures: determinism / date leak / dims ---"
mkdir -p "$SP/figrun_$E" && python3 $T/plot_missing_curves.py --out "$SP/figrun_$E" > "$SP/figrun_$E.log" 2>&1; echo "PLOT_EXIT=$? $(head -c 200 "$SP/figrun_$E.log")"
A=$(cd "$SP/figrun_$E" && shasum -a 256 * ); python3 $T/plot_missing_curves.py --out "$SP/figrun_$E" > /dev/null 2>&1; B=$(cd "$SP/figrun_$E" && shasum -a 256 *); [ "$A" = "$B" ] && echo DETERMINISTIC_OK || echo DETERMINISM_FAIL
for f in gate_missing_curves npjc_e0_e1_4grids; do cmp -s "$SP/figrun_$E/$f.png" "$F/$f.png" && echo "DELIVERED_PNG_MATCHES $f" || echo "DELIVERED_PNG_DIFFERS $f"; done
grep -l "dc:date" $F/*.svg "$SP/figrun_$E"/*.svg 2>/dev/null && echo DATE_LEAK_FAIL || echo NO_DATE_LEAK_OK
for f in $F/*.png; do python3 -c 'import sys,struct;d=open(sys.argv[1],"rb").read();w,h=struct.unpack(">II",d[16:24]);print("PNG",sys.argv[1],w,h,len(d),"OK" if len(d)>=50000 else "SMALL")' "$f"; done
for f in $F/*.svg; do python3 -c 'import sys,os;s=os.path.getsize(sys.argv[1]);print("SVG",sys.argv[1],s,"OK" if s>=20000 else "SMALL")' "$f"; done
echo "--- [10] misc ---"
echo "缺格0 counts: $(grep -c '^缺格：0$' table_npjc_E0_E1_4grids_$E.md) $(grep -c '^缺格：0$' table_npjc_E0_E1_E0d_4grids_$E.md)"
echo "pycache: $(find . -name __pycache__ -o -name '*.pyc' | wc -l | tr -d ' ')"
echo "trailing newline (expect none): $(tail -c1 table_npjc_E0_E1_4grids_$E.md | xxd -p) $(tail -c1 table_both100_E1_vs_E0_$E.md | xxd -p)"
echo "notes: $(wc -l < notes_eps_$E.md) lines; EPS_DONE=$(grep -c EPS_DONE notes_eps_$E.md); 歧义节=$(grep -c '歧义' notes_eps_$E.md)"
echo "===== END $E ====="
