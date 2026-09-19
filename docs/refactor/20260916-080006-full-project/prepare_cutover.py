from pathlib import Path
import json
r=Path.cwd();b=r/'docs/refactor/20260916-080006-full-project';pairs=[]
for src,dst in [('NPJ','archive/legacy_npj_snapshot/root-repository-20260916-080006'),('code','archive/legacy_npj_snapshot/root-code-20260916-080006'),('collab','archive/legacy_collab/root-20260916-080006')]:pairs.append((src,dst))
for name in ['innovation- computation','innovation-transfomer','Office viewer-fix-bug(outline &refresh )','diagrams','image','NPJ-A&NPJ-B区别.md','how-to-refactor-japanese-in vscode.md','explain-advantage&dis~-vscode.md','exam.docx','论文初版本.docx','paper.tex','manuscript/bbag124_word']:
 pairs.append((name,'archive/legacy_docs/root-20260916-080006/'+name))
for name in ['.DS_Store']:
 if (r/name).exists():pairs.append((name,'archive/runtime_artifacts/root-20260916-080006/'+name))
for p in (r/'manuscript/bmc_initial_draft').iterdir():
 if p.suffix in ['.aux','.log','.out','.gz']:pairs.append((str(p.relative_to(r)),'archive/runtime_artifacts/'+str(p.relative_to(r))))
with (b/'cutover-plan.json').open('x') as f:json.dump([{'source':s,'target':t,'operation':'move'} for s,t in pairs],f,ensure_ascii=False,indent=2)
print(len(pairs))
