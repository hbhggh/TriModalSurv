from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
assert (B/'cutover-operations.jsonl').exists()
# 保存 STATUS 三阶段，旧内容只允许 repair_links.py 的目标跨度变化。
status=ROOT/'STATUS.md'
(B/'STATUS.before-links.bin').write_bytes(status.read_bytes())
subprocess.run(['python3','-B',str(B/'repair_links.py')],cwd=ROOT,check=True)
(B/'STATUS.after-links.bin').write_bytes(status.read_bytes())
append='''\n\n## 2026-09-16｜全项目结构化重构\n\n公共代码归 `src/trimodalsurv/`，I01–I04 各有模型、配置、知识与结果入口；旧源码/资料/批次移至 `archive/`，外部 MCAT/PORPOISE 保持独立。\n\n- [项目结构](docs/project-structure.md) · [逐项执行证据](docs/refactor/20260916-080006-full-project/progress.md)\n- [I01 知识](experiments/I01_patient_retrieval/knowledge/index.md) · [I02 知识](experiments/I02_population_prototypes/knowledge/index.md)\n- [I03 知识](experiments/I03_npj_d_dm_e1/knowledge/index.md) · [I04 知识](experiments/I04_cap4_multi_prototypes/knowledge/index.md)\n- [历史汇总复算](docs/refactor/20260916-080006-full-project/history-derived-03/summary.json)\n\n本轮仅重构与 CPU 兼容验证，没有新增正式训练。I04 只整理已有 D 版，C 版仍未实现；历史比较不是匹配训练协议的机制消融。具体通过范围、旧 skip 与审核结论以本轮证据为准。\n\n本次旧正文仅修链接，删除线及科研判断保留；从此继续只在末尾追加。\n'''
with status.open('ab') as f:f.write(append.encode())
assert status.read_bytes().startswith((B/'STATUS.after-links.bin').read_bytes())
(ROOT/'README.md').write_text((B/'README.next.md').read_text())
rule_changes=[]
for filename in ['AGENTS.md','CLAUDE.md']:
 p=ROOT/filename;before=p.read_text();after=before.replace('collab/pitfalls.md','docs/engineering/pitfalls.md').replace('NPJ/scripts/train_launcher.py','scripts/train_launcher.py').replace('NPJ/scripts/launch_formal.sh','scripts/launch_formal.sh')
 # 原collab具体历史证据现在在完整原件目录。
 after=after.replace('collab/', 'archive/legacy_collab/root-20260916-080006/')
 if before!=after:
  p.write_text(after);rule_changes.append({'path':filename,'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'kind':'path-only'})
(B/'rule-path-changes.json').write_text(json.dumps(rule_changes,indent=2))
p=ROOT/'.gitignore'
with p.open('a') as f:f.write('\n# 全项目重构：原始归档/仓库元数据/本轮传输包保留磁盘，不进源码提交。\n/archive/\n/docs/refactor/**/*.tar\n/docs/refactor/**/*.index\n/docs/refactor/**/*.bin\n/docs/refactor/**/validation-evidence/**/*.pt\n')
p=ROOT/'.ignore';s=p.read_text();s=s.replace('!/NPJ/','').replace('# ripgrep / Better Todo Tree：搜索嵌套的 NPJ 开发目录。','# ripgrep / Better Todo Tree：搜索当前公共代码与实验实现。').replace('# .gitignore 仍负责让外层仓库不跟踪 NPJ；这里只调整搜索范围。','# 历史归档和原始结果不进入默认源码搜索；Git 规则另由 .gitignore 管理。');p.write_text(s+'\n/docs/refactor/**/history-derived-*/\n')
p=ROOT/'.vscode/settings.json';settings=json.loads(p.read_text());exclude=settings.setdefault('search.exclude',{});exclude.update({'archive/**':True,'experiments/**/results/**/raw/**':True,'experiments/**/results/**/checkpoints/**':True,'**/__pycache__/**':True});p.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
ledger=ROOT/'docs/engineering/pitfalls.md'
old=ledger.read_bytes()
addition='\n\n## 全项目重构补充（2026-09-16）\n\n| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |\n|---|---|---|---|\n| R1 | 入口拆分后提前返回绕过 set_seed，模块测试无法发现运行初始化差异。 | 对真实入口验证参数解析→随机初始化→目标分发顺序，配置与显式CLI两条路径均覆盖。 | docs/refactor/20260916-080006-full-project/progress.md |\n| R2 | 按报告目录搬结果漏掉相邻历史对照文件，副本不能独立复算。 | 结果保全按实际读取依赖闭包核验，并在禁用旧来源的条件下复算。 | docs/refactor/20260916-080006-full-project/progress.md |\n'
with ledger.open('ab') as f:f.write(addition.encode())
new=ledger.read_bytes();assert new.startswith(old)
(B/'ledger-append.json').write_text(json.dumps({'file':str(ledger.relative_to(ROOT)),'before_bytes':len(old),'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(new).hexdigest()},indent=2))
print('NAVIGATION_UPDATED')
