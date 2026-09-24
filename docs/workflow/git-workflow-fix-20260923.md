# Git 工作流脚本修复记录（2026-09-23）

> 范围：`scripts/gitflow.sh`、`scripts/ci.sh`（均为 2026-09-22 新建、尚未提交）。执行方 Claude Code（Opus 5.5），审查方 Codex（只审核）。
> 来源：2026-09-23 一次只读 Codex 对抗审查报告的三个问题（见 `manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT-程序性知识/研究计划书-BioClinical ModernBERT.md` Post-Mortem 3），以及本次修复中发现的第 4 个问题。
> 回归测试：`tests/test_workflow_scripts.py`（21 条，全部在临时仓库 / 假项目中运行，清洗 `GIT_*` 与脚本配置环境变量并设 `GIT_CEILING_DIRECTORIES`，不触碰真实仓库）。

## 修复摘要

| # | 级别 | 问题 | 修复 | 回归测试 |
|---|---|---|---|---|
| 1 | high | `cleanup` 只用 `merge-base --is-ancestor` 核对 run worktree HEAD「仍在 main 上」；切到 main 上更早的提交也通过，删掉现场而 `run/<id>` tag 仍指向原冻结提交 | 依次核对：tag 存在（`refs/tags/<tag>^{commit}`）→ HEAD 严格等于 tag 提交 → 检出 `refs/heads/RUN_BRANCH_PREFIX<id>`（前缀为空须 detached）→ tag 提交仍在 MAIN 上 → 树干净；全部成立才 `worktree remove`（无 `--force`）+ `branch -d`；任一不符 `die` 并保留现场；`-d` 被拒时照实报告，不升级为 `-D` | `GitflowCleanupTests`（13 条） |
| 2 | medium | `ci.sh` 忽略参数，`--help` 也先递归删 `__pycache__` 再跑整套测试 | 顶部先解析参数：`-h/--help` 打印用法退 0；其他参数退 2；均在 `cd`、清缓存、测试之前 | `CiArgumentTests`（3 条，含无参数正对照） |
| 3 | medium | `gitflow.sh` 先 cd 到仓库根再按相对 `$0` 读帮助；仓库外又先被「不在 git 仓库内」拒绝 | 仓库探测前预存脚本绝对路径并处理 `help/-h/--help`；帮助按文件头注释块动态打印（不再硬编码行号） | `GitflowHelpTests`（3 条） |
| 4 | 审查未报 | macOS 自带 bash 3.2 在 UTF-8 locale 下把紧跟 `$var` 的全角标点首字节并入变量名，`set -u` 下崩溃；`init`/`squash`/`cleanup` 在 git 操作完成后才崩，以 1 退出 | 7 处改成 `${var}`；脚本内加注释说明 | `GitflowMultibyteTests`（静态扫描 + init→squash 端到端） |

## Bug Post-Mortem

### Bug Post-Mortem 1（cleanup 身份核对过宽）

- **现象**：run worktree 被 `reset --hard` 到 main 上更早的提交后，旧 `cleanup` 以 0 退出，删掉 worktree 与 `train/r1`，`run/r1` 仍指向原冻结提交（`LC_ALL=C` 下临时仓库原样复现）。
- **根因**：把「冻结身份不变」近似成「HEAD 可从 main 到达」；可达性对 main 上任意祖先都成立，不能代表相等。
- **修复**：以 freeze 打的 tag 为锚点做逐值相等与分支形态核对，另保留「tag 提交仍在 main 上」与干净树预检；任一不符拒绝并保留现场。
- **Prevention Rule**：身份/冻结类核对一律与冻结锚点逐值相等比较并核对检出形态，不用可达性（is-ancestor）代替相等；拒绝时保留现场，不强删。

### Bug Post-Mortem 2（ci.sh 忽略参数）

- **现象**：`bash scripts/ci.sh --help` 先递归删除 `__pycache__`，再跑整套测试。
- **根因**：脚本没有参数解析段，副作用语句排在最前面。
- **修复**：`set -euo pipefail` 之后立即解析参数，帮助退 0、未知参数退 2，再做 `cd` / 清缓存 / 测试。
- **Prevention Rule**：shell 入口第一步解析参数（`-h/--help` 退 0、未知参数非零），之后才允许任何副作用。

### Bug Post-Mortem 3（gitflow.sh 帮助路径）

- **现象**：在 `scripts/` 里运行 `bash gitflow.sh --help` 报 `sed: gitflow.sh: No such file or directory`；仓库外用绝对路径查询帮助报「不在 git 仓库内」。
- **根因**：帮助分支放在仓库探测与 `cd "$repo_top"` 之后，且用相对 `$0` 读自身。
- **修复**：仓库探测前预存 `SCRIPT_PATH`（绝对路径）并处理帮助参数。
- **Prevention Rule**：需要读取自身文件的脚本在任何 `cd` 之前解析绝对路径；帮助等纯信息参数先于环境探测处理。

### Bug Post-Mortem 4（bash 3.2 多字节变量名）

- **现象**：UTF-8 locale 下旧 `cleanup` 正常路径报 `branch�: unbound variable` 并以 1 退出（worktree 与分支此时已删）；`init` 建好 dev worktree、`squash` 提交 S 并归位 dev 之后同样崩溃。
- **根因**：macOS 的 `isalnum()` 在 UTF-8 locale 下把 0x80–0xFF 按 Latin-1 码位归类（0xEF = ï 为字母），bash 3.2 因而把 `；`（EF BC 9B）等全角字符的首字节并入 `$branch` 的变量名；Python（PEP 538）会给子进程设 `LC_CTYPE=UTF-8`，终端通常也是 UTF-8，所以常态触发。自测若在 C locale 下跑就看不到。
- **修复**：所有紧跟非 ASCII 字符的变量改成 `${var}`；静态回归扫描两个脚本。
- **Prevention Rule**：面向 macOS `/bin/bash` 的脚本中，变量后紧跟中文或全角标点时一律写 `${var}`，并用静态扫描守住；shell 脚本自测至少在 UTF-8 locale 下跑一遍。

## 验证

- 新测试对原脚本（隔离副本）：18 失败 / 3 通过，失败原因逐条对应上表；修复后 21/21 通过（默认 locale 与 `LC_ALL=C` 各一遍），`unittest` 回退路径 21/21。
- 全仓 CI（`PYTHON_BIN=<protomasksurv-exp1 环境的 python> bash scripts/ci.sh`，Claude 会话 worktree 于 `347612b`）：改前 4 failed / 200 passed / 6 skipped；改后 4 failed / 221 passed / 6 skipped，失败集合逐 ID 与改前相同（3 个 I02 + 1 个 I01），新增 21 条全过。

## 待审查方关注

- 规格外的小加固：保留「tag 提交仍在 main 上」核对；加干净树预检（取代 git 自带的「use --force」提示）；`-d` 被拒时给出明确信息。均为拒绝路径，不放宽任何核对。
- `AGENTS.md`「Git 工作流」第 10 条仍写旧口径（`git merge-base --is-ancestor`），改规则文件需用户确认，本次未改。
