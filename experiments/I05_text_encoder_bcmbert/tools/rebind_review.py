"""审查记录 H→S 换绑（Codex 首审 finding 1）：在有 .git 的机器上证明 tree(H) == tree(S)。

Git 工作流是「候选 H 上审查、冒烟 → squash 得 S → 从 S 冻结跑正式实验」。审查记录的 commit 是 H，
正式 test 的冻结 commit 是 S；两者 commit 不同、tree 相同（gitflow.sh squash 校验过）。本工具用 git
重算两者的 tree，相等才写出换绑记录，并用 sha256 绑定原审查记录；evaluate.py 的 test 门核对它，
用户授权记录还要引用它的 sha256（服务器上没有 .git，不能重算 tree）。

用法:
python3 experiments/I05_text_encoder_bcmbert/tools/rebind_review.py build \\
    --review-record <review.json> --commit <S> --out <rebind.json>
python3 experiments/I05_text_encoder_bcmbert/tools/rebind_review.py verify \\
    --review-record <review.json> --rebind-record <rebind.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
KIND = 'review_rebind'
MAIN = 'main'


def _git(repo, *args) -> str:
    return subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, text=True).stdout.strip()


def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _commit(repo, ref) -> str:
    return _git(repo, 'rev-parse', '--verify', f'{ref}^{{commit}}')


def _tree(repo, commit) -> str:
    return _git(repo, 'rev-parse', '--verify', f'{commit}^{{tree}}')


def build_rebind(review_record, commit, *, repo=REPO_ROOT, main=MAIN) -> dict:
    review = json.loads(Path(review_record).read_text(encoding='utf-8'))
    review_commit = _commit(repo, review['commit'])
    if review_commit != review['commit']:
        raise ValueError('审查记录的 commit 必须是完整的 40 位 sha')
    target = _commit(repo, commit)
    if review_commit == target:
        raise ValueError('审查记录已绑定该 commit，不需要换绑')
    if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', target, main]).returncode != 0:
        raise ValueError(f'冻结 commit {target[:12]} 不在 {main} 上')
    review_tree, commit_tree = _tree(repo, review_commit), _tree(repo, target)
    if review_tree != commit_tree:
        raise ValueError(f'tree 不同（{review_tree[:12]} != {commit_tree[:12]}）：S 不是 H 的原样 squash，需在 S 上重审')
    return {'kind': KIND, 'review_record_sha256': _sha256(review_record), 'review_commit': review_commit,
            'commit': target, 'review_tree': review_tree, 'commit_tree': commit_tree,
            'created_at_utc': datetime.now(timezone.utc).isoformat()}


def verify_rebind(review_record, rebind_record, *, repo=REPO_ROOT, main=MAIN) -> dict:
    """用 git 重算一份已有换绑记录；任一字段不符即抛错。"""
    record = json.loads(Path(rebind_record).read_text(encoding='utf-8'))
    fresh = build_rebind(review_record, record['commit'], repo=repo, main=main)
    mismatched = sorted(key for key in fresh if key != 'created_at_utc' and record.get(key) != fresh[key])
    if mismatched:
        raise ValueError(f'换绑记录与 git 重算结果不符: {mismatched}')
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--review-record', type=Path, required=True)
    build.add_argument('--commit', required=True, help='冻结 commit S（main 上）')
    build.add_argument('--out', type=Path, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--review-record', type=Path, required=True)
    verify.add_argument('--rebind-record', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'build':
        record = build_rebind(args.review_record, args.commit)
        with args.out.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
    else:
        record = verify_rebind(args.review_record, args.rebind_record)
    print(json.dumps({'ok': True, 'review_commit': record['review_commit'], 'commit': record['commit'],
                      'tree': record['commit_tree']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
