"""只读核验历史结果，向 stdout 输出两份 Markdown；不训练、不改源数据。"""
import csv
import hashlib
import itertools
import json
import math
import statistics
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 50
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'legacy-tako-formal-20260915'
FORMAL = ARCHIVE / 'raw/tako-formal/evidence/formal'
CANCERS = ['BRCA', 'LUAD', 'UCEC', 'BLCA', 'LGG']
SEEDS = [123, 132, 213, 231, 321]
GRIDS = ['none', 'rna_100', 'text_100', 'both_100']
ARMS = ['retrieval', 'm1', 'm0real']
LABELS = dict(zip(ARMS, ['患者检索', '均值填补', '不补偿']))
PROTOCOL = 'patient-fixed-padmask-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(xs):
    xs = list(xs)
    assert xs
    return sum(xs, Decimal(0)) / len(xs)


def red(text):
    return '<span style="color:#c62828"><strong>' + str(text) + ' ★</strong></span>'


def winners(values):
    return [a for a in ARMS if values[a] == max(values.values())]


def row(cells):
    return '| ' + ' | '.join(str(x) for x in cells) + ' |'


def table(headers):
    return [row(headers), row(['---'] * len(headers))]


def main():
    manifest_path = ARCHIVE / 'historical_artifact_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = {x['copy']: x for x in manifest['files']}
    verified_hashes = {}

    def verify_copy(path):
        key = path.relative_to(ARCHIVE / 'raw').as_posix()
        entry = entries[key]
        digest = sha(path)
        assert digest == entry['sha256'], path
        original = Path(entry['original'])
        assert original.is_file() and sha(original) == digest, original
        verified_hashes[key] = digest

    status_path = FORMAL / 'diagnostics/campaign_status.json'
    verify_copy(status_path)
    status = json.loads(status_path.read_text())
    assert status['stage'] == 'formal' and status['status'] == 'COMPLETED'
    expected = {f'{a}_{c}_s{s}.json' for a, c, s in itertools.product(ARMS, CANCERS, SEEDS)}
    assert {p.name for p in FORMAL.glob('*.json')} == expected
    data, units = {}, {}
    artifact_count = 0
    for name in sorted(expected):
        path = FORMAL / name
        verify_copy(path)
        unit = json.loads(path.read_text(), parse_float=Decimal)
        a, c, s = unit['arm'], unit['cancer'], unit['seed']
        assert name == f'{a}_{c}_s{s}.json'
        assert unit['protocol_id'] == PROTOCOL and unit['stage'] == 'formal'
        assert set(unit['grids']) == set(GRIDS)
        units[a, c, s] = unit
        for g, value in unit['grids'].items():
            score = Decimal(value['cindex_B'])
            assert score.is_finite() and 0 <= score <= 1
            data[c, s, g, a] = score
            for kind in ['audit', 'predictions']:
                artifact = FORMAL / value[kind + '_file']
                assert artifact.is_file() and sha(artifact) == value[kind + '_sha256']
                artifact_count += 1
    for c, s in itertools.product(CANCERS, SEEDS):
        for field in ['checkpoint_sha256', 'comparison_fingerprint']:
            assert len({units[a, c, s][field] for a in ARMS}) == 1
        for g in GRIDS:
            for field in ['n_test', 'grid_sha']:
                assert len({units[a, c, s]['grids'][g][field] for a in ARMS}) == 1
    for c in CANCERS:
        assert len({units['retrieval', c, s]['checkpoint_sha256'] for s in SEEDS}) == 5
    assert len(data) == 300

    def values(keys):
        keys = list(keys)
        return {a: mean(data[c, s, g, a] for c, s, g in keys) for a in ARMS}

    overall = values(itertools.product(CANCERS, SEEDS, GRIDS))
    seed_scores = {s: values(itertools.product(CANCERS, [s], GRIDS)) for s in SEEDS}
    cancer_scores = {c: values(itertools.product([c], SEEDS, GRIDS)) for c in CANCERS}
    cell_scores = {(c, g): values(itertools.product([c], SEEDS, [g])) for c, g in itertools.product(CANCERS, GRIDS)}
    summary_path = ARCHIVE / 'raw/tako-formal/evidence/summary/per_cell.csv'
    verify_copy(summary_path)
    with summary_path.open() as f:
        old_rows = list(csv.DictReader(f))
    assert len(old_rows) == 60
    for r in old_rows:
        assert int(r['n_seeds']) == 5
        assert abs(float(cell_scores[r['cancer'], r['grid']][r['arm']]) - float(r['mean'])) < 1e-14
    best_seed = max(SEEDS, key=lambda s: seed_scores[s]['retrieval'])
    best_cancer = max(CANCERS, key=lambda c: cancer_scores[c]['retrieval'])
    best_cell = max(cell_scores, key=lambda k: cell_scores[k]['retrieval'])
    best_delta_seed = {a: max(SEEDS, key=lambda s: seed_scores[s]['retrieval'] - seed_scores[s][a]) for a in ARMS[1:]}
    best_delta_cancer = {a: max(CANCERS, key=lambda c: cancer_scores[c]['retrieval'] - cancer_scores[c][a]) for a in ARMS[1:]}
    unique_wins = {a: 0 for a in ARMS}
    ties = 0
    for c, s, g in itertools.product(CANCERS, SEEDS, GRIDS):
        win = winners({a: data[c, s, g, a] for a in ARMS})
        if len(win) == 1:
            unique_wins[win[0]] += 1
        else:
            ties += 1

    def comparison(prefix, v, std=None):
        win = winners(v)
        scores = []
        for a in ARMS:
            text = f'{v[a]:.6f}' + (f' ± {std[a]:.6f}' if std else '')
            scores.append(red(text) if a in win else text)
        title = '、'.join(LABELS[a] for a in win)
        if len(win) > 1:
            title += '（并列）'
        return row(list(prefix) + scores + [red(title), f"{v['retrieval']-v['m1']:+.6f}", f"{v['retrieval']-v['m0real']:+.6f}"])

    headers = ['患者检索', '均值填补', '不补偿', '本组三臂最佳', '检索−均值', '检索−不补偿']

    def opening(title):
        lines = [f'# {title}', '', f'协议：`{PROTOCOL}`；指标：B 口径 C-index，越大越好。', '',
                 '## 阅读与标红规则', '',
                 '- 每行把患者检索（retrieval）、均值填补（m1）、不补偿（m0real）放在同一组比较；组内最高的数值及实验名称标红加 ★，并列最高全部标红。表外红色结论句表示对应汇总范围的最高结果，不表示该方法在每组都胜出。',
                 '- 排名、标红和 Δ 均使用未四舍五入的原始值；展示保留六位小数，显示相同不一定是精确并列。Δ 先用原值相减再舍入，可能与展示值直接相减相差 0.000001。HTML 样式被阅读器屏蔽时，可用 ★ 识别最佳。',
                 '- `none`＝无额外人工遮挡，保留天然缺失，天然缺失仍按三臂规则处理；不是完整数据，也不是第四种人工缺失。本批次 BLCA/none 各 seed 的138/138位患者均为完整输入，无缺失可补，构成全部5组三臂并列；按用户要求仍纳入总体均值。',
                 '- `rna_100`＝人工遮挡 RNA；`text_100`＝人工遮挡文本；`both_100`＝同时人工遮挡 RNA 和文本。',
                 '- 按本次确认，四种场景全部等权参与汇总，不按患者数量加权，不剔除任何 seed。两列 Δ 分别相减，不计算“检索−均值−不补偿”。', '',
                 '## 总体三臂比较（含 none）', '',
                 '五癌 × 五 seed × 四场景＝100 组，每臂100个 C-index，共300个读数。', '']
        lines += table(['范围'] + headers)
        lines += [comparison(['全部100组等权均值'], overall), '',
                  f"组内独胜：患者检索 {unique_wins['retrieval']} 组、均值填补 {unique_wins['m1']} 组、不补偿 {unique_wins['m0real']} 组；并列最高 {ties} 组（不重复计入独胜）。", '',
                  f"结论：{red('总体均值填补最好，C-index = ' + format(overall['m1'], '.6f'))}；检索总体低于两种基线。红色表示描述性最高，不表示统计显著。", '']
        return lines

    def provenance():
        return ['## 数据来源、核验与边界', '',
                f'- [原始75份正式结果 JSON](<{FORMAL}>)：每份读取 `grids.<场景>.cindex_B`。',
                f'- [原始汇总](<{summary_path}>)：60个癌种×场景×臂的五 seed 均值均已复算对齐。',
                f'- [历史归档清单](<{manifest_path}>)：结果JSON和状态/汇总文件均核对清单 SHA-256，并与清单指向的原档案一致；600个 audit/prediction 引用文件核对记录哈希。',
                f'- [复算脚本](<{Path(__file__).resolve()}>)：`/usr/bin/python3 "{Path(__file__).resolve()}"` 输出两份报告文本及校验摘要，不修改文件。',
                '- 本次重新分组与聚合已有 C-index，未重新跑模型、训练或从患者预测重新计算 C-index；未改变原档案。',
                '- 五 seed 共用既有患者划分，不是五个独立患者队列。最高 seed 是测试结果的描述性排序，不可只保留最佳 seed 替代五 seed 结论。',
                '- 癌种之间患者构成和事件分布不同；跨癌绝对 C-index 最高不等于检索补偿增益最大。增益需看同癌同 seed 同场景的配对 Δ。',
                '- 本报告包含 none 的总体均值不能与历史仅含三种人工缺失的总体均值直接混用。', '']

    seed_lines = opening('Seed 单位实验结果')
    seed_lines += ['## 哪个 seed 的患者检索成绩最好？', '',
                   red(f"按检索绝对 C-index 排名：seed {best_seed} 最高，四场景×五癌等权均值 {seed_scores[best_seed]['retrieval']:.6f}。"), '',
                   f"相对均值填补增益最大的 seed 是 {best_delta_seed['m1']}；相对不补偿增益最大的 seed 是 {best_delta_seed['m0real']}。这是增益排名，不是检索绝对分排名。", '',
                   '每个 seed 汇总20组。表按患者检索均值降序；每行红色仍只表示该 seed 内三臂最佳。', '']
    seed_lines += table(['检索排名', 'seed'] + headers)
    for rank, s in enumerate(sorted(SEEDS, key=lambda s: seed_scores[s]['retrieval'], reverse=True), 1):
        seed_lines.append(comparison([rank, s], seed_scores[s]))
    seed_lines += ['', '## 按 seed 展开的全部实验数据', '']
    for s in SEEDS:
        seed_lines += [f'### Seed {s}', '', '5癌 × 4场景＝20组；每组三臂使用同一 checkpoint。', '']
        seed_lines += table(['癌种', '场景'] + headers)
        for c, g in itertools.product(CANCERS, GRIDS):
            seed_lines.append(comparison([c, g], {a: data[c, s, g, a] for a in ARMS}))
        seed_lines += ['']
    seed_lines += provenance()

    cancer_lines = opening('癌症为单位实验结果')
    cancer_lines += ['## 哪个癌种、哪个癌种场景的患者检索成绩最好？', '',
                     red(f"按检索绝对 C-index 排名：{best_cancer} 最高，四场景×五 seed 等权均值 {cancer_scores[best_cancer]['retrieval']:.6f}。"), '',
                     red(f"按癌种×场景的五 seed 检索均值排名：{best_cell[0]} / {best_cell[1]} 最高，为 {cell_scores[best_cell]['retrieval']:.6f}。"), '',
                     f"相对均值填补增益最大的癌种是 {best_delta_cancer['m1']}；相对不补偿增益最大的癌种是 {best_delta_cancer['m0real']}。不能把跨癌绝对分高直接解释为补偿更有效。", '',
                     '## 五癌总体排名（四场景全部纳入）', '', '每癌汇总20组，按检索均值降序；每行比较的是该癌种内三臂。', '']
    cancer_lines += table(['检索排名', '癌种'] + headers)
    for rank, c in enumerate(sorted(CANCERS, key=lambda c: cancer_scores[c]['retrieval'], reverse=True), 1):
        cancer_lines.append(comparison([rank, c], cancer_scores[c]))
    cancer_lines += ['', '## 癌种 × 场景排名（五 seed 均值 ± 样本标准差）', '',
                     '共20个癌种×场景组合，按检索均值降序。标准差使用五个 seed、ddof=1；红标比较均值，不比较标准差。', '']
    cancer_lines += table(['检索排名', '癌种', '场景'] + headers)
    for rank, (c, g) in enumerate(sorted(cell_scores, key=lambda k: cell_scores[k]['retrieval'], reverse=True), 1):
        std = {a: statistics.stdev(float(data[c, s, g, a]) for s in SEEDS) for a in ARMS}
        cancer_lines.append(comparison([rank, c, g], cell_scores[c, g], std))
    cancer_lines += ['', '## 按癌种展开的全部实验数据', '']
    for c in CANCERS:
        cancer_lines += [f'### {c}', '', '5 seed × 4场景＝20组；每组三臂使用同一 checkpoint。', '']
        cancer_lines += table(['Seed', '场景'] + headers)
        for s, g in itertools.product(SEEDS, GRIDS):
            cancer_lines.append(comparison([s, g], {a: data[c, s, g, a] for a in ARMS}))
        cancer_lines += ['']
    cancer_lines += provenance()
    docs = {'seed单位-实验结果.md': '\n'.join(seed_lines), '癌症为单位.md': '\n'.join(cancer_lines)}
    for name, text in docs.items():
        assert text.count('<span ') == text.count('</span>')
        assert text.count('<strong>') == text.count('</strong>')
        assert '\\n' not in text
    audit = {'protocol': PROTOCOL, 'metric': 'cindex_B', 'include_none': True,
             'units': len(units), 'values': len(data), 'groups': 100,
             'artifact_hashes_checked': artifact_count, 'source_sha256': verified_hashes,
             'manifest_sha256': sha(manifest_path),
             'overall': overall, 'seed_scores': seed_scores, 'cancer_scores': cancer_scores,
             'best_retrieval_seed': best_seed, 'best_retrieval_cancer': best_cancer,
             'best_retrieval_cell': best_cell, 'unique_wins': unique_wins, 'tied_groups': ties}
    print(json.dumps({'reports': docs, 'audit': audit}, ensure_ascii=False,
                     default=lambda obj: float(obj) if isinstance(obj, Decimal) else str(obj)))


if __name__ == '__main__':
    main()
