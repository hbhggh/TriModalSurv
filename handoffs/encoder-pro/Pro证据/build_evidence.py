"""生成本次文档附件的机械快照与汇总，不运行科研代码。仅本机使用。"""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from verify_package import CANCERS, SEEDS, sha, validate_rows

ROOT = Path('/Users/wuhao/Desktop/TriModalSurv')
OUT = ROOT / 'experiments/innovation-secode-part- Encoder'
EV = OUT / 'Pro证据'
I01 = ROOT / 'experiments/I01_patient_retrieval'
R2 = I01 / 'knowledge/data-analysis-from-grok/2.progress/result'
R4 = I01 / 'knowledge/data-analysis-from-grok/4.progress'


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    from pypdf import PdfReader
    # 先核验结果，禁止失败后仍生成貌似完整的附件。
    source_json = R4 / 'runs/test/complete.json'
    result = json.loads(source_json.read_text())
    rows = [{k: r[k] for k in ['cancer', 'seed', 'grid', 'protocol', 'c_index_b']}
            for r in result['rows']]
    validate_rows(rows)
    assert result['status'] == 'COMPLETED' and result['frozen_enabled'] is True
    assert result['run_fingerprint'] == 'a825b3cc4df41cf56afe228be531a4fc13f69c520bf35a2f2305101652387ec2'
    tex_path = ROOT / 'manuscript/bmc_initial_draft/main.tex'
    tex = tex_path.read_text()
    start = tex.index('\\begin{sidewaystable}')
    end = tex.index('\\end{sidewaystable}', start) + len('\\end{sidewaystable}')
    table = tex[start:end] + '\n'
    assert 'tab:prototype-compensation' in table
    pdf_path = ROOT / 'manuscript/bmc_initial_draft/main.pdf'
    pdf_text = PdfReader(pdf_path).pages[6].extract_text()
    pdf_none = pdf_text.split('None', 1)[1].split('Overall', 1)[0]
    tex_none = next(line for line in table.splitlines() if line.startswith('None &'))
    assert re.findall(r'0\.\d{6}', pdf_none) == re.findall(r'0\.\d{6}', tex_none)
    sources = []

    def record(src, dest, mode='byte_copy', note=''):
        sources.append({'source_path': str(src), 'source_sha256': sha(src),
                        'package_path': str(dest.relative_to(OUT)) if dest else None,
                        'mode': mode, 'note': note})

    def copy(src, relative):
        dest = EV / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            assert sha(src) == sha(dest), f'已有快照不同，停止: {dest}'
        else:
            shutil.copyfile(src, dest)
        record(src, dest)

    for src, relative in [
        (OUT / 'innovation-Encoder.md', '原始需求-innovation-Encoder.md'),
        (OUT / 'Framework-encoder-tabel.excalidraw.svg', 'Framework-encoder-tabel.excalidraw.svg'),
        (pdf_path, 'main.pdf'),
        (ROOT / 'manuscript/消融实验/4progress-claude交接/实验先验知识与公式说明.md',
         '实验先验知识与公式说明-历史原文.md'),
        (ROOT / 'src/trimodalsurv/models/npjc.py', 'code/npjc_current.py'),
        (ROOT / 'src/trimodalsurv/evaluation/common.py', 'code/evaluation_common_current.py'),
        (ROOT / 'src/trimodalsurv/data/tcga_dataset.py', 'code/tcga_dataset_current.py'),
        (R4 / 'luad_m1_force/config.yaml', 'code/config_s0_force.yaml'),
        (R4 / 'luad_m1_force/model.py', 'code/s0_force_route.py'),
        (R2 / 'config.yaml', 'code/config_rules1to5.yaml'),
        (R2 / 'inference.py', 'code/inference_rules1to5.py'),
        (R2 / '02_wsi_meanpool_key/model.py', 'code/wsi_meanpool_key.py'),
        (R2 / '05_imputed_token_downweight/model.py', 'code/imputed_pooling.py'),
        (I01 / 'model.py', 'code/patient_bank.py'),
    ]:
        copy(src, relative)
    (EV / 'table1.tex').write_text(table)
    record(tex_path, EV / 'table1.tex', 'excerpt', '首个sidewaystable，tab:prototype-compensation')
    (EV / 'Table1-PDF提取文本.txt').write_text(pdf_text)
    record(pdf_path, EV / 'Table1-PDF提取文本.txt', 'derived', 'pypdf，第7页；None行15个数值与TeX逐一相同')
    dump(EV / 'aggregate_rows.json', {'source_run_fingerprint': result['run_fingerprint'],
         'source_file_sha256': sha(source_json), 'selection': 'rows，仅5个白名单字段', 'rows': rows})
    record(source_json, EV / 'aggregate_rows.json', 'field_projection',
           '300个聚合实验读数；排除所有患者、预测文件路径和asset列表')
    none = [r for r in rows if r['grid'] == 'none' and r['protocol'] == 'strategy0']
    values = {(r['cancer'], r['seed']): r['c_index_b'] for r in none}
    with (EV / 'none_baseline.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['cancer', 'seed', 'grid', 'protocol', 'c_index_b'])
        writer.writeheader()
        for c in CANCERS:
            for s in SEEDS:
                writer.writerow(dict(cancer=c, seed=s, grid='none', protocol='strategy0', c_index_b=values[c, s]))
    record(source_json, EV / 'none_baseline.csv', 'field_projection', 'rows中none/strategy0，25条原值')
    lines = ['# None / Proto.† 基线明细', '',
        '现有系统对照；不是新encoder结果。数据来自原始JSON，不从PDF舍入值反推。', '',
        '| Seed | ' + ' | '.join(CANCERS) + ' |', '| --- | ' + ' | '.join(['---'] * 5) + ' |']
    for s in SEEDS:
        lines.append('| ' + str(s) + ' | ' + ' | '.join(repr(values[c, s]) for c in CANCERS) + ' |')
    lines.append('| 五seed等权均值 | ' + ' | '.join(f'{sum(values[c,s] for s in SEEDS)/5:.6f}' for c in CANCERS) + ' |')
    lines += ['', 'JSON选择：rows，grid=none，protocol=strategy0，c_index_b；每癌五seed；不去除天然缺失。',
              '', '打包时核验：PDF第7页None行15个数值与TeX全部相同；由build_evidence.py使用pypdf完成。',
              '', '标准库重复核验命令：`python3 Pro证据/verify_package.py`（在交接包根目录）；核验包内哈希、JSON/CSV→均值与TeX的对应，不重新解析PDF。', '']
    (EV / 'None基线明细.md').write_text('\n'.join(lines))
    record(source_json, EV / 'None基线明细.md', 'derived', '原值repr和先平均后六位展示')
    upstream_path = R2 / 'runs/test/complete.json'
    upstream = json.loads(upstream_path.read_text())
    upstream_values = {r['seed']: r['c_index_b'] for r in upstream['rows']
                       if r['cancer'] == 'LUAD' and r['grid'] == 'none'
                       and r['protocol'] == 'combo'}
    assert set(upstream_values) == set(SEEDS)
    parity = [{'seed': s, 'upstream_combo': upstream_values[s],
               's0_force': values['LUAD', s], 'identical': upstream_values[s] == values['LUAD', s]}
              for s in SEEDS]
    assert all(r['identical'] for r in parity)
    dump(EV / 'luad_none_upstream_parity.json', {'cancer': 'LUAD', 'grid': 'none', 'rows': parity})
    record(upstream_path, EV / 'luad_none_upstream_parity.json', 'derived', 'LUAD none combo五seed与4.progress逐值比较')
    freeze_path = R4 / 'frozen-routing.json'
    freeze = json.loads(freeze_path.read_text())
    fields = ['protocol_id', 'enabled', 'a_mean', 'b_mean', 'b_minus_a', 'decision_rule', 'scientific_boundary']
    dump(EV / 'freeze_decision_excerpt.json', {k: freeze[k] for k in fields})
    record(freeze_path, EV / 'freeze_decision_excerpt.json', 'field_projection', 'valid裁决，无asset列表')
    # 保护旧文档、稿件和归档结果；前后哈希核对不是重跑或远端资产审计。
    protected = [OUT / 'Encoder实验先验知识.md', OUT / '给Gemini的结构化Prompt.md',
                 ROOT / 'manuscript/bmc_initial_draft/trimodalsurv-论文初版本-modify-from-bbag124.docx',
                 R4 / '癌症为单位.md', R4 / 'seed单位-实验结果.md']
    for p in protected:
        record(p, None, 'protected_only', '不修改、不上传该文件')
    dump(EV / 'source_manifest.json', {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'current_local_head_not_historical_run_commit': subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'entries': sources,
        'scope': '本地文档及代码快照；未核验远端权重/缓存；非训练或评测执行'})
    print('来源快照/300格聚合投影/25条None/PDF-TeX已生成并核对')


if __name__ == '__main__':
    main()
