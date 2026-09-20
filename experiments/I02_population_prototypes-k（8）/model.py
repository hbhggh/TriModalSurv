"""Inference-only paired population prototypes for missing-modality filling."""

import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.cluster import KMeans


# [创新 I02] 编码后的 WSI 聚类标签绑定 RNA/Text 均值；仅推理补偿。
class PopulationPrototypeBank(nn.Module):
    """Cluster complete patient tokens by WSI and store paired cluster means."""

    modalities = ("rna", "text")
    inference_only = True

    def __init__(self, k, dim, seed=123):
        super().__init__()
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("k must be a positive integer")
        if not isinstance(dim, int) or isinstance(dim, bool) or dim <= 0:
            raise ValueError("dim must be a positive integer")

        self.k = k
        self.dim = dim
        self.seed = seed
        self.register_buffer("wsi", torch.zeros(k, dim))
        self.register_buffer("rna", torch.zeros(k, dim))
        self.register_buffer("text", torch.zeros(k, dim))
        self.register_buffer("counts", torch.zeros(k, dtype=torch.long))
        self.register_buffer("ready", torch.tensor(False, dtype=torch.bool))

    @property
    def prototypes(self):
        return {
            "wsi": self.wsi,
            "rna": self.rna,
            "text": self.text,
        }

    def _validate_update_inputs(self, wsi, rna, text):
        tensors = {"wsi": wsi, "rna": rna, "text": text}
        for name, tensor in tensors.items():
            if not isinstance(tensor, torch.Tensor):
                raise TypeError(f"{name} must be a torch.Tensor")
            if tensor.ndim != 2 or tensor.shape[1] != self.dim:
                raise ValueError(
                    f"{name} must have shape [N, {self.dim}], got {tuple(tensor.shape)}"
                )

        row_counts = {tensor.shape[0] for tensor in tensors.values()}
        if len(row_counts) != 1:
            raise ValueError("wsi, rna and text must contain the same number of rows")
        eligible_count = wsi.shape[0]
        if eligible_count < self.k:
            raise ValueError(
                f"eligible patient count must be at least k={self.k}, got {eligible_count}"
            )
        for name, tensor in tensors.items():
            if not torch.isfinite(tensor).all():
                raise ValueError(f"{name} must contain only finite values")

    @torch.no_grad()
    def update_memory_bank(self, wsi, rna, text):
        """Hard-overwrite all paired prototypes using shared WSI KMeans labels."""
        self._validate_update_inputs(wsi, rna, text)

        labels_numpy = KMeans(
            n_clusters=self.k,
            random_state=self.seed,
            n_init=10,
        ).fit_predict(wsi.detach().cpu().numpy())
        labels = torch.as_tensor(labels_numpy, device=wsi.device, dtype=torch.long)
        counts = torch.bincount(labels, minlength=self.k)
        if (counts == 0).any():
            empty = torch.nonzero(counts == 0, as_tuple=False).reshape(-1).tolist()
            raise ValueError(f"KMeans produced empty clusters: {empty}")

        staged = {}
        for name, tensor in (("wsi", wsi), ("rna", rna), ("text", text)):
            means = torch.stack(
                [tensor[labels == cluster].detach().mean(dim=0) for cluster in range(self.k)]
            )
            target = self.prototypes[name]
            staged[name] = means.to(device=target.device, dtype=target.dtype)
            if not torch.isfinite(staged[name]).all():
                raise ValueError(f"computed {name} prototypes must be finite")
        staged_counts = counts.to(device=self.counts.device, dtype=self.counts.dtype)

        self.wsi.copy_(staged["wsi"])
        self.rna.copy_(staged["rna"])
        self.text.copy_(staged["text"])
        self.counts.copy_(staged_counts)
        self.ready.fill_(True)
        return labels

    @staticmethod
    def _valid_mask(valid, batch_size, device, name):
        mask = torch.as_tensor(valid, device=device)
        if mask.numel() != batch_size:
            raise ValueError(
                f"{name} must contain one value per sample: "
                f"expected {batch_size}, got {mask.numel()}"
            )
        return mask.reshape(batch_size).bool()

    def forward(self, tokens, valids, bin_labels=None, training=None):
        del bin_labels
        is_training = self.training if training is None else bool(training)
        output_tokens = dict(tokens)
        if is_training:
            return output_tokens, []

        if "img" not in tokens:
            raise KeyError("PopulationPrototypeBank requires the img WSI query token")
        img = tokens["img"]
        if img.ndim != 2 or img.shape[1] != self.dim:
            raise ValueError(f"img tokens must have shape [B, {self.dim}]")
        if "img" not in valids:
            raise ValueError("img validity is required for population prototype filling")
        img_valid = self._valid_mask(valids["img"], img.shape[0], img.device, "img_valid")
        if not img_valid.all():
            raise ValueError("PopulationPrototypeBank requires valid WSI/img for every sample")
        if not torch.isfinite(img).all():
            raise ValueError("WSI/img query tokens must contain only finite values")

        missing = {}
        for modality in self.modalities:
            if modality not in tokens or modality not in valids:
                continue
            modality_tokens = tokens[modality]
            if modality_tokens.ndim != 2 or modality_tokens.shape[1] != self.dim:
                raise ValueError(
                    f"{modality} tokens must have shape [B, {self.dim}]"
                )
            valid_mask = self._valid_mask(
                valids[modality],
                modality_tokens.shape[0],
                modality_tokens.device,
                f"{modality}_valid",
            )
            if (~valid_mask).any():
                missing[modality] = ~valid_mask

        if not missing:
            return output_tokens, []
        if not self.ready.item():
            raise RuntimeError("PopulationPrototypeBank is not ready")
        needed = torch.zeros(img.shape[0], dtype=torch.bool, device=img.device)
        for invalid_mask in missing.values():
            if invalid_mask.shape[0] != img.shape[0]:
                raise ValueError("all token modalities must use the same batch size")
            needed |= invalid_mask.to(device=img.device)
        wsi_prototypes = self.wsi.to(device=img.device, dtype=img.dtype)
        similarities = F.normalize(img, dim=-1) @ F.normalize(
            wsi_prototypes, dim=-1
        ).transpose(0, 1)
        best_rows = similarities.argmax(dim=-1)
        for modality, invalid_mask in missing.items():
            recovered = tokens[modality].clone()
            prototype_rows = self.prototypes[modality].to(
                device=recovered.device, dtype=recovered.dtype
            )
            recovered[invalid_mask] = prototype_rows[
                best_rows.to(device=recovered.device)[invalid_mask]
            ]
            output_tokens[modality] = recovered

        return output_tokens, []
