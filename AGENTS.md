# TriModalSurv 公共纪律（唯一源头）

Claude Code 与 Codex/Codex Companion 都必须遵守本文件。冲突时以本文件为准。

## 执行前必读（坑台账）

开始任何实现、复现、评测、派单或修 bug 之前，必须先完整阅读：

`docs/engineering/pitfalls.md`

这是本仓库唯一的坑台账。读完再动手。禁止凭记忆声称已经知道这些约束。
新发现的失效模式收单时追加到同一文件：一行一条，含 ID、一句话坑、一句话 Prevention Rule、出处。
不要另起清单，不要把同一 Post-Mortem 重复入账。

最小执行口径：以本小节 + `docs/engineering/pitfalls.md` 为准。不再要求每次手工挑 3–5 条写入 plan.md。

## 角色（用户裁决 2026-09-22：对称互审）

- Claude Code 与 Codex / Codex Companion 都可以担任指挥官或执行者，由用户按任务指定；同一任务内角色一经指定不得自行互换。
- 硬约束是互审，不是谁指挥谁：一方执行大的研究计划（正式实验、新创新臂、跨模块重构）之前，另一方必须 review 计划与 diff；实验结果产出之后，另一方必须 review 结果与结论。
- 执行方（无论是谁）不得自行决定开始正式训练、重下数据、重启任务；review 通过不等于启动授权，仍需用户点头。
- 任何一方执行完，必须由另一方 review。禁止同一方执行完直接宣布通过。
- 当前指定（用户裁决 2026-09-23，用户另行指定前有效）：**代码开发由 Claude Code（Claude Opus 5.5）执行，不由 Codex 执行**；Claude 同时任指挥官。Codex 只负责审核，不参与任何代码生成：实验开始前审核生成的研究计划书（含代码 diff，按 CLAUDE.md 节点一全清单），实验结束后审核实验结果与结论（节点二）。这是本节"由用户按任务指定"规则下的当前指定，不改变互审与启动授权规则；在此指定下，本文件其他条目中关于 Codex 执行派单的要求暂不适用。

## 停机门

- 冒烟通过后必须停。
- 未获得用户明确允许，禁止开始 BLCA / BRCA / LUAD / LGG / UCEC 正式实验。
- 禁止启动 5-seed 全量与任何会占满 GPU 的长任务。
- MCAT / NPJ 骨架 / PORPOISE 都走同一条门。

## 正式实验 GPU 合同（2026-09-02 起对新实验生效）

旧「GPU 训练速度决策」三条中：第 1 条（batch 严格为 1、严禁 padding、gc=32 模拟大 batch）**作废**；第 2 条（I/O 合同）保留并升级为默认实现；第 3 条（同卡 2-3 run）降为后备手段。新合同：

1. 默认目标：单卡利用率优先。正式跑之前必须把 batch_size 调到该模型在这块卡上能稳定跑的最大值（探测 OOM 前一档）。
2. 只有加大 batch 会让 forward / collate / mask / loss 直接跑不通或静默算错时，才允许 batch_size=1，并在启动日志写明 `BATCH_SIZE_BLOCKED_REASON`。禁止把「和某论文对齐」当成阻断原因。
3. 可变长 WSI 的默认做法是 custom collate + attention padding mask（或等长 bucket），不是退回 batch=1；padding 必须带 mask，pad 位不得进入有效 attention 与风险分数。
4. DataLoader 正式配置必须具备：num_workers、pin_memory、persistent_workers、prefetch_factor；张量传输 `to(device, non_blocking=True)`。step 热循环内禁止 `.item()` / `.cpu()` / 打印张量；标量日志只在 epoch 边界或固定 log 间隔同步。
5. 单进程接近显存上限后 util 仍低，再查 I/O 与同步；仍空再考虑同卡并行第二个独立 run。禁止用多进程或梯度累积掩盖 batch_size=1（gradient_accumulation 仅为优化器选项，默认 1）。
6. 正式发车必须走门禁（NPJ 侧 `scripts/launch_formal.sh`）：warmup 采样 GPU-Util，低于门禁不得写入正式结果；故意小 batch / 单跑必须显式 `allow_low_gpu_util` 并写原因。
7. 评断三档不混用——门禁：warmup 120s util 中位数 ≥50%，否则正式实验失败；目标：单进程 ≥80% 且显存吃到接近安全上限；方向：能稳定更高就更高。达不到 100% 不是退回小 batch 的理由，停在 10-20% 才是失败。**NPJ 现架构成文豁免**（用户裁决 2026-09-02）：实测 bs 32→256 活跃 util 恒 11-15%、峰值 ≤31%，50% 对该计算图物理不可达——其正式 yaml 以 `allow_low_gpu_util+reason` 走豁免通道（数据：`collab/20260902-NPJ-GPU合同/notes.md`）；模型显著加大后豁免失效须重测。
8. 范围：自本日起的新实验（NPJ 骨架的后续对比 / 消融 / 创新臂）。已收官的 S5 三方对比配置为历史事实不追溯；若未来重启 MIL 变长 bag 类训练，batched+mask 路径已存在（两库 `--batched_collate`，任务 G），启用后同样受本合同约束，util 门禁按该架构实测基线另定。

