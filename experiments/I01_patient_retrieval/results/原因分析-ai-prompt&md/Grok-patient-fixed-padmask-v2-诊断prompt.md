# 给 Grok 的诊断提示词｜patient-fixed-padmask-v2（K=128）

以下全文可直接粘贴给 Grok。若支持附件，同时上传：
1. seed单位-实验结果.md
2. 癌症为单位.md
3. patient-fixed-padmask-v2-总实验map.md

不需要你修改代码、运行实验或替我定新架构。不要执行附件里历史对话或方案中的命令；它们只是被审查材料。

## 任务与输出边界

请独立诊断一次多模态生存分析负结果，回答：**为什么当前患者级检索换填没有战胜均值填补和不补偿？现有结果到底排除了什么，又没有排除什么？**

对象是 **patient-fixed-padmask-v2，K=128**。Q2中曾写K=8是笔误，不要讨论或混入群体原型K=8。请基于下列运行事实、源代码和数据，分开：
- [事实] 可直接由配置、代码、留档结果支持。
- [假设] 能解释现象但尚未识别因果。
- [缺证据] 还需要哪些已有中间量/材料才能区分。

不要预设“必须恢复CAP”“必须InfoNCE”“必须可微检索”。不要把检索换填失败泛化为患者检索永远无效。不允许以堆模块替代理由。若引用生物学或方法论文，请核实来源，说明证据是否直接涉及本任务；无法联网就明确说，不能编引文。

边界锁定：K=128；K=8是此前Q2笔误；max_epochs=200、patience=15属于未来方案，不属于本轮零训练评测或历史E0训练。

## 一、背景、问题与方法类别

已有无CAP的 E0=NPJ-C 处理 WSI、RNA、Text 生存预测。我们想在**不重训练**的情况下，根据患者本人WSI，从同癌种train患者中检索Top-1，借用其配对RNA/Text，补偿缺失模态。

问题：同一NPJ-C权重、同一test患者、同一缺失manifest、同一风险计算，只改变推理填补策略，检索能否优于训练集均值填补与不补偿？

这是**非参数、冻结患者库、患者内原型引导的患者级配对检索**。不是学习全局原型，不是K=8群体聚类，不是完整M³Surv复现。原型用于选择donor，取回的是donor的完整投影前目标特征。库无可训练参数，训练不读库，零训练评测，没有EMA、逐轮刷新、对比损失或检索损失。

## 二、实际配置：不要用未来计划替代历史

```yaml
protocol_id: patient-fixed-padmask-v2
cancers: [BLCA, BRCA, LGG, LUAD, UCEC]
seeds: [123, 132, 213, 231, 321]
arms: [retrieval, m1, m0real]
scenarios: [none, rna_100, text_100, both_100]
checkpoints: 25_existing_E0_NPJC
training_this_experiment: false
compensator: none
prototype_k: 128
donor_top_k: 1
wsi_shape: [128, 1536]
rna_shape: [2048, 256]
text_shape: [200, 768]
hidden_size: 256
transformer_layers: 1
attention_heads: 4
mlp_ratio: 4
survival_bins: 4
dropout_rate: 0.1
model_mode: eval
modality_order: [img, text, rna]
evaluation_batch_size: 32
forward_dtype: float32
similarity_dtype: float64
metric: cindex_B
```

这是正式源码常量/运行证据的重建摘要，不是声称历史使用过这一份YAML。
模型eval时dropout关闭，每臂严格加载同一权重。每模态 mean → Linear → ReLU → Dropout 后得到一个256维向量，加模态embedding，形成**3×256**的融合序列。128是WSI缓存行数，不是Transformer融合token数。

历史E0：
- 日志直接支持每癌5seed，共25次，epochs=50、batch32、lr=1e-4、modality_dropout=0；25份日志均跑满50轮。
- 未见早停证据；冻结源码固定轮数循环，与50轮日志相符。
- 9月15日修复前源码重建为 Adam、weight_decay=1、bf16、NLLSurvLoss(alpha=0,eps=1e-7)，无检索/对比损失。
- 同一源码路径显示历史valid按A风险选最佳checkpoint；本次评测使用B风险。**快照不是训练当时源码原件**，A选模/优化器等应标源码重建，不冒充训练时完整指纹。
- 后来讨论的200轮/patience15/统一B早停是未来方案，不属于这次实验。
- “没有人工模态dropout”不等于“所有训练患者都完整”：天然缺失仍存在。
- 当前权重及正式评测指纹核对成功；历史训练时没有留存权重SHA，只能做seed→路径→日志关联，不能声称完整密码学历史链。

