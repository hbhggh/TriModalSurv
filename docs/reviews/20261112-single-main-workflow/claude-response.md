# 首审处理：20261112-single-main-workflow

- 审查对象：`main` 上 `5c508587..5d69a1a3` 三个提交，重点是 `5d69a1a3`（chore(workflow)）里的 `scripts/gitflow.sh`、`tests/test_workflow_scripts.py` 与规则文档。`7c5d92f1`、`97ff217b` 是把 dev 工作树里已有内容原样归并入库，焦点里已说明不必逐文件审。
- 首审调用：2026-11-13 08:34 由主对话经 Terminal 面板发起 `scripts/codex_review.sh docs/reviews/20261112-single-main-workflow --base 5c508587`，08:37 落盘本目录的 `codex-review.json`（只留本地）。入库版本是 `codex-review.public.json`，只把仓库根替换为 `<仓库根>`。
- 首审结论：verdict `needs-attention`，3 条 finding，均为 high。
- 处理方：执行会话（用户裁决 2026-11-13：结果交给执行会话处理；主对话不写本目录，也不再发起审查）。

## 逐条处理

| # | 级别 | finding | 处理 |
| --- | --- | --- | --- |
| 1 | high | freeze 未绑定获审候选 H，可冻结未审代码 | **采纳**。修法经用户裁决：`--candidate <H>` 必填，见下 |
| 2 | high | freeze 不是事务操作，失败会留下可误认的正式 tag | **采纳**。tag 改为最后一步，中途失败回滚 |
| 3 | high | `--no-worktree` 的生产 stamp 会被后续 freeze 覆盖且未绑定 tag | **采纳**。修法经用户裁决：写成 run 级文件，见下 |

### 用户裁决（2026-11-13，修复前征询）

#1、#3 的修法会改 AGENTS.md「Git 工作流」第 6 条的命令写法与操作口径。按「自动审查闭环」第 5 条，修复前先请用户裁决：

- #1：选「必填 `--candidate H`」。另外两个选项是可选参数、保持手工核对。
- #3：选「写成 run 级文件」，由 gitflow.sh 直接调用 `gitstamp.build_stamp`，不改 `scripts/git_stamp.py`。另外两个选项是给 git_stamp.py 加参数、保持现状。
- CLAUDE.md 节点一：选「不改」。理由是 freeze 已经强制做这项核对，节点一原有的 provenance 三项不变。

### #1 修复（`scripts/gitflow.sh` 新增 `require_reviewed_candidate`）

- `freeze <run_id> --candidate <H>`，`--candidate` 必填，在任何副作用之前核对：
  - H 须是 7–40 位小写十六进制提交哈希。HEAD、`main`、`refs/heads/main`、`HEAD^{commit}` 这类会移动的符号引用一律拒绝；不存在或短哈希有歧义也拒绝。
  - H 须是 `main` HEAD 的祖先（`git merge-base --is-ancestor`）。这样能拦住来自未合入 `wt/*` 分支的候选。
  - `git diff --quiet H <main HEAD> -- <CODE_PATHS>` 须无差异，有差异就列出改动的文件并拒绝。`git diff` 出错（退出码大于 1）也拒绝。
- 没有照 Codex 建议写成「`main` HEAD != H 即拒绝」。原因是那样会让 H 之后的论文、笔记类提交阻塞冻结，违反用户裁决 2（2026-11-12，manuscript 不阻塞实验）与现行第 6 条的口径「H 之后 CODE_PATHS 下没有新提交」。现在的修法正好把第 6 条原来的手工 diff 变成脚本强制，不改规则含义。
- `candidate` 不限制运行位置：未合入 `main` 的 H 会被祖先核对拦下。`candidate` 结尾提示的冻结命令改为带上完整哈希的 `freeze <run_id> --candidate <H>`。

### #2 修复（事务：tag 存在即冻结完整成功）

