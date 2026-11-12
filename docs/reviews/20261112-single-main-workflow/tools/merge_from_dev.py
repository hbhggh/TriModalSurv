#!/usr/bin/env python3
"""Step 2 / 3 / 7：把 dev 工作树里的未提交改动、未跟踪文件与被忽略的重资产无损并回主目录，并逐文件 sha256 核验。

用法:
  merge_from_dev.py merge  --main <主目录> --dev <dev工作树> --out <记录目录> [--apply]
                           [--main-wins <relpath>...] [--handled <relpath>=<dev版sha256>...]
  merge_from_dev.py verify --main <主目录> --dev <dev工作树> --out <记录目录>
                           [--allow-diff <relpath>...]

merge（不带 --apply 只演练）：先把 dev 的每个文件分类，出现任何「冲突」就一个文件都不拷，退出码 1。
  dev 已修改的跟踪文件   -> 拷入主目录；要求主目录该文件此刻等于 HEAD 或已等于 dev 版，否则算冲突
  dev 已删除的跟踪文件   -> 只报告（由操作者 git rm），主目录仍存在且不是已删除状态时提示
  dev 未跟踪 / 被忽略文件 -> 主目录没有则拷入；内容相同跳过；内容不同时只有 D_WINS 前缀下的文件覆盖，其余算冲突
  --main-wins 的路径      -> 主目录版胜出，不拷
  --handled 的路径        -> 已另行处理（如 AGENTS.md 已拷入并被改写）：只核对 dev 版 sha256 仍等于登记值
  排除 .DS_Store 与 __pycache__/；符号链接不跟随，出现即算冲突。
verify：重新枚举 dev 的全部上述文件，要求主目录同路径存在且 sha256 相同；--allow-diff 的路径单列。
  缺失数与不一致数必须为 0，否则退出码 1。两个子命令都把清单写进 --out。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

# 契约 1.2 / 1.3：这些路径双端都有且内容不同时，以 dev 的新版为准
D_WINS = ('manuscript/bmc_initial_draft/figures/', 'manuscript/bmc_initial_draft/tables/',
          'manuscript/bmc_initial_draft/main.log', 'manuscript/bmc_initial_draft/main.synctex.gz')


def git(repo, *args):
    result = subprocess.run(['git', '-c', 'core.quotePath=false', '-C', repo, *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise SystemExit('git %s 失败: %s' % (' '.join(args), result.stderr.decode('utf-8', 'replace')))
    return result.stdout.decode('utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def skipped(rel):
    parts = rel.split('/')
    return parts[-1] == '.DS_Store' or '__pycache__' in parts[:-1]


def enumerate_dev(dev):
    """返回 [(kind, relpath)]，kind ∈ modified / deleted / untracked / ignored。"""
    entries, parts, index = [], git(dev, 'status', '--porcelain', '-z', '--untracked-files=all').split('\0'), 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        code, rel = item[:2], item[3:]
        if code[0] in 'RC':
            raise SystemExit('dev 工作树里有改名 / 复制条目，脚本不处理: %r' % item)
        if code == '??':
            kind = 'untracked'
        elif 'D' in code:
            kind = 'deleted'
        else:
            kind = 'modified'
        entries.append((kind, rel))
    for rel in git(dev, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').split('\0'):
        if rel:
            if rel.endswith('/'):
                raise SystemExit('ls-files 输出了目录项，须逐文件展开: %r' % rel)
            entries.append(('ignored', rel))
    return [(kind, rel) for kind, rel in entries if not skipped(rel)]


def classify(main, dev, entries, main_wins, handled):
    rows = []
    for kind, rel in entries:
        src, dst = os.path.join(dev, rel), os.path.join(main, rel)
        row = {'kind': kind, 'path': rel}
        if kind == 'deleted':
            row['action'] = 'report-deleted'
            row['main_state'] = 'absent' if not os.path.lexists(dst) else 'present'
            rows.append(row)
            continue
        if os.path.islink(src) or not os.path.isfile(src):
            row['action'] = 'conflict'
            row['why'] = 'dev 侧是符号链接或不是普通文件'
            rows.append(row)
            continue
        row['dev_sha256'], row['size'] = sha256(src), os.path.getsize(src)
        if rel in handled:
            row['action'] = 'handled' if row['dev_sha256'] == handled[rel] else 'conflict'
            row['why'] = '已另行处理；dev 版 sha256 %s登记值' % ('等于' if row['action'] == 'handled' else '已不等于')
        elif rel in main_wins:
            row['action'] = 'main-wins'
        elif os.path.islink(dst) or (os.path.lexists(dst) and not os.path.isfile(dst)):
            row['action'], row['why'] = 'conflict', '主目录侧是符号链接或不是普通文件'
        elif not os.path.exists(dst):
            row['action'] = 'copy'
        elif sha256(dst) == row['dev_sha256']:
            row['action'] = 'same'
        elif kind == 'modified':
            clean = subprocess.run(['git', '-C', main, 'diff', '--quiet', 'HEAD', '--', rel]).returncode == 0
            row['action'] = 'overwrite' if clean else 'conflict'
            row['why'] = '主目录该文件等于 HEAD' if clean else '主目录该文件另有未提交改动'
        elif any(rel == p or (p.endswith('/') and rel.startswith(p)) for p in D_WINS):
            row['action'], row['why'] = 'overwrite', '契约裁决：dev 新版覆盖'
        else:
            row['action'], row['why'] = 'conflict', '双端内容不同且无裁决'
        rows.append(row)
    return rows


def write_record(out, name, payload):
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, time.strftime(name + '-%Y%m%d-%H%M%S.json'))
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    return path


def summarize(rows, key):
    counts = {}
    for row in rows:
        counts[(row['kind'], row[key])] = counts.get((row['kind'], row[key]), 0) + 1
    for (kind, value), count in sorted(counts.items()):
        print('  %-10s %-15s %d' % (kind, value, count))


def cmd_merge(args):
    main, dev = os.path.realpath(args.main), os.path.realpath(args.dev)
    handled = dict(item.rsplit('=', 1) for item in args.handled)
    rows = classify(main, dev, enumerate_dev(dev), set(args.main_wins), handled)
    summarize(rows, 'action')
    conflicts = [row for row in rows if row['action'] == 'conflict']
    for row in conflicts:
        print('  CONFLICT %s  (%s)' % (row['path'], row.get('why', '')))
    for row in rows:
        if row['action'] in ('overwrite', 'main-wins', 'handled', 'report-deleted'):
            print('  %-14s %s  %s' % (row['action'], row['path'], row.get('why', row.get('main_state', ''))))
    if conflicts:
        print('MERGE: 有 %d 个冲突，未拷贝任何文件' % len(conflicts))
        write_record(args.out, 'merge-conflict', rows)
        return 1
    if not args.apply:
        print('MERGE: 演练结束（未加 --apply，未拷贝）')
        return 0
    bad = []
    for row in rows:
        if row['action'] in ('copy', 'overwrite'):
            src, dst = os.path.join(dev, row['path']), os.path.join(main, row['path'])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            if sha256(dst) != row['dev_sha256']:
                bad.append(row['path'])
    record = write_record(args.out, 'merge-applied', rows)
    done = sum(row['action'] in ('copy', 'overwrite') for row in rows)
    print('MERGE: 已拷贝 %d 个文件，拷后 sha256 不一致 %d；清单 %s' % (done, len(bad), record))
    return 1 if bad else 0


def cmd_verify(args):
    main, dev = os.path.realpath(args.main), os.path.realpath(args.dev)
    allow, rows, counts = set(args.allow_diff), [], {'identical': 0, 'allowed-diff': 0, 'missing': 0, 'mismatch': 0,
                                                     'deleted-both': 0, 'deleted-dev-only': 0}
    by_kind = {}
    for kind, rel in enumerate_dev(dev):
        src, dst = os.path.join(dev, rel), os.path.join(main, rel)
        row = {'kind': kind, 'path': rel}
        if kind == 'deleted':
            row['result'] = 'deleted-both' if not os.path.lexists(dst) else 'deleted-dev-only'
        else:
            row['dev_sha256'] = sha256(src)
            if not os.path.isfile(dst) or os.path.islink(dst):
                row['result'] = 'missing'
            else:
                row['main_sha256'] = sha256(dst)
                if row['main_sha256'] == row['dev_sha256']:
                    row['result'] = 'identical'
                else:
                    row['result'] = 'allowed-diff' if rel in allow else 'mismatch'
        counts[row['result']] += 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
        rows.append(row)
    record = write_record(args.out, 'verify', rows)
    print('VERIFY: dev 文件 %d 个（%s）' % (len(rows), '，'.join('%s %d' % item for item in sorted(by_kind.items()))))
    for name in ('identical', 'allowed-diff', 'deleted-both', 'deleted-dev-only', 'missing', 'mismatch'):
        print('  %-17s %d' % (name, counts[name]))
    for row in rows:
        if row['result'] in ('allowed-diff', 'missing', 'mismatch', 'deleted-dev-only'):
            print('  %-17s %s' % (row['result'], row['path']))
    print('  清单 %s' % record)
    failed = counts['missing'] + counts['mismatch'] + counts['deleted-dev-only']
    print('VERIFY: %s（缺失 %d，不一致 %d）' % ('FAIL' if failed else 'PASS', counts['missing'], counts['mismatch']))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('merge', 'verify'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--main', required=True)
        cmd.add_argument('--dev', required=True)
        cmd.add_argument('--out', required=True)
    sub.choices['merge'].add_argument('--apply', action='store_true')
    sub.choices['merge'].add_argument('--main-wins', nargs='*', default=[])
    sub.choices['merge'].add_argument('--handled', nargs='*', default=[])
    sub.choices['verify'].add_argument('--allow-diff', nargs='*', default=[])
    args = parser.parse_args()
    return cmd_merge(args) if args.command == 'merge' else cmd_verify(args)


if __name__ == '__main__':
    sys.exit(main())
