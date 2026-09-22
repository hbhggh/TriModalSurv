"""把代码同步到没有 .git 的训练服务器之前生成 GIT_STAMP.json；--rebuild-ledger 重建或合并 results.tsv。"""
from pathlib import Path
import argparse
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from trimodalsurv import gitstamp
from trimodalsurv.config import runtime_source_fingerprints


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild-ledger', action='store_true', help='重扫 run 目录并与现有账本合并；不丢已有行')
    parser.add_argument('--merge', nargs='*', default=[], help='一并合并的其他账本，如从服务器拷回的 results.tsv')
    parser.add_argument('--scan', nargs='*', default=None, help='扫描根目录；默认 experiments/')
    args = parser.parse_args(argv)
    if args.rebuild_ledger:
        summary = gitstamp.rebuild_ledger(args.scan, merge=args.merge)
        print(f"账本 {summary['path']}：共 {summary['rows']} 行，本次扫描到 {summary['scanned']} 个 run 目录")
        return 0
    stamp = gitstamp.write_stamp(PROJECT_ROOT)
    print(f"已写 {gitstamp.STAMP_NAME}：commit {stamp['commit'][:12]}（{stamp['branch']}），{len(stamp['files'])} 个源码文件")
    # stamp 只描述 HEAD；这里提前告知服务器端会看到的拒跑原因。
    dirty = gitstamp.git_identity(runtime_source_fingerprints(argparse.Namespace()), root=PROJECT_ROOT)['dirty_files']
    if dirty:
        print(f"注意：{len(dirty)} 个源码文件尚未提交，原样同步到服务器会被拒跑：\n  " + '\n  '.join(dirty[:10]), file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
