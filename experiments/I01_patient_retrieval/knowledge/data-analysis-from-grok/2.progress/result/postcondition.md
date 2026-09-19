# 零训练改推理 1–5：验收记录

**完成状态：正式 valid 选参、冻结与单次 test 均已完成。远端独立审计为 `PASS`：valid `6100` 条、test `900` 条、重算预测 `7000` 条、患者审计 `831980` 条；本机已完整归档。用户正式豁免本轮 Claude 再审，不将其写成 Claude PASS。旧报告快照：`evidence/reports-before-tako-test-r3.tar`。**

| 验收项 | 证据位置 | 是否通过 |
|---|---|---|
| precondition先于推理代码创建，实现门明确 | `precondition.md`、`evidence/progress.md` | [x] 是 |
| 五个固定目录均含真实model/config/分析表 | `01_text100_skip_compensate` 至 `05_imputed_token_downweight` | [x] 是 |
| 共享入口、选择器、报告与独立测试存在 | `run.py`、`runtime.py`、`inference.py`、`selection.py`、`reporting.py`、`tests/` | [x] 是 |
| 25份 E0 权重与45份缓存、标签、manifest内容不变 | `evidence/tako-test-r3/tako-test-r3-final-audit.log` 的 `asset_hashes` | [x] 是 |
| 旧回归与新规则测试均通过，真实 NPJC 未以 skip 代替 | `evidence/b1b2-tests-legacy-tcga.log`（68/68）、`evidence/b1b2-tests-new-tcga.log`（43/43） | [x] 是 |
| 正式 valid 选参完整且冻结六协议 | `runs/valid/selection-lock.json`；审计 `selection_independently_verified=true` | [x] 是 |
| test 只执行一轮，100个癌种×seed×场景格点、9条协议记录/格 | `runs/test/complete.json`（`COMPLETED`）、`evidence/tako-test-r3/tako-test-r3-process-exit.txt`（0） | [x] 是 |
| 600条新协议与300条固定参考均存在 | 审计 `test_records=900`；`runs/test/` 的900个预测记录 | [x] 是 |
| B口径预测与患者审计可重算 | 审计 `prediction_scores_recomputed=7000`、`patient_audits_checked=831980` | [x] 是 |
| 四场景同批结果、标红及两列 Δ 均由原始 test 值生成 | `零训练改推理1-5实验结果.md`、`seed单位-实验结果.md`、`癌症为单位.md` | [x] 是 |
| 三份报告和完整矩阵已归档到指定根目录 | 本目录及 `runs/valid/`、`runs/test/` | [x] 是 |
| 不训练、不改 checkpoint/缓存/split/历史 JSON | 审计 `asset_hashes`、运行日志；无新 checkpoint 或训练日志 | [x] 是 |
| Claude再审 | 用户正式豁免；没有伪造 Claude PASS | [x] 用户豁免（非 Claude PASS） |
| 不commit/push，不自动扩范围 | 执行记录与当前交付 | [x] 是 |

## 停止边界

- 本轮到此停止：不按 test 结果追加规则、参数、seed、癌种或训练。
- 组合优于固定 m1/m0real 只能表述为本冻结零训练规则组合的探索性结果；历史 test 已参与规则设计，不能称独立盲测确认。