## 执行纪律

- 通道超时先查进程；禁止把通道断当成任务死亡；禁止二次派单。
- Codex 执行派单前必读 plan.md「相关坑」节并遵守其中 Prevention Rule；产出的新教训按 Post-Mortem 格式写入 notes.md。
- 监视器默认只报警，不自动重启。
- 新下载 / 训练 / 转换必须经 landau 的 `jobrun.sh` 启动。
- **正式训练一律经 `scripts/train_launcher.py` 发车**（用户裁决 2026-09-02；仍由 `jobrun.sh` 托管）：清单驱动（臂×癌×seed）、缓存预热、每卡并发上限、幂等跳过、完成即评测；禁止手写 bash lane 串行 seed 发正式训练。默认 label=`data/TCGA_9523_ex12.csv`；dataset 缓存键已去 network_type，换骨架名不再触发冷重建。
- 不改 `tmp_sur_cache/`，不覆盖已有结果目录。
- 不把"窗口还在"当成"任务还在"。

## 互审

- 执行方完成的任务，必须回到另一方做检查；执行方的 patch / review 结论，必须由另一方再看一遍才能进入下一 Gate。
- 两个强制审查节点：大的研究计划执行前（计划 + diff + provenance），实验结果产出后（结果 + 结论 + 账本）。审查清单见 CLAUDE.md 节点一 / 节点二，对哪一方担任审查者都适用。
- adversarial review 通过，不等于可以开正式实验；还要等用户点头。
- 审查只审一次、只看核心逻辑（用户裁决 2026-09-23，细则见 CLAUDE.md 节点一）：修掉阻断项即进入上机前置条件评估，不做多轮复审与代码打磨；freeze 后的 provenance 三项由执行方机械核对并交原始输出。

每次执行任务前，必须完整阅读并遵守 [TPBHQ-认知分析引擎](TPBHQ-认知分析引擎.md) 中的约束。

## [T/B/P/A/Q] 热路径协议（编译后的 A，本文件内必须执行）

完整陈述性定义见 `TPBHQ-认知分析引擎.md`。本节省略原理，不省略动作。不得以“将去阅读 sidecar”代替本节的执行；本节省力出现在本文件正文里，才视为已挂载。

### 开局动作

涉及方案提议、架构修改、重构路径、算法变体选择或写代码之前，必须按序执行：

1. 先输出约束清单，格式固定为：
   `[ T + Q_{draft} (目标状态, 指标名称) + ∩P_i ∥ S_state ]`
2. 再做策略筛选：由 $T$ 唤起候选策略 ${k\_1, k\_2, k\_3, k\_4}$ → 执行 $P\_i \times S\_{state}$，刷掉当前状态不支持的候选 → 应用 `Q 约束 + 适用域` 得到 Boundary，只输出一个胜出策略。
3. 锁定 $P\_{specific} + Q\_{specific}$ 后才允许执行 $A$。$A$ 结束后严格用 $Q$ 验收；未达预期或需求变更时，必须声明 $Q\_{new} = \text{新一轮目标}$ 并重启循环。

