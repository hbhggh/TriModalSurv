"""I06 第 3 步：源文本自动核验、抽查表打分与冻结（假数据）。"""
import csv
import json

import pytest

from experiments.I06_llm_condensation import condense, export_texts, freeze, verify

CONFIG = export_texts.load_config()
TERMS = CONFIG['verify']['prognostic_terms']
SOURCE = ('FINAL DIAGNOSIS: Invasive ductal carcinoma, Nottingham grade 2. Tumor size 2.3 cm. '
          'Margins negative. Lymph nodes: 0/12. pT2 pN0. No lymphovascular invasion.')


# ----------------------------------------------------------------------------- 源文本核验

def test_grounded_output_has_no_flags():
    out = 'Invasive ductal carcinoma, grade 2, 2.3 cm; margins negative; lymph nodes 0 / 12; pT2 pN0.'
    assert verify.grounding_flags(out, SOURCE, prognostic_terms=TERMS) == []


def test_ungrounded_numbers_stages_negations_and_prognosis_are_flagged():
    out = 'Tumor size 3.1 cm, 1/12 nodes, pT3, lymphovascular invasion absent; poor prognosis.'
    flags = verify.grounding_flags(out, SOURCE, prognostic_terms=TERMS)
    assert 'number:3.1' in flags and 'number:1/12' in flags and 'stage:pt3' in flags
    assert 'negation:absent' in flags and 'prognostic:poor prognosis' in flags and 'prognostic:prognosis' in flags


def record(pid, text, status='ok', arm='summary', model_id='claude-opus-5-5'):
    return {'patient_id': pid, 'cancer': 'BRCA', 'split': 'train', 'arm': arm, 'status': status, 'text': text,
            'text_sha256': condense.sha256_text(text), 'n_tokens': len(text.split()) + 2, 'payload': None,
            'model': model_id if status in ('ok', 'truncated') else None,
            'input_text_sha256': condense.sha256_text(SOURCE), 'attempts': []}


def test_flag_records_skips_fallbacks_and_computes_rate():
    recs = [record('P1', 'grade 2, 2.3 cm'), record('P2', 'grade 3'), record('P3', 'raw text', 'fallback_refusal')]
    result = verify.flag_records(recs, {p: SOURCE for p in ('P1', 'P2', 'P3')}, config=CONFIG)
    assert result['checked'] == 2 and result['flagged'] == 1 and result['flag_rate'] == 0.5
    assert list(result['flags']) == ['P2']


# ----------------------------------------------------------------------------- 抽查表与打分

def test_agresti_coull_interval_contains_point_and_is_clipped():
    low, high = verify.agresti_coull(0, 40)
    assert low == 0.0 and 0.05 < high < 0.12
    low, high = verify.agresti_coull(20, 40)
    assert low < 0.5 < high


def fill_sheet(path, values):
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    for row, (h, o, f) in zip(rows, values):
        row.update(hallucination=h, omission=o, fabricated_prognosis_or_stage=f, judge='human', needs_human='0')
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=verify.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def test_sheet_is_deterministic_and_scoring_detects_failures(tmp_path):
    recs = [record(f'P{i:02d}', 'grade 2') for i in range(60)]
    sources = {r['patient_id']: SOURCE for r in recs}
    flags = verify.flag_records(recs, sources, config=CONFIG)
    a, b = tmp_path / 'a.csv', tmp_path / 'b.csv'
    verify.write_sheet(a, recs, sources, flags, config=CONFIG)
    verify.write_sheet(b, recs, sources, flags, config=CONFIG)
    assert a.read_text(encoding='utf-8') == b.read_text(encoding='utf-8')
    n = fill_sheet(a, [('0', '0', '0')] * 38 + [('1', '0', '0'), ('0', '1', '0')])
    assert n == CONFIG['verify']['audit_per_arm']
    result = verify.score(a, flags, config=CONFIG)
    assert result['hallucination']['count'] == 1 and result['omission']['count'] == 1
    assert result['obvious_failure'] is False
    fill_sheet(b, [('0', '0', '0')] * 39 + [('1', '0', '1')])
    assert verify.score(b, flags, config=CONFIG)['obvious_failure'] is True


