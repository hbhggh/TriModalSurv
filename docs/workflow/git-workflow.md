# 科研 Git 工作流：单主干 main × 代码范围门禁 × 按需临时 Worktree

> 一句话：**日常在主目录的 `main` 上小步提交 → 代码范围干净且 CI 绿灯时 `candidate` 得到候选 H → 互审与冒烟通过 → `freeze --candidate H` 核对冻结的仍是获审代码，在 `main` HEAD 打 `run/<run_id>` tag（按需建冻结 worktree）→ 跑正式实验，结果盖章指向该 tag 的提交 → `cleanup` 删掉临时 worktree，tag 永远留在 `main` 上。**
>
> 用户裁决 2026-11-12，取代此前「常驻开发分支 + 先压缩成单个 commit 再跑」的做法；原常驻 `dev` 分支及其 worktree 已于同日退役。项目内的强制规则以 `AGENTS.md`「Git 工作流」为准，本文件是它的展开说明。
>
> 配套脚本：`scripts/ci.sh`、`scripts/gitflow.sh`。两者与项目无关，拷进任何仓库的 `scripts/` 即可用。

---

## 【What is it?】 这是什么

一套面向「单人科研 + AI 高频改代码 + 昂贵实验 + 结果要进论文」的 Git 工作流。日常只有一个工作区，临时 worktree 只在需要隔离时出现：

| 对象 | 角色 | 允许改代码 |
|---|---|---|
| `main` 分支（主目录 `<主目录>`） | 唯一的日常工作区：代码、契约与交接文档、实验结果摘要、论文 `manuscript/` 都在这里小步提交；也是本机重资产（数据、特征、缓存、checkpoint、结果）的唯一真源 | 是 |
| `run/<run_id>` tag | 正式实验的永久锚点，指向冻结时的 `main` 提交；结果账本里的 commit 必须能对上它 | 不适用 |
| run worktree `<主目录>.worktrees/run-<run_id>/`（分支 `train/<run_id>`，一次性） | 冻结的正式实验源码，HEAD 严格等于 `run/<run_id>`。只读、禁止 commit，跑完连分支一起删。不想要分支标签可设 `RUN_BRANCH_PREFIX=` 用 detached；远端直接用 `git archive` 同步时可以不建（`--no-worktree`） | 否 |
| 并行 worktree `<主目录>.worktrees/wt-<name>/`（分支 `wt/<name>`，一次性） | 本地并行试验或多个 AI 同时改不同模块时的隔离现场。提交后快进合回 `main`，再删除 | 是 |
| 结果账本（仓库外或被忽略） | `run_id → commit → C-index`。删 worktree 不影响它 | 不适用 |

目录布局：

| 路径 | 检出 | 用途 | 寿命 |
|---|---|---|---|
| `<主目录>/` | `main` | 日常工作区与本机重资产唯一真源；I01–I08 的相对路径不变 | 常驻 |
| `<主目录>.worktrees/run-<run_id>/` | `train/<run_id>` 或 detached，HEAD = `run/<run_id>` | 正式实验的冻结源码，只读 | `freeze` 建，`cleanup` 删 |
| `<主目录>.worktrees/wt-<name>/` | `wt/<name>` | 本地并行隔离，可提交 | `wt-add` 建，快进合回后 `wt-rm` 删 |

`<主目录>.worktrees/` 下只会按需出现这两种目录，用完即删，不常驻任何 worktree。

为什么不再压缩成「一个创新一个 commit」：正式实验的版本追溯靠 `run/<run_id>` tag 与 `GIT_STAMP.json` 就能锚定，不需要 main 的提交粒度来承担；而常驻开发分支意味着两份工作区、两份重资产、一条要时刻归位的分支，维护成本高于收益。

多个创新之间靠**目录与文件名**隔离（`experiments/<ID>/`、config 选择），不靠分支。失败的创新文件留在树里，只在账本标 negative。

