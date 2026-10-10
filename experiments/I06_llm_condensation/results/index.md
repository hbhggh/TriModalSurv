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

## i06-a1a2-20260926：正式训练与 preflight（S = `c5aa9ea`，landau:0,1）

- 100 个 run（4 档案 × 5 癌 × 5 seed）全部 complete，训练配方 = 训练合同（50 轮、按验证集 C-index 选最佳轮，与 Table 1 基线、B1、B2 一致；用户 2026-09-26 确认不改为早停 200 轮），全部带 `--skip_test`。
- preflight 四档案全部 READY：每档案 25 个 checkpoint 的训练 commit = S、dirty = false、Text 路径与运行根一致、实际 runtime 含 skip_test；资产锁（S 上重写）早于全部训练。

| 档案 | checkpoints_sha256 | assets_lock_sha256（锁文件） |
|---|---|---|
| a1struct | `60e9bdb7414f096805de93926a185befdad53c0726a23d57e50914ef9acae226` | `8f83376f02679a3e4c0d6d081235bbb89e022fd49042f99a1a018e3d6e9479c4` |
| a1summ | `68774d35a28d044834fd91794444956839603eb84f6af4f7c99d832e6776afd3` | `e35cad1b46b024e37b6f8d9427348d4831f0bbd14fe0c0cb33c4b4106584181c` |
| a2struct | `316b4f9c004fa4c06639e3a1c84785f010f77442228d555297a77cd1cd62350d` | `10f8e5b2e21c2fad94fdefbd55fa8830bb5b67a74f8f230f980848060dafb662` |
| a2summ | `ba5b41c78b12fd37db3f11e335100d1d9a8dda301fbeffb504119f1fd0e8c6ea` | `5cd257880cd67101a36a620dd012860cd29d3eca0f79860800c19315556add91` |

四档案 source_hashes_sha256 均为 `7017bd2196ff…`（= 冒烟回放记录），runtime_sha256 均为 `2f1459be75b3…`。证据：`evidence/<档案>/{preflight,assets-lock}.json`。

## i06-a1a2-20260926：终点 test 与判定（研究计划书 4.9–4.10）

状态：**主 Q 未达标**（最佳候选 3/5，目标 ≥4/5）。节点二 Codex 结果审查已完成（`experiments/I06_llm_condensation/reviews/20260926-a1-results/`）：首审 2 high、1 medium 全部采纳；复审 1 high 按用户裁决修复、1 medium 用户裁决不采纳，不做第三轮。用户暂不收官（2026-09-26），读完结果文档再定。

- test（landau:1，2026-09-26 22:01–22:57 JST，部署脚本 `tools/i06_formal_landau.sh` 的 test 阶段）：四档案各 COMPLETED、300 行（五癌 × 五 seed × 四场景 × strategy0 / m1 / m0real）。门 = 回放 IDENTICAL + 审查记录（用户放行）+ 用户授权（绑定各档案 checkpoints / assets_lock / runtime 摘要），见 `gates/`。
- 判定（Overall = 每场景五 seed 均值 → 四场景等权平均；与 Table 1 Proto. 列逐癌未舍入严格 >）：

| 候选 | Overall 严格胜 | 不计 LUAD（确认性） | 五癌平均 Overall Δ | 胜的癌种 | BRCA Δ | LGG Δ |
|---|---|---|---|---|---|---|
| A1-S NeuML 结构化 | 2/5 | 1/4 | −0.012371 | LUAD（探索性）、BLCA | −0.040195 | −0.033540 |
| **A1-Z NeuML 摘要（胜者）** | **3/5** | 2/4 | −0.012411 | UCEC、LUAD（探索性）、BLCA | −0.045765 | −0.044755 |
| A2-S Qwen 结构化 | 1/5 | 0/4 | −0.027163 | LUAD（探索性） | −0.039128 | −0.048533 |
| A2-Z Qwen 摘要 | 1/5 | 0/4 | −0.022791 | LUAD（探索性） | −0.016930 | −0.039527 |

- LUAD 的推理路由受已见 test 启发（研究计划书 4.9），LUAD 各列数字属探索性：主判定照计五癌（机械门），另列不计 LUAD 的确认性口径。
- 同 encoder 归因（逐癌 Overall 差，BRCA / UCEC / LUAD / BLCA / LGG；未做显著性检验）：
  - 主对照 A1 − B2（同 NeuML、同 8192 编码规格，只差文本来源；研究计划书 v3.12 起）：A1-S −0.001380 / +0.003594 / +0.001062 / +0.007130 / +0.021722（为正 4/5）；A1-Z −0.006949 / +0.015469 / −0.000395 / +0.013298 / +0.010507（为正 3/5）。
  - 辅助 A1 − B1（B1 为原文前 200 token，同时改变文本内容与长度）：A1-S 为正 1/5、A1-Z 为正 2/5。
  - A2 没有同 encoder 原文对照，只作系统级比较。
- 独立验真：本机（numpy + sksurv）与 landau（sksurv + 现场读取 100 个 checkpoint 原件，`tools/i06_verify_landau.sh`）两路重算四档案 1200 行 C-index，max\|Δ\| = 0；每档案 25 个 checkpoint 哈希与 complete.json 逐行记录一致。
- 溯源：100 个训练记录 `git.json` 的 commit = S `c5aa9ea`、dirty = false、branch `train/i06-a1a2-20260926`；S 在 main 上，tag `run/i06-a1a2-20260926` 指向 S。
- 敏感性（剔除带退回 / 截断标记的患者，计划书 4.9；`tools/sensitivity.py` → `evidence/sensitivity.json`）：冻结文本哈希按 freeze manifest 核对；两臂截断 0，被标记者只有结构化臂 1 人（TCGA-EC-A24G，UCEC，退回原文，train 划分；四个已入库特征清单同样记为 train）。四档案 test 剔除 0 人、改变 0 行，剔除后严格胜 k 与胜者不变。
- Text masked 场景下 BRCA / LUAD / BLCA / LGG 的检索增益恒为 0（strategy0 与 m0real 逐患者风险相同），I05 的 B1 / B2 同样如此，属评测协议性质，不是 I06 特有。
- 结果文档与消融表：本目录 `6.LLM浓缩-A1-result-癌症为单位.md`、`6.LLM浓缩-A1-消融表.md`（同时回传论文目录 `6.LLM浓缩-A1/`，两处逐字节相同），由 `tools/render_results.py` 从 `evidence/<档案>/test/complete.json` 生成。
- 证据：`evidence/<档案>/{test/complete.json, test/campaign.json, checkpoint-sha256.txt, verify-landau-sksurv-ckpt.json, verify-local-numpy.json, formal/}`、`evidence/sensitivity.json`；脱敏规则（只把服务器家目录前缀换成 `~`）与原 / 脱敏哈希见 `evidence/evidence-manifest.json`。`raw/`（逐患者预测、训练记录原件）只留本地与 landau `~/i06_formal_c5aa9ea/`，逐文件哈希见 `raw-evidence-manifest.json`。