def test_score_rejects_old_sheet_for_regenerated_records(tmp_path):
    """round2 R2：记录重新生成（患者集合不变）后，旧抽查表不得套到新 flags 上。"""
    old = [record(f'P{i:02d}', 'grade 2') for i in range(60)]
    new = [record(f'P{i:02d}', 'grade 2, 2.3 cm') for i in range(60)]
    sources = {r['patient_id']: SOURCE for r in old}
    sheet = tmp_path / 'old.csv'
    verify.write_sheet(sheet, old, sources, verify.flag_records(old, sources, config=CONFIG), config=CONFIG)
    fill_sheet(sheet, [('0', '0', '0')] * 40)
    with pytest.raises(ValueError, match='records_sha256'):
        verify.score(sheet, verify.flag_records(new, sources, config=CONFIG), config=CONFIG)


def test_flagged_rows_join_sheet_screening_only_and_fabrication_anywhere_fails(tmp_path):
    """自动核验只做初筛（用户裁决 2026-09-26）：被标记的份加进抽查表（sample=flagged），高标记率本身不判失败；
    比率只在随机样本上估计；任何一行捏造分期 / 预后即判失败。"""
    recs = [record(f'P{i:02d}', 'grade 3') for i in range(50)]  # 原文没有 grade 3 → 全部被标记
    sources = {r['patient_id']: SOURCE for r in recs}
    flags = verify.flag_records(recs, sources, config=CONFIG)
    sheet = tmp_path / 's.csv'
    verify.write_sheet(sheet, recs, sources, flags, config=CONFIG)
    with sheet.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 50 and sum(r['sample'] == 'random' for r in rows) == CONFIG['verify']['audit_per_arm']
    with pytest.raises(ValueError):  # 未填完
        verify.score(sheet, flags, config=CONFIG)
    fill_sheet(sheet, [('0', '0', '0')] * 50)
    result = verify.score(sheet, flags, config=CONFIG)
    assert result['obvious_failure'] is False and result['flag_rate'] == 1.0
    assert result['audited'] == 40 and len(result['flagged_reviewed']) == 10
    flagged_last = [('0', '0', '0')] * 50
    rows_sorted = [r['sample'] for r in rows]
    flagged_last[rows_sorted.index('flagged')] = ('1', '0', '1')  # 捏造只出现在被标记的份里
    fill_sheet(sheet, flagged_last)
    result = verify.score(sheet, flags, config=CONFIG)
    assert result['obvious_failure'] is True and result['hallucination']['count'] == 0
    assert result['hallucination']['flagged_count'] == 1


# ----------------------------------------------------------------------------- 冻结

def export_file(tmp_path, pids):
    path = tmp_path / 'texts.jsonl'
    with path.open('w', encoding='utf-8') as handle:
        for pid in pids:
            handle.write(json.dumps({'patient_id': pid, 'cancer': 'BRCA', 'split': 'train', 'text': SOURCE,
                                     'text_sha256': condense.sha256_text(SOURCE)}) + '\n')
    return path


def quality(tmp_path, arm, recs, failure=False):
    """走真实的 flag → sheet → 填表 → score 流程得到质量报告。"""
    sources = {r['patient_id']: SOURCE for r in recs}
    flags = verify.flag_records(recs, sources, config=CONFIG)
    sheet = tmp_path / f'sheet-{arm}-{len(list(tmp_path.glob("sheet-*")))}.csv'
    verify.write_sheet(sheet, recs, sources, flags, config=CONFIG)
    fill_sheet(sheet, [('0', '0', '1' if failure else '0')] * CONFIG['verify']['audit_per_arm'])
    return verify.score(sheet, flags, config=CONFIG)


def arm_records(arm, pids, **kw):
    return [record(p, f'{arm} text: grade 2, margins negative', arm=arm, **kw) for p in pids]


