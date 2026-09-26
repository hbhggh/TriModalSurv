"""I05 核心算子：冻结的 BioClinical ModernBERT 嵌入版，填 NPJ-C 的 Text 槽位。

槽位契约（已核，见研究计划书 5.1）：每人一个 float32 ``[200, 768]``，模型内先沿 token 维做
``mean(dim=1)``，再进 ``Linear(768, 256)``。本模块只做推理：
分词到固定 200 token（截断或右侧补齐，保留 [CLS]/[SEP]）→ 前向取 ``last_hidden_state`` →
按 ``attention_mask`` 对有效 token 求均值（模型自带的 mean-token 池化）→ 广播写入全部 200 行 → FP32。

方案 C（用户裁决 2026-09-24，Phase 0 发现旧特征 pad 位非零后改定）：NPJ-C 对 token 维做无 mask 的均值，
所以 200 行都等于有效 token 均值时，槽内均值恰为正确的 masked mean，短报告不再按“有效长度/200”缩小。

分词器和模型都可以注入，所以测试不依赖 transformers；真实后端由 :func:`load_backend` 按锁定的
revision 加载。本模块不训练、不微调，也不改 NPJ-C 的任何层。

两个档案（config.text_encoders）：``bcmbert200`` 截断或补齐到 200 token（轮 C）；``bcmbert8192``（A0，
用户裁决 2026-09-24）全文不截断（≤ 8192 token）、逐份单样本、不补齐。两者都广播回槽位的 200 行，
所以“分词长度”（随档案）与“槽位行数”（``SLOT_ROWS``，恒为 200）是两个量。
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
# bcmbert200 档案的分词长度；audit 也用它统计"旧 200 行口径"。槽位行数是另一个量，见 SLOT_ROWS。
MAX_LENGTH = 200
# NPJ-C Text 槽位的行数，必须等于 config.shapes.text[0]；与分词长度无关。
SLOT_ROWS = 200
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
    # 分词器实际使用的补齐与截断策略（bcmbert200 的历史 manifest 已按同名同值记录这两项）
    padding: str = 'max_length'
    truncation: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


# 按档案的锁表：config.text_encoders[profile] 必须与这里逐项相同。batch_size 单独锁，因为它不改变
# 单个样本的数学定义（B=1 时无补齐），但决定 'longest' 补齐的批次组成，影响浮点复现。
LOCKED_SPECS = {
    'bcmbert200': EncoderSpec(),
    'bcmbert8192': EncoderSpec(max_length=8192, padding='longest', truncation=False),
    # I06 A1（用户裁决 2026-09-26，v3.12 解开 200 上限）：规格与 bcmbert8192（B2）逐项相同——全长不截断、逐份单样本，
    # 只把文本来源换成 LLM 浓缩后冻结的文本；A1 与 B2 的唯一差别是文本内容
    'a1struct': EncoderSpec(max_length=8192, padding='longest', truncation=False),
    'a1summ': EncoderSpec(max_length=8192, padding='longest', truncation=False),
}
LOCKED_BATCH_SIZE = {'bcmbert200': 16, 'bcmbert8192': 1, 'a1struct': 1, 'a1summ': 1,
                     'a2struct': 1, 'a2summ': 1}

# I06 A2（用户裁决 2026-09-26）：冻结的 Qwen3-Embedding-0.6B。官方模型卡（2026-09-26 核对）：
# 默认 1024 维、支持 32–1024 自定义维度（MRL），last-token 池化，Apache 2.0，需 transformers ≥ 4.51。
QWEN_MODEL_ID = 'Qwen/Qwen3-Embedding-0.6B'
QWEN_REVISION = '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'
QWEN_MIN_TRANSFORMERS = (4, 51, 0)
QWEN_PAD_ROWS = 'last_token_mrl_l2_broadcast'


@dataclass(frozen=True)
class QwenSpec:
    """Qwen 编码的全部可变项：逐份单样本（不补齐、不截断），取最后一个 token，截前 output_dim 维后 L2 归一化。"""

    model_id: str = QWEN_MODEL_ID
    revision: str = QWEN_REVISION
    max_length: int = 512
    hidden_size: int = 1024
    output_dim: int = HIDDEN_SIZE
    attn_implementation: str = ATTN_IMPLEMENTATION
    padding: str = 'none'
    truncation: bool = False
    pooling: str = 'last_token'
    normalize: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


LOCKED_QWEN_SPECS = {'a2struct': QwenSpec(max_length=8192), 'a2summ': QwenSpec(max_length=8192)}  # v3.12：全长不截断
ALL_PROFILES = tuple(LOCKED_SPECS) + tuple(LOCKED_QWEN_SPECS)


def _qwen_spec_from_config(config: dict, profile: str) -> QwenSpec:
    section = config['text_encoders'][profile]
    spec = QwenSpec(model_id=section['model_id'], revision=section['revision'], max_length=int(section['max_length']),
                    hidden_size=int(section['hidden_size']), output_dim=int(section['output_dim']),
                    attn_implementation=section['attn_implementation'], padding=section['padding'],
                    truncation=bool(section['truncation']), pooling=section['pooling'],
                    normalize=bool(section['normalize']))
    if spec != LOCKED_QWEN_SPECS[profile]:
        raise ValueError(f'config.text_encoders.{profile} 与 model.py 锁定值不一致: {spec} != {LOCKED_QWEN_SPECS[profile]}')
    if section.get('pad_rows') != QWEN_PAD_ROWS:
        raise ValueError(f'{profile} 的 pad_rows 必须是 {QWEN_PAD_ROWS!r}')
    if int(section.get('batch_size', -1)) != LOCKED_BATCH_SIZE[profile]:
        raise ValueError(f'{profile} 的 batch_size 必须是 {LOCKED_BATCH_SIZE[profile]}')
    if list(config['shapes']['text']) != [SLOT_ROWS, spec.output_dim]:
        raise ValueError(f"config.shapes.text {config['shapes']['text']} 与槽位 [{SLOT_ROWS}, {spec.output_dim}] 不符")
    return spec


def spec_from_config(config: dict, profile: str):
    """从 I05 config 读取某个档案的编码器设置，并要求与本模块的锁表逐项相同。"""
    if profile in LOCKED_QWEN_SPECS:
        return _qwen_spec_from_config(config, profile)
    if profile not in LOCKED_SPECS:
        raise ValueError(f'未知的特征档案 {profile!r}；可选 {sorted(LOCKED_SPECS)}')
    section = config['text_encoders'][profile]
    spec = EncoderSpec(model_id=section['model_id'], revision=section['revision'],
                       max_length=int(section['max_length']), hidden_size=int(section['hidden_size']),
                       attn_implementation=section['attn_implementation'], padding=section['padding'],
                       truncation=bool(section['truncation']))
    if spec != LOCKED_SPECS[profile]:
        raise ValueError(f'config.text_encoders.{profile} 与 model.py 锁定值不一致: {spec} != {LOCKED_SPECS[profile]}')
    if section.get('pad_rows') != PAD_ROWS or section.get('padding_side') != 'right':
        raise ValueError(f'方案 C 要求右侧补齐且 pad_rows == {PAD_ROWS!r}')
    if int(section.get('batch_size', -1)) != LOCKED_BATCH_SIZE[profile]:
        raise ValueError(f'{profile} 的 batch_size 必须是 {LOCKED_BATCH_SIZE[profile]}')
    if list(config['shapes']['text']) != [SLOT_ROWS, spec.hidden_size]:
        raise ValueError(f"config.shapes.text {config['shapes']['text']} 与槽位 [{SLOT_ROWS}, {spec.hidden_size}] 不符")
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


def masked_mean_broadcast(hidden, attention_mask, *, rows: int = SLOT_ROWS) -> tuple[np.ndarray, np.ndarray]:
    """有效 token 的均值（float64 累加后转 float32）广播到槽位的 ``rows`` 行；返回 (features[B, rows, H], 有效 token 数)。

    pad 位置的隐藏状态完全不参与计算。广播行数与分词序列长度 L 无关（A0 下 L 可达数千）。
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
    features = np.ascontiguousarray(np.repeat(mean[:, None, :], int(rows), axis=1))
    return features, counts


