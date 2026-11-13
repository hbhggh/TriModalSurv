# 单主干工作流规范与无损归并执行计划（Handoff 契约）

> 日期：2026-11-12
> 状态：已获用户逐层裁决授权（6 层 `/grill-me` 拍板完毕），交由 Claude Code 在 `<主目录>` 执行落地。
> 适用范围：`TriModalSurv` 仓库分支拓扑收敛、双端未提交与忽略重资产无损归并、规则与工作流脚本升级。

---

## 0. 用户裁决摘要（唯一执行准绳）

以下 6 项设计决策已由用户在 2026-11-12 逐层拍板确认，执行时不得偏离：

1. **拓扑收敛（单日常主目录 `main`）**：取消常驻 `dev` 分支与 `<主目录>.worktrees/dev`；日常代码开发、实验结果摘要、知识文档与论文写作（`manuscript/`）全部统一在 `<主目录>`（检出 `main`）单目录维护。仅在正式实验冻结或需要多任务 / 多 AI 本地并行隔离时按需创建临时 worktree，用完即删。
2. **提交粒度与代码范围门禁**：`main` 允许日常小步提交（前缀如 `feat(I08):`、`fix(I08):`、`docs(paper):`、`docs(notes):`），不再要求 squash 成“一创新一 commit”。正式实验版本追溯改由 **`run/<run_id>` tag + `GIT_STAMP.json`** 锚定（论文数字仍须满足对应 commit 在 `main` 上且带 `run/<run_id>` tag）。发车 / 候选 / 冻结的“干净门禁”默认**只检查代码与实验配置路径**，正在编写的 `manuscript/` 论文或根目录笔记绝不阻塞实验。
3. **重资产单点真源 + 临时 worktree 自动软链**：`<主目录>` 是本机唯一重资产存储位置（保持 I01–I08 现有相对路径零改动）。先把 `<dev工作树>` 独有的被忽略重资产一次性无损并回 `<主目录>`；今后按需建临时 worktree 时，由 `scripts/gitflow.sh` 自动将所需只读重资产目录以**符号链接（symlink）**挂载过去，且新跑实验产物一律写往临时 worktree 外部（或 `<主目录>` 对应新 `run_id` 目录），完结后零拷贝安全删除临时 worktree。
4. **知识库与论文的 Git 跟踪分层**：
   - **纳入 Git 版本控制**（保持原路径不断链）：`manuscript/`（`.tex`、`.bib`、脚本生成的 `tables/`、`figures/` 及编译出的 `main.pdf`）、指导代码实现的契约与交接文档（`01_总约束清单.md`、`02_总算子卡槽与候选池.md`、`03_index-故事线 A-1｜患者级动态恢复_v1.md`、`*.handoff.md`、`handoff-*.md`）。入库前严格执行坑 I05-04 绝对路径脱敏检查与坑 E52 表格竖线检查。
   - **纳入 `.gitignore` 仅留本机 `<主目录>`**：版权文献库 `zotero/`、备份 `.bak/`、调研草稿 `deep-research-*.md`、`0.common-sense.md`、`index.excalidraw`（18.5 MB 画布原件留本地防 `.git` 体积膨胀，导出的轻量矢量图 / PDF 进 Git）、`index-paper-example-joy.md`、`index-simplify.md`、`生存分析-论文模版.md`、`image/common-sense/`、`image/deep-research-report(5)/`。
5. **存量 Fast-Forward 无损合入与残留全清**：当前 `main`（`47b68c07`）与 `dev`（`5c508587`）零分叉，`dev` 领先 17 个提交，且 `I08` 缓存与结果清单已硬编码绑定其中的 `3992d985`、`f4b30740`、`5c508587`。`<主目录>` 直接执行 `git merge --ff-only dev` 完整保留这 17 个 commit 哈希；双端未提交文件与忽略资产按第 1 节裁决表取并集归并；最后退役 `<dev工作树>` 与 `dev` 分支，并一并清理 `<主目录>/.claude/worktrees/` 下 4 个干净残留会话 worktree。
6. **规则文件修改授权**：用户已明确授权同步改写 `AGENTS.md`、`CLAUDE.md`、`docs/workflow/git-workflow.md`、`scripts/gitflow.sh`、`tests/test_workflow_scripts.py` 与 `.gitignore`。

