#!/usr/bin/env python3
"""从冻结 T0 生成资料逐文件映射；不移动、复制或改写资料。"""
import collections, hashlib, json, pathlib, subprocess, unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[3]
OUT=pathlib.Path(__file__).resolve().parent
BACKUP=pathlib.Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
I01='experiments/I01_patient_retrieval'; I02='experiments/I02_population_prototypes'
I03='experiments/I03_npj_d_dm_e1'; I04='experiments/I04_cap4_multi_prototypes'
rows=[json.loads(s) for s in (BACKUP/'files.jsonl').read_text().splitlines()]
entries=[]
def add(r,target,kind,reason,execute=False):
    p=r['path']; sid=r['source_id']; src=str(BACKUP/sid/p)
    entries.append(dict(source_id=sid,source_path=p,source=src,target=target,sha256=r.get('sha256'),size=r['size'],file_type=r['type'],link_target=r.get('link_target'),operation=kind,reason=reason,execute_copy=execute,phase='assets',status='planned'))
def mapped(p):
    if p.startswith('innovation- computation/'):
        bits=p.split('/'); exp=I02 if '人群' in bits[1] else I01
        return exp+'/knowledge/legacy-source/'+ '/'.join(bits[2:])
    if p.startswith('innovation-transfomer/'): return 'docs/research-ideas/'+p.split('/',1)[1]
    if p.startswith('Office viewer-fix-bug(outline &refresh )/'): return 'docs/workflow/office-viewer/'+p.split('/',1)[1]
    if p in ('how-to-refactor-japanese-in vscode.md','explain-advantage&dis~-vscode.md'): return 'docs/workflow/'+p
    if p=='exam.docx': return 'docs/workflow/fixtures/'+p
    if p=='diagrams/111.excalidraw.svg': return 'docs/workflow/fixtures/111.excalidraw.svg'
    if p=='diagrams/222.excalidraw.svg': return I01+'/knowledge/legacy-source/222.excalidraw.svg'
    if p.startswith('image/STATUS/'): return 'docs/assets/status/'+p.split('/',2)[2]
    if p=='NPJ-A&NPJ-B区别.md': return 'docs/metrics/'+p
    if p=='论文初版本.docx': return 'manuscript/references/bbag124/论文初版本.docx'
    if p.startswith('manuscript/bbag124_word/'): return 'manuscript/references/bbag124/bbag124_word/'+p.split('/',2)[2]
    if p=='paper.tex': return 'archive/legacy_docs/paper.tex'
for r in rows:
    if r['source_id']!='root': continue
    p=r['path']; t=mapped(p)
    if p.startswith('collab/'):
        add(r,'archive/legacy_collab/'+p[7:],'archive_by_parent','完整原批次；由主事务最终 rename')
        if p=='collab/pitfalls.md': add(r,'docs/engineering/pitfalls.md','copy','唯一活动坑台账',True)
        parts=p.split('/'); batch=parts[1]
        if batch=='20260827-三方对比战役' and (p.startswith('collab/'+batch+'/s5_results/') or parts[-1]=='s5_report.md'):
            add(r,'experiments/_comparisons/legacy-s5-20260827/raw/'+p[7:],'copy','S5 跨三基线原始比较',True)
        if batch=='20260902-A测缺失补偿' and not any(x in parts for x in ('__pycache__','scratch','probe','审查')):
            add(r,'experiments/_comparisons/legacy-missing-compensation-20260902/raw/'+p[7:],'copy','跨 gate/C/E0/E1/E0d 原批次，不按 arm 字段混认身份',True)
        if batch=='20260828-A测缺失补偿' and p.endswith('.csv'):
            add(r,'experiments/_comparisons/legacy-missing-compensation-20260902/raw/'+p[7:],'copy','S5 NPJ-A 原始参照',True)
    elif t:
        add(r,t,'copy','按已锁定资料归属保留相对附件结构；原字节复制',True)
        if not t.startswith('archive/'):
            add(r,'archive/legacy_docs/'+p,'archive_by_parent','旧资料原件保留；由主事务切换')
    elif p.startswith(('docs/','manuscript/')) or (p.startswith('experiments/') and '/results/' in p):
        add(r,p,'retain','已归位的资料及结果保持原位')
