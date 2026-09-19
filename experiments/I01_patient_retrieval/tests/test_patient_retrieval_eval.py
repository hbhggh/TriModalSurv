"""固定患者库的只读缓存、三臂接口与真实 NPJC 前向契约。"""
import copy
import contextlib
import io
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class EvaluationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert (ROOT / 'evaluate.py').is_file(), '固定库三臂评测接口尚未实现'
        from experiments.I01_patient_retrieval import evaluate as module
        cls.module = module

    def setUp(self):
        from experiments.I01_patient_retrieval.model import FixedPatientBank
        rows = np.tile([[2., 1.], [1., 2.]], (64, 1)).astype('float32')
        self.splits = {'train': ['A', 'B'], 'valid': ['V'], 'test': ['Q', 'R']}
        self.features = {'img': {'A': rows, 'B': rows[::-1].copy()},
                         'rna': {'A': np.ones((3, 2)), 'B': np.full((3, 2), 2.)},
                         'text': {'A': np.ones((4, 2)), 'B': np.full((4, 2), 3.)}}
        self.bank = FixedPatientBank('BLCA', self.splits, self.features)
        self.test_features = {'img': {'Q': rows.copy(), 'R': rows.copy()},
                              'rna': {'Q': np.ones((3, 2)), 'R': np.ones((3, 2))},
                              'text': {'Q': np.ones((4, 2))}}
        self.labels = [{'patient_id': pid, 'survival_months': '10', 'censorship': '0'} for pid in ['Q', 'R']]

    def test_none_preserves_natural_missing_and_grid_masks(self):
        before = copy.deepcopy(self.test_features)
        source = self.module.CachedPatients(self.bank, self.test_features, self.labels)
        raw, natural = source.batch(['Q', 'R'], 'none')
        self.assertEqual(raw['text_valid'].tolist(), [True, False])
        self.assertEqual(natural['text'].tolist(), [True, False])
        masked, _ = source.batch(['Q', 'R'], 'both_100')
        self.assertFalse(masked['rna_valid'].any())
        self.assertFalse(masked['text_valid'].any())
        np.testing.assert_array_equal(masked['img'], before['img']['Q'][None].repeat(2, axis=0))
        np.testing.assert_array_equal(self.test_features['text']['Q'], before['text']['Q'])

    def test_smoke_includes_all_padded_test_patients_without_train_leak(self):
        from types import SimpleNamespace
        features = {'img': {}, 'rna': {}, 'text': {}}
        for n in range(8):
            pid = f'Q{n}'
            features['img'][pid] = np.ones((128, 2))
            features['rna'][pid] = features['text'][pid] = np.ones((2, 2))
        features['img']['Q7'][96:] = 0
        source = SimpleNamespace(ids=sorted(features['img']), features=features)
        self.assertIn('Q7', self.module.smoke_ids(source))

    def test_fill_and_masks_are_applied_before_model(self):
        source = self.module.CachedPatients(self.bank, self.test_features, self.labels)
        raw, natural = source.batch(['Q', 'R'], 'both_100')
        for arm in self.module.ARMS:
            filled, audit = self.module.prepare_batch(self.bank, ['Q', 'R'], raw, natural, arm)
            self.assertEqual(filled['rna_valid'].tolist(), [arm != 'm0real'] * 2)
            self.assertFalse(audit[1]['natural_valid']['text'])
            self.assertFalse(audit[0]['original_valid']['rna'])
            if arm == 'retrieval':
                self.assertEqual(audit[0]['donor_id'], 'A')
                np.testing.assert_array_equal(filled['rna'][0], self.features['rna']['A'])
                np.testing.assert_array_equal(filled['text'][0], self.features['text']['A'])

    def test_bad_test_value_and_missing_wsi_rejected(self):
        self.test_features['text']['Q'][0, 0] = np.nan
        with self.assertRaises(ValueError):
            self.module.CachedPatients(self.bank, self.test_features, self.labels)
        del self.test_features['img']['R']
        with self.assertRaises(ValueError):
            self.module.CachedPatients(self.bank, self.test_features, self.labels)

    def test_invalid_or_duplicate_label_rejected(self):
        for labels in [self.labels + self.labels[:1], [dict(self.labels[0], censorship='2'), self.labels[1]]]:
            with self.assertRaises(ValueError):
                self.module.CachedPatients(self.bank, self.test_features, labels)

    def test_fixed_cli_rejects_unapproved_dimensions(self):
        parser = self.module.parser()
        args = self.module.resolve_args(['--data-root', '/tmp/data', '--out-dir', '/tmp/result'])
        self.assertEqual(args.stage, 'preflight')
        self.assertEqual(tuple(args.seeds), (123, 132, 213, 231, 321))
        for option in [['--cancers', 'GBM'], ['--seeds', '999'], ['--compensator', 'capr']]:
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(['--data-root', '/tmp/data', '--out-dir', '/tmp/result'] + option)

    def test_output_cannot_pollute_source_cache(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, '输出目录'):
                self.module.main(['--data-root', directory, '--out-dir', str(path / 'tmp_sur_cache/new')])
            self.assertFalse((path / 'tmp_sur_cache').exists())

    def test_json_output_refuses_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unit.json'
            self.module.write_json_new(path, {'original': True})
            with self.assertRaises(FileExistsError):
                self.module.write_json_new(path, {'original': False})

    def test_duplicate_seed_state_rejected_before_data_access(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        args = SimpleNamespace(seeds=[123, 132], checkpoint_root=Path('/unused'))
        with patch.object(self.module, 'build_model', return_value=object()), \
             patch.object(self.module, 'strict_e0_load', return_value='same-state'), \
             patch.object(self.module, 'file_sha256', return_value='file-hash'):
            with self.assertRaisesRegex(ValueError, '跨 seed 重复骨干权重'):
                self.module.preflight_cancer(args, 'BLCA')

    @unittest.skipUnless(importlib.util.find_spec('torch'), '本机无 torch；须在现有远端环境执行')
    def test_actual_npjc_forward_identity_mask_and_strict_checkpoint(self):
        import tempfile
        import torch
        torch.set_num_threads(1)
        torch.manual_seed(123)
        model = self.module.build_model('BLCA', {'img': 2, 'text': 2, 'rna': 2}, 'cpu')
        self.assertIsNone(model.compensator)
        self.assertFalse(any('compensator' in key for key in model.state_dict()))
        saved_state = {key: value.clone() for key, value in model.state_dict().items()}
        source = self.module.CachedPatients(self.bank, self.test_features, self.labels)
        for grid in ('none', 'both_100'):
            raw, natural = source.batch(['Q'], grid)
            logits, masks = [], []
            def capture(module, args, kwargs):
                masks.append(kwargs['src_key_padding_mask'].clone())
            hook = model.backbone.register_forward_pre_hook(capture, with_kwargs=True)
            for arm in self.module.ARMS:
                inputs, _ = self.module.prepare_batch(self.bank, ['Q'], raw, natural, arm)
                logits.append(self.module.forward_numpy(model, inputs, 'BLCA', 'cpu'))
            hook.remove()
            if grid == 'none':
                np.testing.assert_array_equal(logits[0], logits[1])
                np.testing.assert_array_equal(logits[0], logits[2])
            else:
                self.assertEqual(masks[0].tolist(), [[False, True, True]])
                self.assertEqual(masks[1].tolist(), [[False, False, False]])
                self.assertEqual(masks[2].tolist(), [[False, False, False]])
            for key, value in model.state_dict().items():
                self.assertTrue(torch.equal(saved_state[key], value))
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'E0.pth'
            torch.save(saved_state, checkpoint)
            self.module.strict_e0_load(model, checkpoint)
            with self.assertRaisesRegex(ValueError, '核验与加载之间'):
                self.module.strict_e0_load(model, checkpoint, expected_file_sha='wrong')
            torch.save({**saved_state, 'compensator.fake': torch.zeros(1)}, checkpoint)
            with self.assertRaises(ValueError):
                self.module.strict_e0_load(model, checkpoint)

    @unittest.skipUnless(importlib.util.find_spec('torch'), '本机无 torch；远端执行合成端到端')
    def test_synthetic_unit_artifacts_match_summary_contract(self):
        import json
        import tempfile
        from types import SimpleNamespace
        import torch
        from experiments.I01_patient_retrieval.summarize import _validate_grid
        torch.set_num_threads(1)
        self.labels[1]['survival_months'] = '20'
        source = self.module.CachedPatients(self.bank, self.test_features, self.labels)
        model = self.module.build_model('BLCA', {'img': 2, 'text': 2, 'rna': 2}, 'cpu')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            ckpt = self.module.checkpoint_path(base / 'weights', 'BLCA', 123)
            ckpt.parent.mkdir(parents=True)
            torch.save(model.state_dict(), ckpt)
            out = base / 'results'
            out.mkdir()
            args = SimpleNamespace(checkpoint_root=base / 'weights', out_dir=out, stage='formal',
                                   device='cpu', batch_size=2, review_record=None)
            report = {'checkpoints': {'123': {'sha256': self.module.file_sha256(ckpt),
                                             'state_sha256': self.module.strict_e0_load(model, ckpt)}},
                      'comparison_fingerprint': self.bank.fingerprint}
            self.module.evaluate_unit(args, self.bank, source, model, report, 123)
            for arm in self.module.ARMS:
                path = out / f'{arm}_BLCA_s123.json'
                unit = json.loads(path.read_text())
                self.assertEqual(set(unit['grids']), set(self.module.GRIDS))
                for grid, result in unit['grids'].items():
                    _validate_grid(result, path, grid)
                    values = np.load(out / result['predictions_file'], allow_pickle=False)
                    self.assertEqual(values['patient_id'].tolist(), ['Q', 'R'])
                    self.assertIn('n_complete_checked', result)
                    self.assertEqual(result['n_complete_checked'], 1 if grid == 'none' else 0)
                    if grid != 'none':
                        self.assertIsNone(result['complete_max_logit_abs_diff'])

    def _run_diagnostic_fixture(self, batch_size, *, no_complete=False, delta=0.0):
        """真实 evaluate_unit；只在前向边界注入可控误差以测试容差。"""
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        import torch
        torch.set_num_threads(1)
        features = copy.deepcopy(self.test_features)
        if no_complete:
            features['text'].pop('Q')
        source = self.module.CachedPatients(self.bank, features, self.labels)
        model = self.module.build_model('BLCA', {'img': 2, 'text': 2, 'rna': 2}, 'cpu')
        calls = 0

        def controlled_forward(model, inputs, cancer, device):
            nonlocal calls
            arm_index = calls % 3
            calls += 1
            return np.full((len(inputs['rna_valid']), 4), delta if arm_index else 0.0,
                           dtype=np.float64)

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            ckpt = self.module.checkpoint_path(base / 'weights', 'BLCA', 123)
            ckpt.parent.mkdir(parents=True)
            torch.save(model.state_dict(), ckpt)
            out = base / 'results'
            out.mkdir()
            args = SimpleNamespace(checkpoint_root=base / 'weights', out_dir=out, stage='smoke',
                                   device='cpu', batch_size=batch_size, review_record=None)
            report = {'checkpoints': {'123': {'sha256': self.module.file_sha256(ckpt),
                                             'state_sha256': self.module.strict_e0_load(model, ckpt)}},
                      'comparison_fingerprint': self.bank.fingerprint}
            with patch.object(self.module, 'forward_numpy', side_effect=controlled_forward):
                self.module.evaluate_unit(args, self.bank, source, model, report, 123)
            return [json.loads((out / 'smoke' / f'{arm}_BLCA_s123.json').read_text())
                    for arm in self.module.ARMS]

    @unittest.skipUnless(importlib.util.find_spec('torch'), '远端 PyTorch 环境执行')
    def test_check_count_null_and_batch_partition(self):
        for batch_size in (1, 2):
            for no_complete in (False, True):
                with self.subTest(batch_size=batch_size, no_complete=no_complete):
                    units = self._run_diagnostic_fixture(batch_size, no_complete=no_complete)
                    for grid in self.module.GRIDS:
                        diagnostics = []
                        for unit in units:
                            result = unit['grids'][grid]
                            self.assertIn('n_complete_checked', result)
                            count = 1 if grid == 'none' and not no_complete else 0
                            self.assertEqual(result['n_complete_checked'], count)
                            self.assertEqual(result['complete_max_logit_abs_diff'], 0.0 if count else None)
                            self.assertEqual(result['complete_logit_atol'], 1e-6)
                            diagnostics.append((count, result['complete_max_logit_abs_diff']))
                        self.assertEqual(diagnostics[0], diagnostics[1])
                        self.assertEqual(diagnostics[0], diagnostics[2])

    @unittest.skipUnless(importlib.util.find_spec('torch'), '远端 PyTorch 环境执行')
    def test_complete_tolerance_accepts_inside_and_rejects_outside(self):
        for delta in (5e-7, 1e-6):
            units = self._run_diagnostic_fixture(2, delta=delta)
            for unit in units:
                self.assertEqual(unit['grids']['none']['complete_max_logit_abs_diff'], delta)
        with self.assertRaisesRegex(ValueError, '完整输入三臂 logits 不一致'):
            self._run_diagnostic_fixture(2, delta=2e-6)


if __name__ == '__main__':
    unittest.main()
