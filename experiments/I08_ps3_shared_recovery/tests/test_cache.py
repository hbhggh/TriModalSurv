"""I08 Step 1 缓存：只导出 train/val、D0 守卫、manifest 绑定、往返一致。"""
import io
import json

import numpy as np
import pytest
import torch

from experiments.I07_ps3style_backbone import data, provenance
from experiments.I07_ps3style_backbone.model import MODALITIES
from experiments.I07_ps3style_backbone.tests.test_train import small_model, write_assets
from experiments.I08_ps3_shared_recovery import cache
from experiments.I08_ps3_shared_recovery.contract import PATTERNS, VIEWS, visible


@pytest.fixture(scope='module')
def fold(tmp_path_factory):
    root = tmp_path_factory.mktemp('i08cache')
    write_assets(root)
    reader = cache.TrainValReader(provenance.AssetReader(root), 'BLCA', 0)
    parts, meta = data.load_fold(root, 'BLCA', 0, parts=('train', 'val'), reader=reader)
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


def test_registry_module_matches_repo_files():
    """i07_registry（受身份门保护的 .py）与仓库内 checkpoint-sha256.txt、run.json 逐项一致。"""
    from experiments.I08_ps3_shared_recovery import i07_registry
    reg = cache.registered_ckpts()
    tri = {k: v for k, v in reg.items() if k.endswith('/tri/best.pt')}
    assert set(tri) == set(i07_registry.TRI) and len(tri) == 25
    runs = cache.CKPT_LIST.parent / 'runs'
    for rel, (ck, rn) in i07_registry.TRI.items():
        assert tri[rel] == ck
        assert cache.sha256((runs / rel.replace('best.pt', 'run.json')).read_bytes()) == rn
    srcs = {p.name for p in cache.SOURCES}
    for rel in i07_registry.TRI:
        run = json.loads((runs / rel.replace('best.pt', 'run.json')).read_bytes())
        assert run['assets_fp'] == i07_registry.ASSETS_FP
    assert 'i07_registry.py' in srcs and all(p.suffix in ('.py', '.yaml') for p in cache.SOURCES)  # GIT_STAMP 覆盖的后缀


def test_trainval_reader_never_hands_test_rows_to_loader(tmp_path):
    """load_fold 经代理拿到的所有字节里没有 test 患者；test 的 WSI 文件被拒读；结果与原路径逐值相同。"""
    write_assets(tmp_path)
    full = provenance.AssetReader(tmp_path)
    test_ids = {r['patient_id'] for r in data.csv_rows(full.read('splits', 'splits.csv')) if r['part'] == 'test'}
    assert test_ids

    class Spy(cache.TrainValReader):
        def read(self, sub, rel):
            blob = super().read(sub, rel)
            self.blobs.append(blob)
            return blob
    spy = Spy(provenance.AssetReader(tmp_path), 'BLCA', 0)
    spy.blobs = []
    parts, _ = data.load_fold(tmp_path, 'BLCA', 0, parts=('train', 'val'), reader=spy)
    fp = data.fold_parts(full, 'BLCA', 0)
    parts_ids = fp['train'] + fp['val']
    allowed = set(parts_ids)
    n_npz = 0
    for (sub, rel), blob in zip(spy.reads, spy.blobs):
        if rel.endswith('.npz') and sub in ('rna', 'text'):              # npz 里的 id 是 UTF-32，必须解析后核对
            with np.load(io.BytesIO(blob)) as z:
                ids = {str(x) for x in z['patient_ids']}
                assert ids == allowed, (sub, rel)
                assert z['X' if 'X' in z.files else 'emb'].shape[0] == len(allowed)      # 特征行也只剩 train/val
            n_npz += 1
        else:
            for t in test_ids:
                assert t.encode() not in blob, (sub, rel)
    assert n_npz == 2 and len(parts_ids) == len(allowed)
    assert not [rel for sub, rel in spy.reads if sub == 'wsi_tokens' and rel.split('/')[-1][:-4] in test_ids]
    ref, _ = data.load_fold(tmp_path, 'BLCA', 0, parts=('train', 'val'))
    for s_ in ('train', 'val'):
        assert parts[s_].patient_ids == ref[s_].patient_ids
        for f in ('wsi', 'wsi_mask', 'rna', 'text', 'text_nm', 'time', 'event'):
            assert torch.equal(getattr(parts[s_], f), getattr(ref[s_], f)), f
    with pytest.raises(PermissionError):
        spy.read('wsi_tokens', f'BLCA/{sorted(test_ids)[0]}.npz')


