请对已执行的全项目重构做最终资产/文档保护审阅，返回JSON verdict/required_changes/limitations。使用真实Read/Glob/Grep工具可核对本地证据，不执行命令，不改文件，不模拟工具记录。代码必要项已经由claude-code-review-4.json PASS，本次代码94文件仍与candidate-v8 manifest逐项相同；无需重新提出无关科研创新或正式训练。重点审计下附实际操作/验证逻辑及其证据，确认有没有丢资产、越界覆写旧正文、虚报验证。若需要修改要给具体可执行问题。
用户授权：整个项目归位；MCAT/PORPOISE原位独立；旧MD/SVG原文保全，使用版仅改链接；根README允许重写；STATUS这次仅修链接再尾追加，后续只追加；AGENTS/CLAUDE只替换路径；本批progress.md是持续更新的任务控制文档，不是用户旧知识。原件完整T0备份在/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006，分母21614不可缩。任何旧资料/code不可逆删除禁止；20项同文件系统rename归档，有planned/done/verified及回滚演练。没有训练真实患者、GPU、依赖安装、缓存重建、远端部署或push。
切换后资产审计已实跑：21614原件全SHA，5820使用副本SHA，2674未移动旧知识/附件/结果的内容核验，STATUS三段证明；old SVG无改。142文件链接/47文档PASS。模型数值旧新16真实格和7合成路径最大差0；25权重严格加载；v8 186通过6旧skip。切换后22CLI成功+跨cwd解析相等，本机launcher预检exit0。独立真实prepare/DDP与原生Excalidraw打开没有验收，不夸成正式训练全覆盖。
异常已明确解释，不隐藏：2条.git/refs/codex/turn-diffs动态引用不再存在活动Git（非本批文件移动），但原ref字节/对象在T0备份完整，活动Git对象仍存在，另新增archive保护tag；仍计入21614分母，all-files-map将这2条目标设为备份绝对路径而非伪造原位存在。目录切换后.DS_Store由系统重新生成，旧原件已归档，新版计为T0后运行态。源码原始未知超参数不补造。本轮未提交root全量dirty工作树，已有根NPJ与774f/684e清单快照、history保护refs及完整Git bundle保全历史。根目录实际已切换，外部worktree未搬。
下面为真实摘要和执行脚本；可读取对应原始JSON/JSONL清单进行抽查。最终审核只读，所以无需声称独立重算所有SHA，明确审核边界。

## asset-audit.json
```json
{
  "status": "PASS",
  "fixed_T0_entries": 21614,
  "verified_originals": 21614,
  "coverage": 1.0,
  "copies_checked": 5820,
  "link_only_documents": 2,
  "STATUS_append_prefix": true,
  "retained_history_and_attachment_checks": 2674,
  "new_files": 2728,
  "external_worktrees": "not moved or modified",
  "app_runtime_git_refs_preserved_separately": 2
}
```

## link-audit.json
```json
{
  "status": "PASS",
  "documents": 47,
  "valid_links": 142,
  "newly_broken": [],
  "historical_broken": []
}
```

## post-cutover-verification.json
```json
{
  "status": "PASS",
  "remote_cli_commands": 22,
  "cross_cwd_resolved_equal": true,
  "local_launcher_exit": 0,
  "candidate": "v8",
  "source_identity": "validation-evidence/local-v8-fingerprint-check.json",
  "job_id": "refactor-080006-post-cutover",
  "cli_sha256": "ad6feb5585a86a5820d6386fb5f17fa139a7429c65ed165546d478ecb52563cf"
}
```