## 三、数据适配与缺失协议

每癌单独训练/建库；所有seed共用该癌同一train/valid/test划分。没有跨癌donor。候选仅train，不用生存标签；query自身被排除，valid/test不入库/去中心统计。

| 癌种 | train/valid/test | test天然缺RNA/缺Text/双缺 | RNA/Text/双目标候选 |
| --- | --- | --- | --- |
| BLCA | 136/68/138 | 0/0/0 | 134/136/134 |
| BRCA | 383/192/383 | 1/36/1 | 383/352/352 |
| LGG | 166/83/166 | 0/3/0 | 166/162/162 |
| LUAD | 171/84/172 | 0/5/0 | 167/165/165 |
| UCEC | 197/99/198 | 1/8/0 | 195/188/187 |

天然缺失表的前两列各自包含双缺患者；第三列是交集，不是额外一组患者。

none仅表示无额外人工遮挡，天然缺失仍处理。单人工遮挡叠加天然缺失可能变成双缺，候选域按**实际需要补的模态集合**过滤。双缺从共同候选中选**一个donor**同时提供RNA/Text。

WSI缓存：患者patch足够则MiniBatchKMeans(128, random_state=42)，不足128则原patch后补零；不是每人都有128个真实中心。
补零：LGG train两位有效行124/75；BLCA test一位123，LGG test一位96；其余无此padding。

“原始RNA/Text”仅指投影前缓存embedding，不是raw测序数据/文本原文。当前材料没有完成文本内容来源、临床变量构成、生存信息可用时间或全套表示学习预训练数据审计。不要自行补成某种临床文本定义或断言有/无标签泄漏。

## 四、固定库 padmask-v2 的完整链条

1. 从原始WSI缓存识别全零尾部；先取有效行mask，后去中心。
2. 每train患者仅真实行取均值，再患者等权得到共享1536维μ；query和candidate均用同μ。
3. 检索副本真实行减μ，padding保持0；不改本人输入或donor value。
4. query/candidate相同位置有效行交集参与展平余弦，分子与双侧范数都限定交集。
5. 中心按各自缓存原顺序；**无中心排序、集合匹配或跨患者中心语义对齐**。
6. donor限同癌train且拥有实际缺失目标，ID排序，精确同分取首；空候选、错误shape、非有限、范数≤1e-12均报错，不回退均值。
7. Top-1取完整目标缓存；双缺同donor。
8. m0real保留全零占位且valid=false；m1和retrieval补后valid=true。
9. 原mean→projector→3模态Transformer→masked平均pooling→生存logits；无新增跨模态参数。
10. B风险：sigmoid(logits)，clamp到[1e-6,1−1e-6]，survival=cumprod(1−hazard)，risk=−sum(survival)，再算删失C-index。

注意：
- 模型本人的WSI仍按原128行mean，包括历史padding；padmask修复只作用于检索支路。
- 固定bank与模型seed无关，相同query和缺失集合各seed选同donor；seed不同的是底座权重。
- valid=true是融合mask，不是显式可靠性置信度1。
- retrieval与m1相比均开启目标模态，主要差别是填值；与m0real相比还改变有效模态集合、注意力输入及pooling分母。
- 独立K-means行序无跨患者对应保证，但不能未经分析就说展平余弦数学上必然无效，或必然“等同均值余弦加噪声”。

## 五、正式核心代码原文

下列源文件SHA与正式preflight相符，代码是原文节选，不是伪代码。文件路径供本地追溯；你不能访问我的本地路径时直接使用以下正文，不假装打开过。

### 补零识别与共同有效行余弦

来源：[model/patient_retrieval_bank.py，47–81 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/model/patient_retrieval_bank.py:47)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
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
```

### 患者等权去中心均值与目标模态均值

来源：[model/patient_retrieval_bank.py，116–130 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/model/patient_retrieval_bank.py:116)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
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
```

### 候选过滤、Top-1 与同 donor 取值

