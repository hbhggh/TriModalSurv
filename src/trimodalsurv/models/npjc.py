"""根 NPJC 默认行为，兼容 I02 显式 inference_only 插槽。"""
import torch
from torch import nn
from .fusion import SurvivalHead
from .consistency import consistency_loss

class NPJC(nn.Module):
    def __init__(self, device, modalities, hidden_size, dropout_rate=0.1,
                 pred_dim=15, mlp_ratio=4, n_backbone=1, n_head=4,
                 cancer_types=None, compensator=None):
        super().__init__()
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
        self.modality_embed = nn.Parameter(
            torch.zeros(len(self.modalities), hidden_size)
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=n_head,
            dim_feedforward=hidden_size * mlp_ratio,
            dropout=dropout_rate,
            activation='gelu',
            batch_first=True,
        )
        self.backbone = nn.TransformerEncoder(
            encoder_layer,
            num_layers=n_backbone,
        )
        self.surv_heads = nn.ModuleDict({
            ct: SurvivalHead(hidden_size, n_bins=pred_dim)
            for ct in self.cancer_types
        })
        self.logits_dim = pred_dim

    def encode_patient_modalities(self, all_modalities):
        """Apply the existing per-patient mean pooling and modality projectors."""
        tokens = {}
        valids = {}
        population_mode = bool(
            getattr(self.compensator, 'inference_only', False)
        )
        for mm in self.m_projector.keys():
            x = all_modalities[mm]
            if x.dim() == 3:
                x = x.mean(dim=1)
            tokens[mm] = self.m_projector[mm](x)

            batch_size = tokens[mm].shape[0]
            if mm == 'img' and not population_mode:
                valid = torch.ones(batch_size, device=tokens[mm].device)
            else:
                valid = all_modalities.get(
                    f"{mm}_valid",
                    torch.ones(batch_size, device=tokens[mm].device),
                )
            valids[mm] = torch.as_tensor(
                valid, device=tokens[mm].device
            ).reshape(batch_size).bool()
        return tokens, valids

    def forward(self, all_modalities, cancer_type='Default'):
        tokens, valids = self.encode_patient_modalities(all_modalities)

        consistency_pairs = []
        inference_only = bool(
            getattr(self.compensator, 'inference_only', False)
        )
        should_compensate = self.compensator is not None and not (
            inference_only and self.training
        )
        if should_compensate:
            tokens_dict = dict(tokens)
            valids_dict = {}
            for mm in self.compensator.modalities:
                valid_key = f"{mm}_valid"
                if mm not in tokens_dict or valid_key not in all_modalities:
                    continue
                valids_dict[mm] = all_modalities[valid_key]

                original_key = f"{mm}_orig"
                if original_key in all_modalities:
                    original = all_modalities[original_key]
                    if original.dim() == 3:
                        original = original.mean(dim=1)
                    tokens_dict[original_key] = self.m_projector[mm](original)

                dropped_key = f"{mm}_dropped"
                if dropped_key in all_modalities:
                    valids_dict[dropped_key] = all_modalities[dropped_key]

            if inference_only:
                valids_dict.update(valids)
            if valids_dict:
                tokens_dict, consistency_pairs = self.compensator(
                    tokens_dict,
                    valids_dict,
                    bin_labels=all_modalities.get('bin_labels'),
                    training=self.training,
                )
                for mm in self.compensator.modalities:
                    if mm in tokens_dict and mm in valids_dict:
                        tokens[mm] = tokens_dict[mm]
                        valids[mm] = torch.ones_like(valids[mm])

        seq = torch.stack(
            [tokens[mm] for mm in self.modalities], dim=1
        ) + self.modality_embed
        valid = torch.stack(
            [valids[mm] for mm in self.modalities], dim=1
        )
        h = self.backbone(seq, src_key_padding_mask=~valid)
        valid_weight = valid.unsqueeze(-1).to(dtype=h.dtype)
        pooled = (h * valid_weight).sum(dim=1) / valid_weight.sum(
            dim=1
        ).clamp_min(1.0)

        if isinstance(cancer_type, str):
            hazard, surv = self.surv_heads[cancer_type](pooled)
        elif cancer_type and all(ct == cancer_type[0] for ct in cancer_type):
            hazard, surv = self.surv_heads[cancer_type[0]](pooled)
        else:
            hazards = []
            survs = []
            for i, ct in enumerate(cancer_type):
                hazard_i, surv_i = self.surv_heads[ct](pooled[i].unsqueeze(0))
                hazards.append(hazard_i)
                survs.append(surv_i)
            hazard = torch.cat(hazards, dim=0)
            surv = torch.cat(survs, dim=0)

        if self.compensator is not None:
            consistency = consistency_loss(consistency_pairs).to(
                device=hazard.device, dtype=hazard.dtype
            )
            return hazard, surv, consistency
        return hazard, surv

