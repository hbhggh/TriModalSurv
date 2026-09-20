"""只读交接验收：无需 torch、模型、网络或原始患者数据。"""
from pathlib import Path
import csv
import hashlib
import itertools
import json
import math
import re
import sys
from urllib.parse import unquote

CANCERS = ['LGG', 'BRCA', 'BLCA', 'LUAD', 'UCEC']
SEEDS = [123, 132, 213, 231, 321]
GRIDS = ['none', 'rna_100', 'text_100', 'both_100']
ARMS = ['strategy0', 'm1', 'm0real']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_rows(rows):
    expected = set(itertools.product(CANCERS, SEEDS, GRIDS, ARMS))
    keys = [(r['cancer'], r['seed'], r['grid'], r['protocol']) for r in rows]
    assert len(keys) == len(set(keys)) == 300, '重复或缺少格点'
    assert set(keys) == expected, '矩阵范围不完整'
    for row in rows:
        assert set(row) == {'cancer', 'seed', 'grid', 'protocol', 'c_index_b'}
        assert math.isfinite(row['c_index_b']) and 0 <= row['c_index_b'] <= 1


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parent
    manifest = json.loads((evidence / 'package_manifest.json').read_text())
    for entry in manifest['files']:
        p = root / entry['path']
        assert p.is_file() and sha(p) == entry['sha256'], f'哈希不匹配: {p}'
        assert p.stat().st_size == entry['bytes']
    rows = json.loads((evidence / 'aggregate_rows.json').read_text())['rows']
    validate_rows(rows)
    values = {(r['cancer'], r['seed']): r['c_index_b'] for r in rows
              if r['grid'] == 'none' and r['protocol'] == 'strategy0'}
    with (evidence / 'none_baseline.csv').open(newline='') as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) == 25
    assert {(r['cancer'], int(r['seed'])): float(r['c_index_b'])
            for r in csv_rows} == values
    tex = (evidence / 'table1.tex').read_text()
    line = next(line for line in tex.splitlines() if line.startswith('None &'))
    numbers = [float(x) for x in re.findall(r'0\.\d{6}', line)]
    assert len(numbers) == 15
    pdf_order = ['BRCA', 'UCEC', 'LUAD', 'BLCA', 'LGG']
    for i, c in enumerate(pdf_order):
        mean = sum(values[c, s] for s in SEEDS) / 5
        assert float(f'{mean:.6f}') == numbers[i * 3 + 2]
    baseline_md = (evidence / 'None基线明细.md').read_text()
    prior_md = (root / 'Encoder实验先验知识-Pro版.md').read_text()
    for c in CANCERS:
        mean = sum(values[c, s] for s in SEEDS) / 5
        assert f'{mean:.6f}' in baseline_md and f'{mean:.6f}' in prior_md
    wins = []
    for c in CANCERS:
        means = {a: sum(r['c_index_b'] for r in rows
                        if r['cancer'] == c and r['protocol'] == a) / 20
                 for a in ARMS}
        if means['strategy0'] > max(means['m1'], means['m0real']):
            wins.append(c)
    assert set(wins) == {'LGG', 'BRCA', 'LUAD', 'UCEC'}
    # 仅核验新交接导航；原样保留的历史文档含旧绝对路径，不冒充可联网链接。
    nav_files = [root / n for n in [
        '给ChatGPT-Pro的结构化Prompt.md', 'Encoder实验先验知识-Pro版.md',
        'Pro交接使用说明.md']] + [evidence / '代码与来源说明.md']
    for p in nav_files:
        for target in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            target = unquote(target.strip('<>').split('#')[0])
            if not target or '://' in target:
                continue
            assert not target.startswith('/'), f'新导航有绝对链接: {target}'
            assert (p.parent / target).is_file(), f'缺附件: {target}'
    assert '跳过 Gemini' in (root / '给ChatGPT-Pro的结构化Prompt.md').read_text()
    assert '未实验' in prior_md and '保留天然缺失' in prior_md
    print(json.dumps({'passed': True, 'hashed_files': len(manifest['files']),
                      'aggregate_rows': 300, 'none_baseline_rows': 25,
                      'historical_four_scene_wins': wins,
                      'new_encoder_results': '未实验', 'training_or_evaluation_run': False},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