来源：[model/patient_retrieval_bank.py，154–178 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/model/patient_retrieval_bank.py:154)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python

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
```

### 原始批次：天然缺失、人工遮挡与全零占位

来源：[scripts/eval_patient_retrieval.py，120–133 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/scripts/eval_patient_retrieval.py:120)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
    def batch(self, ids, grid):
        if grid not in GRIDS or len(ids) != len(set(ids)) or not set(ids).issubset(self.ids):
            raise ValueError('非法 grid 或 batch 患者')
        raw = {'img': np.stack([self.features['img'][pid] for pid in ids]),
               'img_valid': np.ones(len(ids), dtype=bool)}
        natural = {}
        for mm in ('rna', 'text'):
            natural[mm] = np.array([self.features[mm].get(pid) is not None for pid in ids])
            valid = natural[mm] & (mm not in masked_modalities(grid))
            raw[mm + '_valid'] = valid
            raw[mm] = np.stack([np.asarray(self.features[mm][pid], dtype=np.float32) if valid[i]
                               else np.zeros(self.bank.shapes[mm], dtype=np.float32)
                               for i, pid in enumerate(ids)])
        return raw, natural
```

### 三臂补偿分叉：仅写入缺失位置

来源：[model/patient_retrieval_bank.py，179–215 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/model/patient_retrieval_bank.py:179)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
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
```

### 原 mean → projector 与 valid 标记

来源：[model/fusion_model.py，1140–1158 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/model/fusion_model.py:1140)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
        tokens = {}
        valids = {}
        for mm in self.m_projector.keys():
            x = all_modalities[mm]
            if x.dim() == 3:
                x = x.mean(dim=1)
            tokens[mm] = self.m_projector[mm](x)

            batch_size = tokens[mm].shape[0]
            if mm == 'img':
                valid = torch.ones(batch_size, device=tokens[mm].device)
            else:
                valid = all_modalities.get(
                    f"{mm}_valid",
                    torch.ones(batch_size, device=tokens[mm].device),
                )
            valids[mm] = torch.as_tensor(
                valid, device=tokens[mm].device
            ).reshape(batch_size).bool()
```

随后省略的 fusion_model.py 1160–1191 行是 compensator 分支，本轮 compensator=None，不进入；接着执行下面的融合代码。

### 三模态 token 融合与 valid mask

来源：[model/fusion_model.py，1193–1203 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/model/fusion_model.py:1193)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
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
```

### B 口径风险变换

来源：[scripts/eval_missing.py，138–147 行](/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/scripts/eval_missing.py:138)；以下为源文件原文节选，不是完整可独立运行的脚本。

```python
def dual_risk_from_logits(logits):
    """复现 A=raw cumprod 与 B=sigmoid+clamp cumprod 两种风险。"""
    import torch

    if not torch.is_tensor(logits) or logits.ndim != 2:
        raise ValueError("logits 必须是二维 torch.Tensor")
    risk_a = -torch.sum(torch.cumprod(1.0 - logits, dim=1), dim=1)
    hazards_b = torch.clamp(torch.sigmoid(logits), 1e-6, 1.0 - 1e-6)
    risk_b = -torch.sum(torch.cumprod(1.0 - hazards_b, dim=1), dim=1)
    return risk_a, risk_b
