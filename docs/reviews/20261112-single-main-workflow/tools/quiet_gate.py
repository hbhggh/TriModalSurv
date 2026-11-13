#!/usr/bin/env python3
"""静默硬门：归并（门 A）与退役（门 B）前确认 dev 工作树没有活跃写入者。只读，不改任何文件。

用法:
  quiet_gate.py --main <主目录> --dev <dev工作树> --expect-dev-head <sha> --mode A|B
                [--window-min 10] [--newer-than <清单文件>] [--exclude <主目录内相对路径>...]

判据（任一不满足即退出码 1，逐条打印证据；不重试）:
  1. 没有进程的工作目录在 dev 工作树下（门 B 同时查 <主目录>/.claude/worktrees）。
  2. dev 分支 HEAD 等于 --expect-dev-head，且 main 与 dev 没有分叉。
  3. dev 工作树在最近 window 分钟内没有文件改动；门 A 同时查主目录（排除 .git、.jj、
     .claude/worktrees 与 --exclude）。门 B 给 --newer-than 时，dev 中不得有 mtime 晚于该清单的文件。
"""
import argparse
import os
import subprocess
import sys
import time

SKIP_NAMES = {'.DS_Store'}
SKIP_DIRS = {'.git', '__pycache__'}


def git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding='utf-8', errors='replace')


def cwd_holders(prefixes):
    out = subprocess.run(['lsof', '-a', '-d', 'cwd', '-Fpcn'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         encoding='utf-8', errors='replace').stdout
    holders, pid, cmd = [], None, None
    for line in out.splitlines():
        if line.startswith('p'):
            pid, cmd = line[1:], None
        elif line.startswith('c'):
            cmd = line[1:]
        elif line.startswith('n'):
            path = line[1:]
            if any(path == p or path.startswith(p + os.sep) for p in prefixes) and pid != str(os.getpid()):
                holders.append((pid, cmd or '?', path))
    return holders


def recent_files(root, cutoff, skip_rel=()):
    hits = []
    skip_rel = tuple(s.rstrip('/') for s in skip_rel)
    for base, dirs, files in os.walk(root):
        rel_base = os.path.relpath(base, root)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not any(os.path.normpath(os.path.join(rel_base, d)) == s for s in skip_rel)]
        for name in files:
            if name in SKIP_NAMES:
                continue
            full = os.path.join(base, name)
            try:
                mtime = os.lstat(full).st_mtime
            except OSError:
                continue
            if mtime > cutoff:
                hits.append((mtime, os.path.relpath(full, root)))
    return sorted(hits, reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--main', required=True)
    parser.add_argument('--dev', required=True)
    parser.add_argument('--expect-dev-head', required=True)
    parser.add_argument('--mode', choices=('A', 'B'), required=True)
    parser.add_argument('--window-min', type=float, default=10)
    parser.add_argument('--newer-than')
    parser.add_argument('--exclude', nargs='*', default=[])
    args = parser.parse_args()
    main_dir, dev_dir = os.path.realpath(args.main), os.path.realpath(args.dev)
    failures = []
    print(time.strftime('gate %s @ %%Y-%%m-%%d %%H:%%M:%%S %%Z' % args.mode))

    prefixes = [dev_dir] + ([os.path.join(main_dir, '.claude', 'worktrees')] if args.mode == 'B' else [])
    holders = cwd_holders(prefixes)
    print('[1] 工作目录在待退役目录下的进程: %d' % len(holders))
    by_cmd = {}
    for pid, cmd, path in holders:
        by_cmd.setdefault((cmd, path), []).append(pid)
    for (cmd, path), pids in sorted(by_cmd.items()):
        print('    %-12s x%-2d %s  pids=%s' % (cmd, len(pids), path, ','.join(pids)))
    if holders:
        failures.append('仍有进程的工作目录在待退役目录下')

    head = git(main_dir, 'rev-parse', '-q', '--verify', 'refs/heads/dev^{commit}').stdout.strip()
    expect = git(main_dir, 'rev-parse', '-q', '--verify', args.expect_dev_head + '^{commit}').stdout.strip()
    counts = git(main_dir, 'rev-list', '--left-right', '--count', 'main...dev').stdout.split()
    print('[2] dev HEAD = %s（期望 %s）；main...dev = %s' % (head[:12] or '?', expect[:12] or '?', ' '.join(counts)))
    if not head or head != expect:
        failures.append('dev HEAD 与期望不符')
    if len(counts) != 2 or (counts[0] != '0' and counts[1] != '0'):
        failures.append('main 与 dev 已分叉')
    wt_head = git(dev_dir, 'rev-parse', '-q', '--verify', 'HEAD').stdout.strip()
    if wt_head != head:
        failures.append('dev 工作树 HEAD %s 不等于 dev 分支' % wt_head[:12])

    cutoff = time.time() - args.window_min * 60
    dev_recent = recent_files(dev_dir, cutoff)
    print('[3] dev 工作树最近 %g 分钟内改动的文件: %d' % (args.window_min, len(dev_recent)))
    for mtime, rel in dev_recent[:15]:
        print('    %s  %s' % (time.strftime('%H:%M:%S', time.localtime(mtime)), rel))
    if dev_recent:
        failures.append('dev 工作树最近仍有文件改动')
    if args.mode == 'A':
        skip = ['.jj', os.path.join('.claude', 'worktrees')] + list(args.exclude)
        main_recent = recent_files(main_dir, cutoff, skip)
        print('    主目录最近 %g 分钟内改动的文件: %d' % (args.window_min, len(main_recent)))
        for mtime, rel in main_recent[:15]:
            print('    %s  %s' % (time.strftime('%H:%M:%S', time.localtime(mtime)), rel))
        if main_recent:
            failures.append('主目录最近仍有文件改动')
    if args.newer_than:
        stamp = os.stat(args.newer_than).st_mtime
        newer = recent_files(dev_dir, stamp)
        print('    dev 中 mtime 晚于校验清单的文件: %d' % len(newer))
        for mtime, rel in newer[:15]:
            print('    %s  %s' % (time.strftime('%H:%M:%S', time.localtime(mtime)), rel))
        if newer:
            failures.append('dev 中有晚于校验清单的改动，须先增量追平')

    if failures:
        print('GATE %s: FAIL — %s' % (args.mode, '；'.join(failures)))
        return 1
    print('GATE %s: PASS' % args.mode)
    return 0


if __name__ == '__main__':
    sys.exit(main())