def check_feature(array, *, context: str, rows: int = SLOT_ROWS, hidden_size: int = HIDDEN_SIZE) -> None:
    """写出前的逐人断言（坑 D6）：形状 ``[rows, hidden]``、dtype、有限值、非零，且各行逐位相同（广播形态）。"""
    if not isinstance(array, np.ndarray) or array.dtype != np.float32:
        raise ValueError(f'{context}: 必须是 float32 ndarray')
    if array.shape != (rows, hidden_size):
        raise ValueError(f'{context}: 形状 {array.shape} != {(rows, hidden_size)}')
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
                 batch_size: int = 16, rows: int = SLOT_ROWS):
        if batch_size < 1:
            raise ValueError('batch_size 必须为正')
        if spec.padding not in ('max_length', 'longest'):
            raise ValueError(f'不支持的 padding 策略 {spec.padding!r}')
        self.tokenizer, self.model, self.spec = tokenizer, model, spec
        self.device, self.batch_size, self.rows = device, int(batch_size), int(rows)
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
        """返回 (特征列表, 每人进入编码器的有效 token 数)。"""
        import torch

        texts = list(texts)
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError('报告文本必须是非空字符串')
        results: list[np.ndarray] = []
        valid_counts: list[int] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            encoded = self.tokenizer(batch, max_length=self.spec.max_length, truncation=self.spec.truncation,
                                     padding=self.spec.padding, return_tensors='pt')
            ids, mask = encoded['input_ids'], encoded['attention_mask']
            if ids.ndim != 2 or ids.shape[0] != len(batch):
                raise ValueError(f'分词输出形状 {tuple(ids.shape)} 与批大小 {len(batch)} 不符')
            if self.spec.padding == 'max_length' and ids.shape[1] != self.spec.max_length:
                raise ValueError(f'分词输出形状 {tuple(ids.shape)} 不是 ({len(batch)}, {self.spec.max_length})')
            if ids.shape[1] > self.spec.max_length:
                # 不截断的档案：超过模型上限就失败，而不是静默截断（"全文"承诺的硬门）
                raise ValueError(f'报告长 {ids.shape[1]} token，超过上限 {self.spec.max_length}，拒绝截断')
            with torch.inference_mode():
                output = self.model(input_ids=ids.to(self.device), attention_mask=mask.to(self.device))
            hidden = output.last_hidden_state if hasattr(output, 'last_hidden_state') else output[0]
            hidden = hidden.detach().to('cpu', dtype=torch.float32).numpy()
            if hidden.shape != (len(batch), ids.shape[1], self.spec.hidden_size):
                raise ValueError(f'last_hidden_state 形状 {hidden.shape} 不符')
            mask_np = mask.detach().cpu().numpy()
            features, counts = masked_mean_broadcast(hidden, mask_np, rows=self.rows)
            for offset in range(len(batch)):
                context = f'batch{start // self.batch_size}/item{offset}'
                check_feature(features[offset], context=context, rows=self.rows, hidden_size=self.spec.hidden_size)
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


