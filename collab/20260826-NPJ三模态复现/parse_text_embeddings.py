#!/usr/bin/env python3
"""parse_text_embeddings.py — 一次性修复脚本（Claude 编写，2026-08-26）

背景：作者 Drive 公开的 text_embeddings zip 中，每个 <pid>.pkl 反序列化后是
空格/换行分隔的字符串（恰好 200×768=153,600 个数），而骨架 loader
（loc_utils_3yr/tcga_dataset.py:464 np.array(data, dtype=np.float32)）期望
[L, 768] 数值数组，遇 str 直接 ValueError。

本脚本把 data/text_embeddings/ 下全部 pkl 解析为 float32 [200, 768]，
写入 data/text_embeddings_parsed/（不动原文件），末尾打印自检块。
"""
import glob
import os
import pickle
import random

import numpy as np

SRC = "data/text_embeddings"
DST = "data/text_embeddings_parsed"
os.makedirs(DST, exist_ok=True)

files = sorted(glob.glob(f"{SRC}/TCGA-*.pkl"))
bad = []
for i, p in enumerate(files):
    with open(p, "rb") as f:
        s = pickle.load(f)
    if isinstance(s, str):
        arr = np.array(s.split(), dtype=np.float32)
        if arr.size % 768 != 0:
            bad.append((p, f"size={arr.size}"))
            continue
        arr = arr.reshape(-1, 768)
    elif isinstance(s, np.ndarray):
        arr = s.astype(np.float32)  # 容错：万一有文件本来就是数组
    else:
        bad.append((p, type(s).__name__))
        continue
    with open(os.path.join(DST, os.path.basename(p)), "wb") as f:
        pickle.dump(arr, f, protocol=4)
    if (i + 1) % 500 == 0:
        print(f"  ... {i + 1}/{len(files)}", flush=True)

out = sorted(glob.glob(f"{DST}/TCGA-*.pkl"))
print("\n================ 自检 ================")
print(f"输入 pkl: {len(files)} | 输出 pkl: {len(out)} | 异常: {len(bad)}")
for p, why in bad[:10]:
    print("  BAD:", p, why)
random.seed(0)
shapes = set()
for p in random.sample(out, min(20, len(out))):
    with open(p, "rb") as f:
        a = pickle.load(f)
    shapes.add((tuple(a.shape), str(a.dtype)))
print("随机抽查 20 个的 (shape, dtype) 集合:", shapes)
print("期望：输出=输入、异常=0、集合仅 ((200, 768), 'float32')")