## git-runtime-ref-audit.json
```json
[
  {
    "path": ".git/refs/codex/turn-diffs/captures/1789513188572/be6bfeaf-cdfb-4fcf-ac58-d0dab7752882/base",
    "backup": "/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006/root/.git/refs/codex/turn-diffs/captures/1789513188572/be6bfeaf-cdfb-4fcf-ac58-d0dab7752882/base",
    "sha256": "38299c2eec6ccadcbdd682d449cb49ca7b2ea7035f161ca52b13a6e565c8bf08",
    "oid": "276728a56ee3a2daa87c701cf816b3f022c5f8db",
    "active_ref_resolves": false,
    "object_available_in_active_git": true,
    "active_ref_output": "",
    "current_destination": "/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006/root/.git/refs/codex/turn-diffs/captures/1789513188572/be6bfeaf-cdfb-4fcf-ac58-d0dab7752882/base",
    "classification": "git-app-runtime-metadata-preserved-in-T0-backup",
    "protected_ref": "refs/tags/archive/20260916-080006-codex-runtime-capture"
  },
  {
    "path": ".git/refs/codex/turn-diffs/checkpoints/ed3dbd2a79753f2cbe4c5f4389838f2f9aa22362e9a489d6846b6d1435f66a87/6e718b2280c5f6b4b7445d2e5530762fbed06d6dbf3c91b3a80822a1435f8e64/1789513174445/d16081cb-94ef-451a-9c5e-a3a7684ccc23",
    "backup": "/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006/root/.git/refs/codex/turn-diffs/checkpoints/ed3dbd2a79753f2cbe4c5f4389838f2f9aa22362e9a489d6846b6d1435f66a87/6e718b2280c5f6b4b7445d2e5530762fbed06d6dbf3c91b3a80822a1435f8e64/1789513174445/d16081cb-94ef-451a-9c5e-a3a7684ccc23",
    "sha256": "38299c2eec6ccadcbdd682d449cb49ca7b2ea7035f161ca52b13a6e565c8bf08",
    "oid": "276728a56ee3a2daa87c701cf816b3f022c5f8db",
    "active_ref_resolves": false,
    "object_available_in_active_git": true,
    "active_ref_output": "",
    "current_destination": "/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006/root/.git/refs/codex/turn-diffs/checkpoints/ed3dbd2a79753f2cbe4c5f4389838f2f9aa22362e9a489d6846b6d1435f66a87/6e718b2280c5f6b4b7445d2e5530762fbed06d6dbf3c91b3a80822a1435f8e64/1789513174445/d16081cb-94ef-451a-9c5e-a3a7684ccc23",
    "classification": "git-app-runtime-metadata-preserved-in-T0-backup",
    "protected_ref": "refs/tags/archive/20260916-080006-codex-runtime-capture"
  }
]
```

## ledger-append.json
```json
{
  "file": "docs/engineering/pitfalls.md",
  "before_bytes": 34713,
  "before_sha256": "936de47657111e5c0ad2bd89ea7689224183d3e97edfcc26ab6cb1371c612b38",
  "after_sha256": "b65028fbdd1bef8bb955b98d3d593cc9fd31a5516dd9de06d3ba4c063c9b735a"
}
```

## rule-path-changes.json
```json
[
  {
    "path": "AGENTS.md",
    "before_sha256": "7ff286f6e67c2c2e84ebc28e63f57e6cac28a2bf50d3a503a8d15b72c8d9e88b",
    "after_sha256": "b0c916313e0e3de39dd9eb2f64f9f6148e1fa6509383ed678d3443e88386d568",
    "kind": "path-only"
  },
  {
    "path": "CLAUDE.md",
    "before_sha256": "3a435121de6168b44a8f108190d45a3b5eff93a3e858cbafcccb0e86e1f5086e",
    "after_sha256": "541bfff1372bfc14837ccb091c48749d41c4d5ba50d299eee1f5454c4dab670e",
    "kind": "path-only"
  }
]
```

## validation-evidence/local-v8-fingerprint-check.json
```json
{
  "status": "PASS",
  "candidate": "v8",
  "source_files": 94,
  "all_local_sha_match": true,
  "remote_full_logs_retrieved": true,
  "after_cutover": true
}
```

