# changemap：在框架图上标出 Claude 改了哪些模块、按什么顺序（plan v2）

日期：2026-10-13｜指挥：Claude Code（Opus 5.5）｜执行：coder-core 子 Agent（Opus，effort high）｜审查：Codex 只读（AGENTS.md「自动审查闭环」，C17：由用户在自己终端运行）

修订记录：v1 → v2 依据 decision-reviewer（REWORK 68/100）逐条修订：实验目录按角色拆子节点（问题 1）；会话来源默认只收当前 worktree、按 tool_use id 去重、丢弃失败调用（2、3a、3b）；步骤改为"首次第 n 步 · 共 k 次" + 节点切换时间线（3c–e）；会话参与清单与时间窗口（4）；JSONL 预筛与增量读取（5）；S3/S4/S5 验收重写（6、8、9）；glob 语义明确（7）；unittest + 3.9 + `Z` 时间戳（10）；输出目录命名（11）；收尾方式（12）。v2 轻量复审 PASS 88/100，3 条 INFO 已并入（uuid 模式不按 mtime 预筛、Q1 按区间取文件并统一点文件处理、svg 刷新退路保持原子写）。

## 0. 约束清单（T/B/P/A/Q）

`[ T：Claude（含子 Agent）改完 TriModalSurv 后，在框架图上看到"改了哪些模块、第几步、改了什么"，并随改随刷新 + Q_draft（见第 4 节 Q1–Q6：两段真实回放的归属与独立实现一致、步骤与独立 JSONL 统计一致、假 reverted 为 0 或逐条有解释、会话覆盖率报告、svg 刷新 ≤ 5 s、ci.sh 全绿）+ ∩P（只在 dev worktree 改白名单文件；不碰 src/ experiments/ configs/ 与训练/数据/结果；只用 Python 标准库、/usr/bin/python3 3.9 下测试全绿；不提交本机绝对路径；不改 hooks/settings；对 ~/.claude/projects 只读）∥ S_state（dev = main = 1c001e43，工作区干净；JSONL 实测：时间戳以 Z 结尾，tool_use id 跨文件重复 265/581，失败调用 13 次） ]`

策略筛选：k1 git diff 叠加（不漏但无顺序）、k2 会话 JSONL 叠加（有顺序但漏 Bash 改动）、k3 代码自动生成依赖图（噪音大，不是模型流程）、k4 PostToolUse hook 实时推送（每次工具调用都触发，违反"自动化轻量"）。用户裁决（2026-10-13）：**k1 + k2 组合**，实时靠轮询 watch，不用 hook；工具与图全部放 TriModalSurv。

## 1. 交付物

| 文件 | 内容 |
| --- | --- |
| `docs/architecture/framework.d2` | 手画的主流程框架图（第 3.1 节），节点有稳定 ID；不含实验臂（实验臂由脚本按需生成） |
| `docs/architecture/framework.map.json` | 主流程节点 → glob；实验角色模板（第 3.2 节） |
| `docs/architecture/README.md` | 三条日常命令、图例、归属规则（首个命中）、"工具提交未进 main 前会显示为改动"的说明 |
| `scripts/changemap.py` | 读 git diff + 会话 JSONL → 生成叠加图 / 文字报告 / watch |
| `tests/test_changemap.py` | 核心逻辑测试，**unittest 写法**（ci.sh 的 pytest 与 `/usr/bin/python3 -m unittest` 都能跑），主控先写 |
| `docs/workflow/20261013-changemap/{notes,result}.md` | 执行过程与结果（子 Agent 写） |

## 2. changemap.py 行为规格

```text
scripts/changemap.py [--base <ref>] [--head <ref>] [--session auto|none|<uuid>[,<uuid>...]]
                     [--include-worktrees] [--projects-dir <dir>] [--out <dir>]
                     [--report] [--check-coverage] [--watch [--interval 2] [--serve]]
```

### 2.1 改动来源 A（git，决定"哪些节点变色"）

- 无 `--head`：`<base>` 对工作树 = `git diff --numstat -z <base>` + 未跟踪文件（`git ls-files --others --exclude-standard -z`，+N −0，N = 文件行数，二进制记 binary）。
- 有 `--head`：`git diff --numstat -z <base> <head>`，不看工作树。
- `--base` 默认 `main`。所有 git 调用加 `-c core.quotepath=false`，用 `-z` 解析（坑 V28/E36/E40）；numstat 二进制为 `-`；改名三段式按新路径归属。

