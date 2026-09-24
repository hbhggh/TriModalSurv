# Codex 节点二结果审查逐条处理（`i05-a0-20260924`）

- 审查入口：`scripts/codex_review.sh`（companion `adversarial-review`，只读，`gpt-5.6-sol`），`--base 3c46f37`（冻结 commit S），审结果提交 `0b8d3a7`。
- 原文 `codex-review.json` 只留本地；入库 `codex-review.public.json` 只把仓库根替换为 `<仓库根>`。
- 结论 `needs-attention`：数值、Q = 2/5、commit/tag、H→S tree 换绑、25 个 git.json、门记录哈希与脱敏证据均可核；1 条 **medium**，无 high / critical。

| # | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|
| 1 | 同一结果被同时解释为“含重训方差”和“纯 Text 管线效应” | 采纳 | `tools/render_encoder_tables.py`：重训方差口径按档案区分（`RETRAIN_NOTES` / `BOUNDARY_NOTES`）。bcmbert200 保持轮 C 原文，逐字节不变；bcmbert8192 改为“冻结环境下 legacytext-rerun 25/25 重训 ckpt 与历史 E0 逐字节相同，未观察到重跑漂移，Δ 可视为配对的单一 Text 管线变更；这不是训练完全确定的证明，基线复用且 LUAD 路由受已见 test 启发，仍属探索性结果”。账本与论文目录 5.x 的三份表按新文字重新渲染。STATUS、结果索引、研究计划书第 7–8 节与坑台账 I05-16 统一为同一口径，删去“完全确定”“重训方差为 0”“纯 Text 管线效应”的说法 | `test_a0_documents_are_script_output`：账本与论文目录必须等于脚本渲染，且 A0 两份结果表含“未观察到重跑漂移”、不含“重训方差”；轮 C 文档测试照常通过（bcmbert200 输出不变） |

按 AGENTS.md「自动审查闭环」第 3 条，这条是 medium，只改解释文字和渲染文案，不改运行逻辑，不属于核心逻辑问题，因此不复审。数值与 Q 判定不变。
