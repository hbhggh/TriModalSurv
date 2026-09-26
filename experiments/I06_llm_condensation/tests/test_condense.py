"""I06 第 2 步：浓缩核心的失败处理、长度预算与试点抽样（假分词器、假客户端，不调用任何 API）。"""
import json
import re

import pytest

from experiments.I06_llm_condensation import condense, export_texts, model
from experiments.I06_llm_condensation.condense import Response

CONFIG = export_texts.load_config()
PROMPTS = model.load_prompts()
LLM = CONFIG['llm']


class WordTokenizer:
    """空白分词 + [CLS]/[SEP]；offset_mapping 与 HF 快分词器同形（特殊 token 为 (0, 0)）。"""

    def __call__(self, text, add_special_tokens=True, truncation=False, max_length=None,
                 return_offsets_mapping=False):
        spans = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
        if truncation and max_length is not None:
            spans = spans[:max_length - 2]
        ids = [1] + [7] * len(spans) + [2] if add_special_tokens else [7] * len(spans)
        out = {'input_ids': ids}
        if return_offsets_mapping:
            out['offset_mapping'] = [(0, 0)] + spans + [(0, 0)]
        return out


def budget(max_tokens=10):
    return condense.TokenBudget(WordTokenizer(), max_tokens)


class ScriptedClient:
    """按患者给出每一轮的响应；记录每轮提交的请求。"""

    def __init__(self, script):
        self.script = {pid: list(seq) for pid, seq in script.items()}
        self.calls = []

    def run(self, requests):
        self.calls.append(requests)
        out = {}
        for cid, req in requests.items():
            pid = cid.split('-', 1)[1].rsplit('-r', 1)[0]
            out[cid] = self.script[pid].pop(0)
        return out


def row(pid, text='Invasive ductal carcinoma grade two with negative margins and no lymphovascular invasion seen',
        cancer='BRCA', split='train'):
    return {'patient_id': pid, 'cancer': cancer, 'split': split, 'text': text,
            'text_sha256': condense.sha256_text(text)}


def summary(text, model_id='claude-opus-5-5'):
    return Response('succeeded', 'end_turn', model_id, json.dumps({'summary': text}), {'output_tokens': 5})


def run(rows, script, *, arm='summary', max_tokens=10, **kw):
    client = ScriptedClient(script)
    records = condense.condense(rows, arm=arm, client=client, budget=budget(max_tokens), prompts=PROMPTS, llm=LLM,
                                length=CONFIG['length'], target_words=None if arm == 'struct' else 50,
                                log=lambda *_: None, **kw)
    return records, client


def test_ok_path_records_text_hash_tokens_and_model():
    records, client = run([row('P1')], {'P1': [summary('IDC grade 2, margins negative.')]})
    rec = records[0]
    assert rec['status'] == 'ok' and rec['text'] == 'IDC grade 2, margins negative.'
    assert rec['n_tokens'] == 7 and rec['model'] == 'claude-opus-5-5'
    assert rec['text_sha256'] == condense.sha256_text(rec['text']) and len(client.calls) == 1


def test_refusal_retried_once_then_falls_back_to_first_200_tokens_of_raw_text():
    refusal = Response('succeeded', 'refusal', 'claude-opus-5-5', None)
    records, client = run([row('P1')], {'P1': [refusal, refusal]})
    rec = records[0]
    assert rec['status'] == 'fallback_refusal' and len(client.calls) == 2
    assert rec['text'] == 'Invasive ductal carcinoma grade two with negative margins'  # 8 词 + 2 个特殊 token
    assert rec['n_tokens'] == 10


def test_invalid_output_regenerated_twice_then_fallback():
    bad = [Response('succeeded', 'end_turn', 'claude-opus-5-5', '{not json'),
           Response('succeeded', 'max_tokens', 'claude-opus-5-5', '{"summary": "cut'),
           Response('succeeded', 'end_turn', 'claude-opus-5-5', json.dumps({'summary': 'x', 'extra': 1}))]
    records, client = run([row('P1')], {'P1': bad})
    assert records[0]['status'] == 'fallback_failure' and len(client.calls) == 3


