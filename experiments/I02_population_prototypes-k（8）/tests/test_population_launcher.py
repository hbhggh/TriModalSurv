"""正式启动器 population 身份、路径和评测接力回归（不启动训练）。"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from concurrent.futures import Future
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('population_launcher_test_target', ROOT.parents[1] / 'scripts/train_launcher.py')
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


class PopulationLauncherTests(unittest.TestCase):
    def test_population_next_seed_waits_for_previous_evaluation(self):
        # 真正执行生产scheduler，替换外部训练/评测进程；延迟Future使竞态可确定复现。
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            args = self.args(root)
            args.logs_dir, args.gpus, args.per_gpu = root / 'logs', ['0'], 1
            runs = launcher.generate_runs('population', 'BLCA', '123,132', 8)
            evaluations, started = [], []

            class DelayedEvaluation(Future):
                def result(self, timeout=None):
                    if not self.done():
                        self.set_result(root / 'eval.json')
                    return super().result(timeout)

            class Executor:
                def __init__(self, **kwargs):
                    pass
                def submit(self, *a, **kw):
                    future = DelayedEvaluation()
                    evaluations.append(future)
                    return future
                def shutdown(self, **kwargs):
                    pass

            def launch(*a, **kw):
                if started:
                    self.assertTrue(evaluations[0].done(), '上一seed评测未结束就启动了下一训练')
                started.append(True)
                return SimpleNamespace(pid=999999, poll=lambda: 0)

            with patch.object(launcher, 'missing_cache_files', return_value=[]), \
                 patch.object(launcher, 'ThreadPoolExecutor', Executor), \
                 patch.object(launcher.subprocess, 'Popen', side_effect=launch):
                self.assertEqual(launcher.run_scheduler(args, runs), 0)
            self.assertEqual(len(started), 2)

    def spec(self, k='2', network='NPJC', arm='population'):
        extra = ('--bin_mode', 'author') + (() if k is None else ('--prototype-k', k))
        return launcher.RunSpec('audit', arm, network, 'population', 'BLCA', 19, extra)

    def args(self, directory):
        return launcher.parse_args([
            '--result-path', str(directory / 'out'), '--cpt-name', 'audit',
            '--eval-out', str(directory / 'eval'), '--eval-manifest', str(directory / 'manifest.json'),
            '--eval-grids', 'none', '--state-file', str(directory / 'state.json'),
        ])

    def test_population_spec_accepts_explicit_k(self):
        launcher._validate_spec(self.spec())

    def test_population_early_stopping_reaches_training_but_not_old_arms(self):
        args = launcher.parse_args(['--epochs', '100', '--early-stopping-patience', '15'])
        command = launcher.build_training_command(args, self.spec('8'))
        self.assertEqual(command[command.index('--early-stopping-patience') + 1], '15')
        self.assertEqual(command[command.index('--epochs') + 1], '100')
        old = launcher.generate_runs('e0', 'BLCA', '123')[0]
        with self.assertRaisesRegex(ValueError, 'population'):
            launcher.build_training_command(args, old)
        default = launcher.parse_args([])
        self.assertNotIn('--early-stopping-patience', launcher.build_training_command(default, old))

    def test_plan_loads_explicit_population_k(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.json'
            path.write_text(json.dumps({'runs': [{'name': 'audit', 'arm': 'population',
                            'cancer': 'BLCA', 'seed': 19, 'bin_mode': 'author', 'extra_args': ['--prototype-k=2']}]}))
            runs = launcher.load_plan(path)
            self.assertEqual(runs[0].network_type, 'NPJC')
            self.assertEqual(launcher._forwarded_eval_args(runs[0]), ['--bin_mode', 'author', '--prototype-k', '2'])

    def test_different_k_get_distinct_run_and_checkpoint_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(Path(temp).resolve())
            first = launcher.generate_runs('population', 'BLCA', '19', 2)[0]
            second = launcher.generate_runs('population', 'BLCA', '19', 3)[0]
            self.assertNotEqual(first.name, second.name)
            first_path = launcher.checkpoint_path(launcher.build_training_command(args, first))
            second_path = launcher.checkpoint_path(launcher.build_training_command(args, second))
            self.assertNotEqual(first_path, second_path)

    def test_population_rejects_missing_invalid_duplicate_k_and_other_network(self):
        for k in (None, '0', '-1', '1.5', 'bad'):
            with self.subTest(k=k), self.assertRaisesRegex(ValueError, 'prototype-k'):
                launcher._validate_spec(self.spec(k))
        with self.assertRaisesRegex(ValueError, 'NPJC'):
            launcher._validate_spec(self.spec(network='MainModalityMoE'))
        with self.assertRaisesRegex(ValueError, 'm0real'):
            launcher._validate_spec(self.spec(arm='m1'))
        duplicate = launcher.RunSpec('audit', 'population', 'NPJC', 'population', 'BLCA', 19,
                                    ('--prototype-k', '2', '--prototype-k=3'))
        with self.assertRaisesRegex(ValueError, 'prototype-k'):
            launcher._validate_spec(duplicate)

    def test_cli_dry_run_supports_population_without_side_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = launcher.main(['--arms', 'population', '--cancers', 'BLCA', '--seeds', '19',
                                        '--prototype-k', '2', '--dry_run', '--gpus', '1', '--per_gpu', '1',
                                        '--eval-grids', 'none', '--eval-out', str(root / 'eval'),
                                        '--eval-manifest', str(root / 'manifest.json'),
                                        '--result-path', str(root / 'out'), '--logs-dir', str(root / 'logs'),
                                        '--state-file', str(root / 'state.json')])
            self.assertEqual(result, 0)
            self.assertIn('--prototype-k 2', output.getvalue())
            self.assertIn('out_population_k2/19/', output.getvalue())
            self.assertIn('DRY_RUN_EVAL', output.getvalue())
            self.assertEqual(list(root.iterdir()), [])

    def test_checkpoint_path_matches_training_and_idempotent_skip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            args = self.args(root)
            command = launcher.build_training_command(args, self.spec())
            checkpoint = launcher.checkpoint_path(command)
            expected = root / 'out_population_k2/19/audit_population_k2_img_1536text_768rna_256_NPJC_BLCA_surv.pth'
            self.assertEqual(checkpoint, expected)
            checkpoint.parent.mkdir(parents=True)
            checkpoint.touch()
            state = launcher._initial_state(args, [self.spec()], {'audit': command}, {'audit': checkpoint})
            self.assertEqual(state['runs']['audit']['status'], 'skipped')
            args.cpt_name = 'audit_population_k2'
            args.result_path = root / 'out_population_k2'
            self.assertEqual(launcher.checkpoint_path(launcher.build_training_command(args, self.spec())), expected)

    def test_eval_forwards_k_and_preserves_old_modes(self):
        self.assertEqual(launcher._forwarded_eval_args(self.spec()), ['--bin_mode', 'author', '--prototype-k', '2'])
        old = launcher.generate_runs('e0,e0d,e1,d0', 'BLCA', '19')
        self.assertEqual([launcher._forwarded_eval_args(run) for run in old], [['--bin_mode', 'author'], ['--bin_mode', 'author'], ['--bin_mode', 'author'], ['--fusion_type', 'mean', '--bin_mode', 'author']])

    def test_eval_relay_reads_and_keeps_k_specific_identity(self):
        # 只替换昂贵的评测进程；真实 launcher 负责读文件、改臂名和落盘。
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            args = self.args(root)
            def evaluator(command, **kwargs):
                parsed = dict(zip(command[2::2], command[3::2]))
                self.assertEqual(parsed.get('--prototype-k'), '2')
                dest = Path(parsed['--out-dir']) / 'm0real_BLCA_s19_population_k2.json'
                dest.write_text(json.dumps({'arm': 'm0real', 'prototype_k': 2, 'grids': {}}))
                return SimpleNamespace(returncode=0)
            active = SimpleNamespace(spec=self.spec(), log_path=root / 'audit.log',
                                     checkpoint=root / 'checkpoint.pth', slot=launcher.Slot('1', 0))
            with patch.object(launcher.subprocess, 'run', side_effect=evaluator):
                output = launcher._run_eval(args, active)
            self.assertEqual(output.name, 'population_BLCA_s19_population_k2.json')
            self.assertEqual(json.loads(output.read_text())['arm'], 'population')
            original = output.read_bytes()
            with patch.object(launcher.subprocess, 'run', side_effect=AssertionError('不得重评覆盖')):
                with self.assertRaises(FileExistsError):
                    launcher._run_eval(args, active)
            self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
