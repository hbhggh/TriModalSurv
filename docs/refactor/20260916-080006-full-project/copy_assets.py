#!/usr/bin/env python3
"""独占复制资料清单；默认只检查，--apply 执行，--rollback 隔离本批次副本。
不执行 archive_by_parent，不移走任何原件；恢复时不删除文件、不覆盖后来修改。
"""
import argparse, datetime, hashlib, json, os, pathlib, subprocess, unicodedata

def digest(p):
    if p.is_symlink(): raise RuntimeError('symlink unsupported for copy: '+str(p))
    return hashlib.sha256(p.read_bytes()).hexdigest()

def event(log,e,state,**extra):
    row={k:e[k] for k in ('id','source','target','sha256')}
    row.update(status=state,phase='assets-copy',timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),**extra)
    with log.open('a',encoding='utf-8') as f:
        f.write(json.dumps(row,ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())

def read_source(e,root):
    if e['source'].startswith('git:'):
        _,commit,path=e['source'].split(':',2)
        return subprocess.check_output(['git','show',commit+':'+path],cwd=root)
    p=pathlib.Path(e['source'])
    if p.is_symlink(): raise RuntimeError('symlink copy requires parent transaction')
    return p.read_bytes()

def safe_target(root,target):
    p=root/target
    if pathlib.Path(target).is_absolute() or '..' in pathlib.Path(target).parts: raise RuntimeError('unsafe target')
    q=p
    while q!=root:
        if q.is_symlink(): raise RuntimeError('target has symlink component: '+str(q))
        q=q.parent
    return p

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=pathlib.Path,default=pathlib.Path(__file__).with_name('assets-map.json'))
    ap.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[3])
    ap.add_argument('--log',type=pathlib.Path)
    ap.add_argument('--apply',action='store_true'); ap.add_argument('--rollback',action='store_true')
    ap.add_argument('--only-prefix',default='')
    a=ap.parse_args(); root=a.root.resolve(); log=a.log or a.manifest.with_name('assets-copy-operations.jsonl')
    if a.apply and a.rollback: ap.error('choose apply or rollback')
    entries=[e for e in json.loads(a.manifest.read_text())['entries'] if e['execute_copy'] and e['target'].startswith(a.only_prefix)]
    states={}; history=[]
    if log.exists():
        for line in log.read_text().splitlines():
            x=json.loads(line); states[x['id']]=x; history.append(x)
    if a.rollback:
        quarantine=root/'archive/runtime_artifacts/assets-copy-rollback'
        for e in reversed(entries):
            prev=states.get(e['id']); p=safe_target(root,e['target'])
            if not prev or prev['status']=='rolled_back': continue
            if not p.exists():
                if prev['status']=='planned': continue
                raise RuntimeError('logged copy missing: '+str(p))
            if digest(p)!=e['sha256']: raise RuntimeError('rollback conflict: '+str(p))
            q=quarantine/e['id']/e['target']
            if q.exists(): raise RuntimeError('rollback quarantine exists: '+str(q))
            event(log,e,'rollback_planned',quarantine=str(q)); q.parent.mkdir(parents=True,exist_ok=True)
            os.rename(p,q); event(log,e,'rolled_back',quarantine=str(q),after_sha256=digest(q))
        print(json.dumps({'rollback':'verified','considered':len(entries)})); return
    count=0
    for e in entries:
        p=safe_target(root,e['target']); prev=states.get(e['id'])
        data=read_source(e,root)
        if hashlib.sha256(data).hexdigest()!=e['sha256']: raise RuntimeError('source hash changed: '+e['source'])
        if p.exists():
            if not prev or prev['status']=='rolled_back': raise RuntimeError('exclusive target collision: '+str(p))
            if digest(p)!=e['sha256']: raise RuntimeError('incomplete or externally modified target: '+str(p))
            if a.apply and prev['status']!='verified': event(log,e,'verified',after_sha256=e['sha256'],recovered=True)
            count+=1; continue
        if prev and prev['status']=='verified': raise RuntimeError('verified target vanished: '+str(p))
        if a.apply:
            event(log,e,'planned',before_sha256=e['sha256']); p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            event(log,e,'done',after_sha256=digest(p))
            if digest(p)!=e['sha256']: raise RuntimeError('post-copy mismatch')
            event(log,e,'verified',after_sha256=e['sha256'])
        count+=1
    print(json.dumps({'mode':'apply' if a.apply else 'dry-run','verified_sources':count,'copy_only':True}))
if __name__=='__main__': main()
