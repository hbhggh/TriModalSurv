"""NPJC 可选补偿分支所需的原始损失函数。"""
import torch
import torch.nn.functional as F

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

