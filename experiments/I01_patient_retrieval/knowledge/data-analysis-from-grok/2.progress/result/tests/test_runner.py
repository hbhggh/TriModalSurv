"""执行入口与逐格证据测试；合成样本不能成为正式结果。"""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runner = None
if (ROOT / 'run.py').exists():
    import run as runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runner, '需要实现run.py，不能以空结果模板代替执行代码')
        self.config = json.loads((ROOT / 'config.yaml').read_text())

    def test_formal_gate_precedes_assets(self):
        for stage in ('valid', 'test'):
            config = copy.deepcopy(self.config)
            config['runtime']['stage'] = stage
            config['paths']['repo_root'] = '/deliberately/missing'
            with self.assertRaisesRegex(ValueError, '正式|授权'):
                runner.execute(config)

    def test_report_stage_never_reads_assets_or_invents_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            config = copy.deepcopy(self.config)
            config['paths']['execution_root'] = directory
            config['paths']['repo_root'] = '/deliberately/missing'
            result = runner.execute(config)
            self.assertEqual(result['status'], 'NOT_RUN')
            for name in ('seed单位-实验结果.md', '癌症为单位.md', '零训练改推理1-5实验结果.md'):
                text = (Path(directory) / name).read_text()
                self.assertIn('未跑', text)
                self.assertNotIn('0.628964', text)

    def test_smoke_candidates_are_not_a_valid_selection(self):
        specs = runner.smoke_specs(self.config)
        self.assertEqual(len(specs), 6)
        self.assertEqual({s['protocol'] for s in specs}, set(self.config['rules']) | {'combo'})
        combo = next(s for s in specs if s['protocol'] == 'combo')
        self.assertEqual((combo['lambda'], combo['alpha'], combo['w']), (.5, 1, .3))

    def test_legacy_comparison_reads_original_nested_grids(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {'protocol_id':'patient-fixed-padmask-v2', 'arm':'retrieval',
                       'cancer':'BLCA','seed':123,'grids':{'none':{'cindex_B':.6}}}
            (Path(directory)/'retrieval_BLCA_s123.json').write_text(json.dumps(payload))
            self.config['paths']['legacy_results_root'] = directory
            result = runner._historical_comparison(self.config,[{'protocol':'retrieval',
                      'cancer':'BLCA','seed':123,'grid':'none','c_index_b':.6}])
            self.assertEqual(result['status'], 'IDENTICAL')

    def test_all_reports_disclose_historical_comparability_block(self):
        reports = runner.with_history_boundary({'a.md':'# 结果', 'b.md':'# 结果'},
                         {'status':'DIFFERENT','cells':[{'delta':.01}]})
        for text in reports.values():
            self.assertIn('历史', text)
            self.assertIn('不可', text)
            self.assertIn('本批', text)

    def test_real_torch_synthetic_cell_no_smoke_c_index(self):
        # 故意不skip：必须在已有Torch环境执行此验收。
        import torch
        import runtime
        from experiments.I01_patient_retrieval.model import FixedPatientBank
        torch.set_num_threads(1)
        config = copy.deepcopy(self.config)
        config['shapes'] = {'img':[128,2], 'text':[2,2], 'rna':[2,2]}
        config['runtime']['batch_size'] = 2
        def wsi(x):
            return np.tile(np.asarray(x, np.float32), (128,1))
        splits = {'train':['a','b'], 'valid':['v','w'], 'test':['t']}
        train = {'img':{'a':wsi([1,0]),'b':wsi([0,1])},
                 'rna':{'a':np.ones((2,2),np.float32),'b':np.full((2,2),2,np.float32)},
                 'text':{'a':np.full((2,2),3,np.float32),'b':np.full((2,2),4,np.float32)}}
        bank = FixedPatientBank('BLCA', splits, train)
        features = {'img':{'v':wsi([2,0]),'w':wsi([0,2])},
                    'rna':{'v':np.ones((2,2),np.float32),'w':np.ones((2,2),np.float32)},
                    'text':{'v':np.ones((2,2),np.float32)}}
        labels = [{'patient_id':'v','survival_months':'2','censorship':'0'},
                  {'patient_id':'w','survival_months':'3','censorship':'1'}]
        source = runtime.QuerySource(bank,features,labels,'valid',config['grids'])
        model = runtime.build_model(config,'BLCA')
        specs = [runtime.baseline_spec(arm) for arm in runtime.BASELINES] + runner.smoke_specs(config)
        with tempfile.TemporaryDirectory() as directory:
            cell = runner.evaluate_cell(config, bank, source, model, specs, source.ids,
                         cancer='BLCA', seed=123, grid='none', directory=Path(directory)/'cell',
                         fingerprint='synthetic', checkpoint_sha='synthetic', compute_metric=False)
            self.assertEqual(len(cell['rows']), 9)
            for row in cell['rows']:
                self.assertNotIn('c_index_b', row)
                self.assertEqual(row['n_complete_checked'], 1)
            self.assertEqual(runtime.verify_cell(Path(directory)/'cell','synthetic'), cell)
            expected = {'cancer':'BLCA','seed':123,'grid':'none','split':'valid',
                        'ids':source.ids,'specs':specs,'checkpoint_sha':'synthetic','compute_metric':False}
            runtime.verify_cell(Path(directory)/'cell','synthetic', expected=expected)
            wrong = dict(expected); wrong['cancer'] = 'BRCA'
            with self.assertRaises(ValueError):
                runtime.verify_cell(Path(directory)/'cell','synthetic', expected=wrong)
            manifest = Path(directory)/'cell'/'cell.json'
            incomplete = copy.deepcopy(cell); incomplete['rows'] = incomplete['rows'][:1]
            manifest.write_text(json.dumps(incomplete))
            with self.assertRaises(ValueError):
                runtime.verify_cell(Path(directory)/'cell','synthetic', expected=expected)
            npz = next((Path(directory)/'cell').glob('*.npz'))
            with np.load(npz, allow_pickle=False) as payload:
                self.assertEqual(payload['logits'].shape, (2,4))
                self.assertEqual(payload['patient_ids'].tolist(), ['v','w'])


if __name__ == '__main__':
    unittest.main()