def test_freeze_writes_manifest_and_frozen_texts_readable_by_extractor(tmp_path):
    pids = [f'P{i:03d}' for i in range(100)]
    texts = export_file(tmp_path, pids)
    struct, summ = arm_records('struct', pids), arm_records('summary', pids)
    manifest = freeze.freeze(texts_path=texts, struct_records=struct, summary_records=summ,
                             struct_quality=quality(tmp_path, 'struct', struct),
                             summary_quality=quality(tmp_path, 'summary', summ), target_words=110,
                             out_dir=tmp_path / 'frozen', config=CONFIG)
    assert manifest['llm']['model'] == 'claude-opus-5-5' and manifest['llm']['effort'] == 'high'
    assert set(manifest['prompts']) == {'system', 'struct_user', 'summary_user', 'length_retry'}
    frozen = freeze.read_frozen(tmp_path / 'frozen' / 'frozen-summary.jsonl',
                                expected_sha256=manifest['frozen_texts']['summary']['sha256'])
    assert sorted(frozen) == pids and frozen['P000']['text'] == 'summary text: grade 2, margins negative'


@pytest.mark.parametrize('problem,match', [
    ('quality', '质量检查未通过'), ('missing', '患者集合'), ('models', '模型版本'), ('cap', '超过上限'),
    ('forged', '质量报告不属于'),         # 只含 arm / obvious_failure 的伪报告（Codex 节点一 finding 3）
    ('stale', '质量报告不属于'),          # 对另一份记录做的质量报告
    ('unknown_status', '未知的记录状态'),  # 拼错的状态不能绕过 2% 上限
])
def test_freeze_refuses_bad_inputs(tmp_path, problem, match):
    pids = [f'P{i:03d}' for i in range(100)]
    texts = export_file(tmp_path, pids)
    struct = arm_records('struct', pids)
    summ = arm_records('summary', pids)
    if problem == 'missing':
        summ = summ[:-1]
    elif problem == 'models':
        summ = arm_records('summary', pids, model_id='claude-fable-5-1')
    elif problem == 'cap':
        for r in struct[:3]:  # 退回 3% > 上限 2%
            r['status'] = 'fallback_refusal'
    sq, zq = quality(tmp_path, 'struct', struct), quality(tmp_path, 'summary', summ, failure=problem == 'quality')
    if problem == 'forged':
        zq = {'arm': 'summary', 'obvious_failure': False}
    elif problem == 'stale':
        summ[0] = record(summ[0]['patient_id'], 'summary text: grade 2', arm='summary')
    elif problem == 'unknown_status':
        struct[0]['status'] = 'fallback_refusl'
    with pytest.raises(ValueError, match=match):
        freeze.freeze(texts_path=texts, struct_records=struct, summary_records=summ, struct_quality=sq,
                      summary_quality=zq, target_words=110, out_dir=tmp_path / 'frozen', config=CONFIG)


def test_read_frozen_rejects_tampered_rows(tmp_path):
    path = tmp_path / 'f.jsonl'
    path.write_text(json.dumps({'patient_id': 'P1', 'cancer': 'BRCA', 'split': 'train', 'text': 'changed',
                                'text_sha256': condense.sha256_text('orig'), 'status': 'ok'}) + '\n', encoding='utf-8')
    with pytest.raises(ValueError):
        freeze.read_frozen(path)


# ----------------------------------------------------------------------------- 原文归一化（试点核实后，用户裁决 2026-09-26）

@pytest.mark.parametrize('source,output', [
    ('TNM: pT3 pNO pMX, stage IIB. All lymph nodes tumor-free.', 'pT3 pN0; lymph nodes 0 positive'),  # OCR 字母 O
    ('multilobulated mass (AJCC pTlc).', 'Pathologic stage: pT1c'),                                    # OCR 字母 l
    ('PATHOLOGICAL TNM (AJCC 7th ed.): pT: 2a PL2. pN: 0.', 'pT2a PL2, pN0'),                          # 分开写
    ('a group of four adjacent lymph nodes; one involved by carcinoma', 'inferior ligament node 1/4'),  # 英文数字
    ('NO CARCINOMA IDENTIFIED IN 15. LYMPH NODES.', 'Lymph nodes: 0/15'),                              # 全阴性
    ('Anterior endomyometrium: 75 %, Posterior: 75 %.', 'involving 75% of anterior endomyometrium'),    # 百分号前空格
    ('MIB-1 LABELLING INDEX 0.5%.', 'Ki-67: MIB-1 labelling index 0.5%'),                               # 标签名
])
def test_source_normalization_grounds_faithful_rewrites(source, output):
    assert verify.grounding_flags(output, source, prognostic_terms=TERMS) == []


