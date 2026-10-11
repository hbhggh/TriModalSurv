# 节点二首审处理（审查对象：dev 98cf7d6f，--base main；正式结果 i07-ps3-20261011）

- 审查原文：`codex-review.json`（本地），入库版 `codex-review.public.json`。审查由主控经 Terminal 面板自动发起（用户 2026-10-11 要求自动化）。
- 结论：needs-attention，1 high。审查确认授权摘要可复算、指标汇总正确。

| # | 级别 | finding | 处理 | 修复位置 | 验证 |
|---|---|---|---|---|---|
| 1 | high | 授权只绑定评测输入，未绑定输出；逐病人预测未入库，无法独立复算 C-index 与填充等价检查 | 采纳（不重跑任何任务；ckpt 与原始输出仍在 landau） | 新增只读核对 `verify_outputs.py`：100 个运行齐全；run.json commit = S 且 dirty=False；test_metrics 身份与路径一致、best_epoch 与 run.json 一致；preds 病人恰为该折 test 划分（splits.csv，sha256 与 manifest 一致）；time/event 与 cohort.csv 逐人一致；用独立逐对 Harrell 实现重算全部 250 项 C-index 必须完全相等；填充差极差 ≤ 1e-5。产出 `results/i07-ps3-20261011/verify/`：`output_manifest.json`（200 个输出文件 sha256）、`preds_test_all.csv`（全部逐病人风险分入库）、`verify_report.json` 与 results_digest = sha256(授权摘要 + commit + 输出 manifest 哈希) | landau 原件 sha256 与本地副本 200/200 一致；核对全部通过（250 项重算相等、极差 1.31e-6、宏平均 0.6807）；变异检查：换入别折预测 → "病人不等于该折 test 划分"，某项指标 +1e-9 → "重算不一致"；`tests/test_verify_outputs.py`：独立实现与 survival.c_index 在大量风险 / 时间并列的随机数据上 20 组完全相等 |

## 局限（如实记录）

输出 manifest 是评测结束后由服务器原件生成，不是评测进程当场写出；它能排除"回传后改写 / 混入旧结果"（200 个文件哈希与服务器原件一致，且每项指标都能从入库的逐病人预测独立重算、病人恰为对应 test 划分），但不能排除"服务器上在评测与生成 manifest 之间被改写"——后者需要同时伪造与指标自洽的逐病人预测。评测进程当场写输出哈希留给下一轮代码改进，不为此重跑本轮。
