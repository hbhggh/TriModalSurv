"""检查活动 Markdown 链接，并把迁移前已失效的引用单列。"""
from pathlib import Path
import json,re,os,urllib.parse
R=Path(__file__).resolve().parents[3];B=Path(__file__).parent
A=json.loads((B/'assets-map.json').read_text())['entries']
source={e['target']:e for e in A if e['execute_copy']}
changes={r['file']:r for r in json.loads((B/'link-changes.json').read_text())}
backup=Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
files=set(R/n for n in ['README.md','STATUS.md','AGENTS.md','CLAUDE.md'])
for base in ['docs/workflow','docs/metrics','docs/research-ideas','docs/templates']:
 files.update((R/base).rglob('*.md'))
files.add(R/'docs/project-structure.md')
for d in (R/'experiments').iterdir():
 if not d.is_dir():continue
 files.update(d.glob('*.md'))
 files.update((d/'knowledge').rglob('*.md'))
 files.update((d/'results').glob('index.md'))
 files.update((d/'results').glob('*/analysis.md'))
files.update((R/'experiments/_comparisons').glob('*/analysis.md'))
def targets(text):
 fence=False
 for line in text.splitlines():
  if line.lstrip().startswith(('```','~~~')):fence=not fence;continue
  if fence:continue
  for m in re.finditer(r'!?\[[^\]\n]*\]\(',line):
   i=m.end();start=i;depth=0;angle=i<len(line) and line[i]=='<'
   if angle:
    end=line.find('>',i+1)
    if end>=0:yield line[i+1:end]
    continue
   while i<len(line):
    if line[i]=='(' :depth+=1
    elif line[i]==')':
     if depth==0:yield line[start:i];break
     depth-=1
    i+=1
  for m in re.finditer(r'\b(?:href|src)=["\x27]([^"\x27]+)["\x27]',line):yield m.group(1)
def location(url,parent):
 url=urllib.parse.unquote(url.strip().strip('<>'))
 if not url or url.startswith(('#','http:','https:','mailto:','data:')):return None
 if url.startswith('vscode://file/'):url=url[len('vscode://file'):]
 elif url.startswith('file://'):url=url[7:]
 elif '://' in url:return None
 url=url.split('#',1)[0];url=re.sub(r':\d+(?::\d+)?$','',url)
 if any(t in url for t in ['<','>','{','}','*']):return None
 p=Path(url);return Path(os.path.normpath(p if p.is_absolute() else parent/p))
checked=[];broken=[];historical=[]
for p in sorted(files):
 if not p.exists():continue
 rel=str(p.relative_to(R));originals={c['new'].strip('<>'):c['old'] for c in changes.get(rel,{}).get('changes',[])}
 for url in targets(p.read_text()):
  q=location(url,p.parent)
  if q is None:continue
  row={'document':rel,'target':url,'resolved':str(q)}
  if q.exists():checked.append(row);continue
  e=source.get(rel);oldurl=originals.get(url,url)
  old_parent=(R/e['source_path']).parent if e and e['source_id']=='root' else (Path('/Users/wuhao/.codex/worktrees')/e['source_id']/'TriModalSurv'/e['source_path']).parent if e else p.parent
  old=location(oldurl,old_parent)
  frozen=None
  if old and old.is_relative_to(R):frozen=backup/'root'/old.relative_to(R)
  elif old and e and e['source_id']!='root':
   w=Path('/Users/wuhao/.codex/worktrees')/e['source_id']/'TriModalSurv'
   if old.is_relative_to(w):frozen=backup/e['source_id']/old.relative_to(w)
  if (e or rel=='STATUS.md') and old and ((frozen and not frozen.exists()) or (not frozen and not old.exists())):
   row['original_target']=str(old);historical.append(row)
  else:broken.append(row)
result={'status':'PASS' if not broken else 'FAIL','documents':len(files),'valid_links':len(checked),'newly_broken':broken,'historical_broken':historical}
(B/'link-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['newly_broken','historical_broken']},ensure_ascii=False));print('newly_broken',len(broken),'historical_broken',len(historical))
for row in broken[:20]:print(row)
raise SystemExit(bool(broken))
