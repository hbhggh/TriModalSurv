"""实际 Claude 只读审阅；进程状态与审阅结论分开留存。"""
import subprocess,json,hashlib,datetime,sys
from pathlib import Path
B=Path(__file__).parent
name,prompt_path=sys.argv[1:];p=Path(prompt_path)
schema={'type':'object','properties':{'verdict':{'type':'string','enum':['PASS','REVISE']},'required_changes':{'type':'array','items':{'type':'string'}},'limitations':{'type':'array','items':{'type':'string'}}},'required':['verdict','required_changes','limitations'],'additionalProperties':False}
cmd=['/opt/homebrew/bin/claude','--safe-mode','-p','--model','opus','--effort','medium','--tools','Read,Glob,Grep','--allowedTools','Read,Glob,Grep','--no-chrome','--no-session-persistence','--output-format','json','--json-schema',json.dumps(schema)]
with p.open() as i,(B/f'{name}.json').open('x') as o,(B/f'{name}.stderr').open('x') as e:r=subprocess.run(cmd,stdin=i,stdout=o,stderr=e)
(B/f'{name}-process.json').write_text(json.dumps({'exit':r.returncode,'command':cmd,'prompt_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'completed':datetime.datetime.now().isoformat()},indent=2));print('CLAUDE_EXIT',r.returncode)
raise SystemExit(r.returncode)
