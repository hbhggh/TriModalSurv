"""Git 工作流脚本回归（scripts/gitflow.sh、scripts/ci.sh、scripts/codex_review.sh）：只在临时目录里建仓库与假项目，不碰真实仓库。"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITFLOW = ROOT / 'scripts' / 'gitflow.sh'
CI = ROOT / 'scripts' / 'ci.sh'
CODEX_REVIEW = ROOT / 'scripts' / 'codex_review.sh'
# 外层环境里的这些变量会改变脚本行为，或把 git 指回真实仓库（GIT_DIR 等），子进程一律清掉
LEAKY = ('MAIN_BRANCH', 'TAG_PREFIX', 'RUN_BRANCH_PREFIX', 'WT_BRANCH_PREFIX', 'WT_ROOT', 'CODE_PATHS', 'CI_CMD',
         'STAMP_CMD', 'TEST_CMD', 'PYTHON_BIN', 'CDPATH', 'BASH_ENV', 'ENV', 'CODEX_COMPANION', 'CODEX_MODEL')


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


def _lock_root(repo):
    return Path(repo) / '.git' / 'gitflow-locks'


def _path_with_blocking_worktree_add(tmp, env):
    """返回 PATH：其中的假 git 在 GF_BARRIER 已设置时，于 git worktree add 之前写 ready 并等待 go，其余原样转给真 git。"""
    bindir = Path(tmp) / 'fake-git-barrier'
    bindir.mkdir(exist_ok=True)
    (bindir / 'git').write_text(
        '#!/bin/sh\n'
        'if [ -n "$GF_BARRIER" ] && [ "$1" = worktree ] && [ "$2" = add ]; then\n'
        '  : > "$GF_BARRIER/ready"; i=0\n'
        '  while [ ! -f "$GF_BARRIER/go" ] && [ "$i" -lt 600 ]; do sleep 0.05; i=$((i + 1)); done\n'
        'fi\n'
        'exec %s "$@"\n' % shutil.which('git'), encoding='utf-8')
    (bindir / 'git').chmod(0o755)
    return '%s:%s' % (bindir, env['PATH'])


def _path_with_git_tag_then_sigterm(tmp, env):
    """返回 PATH：其中的假 git 真正创建 tag（git tag <名> <提交>）之后，立刻向调用它的 gitflow 发 SIGTERM。"""
    bindir = Path(tmp) / 'fake-git-sigterm'
    bindir.mkdir(exist_ok=True)
    real = shutil.which('git')
    (bindir / 'git').write_text(
        '#!/bin/sh\n'
        'if [ "$1" = tag ] && [ "$#" -eq 3 ]; then %s "$@" || exit $?; echo tag-created-then-sigterm >&2; '
        'kill -TERM "$PPID"; exit 0; fi\n'
        'exec %s "$@"\n' % (real, real), encoding='utf-8')
    (bindir / 'git').chmod(0o755)
    return '%s:%s' % (bindir, env['PATH'])


def _path_with_failing_git_tag(tmp, env):
    """返回 PATH：其中的假 git 只让创建 tag（git tag <名> <提交>）失败，其余命令原样转给真 git。"""
    bindir = Path(tmp) / 'fake-git-bin'
    bindir.mkdir(exist_ok=True)
    (bindir / 'git').write_text('#!/bin/sh\nif [ "$1" = tag ] && [ "$#" -eq 3 ]; then echo fake-tag-fail >&2; exit 1; fi\n'
                                'exec %s "$@"\n' % shutil.which('git'), encoding='utf-8')
    (bindir / 'git').chmod(0o755)
    return '%s:%s' % (bindir, env['PATH'])


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
        result = self.gitflow('freeze', 'r1', '--candidate', self.c2, **env)
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


class GitflowCodeGateTests(_Sandbox):
    """单主干（用户裁决 2026-11-12）：candidate / freeze 的干净门只看 CODE_PATHS，写到一半的论文与根目录笔记不阻塞实验。"""

    def setUp(self):
        super().setUp()
        for rel, text in (('src/model.py', 'V = 1\n'), ('experiments/I01/run.py', 'RUN = 1\n'),
                          ('manuscript/draft.tex', 'draft v1\n'), ('.gitignore', 'GIT_STAMP.json\n__pycache__/\n')):
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        self.head = self.git('rev-parse', 'HEAD')
        self.wt_root = self.tmp / 'repo.worktrees'
        self.run_dir = self.wt_root / 'run-r1'

    def gitflow(self, *args, **env):
        return _run(['bash', GITFLOW, *args], self.repo, {**self.env, 'CI_CMD': 'true', **env})

    def edit_paper_and_notes(self):
        (self.repo / 'manuscript' / 'draft.tex').write_text('draft v2，写到一半\n', encoding='utf-8')
        (self.repo / '想法笔记.md').write_text('未跟踪的根目录笔记\n', encoding='utf-8')

    def assert_nothing_frozen(self, result, *fragments):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for fragment in fragments:
            self.assertIn(fragment, result.stderr)
        self.assertIsNone(self.ref('refs/tags/run/r1'))
        self.assertIsNone(self.ref('refs/heads/train/r1'))
        self.assertFalse(self.run_dir.exists())

    def test_candidate_passes_on_main_with_unfinished_paper_and_untracked_note(self):
        self.edit_paper_and_notes()
        result = self.gitflow('candidate')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.head[:7], result.stdout)

    def test_candidate_prints_full_hash_for_freeze(self):
        result = self.gitflow('candidate')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--candidate %s' % self.head, result.stdout)

    def test_candidate_refuses_outside_main_checkout(self):
        # ①：在 wt/* worktree 或主目录的其他分支上运行 candidate 一律拒绝
        other = self.tmp / 'wt-side'
        self.git('worktree', 'add', '-q', '-b', 'wt/side', str(other))
        result = _run(['bash', GITFLOW, 'candidate'], other, {**self.env, 'CI_CMD': 'true'})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('主目录', result.stderr)
        self.git('checkout', '-q', '-b', 'feature')
        result = self.gitflow('candidate')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('main', result.stderr)
        # 主目录切走后，另一个 worktree 检出了 main：分支对，但位置不是主目录，仍拒绝
        elsewhere = self.tmp / 'main-elsewhere'
        self.git('worktree', 'add', '-q', str(elsewhere), 'main')
        result = _run(['bash', GITFLOW, 'candidate'], elsewhere, {**self.env, 'CI_CMD': 'true'})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('主目录', result.stderr)

    def test_narrowed_code_paths_cannot_hide_dirty_source(self):
        # R2-1：CODE_PATHS 只许扩大，缩窄成 manuscript 也照样检查默认的 src
        (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        result = self.gitflow('candidate', CODE_PATHS='manuscript')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('src/model.py', result.stderr)
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head, CODE_PATHS='manuscript'),
                                   'src/model.py')

    def test_exclude_pathspec_cannot_narrow_code_paths(self):
        # R3-1：CODE_PATHS=':(exclude)src' 曾把默认的 src 排除出 candidate 干净门、freeze 干净门与候选 diff
        for extra in (':(exclude)src', ':!src', ':(glob)nothing/**'):
            with self.subTest(CODE_PATHS=extra):
                (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
                self.assertNotEqual(self.gitflow('candidate', CODE_PATHS=extra).returncode, 0)
                self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head, CODE_PATHS=extra))
                self.git('checkout', '-q', '--', 'src/model.py')
        (self.repo / 'src' / 'model.py').write_text('V = 3\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'feat: unreviewed change')
        for extra in (':(exclude)src', ':!src'):
            with self.subTest(candidate_diff=extra):
                self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head, CODE_PATHS=extra))

    def test_candidate_refuses_commit_made_while_ci_runs(self):
        # R3-2：CI 期间另一进程提交，candidate 不得把没跑过这次 CI 的新 HEAD 当候选
        script = self.tmp / 'ci-commits.sh'
        script.write_text('#!/bin/sh\ngit commit -q --allow-empty -m "concurrent commit during CI"\n', encoding='utf-8')
        result = self.gitflow('candidate', CI_CMD='sh %s' % script)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(self.head, result.stderr)  # 报出 CI 开始时的 HEAD
        self.assertNotIn('--candidate', result.stdout)

    def test_candidate_refuses_modified_source(self):
        (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        result = self.gitflow('candidate')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('src/model.py', result.stderr)

    def test_candidate_refuses_untracked_file_under_experiments(self):
        (self.repo / 'experiments' / 'I01' / 'scratch.py').write_text('X = 1\n', encoding='utf-8')
        result = self.gitflow('candidate')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('experiments/I01/scratch.py', result.stderr)

    def test_candidate_fails_when_ci_fails(self):
        self.assertNotEqual(self.gitflow('candidate', CI_CMD='false').returncode, 0)

    def test_freeze_passes_with_unfinished_paper_and_freezes_committed_content(self):
        self.edit_paper_and_notes()
        result = self.gitflow('freeze', 'r1', '--candidate', self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref('refs/tags/run/r1'), self.head)
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.run_dir), self.head)
        self.assertEqual((self.run_dir / 'manuscript' / 'draft.tex').read_text(encoding='utf-8'), 'draft v1\n')
        self.assertFalse((self.run_dir / '想法笔记.md').exists())
        self.assertIn('写到一半', (self.repo / 'manuscript' / 'draft.tex').read_text(encoding='utf-8'))  # 主目录草稿原样
        self.assertTrue((self.repo / '想法笔记.md').exists())

    def test_freeze_refuses_modified_source_without_tagging(self):
        (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head), 'src/model.py')

    def test_freeze_refuses_untracked_file_under_experiments_without_tagging(self):
        (self.repo / 'experiments' / 'I01' / 'scratch.py').write_text('X = 1\n', encoding='utf-8')
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head), 'experiments/I01/scratch.py')

    def test_code_paths_can_be_overridden(self):
        self.edit_paper_and_notes()
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head, CODE_PATHS='src manuscript'), 'manuscript/draft.tex')

    def test_freeze_no_worktree_only_tags_and_stamps(self):
        self.edit_paper_and_notes()
        result = self.gitflow('freeze', 'r1', '--candidate', self.head, '--no-worktree')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref('refs/tags/run/r1'), self.head)
        self.assertIsNone(self.ref('refs/heads/train/r1'))
        self.assertFalse(self.run_dir.exists())
        stamp = json.loads((self.wt_root / 'run-r1.GIT_STAMP.json').read_text(encoding='utf-8'))  # 沙箱无 gitstamp 模块，走内置最小版
        self.assertEqual((stamp['commit'], stamp['run_tag'], stamp['dirty']), (self.head, 'run/r1', False))
        self.assertFalse((self.repo / 'GIT_STAMP.json').exists())  # 首审 #3：不写主目录根，免得被下一次冻结覆盖
        self.assertEqual(self.git('worktree', 'list', '--porcelain').count('worktree '), 1)

    def test_freeze_requires_candidate(self):
        # 首审 #1：不给获审候选 H 就不冻结
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1'), '--candidate')

    def test_freeze_refuses_symbolic_short_or_unknown_candidate(self):
        for candidate in ('HEAD', 'main', 'refs/heads/main', 'HEAD^{commit}', 'abc12', 'deadbeefdeadbeef'):
            with self.subTest(candidate=candidate):
                self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', candidate), '--candidate')

    def test_freeze_after_paper_only_commits_binds_reviewed_code(self):
        # H 之后只有论文提交：代码与 H 相同，放行，冻结当前 main HEAD
        (self.repo / 'manuscript' / 'draft.tex').write_text('draft v2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'docs(paper): v2')
        tip = self.git('rev-parse', 'HEAD')
        result = self.gitflow('freeze', 'r1', '--candidate', self.head[:10])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ref('refs/tags/run/r1'), tip)

    def test_freeze_refuses_code_commit_after_candidate(self):
        # 首审 #1：获审后 main 又提交了代码，工作树干净也不得冻结
        (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'feat: unreviewed change')
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head), 'src/model.py')

    def test_narrowed_code_paths_cannot_hide_reviewed_code_change(self):
        # R2-1：获审后 main 提交了 src 改动，用 CODE_PATHS=manuscript 冻结也必须拒绝
        (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'feat: unreviewed change')
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head, CODE_PATHS='manuscript'),
                                   'src/model.py')

    def test_worktree_freeze_records_candidate_in_run_level_stamp(self):
        # ②：带 worktree 的 freeze 即使由 STAMP_CMD 写 worktree 内的 stamp，也另写一份记录候选 H 的 run 级 stamp
        (self.repo / 'manuscript' / 'draft.tex').write_text('draft v2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'docs(paper): v2')
        tip = self.git('rev-parse', 'HEAD')
        result = self.gitflow('freeze', 'r1', '--candidate', self.head[:10], STAMP_CMD='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        stamp = json.loads((self.wt_root / 'run-r1.GIT_STAMP.json').read_text(encoding='utf-8'))
        self.assertEqual((stamp['candidate'], stamp['commit'], stamp['run_tag']), (self.head, tip, 'run/r1'))
        self.assertIn(self.head, result.stdout)
        self.assertIn(tip, result.stdout)

    def test_freeze_refuses_candidate_not_on_main(self):
        # 候选来自未合入 main 的分支（只改论文，代码范围与 main 相同，只有祖先核对能拦下）
        self.git('checkout', '-q', '-b', 'wt/side')
        (self.repo / 'manuscript' / 'draft.tex').write_text('side\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'side')
        side = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-q', 'main')
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', side), '不在 main')

    def test_freeze_unknown_option_is_refused_without_tagging(self):
        self.assert_nothing_frozen(self.gitflow('freeze', 'r1', '--candidate', self.head, '--bogus'), '--bogus')

    def test_status_runs_on_single_trunk(self):
        result = self.gitflow('status')
        self.assertEqual(result.returncode, 0, result.stderr)


class GitflowLinkedAssetsTests(_Sandbox):
    """--link-assets：临时 worktree 用符号链接挂主目录的重资产；收尾只摘链接本身，绝不递归触碰目标（坑 G5 的延伸）。"""

    CKPT = 'experiments/I01/results/r0/checkpoints'

    def setUp(self):
        super().setUp()
        for rel, text in (('src/model.py', 'V = 1\n'), ('experiments/I01/results/index.md', '# results\n'),
                          ('.gitignore', 'logs/\ncheckpoints/\n*.pth\n*.npz\nGIT_STAMP.json\n__pycache__/\n')):
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        self.head = self.git('rev-parse', 'HEAD')
        self.assets = {f'{self.CKPT}/best.pth': b'weights-1', f'{self.CKPT}/feats.npz': b'npz-bytes',
                       'logs/train.log': b'epoch 1\n'}
        for rel, data in self.assets.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.assertEqual(self.git('status', '--porcelain'), '')  # 主目录的重资产全部被忽略
        self.wt_root = self.tmp / 'repo.worktrees'
        self.run_dir = self.wt_root / 'run-r1'
        self.wt_dir = self.wt_root / 'wt-feat'

    def gitflow(self, *args, **env):
        return _run(['bash', GITFLOW, *args], self.repo, {**self.env, **env})

    def ok(self, *args, **env):
        result = self.gitflow(*args, **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def assert_assets_intact(self):
        for rel, data in self.assets.items():
            path = self.repo / rel
            self.assertFalse(any(p.is_symlink() for p in (path, *path.parents)), rel)
            self.assertEqual(path.read_bytes(), data, rel)

    def assert_linked(self, worktree, rel):
        link = worktree / rel
        self.assertTrue(link.is_symlink(), rel)
        self.assertEqual(link.resolve(), (self.repo / rel).resolve())

    def assert_refused(self, result, worktree, *fragments):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for fragment in ('不删', *fragments):
            self.assertIn(fragment, result.stderr)
        self.assertTrue(worktree.is_dir())  # 排查现场保留
        self.assert_assets_intact()

    def assert_nothing_created(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for name in ('refs/tags/run/r1', 'refs/heads/train/r1', 'refs/heads/wt/feat'):
            self.assertIsNone(self.ref(name), name)
        self.assertFalse(self.run_dir.exists())
        self.assertFalse(self.wt_dir.exists())
        self.assert_assets_intact()

    def cand(self, command):
        return ('--candidate', self.head) if command == 'freeze' else ()

    def assert_rolled_back(self, result):
        self.assert_nothing_created(result)  # tag、run/wt 分支、目录都不存在，主目录资产完好
        self.assertEqual(self.git('worktree', 'list', '--porcelain').count('worktree '), 1)
        self.assertFalse((self.wt_root / 'run-r1.GIT_STAMP.json').exists())
        self.assert_no_lock_left()

    def assert_no_lock_left(self):
        locks = _lock_root(self.repo)
        self.assertEqual(sorted(p.name for p in locks.iterdir()) if locks.exists() else [], [])

    def test_concurrent_same_name_never_destroys_the_winner(self):
        # R2-2：两个同名 freeze / wt-add 同时通过预检时，失败方的回滚曾删掉成功方的 worktree 与分支
        path = _path_with_blocking_worktree_add(self.tmp, self.env)
        cases = (('freeze', 'r1', self.run_dir, 'train/r1'), ('wt-add', 'feat', self.wt_dir, 'wt/feat'))
        for command, name, directory, branch in cases:
            with self.subTest(command=command):
                barrier = self.tmp / ('barrier-' + name)
                barrier.mkdir()
                first = subprocess.Popen(['bash', str(GITFLOW), command, name, *self.cand(command)], cwd=str(self.repo),
                                         env={**self.env, 'PATH': path, 'GF_BARRIER': str(barrier)},
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace')
                for _ in range(400):  # 等第一个进程停在 worktree add 之前（已过全部预检）
                    if (barrier / 'ready').exists() or first.poll() is not None:
                        break
                    time.sleep(0.05)
                if not (barrier / 'ready').exists():  # 不能把 communicate() 写进断言消息：它会立即求值并等进程结束
                    self.fail(first.communicate())
                second = self.gitflow(command, name, *self.cand(command), PATH=path)
                (barrier / 'go').touch()
                out, err = first.communicate(timeout=60)
                outcomes = [(first.returncode, err), (second.returncode, second.stderr)]
                self.assertEqual(sum(rc == 0 for rc, _ in outcomes), 1, outcomes)
                self.assertTrue(directory.is_dir(), outcomes)  # 成功方的现场完好
                self.assertEqual(self.git('rev-parse', 'HEAD', cwd=directory), self.head)
                self.assertEqual(self.ref('refs/heads/' + branch), self.head)
                if command == 'freeze':
                    self.assertEqual(self.ref('refs/tags/run/r1'), self.head)
                self.assert_no_lock_left()
                self.assert_assets_intact()

    def test_stale_lock_refuses_without_touching_anything(self):
        lock = _lock_root(self.repo) / 'run-r1'
        lock.mkdir(parents=True)
        result = self.gitflow('freeze', 'r1', '--candidate', self.head)
        self.assertIn(str(lock), result.stderr)
        self.assert_nothing_created(result)
        self.assertTrue(lock.is_dir())  # 别人的锁不删

    def test_successful_freeze_and_wt_add_release_their_locks(self):
        self.ok('freeze', 'r1', '--candidate', self.head, '--link-assets', 'logs')
        self.ok('wt-add', 'feat')
        self.assert_no_lock_left()
        self.ok('cleanup', 'r1')
        self.ok('wt-rm', 'feat')
        self.assert_no_lock_left()

    def test_stamp_failure_rolls_back_worktree_branch_and_links(self):
        # 首审 #2：stamp 失败曾留下 tag、run 分支、worktree 与链接
        for prefix in ('train/', ''):
            with self.subTest(RUN_BRANCH_PREFIX=prefix):
                self.assert_rolled_back(self.gitflow('freeze', 'r1', '--candidate', self.head, '--link-assets',
                                                     self.CKPT, 'logs', STAMP_CMD='false', RUN_BRANCH_PREFIX=prefix))

    def test_link_failure_midway_rolls_back(self):
        # 第二条链接建失败：第一条链接、worktree、分支都要撤掉，主目录目标不动
        bindir = self.tmp / 'fakebin'
        bindir.mkdir()
        (bindir / 'ln').write_text('#!/bin/sh\ncase "$*" in *run-r1/logs*|*wt-feat/logs*) echo fake-ln-fail >&2; exit 1 ;; esac\n'
                                   'exec %s "$@"\n' % shutil.which('ln'), encoding='utf-8')
        (bindir / 'ln').chmod(0o755)
        path = '%s:%s' % (bindir, self.env['PATH'])
        for command, name in (('freeze', 'r1'), ('wt-add', 'feat')):
            with self.subTest(command=command):
                result = self.gitflow(command, name, *self.cand(command), '--link-assets', self.CKPT, 'logs', PATH=path)
                self.assertIn('fake-ln-fail', result.stderr)  # 确认故障确实注入到了建链这一步
                self.assert_rolled_back(result)

    def test_tag_failure_at_the_last_step_rolls_back_everything(self):
        # 最后一步打 tag 失败：已发布的 run 级 stamp（沙箱无 gitstamp，走内置版）、链接、worktree、分支全部撤掉
        path = _path_with_failing_git_tag(self.tmp, self.env)
        for prefix in ('train/', ''):
            with self.subTest(RUN_BRANCH_PREFIX=prefix):
                result = self.gitflow('freeze', 'r1', '--candidate', self.head, '--link-assets', self.CKPT, 'logs',
                                      PATH=path, RUN_BRANCH_PREFIX=prefix)
                self.assertIn('fake-tag-fail', result.stderr)  # 确认故障注入在打 tag 这一步
                self.assert_rolled_back(result)

    def test_signal_right_after_tag_keeps_the_complete_freeze(self):
        # R3-3：tag 已创建、事务尚未收尾时被 SIGTERM，曾回滚掉 worktree、链接与 stamp 却留下 tag
        result = self.gitflow('freeze', 'r1', '--candidate', self.head, '--link-assets', 'logs',
                              PATH=_path_with_git_tag_then_sigterm(self.tmp, self.env))
        self.assertIn('tag-created-then-sigterm', result.stderr)  # 确认中断确实落在打 tag 之后
        self.assertEqual(result.returncode, 143, result.stderr)  # 信号被转成 exit 143，经 on_exit 正常收尾
        self.assertEqual(self.ref('refs/tags/run/r1'), self.head)
        self.assertTrue(self.run_dir.is_dir(), result.stderr)  # 冻结完整：worktree、分支、链接、stamp 都在
        self.assertEqual(self.ref('refs/heads/train/r1'), self.head)
        self.assert_linked(self.run_dir, 'logs')
        self.assertTrue((self.wt_root / 'run-r1.GIT_STAMP.json').is_file())
        self.assert_no_lock_left()
        self.assert_assets_intact()
        self.ok('cleanup', 'r1')  # 之后能正常收尾

    def test_worktree_add_failure_leaves_no_tag_or_branch(self):
        self.wt_root.mkdir()
        self.wt_root.chmod(0o555)  # worktree 目录建不出来
        self.addCleanup(self.wt_root.chmod, 0o755)
        for command, name in (('freeze', 'r1'), ('wt-add', 'feat')):
            with self.subTest(command=command):
                self.assert_rolled_back(self.gitflow(command, name, *self.cand(command)))

    def test_freeze_links_assets_and_cleanup_only_removes_the_links(self):
        self.ok('freeze', 'r1', '--candidate', self.head, '--link-assets', self.CKPT, 'logs')
        self.assert_linked(self.run_dir, self.CKPT)
        self.assert_linked(self.run_dir, 'logs')
        self.assertEqual((self.run_dir / self.CKPT / 'best.pth').read_bytes(), b'weights-1')  # 经链接可读
        # 钉住 git 行为：以 / 结尾的忽略规则（logs/）不匹配符号链接，链接在 worktree 里显示为未跟踪
        self.assertIn('?? logs', self.git('status', '--porcelain', '--untracked-files=all', cwd=self.run_dir))
        self.ok('cleanup', 'r1')
        self.assertFalse(self.run_dir.exists())
        self.assertIsNone(self.ref('refs/heads/train/r1'))
        self.assertEqual(self.ref('refs/tags/run/r1'), self.head)
        self.assert_assets_intact()

    def test_wt_add_links_assets_and_wt_rm_only_removes_the_links(self):
        self.ok('wt-add', 'feat', '--link-assets', self.CKPT, 'logs')
        self.assertEqual(self.git('symbolic-ref', 'HEAD', cwd=self.wt_dir), 'refs/heads/wt/feat')
        self.assert_linked(self.wt_dir, self.CKPT)
        self.assert_linked(self.wt_dir, 'logs')
        self.ok('wt-rm', 'feat')
        self.assertFalse(self.wt_dir.exists())
        self.assertIsNone(self.ref('refs/heads/wt/feat'))
        self.assert_assets_intact()

    def test_file_written_through_a_link_lands_in_main_and_survives(self):
        self.ok('freeze', 'r1', '--candidate', self.head, '--link-assets', 'logs')
        (self.run_dir / 'logs' / 'new.log').write_bytes(b'epoch 2\n')
        self.ok('cleanup', 'r1')
        self.assertEqual((self.repo / 'logs' / 'new.log').read_bytes(), b'epoch 2\n')
        self.assert_assets_intact()

    def test_real_checkpoint_next_to_a_link_is_refused_and_links_are_kept(self):
        for command, name, worktree in (('freeze', 'r1', self.run_dir), ('wt-add', 'feat', self.wt_dir)):
            with self.subTest(command=command):
                self.ok(command, name, *self.cand(command), '--link-assets', self.CKPT, 'logs')
                (worktree / 'best.pth').write_bytes(b'weights-2')  # 真实文件直接写进 worktree
                closer = 'cleanup' if command == 'freeze' else 'wt-rm'
                self.assert_refused(self.gitflow(closer, name), worktree, 'best.pth')
                self.assertEqual((worktree / 'best.pth').read_bytes(), b'weights-2')
                self.assert_linked(worktree, self.CKPT)  # 拒绝时不摘任何链接
                self.assert_linked(worktree, 'logs')

    def test_unregistered_symlink_is_refused(self):
        self.ok('freeze', 'r1', '--candidate', self.head)
        os.symlink(self.repo / 'logs', self.run_dir / 'logs')  # 不是 gitflow 建的链接
        self.assert_refused(self.gitflow('cleanup', 'r1'), self.run_dir, 'logs')
        self.assertTrue((self.run_dir / 'logs').is_symlink())

    def test_retargeted_link_is_refused(self):
        self.ok('freeze', 'r1', '--candidate', self.head, '--link-assets', 'logs')
        elsewhere = self.tmp / 'elsewhere'
        elsewhere.mkdir()
        (elsewhere / 'keep.log').write_bytes(b'outside')
        (self.run_dir / 'logs').unlink()
        os.symlink(elsewhere, self.run_dir / 'logs')  # 登记过的路径被换成指向主目录之外
        self.assert_refused(self.gitflow('cleanup', 'r1'), self.run_dir, 'logs')
        self.assertTrue((self.run_dir / 'logs').is_symlink())
        self.assertEqual((elsewhere / 'keep.log').read_bytes(), b'outside')

    def test_link_replaced_by_a_real_directory_is_refused(self):
        self.ok('wt-add', 'feat', '--link-assets', 'logs')
        (self.wt_dir / 'logs').unlink()
        (self.wt_dir / 'logs').mkdir()
        (self.wt_dir / 'logs' / 'train.log').write_bytes(b'real run output')
        self.assert_refused(self.gitflow('wt-rm', 'feat'), self.wt_dir, 'logs/train.log')
        self.assertEqual((self.wt_dir / 'logs' / 'train.log').read_bytes(), b'real run output')

    def test_invalid_link_paths_are_refused_before_anything_is_created(self):
        (self.repo / 'logs' / 'sub').mkdir()
        cases = (['/etc'], [str(self.repo / 'logs')], ['../outside'], ['experiments/../logs'], ['missing/dir'],
                 ['src'], ['src/model.py'], ['logs', 'logs/sub'], ['logs', 'logs'], [])
        for paths in cases:
            for command, name in (('freeze', 'r1'), ('wt-add', 'feat')):
                with self.subTest(command=command, paths=paths):
                    self.assert_nothing_created(self.gitflow(command, name, *self.cand(command), '--link-assets', *paths))

    def test_wt_cycle_add_commit_fast_forward_remove(self):
        utf8 = {'LC_ALL': 'en_US.UTF-8'}  # 坑 G3：bash 3.2 的多字节问题只在 UTF-8 locale 下出现
        self.ok('wt-add', 'feat', **utf8)
        (self.wt_dir / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'feat(I9): step', cwd=self.wt_dir)
        tip = self.git('rev-parse', 'HEAD', cwd=self.wt_dir)
        refused = self.gitflow('wt-rm', 'feat', **utf8)  # 还没合入 main
        self.assert_refused(refused, self.wt_dir, 'wt/feat')
        self.assertEqual(self.ref('refs/heads/wt/feat'), tip)
        self.git('merge', '-q', '--ff-only', 'wt/feat')
        self.ok('wt-rm', 'feat', **utf8)
        self.assertFalse(self.wt_dir.exists())
        self.assertIsNone(self.ref('refs/heads/wt/feat'))
        self.assertEqual(self.git('rev-parse', 'main'), tip)

    def test_wt_rm_refuses_uncommitted_change(self):
        self.ok('wt-add', 'feat')
        (self.wt_dir / 'src' / 'model.py').write_text('V = 3\n', encoding='utf-8')
        self.assert_refused(self.gitflow('wt-rm', 'feat'), self.wt_dir)
        self.assertEqual((self.wt_dir / 'src' / 'model.py').read_text(encoding='utf-8'), 'V = 3\n')

    def test_wt_rm_refuses_other_branch_checked_out(self):
        self.ok('wt-add', 'feat')
        self.git('checkout', '-q', '-b', 'hijack', cwd=self.wt_dir)
        self.assert_refused(self.gitflow('wt-rm', 'feat'), self.wt_dir, 'hijack')
        self.assertIsNotNone(self.ref('refs/heads/wt/feat'))

    def test_wt_add_refuses_bad_or_duplicate_names(self):
        for name in ('a/b', '../x', '.hidden', '-x'):
            with self.subTest(name=name):
                self.assertNotEqual(self.gitflow('wt-add', name).returncode, 0)
        self.assertFalse(self.wt_root.exists() and any(self.wt_root.iterdir()))
        self.ok('wt-add', 'feat')
        self.assertNotEqual(self.gitflow('wt-add', 'feat').returncode, 0)
        self.assertTrue(self.wt_dir.is_dir())


class GitflowRunStampTests(_Sandbox):
    """首审 #3：--no-worktree 的 stamp 曾写在主目录根的 GIT_STAMP.json，下一次冻结会覆盖它，且没有绑定 tag。
    这里拷入真实的 src/trimodalsurv/gitstamp.py，走生产路径，不走内置最小版。"""

    def setUp(self):
        super().setUp()
        package = self.repo / 'src' / 'trimodalsurv'
        package.mkdir(parents=True)
        for name in ('__init__.py', 'gitstamp.py'):
            shutil.copy2(ROOT / 'src' / 'trimodalsurv' / name, package / name)
        for rel, text in (('src/model.py', 'V = 1\n'), ('manuscript/draft.tex', 'draft v1\n'),
                          ('.gitignore', '/GIT_STAMP.json\n__pycache__/\n')):
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        self.h1 = self.git('rev-parse', 'HEAD')
        self.wt_root = self.tmp / 'repo.worktrees'

    def gitflow(self, *args, **env):
        return _run(['bash', GITFLOW, *args], self.repo,
                    {**self.env, 'CI_CMD': 'true', 'PYTHON_BIN': sys.executable, **env})

    def freeze(self, run_id, commit, **env):
        return self.gitflow('freeze', run_id, '--no-worktree', '--candidate', commit, **env)

    def stamp(self, run_id):
        return json.loads((self.wt_root / f'run-{run_id}.GIT_STAMP.json').read_text(encoding='utf-8'))

    def test_run_level_stamp_is_bound_to_tag_and_never_overwritten(self):
        result = self.freeze('r1', self.h1)
        self.assertEqual(result.returncode, 0, result.stderr)
        first = self.stamp('r1')
        self.assertEqual((first['commit'], first['run_id'], first['run_tag'], first['candidate']),
                         (self.h1, 'r1', 'run/r1', self.h1))
        self.assertIn('src/model.py', first['files'])  # 生产格式：逐文件 blob 哈希
        self.assertEqual(self.ref('refs/tags/run/r1'), self.h1)
        self.assertFalse((self.repo / 'GIT_STAMP.json').exists())
        before = (self.wt_root / 'run-r1.GIT_STAMP.json').read_bytes()
        (self.repo / 'src' / 'model.py').write_text('V = 2\n', encoding='utf-8')
        self.git('commit', '-q', '-am', 'next version')
        h2 = self.git('rev-parse', 'HEAD')
        result = self.freeze('r2', h2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.wt_root / 'run-r1.GIT_STAMP.json').read_bytes(), before)  # 旧 run 的 stamp 不变
        second = self.stamp('r2')
        self.assertEqual(second['commit'], h2)
        self.assertNotEqual(second['files']['src/model.py'], first['files']['src/model.py'])

    def test_existing_run_stamp_is_refused_and_left_untouched(self):
        self.wt_root.mkdir()
        old = self.wt_root / 'run-r1.GIT_STAMP.json'
        old.write_text('old\n', encoding='utf-8')
        result = self.freeze('r1', self.h1)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIsNone(self.ref('refs/tags/run/r1'))
        self.assertEqual(old.read_text(encoding='utf-8'), 'old\n')

    def test_tag_failure_removes_the_published_stamp(self):
        result = self.freeze('r1', self.h1, PATH=_path_with_failing_git_tag(self.tmp, self.env))
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('fake-tag-fail', result.stderr)
        self.assertIsNone(self.ref('refs/tags/run/r1'))
        self.assertEqual(sorted(p.name for p in self.wt_root.iterdir()), [])  # stamp 与临时文件都不留

    def test_signal_right_after_tag_keeps_the_run_stamp(self):
        # R3-3（--no-worktree）：tag 已创建后被 SIGTERM，run 级 stamp 不得被回滚
        result = self.freeze('r1', self.h1, PATH=_path_with_git_tag_then_sigterm(self.tmp, self.env))
        self.assertIn('tag-created-then-sigterm', result.stderr)
        self.assertEqual(self.ref('refs/tags/run/r1'), self.h1)
        self.assertEqual(self.stamp('r1')['commit'], self.h1)

    def test_stamp_failure_leaves_no_tag_and_no_stamp(self):
        result = self.freeze('r1', self.h1, PYTHON_BIN='false')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIsNone(self.ref('refs/tags/run/r1'))
        self.assertEqual(sorted(p.name for p in self.wt_root.iterdir()) if self.wt_root.exists() else [], [])


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

    def test_help_describes_single_trunk_commands_only(self):
        result = _run(['bash', self.script, '--help'], self.outside, self.env)
        self.assert_help(result)
        for wanted in ('candidate', 'freeze <run_id>', '--no-worktree', '--link-assets', 'wt-add <name>',
                       'wt-rm <name>', 'CODE_PATHS'):
            self.assertIn(wanted, result.stdout)
        for retired in ('squash', 'DEV_BRANCH'):
            self.assertNotIn(retired, result.stdout)

    def test_retired_dev_subcommands_are_unknown(self):
        (self.repo / 'model.py').write_text('V = 1\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        for retired in ('init', 'squash'):
            with self.subTest(subcommand=retired):
                result = _run(['bash', self.script, retired, 'msg'], self.repo, self.env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"未知子命令 '{retired}'", result.stderr)
        self.assertIsNone(self.ref('refs/heads/dev'))
        self.assertFalse((self.tmp / 'repo.worktrees').exists())


class GitflowMultibyteTests(_Sandbox):
    """审查外发现：macOS bash 3.2 在 UTF-8 locale 下把紧跟 $var 的全角标点首字节并入变量名，set -u 下日志行崩溃。"""

    def test_no_unbraced_variable_before_multibyte_text(self):
        pattern = re.compile(r'\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]')
        offenders = [f'{script.name}:{number}: {line.strip()}' for script in (GITFLOW, CI, CODEX_REVIEW)
                     for number, line in enumerate(script.read_text(encoding='utf-8').splitlines(), 1)
                     if not line.lstrip().startswith('#') and pattern.search(line)]
        self.assertEqual(offenders, [])

    def test_freeze_and_cleanup_run_to_completion_in_utf8_locale(self):
        # 原 init → squash 闭环随常驻 dev 一起退役（用户裁决 2026-11-12）；wt-add → 合入 → wt-rm 闭环见
        # GitflowLinkedAssetsTests.test_wt_cycle_add_commit_fast_forward_remove
        (self.repo / 'model.py').write_text('V = 1\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        env = {**self.env, 'LC_ALL': 'en_US.UTF-8', 'CI_CMD': 'true'}
        head = self.git('rev-parse', 'HEAD')
        for args in (['candidate'], ['freeze', 'r1', '--candidate', head], ['status'], ['cleanup', 'r1']):
            with self.subTest(args=args):
                result = _run(['bash', GITFLOW, *args], self.repo, env)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.tmp / 'repo.worktrees' / 'run-r1').exists())


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
