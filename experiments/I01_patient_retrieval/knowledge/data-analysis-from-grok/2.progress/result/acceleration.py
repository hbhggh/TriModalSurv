"""仅计算实现加速；不改变检索候选域、特征或科研参数。"""
import numpy as np
import hashlib


def gpu_cosines(query, keys, *, device, epsilon, query_mask=None, key_masks=None):
    """候选维并行 float64 余弦；旧展平模式分子/双方范数共用交集 mask。"""
    import torch
    query = np.asarray(query)
    keys = np.asarray(keys)
    if query.ndim not in (1, 2) or keys.ndim != query.ndim + 1 or keys.shape[1:] != query.shape or not len(keys):
        raise ValueError('非法批量余弦形状或空候选')
    if not np.isfinite(query).all() or not np.isfinite(keys).all() or not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('非法数值或范数阈值')
    if (query_mask is None) != (key_masks is None):
        raise ValueError('双方 mask 必须同时提供')
    with torch.inference_mode():
        q = torch.as_tensor(query, dtype=torch.float64, device=device)
        k = torch.as_tensor(keys, dtype=torch.float64, device=device)
        if query_mask is not None:
            qm, km = np.asarray(query_mask), np.asarray(key_masks)
            if query.ndim != 2 or qm.dtype != np.bool_ or km.dtype != np.bool_ or qm.shape != query.shape[:1] or km.shape != keys.shape[:2]:
                raise ValueError('非法共同有效行 mask')
            common = qm[None] & km
            if not common.any(axis=1).all():
                raise ValueError('共同有效行为空')
            mask = torch.as_tensor(common, device=device)[:, :, None]
            q = torch.where(mask, q[None], 0.).flatten(1)
            k = torch.where(mask, k, 0.).flatten(1)
        else:
            q = q.reshape(1, -1)
            k = k.reshape(len(keys), -1)
        qnorm = torch.linalg.vector_norm(q, dim=1)
        knorm = torch.linalg.vector_norm(k, dim=1)
        if bool(((qnorm <= epsilon) | ~torch.isfinite(qnorm)).any()) or bool(((knorm <= epsilon) | ~torch.isfinite(knorm)).any()):
            raise ValueError('退化余弦范数')
        scores = ((q * k).sum(dim=1) / (qnorm * knorm)).cpu().numpy()
    if not np.isfinite(scores).all():
        raise ValueError('非有限余弦')
    return scores


class RetrievalCache:
    """每癌每 split 独立实例；固定打分跨 seed/λ/w/α 复用。

    GPU 并行计算后用一次 NumPy 原归约核验每个候选。选择使用原归约结果，
    避免 GPU 舍入把完全并列或近并列患者顺序改变；核验也缓存，不随网格重复。
    """
    def __init__(self, bank, *, device, epsilon):
        self.bank, self.device, self.epsilon = bank, device, epsilon
        self._scores, self._means = {}, {}
        self.score_builds = 0

    def _mean(self, modality, pid, mask=None):
        key = (modality, pid)
        if key not in self._means:
            value = self.bank._features[modality][pid]
            value = value if mask is None else value[mask]
            mean = value.astype(np.float64).mean(axis=0, dtype=np.float64)
            if modality == 'img':
                mean = mean - self.bank.mean
            self._means[key] = mean
        return self._means[key]

    def _scores_verified(self, query, keys, *, query_mask=None, key_masks=None):
        gpu = gpu_cosines(query, keys, device=self.device, epsilon=self.epsilon,
                          query_mask=query_mask, key_masks=key_masks)
        exact = []
        for index, key in enumerate(keys):
            if query_mask is not None:
                common = query_mask & key_masks[index]
                q, k = query[common].reshape(-1), key[common].reshape(-1)
            else:
                q, k = query.reshape(-1), key.reshape(-1)
            qn, kn = float(np.linalg.norm(q)), float(np.linalg.norm(k))
            if min(qn, kn) <= self.epsilon or not np.isfinite([qn, kn]).all():
                raise ValueError('参考归约退化范数')
            exact.append(float(np.sum(q * k, dtype=np.float64) / (qn * kn)))
        exact = np.asarray(exact, np.float64)
        # 仅验证计算后端误差，不作为科研选择容差；最终 argmax 用原精确归约。
        if not np.allclose(gpu, exact, atol=1e-12, rtol=0):
            raise ValueError('GPU 与原 float64 余弦不一致')
        return exact

    def custom_retrieve(self, patient_id, query_wsi, missing, *, query_split, enabled,
                        grid, query_rna, natural_rna, alpha, epsilon):
        bank = self.bank
        if epsilon != self.epsilon:
            raise ValueError('缓存范数阈值漂移')
        if not missing or set(missing) - {'rna', 'text'}:
            raise ValueError('非法目标模态')
        signature, mask = bank.validate_query(patient_id, query_wsi, query_split=query_split)
        meanpool = 2 in enabled
        joint = 4 in enabled and grid == 'text_100' and bool(natural_rna)
        if not np.isfinite(alpha) or alpha < 0:
            raise ValueError('非法联合相似度权重')
        digest = hashlib.sha256(np.asarray(query_wsi).tobytes() + mask.tobytes())
        if joint:
            rna = np.asarray(query_rna)
            if rna.shape != tuple(bank.shapes['rna']) or not np.isfinite(rna).all():
                raise ValueError('非法 query RNA')
            digest.update(rna.tobytes())
        cache_key = (bank.fingerprint, query_split, patient_id, tuple(sorted(missing)),
                     meanpool, joint, digest.hexdigest())
        if cache_key not in self._scores:
            candidates = [i for i, pid in enumerate(bank.patient_ids)
                          if pid != patient_id and all(pid in bank._features[m] for m in missing)
                          and (not joint or all(pid in bank._features[m] for m in ('rna', 'text')))]
            if not candidates:
                raise ValueError('空候选集合，禁止回退')
            if meanpool:
                query = np.asarray(query_wsi)[mask].astype(np.float64).mean(axis=0, dtype=np.float64) - bank.mean
                keys = np.stack([self._mean('img', bank.patient_ids[i], bank.row_masks[i]) for i in candidates])
                wsi_scores = self._scores_verified(query, keys)
            else:
                wsi_scores = self._scores_verified(signature, bank.keys[candidates],
                    query_mask=mask, key_masks=bank.row_masks[candidates])
            rna_scores = None
            if joint:
                query = np.asarray(query_rna).astype(np.float64).mean(axis=0, dtype=np.float64)
                keys = np.stack([self._mean('rna', bank.patient_ids[i]) for i in candidates])
                rna_scores = self._scores_verified(query, keys)
            self._scores[cache_key] = (candidates, wsi_scores, rna_scores)
            self.score_builds += 1
        candidates, wsi_scores, rna_scores = self._scores[cache_key]
        scores = wsi_scores if rna_scores is None else wsi_scores + float(alpha) * rna_scores
        selected = int(np.argmax(scores))
        index = candidates[selected]
        donor = bank.patient_ids[index]
        return {'donor_id': donor, 'similarity': float(scores[selected]),
                'score_wsi': float(wsi_scores[selected]),
                'score_rna': None if rna_scores is None else float(rna_scores[selected]),
                'candidate_count': len(candidates), 'query_valid_rows': int(mask.sum()),
                'donor_valid_rows': bank.valid_row_counts[donor],
                'common_valid_rows': int(np.count_nonzero(mask & bank.row_masks[index])),
                'padding_strategy': bank.metadata()['padding_strategy'],
                'values': {m: bank._features[m][donor].copy() for m in missing}}
