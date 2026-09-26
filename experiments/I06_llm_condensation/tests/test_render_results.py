"""I06 第 6 步：Overall 判定、胜者规则、检索增益与结果文档渲染（真实基线与 B1 / B2 文件，候选为合成）。"""
import json

import pytest

from experiments.I05_text_encoder_bcmbert.tools import render_encoder_tables as i05r
from experiments.I06_llm_condensation.tools import render_results as rr

I05 = i05r.load_config()
I06 = json.loads(rr.I06_CONFIG.read_text(encoding='utf-8'))
BASELINE = rr.REPO_ROOT / I05['legacy']['test_complete']
B1_PATH = rr.DEFAULT_CONTROLS['B1'][1]


def test_real_baseline_overall_matches_paper_table1():
    base, _ = i05r.load_baseline(BASELINE, I05)
    rr.check_table1_overall(base, I05, I06)
    assert f"{rr.overall(base, 'LGG', I05):.6f}" == '0.738872'


def const(value_by_cancer):
    return {(c, s, g): value_by_cancer[c] for c in I05['cancers'] for s in I05['seeds'] for g in I05['grids']}


def test_winner_rule_counts_wins_first_then_mean_delta_then_order():
    base = const({c: 0.60 for c in I05['cancers']})
    four_small = const({'BLCA': 0.61, 'BRCA': 0.61, 'LGG': 0.61, 'LUAD': 0.61, 'UCEC': 0.50})  # 4/5，平均 Δ −0.012
    three_big = const({'BLCA': 0.70, 'BRCA': 0.70, 'LGG': 0.70, 'LUAD': 0.55, 'UCEC': 0.55})   # 3/5，平均 Δ +0.04
    tie = const({c: 0.60 for c in I05['cancers']})                                               # 全部相等 → 0/5
    decision = rr.decide({'A1-S': three_big, 'A1-Z': four_small, 'A2-S': tie, 'A2-Z': tie}, base, I05,
                         I06['candidate_tie_order'])
    assert decision['winner'] == 'A1-Z' and decision['reached'] is True
    assert decision['candidates']['A2-S']['k'] == 0  # 相等不算胜
    same = rr.decide({'A1-S': tie, 'A1-Z': tie, 'A2-S': tie, 'A2-Z': tie}, base, I05, I06['candidate_tie_order'])
    assert same['winner'] == 'A1-S' and same['reached'] is False


def test_retrieval_gain_averages_grids_and_counts_positive_seeds():
    s0 = const({c: 0.62 for c in I05['cancers']})
    m0 = const({c: 0.60 for c in I05['cancers']})
    gain = rr.retrieval_gain(s0, m0, I05)
    assert gain['LGG']['average'] == pytest.approx(0.02) and gain['LGG']['k_positive_seeds'] == 5


def synthetic_candidate(tmp_path, name, shift):
    payload = json.loads(B1_PATH.read_text(encoding='utf-8'))
    profile = I06['candidates'][name]['profile']
    payload['profile'], payload['protocol_id'] = profile, I05['protocol_ids'][profile]
    for row in payload['rows']:
        if row['protocol'] == 'strategy0':
            row['c_index_b'] = min(1.0, row['c_index_b'] + shift)
    path = tmp_path / f'{name}.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_render_all_end_to_end_is_deterministic(tmp_path):
    shifts = {'A1-S': 0.0, 'A1-Z': 0.04, 'A2-S': 0.01, 'A2-Z': 0.0}
    candidates = {n: synthetic_candidate(tmp_path, n, s) for n, s in shifts.items()}
    first = rr.render_all(baseline=BASELINE, controls=rr.DEFAULT_CONTROLS, candidates=candidates, i06_config=I06)
    second = rr.render_all(baseline=BASELINE, controls=rr.DEFAULT_CONTROLS, candidates=candidates, i06_config=I06)
    assert first[rr.RESULT_NAME] == second[rr.RESULT_NAME] and first[rr.ABLATION_NAME] == second[rr.ABLATION_NAME]
    decision = first['decision']
    assert decision['winner'] == 'A1-Z' and decision['candidates']['A1-Z']['k'] == 5
    assert decision['candidates']['A1-S']['k'] == 3  # 与 B1 相同：Overall 胜 BLCA、LUAD、UCEC
    text = first[rr.RESULT_NAME]
    assert '胜者：A1-Z NeuML 摘要，Overall 严格胜 5/5，达标' in text
    for cancer in I05['cancers']:
        assert f'### {cancer}' in text
    assert text.count('| **Overall** |') == 5 and '检索效果最好' in text
    assert first[rr.ABLATION_NAME].count('| Overall |') == 2


def test_render_rejects_wrong_profile_for_candidate(tmp_path):
    candidates = {n: synthetic_candidate(tmp_path, n, 0.0) for n in I06['candidates']}
    candidates['A2-Z'] = candidates['A1-S']  # 档案与候选不符
    with pytest.raises(ValueError, match='档案'):
        rr.render_all(baseline=BASELINE, controls=rr.DEFAULT_CONTROLS, candidates=candidates, i06_config=I06)