def test_transport_errors_are_resubmitted_then_fallback():
    err = Response('errored', error_type='api_error')
    records, _ = run([row('P1')], {'P1': [err, err, summary('ok text here')]})
    assert records[0]['status'] == 'ok'
    records, _ = run([row('P2')], {'P2': [err] * (condense.MAX_TRANSPORT_RETRIES + 1)})
    assert records[0]['status'] == 'fallback_failure'


def test_too_long_output_gets_feedback_then_is_truncated_deterministically():
    long_text = ' '.join(f'w{i}' for i in range(20))
    tries = 1 + CONFIG['length']['length_retries']
    records, client = run([row('P1')], {'P1': [summary(long_text)] * tries})
    rec = records[0]
    assert len(client.calls) == tries and rec['status'] == 'truncated'
    assert rec['text'] == ' '.join(f'w{i}' for i in range(8)) and rec['n_tokens'] == 10
    retry_user = next(iter(client.calls[1].values()))['user']
    assert '<previous>' in retry_user and '22 tokens long' in retry_user and 'at most 10 tokens' in retry_user


def test_struct_with_every_field_not_mentioned_falls_back():
    empty = {f.key: ([] if f.kind == 'pairs' else model.NOT_MENTIONED) for f in model.fields_for('BRCA')}
    resp = Response('succeeded', 'end_turn', 'claude-opus-5-5', json.dumps(empty))
    records, _ = run([row('P1')], {'P1': [resp]}, arm='struct')
    assert records[0]['status'] == 'fallback_empty' and records[0]['payload'] == empty


def test_mixed_model_versions_in_one_arm_are_rejected():
    with pytest.raises(ValueError, match='模型版本'):
        run([row('P1'), row('P2')], {'P1': [summary('a b')], 'P2': [summary('c d', model_id='other-model')]})


def test_capped_fraction_counts_fallbacks_and_truncations():
    records = [{'status': s} for s in ['ok'] * 97 + ['truncated', 'fallback_refusal', 'fallback_empty']]
    assert condense.capped_fraction(records) == pytest.approx(0.03)
    assert condense.fallback_fraction(records) == pytest.approx(0.02)
    assert condense.truncated_fraction(records) == pytest.approx(0.01)


def test_truncate_returns_prefix_within_budget_and_leaves_short_text_untouched():
    b = budget(5)
    assert b.truncate('a b c') == 'a b c'
    cut = b.truncate('alpha  beta\ngamma delta epsilon')
    assert cut == 'alpha  beta\ngamma' and b.count(cut) <= 5


def test_pilot_rows_are_train_only_stratified_and_deterministic():
    rows = [row(f'{c}-{i:03d}', cancer=c, split=s)
            for c in CONFIG['cancers'] for i, s in enumerate(['train'] * 15 + ['test'] * 5)]
    first = condense.pilot_rows(rows, config=CONFIG)
    assert first == condense.pilot_rows(rows, config=CONFIG)
    assert len(first) == 10 * len(CONFIG['cancers']) and {r['split'] for r in first} == {'train'}
    assert all(sum(r['cancer'] == c for r in first) == 10 for c in CONFIG['cancers'])


def test_summary_target_words_from_pilot_medians():
    struct = [{'status': 'ok', 'n_tokens': n, 'text': ''} for n in (100, 120, 140)]
    summ = [{'status': 'ok', 'n_tokens': 26, 'text': ' '.join(['w'] * 20)}]  # 1.3 token/词
    assert condense.summary_target_words(struct, summ) == round(120 / 1.3)


def test_write_records_refuses_to_overwrite(tmp_path):
    path = tmp_path / 'r.jsonl'
    condense.write_records(path, [{'a': 1}])
    with pytest.raises(FileExistsError):
        condense.write_records(path, [{'a': 1}])


# ----------------------------------------------------------------------------- 续跑（本地进程中断后回放已提交批次）

