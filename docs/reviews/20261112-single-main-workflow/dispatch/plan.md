# 派单计划：单主干工作流的脚本与规则改写

日期：2026-11-12。依据：仓库根 `单主干工作流规范与无损归并执行计划-handoff.md` 第 0 节（6 项用户裁决）与第 2 节（规格）。本文件是两个子任务的唯一 spec；与契约冲突时以契约为准并在 notes 里指出。

路径记号：`<主目录>` = 检出 `main` 的仓库根；`<WT_ROOT>` = `<主目录>.worktrees`。

## 共同禁止事项

- 禁止 `git add` / `commit` / `stash` / `checkout` / `reset` / `merge` / `branch` / `tag` / `worktree` 等任何改变仓库状态的 git 命令（测试沙箱里的临时仓库除外）。只读的 `git diff` / `status` / `log` / `grep` 可以用。
- 只改各自白名单里的文件。白名单外发现问题写进 notes，不动手。
- 不读写 `<主目录>.worktrees/dev/`（另有会话在其中工作），不碰 `.claude/worktrees/`。
- 不跑全量 `scripts/ci.sh`；只跑本文件给出的定向命令。
- 自写内容不出现本机绝对路径（坑 I05-04）；Markdown 表格单元格内不写竖线符（坑 E52）。
- 执行中把过程与发现追加到自己的 notes 文件，完成后写 result 文件（改了什么、测试命令与原始输出、未解决事项）。

## 任务 A（核心逻辑，coder-core）：`scripts/gitflow.sh`

白名单：`scripts/gitflow.sh`；`scripts/codex_review.sh` 仅第 6 行注释（「如 dev 候选用 --base main」改成单主干下的说法，如「如审查 main 上某个提交之后的改动用 --base <commit>」）。
只读：`tests/test_workflow_scripts.py`（主控已写好新测试，在旧脚本上 23 红 33 绿；不要改它，认为测试本身有错就写进 notes 并停下说明）。
过程文档：`docs/reviews/20261112-single-main-workflow/dispatch/notes-gitflow.md`、`result-gitflow.md`。

测试命令（要求全绿，且连跑 3 遍都绿）：

```bash
PYTHONDONTWRITEBYTECODE=1 <protomasksurv-exp1 环境>/bin/python -m pytest tests/test_workflow_scripts.py -q -p no:cacheprovider
bash -n scripts/gitflow.sh
```

### 规格

1. 删除 `init`、`squash` 子命令与 `DEV_BRANCH`。调用它们走既有的「未知子命令 '<名>'」分支（退出码非 0）。帮助文本（文件头注释）同步改写，不再出现 `squash` 与 `DEV_BRANCH`，要出现 `candidate`、`freeze <run_id>`、`--no-worktree`、`--link-assets`、`cleanup <run_id>`、`wt-add <name>`、`wt-rm <name>`、`CODE_PATHS`、`RUN_BRANCH_PREFIX`。
2. 新增可用环境变量覆盖的配置：`CODE_PATHS`（默认 `src configs scripts tests experiments pyproject.toml conftest.py`，空格分隔）、`WT_BRANCH_PREFIX`（默认 `wt/`）。
3. 代码范围干净门：`git status --porcelain --untracked-files=all -- <CODE_PATHS 各项>` 输出为空才算干净（`core.quotePath=false`）。不干净时报错并列出这些路径。`manuscript/`、根目录笔记等 `CODE_PATHS` 之外的改动不阻塞。
4. `candidate`：不再要求 `dev` 分支。跑 CI（沿用 `run_ci`），再过代码门，打印 `H = <短哈希>` 与摘要。
5. `freeze <run_id> [--no-worktree] [--link-assets <relpath>...]`：
   - 须在 `<主目录>` 且检出 `MAIN_BRANCH`。
   - 顺序：解析全部参数（未知选项即拒绝，报错里带上该选项原文）→ 校验 `--link-assets` 各路径 → 过代码门 → 之后才打 tag、建 worktree。任何一步拒绝都不得留下 tag、分支或目录。
   - 默认行为与现有一致：tag `run/<run_id>`，`<WT_ROOT>/run-<run_id>`，分支 `train/<run_id>`（`RUN_BRANCH_PREFIX=''` 时 detached），生成 stamp。
   - `--no-worktree`：只打 tag，不建 worktree 与分支；stamp 在 `<主目录>` 生成（有 `scripts/git_stamp.py` 就用它，否则内置最小版写到 `<WT_ROOT>/run-<run_id>.GIT_STAMP.json`，字段含 `commit`、`tag`、`dirty: false`）。`--no-worktree` 与 `--link-assets` 同时给出时拒绝。
