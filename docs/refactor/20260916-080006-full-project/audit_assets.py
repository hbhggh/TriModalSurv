from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent;BACKUP=Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
runtime_refs={e['path']:e for e in json.loads((B/'git-runtime-ref-audit.json').read_text())}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for v in iter(lambda:f.read(1048576),b''):h.update(v)
 return h.hexdigest()
moves=json.loads((B/'cutover-plan.json').read_text());baseline=[json.loads(s) for s in (BACKUP/'files.jsonl').read_text().splitlines()];rows=[];missing=[];archived_verified=set();retained_verified=set();authorized_checks=set()
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
   else:archived_verified.add(r['path'])
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
 if rel in {'AGENTS.md','CLAUDE.md','STATUS.md'} or rel in changed:authorized_checks.add(rel)
 elif rel!='docs/refactor/20260916-080006-full-project/progress.md':retained_verified.add(rel)
 protected_active+=1

new=[];oldroot={r['path'] for r in baseline if r['source_id']=='root'}
for p in ROOT.rglob('*'):
 if not p.is_file() or '.git' in p.parts or p.is_symlink():continue
 rel=str(p.relative_to(ROOT))
 if (rel not in oldroot or any(rel==m['source'] for m in moves)) and not rel.startswith('archive/') and p!=B/'new-files-manifest.json':new.append({'path':rel,'sha256':sha(p),'bytes':p.stat().st_size})
(B/'new-files-manifest.json').write_text(json.dumps(new,ensure_ascii=False,indent=2))
copy_targets={e['target'] for e in assets if e['execute_copy']}
root_paths={r['path'] for r in baseline if r['source_id']=='root'}
existence_only=sorted(root_paths-archived_verified-retained_verified-authorized_checks-copy_targets-set(runtime_refs))
(B/'active-existence-only.json').write_text(json.dumps(existence_only,ensure_ascii=False,indent=2))
summary={
 'status':'PASS','fixed_T0_entries':len(rows),
 'backup_entries_verified':len(rows),
 'backup_sha_verified':sum(r['type']!='symlink' for r in baseline),
 'backup_symlinks_verified':sum(r['type']=='symlink' for r in baseline),
 't0_entry_coverage':1.0,
 'root_destinations_present':len(root_paths),
 'archived_original_content_verified':len(archived_verified),
 'active_content_verified_copies':copy_count,
 'active_content_verified_retained':len(retained_verified),
 'authorized_transformation_checks':len(authorized_checks),
 'active_existence_only':len(existence_only),
 'counter_note':'Copies may overlap retained originals; these content-check counters are not additive. Existence-only paths are listed separately.',
 'link_only_documents':len(links),'STATUS_append_prefix':True,'new_files':len(new),
 'external_worktrees':'not touched by this batch; backup-verified only, in-place content not re-checked',
 'app_runtime_git_refs_preserved_separately':len(runtime_refs)}
(B/'asset-audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
