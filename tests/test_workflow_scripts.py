"""Git 工作流脚本回归（scripts/gitflow.sh、scripts/ci.sh）：只在临时目录里建仓库与假项目，不碰真实仓库。"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITFLOW = ROOT / 'scripts' / 'gitflow.sh'
CI = ROOT / 'scripts' / 'ci.sh'
# 外层环境里的这些变量会改变脚本行为，或把 git 指回真实仓库（GIT_DIR 等），子进程一律清掉
LEAKY = ('MAIN_BRANCH', 'DEV_BRANCH', 'TAG_PREFIX', 'RUN_BRANCH_PREFIX', 'WT_ROOT', 'CI_CMD', 'STAMP_CMD',
         'TEST_CMD', 'PYTHON_BIN', 'CDPATH', 'BASH_ENV', 'ENV')


def _env(ceiling, **values):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') and k not in LEAKY}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_CEILING_DIRECTORIES=str(ceiling),
               GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.com',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@example.com')
    env.update(values)
    return env


def _run(args, cwd, env):
    # bash 的报错可能截断多字节字符，按 replace 解码，免得夹具先于断言崩掉
    return subprocess.run([str(a) for a in args], cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, encoding='utf-8', errors='replace')


@unittest.skipIf(shutil.which('git') is None or shutil.which('bash') is None, '需要 git 与 bash')
class _Sandbox(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name).resolve()
        self.assertNotIn(ROOT, self.tmp.parents)  # 沙箱绝不能落在真实仓库里
        self.env = _env(self.tmp)
        self.repo = self.tmp / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main')

    def git(self, *args, cwd=None):
        result = _run(['git', *args], cwd or self.repo, self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def ref(self, name):
        result = _run(['git', 'rev-parse', '-q', '--verify', name], self.repo, self.env)
        return result.stdout.strip() if result.returncode == 0 else None


class GitflowCleanupTests(_Sandbox):
    """审查 [high]：cleanup 只核对「HEAD 仍在 main 上」，run worktree 被切到 main 上更早的提交也会放行并删掉现场。"""

    def setUp(self):
        super().setUp()
        (self.repo / 'model.py').write_text('V = 1\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'c1')
        self.c1 = self.git('rev-parse', 'HEAD')
        (self.repo / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'c2')
        self.c2 = self.git('rev-parse', 'HEAD')

    def gitflow(self, *args, **env):
        return _run(['bash', GITFLOW, *args], self.repo, dict(self.env, **env))

    def freeze(self, **env):
        result = self.gitflow('freeze', 'r1', **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        run_dir = self.tmp / 'repo.worktrees' / 'run-r1'  # 默认 WT_ROOT = <主目录>.worktrees
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=run_dir), self.c2)
        self.assertEqual(self.ref('refs/tags/run/r1'), self.c2)
        return run_dir

    def assert_removed(self, result, run_dir):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(run_dir.exists())
        self.assertIsNone(self.ref('refs/heads/train/r1'))
        self.assertEqual(self.ref('refs/tags/run/r1'), self.c2)  # tag 保留

    def assert_refused(self, result, run_dir, *fragments, tag=True, branch='train/r1'):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for fragment in ('不删', *fragments):
            self.assertIn(fragment, result.stderr)
        self.assertTrue(run_dir.is_dir())  # 排查现场保留
        if tag:
            self.assertEqual(self.ref('refs/tags/run/r1'), self.c2)
        if branch:
            self.assertIsNotNone(self.ref(f'refs/heads/{branch}'))  # 没有被 -D

    def test_frozen_run_is_removed_and_tag_kept(self):
        run_dir = self.freeze()
        self.assert_removed(self.gitflow('cleanup', 'r1'), run_dir)

    def test_main_moving_on_during_run_is_not_drift(self):
        run_dir = self.freeze()
        (self.repo / 'model.py').write_text('V = 3\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'c3')  # 实验期间 main 被下一个创新推进，属正常
        self.assert_removed(self.gitflow('cleanup', 'r1'), run_dir)

    def test_run_branch_reset_to_earlier_main_commit_is_refused(self):
        run_dir = self.freeze()
        self.git('reset', '-q', '--hard', self.c1, cwd=run_dir)  # c1 也在 main 上
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, 'HEAD', 'run/r1')
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=run_dir), self.c1)

    def test_detached_checkout_of_earlier_main_commit_is_refused(self):
        run_dir = self.freeze()
        self.git('checkout', '-q', '--detach', self.c1, cwd=run_dir)
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, 'HEAD', 'run/r1')

    def test_commit_on_run_branch_is_refused(self):
        run_dir = self.freeze()
        self.git('commit', '-q', '--allow-empty', '-m', 'hotfix inside run worktree', cwd=run_dir)
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, 'HEAD', 'run/r1')

    def test_missing_tag_is_refused(self):
        run_dir = self.freeze()
        self.git('tag', '-d', 'run/r1')
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, 'tag run/r1 不存在', tag=False)

    def test_other_branch_at_frozen_commit_is_refused(self):
        run_dir = self.freeze()
        self.git('checkout', '-q', '-b', 'hijack', cwd=run_dir)
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, "'hijack'", "'train/r1'")
        self.assertIsNotNone(self.ref('refs/heads/hijack'))

    def test_detached_head_where_run_branch_expected_is_refused(self):
        run_dir = self.freeze()
        self.git('checkout', '-q', '--detach', cwd=run_dir)
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, 'detached', "'train/r1'")

    def test_detached_mode_is_removed_with_same_setting(self):
        run_dir = self.freeze(RUN_BRANCH_PREFIX='')
        self.assertNotEqual(_run(['git', 'symbolic-ref', '-q', 'HEAD'], run_dir, self.env).returncode, 0)
        self.assert_removed(self.gitflow('cleanup', 'r1', RUN_BRANCH_PREFIX=''), run_dir)

    def test_detached_mode_with_checked_out_branch_is_refused(self):
        run_dir = self.freeze(RUN_BRANCH_PREFIX='')
        self.git('checkout', '-q', '-b', 'train/r1', cwd=run_dir)
        self.assert_refused(self.gitflow('cleanup', 'r1', RUN_BRANCH_PREFIX=''), run_dir, 'detached')

    def test_prefix_setting_must_match_freeze(self):
        run_dir = self.freeze()
        self.assert_refused(self.gitflow('cleanup', 'r1', RUN_BRANCH_PREFIX=''), run_dir,
                            'detached', 'RUN_BRANCH_PREFIX')

    def test_frozen_commit_dropped_from_main_is_refused(self):
        run_dir = self.freeze()
        self.git('reset', '-q', '--hard', self.c1)  # 违规改写 main：冻结提交不再被 main 包含
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, '不在 main 上')

    def test_dirty_run_worktree_is_refused_without_force(self):
        run_dir = self.freeze()
        (run_dir / 'results.csv').write_text('c_index\n0.61\n', encoding='utf-8')  # 结果误写进 run worktree
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, '不干净')
        self.assertTrue((run_dir / 'results.csv').exists())


class GitflowHelpTests(_Sandbox):
    """审查 [medium]：帮助在仓库探测与 cd 之后才处理，且按相对 $0 读自身。"""

    def setUp(self):
        super().setUp()
        (self.repo / 'scripts').mkdir()
        self.script = self.repo / 'scripts' / 'gitflow.sh'
        shutil.copy2(GITFLOW, self.script)
        self.outside = self.tmp / 'outside'
        self.outside.mkdir()

    def assert_help(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('cleanup <run_id>', result.stdout)
        self.assertIn('RUN_BRANCH_PREFIX', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_help_from_scripts_directory_by_relative_path(self):
        self.assert_help(_run(['bash', 'gitflow.sh', '--help'], self.repo / 'scripts', self.env))

    def test_help_outside_any_repository(self):
        self.assertNotEqual(_run(['git', 'rev-parse', '--git-dir'], self.outside, self.env).returncode, 0)
        for args in (['--help'], ['-h'], ['help'], []):
            with self.subTest(args=args):
                self.assert_help(_run(['bash', self.script, *args], self.outside, self.env))

    def test_unknown_subcommand_still_fails(self):
        result = _run(['bash', self.script, 'bogus'], self.repo, self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未知子命令 'bogus'", result.stderr)


class GitflowMultibyteTests(_Sandbox):
    """审查外发现：macOS bash 3.2 在 UTF-8 locale 下把紧跟 $var 的全角标点首字节并入变量名，set -u 下日志行崩溃。"""

    def test_no_unbraced_variable_before_multibyte_text(self):
        pattern = re.compile(r'\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]')
        offenders = [f'{script.name}:{number}: {line.strip()}' for script in (GITFLOW, CI)
                     for number, line in enumerate(script.read_text(encoding='utf-8').splitlines(), 1)
                     if not line.lstrip().startswith('#') and pattern.search(line)]
        self.assertEqual(offenders, [])

    def test_init_and_squash_run_to_completion(self):
        (self.repo / 'model.py').write_text('V = 1\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        result = _run(['bash', GITFLOW, 'init'], self.repo, self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        dev = self.tmp / 'repo.worktrees' / 'dev'
        (dev / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'feat(I9): step', cwd=dev)
        tree = self.git('rev-parse', 'HEAD^{tree}', cwd=dev)
        result = _run(['bash', GITFLOW, 'squash', 'feat(I9): innovation'], self.repo, self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'main^{tree}'), tree)
        self.assertEqual(self.git('rev-parse', 'dev'), self.git('rev-parse', 'main'))


class CiArgumentTests(unittest.TestCase):
    """审查 [medium]：ci.sh 忽略参数，--help 也会先清 __pycache__ 再跑整套测试。"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name).resolve() / 'project'
        (self.project / 'scripts').mkdir(parents=True)
        shutil.copy2(CI, self.project / 'scripts' / 'ci.sh')  # 只跑副本：真实 ci.sh 会清真实缓存并递归跑全仓测试
        self.cache = self.project / 'pkg' / '__pycache__'
        self.cache.mkdir(parents=True)
        (self.cache / 'stale.cpython-310.pyc').write_bytes(b'stale')
        self.marker = self.project / 'tests_ran'
        fake = self.project / 'fake_tests.sh'
        fake.write_text('#!/bin/sh\ntouch tests_ran\n', encoding='utf-8')
        fake.chmod(0o755)
        self.env = _env(self.project.parent, TEST_CMD='./fake_tests.sh')

    def ci(self, *args):
        return _run(['bash', 'scripts/ci.sh', *args], self.project, self.env)

    def test_no_arguments_clears_cache_then_runs_tests(self):
        # 正对照：证明下面「无副作用」的断言看得见副作用
        result = self.ci()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.cache.exists())
        self.assertTrue(self.marker.exists())

    def test_help_prints_usage_without_side_effects(self):
        for flag in ('--help', '-h'):
            with self.subTest(flag=flag):
                result = self.ci(flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('TEST_CMD', result.stdout)
                self.assertTrue(self.cache.is_dir())
                self.assertFalse(self.marker.exists())

    def test_unknown_argument_fails_without_side_effects(self):
        for args in (['--bogus'], ['-k', 'gitflow']):
            with self.subTest(args=args):
                result = self.ci(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"'{args[0]}'", result.stderr)
                self.assertTrue(self.cache.is_dir())
                self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
