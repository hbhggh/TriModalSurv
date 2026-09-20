"""冻结患者内 WSI 原型索引；返回同一 train 患者的投影前配对特征。"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

import numpy as np

MODALITIES = ('rna', 'text')
PROTOCOL_ID = 'patient-fixed-padmask-v2'
PADDING_STRATEGY = 'raw_nonzero_prefix; train_patient_equal_valid_mean; pair_intersection_cosine'


def validate_splits(splits: Mapping[str, Sequence[str]]) -> dict[str, tuple[str, ...]]:
    if set(splits) != {'train', 'valid', 'test'}:
        raise ValueError('split keys must be train/valid/test')
    result = {}
    seen = set()
    for split in ('train', 'valid', 'test'):
        ids = tuple(splits[split])
        if any(not isinstance(pid, str) or not pid.strip() for pid in ids):
            raise ValueError(f'invalid patient ID in split {split}')
        if len(set(ids)) != len(ids):
            raise ValueError(f'duplicate patient ID in split {split}')
        overlap = seen.intersection(ids)
        if overlap:
            raise ValueError(f'split overlap: {sorted(overlap)}')
        seen.update(ids)
        result[split] = tuple(sorted(ids))
    if not result['train']:
        raise ValueError('empty train split')
    return result


def _numeric(value, *, context, shape=None):
    array = np.asarray(value)
    if array.dtype.kind not in 'fiu' or array.ndim not in (1, 2):
        raise ValueError(f'{context}: expected numeric feature vector or matrix')
    if not array.size or not np.isfinite(array).all():
        raise ValueError(f'{context}: empty or nonfinite feature')
    if shape is not None and array.shape != tuple(shape):
        raise ValueError(f'{context}: shape {array.shape} != {tuple(shape)}')
    return array


def valid_row_mask(wsi, *, context, shape=None):
    """仅接受旧缓存的非零前缀+补零后缀；在去中心之前取 mask。"""
    array = _numeric(wsi, context=context, shape=shape)
    if array.ndim != 2 or array.shape[0] != 128:
        raise ValueError(f'{context}: expected 128 WSI rows')
    mask = ~np.all(array == 0, axis=1)
    count = int(np.count_nonzero(mask))
    if count == 0 or not np.array_equal(mask, np.arange(128) < count):
        raise ValueError(f'{context}: invalid zero/padding layout (need nonzero prefix)')
    mask.setflags(write=False)
    return mask


def masked_cosine(query, key, query_mask, key_mask):
    """固定行序，仅共同有效行进入分子和双方分母。"""
    q = _numeric(query, context='centered query')
    k = _numeric(key, context='centered key', shape=q.shape)
    if q.ndim != 2:
        raise ValueError('centered WSI must be a matrix')
    qm, km = np.asarray(query_mask), np.asarray(key_mask)
    if any(m.dtype != np.bool_ or m.shape != (q.shape[0],) for m in (qm, km)):
        raise ValueError('invalid row mask shape/dtype')
    common = qm & km
    if not common.any():
        raise ValueError('empty valid-row overlap')
    qv = q[common].astype(np.float64, copy=False).reshape(-1)
    kv = k[common].astype(np.float64, copy=False).reshape(-1)
    qnorm, knorm = np.linalg.norm(qv), np.linalg.norm(kv)
    if any(not np.isfinite(n) or n <= 1e-12 for n in (qnorm, knorm)):
        raise ValueError('invalid common-row centered norm')
    score = float(np.sum(qv * kv, dtype=np.float64) / (qnorm * knorm))
    if not np.isfinite(score):
        raise ValueError('nonfinite masked cosine')
    return score


class FixedPatientBank:
    """无模型参数、无更新接口；仅复制所声明 train 患者的真实可用特征。"""

    def __init__(self, cancer, splits, features, *, expected_shapes=None):
        self.cancer = str(cancer)
        self.splits = validate_splits(splits)
        self.patient_ids = self.splits['train']
        self._sets = {k: frozenset(v) for k, v in self.splits.items()}
        self._features = {mm: {} for mm in ('img', *MODALITIES)}
        self.shapes = dict(expected_shapes or {})
        row_masks = {}
        digest = hashlib.sha256()
        digest.update(json.dumps({'protocol': PROTOCOL_ID, 'cancer': self.cancer,
                                  'splits': self.splits}, sort_keys=True).encode())
        for mm in self._features:
            available = features.get(mm, {})
            for pid in self.patient_ids:
                raw = available.get(pid)
                if raw is None:
                    if mm == 'img':
                        raise ValueError(f'missing train WSI: {pid}')
                    continue
                array = _numeric(raw, context=f'{mm}/{pid}', shape=self.shapes.get(mm))
                if mm == 'img':
                    row_masks[pid] = valid_row_mask(array, context=pid)
                self.shapes.setdefault(mm, array.shape)
                copied = np.array(array, copy=True, order='C')
                copied.setflags(write=False)
                self._features[mm][pid] = copied
                digest.update(json.dumps([mm, pid, list(copied.shape), str(copied.dtype)]).encode())
                digest.update(copied.tobytes())
            if not self._features[mm]:
                raise ValueError(f'no genuinely available train {mm} candidates')
        self.row_masks = np.stack([row_masks[pid] for pid in self.patient_ids])
        self.row_masks.setflags(write=False)
        self.valid_row_counts = {pid: int(row_masks[pid].sum()) for pid in self.patient_ids}
        self.mean = np.mean([self._features['img'][pid][row_masks[pid]].mean(axis=0, dtype=np.float64)
                             for pid in self.patient_ids], axis=0, dtype=np.float64)
        self.mean.setflags(write=False)
        self.keys = np.stack([self._signature(self._features['img'][pid], pid)[0]
                              for pid in self.patient_ids])
        self.keys.setflags(write=False)
        self.means = {}
        for mm in MODALITIES:
            total = np.zeros(self.shapes[mm], dtype=np.float64)
            for value in self._features[mm].values():
                total += value
            total /= len(self._features[mm])
            total.setflags(write=False)
            self.means[mm] = total
        digest.update(PADDING_STRATEGY.encode())
        digest.update(self.mean.tobytes())
        digest.update(self.row_masks.tobytes())
        self.fingerprint = digest.hexdigest()
        self._lookup = {}  # 同一 query 的确定性结果跨 seed 复用；不保存被投影的特征。

    def _signature(self, wsi, patient_id):
        array = _numeric(wsi, context=f'img/{patient_id}', shape=self.shapes['img'])
        mask = valid_row_mask(array, context=patient_id, shape=self.shapes['img'])
        centered = np.zeros(array.shape, dtype=np.float64)
        centered[mask] = array[mask].astype(np.float64) - self.mean
        norm = np.linalg.norm(centered[mask].reshape(-1))
        if not np.isfinite(norm) or norm <= 1e-12:
            raise ValueError(f'{patient_id}: invalid centered norm {norm}')
        centered.setflags(write=False)
        return centered, mask

    def validate_query(self, patient_id, wsi, query_split='test'):
        if query_split not in self._sets or patient_id not in self._sets[query_split]:
            raise ValueError(f'{patient_id}: query not in declared {query_split} split')
        return self._signature(wsi, patient_id)

    def retrieve(self, patient_id, wsi, missing_modalities, *, query_split='test'):
        missing = tuple(mm for mm in MODALITIES if mm in missing_modalities)
        if not missing or set(missing_modalities) != set(missing):
            raise ValueError('retrieval requires rna and/or text')
        signature, mask = self.validate_query(patient_id, wsi, query_split)
        query_hash = hashlib.sha256(signature.tobytes() + mask.tobytes()).hexdigest()
        cache_key = (PROTOCOL_ID, self.fingerprint, query_split, patient_id, missing, query_hash)
        if cache_key not in self._lookup:
            candidates = [i for i, pid in enumerate(self.patient_ids)
                          if pid != patient_id and all(pid in self._features[mm] for mm in missing)]
            if not candidates:
                raise ValueError(f'{patient_id}: empty candidate set for {missing}')
            # 每个 pair 独立按固定维度求和，避免 query batch 改变 GEMM 舍入及 Top-1。
            scores = [masked_cosine(signature, self.keys[i], mask, self.row_masks[i]) for i in candidates]
            selected = int(np.argmax(scores))  # patient_ids 已排序，完全并列取最前。
            index = candidates[selected]
            self._lookup[cache_key] = (self.patient_ids[index], scores[selected], len(candidates),
                                      int(np.count_nonzero(mask & self.row_masks[index])))
        donor, score, count, common_count = self._lookup[cache_key]
        return {'donor_id': donor, 'similarity': score, 'candidate_count': count,
                'query_valid_rows': int(mask.sum()), 'donor_valid_rows': self.valid_row_counts[donor],
                'common_valid_rows': common_count, 'padding_strategy': PADDING_STRATEGY,
                'values': {mm: self._features[mm][donor].copy() for mm in missing}}

    def compensate(self, patient_ids, wsi, values, valids, arm, *, query_split='test'):
        if arm not in ('m0real', 'm1', 'retrieval'):
            raise ValueError(f'unknown arm: {arm}')
        ids = list(patient_ids)
        if len(ids) != len(set(ids)) or len(wsi) != len(ids):
            raise ValueError('duplicate patient ID or batch size mismatch')
        output, masks = {}, {}
        for mm in MODALITIES:
            array = np.asarray(values[mm])
            if array.shape != (len(ids), *self.shapes[mm]) or not np.isfinite(array).all():
                raise ValueError(f'{mm}: invalid batch feature shape or values')
            mask = np.asarray(valids[mm])
            if mask.shape != (len(ids),) or not np.isin(mask, [0, 1]).all():
                raise ValueError(f'{mm}: invalid valid mask')
            output[mm] = array.copy()
            masks[mm] = mask.astype(bool, copy=True)
        records = []
        for row, pid in enumerate(ids):
            _, row_mask = self.validate_query(pid, wsi[row], query_split)
            missing = tuple(mm for mm in MODALITIES if not masks[mm][row])
            record = {'patient_id': pid, 'original_valid': {mm: bool(masks[mm][row]) for mm in MODALITIES},
                      'donor_id': None, 'similarity': None, 'candidate_count': 0,
                      'query_valid_rows': int(row_mask.sum()), 'donor_valid_rows': None,
                      'common_valid_rows': None, 'padding_strategy': PADDING_STRATEGY}
            # [创新 I01-01] 投影前取同一患者的完整配对特征，保留原行序和补零。
            if missing and arm == 'retrieval':
                selected = self.retrieve(pid, wsi[row], missing, query_split=query_split)
                for mm in missing:
                    output[mm][row] = selected['values'][mm]
                    masks[mm][row] = True
                record.update({k: selected[k] for k in ('donor_id', 'similarity', 'candidate_count',
                                                       'donor_valid_rows', 'common_valid_rows')})
            elif missing and arm == 'm1':
                for mm in missing:
                    output[mm][row] = self.means[mm]
                    masks[mm][row] = True
            records.append(record)
        return output, masks, records

    def metadata(self):
        return {'protocol_id': PROTOCOL_ID, 'cancer': self.cancer, 'fingerprint': self.fingerprint,
                'train_ids': list(self.patient_ids), 'shapes': {k: list(v) for k,v in self.shapes.items()},
                'available_counts': {mm: len(self._features[mm]) for mm in MODALITIES},
                'both_available_count': len(set(self._features['rna']) & set(self._features['text'])),
                'centering': 'train patient-equal valid-row D mean; original row order', 'k': 128,
                'padding_strategy': PADDING_STRATEGY, 'valid_row_counts': self.valid_row_counts.copy(),
                'row_masks_sha256': hashlib.sha256(self.row_masks.tobytes()).hexdigest(),
                'centering_mean_sha256': hashlib.sha256(self.mean.tobytes()).hexdigest()}
