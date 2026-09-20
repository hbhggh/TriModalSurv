#!/usr/bin/env python3
"""只读冻结历史及迁移副本，标准库复算五组；输出独占 derived 目录。
原值/派生值容差1e-12；历史已舍入表按原小数位精确字符串核对。
"""
import argparse,collections,csv,hashlib,io,json,math,pathlib,re,runpy,statistics as st,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
HERE=pathlib.Path(__file__).resolve().parent
B=pathlib.Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
C5=['BLCA','BRCA','LUAD','LGG','UCEC']; S5=[123,132,213,231,321]; S25=S5+list(range(1,21)); G4=['none','rna_100','text_100','both_100']
PAT=re.compile(r'^.+_(BLCA|BRCA|LUAD|LGG|UCEC)_s(\d+)(?:_population_k8)?\.json$')
ap=argparse.ArgumentParser(); ap.add_argument('--out',type=pathlib.Path,required=True); ap.add_argument('--require-migrated',action='store_true'); args=ap.parse_args()
args.out.mkdir(parents=True,exist_ok=False)
manifest=json.loads((HERE/'assets-map.json').read_text()); mapping=collections.defaultdict(list)
for e in manifest['entries']:
 if e['execute_copy'] or e['operation']=='retain': mapping[e['source']].append(e)
sources={}; checks=[]; summaries={}; group=''
def sha(data): return hashlib.sha256(data).hexdigest()
def raw(p):
 p=pathlib.Path(p); data=p.read_bytes(); h=sha(data)
 rec=sources.setdefault(str(p),{'sha256':h,'size':len(data),'groups':[],'migrated':[]})
 if group not in rec['groups']: rec['groups'].append(group)
 for e in mapping.get(str(p),[]):
  q=ROOT/e['target']
  if q.exists():
   qh=sha(q.read_bytes()); assert qh==h,('migrated hash mismatch',str(q))
   if str(q) not in rec['migrated']: rec['migrated'].append(str(q))
 # I01 root T0 already contains the existing result tree; backup canonical paths use root.
 if args.require_migrated and not rec['migrated'] and p.suffix not in ('.py',):
  raise AssertionError(('no migrated copy mapped',str(p)))
 return data

def doc(p): return json.loads(raw(p))
def csvrows(p): return list(csv.DictReader(io.StringIO(raw(p).decode())))
def check(label,a,b,rounded=None):
 if rounded is not None: ok=f'{float(a):.{rounded}f}'==str(b).replace('**',''); delta=None
 elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
  delta=abs(a-b); ok=math.isfinite(a) and math.isfinite(b) and delta<=1e-12
 else: delta=None; ok=a==b
 checks.append(dict(group=group,label=label,ok=ok,delta=delta,actual=a,expected=b))
