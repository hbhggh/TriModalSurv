"""I06 第 1 步：字段清单、序列化、请求构造与纯文本导出（假数据，不调用任何 LLM）。"""
import csv
import json

import pytest

from experiments.I05_text_encoder_bcmbert.extract_text_features import sha256_text
from experiments.I06_llm_condensation import export_texts
from experiments.I06_llm_condensation import model

CONFIG = export_texts.load_config()


def filled(cancer, **overrides):
    payload = {}
    for field in model.fields_for(cancer):
        payload[field.key] = [] if field.kind == 'pairs' else model.NOT_MENTIONED
    payload.update(overrides)
    return payload


# ----------------------------------------------------------------------------- 字段与 schema

@pytest.mark.parametrize('cancer', model.CANCERS)
def test_schema_requires_every_field_and_forbids_extras(cancer):
    schema = model.struct_schema(cancer)
    keys = [f.key for f in model.fields_for(cancer)]
    assert schema['required'] == keys and list(schema['properties']) == keys
    assert schema['additionalProperties'] is False
    assert len(keys) == len(set(keys))


def test_merged_hints_do_not_duplicate_fields():
    ucec = [f.key for f in model.fields_for('UCEC')]
    assert 'lymphovascular_invasion' in ucec and 'lvsi' not in ucec
    lvi = next(f for f in model.fields_for('UCEC') if f.key == 'lymphovascular_invasion')
    assert 'LVSI' in lvi.description


def test_validate_struct_rejects_missing_extra_and_wrong_types():
    good = filled('LGG')
    model.validate_struct('LGG', good)
    with pytest.raises(ValueError):
        model.validate_struct('LGG', {k: v for k, v in good.items() if k != 'ki67'})
    with pytest.raises(ValueError):
        model.validate_struct('LGG', {**good, 'extra': 'x'})
    with pytest.raises(ValueError):
        model.validate_struct('LGG', {**good, 'ki67': 5})
    with pytest.raises(ValueError):
        model.validate_struct('LGG', {**good, 'ihc_molecular': [{'name': 'IDH1'}]})


# ----------------------------------------------------------------------------- 序列化

def test_serialize_struct_omits_not_mentioned_and_keeps_fixed_order():
    payload = filled('BRCA', histologic_type='invasive ductal carcinoma', margins='Negative.',
                     er_status='positive (95%)', lymph_nodes='0/12',
                     ihc_molecular=[{'name': 'Ki-67', 'result': '20%'},
                                    {'name': 'CK5/6', 'result': 'not mentioned'}])
    text = model.serialize_struct('BRCA', payload)
    assert text == ('Histologic type: invasive ductal carcinoma. Lymph nodes: 0/12. Margins: Negative. '
                    'ER: positive (95%). IHC and molecular: Ki-67 20%.')
    assert 'not mentioned' not in text.lower()


def test_serialize_struct_keeps_pertinent_negatives():
    payload = filled('BLCA', lymphovascular_invasion='absent', carcinoma_in_situ='not identified')
    text = model.serialize_struct('BLCA', payload)
    assert 'Lymphovascular invasion: absent.' in text and 'Carcinoma in situ: not identified.' in text


def test_serialize_struct_all_not_mentioned_is_empty_and_variants_are_dropped():
    payload = filled('LUAD', margins=' Not Mentioned. ')
    assert model.serialize_struct('LUAD', payload) == ''


def test_present_fields_matches_serialized_fields():
    payload = filled('UCEC', histologic_type='endometrioid', extent_invasion='less than half')
    assert model.present_fields('UCEC', payload) == ['histologic_type', 'extent_invasion']


def test_serialize_summary_collapses_whitespace_and_validates():
    assert model.serialize_summary({'summary': ' Grade 2  endometrioid\ncarcinoma. '}) == \
        'Grade 2 endometrioid carcinoma.'
    with pytest.raises(ValueError):
        model.serialize_summary({'summary': 'x', 'extra': 1})


# ----------------------------------------------------------------------------- 请求

def test_build_request_inserts_report_verbatim_including_braces():
    prompts = model.load_prompts()
    report = 'DIAGNOSIS: {not a placeholder} grade 3 of 3.'
    req = model.build_request('struct', 'BRCA', report, prompts=prompts)
    assert report in req['user'] and req['schema'] == model.struct_schema('BRCA')
    assert 'pertinent negatives' in req['system'] and 'OCR' in req['system']
    summ = model.build_request('summary', 'LGG', report, prompts=prompts, target_words=120)
    assert 'about 120 words' in summ['user'] and summ['schema'] == model.SUMMARY_SCHEMA
    with pytest.raises(ValueError):
        model.build_request('summary', 'LGG', report, prompts=prompts)
    with pytest.raises(ValueError):
        model.build_request('struct', 'LGG', '   ', prompts=prompts)