- 副作用顺序改为：`mkdir WT_ROOT` → 建 run worktree（含分支）→ 挂链接并核对 → 写 stamp → **最后一步才打 tag**。`--no-worktree` 的顺序是：发布 run 级 stamp → 打 tag。
- 回滚挂在 `tx_begin` 安装的 EXIT trap 上：中途任何 `die`、`set -e` 退出或显式 `exit`，都按登记逐项撤掉本次亲手建的东西。
  - 先删临时 stamp 文件和已发布的 run 级 stamp。
  - 再摘掉登记过、仍合法的链接（`rm` 链接本身，不递归，不碰主目录目标）。
  - 然后 `git worktree remove`（不加 `--force`）并 `prune`。
  - 最后，分支仍指向本次提交时 `git branch -d`（不用 `-D`）。
  - 删 worktree 之前用 `tx_owns_worktree` 核对：它仍是本仓库的 worktree 顶层，且 HEAD 等于本次检出的提交。撤不掉的照实报告，并保留现场。
- 成功时由 `tx_end` 解除 trap。`$( )` 与 `( )` 子 shell 不继承 EXIT trap，失败会经 `set -e` 回到主 shell 再回滚。这一点由下面的故障注入测试钉住，在 macOS `/bin/bash` 3.2、UTF-8 locale 下实测通过。
- `wt-add` 是同一模式（建 worktree 后挂链接），复用同一套回滚。
- 删除了旧的提示语「已打 tag，但建 run worktree 失败；可 git tag -d 再重试」。

### #3 修复（run 级 stamp，不可覆盖，绑定 tag）

- `--no-worktree` 不再写主目录根的 `GIT_STAMP.json`。stamp 改写成 run 级文件 `WT_ROOT/run-<run_id>.GIT_STAMP.json`，生成方式：
  - 主目录有 `src/trimodalsurv/gitstamp.py` 时，调用其 `build_stamp`。这和服务器端 gitstamp 读取的是同一格式，含逐文件 blob 哈希。另外加上 `run_id` 与 `run_tag` 两个字段，读取端只用 `commit`、`branch`、`files`，多出的字段不影响。
  - 断言 stamp 的 `commit` 等于待冻结提交，不等就失败。
  - 先写唯一临时文件，再用硬链接发布：目标已存在即失败，绝不覆盖。freeze 在副作用之前还会预检这个文件不存在。
- 同步时用 `git archive run/<run_id>`，并把这个文件作为 `GIT_STAMP.json` 放进快照根目录。已同步写进 AGENTS.md 第 6 条、`docs/workflow/git-workflow.md`、`scripts/README.md`。
- `--no-worktree` 与 `STAMP_CMD` 同时出现时拒绝，避免绕回旧路径。
- 带 worktree 的 freeze 仍在 run worktree 根由 `scripts/git_stamp.py` 写 `GIT_STAMP.json`。这份 stamp 本来就随该 run 的 worktree 存在，不会被别的 run 覆盖，所以不改。worktree 里没有 git_stamp.py 时，也走上面的 run 级文件。

### 补测（`tests/test_workflow_scripts.py`，67 → 69 条，另有 subTest）

新增测试：

