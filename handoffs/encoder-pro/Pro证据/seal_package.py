"""封装白名单文档并验证来源不变；不触碰原实验文件。"""
from pathlib import Path
import json
import subprocess
import sys
import zipfile

from verify_package import sha


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parent
    sources = json.loads((evidence / 'source_manifest.json').read_text())
    for entry in sources['entries']:
        path = Path(entry['source_path'])
        assert sha(path) == entry['source_sha256'], f'来源变化，须核验后重建: {path}'
    names = ['给ChatGPT-Pro的结构化Prompt.md', 'Encoder实验先验知识-Pro版.md', 'Pro交接使用说明.md']
    files = [root / name for name in names]
    files += sorted(p for p in evidence.rglob('*') if p.is_file()
                    and p.name != 'package_manifest.json' and '__pycache__' not in p.parts)
    assert not any(p.is_symlink() for p in files), '拒绝符号链接'
    allowed = {'.md', '.json', '.csv', '.yaml', '.py', '.pdf', '.svg', '.png', '.tex', '.txt'}
    assert all(p.suffix in allowed for p in files)
    manifest_path = evidence / 'package_manifest.json'
    manifest_path.write_text(json.dumps({
        'schema_version': 1,
        'exclusion': '此清单自身不纳入哈希；ZIP/commit收据保存在包外',
        'files': [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size,
                   'sha256': sha(p)} for p in files]}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run([sys.executable, '-B', str(evidence / 'verify_package.py')], check=True)
    zip_path = root / 'ChatGPT-Pro交接包.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in files + [manifest_path]:
            zi = zipfile.ZipInfo(str(p.relative_to(root)), date_time=(2026, 9, 20, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, p.read_bytes())
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        for p in files + [manifest_path]:
            assert z.read(str(p.relative_to(root))) == p.read_bytes()
    print(json.dumps({'zip': str(zip_path), 'sha256': sha(zip_path),
                      'files': len(files) + 1, 'source_files_unchanged': len(sources['entries'])},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
