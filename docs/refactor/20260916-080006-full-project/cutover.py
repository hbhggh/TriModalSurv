"""最终目录切换：固定T0漂移门、可逆rename、不删除。"""
from pathlib import Path
import json,sys,hashlib
from transaction import Transaction,fingerprint
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
backup=Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
plan=json.loads((B/'cutover-plan.json').read_text())
if '--apply' not in sys.argv:
 for op in plan:
  a=ROOT/op['source'];b=ROOT/op['target'];assert a.exists();assert not b.exists(),b
  frozen=(backup/'NPJ-after-manifest-commit') if op['source']=='NPJ' else backup/'root'/op['source'];assert fingerprint(a)==fingerprint(frozen),f'External drift {a}'
 print('CUTOVER_DRY_PASS',len(plan));raise SystemExit
assert (B/'cutover-gate.json').exists(),'Must review verification gate first'
gate=json.loads((B/'cutover-gate.json').read_text());assert gate['status']=='PASS'
tx=Transaction(B/'cutover-operations.jsonl')
for op in plan:
 a=ROOT/op['source'];b=ROOT/op['target']
 if a.exists():assert fingerprint(a)==fingerprint((backup/'NPJ-after-manifest-commit') if op['source']=='NPJ' else backup/'root'/op['source']),f'External drift {a}'
 tx.apply(a,b,'move')
print('CUTOVER_VERIFIED',len(plan))
