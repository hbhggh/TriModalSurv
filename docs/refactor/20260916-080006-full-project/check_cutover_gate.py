"""仅硬门通过后生成切换许可；不移动文件。"""
from pathlib import Path
import json,hashlib,re
B=Path(__file__).parent;R=B.parents[2]
assert not (B/'cutover-gate.json').exists()
evidence={}
for name in ['validation-evidence/real-parity.json','validation-evidence/synthetic-parity.json','validation-evidence/checkpoints-verified.json','validation-evidence/epoch-parity.json','history-derived-03/summary.json']:
 p=B/name;x=json.loads(p.read_text());assert (all(v.get('status')=='PASS' for v in x.values()) if name.startswith('history-derived') else x.get('status')=='PASS'),name;evidence[name]=hashlib.sha256(p.read_bytes()).hexdigest()
log=(B/'validation-evidence/new-v8-tests.log').read_text();assert re.search(r'186 passed, 6 skipped',log)
rows=json.loads((B/'validation-evidence/cli-preflight-v8.json').read_text());assert len(rows)==22 and all(x['exit']==0 for x in rows)
for a,b in zip(rows[:11],rows[11:]):
 if 'runtime' in a['stdout'] and '--dry_run' in a['command']:assert json.loads(a['stdout'].splitlines()[-1])==json.loads(b['stdout'].splitlines()[-1])
for r in json.loads((B/'candidate-v8-manifest.json').read_text()):assert hashlib.sha256((R/r['path']).read_bytes()).hexdigest()==r['sha256'],r['path']
review=json.loads((B/'claude-code-review-4.json').read_text());result=review['result'];blocks=re.findall(r'```json\s*(.*?)\s*```',result,re.S)
verdict=review.get('structured_output') or json.loads(blocks[-1] if blocks else result);assert verdict['verdict']=='PASS' and not verdict['required_changes'],verdict
for name in ['transaction-fixture.json','safeguard.json','npj-manifest-snapshot.json','candidate-v8-manifest.json','claude-code-review-4.json']:
 p=B/name;evidence[name]=hashlib.sha256(p.read_bytes()).hexdigest()
(B/'cutover-gate.json').write_text(json.dumps({'status':'PASS','checks':evidence,'limits':'CPU only; no formal experiment or deployment; final links/assets audit follows rename'},indent=2))
print('CUTOVER_GATE_PASS')
