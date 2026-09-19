"""I04 原初始化趟与 epoch 末诊断；只在调用方明确挂接后生效。"""
import torch
from torch.utils.data import DataLoader
from .model import CAPRecallMulti
from trimodalsurv.training.runtime import _unwrap_model, _model_compensator

def _capl_compensator(model):
    compensator = _model_compensator(model)
    return compensator if isinstance(compensator, CAPRecallMulti) else None


def _capl_pooled_tokens(projector, modality, raw, device, non_blocking=False):
    features = raw.to(device, dtype=torch.float, non_blocking=non_blocking)
    if features.dim() > 2:
        features = features.mean(dim=1)
    return projector[modality](features)


def init_capl_prototypes(model, train_dataset, seed, device, batch_size=None,
                         non_blocking=False):
    """训练前一次性 K-means 初始化（语义 2）：只读 train split，不更新任何参数。

    z 取自 ``{m}_orig``（存在时）的投影；真实存在判据为 ``{m}_valid | {m}_dropped``，
    即 modality dropout 人为置零的样本仍计入，天然缺失的样本排除。
    """
    compensator = _capl_compensator(model)
    if compensator is None:
        return None
    unwrapped = _unwrap_model(model)
    projector = unwrapped.m_projector
    loader = DataLoader(
        train_dataset,
        shuffle=False,
        batch_size=int(batch_size) if batch_size else 32,
        num_workers=0,
    )
    was_training = unwrapped.training
    unwrapped.eval()
    tokens = {modality: [] for modality in compensator.modalities}
    labels = {modality: [] for modality in compensator.modalities}
    try:
        with torch.no_grad():
            for dbatch in loader:
                bin_labels = dbatch['survival_months_bin'].reshape(-1).long()
                for modality in compensator.modalities:
                    if modality not in dbatch:
                        continue
                    valid = dbatch.get(f"{modality}_valid")
                    if valid is None:
                        continue
                    exists = valid.reshape(-1).bool()
                    dropped = dbatch.get(f"{modality}_dropped")
                    if dropped is not None:
                        exists = exists | dropped.reshape(-1).bool()
                    if not exists.any():
                        continue
                    raw = dbatch.get(f"{modality}_orig", dbatch[modality])
                    projected = _capl_pooled_tokens(
                        projector, modality, raw, device, non_blocking
                    )
                    selector = exists.to(projected.device)
                    tokens[modality].append(projected[selector].detach())
                    labels[modality].append(bin_labels[exists])
    finally:
        unwrapped.train(was_training)

    tokens_by_modality = {
        modality: torch.cat(chunks, dim=0)
        for modality, chunks in tokens.items() if chunks
    }
    labels_by_modality = {
        modality: torch.cat(chunks, dim=0)
        for modality, chunks in labels.items() if chunks
    }
    if not tokens_by_modality:
        raise RuntimeError('CAPL 初始化失败：train split 没有任何真实存在的 text/rna 样本')
    compensator.init_prototypes(tokens_by_modality, labels_by_modality, seed)
    return compensator


def print_capl_stats(model, loader, device, epoch, max_batches=8,
                     non_blocking=False):
    """epoch 末诊断（语义 7）：valid loader 前 max_batches 个 batch 的召回注意力统计。"""
    compensator = _capl_compensator(model)
    if compensator is None or loader is None:
        return
    unwrapped = _unwrap_model(model)
    projector = unwrapped.m_projector
    was_training = unwrapped.training
    unwrapped.eval()
    anchors = []
    try:
        with torch.no_grad():
            for index, dbatch in enumerate(loader):
                if index >= max_batches:
                    break
                if 'img' not in dbatch:
                    continue
                anchors.append(
                    _capl_pooled_tokens(
                        projector, 'img', dbatch['img'], device, non_blocking
                    ).detach()
                )
            if not anchors:
                return
            anchor = torch.cat(anchors, dim=0)
            for modality in compensator.modalities:
                entropy, entropy_max, top1, n_valid, scale = compensator.recall_stats(
                    anchor, modality
                )
                total = compensator.n_bins * compensator.proto_per_bin
                print(
                    f"CAPL_STATS epoch={epoch} modality={modality} "
                    f"attn_entropy_mean={entropy:.6f} attn_entropy_max={entropy_max:.6f} "
                    f"top1_share={top1:.6f} "
                    f"updated_slots={compensator.used_slots(modality)}/{total} "
                    f"valid_slots={n_valid} scale={scale:.6f}"
                )
    finally:
        unwrapped.train(was_training)


