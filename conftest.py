"""测试在未提交的工作区上运行是常态：放行盖章拒跑门，并把账本指向临时目录，不污染真实 results.tsv。"""
import os

import pytest

# accelerate 在 Mac 上会自动选 MPS，而 NPJ-C 的 nested tensor 算子不支持 MPS；AcceleratorState 又是进程级单例，
# 首个测试选了 MPS 后续传 cpu=True 会报错。测试一律走 CPU，与服务器无 GPU 的 CI 行为一致（生产代码不受影响）。
os.environ.setdefault('ACCELERATE_USE_CPU', 'true')


@pytest.fixture(autouse=True)
def _isolated_git_stamp(tmp_path_factory, monkeypatch):
    monkeypatch.setenv('TRIMODALSURV_ALLOW_DIRTY', '1')
    monkeypatch.setenv('TRIMODALSURV_LEDGER', str(tmp_path_factory.mktemp('ledger') / 'results.tsv'))