6. `wt-add <name> [--link-assets <relpath>...]`：`name` 须匹配 `^[A-Za-z0-9][A-Za-z0-9._-]*$`；从 `MAIN_BRANCH` 建 `<WT_ROOT>/wt-<name>`，分支 `<WT_BRANCH_PREFIX><name>`；目录或分支已存在即拒绝。
7. `--link-assets` 校验（全部在产生任何副作用之前完成）：
   - 至少给一个路径；拒绝绝对路径、空串、含 `..` 分量的路径。
   - `<主目录>/<relpath>` 必须存在。
   - 该路径在待检出的提交里不得已存在（`git cat-file -e "<commit>:<relpath>"` 命中即拒绝），它的任何祖先也不得是该提交里的非目录条目。
   - 同一次调用里的路径不得重复，也不得互为祖先（否则后一个会穿过前一个链接写进主目录）。
   - 建链接：在 worktree 里 `mkdir -p` 父目录，`ln -s <主目录物理路径>/<relpath> <worktree>/<relpath>`。
   - 登记：把每个 relpath 逐行写进该 worktree 的 git 管理目录下的 `gitflow-linked-assets`（`git -C <worktree> rev-parse --absolute-git-dir` 所指目录），不落在工作树里。
   - `freeze` 原有的「run worktree 创建后不干净，异常」断言要扣除登记的链接。
8. `cleanup <run_id>` 与 `wt-rm <name>` 的收尾顺序（坑 G1、G5）：
   - 身份核对。`cleanup` 保持现有全部核对（tag 存在、HEAD 严格等于 tag、检出形态匹配、冻结提交仍在 `MAIN_BRANCH` 上）。`wt-rm` 核对：目录存在且是可用 worktree、检出的正是 `refs/heads/<WT_BRANCH_PREFIX><name>`、该分支已是 `MAIN_BRANCH` 的祖先（未合入即拒绝，报错里带分支名）。
   - 「合法链接」的定义：登记文件里有这一行、该路径当前仍是符号链接、`readlink` 的值严格等于 `<主目录物理路径>/<relpath>`。
   - 未提交 / 未跟踪检查用 `git status --porcelain --untracked-files=all`，忽略文件检查用 `git ls-files --others --ignored --exclude-standard`（都带 `core.quotePath=false`）。两份清单里只扣除合法链接；忽略文件再按原白名单放行（根 `GIT_STAMP.json`、`.DS_Store`、`__pycache__/*.pyc`）。有任何剩余即拒绝，报错含「不删」并列出这些路径，此时不得动任何链接、文件、分支。
   - 登记过但已不是合法链接的路径（被换了目标、被换成真实目录、指向主目录外）一律拒绝。未登记的符号链接按普通未跟踪 / 忽略文件处理，也就是拒绝。
   - 全部通过后才逐个摘链接：`rm -- <worktree>/<relpath>`，不带尾斜杠，不加 `-r`，执行前再判一次 `-L`。然后 `git worktree remove`（不加 `--force`）、`git worktree prune`、`git branch -d`（不升级成 `-D`）。tag 保留。
9. `status`：单主干视图（当前分支、worktree 列表、最近的 `run/*` tag、代码门是否干净），不再提 dev。
10. 红线：`-h` / `--help` / 无参数先于仓库探测退出 0，未知子命令非 0（坑 G2）；变量后紧跟中文或全角标点一律 `${var}`（坑 G3，`test_no_unbraced_variable_before_multibyte_text` 守着）；macOS `/bin/bash` 3.2 兼容：`set -u` 下空数组用 `${arr[@]+"${arr[@]}"}` 展开，不用 `mapfile`、关联数组、`${var,,}`，不在 `$(...)` 里写 `case`（坑 E37）；拒绝路径一律保留现场，不 `--force`、不 `-D`、不 `rm -r`。

### 验收

- 上面的测试命令全绿（56 条左右），连跑 3 遍。
- 原有 16 条 `GitflowCleanupTests` 一条不改、全部通过。
- result 里贴最后一遍测试的原始输出尾部，并逐条说明规格 1–10 各落在脚本哪几行。

## 任务 B（文档，Opus）：规则文件改写

白名单：`AGENTS.md`、`CLAUDE.md`、`docs/workflow/git-workflow.md`、`scripts/README.md`、`tests/README.md`、`README.md`、`.colabignore`（仅第 5 行注释）。
过程文档：`docs/reviews/20261112-single-main-workflow/dispatch/notes-docs.md`、`result-docs.md`。
脚本接口以本文件任务 A 的规格为准（脚本正在并行改写，不要去读半成品）。

### 逐文件要求

