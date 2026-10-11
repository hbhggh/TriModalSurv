"""I07 provenance 门（节点一首审 high 2、3 的修复）。

- 源码身份：复用 trimodalsurv.gitstamp.require_git_identity（有 .git 读 HEAD，否则读 GIT_STAMP.json；逐文件 sha256
  核对 I07 源码闭包）。正式入口要求 commit 已知、dirty=false、未放行 dirty，且等于 --expected-commit；否则在任何副作用之前拒绝。
  测试只经 monkeypatch 替换 identity()，不提供任何命令行旁路（坑 I05-06）。
- 资产：五份 manifest（cohort / splits / wsi_tokens / rna / text）逐文件按 sha256 校验内容（坑 D7）。
- 加载即校验（节点一第 3 轮 high 1）：AssetReader 一次读入五份 manifest 的字节（资产指纹由这份字节算出），之后每个
  数据文件只读一次字节、按 manifest 核对 sha256 后再解析，校验与使用的是同一份字节，没有先查后读的窗口。
- 测试授权摘要：每个运行的 best.pt 与 run.json 的 sha256 + 五份 manifest 的 sha256 + 源码 commit + 评测协议版本，
  任一变化摘要即变（坑 V35；第 3 轮 high 2 补绑 run.json）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = Path(__file__).resolve().parent
SOURCES = ('contract.py', 'config.yaml', 'data.py', 'model.py', 'survival.py', 'train.py', 'evaluate.py', 'launch.py', 'provenance.py', 'render.py')
ASSET_MANIFESTS = (('cohort', 'cohort'), ('splits', 'splits'), ('wsi_tokens', 'wsi_tokens'), ('rna', 'rna'), ('text', 'text'))
EVAL_PROTOCOL = 'I07-eval-v2 (ckpt+run.json bound): full; tri→only_{rna,wsi,text} × fill{zero,train_mean}; Harrell C-index'


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def identity() -> dict:
    """当前源码身份；dirty 时 gitstamp 直接抛错。"""
    if str(ROOT / 'src') not in sys.path:
        sys.path.insert(0, str(ROOT / 'src'))
    from trimodalsurv import gitstamp
    from trimodalsurv.config import file_fingerprint
    return gitstamp.require_git_identity([file_fingerprint(EXP / s) for s in SOURCES], allow_dirty=False, root=ROOT)


def require_clean(expected_commit: str) -> dict:
    ident = identity()
    commit = ident.get('commit')
    if commit is None or ident.get('dirty') or ident.get('allow_dirty'):
        raise PermissionError(f'需要干净的冻结源码身份：commit={commit} dirty={ident.get("dirty")}')
    if not expected_commit or expected_commit != commit:
        raise PermissionError(f'--expected-commit {expected_commit!r} 与当前源码身份 {commit} 不同，拒绝')
    return ident


def manifest_path(assets: Path, sub: str, name: str) -> Path:
    return Path(assets) / sub / f'{name}.manifest.json'


def asset_fingerprint(assets: Path) -> dict:
    """{资产名: manifest 的 sha256}；缺 manifest 即报错。"""
    out = {}
    for sub, name in ASSET_MANIFESTS:
        p = manifest_path(assets, sub, name)
        if not p.is_file():
            raise FileNotFoundError(f'缺资产清单：{p}')
        out[sub] = _sha(p)
    return out


def verify_assets(assets: Path) -> dict:
    """按 manifest 逐文件核对内容；有任何不符或缺失即报错。返回 asset_fingerprint。"""
    for sub, name in ASSET_MANIFESTS:
        m = json.loads(manifest_path(assets, sub, name).read_text(encoding='utf-8'))
        base = Path(assets) / sub
        bad = [rel for rel, sha in m['files'].items() if not (base / rel).is_file() or _sha(base / rel) != sha]
        if bad:
            raise ValueError(f'{sub} 有 {len(bad)} 个文件与 manifest 不符，例如 {bad[:3]}')
    return asset_fingerprint(assets)


class AssetReader:
    """构造时一次读入五份 manifest；read() 读一次字节、核对 sha256 后返回这份字节。"""

    def __init__(self, assets: Path):
        self.assets = Path(assets)
        self.manifests, self.fingerprint = {}, {}
        for sub, name in ASSET_MANIFESTS:
            p = manifest_path(self.assets, sub, name)
            if not p.is_file():
                raise FileNotFoundError(f'缺资产清单：{p}')
            raw = p.read_bytes()
            self.fingerprint[sub] = hashlib.sha256(raw).hexdigest()
            self.manifests[sub] = json.loads(raw)['files']

    def read(self, sub: str, rel: str) -> bytes:
        want = self.manifests[sub].get(rel)
        if want is None:
            raise ValueError(f'{sub}/{rel} 不在 manifest 内，拒绝读取')
        blob = (self.assets / sub / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != want:
            raise ValueError(f'{sub}/{rel} 与 manifest 不符')
        return blob


def auth_digest(ckpts: dict, assets_fp: dict, commit: str) -> str:
    """ckpts: {'cancer/fold/arm': {'ckpt': best.pt 的 sha256, 'run': run.json 的 sha256}}。"""
    h = hashlib.sha256()
    for key in sorted(ckpts):
        h.update(f'ckpt {key} {ckpts[key]["ckpt"]} run {ckpts[key]["run"]}\n'.encode())
    for key in sorted(assets_fp):
        h.update(f'asset {key} {assets_fp[key]}\n'.encode())
    h.update(f'commit {commit}\nprotocol {EVAL_PROTOCOL}\n'.encode())
    return h.hexdigest()