### 2.2 改动来源 B（会话 JSONL，决定"第几步、Claude 说了什么"）

- 文件布局：`<projects-dir>/*/*.jsonl`（会话）与 `<projects-dir>/*/*/subagents/*.jsonl`（子 Agent）。`--projects-dir` 默认 `~/.claude/projects`。
- **预筛**（仅 `--session auto`）：只读 mtime ≥ 窗口起点的文件；指定 uuid 时按文件名选取、不按 mtime 过滤。watch 模式按文件记录已读字节偏移，只增量读新增部分（文件变小则从头重读）。
- 收集：`type=assistant` 消息中名为 `Edit` / `Write` / `MultiEdit` / `NotebookEdit` 的 `tool_use`，路径取 `input.file_path`（NotebookEdit 取 `notebook_path`）。
- **只收成功调用**：按 `tool_use_id` 配对 `type=user` 消息里的 `tool_result`，`is_error=true` 的丢弃；找不到结果的（会话进行中）暂按成功计，报告里单列条数。
- **去重**：按 tool_use id 去重，会话归属取最早出现的文件（mtime 最早，平局按路径）。
- **工作区范围**：默认只收 `git rev-parse --show-toplevel` 根下的编辑；`--include-worktrees` 才收 `git worktree list --porcelain` 的其他根（换算为同一相对路径）。被排除的条数写进报告。仓库外路径丢弃。
- **时间窗口**（`--session auto`）：时间戳统一解析为 UTC epoch（自己处理末尾 `Z`，不依赖 3.9/3.10 的 `fromisoformat`）；下限 = `<base>` 提交时间 `%ct`；`--head` 模式上限 = `<head>` 提交时间。`none` 关闭来源 B；指定 uuid 则只收这些会话（含其子 Agent 文件）且不限时间。
- 说明文字：同一 JSONL 文件中该调用之前最近一段 assistant `text` 的首行，截断 60 字，去掉换行与反引号。
- 报告列出**参与会话清单**：会话 ID、是否子 Agent、首条用户消息前 40 字、计入的编辑数，供人工核对是否混入无关会话。
- JSONL 行损坏或字段缺失：跳过并计数，报告注明，不中断。

### 2.3 节点归属

- glob 语义（自己实现转换并测试）：`*` 和 `?` **不跨** `/`；`**` 匹配零或多层目录；`{ID}` 只出现在实验模板里，匹配 `experiments/` 下一层目录名（可含空格）。路径与 glob 均为 POSIX 相对路径、NFC 规范化后比较。
- 规则顺序：主流程节点规则（map 中的顺序）→ 实验角色模板（第 3.2 节顺序）→ 兜底 `unmapped`。**取第一个命中**；README 写明。
- `--check-coverage`：对 `git ls-files -z` 的全部已跟踪文件做归属，输出 (a) 每个节点文件数，(b) unmapped 文件清单，(c) **重叠清单**：同时命中多条规则的文件及其最终归属，用于发现宽泛规则吞掉精确规则。

### 2.4 合并（核心逻辑）

对每个节点：

- `changed`：A 中至少一个文件属于它。
  - 首次时间 = **该节点内、出现在 A 中的文件**的 B 记录里最早的时间（只用 A 中文件，避免已撤销文件的旧编辑抢先）。
  - 步骤号 n = 首次时间在所有有 B 记录的 changed 节点中的排名（1 起；同一时刻按节点 ID 字典序打破平局）。
  - 次数 k = 该节点内出现在 A 中的文件的 B 记录条数。
  - label 追加"首次第 n 步 · 共 k 次 · +a −d"；无 B 记录则追加"窗口内无会话记录"，这些文件在报告里逐个列出（可能是手改、Bash 改、窗口外编辑、其他 worktree 或 Codex 改动）。
- `reverted`：A 中无文件属于它，但 B 有记录 → "会话里改过，相对起点无净改动"（虚线框）。
- `untouched`：都没有。
- **节点切换时间线**：把 B 中属于 changed/reverted 节点的成功编辑按时间排序，连续落在同一节点的合并为一段，得到"docs → tests → I07·数据 → tests → I07·模型 …"，每段记起止时间、编辑次数、首条说明。图上以"时间线"表节点展示（最多 20 段，超出写"…另有 m 段，见报告"），报告全量列出。
- 覆盖率：changed 文件中有 B 记录的占比，写进报告与 `changes.json`。

### 2.5 输出

