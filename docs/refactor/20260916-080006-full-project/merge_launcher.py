from pathlib import Path
import ast
p=Path('scripts/train_launcher.py');root=p.read_text();merged=Path('docs/refactor/20260916-080006-full-project/launcher-threeway.py').read_text()
def region(s,name):
 for n in ast.parse(s).body:
  if isinstance(n,(ast.Assign,ast.AnnAssign)):
   ns=n.targets if isinstance(n,ast.Assign) else [n.target]
   if any(isinstance(t,ast.Name) and t.id==name for t in ns):return n
 raise ValueError(name)
n=region(root,'ARM_PRESETS');lines=root.splitlines(True);presets=''.join(lines[n.lineno-1:n.end_lineno]);presets=presets.replace('= {','= {\n    "population": {"network_type": "NPJC", "compensator": "population", "extra_args": ()},',1)
n=region(merged,'ARM_PRESETS');lines=merged.splitlines(True);lines[n.lineno-1:n.end_lineno]=[presets+'\n'];merged=''.join(lines)
merged=merged.replace('EVAL_FORWARDED_OPTIONS: Tuple[str, ...] = ("--fusion_type", "--prototype-k")','EVAL_FORWARDED_OPTIONS: Tuple[str, ...] = ("--fusion_type", "--proto_per_bin", "--bin_mode", "--prototype-k")')
merged=merged.replace('{"none", "capr", "bank", "population"}', '{"none", "capr", "capl", "bank", "population"}')
compile(merged,str(p),'exec');p.write_text(merged)
# 入口先做无副作用参数预读，然后交由实验解析器，避免公共解析器拒绝特有参数。
for filename,kind in [('main_survival.py','train'),('eval_missing.py','evaluate')]:
 p=Path('scripts')/filename;s=p.read_text();needle='def main():\n';insert='''def main():
    import argparse
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument('--compensator')
    selected, _ = probe.parse_known_args()
    if selected.compensator == 'population':
'''
 if kind=='train':insert+='''        from experiments.I02_population_prototypes.train import parsing_args, main as run
        return run(parsing_args())
'''
 else:insert+='''        from experiments.I02_population_prototypes.evaluate import parse_args as parse, run_evaluation as run
        run(parse())
        return 0
'''
 s=s.replace(needle,insert);p.write_text(s)
