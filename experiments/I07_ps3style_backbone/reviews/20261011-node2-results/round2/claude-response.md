# 节点二复审处理（审查对象：dev ca7802a3，--base main）

- 审查原文：`codex-review.json`（本地），入库版 `codex-review.public.json`；由主控经 Terminal 面板自动发起。
- 结论：needs-attention，1 high。复审仍有核心问题 → 按 AGENTS.md「自动审查闭环」第 5 条停下交用户。
- **用户裁决（2026-10-11）**：「修完用测试兜底，然后收尾」——修复并补测，不开第 3 轮。

| # | 级别 | finding | 处理 | 修复位置 | 验证 |
|---|---|---|---|---|---|
| 1 | high | results_digest 未绑定入库的 preds_test_all.csv（CSV 哈希只在 verify_report 里，报告本身不进摘要） | 采纳 | `verify_outputs.py`：results_digest = sha256(核对协议 `I07-verify-v1` + 授权摘要 + commit + output_manifest.json + preds_test_all.csv + 逐运行指标规范化 JSON)；报告收录逐运行指标；新增 `--recheck <verify 目录>`，只凭入库 CSV / manifest / 报告从 CSV 独立重算全部 C-index、宏平均、填充差极差与 results_digest，逐项须等于报告；生成后立即自检。重新生成 `results/i07-ps3-20261011/verify/`，results_digest = `b71bccf8…`（CSV 字节未变，sha256 仍为 1dfe01a0…） | `tests/test_verify_outputs.py`：入库产物复核通过；改一个风险分（+1e-9，不改变排序）、改一个生存时间、删一行——即使同时把报告里的 CSV 哈希改成新值，复核仍失败；改报告的 results_digest → 失败 |

不重跑任何训练 / 评测，数字不变（三模态宏平均 0.6807）。