```


源码指纹：
- `model/patient_retrieval_bank.py`：`1a87fd04dc4ec87591421b76424aba60b0bb523a6849eae2dcc5a6b921663bb0`
- `model/fusion_model.py`：`03c4060232d2d18ca277205e5a3dc47a8e3617e930128c839b11402953a7a096`
- `scripts/eval_missing.py`：`e42d52c3a87e34ba77d293c61131046cff6bdeadf703c74dde3d2cf59f98ef93`
- `scripts/eval_patient_retrieval.py`：`76cf8f3e58703c4615910e8cc3457a6539e9feefc27dc937239ae89a57a334de`

## 六、已核验结果：B口径

按癌种×seed×场景等权宏平均，不按患者数加权。none按最终要求参与总排名；另列旧三人工缺失口径，不把二者混用。Δ分别为检索−均值与检索−不补偿，**不是检索减去两者之和**。

| 统计范围 | 检索 retrieval | 均值 m1 | 不补偿 m0real | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- |
| 四场景（含 none） | 0.628964 | <span style="color:#c62828"><strong>0.631825 ★</strong></span> | 0.630751 | -0.002861 | -0.001788 |
| 三人工缺失场景 | 0.618083 | <span style="color:#c62828"><strong>0.621349 ★</strong></span> | 0.620220 | -0.003266 | -0.002138 |

四场景100组：检索对m1为32胜/5平/63负，对m0real为37/5/58；三臂独胜17/39/39，并列5。
原三人工场景75组：检索对m1为28/0/47，对m0real为30/0/45。
并列5组均BLCA/none，该癌test138人全完整，无填补。

### 按癌种（含none）

| 癌种（含 none） | 检索 | 均值 | 不补偿 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- |
| BLCA | 0.570767 | 0.582191 | <span style="color:#c62828"><strong>0.583388 ★</strong></span> | -0.011424 | -0.012621 |
| BRCA | <span style="color:#c62828"><strong>0.656659 ★</strong></span> | 0.651172 | 0.656557 | +0.005487 | +0.000102 |
| LGG | 0.714976 | <span style="color:#c62828"><strong>0.722464 ★</strong></span> | 0.711525 | -0.007488 | +0.003451 |
| LUAD | 0.578457 | <span style="color:#c62828"><strong>0.587004 ★</strong></span> | 0.586206 | -0.008547 | -0.007748 |
| UCEC | <span style="color:#c62828"><strong>0.623959 ★</strong></span> | 0.616292 | 0.616081 | +0.007667 | +0.007879 |

### 按seed（含none）

| Seed（含 none） | 检索 | 均值 | 不补偿 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- |
| 123 | 0.630686 | <span style="color:#c62828"><strong>0.633197 ★</strong></span> | 0.632342 | -0.002511 | -0.001656 |
| 132 | 0.629121 | 0.636741 | <span style="color:#c62828"><strong>0.639414 ★</strong></span> | -0.007620 | -0.010293 |
| 213 | <span style="color:#c62828"><strong>0.621158 ★</strong></span> | 0.616466 | 0.613520 | +0.004692 | +0.007638 |
| 231 | 0.631430 | <span style="color:#c62828"><strong>0.639490 ★</strong></span> | 0.634074 | -0.008060 | -0.002644 |
| 321 | 0.632424 | 0.633229 | <span style="color:#c62828"><strong>0.634407 ★</strong></span> | -0.000806 | -0.001983 |

检索绝对成绩最高seed321；相对两基线增益最大seed213。绝对最高癌LGG，相对两基线增益最大癌UCEC。不能挑一个test表现最好的seed当总体正收益。

### 癌种×场景五seed均值

| 癌种 | 场景 | 检索 | 均值 | 不补偿 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- |
| BLCA | none | <span style="color:#c62828"><strong>0.589972 ★</strong></span> | <span style="color:#c62828"><strong>0.589972 ★</strong></span> | <span style="color:#c62828"><strong>0.589972 ★</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.589938 | 0.589105 | <span style="color:#c62828"><strong>0.593546 ★</strong></span> | +0.000833 | -0.003609 |
| BLCA | text_100 | 0.550069 | 0.574913 | <span style="color:#c62828"><strong>0.575989 ★</strong></span> | -0.024844 | -0.025920 |
| BLCA | both_100 | 0.553088 | <span style="color:#c62828"><strong>0.574774 ★</strong></span> | 0.574046 | -0.021686 | -0.020958 |
| BRCA | none | 0.687930 | 0.686068 | <span style="color:#c62828"><strong>0.691359 ★</strong></span> | +0.001862 | -0.003429 |
| BRCA | rna_100 | <span style="color:#c62828"><strong>0.685886 ★</strong></span> | 0.684751 | 0.683842 | +0.001135 | +0.002044 |
| BRCA | text_100 | 0.628545 | 0.619121 | <span style="color:#c62828"><strong>0.655002 ★</strong></span> | +0.009424 | -0.026456 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.624276 ★</strong></span> | 0.614750 | 0.596026 | +0.009527 | +0.028250 |
| LGG | none | 0.795997 | <span style="color:#c62828"><strong>0.799517 ★</strong></span> | 0.796825 | -0.003520 | -0.000828 |
| LGG | rna_100 | 0.782195 | <span style="color:#c62828"><strong>0.790959 ★</strong></span> | 0.767219 | -0.008765 | +0.014976 |
| LGG | text_100 | 0.651553 | 0.664113 | <span style="color:#c62828"><strong>0.705866 ★</strong></span> | -0.012560 | -0.054313 |
| LGG | both_100 | 0.630159 | <span style="color:#c62828"><strong>0.635266 ★</strong></span> | 0.576190 | -0.005107 | +0.053968 |
| LUAD | none | 0.583257 | <span style="color:#c62828"><strong>0.583819 ★</strong></span> | 0.582064 | -0.000562 | +0.001193 |
| LUAD | rna_100 | <span style="color:#c62828"><strong>0.581011 ★</strong></span> | 0.580239 | 0.580660 | +0.000772 | +0.000351 |
| LUAD | text_100 | 0.576027 | 0.595156 | <span style="color:#c62828"><strong>0.596630 ★</strong></span> | -0.019130 | -0.020604 |
| LUAD | both_100 | 0.573535 | <span style="color:#c62828"><strong>0.588803 ★</strong></span> | 0.585469 | -0.015269 | -0.011934 |
| UCEC | none | 0.650879 | <span style="color:#c62828"><strong>0.656888 ★</strong></span> | 0.651502 | -0.006009 | -0.000623 |
| UCEC | rna_100 | 0.650612 | <span style="color:#c62828"><strong>0.655464 ★</strong></span> | 0.647229 | -0.004852 | +0.003383 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.597596 ★</strong></span> | 0.577743 | 0.589272 | +0.019853 | +0.008324 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.596751 ★</strong></span> | 0.575072 | 0.576319 | +0.021678 | +0.020432 |

红★为该行三臂最高，非统计显著。完整逐seed值与sample SD见两份附件。

### 工程证据及限制

正式75个JSON、300 C-index完整；600个audit/预测文件SHA本轮重验一致。原独立验收留档300项B C-index复算PASS；本轮只是重聚合与哈希核验，没有再跑模型/患者级指标。
完整输入logits容差atol1e-6/rtol0，原最大差7.152557373046875e-7。none每癌每seed实际检查人数BLCA138/BRCA347/LGG163/LUAD167/UCEC189；三人工全遮挡格人数0、误差null，不能把未检查说成零误差。
工程PASS只能降低某些实现错误的可能性，不证明检索机制正确，也不排除未审计的上游数据问题。
五seed不是五个独立队列；没有预设显著性阈值，没有本次CI、IBS或校准结果，不得臆造显著性/临床收益。

## 七、希望你优先解答的问题

1. **联合分布不匹配**：跨患者RNA/Text换填可能偏离底座训练分布，但是否有证据将其称为OOD、更不能直接等同adversarial noise？m1是否只是较低方差估计，m0是否通过mask避开错误信息？哪些是合理假设，哪些需证据？
2. **检索几何与生物学信号要拆开**：失败可能来自原型行序不对齐/相似度几何，也可能是WSI本就不能充分预测目标模态的生存相关信息。怎样避免直接把两者都叫“生物学解耦”？跨模态对比学习是否是可选方案而非逻辑必需？
3. **融合输入与缺失模式**：为什么LGG/text_100很差，但LGG/both_100大幅优于不补偿却仍不如均值？为什么BRCA/text_100优于均值但低于不补偿？为什么UCEC在text和both都正向？说明你的解释如何同时容纳这些相反现象。
4. **患者内原型的作用**：当前原型只决定donor，value随后mean到单向量；复制完整序列不等于融合层保留其token级信息。此接口是否限制本方法能获得的收益？不能未经证据说必须改接口。
5. **单donor与均值的偏差—方差权衡**：检索需要提供多少有效条件信息才能抵消借用单患者特征的方差？不要求虚构数值阈值。
6. **历史训练口径**：A选模/B评测和无人工缺失训练能否解释整体表现，又是否足以解释三臂相对差异？区分共因与特定于retrieval的原因。
7. **证据边界**：哪些最重要的中间量尚未提供，例如donor频率、相似度/共同有效行分布、投影后value差异、风险排序翻转、训练与检索值分布？请列最少且能区分假设的信息，不泛列几十项。
8. 若讨论Gating、CAP/跨注意力、对齐或联合训练，请说明其解决的具体失败条件、成立前提与可能副作用；哪些无需改变、哪些只有在特定假设成立时才值得改变。不能从本轮结果推出“必须加”。

## 八、输出形式

中文，结论先行，不要打分卡，不要泛泛文献综述。

1. 当前主线：一句判定本轮事实能支持的声称；列不超过3个优先假设。
2. 主因链：一张简短逻辑链图，已知节点和假设节点分开。
3. 证据对照：每个假设列支持现象、反例/不能解释的现象、缺少的最小证据；机制名称不能代替证明。
4. 决策树：只表示“补齐哪类证据后才能保留/降级某解释”，不是擅自安排新实验。
5. 拍板前需确认：哪些科研边界需要用户决定。不要把待验证架构方案写成结论，不自动扩大seed/癌种或启动训练。

最后用一段话给出适合放在研究记录中的克制负结果总结。不要将“本协议总体不优”写成“所有检索方法已被证伪”。

附：本地证据入口为 patient-fixed-padmask-v2-总实验map.md；原始JSON在 legacy-tako-formal-20260915/raw/tako-formal/evidence/formal/。此提示词仅请求诊断，不授权外部上传患者级数据或执行代码。