- `--out` 默认 `~/.cache/changemap/<仓库名>-<worktree 名>/`（仓库名取 `git rev-parse --git-common-dir` 的上级目录名，worktree 名取 toplevel 目录名），不写进仓库，也不会触发自身 watch。
- `framework.live.d2`：原图全文（逐字前缀）+ 按需生成的实验臂容器（只为 A 或 B 涉及的实验生成，其余合并为一个"其他实验（m 个，未改动）"框）+ 样式覆盖 + 图例 + 时间线表。实验目录名转 d2 ID 时规整为 `[A-Za-z0-9_]`，显示名保留原文。
- **原子写**：同目录唯一临时文件写完后 `os.replace` 覆盖。注：台账 G6 的"硬链接发布、目标已存在即失败"针对不可覆盖的正式结果，**不适用**于需覆盖的 live 文件。
- `changes.json`：节点状态、文件、行数、首次步骤、次数、时间线、参与会话、覆盖率、跳过行数、排除条数、base/head。
- `--report`：同样内容打印为 Markdown。

### 2.6 watch

- 每 `--interval` 秒算指纹 = `git status --porcelain=v1 -z` + `git diff --numstat -z <base>` + A 中已变更与未跟踪文件的 (路径, size, mtime) + 预筛后 JSONL 的 (路径, size, mtime)；变化才重新生成。
- `--serve` 启动 `d2 --watch --browser=0 framework.live.d2 framework.live.svg` 子进程并打印地址；找不到 d2 时提示 `brew install d2` 并继续只生成 .d2。Ctrl-C 结束子进程。

### 2.7 只读保证

对仓库只执行只读 git 命令；对 `~/.claude/projects` 只读；唯一写入位置是 `--out`。

## 3. 框架图

### 3.1 主流程节点（照真实代码；glob 执行时以 `--check-coverage` 结果修正）

| 节点 ID | 显示名 | glob |
| --- | --- | --- |
| launch | 发车与门禁 | `scripts/train_launcher.py`, `scripts/launch_formal.sh`, `scripts/gpu_util_gate.py` |
| entry | 训练入口与循环 | `scripts/main_survival.py`, `src/trimodalsurv/training/runtime.py`, `src/trimodalsurv/training/common_tools.py`, `src/trimodalsurv/training/model_util.py` |
| config | 配置 | `src/trimodalsurv/config.py`, `configs/**` |
| data | 数据集与分箱 | `src/trimodalsurv/data/**` |
| npjc | NPJC 骨架 | `src/trimodalsurv/models/npjc.py` |
| fusion | 融合与生存头 | `src/trimodalsurv/models/fusion.py` |
| compensator | 缺失补偿 | `src/trimodalsurv/models/compensator.py` |
| consistency | 一致性损失 | `src/trimodalsurv/models/consistency.py` |
| loss | 生存损失 | `src/trimodalsurv/training/loss_func.py` |
| eval | 缺失评估 | `src/trimodalsurv/evaluation/**`, `scripts/eval_missing.py`, `scripts/gen_missing_manifest.py` |
| provenance | 溯源与工作流工具 | `src/trimodalsurv/gitstamp.py`, `scripts/git_stamp.py`, `scripts/gitflow.sh`, `scripts/ci.sh`, `scripts/codex_review.sh`, `scripts/changemap.py` |
| project | 项目配置 | `pyproject.toml`, `conftest.py`, `.gitignore` |
| tests | 共享测试 | `tests/**` |
| docs | 文档与规则 | `docs/**`, `manuscript/**`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `STATUS.md` |

连线：launch → entry；config → entry；data → entry；entry → npjc / compensator → fusion → loss；consistency → fusion、compensator；entry → eval。

### 3.2 实验臂角色模板（每个被涉及的 `experiments/{ID}/` 生成一个容器，内含以下子节点，按此顺序首个命中）

| 子节点 | glob（相对 `experiments/{ID}/`） |
| --- | --- |
| 测试 | `tests/**` |
| 结果 | `results/**` |
| 审查记录 | `reviews/**` |
| 数据准备 | `prep/**`, `data*.py`, `export_texts.py`, `condense.py`, `prompts/**` |
| 模型 | `model*.py`, `survival.py` |
| 训练与发车 | `train*.py`, `runtime.py`, `launch*.py`, `train_plan*.yaml`, `config.yaml` |
| 评测与渲染 | `evaluate*.py`, `verify*.py`, `render*.py`, `summarize*.py` |
| 工具与溯源 | `tools/**`, `provenance.py`, `contract.py`, `freeze.py` |
| 知识与说明 | `knowledge/**`, `assets/**`, `*.md`, `__init__.py` |
| 其他 | `**`（兜底，同一实验内未命中以上规则的文件） |

