# 科研 Git 工作流迁移模板：策略一（先 Squash 后跑）× Worktree

> 一句话：**dev 上小步 commit → CI 与 review 通过，并且 smoke 实验结束 → squash 成 main 上一个 commit S → 从 S 建冻结 run worktree（分支 `train/<id>`）跑正式实验 → 结果盖章指向 S → 删 run worktree 和 `train/<id>`，S 永远留在 main。**
>
> 配套脚本：`scripts/ci.sh`、`scripts/gitflow.sh`。两者与项目无关，拷进任何仓库的 `scripts/` 即可用。

---

## 【What is it?】 这是什么

一套面向「单人科研 + AI 高频改代码 + 昂贵实验 + 结果要进论文」的 Git 工作流。它只用四个对象：

| 对象 | 角色 | 允许改代码 |
|---|---|---|
| `main` 分支（主目录） | 实验账本。一个创新 = 一个 commit，每个正式实验的 commit 都在 main 上 | 否 |
| `dev` 分支（长期开发 worktree） | AI 试错现场。小步 commit 当存档点，永远只领先 main「正在做的那一个创新」 | 是 |
| run worktree（分支 `train/<id>`，一次性） | 冻结的正式实验源码。从 main 建，分支只读、禁止 commit，跑完连分支一起删。不想要分支标签可设 `RUN_BRANCH_PREFIX=` 用 detached | 否 |
| 结果账本（仓库外） | `run_id → commit → C-index`。删 worktree 不影响它 | 不适用 |

它与「策略二（先跑后 squash）」的区别：策略二让实验 commit H 留在分支上，squash 后 main 上是另一个 commit S，需要 tag 和 H→S 映射；本模板先 squash，实验直接从 S 跑，**H 与 S 合一**，不需要映射。

多个创新之间靠**文件名**隔离（`model_innovation_1.py`、`model_innovation_2.py` + config 选择），不靠分支。失败的创新文件留在树里，只在账本标 negative。

```text
main（主目录）                  dev（长期开发 worktree）
● baseline ───────────────────┐
                              ● a1 feat(inn1): add file
                              ● a2 feat(inn1): wire config
                              ● a3 fix(inn1): mask
                    squash ←──┘
● S1 feat(inn1): ...   ──→ run worktree @ S1，stamp = S1
        dev 归位到 S1，开始创新 2
                              ● b1 feat(inn2): add file
● S2 feat(inn2): ...   ──→ run worktree @ S2，stamp = S2
```

---

## 【When should I think of using it?】 什么时候该想到它

出现下面任一信号时：

- AI（Claude / Codex）一次改十几个文件，你只掌握目标，diff 才是真正发生的事，需要高频存档点和廉价回退。
- 一次正式实验要烧几十 GPU 小时，跑之前必须确定「跑的是哪一版代码」，跑完之后必须能从数字反查到源码。
- 想同时推进两个创新：一个在跑实验，另一个在改代码，二者不能互相污染。
- 论文审稿时要回答「Table 1 这个数字来自哪一版代码」。
- main 历史已经被 `fix`、`wip`、`try again` 淹没，想让它读起来像一份创新清单。

---

## 【What must be true before I start?】 开始前必须成立的前提

