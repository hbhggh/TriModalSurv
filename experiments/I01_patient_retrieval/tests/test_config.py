"""配置优先级、显式覆盖和排他写入；可在无科学计算依赖的本机运行。"""
import argparse
import json
import tempfile
import unittest
from pathlib import Path

from trimodalsurv.config import resolve_config, write_resolved_config


class ConfigTests(unittest.TestCase):
    def test_unpassed_cli_does_not_replace_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            base, experiment = Path(directory) / 'base.yaml', Path(directory) / 'experiment.yaml'
            base.write_text(json.dumps({'batch_size': 32, 'model': {'dropout': .1, 'hidden': 256}}))
            experiment.write_text(json.dumps({'batch_size': 7, 'model': {'dropout': .2}}))
            parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
            parser.add_argument('--batch-size', type=int)
            merged = resolve_config(base, experiment, parser.parse_args([]))
            self.assertEqual(merged['batch_size'], 7)
            self.assertEqual(merged['model'], {'dropout': .2, 'hidden': 256})
            explicit = resolve_config(base, experiment, parser.parse_args(['--batch-size', '1']))
            self.assertEqual(explicit['batch_size'], 1)

    def test_explicit_false_and_zero_survive_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            base, experiment = Path(directory) / 'base.yaml', Path(directory) / 'experiment.yaml'
            base.write_text('{"flag":true,"value":1}')
            experiment.write_text('{}')
            merged = resolve_config(base, experiment, {'flag': False, 'value': 0})
            self.assertEqual(merged, {'flag': False, 'value': 0})

    def test_resolved_output_preserves_paths_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'resolved_config.json'
            write_resolved_config(target, {'path': Path('/data/cache')})
            self.assertEqual(json.loads(target.read_text())['path'], '/data/cache')
            with self.assertRaises(FileExistsError):
                write_resolved_config(target, {'overwritten': True})
            self.assertEqual(json.loads(target.read_text()), {'path': '/data/cache'})


if __name__ == '__main__':
    unittest.main()
