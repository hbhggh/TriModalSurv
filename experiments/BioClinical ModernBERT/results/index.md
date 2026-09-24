# I05 结果索引（结果账本）

本账本自 2026-09-24 起位于 `experiments/BioClinical ModernBERT/results/`（由 `experiments/I05_text_encoder_bcmbert/results/` 迁入，用户裁决）；两份四场景结果表、4×5 表与 Q 判定同时回传论文目录 `manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT-程序性知识/`。

**溯源说明（用户裁决 2026-09-24）**：用户选择把 main 上 I05 的全部提交压成一行（接受溯源失效）。训练与推理所用的冻结 commit `6631662` 因此不再是 main 的祖先，按 AGENTS.md「Git 工作流」第 9 条，本 run 结果的 commit 溯源失效，仅作 negative 记录，不进论文；中间冻结点 a/b/c 的 tag 已删除；`run/i05-bcmbert200-20260924d` 于 2026-09-24 按用户裁决重建并指向 `6631662`，可 `git show 6631662:<路径>` 读回当时源码。

按 `results/<run_id>/` 保存；已有结果不覆盖。证据是服务器原始 JSON 的脱敏副本（只把家目录绝对路径前缀替换为 `~`，数值不变），原文件 sha256 见各目录 `evidence/evidence-manifest.json`。

| run_id | 阶段 | 档案 | 状态 | 说明 |
|---|---|---|---|---|
| [`i05-bcmbert200-20260924d`](i05-bcmbert200-20260924d/encoder-table.md) | test（Phase 4）| bcmbert200 | **negative**（Q 未达标；用户 2026-09-24 裁决收官） | none 下严格胜 **2/5**（BLCA +0.004892、LUAD +0.012390）；LGG −0.053623、BRCA −0.033292、UCEC −0.016292。冻结 commit `6631662`（tag `run/i05-bcmbert200-20260924d`），训练与推理均在 tako |
| `i05-a0-<日期>`（待定） | 第二轮 | bcmbert8192 | 未运行 | A0：全文 ≤8192 token，masked mean 广播 200 行；Q 对 Table 1，另报相对 bcmbert200 与 legacytext-rerun 的同代码 Δ |
| `i05-legacytext-<日期>`（待定） | 第二轮 | legacytext-rerun | 未运行 | 原有 Text 在现行代码按同一配方重训 25 个，拆分重训方差（不进 Q） |

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
