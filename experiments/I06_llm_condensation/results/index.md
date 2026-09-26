# I06 结果索引

按 `results/<run_id>/` 保存；已有结果不覆盖。含原文的记录、抽查表、批次原始结果只放 `raw/`（按 .gitignore 不提交）；`evidence/` 只放哈希、比率与患者 ID。终点结果文档 `6.LLM浓缩-A1-result-癌症为单位.md` 回传论文目录。

## i06-condense-20260926：LLM 浓缩与冻结（Phase 1–2，研究计划书 v3.12）

| 项目 | 结构化臂 | 摘要臂 |
|---|---|---|
| 模型 | claude-opus-5-5，effort high，Message Batches | 同左 |
| 长度 | 不设上限、不截断（v3.12）；中位 260 / 最长 806 NeuML token | 目标 155 词（对齐结构化臂中位）；中位 252 / 最长 394 |
| 份数 | 2506：ok 2505，退回原文 1（全部字段未提及） | 2506：ok 2506 |
| 批次 | `msgbatch_01FARDe1hc2RJ3VbPKiYSoX3`（第 1 轮回放，prompt 未提长度） | `msgbatch_01QcJssFbswjcKstksmtnzM2` |
| 质量（随机 40 份，Codex 只读评审 + 人工复核 55 行） | 幻觉 2/40、遗漏 2/40、捏造分期 / 预后 0/40 | 幻觉 2/40、遗漏 2/40、捏造 0/40 |
| 冻结文本 sha256 | `95402d09081166e50912d4f00e63d3dd907e4eef826daa711777d21bcc9f7d48` | `7282a0ffb45a8beaa599ffac1e8184446703dc66fa1b1e4e08ef4fb73adb61d0` |

- freeze manifest：`evidence/freeze-manifest.json`（sha256 `f4e0b13ae92f11665856d9db171b455d8d8360cad143d4d0a78e11f16bdecaf9`）；质量报告：`evidence/quality-struct.json`、`evidence/quality-summary.json`。
- API 花费合计约 $160（200 版全量 $128 + 摘要臂重跑 $27.5 + 两轮试点约 $4）。200 版文本与其 Codex 抽查只作归档，不进入冻结（研究计划书 v3.10–v3.12）。

## i06-smoke-e57d932：候选 H 冒烟（landau，2026-09-26）

H = `e57d932`（`git archive` 快照 + `GIT_STAMP.json`，commit = H，dirty = false），部署脚本 `tools/i06_smoke_landau.sh`。只判通 / 不崩（坑 V21），不进账本主表。

| 阶段 | 结果 |
|---|---|
| 资产 | 45 个历史缓存（legacy-preflight + valid-source 锁定哈希）与 25 个历史 E0 checkpoint 在 landau 上逐个校验通过；每个档案复制 30 个 img/rna 缓存，不链接、不改动历史缓存 |
| 特征提取（landau:1） | 四个档案各 2506 人，manifest complete，截断 0，编码规格 max_length 8192 不截断；文本来源分别为冻结的 struct / summary 臂；提取器身份 = H、干净。A1 用 transformers 4.48.3（与 B1 同版本），A2 用 4.51.3 |
| text 缓存预热 | 四个档案各 15 个新 text 缓存（每档案共 45 个） |
| 资产锁 | 四个档案全部 ASSETS_VERIFIED |
| 冒烟训练与推理（BLCA / seed 123，cuda:1，`--skip_test`） | 四个档案全部 SMOKE_PASS（12 行，不计算指标） |
| 历史回放门（legacy-replay，cross-hardware 档） | **IDENTICAL**，n_different = 0（300 行），source_hashes_sha256 `7017bd2196ff…` |

证据：`evidence/<档案>/{assets-lock,feature-manifest,smoke-complete}.json`、`evidence/replay/replay-comparison.json`（均不含本机绝对路径）。
