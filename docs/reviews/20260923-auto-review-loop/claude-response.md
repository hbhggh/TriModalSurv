# Claude 对 Codex 审查的逐条处理（2026-09-23，自动审查闭环首次实际运行）

- 审查原文：同目录 `codex-review.public.json`（原文只把仓库根替换为 `<仓库根>`）（companion `adversarial-review`，`--scope working-tree`，`gpt-5.6-sol`；结论 `needs-attention`，3 项 high）。
- 审查对象：Claude 会话 worktree（基于 `14f722e`）中的 `scripts/gitflow.sh`、`scripts/ci.sh`、`scripts/codex_review.sh`、`tests/test_workflow_scripts.py`，以及 AGENTS.md / CLAUDE.md / STATUS.md 的规则改动。
- 调用记录：第一次调用在无任何输出时被宿主应用退出中断（空 `.partial`，companion 无作业记录），确认无存活作业后重新发起一次；本文件处理的是唯一一份完整结论。
- 按闭环规则只审一次、不复审；第 3 项不采纳其中的复审建议，交用户裁决。

| # | 级别 | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|---|
| 1 | high | `cleanup` 用 `status --porcelain` 判干净，看不见被 `.gitignore` 隐藏的 checkpoint / 日志，`worktree remove` 会一并删除 | **采纳（调整）**。按建议"任何被忽略文件都拒绝"会让正常 cleanup 永远失败：freeze 调 `git_stamp.py` 在 run worktree 内写 `GIT_STAMP.json`（被忽略），运行也会产生 `__pycache__`。改为白名单：只放行 `GIT_STAMP.json`、`__pycache__/`、`*.pyc`、`.DS_Store`（均可再生），其余被忽略文件列出并拒绝 | `scripts/gitflow.sh` `cmd_cleanup`（`status --porcelain --ignored` 过滤）；同步头注释、`docs/workflow/git-workflow.md` 第 8 步与规则块第 10 条、AGENTS.md「Git 工作流」第 10 条 | `test_ignored_run_outputs_are_refused`（`logs/`、`*.pth` 被拒且保留；旧脚本上 RED）、`test_regenerable_ignored_files_do_not_block_cleanup` |
| 2 | high | `codex_review.sh` 先定名后校验：坏 JSON 留下正式文件并堵死重试；`parseError` / 缺 `result` / 非法 verdict 仍以 0 退出；固定 partial 路径会被下次截断 | **采纳**。`mktemp` 唯一临时文件；校验合法 JSON、无 `parseError`、`result.verdict ∈ {approve, needs-attention}`（取自 companion `schemas/review-output.schema.json`）、`findings` 为数组，全部通过才 `mv` 为 `codex-review.json`；失败以 1 退出并保留该次原始输出；`mv` 前再查一次正式文件防并发覆盖 | `scripts/codex_review.sh` 落盘段 | `CodexReviewOutputTests`：合法结论落盘；非法 JSON、parseError、缺 result、非法 verdict、缺 findings、companion 非零退出六种降级均不生成正式文件，且每次失败现场各自保留 |
| 3 | high | CLAUDE.md "修复后不复审"与"审查后逻辑变化须补充审查"冲突，核心逻辑修复可能未经 Codex 看过就进正式实验 | **部分采纳**：文字冲突属实，已澄清边界——为回应审查意见所做的修复不复审（用户裁决"只审一次"），但逐条列入本文件并随汇报交用户；审查之后另起、并非回应审查意见的逻辑 / 配置 / 范围变更是新的审查点，再审一次。**不采纳**"语义修复须重新审查"：与用户 2026-09-23 明确裁决（只审一次、不复审）相反 → 按闭环第 5 条交用户裁决 | CLAUDE.md 节点一末条、AGENTS.md「自动审查闭环」第 3 条 | 规则文字，无代码测试 |

> 第 3 项的用户裁决（2026-09-24）：接受有条件复审——首审无核心逻辑问题即放行；有则修复后复审一次；复审仍有则停下交用户，不自动第三轮。已写入 AGENTS.md「自动审查闭环」第 3、5 条与 CLAUDE.md 节点一。本次首审第 1、2 项属于核心逻辑问题，因此发起了下面的复审。

## 测试

- `tests/test_workflow_scripts.py`：29/29 通过（默认 locale）。
- 全仓 CI：审查前（worktree `14f722e`）5 failed / 236 passed，失败集合与主仓库基线逐 ID 相同；修复后（worktree 同步到 `c4dfc7e`）4 failed / 243 passed，只剩 3 个 I02 与 1 个 I01 既有失败（I05 那一项已被 `c4dfc7e` 修掉），无新增。

## 复审（round 2，2026-09-24；用户裁决：首审有核心逻辑问题须复审一次）

- 原文：`round2/codex-review.public.json`（结论 `needs-attention`，3 项 high）。Codex 认为复审规则本身没有新的核心冲突，但首审第 1、2 项没有真正闭合。
- 按规则第 5 条，复审仍有核心逻辑问题时停下交用户，不自动进入第三轮。下面 3 项都是首审修复的补漏，范围明确，已修复并补测；是否放行由用户裁决。

| # | 级别 | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|---|
| 1 | high | `status --ignored` 把整个 `__pycache__/` 折叠成一行，目录里混入的 checkpoint 被白名单放行 | **采纳**。改用 `git ls-files --others --ignored --exclude-standard` 逐个枚举被忽略的文件；白名单收紧为：根目录 `GIT_STAMP.json`、任意位置 `.DS_Store`、`__pycache__/` 下的 `*.pyc` | `scripts/gitflow.sh` `cmd_cleanup` | `test_checkpoint_hidden_in_pycache_is_refused`（在首审修复版本上 RED，现 GREEN） |
| 2 | high | 只校验 verdict 与 findings 是否为数组，不符合真实 schema 的结论（缺 `next_steps`、空 finding、非法 severity 等）仍可落盘 | **采纳**。读取 companion 自带的 `schemas/review-output.schema.json`，逐字段校验 `result`（必需字段、枚举、类型、范围、`additionalProperties: false`、每个 finding 的结构）；找不到 schema 即失败 | `scripts/codex_review.sh` 校验段 | `CodexReviewOutputTests`：合法夹具改为完全符合 schema；新增缺 `next_steps`、空 summary、空 finding、非法 severity、`line_start=0`、`confidence=2`、多余字段等拒绝用例 |
| 3 | high | 「查存在」与 `mv` 之间有并发窗口，后完成的审查会覆盖先完成的 | **采纳**。改用硬链接原子发布：目标已存在时 `ln` 直接失败，本次原始输出保留在唯一临时文件 | `scripts/codex_review.sh` 发布段 | `test_concurrent_publish_never_overwrites`（替身在校验期间抢先写入正式文件 → 本次退出 1、先到者原样保留、本次输出可追溯） |

- 测试：`tests/test_workflow_scripts.py` 31/31 通过（默认 locale 与 `LC_ALL=C`）。