def test_normalization_still_flags_fabrication():
    source = 'TNM: pT2 pNO. Tumor size 2.3 cm. Lymph nodes 0/12.'
    flags = verify.grounding_flags('pT3 pN1, 3.1 cm, 5/12 nodes', source, prognostic_terms=TERMS)
    assert {'stage:pt3', 'stage:pn1', 'number:3.1', 'number:5/12'} <= set(flags)
    assert verify.grounding_flags('0/14 nodes', source, prognostic_terms=TERMS) == ['number:0/14']  # 分母须在原文


def test_derived_totals_absent_from_source_are_still_flagged():
    """各站加总得到、原文没有写出的总数照样标记，交人工抽查判断（不为加总放宽规则）。"""
    source = 'Sentinel #1 (1/1). Sentinel #2 (0/1). Non-sentinel (0/1).'
    assert verify.grounding_flags('Lymph nodes: 1/3', source, prognostic_terms=TERMS) == ['number:1/3']


def test_truncation_is_reported_not_capped(tmp_path):
    """截断只报告（用户裁决 2026-09-26）：结构化臂截断 30% 仍可冻结，manifest 如实记录截断率。"""
    pids = [f'P{i:03d}' for i in range(100)]
    texts = export_file(tmp_path, pids)
    struct, summ = arm_records('struct', pids), arm_records('summary', pids)
    for r in struct[:30]:
        r['status'] = 'truncated'
    manifest = freeze.freeze(texts_path=texts, struct_records=struct, summary_records=summ,
                             struct_quality=quality(tmp_path, 'struct', struct),
                             summary_quality=quality(tmp_path, 'summary', summ), target_words=109,
                             out_dir=tmp_path / 'frozen', config=CONFIG)
    assert manifest['arms']['struct']['truncated_fraction'] == pytest.approx(0.30)
    assert manifest['arms']['struct']['fallback_fraction'] == 0.0


# ----------------------------------------------------------------------------- Codex 评审（用户裁决 2026-09-26）

def test_codex_judge_chunks_apply_and_human_review_gate(tmp_path):
    recs = [record(f'P{i:02d}', 'grade 2') for i in range(60)]
    sources = {r['patient_id']: SOURCE for r in recs}
    flags = verify.flag_records(recs, sources, config=CONFIG)
    sheet = tmp_path / 'sheet.csv'
    verify.write_sheet(sheet, recs, sources, flags, config=CONFIG)
    paths = verify.judge_chunks(sheet, tmp_path / 'chunks', chunk_size=15)
    items = [item for path in paths for item in json.loads(path.read_text())]
    assert len(paths) == 3 and [i['row_id'] for i in items] == list(range(40))
    assert set(items[0]) == {'row_id', 'cancer', 'arm', 'original_report', 'condensed_text'}  # 不给自动核验标记
    verdicts = [{'row_id': i, 'hallucination': int(i == 3), 'omission': int(i == 5), 'fabricated_prognosis_or_stage': 0,
                 'evidence': 'x' if i in (3, 5) else ''} for i in range(40)]
    with pytest.raises(ValueError, match='缺'):
        verify.apply_judge(sheet, verdicts[:-1], tmp_path / 'bad.csv', config=CONFIG)
    judged = tmp_path / 'judged.csv'
    summary = verify.apply_judge(sheet, verdicts, judged, config=CONFIG)
    assert summary == {'rows': 40, 'codex_positive': 2, 'needs_human': 2 + CONFIG['verify']['human_check_negatives']}
    with pytest.raises(ValueError, match='人工复核'):  # needs_human 行未复核不能打分
        verify.score(judged, flags, config=CONFIG)
    rows = verify.read_sheet(judged)
    for row in rows:
        if row['needs_human'] == '1':
            row['judge'] = 'human'
            if row['codex_verdict'] == '1,0,0':
                row['hallucination'] = '0'  # 人工推翻一条 Codex 判定
    with judged.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=verify.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    result = verify.score(judged, flags, config=CONFIG)
    assert result['hallucination']['count'] == 0 and result['omission']['count'] == 1
    assert result['judge']['human_reviewed'] == 12 and result['judge']['human_agrees_with_codex'] == 11
    assert result['obvious_failure'] is False
