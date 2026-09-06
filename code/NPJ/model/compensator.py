import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def _sample_mask(mask, batch_size, device, name):
    mask = torch.as_tensor(mask, device=device)
    if mask.numel() != batch_size:
        raise ValueError(
            f"{name} must contain one value per sample: "
            f"expected {batch_size}, got {mask.numel()}"
        )
    return mask.reshape(batch_size).bool()


def _append_consistency_pair(
    pairs, recovered, tokens_dict, valids_dict, modality, invalid_mask
):
    original = tokens_dict.get(f"{modality}_orig")
    dropped = valids_dict.get(f"{modality}_dropped")
    if original is None or dropped is None:
        return

    dropped_mask = _sample_mask(
        dropped, recovered.shape[0], recovered.device, f"{modality}_dropped"
    )
    pair_mask = invalid_mask & dropped_mask
    if pair_mask.any():
        pairs.append((recovered[pair_mask], original[pair_mask].detach()))


class CAPRecall(nn.Module):
    def __init__(self, modalities=('text', 'rna'), dim=256, n_bins=4, ema=0.99):
        super().__init__()
        if not modalities:
            raise ValueError("modalities must not be empty")
        if dim <= 0 or n_bins <= 0:
            raise ValueError("dim and n_bins must be positive")
        if not 0.0 <= ema < 1.0:
            raise ValueError("ema must be in [0, 1)")

        self.modalities = tuple(modalities)
        self.dim = dim
        self.n_bins = n_bins
        self.ema = ema

        self.query = nn.ModuleDict()
        self.key = nn.ModuleDict()
        self.output = nn.ModuleDict()
        for modality in self.modalities:
            self.query[modality] = nn.Linear(dim, dim)
            self.key[modality] = nn.Linear(dim, dim)
            self.output[modality] = nn.Linear(dim, dim)
            self.register_buffer(
                f"{modality}_prototypes", torch.zeros(n_bins, dim)
            )
            self.register_buffer(
                f"{modality}_prototype_counts",
                torch.zeros(n_bins, dtype=torch.long),
            )

    def _prototype_table(self, modality):
        if modality not in self.modalities:
            raise KeyError(f"Unsupported modality: {modality}")
        return getattr(self, f"{modality}_prototypes")

    def _prototype_counts(self, modality):
        return getattr(self, f"{modality}_prototype_counts")

    @torch.no_grad()
    def update_prototypes(self, tokens, valids, bin_labels):
        if not self.training:
            return

        labels = torch.as_tensor(bin_labels)
        if labels.numel() == 0:
            return
        labels = labels.reshape(-1).long()
        if ((labels < 0) | (labels >= self.n_bins)).any():
            raise ValueError(f"bin_labels must be in [0, {self.n_bins})")

        for modality in self.modalities:
            if modality not in tokens or modality not in valids:
                continue
            modality_tokens = tokens[modality]
            if modality_tokens.ndim != 2 or modality_tokens.shape[1] != self.dim:
                raise ValueError(
                    f"{modality} tokens must have shape [B, {self.dim}]"
                )
            if labels.numel() != modality_tokens.shape[0]:
                raise ValueError("bin_labels must contain one value per sample")

            valid_mask = _sample_mask(
                valids[modality],
                modality_tokens.shape[0],
                modality_tokens.device,
                f"{modality}_valid",
            )
            modality_labels = labels.to(modality_tokens.device)
            prototypes = self._prototype_table(modality)
            counts = self._prototype_counts(modality)

            for bin_index in range(self.n_bins):
                selected = valid_mask & (modality_labels == bin_index)
                if not selected.any():
                    continue
                batch_mean = modality_tokens[selected].detach().mean(dim=0)
                batch_mean = batch_mean.to(
                    device=prototypes.device, dtype=prototypes.dtype
                )
                if counts[bin_index].item() == 0:
                    prototypes[bin_index].copy_(batch_mean)
                else:
                    prototypes[bin_index].mul_(self.ema).add_(
                        batch_mean, alpha=1.0 - self.ema
                    )
                counts[bin_index].add_(int(selected.sum().item()))

    def recall(self, anchor_img_token, modality):
        if anchor_img_token.shape[-1] != self.dim:
            raise ValueError(
                f"anchor_img_token last dimension must be {self.dim}"
            )
        prototypes = self._prototype_table(modality)
        query = self.query[modality](anchor_img_token)
        keys = self.key[modality](prototypes)
        attention = torch.softmax(
            query @ keys.transpose(-1, -2) / math.sqrt(self.dim), dim=-1
        )
        recalled = attention @ prototypes
        return self.output[modality](recalled)

    def forward(self, tokens_dict, valids_dict, bin_labels=None, training=False):
        output_tokens = dict(tokens_dict)
        if training and bin_labels is not None:
            self.update_prototypes(tokens_dict, valids_dict, bin_labels)

        pairs = []
        for modality in self.modalities:
            if modality not in tokens_dict or modality not in valids_dict:
                continue
            tokens = tokens_dict[modality]
            valid_mask = _sample_mask(
                valids_dict[modality],
                tokens.shape[0],
                tokens.device,
                f"{modality}_valid",
            )
            invalid_mask = ~valid_mask
            if not invalid_mask.any():
                continue
            if 'img' not in tokens_dict:
                raise KeyError("CAPRecall requires the img anchor token")

            recovered = tokens.clone()
            recovered[invalid_mask] = self.recall(
                tokens_dict['img'][invalid_mask], modality
            )
            output_tokens[modality] = recovered
            if training:
                _append_consistency_pair(
                    pairs,
                    recovered,
                    tokens_dict,
                    valids_dict,
                    modality,
                    invalid_mask,
                )

        return output_tokens, pairs


class MissingBank(nn.Module):
    def __init__(self, modalities=('text', 'rna'), dim=256):
        super().__init__()
        if not modalities:
            raise ValueError("modalities must not be empty")
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.modalities = tuple(modalities)
        self.dim = dim
        self.bank = nn.ParameterDict({
            modality: nn.Parameter(torch.zeros(dim))
            for modality in self.modalities
        })

    def forward(self, tokens_dict, valids_dict, bin_labels=None, training=False):
        del bin_labels
        output_tokens = dict(tokens_dict)
        pairs = []
        for modality in self.modalities:
            if modality not in tokens_dict or modality not in valids_dict:
                continue
            tokens = tokens_dict[modality]
            valid_mask = _sample_mask(
                valids_dict[modality],
                tokens.shape[0],
                tokens.device,
                f"{modality}_valid",
            )
            invalid_mask = ~valid_mask
            if not invalid_mask.any():
                continue

            recovered = tokens.clone()
            recovered[invalid_mask] = self.bank[modality].to(tokens.dtype)
            output_tokens[modality] = recovered
            if training:
                _append_consistency_pair(
                    pairs,
                    recovered,
                    tokens_dict,
                    valids_dict,
                    modality,
                    invalid_mask,
                )

        return output_tokens, pairs


def consistency_loss(pairs):
    if not pairs:
        return torch.tensor(0.0)

    similarities = []
    for recovered, original in pairs:
        if recovered.numel() == 0:
            continue
        similarities.append(
            F.cosine_similarity(recovered, original, dim=-1).reshape(-1)
        )
    if not similarities:
        return pairs[0][0].new_zeros(())
    return 1.0 - torch.cat(similarities).mean()
