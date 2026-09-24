"""结果渲染（数值只来自原始 JSON）与发车契约（dry-run 逐参对比）。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_DIR.parents[1]

from experiments.I05_text_encoder_bcmbert.tools import render_encoder_tables as render  # noqa: E402

# 交接包 Pro证据/None基线明细.md 的 25 个原值（Table 1 None / Proto.† 的逐 seed 值）。
NONE_BASELINE = {
    'LGG': [0.8088336783988958, 0.7839889579020014, 0.8071083505866115, 0.7939958592132506, 0.7946859903381642],
    'BRCA': [0.6970591574883616, 0.6803678891790621, 0.6929714999432269, 0.6810491654365846, 0.6891109344839332],
    'BLCA': [0.6073907009021513, 0.6075641915336571, 0.4909784871616933, 0.614677307425399, 0.6292505204718946],
    'LUAD': [0.5714285714285714, 0.5786240786240786, 0.5793260793260794, 0.5845910845910846, 0.5984555984555985],
    'UCEC': [0.6501224126418874, 0.677053193857111, 0.6492321388827065, 0.6389939906521255, 0.6394391275317161],
}


@pytest.fixture(scope='module')
def config():
    return render.load_config(EXPERIMENT_DIR / 'config.yaml')


@pytest.fixture(scope='module')
def baseline(config):
    return render.load_baseline(REPO_ROOT / config['legacy']['test_complete'], config)


def test_baseline_is_table1_none_proto(config, baseline):
    values, meta = baseline
    assert meta['sha256'] == config['legacy']['test_complete_sha256']
    for cancer, expected in NONE_BASELINE.items():
        assert [values[(cancer, seed, 'none')] for seed in config['seeds']] == expected
        assert f'{sum(expected) / 5:.6f}' == f"{config['table1_none_proto'][cancer]:.6f}"


def test_template_render_is_deterministic_and_well_formed(config, baseline, tmp_path):
    values, meta = baseline
    first = render.render_all(config, values, None, meta, None)
    second = render.render_all(config, values, None, meta, None)
    assert first == second
    assert set(first) == set(render.FILENAMES)
    table = first['encoder-table.md']
    assert '| 现有系统 None / Proto.†（Table 1） | 0.797723 | 0.688112 | 0.589972 | 0.582485 | 0.650968 |' in table
    assert '| 其他方法的 Encoder | 未实验（算法待定） |' in table
    assert '严格胜率（none，Q 判定）：未实验。' in first['癌症为单位.md']
    assert first['seed单位-实验结果.md'].count('### Seed ') == 5
    assert first['癌症为单位.md'].index('### LGG') < first['癌症为单位.md'].index('### UCEC')
    render.write_documents(first, tmp_path)
    render.write_documents(second, tmp_path)
    (tmp_path / 'foreign.md').write_text('hand written')
    with pytest.raises(FileExistsError):
        render.write_documents({'foreign.md': 'x'}, tmp_path)


def test_q_judgement_counts_strict_wins_only(config, baseline):
    values, meta = baseline
    new = dict(values)
    shifts = {'LGG': 0.01, 'BRCA': 0.01, 'BLCA': 0.0, 'LUAD': 0.01, 'UCEC': -0.01}
    for (cancer, seed, grid), value in values.items():
        new[(cancer, seed, grid)] = value + (shifts[cancer] if grid == 'none' else 0.0)
    judgement = render.q_judgement(config, values, new)
    assert [judgement[c]['verdict'] for c in config['display_cancer_order']] == ['胜', '胜', '平', '胜', '负']
    line = render.q_line(config, judgement)
    assert '**3/5**（未达标）' in line and 'BLCA、UCEC' in line
    documents = render.render_all(config, values, new, meta, {'sha256': 'x' * 64, 'run_fingerprint': 'y' * 64})
    assert render.red('并列') in documents['癌症为单位.md']
    assert render.red(render.NEW_LABEL) in documents['seed单位-实验结果.md']
    assert '二者不混称' in documents['seed单位-实验结果.md']


def test_incomplete_or_duplicate_rows_rejected(config):
    rows = json.loads((REPO_ROOT / config['legacy']['test_complete']).read_text())['rows']
    strategy0 = [row for row in rows if row['protocol'] == 'strategy0']
    with pytest.raises(ValueError, match='不完整'):
        render.strategy0_values({'rows': strategy0[:-1]}, config, label='t')
    with pytest.raises(ValueError, match='重复'):
        render.strategy0_values({'rows': strategy0 + strategy0[:1]}, config, label='t')
    broken = json.loads(json.dumps(strategy0))
    broken[0]['c_index_b'] = float('nan')
    with pytest.raises(ValueError):
        render.strategy0_values({'rows': broken}, config, label='t')


DOC_DIR = REPO_ROOT / 'manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT-程序性知识'
LEDGER_TEST = (REPO_ROOT / 'experiments/BioClinical ModernBERT/results/i05-bcmbert200-20260924d/evidence'
               / 'formal_eval/runs/test/complete.json')


def test_documents_quote_script_numbers_only(config, baseline):
    """坑 V23：文档里的对照行必须等于脚本从原始 JSON 算出的值；论文目录的模板必须是脚本原样输出。"""
    values, meta = baseline
    means = [f"{sum(values[(c, s, 'none')] for s in config['seeds']) / 5:.6f}" for c in config['display_cancer_order']]
    for name, prefix in (('4.2研究计划书-BioClinical ModernBERT.md', '| 现有系统 None / Proto.†（Table 1） |'),
                         ('innovation-BioClinical ModernBERT.md', '| 现有系统 None / Proto.† |')):
        lines = [line for line in (DOC_DIR / name).read_text(encoding='utf-8').splitlines() if line.startswith(prefix)]
        assert lines == [prefix + ' ' + ' | '.join(means) + ' |'], name
    # 论文目录的三份结果文件已按用户裁决回传新臂真值：必须等于脚本从结果账本原始 JSON 的渲染输出
    new, new_meta = render.load_new(LEDGER_TEST, config)
    rendered = render.render_all(config, values, new, meta, new_meta)
    for name, text in rendered.items():
        assert (DOC_DIR / name).read_text(encoding='utf-8') == text, f'{name} 与脚本输出不一致'
        assert (LEDGER_TEST.parents[4] / name).read_text(encoding='utf-8') == text, f'账本 {name} 与脚本输出不一致'


def test_chance_of_four_of_five_under_null():
    assert render.chance_at_least(4) == 6 / 32


@pytest.mark.parametrize('plan, model_config, expected', [
    ('train_plan.yaml', 'experiments/I05_text_encoder_bcmbert/model_config.yml', {('--model_config', '--result_path')}),
    ('train_plan_bcmbert8192.yaml', 'experiments/I05_text_encoder_bcmbert/model_config_bcmbert8192.yml',
     {('--model_config', '--result_path')}),
    ('train_plan_legacytext.yaml', 'configs/models/surv_multimodal_mainmoe_uni2.yml', {('--result_path',)}),
])
def test_launch_contract_only_allows_two_differences(plan, model_config, expected):
    completed = subprocess.run([sys.executable, str(EXPERIMENT_DIR / 'tools' / 'check_launch_contract.py'),
                                '--python', sys.executable, '--plan', str(EXPERIMENT_DIR / plan),
                                '--model-config', str(REPO_ROOT / model_config)],
                               cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report['ok'] and report['n_i05'] == report['n_e0'] == 25 and report['seed_major_order']
    assert {tuple(value) for value in report['observed_differences'].values()} == expected


def test_formal_launcher_is_executable_in_checkout():
    """train_launcher 用 Popen 直接执行 launch_formal.sh；缺可执行位时正式发车在服务器上直接失败（Post-Mortem 10）。"""
    import os
    launcher = REPO_ROOT / 'scripts' / 'launch_formal.sh'
    assert launcher.is_file() and os.access(launcher, os.X_OK)


def test_independent_concordance_matches_hand_computed_cases():
    """verify_results 的纯 numpy C-index 按 sksurv 语义实现：时间并列时删失样本可比、风险并列记 0.5。"""
    from experiments.I05_text_encoder_bcmbert.tools import verify_results as verify
    # 3 人、全是事件、风险与时间完全逆序 → 全部一致
    assert verify.concordance_numpy([1, 1, 1], [1, 2, 3], [3, 2, 1]) == 1.0
    assert verify.concordance_numpy([1, 1, 1], [1, 2, 3], [1, 2, 3]) == 0.0
    # 风险并列记 0.5：可比对 (0,1)(0,2)(1,2)，其中 (0,1) 并列
    assert verify.concordance_numpy([1, 1, 1], [1, 2, 3], [2, 2, 1]) == (0.5 + 1 + 1) / 3
    # 同一时刻：事件 0 与删失 1 可比，删失不作为比较的起点
    assert verify.concordance_numpy([1, 0, 1], [1, 1, 2], [3, 1, 2]) == (1 + 1) / 2


LEDGER_200 = LEDGER_TEST


def _fake_complete(tmp_path, config, profile, shift, name):
    """把账本 bcmbert200 的 complete.json 改写成另一档案的合成 test 结果（none 行整体平移 shift）。"""
    payload = json.loads(LEDGER_200.read_text(encoding='utf-8'))
    payload['profile'] = profile
    payload['protocol_id'] = config['protocol_ids'][profile]
    payload['run_fingerprint'] = name * 64
    for row in payload['rows']:
        if row['grid'] == 'none':
            row['c_index_b'] = min(1.0, row['c_index_b'] + shift)
    path = tmp_path / f'{profile}-complete.json'
    path.write_text(json.dumps(payload))
    return path


def test_load_new_checks_profile_and_protocol(config, tmp_path):
    with pytest.raises(ValueError, match='bcmbert8192'):
        render.load_new(LEDGER_200, config, 'bcmbert8192')
    path = _fake_complete(tmp_path, config, 'bcmbert8192', 0.0, 'a')
    broken = json.loads(path.read_text())
    broken['protocol_id'] = config['protocol_ids']['bcmbert200']
    path.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match='协议'):
        render.load_new(path, config, 'bcmbert8192')
    with pytest.raises(ValueError, match='参考臂只能是'):
        render.load_reference(LEDGER_200, config, 'legacy-replay')


def test_render_bcmbert8192_with_references(config, baseline, tmp_path):
    values, meta = baseline
    new, new_meta = render.load_new(_fake_complete(tmp_path, config, 'bcmbert8192', 0.02, 'b'), config, 'bcmbert8192')
    references = {'bcmbert200': render.load_reference(LEDGER_200, config, 'bcmbert200'),
                  'legacytext-rerun': render.load_reference(
                      _fake_complete(tmp_path, config, 'legacytext-rerun', -0.01, 'c'), config, 'legacytext-rerun')}
    first = render.render_all(config, values, new, meta, new_meta, profile='bcmbert8192', references=references)
    second = render.render_all(config, values, new, meta, new_meta, profile='bcmbert8192', references=references)
    assert first == second
    table_md = first['encoder-table.md']
    label = render.NEW_LABELS['bcmbert8192']
    assert f'| {label} |' in table_md and '| 我们提出来的 Encoder |' not in table_md
    ref200 = references['bcmbert200'][0]
    means200 = [f"{sum(ref200[(c, s, 'none')] for s in config['seeds']) / 5:.6f}" for c in config['display_cancer_order']]
    assert f"| {render.REFERENCE_LABELS['bcmbert200']} | " + ' | '.join(means200) + ' |' in table_md
    # 全部 none 行 +0.02 → 相对 bcmbert200 五癌全胜；相对 legacytext（−0.01）同样全胜
    assert '相对 bcmbert200 严格胜 5/5（同代码对照，信息性，不进 Q）。' in table_md
    assert '相对 legacytext-rerun 严格胜 5/5（同代码对照，信息性，不进 Q）。' in table_md
    assert '## 同代码对照（none，五 seed 均值，不进 Q）' in first['癌症为单位.md']
    assert '## 同代码对照（none，逐 seed，不进 Q）' in first['seed单位-实验结果.md']
    assert '唯一差别是上下文长度' in first['癌症为单位.md'] and '不截断（全文 ≤ 8192 token' in first['癌症为单位.md']
    with pytest.raises(ValueError, match='参考臂'):
        render.render_all(config, values, None, meta, None, profile='bcmbert8192', references=references)
    with pytest.raises(ValueError, match='参考臂'):
        render.render_all(config, values, new, meta, new_meta, profile='bcmbert200', references=references)


def test_render_bcmbert8192_template_without_results(config, baseline):
    values, meta = baseline
    documents = render.render_all(config, values, None, meta, None, profile='bcmbert8192')
    assert f"| {render.NEW_LABELS['bcmbert8192']} | 未实验 |" in documents['encoder-table.md']
    assert '不截断（全文 ≤ 8192 token' in documents['癌症为单位.md']


A0_DOC_DIR = REPO_ROOT / 'manuscript/消融实验/2.innovation-secode-part- Encoder/5.如何修补BioClinical-ModernBERT.md'


A0_LEDGER_TEST = (REPO_ROOT / 'experiments/BioClinical ModernBERT/results/i05-a0-20260924/evidence'
                  / 'formal_eval/runs/test/complete.json')


def test_a0_documents_are_script_output(config, baseline):
    """第 5 号目录（A0）与账本的三份结果文件必须等于脚本从账本原始 JSON 的 bcmbert8192 渲染（参考臂：轮 C bcmbert200）。"""
    values, meta = baseline
    new, new_meta = render.load_new(A0_LEDGER_TEST, config, 'bcmbert8192')
    references = {'bcmbert200': render.load_reference(LEDGER_200, config, 'bcmbert200')}
    rendered = render.render_all(config, values, new, meta, new_meta, profile='bcmbert8192', references=references)
    for name, text in rendered.items():
        assert (A0_DOC_DIR / name).read_text(encoding='utf-8') == text, f'{name} 与脚本输出不一致'
        assert (A0_LEDGER_TEST.parents[4] / name).read_text(encoding='utf-8') == text, f'账本 {name} 与脚本输出不一致'

