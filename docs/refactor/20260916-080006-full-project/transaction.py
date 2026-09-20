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
