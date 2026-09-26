#!/usr/bin/env python3
"""LLM 浓缩：读纯文本清单 → 单一 LLM 批处理 → 逐份记录（研究计划书 4.4–4.6）。

失败处理（逐份独立计数）：
- 传输失败（errored / expired / canceled）：重提，最多 ``MAX_TRANSPORT_RETRIES`` 轮；
- 拒答（stop_reason = refusal）：重试 ``refusal_retries`` 次，仍拒则退回原文（按 ``max_neuml_tokens`` 截断；v3.12 起为 8192，即全文，与 B2 输入相同）；
- 输出不合格（max_tokens 截断、JSON 解析失败、schema 不符）：重新生成 ``max_regenerations`` 次，仍失败则退回；
- 结构化臂所有字段都是 not mentioned（序列化为空）：直接退回；
- 超长（NeuML token > 200）：附上一次答案与超长提示重试 ``length_retries`` 次，仍超长则按分词偏移确定性截断。
退回与截断的文本都切在第 200 个 NeuML token 的字符边界上，NeuML 与 Qwen 两个 encoder 拿到的是同一个字符串。
同一臂所有成功响应返回的模型版本字符串必须相同；退回原文（拒答 / 失败 / 全部未提及）超过 ``fallback_cap`` 时写完记录后以非零退出；截断只报告（用户裁决 2026-09-26）。
不开 fallbacks，不传 temperature；只读 export_texts 产出的纯文本清单。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I06_llm_condensation import export_texts, model  # noqa: E402

MAX_TRANSPORT_RETRIES = 3
FALLBACK_STATUSES = ('fallback_refusal', 'fallback_failure', 'fallback_empty')
CAPPED_STATUSES = FALLBACK_STATUSES + ('truncated',)
ALL_STATUSES = ('ok',) + CAPPED_STATUSES


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ----------------------------------------------------------------------------- 长度预算（NeuML 分词）

class TokenBudget:
    """按 NeuML 分词器计数（含 [CLS]/[SEP]，与特征提取的 max_length=200 口径一致）并按字符偏移截断。"""

    def __init__(self, tokenizer, max_tokens: int):
        self.tokenizer = tokenizer
        self.max_tokens = int(max_tokens)

    def count(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=True)['input_ids'])

    def truncate(self, text: str) -> str:
        """返回原文的一个前缀，使其 token 数 ≤ max_tokens；切点落在某个 token 的字符结束处。"""
        if self.count(text) <= self.max_tokens:
            return text
        enc = self.tokenizer(text, add_special_tokens=True, truncation=True, max_length=self.max_tokens,
                             return_offsets_mapping=True)
        ends = [end for start, end in enc['offset_mapping'] if end > start]
        cut = text[:max(ends)] if ends else ''
        while cut and self.count(cut) > self.max_tokens:  # 前缀重新分词偶尔多出 token 时逐 token 收缩
            ends = [end for end in ends if end < len(cut)]
            cut = text[:max(ends)] if ends else ''
        return cut

    def truncate_clean(self, text: str) -> str:
        """LLM 输出超长时用：先按 token 截，再退回到最后一个完整句子 / 字段（后接空白的 . 或 ;），
        找不到就退回到完整单词。按 token 硬切会把 "FIGO IIIC" 切成 "FIGO II"，产生原文没有的错值
        （Codex 抽查 TCGA-BG-A0M6，2026-09-26）。"""
        cut = self.truncate(text)
        if len(cut) == len(text):
            return text
        bounds = [m.end() for m in re.finditer(r'[.;](?=\s|$)', text) if m.end() <= len(cut)]
        if bounds:
            return text[:max(bounds)]
        words = [m.start() for m in re.finditer(r'\s', text) if m.start() <= len(cut)]
        return text[:max(words)].rstrip() if words else ''


def load_neuml_budget(tokenizer_dir, max_tokens):
    from transformers import AutoTokenizer  # 只在真实运行时需要
    return TokenBudget(AutoTokenizer.from_pretrained(str(tokenizer_dir), use_fast=True), max_tokens)


# ----------------------------------------------------------------------------- 客户端接口

@dataclass
class Response:
    status: str                 # succeeded / errored / expired / canceled
    stop_reason: str | None = None
    model: str | None = None
    text: str | None = None     # 第一个 text 块
    usage: dict = field(default_factory=dict)
    error_type: str | None = None


class AnthropicBatchClient:
    """Message Batches API（结构化输出放在 output_config.format，effort 放在 output_config）。"""

    def __init__(self, *, model_id: str, effort: str, max_output_tokens: int, poll_seconds: int = 60, log=print,
                 resume_batch_ids=(), client=None):
        if client is None:
            import anthropic  # 只在真实运行时需要；API key 由环境提供，本代码不读取也不记录
            client = anthropic.Anthropic()
        self.client = client
        self.model_id, self.effort, self.max_output_tokens = model_id, effort, int(max_output_tokens)
        self.poll_seconds, self.log = poll_seconds, log
        self.batch_ids = []
        # 续跑：本地进程中断后，按原顺序回放已提交批次的结果（状态机确定，回放即恢复中断时的状态）
        self.resume_batch_ids = list(resume_batch_ids)

    def run(self, requests: dict) -> dict:
        if self.resume_batch_ids:
            batch_id = self.resume_batch_ids.pop(0)
            self.batch_ids.append(batch_id)
            self.log(f'batch {batch_id}: 续跑，回放已提交批次')
            return self._collect(batch_id, expected=set(requests))
        # Request / MessageCreateParamsNonStreaming 都是 TypedDict，直接写 dict，发出的请求相同
        batch = self.client.messages.batches.create(requests=[
            {'custom_id': cid, 'params': {
                'model': self.model_id, 'max_tokens': self.max_output_tokens, 'system': req['system'],
                'messages': [{'role': 'user', 'content': req['user']}],
                'output_config': {'format': {'type': 'json_schema', 'schema': req['schema']}, 'effort': self.effort}}}
            for cid, req in requests.items()])
        self.batch_ids.append(batch.id)
        self.log(f'batch {batch.id}: {len(requests)} 份已提交')
        return self._collect(batch.id, expected=set(requests))

    def _collect(self, batch_id: str, *, expected: set) -> dict:
        while self.client.messages.batches.retrieve(batch_id).processing_status != 'ended':
            time.sleep(self.poll_seconds)
        out = {}
        for result in self.client.messages.batches.results(batch_id):
            kind = result.result.type
            if kind == 'succeeded':
                msg = result.result.message
                text = next((b.text for b in msg.content if b.type == 'text'), None)
                usage = msg.usage.model_dump() if hasattr(msg.usage, 'model_dump') else dict(msg.usage)
                out[result.custom_id] = Response('succeeded', msg.stop_reason, msg.model, text, usage)
            else:
                error = getattr(getattr(result.result, 'error', None), 'type', None)
                out[result.custom_id] = Response(kind, error_type=error)
        if set(out) != expected:  # 续跑时重建的请求必须与该批次逐一对应，否则状态已分叉
            raise ValueError(f'批次 {batch_id} 的 custom_id 与本轮请求不一致：'
                             f'缺 {len(expected - set(out))} 份，多 {len(set(out) - expected)} 份')
        return out


# ----------------------------------------------------------------------------- 浓缩核心

@dataclass
class _State:
    row: dict
    transport: int = 0
    refusals: int = 0
    regenerations: int = 0
    length_retries: int = 0
    feedback: str | None = None
    attempts: list = field(default_factory=list)
    record: dict | None = None


def _parse(arm, cancer, text):
    payload = json.loads(text)
    return model.validate_struct(cancer, payload) if arm == 'struct' else model.validate_summary(payload)


def condense(rows, *, arm: str, client, budget: TokenBudget, prompts: dict, llm: dict, length: dict,
             target_words: int | None = None, log=print) -> list:
    """浓缩一批报告，返回逐份记录（顺序同输入）。"""
    states = {row['patient_id']: _State(row) for row in rows}
    if len(states) != len(rows):
        raise ValueError('患者 ID 重复')
    max_tokens = budget.max_tokens
    round_no = 0

    def finish(state, status, text, payload=None, response=None):
        state.record = {
            'patient_id': state.row['patient_id'], 'cancer': state.row['cancer'], 'split': state.row['split'],
            'arm': arm, 'status': status, 'text': text, 'text_sha256': sha256_text(text),
            'n_tokens': budget.count(text), 'payload': payload,
            'model': response.model if response is not None else None,
            'input_text_sha256': state.row['text_sha256'], 'attempts': state.attempts}

    def fallback(state, status):
        finish(state, status, budget.truncate(state.row['text']))

    while True:
        pending = [s for s in states.values() if s.record is None]
        if not pending:
            break
        round_no += 1
        requests = {}
        for state in pending:
            req = model.build_request(arm, state.row['cancer'], state.row['text'], prompts=prompts,
                                      target_words=target_words)
            if state.feedback is not None:
                req = {**req, 'user': req['user'] + state.feedback}
            requests[f"{arm[0]}-{state.row['patient_id']}-r{round_no}"] = req
        responses = client.run(requests)
        log(f'{arm} 第 {round_no} 轮：{len(requests)} 份')
        for cid, state in zip(requests, pending):
            resp = responses.get(cid) or Response('errored', error_type='missing_result')
            attempt = {'round': round_no, 'custom_id': cid, 'status': resp.status, 'stop_reason': resp.stop_reason,
                       'model': resp.model, 'usage': resp.usage, 'error_type': resp.error_type,
                       'output_sha256': sha256_text(resp.text) if resp.text is not None else None}
            state.attempts.append(attempt)
            if resp.status != 'succeeded':
                state.transport += 1
                if state.transport > MAX_TRANSPORT_RETRIES:
                    fallback(state, 'fallback_failure')
                continue
            if resp.stop_reason == 'refusal':
                state.refusals += 1
                if state.refusals > llm['refusal_retries']:
                    fallback(state, 'fallback_refusal')
                continue
            try:
                if resp.stop_reason == 'max_tokens' or resp.text is None:
                    raise ValueError('输出不完整')
                payload = _parse(arm, state.row['cancer'], resp.text)
            except ValueError:  # json.JSONDecodeError 是 ValueError 的子类
                state.regenerations += 1
                if state.regenerations > llm['max_regenerations']:
                    fallback(state, 'fallback_failure')
                continue
            text = model.serialize(arm, state.row['cancer'], payload)
            if not text:
                finish(state, 'fallback_empty', budget.truncate(state.row['text']), payload, resp)
                continue
            n_tokens = budget.count(text)
            if n_tokens <= max_tokens:
                finish(state, 'ok', text, payload, resp)
            elif state.length_retries < length['length_retries']:
                state.length_retries += 1
                state.feedback = ('\n\nPrevious answer:\n<previous>\n' + resp.text + '\n</previous>\n'
                                  + model.length_retry_message(n_tokens, max_tokens, prompts=prompts))
            else:
                finish(state, 'truncated', budget.truncate_clean(text), payload, resp)
    records = [states[row['patient_id']].record for row in rows]
    models = {r['model'] for r in records if r['model'] is not None}
    if len(models) > 1:
        raise ValueError(f'同一臂返回了多个模型版本字符串: {sorted(models)}')
    return records


def retruncate(records, *, arm: str, budget: TokenBudget) -> tuple:
    """对已有记录的 truncated 份，用保存的 payload 在本地按 truncate_clean 重新截断（不调用 LLM）。"""
    out, changed = [], 0
    for record in records:
        if record['status'] == 'truncated':
            text = budget.truncate_clean(model.serialize(arm, record['cancer'], record['payload']))
            if not text:
                raise ValueError(f"{record['patient_id']}: 按边界截断后为空")
            if text != record['text']:
                changed += 1
            record = {**record, 'text': text, 'text_sha256': sha256_text(text), 'n_tokens': budget.count(text),
                      'truncation': 'sentence_boundary'}
        out.append(record)
    return out, changed


def capped_fraction(records) -> float:
    return sum(r['status'] in CAPPED_STATUSES for r in records) / len(records) if records else 0.0


def fallback_fraction(records) -> float:
    """退回原文的占比。上限只管这一类：退回的原文与浓缩文本在嵌入空间分簇，可能被模型当作指示量；
    截断只去掉浓缩文本末尾几个 token，不形成分簇，只报告（用户裁决 2026-09-26）。"""
    return sum(r['status'] in FALLBACK_STATUSES for r in records) / len(records) if records else 0.0


def truncated_fraction(records) -> float:
    return sum(r['status'] == 'truncated' for r in records) / len(records) if records else 0.0


# ----------------------------------------------------------------------------- 试点与摘要长度目标

def pilot_rows(rows, *, config) -> list:
    """train split 每癌固定种子抽 per_cancer 份（只读纯文本清单，不看标签）。"""
    pilot = config['pilot']
    rng = random.Random(pilot['seed'])
    chosen = []
    for cancer in config['cancers']:
        pool = sorted((r for r in rows if r['cancer'] == cancer and r['split'] == pilot['split']),
                      key=lambda r: r['patient_id'])
        if len(pool) < pilot['per_cancer']:
            raise ValueError(f'{cancer} 的 {pilot["split"]} 报告不足 {pilot["per_cancer"]} 份')
        chosen.extend(rng.sample(pool, pilot['per_cancer']))
    return sorted(chosen, key=lambda r: r['patient_id'])


def summary_target_words(struct_records, summary_records) -> int:
    """摘要臂长度目标：结构化臂试点序列化文本的 NeuML token 中位数，按试点摘要的 token/词 比换算成词数。"""
    ok_struct = [r['n_tokens'] for r in struct_records if r['status'] == 'ok']
    ratios = [r['n_tokens'] / len(r['text'].split()) for r in summary_records
              if r['status'] == 'ok' and r['text'].split()]
    if not ok_struct or not ratios:
        raise ValueError('试点记录不足，无法确定摘要长度目标')
    return max(1, round(statistics.median(ok_struct) / statistics.median(ratios)))


def write_records(path, records) -> str:
    path = Path(path)
    with path.open('x', encoding='utf-8') as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    return export_texts.sha256_file(path)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ['retruncate']:
        return retruncate_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--texts', type=Path, required=True, help='export_texts.py 产出的纯文本清单')
    parser.add_argument('--arm', choices=model.ARMS, required=True)
    parser.add_argument('--scope', choices=('pilot', 'all'), required=True)
    parser.add_argument('--tokenizer', type=Path, required=True, help='NeuML 分词器目录（锁定 revision）')
    parser.add_argument('--target-words', type=int, help='摘要臂必填：试点为 config 的 pilot_summary_words，全量为试点写死的值')
    parser.add_argument('--out', type=Path, required=True, help='逐份记录 JSONL（已存在即失败）')
    parser.add_argument('--resume-batch-ids', nargs='+', default=(),
                        help='本地进程中断后续跑：按原顺序给出已提交的批次号，回放结果后继续后续轮次')
    parser.add_argument('--config', type=Path, default=export_texts.DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    config = export_texts.load_config(args.config)
    if args.arm == 'summary' and args.target_words is None:
        parser.error('摘要臂必须给出 --target-words')
    rows = export_texts.read_export(args.texts, config=config)
    if args.scope == 'pilot':
        rows = pilot_rows(rows, config=config)
    llm = config['llm']
    client = AnthropicBatchClient(model_id=llm['model'], effort=llm['effort'],
                                  max_output_tokens=llm['max_output_tokens'], resume_batch_ids=args.resume_batch_ids)
    budget = load_neuml_budget(args.tokenizer, config['length']['max_neuml_tokens'])
    records = condense(rows, arm=args.arm, client=client, budget=budget, prompts=model.load_prompts(),
                       llm=llm, length=config['length'], target_words=args.target_words)
    digest = write_records(args.out, records)
    frac = fallback_fraction(records)
    print(json.dumps({'n': len(records), 'records_sha256': digest, 'batch_ids': client.batch_ids,
                      'fallback_fraction': frac, 'truncated_fraction': truncated_fraction(records)},
                     ensure_ascii=False))
    if frac > config['fallback_cap']:
        print(f'退回原文占比 {frac:.4f} 超过上限 {config["fallback_cap"]}，停下交用户', file=sys.stderr)
        return 3
    return 0


def retruncate_main(argv) -> int:
    parser = argparse.ArgumentParser(description='按句子 / 字段边界重新截断已有记录的 truncated 份（本地，不调用 LLM）')
    parser.add_argument('--records', type=Path, required=True)
    parser.add_argument('--arm', choices=model.ARMS, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='新的记录文件（已存在即失败）')
    parser.add_argument('--config', type=Path, default=export_texts.DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    config = export_texts.load_config(args.config)
    records = [json.loads(line) for line in args.records.read_text(encoding='utf-8').splitlines() if line]
    budget = load_neuml_budget(args.tokenizer, config['length']['max_neuml_tokens'])
    records, changed = retruncate(records, arm=args.arm, budget=budget)
    print(json.dumps({'n': len(records), 'changed': changed, 'records_sha256': write_records(args.out, records)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
