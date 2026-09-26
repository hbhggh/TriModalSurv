#!/usr/bin/env python3
"""冻结浓缩文本（研究计划书 4.6）：写 freeze manifest 与供特征提取读取的冻结文本清单。

拒绝冻结的情形：任一臂质量检查"明显失败"；质量报告不是对这份记录做的（记录摘要、checked 数或抽查患者集合不符）；
未知的记录状态；退回原文超过 fallback_cap（截断只报告）；两臂患者集合与纯文本清单不同；
逐份文本哈希不符；两臂返回的模型版本字符串不一致或与 config 不符。
冻结文本清单每行只有 patient_id / cancer / split / text / text_sha256 / status，I05 提取器只读它。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I06_llm_condensation import condense, export_texts, model, verify  # noqa: E402

FROZEN_COLUMNS = ('patient_id', 'cancer', 'split', 'text', 'text_sha256', 'status')


def read_jsonl(path) -> list:
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def check_quality_binding(arm, records, quality, *, texts, config) -> None:
    """质量报告必须是对这一份记录做的核验与抽查（Codex 节点一 finding 3）。"""
    checked = sum(r['status'] in verify.CHECKED_STATUSES for r in records)
    audit = [r['patient_id'] for r in verify.audit_sample(records, config=config)]
    flags = verify.flag_records(records, {pid: row['text'] for pid, row in texts.items()}, config=config)
    flagged = sorted(pid for pid in flags['flags'] if pid not in set(audit))
    expected = {'arm': arm, 'records_sha256': verify.records_digest(records), 'checked': checked,
                'audited': len(audit), 'audit_patients': audit, 'flagged_reviewed': flagged}
    mismatched = sorted(key for key, value in expected.items() if quality.get(key) != value)
    if mismatched:
        raise ValueError(f'{arm}: 质量报告不属于这份记录: {mismatched}')


def check_arm(arm, records, quality, *, texts, config) -> dict:
    verify.check_statuses(records)
    ids = [r['patient_id'] for r in records]
    if sorted(ids) != sorted(texts) or len(ids) != len(set(ids)):
        raise ValueError(f'{arm}: 患者集合与纯文本清单不同')
    for r in records:
        if r['arm'] != arm:
            raise ValueError(f"{r['patient_id']}: 记录属于 {r['arm']} 臂")
        if r['text_sha256'] != condense.sha256_text(r['text']):
            raise ValueError(f"{r['patient_id']}: 文本哈希不符")
        if r['input_text_sha256'] != texts[r['patient_id']]['text_sha256']:
            raise ValueError(f"{r['patient_id']}: 输入原文哈希与纯文本清单不符")
        if not r['text'].strip():
            raise ValueError(f"{r['patient_id']}: 冻结文本为空")
    check_quality_binding(arm, records, quality, texts=texts, config=config)
    if quality.get('obvious_failure') is not False:
        raise ValueError(f'{arm}: 质量检查未通过: {quality.get("failure_reasons")}')
    frac = condense.fallback_fraction(records)
    if frac > config['fallback_cap']:
        raise ValueError(f'{arm}: 退回原文占比 {frac:.4f} 超过上限')
    models = {r['model'] for r in records if r['model'] is not None}
    # 返回的版本字符串可能带快照后缀：要求全臂唯一，且以配置的模型 ID 开头
    if len(models) > 1 or any(not m.startswith(config['llm']['model']) for m in models):
        raise ValueError(f'{arm}: 模型版本字符串不符: {sorted(models)}')
    statuses = {}
    for r in records:
        statuses[r['status']] = statuses.get(r['status'], 0) + 1
    return {'n': len(records), 'statuses': statuses, 'fallback_fraction': frac,
            'truncated_fraction': condense.truncated_fraction(records), 'models': sorted(models),
            'max_tokens': max(r['n_tokens'] for r in records)}


def freeze(*, texts_path, struct_records, summary_records, struct_quality, summary_quality, target_words,
           out_dir, config) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    texts = {row['patient_id']: row for row in export_texts.read_export(texts_path, config=config)}
    arms = {'struct': (struct_records, struct_quality), 'summary': (summary_records, summary_quality)}
    summaries = {arm: check_arm(arm, recs, q, texts=texts, config=config) for arm, (recs, q) in arms.items()}
    models = {m for s in summaries.values() for m in s['models']}
    if len(models) > 1:
        raise ValueError(f'两臂模型版本字符串不一致: {sorted(models)}')
    files = {}
    for arm, (recs, _) in arms.items():
        path = out_dir / f'frozen-{arm}.jsonl'
        with path.open('x', encoding='utf-8') as handle:
            for r in sorted(recs, key=lambda x: x['patient_id']):
                handle.write(json.dumps({k: r[k] for k in FROZEN_COLUMNS}, ensure_ascii=False) + '\n')
        files[arm] = {'path': path.name, 'sha256': export_texts.sha256_file(path)}
    manifest = {
        'schema_version': 1, 'experiment': config['experiment'],
        'texts_sha256': export_texts.sha256_file(texts_path),
        'llm': {k: config['llm'][k] for k in ('provider', 'model', 'effort')}, 'returned_models': sorted(models),
        'prompts': {name: p['sha256'] for name, p in model.load_prompts().items()},
        'summary_target_words': int(target_words), 'max_neuml_tokens': config['length']['max_neuml_tokens'],
        'arms': summaries, 'quality': {'struct': struct_quality, 'summary': summary_quality}, 'frozen_texts': files}
    manifest_path = out_dir / 'freeze-manifest.json'
    with manifest_path.open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
    manifest['manifest_sha256'] = export_texts.sha256_file(manifest_path)
    return manifest


def read_frozen(path, *, expected_sha256=None) -> dict:
    """特征提取读取冻结文本的唯一入口：patient_id → text；逐行核对文本哈希，可选核对文件哈希。"""
    path = Path(path)
    if expected_sha256 is not None and export_texts.sha256_file(path) != expected_sha256:
        raise ValueError(f'冻结文本文件哈希不符: {path}')
    out = {}
    for row in read_jsonl(path):
        if tuple(row) != FROZEN_COLUMNS or condense.sha256_text(row['text']) != row['text_sha256']:
            raise ValueError(f"{row.get('patient_id')}: 冻结文本行损坏")
        out[row['patient_id']] = row
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--texts', type=Path, required=True)
    parser.add_argument('--struct-records', type=Path, required=True)
    parser.add_argument('--summary-records', type=Path, required=True)
    parser.add_argument('--struct-quality', type=Path, required=True)
    parser.add_argument('--summary-quality', type=Path, required=True)
    parser.add_argument('--target-words', type=int, required=True)
    parser.add_argument('--out-dir', type=Path, required=True, help='新目录（已存在即失败）')
    parser.add_argument('--config', type=Path, default=export_texts.DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    config = export_texts.load_config(args.config)
    manifest = freeze(texts_path=args.texts, struct_records=read_jsonl(args.struct_records),
                      summary_records=read_jsonl(args.summary_records),
                      struct_quality=json.loads(args.struct_quality.read_text(encoding='utf-8')),
                      summary_quality=json.loads(args.summary_quality.read_text(encoding='utf-8')),
                      target_words=args.target_words, out_dir=args.out_dir, config=config)
    print(json.dumps({'manifest_sha256': manifest['manifest_sha256'], 'frozen_texts': manifest['frozen_texts']},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
