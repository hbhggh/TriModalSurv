"""只读探针：S5 BLCA s123 ckpt 上测 GatedFusion 的真实行为（不改源文件、不训练）。"""
import sys, json, collections
sys.path.insert(0, '/home/wuhao/NPJ')
import torch, torch.nn as nn, numpy as np
from torch.utils.data import DataLoader
from sksurv.metrics import concordance_index_censored
import main_survival as ms
import model.fusion_model as fm
from loc_utils_3yr.tcga_dataset import TCGASurDataset

dev = torch.device('cuda')
cfg = ms.YmlConfig('model/config/surv_multimodal_mainmoe_uni2.yml')
mc = {k: cfg.parse_to_modality(v) for k, v in cfg.obj.modality.items()}
LABEL = 'data/TCGA_9523_ex12.csv'; MAN = 'data/missing_manifest_v1.csv'
CK = 'out/123/tcga_uni2_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth'

REC = collections.defaultdict(list)
orig_fwd = fm.GatedFusion.forward
def probe_fwd(self, reps):
    reps_list = [r for r in reps if r is not None]
    if len(reps_list) == 1:
        REC['single_return'].append(1); return orig_fwd(self, reps)
    all_reps, masks = [], []
    for r in reps:
        if r is None: all_reps.append(torch.zeros_like(reps_list[0])); masks.append(0)
        else: all_reps.append(r); masks.append(1)
    cat = torch.cat(all_reps, -1); gl = self.gate(cat)
    mt = torch.tensor(masks, device=cat.device, dtype=torch.float32).unsqueeze(0)
    gl = gl + (mt == 0).float() * (-1e9); w = torch.softmax(gl, -1)
    REC['w'].append(w.detach().cpu()); REC['masks'].append(masks)
    REC['norms'].append(torch.stack([r.norm(dim=-1) for r in all_reps], 1).detach().cpu())
    return orig_fwd(self, reps)
fm.GatedFusion.forward = probe_fwd

model = ms.load_model(network_type='MainModalityMoE', device=dev, modalities=mc, hidden_size=256,
                      pred_dim=cfg.obj.network.pred_dim, n_token=cfg.obj.network.n_token, cancer_types=['BLCA'])
model = nn.DataParallel(model).to(dev)
model.load_state_dict(torch.load(CK, map_location=dev)); model.eval()
mods = list(model.module.m_projector.keys())

def run(grid, fix_mask=False):
    REC.clear()
    ds = TCGASurDataset(LABEL, mc, 'test', 'surv', 'all', 128, 'BLCA', 'MainModalityMoE',
                        missing_manifest=MAN, missing_grid=grid)
    L, T, C = [], [], []
    with torch.no_grad():
        for b in DataLoader(ds, batch_size=32, shuffle=False):
            t = b.pop('survival_months'); b.pop('survival_months_bin'); c = b.pop('censorship')
            b.pop('label', None); b.pop('patient_id', None); b.pop('idx', None); ct = b.pop('cancer_type')
            if fix_mask:
                for mm in mods: b[f'{mm}_mask'] = b[f'{mm}_valid']
            x = {k: v.to(dev, dtype=torch.float) for k, v in b.items()}
            out = model(x, cancer_type=ct); h = out[0]
            L.append(h.float().cpu()); T.append(t); C.append(c)
    L = torch.cat(L); T = torch.cat(T).numpy(); C = torch.cat(C).numpy(); ev = (1 - C).astype(bool)
    hz = torch.clamp(torch.sigmoid(L), 1e-6, 1 - 1e-6); rb = -torch.sum(torch.cumprod(1 - hz, 1), 1).numpy()
    cb = concordance_index_censored(ev, T, rb)[0]
    res = {'grid': grid or 'full', 'fix_mask': fix_mask, 'cindex_B': round(float(cb), 4),
           'single_return_batches': len(REC['single_return'])}
    if REC['w']:
        W = torch.cat(REC['w']); N = torch.cat(REC['norms'])
        res['gate_w_mean'] = {m: round(float(W[:, i].mean()), 4) for i, m in enumerate(mods)}
        res['gate_w_min'] = {m: round(float(W[:, i].min()), 4) for i, m in enumerate(mods)}
        res['token_norm_mean'] = {m: round(float(N[:, i].mean()), 3) for i, m in enumerate(mods)}
        res['token_norm_std'] = {m: round(float(N[:, i].std()), 3) for i, m in enumerate(mods)}
        res['mask_seen'] = sorted(set(tuple(m) for m in REC['masks']))
    print(json.dumps(res, ensure_ascii=False)); return res

for g, f in [(None, False), ('rna_100', False), ('text_100', False), ('both_100', False),
             ('rna_100', True), ('text_100', True), ('both_100', True), ('rna_25', True)]:
    run(g, f)
print('PROBE_DONE')