```text
main（主目录，唯一日常工作区）
● feat(I08): add recovery head
● docs(paper): draft results section        ← 论文改动不阻塞发车
● fix(I08): mask padding
● docs(notes): smoke log          ── tag run/i08-v1 ──→ run worktree @ 该提交，stamp = 该提交
● feat(I09): add new arm                     （正式实验在跑，main 照常前进）
● docs(paper): table 2            ── tag run/i09-v1 ──→ git archive run/i09-v1（--no-worktree）
```

---

## 【When should I think of using it?】 什么时候该想到它

出现下面任一信号时：

- AI（Claude / Codex）一次改十几个文件，你只掌握目标，diff 才是真正发生的事，需要高频存档点和廉价回退。
- 一次正式实验要烧几十 GPU 小时，跑之前必须确定「跑的是哪一版代码」，跑完之后必须能从数字反查到源码。
- 论文与代码在同一个仓库里同时推进，不希望「论文写到一半」挡住实验发车。
- 想在一台机器上同时推进两件事（一个在跑实验，另一个在改代码），又不想复制几十 GB 的重资产。
- 论文审稿时要回答「Table 1 这个数字来自哪一版代码」。

---

## 【What must be true before I start?】 开始前必须成立的前提

1. **Git ≥ 2.15**（`git worktree` 稳定），主目录检出 `main`。
2. **测试命令存在且退出码可信**：`scripts/ci.sh` 默认跑 pytest，没有 pytest 退回 unittest；也可用 `TEST_CMD` 指定。没有测试就先写一个 import 冒烟测试，门禁不能是空的。本项目的 CI 解释器固定为 `protomasksurv-exp1` 环境：`PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh`；默认的 `python3` 没有 torch / pytest，会有 4 个导入错误，那不是代码问题（2026-09-28 实测）。
3. **结果目录在临时 worktree 之外**：正式结果写到主目录对应的新 `run_id` 目录（`experiments/<ID>/results/<run_id>/`）、仓库旁的目录或远端服务器，绝不写进 run worktree 或并行 worktree（它们会被删）。
4. **有 stamp 机制**：每次正式运行记录 commit SHA 与 dirty 状态。项目有自己的（如 `scripts/git_stamp.py`）就用自己的；没有则 `gitflow.sh freeze` 自带最小版。
5. **两个脚本已拷入 `scripts/`** 并 `chmod +x`；需要的话用环境变量覆盖默认值（见下表）。
6. **大文件不在 Git 里**：数据集、checkpoint、日志走 `.gitignore`，只存在于主目录这一份真源；临时 worktree 需要时用 `--link-assets` 链接过去，不拷贝。
7. **AI 助手读得到规则**：规则正文在项目的 `AGENTS.md`「Git 工作流」节（`CLAUDE.md` 首行引入它）。

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `MAIN_BRANCH` | `main` | 唯一主干分支 |
| `CODE_PATHS` | 空（默认范围 `src configs scripts tests experiments pyproject.toml conftest.py`） | 代码范围的追加项，空格分隔，只能是普通相对路径（`:(exclude)` 等 pathspec 魔法写法拒绝）；只能扩大、不能缩小，实际范围恒为默认项与追加项的并集；范围外的改动不阻塞 |
| `WT_ROOT` | `<主目录>.worktrees` | run worktree 与并行 worktree 的存放目录 |
| `TAG_PREFIX` | `run/` | 正式实验 tag 前缀 |
| `RUN_BRANCH_PREFIX` | `train/` | run worktree 的分支前缀，须与 `TAG_PREFIX` 不同；设为空串则用 detached HEAD |
| `WT_BRANCH_PREFIX` | `wt/` | 并行 worktree 的分支前缀 |
| `CI_CMD` | `scripts/ci.sh` | 候选门禁命令，只看退出码 |
| `STAMP_CMD` | 自动 | 只用于 run worktree；未设置时有 `scripts/git_stamp.py` 就用它，否则写 run 级文件 `<WT_ROOT>/run-<run_id>.GIT_STAMP.json`（有 `src/trimodalsurv/gitstamp.py` 用其 `build_stamp`，否则内置最小版） |
| `PYTHON_BIN` | `python3` | 解释器 |
| `TEST_CMD` | 自动 | `ci.sh` 的测试命令 |

