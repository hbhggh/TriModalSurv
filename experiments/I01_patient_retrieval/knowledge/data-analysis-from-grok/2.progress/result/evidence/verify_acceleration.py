"""五癌 valid 真实数据对拍：全部61候选、四场景，不计算 C-index。"""
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runtime as rt
import run
from selection import build_candidates


def main(config_path):
    cfg = rt.load_config(config_path)
    rt.setup_imports(cfg)
    rt.verify_gpu(cfg)
    import torch
    torch.set_num_threads(cfg['runtime']['cpu_threads'])
    from experiments.I01_patient_retrieval.evaluate import strict_e0_load, checkpoint_path
    out = ROOT / 'evidence' / 'acceleration-parity'
    out.mkdir(exist_ok=False)
    assets = rt.hash_assets(cfg)
    source_hashes = rt.source_hashes(cfg)
    specs = [rt.baseline_spec(a) for a in rt.BASELINES] + build_candidates(cfg)
    reports = []
    for cancer in cfg['cancers']:
        bank, source = rt.load_cancer(cfg, cancer, 'valid')
        accelerator = bank.retrieval_accelerator
        ids = rt.smoke_ids(source, cfg)
        model = rt.build_model(cfg, cancer, cfg['runtime']['device'])
        ckpt = checkpoint_path(Path(cfg['paths']['checkpoint_root']), cancer, cfg['smoke']['seed'])
        cksha = rt.file_sha256(ckpt)
        strict_e0_load(model, ckpt, expected_file_sha=cksha)
        before = {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        for grid in cfg['grids']:
            elapsed = {}; results = {}
            for mode in ('reference', 'accelerated'):
                bank.retrieval_accelerator = None if mode == 'reference' else accelerator
                t0 = time.perf_counter()
                d = out / cancer / grid / mode
                results[mode] = run.evaluate_cell(cfg, bank, source, model, specs, ids,
                    cancer=cancer, seed=cfg['smoke']['seed'], grid=grid,
                    directory=d, fingerprint='acceleration-parity-valid-only',
                    checkpoint_sha=cksha, compute_metric=False)
                elapsed[mode] = time.perf_counter() - t0
            maximum = 0.
            for left, right in zip(results['reference']['rows'], results['accelerated']['rows']):
                assert left == right, '行元数据或一致性诊断改变'
                for filename in (left['prediction_file'], left['audit_file']):
                    lp, rp = out/cancer/grid/'reference'/filename, out/cancer/grid/'accelerated'/filename
                    if filename.endswith('.json'):
                        assert json.loads(lp.read_text()) == json.loads(rp.read_text()), 'donor或审计信息改变'
                    else:
                        with np.load(lp, allow_pickle=False) as a, np.load(rp, allow_pickle=False) as b:
                            assert set(a.files) == set(b.files)
                            for key in a.files:
                                if key == 'logits':
                                    maximum = max(maximum, float(np.max(np.abs(a[key]-b[key]))))
                                assert np.array_equal(a[key], b[key]), '预测内容改变:'+key
            row = {'cancer':cancer, 'grid':grid, 'patients':len(ids), 'candidates':len(specs),
                   'seconds':elapsed, 'max_logit_abs_diff':maximum, 'score_builds':accelerator.score_builds}
            reports.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        assert all(torch.equal(v.detach().cpu(), before[k]) for k,v in model.state_dict().items())
        del bank, source, model, accelerator, before
    assert rt.hash_assets(cfg) == assets and rt.source_hashes(cfg) == source_hashes
    rt.write_json_new(out/'complete.json', {'status':'PASS','reports':reports,
        'source_hashes':source_hashes,'asset_hashes':assets,'metrics_computed':False,
        'donor_audits_identical':True,'prediction_arrays_identical':True,'state_dict_unchanged':True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    main(parser.parse_args().config)