子节点在容器内按"数据准备 → 模型 → 训练与发车 → 评测与渲染"横向排列，与主流程的 data / model / loss / eval 列对齐；其余子节点放第二行。

## 4. 分步任务与验收

| 步 | 内容 | 核心逻辑 | 验收 |
| --- | --- | --- | --- |
| S1 | 主控写 `tests/test_changemap.py`（unittest），在没有 `scripts/changemap.py` 时以显式存在性断言 RED（坑 V12） | 是 | 两个解释器下都 RED，且失败原因是"脚本不存在"的显式断言，不是别的导入错误 |
| S2 | 子 Agent 实现 `scripts/changemap.py` 至测试全绿 | 是 | `<protomasksurv-exp1>/bin/python -B -m pytest -q tests/test_changemap.py` 与 `/usr/bin/python3 -B -m unittest tests.test_changemap` 都全绿；连跑 3 次 |
| S3 | 子 Agent 写 `framework.d2` + `framework.map.json` + README | 否 | `d2` 编译通过；`--check-coverage` 输出的 unmapped 清单与重叠清单逐个写理由进 notes.md（主控审）；任何"宽泛规则吞掉精确规则"的重叠必须修正规则顺序 |
| S4 | 真实回放（主控亲自跑），两段区间：R1 `ef5d18cb..3d01b19f`（I07，几乎全在实验目录）、R2 `c5aa9ea2~1..c5aa9ea2`（I06，同时改 src/training、tests、I05/I06） | 是 | 见 Q1–Q4 |
| S5 | 刷新延迟：在 `/private/tmp/changemap-*` 的 `git clone --shared` 副本上，用真实 `~/.claude/projects`（只读）跑 `--watch --serve` | 是 | 见 Q5 |
| S6 | 全量 CI | 否 | `PYTHON_BIN=<protomasksurv-exp1>/bin/python scripts/ci.sh` 退出码 0 |
| S7 | Codex 只读审查 | — | 主控给出完整 `codex_review.sh` 命令由用户在终端运行（C17），审查目录 `docs/reviews/20261013-changemap/`；按闭环处理 |

### 验收标准 Q（主控亲自核对，交原始输出）

- **Q1 归属正确（独立实现）**：对 R1、R2，用不经过 changemap 的另一套实现算"文件 → 节点"：主控单独写一段 python，用 `git diff --name-only -z` 取文件、逐规则用 `git -c core.quotepath=false diff --name-only -z <base> <head> -- ':(glob)<pattern>'` 取命中集合（取区间内的文件，不取当前索引）、按规则顺序首个命中；两套实现对点文件的处理一致（`*` 能匹配点文件）。两套结果逐文件完全一致。
- **Q2 R1 颗粒度**：R1 至少点亮 4 个不同的 I07 子节点；R2 至少点亮 1 个 src 主流程节点和 1 个实验子节点。
- **Q3 步骤正确（独立统计）**：主控单独写一段 python 直接扫 JSONL（同样按工作区过滤、丢失败、按 id 去重），列出每个 changed 文件的首次成功编辑时间，推出节点首次时间与次数，与 `changes.json` 全量比对一致。
- **Q4 假 reverted 与覆盖率**：报告的 reverted 节点为 0，或逐个有 JSONL 证据说明"确实改过又改回"；B 覆盖率写明数字，每个"窗口内无会话记录"的文件给出原因（查 git log / 是否 Bash 改）。
- **Q5 用户看到的刷新**：`--serve` 下在副本里连续改同一 `src/` 文件 3 次、再改另一节点 1 次，每次从保存到 `framework.live.svg` mtime 更新 ≤ 5 s，且 svg 中对应节点颜色正确；`os.replace` 换 inode 后 d2 仍能检测到（若检测不到，退路是 changemap 自己运行 `d2 live.d2 <临时>.svg` 再 `os.replace` 发布 svg，仍保持原子写，不改成原地截断写入；记入 notes 与坑台账）。
- **Q6 CI**：ci.sh 退出码 0；`/usr/bin/python3 -B -m unittest tests.test_changemap` 全绿。

### S1 测试必须覆盖（主控写）

