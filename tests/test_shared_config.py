"""公共配置新合同：显式 null/false/0 与逐层覆盖。"""
import json
from trimodalsurv.config import resolve_config


def test_explicit_false_zero_and_null_override(tmp_path):
    base = tmp_path / 'base.json'
    experiment = tmp_path / 'experiment.json'
    base.write_text(json.dumps({'enabled': True, 'count': 9, 'optional': 'x', 'nested': {'a': 1, 'b': 2}}))
    experiment.write_text(json.dumps({'count': 4, 'nested': {'a': 3}}))
    actual = resolve_config(base, experiment, {'enabled': False, 'count': 0, 'optional': None})
    assert actual == {'enabled': False, 'count': 0, 'optional': None, 'nested': {'a': 3, 'b': 2}}
