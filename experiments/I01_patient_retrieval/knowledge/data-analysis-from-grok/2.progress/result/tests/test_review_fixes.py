"""R2两处缺口：参数标注与源码元数据；只使用合成数据。"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
import runtime
import selection
import reporting
from test_selection import make_config, all_rows, baseline_rows
from test_reporting import make_config as report_config, make_selection, make_test_rows


class ReviewFixTests(unittest.TestCase):
    def test_inactive_alpha_tie_is_marked_in_candidate_and_lock(self):
        config = make_config()
        specs = selection.build_candidates(config)
        result = selection.choose_validation(all_rows(specs, config), specs,
                                             baseline_rows(config), config)
        combo = result['selected']['combo']
        self.assertFalse(combo['ucec_exception'])
        self.assertEqual(combo['alpha'], 0.5)  # 原平局算法不改变。
        self.assertEqual(combo.get('inactive_parameters'), ['alpha'])
        for item in result['candidates']:
            if item['protocol'] == 'combo':
                self.assertEqual(item.get('inactive_parameters'), ['alpha'])
        for protocol, expected in zip(config['rules'],
                [['lambda', 'alpha', 'w'], ['lambda', 'alpha', 'w'],
                 ['alpha', 'w'], ['lambda', 'w'], ['lambda', 'alpha']]):
            self.assertEqual(result['selected'][protocol].get('inactive_parameters'), expected)

    def test_enabled_ucec_keeps_alpha_active(self):
        config = make_config()
        specs = selection.build_candidates(config)
        result = selection.choose_validation(
            all_rows(specs, config, lambda *_: 0.62), specs, baseline_rows(config), config)
        self.assertTrue(result['selected']['combo']['ucec_exception'])
        self.assertEqual(result['selected']['combo'].get('inactive_parameters'), [])

    def test_both_parameter_tables_mark_inactive_not_optimal(self):
        cfg, chosen = report_config(), make_selection()
        chosen['selected']['combo']['ucec_exception'] = False
        chosen['selected']['combo']['inactive_parameters'] = ['alpha']
        for item in chosen['candidates']:
            if item['candidate_id'] == chosen['selected']['combo']['candidate_id']:
                item['ucec_exception_enabled'] = False
                item['inactive_parameters'] = ['alpha']
        reports = reporting.render_reports(make_test_rows(cfg, chosen), chosen, cfg,
                                           status='completed')
        rows = [line.split(' | ') for line in reports['零训练改推理1-5实验结果.md'].splitlines()
                if line.startswith('| combo | valid-candidate-05 |')]
        self.assertEqual(len(rows), 2)
        self.assertIn('未生效', rows[0][4])  # 冻结参数表的alpha列。
        self.assertIn('未生效', rows[1][3])  # 候选参数表的alpha列。

    def test_source_hash_ignores_metadata_but_detects_real_code_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, rules = root / 'repo', root / 'rules'
            src = repo / 'src/trimodalsurv'
            old = repo / 'experiments/I01_patient_retrieval'
            src.mkdir(parents=True)
            old.mkdir(parents=True)
            rules.mkdir()
            for path in [src/'real.py', rules/'run.py', old/'model.py', old/'evaluate.py', old/'config.yaml']:
                path.write_text('original')
            cfg = {'paths': {'repo_root': str(repo)}, 'baseline_source_sha256': {}, 'rules': []}
            with patch.object(runtime, 'ROOT', rules):
                before = runtime.source_hashes(cfg)
                (src/'._real.py').write_bytes(b'AppleDouble')
                (rules/'._run.py').write_bytes(b'AppleDouble')
                (src/'.hidden').mkdir()
                (src/'.hidden/generated.py').write_text('metadata only')
                self.assertEqual(runtime.source_hashes(cfg), before)
                (src/'real.py').write_text('changed')
                after = runtime.source_hashes(cfg)
                self.assertNotEqual(after['repo/src/trimodalsurv/real.py'],
                                    before['repo/src/trimodalsurv/real.py'])


if __name__ == '__main__':
    unittest.main()
