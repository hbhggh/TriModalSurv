"""运行记录独占、来源闭包与完成证据契约；不读取患者数据。"""
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from trimodalsurv.config import (actual_model_spec, start_run_record, finalize_run_record,
    runtime_source_fingerprints, run_record_root, training_artifact_paths, preflight_training_outputs)


class RunProvenanceTests(unittest.TestCase):
    def test_model_spec_reports_real_fusion_without_changing_npjc_contract(self):
        layer = SimpleNamespace(self_attn=SimpleNamespace(embed_dim=8, num_heads=2),
                                linear1=SimpleNamespace(out_features=16))
        model = SimpleNamespace(backbone=[layer], modalities=['rna'], compensator=None,
                                m_projector={'rna': [None, None, SimpleNamespace(p=0.1)]}, logits_dim=4)
        self.assertNotIn('fusion', actual_model_spec(model))
        model.fusion = type('MeanFusion', (), {})()
        self.assertEqual(actual_model_spec(model)['fusion'], 'MeanFusion')
        model.fusion = type('GatedFusion', (), {})()
        self.assertEqual(actual_model_spec(model)['fusion'], 'GatedFusion')

    def test_exclusive_record_pending_and_finalized_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / 'model.pth'
            artifact = root / 'metrics.json'
            payload = {'inputs': [], 'source_fingerprints': [], 'runtime': {'seed': 123}}
            run = start_run_record(root / 'results', payload, checkpoint_path=checkpoint, run_id='test')
            self.assertEqual(json.loads((run / 'resolved_config.yaml').read_text()), payload)
            self.assertEqual(json.loads((run / 'checkpoint_manifest.json').read_text())['status'], 'pending')
            with self.assertRaises(FileExistsError):
                start_run_record(root / 'results', payload, checkpoint_path=checkpoint, run_id='test')
            with self.assertRaises(FileNotFoundError):
                finalize_run_record(run, checkpoint_path=checkpoint)
            self.assertFalse((run / 'audit/completion.json').exists())
            checkpoint.write_bytes(b'synthetic-checkpoint')
            artifact.write_text('{"loss": 1}')
            finalize_run_record(run, checkpoint_path=checkpoint, artifacts=[artifact])
            completion = json.loads((run / 'audit/completion.json').read_text())
            self.assertEqual(completion['status'], 'complete')
            self.assertEqual(completion['artifacts'][0]['source']['sha256'], completion['artifacts'][0]['copy']['sha256'])
            self.assertEqual((run / 'raw/00-metrics.json').read_bytes(), artifact.read_bytes())
            with self.assertRaises(FileExistsError):
                finalize_run_record(run, checkpoint_path=checkpoint)

    def test_run_id_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                start_run_record(directory, {}, checkpoint_path='unused', run_id='../escape')

    def test_source_closure_contains_models_experiments_entry_and_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.yaml'
            config.write_text('{}')
            sources = runtime_source_fingerprints(argparse.Namespace(config=str(config)))
            names = {item['path'] for item in sources}
            repo = Path(__file__).resolve().parents[1]
            for rel in ('src/trimodalsurv/models/npjc.py', 'experiments/I04_cap4_multi_prototypes/model.py',
                        'scripts/main_survival.py'):
                self.assertIn(str(repo / rel), names)
            self.assertIn(str(config.resolve()), names)
            self.assertTrue(all(len(item['sha256']) == 64 for item in sources))

    def test_seed_artifacts_separate_and_preflight_refuses_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = training_artifact_paths(root / '123' / 'baseline')
            second = training_artifact_paths(root / '132' / 'baseline')
            self.assertTrue(set(first.values()).isdisjoint(second.values()))
            for path in first.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.name.endswith('_plots'):
                    path.mkdir()
                else:
                    path.write_text('existing')
                with self.assertRaises(FileExistsError):
                    preflight_training_outputs(root / '123' / 'baseline', root / '123' / 'baseline.pth',
                                               training=True, sidecar=root / 'sidecar')
            self.assertEqual(preflight_training_outputs(root / '132' / 'baseline',
                root / '132' / 'baseline.pth', training=True, sidecar=root / 'sidecar'), second)

    def test_run_root_does_not_invent_experiment_identity(self):
        args = argparse.Namespace(result_path='/tmp/output', config=None)
        self.assertEqual(run_record_root(args), Path('/tmp/output/results').resolve())
        args.config = '/project/experiments/I03_npj_d_dm_e1/config.yaml'
        self.assertEqual(run_record_root(args), Path('/project/experiments/I03_npj_d_dm_e1/results'))
        args.run_record_root = '/tmp/explicit'
        self.assertEqual(run_record_root(args), Path('/tmp/explicit').resolve())


if __name__ == '__main__':
    unittest.main()
