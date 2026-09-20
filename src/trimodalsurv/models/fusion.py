"""NPJ gate / D 共享骨干，保留 T0 数值行为与参数键。"""
import torch
from torch import nn
from .consistency import consistency_loss

class GatedFusion(nn.Module):
    def __init__(self, hidden_dim, num_modalities):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_modalities = num_modalities
        self.gate = nn.Linear(hidden_dim * num_modalities, num_modalities)

    def forward(self, reps):
        reps_list = [r for r in reps if r is not None]
        if len(reps_list) == 1:
            return reps_list[0]  # only one valid modality

        all_reps = []
        masks = []
        for r in reps:
            if r is None:
                zero_tensor = torch.zeros_like(reps_list[0])
                all_reps.append(zero_tensor)
                masks.append(0)
            else:
                all_reps.append(r)
                masks.append(1)

        cat = torch.cat(all_reps, dim=-1)  # [B, hidden_dim * M]
        gate_logits = self.gate(cat)       # [B, M]

        mask_tensor = torch.tensor(masks, device=cat.device, dtype=torch.float32).unsqueeze(0)  # [1, M]
        inf_mask = (mask_tensor == 0).float() * (-1e9)
        gate_logits = gate_logits + inf_mask  

        gate_weights = torch.softmax(gate_logits, dim=-1)  # [B, M]
        gated = torch.stack(all_reps, dim=1)  # [B, M, D]
        gate_weights = gate_weights.unsqueeze(-1)  # [B, M, 1]
        return (gate_weights * gated).sum(dim=1)  # [B, D]


class MeanFusion(nn.Module):
    """等权均值融合（NPJ-D 消融，2026-09-06）：与 GatedFusion 同接口，无可学习参数。

    输入长度 M 的列表（元素 [B, D] 或 None），输出 [B, D]。
    对非 None 的元素做等权算术平均；None 元素跳过（与 GatedFusion 用 -1e9
    屏蔽 None 的效果一致）；只有一个非 None 时直接返回它。
    """

    def forward(self, reps):
        reps_list = [r for r in reps if r is not None]
        if not reps_list:
            raise ValueError("MeanFusion 至少需要一个非 None 的模态表征")
        if len(reps_list) == 1:
            return reps_list[0]  # only one valid modality
        return torch.stack(reps_list, dim=1).mean(dim=1)  # [B, D]


class SurvivalHead(nn.Module):  
    def __init__(self, input_dim, n_bins):
        super().__init__()
        self.hazard_layer = nn.Linear(input_dim, n_bins)

    def forward(self, x):
        hazard = self.hazard_layer(x) # [B, T]
        surv = torch.cumprod(1 - hazard, dim=1)        # [B, T]
        return hazard, surv


class MainModalityMoE(nn.Module):
    def __init__(self, device, modalities, hidden_size, dropout_rate=0.1, 
                 pred_dim=15, mlp_ratio=4, n_token=16, n_backbone=1, 
                 n_head=4, num_experts=4, topk=1, cancer_types=None,
                 compensator=None, fusion_type: str = "gate"):
        super(MainModalityMoE, self).__init__()
        self.device = device
        self.modalities = list(modalities.keys())
        self.cancer_types = cancer_types or ['Default']
        self.compensator = compensator

        self.m_projector = nn.ModuleDict({
            mm: nn.Sequential(
                nn.Linear(modalities[mm].feature_dim, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout_rate)
            ) for mm in self.modalities
        })

        # 指挥官小修（NPJ-D 消融，2026-09-06）：gate = 原 NPJ-A；mean = 去 GatedFusion 的等权均值对照臂
        self.fusion_type = fusion_type
        if fusion_type == 'gate':
            self.fusion = GatedFusion(hidden_size, num_modalities=len(self.modalities))
        elif fusion_type == 'mean':
            self.fusion = MeanFusion()
        else:
            raise ValueError(f"Unsupported fusion_type: {fusion_type!r} (expected 'gate' or 'mean')")

        self.backbone = nn.Sequential(
            *[nn.TransformerEncoderLayer(
                d_model=hidden_size,
                nhead=n_head,
                dim_feedforward=hidden_size * mlp_ratio,
                dropout=dropout_rate,
                activation='gelu',
                batch_first=True
            ) for _ in range(n_backbone)]
        )

        # self.surv_head = SurvivalHead(hidden_size, n_bins=pred_dim)
        self.surv_heads = nn.ModuleDict({
            ct: SurvivalHead(hidden_size, n_bins=pred_dim) for ct in self.cancer_types
        })
        self.logits_dim = pred_dim

    def forward(self, all_modalities, cancer_type='Default'):
        input_data = {}
        for mm in self.m_projector.keys():
            if mm not in all_modalities:
                input_data[mm] = None
                continue

            x = all_modalities[mm]
            if x.dim() > 2:
                x = x.mean(dim=1)

            mask_key = f"{mm}_mask"
            if mask_key in all_modalities and all_modalities[mask_key].sum() == 0:
                input_data[mm] = None
            else:
                input_data[mm] = self.m_projector[mm](x)

        consistency_pairs = []
        if self.compensator is not None:
            tokens_dict = {
                mm: token for mm, token in input_data.items() if token is not None
            }
            valids_dict = {}
            for mm in self.compensator.modalities:
                valid_key = f"{mm}_valid"
                if mm not in tokens_dict or valid_key not in all_modalities:
                    continue
                valids_dict[mm] = all_modalities[valid_key]

                original_key = f"{mm}_orig"
                if original_key in all_modalities:
                    original = all_modalities[original_key]
                    if original.dim() > 2:
                        original = original.mean(dim=1)
                    tokens_dict[original_key] = self.m_projector[mm](original)

                dropped_key = f"{mm}_dropped"
                if dropped_key in all_modalities:
                    valids_dict[dropped_key] = all_modalities[dropped_key]

            if valids_dict:
                tokens_dict, consistency_pairs = self.compensator(
                    tokens_dict,
                    valids_dict,
                    bin_labels=all_modalities.get('bin_labels'),
                    training=self.training,
                )
                for mm in self.compensator.modalities:
                    if mm in tokens_dict:
                        input_data[mm] = tokens_dict[mm]

        input_list = [input_data.get(mm, None) for mm in self.m_projector.keys()]
        fused = self.fusion(input_list)  # [B, D]
        fused = fused.unsqueeze(1)       # [B, 1, D]

        backbone_out = self.backbone(fused)  # [B, 1, D]
        pooled = backbone_out.mean(dim=1)    # [B, D]

        if cancer_type and all(ct == cancer_type[0] for ct in cancer_type):
            hazard, surv = self.surv_heads[cancer_type[0]](pooled)
        else:
            hazards = []
            survs = []
            for i, ct in enumerate(cancer_type):
                out = self.surv_heads[ct](pooled[i].unsqueeze(0))  # [1, T]
                hazards.append(out[0])
                survs.append(out[1])

            hazard = torch.cat(hazards, dim=0)  # [B, T]
            surv = torch.cat(survs, dim=0)      # [B, T]
        if self.compensator is not None:
            consistency = consistency_loss(consistency_pairs).to(
                device=hazard.device, dtype=hazard.dtype
            )
            return hazard, surv, consistency
        return hazard, surv