| 类 | 测试 | 覆盖 |
| --- | --- | --- |
| GitflowCodeGateTests | `test_freeze_requires_candidate` | 不给 `--candidate` 即拒绝，不留 tag、分支、目录 |
| GitflowCodeGateTests | `test_freeze_refuses_symbolic_short_or_unknown_candidate` | HEAD、main、refs/heads/main、`HEAD^{commit}`、过短、不存在的哈希都拒绝 |
| GitflowCodeGateTests | `test_freeze_after_paper_only_commits_binds_reviewed_code` | H 之后只有论文提交时放行，tag 打在当前 main HEAD；用 10 位短哈希 |
| GitflowCodeGateTests | `test_freeze_refuses_code_commit_after_candidate` | H 之后 main 有代码提交、工作树干净时仍拒绝，并列出 `src/model.py` |
| GitflowCodeGateTests | `test_freeze_refuses_candidate_not_on_main` | 候选来自未合入分支，且只改了论文，只有祖先核对能拦下 |
| GitflowLinkedAssetsTests | `test_stamp_failure_rolls_back_worktree_branch_and_links` | `STAMP_CMD=false`，分支模式与 detached 模式 |
| GitflowLinkedAssetsTests | `test_link_failure_midway_rolls_back` | 假 `ln` 让第二条链接失败，freeze 与 wt-add 都测 |
| GitflowLinkedAssetsTests | `test_tag_failure_at_the_last_step_rolls_back_everything` | 假 `git` 只让 `git tag <名> <提交>` 失败，两种模式都测 |
| GitflowLinkedAssetsTests | `test_worktree_add_failure_leaves_no_tag_or_branch` | WT_ROOT 只读，freeze 与 wt-add 都测 |
| GitflowRunStampTests（新类） | `test_run_level_stamp_is_bound_to_tag_and_never_overwritten` | 拷入真实 `gitstamp.py` 走生产路径；连续冻结两个不同提交，旧 run 的 stamp 字节不变，新 stamp 的 commit 与文件哈希都更新，主目录根不出现 GIT_STAMP.json |
| GitflowRunStampTests | `test_existing_run_stamp_is_refused_and_left_untouched` | run 级 stamp 已存在时拒绝，且文件不被改动 |
| GitflowRunStampTests | `test_tag_failure_removes_the_published_stamp` | 打 tag 失败时撤掉已发布的 stamp |
| GitflowRunStampTests | `test_stamp_failure_leaves_no_tag_and_no_stamp` | `PYTHON_BIN=false` 时不留 tag、stamp、临时文件 |

- 原有的 freeze 调用全部补上 `--candidate <当前 HEAD>`。`--no-worktree` 内置最小版的断言字段由 `tag` 改为 `run_tag`，并新增「主目录根不出现 GIT_STAMP.json」。
- **在未修复代码上为红**：
  - 修复前的 gitflow.sh 不认 `--candidate`，直接跑会因为参数错误全红，红的原因不对。所以另做了一份只多认 `--candidate`（并忽略它）的旧脚本垫片，在仓库外运行新测试。
  - 结果 11 条失败、56 条通过。失败的正好是新增与改动的测试，原因符合预期：失败后 tag 还留着；stamp 走内置版且会覆盖已有文件；未审候选照样冻结。
  - 两条打 tag 失败的用例在旧代码上不会红，因为旧代码第一步就打 tag，打失败也不留东西。它们守的是新增的「回滚已发布 stamp」，由下面的变异自检证明有效。
- **变异自检**：逐个删掉新守卫各跑一次，11 个变异全部变红。
  - 删祖先核对、删代码范围 diff 核对、删十六进制格式核对、删候选核对调用。
  - 不装回滚 trap，回滚时不摘链接、不删分支、不删 run 级 stamp。
  - tag 挪回 worktree 之前，run 级 stamp 改写主目录根，stamp 发布改为可覆盖。
  - 第一轮有 2 个变异仍是绿的，原因是测试用例不够，已补用例后变红：十六进制核对被长度检查掩盖了，补了 7 位以上的符号引用用例；「回滚删 stamp」原来没有用例走到，补了打 tag 失败的注入。
  - 未覆盖：Python 里「stamp 的 commit 必须等于待冻结提交」那条断言，测试中 HEAD 总等于冻结提交，触发不到。它是并发移动 HEAD 时的防御。

### 测试结果

