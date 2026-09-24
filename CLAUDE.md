@AGENTS.md

# 关键节点审查规则（Claude Code）

## 角色与边界

- 角色对称（用户裁决 2026-09-22）：Claude 与 Codex 都可以担任指挥官或执行者，由用户按任务指定。本文件描述的是「担任审查方」时的动作；Claude 担任执行方时，由 Codex 按同样的两个节点审查 Claude。
- 当前指定（用户裁决 2026-09-23，用户另行指定前有效）：**代码开发由 Claude Code（Claude Opus 5.5）执行，不由 Codex 执行。** Claude 同时任指挥官，负责设计、构建代码、本地验证和发车准备。
  - Codex 只负责审核，不参与任何代码生成：实验开始前审核生成的研究计划书（按节点一全清单，含代码 diff、配置、测试输出、`--dry_run` 与 provenance），实验结束后审核实验结果与结论（节点二）。
  - 在此指定下，下面两个节点的清单由 Codex 执行。Claude 按"由执行方……"的条目准备审查包、提醒用户发起审查、修复阻断项，不做自审，也不替审查方写 PASS 记录。
  - 本仓库以此覆盖全局 `~/.claude/CLAUDE.md`「多模型协作协议」中由 Codex 实施编码的分工：不向 Codex 派发任何编码任务（不用 `task --write`），companion 只用 `adversarial-review` / `review` 发起只读审核。
- 两个强制节点：一方执行大的研究计划（正式训练/实验、新创新臂、跨模块重构）之前的 Code Review，以及实验结果产出后的复盘与审查。
- 审查以只读方式进行：审查方不直接修改被审代码、不启动或重启任务；问题交回执行方修复后复核。
- 审查通过只是正式实验的必要条件；用户明确同意后，才可由执行方按 AGENTS.md 的发车规则启动。

## 审查前必读（坑台账）

开始上述任一节点的审查之前，必须先完整阅读：

`docs/engineering/pitfalls.md`

这是本仓库唯一的坑台账。读完再动手。禁止凭记忆声称已经知道这些约束。
新发现的失效模式由执行方在任务收尾时追加到同一文件：一行一条，含 ID、一句话坑、一句话 Prevention Rule、出处。
不要另起清单，不要把同一 Post-Mortem 重复入账。

最小执行口径：以本小节 + `docs/engineering/pitfalls.md` 为准。不再要求每次手工挑 3–5 条写入 plan.md。
审查方应指出遗漏的新坑及其证据，由执行方补写 Post-Mortem 并去重入账；影响所有后续任务的规则升级，经用户确认后由执行方固化进 CLAUDE.md/AGENTS.md。
台账及历史任务文档中的旧角色分工、Claude 派单/监视流程和手工摘抄要求，以 AGENTS.md 为准；具体防坑条目与工程约束继续遵守。

## 节点一：正式训练/实验开始前

- 审查闭环只审一次（用户裁决 2026-09-23）：每个实验前只发起一次 Codex 审查，只看核心逻辑（整体逻辑、致命错误、数据划分与泄漏、mask / loss / risk 口径、对照与因果口径、provenance 设计）；代码语法、风格或写法不完美不构成阻断。执行方修掉阻断项、补测后，不再请求复审，直接评估上机前置条件并交用户授权；是否再审由用户决定。
- 由于只审一次且通常发生在 freeze 之前，下面的 provenance 三项由执行方在 freeze 后用命令机械核对，并把原始输出交给用户；不满足即阻断。
- 由执行方提醒用户发起审查，交付待运行代码与配置、实验范围、实际测试/冒烟输出及发车 `--dry_run` 输出。
- 逐文件查看 git diff，检查整体逻辑、致命错误、数据划分与泄漏、mask / loss / risk 口径，以及是否违反坑台账、停机门和 GPU 合同。
- 核对 Git 工作流 provenance（AGENTS.md「Git 工作流」）：待跑 commit 已是 `main` HEAD（squash 完成、`dev` 已归位、`git diff main dev` 为空）；run worktree HEAD（分支 `train/<run_id>`，或 detached）等于 `main` HEAD 且 `git status` 干净；`GIT_STAMP.json` 的 commit 等于 `main` HEAD 且对应 `run/<run_id>` tag。三者任一不满足即阻断。
- 核对 AGENTS.md 的完整发车与评测纪律：包括 batch_size、I/O、GPU-Util 门禁及豁免条件，`train_launcher.py` / `jobrun.sh`、`--dry_run` 和评测入口；核查有没有越权启动或重复启动任务。
- 审查结论须写明所审代码/配置版本与实验范围、通过或阻断、问题的文件位置及证据。阻断项由执行方修复、补测；按只审一次的口径不再交回复核，用户要求时除外。
- 审查后若实验范围或核心逻辑发生实质变化，由执行方向用户说明，由用户决定是否补充审查；变更后的实验须经用户明确同意再启动。审查方不以审查意见替代启动授权。

## 节点二：实验结果产出后

- 核对执行方提供的原始结果、日志、实际配置、checkpoint、癌种/seed 清单与汇总依据，确认结果来自所审实验、无缺失混入或旧结果冒充。
- 核对结果 provenance：`git.json` / `results.tsv` 的 commit 必须 `git branch --contains <commit>` 命中 `main`、`dirty=0`、且有对应 `run/<run_id>` tag；否则结果不得进论文，也不得作为本节点的审查对象。
- 复核指标计算、基线与对照口径、异常和失败记录；区分技术失败、效果未达预期与证据不足，明确结论能够支持的范围。
- 输出有证据的审查意见和待解决问题，交由执行方与用户确认后续动作；不自行改变研究方向、扩大实验或要求自动重跑。
- 审查发现的新失效模式交给执行方按 AGENTS.md 记录 Post-Mortem、补充 Prevention Rule 并回流坑台账。

## 历史项目上下文

- 三方对比战役（MCAT / PORPOISE / NPJ 骨架，5 癌种 4:2:4，5 seeds 逐值呈现），历史执行细节见 `archive/legacy_collab/root-20260916-080006/20260827-三方对比战役/plan.md` 与 `~/.claude/plans/twinkling-greeting-kahan.md`；当前任务范围与启动权限以用户本次明确授权为准。
