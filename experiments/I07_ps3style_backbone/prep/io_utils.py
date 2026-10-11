"""I07 数据准备的公共工具：病人 ID 规范化、原子写入、sha256 与资产清单。"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np

CANCERS = ('BLCA', 'BRCA', 'LUAD', 'LGG', 'UCEC')


def norm_pid(raw: str) -> str:
    """统一为 TCGA 条码前 12 位（坑 D4）；不是 TCGA-XX-XXXX 形态就报错。"""
    pid = str(raw).strip().upper()[:12]
    parts = pid.split('-')
    if len(pid) != 12 or len(parts) != 3 or parts[0] != 'TCGA':
        raise ValueError(f'无法识别的病人 ID：{raw!r}')
    return pid


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _atomic(path: Path, write) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
    os.close(fd)
    try:
        write(Path(tmp))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    _atomic(path, lambda p: p.write_text(text, encoding='utf-8'))


def atomic_write_json(path: Path, obj) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def atomic_save_npz(path: Path, **arrays) -> None:
    def write(p: Path):
        with open(p, 'wb') as f:
            np.savez(f, **arrays)
    _atomic(path, write)


def require_new_dir(path: Path) -> Path:
    """输出目录必须不存在或为空，绝不覆盖已有资产。"""
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f'输出目录非空，拒绝覆盖：{path}')
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_manifest(out_dir: Path, name: str, params: dict) -> Path:
    """为 out_dir 下全部文件（除清单自身）记录 sha256，连同生成参数写入清单。"""
    out_dir = Path(out_dir)
    files = {}
    for p in sorted(out_dir.rglob('*')):
        if p.is_file() and not p.name.startswith('.') and p.name != f'{name}.manifest.json':
            files[str(p.relative_to(out_dir))] = sha256_file(p)
    path = out_dir / f'{name}.manifest.json'
    atomic_write_json(path, {'params': params, 'files': files})
    return path