---

## 【When is this applicable, and when is it not?】 适用与不适用

**适用**

- 单人或小团队，`main` 不会被多人同时推进。
- 验收标准是**实验结果**（C-index、AUC、loss 曲线），而不是测试能判定的东西。
- 创新可以用目录、文件或 config 开关隔离，失败创新留在树里无害。
- 需要「数字 → commit → 源码」的永久反查。

**不适用，或要换做法**

| 情况 | 该怎么做 |
|---|---|
| 改动的验收靠测试就能判定（bug fix、重构、日志、文档） | 不用 freeze，直接在 `main` 上提交；涉及代码时先跑 CI |
| 必须保证「main 只收成功创新」 | 本模板不提供这个保证：失败创新留在树里、账本标 negative。真需要就改用分支隔离 + PR 合并的流程 |
| 多人高并发合入 `main` | 走 GitHub PR + 必需的 CI check；本模板的代码门与 tag 规则照样适用 |
| 需要并行改代码又不想互相干扰 | 用 `wt-add` 建并行 worktree，完成后快进合回 `main` 再 `wt-rm` |
| 训练机上没有 `.git` | 同步源是 `run/<run_id>` 指向的提交（run worktree 或 `git archive run/<run_id>`）；stamp 文件随代码一起同步，训练入口读 stamp 而不是读 git |

---

## 【How do I do it?】 怎么做

不需要初始化：主目录检出 `main` 即可开始。

### 日常循环（主目录）

| 步 | 在哪里 | 命令 / 动作 | 得到什么 |
|---|---|---|---|
| 1 | 主目录 | 改一小块。涉及 `CODE_PATHS` 内的代码时先跑 `PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh`，绿灯才提交；只改论文或笔记可直接提交 | 存档点 |
| 2 | 主目录 | 提交，前缀带实验或模块标识：`feat(I08): ...`、`fix(I08): ...`、`docs(paper): ...`、`docs(notes): ...` | `main` 上的小步历史 |
| 3 | 主目录 | 改坏了：`git restore <file>` 回到上一个 commit；已提交的改动用 `git revert` 撤销，不改写历史 | 廉价回退 |

### 正式实验循环（candidate → 互审 → 冒烟 → freeze → 跑 → cleanup）