---

## 1. 盘面实测基线与逐项冲突裁决表

> 执行前须用命令复核本节基线；若用户在交接后新增了修改，先按时间与哈希增量核对再合并（防坑 I05-01）。

### 1.1 分支与 Worktree 现状

- `<主目录>`：`$HOME/Desktop/TriModalSurv`，当前检出 `main`（`47b68c07`）。
- `<dev工作树>`：`$HOME/Desktop/TriModalSurv.worktrees/dev`，当前检出 `dev`（`5c508587`，领先 `main` 17 个提交，`main..dev` 含 `5f0e34c1..5c508587`，`dev..main` 为 0）。
- 4 个干净的会话临时 worktree（`git status --short` 均为空，可安全清理）：
  - `.claude/worktrees/laughing-swartz-473544`（分支 `claude/laughing-swartz-473544` @ `47b68c07`）
  - `.claude/worktrees/paper-logic-cross-validation-1ead15`（分支 `claude/paper-logic-cross-validation-1ead15` @ `47b68c07`）
  - `.claude/worktrees/slot-b4-simplify-update-801064`（分支 `claude/slot-b4-simplify-update-801064` @ `0a53b017`，已在 `main` 历史中）
  - `.claude/worktrees/trimodalsurvey-operator-experiment-22aba8`（分支 `claude/trimodalsurvey-operator-experiment-22aba8` @ `47b68c07`）

### 1.2 双端未提交与未跟踪文件归并裁决表

> 注：遵守坑 E52，下表单元格内不使用任何竖线符。