- `PYTHONDONTWRITEBYTECODE=1 <protomasksurv-exp1>/bin/python -m pytest tests/test_workflow_scripts.py -q -p no:cacheprovider` 连跑 3 遍，每遍 69 passed。另在 `LC_ALL=en_US.UTF-8` 下跑 1 遍，69 passed。
- `PYTHON_BIN=<protomasksurv-exp1>/bin/python scripts/ci.sh`：713 passed，7 skipped，打印 `CI PASS`，退出码 0。

### 改动文件

- `scripts/gitflow.sh`：帮助说明、`parse_link_args` 增加 `--candidate`、`require_reviewed_candidate`、事务框架 `tx_*`、`publish_run_stamp` 与 `write_worktree_stamp`（取代 `write_stamp`）、`cmd_freeze` 与 `cmd_wt_add` 的副作用段。
- `tests/test_workflow_scripts.py`：见上。
- 同步文档，只改与这三项修复对应的句子：
  - `AGENTS.md`「Git 工作流」第 6 条：freeze 写法、候选核对、事务、`--no-worktree` 的 stamp 位置。
  - `docs/workflow/git-workflow.md`：一句话总览、`STAMP_CMD` 行、正式实验循环第 4 步、命令速查三行。
  - `scripts/README.md`：同步源一句。
  - `tests/README.md`：`test_workflow_scripts.py` 的覆盖说明。
- 未改：CLAUDE.md（用户裁决）、`scripts/git_stamp.py`、`src/trimodalsurv/gitstamp.py`。

### 本轮之外的现象（只记录，未处理）

- 修复期间主目录出现 `D handoff-论文生成.md`：这个已跟踪文件（第 2 个提交 `97ff217b` 入库）被从工作树删除了。不是本轮修复造成的，未恢复，交主对话或用户判断。它会出现在 round2 的工作树审查范围里，与本轮修复无关。

## 复审 round2（2026-11-13 09:28，停下交用户裁决）

- 调用：执行会话经 Terminal 面板发起 `scripts/codex_review.sh docs/reviews/20261112-single-main-workflow/round2 <焦点>`（工作树范围，因为修复未提交）。原文 `round2/codex-review.json` 只留本地，入库版本是 `round2/codex-review.public.json`。
- 结论：verdict `needs-attention`，2 条 high。首审的三条 finding 没有被复审再次指出。复审仍有核心逻辑问题，按「自动审查闭环」第 3、5 条停下交用户裁决，**不自动进入第三轮，也没有动手修复**。

| # | 级别 | finding | 执行方初步判断（待用户裁决） |
| --- | --- | --- | --- |
| R2-1 | high | 调用方可缩窄 CODE_PATHS 冻结未审代码 | **成立**。候选核对和干净门都用环境变量 `CODE_PATHS`：获审后改了 `src`，再用 `CODE_PATHS=manuscript freeze --candidate H` 能绕过。修法有两种，都会改 AGENTS 第 3 条「可用同名环境变量覆盖」的含义：(a) 候选核对固定用默认路径与覆盖值的并集，覆盖只许扩大、不许缩小；(b) candidate 把路径集合写进持久记录，freeze 要求完全一致。需要用户选择 |
| R2-2 | high | 并发同名事务的回滚会删除另一事务的产物 | **成立**，是本轮新增回滚带来的新风险。触发条件是两个进程用同一个 run_id 或 wt 名同时冻结。修法：在预检前对 run_id / name 取原子锁（如 git 管理目录里的 `mkdir` 锁），并给事务写唯一 ownership token，回滚只删 token 匹配的对象；补受 barrier 控制的并发测试。只改脚本和测试，不改规则含义 |

另外两项待办：主对话晚到的消息要求 ① candidate 只许在检出 main 的主目录运行、② stamp 记录候选 H。用户已选「补上」，原计划在 round2 出结论前停掉复审、补完再重发。但 round2 在用户答复前已经出了结论，这个前提不成立，所以 ①② 没有实施，与 R2-1、R2-2 一起交用户裁决。CLAUDE.md 按用户在本会话的裁决不改。