| 步 | 在哪里 | 命令 / 动作 | 得到什么 |
|---|---|---|---|
| 1 | 主目录（须检出 `main`；其他 worktree 或分支上即拒绝） | `PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/gitflow.sh candidate` | 先跑 CI，再过代码门：`CODE_PATHS` 下无未提交改动、无未跟踪文件。通过后打印 `H = <短哈希>` 与摘要；不干净时列出路径并拒绝。`manuscript/` 与根目录笔记的改动不阻塞 |
| 2 | 任意 | 互审：按 `AGENTS.md`「互审 · 自动审查闭环」发起，重点是数据泄漏、mask、loss、config、seed、结果路径 | Review PASS / 阻断 |
| 3 | 训练服务器 | 冒烟（用户裁决 2026-09-24）：`git archive H` 打包 → sha256 校验 → 传输 → 解包；`GIT_STAMP.json`（commit = H）随代码同步；1 癌 1 seed 训练 + 推理冒烟 + 必要的回放门。冒烟产物只判通/不崩，不进账本主表；失败回主目录修复、重新 candidate | 冒烟 PASS 才能冻结 |
| 4 | 主目录（须检出 `main`） | `scripts/gitflow.sh freeze i08-v1 --candidate <H 的提交哈希> [--no-worktree] [--link-assets <relpath>...]` | 先解析参数，再核对候选：H 在 `main` 上，且 H 之后 `CODE_PATHS` 下没有新改动（不满足即拒绝，对新的 HEAD 重新走第 1–3 步）；然后校验链接路径、过代码门。默认建分支 `train/i08-v1` 的 run worktree（HEAD = `main` HEAD）、挂链接、生成 stamp，最后一步才打 tag `run/i08-v1`；两种模式都写 run 级 stamp，记录 `candidate`（H）与 `commit`（实际冻结的提交）；同名 freeze 与 cleanup 互斥（原子锁）；`--no-worktree` 不建 worktree，把 stamp 写成 run 级文件 `<主目录>.worktrees/run-i08-v1.GIT_STAMP.json`（同步时作为 `GIT_STAMP.json` 放进 `git archive` 快照）。任一步拒绝或中途失败都不留下 tag，本次已建的 worktree、分支、链接与 stamp 一并回滚 |
| 5 | run worktree 或 `git archive run/i08-v1` 的快照 | 从这里同步或启动正式实验（绑定 commit 的资产锁在 tag 指向的提交上重写一次）。**禁止修改、禁止 commit**。结果写到 worktree 外，账本追加 `run_id, commit, 指标` | 结果绑定 tag 指向的提交 |
| 6 | 主目录 | 判定：好 → 无需 Git 操作；差 → 账本标 negative，代码留着。然后 `scripts/gitflow.sh cleanup i08-v1` | 脚本先核对：tag `run/i08-v1` 存在；run worktree HEAD **严格等于**该 tag 的提交（只「仍在 main 上」不够——切到 main 上更早的提交也在 main 上）；仍检出 `train/i08-v1`（detached 模式须仍为 detached）；该提交仍在 main 上；树干净（未提交、未跟踪与被 .gitignore 隐藏的文件都算，只放行根目录 `GIT_STAMP.json`、`.DS_Store`、`__pycache__` 里的字节码与登记过的合法链接——`worktree remove` 会连同被忽略的 checkpoint、日志一起删掉）。全部成立才逐个摘掉链接、删 worktree 与 `train/i08-v1` 分支；tag 与账本保留。任一不符即拒绝并保留现场 |

正式实验进行期间，主目录的 `main` 可以照常前进（写论文、做下一个创新）；正在跑的 run worktree 钉在 tag 上不动。

### 按需并行 worktree（wt-add → 提交 → 快进合回 → wt-rm）

| 步 | 在哪里 | 命令 / 动作 | 得到什么 |
|---|---|---|---|
| 1 | 主目录 | `scripts/gitflow.sh wt-add exp-b [--link-assets <relpath>...]` | 从 `main` 建 `<主目录>.worktrees/wt-exp-b/`，分支 `wt/exp-b`。name 以字母或数字开头，只含字母、数字与 `.` `_` `-`；目录或分支已存在即拒绝 |
| 2 | 并行 worktree | 照日常循环改代码、跑 CI、提交 | `wt/exp-b` 上的提交 |
| 3 | 主目录 | `git merge --ff-only wt/exp-b` | `main` 快进到这些提交，哈希不变 |
| 4 | 主目录 | `scripts/gitflow.sh wt-rm exp-b` | 核对目录是可用 worktree、检出的正是 `wt/exp-b`、该分支已是 `main` 的祖先（未合入即拒绝）、树干净（口径同 `cleanup`）；通过后摘链接、删 worktree、`git branch -d wt/exp-b` |

第 3 步如果因为 `main` 在此期间已经前进而无法快进：在并行 worktree 里 `git rebase main`（`wt/*` 分支只在本机、不推远端，可以变基），重新过 CI，再回主目录快进合回。不要为了省事改用非快进合并，那会在 `main` 上留下合并环。

并行 worktree 不是正式实验的源码来源；正式实验仍从主目录 `freeze`。

