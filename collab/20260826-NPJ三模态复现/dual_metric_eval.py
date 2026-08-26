#!/usr/bin/env python3
"""dual_metric_eval.py — 双口径离线复评（decision-reviewer R2，只读，不改训练代码）

对 5 个已训练 ckpt 在同一 test split 上同时计算：
  A = 作者口径  risk_A = -Σ cumprod(1 - raw_logits)      （复现口径，与论文可比）
  B = 修正口径  risk_B = -Σ cumprod(1 - sigmoid(logits))  （数学上有意义的口径）
A−B 量化"评估端未过 sigmoid"（对抗审查 P0-1）的实际影响。
边界申明：ckpt 由 A 口径的 valid 指标选出，B ≠ 修正训练全流程后的真实性能。
"""
import sys

sys.path.insert(0, '/home/wuhao/NPJ')
import numpy as np
import torch
import torch.nn as nn
from sksurv.metrics import concordance_index_censored
from torch.utils.data import DataLoader

import main_survival as ms

SEEDS = [123, 132, 213, 231, 321]
CKPT = "out/{seed}/tcga_orig_img_2048text_768rna_256_MainModalityMoE_BLCA_surv.pth"

device = torch.device('cuda')
cfg = ms.YmlConfig('model/config/surv_multimodal_mainmoe.yml')
modality_config = {k: cfg.parse_to_modality(v) for k, v in cfg.obj.modality.items()}

_, _, test_ds = ms.get_dataset_tcga_sur(
    'data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv',
    modalities=modality_config, task_type='surv', img_select='all',
    n_image_tokens=128, cancer_types='BLCA', network_type='MainModalityMoE',
    simulate_missing_modality=None)
loader = DataLoader(test_ds, shuffle=False, batch_size=32, num_workers=0)
print(f"test 病人数: {len(test_ds)}")

rows = []
for seed in SEEDS:
    model = ms.load_model(network_type='MainModalityMoE', device=device,
                          modalities=modality_config, hidden_size=256,
                          pred_dim=cfg.obj.network.pred_dim, n_token=cfg.obj.network.n_token,
                          cancer_types=['BLCA'])
    model = nn.DataParallel(model).to(device)
    sd = torch.load(CKPT.format(seed=seed), map_location=device)
    model.load_state_dict(sd)
    model.eval()

    logits_l, t_l, c_l = [], [], []
    with torch.no_grad():
        for b in loader:
            t = b.pop('survival_months'); b.pop('survival_months_bin')
            c = b.pop('censorship'); b.pop('label', None); b.pop('patient_id', None)
            ct = b.pop('cancer_type'); b.pop('idx', None)
            x = {k: v.to(device, dtype=torch.float) for k, v in b.items()}
            out = model(x, cancer_type=ct)
            h = out[0] if isinstance(out, tuple) else out
            logits_l.append(h.float().cpu()); t_l.append(t); c_l.append(c)

    L = torch.cat(logits_l)
    T = torch.cat(t_l).numpy(); C = torch.cat(c_l).numpy()
    ev = (1 - C).astype(bool)

    risk_a = -torch.sum(torch.cumprod(1 - L, dim=1), dim=1).numpy()
    hz = torch.clamp(torch.sigmoid(L), 1e-6, 1 - 1e-6)
    risk_b = -torch.sum(torch.cumprod(1 - hz, dim=1), dim=1).numpy()

    ca = concordance_index_censored(ev, T, risk_a)[0]
    cb = concordance_index_censored(ev, T, risk_b)[0]
    # 附加诊断：raw logits 的范围（|z|<1 时 A/B 排序应高度一致）
    frac_out = float((L.abs() >= 1).float().mean())
    rows.append((seed, ca, cb))
    print(f"seed {seed}: A={ca:.4f}  B={cb:.4f}  A-B={ca-cb:+.4f}  |logit|>=1 占比={frac_out:.3%}")

a = np.array([r[1] for r in rows]); b = np.array([r[2] for r in rows])
print(f"\nA(作者口径) mean±std: {a.mean():.4f} ± {a.std():.4f}")
print(f"B(修正口径) mean±std: {b.mean():.4f} ± {b.std():.4f}")
print(f"A−B 均值: {a.mean()-b.mean():+.4f}")
