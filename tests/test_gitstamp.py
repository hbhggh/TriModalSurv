"""运行即盖章契约：commit 身份、拒跑门、无 .git 拷贝的 stamp、可重建账本；不读取患者数据。"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from trimodalsurv import gitstamp
from trimodalsurv.config import file_fingerprint, start_run_record, finalize_run_record

FAKE_GIT = {'source': 'git', 'commit': 'a' * 40, 'branch': 'exp/demo', 'dirty': False,
            'dirty_files': [], 'external': [], 'allow_dirty': False}


def _run_git(root, *args):
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@contextmanager
def _environment(**values):
    """conftest 默认放行 dirty；需要验证拒跑的用例在这里显式收回。"""
    with mock.patch.dict(os.environ):
        os.environ.pop(gitstamp.ALLOW_DIRTY_ENV, None)
        os.environ.update(values)
        yield


@unittest.skipIf(shutil.which('git') is None, '需要 git')
class GitIdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve() / 'project'
        for rel, text in {'src/a.py': 'A = 1\n', 'configs/c.yaml': '{}\n', 'notes.md': 'draft\n',
                          '实验（8）/m.py': 'M = 1\n'}.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text, encoding='utf-8')
        _run_git(self.root, 'init', '-q')
        _run_git(self.root, 'add', '-A')
        _run_git(self.root, 'commit', '-q', '-m', 'hypothesis')
        self.commit = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()

    def closure(self, root=None, names=('src/a.py', 'configs/c.yaml', '实验（8）/m.py')):
        return [file_fingerprint((root or self.root) / name) for name in names]

    def test_clean_closure_pins_commit_and_ignores_documents(self):
        (self.root / 'notes.md').write_text('edited draft\n', encoding='utf-8')
        with _environment():
            identity = gitstamp.require_git_identity(self.closure(), root=self.root)
        self.assertEqual((identity['source'], identity['commit'], identity['dirty']), ('git', self.commit, False))
        self.assertEqual((identity['dirty_files'], identity['allow_dirty']), ([], False))

    def test_modified_or_untracked_source_is_refused_before_any_record(self):
        (self.root / 'src/a.py').write_text('A = 2\n', encoding='utf-8')
        (self.root / 'src/b.py').write_text('B = 1\n', encoding='utf-8')
        names = ('src/a.py', 'src/b.py', 'configs/c.yaml')
        with _environment():
            with self.assertRaises(gitstamp.DirtyWorktreeError) as caught:
                gitstamp.require_git_identity(self.closure(names=names), root=self.root)
            self.assertIn('src/a.py', str(caught.exception))
            self.assertIn('git commit', str(caught.exception))
            allowed = gitstamp.require_git_identity(self.closure(names=names), root=self.root, allow_dirty=True)
        self.assertEqual(allowed['dirty_files'], ['src/a.py', 'src/b.py'])
        self.assertTrue(allowed['dirty'] and allowed['allow_dirty'])
        with _environment(**{gitstamp.ALLOW_DIRTY_ENV: '1'}):
            self.assertTrue(gitstamp.require_git_identity(self.closure(names=names), root=self.root)['allow_dirty'])

    def test_stamp_carries_commit_to_copy_without_git(self):
        stamp = gitstamp.write_stamp(self.root)
        self.assertIn('实验（8）/m.py', stamp['files'])
        self.assertNotIn('notes.md', stamp['files'])
        server = self.root.parent / 'server-copy'
        shutil.copytree(self.root, server, ignore=shutil.ignore_patterns('.git'))
        with _environment():
            identity = gitstamp.require_git_identity(self.closure(server), root=server)
            self.assertEqual((identity['source'], identity['commit'], identity['dirty']), ('stamp', self.commit, False))
            (server / 'src/a.py').write_text('A = 3\n', encoding='utf-8')
            with self.assertRaises(gitstamp.DirtyWorktreeError) as caught:
                gitstamp.require_git_identity(self.closure(server), root=server)
            self.assertIn('scripts/git_stamp.py', str(caught.exception))
            (server / gitstamp.STAMP_NAME).unlink()
            with self.assertRaises(gitstamp.DirtyWorktreeError) as caught:
                gitstamp.require_git_identity(self.closure(server), root=server)
            self.assertIn('拿不到 git 身份', str(caught.exception))

    def test_stale_stamp_is_detected_by_content(self):
        gitstamp.write_stamp(self.root)
        (self.root / 'src/a.py').write_text('A = 4\n', encoding='utf-8')
        _run_git(self.root, 'commit', '-q', '-am', 'next hypothesis')
        server = self.root.parent / 'server-copy'
        shutil.copytree(self.root, server, ignore=shutil.ignore_patterns('.git'))
        identity = gitstamp.git_identity(self.closure(server), root=server)
        self.assertEqual((identity['commit'], identity['dirty_files']), (self.commit, ['src/a.py']))

    def test_nested_copy_never_borrows_outer_repository(self):
        nested = self.root / 'vendor' / 'copy'
        (nested / 'src').mkdir(parents=True)
        (nested / 'src/a.py').write_text('A = 1\n', encoding='utf-8')
        identity = gitstamp.git_identity([file_fingerprint(nested / 'src/a.py')], root=nested)
        self.assertEqual((identity['source'], identity['commit'], identity['dirty']), ('none', None, True))

    def test_external_inputs_are_listed_without_absolute_paths(self):
        outside = self.root.parent / 'outside.yaml'
        outside.write_text('{}\n', encoding='utf-8')
        identity = gitstamp.git_identity(self.closure() + [file_fingerprint(outside)], root=self.root)
        self.assertFalse(identity['dirty'])
        self.assertEqual([item['name'] for item in identity['external']], ['outside.yaml'])
        self.assertNotIn(str(self.root.parent), json.dumps(identity, ensure_ascii=False))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.ledger = self.root / 'ledger' / 'results.tsv'
        self.checkpoint = self.root / 'model.pth'
        self.checkpoint.write_bytes(b'synthetic-checkpoint')
        label = self.root / 'label.csv'
        label.write_text('patient_id,split\nP1,train\n', encoding='utf-8')
        self.label = file_fingerprint(label)
        self.payload = {'git': dict(FAKE_GIT), 'inputs': [self.label], 'source_fingerprints': [],
                        'runtime': {'seed': 123, 'cancer_types': 'BLCA', 'note': '一句话\t假设', 'config': None}}

    def start(self, run_id=None):
        with _environment(**{gitstamp.LEDGER_ENV: str(self.ledger)}):
            return start_run_record(self.root / 'results', self.payload, checkpoint_path=self.checkpoint, run_id=run_id)

    def test_run_id_and_git_record_carry_commit(self):
        run = self.start()
        self.assertRegex(run.name, r'^\d{8}T\d{6}Z_aaaaaaa-[0-9a-f]{8}$')
        recorded = json.loads((run / 'git.json').read_text(encoding='utf-8'))
        self.assertEqual((recorded['commit'], recorded['branch']), (FAKE_GIT['commit'], 'exp/demo'))
        self.assertIn('-dirty-', gitstamp.new_run_id({'commit': 'b' * 40, 'dirty': True}))
        self.assertTrue(gitstamp.new_run_id({'commit': None, 'dirty': True}).split('_')[1].startswith('nogit-dirty-'))

    def test_finished_run_appends_one_row_and_ledger_is_rebuildable(self):
        run = self.start('done-run')
        finalize_run_record(run, checkpoint_path=self.checkpoint, metrics={'c-index': 0.6125, 'loss': float('nan')})
        rows = gitstamp.read_ledger(self.ledger)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['commit'], row['dirty'], row['branch'], row['status']), ('a' * 40, '0', 'exp/demo', 'done'))
        self.assertEqual((row['seed'], row['cancer'], row['note']), ('123', 'BLCA', '一句话 假设'))
        self.assertEqual(row['split_id'], self.label['sha256'][:12])
        self.assertEqual(json.loads(row['metrics']), {'c-index': 0.6125, 'loss': 'nan'})
        original = self.ledger.read_text(encoding='utf-8')
        self.ledger.unlink()
        summary = gitstamp.rebuild_ledger([self.root / 'results'], path=self.ledger)
        self.assertEqual((summary['rows'], summary['scanned']), (1, 1))
        self.assertEqual(self.ledger.read_text(encoding='utf-8'), original)

    def test_rebuild_merges_foreign_rows_and_upgrades_pending(self):
        foreign = self.root / 'server.tsv'
        gitstamp.append_ledger({'time_utc': '2026-01-01T00:00:00+00:00', 'commit': 'c' * 40, 'status': 'done',
                                'run_dir': 'experiments/I03/results/remote-run'}, path=foreign)
        run = self.start('local-run')
        gitstamp.rebuild_ledger([self.root / 'results'], merge=[foreign], path=self.ledger)
        by_dir = {Path(row['run_dir']).name: row['status'] for row in gitstamp.read_ledger(self.ledger)}
        self.assertEqual(by_dir, {'remote-run': 'done', 'local-run': 'pending'})
        finalize_run_record(run, checkpoint_path=self.checkpoint)
        gitstamp.rebuild_ledger([self.root / 'results'], path=self.ledger)
        by_dir = {Path(row['run_dir']).name: row['status'] for row in gitstamp.read_ledger(self.ledger)}
        self.assertEqual(by_dir, {'remote-run': 'done', 'local-run': 'done'})

    def test_unfinished_run_is_recorded_as_crash_once(self):
        run = self.start('crashed-run')
        gitstamp._LAST_ERROR['text'] = 'RuntimeError: CUDA out of memory'
        self.addCleanup(gitstamp._LAST_ERROR.clear)
        gitstamp._record_unfinished()
        gitstamp._record_unfinished()
        crash = json.loads((run / 'audit/crash.json').read_text(encoding='utf-8'))
        self.assertEqual(crash['status'], 'crash')
        rows = gitstamp.read_ledger(self.ledger)
        self.assertEqual([(row['status'], row['commit']) for row in rows], [('crash', 'a' * 40)])
        self.assertIn('CUDA out of memory', rows[0]['note'])
        self.assertFalse((run / 'audit/completion.json').exists())

    def test_ledger_failure_never_fails_a_finished_run(self):
        run = self.start('unwritable-ledger')
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.mkdir()  # 账本路径被目录占用 → 追加必然失败
        finalize_run_record(run, checkpoint_path=self.checkpoint)
        self.assertEqual(json.loads((run / 'audit/completion.json').read_text())['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