### 资产链接 `--link-assets` 的含义与边界

重资产（数据、特征、缓存、checkpoint）只在主目录存一份。`freeze` 与 `wt-add` 可以带 `--link-assets <relpath>...`，在临时 worktree 的 `<relpath>` 处建一个符号链接，指向 `<主目录>/<relpath>` 这份真源，避免几十 GB 的拷贝。

- **校验在任何副作用之前完成**：至少给一个路径；必须是相对路径，不能为空，不能含 `..`；`<主目录>/<relpath>` 必须存在；该路径本身在待检出提交里不得存在（已跟踪的文件或目录都算），它的任何祖先也不得是该提交里的非目录条目；同一次调用里的路径不得重复，也不得互为祖先。实际含义：含已跟踪文件的目录（例如带入库摘要的 `experiments/<ID>/results/`）不能整个链接，只能链接其下未被跟踪的子路径（通常是被 `.gitignore` 忽略的重资产目录）。任一不满足即拒绝，不打 tag、不建目录。`freeze` 的 `--no-worktree` 与 `--link-assets` 不能同用。
- **登记位置**：链接清单写在该 worktree 的 git 管理目录里（`git -C <worktree> rev-parse --absolute-git-dir` 所指目录下的 `gitflow-linked-assets`），不落在工作树中，所以不影响 `git status`。
- **「只读」只是约定**：脚本不改目标的权限。经链接写入的内容会直接落到 `<主目录>` 的真源里，并且在 worktree 删除后依然存在。因此 worktree 里的程序只读链接；新实验产物写到 worktree 之外，或写到 `<主目录>` 对应的新 `run_id` 目录，绝不覆盖已有结果。
- **收尾只摘链接**：`cleanup` / `wt-rm` 只认「登记过、仍是符号链接、指向值严格等于 `<主目录物理路径>/<relpath>`」的合法链接。通过全部核对后逐个 `rm` 链接本身（不递归、不带尾斜杠），再删 worktree；主目录里的目标完好无损。登记过却被换了目标或换成真实目录的路径、未登记的符号链接，一律拒绝并保留现场。
- **链接旁边写了真实文件也会拒绝**：例如在 run worktree 的真实目录里写出 `best.pth`，`cleanup` 照样拒绝——它会随 `worktree remove` 一起消失。

### 三种意外的处理

| 意外 | 处理 |
|---|---|
| 实验跑到一半发现 bug | 不碰 run worktree。回主目录在 `main` 上修 → `candidate` → 冒烟 → `freeze i08-v2` 重跑。旧结果作废，账本标 invalid |
| `train/<id>` 上被 commit 了，或 run worktree 被切到别的提交（哪怕是 main 上更早的提交）/ 别的分支 | `cleanup` 会拒绝删除并保留现场，这次实验的 provenance 已失效。先 `git -C <run worktree> reflog -n 10` 查清经过；混入的 commit 回主目录 `cherry-pick` 到 `main` 走正常流程，账本标 invalid。之后的清理不走脚本，查清并经用户确认后手动做：挂了资产链接的，先逐个 `rm <run worktree>/<relpath>`（只删链接本身，路径末尾不带斜杠，不加 `-r`）；再 `git worktree remove <run worktree>`；混入的 commit 已经 cherry-pick 走之后，才用 `git branch -D train/<id>` 删分支。`cleanup` 拒绝就是证据，查清之前不要用 `-D` / `--force` 糊过去 |
| CI 显示通过但代码其实是坏的 | 检查门禁命令是否被管道接到 `tail` 之类的命令左侧（管道会吞掉退出码）；检查是否有过期 `__pycache__`（`ci.sh` 已自动清理） |

### 反查：从数字到源码

```bash
grep 0.6431 results.tsv                  # → commit e9832fa
git branch --contains e9832fa            # → main（必须命中，否则结果无效）
git tag --points-at e9832fa              # → run/i08-v1（正式实验必须有）
git show --stat e9832fa                  # 那次冻结时的提交动了哪些文件
git show e9832fa:config.py               # 不切目录直接读当时的配置
```

