# landau 目录整理与路径映射（2026-09-24）

用户 2026-09-24 要求整理 landau 家目录与 `~/NPJ`，把相似文件归到同一文件夹。只移动、不删除（同盘 `mv -n`，不复制、不覆盖）。仓库历史证据里写的 landau 路径若已不存在，按映射表查新位置；证据记录的 sha256 不受移动影响。

- 映射表：[`landau-path-map-20260924.tsv`](landau-path-map-20260924.tsv)，共 138 条（旧路径 → 新路径）。服务器上的原件是 `~/archive/MOVED.tsv`，NPJ 部分另存 `~/NPJ/_MOVED.tsv`。
- 撤销：`bash ~/archive/UNDO_MOVES.sh`，按相反顺序移回原位；目标已存在时不覆盖。
- 整理脚本：`~/archive/tidy_landau.sh`，默认 dry-run，`--apply` 才执行；执行前逐项检查：源存在、目标不存在、没有进程工作在其中、同一文件系统。

| 新目录 | 内容 |
|---|---|
| `~/archive/npj-eval-202609/` | NPJ 战役的评测、parity、smoke 小目录（`npjc_eval_*`、`npjd_*`、`npjq_*`、`amiss_eval*`、`parity_e0m` 等 26 个） |
| `~/archive/protomasksurv/` | `protomasksurv-exp1-*` 与 `protomasksurv-exp3-*`（8 个）；裸仓库的 4 个 worktree 已用 `git worktree repair` 修复路径 |
| `~/archive/omicsgate/` | `omicsgate_transformer` |
| `~/archive/misc-files/` | 0 字节误建文件、repomix/bundle 导出、技能备份包、vscode tunnel 杂项（14 个） |
| `~/NPJ/_outputs/` | `out`、`out_*`、`launcher_logs`、`npjc_smoke_arch`（12 个） |
| `~/NPJ/_backups/` | `backup_*`、`codex_*`、`refactor-validation-20260916-080006`、`refactor_assets`（10 个） |
| `~/NPJ/_adhoc_scripts/` | 未被 git 跟踪的临时 `.sh`、`tasks_*.txt`、`scripts_tmp`（65 个） |
| `~/NPJ/_scratch/` | `scratch`、`tmp_d_verify` |

原地不动：NPJ 中 git 跟踪的代码，以及 `data`、`downloads`、`jobs`、`jobrun.sh`（`JOBS` 路径写死）、`keeper.sh`（cron 每 10 分钟运行）、`logs`、`tmp_sur_cache*`（AGENTS.md：不改）、`runs_state.json`、`scripts/`；家目录的 `baselines`、`mcat-selcomp`、`Transformer-ProtoMaskSurv*`（有进程在用）、`miniconda3` 与工具目录、点文件。

跳过（待用户决定）：`omisgate-v2`、`omisgate-v3`、`omicsgate_transformer_tournament` 里仍有 139–175 天前开启的 shell / claude 会话以它们为工作目录，本轮未移动。
