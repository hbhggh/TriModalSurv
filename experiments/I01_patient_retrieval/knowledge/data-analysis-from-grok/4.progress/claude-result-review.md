# Claude 云端结果与代码审核

## 元数据

| 项目 | 值 |
| --- | --- |
| 审核方式 | Claude Code（Opus，高 effort，只读、plan 权限） |
| 审核范围 | `4.progress`，只读对照 `2.progress/result` 与 `3.progress/result` |
| 允许操作 | Read、只读 Bash；禁止写入、训练、评测、联网 |
| 审核结论 | **CONCERNS（无阻断项）** |

## 原文结论

> 代码、工件、数字这三块都通过。问题只在结果 MD 的表述上：4/5 的说服力比文字给人的印象弱，有两句话写得不对。

### 已通过的独立核验

- 未发现训练、权重/缓存改写或新 checkpoint；前向使用 `inference_mode`，每 seed 检查 state_dict，运行前后核对 74 项资产哈希。
- `enabled=true` 与 `valid_decision=audit_only` 被配置和运行器锁定；路由与 3.progress 的 enabled=true 分支逐状态一致；12/12 单测通过。
- `complete.json` 为 `COMPLETED`：300 个汇总行、20 个 LUAD 执行行、100 条 retrieval 参考；20 个 LUAD 单元工件哈希一致。
- 172 人 × 20 个 LUAD 审计均为 `enabled=true`：`rna_100`/`both_100` 全走 m1，`text_100` 全走 m0real；`none` 为 167 个完整患者与 5 个仅缺 Text 患者，均走组合。
- 200 个 m1/m0 与 2.progress 一致；80 个非 LUAD 组合与 2.progress combo 一致且 `enabled=null`；LUAD rna/both 的 10 格与 m1 逐 logit 一致，且相对 3.progress 均不同；LUAD text 与 m0real、none 与组合一致。
- Claude 以 NPZ 中 `risk_b` 复算 20 格 C-index，均一致。
- 主表 `0.640506 / 0.631824 / 0.630751`、75 格人工缺失表、4/5、BLCA 未胜、3.progress 的 3/5 与 valid `B-A=-0.008815` 均复算一致；不存在将结果写成患者检索机制成立的越界结论。

### 非阻断 concerns（必须纳入报告修订）

1. LUAD 相对 m1 只高 `0.0000351`，4/5 完全依赖这一极小差值；应明确为“近似平局、不稳”，且此提升是 test 驱动的场景式基线切换。
2. LUAD test 的 `none` 没有天然缺 RNA，因此该分支触发 0 次；从 3/5 到 4/5 的变化仅来自 `rna_100`/`both_100` 改走 m1；`text_100` 相对 3.progress 没变化。
3. 总报告的“LUAD-m1-force关闭时”及“4/5目标未达”两句与本轮强制开启、已达 4/5 的实际状态矛盾，需修正。
4. `reporting.py` 将“4/5”与“3/5”写死，需由实际汇总结果生成。
5. 本轮远端源码哈希未写入 `complete.json` 或 preflight；需补充代码/配置指纹，不能把它误称为已由正式工件证明。
6. “LUAD-m1-force 组合”作为列名覆盖非 LUAD 的上游复用行，需增加复用边界说明。

## 后续处理状态

上述 concerns 均不触发重训、改 seed、改 BLCA、改 lambda/alpha/w 或追加 test。仅允许修订报告生成逻辑与结果表述；修订后需再次只读审核代码及文档。
