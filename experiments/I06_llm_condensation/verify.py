#!/usr/bin/env python3
"""浓缩质量检查（研究计划书 4.6，瘦身版）：源文本自动核验 + 每臂抽查表 + 打分。

- flag：输出里的数字（含分数与百分数）、分级 / 分期字样与否定词，归一化后必须能在原文中找到；
  另查预后判断词表。只标记，不修改。退回的份（原文本身）不参与核验。
  原文归一化（试点核实后，用户裁决 2026-09-26）：分期 OCR 错字（pNO→pn0、pTlc→pt1c）、
  分开写的分期（"pT: 2a"→pt2a）、英文数字（four→4）；分数的分子分母都能在原文找到即视为有依据（各站加总）。
- sheet：每臂按固定种子随机抽 ``audit_per_arm`` 份（sample=random，用于无偏估计比率），另加全部被自动核验标记的份
  （sample=flagged，优先人工复核），写成 CSV 抽查表，由用户填三列 0/1。
- judge-chunks / apply-judge：Codex（跨厂商模型，只读）逐行评审抽查表（用户裁决 2026-09-26，参照 Tripathi 2025：
  AI 全审 + 人工复核）。Codex 判为有问题的行与每臂随机 ``human_check_negatives`` 行判为无问题的，标 needs_human=1，
  由用户复核后把 judge 改为 human。
- score：读回填好的抽查表，在随机样本上算幻觉率、遗漏率（Agresti–Coull 95% 区间），并报告核验标记率。
  自动核验只做初筛，不单独判失败（用户裁决 2026-09-26，参照 Lanino 2025 / Asgari 2025 / Vachhani 2026）；
  任何一行发现捏造的分期或预后即判"明显失败"。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
for _path in (str(REPO_ROOT / 'src'), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from experiments.I06_llm_condensation import condense, export_texts  # noqa: E402

NUMBER = re.compile(r'\d+(?:\.\d+)?(?:\s*/\s*\d+)?(?:\s*%)?')  # 百分号前允许空格（原文 "75 %"）
STAGE = re.compile(r'\b(?:y?p[tnm][0-4x](?:is|mi|[a-d])?\d?|g[1-4x]|figo|who)\b')
NEGATIONS = ('negative', 'absent', 'not identified', 'not seen', 'no evidence', 'free of', 'uninvolved', 'none')
VERDICT_COLUMNS = ('hallucination', 'omission', 'fabricated_prognosis_or_stage')
JUDGE_COLUMNS = ('judge', 'needs_human', 'codex_verdict', 'codex_evidence')
SHEET_COLUMNS = (('patient_id', 'cancer', 'arm', 'sample', 'records_sha256', 'flags', 'source_text', 'condensed_text')
                 + VERDICT_COLUMNS + JUDGE_COLUMNS + ('note',))
RUBRIC = EXPERIMENT_DIR / 'prompts' / 'judge_rubric.txt'
CHECKED_STATUSES = ('ok', 'truncated')


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower()).strip()


def _squash(token: str) -> str:
    return re.sub(r'\s+', '', token)


def number_tokens(text: str) -> set:
    """整段文本里的数字 token（去空白）；分数额外拆出分子与分母，百分数额外加入去掉 % 的形式。
    按完整 token 比对，避免 "3" 在原文 "2.3" 里被当成子串命中。"""
    tokens = set()
    for raw in NUMBER.findall(text):
        token = _squash(raw)
        tokens.add(token)
        tokens.update(part.rstrip('%') for part in token.split('/'))
        tokens.add(token.rstrip('%'))
    return tokens


WORD_NUMBERS = {w: str(i) for i, w in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
    'seventeen eighteen nineteen twenty'.split())}
# 原文里的分期写法：允许 p 与 T/N/M 之间、T/N/M 与数值之间有空白或冒号，数值允许 OCR 错字 o / l / i
SOURCE_STAGE = re.compile(r'\b(y?p)\s*([tnm])\s*:?\s*([0-4xoli])((?:is|mi|[a-d])?\d?)\b')
OCR_DIGIT = {'o': '0', 'l': '1', 'i': '1'}
LABEL_NAMES = re.compile(r'\bki-?67\b')


def source_stages(src: str) -> set:
    """原文（已 normalize）中的分期，规范成输出侧 STAGE 的写法（pnO→pn0、pt: 2a→pt2a、ptlc→pt1c）。"""
    return {prefix + axis + OCR_DIGIT.get(value, value) + suffix
            for prefix, axis, value, suffix in SOURCE_STAGE.findall(src)}


def source_numbers(src: str) -> set:
    """原文的数字 token，加上英文数字与分期里的数值（OCR 修正后）。"""
    numbers = number_tokens(src)
    numbers.update(WORD_NUMBERS[w] for w in re.findall(r'\b[a-z]+\b', src) if w in WORD_NUMBERS)
    numbers.update(OCR_DIGIT.get(value, value) for _, _, value, _ in SOURCE_STAGE.findall(src) if value != 'x')
    return numbers


def _number_grounded(raw: str, src_numbers: set) -> bool:
    token = _squash(raw)
    if token in src_numbers:
        return True
    if '/' in token:  # 分数：分子分母都在原文出现（英文数字转写）即视为有依据；
        numerator, denominator = token.split('/', 1)  # 分子 0 = 原文"N 枚均阴性"，只要求分母在原文出现
        return denominator in src_numbers and (numerator == '0' or numerator in src_numbers)
    return False


def grounding_flags(output: str, source: str, *, prognostic_terms) -> list:
    """输出中找不到原文依据的数字 / 分期字样 / 否定词，以及出现的预后判断词。"""
    out, src = normalize(output), normalize(source)
    out = LABEL_NAMES.sub(' ', out)  # schema 标签名里的数字不是取值（Ki-67 与原文的 MIB-1 是同一指标）
    src_numbers, src_stages = source_numbers(src), source_stages(src)
    flags = []
    for raw in sorted(set(NUMBER.findall(out))):
        if not _number_grounded(raw, src_numbers):
            flags.append(f'number:{raw}')
    for token in sorted(set(STAGE.findall(out))):
        if token not in src and token not in src_stages:
            flags.append(f'stage:{token}')
    for word in NEGATIONS:
        if re.search(rf'\b{re.escape(word)}\b', out) and not re.search(rf'\b{re.escape(word)}\b', src):
            flags.append(f'negation:{word}')
    for term in prognostic_terms:
        if re.search(rf'\b{re.escape(term.lower())}\b', out):
            flags.append(f'prognostic:{term}')
    return flags


def records_digest(records) -> str:
    """一臂记录的内容摘要（按 patient_id 排序）：质量报告据此绑定它核验的是哪一份记录。"""
    body = json.dumps(sorted(records, key=lambda r: r['patient_id']), ensure_ascii=False, sort_keys=True)
    return condense.sha256_text(body)


def check_statuses(records) -> None:
    unknown = sorted({r['status'] for r in records} - set(condense.ALL_STATUSES))
    if unknown:
        raise ValueError(f'未知的记录状态: {unknown}')


def flag_records(records, sources: dict, *, config) -> dict:
    check_statuses(records)
    terms = config['verify']['prognostic_terms']
    per_patient, checked = {}, 0
    for record in records:
        if record['status'] not in CHECKED_STATUSES:
            continue
        checked += 1
        flags = grounding_flags(record['text'], sources[record['patient_id']], prognostic_terms=terms)
        if flags:
            per_patient[record['patient_id']] = flags
    arms = {r['arm'] for r in records}
    if len(arms) != 1:
        raise ValueError(f'一份记录文件只能含一个臂: {sorted(arms)}')
    return {'arm': arms.pop(), 'records_sha256': records_digest(records), 'checked': checked,
            'flagged': len(per_patient), 'flag_rate': len(per_patient) / checked if checked else 0.0,
            'flags': per_patient}


def audit_sample(records, *, config) -> list:
    """随机样本（固定种子）：用于无偏估计幻觉率与遗漏率。"""
    rng = random.Random(config['verify']['audit_seed'])
    pool = sorted(records, key=lambda r: r['patient_id'])
    n = min(config['verify']['audit_per_arm'], len(pool))
    return sorted(rng.sample(pool, n), key=lambda r: r['patient_id'])


def audit_plan(records, flagged_ids, *, config) -> dict:
    """patient_id → random / flagged：随机样本之外，再加全部被标记的份（初筛结果交人工复核）。"""
    plan = {r['patient_id']: 'random' for r in audit_sample(records, config=config)}
    plan.update({pid: 'flagged' for pid in sorted(flagged_ids) if pid not in plan})
    return plan


def write_sheet(path, records, sources: dict, flags: dict, *, config) -> None:
    with Path(path).open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        plan = audit_plan(records, flags['flags'], config=config)
        for record in sorted((r for r in records if r['patient_id'] in plan), key=lambda r: r['patient_id']):
            writer.writerow({'patient_id': record['patient_id'], 'cancer': record['cancer'], 'arm': record['arm'],
                             'sample': plan[record['patient_id']], 'records_sha256': flags['records_sha256'],
                             'flags': '; '.join(flags['flags'].get(record['patient_id'], [])),
                             'source_text': sources[record['patient_id']], 'condensed_text': record['text'],
                             **{col: '' for col in VERDICT_COLUMNS + JUDGE_COLUMNS}, 'note': ''})


def read_sheet(path) -> list:
    with Path(path).open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    if not rows or tuple(rows[0]) != SHEET_COLUMNS:
        raise ValueError(f'{path}: 抽查表为空或列不符')
    return rows


def judge_chunks(sheet_path, out_dir, *, chunk_size: int) -> list:
    """把抽查表切成评审输入：只给原文与浓缩文本（不给自动核验标记，评审独立判断）。row_id = 表内行号。"""
    rows = read_sheet(sheet_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    paths = []
    for start in range(0, len(rows), chunk_size):
        path = out_dir / f'chunk-{start // chunk_size:03d}.json'
        items = [{'row_id': i, 'cancer': row['cancer'], 'arm': row['arm'], 'original_report': row['source_text'],
                  'condensed_text': row['condensed_text']} for i, row in enumerate(rows) if start <= i < start + chunk_size]
        path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
        paths.append(path)
    return paths


def apply_judge(sheet_path, verdicts: list, out_path, *, config) -> dict:
    """把 Codex 判定写回抽查表：判定列先取 Codex 的，judge=codex；判为有问题的行与随机若干判为无问题的行标 needs_human=1。"""
    rows = read_sheet(sheet_path)
    by_id = {}
    for v in verdicts:
        if v['row_id'] in by_id or not 0 <= v['row_id'] < len(rows):
            raise ValueError(f"评审结果 row_id 重复或越界: {v['row_id']}")
        if any(v[col] not in (0, 1) for col in VERDICT_COLUMNS):
            raise ValueError(f"row {v['row_id']}: 判定必须是 0 或 1")
        by_id[v['row_id']] = v
    if len(by_id) != len(rows):
        raise ValueError(f'评审结果缺 {len(rows) - len(by_id)} 行')
    negatives = [i for i in range(len(rows)) if not any(by_id[i][c] for c in VERDICT_COLUMNS)]
    rng = random.Random(config['verify']['audit_seed'])
    checks = set(rng.sample(negatives, min(config['verify']['human_check_negatives'], len(negatives))))
    for i, row in enumerate(rows):
        v = by_id[i]
        row.update({col: str(v[col]) for col in VERDICT_COLUMNS})
        positive = any(v[col] for col in VERDICT_COLUMNS)
        row.update(judge='codex', needs_human='1' if positive or i in checks else '0',
                   codex_verdict=','.join(str(v[col]) for col in VERDICT_COLUMNS), codex_evidence=v['evidence'])
    with Path(out_path).open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {'rows': len(rows), 'codex_positive': len(rows) - len(negatives), 'needs_human': sum(r['needs_human'] == '1' for r in rows)}


def agresti_coull(x: int, n: int, z: float = 1.959964) -> tuple:
    if n <= 0:
        raise ValueError('样本量必须为正')
    n_t = n + z * z
    p_t = (x + z * z / 2) / n_t
    half = z * math.sqrt(p_t * (1 - p_t) / n_t)
    return max(0.0, p_t - half), min(1.0, p_t + half)


def score(sheet_path, flags: dict, *, config) -> dict:
    rows = read_sheet(sheet_path)
    for row in rows:
        if row['judge'] not in ('codex', 'human'):
            raise ValueError(f"{row['patient_id']}: judge 必须是 codex 或 human")
        if row['needs_human'] == '1' and row['judge'] != 'human':
            raise ValueError(f"{row['patient_id']}: 该行需人工复核（needs_human=1），复核后把 judge 改为 human")
        for col in VERDICT_COLUMNS:
            if row[col].strip() not in ('0', '1'):
                raise ValueError(f"{row['patient_id']}: 列 {col} 必须填 0 或 1")
    if any(row['arm'] != flags['arm'] for row in rows):
        raise ValueError('抽查表与核验结果不属于同一臂')
    # round2 R2：抽查表逐行带生成时的记录摘要；记录重新生成后，旧表的人工判定不能套到新记录上
    if any(row.get('records_sha256') != flags['records_sha256'] for row in rows):
        raise ValueError('抽查表不是对这份记录生成的（records_sha256 不符），需要重新生成抽查表并重新填写')
    randoms = [row for row in rows if row['sample'] == 'random']
    if not randoms:
        raise ValueError('抽查表没有随机样本')
    n = len(randoms)
    # 绑定核验的记录与实际抽查的患者，冻结时据此核对（Codex 节点一 finding 3）
    result = {'arm': flags['arm'], 'records_sha256': flags['records_sha256'],
              'sheet_sha256': export_texts.sha256_file(sheet_path), 'audited': n,
              'audit_patients': sorted(row['patient_id'] for row in randoms),
              'flagged_reviewed': sorted(row['patient_id'] for row in rows if row['sample'] == 'flagged'),
              'flag_rate': flags['flag_rate'], 'flagged': flags['flagged'], 'checked': flags['checked']}
    for col in VERDICT_COLUMNS:  # 比率只在随机样本上估计（无偏）；被标记的份另报计数
        x = sum(row[col].strip() == '1' for row in randoms)
        low, high = agresti_coull(x, n)
        result[col] = {'count': x, 'rate': x / n, 'ci95_agresti_coull': [low, high],
                       'flagged_count': sum(row[col].strip() == '1' for row in rows if row['sample'] == 'flagged')}
    reviewed = [row for row in rows if row['needs_human'] == '1']
    agree = sum(row['codex_verdict'] == ','.join(row[c].strip() for c in VERDICT_COLUMNS) for row in reviewed)
    result['judge'] = {'codex_rows': len(rows), 'human_reviewed': len(reviewed), 'human_agrees_with_codex': agree,
                       'rubric_sha256': export_texts.sha256_file(RUBRIC)}
    reasons = []
    fabricated = [row['patient_id'] for row in rows if row['fabricated_prognosis_or_stage'].strip() == '1']
    if fabricated:
        reasons.append(f'抽查发现捏造的预后 / 分期内容: {fabricated}')
    result['obvious_failure'] = bool(reasons)
    result['failure_reasons'] = reasons
    return result


def _load(args, config):
    records = [json.loads(line) for line in Path(args.records).read_text(encoding='utf-8').splitlines() if line]
    sources = {row['patient_id']: row['text'] for row in export_texts.read_export(args.texts, config=config)}
    return records, sources


def _write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    item = sub.add_parser('judge-chunks')
    item.add_argument('--sheet', type=Path, required=True)
    item.add_argument('--out-dir', type=Path, required=True)
    item.add_argument('--chunk-size', type=int, default=40)
    item = sub.add_parser('apply-judge')
    item.add_argument('--sheet', type=Path, required=True)
    item.add_argument('--verdicts', type=Path, nargs='+', required=True, help='Codex 各块返回的 JSON 数组文件')
    item.add_argument('--out', type=Path, required=True)
    for name in ('flag', 'sheet'):
        item = sub.add_parser(name)
        item.add_argument('--records', type=Path, required=True)
        item.add_argument('--texts', type=Path, required=True)
        item.add_argument('--out', type=Path, required=True)
    sub.choices['sheet'].add_argument('--flags', type=Path, required=True)
    item = sub.add_parser('score')
    item.add_argument('--sheet', type=Path, required=True)
    item.add_argument('--flags', type=Path, required=True)
    item.add_argument('--out', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=export_texts.DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    config = export_texts.load_config(args.config)
    if args.command == 'judge-chunks':
        print(json.dumps([str(p) for p in judge_chunks(args.sheet, args.out_dir, chunk_size=args.chunk_size)]))
        return 0
    if args.command == 'apply-judge':
        verdicts = [v for path in args.verdicts for v in json.loads(Path(path).read_text(encoding='utf-8'))]
        print(json.dumps(apply_judge(args.sheet, verdicts, args.out, config=config), ensure_ascii=False))
        return 0
    if args.command == 'flag':
        records, sources = _load(args, config)
        result = flag_records(records, sources, config=config)
        _write_json(args.out, result)
        print(json.dumps({k: result[k] for k in ('arm', 'checked', 'flagged', 'flag_rate')}, ensure_ascii=False))
    elif args.command == 'sheet':
        records, sources = _load(args, config)
        write_sheet(args.out, records, sources, json.loads(Path(args.flags).read_text(encoding='utf-8')),
                    config=config)
    else:
        result = score(args.sheet, json.loads(Path(args.flags).read_text(encoding='utf-8')), config=config)
        _write_json(args.out, result)
        print(json.dumps(result, ensure_ascii=False))
        return 4 if result['obvious_failure'] else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
