"""测试用的最小分词器与编码器替身：只实现方案 A 用到的接口，不依赖 transformers。"""
from types import SimpleNamespace

import numpy as np

CLS, SEP, PAD = 1, 2, 0


def word_id(word: str) -> int:
    return sum(map(ord, word)) % 997 + 3


class FakeTokenizer:
    padding_side = 'right'

    def __call__(self, texts, *, add_special_tokens=True, truncation=False, padding=False, max_length=None,
                 return_tensors=None):
        sequences = []
        for text in texts:
            body = [word_id(word) for word in text.split()]
            if truncation and max_length is not None:
                body = body[:max_length - 2]
            sequences.append([CLS, *body, SEP] if add_special_tokens else body)
        if padding == 'max_length':
            masks = [[1] * len(ids) + [0] * (max_length - len(ids)) for ids in sequences]
            sequences = [ids + [PAD] * (max_length - len(ids)) for ids in sequences]
        else:
            masks = [[1] * len(ids) for ids in sequences]
        if return_tensors == 'pt':
            import torch
            return {'input_ids': torch.tensor(sequences, dtype=torch.long),
                    'attention_mask': torch.tensor(masks, dtype=torch.long)}
        return {'input_ids': sequences, 'attention_mask': masks}


class FakeModel:
    """查表式编码器：pad 位置也输出非零值，用来检验置零逻辑。"""

    def __init__(self, hidden_size=768, vocab=1000, seed=0):
        rng = np.random.default_rng(seed)
        self.table = rng.normal(size=(vocab, hidden_size)).astype(np.float32) + 0.5
        self.eval_called = False

    def eval(self):
        self.eval_called = True
        return self

    def __call__(self, *, input_ids, attention_mask):
        import torch
        hidden = torch.from_numpy(self.table[input_ids.cpu().numpy()])
        return SimpleNamespace(last_hidden_state=hidden)