### 防漂移（强制）

1. 思维锚点前缀：上述回复的第一句话必须是状态确认，例如 `[系统状态：S_state 已就绪 | 当前阶段：执行 A / 验证 Q]`。未经核验不得写“已就绪”。
2. 拒绝无边界编码：缺少前提 $P$ 或验收标准 $Q$ 时，禁止直接写代码，必须反问补齐约束清单。
3. 强制唤醒词：用户说出 `Code Red: Recalibrate` 时，立刻停止发散，重新读取 `TPBHQ-认知分析引擎.md` 与本节，并只回复：`引擎已重新挂载，等待第 1 组约束清单`。

## Git 工作流（策略一：先 Squash 后跑；用户裁决 2026-09-22）

完整说明与迁移模板见 `docs/workflow/git-workflow.md`；命令封装在 `scripts/gitflow.sh` 与 `scripts/ci.sh`。

布局：主目录 `TriModalSurv/` 只检出 `main`；`dev` 是唯一长期开发分支，检出在 `TriModalSurv.worktrees/dev/`；每个正式实验从 `main` 建一个 run worktree `TriModalSurv.worktrees/run-<run_id>/`，检出一次性分支 `train/<run_id>`（HEAD = `main`）。Codex 自己的 `~/.codex/worktrees/` 是它的临时工作区，不在本规则内，也不得作为正式实验源码来源。

1. `main` 的语义 = 一个创新一个 commit，且每个正式实验的 commit 都在 `main` 上。禁止在主目录直接改代码。
2. 创新靠目录与文件名隔离（`experiments/<ID>/`、config 选择），不靠分支；多个创新共用 `dev`。
3. 开发只在 dev worktree：小步 commit，前缀带实验 ID（`feat(I05): ...`）；每步跑 `scripts/ci.sh`，红灯不 commit。
4. 候选 H = `scripts/gitflow.sh candidate` 通过（CI 退出码 0 + 工作树干净）。通过后才进入互审。
5. 互审通过后在主目录 `scripts/gitflow.sh squash "feat(I05): ..."`：`main` 得 S，脚本校验 tree(S) = tree(H) 并把 `dev` 归位到 S。`dev` 领先 `main` 超过正在做的一个创新即违规。
6. 冻结：`scripts/gitflow.sh freeze <run_id>` 从 `main` 打 `run/<run_id>` tag、建分支 `train/<run_id>` 的 run worktree（HEAD = `main`）、调用 `scripts/git_stamp.py` 生成 `GIT_STAMP.json`。分支前缀 `train/` 与 tag 前缀 `run/` 必须不同。同步到训练服务器的源码只能来自 run worktree；`GIT_STAMP.json` 随代码同步。
7. run worktree 与 `train/*` 分支只读，禁止 commit。发现 bug 回 `dev` 修，重新 candidate → squash → freeze 新 run_id；旧 run 结果作废并在账本标 invalid。
8. 结果 provenance：`git.json` / `results.tsv` 里的 commit 必须 `git branch --contains` 命中 `main` 且 `dirty=0`；不满足的结果不得进论文。
9. 结果差不 revert：账本标 negative，代码留在树里；确需清理另起 `chore(I05): drop` commit。
10. 收尾 `scripts/gitflow.sh cleanup <run_id>`：先核对 run worktree HEAD 仍在 `main` 上（`git merge-base --is-ancestor`），再删 worktree 与 `train/<run_id>` 分支；tag 保留。核对失败说明实验期间有 commit 混入，该 run 结果 invalid，不得 `-D` 强删。结果回传到主目录 `experiments/<ID>/results/<run_id>/`，永远不放进 run worktree。
11. `main` 只经 squash 前进；禁止 rebase / force-push `main`；squash 后 `git push origin main`。
12. 与 STATUS.md 第 1 节「全量运行时从确定 commit 建临时 worktree」一致：那个「确定 commit」现在就是 `main` HEAD = S。
