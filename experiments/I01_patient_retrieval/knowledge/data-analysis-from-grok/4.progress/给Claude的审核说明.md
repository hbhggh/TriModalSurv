# Claude 计划审核说明：S0-force（仅 LUAD 路由）

## 审核对象与权限

请只读审核以下文件：

- `4.progress/研究计划.md`
- `2.progress/result` 的冻结组合及固定参考记录
- `3.progress/result` 的路由实现、valid 审计和关闭开关的 test 记录

禁止修改任何文件、启动评测、训练、下载数据或创建 checkpoint。请不要建议重训、扩 seed、新架构、调 λ/α/w，或改 BLCA；这些均不在本轮范围。

## 3.progress 的三层原因

| 层 | 已归档事实 | 本轮如何处理 |
|---|---|---|
| ① 设计 | 路由依据已见 test 提出，却仍用 valid 的 `B>A` 否决；valid 与 test 的符号相反。valid A=0.654042，B=0.645226，B−A=−0.008815。 | 明确承认 test 泄漏；valid 只作审计，不再拥有关闭权。 |
| ② 代码 | `3.progress` 按字面正确执行 `enabled = (B>A)`。 | 不重写路由表，仅把冻结规则改成布尔 `enabled=true`。 |
| ③ 结果 | 开关关闭后，LUAD test 全格 `strategy0_enabled=false`，100 格组合与上游组合恒等。 | 本轮禁止复用其 LUAD test，只重算强制启用后的 LUAD 20 格。 |

## S0-force 与原 B>A 门禁的差异

| 项 | 3.progress | 4.progress S0-force |
|---|---|---|
| valid A/B | 计算 | 仍计算并完整记录 |
| 冻结规则 | `enabled = (B>A)` | `enabled = true` |
| valid 的作用 | 有权关闭路由 | 仅泄漏审计 |
| LUAD test | `enabled=false`，因此等于上游组合 | 必须 `enabled=true`，只允许一次冻结 test |

## 锁定路由表

| LUAD 场景／实际缺失 | 动作 |
|---|---|
| `text_100` 整场景 | 固定 m0real；不检索、不填借来 Text。 |
| `rna_100` | 固定 m1；禁止检索；pooling 与 m1 相同。 |
| `both_100` | RNA 与 Text 均固定 m1；禁止检索；pooling 与 m1 相同。 |
| `none` 仅天然缺 RNA | RNA 固定 m1。 |
| `none` 仅天然缺 Text／无缺失 | 保持上游冻结组合（`λ=1,w=0.5`）。 |
| `none` 天然双缺 | 双模态固定 m1。 |

非 LUAD 必须复用 `2.progress` 的冻结组合；不改变 donor、λ、α、w 或 UCEC 例外。固定 m1/m0real 也必须逐格复用 `2.progress`。

## 必须保留的泄漏声明

该路由由已见 test 结果启发，而 valid 明确反对启用（B−A<0）仍强制开启。因此本轮不是盲测或独立确认；即使 LUAD 及五癌胜率改善，也只能表述为“少检索、改走 m1 的探索性反事实”，不能表述为患者检索机制有效。

## 请只回答的审核问题

1. S0-force 的“强制启用”是否与上述逐行路由表一致，且是否没有偷偷改变 BLCA、λ、α、w、seed、权重、缓存或 split？
2. 复用边界是否明确：只能复用 `3.progress` valid（哈希一致时），禁止复用其 `enabled=false` 的 LUAD test；非 LUAD、m1、m0 必须来自 `2.progress`？
3. 泄漏声明、阻断条件和结果报告边界是否足以防止把 4/5 误写成患者检索机制成立？

请以以下格式输出：

```markdown
DECISION: PASS | CONCERNS

| 审核项 | 结论 | 证据／阻断原因 |
|---|---|---|
| 路由一致性 | PASS/CONCERNS | ... |
| 复用与写保护 | PASS/CONCERNS | ... |
| 泄漏与声称边界 | PASS/CONCERNS | ... |

最终结论：允许／不允许进入 precondition、代码与评测阶段。
```

