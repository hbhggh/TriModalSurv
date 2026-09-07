#!/usr/bin/env python3
"""landau 侧：统计 ex12 标签各癌种 test 集的自然缺失（text pkl 不存在 / rna identifier 不含）。只读。
用法（landau，cd /home/wuhao/NPJ）：python scripts_tmp/count_natural_missing.py model/config/surv_multimodal_mainmoe_uni2.yml data/TCGA_9523_ex12.csv"""
import sys,os,csv,pickle,yaml,collections
cfg=yaml.safe_load(open(sys.argv[1])); label=sys.argv[2]
text_dir=cfg["modality"]["text"]["path"]; rna_dir=cfg["modality"]["rna"]["path"]
rows=[r for r in csv.DictReader(open(label))]
key_c=[k for k in rows[0] if k.lower() in ("cancer_type","cancer","type")][0]; key_p=[k for k in rows[0] if "patient" in k.lower() or k.lower() in ("pid","case_id")][0]; key_s=[k for k in rows[0] if k.lower()=="split"][0]
for c in ["BLCA","BRCA","LUAD","LGG","UCEC"]:
    test=[r[key_p][:12] for r in rows if r[key_c]==c and r[key_s]=="test"]
    rna_ids=set()
    p=os.path.join(rna_dir,f"RNA_{c}_embedding_token_lvl.pkl")
    if os.path.exists(p):
        d=pickle.load(open(p,"rb")); rna_ids={str(x)[:12] for x in d.get("identifier",[])}
    miss_text=sum(1 for pid in test if not os.path.exists(os.path.join(text_dir,f"{pid}.pkl")))
    miss_rna=sum(1 for pid in test if pid not in rna_ids) if rna_ids else -1
    print(f"{c}: test n={len(test)} natural_missing text={miss_text} rna={miss_rna}")
