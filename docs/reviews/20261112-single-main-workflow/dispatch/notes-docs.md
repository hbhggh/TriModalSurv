# 任务 B 过程记录（规则文档改写）

日期：2026-11-12。执行者：Opus 子 Agent。依据：`dispatch/plan.md` 任务 B、仓库根 `单主干工作流规范与无损归并执行计划-handoff.md` 第 0 节与第 2.1 节。

## 过程

1. 读完 plan.md、交接契约，以及白名单内各文件现状。对 `scripts/gitflow.sh` 只跑过一次 `grep -n "STAMP"`（查 stamp 落点），文档内容没有依据它；接口以 plan.md 任务 A「规格」为准。只读查了 `scripts/git_stamp.py`（stamp 写到仓库根 `GIT_STAMP.json`）与 `tests/test_workflow_scripts.py` 的测试名（用于 `tests/README.md` 的描述）。
2. 改写前把白名单文件当前工作树版本复制到会话 scratchpad 作快照，用快照做 `diff`，以便与 HEAD 上既有的「Colab GPU」节未提交改动区分开。
3. `AGENTS.md` 只做三次定点替换：「Git 工作流」节（原第 117–135 行，保留与「AI研究接力记录」之间的两行空行）、「自动审查闭环」第 2 条那一句、「Colab GPU」节里引用「第 5 条」的那一句。新节仍是 13 条，冒烟仍是第 5 条，所以 Colab 节与 `.colabignore` 的引用改为「第 5 条「冒烟」」，编号和条目名两头都能对上。
4. `CLAUDE.md` 只替换节点一 provenance 条目中间的三项，行首引导语与句尾「三者任一不满足即阻断」保留；三项用契约 2.1 第 5 点原文。
5. `docs/workflow/git-workflow.md` 按原骨架整篇重写；`scripts/README.md`、`tests/README.md`、`README.md` 定点修改。
6. 自查：旧词 grep、`git diff` 与快照 diff、表格管道符逐行计数（脚本计数，不目测）。

## 发现与疑问（交主控裁决，未自拟阻断规则）

- **候选 H 与冻结提交之间的缺口**：`freeze` 在执行时的 `main` HEAD 打 tag，这个提交不一定等于通过互审与冒烟的候选 H（中间可能有新的提交，包括 `CODE_PATHS` 内的代码提交）。契约与任务 A 规格都没有规定如何处理，脚本也不核对。新规则只如实写「在 `main` HEAD 打 tag」，没有自拟「H 与 HEAD 之间 `CODE_PATHS` 不得有新提交」这类阻断条款。建议主控决定是否加一条约定（例如冻结前核对 `git diff --stat H HEAD -- <CODE_PATHS>` 为空），或让 `freeze` 接受 `<commit>` 参数。
- **并行 worktree 合回时 `main` 已前进**：契约只写 `merge --ff-only`。`main` 在此期间有新提交时快进会失败，需要先在 `wt/<name>` 上变基或合入 `main`。规则里没有写这一步的做法，交主控裁决。
- **历史改写禁令的收窄**：旧第 12 条禁止对 `main` 的一切 rebase 与 force-push；契约 2.1 第 1 点收窄为「禁止 force-push 或改写已打 `run/*` tag 的 `main` 历史」。新规则按契约原文写，收窄点在此报告。
- **日常回退写法**：`git-workflow.md` 日常循环第 3 步把旧的 `git reset --keep <好的 commit>` 换成「已提交的改动用 `git revert` 撤销，不改写历史」，这是为配合单主干不改写历史的取向；属于说明文字，不是新阻断规则。
- **`--no-worktree` 的 stamp 位置**：任务 A 规格写「stamp 在 `<主目录>` 生成（有 `scripts/git_stamp.py` 就用它，否则内置最小版写到 `<WT_ROOT>/run-<run_id>.GIT_STAMP.json`）」。本项目有 `git_stamp.py`，它写到仓库根 `GIT_STAMP.json`（被 `.gitignore` 忽略），文档只写「在主目录生成 stamp」。

## 白名单外仍引用旧流程的文件（只记录，未动手）

`git grep` 扫描（排除 `archive/`、`docs/reviews/`、`collab/`、`docs/refactor/` 历史证据）后，以下活跃文件仍含 `STATUS.md` 链接、「Git 工作流」第 N 条编号、`dev worktree` 或 `gitflow.sh init/squash` 一类旧引用，需另行处理：

- `configs/README.md`、`docs/README.md`、`src/README.md`、`src/trimodalsurv/README.md`、`experiments/README.md`、`manuscript/README.md`（多为页脚「项目状态」链接指向已删除的 `STATUS.md`）
- `experiments/I01_patient_retrieval/README.md` 与 `knowledge/index.md`、`results/archive/index.md`；`experiments/I02…I04/knowledge/index.md`；`experiments/I05_text_encoder_bcmbert/README.md` 与 `tools/rebind_review.py`；`experiments/BioClinical ModernBERT/results/index.md`
- `docs/workflow/git-workflow-fix-20260923.md`（旧流程的历史修复记录）
- `manuscript/消融实验/…` 下 5 份笔记
- `scripts/gitflow.sh`（任务 A 正在改写）

`docs/engineering/pitfalls.md` 不在白名单内，本任务没有核对其中是否有依赖旧流程编号的条目。
