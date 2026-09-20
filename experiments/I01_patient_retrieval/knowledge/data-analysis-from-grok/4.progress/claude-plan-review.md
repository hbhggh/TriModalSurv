# Claude 计划审核记录

## 审核状态

| 项 | 记录 |
|---|---|
| 审核对象 | `研究计划.md`、`给Claude的审核说明.md` |
| 审核方式 | 本机 Claude Code CLI，只读 `--permission-mode plan` |
| 时间 | 2026-09-17（Asia/Tokyo） |
| 结果 | **阻断：未获得 Claude 审核结论** |
| CLI 原始错误 | `Failed to authenticate: OAuth session expired and could not be refreshed` |

## 门禁结论

- `DECISION: BLOCKED`：不是 Claude 的 `PASS`，也不是其对计划的 `CONCERNS`；本次没有可用的审核文本。
- 因“Claude 计划通过才许评测”的锁定约束，未创建 `precondition.md`，未写路由代码，未执行 valid 或 test。
- 待 Claude OAuth 会话恢复后，重新发起同一份只读计划审核；在获得明确 `PASS` 前不得越过本门。

---

## 恢复 OAuth 后的只读审核原文

```text
DECISION: CONCERNS

| 审核项 | 结论 | 证据／阻断原因 |
|---|---|---|
| 路由一致性 | PASS | 3.progress 的 route_patient 与锁定路由表逐行一致：text_100→m0real；rna_100/both_100→m1；none 缺RNA→m1；none 仅缺Text或无缺失→upstream_combo；非LUAD→upstream_combo。S0-force 只把 enabled 冻结为 true。 |
| 复用与写保护 | CONCERNS | 必须在 precondition 明确列出 valid 复用凭据、远端执行根和写入白名单，并登记 2.progress、3.progress 的前后 SHA。 |
| 泄漏与声称边界 | CONCERNS | 必须将 valid 反对仍强制启用、按场景切到固定基线、逐格平局和按已见 test 选择的事实写入冻结文件、报告开头和 postcondition。 |

最终结论：允许进入 precondition、代码与评测阶段。条件是 C3–C9 必须先写进 precondition.md，并在代码或测试里做成硬断言（C1、C2 在代码阶段一并落实）；任何一条没有落实，就不得跑 valid 或 test。
```

## Claude 条件清单（本轮强制）

| 编号 | 条件 | 落点 |
|---|---|---|
| C1 | LUAD `rna_100`／`both_100` 必须逐格等价固定 m1，`text_100` 必须逐格等价固定 m0real；`none` 记录逐患者路由计数。 | 单元测试、运行后断言与报告。 |
| C2 | 非 LUAD 的复用记录标注 `route=upstream_combo`、`strategy0_enabled=null`，不得写作 `false`。 | 合表与审计序列化。 |
| C3 | 复用 valid B 前登记 3.progress valid 完整产物、代码、source/asset hash；理由限定为它本来就在 `enabled=true` 下运行。 | `precondition.md`、冻结文件。 |
| C4 | 写明本机和 Tako 的新执行根及写入白名单，且均与 2.progress／3.progress 目录不同。 | `precondition.md`。 |
| C5 | 运行前后都核验 2.progress、3.progress 的归档哈希。 | `precondition.md`、`postcondition.md`。 |
| C6 | 核验 Tako 上游副本与本机归档哈希一致，才允许声称逐格复用。 | 运行门证据。 |
| C7 | 归因固定为“LUAD 按场景切换到 m1/m0real”，不能简化为“少检索、改走 m1”。 | 冻结文件与所有结果报告。 |
| C8 | 报告逐场景平局：`rna_100`／`both_100` 为 m1 副本、`text_100` 为 m0real 副本；这些由已见 test 启发。 | 总结果与 seed／癌种报告。 |
| C9 | `frozen-routing.json`、三份结果报告、`postcondition.md` 都显式写 valid B−A<0 的强制启用与 test 泄漏；4/5 仅为探索性反事实，不是效果验收。 | 全部结果文件。 |