## round2 处理与第三轮修复（用户裁决 2026-11-13：全修后再审一次）

用户选「全修后再审一次」，即授权第三轮审查。R2-1 选「只许扩大」。CLAUDE.md 仍按用户在本会话的裁决不改。

| # | 处理 | 修复位置 |
| --- | --- | --- |
| R2-1 | **采纳**（用户选修法：只许扩大） | `CODE_PATHS` 环境变量只作追加项，实际范围恒为默认 7 项与追加项的并集，并去重。candidate 干净门、freeze 干净门、候选 diff 核对、status 都用它，提示打印实际生效的范围 |
| R2-2 | **采纳** | 新增 `acquire_lock`：在主仓库 git 目录 `gitflow-locks/` 下用 `mkdir` 原子建锁，freeze 与 cleanup 用 `run-<id>`，wt-add 与 wt-rm 用 `wt-<name>`，任何状态预检之前就加锁。锁已存在即拒绝，不删别人的锁，什么都不动。退出处理 `on_exit` 统一负责回滚和释放锁。另外，worktree 建成后在其 git 管理目录写入本次事务的 token，回滚只删 token 相符、且由本次 `worktree add` 成功建出的 worktree |
| ① | **实施**（用户已选补） | candidate 只许在检出 main 的主目录运行，其他 worktree、其他分支、在别处检出了 main 的 worktree 都拒绝。另外多打印一行完整哈希，就是传给 freeze 的 H |
| ② | **实施**（用户已选补） | 两种模式都写 run 级 stamp，记录 `candidate`（H 的完整哈希）、`commit`（实际冻结的 main HEAD）和 `run_tag`。带 worktree 时，worktree 内的 `GIT_STAMP.json`（git_stamp.py 或 STAMP_CMD 生成）照旧保留。freeze 输出也打印两个哈希与 stamp 路径 |

### 补测（69 → 77 条）

| 测试 | 覆盖 |
| --- | --- |
| `test_narrowed_code_paths_cannot_hide_dirty_source` | R2-1：src 有脏改动，`CODE_PATHS=manuscript` 时 candidate 与 freeze 都拒绝 |
| `test_narrowed_code_paths_cannot_hide_reviewed_code_change` | R2-1：获审后提交了 src 改动，`CODE_PATHS=manuscript` 冻结仍拒绝 |
| `test_candidate_refuses_outside_main_checkout` | ①：wt 分支的 worktree、主目录的其他分支、在别处检出 main 的 worktree，三种情况都拒绝 |
| `test_candidate_prints_full_hash_for_freeze` | ①：提示里给出 `--candidate <完整哈希>` |
| `test_worktree_freeze_records_candidate_in_run_level_stamp` | ②：带 worktree 且用 STAMP_CMD 时也写 run 级 stamp；H 与实际冻结提交不同（之后有论文提交）时两者分别记录 |
| `test_run_level_stamp_is_bound_to_tag_and_never_overwritten`（加断言） | ②：生产路径的 stamp 含 `candidate` |
| `test_concurrent_same_name_never_destroys_the_winner` | R2-2：受控屏障。假 git 让第一个进程过完全部预检后停在 `worktree add` 前，第二个同名进程跑完后再放行。freeze 与 wt-add 都测：恰好一方成功，成功方的 worktree、分支、tag 完好，锁已释放，主目录资产完好 |
| `test_stale_lock_refuses_without_touching_anything` | R2-2：残留锁时拒绝，什么都不建，也不删别人的锁 |
| `test_successful_freeze_and_wt_add_release_their_locks` | R2-2：成功和收尾之后都不留锁；回滚类测试也同样断言不留锁 |