| 路径或目录 | main 状态 | dev 状态 | 归并裁决与动作 |
| --- | --- | --- | --- |
| `.vscode/settings.json` | 已修改 | 已修改（含 10-22 与 10-26 完整规则） | 取 `dev` 版本覆盖至 `main` 并提交 |
| `.colabignore` | 无 | 未跟踪新文件 | 从 `dev` 拷入 `main` 并提交 |
| `AGENTS.md` | 干净 | 已修改（新增 Colab GPU 节） | 先取 `dev` 版本为基础，再按第 2 节升级「Git 工作流」节后提交 |
| `docs/engineering/pitfalls.md` | 干净 | 已修改（新增 E52） | 取 `dev` 版本（保留 E52，收尾若有新坑再追加）并提交 |
| `docs/workflow/office-viewer/outline-sync-fix.md` | 已修改 | 已修改（含 10-26 回滚守卫与全角井号修复） | 取 `dev` 版本覆盖至 `main` 并提交 |
| `docs/reviews/20261015-colab-job/` 与 `20261111-scoop-check-I08/` | 无 | 未跟踪目录 | 从 `dev` 拷入 `main`（注意：`codex-review.json` 被 `.gitignore` 忽略留本地，`codex-review.public.json` 与 `claude-response.md` 进 Git） |
| `docs/workflow/20261013-changemap/` | 无 | 未跟踪目录 | 从 `dev` 拷入 `main` 并核对脱敏后提交 |
| `experiments/I01_patient_retrieval/.../1.progress/实验结果分析-grok.md` | 干净 | 已修改 | 取 `dev` 修改拷入 `main` 并提交 |
| `experiments/I01_patient_retrieval/.../2.progress/result/实验结果分析-grok.md` | 已修改 | 干净 | 保留 `main` 修改（FF 前先备份再还原）并提交 |
| `experiments/I07_ps3style_backbone/results/i07-ps3-20261011/render/results.md` | 干净 | 已修改 | 取 `dev` 修改拷入 `main` 并提交 |
| `experiments/I08_ps3_shared_recovery/` 下全部未提交修改与新增 `tools/` · `tests/` · `results/` · `reviews/` | 无（FF 后获得基线） | 多项修改与新增制表画图工具及单测 | FF 后将 `dev` 工作树中 `I08` 的全部修改与新增文件完整同步至 `main` 并提交（忽略文件走 1.3 节） |
| `manuscript/bmc_initial_draft/main.tex` 与 `trimodalsurv-论文初版本-modify-from-bbag124.docx` | 误删（`D`） | 完好 | 在 `main` 执行 `git checkout --` 恢复完好状态 |
| `manuscript/bmc_initial_draft/figures/` · `tables/` · `main.pdf` | 旧版或误删 | 最新生成（含 `table4.tex`、`framework.html`、最新编译 `main.pdf`） | 用 `dev` 版本完整覆盖 `main` 对应路径并纳入 Git 提交 |
| `manuscript/消融实验/` 下 3 个已修改 `.md` | 已修改（`main` 更新） | 干净 | 保留 `main` 的 3 份修改（FF 前备份、FF 后还原）并提交 |
| `conftest.py` | 误删（`D`） | 完好 | 在 `main` 执行 `git checkout -- conftest.py` 恢复 |
| `NPJ-A&NPJ-B区别.md` · `STATUS.md` · `v1-table1.tex` · `image/todo/1789544641035.png` | 前三项已删（`D`） | 四项均删（`D`） | 双端一致删除，在 `main` 用 `git rm` 正式记录删除 |
| `01_总约束清单.md` · `03_index-故事线 A-1｜患者级动态恢复_v1.md` · `患者级动态恢复_v1.handoff.md` | 未跟踪 | `03` 与 `handoff` 同字节副本 | 保留 `main` 原件，脱敏检查通过后纳入 Git 提交 |
| `02_总算子卡槽与候选池.md` | 未跟踪（11-09 20:52 更新） | 未跟踪（11-08 旧副本） | 以 `main` 的 11-09 最新版为准纳入 Git 提交（无需被 `dev` 覆盖） |
| `handoff-论文生成-gemini.md` 与 `handoff-论文生成.md` | 仅有 `-gemini.md` | 仅有 `handoff-论文生成.md` | 把 `dev` 的 `handoff-论文生成.md` 拷入 `main`，两份并存，脱敏检查后纳入 Git 提交 |
| 本文件 `单主干工作流规范与无损归并执行计划-handoff.md` | 待拷入 | 当前所在位置 | Step 0 先拷入 `main` 根目录，脱敏与表格检查通过后一并纳入 Git 提交 |
| `zotero/` · `.bak/` · `deep-research-*.md` · `0.common-sense.md` · `index.excalidraw` · `index-paper-example-joy.md` · `index-simplify.md` · `生存分析-论文模版.md` · `image/common-sense/` · `image/deep-research-report(5)/` | 未跟踪（仅在 `main`） | 无 | 原地保留在 `main` 本地磁盘，写入 `.gitignore` 忽略，不上传远端 |

### 1.3 被 `.gitignore` 忽略的重资产基线

- 排除 `.DS_Store` 与 `__pycache__/` 后，`<dev工作树>` 共有 **3,671** 个被忽略文件：
  - **3,662 个仅存在于 `<dev工作树>`**：主要分布在 `experiments/I06_llm_condensation/results`（3,464 个）、`experiments/I07_ps3style_backbone/results`（100 个）、`experiments/I08_ps3_shared_recovery/results`（75 个）、各审查目录本地 `codex-review.json`（17 个）、`BioClinical ModernBERT/results`（1 个）、`GIT_STAMP.json`（1 个）、`results.tsv`（1 个）。
  - **9 个双端共有**：其中 7 个 sha256 完全相同，仅 `manuscript/bmc_initial_draft/main.log` 与 `main.synctex.gz` 2 个编译副产物为 `dev` 较新。
- **硬性铁律**：在删除 `<dev工作树>` 之前，这 3,662 个独有忽略文件必须 100% 拷入 `<主目录>` 对应相对路径，且逐文件核对存在性与字节数 / sha256 完全一致（防坑 G5）。

---

