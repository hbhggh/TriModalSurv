# Selection / Reporting 实现证据

时间：2026-09-16 19:03:53 JST

## 结论

- [确定] 只新增 `selection.py`、`reporting.py`、`tests/test_selection.py`、`tests/test_reporting.py` 和本报告。
- [确定] `build_candidates(config)` 固定生成 13 个单点 + 45 个组合，共 58 个 spec。
- [确定] `choose_validation(...)` 只接受完整 valid；三参考各 100 格；按 valid 锁定 UCEC/text 例外，返回 6 个选择、58 条候选分数和 5800 条 routed rows。
- [确定] `render_reports(...)` 为纯函数：未完成时只接受空 rows 并输出三份 100 格空表；完成时强制 9×100 test、单批指纹、共享 provenance 后输出三份 Markdown 字符串。
- [确定] 未训练，未读取真实 valid/test 结果，未写正式报告数字，未 commit。

## 接口摘要

```python
build_candidates(config) -> list[dict]  # 58 specs

choose_validation(rows, specs, baseline_rows, config) -> {
    "schema_version": 1,
    "selected": {protocol: locked_spec},       # 5 rules + combo
    "candidates": [candidate_score, ...],      # 58
    "routed_rows": [metric_row, ...],          # 58 × 100
}

render_reports(test_rows, selection, config, *, status, blocker=None) -> {
    "零训练改推理1-5实验结果.md": markdown,
    "seed单位-实验结果.md": markdown,
    "癌症为单位.md": markdown,
}
```

`selected[protocol]["ucec_exception"]` 是 valid 后的最终 bool；test 不重新判。completed metric 行额外要求非空且全批唯一的 `run_fingerprint`。

## TDD 证据

