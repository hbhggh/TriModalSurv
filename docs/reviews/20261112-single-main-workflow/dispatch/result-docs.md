# 任务 B 结果（规则文档改写）

日期：2026-11-12。未执行任何改变仓库状态的 git 命令，未 commit。过程与疑问见同目录 `notes-docs.md`。

## 逐文件改动

| 文件 | 改动 |
|---|---|
| `AGENTS.md` | 「Git 工作流」节整节重写为单主干规则（标题注明用户裁决 2026-11-12，仍为 13 条）；「自动审查闭环」第 2 条的 `--base` 那一句改为单主干说法；「Colab GPU」节「源码」条的引用改为「第 5 条「冒烟」」。其余各节与既有未提交的「Colab GPU」节其余内容未动 |
| `CLAUDE.md` | 节点一 provenance 条目的三项改为契约 2.1 第 5 点原文；行首引导语与句尾「三者任一不满足即阻断」保留 |
| `docs/workflow/git-workflow.md` | 按原骨架整篇重写：对象表、布局说明、示意图、前提与环境变量表（删 `DEV_BRANCH`，加 `CODE_PATHS`、`WT_BRANCH_PREFIX`）、适用表、日常循环、正式实验循环、并行 worktree 循环、`--link-assets` 含义与边界、意外处理、反查、Afterward 清单、脚本速查表；删除初始化、压缩合并、开发分支归位与旧规则块 |
| `scripts/README.md` | `gitflow.sh` 行的子命令清单改为 `candidate` / `freeze` / `cleanup` / `wt-add` / `wt-rm` / `status`；同步源说明改为 `run/<run_id>` 指向的提交（run worktree 或 `--no-worktree` 后的 `git archive`）；删除 `STATUS.md` 链接 |
| `tests/README.md` | `test_workflow_scripts.py` 描述补上代码范围门、`--link-assets` 回归与 `wt-add` 闭环；删除 `STATUS.md` 链接 |
| `README.md` | 删除第 7 行「项目状态与历史」导航项 |
| `.colabignore` | 第 5 行注释引用改为「第 5 条「冒烟」」 |

## 旧句对照表（`AGENTS.md` 原「Git 工作流」节与点名的节外引用）