def write(name,obj): (args.out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load_arm(dirs,arm):
 out={}
 for d in dirs:
  for p in sorted(d.glob('*.json')):
   m=PAT.match(p.name)
   if not m: continue
   j=doc(p); c,s=m[1],int(m[2]); assert j['cancer']==c and int(j['seed'])==s
   for g,v in j['grids'].items():
    key=(arm,c,s,g)
    if key in out: assert out[key]==v['cindex_B'],('conflict',key)
    out[key]=v['cindex_B']
 return out

def s5():
 base=B/'root/collab/20260827-三方对比战役'; values={}
 for p in sorted((base/'s5_results').glob('*.json')):
  j=doc(p)
  if isinstance(j,list):
   for r in j:
    for met,key in [('NPJ-A','cindex_A_raw'),('NPJ-B','cindex_B_sigmoid')]: values[(r['cancer'],met,int(r['seed']))]=r[key]
  else:
   seed=int(re.search(r'_s(\d+)',p.stem)[1]); values[(j['cancer'],j['lib'],seed)]=j['c_index']
 assert len(values)==100
 # 历史原表 4 位；CSV 6 位；均不伪装为全精度统计。
 cancer=None; n=0
 for line in raw(base/'s5_report.md').decode().splitlines():
  m=re.match(r'### (BLCA|BRCA|LUAD|LGG|UCEC)',line)
  if m: cancer=m[1]
  parts=[s.strip() for s in line.strip('|').split('|')]
  if cancer and parts[0] in ('MCAT','PORPOISE','NPJ-A','NPJ-B') and len(parts)==7:
   vs=[values[cancer,parts[0],s] for s in S5]
   for s,v,x in zip(S5,vs,parts[1:6]): check(f'md/{cancer}/{parts[0]}/{s}',v,x,4); n+=1
   check(f'range/{cancer}/{parts[0]}',max(vs)-min(vs),parts[6],4)
 for r in csvrows(B/'root/collab/20260902-A测缺失补偿/s5_full_reference.csv'):
  for col in ('cindex_A','cindex_B'):
   if not r.get(col): continue
   arm=('NPJ-A' if col=='cindex_A' else 'NPJ-B') if r['method']=='NPJ' else r['method']
   # CSV numeric string drops trailing zeros.
   check(f'csv/{r["cancer"]}/{arm}/{r["seed"]}',round(values[r['cancer'],arm,int(r['seed'])],6),float(r[col]))
 assert n==100
 cells=[dict(cancer=c,arm=a,mean=st.mean(values[c,a,s] for s in S5),median=st.median(values[c,a,s] for s in S5)) for c in C5 for a in ('MCAT','PORPOISE','NPJ-A','NPJ-B')]
 write('s5-values.json',[{'cancer':k[0],'arm':k[1],'seed':k[2],'value':v} for k,v in sorted(values.items())]); write('s5-derived.json',cells)
 return {'raw_values':100,'cells':20,'historical_mean_available':False,'rounding':'MD 4 decimals; CSV 6 decimals; newly derived means are not historical means'}

def missing():
 base=B/'root/collab/20260902-A测缺失补偿'; arms={}
 for a in ['m0real','m1','m1b','m2']: arms.update(load_arm([base/'results_gate'/a],a))
 for a in ['E0','E1']:
  arms.update(load_arm([base/'results_npjc'/a.lower(),base/'results_npjc_both'/a.lower()],a))
 arms.update(load_arm([base/'results_npjc_e0d'],'E0d'))
 n=0
 for fname in ['table_gate_4arms.md','table_npjc_E0_E1_E0d_4grids.md']:
  g=None
  for line in raw(base/fname).decode().splitlines():
   m=re.match(r'## 格点 (\w+)',line)
   if m: g=m[1]
   p=[s.strip() for s in line.strip('|').split('|')]
   if len(p)!=9 or p[0] not in C5: continue
   c,a=p[:2]; vals=[arms[a,c,s,g] for s in S5]
   for s,v,x in zip(S5,vals,p[2:7]): check(f'{fname}/{a}/{c}/{s}/{g}',v,x,4); n+=1
   check(f'{fname}/median/{a}/{c}/{g}',st.median(vals),p[7],4)
   if p[8]:
    ref='m0real' if fname.startswith('table_gate') else 'E0'; d=[v-arms[ref,c,s,g] for s,v in zip(S5,vals)]
    if ref=='m0real': expected=f'{sum(v>0 for v in d)}:{sum(v<=0 for v in d)}'
    else: expected=f'{sum(v>1e-6 for v in d)}:{sum(v < -1e-6 for v in d)}:{sum(abs(v)<=1e-6 for v in d)}'
    check(f'{fname}/winloss/{a}/{c}/{g}',expected,p[8].split()[0]); check(f'{fname}/delta/{a}/{c}/{g}',f'{st.median(d):+.4f}',re.search(r'Δ中位 ([+-][\d.]+)',p[8])[1])
 write('missing-values.json',[dict(arm=k[0],cancer=k[1],seed=k[2],grid=k[3],value=v) for k,v in sorted(arms.items())])
 return {'raw_values':len(arms),'historical_table_seed_values':n,'tie_rules':'gate strict >; C/E0/E1/E0d EPS=1e-6','historical_mean_available':False}

def i01():
 base=B/'root/experiments/I01_patient_retrieval/results/legacy-tako-formal-20260915/raw/tako-formal/evidence'
 units={}
 for p in sorted((base/'formal').glob('*.json')):
  j=doc(p); units[j['arm'],j['cancer'],int(j['seed'])]=j
 assert len(units)==75
 for c in C5:
  for s in S5:
   js=[units[a,c,s] for a in ['m0real','m1','retrieval']]
   assert len({j['checkpoint_sha256'] for j in js})==1 and len({j['comparison_fingerprint'] for j in js})==1
   assert all(set(j['grids'])==set(G4) for j in js)
   for g in G4: assert len({j['grids'][g]['grid_sha'] for j in js})==1
 old=csvrows(base/'summary/per_cell.csv'); derived=[]
 for r in old:
  a,c,g=r['arm'],r['cancer'],r['grid']; vals=[units[a,c,s]['grids'][g]['cindex_B'] for s in S5]
  check(f'{a}/{c}/{g}/n',len(vals),int(r['n_seeds']))
  check(f'{a}/{c}/{g}/mean',st.fmean(vals),float(r['mean'])); check(f'{a}/{c}/{g}/sd',st.stdev(vals),float(r['sample_std']))
  derived.append(dict(arm=a,cancer=c,grid=g,mean=st.fmean(vals),sd=st.stdev(vals)))
 paired=csvrows(base/'summary/paired_deltas.csv')
 for r in paired:
  c,g,s=r['cancer'],r['grid'],int(r['seed']); ref=r['contrast'].split('minus-')[1]
  ds=[units['retrieval',c,z]['grids'][g]['cindex_B']-units[ref,c,z]['grids'][g]['cindex_B'] for z in S5]
  check(f'{r["contrast"]}/{c}/{g}/{s}/delta',ds[S5.index(s)],float(r['delta']))
  check(f'{r["contrast"]}/{c}/{g}/{s}/mean',st.fmean(ds),float(r['mean'])); check(f'{r["contrast"]}/{c}/{g}/{s}/sd',st.stdev(ds),float(r['sample_std']))
 write('i01-derived.json',derived)
 return {'units':75,'raw_values':300,'mean_cells':len(old),'paired_rows':len(paired),'scope':'JSON aggregation only; no C-index recomputation from patient features'}

def i02():
 base=B/'684e/collab/20260915-population-prototypes/results-summary'; oldbase=B/'684e/collab/20260902-A测缺失补偿'
 dirs={'Population-K8':[base/'evidence/population/eval'],'E0':[oldbase/'results_npjc/e0',oldbase/'results_npjc_both/e0'],'E0m':[oldbase/'results_npjc_e0m']}
 vals={}
 for a,ds in dirs.items(): vals.update(load_arm(ds,a))
 old=csvrows(base/'metrics_long.csv'); assert len(vals)==len(old)==525
 for r in old: check(f'raw/{r["arm"]}/{r["cancer"]}/{r["seed"]}/{r["grid"]}',vals[r['arm'],r['cancer'],int(r['seed']),r['grid']],float(r['cindex_B']))
 derived=[]
 for r in csvrows(base/'summary_mean_sd.csv'):
  a,c,g=r['arm'],r['cancer'],r['grid']; v=[vals[a,c,s,g] for s in S5]
  check(f'{a}/{c}/{g}/mean',st.mean(v),float(r['mean'])); check(f'{a}/{c}/{g}/sd',st.stdev(v),float(r['sd'])); check(f'{a}/{c}/{g}/n',len(v),int(r['n_seeds']))
  derived.append(dict(arm=a,cancer=c,grid=g,mean=st.mean(v),sd=st.stdev(v)))
 for r in csvrows(base/'historical_deltas.csv'):
  c,g,a=r['cancer'],r['grid'],r['comparator']; ds=[vals['Population-K8',c,s,g]-vals[a,c,s,g] for s in S5]
  for k,v in {'mean_delta':st.mean(ds),'sd_delta':st.stdev(ds),'positive':sum(x>1e-12 for x in ds),'negative':sum(x < -1e-12 for x in ds),'tied':sum(abs(x)<=1e-12 for x in ds)}.items(): check(f'{a}/{c}/{g}/{k}',v,float(r[k]))
 write('i02-derived.json',derived)
 return {'raw_values':525,'mean_cells':len(derived),'compared':'metrics_long B / summary_mean_sd / historical_deltas','protocol_boundary':'historical comparison, not matched-training mechanism ablation'}

def i03():
 base=B/'2af8/collab/20260906-NPJ-D消融'; oldbase=B/'2af8/collab/20260902-A测缺失补偿'
 vals={}
 for a,dirs in {'D':[base/'results_npjd_d0'],'Dm':[base/'results_npjd_dm'],'E1':[oldbase/'results_npjc/e1',oldbase/'results_npjc_both/e1',base/'results_npjc_e1_25']}.items(): vals.update(load_arm(dirs,a))
 assert len(vals)==1500
 derived=[]
 for a in ['D','Dm','E1']:
  for c in C5:
   for g in G4:
    v=[vals[a,c,s,g] for s in S25]; derived.append(dict(arm=a,cancer=c,grid=g,mean=st.mean(v),median=st.median(v),min=min(v),max=max(v)))
 n=0; g=None
 for line in raw(base/'table_npjd_D_Dm_E1_absolute_25seed.md').decode().splitlines():
  if line.startswith('## 附录'): break
  m=re.match(r'### 格点 (\w+)',line)
  if m: g=m[1]
  p=[s.strip() for s in line.strip('|').split('|')]
  if len(p)!=30 or p[0] not in C5: continue
  c,a=p[:2]; v=[vals[a,c,s,g] for s in S25]
  for s,x,y in zip(S25,v,p[2:27]): check(f'{a}/{c}/{g}/{s}',x,y,4); n+=1
  for label,x,y in zip(['median','min','max'],[st.median(v),min(v),max(v)],p[27:]): check(f'{a}/{c}/{g}/{label}',x,y,4)
 assert n==1500
 write('i03-values.json',[dict(arm=k[0],cancer=k[1],seed=k[2],grid=k[3],value=v) for k,v in sorted(vals.items())]); write('i03-derived.json',derived)
 return {'raw_B_values':1500,'cells':60,'historical_statistic':'median/min/max rounded to 4 decimals, not mean','new_means':'60 derived means; historical unrounded mean unavailable'}

for name,fn in [('s5',s5),('missing_20260902',missing),('i01',i01),('i02',i02),('i03_r6',i03)]:
 group=name
 try: summaries[name]=dict(status='computed',**fn())
 except Exception as e: summaries[name]={'status':'ERROR','error':repr(e)}
for name,summary in summaries.items():
 cs=[c for c in checks if c['group']==name]; bad=[c for c in cs if not c['ok']]
 summary.update(checks=len(cs),mismatches=len(bad),max_numeric_difference=max([c['delta'] for c in cs if c['delta'] is not None] or [0.0]))
 if bad: summary['status']='MISMATCH'
 elif summary['status']=='computed': summary['status']='PASS'
write('sources.json',sources); write('checks.json',checks); write('summary.json',summaries)
print(json.dumps(summaries,ensure_ascii=False,indent=2))
sys.exit(0 if all(x['status']=='PASS' for x in summaries.values()) else 1)