def last_token_mrl_l2(hidden, *, output_dim: int) -> np.ndarray:
    """单样本（不补齐）的 last-token 池化：取最后一个 token 的隐状态，截前 output_dim 维（MRL），L2 归一化。"""
    h = np.asarray(hidden)
    if h.ndim != 3 or h.shape[0] != 1:
        raise ValueError(f'last-token 池化只接受单样本 hidden [1, L, H]，实际 {h.shape}')
    if h.shape[2] < output_dim:
        raise ValueError(f'hidden 维度 {h.shape[2]} < output_dim {output_dim}')
    vector = h[0, -1, :output_dim].astype(np.float64)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError('last-token 向量范数为 0 或非有限')
    return (vector / norm).astype(np.float32)


class QwenTextEncoder:
    """冻结 Qwen3-Embedding：逐份单样本编码（无补齐、不截断），last-token → 截 768 维 → L2 归一化 → 广播 200 行。"""

    def __init__(self, tokenizer, model, *, spec: QwenSpec = QwenSpec(), device: str = 'cpu', rows: int = SLOT_ROWS):
        self.tokenizer, self.model, self.spec = tokenizer, model, spec
        self.device, self.rows = device, int(rows)
        if hasattr(self.model, 'eval'):
            self.model.eval()

    def token_lengths(self, texts: Sequence[str]) -> list[int]:
        return [len(self.tokenizer([text], truncation=False, padding=False)['input_ids'][0]) for text in texts]

    def encode_with_counts(self, texts: Sequence[str]) -> tuple[list[np.ndarray], list[int]]:
        import torch

        results, counts = [], []
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError('报告文本必须是非空字符串')
            encoded = self.tokenizer([text], truncation=False, padding=False, return_tensors='pt')
            ids, mask = encoded['input_ids'], encoded['attention_mask']
            if ids.ndim != 2 or ids.shape[0] != 1 or not bool(mask.all()):
                raise ValueError('Qwen 编码必须是单样本且无补齐')
            if ids.shape[1] > self.spec.max_length:
                raise ValueError(f'文本长 {ids.shape[1]} token，超过上限 {self.spec.max_length}，拒绝截断')
            with torch.inference_mode():
                output = self.model(input_ids=ids.to(self.device), attention_mask=mask.to(self.device))
            hidden = output.last_hidden_state if hasattr(output, 'last_hidden_state') else output[0]
            hidden = hidden.detach().to('cpu', dtype=torch.float32).numpy()
            if hidden.shape != (1, ids.shape[1], self.spec.hidden_size):
                raise ValueError(f'last_hidden_state 形状 {hidden.shape} 不符')
            vector = last_token_mrl_l2(hidden, output_dim=self.spec.output_dim)
            feature = np.ascontiguousarray(np.repeat(vector[None, :], self.rows, axis=0))
            check_feature(feature, context=f'item{index}', rows=self.rows, hidden_size=self.spec.output_dim)
            results.append(feature)
            counts.append(int(ids.shape[1]))
        return results, counts

    def encode(self, texts: Sequence[str]) -> list[np.ndarray]:
        return self.encode_with_counts(texts)[0]