1. **Git ≥ 2.15**（`git worktree` 稳定），仓库有一个干净的 `main`。
2. **测试命令存在且退出码可信**：`scripts/ci.sh` 默认跑 pytest，没有 pytest 退回 unittest；也可用 `TEST_CMD` 指定。没有测试就先写一个 import 冒烟测试，门禁不能是空的。
3. **结果目录在 worktree 之外**：正式结果写到主目录的 `results/`、仓库旁的 `<项目>-results/`、或远端服务器，绝不写进 run worktree（它会被删）。
4. **有 stamp 机制**：每次正式运行记录 commit SHA 与 dirty 状态。项目有自己的（如 `scripts/git_stamp.py`）就用自己的；没有则 `gitflow.sh freeze` 自带最小版。
5. **两个脚本已拷入 `scripts/`** 并 `chmod +x`；需要的话用环境变量覆盖默认值（见下表）。
6. **大文件不在 Git 里**：数据集、checkpoint、日志走 `.gitignore` 或外部存储，否则 worktree 会很重。
7. **AI 助手读得到规则**：把本文末尾的「AGENTS.md 规则块」粘进项目的 AGENTS.md / CLAUDE.md。

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `MAIN_BRANCH` | `main` | 账本分支 |
| `DEV_BRANCH` | `dev` | 长期开发分支 |
| `WT_ROOT` | `<主目录>.worktrees` | dev 与 run worktree 的存放目录 |
| `TAG_PREFIX` | `run/` | 正式实验 tag 前缀 |
| `RUN_BRANCH_PREFIX` | `train/` | run worktree 的分支前缀，须与 `TAG_PREFIX` 不同；设为空串则用 detached HEAD |
| `CI_CMD` | `scripts/ci.sh` | 候选门禁命令，只看退出码 |
| `STAMP_CMD` | 自动 | 有 `scripts/git_stamp.py` 就用它，否则内置最小 stamp |
| `PYTHON_BIN` | `python3` | 解释器 |
| `TEST_CMD` | 自动 | `ci.sh` 的测试命令 |

---

## 【When is this applicable, and when is it not?】 适用与不适用

**适用**

- 单人或小团队，main 不会被多人同时推进。
- 验收标准是**实验结果**（C-index、AUC、loss 曲线），而不是测试能判定的东西。
- 创新可以用文件或 config 开关隔离，失败创新留在树里无害。
- 需要「数字 → commit → 源码」的永久反查。

**不适用，或要换做法**

| 情况 | 该怎么做 |
|---|---|
| 改动的验收靠测试就能判定（bug fix、重构、日志） | 不用 freeze/run，dev 小步 commit → `candidate` → `squash` 即可；或直接在 main 上一个 commit |
| 必须保证「main 只收成功创新」且创新靠分支隔离 | 用策略二：分支上锁 H → 从 H 建 run worktree → 成功才 squash，且给 H 打永久 tag |
| 多人高并发合入 main | 走 GitHub PR + Squash and merge + 必需的 CI check，本模板的 `squash` 子命令由 PR 按钮替代 |
| 需要保留每个中间 commit 的历史（审计、教学） | 不 squash，用 `merge --no-ff` |
| 实验期间 main 必须能被别的工作推进 | 可以，但 `squash` 会拒绝「dev 不包含最新 main」的情况，先在 dev 里 `git merge main` |
| 训练机上没有 `.git` | run worktree 是同步源；stamp 文件随代码一起同步过去，训练入口读 stamp 而不是读 git |

---

## 【How do I do it?】 怎么做

### 一次性初始化

```bash
scripts/gitflow.sh init          # 主目录运行：建 dev 分支和 <主目录>.worktrees/dev
```

### 每个创新的循环（9 步；第 5 步冒烟为用户裁决 2026-09-24 新增）

