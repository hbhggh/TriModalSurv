"""迁移门禁：仅 valid 对拍，比较同权重、同患者、同候选的跨 GPU 输出。"""
import json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
old = ROOT / 'evidence' / 'tako-parity-preserved'
new = ROOT / 'evidence' / 'acceleration-parity'
a = json.loads((old/'complete.json').read_text())
b = json.loads((new/'complete.json').read_text())
assert a['status'] == b['status'] == 'PASS'
assert a['source_hashes'] == b['source_hashes']
assert a['asset_hashes'] == b['asset_hashes']
maximum = 0.0
count = 0
for path in sorted((old).glob('*/*/accelerated/*.npz')):
    other = new / path.relative_to(old)
    with np.load(path, allow_pickle=False) as x, np.load(other, allow_pickle=False) as y:
        assert set(x.files) == set(y.files)
        for key in x.files:
            if key in ('logits','risk_b'):
                np.testing.assert_allclose(x[key], y[key], atol=1e-6, rtol=0)
                maximum = max(maximum, float(np.max(np.abs(x[key]-y[key]))))
            else:
                np.testing.assert_array_equal(x[key], y[key])
    count += 1
for path in old.glob('*/*/accelerated/*.json'):
    if path.name == 'cell.json':
        continue
    assert json.loads(path.read_text()) == json.loads((new/path.relative_to(old)).read_text()), str(path)
assert count == 20 * 61, count
report = {'status':'PASS','valid_prediction_files':count,'donor_audits_identical':True,
          'max_prediction_abs_diff':maximum,'atol':1e-6,'rtol':0,'test_evaluated':False}
target = ROOT/'evidence'/'migration-parity.json'
with target.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report), flush=True)