## cutover-plan.json
```json
[
  {
    "source": "NPJ",
    "target": "archive/legacy_npj_snapshot/root-repository-20260916-080006",
    "operation": "move"
  },
  {
    "source": "code",
    "target": "archive/legacy_npj_snapshot/root-code-20260916-080006",
    "operation": "move"
  },
  {
    "source": "collab",
    "target": "archive/legacy_collab/root-20260916-080006",
    "operation": "move"
  },
  {
    "source": "innovation- computation",
    "target": "archive/legacy_docs/root-20260916-080006/innovation- computation",
    "operation": "move"
  },
  {
    "source": "innovation-transfomer",
    "target": "archive/legacy_docs/root-20260916-080006/innovation-transfomer",
    "operation": "move"
  },
  {
    "source": "Office viewer-fix-bug(outline &refresh )",
    "target": "archive/legacy_docs/root-20260916-080006/Office viewer-fix-bug(outline &refresh )",
    "operation": "move"
  },
  {
    "source": "diagrams",
    "target": "archive/legacy_docs/root-20260916-080006/diagrams",
    "operation": "move"
  },
  {
    "source": "image",
    "target": "archive/legacy_docs/root-20260916-080006/image",
    "operation": "move"
  },
  {
    "source": "NPJ-A&NPJ-B区别.md",
    "target": "archive/legacy_docs/root-20260916-080006/NPJ-A&NPJ-B区别.md",
    "operation": "move"
  },
  {
    "source": "how-to-refactor-japanese-in vscode.md",
    "target": "archive/legacy_docs/root-20260916-080006/how-to-refactor-japanese-in vscode.md",
    "operation": "move"
  },
  {
    "source": "explain-advantage&dis~-vscode.md",
    "target": "archive/legacy_docs/root-20260916-080006/explain-advantage&dis~-vscode.md",
    "operation": "move"
  },
  {
    "source": "exam.docx",
    "target": "archive/legacy_docs/root-20260916-080006/exam.docx",
    "operation": "move"
  },
  {
    "source": "论文初版本.docx",
    "target": "archive/legacy_docs/root-20260916-080006/论文初版本.docx",
    "operation": "move"
  },
  {
    "source": "paper.tex",
    "target": "archive/legacy_docs/root-20260916-080006/paper.tex",
    "operation": "move"
  },
  {
    "source": "manuscript/bbag124_word",
    "target": "archive/legacy_docs/root-20260916-080006/manuscript/bbag124_word",
    "operation": "move"
  },
  {
    "source": ".DS_Store",
    "target": "archive/runtime_artifacts/root-20260916-080006/.DS_Store",
    "operation": "move"
  },
  {
    "source": "manuscript/bmc_initial_draft/main.synctex.gz",
    "target": "archive/runtime_artifacts/manuscript/bmc_initial_draft/main.synctex.gz",
    "operation": "move"
  },
  {
    "source": "manuscript/bmc_initial_draft/main.out",
    "target": "archive/runtime_artifacts/manuscript/bmc_initial_draft/main.out",
    "operation": "move"
  },
  {
    "source": "manuscript/bmc_initial_draft/main.aux",
    "target": "archive/runtime_artifacts/manuscript/bmc_initial_draft/main.aux",
    "operation": "move"
  },
  {
    "source": "manuscript/bmc_initial_draft/main.log",
    "target": "archive/runtime_artifacts/manuscript/bmc_initial_draft/main.log",
    "operation": "move"
  }
]
```