def test_prompts_have_sha256_and_no_patient_identifiers():
    prompts = model.load_prompts()
    assert set(prompts) == set(model.PROMPT_FILES)
    assert all(len(p['sha256']) == 64 for p in prompts.values())
    req = model.build_request('struct', 'LUAD', 'Report text.', prompts=prompts)
    assert 'TCGA-' not in req['system'] + req['user']


# ----------------------------------------------------------------------------- 纯文本导出

LABEL_COLUMNS = ['patient_filename', 'text', 'patient_id', 'cancer_type', 'label', 'raw_censorship',
                 'raw_survival_months', 'days_to_death', 'censorship', 'survival_months', 'split']


def write_labels(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, '7') for col in LABEL_COLUMNS})


def fake_world(tmp_path):
    texts = {'TCGA-AA-0001': ('BRCA', 'train', 'Invasive ductal carcinoma, grade 2. Seen on 01/02/2003.'),
             'TCGA-AA-0002': ('LGG', 'valid', 'Oligodendroglioma, WHO grade II. TCGA-AA-0002-01Z.'),
             'TCGA-AA-0003': ('UCEC', 'test', 'Endometrioid adenocarcinoma, FIGO grade 1.')}
    rows = [{'patient_id': pid, 'cancer_type': c, 'split': s, 'text': t, 'patient_filename': pid}
            for pid, (c, s, t) in texts.items()]
    rows.append({'patient_id': 'TCGA-AA-0009', 'cancer_type': 'KIRC', 'split': 'train', 'text': 'other'})
    labels = tmp_path / 'labels.csv'
    write_labels(labels, rows)
    manifest = {'patients': {pid: {'cancer': c, 'split': s, 'text_sha256': sha256_text(t)}
                             for pid, (c, s, t) in texts.items()}}
    return labels, manifest, texts


def test_export_writes_only_five_columns_and_matches_manifest(tmp_path):
    labels, manifest, texts = fake_world(tmp_path)
    out = tmp_path / 'texts.jsonl'
    summary = export_texts.export(labels, out, config=CONFIG, manifest=manifest)
    rows = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
    assert [list(r) for r in rows] == [CONFIG['export_columns']] * 3
    assert [r['patient_id'] for r in rows] == sorted(texts)
    raw = out.read_text(encoding='utf-8')
    assert 'survival_months' not in raw and 'censorship' not in raw
    assert summary['n'] == 3 and summary['with_tcga_barcode'] == 1 and summary['with_date'] == 1
    assert export_texts.read_export(out, config=CONFIG) == rows


def test_export_refuses_to_overwrite(tmp_path):
    labels, manifest, _ = fake_world(tmp_path)
    out = tmp_path / 'texts.jsonl'
    export_texts.export(labels, out, config=CONFIG, manifest=manifest)
    with pytest.raises(FileExistsError):
        export_texts.export(labels, out, config=CONFIG, manifest=manifest)


@pytest.mark.parametrize('mutation', ['text', 'split', 'missing'])
def test_export_rejects_any_mismatch_with_b1_manifest(tmp_path, mutation):
    labels, manifest, texts = fake_world(tmp_path)
    entry = manifest['patients']['TCGA-AA-0001']
    if mutation == 'text':
        entry['text_sha256'] = '0' * 64
    elif mutation == 'split':
        entry['split'] = 'test'
    else:
        manifest['patients']['TCGA-ZZ-9999'] = {'cancer': 'BRCA', 'split': 'train', 'text_sha256': '0' * 64}
    with pytest.raises(ValueError):
        export_texts.export(labels, tmp_path / 'out.jsonl', config=CONFIG, manifest=manifest)


def test_read_export_rejects_label_columns_and_tampered_text(tmp_path):
    bad = tmp_path / 'bad.jsonl'
    bad.write_text(json.dumps({'patient_id': 'x', 'cancer': 'BRCA', 'split': 'train', 'text': 't',
                               'text_sha256': sha256_text('t'), 'survival_months': 3}) + '\n', encoding='utf-8')
    with pytest.raises(ValueError):
        export_texts.read_export(bad, config=CONFIG)
    tampered = tmp_path / 'tampered.jsonl'
    tampered.write_text(json.dumps({'patient_id': 'x', 'cancer': 'BRCA', 'split': 'train', 'text': 't2',
                                    'text_sha256': sha256_text('t')}) + '\n', encoding='utf-8')
    with pytest.raises(ValueError):
        export_texts.read_export(tampered, config=CONFIG)


def test_locked_b1_manifest_hash_matches_repository_copy():
    manifest = export_texts.load_b1_manifest(CONFIG)
    assert len(manifest['patients']) == 2506
