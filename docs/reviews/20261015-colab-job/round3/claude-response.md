# 第三轮处理：20261015-colab-job / round3

- 这一轮由用户在 2026-10-15 明确授权，属于自动闭环之外的额外审查。
- 结论：`codex-review.json`，verdict `needs-attention`，1 条 high。
- 用户裁决：
  - 复审仍有核心问题，交用户后，用户选择"先开 GPU，并行修复"。
  - 训练期间用户要求按最小修改原则收口：**不再送第四轮审查**。
  - 修复版经用户批准，整体合并进 `~/.claude/skills/colab-gpu/scripts/`。

| # | 级别 | finding | 处理 |
|---|---|---|---|
| 1 | high | DIED 重启会与旧 kernel 收尾竞争并污染新任务 | **采纳**，修复与补测见下；按用户裁决不复审 |

## 修复（`colab_job.sh`）

- kernel 认领请求后，先把认领者（本 kernel 进程）的 pid 写进 `JOB.run.<token>`，再启动任务。收尾放在 `finally` 里删除认领文件，文件已被回收时不报错。
- `register_request()` 在 rc 未写时，只要认领者或子进程任一存活，就判 RUNNING 并拒绝。只有"rc 已写"或"认领者与子进程都已不在"时，才回收 pid、rc 和认领文件，因为这时已经没有旧 owner 会继续写状态。空的认领文件（刚认领、尚未写入 pid）按存活处理。

## 补测（`test_colab_job_start.sh`）

- **T7**：认领者和子进程都已不在（DIED）。期望允许重新 start、只执行 1 次，并清理残留文件。
- **T8**（本 finding 的场景）：子进程已退出、认领者存活、rc 未写。期望同名 start 被拒，旧 owner 的 pid 和认领文件不被回收；旧 owner 收尾后再 start，只执行 1 次，state 显示新任务的退出码 7，没有被旧 rc 污染。
- **T9**：rc 已写、认领文件尚未删除。期望允许回收，旧 owner 随后的清理不影响新任务。
- 结果：
  - **round2 版（本次 L4 运行用的冻结副本，sha256 `400ee9af…`）：RED**。T8 同名 start 通过，旧 owner 被回收，执行了 2 次。
  - **修复版：GREEN**，T1–T9 共 29 项全部通过，退出码 0。
- 证据边界：以上是本地模拟，不是真实 Colab kernel；本次 L4 验证只 start 一次，走不到这些路径。

## 去向

- 修复版 `colab_job.sh`（sha256 `20335c7a…`）和 `test_colab_job_start.sh`（sha256 `49406b7a…`）已整体复制进 skill，并核对逐字节一致。
- 按用户裁决，项目不保留副本：dev worktree 里未提交的 `tools/` 已删除。上面几轮记录中提到的 `tools/…` 路径，现在对应 `~/.claude/skills/colab-gpu/scripts/` 下的同名文件。