| 步 | 在哪里 | 命令 / 动作 | 得到什么 |
|---|---|---|---|
| 1 | dev worktree | AI 改一小块 → `scripts/ci.sh` → commit，前缀带创新 ID：`feat(inn2): ...` | 存档点 a1, a2, … |
| 2 | dev worktree | 改坏了：`git restore <file>` 回到上一个 commit；整段作废：`git reset --keep <好的 commit>` | 廉价回退 |
| 3 | dev worktree | `scripts/gitflow.sh candidate` | CI 退出码 0 + 树干净 → 候选 H，并打印 main..H 的 commit 与文件清单供 review |
| 4 | 任意 | Review：看 `git diff main..dev`，重点是数据泄漏、mask、loss、config、seed、结果路径 | Review PASS / 阻断 |
| 5 | 训练服务器 | 冒烟：`git archive H` 打包 → sha256 校验 → 传输 → 解包；在 dev worktree 运行 `scripts/git_stamp.py` 生成 `GIT_STAMP.json`（commit = H）随代码同步；1 癌 1 seed 训练 + 推理冒烟 + 必要的回放门。冒烟产物只判通/不崩，不进账本主表；失败回第 1 步 | 冒烟 PASS 才能 squash。tree(S) = tree(H)，所以冒烟时按文件内容计算的源码摘要与回放记录在 S 上仍然有效 |
| 6 | 主目录 | `scripts/gitflow.sh squash "feat(inn2): implement prototype bank"` | main 上一个 commit S；脚本校验 tree(S) == tree(H)，并把 dev 归位到 S |
| 7 | 主目录 | `scripts/gitflow.sh freeze inn2-v1` | tag `run/inn2-v1` → S；分支 `train/inn2-v1` 的 run worktree，HEAD = S；stamp 记 commit = S、dirty = false |
| 8 | run worktree | 从这里同步或启动正式实验（绑定 commit 的资产锁在这里重写一次）。**禁止修改、禁止 commit**。结果写到 worktree 外，账本追加 `run_id, commit, 指标` | 结果绑定 S |
| 9 | 主目录 | 判定：好 → 无需 Git 操作；差 → 账本标 negative，代码留着。然后 `scripts/gitflow.sh cleanup inn2-v1` | 脚本先核对：tag `run/inn2-v1` 存在；run worktree HEAD **严格等于**该 tag 的提交（只「仍在 main 上」不够——切到 main 上更早的提交也在 main 上）；仍检出 `train/inn2-v1`（detached 模式须仍为 detached）；该提交仍在 main 上；树干净（被 .gitignore 隐藏的文件也算，只放行 `GIT_STAMP.json` 与字节码缓存——`worktree remove` 会连同被忽略的 checkpoint、日志一起删掉）。全部成立才删 worktree 与 `train/inn2-v1` 分支；tag 与账本保留。任一不符即拒绝并保留现场 |

dev 归位后立刻可以开始下一个创新；正在跑的 run worktree 钉在 S 不动。

### 三种意外的处理

| 意外 | 处理 |
|---|---|
| 实验跑到一半发现 bug | 不碰 run worktree。回 dev 修 → `candidate` → `squash`（得 `fix(inn2): ...` 的 S'）→ `freeze inn2-v2` 重跑。旧结果作废，账本标 invalid |
| 误把 dev reset 到别处 | `git reflog dev` 找到原来的 SHA → `git reset --keep <sha>` |
| `train/<id>` 上被 commit 了，或 run worktree 被切到别的提交（哪怕是 main 上更早的提交）/ 别的分支 | `cleanup` 会拒绝删除并保留现场，这次实验的 provenance 已失效。先 `git -C <run worktree> reflog -n 10` 查清经过；混入的 commit `cherry-pick` 回 dev 走正常流程，账本标 invalid，然后手动 `git worktree remove <run worktree>` 与 `git branch -D train/<id>`。`cleanup` 拒绝就是证据，不要用 `-D` / `--force` 糊过去 |
| CI 显示通过但代码其实是坏的 | 检查门禁是否在管道左侧（`./ci.sh \| tail` 会吞掉退出码）；检查是否有过期 `__pycache__`（`ci.sh` 已自动清理） |

### 反查：从数字到源码

```bash
grep 0.6431 results.tsv                  # → commit e9832fa
git branch --contains e9832fa            # → main（必须命中，否则结果无效）
git tag --points-at e9832fa              # → run/inn1-v1
git show --stat e9832fa                  # 那次创新动了哪些文件
git show e9832fa:config.py               # 不切目录直接读当时的配置
```

### 粘进 AGENTS.md / CLAUDE.md 的规则块

