"""I04：已有 D 版风险分箱多中心召回；未新增 C 版实验。"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from trimodalsurv.models.compensator import CAPRecall, _sample_mask, _append_consistency_pair

# [创新 I04] 风险箱内 K-means 初始化、最近槽 EMA 与有效槽温度召回。
def _kmeans_plus_plus(points, k, generator):
    """k-means++ 起点：从 points[N, D] 取 k 个中心（k <= N），CPU generator 决定随机源。"""
    n_points = points.shape[0]
    centers = points.new_empty((k, points.shape[1]))
    first = int(torch.randint(n_points, (1,), generator=generator).item())
    centers[0] = points[first]
    if k == 1:
        return centers
    closest = ((points - centers[0]) ** 2).sum(dim=1)
    for index in range(1, k):
        weights = closest.detach().to(device='cpu', dtype=torch.float64)
        total = weights.sum()
        if not bool(torch.isfinite(total)) or float(total) <= 0.0:
            # 剩余点与已选中心全部重合：退化为顺序取点（后续去重会屏蔽重复槽）
            choice = index % n_points
        else:
            choice = int(torch.multinomial(weights / total, 1, generator=generator).item())
        centers[index] = points[choice]
        closest = torch.minimum(closest, ((points - centers[index]) ** 2).sum(dim=1))
    return centers


def _kmeans_fit(points, k, generator, iterations=10):
    """固定 10 轮 Lloyd 迭代；空簇保持中心不动。返回 [k, D]。"""
    centers = _kmeans_plus_plus(points, k, generator)
    if k == 1:
        return points.mean(dim=0, keepdim=True)
    for _ in range(iterations):
        assignment = torch.cdist(points, centers).argmin(dim=1)
        for index in range(k):
            members = points[assignment == index]
            if members.shape[0] == 0:
                continue
            centers[index] = members.mean(dim=0)
    return centers


def _distinct_rows(rows):
    """按逐位相等去重，保持原顺序；用于保证有效槽两两不同。"""
    kept = []
    for index in range(rows.shape[0]):
        row = rows[index]
        if any(torch.equal(row, other) for other in kept):
            continue
        kept.append(row)
    return kept


class CAPRecallMulti(nn.Module):
    """每个风险箱 L 个原型槽的 CAP 召回（L=1 时为「每箱一个中心」，但形状仍是 [4, 1, D]）。"""

    def __init__(self, modalities=('text', 'rna'), dim=256, n_bins=4,
                 proto_per_bin=1, ema=0.99):
        super().__init__()
        if not modalities:
            raise ValueError("modalities must not be empty")
        if dim <= 0 or n_bins <= 0:
            raise ValueError("dim and n_bins must be positive")
        if not isinstance(proto_per_bin, int) or proto_per_bin < 1:
            raise ValueError("proto_per_bin must be a positive integer")
        if not 0.0 <= ema < 1.0:
            raise ValueError("ema must be in [0, 1)")

        self.modalities = tuple(modalities)
        self.dim = dim
        self.n_bins = n_bins
        self.proto_per_bin = proto_per_bin
        self.ema = ema

        self.query = nn.ModuleDict()
        self.key = nn.ModuleDict()
        self.output = nn.ModuleDict()
        for modality in self.modalities:
            self.query[modality] = nn.Linear(dim, dim)
            self.key[modality] = nn.Linear(dim, dim)
            self.output[modality] = nn.Linear(dim, dim)
            self.register_buffer(
                f"{modality}_prototypes", torch.zeros(n_bins, proto_per_bin, dim)
            )
            self.register_buffer(
                f"{modality}_slot_valid",
                torch.zeros(n_bins, proto_per_bin, dtype=torch.bool),
            )
            self.register_buffer(
                f"{modality}_slot_counts",
                torch.zeros(n_bins, proto_per_bin, dtype=torch.long),
            )

        # 修订 v3：每模态一个可学习温度（CLIP 惯例 0.07）。放在 Q/K/O 构造之后，
        # 不消耗随机数，故 Q/K/O 初始化与 v2 逐位相同。
        self.logit_scale = nn.ParameterDict({
            modality: nn.Parameter(torch.tensor(math.log(1.0 / 0.07)))
            for modality in self.modalities
        })

        # 本 epoch 更新过的槽（诊断用）。刻意不是 buffer：不得进 state_dict。
        self._epoch_used = {}

    # ---------------- buffer 取用 ----------------
    def _prototype_table(self, modality):
        if modality not in self.modalities:
            raise KeyError(f"Unsupported modality: {modality}")
        return getattr(self, f"{modality}_prototypes")

    def _slot_valid_table(self, modality):
        if modality not in self.modalities:
            raise KeyError(f"Unsupported modality: {modality}")
        return getattr(self, f"{modality}_slot_valid")

    def _slot_counts(self, modality):
        return getattr(self, f"{modality}_slot_counts")

    def _epoch_used_table(self, modality, reference):
        table = self._epoch_used.get(modality)
        if table is None or table.device != reference.device:
            table = torch.zeros(
                self.n_bins, self.proto_per_bin, dtype=torch.bool,
                device=reference.device,
            )
            self._epoch_used[modality] = table
        return table

    def reset_epoch_stats(self):
        for table in self._epoch_used.values():
            table.zero_()

    def used_slots(self, modality):
        table = self._epoch_used.get(modality)
        return 0 if table is None else int(table.sum().item())

    # ---------------- 初始化（训练前一次性 K-means） ----------------
    @torch.no_grad()
    def init_prototypes(self, tokens_by_modality, bin_labels, seed):
        """按模态、按箱做 K-means（k = min(L, n_{m,b})），中心填入前 k 个槽。

        ``tokens_by_modality[m]`` 只应包含该模态**真实存在**的投影表示 [N_m, D]；
        ``bin_labels`` 可以是逐模态映射，也可以是与全部模态共用的 [N] 张量。
        """
        for modality_index, modality in enumerate(self.modalities):
            if modality not in tokens_by_modality:
                continue
            tokens = tokens_by_modality[modality]
            if isinstance(bin_labels, dict):
                labels = bin_labels[modality]
            else:
                labels = bin_labels
            labels = torch.as_tensor(labels).reshape(-1).long()
            if tokens.ndim != 2 or tokens.shape[1] != self.dim:
                raise ValueError(f"{modality} tokens must have shape [N, {self.dim}]")
            if labels.numel() != tokens.shape[0]:
                raise ValueError("bin_labels must contain one value per sample")
            if labels.numel() and ((labels < 0) | (labels >= self.n_bins)).any():
                raise ValueError(f"bin_labels must be in [0, {self.n_bins})")

            prototypes = self._prototype_table(modality)
            slot_valid = self._slot_valid_table(modality)
            counts = self._slot_counts(modality)
            prototypes.zero_()
            slot_valid.zero_()
            counts.zero_()

            labels = labels.to(device=tokens.device)
            bin_sizes = []
            k_values = []
            for bin_index in range(self.n_bins):
                members = tokens[labels == bin_index].detach().to(
                    device=prototypes.device, dtype=prototypes.dtype
                )
                bin_sizes.append(int(members.shape[0]))
                if members.shape[0] == 0:
                    k_values.append(0)
                    continue
                k = min(self.proto_per_bin, int(members.shape[0]))
                generator = torch.Generator().manual_seed(
                    (int(seed) * 1000003 + modality_index * 10007 + bin_index * 101)
                    % (2 ** 31 - 1)
                )
                centers = _kmeans_fit(members, k, generator)
                distinct = _distinct_rows(centers)
                for slot, center in enumerate(distinct):
                    prototypes[bin_index, slot].copy_(center)
                    slot_valid[bin_index, slot] = True
                k_values.append(len(distinct))
            print(f"CAPL_INIT modality={modality} bins={bin_sizes} k={k_values}")
        self.reset_epoch_stats()

    # ---------------- 训练期 EMA 更新 ----------------
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
            slot_valid = self._slot_valid_table(modality)
            counts = self._slot_counts(modality)
            used = self._epoch_used_table(modality, prototypes)

            for bin_index in range(self.n_bins):
                selected = valid_mask & (modality_labels == bin_index)
                if not selected.any():
                    continue
                active = slot_valid[bin_index]
                if not active.any():
                    continue
                members = modality_tokens[selected].detach().to(
                    device=prototypes.device, dtype=prototypes.dtype
                )
                bank = prototypes[bin_index]
                distances = torch.cdist(members, bank)
                distances = distances.masked_fill(
                    ~active.unsqueeze(0), float('inf')
                )
                assignment = distances.argmin(dim=1)
                sums = torch.zeros_like(bank)
                sums.index_add_(0, assignment, members)
                hits = torch.zeros(
                    self.proto_per_bin, device=bank.device, dtype=bank.dtype
                )
                hits.index_add_(
                    0, assignment, torch.ones_like(assignment, dtype=bank.dtype)
                )
                touched = hits > 0
                means = sums[touched] / hits[touched].unsqueeze(1)
                bank[touched] = bank[touched] * self.ema + means * (1.0 - self.ema)
                counts[bin_index] = counts[bin_index] + hits.long()
                used[bin_index] = used[bin_index] | touched

    # ---------------- 召回 ----------------
    def _attention(self, anchor_img_token, modality):
        if anchor_img_token.shape[-1] != self.dim:
            raise ValueError(
                f"anchor_img_token last dimension must be {self.dim}"
            )
        prototypes = self._prototype_table(modality).reshape(-1, self.dim)
        slot_valid = self._slot_valid_table(modality).reshape(-1)
        if not bool(slot_valid.any()):
            raise RuntimeError(
                f"CAPRecallMulti[{modality}] has no valid prototype slot; "
                "call init_prototypes before recall"
            )
        # 修订 v3：q/k 先 L2 归一，再乘 exp(可学习温度)；clamp 在 exp 之前，
        # 保证 logit_scale 取到极端值时前向有限、反向无 NaN。
        query = F.normalize(self.query[modality](anchor_img_token), dim=-1, eps=1e-8)
        keys = F.normalize(self.key[modality](prototypes), dim=-1, eps=1e-8)
        s_eff = self.logit_scale[modality].clamp(max=math.log(100.0))
        logits = torch.exp(s_eff) * (query @ keys.transpose(-1, -2))
        logits = logits.masked_fill(~slot_valid, float('-inf'))
        return torch.softmax(logits, dim=-1), prototypes, slot_valid

    def recall(self, anchor_img_token, modality):
        attention, prototypes, _ = self._attention(anchor_img_token, modality)
        recalled = attention @ prototypes
        return self.output[modality](recalled)

    @torch.no_grad()
    def recall_stats(self, anchor_img_token, modality):
        """epoch 末诊断：返回 (熵均值, 熵上界 ln(#valid), top1 均值, #valid, exp(s_eff))。

        修订 v3 追加第 5 项 ``exp(s_eff)``（生效温度），供 CAPL_STATS 打印。
        """
        attention, _, slot_valid = self._attention(anchor_img_token, modality)
        entropy = -(attention * attention.clamp_min(1e-12).log()).sum(dim=-1)
        top1 = attention.max(dim=-1).values
        n_valid = int(slot_valid.sum().item())
        s_eff = self.logit_scale[modality].clamp(max=math.log(100.0))
        scale = float(torch.exp(s_eff).item())
        return (
            float(entropy.mean().item()),
            float(math.log(n_valid)) if n_valid > 0 else 0.0,
            float(top1.mean().item()),
            n_valid,
            scale,
        )

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
                raise KeyError("CAPRecallMulti requires the img anchor token")

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


