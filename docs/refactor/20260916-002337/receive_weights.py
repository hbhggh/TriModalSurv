"""由 landau jobrun 托管的有限白名单接收器；不删除源文件。"""
from pathlib import Path
import tarfile, os, json, hashlib
root=Path(__file__).resolve().parent
expected=json.loads((root/'remote_weights_before.json').read_text())
by_name={r['relative']:r for r in expected}
assert len(by_name)==25
fifo=root/'incoming.fifo'
os.mkfifo(fifo,0o600)
received=[]
with fifo.open('rb') as stream, tarfile.open(fileobj=stream,mode='r|') as tar:
 for entry in tar:
  assert entry.isfile() and entry.name in by_name and entry.name not in received, entry.name
  meta=by_name[entry.name]; assert entry.size==meta['size']
  dest=root/'checkpoints'/entry.name
  dest.parent.mkdir(parents=True,exist_ok=True)
  tmp=dest.with_name(dest.name+'.partial')
  md5=hashlib.md5(); sha=hashlib.sha256(); size=0
  with tar.extractfile(entry) as src,tmp.open('xb') as out:
   while chunk:=src.read(1048576):
    out.write(chunk); md5.update(chunk); sha.update(chunk);size+=len(chunk)
   out.flush();os.fsync(out.fileno())
  assert size==meta['size'] and md5.hexdigest()==meta['md5'] and sha.hexdigest()==meta['sha256']
  assert not dest.exists()
  tmp.rename(dest); received.append(entry.name)
  print('VERIFIED',entry.name,flush=True)
assert set(received)==set(by_name)
with (root/'verified.json').open('x') as out:
 json.dump({'count':len(received),'files':expected},out,indent=2)
print('VERIFIED_ALL',len(received),flush=True)
