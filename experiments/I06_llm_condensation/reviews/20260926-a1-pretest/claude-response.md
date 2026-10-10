# test 门前 Codex 审查：逐条处理（S = c5aa9ea）

- 审查对象：dev（= S `c5aa9ea` + 其后文档提交）相对 `20bbe6a`；结论 `needs-attention`，2 条 high、1 条 medium
- 执行方已核实：三条都是代码门不够严，本次 S 的实际数据链未受影响（证据见下）；是否据此放行 test 交用户裁决（AGENTS.md「自动审查闭环」第 5 条）

| # | 级别 | 问题 | 对本次数据的核实 | 代码处理 |
|---|---|---|---|---|
| 1 | high | 续跑只核对 custom_id，不核对请求内容 | 用于冻结文本的结构化臂回放了第 1 轮批次 `msgbatch_01FARDe1hc2RJ3VbPKiYSoX3`，提交时代码为 `3e4346f`。`git diff 3e4346f c5aa9ea` 显示 prompts 只新增评审标准（不进浓缩请求），`model.py`（请求构造、schema）无改动；`config.llm` 相同（claude-opus-5-5 / high / 16000）；原文清单为同一文件（sha `b3f05c74…`，记入 freeze manifest）；发请求代码只把 TypedDict 换成键值相同的 dict。回放请求与原请求逐字相同，状态未分叉 | 采纳（后续加固）：提交批次时落盘每个 custom_id 的规范化请求摘要，续跑逐项比对，不同即拒绝 |
| 2 | high | 提取器不强制 freeze manifest，只核对自报的冻结文件哈希 | 四个特征 manifest 的 `text_source.sha256` 分别为 struct `95402d090811…`、summary `7282a0ffb45a…`，与 freeze manifest 登记的冻结文件哈希逐一相等；freeze manifest 绑定两臂质量报告（Codex 评审 + 人工复核 55 行） | 采纳（后续加固）：提取必须输入 freeze manifest，按臂取文件名与哈希、核对质量状态，并把 manifest 哈希写入特征 manifest、资产锁与授权门 |
| 3 | medium | `skip_test` 训练仍在训练前加载 test 数据集 | 训练只加载、不预测：test 标签不进损失，训练记录的 metrics 只有 `test_skipped`；test 缓存内容由资产锁在 preflight 逐一核对未变。Table 1 基线、B1、B2 的训练同样加载 test（且训练末尾曾在 test 上预测），A1/A2 与对照同口径 | 不改本次训练代码（改了反而使 A1/A2 与对照的训练路径不同）；论文与计划书的表述改为"训练期间不在 test 上预测、不计算 test 指标"，不写"未触碰 test" |

## 用户裁决（2026-09-26）

用户选择「凭证据放行，先跑 test」：本次 test 用 S 照常进行；审查记录 `decision=PASS` 由用户签署（记录内注明为用户放行结论而非 Codex 复审结论），四个档案的授权记录绑定各自的 checkpoints / assets_lock / runtime 摘要（`results/i06-a1a2-20260926/gates/`）。两条 high 的代码加固之后在 dev 修复，修完按闭环复审一次，不影响本次结果；medium 按上表处理，不改本次训练代码。
