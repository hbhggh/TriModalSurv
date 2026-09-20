"""迁移后的严格权重加载、实际配置和门禁边界。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import torch
from experiments.I01_patient_retrieval import evaluate
from trimodalsurv.config import actual_model_spec, resolved_config


class MigrationContracts(unittest.TestCase):
    def test_actual_model_configuration_and_unknown_training_parameters(self):
        model = evaluate.build_model('BLCA', {'img': 2, 'text': 3, 'rna': 4}, 'cpu')
        self.assertEqual(actual_model_spec(model), evaluate.MODEL_SPEC)
        record = resolved_config(SimpleNamespace(batch_size=7, device='cpu'), model,
                                 inputs={'cache': 'hash'}, checkpoints={}, sources={})
        self.assertEqual(record['runtime']['batch_size'], 7)
        self.assertEqual(record['model_input_dimensions'], {'img': 2, 'text': 3, 'rna': 4})
        self.assertEqual(record['historical_training']['batch_size'], '未记录')
        model.m_projector['text'][2].p = .2
        with self.assertRaisesRegex(ValueError, 'dropout'):
            actual_model_spec(model)

    def test_strict_load_rejects_missing_nonfinite_and_prefix_collision(self):
        model = evaluate.build_model('BLCA', {'img': 2, 'text': 2, 'rna': 2}, 'cpu')
        original = model.state_dict()
        key = next(iter(original))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'weights.pth'
            missing = dict(original)
            del missing[key]
            torch.save(missing, target)
            with self.assertRaises(RuntimeError):
                evaluate.strict_e0_load(model, target)
            bad = copy.deepcopy(original)
            bad[key].reshape(-1)[0] = float('nan')
            torch.save(bad, target)
            with self.assertRaisesRegex(ValueError, '非有限'):
                evaluate.strict_e0_load(model, target)
            torch.save({**original, 'module.' + key: original[key]}, target)
            with self.assertRaisesRegex(ValueError, '冲突'):
                evaluate.strict_e0_load(model, target)
            torch.save({'state_dict': {'module.' + key: value for key, value in original.items()}}, target)
            self.assertEqual(len(evaluate.strict_e0_load(model, target)), 64)

    def test_experiment_overrides_defaults_but_cannot_change_locked_model(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.yaml'
            config.write_text(json.dumps({'batch_size': 7, 'model': evaluate.MODEL_SPEC,
                                         'protocol_id': evaluate.PROTOCOL_ID, 'bin_mode': 'author', 'cancers': ['BLCA'], 'seeds': [123]}))
            argv = ['--data-root', directory, '--out-dir', directory + '/run', '--config', str(config)]
            self.assertEqual(evaluate.resolve_args(argv).batch_size, 7)
            self.assertEqual(evaluate.resolve_args(argv + ['--batch-size', '2']).batch_size, 2)
            changed = json.loads(config.read_text())
            changed['model']['hidden_size'] = 512
            config.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, '锁定配置'):
                evaluate.resolve_args(argv)

    def test_existing_run_and_formal_without_record_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ['--data-root', directory, '--out-dir', directory + '/run']
            Path(directory, 'run').mkdir()
            with self.assertRaises(FileExistsError):
                evaluate.main(argv)
            with self.assertRaisesRegex(ValueError, '互审记录'):
                evaluate.main(argv + ['--stage', 'formal'])


if __name__ == '__main__':
    unittest.main()