class FakeBatches:
    """最小的 Message Batches 替身：提交即结束；结果由 responder(custom_id) 按轮次确定性给出。"""

    def __init__(self, responder):
        self.responder, self.store, self.created = responder, {}, 0

    def create(self, *, requests):
        self.created += 1
        batch_id = f'msgbatch_{len(self.store):03d}'
        self.store[batch_id] = [r['custom_id'] for r in requests]
        return type('B', (), {'id': batch_id})()

    def retrieve(self, batch_id):
        return type('B', (), {'processing_status': 'ended'})()

    def results(self, batch_id):
        from types import SimpleNamespace as NS
        for cid in self.store[batch_id]:
            text = self.responder(cid)
            msg = NS(content=[NS(type='text', text=json.dumps({'summary': text}))], stop_reason='end_turn',
                     model='claude-opus-5-5', usage=NS(model_dump=lambda: {'output_tokens': 5}))
            yield NS(custom_id=cid, result=NS(type='succeeded', message=msg))


def _long_until_round(cid):
    """P1 前两轮超长、第 3 轮合格；P2 第 1 轮就合格。"""
    round_no = int(cid.rsplit('-r', 1)[1])
    if cid.startswith('s-P1-') and round_no < 3:
        return ' '.join(f'w{i}' for i in range(20))
    return 'short answer'


def test_resume_replays_submitted_batches_and_reproduces_records():
    from types import SimpleNamespace as NS
    rows = [row('P1'), row('P2')]

    def go(fake, resume=()):
        client = condense.AnthropicBatchClient(model_id='claude-opus-5-5', effort='high', max_output_tokens=100,
                                               poll_seconds=0, log=lambda *_: None, resume_batch_ids=resume,
                                               client=NS(messages=NS(batches=fake)))
        records = condense.condense(rows, arm='summary', client=client, budget=budget(10), prompts=PROMPTS,
                                    llm=LLM, length=CONFIG['length'], target_words=100, log=lambda *_: None)
        return records, client

    full, full_client = go(FakeBatches(_long_until_round))
    assert len(full_client.batch_ids) == 3 and full[0]['status'] == 'ok' and full[1]['status'] == 'ok'
    interrupted = FakeBatches(_long_until_round)  # 同一服务器：已有前两轮批次，本地进程在第 3 轮前中断
    go(interrupted)
    interrupted.store = dict(list(interrupted.store.items())[:2])
    interrupted.created = 0
    resumed, client = go(interrupted, resume=list(interrupted.store))
    assert resumed == full and interrupted.created == 1  # 只新提交了第 3 轮
    bad = FakeBatches(_long_until_round)
    go(bad)
    with pytest.raises(ValueError, match='custom_id'):  # 给错顺序：第 1 轮拿到第 2 轮的批次
        go(bad, resume=list(bad.store)[1:])


# ----------------------------------------------------------------------------- 按边界截断（Codex 抽查 TCGA-BG-A0M6）

def test_truncate_clean_never_leaves_a_partial_value():
    b = budget(9)  # 最多 7 个词
    text = 'Grade: 2. Size: 2.3 cm. Stage: pT3a FIGO IIIC.'
    assert b.truncate(text) == 'Grade: 2. Size: 2.3 cm. Stage: pT3a'  # 硬切会留下半句
    assert b.truncate_clean(text) == 'Grade: 2. Size: 2.3 cm.'          # 小数点 2.3 不算边界
    assert budget(4).truncate_clean('Stage pT3a pN1 pMX FIGO IIIC') == 'Stage pT3a'  # 无句界时退到完整单词
    assert b.truncate_clean('short text.') == 'short text.'


def test_retruncate_rewrites_only_truncated_records_from_payload():
    payload = {'summary': 'Stage pT3a. Nodes 2/2 positive. FIGO IIIC stage per report here.'}
    rec = {'patient_id': 'P1', 'cancer': 'UCEC', 'status': 'truncated', 'payload': payload, 'text': 'Stage pT3a. Nodes 2/2 positive. FIGO II',
           'text_sha256': 'x', 'n_tokens': 10}
    ok = {'patient_id': 'P2', 'cancer': 'UCEC', 'status': 'ok', 'payload': {'summary': 'a b'}, 'text': 'a b',
          'text_sha256': condense.sha256_text('a b'), 'n_tokens': 4}
    out, changed = condense.retruncate([rec, ok], arm='summary', budget=budget(10))
    assert changed == 1 and out[1] == ok
    assert out[0]['text'] == 'Stage pT3a. Nodes 2/2 positive.' and out[0]['truncation'] == 'sentence_boundary'
    assert out[0]['text_sha256'] == condense.sha256_text(out[0]['text'])
