"""只读对账：新旧冒烟逐数组/审计一致，指纹与资产闭合。"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--new-root', type=Path, required=True)
    parser.add_argument('--old-root', type=Path, required=True)
    args = parser.parse_args()
    new, old = args.new_root, args.old_root
    smoke = read(new/'runs/smoke/complete.json')
    previous = read(old/'runs/smoke/complete.json')
    preflight = read(new/'runs/preflight/complete.json')
    assert smoke['status'] == 'SMOKE_PASS' and not smoke['metrics_computed']
    assert smoke['asset_hashes_unchanged'] and smoke['state_dict_unchanged']
    assert preflight['asset_hashes'] == read(old/'runs/preflight/complete.json')['asset_hashes']
    assert smoke['source_hashes'] == preflight['source_hashes'] == read(new/'evidence/b1b2-source.json')['source_hashes']
    assert len(smoke['cells']) == 20 and len(smoke['rows']) == 180
    assert set(smoke['cells']) == set(previous['cells'])
    assert not (new/'runs/valid').exists() and not (new/'runs/test').exists()
    assert not read(new/'evidence/b1b2-smoke.yaml')['authorization']['formal_approved']
    checked, max_diff, npz_count, audit_count = 0, 0.0, 0, 0
    for relative, expected_sha in smoke['cells'].items():
        cell_dir = new/'runs/smoke'/relative
        old_dir = old/'runs/smoke'/relative
        assert sha(cell_dir/'cell.json') == expected_sha
        cell, prior = read(cell_dir/'cell.json'), read(old_dir/'cell.json')
        assert not cell['metrics_computed']
        assert len(cell['rows']) == 9
        for row, old_row in zip(cell['rows'], prior['rows']):
            assert 'c_index_b' not in row and row['split'] == 'valid'
            assert {k:v for k,v in row.items() if k != 'run_fingerprint'} == {
                k:v for k,v in old_row.items() if k != 'run_fingerprint'}
        for name, expected in cell['artifacts'].items():
            artifact, before = cell_dir/name, old_dir/name
            assert sha(artifact) == expected
            if name.endswith('.npz'):
                with np.load(artifact, allow_pickle=False) as a, np.load(before, allow_pickle=False) as b:
                    assert set(a.files) == set(b.files)
                    for key in a.files:
                        assert a[key].dtype == b[key].dtype
                        assert np.array_equal(a[key], b[key]), (relative, name, key)
                npz_count += 1
            else:
                current_audit, prior_audit = read(artifact), read(before)
                # 新运行必须有新指纹；先校验归属，再比较真正的检索/填值审计。
                assert current_audit.pop('run_fingerprint') == smoke['run_fingerprint']
                assert prior_audit.pop('run_fingerprint') == previous['run_fingerprint']
                assert current_audit == prior_audit, (relative, name)
                audit_count += 1
        row = cell['rows'][0]
        checked += row['n_complete_checked']
        if row['n_complete_checked']:
            max_diff = max(max_diff, row['complete_max_logit_abs_diff'])
        else:
            assert row['complete_max_logit_abs_diff'] is None
    assert npz_count == audit_count == 180
    print(json.dumps({'status':'PASS','cells':20,'protocol_records':180,
        'predictions_array_equal':npz_count,'audit_equal_except_verified_run_fingerprint':audit_count,
        'n_complete_checked':checked,'complete_max_logit_abs_diff':max_diff,
        'asset_count_unchanged':len(preflight['asset_hashes']),
        'source_count':len(smoke['source_hashes']),
        'metadata_in_source':sum('/.' in key for key in smoke['source_hashes']),
        'formal_valid_test_run':False,'claude_rereview':'WAIVED_THIS_TURN'}, indent=2))


if __name__ == '__main__':
    main()
