"""重读基线中全部旧资产，并验证 STATUS 仅末尾追加。"""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[3]
folder=Path(__file__).resolve().parent
baseline=json.loads((folder/'baseline.json').read_text())
changes=[];protected=0;images=0;counts={}
for item in baseline['files']:
    p=Path(baseline['roots'][item['root']]['root'])/item['path']
    suffix=p.suffix.lower()
    if suffix in {'.md','.svg'}: protected+=1;counts[item['root']]=counts.get(item['root'],0)+1
    if suffix in {'.png','.jpg','.jpeg','.webp'}:images+=1
    if item['root']=='main' and item['path']=='STATUS.md':
        before=(folder/'STATUS.before.bin').read_bytes()
        if not p.read_bytes().startswith(before):changes.append(str(p))
        continue
    h=hashlib.sha256()
    if not p.is_file():changes.append(str(p));continue
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    if p.stat().st_size!=item['size'] or h.hexdigest()!=item['sha256']:changes.append(str(p))
weights=root/'experiments/I02_population_prototypes/results/formal-k8-es15-e100-v1'
w=json.loads((weights/'checkpoint_manifest.json').read_text())
for item in w['files']:
    p=weights/'checkpoints'/item['relative'];b=p.read_bytes()
    assert len(b)==item['size'] and hashlib.md5(b).hexdigest()==item['md5'] and hashlib.sha256(b).hexdigest()==item['sha256']
report={'status':'PASS' if not changes else 'FAIL','baseline_files':len(baseline['files']),'protected_md_svg':protected,'protected_md_svg_by_root':counts,'image_attachments':images,'changed_original_files':changes,'status_original_prefix_preserved':(root/'STATUS.md').read_bytes().startswith((folder/'STATUS.before.bin').read_bytes()),'i02_checkpoints_verified':len(w['files'])}
with (folder/'preservation-verification.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report,ensure_ascii=False))
assert not changes
