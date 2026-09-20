"""仅临时夹具：碰撞、半途失败、重入和逆向恢复。"""
import hashlib,json,pathlib,subprocess,sys,tempfile
SCRIPT=pathlib.Path(__file__).with_name('copy_assets.py').resolve()
with tempfile.TemporaryDirectory(prefix='trimodalsurv-assets-') as tmp:
    base=pathlib.Path(tmp); root=base/'root'; root.mkdir(); source=base/'source'; source.write_bytes(b'original')
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    item=dict(id='fixture',source=str(source),target='docs/a.bin',sha256=h,execute_copy=True)
    manifest=base/'manifest.json'; manifest.write_text(json.dumps({'entries':[item]})); log=base/'ops.jsonl'
    cmd=[sys.executable,str(SCRIPT),'--root',str(root),'--manifest',str(manifest),'--log',str(log)]
    def run(*args,ok=True):
        p=subprocess.run(cmd+list(args),capture_output=True,text=True)
        assert (p.returncode==0)==ok,(args,p.stdout,p.stderr)
    target=root/'docs/a.bin'; target.parent.mkdir(); target.write_bytes(b'collision')
    run('--apply',ok=False); assert target.read_bytes()==b'collision'
    target.rename(base/'collision-preserved')
    run('--apply'); assert target.read_bytes()==b'original'
    run('--apply'); assert len(log.read_text().splitlines())==3
    run('--rollback'); assert not target.exists()
    assert (root/'archive/runtime_artifacts/assets-copy-rollback/fixture/docs/a.bin').read_bytes()==b'original'
    # 模拟已完成写出但进程在 verified 前断开；仅有 planned 不能绕过 hash。
    log.write_text(json.dumps(dict(item,status='planned'))+'\n'); target.write_bytes(b'partial')
    run('--apply',ok=False); assert target.read_bytes()==b'partial'
    target.rename(base/'partial-preserved'); target.write_bytes(b'original')
    run('--apply'); assert json.loads(log.read_text().splitlines()[-1])['status']=='verified'
    print(json.dumps({'exclusive_collision':'PASS','partial_write_rejected':'PASS','reentry_hash_verified':'PASS','reverse_quarantine':'PASS'}))
