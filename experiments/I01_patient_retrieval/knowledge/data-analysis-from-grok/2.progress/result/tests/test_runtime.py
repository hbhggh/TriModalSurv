"""运行门、split、冻结与报告诊断的行为验收；只写临时测试目录。"""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE = ROOT / 'runtime.py'
runtime = None
if MODULE.exists():
    import runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runtime, '需要实现运行门与valid/test隔离，runtime.py尚不存在')
        self.config = json.loads((ROOT / 'config.yaml').read_text())

    def test_config_rejects_unknown_or_changed_scientific_scope(self):
        runtime.validate_config(self.config)
        for path, value in [('prototype_k', 32), ('cancers', ['BLCA']), ('seeds', [123])]:
            cfg = copy.deepcopy(self.config)
            cfg[path] = value
            with self.assertRaises(ValueError):
                runtime.validate_config(cfg)
        cfg = copy.deepcopy(self.config)
        cfg['search']['lambda_grid'] = [.25, .5, 1]
        with self.assertRaises(ValueError):
            runtime.validate_config(cfg)

    def test_formal_authorization_rejected_before_assets(self):
        for stage in ('valid', 'test'):
            with self.assertRaisesRegex(ValueError, '正式|授权'):
                runtime.require_authorization(self.config, stage, {'a.py': 'abc'})

    def test_formal_requires_review_bound_to_same_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / 'review.json'
            approval = root / 'approval.txt'
            review.write_text(json.dumps({'reviewer':'Claude', 'decision':'PASS', 'source_hashes':{'a.py':'old'}}))
            approval.write_text('SYNTHETIC 用户授权 valid/test，仅用于门禁测试')
            cfg = copy.deepcopy(self.config)
            cfg['authorization']['formal_approved'] = True
            cfg['paths']['review_record'] = str(review)
            cfg['paths']['user_approval_record'] = str(approval)
            with self.assertRaisesRegex(ValueError, '源码|指纹'):
                runtime.require_authorization(cfg, 'valid', {'a.py':'new'})
            review.write_text(json.dumps({'reviewer':'Claude','decision':'PASS','source_hashes':{'a.py':'new'}}))
            self.assertTrue(runtime.require_authorization(cfg, 'valid', {'a.py':'new'}))

    def test_query_source_uses_explicit_valid_not_test(self):
        import numpy as np
        from experiments.I01_patient_retrieval.model import FixedPatientBank
        def wsi(x):
            return np.tile(np.asarray(x, dtype=np.float32), (128,1))
        splits={'train':['a','b'], 'valid':['v'], 'test':['t']}
        train={'img':{'a':wsi([1,0]),'b':wsi([0,1])},
               'rna':{'a':np.ones((2,2)),'b':np.ones((2,2))*2},
               'text':{'a':np.ones((2,2)),'b':np.ones((2,2))*3}}
        bank=FixedPatientBank('BLCA',splits,train)
        features={'img':{'v':wsi([2,0])},'rna':{'v':np.ones((2,2))},'text':{}}
        labels=[{'patient_id':'v','survival_months':'2','censorship':'0'}]
        source=runtime.QuerySource(bank,features,labels,'valid',self.config['grids'])
        raw,natural=source.batch(['v'],'none')
        self.assertTrue(raw['rna_valid'][0])
        self.assertFalse(raw['text_valid'][0])
        with self.assertRaises(ValueError):
            runtime.QuerySource(bank,features,labels,'test',self.config['grids'])

    def test_explicit_user_waiver_bound_to_source_protocol_and_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            waiver, approval = root/'waiver.json', root/'approval.txt'
            approval.write_text('SYNTHETIC 正式运行也豁免Claude再审，批准valid和test')
            record = {'authority':'user', 'decision':'WAIVE_CLAUDE_REVIEW',
                      'protocol_id':self.config['protocol_id'], 'stages':['valid','test'],
                      'source_hashes':{'a.py':'new'},
                      'approval_sha256':runtime.file_sha256(approval)}
            waiver.write_text(json.dumps(record))
            cfg = copy.deepcopy(self.config)
            cfg['authorization'].update(formal_approved=True, review_waived_by_user=True)
            cfg['paths'].update(review_waiver_record=str(waiver), user_approval_record=str(approval))
            for stage in ('valid','test'):
                try:
                    accepted = runtime.require_authorization(cfg,stage,{'a.py':'new'})
                except ValueError as exc:
                    self.fail(f'真实用户豁免分支未实现: {exc}')
                self.assertTrue(accepted)
            for key,value in [('authority','Claude'), ('decision','PASS'),
                              ('protocol_id','other'), ('stages',['valid']),
                              ('source_hashes',{'a.py':'old'}), ('approval_sha256','wrong')]:
                changed = dict(record); changed[key]=value
                waiver.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    runtime.require_authorization(cfg,'test',{'a.py':'new'})
            waiver.write_text(json.dumps(record))
            cfg['authorization']['review_waived_by_user']=False
            with self.assertRaises(ValueError):
                runtime.require_authorization(cfg,'valid',{'a.py':'new'})

    def test_diagnostic_zero_checked_is_null_and_counts_once(self):
        import numpy as np
        d=runtime.CompleteDiagnostic(1e-6,0)
        zeros=np.zeros((3,4),dtype=np.float32)
        d.check(np.array([False,False,False]), {'m0real':zeros,'m1':zeros,'combo':zeros})
        self.assertEqual(d.result(), {'n_complete_checked':0,'complete_max_logit_abs_diff':None,'complete_logit_atol':1e-6})
        changed=zeros.copy(); changed[0,0]=5e-7
        d.check(np.array([True,False,False]), {'m0real':zeros,'m1':changed,'combo':zeros})
        self.assertEqual(d.result()['n_complete_checked'],1)
        changed[0,0]=2e-6
        with self.assertRaises(ValueError):
            d.check(np.array([True,False,False]), {'m0real':zeros,'combo':changed})

    def test_exclusive_json_and_lock_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'lock.json'
            payload={'selected':{'combo':{'lambda':.25}},'source_hashes':{'a':'b'}}
            runtime.write_json_new(path,payload)
            with self.assertRaises(FileExistsError):
                runtime.write_json_new(path,{'different':True})
            digest=runtime.file_sha256(path)
            self.assertEqual(runtime.read_verified_json(path,digest),payload)
            path.write_text('{}')
            with self.assertRaises(ValueError):
                runtime.read_verified_json(path,digest)

    def test_protected_output_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            cache=root/'cache'; cache.mkdir()
            with self.assertRaises(ValueError):
                runtime.check_output_boundary(cache/'nested', [cache], root)
            runtime.check_output_boundary(root/'run',[cache],root)

    def test_json_completion_is_published_only_after_full_write(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'complete.json'
            with patch.object(runtime.os, 'link', side_effect=OSError('SYNTHETIC publication failure')):
                with self.assertRaises(OSError):
                    runtime.write_json_new(path, {'rows':[1,2,3]})
            self.assertFalse(path.exists(), '不能留下半写的完成标志')

    def test_cell_resume_checks_artifacts_and_refuses_tampering(self):
        self.assertTrue(hasattr(runtime, 'verify_cell'), '必须验证已完成单元，不能只看文件存在')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            artifact=root/'pred.bin'; artifact.write_bytes(b'SYNTHETIC-prediction')
            payload={'run_fingerprint':'run', 'artifacts':{'pred.bin':runtime.file_sha256(artifact)},
                     'rows':[{'cancer':'BLCA','seed':123,'grid':'none'}]}
            runtime.write_json_new(root/'cell.json',payload)
            self.assertEqual(runtime.verify_cell(root,'run'),payload)
            artifact.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                runtime.verify_cell(root,'run')

    def test_lock_rejects_test_evidence_and_scientific_drift(self):
        self.assertTrue(hasattr(runtime, 'validate_selection_lock'), '必须有冻结锁校验')
        sources={'x':'y'}; assets={'a':'b'}
        lock={'stage':'valid','science_config':runtime.science_config(self.config),
              'source_hashes':sources,'asset_hashes':assets,'environment':{'v':1}}
        runtime.validate_selection_lock(lock,self.config,sources,assets,{'v':1})
        changed=copy.deepcopy(lock); changed['stage']='test'
        with self.assertRaises(ValueError):
            runtime.validate_selection_lock(changed,self.config,sources,assets,{'v':1})
        with self.assertRaises(ValueError):
            runtime.validate_selection_lock(lock,self.config,{'x':'z'},assets,{'v':1})


if __name__ == '__main__':
    unittest.main()
