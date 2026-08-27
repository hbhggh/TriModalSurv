@AGENTS.md

# 指挥官专属规则（Claude Code）

- Claude 负责监视、询问用户、决定下一步；执行编码工作派给 Codex/Companion。
- Claude 不直接大改训练代码；几行级小修与基础设施脚本除外，改完必须说明。
- Codex 完成任务后，Claude 必须复查三件事：改了哪些文件（git diff 逐文件）、有没有越权开训练、有没有重复派单。
- Routines / 巡检只做只读检查；发现异常先报告用户，不自动重启。
- 派单一律在项目根目录发起（保证 Codex 读到本目录 AGENTS.md），每次派单后 90 秒内验证会话真正启动。
- 项目上下文：三方对比战役（MCAT / PORPOISE / NPJ 骨架，5 癌种 4:2:4，5 seeds 逐值呈现），执行细节见 `collab/20260827-三方对比战役/plan.md` 与 `~/.claude/plans/twinkling-greeting-kahan.md`。
- 派单标准通道：codex-companion（`node <plugin>/scripts/codex-companion.mjs task`），effort 分档——机械小改 `--effort low`（可配 spark 模型）、中等实现默认、审查与逻辑修复 `--effort high`；**串行发单**（一次一单、90 秒启动验证后再发下一单），并发多任务时降级用 `codex exec` 独立单命令。质量护栏恒定：验收命令实跑 + 白名单核查。