| 旧句（摘要） | 处理 | 新位置与说明 |
|---|---|---|
| 标题「策略一：先 Squash 后跑；用户裁决 2026-09-22」 | 改写 | 「单主干 main；用户裁决 2026-11-12」 |
| 「完整说明与迁移模板见 git-workflow.md；命令封装在 gitflow.sh 与 ci.sh」 | 改写 | 引导句保留，补「目录布局表与脚本速查」 |
| 布局：主目录只检出 `main` | 改写 | 布局段：`<主目录>` 检出 `main`，是唯一日常工作区与本机唯一重资产真源 |
| 布局：`dev` 是唯一长期开发分支，检出在 `.worktrees/dev/` | 作废 | 布局段只留一句历史说明：原常驻开发分支已于 2026-11-12 退役 |
| 布局：每个正式实验从 `main` 建 run worktree，分支 `train/<run_id>` | 改写 | 布局段：`.worktrees/` 下只按需出现 `run-<run_id>/` 与 `wt-<name>/`，用完即删；细节在第 6 条 |
| 布局：会话自动建的 worktree 只读，改动一律落在开发分支 worktree（2026-10-11） | 改写 | 只读规则原样保留；落点改为 `<主目录>`（`main`）或经 `wt-add` 建的 worktree |
| 1. `main` 的语义 = 一个创新一个 commit | 作废 | 新第 1 条明确不再要求，追溯改由 tag 与 stamp 锚定 |
| 1. 每个正式实验的 commit 都在 `main` 上 | 保留 | 并入新第 9 条 provenance 铁律 |
| 1. 禁止在主目录直接改代码 | 作废 | 主目录就是日常工作区（新第 1 条） |
| 2. 创新靠目录与文件名隔离，不靠分支 | 保留 | 新第 1 条末句 |
| 2. 多个创新共用开发分支 | 作废 | 无开发分支 |
| 3. 开发只在开发 worktree，小步 commit，前缀带实验 ID | 改写 | 新第 1 条：在 `main` 上小步提交，前缀示例 `feat(I08)` 等四种 |
| 3. 每步跑 ci.sh，红灯不 commit；CI 解释器说明与 2026-09-28 实测备注 | 保留 | 新第 2 条，限定为涉及代码改动时；解释器说明逐字保留 |
| 4. 候选 H = candidate 通过（CI + 工作树干净），通过后才互审 | 改写 | 新第 4 条；「工作树干净」改为新第 3 条的 `CODE_PATHS` 代码范围门 |
| 5. 冒烟：互审后从 H 的干净快照上机，`git archive H` 打包、校验和传输、stamp 随代码同步 | 保留 | 新第 5 条，打包与校验要求逐字保留 |
| 5. 冒烟通过才进入合并压缩，不过则回开发分支修复 | 改写 | 新第 5 条：通过才进入冻结，不过则回 `main` 修复 |
| 5. 冒烟产物不进账本；只靠测试验收的改动可跳过 | 保留 | 新第 5 条 |
| 6. 主目录合并压缩得 S、校验树一致、开发分支归位、领先即违规 | 作废 | 无此环节 |
| 7. freeze 打 tag、建 `train/<run_id>` run worktree、调 git_stamp.py | 改写 | 新第 6 条，补参数校验顺序、拒绝不留痕、`--no-worktree`；`--link-assets` 单列为新第 7 条 |
| 7. 分支前缀 `train/` 与 tag 前缀 `run/` 必须不同 | 保留 | 新第 6 条 |
| 7. 正式实验同步源只能来自 run worktree；stamp 随代码同步 | 改写 | 新第 6 条：只能来自 `run/<run_id>` 指向的提交（run worktree 或 `git archive run/<run_id>`） |
| 7. 绑定 commit 的资产锁须在 S 上重写一次；冒烟资产按内容哈希复用 | 改写 | 新第 6 条：在 `run/<run_id>` 指向的提交上重写一次；复用规则保留 |
| 8. run worktree 与 `train/*` 只读，禁止 commit | 保留 | 新第 8 条 |
| 8. 发现 bug 回开发分支修，candidate → 冒烟 → 合并压缩 → freeze 新 run_id；旧结果 invalid | 改写 | 新第 8 条：回 `main` 修，candidate → 冒烟 → freeze 新 run_id；旧结果 invalid 保留 |
| 9. 结果 provenance：commit 须 `git branch --contains` 命中 `main` 且 `dirty=0` | 保留 | 新第 9 条，补「实验 manifest」与「正式实验须有 `run/<run_id>` tag」 |
| 10. 结果差不 revert，账本标 negative，另起 drop commit | 保留 | 新第 10 条，示例 ID 改为 `<ID>` 占位 |
| 11. cleanup 的全部核对项（tag、HEAD 严格等于 tag、检出形态、仍在 `main` 上、树干净含忽略文件） | 保留 | 新第 11 条逐项保留 |
| 11. 树干净只放行 `GIT_STAMP.json` 与字节码缓存 | 改写 | 新第 11 条：放行根 `GIT_STAMP.json`、`.DS_Store`、`__pycache__` 字节码与登记过的合法链接；被篡改链接与未登记链接拒绝；先只摘链接再删 worktree |
| 11. 核对失败即 invalid、保留现场、不得 `-D` 或 `--force`；结果回传主目录 | 保留 | 新第 11 条 |
| 12. `main` 只经合并压缩前进 | 作废 | 改为日常小步提交（新第 1 条） |
| 12. 禁止 rebase 或 force-push `main` | 改写 | 新第 13 条按契约收窄为：禁止 force-push 或改写已打 `run/*` tag 的 `main` 历史（收窄点见 notes） |
| 12. 合并压缩后 `git push origin main` | 改写 | 新第 13 条：何时推送由用户决定，提交后不自动推送 |
| 13. 与已删除状态文件第 1 节一致：确定 commit 即 `main` HEAD = S | 作废 | 该文件已删除；冻结提交的定义由新第 6 条承担 |
| （新增）并行 worktree `wt-add` / `wt-rm` | 新增 | 新第 12 条 |
| 节外：「自动审查闭环」第 2 条「开发分支候选用 `--base main` 审分支」 | 改写 | 「已提交在 `main` 上的改动用 `--base <起点 commit>` 审（起点取这批改动之前的那个提交）」 |
| 节外：「Colab GPU」节「按「Git 工作流」第 5 条」 | 改写 | 「按「Git 工作流」第 5 条「冒烟」」，新节第 5 条仍是冒烟，编号与条目名都成立 |
| 节外：`.colabignore` 第 5 行「AGENTS.md「Git 工作流」第 5 条」 | 改写 | 同上，加「冒烟」 |
| 节外：`CLAUDE.md` 节点一 provenance 三项 | 改写 | 契约 2.1 第 5 点原文三项 |

## 自查原始输出

命令均在仓库根运行，以下是最终状态下原样重跑的输出。过程文档 `notes-docs.md` 与本文件不在旧词扫描范围内：对照表必须引用旧句，旧词出现在这里是预期的。本机 grep 是 ugrep，`-w` 按 Unicode 词界判断，紧贴汉字的 `dev` 可能漏检，所以改用不带 `-w` 的子串计数，再用一个小脚本按字符打印每处 `dev` 的上下文。绝对路径扫描只输出文件与行号，避免把本机路径抄进本文件。

### 1. 旧词扫描（6 个规则文件与 `.colabignore`）

