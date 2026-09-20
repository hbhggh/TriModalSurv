"""完整副本与逐文件校验；只向独占备份目录写入，不修改来源。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path('/Users/wuhao/Desktop/TriModalSurv')
BATCH = ROOT / 'docs/refactor/20260916-080006-full-project'
BACKUP = Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
SOURCES = {
    'root': ROOT,
    '774f': Path('/Users/wuhao/.codex/worktrees/774f/TriModalSurv'),
    '684e': Path('/Users/wuhao/.codex/worktrees/684e/TriModalSurv'),
    '2af8': Path('/Users/wuhao/.codex/worktrees/2af8/TriModalSurv'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def git_state(path):
    commands = {
        'head': ['rev-parse', 'HEAD'], 'branch': ['branch', '--show-current'],
        'status': ['status', '--porcelain=v1', '-uall'],
        'refs': ['show-ref'], 'stashes': ['stash', 'list'],
        'staged': ['diff', '--cached', '--binary'],
        'unstaged': ['diff', '--binary'],
    }
    out = {}
    for name, command in commands.items():
        p = subprocess.run(['git', '-c', 'core.quotePath=false', '-C', str(path), *command],
                           capture_output=True, check=False)
        if p.returncode not in (0, 1):
            raise RuntimeError((path, name, p.stderr.decode(errors='replace')))
        out[name] = p.stdout.decode(errors='replace')
    return out


def main():
    BACKUP.mkdir(parents=True, exist_ok=False)
    repos = {'root': ROOT, 'NPJ': ROOT / 'NPJ', 'MCAT': ROOT / 'baselines/MCAT',
             'PORPOISE': ROOT / 'baselines/PORPOISE', **{k: v for k, v in SOURCES.items() if k != 'root'},
             'dbad': Path('/Users/wuhao/.codex/worktrees/dbad/TriModalSurv')}
    states = {key: git_state(path) for key, path in repos.items()}
    (BACKUP / 'git-state.json').write_text(json.dumps(states, ensure_ascii=False, indent=2))
    # 两个历史工作树只在内容确实相同时共用备份。
    assert states['2af8']['head'] == states['dbad']['head']
    assert not states['2af8']['status'] and not states['dbad']['status']
    total = 0
    sizes = 0
    with (BACKUP / 'files.jsonl').open('x') as manifest:
        for source_id, source in SOURCES.items():
            target = BACKUP / source_id
            target.mkdir()
            for directory, dirs, files in os.walk(source, followlinks=False):
                base = Path(directory)
                rel_dir = base.relative_to(source)
                (target / rel_dir).mkdir(exist_ok=True)
                for name in list(dirs):
                    p = base / name
                    if p.is_symlink():
                        files.append(name)
                        dirs.remove(name)
                for name in files:
                    p = base / name
                    rel = p.relative_to(source)
                    dst = target / rel
                    stat = p.lstat()
                    row = {'source_id': source_id, 'path': str(rel), 'size': stat.st_size,
                           'mtime_ns': stat.st_mtime_ns, 'mode': stat.st_mode}
                    if p.is_symlink():
                        link = os.readlink(p)
                        dst.symlink_to(link)
                        row.update(type='symlink', target=link)
                    elif p.is_file():
                        shutil.copy2(p, dst, follow_symlinks=False)
                        source_hash, copied_hash = digest(p), digest(dst)
                        assert source_hash == copied_hash, str(p)
                        assert p.stat().st_size == stat.st_size, str(p)
                        row.update(type='file', sha256=copied_hash)
                        sizes += stat.st_size
                    else:
                        raise RuntimeError(f'未知文件类型，停止保全：{p}')
                    manifest.write(json.dumps(row, ensure_ascii=False) + '\n')
                    total += 1
                    if total % 4000 == 0:
                        print(f'已逐文件复制校验 {total} 项', flush=True)
            print(f'来源 {source_id} 已保全', flush=True)
    summary = {'status': 'verified', 'backup': str(BACKUP), 'entries': total,
               'bytes': sizes, 'completed_at': datetime.datetime.now().astimezone().isoformat(),
               'aliases': {'dbad': '2af8 (same clean HEAD)'},
               'manifest_sha256': digest(BACKUP / 'files.jsonl')}
    (BACKUP / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    with (BATCH / 'safeguard.json').open('x') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
