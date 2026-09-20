from pathlib import Path
import subprocess,sys,json,os
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);rows=[];py=sys.executable
env={**os.environ,'PYTHONPATH':str(root/'src')+':'+str(root),'PYTHONDONTWRITEBYTECODE':'1','CUDA_VISIBLE_DEVICES':''}
commands=[['scripts/train_launcher.py','--arms','e0,d0,dq0,dq_capl1,population','--cancers','BLCA','--seeds','123','--prototype-k','8','--dry_run'],['scripts/main_survival.py','--network_type','NPJC','--compensator','none','--bin_mode','author','--cancer_types','BLCA','--dry_run'],['-m','experiments.I02_population_prototypes.train','--config',str(root/'experiments/I02_population_prototypes/config.yaml'),'--cancer_types','BLCA','--dry_run'],['-m','experiments.I04_cap4_multi_prototypes.train','--network_type','MainModalityMoE','--compensator','capl','--proto_per_bin','2','--fusion_type','mean','--bin_mode','train_quantile','--cancer_types','BLCA','--dry_run'],['-m','experiments.I01_patient_retrieval.evaluate','--help'],['-m','experiments.I02_population_prototypes.evaluate','--help'],['scripts/eval_missing.py','--help']]
commands.extend([
 ['scripts/main_survival.py','--config',str(root/'experiments/I02_population_prototypes/config.yaml'),'--cancer_types','BLCA','--dry_run'],
 ['scripts/main_survival.py','--config',str(root/'experiments/I03_npj_d_dm_e1/config.yaml'),'--preset','D','--cancer_types','BLCA','--dry_run'],
 ['scripts/main_survival.py','--config',str(root/'experiments/I03_npj_d_dm_e1/config.yaml'),'--preset','E1','--cancer_types','BLCA','--dry_run'],
 ['scripts/main_survival.py','--config',str(root/'experiments/I04_cap4_multi_prototypes/config.yaml'),'--preset','dq_capl8','--cancer_types','BLCA','--dry_run'],
])
for cwd in [root,root.parent]:
 for c in commands:
  args=[py,'-B',*c]
  if c[0].startswith('scripts/'):args[2]=str(root/c[0])
  p=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True)
  rows.append({'cwd':str(cwd),'command':args,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});print(c[0:2],p.returncode,flush=True)
with out.open('x') as f:json.dump(rows,f,indent=2)
assert all(r['exit']==0 for r in rows)
for first,second in zip(rows[:len(commands)],rows[len(commands):]):
 if 'runtime' in first['stdout'] and '--dry_run' in first['command']:
  left=json.loads(first['stdout'].splitlines()[-1]);right=json.loads(second['stdout'].splitlines()[-1]);assert left==right,('cwd configuration drift',first['command'])