```text
$ grep -n -E "squash|worktrees/dev|STATUS\.md" AGENTS.md CLAUDE.md docs/workflow/git-workflow.md scripts/README.md tests/README.md README.md .colabignore; echo "exit=$?"
exit=1
$ grep -n -i squash AGENTS.md CLAUDE.md docs/workflow/git-workflow.md scripts/README.md tests/README.md README.md .colabignore; echo "exit=$?"
exit=1
$ grep -n -c dev AGENTS.md CLAUDE.md docs/workflow/git-workflow.md scripts/README.md tests/README.md README.md .colabignore   # 子串计数，不带 -w
AGENTS.md:2
CLAUDE.md:0
docs/workflow/git-workflow.md:1
scripts/README.md:0
tests/README.md:0
README.md:0
.colabignore:0
$ python3 -I <scratchpad>/devctx.py AGENTS.md CLAUDE.md docs/workflow/git-workflow.md scripts/README.md tests/README.md README.md .colabignore   # 每处 dev 子串前后各 8 个字符
AGENTS.md:48: ...量传输 `to(device, non...
AGENTS.md:121: ...常驻。原常驻 `dev` 分支及其 w...
docs/workflow/git-workflow.md:5: ...做法；原常驻 `dev` 分支及其 w...
$ grep -n -E "/[U]sers/|/[h]ome/" AGENTS.md CLAUDE.md docs/workflow/git-workflow.md scripts/README.md tests/README.md README.md .colabignore | cut -d: -f1,2
AGENTS.md:140
AGENTS.md:141
CLAUDE.md:57
```

### 2. `AGENTS.md` / `CLAUDE.md` 改动范围

```text
$ diff <快照>/AGENTS.md AGENTS.md | grep -E "^[0-9]"
69c69
89c89
117c117
119c119
121c121
123,135c123,135
$ diff <快照>/CLAUDE.md CLAUDE.md | grep -E "^[0-9]"
36c36
$ git diff --stat -- AGENTS.md CLAUDE.md
 AGENTS.md | 53 +++++++++++++++++++++++++++++++++--------------------
 CLAUDE.md |  2 +-
 2 files changed, 34 insertions(+), 21 deletions(-)
```

完整 `git diff -- AGENTS.md CLAUDE.md`（相对 HEAD；第一个 hunk 的 13 行新增是既有的「Colab GPU」节，原样保留，其中「源码」那一句已含本次改动）：

```diff
diff --git a/AGENTS.md b/AGENTS.md
index 2413d8f6..5caca8f0 100644
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -61,6 +61,19 @@ Claude Code 与 Codex/Codex Companion 都必须遵守本文件。冲突时以本
 - 不改 `tmp_sur_cache/`，不覆盖已有结果目录。
 - 不把"窗口还在"当成"任务还在"。
 
+## Colab GPU（L4 补充算力；2026-10-15 起草）
+
+通用流程、费用护栏和踩坑按 `~/.claude/skills/colab-gpu/SKILL.md` 执行，本节只写本项目特有的部分。小时级稳定性验证（2026-10-15）完成前，长任务保活按未验证处理。
+
+- **定位**：Colab 只用于冒烟、调参和基础设施验证。正式实验仍在 landau，经 `jobrun.sh` 和发车器启动；Colab 上的结果不入账本、不进论文，除非用户另行裁决。
+- **源码**：不从开发目录直接 push。按「Git 工作流」第 5 条「冒烟」，从待跑 commit `git archive` 出最小源码闭包，放到仓库外的运行目录 `~/colab_runs/<run>/`；用 `trimodalsurv.gitstamp.build_stamp` 生成 `GIT_STAMP.json`，只写进运行目录，不写主检出；再生成 `SHA256SUMS`，push 后在远端 `sha256sum -c` 校验（坑 I05-10）；最后把仓库根的 `.colabignore` 复制进运行目录。I07 的源码闭包是 `experiments/__init__.py`、`experiments/I07_ps3style_backbone/`（排除 `results/`、`reviews/`）和 `src/`。
+- **入口与参数（I07）**：远端执行 `python -m experiments.I07_ps3style_backbone.launch train --assets data/i07_assets/v1 --runs outputs/<run> --gpus 0 --per-gpu 4 --epochs 50 --expected-commit <commit> --allow-low-gpu-util "<理由>"`，参数与 landau 正式运行 i07-ps3-20261011 一致。只做训练；test 评测必须走授权摘要（坑 V35），不在 Colab 上做。
+- **数据**：I07 资产在 landau `~/NPJ/i07_assets/v1/`（2.0 GB、2522 个文件、五份 manifest）。校外先连 VPN，再用 `rsync -a landau-direct:NPJ/i07_assets/v1/ <运行目录>/data/i07_assets/v1/` 拉到本机（VPN 下实测约 1 MB/s），然后随快照一起 push。上行约 4.5 MB/s，约 8 分钟，这段时间计入 GPU 计费；每开一个新会话都要重新上传。
+- **结果目录**：仓库根 `.colabignore` 已列出 `experiments/*/results/`、`experiments/*/runs/`、`results/`、`runs/`、`results.tsv`、`tmp_sur_cache*/` 和 `*.pt|*.pth|*.ckpt`。远端训练只写 `outputs/`（脚本内置默认排除）。拉回的结果留在运行目录，不放进 `experiments/*/results/`，也不覆盖已有结果。
+- **CU 预算**：L4 约 1.54 CU/小时。单次会话默认上限 3 CU（约 115 分钟，含上传），超出须事先得到用户同意。I07 一轮 100 次训练在 landau 上墙钟 6.4 分钟；L4 上的实测数据待小时级验证补上。
+- **数据合规**（2026-10-15 核对）：I07 用到的 TCGA 数据全部属于 GDC 开放层。GDC API 实测五个癌种的病理报告 3129/3129、切片 8589/8589、STAR-Counts 3386/3386，访问级别均为 `open`，不涉及 dbGaP 受控数据，因此可以上传到区域不固定（美国或亚洲）的 Colab VM。UNI2-h 特征受模型许可（非商业）约束，只放在私有运行时，不公开分发。新增数据源上传前须重新核对。
+- **与执行纪律的衔接（待用户裁决）**：Colab 上的后台任务用 `colab_job.sh start` 托管（有 pid、rc 和日志），视同 landau 的 `jobrun.sh`。停机门不变：会占满 GPU 的长任务仍需用户逐次同意。
+
 ## 互审
 
 - 执行方完成的任务，必须回到另一方做检查；执行方的 patch / review 结论，必须由另一方再看一遍才能进入下一 Gate。
@@ -73,7 +86,7 @@ Claude Code 与 Codex/Codex Companion 都必须遵守本文件。冲突时以本
 Claude 担任执行方时，写完代码到交付用户之间是一条不中断的流水线，不再"提醒用户发起审查"：
 
 1. **自测**：Claude 跑相关测试与 `scripts/ci.sh`，红灯先自修，绿了才进审查。
-2. **自动发起首审**：Claude 用 Bash（后台运行，完成后自动接续）调用 `bash scripts/codex_review.sh <审查目录> [--base <ref>]`。它固定走 companion `adversarial-review --wait --json`，Codex 只读、模型 `gpt-5.6-sol`。未提交改动审工作树；dev 候选用 `--base main` 审分支。审查目录：实验任务放 `experiments/<ID>/reviews/<YYYYMMDD>-<主题>/`，其他任务放 `docs/reviews/<YYYYMMDD>-<主题>/`；原文 `codex-review.json` 不覆盖、不改写；它含本机绝对路径（`repoRoot`），按 `.gitignore` 只留本地，入库的是只把仓库根替换为 `<仓库根>`、其余逐字不变的 `codex-review.public.json`。
+2. **自动发起首审**：Claude 用 Bash（后台运行，完成后自动接续）调用 `bash scripts/codex_review.sh <审查目录> [--base <ref>]`。它固定走 companion `adversarial-review --wait --json`，Codex 只读、模型 `gpt-5.6-sol`。未提交改动审工作树；已提交在 `main` 上的改动用 `--base <起点 commit>` 审（起点取这批改动之前的那个提交）。审查目录：实验任务放 `experiments/<ID>/reviews/<YYYYMMDD>-<主题>/`，其他任务放 `docs/reviews/<YYYYMMDD>-<主题>/`；原文 `codex-review.json` 不覆盖、不改写；它含本机绝对路径（`repoRoot`），按 `.gitignore` 只留本地，入库的是只把仓库根替换为 `<仓库根>`、其余逐字不变的 `codex-review.public.json`。
 3. **只审核心逻辑，至多复审一次**（复审规则：用户裁决 2026-09-24）：审查只看正确性、数据划分与泄漏、mask / loss / risk 口径、provenance、破坏性操作、测试是否真覆盖了声称的行为；语法、风格、命名等不影响正确性的问题不报、不处理。「核心逻辑问题」指 Codex 标为 high / critical 的 finding，或经采纳后必须修改运行逻辑（不只是文档措辞）的 finding。
    - 首审无核心逻辑问题 → 放行，不复审。
    - 首审有核心逻辑问题 → 修复、补测后自动复审一次（仍用 `codex_review.sh`，输出到同一审查目录的 `round2/`，焦点写明「复审首审 finding 的修复」）。复审无核心逻辑问题 → 放行；复审仍有核心逻辑问题 → 按第 5 条停下交用户，不自动第三轮。
@@ -101,25 +114,25 @@ Claude 担任执行方时，写完代码到交付用户之间是一条不中断
 2. 拒绝无边界编码：缺少前提 $P$ 或验收标准 $Q$ 时，禁止直接写代码，必须反问补齐约束清单。
 3. 强制唤醒词：用户说出 `Code Red: Recalibrate` 时，立刻停止发散，重新读取本节，并只回复：`引擎已重新挂载，等待第 1 组约束清单`。
 
-## Git 工作流（策略一：先 Squash 后跑；用户裁决 2026-09-22）
-
-完整说明与迁移模板见 `docs/workflow/git-workflow.md`；命令封装在 `scripts/gitflow.sh` 与 `scripts/ci.sh`。
-
-布局：主目录 `TriModalSurv/` 只检出 `main`；`dev` 是唯一长期开发分支，检出在 `TriModalSurv.worktrees/dev/`；每个正式实验从 `main` 建一个 run worktree `TriModalSurv.worktrees/run-<run_id>/`，检出一次性分支 `train/<run_id>`（HEAD = `main`）。应用为会话自动建的 worktree（Codex 的 `~/.codex/worktrees/`，Claude 桌面应用的 `.claude/worktrees/<名字>/` 及其 `claude/*` 分支）是临时工作区，不在本规则内：只用于讨论、检索和只读操作，不在其中改仓库文件或 commit，也不得作为正式实验源码来源；需要改代码或文档时，改动一律落在 `dev` worktree（用户裁决 2026-10-11）。
-
-1. `main` 的语义 = 一个创新一个 commit，且每个正式实验的 commit 都在 `main` 上。禁止在主目录直接改代码。
-2. 创新靠目录与文件名隔离（`experiments/<ID>/`、config 选择），不靠分支；多个创新共用 `dev`。
-3. 开发只在 dev worktree：小步 commit，前缀带实验 ID（`feat(I05): ...`）；每步跑 `scripts/ci.sh`，红灯不 commit。CI 解释器固定为 `protomasksurv-exp1` 环境，调用时显式传入：`PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh`（`candidate` 同样在前面加这个变量）；默认的 `python3` 没有 torch / pytest，会有 4 个导入错误，那不是代码问题（2026-09-28 实测）。
-4. 候选 H = `scripts/gitflow.sh candidate` 通过（CI 退出码 0 + 工作树干净）。通过后才进入互审。
-5. 冒烟（用户裁决 2026-09-24）：互审通过后，从 H 的干净快照上机冒烟（`git archive H` 打包、校验和传输，`GIT_STAMP.json` 的 commit = H 随代码同步）；冒烟通过才进入 squash，不过则回 dev 修复、重新 candidate。冒烟产物只判通/不崩，不进账本主表。涉及正式实验的创新必须经过这一步；只靠测试验收的改动（修 bug、重构、文档）可跳过。
-6. 冒烟通过后在主目录 `scripts/gitflow.sh squash "feat(I05): ..."`：`main` 得 S，脚本校验 tree(S) = tree(H) 并把 `dev` 归位到 S。`dev` 领先 `main` 超过正在做的一个创新即违规。
-7. 冻结：`scripts/gitflow.sh freeze <run_id>` 从 `main` 打 `run/<run_id>` tag、建分支 `train/<run_id>` 的 run worktree（HEAD = `main`）、调用 `scripts/git_stamp.py` 生成 `GIT_STAMP.json`。分支前缀 `train/` 与 tag 前缀 `run/` 必须不同。**正式实验**同步到训练服务器的源码只能来自 run worktree（冒烟见第 5 条）；`GIT_STAMP.json` 随代码同步。绑定 commit 的训练前资产锁须在 S 上重写一次，早于全部正式训练；其余冒烟阶段生成的数据资产（特征、缓存）按内容哈希复用。
-8. run worktree 与 `train/*` 分支只读，禁止 commit。发现 bug 回 `dev` 修，重新 candidate → 冒烟 → squash → freeze 新 run_id；旧 run 结果作废并在账本标 invalid。
-9. 结果 provenance：`git.json` / `results.tsv` 里的 commit 必须 `git branch --contains` 命中 `main` 且 `dirty=0`；不满足的结果不得进论文。
-10. 结果差不 revert：账本标 negative，代码留在树里；确需清理另起 `chore(I05): drop` commit。
-11. 收尾 `scripts/gitflow.sh cleanup <run_id>`：先核对 `run/<run_id>` tag 存在、run worktree HEAD 严格等于该 tag 的提交（只核对"仍在 `main` 上"不够）、仍检出 `train/<run_id>`（detached 模式须仍为 detached）、该提交仍在 `main` 上且树干净（被 `.gitignore` 隐藏的文件也算，只放行 `GIT_STAMP.json` 与字节码缓存），再删 worktree 与 `train/<run_id>` 分支；tag 保留。核对失败说明实验期间源码被切换或有 commit 混入，该 run 结果 invalid；保留现场，不得 `-D` / `--force` 强删。结果回传到主目录 `experiments/<ID>/results/<run_id>/`，永远不放进 run worktree。
-12. `main` 只经 squash 前进；禁止 rebase / force-push `main`；squash 后 `git push origin main`。
-13. 与 STATUS.md 第 1 节「全量运行时从确定 commit 建临时 worktree」一致：那个「确定 commit」现在就是 `main` HEAD = S。
+## Git 工作流（单主干 main；用户裁决 2026-11-12）
+
+完整说明、目录布局表与脚本速查见 `docs/workflow/git-workflow.md`；命令封装在 `scripts/gitflow.sh` 与 `scripts/ci.sh`。
+
+布局：主目录 `<主目录>`（即 `TriModalSurv/`）检出 `main`，是唯一的日常工作区，也是本机重资产（数据、特征、缓存、checkpoint、实验结果）的唯一真源。代码、契约与交接文档、实验结果摘要、论文 `manuscript/` 都在这里维护，I01–I08 的现有相对路径保持不变。`<主目录>.worktrees/` 下只会按需出现两种临时 worktree：正式实验冻结用的 `run-<run_id>/`（分支 `train/<run_id>`，或 detached），以及本地并行隔离用的 `wt-<name>/`（分支 `wt/<name>`）；两者用完即删，不常驻。原常驻 `dev` 分支及其 worktree 已于 2026-11-12 退役，不再重建。应用为会话自动建的 worktree（Codex 的 `~/.codex/worktrees/`，Claude 桌面应用的 `.claude/worktrees/<名字>/` 及其 `claude/*` 分支）是临时工作区，不在本规则内：只用于讨论、检索和只读操作，不在其中改仓库文件或 commit，也不得作为正式实验源码来源；需要改代码或文档时，改动落在 `<主目录>`（`main`），或落在经 `scripts/gitflow.sh wt-add` 建的 worktree（用户裁决 2026-10-11；落点于 2026-11-12 随单主干改写）。
+
+1. 日常提交：直接在 `<主目录>` 的 `main` 上小步 commit，前缀带实验或模块标识，如 `feat(I08): ...`、`fix(I08): ...`、`docs(paper): ...`、`docs(notes): ...`。不要求把一个创新压成一个 commit；正式实验的版本追溯由 `run/<run_id>` tag 与 `GIT_STAMP.json` 锚定（第 6 条、第 9 条）。创新靠目录与文件名隔离（`experiments/<ID>/`、config 选择），不靠分支。
+2. CI：涉及代码改动时，每步提交前先跑 `scripts/ci.sh`，红灯不 commit；只改论文或笔记的提交不需要跑。CI 解释器固定为 `protomasksurv-exp1` 环境，调用时显式传入：`PYTHON_BIN=<protomasksurv-exp1 环境>/bin/python scripts/ci.sh`（`candidate` 同样在前面加这个变量）；默认的 `python3` 没有 torch / pytest，会有 4 个导入错误，那不是代码问题（2026-09-28 实测）。
+3. 代码范围干净门：`candidate` 与 `freeze` 只检查代码与实验配置路径 `CODE_PATHS`（默认 `src`、`configs`、`scripts`、`tests`、`experiments`、`pyproject.toml`、`conftest.py`，可用同名环境变量以空格分隔覆盖）。这些路径下只要有未提交改动或未跟踪文件，脚本就拒绝并列出路径；被 `.gitignore` 忽略的文件不在门内。`manuscript/`、根目录笔记等范围外的改动不阻塞实验，这样写论文不必给发车让路。这道门只看工作树是否干净，不替代第 2 条的 CI。
+4. 候选：在 `<主目录>` 运行 `scripts/gitflow.sh candidate`，它先跑 CI，再过代码门，两者都通过才打印 `H = <短哈希>` 与摘要。候选 H 是 `main` 上已提交的 commit；通过后才进入互审。
+5. 冒烟（用户裁决 2026-09-24）：互审通过后，从 H 的干净快照上机冒烟（`git archive H` 打包、校验和传输，`GIT_STAMP.json` 的 commit = H 随代码同步）；冒烟通过才进入冻结，不过则回 `main` 修复、重新 candidate。冒烟产物只判通/不崩，不进账本主表。涉及正式实验的创新必须经过这一步；只靠测试验收的改动（修 bug、重构、文档）可跳过。
+6. 冻结：正式实验前在 `<主目录>`（须检出 `main`）运行 `scripts/gitflow.sh freeze <run_id> [--no-worktree] [--link-assets <relpath>...]`。脚本先解析全部参数（未知选项即拒绝）、校验 `--link-assets` 路径、过代码门，全部通过后才在 `main` HEAD 打永久 tag `run/<run_id>`；任何一步拒绝都不留下 tag、分支或目录。默认建 run worktree `<主目录>.worktrees/run-<run_id>/`（分支 `train/<run_id>`；`RUN_BRANCH_PREFIX` 设为空串时为 detached），HEAD 等于该 tag，并调用 `scripts/git_stamp.py` 生成 `GIT_STAMP.json`。分支前缀 `train/` 与 tag 前缀 `run/` 必须不同。远端直接用 `git archive run/<run_id>` 打包同步时，可用 `--no-worktree`：只打 tag 并在 `<主目录>` 生成 stamp，不建 worktree 与分支；它不能与 `--link-assets` 同用。**正式实验**同步到训练服务器的源码只能来自 `run/<run_id>` 指向的提交，即 run worktree 或 `git archive run/<run_id>` 的快照（冒烟见第 5 条）；`GIT_STAMP.json` 随代码同步。绑定 commit 的训练前资产锁须在 `run/<run_id>` 指向的提交上重写一次，早于全部正式训练；其余冒烟阶段生成的数据资产（特征、缓存）按内容哈希复用。
+7. 资产链接 `--link-assets <relpath>...`（`freeze` 与 `wt-add` 共用）：在 worktree 的 `<relpath>` 处建符号链接，指向 `<主目录>/<relpath>` 这份真源，避免拷贝重资产。脚本在产生任何副作用之前校验：路径须为相对路径、不含 `..`、在 `<主目录>` 中存在、在待检出提交里不存在（已跟踪的文件或目录都不行，含已跟踪文件的目录不能整个链接），祖先不是该提交里的非目录条目，同一次调用里的路径不得重复或互为祖先；链接清单登记在该 worktree 的 git 管理目录里，不落在工作树中。边界：「只读」只是约定，脚本不改目标权限；经链接写入的内容会直接落到 `<主目录>` 的真源里。因此 worktree 里的程序只读链接，新实验产物写到 worktree 之外，或写到 `<主目录>` 对应的新 `run_id` 目录（`experiments/<ID>/results/<run_id>/`），不覆盖已有结果。
+8. run worktree 与 `train/*` 分支只读，禁止 commit。发现 bug 回 `<主目录>` 的 `main` 修，重新 candidate → 冒烟 → freeze 新 run_id；旧 run 结果作废并在账本标 invalid。
+9. 结果 provenance（铁律）：`git.json` / `results.tsv` / 实验 manifest 里的 commit 必须 `git branch --contains` 命中 `main` 且 `dirty=0`，正式实验还必须有对应的 `run/<run_id>` tag；不满足的结果不得进论文。
+10. 结果差不 revert：账本标 negative，代码留在树里；确需清理另起 `chore(<ID>): drop` commit。
+11. 收尾 `scripts/gitflow.sh cleanup <run_id>`：先核对 `run/<run_id>` tag 存在、run worktree HEAD 严格等于该 tag 的提交（只核对"仍在 `main` 上"不够）、仍检出 `train/<run_id>`（detached 模式须仍为 detached）、该提交仍在 `main` 上且树干净。树干净指未提交、未跟踪与被 `.gitignore` 隐藏的文件都算，只放行根目录 `GIT_STAMP.json`、`.DS_Store`、`__pycache__` 里的字节码，以及第 7 条登记过的合法链接（仍是符号链接，且指向 `<主目录>/<relpath>`）；登记过却被换了目标或换成真实目录的路径、未登记的符号链接，一律拒绝。全部成立后，脚本先逐个摘掉链接（只删链接本身，不递归，不触碰 `<主目录>` 里的目标），再删 worktree 与 `train/<run_id>` 分支；tag 保留。核对失败说明实验期间源码被切换或有 commit 混入，该 run 结果 invalid；保留现场，不得 `-D` / `--force` 强删。结果回传到主目录 `experiments/<ID>/results/<run_id>/`，永远不放进 run worktree。
+12. 并行 worktree：需要本地并行试验，或多个 AI 同时改不同模块、彼此不能干扰时，用 `scripts/gitflow.sh wt-add <name> [--link-assets <relpath>...]` 从 `main` 建 `<主目录>.worktrees/wt-<name>/`（分支 `wt/<name>`；name 以字母或数字开头，只含字母、数字与 `.` `_` `-`；目录或分支已存在即拒绝）。在其中提交，完成后在 `<主目录>` 用 `git merge --ff-only wt/<name>` 合回 `main`，再运行 `scripts/gitflow.sh wt-rm <name>`。`wt-rm` 核对目录是可用 worktree、检出的正是 `wt/<name>`、该分支已是 `main` 的祖先（未合入即拒绝），并按第 11 条的口径检查树干净，通过后摘链接、删 worktree、`git branch -d`；拒绝时保留现场，不得 `-D` / `--force`。正式实验不从 `wt-<name>` 跑，仍按第 6 条冻结。
+13. 历史与推送：禁止 force-push 或改写已打 `run/*` tag 的 `main` 历史，否则 tag 与账本里的 commit 会脱离 `main`。何时 `git push origin main` 由用户决定，提交后不自动推送。
 
 
 ## AI研究接力记录（强约束）
diff --git a/CLAUDE.md b/CLAUDE.md
index 0fc7b6a2..8a898a60 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -33,7 +33,7 @@
 - 审查包含待运行代码与配置、实验范围、实际测试/冒烟输出及发车 `--dry_run` 输出（焦点追加本节清单）；原文 `codex-review.json` 与逐条处理 `claude-response.md` 落审查目录后一并汇报用户。
 - 由于审查通常发生在 freeze 之前，下面的 provenance 三项由执行方在 freeze 后用命令机械核对，并把原始输出交给用户；不满足即阻断。
 - 逐文件查看 git diff，检查整体逻辑、致命错误、数据划分与泄漏、mask / loss / risk 口径，以及是否违反坑台账、停机门和 GPU 合同。
-- 核对 Git 工作流 provenance（AGENTS.md「Git 工作流」）：待跑 commit 已是 `main` HEAD（squash 完成、`dev` 已归位、`git diff main dev` 为空）；run worktree HEAD（分支 `train/<run_id>`，或 detached）等于 `main` HEAD 且 `git status` 干净；`GIT_STAMP.json` 的 commit 等于 `main` HEAD 且对应 `run/<run_id>` tag。三者任一不满足即阻断。
+- 核对 Git 工作流 provenance（AGENTS.md「Git 工作流」）：待跑 commit 已提交在 `main` 上且 `CODE_PATHS` 工作树干净；若使用冻结 worktree，其 HEAD 严格等于 `run/<run_id>` tag 且 `git status` 干净；`GIT_STAMP.json` 的 commit 等于该 tag 指向的 `main` 提交。三者任一不满足即阻断。
 - 核对 AGENTS.md 的完整发车与评测纪律：包括 batch_size、I/O、GPU-Util 门禁及豁免条件，`train_launcher.py` / `jobrun.sh`、`--dry_run` 和评测入口；核查有没有越权启动或重复启动任务。
 - 审查结论须写明所审代码/配置版本与实验范围、通过或阻断、问题的文件位置及证据。阻断项由执行方修复、补测，并在 `claude-response.md` 逐条记录；执行方不采纳的 high / critical 项交用户裁决。
 - 审查后若实验范围或核心逻辑发生实质变化（并非回应审查意见的修复），由执行方向用户说明，由用户决定是否作为新的审查点再审；变更后的实验须经用户明确同意再启动。审查方不以审查意见替代启动授权。
```

### 3. 表格管道符计数

```text
$ python3 -I <scratchpad>/pipes.py docs/workflow/git-workflow.md scripts/README.md tests/README.md README.md AGENTS.md CLAUDE.md
docs/workflow/git-workflow.md: 表格 9 张，不一致行 0
scripts/README.md: 表格 1 张，不一致行 0
tests/README.md: 表格 1 张，不一致行 0
README.md: 表格 1 张，不一致行 0
AGENTS.md: 表格 0 张，不一致行 0
CLAUDE.md: 表格 0 张，不一致行 0
```

结论：

- 旧词：`squash`、`worktrees/dev`、`STATUS.md` 零命中；`dev` 子串只剩 `AGENTS.md:48` 的 `device`（GPU 合同节，未改）与两处历史说明。绝对路径只命中 `AGENTS.md` 第 140–141 行与 `CLAUDE.md` 第 57 行的「AI研究接力」既有路径，均非本次新增。
- 改动范围：`AGENTS.md` 只有第 69 行（「Colab GPU」节引用句）、第 89 行（「自动审查闭环」第 2 条）与第 117–135 行（「Git 工作流」节，行数不变，节尾两行空行保留）；`CLAUDE.md` 只有第 36 行。
- 表格：脚本逐行统计每张表（跳过代码块）各行管道符数并与表头比较，全部一致。原 `git-workflow.md` 意外处理表里含转义竖线的 `./ci.sh \| tail` 已改为文字描述。

## 未解决事项（交主控裁决，均未自拟规则）

1. 候选 H 与冻结提交之间的缺口：`freeze` 在执行时的 `main` HEAD 打 tag，不一定等于通过互审与冒烟的 H，中间可能混入 `CODE_PATHS` 内的新提交；脚本与契约都没规定核对。
2. 并行 worktree 合回时 `main` 已前进：`merge --ff-only` 会失败，规则没写应先变基还是先合入。
3. 历史改写禁令按契约收窄为「禁止 force-push 或改写已打 `run/*` tag 的 `main` 历史」；旧规则禁止对 `main` 的一切 rebase。
4. `git-workflow.md` 日常循环第 3 步写了「已提交的改动用 `git revert` 撤销，不改写历史」，属说明文字；它与 AGENTS 第 10 条「结果差不 revert」字面相近但对象不同（前者撤销误提交，后者是不因结果差撤代码），需要时可改措辞。
5. `--no-worktree` 的 stamp 落点：本项目有 `scripts/git_stamp.py`，stamp 写到仓库根 `GIT_STAMP.json`；文档只写「在主目录生成 stamp」，未写具体文件名。
6. 意外处理表保留了「`cleanup` 拒绝后手动 `git worktree remove` 与 `git branch -D`」的做法，但没说 worktree 挂了资产链接时手动清理如何处理链接；建议明确先手动删除链接本身再删 worktree。
7. 白名单外仍引用 `STATUS.md`、旧编号或旧子命令的文件清单见 `notes-docs.md`。