- **在 round2 版代码上为红**：7 条新测试失败，70 条通过。并发测试第一版把 `first.communicate()` 写进了断言消息，消息会被立即求值，等于先让第一个进程跑完，竞争根本没发生，所以这条测试在 round2 代码上是假绿。改正后在 round2 代码上复现了问题：成功方的 worktree 和分支被失败方的回滚删掉，只剩 tag。
- **变异自检（第三轮新增 8 个）**：全部变红。这 8 个分别是：
  - 环境变量直接替换范围；
  - 删主目录位置核对（第一版是假绿，补了「在别处检出 main」的用例）；
  - 删 main 分支核对；
  - stamp 不记 candidate；
  - worktree 模式不写 run 级 stamp；
  - 锁不互斥；
  - on_exit 不调回滚；
  - 锁不释放。
  首审修复的 10 个变异复跑，仍全部变红；原来「不装 trap」那一项因结构改动，由「on_exit 不调回滚」取代。
- **未单独覆盖**：事务 token 核对。锁在的时候同名竞争进不来，token 是第二道防线，只有去掉锁才能单独测到它。

### 测试结果（第三轮修复后）

- workflow 测试连跑 3 遍，每遍 77 passed；`LC_ALL=en_US.UTF-8` 下 1 遍，77 passed。
- `scripts/ci.sh` 全量：721 passed，7 skipped，CI PASS，退出码 0。

### 文档同步

- `AGENTS.md`「Git 工作流」第 3 条：CODE_PATHS 只许扩大。
- 第 4 条：candidate 限检出 main 的主目录运行，打印完整哈希。
- 第 6 条：同名互斥锁；run 级 stamp 记录候选与冻结提交。
- `docs/workflow/git-workflow.md`：环境变量表、正式实验循环第 1 步与第 4 步、命令速查。
- `tests/README.md`：覆盖说明。
- 规则含义上的改动只有用户裁决过的这几项。CLAUDE.md 不改。

## 第三轮审查 round3（2026-11-13 10:23，停下交用户裁决）

- 调用：执行会话经 Terminal 面板发起，范围是工作树。原文 `round3/codex-review.json` 只留本地，入库版本是 `round3/codex-review.public.json`。
- 结论：verdict `needs-attention`，2 条 high、1 条 medium。round2 的 R2-2（同名并发）没有被再次指出。Codex 说明它在只读沙箱里没有可写临时目录，没能独立复跑 pytest。
- 用户授权的就是这一次审查，所以停下交用户，**没有修复**。

| # | 级别 | finding | 执行方判断 |
| --- | --- | --- | --- |
| R3-1 | high | 排除型 pathspec 仍可缩窄 CODE_PATHS | **成立**。追加项会原样交给 git，`CODE_PATHS=':(exclude)src'` 会把默认的 src 排除掉，R2-1 的修复没有堵住这条路。修法只涉及脚本：拒绝以 `:` 开头和含 `*?[` 的追加项，或对这些 git 调用设 `GIT_LITERAL_PATHSPECS=1`；再补三个负例：candidate、freeze 干净门、候选 diff。不改规则含义 |
| R3-2 | medium | candidate 可能发布没有经过本次 CI 的并发新提交 | **成立**。现在 CI 跑完才读 HEAD，并且分三次读。修法：CI 前读一次完整 HEAD，CI 和干净门结束后再读一次，要求两次相等，所有输出都从这一次读取的值生成。只改脚本 |
| R3-3 | high | tag 打完之后、`tx_end` 之前收到信号，会留下伪完整冻结 | **成立**，窗口只有两条命令之间。修法：on_exit 回滚前先查预期 tag，存在且严格指向 TX_COMMIT 时，按已提交处理并保留全部产物；再补「tag 创建后立即终止进程」的确定性测试。只改脚本和测试 |

三条修法都只改 `scripts/gitflow.sh` 和测试，规则含义不变。但审查轮次已经到了用户授权的上限，是否修复、修完要不要再审，由用户决定。

## round3 处理（用户裁决 2026-11-13：修但不再审）

用户选「修但不再审」：三条都修，不再发起第四轮审查，改由主对话独立审 diff、复跑测试。