## 2. 新版单主干 Git 工作流与脚本改造规格

### 2.1 `AGENTS.md` · `CLAUDE.md` · `docs/workflow/git-workflow.md` 改写要点

1. **废除常驻 `dev` 与强制 squash**：
   - `<主目录>` 检出 `main`，是日常唯一工作区（代码、契约文档、实验轻量摘要、论文 `manuscript/`、本机唯一重资产真源均在此处）。
   - 日常开发直接在 `main` 小步提交（前缀带实验或模块标识，如 `feat(I08): ...`、`fix(I08): ...`、`docs(paper): ...`）。涉及代码改动时每步先跑 `PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh`，绿灯才提交。
   - 禁止 force-push 或改写已打 `run/*` tag 的 `main` 历史。
2. **代码范围干净门禁（Code-Scoped Clean Gate）**：
   - 默认代码门禁路径集合 `CODE_PATHS`：`src`、`configs`、`scripts`、`tests`、`experiments`、`pyproject.toml`、`conftest.py`。
   - 跑实验候选核验或冻结前，只要求 `git status --porcelain -- "${CODE_PATHS[@]}"` 为空且 `scripts/ci.sh` 退出码为 0；正在编辑的 `manuscript/` 或根目录文档不阻塞实验。
3. **正式实验冻结与追溯（Provenance）**：
   - 正式实验前在 `main` 运行 `scripts/gitflow.sh freeze <run_id> [--no-worktree] [--link-assets <relpath>...]`：
     - 先跑 `CODE_PATHS` 干净门禁；
     - 在 `main` HEAD 打永久 tag `run/<run_id>`；
     - 默认在 `<主目录>.worktrees/run-<run_id>` 建只读冻结 worktree（分支 `train/<run_id>` 或 detached）并生成 `GIT_STAMP.json`；若指定 `--link-assets <relpath>`，在 `run-<run_id>/<relpath>` 建立指向 `<主目录>/<relpath>` 的只读符号链接；若远端实验直接用 `git archive run/<run_id>` 打包同步，也支持 `--no-worktree` 仅打 tag 与生成 stamp。
   - 结果 provenance 铁律不变：`git.json` / `results.tsv` / 实验 manifest 中的 commit 必须满足 `git branch --contains <commit>` 命中 `main`、`dirty=0`、且正式实验对应 `run/<run_id>` tag。
   - 实验结束后 `scripts/gitflow.sh cleanup <run_id>`：核对 `run/<run_id>` tag 存在、HEAD 严格等于该 tag 提交、检出分支匹配、树干净、无误写入的非白名单忽略产物（注：指向 `<主目录>` 内部的符号链接本身安全放行并移除链接，绝不递归触碰目标目录；普通被忽略结果文件如 `.pth` / `.npz` / `.log` 仍严禁遗留在 worktree 内），通过后删除 `run-<run_id>` worktree 与 `train/<run_id>` 分支，保留 `run/<run_id>` tag。
4. **按需并行隔离工作树（Parallel Worktree）**：
   - 当需要本地并行跑实验或多个 AI 同时修改不同模块时，使用新增子命令：
     - `scripts/gitflow.sh wt-add <name> [--link-assets <relpath>...]`：从 `main` 创建 `<主目录>.worktrees/wt-<name>`（分支 `wt/<name>`），可选挂载指向 `<主目录>/<relpath>` 的只读重资产符号链接。约定并行实验的新输出写往 worktree 外部或 `<主目录>/experiments/<ID>/results/<new_run_id>/`。
     - `scripts/gitflow.sh wt-rm <name>`：核对 `wt/<name>` 已合入 `main`（`git merge-base --is-ancestor`）、工作树无未提交改动、无误留的非符号链接忽略重资产（放行指向 `<主目录>` 的 symlink、`GIT_STAMP.json`、`.DS_Store`、`__pycache__/*.pyc`），安全移除 worktree 并 `git branch -d wt/<name>`。
