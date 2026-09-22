"""测试在未提交的工作区上运行是常态：放行盖章拒跑门，并把账本指向临时目录，不污染真实 results.tsv。"""
import pytest


@pytest.fixture(autouse=True)
def _isolated_git_stamp(tmp_path_factory, monkeypatch):
    monkeypatch.setenv('TRIMODALSURV_ALLOW_DIRTY', '1')
    monkeypatch.setenv('TRIMODALSURV_LEDGER', str(tmp_path_factory.mktemp('ledger') / 'results.tsv'))