### 初始 RED

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s <R>/tests -v
```

在生产文件不存在时，测试明确报：

```text
RED: selection module is missing: <R>/selection.py
RED: reporting module is missing: <R>/reporting.py
```

### 对抗 RED

首轮实现转绿后新增三项防伪测试，均先失败：

- 57 个 spec 仍可进入选择；
- 同一 checkpoint 内容指纹可跨 seed 复用；
- `complete_max_logit_abs_diff` 为负值仍可报告。

修复后，候选集合必须与 `build_candidates(config)` 的 58 个 spec 完全一致；checkpoint 指纹只能映射一个 cancer-seed 单元；绝对误差必须落在 `[0, logit_atol]`。

### 最终 GREEN

```text
test_selection.py: Ran 6 tests in 0.205s — OK
test_reporting.py: Ran 3 tests in 0.030s — OK
IN_MEMORY_COMPILE_OK=4
```

覆盖：58-spec 结构、严格平局顺序、UCEC/text 五 seed 严格 `>` m0 路由、其余四癌 text 固定 m0、valid/test 隔离、完整格点、NaN/Inf/越界、重复格、三参考、checkpoint/患者数/完整患者 parity、9×100、单批指纹、三份未跑空表、75 格另表、五单点、最差场景、valid 全候选、六位显示与原值标红/Δ。

并行期间运行全目录 discover 曾同时看到其他 Agent 尚未完成的 Torch/runtime 测试；它们不属于本交付的通过声明，整包验收由主 Agent 在全部模块收口后重跑。

## Bug Post-Mortem

### Bug Post-Mortem
- **现象**: 首轮选择器能接受缺少一个组合候选的 57-spec 集合。
- **根因**: 只校验了协议集合与单个 spec schema，没有把输入集合反向绑定到 `build_candidates(config)`。
- **修复**: 比较 58 个 `candidate_id -> spec` 完整映射，任何缺失、额外或参数改变都拒绝。
- **Prevention Rule**: 选择入口必须校验完整候选身份集合，不能只校验协议名和格点完整性。

### Bug Post-Mortem
- **现象**: 首轮 provenance 校验未拒绝跨 seed 复用同一 checkpoint 指纹，报告器也接受负的绝对误差。
- **根因**: 只做了 unit→hash 单向一致性和误差上界，没有检查 hash→unit 唯一性及误差下界。
- **修复**: 新增 checkpoint 反向唯一映射；完整患者绝对误差强制 `[0, logit_atol]`。
- **Prevention Rule**: provenance 校验同时做正向共享和反向唯一；带“absolute/max”语义的诊断量同时检查上下界。

## 文件指纹（测试完成后）

```text
039c1012b059d65b856bf44957fa66a427b81d15a733a063b209f735d656e27c  selection.py
ed7b0497d47af32a96feb67e18dbb2d0692daf66b8fce5733b1a0ec9cbe44456  reporting.py
b9c79c5f038eca2f36372fc2038b3105e1dba127739aedf92d42e8d3191cb9eb  tests/test_selection.py
fbeeda5870ae09aa6ca152520aa3b9945f989d3d58616485d51f4cd24b278d94  tests/test_reporting.py
```

## 独立审核修复（2026-09-16 19:10:53 JST）

### 反例 RED

独立审核提出的三类反例均先在测试中复现：

1. 未启用规则①的规则②–⑤在 UCEC/text 列被错误显示为“固定 m0real”；
2. `n_complete_checked > n_patients`，或同一 cancer/seed/grid 不同协议的检查人数/最大误差不一致，仍能进入选择或 completed 报告；
3. `selected` 的 ID 不在 58-candidate valid 账中，或 λ / UCEC 例外被篡改，仍能 completed。

RED 输出：`test_selection.py` 1 项失败；`test_reporting.py` 7 个 subtest 失败，均对应上述缺口。

### 修复与 GREEN

- UCEC/text 展示按 `enabled_rules` 判断：未启用①为“不适用”；启用①后才区分“启用”与“固定 m0real”。
- 每行强制 `0 <= n_complete_checked <= n_patients`；同格所有协议强制 `(n_complete_checked, complete_max_logit_abs_diff)` 完全一致。
- candidate score 记录 `enabled_rules`；completed 前逐项校验 selected 的 protocol、candidate_id、enabled_rules、λ、α、w、最终 UCEC 例外与 58-candidate valid 账一致。
- 报告测试夹具改为 selected 六项真实存在于 58 条 valid 候选账中，并加入 ID、参数、例外三种篡改拒绝用例。

```text
test_selection.py: Ran 6 tests in 0.226s — OK
test_reporting.py: Ran 4 tests in 0.042s — OK
```

### Bug Post-Mortem
- **现象**: 未启用规则①的单点被报告为 UCEC/text “固定 m0real”。
- **根因**: 展示层只读取最终 bool，没有先判断规则①是否属于 `enabled_rules`。
- **修复**: 三态展示改为“不适用 / 启用 / 固定 m0real”。
- **Prevention Rule**: 条件分支的 false 必须区分“功能未启用”和“功能启用但判定失败”。

### Bug Post-Mortem
- **现象**: 完整患者诊断允许检查人数超过总人数，且同格各协议可填不同检查人数或最大误差。
- **根因**: 仅做单行 null/容差校验，缺少人数上界和跨协议同格一致性约束。
- **修复**: 增加人数上界，并按 cancer/seed/grid 比较诊断二元组。
- **Prevention Rule**: 诊断证据既要单行合法，也要跨同一实验单元保持一致。

### Bug Post-Mortem
- **现象**: completed 报告接受与 58 条 valid 候选账完全不相交的 selected 夹具。
- **根因**: 只分别校验 selected 与候选账的数量/唯一性，没有建立外键和参数一致性。
- **修复**: selected 逐项绑定 valid candidate_id，并核对协议、启用规则、参数与 UCEC valid 决策。
- **Prevention Rule**: 冻结选择必须以 valid 候选账为权威表，报告入口执行外键加不可变字段校验。

### 修复后文件指纹

```text
c1edbeae325d81a0eb4466b8d664f415089bc50dc5c1611c2b6342f3d08f7624  selection.py
594aed63663205599e0b45a0ae12bc456575e0f41d5f4904802a9e3f50d466e6  reporting.py
bce4b55173da7c330f18ed220f3d1c6e688a053678c65c5252e0e37516e1a84e  tests/test_selection.py
9634164af17b49bbf78b12719af1288dbbc25b69318d01d7895a03df4374b3ea  tests/test_reporting.py
```
