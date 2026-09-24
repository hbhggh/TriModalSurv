# I05 结果索引（结果账本）

本账本自 2026-09-24 起位于 `experiments/BioClinical ModernBERT/results/`（由 `experiments/I05_text_encoder_bcmbert/results/` 迁入，用户裁决）；两份四场景结果表、4×5 表与 Q 判定同时回传论文目录 `manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT-程序性知识/`。

**溯源说明（用户裁决 2026-09-24）**：用户选择把 main 上 I05 的全部提交压成一行（接受溯源失效）。训练与推理所用的冻结 commit `6631662` 因此不再是 main 的祖先，按 AGENTS.md「Git 工作流」第 9 条，本 run 结果的 commit 溯源失效，仅作 negative 记录，不进论文；中间冻结点 a/b/c 的 tag 已删除；`run/i05-bcmbert200-20260924d` 于 2026-09-24 按用户裁决重建并指向 `6631662`，可 `git show 6631662:<路径>` 读回当时源码。

按 `results/<run_id>/` 保存；已有结果不覆盖。证据是服务器原始 JSON 的脱敏副本（只把家目录绝对路径前缀替换为 `~`，数值不变），原文件 sha256 见各目录 `evidence/evidence-manifest.json`。

| run_id | 阶段 | 档案 | 状态 | 说明 |
|---|---|---|---|---|
| [`i05-bcmbert200-20260924d`](i05-bcmbert200-20260924d/encoder-table.md) | test（Phase 4）| bcmbert200 | **negative**（Q 未达标；用户 2026-09-24 裁决收官） | none 下严格胜 **2/5**（BLCA +0.004892、LUAD +0.012390）；LGG −0.053623、BRCA −0.033292、UCEC −0.016292。冻结 commit `6631662`（tag `run/i05-bcmbert200-20260924d`），训练与推理均在 tako |
| [`i05-a0-20260924`](i05-a0-20260924/encoder-table.md) | test（第二轮 A0）| bcmbert8192 | **negative**（Q 未达标；待用户裁决） | none 下严格胜 **2/5**（BLCA +0.006107、LUAD +0.014180）；LGG −0.078951、BRCA −0.033837、UCEC −0.014200。相对轮 C bcmbert200 严格胜 3/5（信息性）。冻结 commit `3c46f37`（tag `run/i05-a0-20260924`，在 main 上），训练与推理均在 tako |
| `i05-a0-20260924`（同一 run，对照臂） | 第二轮 | legacytext-rerun | **未评测**（用户裁决记为发现） | 25 个重训 ckpt 与历史 E0 **逐字节相同**（25/25 sha256 相等，`i05-a0-20260924/checkpoint-sha256-legacytext-rerun.txt`）：现行代码训练完全确定性，重训方差为 0；加上回放 IDENTICAL，此臂 test 结果必然等于 Table 1。preflight 按“仍是历史 E0 权重”门拒绝（设计行为） |

结果要进论文，必须满足：`git.json` 与账本里的 commit 在 main 上、`dirty=0`、有对应的 `run/<run_id>` tag（AGENTS.md「Git 工作流」第 9 条）。本 run 满足：25 个训练记录 commit = `663166247783`、dirty=false，tag `run/i05-bcmbert200-20260924d` 存在。

## i05-bcmbert200-20260924d 运行链路

| 步骤 | 结果 | 证据 |
|---|---|---|
| Phase 0 只读核验（landau，`3de43a2`） | 报告原文可得；旧 pad 位非零 → 用户改定方案 C | 研究计划书 3.2、先验知识 4.1b |
| Phase 1 特征提取（tako:1，venv transformers 4.48.3） | 2,506 人，manifest complete；86% 在 200 token 截断 | `evidence/`（特征 manifest 在服务器，sha256 `66eb66f8…`） |
| assets 与训练前资产锁 | ASSETS_VERIFIED；img/rna 30 个与历史逐字节相同，text 15 个新建；锁内容摘要 `5a1a602d…` | `evidence/exec/runs/assets/` |
| Phase 2 冒烟（BLCA/123） | 训练完成；推理 SMOKE_PASS | `evidence/smoke_eval/` |
| 回放门（legacy-replay，tako 原机） | **IDENTICAL**：300 行逐值相同，max\|Δ\| = 0 | `evidence/replay/` |
| Phase 3 正式训练（tako:4,2,3,0） | 25/25 complete | `evidence/formal/` |
| preflight | READY：25 个 ckpt 训练身份逐一通过；资产锁早于全部 run 且当前内容等于锁 | `evidence/formal_eval/runs/preflight/` |
| test 门 | 回放 PASS + 审查记录 + 用户授权（用户 2026-09-24 在对话中签署；审查记录注明由用户签署、并非 Codex 输出） | `evidence/gates/` |
| Phase 4 test（tako:1） | COMPLETED，300 行；天然缺失人数与 LUAD 路由计数与历史一致 | `evidence/formal_eval/runs/test/complete.json` |
| Phase 5 渲染 | 两份结果表与 4×5 表由脚本从原始 JSON 生成；独立重算逐位一致 | 本目录三份 md |

## 节点二补证（Codex 结果审查 needs-attention 后补齐）

Codex 结果审查（`review-node2-results.json`）指出归档缺少逐患者预测、audit、日志与 checkpoint 核对依据。已补齐：