---

## 【What should be true afterward?】 做完之后应该成立什么

每个循环结束后逐条核对，任一不成立就是流程被绕过了：

1. 账本每一行的 commit 都满足 `git branch --contains <commit>` 命中 `main`、`dirty = 0`，正式实验还有对应的 `run/<run_id>` tag。
2. 每个正式实验的 stamp 里 `dirty = false`，commit 等于该 `run/<run_id>` tag 指向的提交。
3. `git worktree list` 只剩主目录，外加正在跑的 run worktree 或正在用的并行 worktree；`git branch --list 'train/*' 'wt/*'` 只剩仍在使用的分支。
4. 被 `--link-assets` 链接过的主目录重资产完好，数量与内容没有因为 worktree 删除而变化。
5. 主目录 `scripts/ci.sh` 绿。
6. 从任意一个论文数字出发，五条命令内能读到当时的 config 和模型源码，不需要切换目录。

Git Graph 里应该看到：**`main` 一条直线，小步提交按时间排列；`run/*` tag 标在跑过正式实验的提交上；实验进行中 `train/<id>` 标签停在 tag 上，cleanup 后消失；并行分支 `wt/<name>` 快进合回后与 `main` 重合，wt-rm 后消失；没有分叉、没有 merge 气泡。**

不要 force-push，也不要改写已打 `run/*` tag 的 `main` 历史，否则 tag 与账本里的 commit 会脱离 `main`。何时 `git push origin main` 由用户决定。

---

## 附：脚本速查

| 命令 | 在哪里 | 做什么 |
|---|---|---|
| `scripts/ci.sh` | 任意 | 清 `__pycache__` → 测试 → 退出码（只接受 `-h` / `--help`，其他参数退出码 2 且无副作用） |
| `scripts/gitflow.sh candidate` | 主目录（检出 `main`） | CI + 代码范围干净门 + 打印 `H = <短哈希>`、完整哈希与摘要 |
| `scripts/gitflow.sh freeze <run_id> --candidate <H>` | 主目录（检出 `main`） | 候选核对 → 代码门 → run worktree（分支 `train/<run_id>`）+ stamp → 最后打 tag `run/<run_id>`；中途失败全部回滚 |
| `scripts/gitflow.sh freeze <run_id> --candidate <H> --no-worktree` | 主目录（检出 `main`） | 候选核对 → 代码门 → run 级 stamp `<主目录>.worktrees/run-<run_id>.GIT_STAMP.json` → 打 tag；同步时用 `git archive run/<run_id>` 并把该 stamp 作为 `GIT_STAMP.json` 放进快照 |
| `scripts/gitflow.sh freeze <run_id> --candidate <H> --link-assets <relpath>...` | 主目录（检出 `main`） | 同默认 freeze，另在 run worktree 里建指向主目录真源的符号链接 |
| `scripts/gitflow.sh cleanup <run_id>` | 主目录 | 核对 HEAD = tag `run/<run_id>`、检出 `train/<run_id>`（或 detached）、树干净 → 摘链接 → 删 run worktree 与 `train/<run_id>`，tag 保留 |
| `scripts/gitflow.sh wt-add <name> [--link-assets <relpath>...]` | 主目录 | 从 `main` 建 `wt-<name>`（分支 `wt/<name>`），可选挂载资产链接 |
| `scripts/gitflow.sh wt-rm <name>` | 主目录 | 核对已合入 `main`、树干净 → 摘链接 → 删 worktree → `git branch -d wt/<name>` |
| `scripts/gitflow.sh status` | 任意仓库内 | 当前分支、worktree 列表、最近的 `run/*` tag、代码门是否干净 |
| `scripts/gitflow.sh help` | 任意目录（含仓库外） | 打印用法 |