5. **`CLAUDE.md` 节点一同步修订**：
   - 将原第 36 行“squash 完成、`dev` 已归位、`git diff main dev` 为空”更新为：“待跑 commit 已提交在 `main` 上且 `CODE_PATHS` 工作树干净；若使用冻结 worktree，其 HEAD 严格等于 `run/<run_id>` tag 且 `git status` 干净；`GIT_STAMP.json` 的 commit 等于该 tag 指向的 `main` 提交”。

### 2.2 `scripts/gitflow.sh` 与 `tests/test_workflow_scripts.py` 编码红线

- **防坑 G2**：参数解析（`-h` / `--help` 退 0，未知子命令非 0）先于仓库探测与任何副作用。
- **防坑 G3**：所有紧跟中文或全角字符的 shell 变量一律写 `${var}`，`test_no_unbraced_variable_before_multibyte_text` 必须全绿。
- **防坑 G1 / G5**：保留原有 `GitflowCleanupTests` 的全部 14 条安全回归语义，并新增单测覆盖：
  1. `candidate` 与 `freeze` 在 `manuscript/draft.tex` 有未提交修改或根下有未跟踪笔记时正常放行，而在 `src/` 或 `experiments/` 有脏改动时果断拒绝；
  2. `freeze --link-assets` / `wt-add --link-assets` 创建指向 `<主目录>` 子目录（内部含 `.pth` / `.npz`）的符号链接后，`cleanup` / `wt-rm` 能安全移除 worktree 且 `<主目录>` 内的目标重资产文件完好无损；而若在 worktree 真实目录内直接写入 `best.pth`，`cleanup` / `wt-rm` 依然拒绝并保留现场；
  3. 移除过时的 `init` / `squash` 常驻 `dev` 流程测试，替换为 `wt-add` → 提交 → `merge --ff-only` 回 `main` → `wt-rm` 闭环测试。

---

## 3. 分步执行流水线（Claude Code 执行手册）

### Step 0：前置核验与可逆备份（未备份严禁动盘）

1. 完整阅读 `docs/engineering/pitfalls.md` 与本文件。
2. 确认当前 `pwd -P` 为 `$HOME/Desktop/TriModalSurv`（`<主目录>`），绝不在 `<dev工作树>` 内自删目录（防坑 G4 / V13）。
3. 将 `<dev工作树>/单主干工作流规范与无损归并执行计划-handoff.md` 复制到 `<主目录>/单主干工作流规范与无损归并执行计划-handoff.md`。
4. 在 `/private/tmp/trimodalsurv-converge-20261112/`（防坑 S2）建立完整安全备份：
   - 记录双端 `HEAD` SHA、`git status --porcelain`、`git worktree list`；
   - 导出 `main` 与 `dev` 的 `git diff HEAD` 补丁；
   - 将 `<主目录>` 当前所有已修改（`M`）的跟踪文件按相对路径完整备份到 `/private/tmp/trimodalsurv-converge-20261112/main_modified_backup/`。

### Step 1：`<主目录>` 恢复干净跟踪态并 Fast-Forward 合入 `dev` 17 个提交

1. 核对 `git -C <主目录> rev-list --left-right --count main...dev` 仍为 `0	17`。
2. 在 `<主目录>` 执行 `git checkout -- .`（此时 `<主目录>` 先前的修改已备份在 `/private/tmp/.../main_modified_backup/`，未跟踪文件丝毫不受影响，同时自动恢复了误删的 `conftest.py`、`manuscript/bmc_initial_draft/main.tex`、`trimodalsurv-论文初版本-modify-from-bbag124.docx` 等）。
3. 在 `<主目录>` 执行 `git merge --ff-only dev`。
4. 立即断言：
   - `git rev-parse HEAD` 等于 `<dev工作树>` 的 `HEAD`（`5c508587...`）；
   - `git branch --contains 3992d985`、`git branch --contains f4b30740`、`git branch --contains 5c508587` 全部包含 `main`。

### Step 2：按 1.2 节裁决表无损归并双端工作树改动

