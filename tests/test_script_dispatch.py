"""实际脚本分发契约；替换模型执行边界，不训练或导入 Torch。"""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, **attributes):
    result = ModuleType(name)
    result.__dict__.update(attributes)
    return result


def load_script(filename):
    name = '_dispatch_contract_' + Path(filename).stem
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    loaded = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {name: loaded}), patch.object(sys, 'path', sys.path.copy()):
        spec.loader.exec_module(loaded)
    return loaded


class ScriptDispatchTests(unittest.TestCase):
    def test_training_routes_seed_after_parse_before_execution(self):
        for route in ('population', 'capl', 'none'):
            with self.subTest(route=route):
                events = []
                args = SimpleNamespace(compensator=route, seed=123)

                def parse(label):
                    events.append(('parse', label))
                    return args

                def run(label, actual):
                    self.assertIs(actual, args)
                    events.append(('run', label))
                    return 'finished-' + label

                runtime = module('trimodalsurv.training.runtime',
                    parsing_args=lambda: parse('shared'),
                    set_seed=lambda seed: events.append(('seed', seed)),
                    main=lambda actual: run('shared', actual))
                modules = {
                    'trimodalsurv': module('trimodalsurv'),
                    'trimodalsurv.training': module('trimodalsurv.training', runtime=runtime),
                    'trimodalsurv.training.runtime': runtime,
                    'experiments.I02_population_prototypes.train': module('population_train',
                        parsing_args=lambda: parse('population'),
                        main=lambda actual: run('population', actual)),
                    'experiments.I04_cap4_multi_prototypes.train': module('capl_train',
                        main=lambda actual: run('capl', actual)),
                }
                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['main_survival.py', '--compensator=' + route]):
                    entry = load_script('main_survival.py')
                    expected = 'shared' if route == 'none' else route
                    self.assertEqual(entry.main(), 'finished-' + expected)
                self.assertEqual(events, [
                    ('parse', 'population' if route == 'population' else 'shared'),
                    ('seed', 123), ('run', expected)])

    def test_training_config_routes_and_explicit_cli_precedence(self):
        cases = [
            ('population', None, 'population', 'population'),
            ('capl', None, 'shared', 'capl'),
            ('population', 'none', 'shared', 'shared'),
        ]
        for configured, explicit, parser_name, route in cases:
            with self.subTest(configured=configured, explicit=explicit):
                events = []
                args = SimpleNamespace(compensator=explicit or configured, seed=132)

                def parse(name):
                    events.append(('parse', name))
                    return args

                def run(name, actual):
                    self.assertIs(actual, args)
                    events.append(('run', name))

                runtime = module('runtime', parsing_args=lambda: parse('shared'),
                    set_seed=lambda seed: events.append(('seed', seed)),
                    main=lambda actual: run('shared', actual))
                modules = {
                    'trimodalsurv': module('trimodalsurv'),
                    'trimodalsurv.training': module('trimodalsurv.training', runtime=runtime),
                    'trimodalsurv.config': module('trimodalsurv.config',
                        read_config=lambda _: {'runtime': {'compensator': configured}}),
                    'experiments.I02_population_prototypes.train': module('population_train',
                        parsing_args=lambda: parse('population'),
                        main=lambda actual: run('population', actual)),
                    'experiments.I04_cap4_multi_prototypes.train': module('capl_train',
                        main=lambda actual: run('capl', actual)),
                }
                argv = ['main_survival.py', '--config', 'experiment.yaml']
                if explicit is not None:
                    argv += ['--compensator', explicit]
                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', argv):
                    load_script('main_survival.py').main()
                self.assertEqual(events, [('parse', parser_name), ('seed', 132), ('run', route)])

    def test_evaluation_routes_and_capl_factory(self):
        for route in ('population', 'capl', 'none'):
            with self.subTest(route=route):
                events = []
                args = SimpleNamespace(compensator=route)
                factory = object()

                def parse(label):
                    events.append(('parse', label))
                    return args

                def run(label, actual, **kwargs):
                    self.assertIs(actual, args)
                    events.append(('run', label, kwargs))

                shared = module('trimodalsurv.evaluation.missing',
                    parse_args=lambda: parse('shared'),
                    run_evaluation=lambda actual, **kwargs: run('shared', actual, **kwargs))
                modules = {
                    'trimodalsurv.evaluation.missing': shared,
                    'experiments.I02_population_prototypes.evaluate': module('population_eval',
                        parse_args=lambda: parse('population'),
                        run_evaluation=lambda actual: run('population', actual)),
                    'experiments.I04_cap4_multi_prototypes.train': module('capl_train', load_model=factory),
                }
                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['eval_missing.py', '--compensator', route]):
                    entry = load_script('eval_missing.py')
                    self.assertEqual(entry.main(), 0)
                expected = 'population' if route == 'population' else 'shared'
                kwargs = {} if route == 'population' else {'model_factory': factory if route == 'capl' else None}
                self.assertEqual(events, [('parse', expected), ('run', expected, kwargs)])


class LauncherBinModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = load_script('train_launcher.py')

    def test_equals_and_separate_forms_are_preserved_without_duplicate(self):
        for extra in (['--bin_mode=author'], ['--bin_mode', 'author']):
            with self.subTest(extra=extra):
                raw = {'name': 'e0_BLCA_s123', 'arm': 'e0', 'cancer': 'BLCA',
                       'seed': 123, 'bin_mode': 'train_quantile', 'extra_args': extra}
                with patch.object(self.launcher, '_load_yaml', return_value={'runs': [raw]}):
                    spec = self.launcher.load_plan(Path('unused.yaml'))[0]
                self.assertEqual(spec.extra_args, tuple(extra))
                args = SimpleNamespace(python=sys.executable, cpt_name='test', result_path='/tmp/test-result',
                    label='/tmp/label.csv', model_config='/tmp/model.yaml', gpu_config='/tmp/gpu.yaml',
                    lr=1e-4, epochs=1, batch_size=2)
                command = self.launcher.build_training_command(args, spec)
                self.assertEqual(sum(token.split('=', 1)[0] == '--bin_mode' for token in command), 1)
                self.assertEqual(self.launcher._option_value(command, '--bin_mode'), 'author')

    def test_plan_field_adds_mode_only_when_missing(self):
        raw = {'name': 'e0_BLCA_s123', 'arm': 'e0', 'cancer': 'BLCA',
               'seed': 123, 'bin_mode': 'train_quantile', 'extra_args': ['--epochs', '1']}
        with patch.object(self.launcher, '_load_yaml', return_value={'runs': [raw]}):
            spec = self.launcher.load_plan(Path('unused.yaml'))[0]
        self.assertEqual(spec.extra_args, ('--epochs', '1', '--bin_mode', 'train_quantile'))


if __name__ == '__main__':
    unittest.main()