1. `AGENTS.md`
   - 「Git 工作流」节整节重写为契约 2.1 的单主干规则，标题注明用户裁决 2026-11-12。必须覆盖：`<主目录>` 检出 `main` 是唯一日常工作区与本机唯一重资产真源；日常小步提交及前缀（`feat(I08):`、`fix(I08):`、`docs(paper):`、`docs(notes):`）；涉及代码改动先跑 CI（保留现有 `PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh` 的说明与 2026-09-28 实测备注）；`CODE_PATHS` 代码范围门；`candidate`；冒烟（保留「从待跑 commit 的干净快照 `git archive` 打包、校验和传输、`GIT_STAMP.json` 随代码同步」，去掉 squash 环节）；`freeze`（含 `--no-worktree`、`--link-assets`）；run worktree 与 `train/*` 只读、发现 bug 回 `main` 修并 freeze 新 run_id；结果 provenance 铁律（commit 须 `git branch --contains` 命中 `main`、`dirty=0`、正式实验有 `run/<run_id>` tag）；结果差不 revert；`cleanup`（保留现有全部核对项，补上符号链接只摘链接、不触碰目标）；`wt-add` / `wt-rm`；禁止 force-push 或改写已打 `run/*` tag 的 `main` 历史；提交后由用户决定何时 `git push origin main`。
   - 保留并改写会话 worktree 规则：应用自动建的 worktree（`~/.codex/worktrees/`、`.claude/worktrees/<名字>/`）只用于讨论、检索和只读操作；需要改代码或文档时，改动落在 `<主目录>`（`main`），或经 `wt-add` 建的 worktree。
   - 作废：常驻 `dev`、「禁止在主目录直接改代码」、「一个创新一个 commit」、squash 相关全部条目、第 13 条对 `STATUS.md` 的引用（该文件已删除）。
   - 节外散落引用：「自动审查闭环」第 2 条的「dev 候选用 `--base main` 审分支」改成单主干说法（已提交的改动用 `--base <起点 commit>` 审）；「Colab GPU」节里「按「Git 工作流」第 5 条」改成按节名或新编号引用，确保指向仍成立。
   - 其余各节（角色、研究目标、停机门、GPU 合同、执行纪律、互审、T/B/P/A/Q、AI 研究接力）一字不改。
2. `CLAUDE.md`：只改节点一的 provenance 条目。原「待跑 commit 已是 `main` HEAD（squash 完成、`dev` 已归位、`git diff main dev` 为空）；…」改为契约 2.1 第 5 点的三项：待跑 commit 已提交在 `main` 上且 `CODE_PATHS` 工作树干净；若使用冻结 worktree，其 HEAD 严格等于 `run/<run_id>` tag 且 `git status` 干净；`GIT_STAMP.json` 的 commit 等于该 tag 指向的 `main` 提交。其余不动。
3. `docs/workflow/git-workflow.md`：按现有「What is it / When / What must be true / How / Afterward / 脚本速查」骨架重写为单主干版本。包含：目录布局表、日常循环、正式实验循环（candidate → 互审 → 冒烟 → freeze → 跑 → cleanup）、按需并行 worktree（`wt-add` → 提交 → `merge --ff-only` 回 `main` → `wt-rm`）、`--link-assets` 的含义与边界（链接指向主目录真源；「只读」是约定，脚本不改目标权限；经链接写入会直接落到主目录；新产物写到 worktree 之外）、三种意外的处理、反查、脚本速查表。删除 init / squash / dev 归位的全部内容与「粘进 AGENTS.md 的规则块」里的旧条目（规则块改成与新 AGENTS 节一致，或改为一句指向 AGENTS.md）。
4. `scripts/README.md`：`gitflow.sh` 一行的子命令清单改为 `candidate` / `freeze` / `cleanup` / `wt-add` / `wt-rm` / `status`；第 29 行附近的同步源说明保留并与新规则一致；删除指向 `STATUS.md` 的链接。
5. `tests/README.md`：`test_workflow_scripts.py` 的描述补上代码范围门与 `--link-assets` 回归；删除指向 `STATUS.md` 的链接。
6. `README.md`：删除第 7 行指向 `STATUS.md` 的导航项。
7. `.colabignore`：第 5 行注释里的「第 5 条」改成与新 AGENTS 节一致的指向。

### 验收

- result 里给一张「旧句 → 保留 / 改写 / 作废」对照表，覆盖 `AGENTS.md` 原「Git 工作流」节每一条（原第 1–13 条与布局段）和上面点名的节外引用。
- `git diff -- AGENTS.md` 中，「Git 工作流」节与点名的两处节外引用之外不得有改动（主控会逐行核对；注意工作树里的 `AGENTS.md` 相对 HEAD 还多一个「Colab GPU」节，那是既有的未提交内容，要保留）。
- 白名单文件里 `grep -n -E "squash|worktrees/dev|STATUS\.md"` 无命中，`dev` 一词只允许出现在历史说明（如「原常驻 dev 已于 2026-11-12 退役」）与 `/dev/null` 中。
- 新增和修改的 Markdown 表格每行管道符数与表头一致。
