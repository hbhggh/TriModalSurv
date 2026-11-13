#!/usr/bin/env python3
"""Step 0：双端状态快照 + 主目录将被覆盖 / 还原的文件备份。只读取仓库，只写 --out 目录。可重复运行，每次一个新子目录。

用法: backup_snapshot.py --main <主目录> --dev <dev工作树> --out <备份根目录>

备份内容（落在 <out>/snap-<时间>/）:
  state/      双端 HEAD、status、worktree list、分支与 tag 清单、git diff HEAD 二进制补丁
  main_files/ 主目录全部已修改的跟踪文件，以及未跟踪文件中会被归并触及的部分
              （manuscript/ 下的未跟踪文件、根目录未跟踪的 .md）
  dev_files/  dev 工作树中按裁决不拷入主目录的文件（02_总算子卡槽与候选池.md）
  session_wt/ 会话 worktree 里被忽略的 .claude/settings.local.json
写完后逐文件与来源做字节比较，任何不一致即退出码 1。
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import time


def git(repo, *args, binary=False):
    result = subprocess.run(['git', '-c', 'core.quotePath=false', '-C', repo, *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise SystemExit('git %s 失败: %s' % (' '.join(args), result.stderr.decode('utf-8', 'replace')))
    return result.stdout if binary else result.stdout.decode('utf-8', 'replace')


def status_entries(repo):
    raw = git(repo, 'status', '--porcelain', '-z', '--untracked-files=all', binary=True).decode('utf-8')
    entries, parts, index = [], raw.split('\0'), 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        code, path = item[:2], item[3:]
        if code[0] in 'RC':
            index += 1  # 改名条目多带一个原路径
        entries.append((code, path))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--main', required=True)
    parser.add_argument('--dev', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    main_dir, dev_dir = os.path.realpath(args.main), os.path.realpath(args.dev)
    snap = os.path.join(args.out, time.strftime('snap-%Y%m%d-%H%M%S'))
    os.makedirs(os.path.join(snap, 'state'))

    def save(name, text, binary=False):
        with open(os.path.join(snap, 'state', name), 'wb' if binary else 'w') as handle:
            handle.write(text)

    for label, repo in (('main', main_dir), ('dev', dev_dir)):
        save(label + '.HEAD', git(repo, 'rev-parse', 'HEAD'))
        save(label + '.status.txt', git(repo, 'status', '--porcelain', '--untracked-files=all'))
        save(label + '.diff-HEAD.patch', git(repo, 'diff', '--binary', 'HEAD', binary=True), binary=True)
    save('worktree-list.txt', git(main_dir, 'worktree', 'list', '--porcelain'))
    save('branches.txt', git(main_dir, 'branch', '-a', '-vv', '--no-abbrev'))
    save('tags.txt', git(main_dir, 'tag', '-l', '--format=%(refname:short) %(objectname)'))
    save('left-right.txt', git(main_dir, 'rev-list', '--left-right', '--count', 'main...dev'))

    copied = []

    def keep(src_root, rel, bucket):
        src = os.path.join(src_root, rel)
        if not os.path.isfile(src) or os.path.islink(src):
            return
        dst = os.path.join(snap, bucket, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied.append((src, dst))

    for code, path in status_entries(main_dir):
        if code == '??':
            if path.startswith('manuscript/') or ('/' not in path and path.endswith('.md')):
                keep(main_dir, path, 'main_files')
        elif 'D' not in code:
            keep(main_dir, path, 'main_files')
    keep(dev_dir, '02_总算子卡槽与候选池.md', 'dev_files')
    session_root = os.path.join(main_dir, '.claude', 'worktrees')
    if os.path.isdir(session_root):
        for name in sorted(os.listdir(session_root)):
            keep(session_root, os.path.join(name, '.claude', 'settings.local.json'), 'session_wt')

    bad = [src for src, dst in copied if not filecmp.cmp(src, dst, shallow=False)]
    with open(os.path.join(snap, 'state', 'copied.txt'), 'w') as handle:
        handle.write(''.join('%s\n' % os.path.relpath(dst, snap) for _, dst in copied))
    print('snapshot : %s' % snap)
    print('main HEAD: %s' % git(main_dir, 'rev-parse', 'HEAD').strip())
    print('dev  HEAD: %s' % git(dev_dir, 'rev-parse', 'HEAD').strip())
    print('copied   : %d 个文件；字节比较不一致 %d' % (len(copied), len(bad)))
    for src in bad:
        print('  MISMATCH %s' % src)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
