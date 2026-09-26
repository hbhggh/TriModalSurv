# 节点一 Codex 首审：逐条处理（I06 · A1 LLM 浓缩）

- 审查对象：候选 H = dev `5ab2ca3`，相对 `main`（merge-base `20bbe6a`）的分支 diff
- 首审原文：`codex-review.json`（本地保留）/ `codex-review.public.json`（仓库根替换为 `<仓库根>`，其余不变）
- 结论：`needs-attention`，3 条 high。三条都属于核心逻辑（test 泄漏、质量门可被绕过），全部采纳，修复后按闭环复审一次（`round2/`）

| # | 级别 | 问题 | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|---|
| 1 | high | 正式 test 授权没有绑定 ckpt 集合，可以复用 | **采纳**。用户授权记录新增两个必填键 `checkpoints_sha256`（本轮 ckpt 集合摘要 `digest_json(checkpoints)`）和 `assets_lock_sha256`，preflight 会打印这两个值。换一套 ckpt 或换资产锁必须重新授权。**未采纳的部分**：跨目录的全局消费账本（原子消费 evaluation_id）。理由：同一套 ckpt 加同一份源码，test 结果是确定的（I05 回放逐位相同），重复跑拿不到择优空间；四个候选各跑一次 test 是计划书 3.1 预先登记的选择规则，四个候选的结果全部报告。全局账本属于防不了算错、也防不了泄漏的额外工程，按用户「避免工程陷阱」的约束不做 | `experiments/I05_text_encoder_bcmbert/evaluate.py` `check_test_gates`、test 入口调用、preflight 打印；`README.md` 授权格式 | `test_strategy0_and_replay.py::test_test_gates` 新增负例：授权里的 ckpt 摘要或资产锁不符 → 拒绝；用另一套 ckpt（摘要不同）复用旧授权 → 拒绝 |
| 2 | high | 正式评测门没有核实训练时真的用了 `--skip_test` | **采纳**。`training_contract.runtime_by_profile` 为 a1struct200 / a1summ200 / a2struct200 / a2summ200 要求 `skip_test: true`；`check_training_record` 按实际 run 的 `resolved_config.runtime` 核对，缺失或为 false 都拒绝。已收官的 I05 档案不追溯 | `experiments/I05_text_encoder_bcmbert/config.yaml`、`evaluate.py` `check_training_record` | `test_i06_profiles.py::test_i06_training_record_requires_actual_skip_test`：四个档案在缺 skip_test 和 skip_test=false 时都报 `['skip_test']`；为 true 时通过参数门；bcmbert200 不受影响 |
| 3 | high | 冻结门接受没有绑定的质量报告，也接受未知状态 | **采纳**。`flag_records` 输出 `records_sha256`（按 patient_id 排序后整臂记录的摘要）；`score` 透传它，并写出 `audit_patients`，同时核对抽查表臂别；`freeze.check_quality_binding` 要求 arm、records_sha256、checked 数、audited 数、抽查患者集合（`audit_sample` 的确定性结果）全部一致；`obvious_failure` 必须严格为 False；`check_statuses` 拒绝 `condense.ALL_STATUSES` 以外的状态（flag 与 freeze 两处都查） | `experiments/I06_llm_condensation/verify.py`、`freeze.py`、`condense.py`（`ALL_STATUSES`） | `test_verify_and_freeze.py`：质量报告改为真实 flag→sheet→score 流程生成；新增负例：伪报告（只有 arm / obvious_failure）、过期报告（记录改动后）、拼错状态 → 均拒绝 |

## 测试

- I05 相关：`test_i06_profiles.py` + `test_strategy0_and_replay.py` + `test_config_and_locks.py` 55 passed
- I06：53 passed
- 全仓 `scripts/ci.sh`：427 passed / 6 skipped，CI PASS

## 首审 next_steps 第 2 条

Codex 只读沙箱里没有临时目录，所以没能跑 pytest。上面的测试由执行方在可写环境跑完，结果见上。

## 复审

见 `round2/`（焦点：复审首审 3 条 finding 的修复）。