1. 从 `/private/tmp/trimodalsurv-converge-20261112/main_modified_backup/` 还原 `<主目录>` 独有的 4 份跟踪文件修改：
   - `experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/2.progress/result/实验结果分析-grok.md`
   - `manuscript/消融实验/1.innovation-computation/4progress-claude交接/实验先验知识与公式说明.md`
   - `manuscript/消融实验/2.innovation-secode-part- Encoder/1.prototype_learning/1.原始发给ai的信息/Encoder实验先验知识-Pro版.md`
   - `manuscript/消融实验/2.innovation-secode-part- Encoder/1.prototype_learning/6.LLM浓缩-A1/研究计划书-A1-LLM浓缩.md`
2. 从 `<dev工作树>` 将 1.2 节指定取 `dev` 的已修改文件与新增未跟踪代码/文档/图表精确复制到 `<主目录>`（注意：**不要**用 `<dev工作树>/02_总算子卡槽与候选池.md` 覆盖 `<主目录>` 的 11-09 新版）：
   - `.vscode/settings.json`、`.colabignore`、`AGENTS.md`、`docs/engineering/pitfalls.md`、`docs/workflow/office-viewer/outline-sync-fix.md`
   - `docs/reviews/20261015-colab-job/`、`docs/reviews/20261111-scoop-check-I08/`、`docs/workflow/20261013-changemap/`
   - `experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/1.progress/实验结果分析-grok.md`
   - `experiments/I07_ps3style_backbone/results/i07-ps3-20261011/render/results.md`
   - `experiments/I08_ps3_shared_recovery/` 下全部修改文件与新增目录/文件（`interface.md`、`results/`、`reviews/`、`tests/`、`tools/`）
   - `manuscript/bmc_initial_draft/figures/`、`manuscript/bmc_initial_draft/tables/`、`manuscript/bmc_initial_draft/main.pdf`
   - `handoff-论文生成.md`
3. 对双端一致删除的 4 个跟踪文件执行 `git rm`：
   - `NPJ-A&NPJ-B区别.md`、`STATUS.md`、`v1-table1.tex`、`image/todo/1789544641035.png`（同时用 `git grep` 检查仓库内是否有指向 `STATUS.md` 的核心活跃说明需顺手更新备注）。

### Step 3：无损归并 `<dev工作树>` 全部被忽略重资产并逐文件 sha256 校验

1. 用 Python 脚本枚举 `<dev工作树>` 中 `git -c core.quotePath=false ls-files --others --ignored --exclude-standard` 的全部文件（排除 `.DS_Store` 与 `__pycache__/`）。
2. 若目标路径在 `<主目录>` 不存在则创建父目录并 `shutil.copy2` 复制；若已存在且为 `manuscript/bmc_initial_draft/main.log` 或 `main.synctex.gz` 则以 `dev` 新版覆盖；其余已存在文件断言 sha256 一致（若遇任何意外不一致立即停机报告，不覆盖）。
3. **硬门禁断言**：遍历 `<dev工作树>` 上述全部约 3,671 个忽略文件，逐一核对 `<主目录>` 同相对路径文件存在且 sha256 100% 相等，打印总核验数与不一致数（必须为 `0`）。

### Step 4：落地新 `.gitignore`、单主干规则文档与 `scripts/gitflow.sh`

1. 更新 `<主目录>/.gitignore`，新增第 0 节裁决 4 的本机私有知识资产忽略规则（精确锚定根路径，避免误伤实验子目录）。
2. 按第 2 节规格升级 `scripts/gitflow.sh` 与 `tests/test_workflow_scripts.py`。
3. 同步更新 `AGENTS.md`（「Git 工作流」节）、`CLAUDE.md`（节点一 provenance 条目）、`docs/workflow/git-workflow.md`。

### Step 5：全量自测、脱敏扫描、表格竖线扫描与分步提交

1. 运行全仓 CI 与新增测试：
   - `PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh`
   - 确认 `tests/test_workflow_scripts.py`、`experiments/I08_ps3_shared_recovery/tests/test_paper_tables.py`、`test_paper_tools.py` 全部通过。
