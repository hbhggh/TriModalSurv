# 节点一复审（round2）：逐条处理

- 审查对象：候选 H = dev `ab17658`（首审修复后）
- 结论：`needs-attention`。Codex 确认首审的 skip_test 与未知状态两处修复有效，另提出 2 条 high
- 按 AGENTS.md「自动审查闭环」第 5 条：复审仍有核心逻辑问题 → **停下交用户裁决**，不自动进入第三轮

| # | 级别 | 问题 | 执行方评估 | 建议的最小修法 |
|---|---|---|---|---|
| R1 | high | 同一份授权仍可以跑多套 test campaign：正式 test 允许用 CLI 改 `--retrieval-backend` / `--batch-size` / `--cpu-threads` / GPU，runtime 不同，「结果确定」这一前提不成立 | 成立。runtime 覆盖确实可以产生（数值上极小的）不同结果，理论上留下择优空间 | test 阶段禁止这几个 runtime 覆盖参数（只用 config 的锁定值），同时把规范化后的 `ucfg.runtime` 摘要写进授权。这样 ckpt、源码、runtime 全部锁定，重复跑的结果相同。**不做**仓库外的全局原子消费账本 |
| R2 | high | 质量报告可以把旧的抽查结论套到新记录上：`score` 从 flags 复制新的 records_sha256，但不核对抽查表内容是否来自这份记录 | 成立。记录重新生成、患者集合不变时，旧抽查表会被误认成新记录的抽查结果 | `write_sheet` 每行写入 `records_sha256` 列，`score` 要求每一行都等于 flags 的 records_sha256，否则拒绝。质量报告再绑定抽查表文件的 sha256。补「新 flags + 同患者旧 sheet 必须拒绝」的测试 |

## 用户裁决（2026-09-26）

用户选择「最小修法后放行」：按上表的最小修法修两处，补测、CI 绿灯后放行，**不发起第三轮审查**，不做全局消费账本。

## 处理结果

| # | 处理 | 修复位置 | 补测 |
|---|---|---|---|
| R1 | **采纳（最小修法）**。`_validate_args` 在 test 阶段拒绝 `--retrieval-backend` / `--batch-size` / `--cpu-threads`，只用 config 锁定值；新增 `runtime_digest(ucfg)`（不含阶段名与物理卡号），preflight 会打印它，用户授权必须写入 `runtime_sha256`，由 `check_test_gates` 核对。ckpt、源码、runtime 全部锁定后，重跑 test 结果相同。全局消费账本不做（用户裁决） | `experiments/I05_text_encoder_bcmbert/evaluate.py`；`README.md` 授权格式 | `test_argument_rules`：a1struct200 的 test 阶段带三个覆盖参数中的任意一个都拒绝；`test_test_gates`：授权 runtime 摘要不符、换 runtime 复用旧授权都拒绝；`test_runtime_digest_ignores_gpu_id_but_binds_runtime`：换卡摘要不变，换后端或 batch 摘要改变 |
| R2 | **采纳（最小修法）**。`write_sheet` 每行写入生成时的 `records_sha256`；`score` 要求每行都等于当前 flags 的 records_sha256，否则拒绝并提示重新生成、重新填写；质量报告另记录 `sheet_sha256` | `experiments/I06_llm_condensation/verify.py` | `test_score_rejects_old_sheet_for_regenerated_records`：记录重新生成（患者集合不变）后，用旧表加新 flags 会被拒绝 |

## 测试

- I06 + I05（test_i06_profiles / test_strategy0_and_replay）：77 passed
- 全仓 `scripts/ci.sh`：429 passed / 6 skipped，CI PASS

## 残余风险（已知、接受）

- 手工改写抽查表的 `records_sha256` 列，或手工伪造授权记录，属于人为违规，门禁不防；授权记录由用户本人书写。
- 同一套锁定条件下，GPU 数值的非确定性只有浮点级，不构成择优空间。
