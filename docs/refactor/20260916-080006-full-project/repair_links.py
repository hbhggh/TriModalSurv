"""只改 Markdown/HTML 链接目标；逐跨度日志可证明正文保持。"""
from pathlib import Path
import json,os,re,hashlib,urllib.parse,sys
DRY = "--dry-run" in sys.argv
preview_documents = {}
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
moves=json.loads((B/'cutover-plan.json').read_text());assets=json.loads((B/'assets-map.json').read_text())['entries']
mapping={};source_docs={}
for e in assets:
 if e['execute_copy'] and not e['target'].startswith('archive/'):
  source_id=e['source_id'];p=e['source_path']
  old=(ROOT/p if source_id=='root' else Path('/Users/wuhao/.codex/worktrees')/source_id/'TriModalSurv'/p)
  mapping[str(old)]=str(ROOT/e['target'])
  target=ROOT/e['target']
  if target.suffix=='.md' and ('/knowledge/' in str(target) or e['target'].startswith(('docs/workflow/','docs/metrics/','docs/research-ideas/'))):source_docs[str(target)]=old
# 没有使用副本的来源指向完整归档。
def dest(path):
 s=str(path)
 if s in mapping:return Path(mapping[s])
 for e in moves:
  src=ROOT/e['source']
  if path==src or path.is_relative_to(src):return ROOT/e['target']/path.relative_to(src)
 return path
for p in [ROOT/'STATUS.md',* (ROOT/'experiments/I01_patient_retrieval').glob('*.md'),* (ROOT/'experiments/I01_patient_retrieval/knowledge').glob('*.md')]:source_docs[str(p)]=p
pattern=re.compile(r'(?P<md>!?\[[^\]\n]*\]\()(?P<target><[^>\n]*>|[^)\n]+)(?P<end>\))|(?P<html>\b(?:href|src)=[\"\x27])(?P<url>[^\"\x27]*)(?P<quote>[\"\x27])')
changes=[]
for name,old_file in source_docs.items():
 p=Path(name)
 if not p.exists():continue
 before=p.read_text();segments=[];offset=0;fence=False
 for line in before.splitlines(keepends=True):
  if line.lstrip().startswith(('```','~~~')):fence=not fence
  if not fence:
   for m in pattern.finditer(line):
    group='target' if m.group('md') else 'url';raw=m.group(group);bracket=raw.startswith('<') and raw.endswith('>');u=raw[1:-1] if bracket else raw
    if u.startswith(('#','http:','https:','mailto:','data:')):continue
    scheme=''
    if u.startswith('vscode://file/'):scheme='vscode://file';u=u[len(scheme):]
    elif u.startswith('file://'):scheme='file://';u=u[len(scheme):]
    elif '://' in u:continue
    u=urllib.parse.unquote(u);fragment=''
    if '#' in u:u,fragment=u.split('#',1);fragment='#'+fragment
    ln='';hit=re.search(r':\d+(?::\d+)?$',u)
    if hit:ln=hit.group();u=u[:hit.start()]
    if not u:continue
    old=Path(u) if u.startswith('/') else old_file.parent/u
    old=Path(os.path.normpath(old));new=dest(old)
    value=(scheme+str(new) if scheme else str(new) if raw.lstrip('<').startswith('/') else os.path.relpath(new,p.parent))+ln+fragment
    if bracket:value='<'+value+'>'
    # 新增空格路径用<>，保持目标可解析；不改label或正文。
    elif m.group('md') and ' ' in value:value='<'+value+'>'
    if value!=raw:segments.append((offset+m.start(group),offset+m.end(group),raw,value))
  offset+=len(line)
 after=before
 for start,end,old,new in reversed(segments):assert after[start:end]==old;after=after[:start]+new+after[end:]
 if segments:
  if not DRY:p.write_text(after)
  preview_documents[str(p.relative_to(ROOT))] = after
  changes.append({'file':str(p.relative_to(ROOT)),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'changes':[{'start':s,'end':e,'old':o,'new':n} for s,e,o,n in segments]})
(B/('link-changes.preview.json' if DRY else 'link-changes.json')).write_text(json.dumps(changes,ensure_ascii=False,indent=2))
print('documents',len(changes),'link changes',sum(len(x['changes']) for x in changes))

if DRY:(B/'preview-documents.json').write_text(json.dumps(preview_documents,ensure_ascii=False))