def load_qwen_backend(spec: QwenSpec = QwenSpec(), *, device: str = 'cpu', cache_dir: str | None = None,
                      local_files_only: bool = False):
    """按锁定的 revision 读取 Qwen3-Embedding 快照，返回 (tokenizer, model, snapshot_dir)；FP32 推理、冻结参数。"""
    import torch
    import transformers
    from huggingface_hub import snapshot_download

    version = tuple(int(''.join(ch for ch in piece if ch.isdigit()) or 0)
                    for piece in (transformers.__version__.split('.') + ['0', '0'])[:3])
    if version < QWEN_MIN_TRANSFORMERS:
        raise RuntimeError(f'transformers {transformers.__version__} 低于 Qwen3 要求的 4.51.0（需单独环境）')
    snapshot = Path(snapshot_download(repo_id=spec.model_id, revision=spec.revision, cache_dir=cache_dir,
                                      local_files_only=local_files_only))
    if snapshot.name != spec.revision:
        raise RuntimeError(f'下载到的快照 {snapshot.name} 不是锁定的 revision {spec.revision}')
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(snapshot))
    model = transformers.AutoModel.from_pretrained(str(snapshot), torch_dtype=torch.float32,
                                                   attn_implementation=spec.attn_implementation)
    if int(model.config.hidden_size) != spec.hidden_size:
        raise RuntimeError(f'hidden_size {model.config.hidden_size} != {spec.hidden_size}')
    model.to(device)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return tokenizer, model, snapshot


def build_encoder(profile: str, spec, tokenizer, model, *, device: str, batch_size: int):
    """按档案类型构造编码器：NeuML 档案用 FrozenTextEncoder，Qwen 档案用 QwenTextEncoder。"""
    if profile in LOCKED_QWEN_SPECS:
        return QwenTextEncoder(tokenizer, model, spec=spec, device=device, rows=SLOT_ROWS)
    return FrozenTextEncoder(tokenizer, model, spec=spec, device=device, batch_size=batch_size, rows=SLOT_ROWS)


def output_dim(spec) -> int:
    return spec.output_dim if isinstance(spec, QwenSpec) else spec.hidden_size


__all__ = ['MODEL_ID', 'REVISION', 'BASE_MODEL_ID', 'MAX_LENGTH', 'SLOT_ROWS', 'HIDDEN_SIZE', 'EncoderSpec',
           'LOCKED_SPECS', 'LOCKED_BATCH_SIZE', 'spec_from_config', 'masked_mean_broadcast', 'check_feature', 'transformers_version_ok',
           'FrozenTextEncoder', 'load_backend', 'QwenSpec', 'LOCKED_QWEN_SPECS', 'ALL_PROFILES', 'QwenTextEncoder',
           'load_qwen_backend', 'last_token_mrl_l2', 'build_encoder', 'output_dim']
