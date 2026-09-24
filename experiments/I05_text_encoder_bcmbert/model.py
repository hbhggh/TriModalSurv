"""I05 核心算子：冻结的 BioClinical ModernBERT 嵌入版，填 NPJ-C 的 Text 槽位。

槽位契约（已核，见研究计划书 5.1）：每人一个 float32 ``[200, 768]``，模型内先沿 token 维做
``mean(dim=1)``，再进 ``Linear(768, 256)``。本模块只做推理：
分词到固定 200 token（截断或右侧补齐，保留 [CLS]/[SEP]）→ 前向取 ``last_hidden_state`` →
按 ``attention_mask`` 对有效 token 求均值（模型自带的 mean-token 池化）→ 广播写入全部 200 行 → FP32。

方案 C（用户裁决 2026-09-24，Phase 0 发现旧特征 pad 位非零后改定）：NPJ-C 对 token 维做无 mask 的均值，
所以 200 行都等于有效 token 均值时，槽内均值恰为正确的 masked mean，短报告不再按“有效长度/200”缩小。

分词器和模型都可以注入，所以测试不依赖 transformers；真实后端由 :func:`load_backend` 按锁定的
revision 加载。本模块不训练、不微调，也不改 NPJ-C 的任何层。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

# 用户锁定（2026-09-23）：模型 ID 与 revision 一起锁死；配置必须与这里逐项相同。
MODEL_ID = 'NeuML/bioclinical-modernbert-base-embeddings'
REVISION = '048ad4491de0fb4e2695bfe4705da67caf4804b8'
BASE_MODEL_ID = 'thomas-sounack/BioClinical-ModernBERT-base'
MAX_LENGTH = 200
HIDDEN_SIZE = 768
ATTN_IMPLEMENTATION = 'eager'
MIN_TRANSFORMERS = (4, 48, 0)
# [CLS] + 至少一个正文 token + [SEP]
MIN_VALID_TOKENS = 3
PAD_ROWS = 'masked_mean_broadcast'


@dataclass(frozen=True)
class EncoderSpec:
    """冻结编码器的全部可变项；任何一项改变都算换了实验变量。"""

    model_id: str = MODEL_ID
    revision: str = REVISION
    max_length: int = MAX_LENGTH
    hidden_size: int = HIDDEN_SIZE
    attn_implementation: str = ATTN_IMPLEMENTATION

    def as_dict(self) -> dict:
        return asdict(self)


def spec_from_config(config: dict) -> EncoderSpec:
    """从 I05 config 读取编码器设置，并要求与本模块的锁定值逐项相同。"""
    section = config['text_encoder']
    spec = EncoderSpec(model_id=section['model_id'], revision=section['revision'],
                       max_length=int(section['max_length']), hidden_size=int(section['hidden_size']),
                       attn_implementation=section['attn_implementation'])
    if spec != EncoderSpec():
        raise ValueError(f'config.text_encoder 与 model.py 锁定值不一致: {spec} != {EncoderSpec()}')
    if section.get('pad_rows') != PAD_ROWS or section.get('padding_side') != 'right':
        raise ValueError(f'方案 C 要求右侧补齐且 pad_rows == {PAD_ROWS!r}')
    return spec


def _prefix_counts(mask: np.ndarray) -> np.ndarray:
    """attention_mask 必须是 0/1 且为右侧补齐的前缀形态（每行先 1 后 0）；返回每行有效 token 数。"""
    if not np.isin(mask, (0, 1)).all():
        raise ValueError('attention_mask 只能取 0/1')
    valid = mask.astype(bool)
    counts = valid.sum(axis=1)
    expected = np.arange(mask.shape[1])[None, :] < counts[:, None]
    if not np.array_equal(valid, expected):
        raise ValueError('attention_mask 不是右侧补齐的前缀形态')
    return counts


def masked_mean_broadcast(hidden, attention_mask) -> tuple[np.ndarray, np.ndarray]:
    """有效 token 的均值（float64 累加后转 float32）广播到全部 L 行；返回 (features[B, L, H], 有效 token 数)。

    pad 位置的隐藏状态完全不参与计算。
    """
    h = np.asarray(hidden)
    m = np.asarray(attention_mask)
    if h.ndim != 3 or m.ndim != 2 or h.shape[:2] != m.shape:
        raise ValueError(f'hidden {h.shape} 与 attention_mask {m.shape} 形状不匹配')
    counts = _prefix_counts(m)
    if (counts < MIN_VALID_TOKENS).any():
        raise ValueError(f'有效 token 数 < {MIN_VALID_TOKENS}')
    weights = m.astype(np.float64)[..., None]
    mean = ((h.astype(np.float64) * weights).sum(axis=1) / counts[:, None]).astype(np.float32)
    features = np.ascontiguousarray(np.repeat(mean[:, None, :], h.shape[1], axis=1))
    return features, counts


def check_feature(array, *, context: str, max_length: int = MAX_LENGTH, hidden_size: int = HIDDEN_SIZE) -> None:
    """写出前的逐人断言（坑 D6）：形状、dtype、有限值、非零，且 200 行逐位相同（方案 C 的广播形态）。"""
    if not isinstance(array, np.ndarray) or array.dtype != np.float32:
        raise ValueError(f'{context}: 必须是 float32 ndarray')
    if array.shape != (max_length, hidden_size):
        raise ValueError(f'{context}: 形状 {array.shape} != {(max_length, hidden_size)}')
    if not np.isfinite(array).all():
        raise ValueError(f'{context}: 含非有限值')
    if not np.any(array[0] != 0):
        raise ValueError(f'{context}: 均值向量全零')
    if not (array == array[0]).all():
        raise ValueError(f'{context}: 各行不相同，不是方案 C 的广播形态')


def transformers_version_ok(version: str) -> bool:
    parts = []
    for piece in str(version).split('.')[:3]:
        digits = ''.join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts) >= MIN_TRANSFORMERS


# [创新 I05-01] 冻结 BioClinical ModernBERT 嵌入版填 Text 槽位：本实验相对现有系统的唯一改动。
class FrozenTextEncoder:
    """把报告文本编码成方案 C 的 ``[200, 768]`` 特征（有效 token 均值广播到 200 行）；只做推理。"""

    def __init__(self, tokenizer, model, *, spec: EncoderSpec = EncoderSpec(), device: str = 'cpu',
                 batch_size: int = 16):
        if batch_size < 1:
            raise ValueError('batch_size 必须为正')
        self.tokenizer, self.model, self.spec = tokenizer, model, spec
        self.device, self.batch_size = device, int(batch_size)
        if getattr(self.tokenizer, 'padding_side', 'right') != 'right':
            raise ValueError('方案 C 要求 tokenizer.padding_side == "right"')
        if hasattr(self.model, 'eval'):
            self.model.eval()

    def token_lengths(self, texts: Sequence[str]) -> list[int]:
        """未截断时的 token 数（含特殊 token），只用于记录截断比例。"""
        encoded = self.tokenizer(list(texts), add_special_tokens=True, truncation=False, padding=False)
        return [len(ids) for ids in encoded['input_ids']]

    def encode(self, texts: Sequence[str]) -> list[np.ndarray]:
        return self.encode_with_counts(texts)[0]

    def encode_with_counts(self, texts: Sequence[str]) -> tuple[list[np.ndarray], list[int]]:
        """返回 (特征列表, 每人截断后的有效 token 数)。"""
        import torch

        texts = list(texts)
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError('报告文本必须是非空字符串')
        results: list[np.ndarray] = []
        valid_counts: list[int] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            encoded = self.tokenizer(batch, max_length=self.spec.max_length, truncation=True,
                                     padding='max_length', return_tensors='pt')
            ids, mask = encoded['input_ids'], encoded['attention_mask']
            if tuple(ids.shape) != (len(batch), self.spec.max_length):
                raise ValueError(f'分词输出形状 {tuple(ids.shape)} 不是 ({len(batch)}, {self.spec.max_length})')
            with torch.inference_mode():
                output = self.model(input_ids=ids.to(self.device), attention_mask=mask.to(self.device))
            hidden = output.last_hidden_state if hasattr(output, 'last_hidden_state') else output[0]
            hidden = hidden.detach().to('cpu', dtype=torch.float32).numpy()
            if hidden.shape != (len(batch), self.spec.max_length, self.spec.hidden_size):
                raise ValueError(f'last_hidden_state 形状 {hidden.shape} 不符')
            mask_np = mask.detach().cpu().numpy()
            features, counts = masked_mean_broadcast(hidden, mask_np)
            for offset in range(len(batch)):
                context = f'batch{start // self.batch_size}/item{offset}'
                check_feature(features[offset], context=context, max_length=self.spec.max_length,
                              hidden_size=self.spec.hidden_size)
                results.append(np.ascontiguousarray(features[offset]))
                valid_counts.append(int(counts[offset]))
        return results, valid_counts


def load_backend(spec: EncoderSpec = EncoderSpec(), *, device: str = 'cpu', cache_dir: str | None = None,
                 local_files_only: bool = False):
    """按锁定的 revision 下载或读取本地快照，返回 (tokenizer, model, snapshot_dir)。"""
    import torch
    import transformers
    from huggingface_hub import snapshot_download

    if not transformers_version_ok(transformers.__version__):
        raise RuntimeError(f'transformers {transformers.__version__} 低于 ModernBERT 要求的 4.48.0')
    snapshot = Path(snapshot_download(repo_id=spec.model_id, revision=spec.revision, cache_dir=cache_dir,
                                      local_files_only=local_files_only))
    if snapshot.name != spec.revision:
        raise RuntimeError(f'下载到的快照 {snapshot.name} 不是锁定的 revision {spec.revision}')
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(snapshot))
    tokenizer.padding_side = 'right'
    model = transformers.AutoModel.from_pretrained(str(snapshot), torch_dtype=torch.float32,
                                                   attn_implementation=spec.attn_implementation)
    if int(model.config.hidden_size) != spec.hidden_size:
        raise RuntimeError(f'hidden_size {model.config.hidden_size} != {spec.hidden_size}')
    model.to(device)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return tokenizer, model, snapshot


__all__ = ['MODEL_ID', 'REVISION', 'BASE_MODEL_ID', 'MAX_LENGTH', 'HIDDEN_SIZE', 'EncoderSpec',
           'spec_from_config', 'masked_mean_broadcast', 'check_feature', 'transformers_version_ok',
           'FrozenTextEncoder', 'load_backend']
