"""I08 Step 1 缓存：只导出 train/val、D0 守卫、manifest 绑定、往返一致。"""
import json

import numpy as np
import pytest
import torch

from experiments.I07_ps3style_backbone import data
from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.tests.test_train import small_model, write_assets
from experiments.I08_ps3_shared_recovery import cache
from experiments.I08_ps3_shared_recovery.contract import PATTERNS, VIEWS, visible


@pytest.fixture(scope='module')
def fold(tmp_path_factory):
    root = tmp_path_factory.mktemp('i08cache')
    write_assets(root)
    parts, meta = data.load_fold(root, 'BLCA', 0, parts=('train', 'val'))
    m = small_model()
    for p in m.parameters():
        p.requires_grad_(False)
    return m.eval(), parts, root


def test_export_contains_all_views_and_no_test(fold):
    m, parts, _ = fold
    arrays, d0 = cache.export_fold(m, parts)
    assert max(d0.values()) < cache.D0_TOL
    assert not [k for k in arrays if k.startswith('test')]
    for s in ('train', 'val'):
        for v in VIEWS:
            for mod in (MODALITIES if v == 'full' else visible(v)):
                assert arrays[f'{s}__p__{v}__{mod}'].shape == (len(parts[s]), m.d)
        assert list(arrays[f'{s}__patient_ids']) == parts[s].patient_ids
    t = cache.fold_tensors(arrays)
    # 缓存的 p^F 过风险头 = 缓存的 I07 完整风险（D0）
    head_in = torch.cat([t['val']['p']['full'][mod] for mod in MODALITIES], -1)
    assert float((head_in @ t['head_w'] + t['head_b'] - t['val']['risk_full']).abs().max()) < 1e-6


def test_export_rejects_test_split(fold):
    m, parts, root = fold
    allp, _ = data.load_fold(root, 'BLCA', 0)
    with pytest.raises(PermissionError):
        cache.export_fold(m, allp)                                # 含 test 即拒绝


def test_d0_guard_trips_on_nondeterminism(fold):
    m, parts, _ = fold
    m2 = small_model()
    m2.train()                                                  # dropout=0 但 AlphaDropout / Dropout 仍为 train 模式
    torch.nn.init.normal_(m2.risk.weight)
    for p in m2.parameters():
        p.requires_grad_(False)

    class Noisy(torch.nn.Module):                               # 每次前向加随机扰动：确定性守卫必须报错
        def __init__(self, base):
            super().__init__()
            self.base, self.d, self.risk = base, base.d, base.risk

        def forward(self, *a, **k):
            out = self.base(*a, **k)
            out['risk'] = out['risk'] + torch.rand_like(out['risk']) * 1e-3
            return out
    with pytest.raises(AssertionError):
        cache.export_fold(Noisy(m2.eval()), parts)


def test_roundtrip_and_manifest_binding(fold, tmp_path):
    m, parts, _ = fold
    arrays, _ = cache.export_fold(m, parts)
    blob = cache.npz_bytes(arrays)
    cache.write_atomic(tmp_path / cache.fold_name('BLCA', 0), blob)
    manifest = {'files': {cache.fold_name('BLCA', 0): {'sha256': cache.sha256(blob)}}}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    back = cache.load_fold_cache(tmp_path, 'BLCA', 0)
    assert all(np.array_equal(back[k], arrays[k]) for k in arrays)
    with pytest.raises(FileExistsError):
        cache.write_atomic(tmp_path / cache.fold_name('BLCA', 0), blob)          # 不覆盖
    manifest['files'][cache.fold_name('BLCA', 0)]['sha256'] = '0' * 64
    with pytest.raises(PermissionError):
        cache.load_fold_cache(tmp_path, 'BLCA', 0, manifest)


def test_registry_parses_repo_checkpoint_list():
    reg = cache.registered_ckpts()
    tri = [k for k in reg if k.endswith('/tri/best.pt')]
    assert len(tri) == 25 and all(len(v) == 64 for v in reg.values())