## audit_assets.py
```python
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent;BACKUP=Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
runtime_refs={e['path']:e for e in json.loads((B/'git-runtime-ref-audit.json').read_text())}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for v in iter(lambda:f.read(1048576),b''):h.update(v)
 return h.hexdigest()
moves=json.loads((B/'cutover-plan.json').read_text());baseline=[json.loads(s) for s in (BACKUP/'files.jsonl').read_text().splitlines()];rows=[];missing=[]
for r in baseline:
 backup=BACKUP/r['source_id']/r['path'];ok=backup.exists() or backup.is_symlink()
 if ok:
  if r['type']=='symlink':ok=backup.is_symlink() and os.readlink(backup)==r['link_target']
  else:ok=sha(backup)==r['sha256']
 if not ok:missing.append(str(backup))
 active=None
 if r['source_id']=='root':
  active=ROOT/r['path']
  for m in moves:
   if active==ROOT/m['source'] or active.is_relative_to(ROOT/m['source']):active=ROOT/m['target']/active.relative_to(ROOT/m['source']);break
  if not active.exists() and not active.is_symlink():
   if r['path'] in runtime_refs:
    entry=runtime_refs[r['path']];assert r['sha256']==entry['sha256'] and sha(Path(entry['backup']))==entry['sha256'];active=Path(entry['backup'])
   else:missing.append('current destination missing '+str(active))
  elif active.is_relative_to(ROOT) and str(active.relative_to(ROOT)).startswith('archive/'):
   expected=backup
   if r['path'].startswith('NPJ/.git/'):
    expected=BACKUP/'NPJ-after-manifest-commit'/Path(r['path']).relative_to('NPJ')
   same=(active.is_symlink() and os.readlink(active)==os.readlink(expected)) if r['type']=='symlink' else sha(active)==sha(expected)
   if not same:missing.append('archived original changed '+str(active))
 category='git-metadata' if '.git' in Path(r['path']).parts else 'protected-original'
 rows.append({'source_id':r['source_id'],'old_path':r['path'],'original_sha256':r.get('sha256'),'backup':str(backup),'backup_verified':ok,'current_destination':(str(active.relative_to(ROOT)) if active.is_relative_to(ROOT) else str(active)) if active else None,'category':category})
assert not missing,missing[:20]
(B/'all-files-map.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
ledger=json.loads((B/'ledger-append.json').read_text());lp=ROOT/ledger['file'];assert sha(lp)==ledger['after_sha256'];assert hashlib.sha256(lp.read_bytes()[:ledger['before_bytes']]).hexdigest()==ledger['before_sha256']
assets=json.loads((B/'assets-map.json').read_text())['entries'];links=json.loads((B/'link-changes.json').read_text());changed={e['file']:e for e in links};copy_count=0
for e in assets:
 if not e['execute_copy']:continue
 p=ROOT/e['target'];expected=ledger['after_sha256'] if e['target']==ledger['file'] else changed.get(e['target'],{}).get('after_sha256',e['sha256']);assert p.exists() and sha(p)==expected,str(p);copy_count+=1
# 按原跨度重新构造使用版，保证只有已列链接目标改变。
for item in links:
 p=ROOT/item['file'];current=p.read_text()
 if item['file']=='STATUS.md':current=(B/'STATUS.after-links.bin').read_text()
 offset=0;spans=[]
 for c in item['changes']:
  start=c['start']+offset;end=start+len(c['new']);assert current[start:end]==c['new'];spans.append((start,end,c['old']));offset+=len(c['new'])-len(c['old'])
 for start,end,old in reversed(spans):current=current[:start]+old+current[end:]
 assert hashlib.sha256(current.encode()).hexdigest()==item['before_sha256'],item['file']
assert (ROOT/'STATUS.md').read_bytes().startswith((B/'STATUS.after-links.bin').read_bytes())

# 未移动的旧知识、附件和既有 results 也验内容，不能仅检查备份存在。
protected_active = 0
for r in baseline:
 if r['source_id']!='root' or r['type']=='symlink':continue
 rel=r['path'];rp=Path(rel)
 if any(rel==m['source'] or rp.is_relative_to(Path(m['source'])) for m in moves):continue
 protected=(rp.suffix.lower() in {'.md','.svg','.png','.jpg','.jpeg','.webp','.gif','.docx','.pdf','.pth','.pt','.npz','.pkl'} or 'results' in rp.parts)
 if not protected:continue
 p=ROOT/rel
 if rel=='README.md':continue  # 用户明确授权重写；T0原文完整保全。
 if rel in {'AGENTS.md','CLAUDE.md'}:
  before=(BACKUP/'root'/rel).read_text()
  expected=before.replace('collab/pitfalls.md','docs/engineering/pitfalls.md').replace('NPJ/scripts/train_launcher.py','scripts/train_launcher.py').replace('NPJ/scripts/launch_formal.sh','scripts/launch_formal.sh').replace('collab/','archive/legacy_collab/root-20260916-080006/')
  assert p.read_text()==expected,rel
 elif rel=='STATUS.md':
  assert hashlib.sha256((B/'STATUS.before-links.bin').read_bytes()).hexdigest()==r['sha256']
 elif rel=='docs/refactor/20260916-080006-full-project/progress.md':
  pass  # 本批任务控制账本持续更新；它在T0的版本仍在完整备份中。
 elif rel in changed:
  assert changed[rel]['before_sha256']==r['sha256'],rel
 else:assert sha(p)==r['sha256'],f'Unexplained historical asset change: {rel}'
 protected_active+=1

new=[];oldroot={r['path'] for r in baseline if r['source_id']=='root'}
for p in ROOT.rglob('*'):
 if not p.is_file() or '.git' in p.parts or p.is_symlink():continue
 rel=str(p.relative_to(ROOT))
 if (rel not in oldroot or any(rel==m['source'] for m in moves)) and not rel.startswith('archive/') and p!=B/'new-files-manifest.json':new.append({'path':rel,'sha256':sha(p),'bytes':p.stat().st_size})
(B/'new-files-manifest.json').write_text(json.dumps(new,ensure_ascii=False,indent=2))
summary={'status':'PASS','fixed_T0_entries':len(rows),'verified_originals':len(rows),'coverage':1.0,'copies_checked':copy_count,'link_only_documents':len(links),'STATUS_append_prefix':True,'retained_history_and_attachment_checks':protected_active,'new_files':len(new),'external_worktrees':'not moved or modified','app_runtime_git_refs_preserved_separately':len(runtime_refs)}
(B/'asset-audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

```

