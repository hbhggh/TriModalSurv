"""仅合成输入验证最大实际批量；不读取test表现，不训练。"""
import argparse
import json
import sys
import time
import subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import runtime as rt


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True)
    p.add_argument('--seconds',type=int,default=120)
    args=p.parse_args()
    cfg=rt.load_config(args.config)
    rt.setup_imports(cfg)
    gate=rt.verify_gpu(cfg)
    import torch
    from inference import load_rule
    from experiments.I01_patient_retrieval.evaluate import strict_e0_load,checkpoint_path
    torch.set_num_threads(cfg['runtime']['cpu_threads'])
    model=rt.build_model(cfg,'BRCA','cuda')
    strict_e0_load(model,checkpoint_path(Path(cfg['paths']['checkpoint_root']),'BRCA',123))
    n=cfg['runtime']['batch_size']
    # 批量上界为全部五癌valid/test中最大队列383；不探测无实际用途的更大批量。
    inputs={m:np.zeros((n,*shape),np.float32) for m,shape in cfg['shapes'].items()}
    inputs.update({m+'_valid':np.ones(n,dtype=bool) for m in cfg['shapes']})
    weights=np.ones((n,3),np.float64)
    util=[]; rounds=0; start=time.monotonic(); sampled=0
    with torch.inference_mode():
        while time.monotonic()-start < args.seconds:
            logits=load_rule(5).weighted_forward(model,inputs,'BRCA','cuda',weights,non_blocking=True)
            torch.cuda.synchronize()
            assert logits.shape==(n,4) and torch.isfinite(logits).all()
            rounds+=1
            if time.monotonic()-sampled>=1:
                value=subprocess.check_output(['nvidia-smi','-i',str(cfg['runtime']['gpu_id']),
                    '--query-gpu=utilization.gpu','--format=csv,noheader,nounits'],text=True)
                util.append(int(value.strip())); sampled=time.monotonic()
    median=float(np.median(util))
    result={'status':'PASS','synthetic_only':True,'c_index_computed':False,
        'batch_size':n,'max_actual_query_cohort':383,'batch_bound':'largest entire query cohort',
        'rounds':rounds,'duration_seconds':time.monotonic()-start,
        'peak_allocated_bytes':torch.cuda.max_memory_allocated(), 'gpu_util_samples':util,
        'gpu_util_median':median,'gpu_gate':gate,
        'allow_low_gpu_util':median<50,
        'low_util_reason':'Existing NPJC small-compute architecture exemption in project AGENTS GPU contract section 7' if median<50 else None}
    rt.write_json_new(ROOT/'evidence/formal-gpu-probe.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
