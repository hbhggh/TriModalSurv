"""运行即盖章：把一次运行钉到唯一的 git commit，并向可重建的账本追加一行。

身份来源按序：目录内有 .git → 直接读 HEAD；没有（代码是拷贝到服务器的）→ 读随代码同步的
GIT_STAMP.json（在有 .git 的机器上由 scripts/git_stamp.py 生成）。两种来源走同一判据：
活动源码闭包里每个文件的实际 sha256 必须等于该 commit 中同路径 blob 的 sha256，否则为 dirty。
文档、笔记等闭包外文件的改动不算 dirty。

旁路实验脚本接入（任何副作用之前）：
    from trimodalsurv.config import runtime_source_fingerprints
    from trimodalsurv.gitstamp import require_git_identity
    git = require_git_identity(runtime_source_fingerprints(args, experiment_dir=Path(__file__).parent),
                               allow_dirty=args.allow_dirty)
随后把 git 放进 start_run_record 的 payload['git']；finalize_run_record 负责记账。
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

STAMP_NAME = 'GIT_STAMP.json'
LEDGER_NAME = 'results.tsv'
STAMP_SUFFIXES = ('.py', '.yaml', '.yml', '.sh')
ALLOW_DIRTY_ENV = 'TRIMODALSURV_ALLOW_DIRTY'
LEDGER_ENV = 'TRIMODALSURV_LEDGER'
LEDGER_COLUMNS = ('time_utc', 'commit', 'dirty', 'branch', 'status', 'config', 'seed', 'cancer',
                  'metrics', 'split_id', 'run_dir', 'note')


class DirtyWorktreeError(RuntimeError):
    """源码闭包与 commit 不一致，或根本拿不到 commit。"""


def repo_root():
    return Path(__file__).resolve().parents[2]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _git(root, *args, stdin=None):
    # quotePath=false：含中文的路径原样输出（坑台账 V28）。
    return subprocess.run(['git', '-c', 'core.quotePath=false', '-C', str(root), *args], input=stdin,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout


def _has_git(root):
    # 只认本目录自己的 .git：拷贝目录若恰好落在别的仓库里，不得借用外层仓库的 HEAD。
    if not (Path(root) / '.git').exists():
        return False
    try:
        _git(root, 'rev-parse', '--verify', 'HEAD')
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _head_blob_hashes(root, relpaths):
    """HEAD 中各路径 blob 的 sha256；HEAD 里没有的路径不出现在结果中。"""
    relpaths = list(relpaths)
    if not relpaths:
        return {}
    out = _git(root, 'cat-file', '--batch', stdin=''.join(f'HEAD:{rel}\n' for rel in relpaths).encode())
    hashes, cursor = {}, 0
    for rel in relpaths:
        end = out.index(b'\n', cursor)
        header = out[cursor:end].split()
        cursor = end + 1
        if header[-1] == b'missing':
            continue
        size = int(header[2])
        if header[1] == b'blob':
            hashes[rel] = hashlib.sha256(out[cursor:cursor + size]).hexdigest()
        cursor += size + 1
    return hashes


def _head_identity(root):
    return {'commit': _git(root, 'rev-parse', 'HEAD').decode().strip(),
            'branch': _git(root, 'rev-parse', '--abbrev-ref', 'HEAD').decode().strip()}


def build_stamp(root=None):
    """内容只取决于 HEAD，与工作区是否干净无关；是否一致由运行时逐文件比对裁决。"""
    root = Path(root or repo_root())
    names = _git(root, 'ls-tree', '-r', '-z', '--name-only', 'HEAD').decode().split('\0')
    tracked = sorted(name for name in names if name.endswith(STAMP_SUFFIXES))
    return {'schema_version': 1, **_head_identity(root), 'generated_at_utc': _now(),
            'files': _head_blob_hashes(root, tracked)}


def write_stamp(root=None):
    root = Path(root or repo_root())
    stamp = build_stamp(root)
    temporary = root / (STAMP_NAME + '.tmp')
    temporary.write_text(json.dumps(stamp, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, root / STAMP_NAME)
    return stamp


def git_identity(fingerprints, root=None):
    """只记录、不拒绝。fingerprints 为 file_fingerprint 列表（绝对路径 + 实际 sha256）。"""
    root = Path(root or repo_root()).resolve()
    actual, external = {}, []
    for item in fingerprints:
        path = Path(item['path'])
        try:
            actual[path.relative_to(root).as_posix()] = item['sha256']
        except ValueError:
            # 仓库外的输入无法由 checkout 还原；只留文件名与内容指纹，不落绝对路径。
            external.append({'name': path.name, 'sha256': item['sha256']})
    identity, expected = {'source': 'none', 'commit': None, 'branch': None}, {}
    if _has_git(root):
        identity.update(source='git', **_head_identity(root))
        expected = _head_blob_hashes(root, sorted(actual))
    elif (root / STAMP_NAME).is_file():
        stamp = json.loads((root / STAMP_NAME).read_text(encoding='utf-8'))
        identity.update(source='stamp', commit=stamp['commit'], branch=stamp.get('branch'),
                        stamp_generated_at_utc=stamp.get('generated_at_utc'))
        expected = stamp.get('files', {})
    dirty_files = sorted(rel for rel, sha in actual.items() if expected.get(rel) != sha)
    identity.update(dirty=bool(dirty_files) or identity['commit'] is None,
                    dirty_files=dirty_files, external=external)
    return identity


def allow_dirty_requested(flag=False):
    return bool(flag) or os.environ.get(ALLOW_DIRTY_ENV, '').strip().lower() in {'1', 'true', 'yes'}


def _refusal_message(identity):
    escape = '调试可加 --allow-dirty（或环境变量 ' + ALLOW_DIRTY_ENV + '=1）；该结果不得进论文。'
    if identity['source'] == 'none':
        return ('拿不到 git 身份：此目录没有 .git，也没有 ' + STAMP_NAME + '。请在有 .git 的机器上提交后运行 '
                '`python3 scripts/git_stamp.py`，再把代码连同 ' + STAMP_NAME + ' 一起同步过来。' + escape)
    shown = identity['dirty_files'][:10]
    rest = len(identity['dirty_files']) - len(shown)
    listing = '\n  '.join(shown) + (f'\n  …另有 {rest} 个' if rest > 0 else '')
    fix = ('请先 git commit 这些文件。' if identity['source'] == 'git' else
           '请在有 .git 的机器上提交，重新运行 `python3 scripts/git_stamp.py` 后再同步代码。')
    return (f"源码与 commit {identity['commit'][:12]} 不一致（{len(identity['dirty_files'])} 个文件），拒绝运行：\n"
            f'  {listing}\n{fix}{escape}')


def require_git_identity(fingerprints, *, allow_dirty=False, root=None):
    """入口最前面调用，先于任何副作用。dirty 且未放行即抛错；放行则在身份里留下 allow_dirty 标记。"""
    identity = git_identity(fingerprints, root=root)
    identity['allow_dirty'] = False
    if identity['dirty']:
        if not allow_dirty_requested(allow_dirty):
            raise DirtyWorktreeError(_refusal_message(identity))
        identity['allow_dirty'] = True
    return identity


def new_run_id(identity):
    commit = identity.get('commit')
    label = (commit[:7] if commit else 'nogit') + ('-dirty' if identity.get('dirty') else '')
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{label}-{uuid.uuid4().hex[:8]}"


# ---- 账本：每个 run 目录是信源，results.tsv 只是可重建的索引 ----

def ledger_path(root=None):
    explicit = os.environ.get(LEDGER_ENV)
    return Path(explicit).expanduser().resolve() if explicit else Path(root or repo_root()) / LEDGER_NAME


def _relative(path, root):
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def ledger_row(run_dir, root=None):
    """一行账本只从 run 目录内的文件生成，因此账本丢失或分叉后可以重建。"""
    run_dir = Path(run_dir).resolve()
    root = Path(root or repo_root()).resolve()

    def load(name):
        path = run_dir / name
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

    git, resolved = load('git.json'), load('resolved_config.yaml')
    completion, crash = load('audit/completion.json'), load('audit/crash.json')
    runtime = resolved.get('runtime') or {}
    config = runtime.get('config')
    if config:
        config = _relative(config, root) + (f"#{runtime['preset']}" if runtime.get('preset') else '')
    cancer = runtime.get('cancer_types')
    if cancer in (None, '', 'None'):
        cancer = runtime.get('cancer_type')
    # split 列就在标签文件里，标签文件内容指纹即数据划分指纹。
    label = next((item for item in resolved.get('inputs') or [] if str(item.get('path', '')).endswith('.csv')), None)
    note = ' | '.join(text for text in (runtime.get('note'), crash.get('error')) if text)
    return {
        'time_utc': completion.get('finished_at_utc') or crash.get('crashed_at_utc') or git.get('recorded_at_utc'),
        'commit': git.get('commit'), 'dirty': int(bool(git.get('dirty'))) if git else None,
        'branch': git.get('branch'), 'status': 'done' if completion else 'crash' if crash else 'pending',
        'config': config, 'seed': runtime.get('seed'), 'cancer': None if cancer == 'None' else cancer,
        'metrics': completion.get('metrics') or {}, 'split_id': label['sha256'][:12] if label else None,
        'run_dir': _relative(run_dir, root), 'note': note,
    }


def _cell(value):
    if value is None:
        return ''
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return ' '.join(text.split())  # 制表符与换行会破坏 TSV


def _format(row):
    return '\t'.join(_cell(row.get(column)) for column in LEDGER_COLUMNS) + '\n'


def append_ledger(row, path=None):
    path = Path(path or ledger_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        try:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # 不支持锁的文件系统：万一并发交错，由 rebuild_ledger 修复
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write('\t'.join(LEDGER_COLUMNS) + '\n')
        handle.write(_format(row))


def read_ledger(path):
    rows = []
    path = Path(path)
    if not path.is_file():
        return rows
    lines = path.read_text(encoding='utf-8').splitlines()
    header = lines[0].split('\t') if lines else []
    for line in lines[1:]:
        cells = line.split('\t')
        if cells == header or len(cells) != len(header):
            continue  # 重复表头或交错写坏的行
        rows.append(dict(zip(header, cells)))
    return rows


def rebuild_ledger(scan_roots=None, *, merge=(), path=None, root=None):
    """重扫 run 目录并与已有账本合并：按 run_dir 去重、扫描结果优先；扫不到的旧行原样保留。"""
    root = Path(root or repo_root()).resolve()
    path = Path(path or ledger_path(root))
    rows = {}
    for source in [path, *merge]:
        for row in read_ledger(source):
            rows[row.get('run_dir', '')] = {column: row.get(column, '') for column in LEDGER_COLUMNS}
    scanned = 0
    for scan_root in scan_roots or [root / 'experiments']:
        for marker in sorted(Path(scan_root).rglob('git.json')):
            if (marker.parent / 'resolved_config.yaml').is_file():
                row = ledger_row(marker.parent, root)
                rows[_cell(row['run_dir'])] = {column: _cell(row.get(column)) for column in LEDGER_COLUMNS}
                scanned += 1
    ordered = sorted(rows.values(), key=lambda row: (row['time_utc'], row['run_dir']))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text('\t'.join(LEDGER_COLUMNS) + '\n' + ''.join(_format(row) for row in ordered), encoding='utf-8')
    os.replace(temporary, path)
    return {'rows': len(ordered), 'scanned': scanned, 'path': str(path)}


# ---- 失败的运行也进账本 ----

_WATCHED, _LAST_ERROR, _HOOKED = {}, {}, []


def watch_run(run_dir):
    """登记未完成的 run；进程退出时仍未完成的记为 crash。SIGKILL 等硬杀不经过这里，由 rebuild_ledger 标 pending。"""
    if not _HOOKED:
        _HOOKED.append(True)
        atexit.register(_record_unfinished)
        previous = sys.excepthook

        def hook(kind, value, trace):
            _LAST_ERROR['text'] = f'{kind.__name__}: {value}'
            previous(kind, value, trace)
        sys.excepthook = hook
    # 账本位置在启动时定格，退出阶段环境变量可能已被还原；pid 防止 fork 出的子进程（DataLoader worker）代为记账。
    _WATCHED[str(run_dir)] = (str(ledger_path()), os.getpid())


def unwatch_run(run_dir):
    return _WATCHED.pop(str(run_dir), (None, None))[0]


def record_crash(run_dir, error, ledger=None):
    target = Path(run_dir)
    with (target / 'audit' / 'crash.json').open('x', encoding='utf-8') as handle:
        json.dump({'status': 'crash', 'error': str(error)[:300], 'crashed_at_utc': _now()}, handle,
                  ensure_ascii=False, indent=2, sort_keys=True)
        handle.write('\n')
    append_ledger(ledger_row(target), path=ledger)


def _record_unfinished():
    for run_dir in list(_WATCHED):
        ledger, owner = _WATCHED.pop(run_dir)
        audit = Path(run_dir) / 'audit'
        if owner != os.getpid() or not audit.is_dir() or (audit / 'completion.json').exists() \
                or (audit / 'crash.json').exists():
            continue
        try:
            record_crash(run_dir, _LAST_ERROR.get('text') or '进程退出时运行尚未完成', ledger=ledger)
        except Exception:
            pass  # 退出阶段不得再抛错；漏记的 run 由 rebuild_ledger 补上