def test_load_backbone_rejects_tampered_ckpt_or_run_json(tmp_path):
    m = small_model()
    d = tmp_path / 'run'
    d.mkdir()
    torch.save(m.state_dict(), d / 'best.pt')
    fp = {'cohort': 'a', 'rna': 'b', 'splits': 'c', 'text': 'd', 'wsi_tokens': 'e'}
    (d / 'run.json').write_text(json.dumps({'arm': 'tri', 'assets_fp': fp, 'config': {'d': 32, 'lr': 1e-4,
                                            'weight_decay': 1e-5, 'batch_size': 64, 'epochs': 50, 'dropout': 0.0, 'seed': 2026}}))
    good = (cache.sha256((d / 'best.pt').read_bytes()), cache.sha256((d / 'run.json').read_bytes()))
    for bad in ((good[0], '0' * 64), ('0' * 64, good[1])):
        with pytest.raises(PermissionError):
            cache.load_backbone(d, None, 'X/fold0/tri/best.pt', 'cpu', registry={'X/fold0/tri/best.pt': bad})
    with pytest.raises(PermissionError):                                       # 未登记
        cache.load_backbone(d, None, 'X/fold0/tri/best.pt', 'cpu', registry={})
    reg = {'X/fold0/tri/best.pt': good}
    meta = {'assets_fp': dict(fp), 'pathways': [[0, 1, 2], [3, 4, 5]], 'n_fields': 4}
    for bad_meta, bad_reg in ((dict(fp, rna='zz'), fp), (fp, dict(fp, splits='zz'))):   # 读到的资产或登记值换了
        with pytest.raises(PermissionError):
            cache.load_backbone(d, dict(meta, assets_fp=bad_meta), 'X/fold0/tri/best.pt', 'cpu', registry=reg,
                                assets_fp=bad_reg)


def test_trainval_reader_rejects_cross_split_duplicates(tmp_path):
    """复审 R2-1：同一患者同时在 train 与 test（删 test 行后 I07 的重叠检查看不到）必须拒绝；未知 part 也拒绝。"""
    write_assets(tmp_path)
    split_path = tmp_path / 'splits' / 'splits.csv'
    rows = data.csv_rows(split_path.read_bytes())
    tr = next(r for r in rows if r['part'] == 'train' and r['cancer'] == 'BLCA' and r['fold'] == '0')
    for extra in (dict(tr, part='test'), dict(tr, part='holdout')):
        blob = cache.TrainValReader._dump(rows[0].keys(), rows + [extra])
        split_path.write_bytes(blob)
        man = tmp_path / 'splits' / 'splits.manifest.json'
        mj = json.loads(man.read_text())
        mj['files']['splits.csv'] = cache.sha256(blob)
        man.write_text(json.dumps(mj))
        with pytest.raises((AssertionError, ValueError)):
            cache.TrainValReader(provenance.AssetReader(tmp_path), 'BLCA', 0)


def _good_manifest(cfg):
    from experiments.I08_ps3_shared_recovery import i07_registry
    head = cache._git('rev-parse', 'HEAD').stdout.strip()
    files = {cache.fold_name(c, k): {'sha256': '0' * 64, 'ckpt_sha256': i07_registry.TRI[f'{c}/fold{k}/tri/best.pt'][0],
                                     'run_sha256': i07_registry.TRI[f'{c}/fold{k}/tri/best.pt'][1],
                                     'n': {'train': 10, 'val': 3}, 'd0_max_abs': 1e-7, 'd0': {},
                                     'assets_fp': dict(i07_registry.ASSETS_FP)}
             for c in cfg['backbone']['cancers'] for k in cfg['backbone']['folds']}
    return {'source': {'commit': head, 'dirty': False, 'source': 'git'}, 'source_files': cache.source_files(),
            'config_sha256': 'x', 'config_cache_view_sha256': cache.config_cache_view_sha(cfg), 'splits': ['train', 'val'],
            'views': list(VIEWS), 'backbone_run': 'i07-ps3-20261011', 'd0_tol': cache.D0_TOL, 'files': files}


def test_verify_cache_manifest(tmp_path):
    import copy
    from experiments.I08_ps3_shared_recovery import contract
    cfg = contract.load_config()[0]
    good = _good_manifest(cfg)
    assert cache.verify_cache_manifest(good, cfg)
    first = cache.fold_name('BLCA', 0)
    mutations = [
        lambda m: m['source'].update(dirty=True),
        lambda m: m['source'].update(commit='f' * 40),                         # 不是 HEAD 祖先
        lambda m: m['source_files'].update({'experiments/I08_ps3_shared_recovery/cache.py': '0' * 64}),
        lambda m: m.update(splits=['train', 'val', 'test']),
        lambda m: m['files'].pop(first),                                        # 缺折
        lambda m: m['files'][first].update(ckpt_sha256='0' * 64),
        lambda m: m['files'][first].update(run_sha256='0' * 64),
        lambda m: m['files'][first].update(d0_max_abs=1e-3),
        lambda m: m['files'][first]['assets_fp'].update(splits='0' * 64),     # 换了一套资产
        lambda m: m.update(extra=1),
    ]
    for mut in mutations:
        m = copy.deepcopy(good)
        mut(m)
        with pytest.raises(PermissionError):
            cache.verify_cache_manifest(m, cfg)