2. 提交前执行三道静态检查（防坑 I05-04 / I05-12 / E52）：
   - **暂存前明确路径 `git add`**（严禁对含未跟踪私密文件的目录盲目 `git add -A`）；
   - **绝对路径扫描**：`git diff --cached | grep "^+" | grep -E "/[U]sers/|/[h]ome/"`（用 `[x]` 字符类避免匹配本说明行自身；对新增自写内容必须为 0 命中，历史遗留本机路径须脱敏为占位符）；
   - **Markdown 表格管道符检查**：对本次新增或修改的 `.md` 表格逐行核对管道符数量与表头一致，单元格内部零裸竖线。
3. 在 `main` 上分 3 个清晰的小步提交落盘：
   - Commit 1：`feat(I08): 补充论文图表生成与校验工具、开发期评测更新及坑台账 E52`（含 `I08`、`I07`、`I01`、`pitfalls.md`、审查公开记录等）；
   - Commit 2：`docs(manuscript): 归并论文初稿最新图表编译产物与故事线交接契约文档`（含 `manuscript/`、`01–03_*.md`、`*handoff*.md`）；
   - Commit 3：`chore(workflow): 收敛为单主干 main 工作流并支持代码范围门禁与按需软链 worktree`（含 `.gitignore`、`.vscode/settings.json`、`.colabignore`、`AGENTS.md`、`CLAUDE.md`、`docs/workflow/`、`scripts/gitflow.sh`、`tests/test_workflow_scripts.py` 及 4 个清理删除项）。
   - *注*：暂不自动 `git push origin main`，交最终汇报后由用户决定何时推送。

### Step 6：执行自动审查闭环（`scripts/codex_review.sh`）

1. 按 `AGENTS.md`「互审 · 自动审查闭环」，对本次工作流脚本与规则变更发起只读审查（目录：`docs/reviews/20261112-single-main-workflow/`，`--base 5c508587`）。
2. 若在 Claude 沙箱内触发坑 C17（Codex 配置读取权限限制），按 C17 规范输出完整终端命令请用户在本地终端运行，或交用户裁决，不伪造审查结果。

### Step 7：安全退役 `<dev工作树>` 并清理 `.claude/worktrees/*`

1. 清理 4 个全部干净的 `.claude/worktrees/*`：
   - 逐个核对 `git -C <wt> status --porcelain` 为空且无独有忽略产物后，`git worktree remove <wt>`，并用 `git branch -d claude/<name>` 删除已合并分支。
2. 退役 `<dev工作树>`：
   - 再次运行核验脚本确认：`<dev工作树>` 的所有提交均已在 `main` 祖先链上，所有未提交 / 未跟踪 / 被忽略文件均已在 `<主目录>` 存在最新或逐字节一致版本；
   - 将 `<dev工作树>` 移至 `/private/tmp/trimodalsurv-converge-20261112/retired_dev_worktree/`（遵循坑 S2：用可恢复移动代替递归强删 `rm -rf`，既让 `git worktree prune` 干净注销 worktree，又在本机保留会话期兜底备份！）；
   - 在 `<主目录>` 运行 `git worktree prune` 与 `git branch -d dev`（必须使用小写 `-d`，以 Git 原生检查证明 `dev` 无未合并提交）。

### Step 8：终态 Q 验收清单（全部打勾才算收单）

- [ ] `git worktree list` 仅剩唯一一行：`<主目录> ... [main]`。
- [ ] `git branch` 仅剩 `main`（无 `dev`，无残留 `claude/*` 或 `train/*`）。
- [ ] `git branch --contains 3992d985`、`f4b30740`、`5c508587` 均命中 `main`。
- [ ] `<dev工作树>` 原 3,662 个独有忽略重资产在 `<主目录>` 100% 校验通过。
- [ ] `git status --short` 为空（本机私有 `zotero/`、`index.excalidraw`、`deep-research-*.md` 等已被 `.gitignore` 安静忽略）。
- [ ] `PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh` 退出码为 `0`。