## repair_links.py
```python
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

```

## finalize_navigation.py
```python
from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
assert (B/'cutover-operations.jsonl').exists()
# 保存 STATUS 三阶段，旧内容只允许 repair_links.py 的目标跨度变化。
status=ROOT/'STATUS.md'
(B/'STATUS.before-links.bin').write_bytes(status.read_bytes())
subprocess.run(['python3','-B',str(B/'repair_links.py')],cwd=ROOT,check=True)
(B/'STATUS.after-links.bin').write_bytes(status.read_bytes())
append='''\n\n## 2026-09-16｜全项目结构化重构\n\n公共代码归 `src/trimodalsurv/`，I01–I04 各有模型、配置、知识与结果入口；旧源码/资料/批次移至 `archive/`，外部 MCAT/PORPOISE 保持独立。\n\n- [项目结构](docs/project-structure.md) · [逐项执行证据](docs/refactor/20260916-080006-full-project/progress.md)\n- [I01 知识](experiments/I01_patient_retrieval/knowledge/index.md) · [I02 知识](experiments/I02_population_prototypes/knowledge/index.md)\n- [I03 知识](experiments/I03_npj_d_dm_e1/knowledge/index.md) · [I04 知识](experiments/I04_cap4_multi_prototypes/knowledge/index.md)\n- [历史汇总复算](docs/refactor/20260916-080006-full-project/history-derived-03/summary.json)\n\n本轮仅重构与 CPU 兼容验证，没有新增正式训练。I04 只整理已有 D 版，C 版仍未实现；历史比较不是匹配训练协议的机制消融。具体通过范围、旧 skip 与审核结论以本轮证据为准。\n\n本次旧正文仅修链接，删除线及科研判断保留；从此继续只在末尾追加。\n'''
with status.open('ab') as f:f.write(append.encode())
assert status.read_bytes().startswith((B/'STATUS.after-links.bin').read_bytes())
(ROOT/'README.md').write_text((B/'README.next.md').read_text())
rule_changes=[]
for filename in ['AGENTS.md','CLAUDE.md']:
 p=ROOT/filename;before=p.read_text();after=before.replace('collab/pitfalls.md','docs/engineering/pitfalls.md').replace('NPJ/scripts/train_launcher.py','scripts/train_launcher.py').replace('NPJ/scripts/launch_formal.sh','scripts/launch_formal.sh')
 # 原collab具体历史证据现在在完整原件目录。
 after=after.replace('collab/', 'archive/legacy_collab/root-20260916-080006/')
 if before!=after:
  p.write_text(after);rule_changes.append({'path':filename,'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'kind':'path-only'})
(B/'rule-path-changes.json').write_text(json.dumps(rule_changes,indent=2))
p=ROOT/'.gitignore'
with p.open('a') as f:f.write('\n# 全项目重构：原始归档/仓库元数据/本轮传输包保留磁盘，不进源码提交。\n/archive/\n/docs/refactor/**/*.tar\n/docs/refactor/**/*.index\n/docs/refactor/**/*.bin\n/docs/refactor/**/validation-evidence/**/*.pt\n')
p=ROOT/'.ignore';s=p.read_text();s=s.replace('!/NPJ/','').replace('# ripgrep / Better Todo Tree：搜索嵌套的 NPJ 开发目录。','# ripgrep / Better Todo Tree：搜索当前公共代码与实验实现。').replace('# .gitignore 仍负责让外层仓库不跟踪 NPJ；这里只调整搜索范围。','# 历史归档和原始结果不进入默认源码搜索；Git 规则另由 .gitignore 管理。');p.write_text(s+'\n/docs/refactor/**/history-derived-*/\n')
p=ROOT/'.vscode/settings.json';settings=json.loads(p.read_text());exclude=settings.setdefault('search.exclude',{});exclude.update({'archive/**':True,'experiments/**/results/**/raw/**':True,'experiments/**/results/**/checkpoints/**':True,'**/__pycache__/**':True});p.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
ledger=ROOT/'docs/engineering/pitfalls.md'
old=ledger.read_bytes()
addition='\n\n## 全项目重构补充（2026-09-16）\n\n| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |\n|---|---|---|---|\n| R1 | 入口拆分后提前返回绕过 set_seed，模块测试无法发现运行初始化差异。 | 对真实入口验证参数解析→随机初始化→目标分发顺序，配置与显式CLI两条路径均覆盖。 | docs/refactor/20260916-080006-full-project/progress.md |\n| R2 | 按报告目录搬结果漏掉相邻历史对照文件，副本不能独立复算。 | 结果保全按实际读取依赖闭包核验，并在禁用旧来源的条件下复算。 | docs/refactor/20260916-080006-full-project/progress.md |\n'
with ledger.open('ab') as f:f.write(addition.encode())
new=ledger.read_bytes();assert new.startswith(old)
(B/'ledger-append.json').write_text(json.dumps({'file':str(ledger.relative_to(ROOT)),'before_bytes':len(old),'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(new).hexdigest()},indent=2))
print('NAVIGATION_UPDATED')

```