```text
## Git 工作流（策略一：先 Squash 后跑）
1. main 的语义 = 一个创新一个 commit；每个正式实验的 commit 都在 main 上。禁止在主目录直接改代码。
2. dev 是唯一长期开发分支，检出在 <主目录>.worktrees/dev/；多个创新共用 dev，靠文件名/config 隔离，不靠分支。
3. 开发只在 dev worktree：小步 commit，前缀带创新 ID；每步跑 scripts/ci.sh，红灯不 commit。
4. 候选 H = scripts/gitflow.sh candidate 通过（CI 退出码 0 + 工作树干净）。通过后才进入 review。
5. Review 通过后从 H 的干净快照（git archive H + GIT_STAMP commit=H）上机冒烟；冒烟通过才 squash，冒烟产物不进账本。
6. 冒烟通过后在主目录 scripts/gitflow.sh squash "<msg>"：main 得 S，dev 归位到 S。dev 领先 main 超过一个创新即违规。
7. 正式实验只从 scripts/gitflow.sh freeze <run_id> 建的 run worktree 启动：分支 train/<run_id>，HEAD = main；stamp 的 commit 必须等于 main HEAD。
8. run worktree 与 train/* 分支只读，禁止 commit。发现 bug 回 dev 修，重新 candidate → 冒烟 → squash → freeze 新 run_id；旧结果作废。
9. 结果 provenance：账本里的 commit 必须 git branch --contains 命中 main，否则结果不得进论文。
10. 结果差不 revert：账本标 negative，代码留在树里；确需清理另起 chore(<ID>): drop。
11. 收尾 scripts/gitflow.sh cleanup <run_id>：先核对 tag run/<run_id> 存在、run worktree HEAD 严格等于该 tag 的提交（只核对"仍在 main 上"不够）、仍检出 train/<run_id>（detached 模式须仍为 detached）、该提交仍在 main 上且树干净（被 .gitignore 隐藏的文件也算，只放行 GIT_STAMP.json 与字节码缓存），再删 worktree 与 train/<run_id> 分支；tag 与账本保留；核对失败保留现场，不得 -D / --force 强删。结果永远不放在 run worktree 内。
12. main 只经 squash 前进；禁止 rebase / force-push main。
```

---

## 【What should be true afterward?】 做完之后应该成立什么

每个循环结束后逐条核对，任一不成立就是流程被绕过了：

1. `git log --oneline main`：每行一个创新（或一次 `fix(<ID>)`），没有 `wip` / `try` 类 commit。
2. 账本每一行的 commit 都满足 `git branch --contains <commit>` 命中 `main`，且有对应 `run/<run_id>` tag。
3. `git worktree list` 只剩主目录和 dev，`git branch --list 'train/*'` 为空；没有残留的 run worktree。
4. 每个正式实验的 stamp 里 `dirty = false`，commit 等于当时的 main HEAD。
5. `git diff main dev` 在归位后为空；开始下一个创新后 dev 只领先 main 该创新的 commit。
6. 主目录 `scripts/ci.sh` 绿。
7. 从任意一个论文数字出发，五条命令内能读到当时的 config 和模型源码，不需要切换目录。

Git Graph 里应该看到：**main 一条直线，节点数 = 创新数；dev 要么与 main 重合，要么在 main 正上方多几个节点；tag 标在跑过正式实验的 commit 上；实验进行中 `train/<id>` 标签停在 S 上，cleanup 后消失；没有分叉、没有 merge 气泡。**

---

## 附：脚本速查

```text
scripts/ci.sh                          清 __pycache__ → 测试 → 退出码（只接受 -h/--help，其他参数退出码 2 且无副作用）
scripts/gitflow.sh init                建 dev worktree（一次）
scripts/gitflow.sh candidate           dev 里：CI + 干净树 + 打印 H 与 review 摘要
scripts/gitflow.sh squash "<msg>"      主目录：squash 得 S，dev 归位
scripts/gitflow.sh freeze <run_id>     主目录：tag + run worktree（分支 train/<run_id>）+ stamp
scripts/gitflow.sh cleanup <run_id>    核对 HEAD = tag run/<run_id>、检出 train/<run_id>（或 detached）、树干净 → 删 run worktree 与 train/<run_id>
scripts/gitflow.sh status              worktree 列表 + graph + tag
scripts/gitflow.sh help                打印用法（任意目录，含仓库外）
```
