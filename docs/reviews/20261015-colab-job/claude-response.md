# 首审处理：20261015-colab-job

- 审查对象：dev worktree 中未提交的 `tools/colab_job.sh`、`.colabignore`、`AGENTS.md`「Colab GPU」一节，以及仓库外的运行驱动 `~/colab_runs/i07-l4-20261015/soak_i07.sh`。
- 背景：Colab L4 小时级稳定性验证（基础设施验证，非正式实验，结果不入账本）。源码为 main `1c001e43` 的 git archive 快照加 `GIT_STAMP.json`。
- 首审结论：`codex-review.json`，verdict `needs-attention`，1 条 high。

## 首次调用中断记录（AGENTS.md「自动审查闭环」第 5 条例外）

- 2026-10-15 18:2x JST，用户在自己的终端运行首审命令，没有产出任何结论。核实结果：
  - 审查目录不存在。`codex_review.sh` 在调用 companion 前会先 `mkdir -p` 输出目录，说明它在启动检查阶段就退出了。
  - `~/.codex/sessions/2026/10/15/` 不存在。
  - 没有存活的 `codex-companion.mjs adversarial-review` 进程。
- 18:38 在用户的终端面板（tab c1）用同一脚本重新发起一次，18:39 落盘本目录的 `codex-review.json`。按例外条款，这一次不算复审。

## 逐条处理

| # | 级别 | finding | 处理 |
|---|---|---|---|
| 1 | high | 同名重试会撤销旧排队任务的取消标记，旧请求可能延后启动，导致重复训练和持续扣费 | **采纳**，修复与补测见下 |

### #1 修复（`tools/colab_job.sh`）

- 每次 `start` 生成唯一 token，登记请求文件 `logs/JOB.req.<token>`。kernel 里的代码用 `os.rename(req → JOB.run.<token>)` 原子认领**属于自己的**请求；认领不到（已被撤销）就不执行。
- 排队超时的撤销就是删掉自己的请求文件：`rm` 与 `rename` 只会有一个成功。撤销前一刻已被认领时，报告"已启动"并退出 0；撤销成功才报告"不会延后启动"。重试换新 token，旧请求无论何时轮到都认领不到，**不会复活**。原来的共享 `JOB.cancel` 标记已删除。
- 新增 `register_request()`：在远端同一把 `fcntl` 锁里检查并登记。同名请求未决（`JOB.req.*` 存在）返回 PENDING，同名进程存活返回 RUNNING，两种情况都拒绝；进程已不在（DIED）时允许重新登记。这样也防住了并发的同名 start。
- 轮询和撤销命令遇到 ssh 失败不再被 `set -e` 直接中断（`|| st=""`、`|| r="SSH_ERROR"`），确保会走到撤销与报错。

### #1 补测（`tools/test_colab_job_start.sh`）

- 本地模拟，不连 Colab：
  - fake ssh 在本机执行"远端"命令；
  - fake `colab exec` 把代码**立即放进队列**，结束客户端也撤不回已排队的代码，即审查指出的最坏情况；
  - kernel worker 按 FIFO 串行执行；
  - 全部在 zh_CN.UTF-8 下用 /bin/bash 3.2 运行。
- 用例：
  - T1 正常启动；
  - T2 超时后同名重试，且 kernel 在重试窗口内空闲（复活场景）；
  - T3 两个同名 start 并发；
  - T4 已结束任务同名重跑；
  - T5 已有同名请求在排队时拒绝新的 start。
- **旧版（PoC 定稿，与 `~/.claude/skills/colab-gpu/scripts/colab_job.sh` 逐字节相同）：RED，5 项 FAIL**：
  - T2 执行 2 次（复现了 finding）；
  - T3 两个 start 都报成功，执行 2 次；
  - T5 第二个 start 未被拒，并且"已标记取消"的请求后来执行了 1 次。
- **新版：GREEN**，连跑 4 次全部 ALL PASS（第 4 次不经管道，退出码 0）。模拟 kernel 输出显示 j2 和 j5 的旧请求"已在启动前撤销，不执行"，远端没有残留的 `req.*` / `run.*` 文件。
- 其他：参数路径 6 条自测（zh_CN.UTF-8、bash 3.2）结果符合预期；`scripts/ci.sh` 520 passed / 6 skipped，`CI PASS`。
- 证据边界：以上是对 Colab kernel 串行与排队语义的模拟，不是真实 kernel。真实 L4 运行只会走到正常启动路径。
