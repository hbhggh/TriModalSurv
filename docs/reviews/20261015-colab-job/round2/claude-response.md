# 复审处理：20261015-colab-job / round2

- 复审结论：`codex-review.json`，verdict `needs-attention`，1 条 high。
- 按 AGENTS.md「自动审查闭环」第 3、5 条：复审仍有核心逻辑问题，**停下交用户裁决，不自动进入第三轮**。下面的修复只改了未提交的工具文件，可以撤回；采纳与否、是否再审，由用户决定。

| # | 级别 | finding | 处理 |
|---|---|---|---|
| 1 | high | 已认领但尚未写入 PID 的任务可被同名 start 绕过 | **采纳（待用户确认）**，修复与补测见下 |

## 修复（`tools/colab_job.sh` 的 `register_request()`）

- 在同一把 `fcntl` 锁里，"存在 `JOB.run.*` 且没有 pid、没有 rc"（已被 kernel 认领、pid 尚未写入）也判为 RUNNING 并拒绝。
- 同名任务已结束（rc 已写）或已死（pid 对应进程不在）时，除了清理 pid / rc，也一并清理残留的 `JOB.run.*`，避免认领文件残留后永久拒绝。
- 已知边界：kernel 恰好在 rename 之后、写 pid 之前崩溃时，`run.*` 会残留且没有 pid，之后的同名 start 会一直报 RUNNING，需要人工删除该文件。这里选择宁可拒绝，不允许重复启动。

## 补测（`tools/test_colab_job_start.sh`）

- 不在生产代码里加测试钩子（坑 I05-06），而是直接在模拟远端构造状态，确定性地命中窗口：
  - **T6**：已有 `j6.run.111`，没有 pid、没有 rc。断言同名 start 被拒（退出码 1）、执行 0 次、认领文件不被误删。
  - **T7**：已有 `j7.run.222`，pid 对应进程已退出（DIED）。断言 start 成功、执行 1 次、残留认领文件被清理。
- **上一版（去掉 run.* 检查后重建）：RED**。T6 的同名 start 通过（退出码 0）并执行了 1 次，复现了复审 finding；T7 残留文件没有清理。
- **修复版：GREEN**。连跑 3 次，每次 21 项 PASS、0 FAIL，退出码 0。首审的 T1–T5 同时回归通过。
- 静态检查：`bash -n` 通过；`$var` 紧跟全角字符 0 处。
