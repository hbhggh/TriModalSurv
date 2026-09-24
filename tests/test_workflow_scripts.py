"""Git 工作流脚本回归（scripts/gitflow.sh、scripts/ci.sh、scripts/codex_review.sh）：只在临时目录里建仓库与假项目，不碰真实仓库。"""
import json
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
CODEX_REVIEW = ROOT / 'scripts' / 'codex_review.sh'
# 外层环境里的这些变量会改变脚本行为，或把 git 指回真实仓库（GIT_DIR 等），子进程一律清掉
LEAKY = ('MAIN_BRANCH', 'DEV_BRANCH', 'TAG_PREFIX', 'RUN_BRANCH_PREFIX', 'WT_ROOT', 'CI_CMD', 'STAMP_CMD',
         'TEST_CMD', 'PYTHON_BIN', 'CDPATH', 'BASH_ENV', 'ENV', 'CODEX_COMPANION', 'CODEX_MODEL')


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
        (self.repo / '.gitignore').write_text('logs/\n*.pth\nGIT_STAMP.json\n__pycache__/\n', encoding='utf-8')
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

    def test_ignored_run_outputs_are_refused(self):
        # 审查 r1 #1：status --porcelain 看不见被忽略的 checkpoint / 日志，worktree remove 会连它们一起删
        run_dir = self.freeze()
        (run_dir / 'logs').mkdir()
        (run_dir / 'logs' / 'train.log').write_text('epoch 1\n', encoding='utf-8')
        (run_dir / 'best.pth').write_bytes(b'weights')
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, 'logs/', 'best.pth')
        self.assertTrue((run_dir / 'logs' / 'train.log').exists())
        self.assertTrue((run_dir / 'best.pth').exists())

    def test_checkpoint_hidden_in_pycache_is_refused(self):
        # 审查 r2 #1：status --ignored 把整个 __pycache__/ 折叠成一行，目录里混入的 checkpoint 曾被一并放行
        run_dir = self.freeze()
        (run_dir / '__pycache__').mkdir()
        (run_dir / '__pycache__' / 'model.cpython-310.pyc').write_bytes(b'pyc')
        (run_dir / '__pycache__' / 'best.pth').write_bytes(b'weights')
        self.assert_refused(self.gitflow('cleanup', 'r1'), run_dir, '__pycache__/best.pth')
        self.assertTrue((run_dir / '__pycache__' / 'best.pth').exists())

    def test_regenerable_ignored_files_do_not_block_cleanup(self):
        run_dir = self.freeze()
        (run_dir / 'GIT_STAMP.json').write_text('{}\n', encoding='utf-8')  # freeze 用 git_stamp.py 时写在这里
        (run_dir / '__pycache__').mkdir()
        (run_dir / '__pycache__' / 'model.cpython-310.pyc').write_bytes(b'pyc')
        self.assert_removed(self.gitflow('cleanup', 'r1'), run_dir)


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
        offenders = [f'{script.name}:{number}: {line.strip()}' for script in (GITFLOW, CI, CODEX_REVIEW)
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


class CodexReviewEntryTests(_Sandbox):
    """自动审查入口：参数与防覆盖检查都先于调用 Codex；用不存在的 companion 保证测试永不真的发起审查。"""

    def setUp(self):
        super().setUp()
        self.env = dict(self.env, CODEX_COMPANION=str(self.tmp / 'no-such-companion.mjs'))
        self.out = self.tmp / 'review'

    def review(self, *args):
        return _run(['bash', CODEX_REVIEW, *args], self.repo, self.env)

    def test_help_prints_usage(self):
        result = self.review('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('codex-review.json', result.stdout)
        self.assertFalse(self.out.exists())

    def test_usage_errors_exit_2_without_side_effects(self):
        for args in ([], ['--bogus', self.out], [self.out, '--base']):
            with self.subTest(args=args):
                result = self.review(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.out.exists())

    def test_existing_review_is_never_overwritten(self):
        self.out.mkdir()
        (self.out / 'codex-review.json').write_text('{"old": true}', encoding='utf-8')
        result = self.review(self.out)
        self.assertEqual(result.returncode, 2)
        self.assertIn('不覆盖', result.stderr)
        self.assertEqual((self.out / 'codex-review.json').read_text(encoding='utf-8'), '{"old": true}')

    def test_missing_companion_fails_before_writing(self):
        result = self.review(self.out)
        self.assertEqual(result.returncode, 1)
        self.assertIn('找不到 companion', result.stderr)
        self.assertFalse(self.out.exists())


def _companion_schema():
    """真实 companion 自带的审查 schema；codex_review.sh 按它校验，测试也用同一份，不自造。"""
    root = Path.home() / '.claude' / 'plugins' / 'cache' / 'openai-codex' / 'codex'
    found = sorted(root.glob('*/schemas/review-output.schema.json'))
    return found[-1] if found else None


@unittest.skipIf(shutil.which('node') is None or _companion_schema() is None, '需要 node 与已安装的 Codex 插件 schema')
class CodexReviewOutputTests(_Sandbox):
    """审查 r1 #2 / r2 #2、#3：只有完全符合 schema 的结论才原子发布为 codex-review.json；其余保留失败现场并以 1 退出。"""

    FINDING = {'severity': 'high', 'title': 't', 'body': 'b', 'file': 'x.py', 'line_start': 1, 'line_end': 2,
               'confidence': 0.9, 'recommendation': 'r'}

    def setUp(self):
        super().setUp()
        plugin = self.tmp / 'plugin'  # 模拟插件目录：scripts/ 下是替身，schemas/ 下是真实 schema 的拷贝
        (plugin / 'scripts').mkdir(parents=True)
        (plugin / 'schemas').mkdir()
        shutil.copy2(_companion_schema(), plugin / 'schemas' / 'review-output.schema.json')
        fake = plugin / 'scripts' / 'fake-companion.mjs'  # 替身：原样吐出环境变量里的内容，不接触真实 Codex
        fake.write_text('import fs from "node:fs";\n'
                        'if (process.env.FAKE_RACE) fs.writeFileSync(process.env.FAKE_RACE, "{\\"other\\": true}");\n'
                        'process.stdout.write(process.env.FAKE_OUT || "");\n'
                        'process.exit(Number(process.env.FAKE_EXIT || 0));\n', encoding='utf-8')
        self.env = dict(self.env, CODEX_COMPANION=str(fake))
        self.out = self.tmp / 'review'

    def body(self, **result):
        base = {'verdict': 'needs-attention', 'summary': 's', 'findings': [dict(self.FINDING)], 'next_steps': ['n']}
        base.update(result)
        return json.dumps({'review': 'Adversarial Review', 'result': base})

    def review(self, out, exit_code=0, **env):
        env = dict(self.env, FAKE_OUT=out, FAKE_EXIT=str(exit_code), **env)
        return _run(['bash', CODEX_REVIEW, self.out], self.repo, env)

    def partials(self):
        return sorted(p.name for p in self.out.glob('.codex-review.*'))

    def test_schema_valid_verdict_is_published(self):
        body = self.body()
        result = self.review(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.out / 'codex-review.json').read_text(encoding='utf-8'), body)
        self.assertEqual(self.partials(), [])

    def test_degraded_outputs_never_become_official(self):
        bad_finding = lambda **kw: [dict(self.FINDING, **kw)]
        cases = {'malformed': ('{"result": ', 0), 'parse-error': ('{"parseError": "x", "result": null}', 0),
                 'no-result': ('{"review": "Adversarial Review"}', 0),
                 'bad-verdict': (self.body(verdict='pass'), 0),
                 'no-next-steps': (json.dumps({'result': {'verdict': 'approve', 'summary': 's', 'findings': []}}), 0),
                 'empty-summary': (self.body(summary=''), 0),
                 'empty-finding': (self.body(findings=[{}]), 0),
                 'bad-severity': (self.body(findings=bad_finding(severity='blocker')), 0),
                 'line-zero': (self.body(findings=bad_finding(line_start=0)), 0),
                 'confidence-2': (self.body(findings=bad_finding(confidence=2)), 0),
                 'extra-field': (self.body(findings=bad_finding(extra='x')), 0),
                 'companion-failed': (self.body(), 3)}
        for count, (label, (body, code)) in enumerate(cases.items(), 1):
            with self.subTest(label):
                result = self.review(body, code)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertFalse((self.out / 'codex-review.json').exists())
                self.assertEqual(len(self.partials()), count)  # 每次失败现场各自保留，不被后一次截断

    def test_concurrent_publish_never_overwrites(self):
        # 审查 r2 #3：另一审查在本次校验期间先发布了正式文件 → 本次失败退出，先到者原样保留，本次原始输出可追溯
        official = self.out / 'codex-review.json'
        result = self.review(self.body(), FAKE_RACE=str(official))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('不覆盖', result.stderr)
        self.assertEqual(official.read_text(encoding='utf-8'), '{"other": true}')
        self.assertEqual(len(self.partials()), 1)


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