## transaction.py
```python
"""仅处理已列明的迁移；独占目标、持久日志、可逆移动。"""
import hashlib,json,os,shutil,stat,unicodedata
from pathlib import Path

def fingerprint(p):
    p=Path(p)
    if p.is_symlink(): return {'kind':'symlink','target':os.readlink(p)}
    if p.is_file():
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1048576),b''):h.update(b)
        return {'kind':'file','bytes':p.stat().st_size,'sha256':h.hexdigest()}
    if p.is_dir():
        return {'kind':'directory','entries':{str(q.relative_to(p)):fingerprint(q) for q in sorted(p.rglob('*')) if q.is_symlink() or q.is_file()}}
    raise FileNotFoundError(p)

def key(p):return unicodedata.normalize('NFC',str(p)).casefold()

class Transaction:
    def __init__(self,log):
        self.log=Path(log);self.log.parent.mkdir(parents=True,exist_ok=True)
    def events(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []
    def record(self,row):
        with self.log.open('a') as f:
            f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    def apply(self,source,target,action='copy'):
        source,target=Path(source).absolute(),Path(target).absolute()
        assert action in ('copy','move')
        op=hashlib.sha256(f'{action}:{source}:{target}'.encode()).hexdigest()
        events=[e for e in self.events() if e['id']==op]
        if events and events[-1]['status']=='verified':
            assert fingerprint(target)==events[-1]['after'],f'target drift {target}'
            return events[-1]
        if events:raise RuntimeError(f'Incomplete operation requires inspection: {op}')
        before=fingerprint(source)
        if target.exists() or target.is_symlink():raise FileExistsError(target)
        if target.parent.exists():
            assert all(key(c)!=key(target) for c in target.parent.iterdir()),f'case/Unicode collision {target}'
        row={'id':op,'source':str(source),'target':str(target),'action':action,'before':before,'status':'planned'}
        self.record(row);target.parent.mkdir(parents=True,exist_ok=True)
        if action=='move':
            assert source.stat().st_dev==target.parent.stat().st_dev,'Cross-device move refused'
            source.rename(target)
        elif source.is_symlink():target.symlink_to(os.readlink(source))
        elif source.is_dir():shutil.copytree(source,target,symlinks=True)
        else:
            with source.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
            shutil.copystat(source,target)
        self.record({**row,'status':'done'})
        after=fingerprint(target);assert before==after,f'Copy mismatch: {target}'
        row={**row,'status':'verified','after':after};self.record(row);return row
    def rollback_moves(self):
        verified={e['id']:e for e in self.events() if e['status']=='verified'}
        rolled={e['id'] for e in self.events() if e['status']=='rolled_back'}
        for op,e in reversed(list(verified.items())):
            if e['action']!='move' or op in rolled:continue
            src,dst=Path(e['source']),Path(e['target'])
            assert not src.exists() and not src.is_symlink(),f'Rollback conflict {src}'
            assert fingerprint(dst)==e['after'],f'Rollback target drift {dst}'
            src.parent.mkdir(parents=True,exist_ok=True);dst.rename(src)
            assert fingerprint(src)==e['before'];self.record({**e,'status':'rolled_back'})

if __name__=='__main__':
    import tempfile
    with tempfile.TemporaryDirectory(prefix='trimodal-transaction-fixture-') as td:
        root=Path(td);a=root/'a';a.write_bytes(b'fixture')
        tx=Transaction(root/'journal.jsonl');tx.apply(a,root/'b','move')
        tx.apply(a,root/'b','move')  # 已验证的幂等重跑
        tx.rollback_moves();assert a.read_bytes()==b'fixture'
        try:tx.apply(a,a,'copy')
        except FileExistsError:pass
        else:raise AssertionError('collision not rejected')
        tx.record({'id':hashlib.sha256(f'copy:{a.absolute()}:{(root/"c").absolute()}'.encode()).hexdigest(),'status':'planned'})
        try:tx.apply(a,root/'c')
        except RuntimeError:pass
        else:raise AssertionError('incomplete not rejected')
        evidence={'collision_rejected':True,'incomplete_rejected':True,'move_reverse_exact':True,'idempotent_verified':True}
    Path(__file__).with_name('transaction-fixture.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence))

```

## 证据位置
docs/refactor/20260916-080006-full-project
源码审核：claude-code-review-4.json；原始操作：cutover-operations.jsonl、assets-copy-operations.jsonl；逐原文件all-files-map.json；旧→新使用副本assets-map.json；链接跨度link-changes.json；STATUS.before-links.bin、STATUS.after-links.bin；根STATUS.md。
