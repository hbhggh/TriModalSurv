from pathlib import Path
import tarfile,json,hashlib,sys
root=Path.cwd();batch=root/'docs/refactor/20260916-080006-full-project';version=sys.argv[1];rows=[]
with tarfile.open(batch/f'candidate-{version}.tar','x') as t:
 for base in ['src','scripts','tests','configs','experiments']:
  for p in sorted((root/base).rglob('*')):
   if not p.is_file() or '__pycache__' in p.parts:continue
   rel=p.relative_to(root)
   if base=='experiments' and ('results' in rel.parts or 'knowledge' in rel.parts):continue
   if p.suffix not in ['.py','.yaml','.yml','.sh','.toml']:continue
   t.add(p,arcname=str(Path('project')/rel));rows.append({'path':str(rel),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 for p in [root/'pyproject.toml',*batch.glob('*parity*.py'),batch/'compare_real.py']:
  t.add(p,arcname=str(Path('project')/p.relative_to(root)));rows.append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
with (batch/f'candidate-{version}-manifest.json').open('x') as f:json.dump(rows,f,indent=2)
print(version,len(rows))
