# 节点二 Codex 结果审查：逐条处理（`i06-a1a2-20260926`）

- 审查入口：`scripts/codex_review.sh`（companion `adversarial-review`，只读，`gpt-5.6-sol`），`--base c5aa9ea`（冻结 commit S），审结果提交 `3722af1`。
- 原文 `codex-review.json` 只留本地；入库 `codex-review.public.json` 只把仓库根替换为 `<仓库根>`。
- 结论 `needs-attention`：主数字可复算；2 条 high（归因口径、LUAD 探索性）、1 条 medium（敏感性缺患者级证据）。三条全部采纳。两条 high 是核心逻辑问题（因果口径），按 AGENTS.md「自动审查闭环」第 3 条修复、补测后自动复审一次（`round2/`）。

| # | 级别 | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|---|
| 1 | high | A1 − B1 被错误标成单变量对照 | 采纳。核实：研究计划书第 44、69、132、272、369 行（v3.12 起）写明 A1 与 B2 编码规格逐项相同、主对照为 B2；渲染脚本的口径文字与计划书 1.4、4.10、第 7 节、第 12 节仍是 v3.12 以前的旧措辞 | `tools/render_results.py`：口径改为 A1 − B2 主对照、A1 − B1 辅助（常量 `ATTRIBUTION`）；新增「同 encoder 归因」表（A1-S / A1-Z 对 B2、B1 的逐癌 Overall 差与为正癌种数）；癌种结论同时给出对 B2（主）与对 B1（辅）的差，A2 胜出时标“不同 encoder，只作系统级参考”；消融表说明同步。`results/index.md` 归因条目、计划书上述 4 处与 v3.15 修订行同步改正 | `test_render_all_end_to_end_is_deterministic`：结果含 `ATTRIBUTION`、不含旧句；归因表恰为四行，合成数据下 A1-Z − B1 为正 5/5、A1-S − B1（差恰为 0）为 0/5；癌种结论含“（主对照）；对 B1”；消融表含“A1 − B2（同 encoder” |
| 2 | high | 探索性 LUAD 结果被计入未加限定的主胜场 | 采纳。机械门按计划书 3.1 照计五癌不变，另给确认性口径 | `render_results.py`：`EXPLORATORY = ('LUAD',)`；`decide` 增加 `k_confirm`（不计 LUAD）；口径加披露；汇总表加「不计 LUAD（确认性）」列；胜者句写“（不计探索性的 LUAD：k/4）”；汇总表、归因表、检索表、癌种结论与消融表表头标“LUAD（探索性）”，LUAD 小节加说明；`results/index.md` 同步 | `test_winner_rule_counts_wins_first_then_mean_delta_then_order`：`k_confirm` 两例；端到端测试：胜者句含确认性口径，含“### LUAD（探索性）”、汇总表行标记与消融表表头标记 |
| 3 | medium | “test 敏感性为空集”缺少可独立核验的患者级绑定 | 采纳 | 新增 `tools/sensitivity.py`：冻结文本哈希必须等于 freeze manifest 登记值；按候选所用臂剔除 `condense.CAPPED_STATUSES`（退回 / 截断）患者，逐行重算 C-index（剔除集为空取原值），再按 Overall 口径重做判定。输出 `results/i06-a1a2-20260926/evidence/sensitivity.json`（患者级清单、每档案每癌 test 人数与剔除名单、改变行数与最大差、剔除前后 k 与胜者），已登记进 `evidence/evidence-manifest.json`。结果：被标记者 1 人（TCGA-EC-A24G，UCEC，结构化臂 fallback_empty，train；四个已入库特征清单 `i06-smoke-e57d932/evidence/<档案>/feature-manifest.json` 同样记为 train），四档案 test 剔除 0 人、改变 0 行，k 与胜者不变 | 新增 `tests/test_sensitivity.py`：哈希不符即拒绝、只保留 CAPPED 状态；标记者不在 test 时不改变任何行；在 test 时按剩余患者重算，并与独立 numpy 计算相等 |

数值与判定不变：胜者 A1-Z，严格胜 3/5，主 Q 未达标；不计 LUAD 的确认性口径为 2/4。按主对照重新表述的归因：A1 − B2 逐癌 Overall 差为正的癌种，A1-S 4/5、A1-Z 3/5；辅助 A1 − B1 为 1/5、2/5。未做显著性检验。

坑台账：新增 V42（计划书改了对照口径后，渲染脚本与计划书旧段落未同步；新脚本漏迁移旧脚本已有的探索性披露），记在主目录 `docs/engineering/pitfalls.md`。

## 复审（`round2/`，`--base 3722af1`，审修复提交 `e546387`）

结论 `needs-attention`：1 条 high、1 条 medium。复审仍有 high，按 AGENTS.md「自动审查闭环」第 3、5 条停下交用户裁决，不自动进入第三轮。

| # | 级别 | finding | 执行方核实 | 用户裁决（2026-09-26）与处理 |
|---|---|---|---|---|
| 1 | high | 现行约束仍把 A1−B1 写成单变量差 | 成立：计划书第 0 节约束清单（第 40 行）仍写“A1 − B1 为同一 encoder 下浓缩的单变量差”“浓缩文本 ≤200 NeuML token”。首审修复时按整句检索旧措辞，这一行的写法没被匹配到；改用关键词（“单变量”“≤200”）检索全部计划书、结果文档、消融表、index 与渲染脚本，确认只剩这一处现行约束（其余命中为历史修订行、用户批注或已加 v3.12 说明的条目） | 「只修 high」：第 0 节约束清单改为 A1 − B2 主对照、A1 − B1 辅助、LUAD 探索性、浓缩文本不设长度上限且编码不截断（v3.12）；计划书 v3.15 行同步。按用户裁决不做第三轮审查 |
| 2 | medium | 敏感性测试未覆盖实际 run 编排和最终判定 | 成立：测试只覆盖 `flagged_patients` 与单行 `recompute`，没有调用 `run()` | 「medium 不采纳」：本次真实数据 test 剔除 0 人、改变 0 行，敏感性结论与主判定都不依赖 `run()` 里剔除后重算的分支；若以后出现被剔除的 test 患者，再补 `run()` 级测试 |

数值与判定不变。坑台账 V42 已补“按关键词而非整句检索旧措辞”。