| 补齐内容 | 位置 |
|---|---|
| test 阶段全部逐患者预测（320 个 npz）、audit 与单元格记录 | `raw/formal_eval/runs/test/` |
| 25 个训练运行记录全目录（含训练日志）、launcher 日志、冒烟训练记录、各阶段 jobrun 日志 | `raw/formal/`、`raw/smoke/`、`raw/logs/` |
| 25 个 checkpoint 的逐文件 sha256（本体 139 MB 不进公开仓库，保存在 tako 结果根并已设只读） | `checkpoint-sha256.txt`（已提交） |
| 原文件哈希清单（脱敏只替换家目录路径前缀；npz 原样复制） | `raw-evidence-manifest.json`（已提交） |

按仓库 `.gitignore`（`results/**/raw/`、`logs/`、`*.npz`、`checkpoints/` 不进公开仓库），`raw/` 只保存在本地结果目录与服务器结果根（tako `~/i05_out_20260924d/`，2026-09-24 清理其余临时目录时保留），不提交；提交的是它的逐文件哈希清单 `raw-evidence-manifest.json` 与 `checkpoint-sha256.txt`，据此可核对本地与服务器原件未被替换。

独立验真（`tools/verify_results.py`，不导入评测器）：

| 核对 | 本机（纯 numpy 独立实现） | tako（sksurv，读服务器原件） |
|---|---|---|
| 300 行 C-index 从逐患者预测重算 vs 记录值 | 全部相同，max\|Δ\| = 0.0 | 全部相同，max\|Δ\| = 0.0 |
| 同单元格各臂患者与标签一致、患者数相符 | 通过 | 通过 |
| 每行 checkpoint_sha256 与 ckpt 哈希清单一致（25 个） | 通过（只核对清单） | 通过 |
| 现场读取 25 个 .pth 原件计算 sha256，与清单及每行记录一致（复审 high 后补做） | 不适用（本体不在本机） | 通过：`checkpoint_check = hashed_checkpoint_files`，原件只读 |
| 由重算值重做 Q 判定 | 严格胜 2/5，未达标 | 严格胜 2/5，未达标 |

报告：`verify-local-numpy.json`、`verify-tako-sksurv.json`、`verify-tako-sksurv-ckpt.json`（含 checkpoint 本体哈希）。Codex 复审（`review-node2-results-r2.json`）确认逐患者预测、日志、manifest 与两路重算已补齐，negative 限定为“预设 Q 未达标”；其唯一 high（验证器未哈希 ckpt 本体）已由 `--checkpoint-root` 模式在 tako 原件上补做。

## i05-a0-20260924 运行链路（第二轮 A0，bcmbert8192）

| 步骤 | 结果 | 证据 |
|---|---|---|
| Codex 节点一审查 | 首审（`3d818dc`）3 条 high → `c14b42c` 修复；复审 round2 仍 1 条 high（历史 Text 患者集合核对为可选门）→ 用户裁决按推荐修法在 `1cb6bfd` 修复、不再审 | `experiments/I05_text_encoder_bcmbert/reviews/20260924-a0-fullctx/` |
| 候选冒烟（H = `1cb6bfd`，tako） | 分词审计：2506 人最长 6822、超过 8192 的 0 人；提取 2506 人，0 截断，有效 token 数 = 全文 token 数；预热 15 个 text 缓存；assets 两档 VERIFIED；冒烟训练完成、推理 SMOKE_PASS；legacy-replay **IDENTICAL**（300 行，max\|Δ\| = 0） | `evidence/cand/`、`evidence/smoke_eval/`、`evidence/replay/`、`evidence/feature-manifest.json` |
| squash / freeze | S = `3c46f37`，tree(S) = tree(H) = `72134300…`；main HEAD = run worktree HEAD = GIT_STAMP = tag `run/i05-a0-20260924` | 执行方机械核对原始输出（交用户） |
| 资产锁（S 上重写） | 两档 ASSETS_VERIFIED，锁 commit = S，早于全部正式训练 | `evidence/exec8192/`、`evidence/exec_legacy/` |
| 正式训练（tako:0,1 / tako:2,3） | 25 + 25 complete，commit = S，dirty = false | `evidence/formal/`、`evidence/formal_legacy/` |
| preflight | bcmbert8192 READY（源码摘要 `5b16558e…` = 回放记录）；legacytext-rerun 被拒：25 个 ckpt 与历史 E0 逐字节相同 | `evidence/formal_eval/runs/preflight/`、`checkpoint-sha256-legacytext-rerun.txt`（拒绝日志 `raw/logs/preflight.log` 只留本地，哈希见 `evidence/evidence-manifest.json`） |
| test 门 | 回放 PASS + 审查记录（绑定 H，注明复审 high 由用户裁决放行）+ H→S 换绑记录（tree 相等）+ 用户授权（2026-09-24 对话内签署） | `evidence/gates/` |
| test（tako:0） | COMPLETED，300 行 | `evidence/formal_eval/runs/test/complete.json` |
| 独立验真 | 本机 numpy 与 tako sksurv 两路重算 300 行 C-index 均 max\|Δ\| = 0；tako 现场读取 25 个只读 .pth 原件哈希，与清单及逐行记录一致 | `verify-local-numpy.json`、`verify-tako-sksurv-ckpt.json` |
| 渲染 | 两份结果表与 4×5 表由脚本从原始 JSON 生成（参考臂：轮 C bcmbert200），同时回传论文目录 5.x | 本目录三份 md |

`raw/`（逐患者预测、训练记录全目录、日志）只保存在本地结果目录与 tako `~/i05_a0_out/`（ckpt 已设只读）；逐文件哈希见 `raw-evidence-manifest.json`。