| # | 处理 | 修复位置 |
| --- | --- | --- |
| R3-1 | **采纳** | 两层防线。第一层：`CODE_PATHS` 的追加项以 `:` 开头（pathspec 魔法，如 `:(exclude)src`、`:!src`、`:(glob)…`）时，脚本一启动就拒绝。第二层：代码门的 `git status` 与候选核对的两次 `git diff` 都加 `--literal-pathspecs`，所有路径一律按字面处理 |
| R3-2 | **采纳** | candidate 在 CI 之前只读一次完整 HEAD，CI 和干净门结束后再读一次，两次不同即拒绝，并报出两次的哈希。短哈希、subject、完整哈希和 freeze 提示都从这一次读取的值生成 |
| R3-3 | **采纳** | 回滚前先认 tag：on_exit 发现 `TX_TAG` 已存在且严格指向 `TX_COMMIT`，就按已提交处理，保留全部产物，只清掉事务 token。`acquire_lock` 另外 trap INT、TERM、HUP，分别转成 `exit 130`、`exit 143`、`exit 129`：实测 bash 3.2 被未捕获的信号终止时也会跑 EXIT trap，但 `$?` 是 0 |

### 补测（77 → 81 条）

| 测试 | 覆盖 |
| --- | --- |
| `test_exclude_pathspec_cannot_narrow_code_paths` | R3-1：`:(exclude)src`、`:!src`、`:(glob)…` 三种写法下，candidate 干净门、freeze 干净门都拒绝；获审后提交了 src，候选 diff 也拒绝 |
| `test_candidate_refuses_commit_made_while_ci_runs` | R3-2：用 CI_CMD 在 CI 期间提交一次，candidate 拒绝，报出 CI 开始时的 HEAD，也不给 freeze 提示 |
| `test_signal_right_after_tag_keeps_the_complete_freeze` | R3-3：假 git 真正创建 tag 后立刻向 gitflow 发 SIGTERM。检查：退出码 143；tag、run worktree、分支、链接、run 级 stamp 都在；锁已释放；之后 cleanup 能正常收尾 |
| `test_signal_right_after_tag_keeps_the_run_stamp` | R3-3 的 `--no-worktree` 模式：tag 与 run 级 stamp 都保留 |

- **在 round3 版代码上为红**：4 条全部失败，原因符合预期。
  - 排除写法没有被拒绝。
  - CI 期间的并发提交被当成了候选。
  - 收到信号后，worktree 和 stamp 被回滚掉了。
- **变异自检**，以下 5 个变异全部变红：
  - 魔法拒绝与 literal 两层同时去掉；
  - 去掉 CI 前后的 HEAD 核对；
  - on_exit 不认已打的 tag；
  - 不把 TERM 转成 exit；
  - 前面几轮因代码改动锚点失效的两个旧变异，换新锚点后重跑（删代码范围 diff 核对、on_exit 不调回滚）。

  前两批变异（首审修复 9 个、round2 修复 7 个）复跑，也都仍然变红。只去掉 R3-1 两层中的任意一层，测试不会变红。这是有意的两层冗余，所以只能用「两层都去掉」来证明测试有效。

### 测试结果

- workflow 测试连跑 3 遍，每遍 81 passed；`LC_ALL=en_US.UTF-8` 下 1 遍，81 passed。
- `scripts/ci.sh` 全量：725 passed，7 skipped，CI PASS，退出码 0。

### 文档同步

- `AGENTS.md`「Git 工作流」第 3 条：追加项只能是普通相对路径。
- 第 4 条：CI 前后 HEAD 有变化即拒绝。
- `docs/workflow/git-workflow.md`：环境变量表的 `CODE_PATHS` 一行。
- `tests/README.md`：覆盖说明。

按用户裁决不再审查。round3 修复的正确性，由主对话独立审 diff、复跑测试来把关。