# 外部历史整批：不碰外部 worktree，不覆盖当前已有实验文件。
selected={'774f':['20260915-M3Surv-fixed-bank'], '684e':['20260915-population-prototypes'], '2af8':['20260906-NPJ-D消融']}
for r in rows:
    sid=r['source_id']; p=r['path']; parts=p.split('/')
    if sid not in selected or len(parts)<3 or parts[0]!='collab' or parts[1] not in selected[sid]: continue
    add(r,'archive/legacy_collab/source-'+sid+'/'+p[7:],'copy','外部历史原批次完整副本',True)
    if sid=='2af8': add(r,I03+'/results/legacy-r6-20260906/raw/'+p[7:],'copy','D/Dm/旧E1历史证据；保留批次内部相对结构',True)
# r6 脚本相对依赖的两个相邻批次同源完整复制，保持原始脚本可复算。
for r in rows:
    p=r['path']
    if r['source_id']=='2af8' and any(p.startswith('collab/'+b+'/') for b in ('20260902-A测缺失补偿','20260827-三方对比战役')) and '/scratch/' not in p and '__pycache__' not in p:
        add(r,I03+'/results/legacy-r6-20260906/raw/'+p[7:],'copy','r6 同源 E0/E1/S5 参照依赖；不得混用根旧批次',True)
# I04 精确冻结提交，Git blob 逐文件来源。
commit=subprocess.check_output(['git','rev-parse','f2e2358'],cwd=ROOT,text=True).strip()
paths=subprocess.check_output(['git','ls-tree','-r','--name-only','-z',commit,'--','collab/20260907-ProSurv-CAP4-L32'],cwd=ROOT).split(b'\0')
for raw in paths:
    if not raw: continue
    p=raw.decode(); data=subprocess.check_output(['git','show',commit+':'+p],cwd=ROOT)
    r=dict(source_id='git:'+commit,path=p,sha256=hashlib.sha256(data).hexdigest(),size=len(data),type='file')
    for t in ['archive/legacy_collab/source-f2e2358/'+p[7:],I04+'/results/legacy-cap4-20260907/raw/'+p[7:]]:
        add(r,t,'copy','I04 原有 D 版和冒烟历史；不是正式效果实验',True)
        entries[-1]['source']='git:'+commit+':'+p
# 目标跨大小写/Unicode 重复检查；不同来源必须明确，不覆盖。
seen={}
for i,e in enumerate(entries):
    e['id']='asset-'+hashlib.sha256((e['source_id']+'\0'+e['source_path']+'\0'+e['target']).encode()).hexdigest()[:20]
    key=unicodedata.normalize('NFC',e['target']).casefold()
    if key in seen: raise RuntimeError(('target collision',seen[key],e))
    seen[key]=e['id']
    target=ROOT/e['target']
    if e['execute_copy'] and target.exists(): raise RuntimeError('exclusive target already exists: '+str(target))
result=dict(schema_version=1,backup=str(BACKUP),scope='资料子清单；源码、根导航、Git 元数据由主清单覆盖',notes=['所有原始文件字节不改；使用版链接修复另独立记录','archive_by_parent 不由此脚本执行；先完成主门再 rename','I01/I02 既有 results 全部 retain；本脚本不新建其 run'],counts=dict(collections.Counter(e['operation'] for e in entries)),historical_i04_commit=commit,historical_i04_file_count=len([p for p in paths if p]),entries=entries)
with (OUT/'assets-map.json').open('x') as f: json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='entries'},ensure_ascii=False,indent=2))
