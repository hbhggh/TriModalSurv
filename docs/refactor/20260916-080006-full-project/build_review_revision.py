from pathlib import Path
import tarfile,difflib,json,hashlib
R=Path(__file__).resolve().parents[3];B=Path(__file__).parent
text='''请以 Claude 独立审阅本次全项目重构增量。上一轮结论 REVISE，F1–F12下列逐项修复。只审阅，不执行命令、不修改文件。本次不训练真实患者、不GPU、不安装。请判断这些必要项是否真正闭环，检查新增run记录是否改变模型计算或违反不覆盖历史合同。最后给 JSON {verdict: PASS|REVISE, required_changes:[], limitations:[]}。不要因测试绿而忽略入口问题，也不要要求未经授权的新科研方案/训练。根切换尚未执行；代码通过后才可逆移动并另交最终资产证据审阅。
F1/F2: population先解析→set_seed→run；真实scripts分发测试含配置-only，显式CLI优先。
F3:根/非根CLI预检完整JSON相等，增加I03/I04显式preset和I02公共入口。
F4:experiments-report.md已实际落盘，末尾附全文。
F5:actual_model_spec对fusion实际类名回读；NPJC没有fusion时不改变I01 exact spec。
F6:runtime_source_fingerprints冻结src/实验/脚本保守源码超集+实际配置，I02标签指纹也入。
F7:real worker各侧evidence/imports及环境JSON已取回，worker manifest22文件；原患者ID/hash指纹保留，不在审阅摘要中泄露患者数据。
F8:bin_mode等号形式和不重复追加已有回归。
F9:调用真实runtime.load_model与I03工厂比较类型、组合、state_dict shape/dtype。
F10:I03/I04配置可显式--preset，不自动挑选；Dm evaluation m1仍复用D ckpt，不假造训练机制。
F11:progress已更新阶段，未切换/未复审明确。
F12:明确完整checkout，缺model/gpu配置报错。src安装包只库。
额外：新运行独占run目录记录pending→completion，真实参数及来源清单齐全；checkpoint命名不变，预测CSV与plots按seed+完整task身份隔离，产物先预检拒绝已有，主进程独占写。不重训历史；历史best_metric=0等问题保留科研语义，不借重构改结果。
验证范围：I01/I02模型及填补算子未变，旧新32患者16格最大误差0；7组合成forward/loss/grad/optimizer+严格重载最大误差0；25个I02strict load通过。此次改入口/记录，新增相关测试，旧6skip不增skip掩盖。
以下是冻结v3到当前完整源码差异及新增测试，后附实际验证证据。
'''
with tarfile.open(B/'candidate-v3.tar') as t:
 old={m.name.removeprefix('project/'):t.extractfile(m).read().decode() for m in t.getmembers() if m.isfile()}
for rel in ['src/trimodalsurv/config.py','src/trimodalsurv/training/runtime.py','src/trimodalsurv/training/model_util.py','experiments/I02_population_prototypes/train.py','scripts/main_survival.py','scripts/train_launcher.py','experiments/I03_npj_d_dm_e1/config.yaml','pyproject.toml','tests/test_script_dispatch.py','tests/test_experiment_presets.py','tests/test_run_provenance.py','experiments/I02_population_prototypes/tests/test_population_early_stopping.py']:
 after=(R/rel).read_text();text+='\n### '+rel+'\n```diff\n'+''.join(difflib.unified_diff(old.get(rel,'').splitlines(True),after.splitlines(True),fromfile='v3/'+rel,tofile='current/'+rel))+'\n```\n'
for rel in ['experiments-report.md','validation-evidence/new-v6-tests.log']:
 text+='\n### '+rel+'\n'+(B/rel).read_text()+'\n'
rows=json.loads((B/'validation-evidence/cli-preflight-v6.json').read_text());assert all(x['exit']==0 for x in rows)
text+='\nCLI 22命令退出码：'+json.dumps([x['exit'] for x in rows])+'；完整runtime/model跨cwd相等断言已在driver正常退出前执行。\n'
for rel in ['cutover.py','audit_assets.py','finalize_navigation.py']:
 text+='\n### 待执行归位脚本 '+rel+'\n```python\n'+(B/rel).read_text()+'\n```\n'
(B/'code-review-revision-prompt.md').write_text(text)
print(len(text),hashlib.sha256(text.encode()).hexdigest())