1. glob：`*` 不跨 `/`；`**` 零层与多层；`{ID}` 含空格目录名；首个命中优先；中文路径 NFC/NFD 两种输入；不命中进 unmapped；重叠检测。
2. numstat `-z`：普通、二进制 `-`、改名三段式、含空格与中文的路径。
3. 未跟踪文件计入 A，行数 = 文件行数。
4. JSONL：四种编辑工具都收、Read/Bash 不收；子 Agent 文件也收；`is_error=true` 丢弃；同一 tool_use id 出现在两个文件只算一次；默认只收当前 toplevel，另一 worktree 根的编辑被排除并计数，`--include-worktrees` 时换算为同一相对路径；仓库外路径丢弃；损坏行跳过计数；时间戳带 `Z`；窗口外的编辑不收。
5. 合并：首次时间只用 A 中文件；步骤排名与平局；次数 k；changed 无 B 记录；reverted；时间线连续同节点合并。
6. 说明文字：取之前最近 assistant text 首行、截断 60 字、无反引号。
7. 输出：live.d2 以原图全文为逐字前缀；只为涉及的实验生成容器；目录名规整为合法 ID；原子写；`changes.json` 字段齐全；输出目录名含仓库名与 worktree 名。
8. 只读：对 fixture 仓库跑完后 `git status --porcelain` 与跑前一致，fixture projects 目录文件 mtime 不变。
9. 端到端：临时 git 仓库 + 运行时拼出的 projects 目录（不硬编码 `/Users/`），跑 CLI，断言 `changes.json`。
10. watch 指纹：只改未跟踪文件内容（status 不变）也会触发重算。

## 5. 文件白名单（dev worktree 内，仓库相对路径）

- 新增：`scripts/changemap.py`、`tests/test_changemap.py`、`docs/architecture/framework.d2`、`docs/architecture/framework.map.json`、`docs/architecture/README.md`、`docs/workflow/20261013-changemap/notes.md`、`docs/workflow/20261013-changemap/result.md`
- 追加：`docs/engineering/pitfalls.md`（仅当出现新坑，一行一条，去重）
- 临时：`/private/tmp/changemap-*`（副本、fixture、独立核对脚本），用完删除；独立核对脚本的原始输出抄进 notes.md

## 6. 禁止事项

- 不改白名单外任何文件，尤其 `src/`、`experiments/`、`configs/`、其他 `scripts/`、`.gitignore`、AGENTS.md、CLAUDE.md。
- 子 Agent 不 commit、不 push、不跑 gitflow。
- 不联网、不装包；只用标准库。
- 提交文件中不出现 `/Users/` 或 `/home/` 绝对路径（坑 I05-04）；提交前 `git diff --cached | grep "^+" | grep -E "/home/|/Users/"` 必须为空。
- 不碰 `~/.claude/settings*.json`、hooks、任何 Claude 配置；对 `~/.claude/projects` 只读。
- 不启动训练、评测、GPU 任务；不连 landau/tako。

## 7. 收尾

- 审查通过并经用户确认后，主控在 dev 单独提交 `chore(tools): changemap 框架图改动叠加`（只 add 白名单文件），`scripts/gitflow.sh candidate` 通过后作为**独立工具提交** squash 进 main（只靠测试验收，跳过上机冒烟，AGENTS.md Git 第 5 条）。
- squash 前 `--base main` 会把 changemap 自身显示为改动，README 说明这个现象。

## 8. 相关坑

G4（会话目录 ≠ 目标仓库，改动只落 dev worktree）、V28/E36/E40（git 路径转义，`-c core.quotepath=false` + `-z`）、G6（不可覆盖结果用硬链接发布；live 文件覆盖用 `os.replace`，见 2.5）、V12（RED 用显式存在性断言）、I05-04/I05-12（不提交本机绝对路径，只 add 明确文件）、E34（zsh 下 glob 参数加引号）、S1（测试设 `PYTHONDONTWRITEBYTECODE=1`）、M7（独立核对脚本的输出抄进 notes）、C17（Codex 审查由用户终端运行）、V20（回归基线取派单前快照）。

## 9. 测试命令

```text
cd <dev worktree>
PYTHONDONTWRITEBYTECODE=1 <protomasksurv-exp1>/bin/python -m pytest -q tests/test_changemap.py
/usr/bin/python3 -B -m unittest tests.test_changemap
/usr/bin/python3 scripts/changemap.py --help
PYTHON_BIN=<protomasksurv-exp1>/bin/python scripts/ci.sh
```
