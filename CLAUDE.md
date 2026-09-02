@AGENTS.md

# 指挥官专属规则（Claude Code）

## 执行前必读（坑台账）

开始任何实现、复现、评测、派单或修 bug 之前，必须先完整阅读：

`collab/pitfalls.md`

这是本仓库唯一的坑台账。读完再动手。禁止凭记忆声称已经知道这些约束。
新发现的失效模式收单时追加到同一文件：一行一条，含 ID、一句话坑、一句话 Prevention Rule、出处。
不要另起清单，不要把同一 Post-Mortem 重复入账。

最小执行口径：以本小节 + `collab/pitfalls.md` 为准。不再要求每次手工挑 3–5 条写入 plan.md。

- Claude 负责监视、询问用户、决定下一步；执行编码工作派给 Codex/Companion。
- Claude 不直接大改训练代码；几行级小修与基础设施脚本除外，改完必须说明。
- Codex 完成任务后，Claude 必须复查三件事：改了哪些文件（git diff 逐文件）、有没有越权开训练、有没有重复派单。
- Routines / 巡检只做只读检查；发现异常先报告用户，不自动重启。
- 派单一律在项目根目录发起（保证 Codex 读到本目录 AGENTS.md），每次派单后 90 秒内验证会话真正启动。
- 项目上下文：三方对比战役（MCAT / PORPOISE / NPJ 骨架，5 癌种 4:2:4，5 seeds 逐值呈现），执行细节见 `collab/20260827-三方对比战役/plan.md` 与 `~/.claude/plans/twinkling-greeting-kahan.md`。
- 派单标准通道：codex-companion（`node <plugin>/scripts/codex-companion.mjs task`），**每单必须显式传 `--model` 与 `--effort`**（sol/terra 无别名必须写全名 slug；companion 的 effort 白名单不含 `max`）：

  | 任务类型 | 模型 | effort |
  |---|---|---|
  | 机械小改 / 批量替换 / 跑脚本 | `gpt-5.3-codex-spark` | `low` |
  | 常规实现（单模块、明确 spec） | `gpt-5.6-terra` | `medium` |
  | 复杂实现 / 多文件联动 | `gpt-5.6-sol` | `high` |
  | 对抗审查 / 逻辑修复 / 疑难诊断 | `gpt-5.6-sol` | `xhigh` |

- 长任务后台化：预计 >10 分钟的单一律 `--background` 发；jobId 与完整派单命令（含 model/effort）写入该战役 notes.md（保证事后可追溯"这单用的哪档"）；追踪用 `status <jobId> --wait --timeout-ms`；巡检对 running 任务做 idle 检测，**45 分钟无输出 → 报告用户**（只报警不杀，遵守 AGENTS.md）。
- **串行发单**（一次一单、90 秒启动验证后再发下一单），并发多任务时降级用 `codex exec` 独立单命令。质量护栏恒定：验收命令实跑 + 白名单核查。
- companion 用法坑：task 默认只读沙箱，写任务必须首启带 `--write`；`--resume-last` 继承原线程沙箱、无法中途升权——升权=不带 `--resume-last` 开新会话（`--fresh` 实为空操作，可省略）；companion 对不认识的 `--flag` 会**静默拼进 prompt 正文**，发单前自查参数拼写。
- 坑台账回流（防重复 bug）：台账在 `collab/pitfalls.md`，一行一坑。①**注入**——每份派单 plan.md 必须含「相关坑」节，从台账挑 3~5 条与本任务相关的条目抄入（无相关坑则写"无"）；②**入账**——收单 review 固定动作：读 notes.md/result.md 新增 Post-Mortem，各提炼一行追加进台账；③**升级**——影响所有后续任务的坑，经用户确认后固化进 CLAUDE.md/AGENTS.md。
