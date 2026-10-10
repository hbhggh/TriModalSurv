"""I06 敏感性（研究计划书 4.9）：冻结文本哈希绑定、只剔除退回 / 截断标记的患者、剔除后按剩余患者重算 C-index。"""
import hashlib
import json

import numpy as np
import pytest

from experiments.I05_text_encoder_bcmbert.tools import verify_results as vr
from experiments.I06_llm_condensation import condense
from experiments.I06_llm_condensation.tools import sensitivity as sens


def write_frozen(tmp_path, records):
    data = ''.join(json.dumps(r) + '\n' for r in records).encode('utf-8')
    (tmp_path / 'frozen-struct.jsonl').write_bytes(data)
    return {'frozen_texts': {'struct': {'path': 'frozen-struct.jsonl', 'sha256': hashlib.sha256(data).hexdigest()}}}


def test_flagged_patients_binds_hash_and_keeps_only_capped_statuses(tmp_path):
    records = [{'patient_id': f'P{i}', 'cancer': 'UCEC', 'split': split, 'status': status, 'text': 't'}
               for i, (split, status) in enumerate([('train', 'ok'), ('train', 'fallback_empty'), ('test', 'truncated')])]
    manifest = write_frozen(tmp_path, records)
    flagged = sens.flagged_patients(tmp_path, manifest)
    assert set(flagged['struct']) == {'P1', 'P2'} and flagged['struct']['P1']['split'] == 'train'
    assert set(condense.CAPPED_STATUSES) >= {'fallback_empty', 'truncated'}
    manifest['frozen_texts']['struct']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='哈希'):
        sens.flagged_patients(tmp_path, manifest)


def cell(tmp_path, ids, time, censorship, risk):
    path = tmp_path / 'UCEC' / '123' / 'none'
    path.mkdir(parents=True)
    np.savez(path / 'combo.npz', patient_ids=np.array(ids), time=np.array(time, dtype=float),
             censorship=np.array(censorship, dtype=float), risk_b=np.array(risk, dtype=float))
    event = (1 - np.array(censorship)).astype(bool)
    value = vr.concordance_numpy(event, np.array(time, dtype=float), np.array(risk, dtype=float))
    row = {'cancer': 'UCEC', 'seed': 123, 'grid': 'none', 'cell': 'UCEC/123/none', 'prediction_file': 'combo.npz',
           'protocol': 'strategy0', 'c_index_b': value}
    return {'rows': [row]}


def test_recompute_drops_only_flagged_test_patients(tmp_path):
    ids = ['A', 'B', 'C', 'D', 'E', 'F']
    complete = cell(tmp_path, ids, [1, 2, 3, 4, 5, 6], [0, 0, 1, 0, 0, 1], [6, 2, 4, 3, 1, 5])
    same = sens.recompute(tmp_path, complete, {'Z'})  # 标记者不在 test：取原值，不改变任何行
    assert same['rows_changed'] == 0 and same['per_cancer']['UCEC'] == {'n_test': 6, 'n_excluded': 0, 'excluded': []}
    assert same['values'][('UCEC', 123, 'none')] == complete['rows'][0]['c_index_b']
    dropped = sens.recompute(tmp_path, complete, {'A'})  # 标记者在 test：按剩余 B–F 五人重算
    expected = vr.concordance_numpy(np.array([1, 0, 1, 1, 0], dtype=bool), np.array([2, 3, 4, 5, 6], dtype=float),
                                    np.array([2, 4, 3, 1, 5], dtype=float))
    assert dropped['rows_changed'] == 1
    assert dropped['values'][('UCEC', 123, 'none')] == expected != complete['rows'][0]['c_index_b']
    assert dropped['per_cancer']['UCEC']['excluded'] == ['A']
