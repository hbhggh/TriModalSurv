"""v2文档重封装：保持v1证据快照；显式记录唯一已知源稿时间差。"""
from pathlib import Path
import json
import subprocess
import sys
import zipfile
from verify_package import sha


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parent
    source = json.loads((evidence / 'source_manifest.json').read_text())
    drift = []
    for entry in source['entries']:
        p = Path(entry['source_path'])
        actual = sha(p)
        if actual == entry['source_sha256']:
            continue
        # 不放宽成任意“忽略来源变化”；仅允许本轮已核实的单一源稿与快照对。
        assert str(p) == '/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.tex'
        assert entry['source_sha256'] == 'f11ea7e0cc333b00b2e4d18f831399de8838413769d859aad58dc169ec10ecf1'
        assert actual == 'db9a395062029cf617f9274b7950162990bc7ed903999fd27c3520a241a715ed'
        snapshot = evidence / 'table1.tex'
        assert sha(snapshot) == '7bdfc45595f19595394315a35ead05248fe808edea818c0b04ebdf3c9573c9fd'
        old_none = next(x for x in snapshot.read_text().splitlines() if x.startswith('None &'))
        current_none = next(x for x in p.read_text().splitlines() if x.startswith('None &'))
        assert old_none == current_none
        drift.append({'path': str(p), 'v1_source_sha256': entry['source_sha256'],
                      'current_source_sha256': actual, 'snapshot_sha256': sha(snapshot),
                      'none_row_unchanged': True, 'policy': '保留v1证据；不复制或修改用户新工作稿'})
    assert len(drift) == 1
    (evidence / 'v2_source_status.json').write_text(json.dumps({
        'version': 'v2', 'previous_commit': '722fb79997c1cd39630c275ba50f07390d56c600',
        'source_entries': len(source['entries']), 'unchanged_source_entries': len(source['entries']) - len(drift),
        'explicit_source_drift': drift, 'new_experiment_run': False}, ensure_ascii=False, indent=2) + '\n')
    files = [root / n for n in ['给ChatGPT-Pro的结构化Prompt.md',
             'Encoder实验先验知识-Pro版.md', 'Pro交接使用说明.md']]
    files += sorted(p for p in evidence.rglob('*') if p.is_file()
                    and p.name != 'package_manifest.json' and '__pycache__' not in p.parts)
    assert not any(p.is_symlink() for p in files)
    manifest = evidence / 'package_manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'handoff_version': 'v2',
        'exclusion': '清单本身、ZIP与发布收据不纳入清单，避免自引用',
        'files': [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size,
                   'sha256': sha(p)} for p in files]}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run([sys.executable, '-B', str(evidence / 'verify_package.py')], check=True)
    zpath = root / 'ChatGPT-Pro交接包.zip'
    with zipfile.ZipFile(zpath, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in files + [manifest]:
            zi = zipfile.ZipInfo(str(p.relative_to(root)), date_time=(2026, 9, 20, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, p.read_bytes())
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        for p in files + [manifest]:
            assert z.read(str(p.relative_to(root))) == p.read_bytes()
    print(json.dumps({'version': 'v2', 'files': len(files)+1, 'zip_sha256': sha(zpath),
                      'unchanged_sources': 25, 'explicit_source_drift': len(drift)},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
