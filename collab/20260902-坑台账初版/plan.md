# 坑台账初版 · 派单契约

派单人 Claude，执行人 Codex。目标：把历史 Post-Mortem 提炼成集中坑台账，防止重复 bug。

## 目标

读取下列文件中**全部** `### Bug Post-Mortem` 条目（以及审查报告中虽非 PM 格式但性质相同的教训），归类提炼，生成台账 `collab/pitfalls.md`：

- `collab/20260826-NPJ三模态复现/notes.md`、`result.md`、`审查/codex-对抗审查报告-20260826.md`
- `collab/20260827-三方对比战役/notes.md`（约 30 条，主要来源）、`result.md`（约 12 条，多为 notes 精选转载，需去重）
- `collab/20260828-A测缺失补偿/` 目录下全部 .md（扫描以防遗漏；该目录已废弃但教训仍有效）
- `collab/20260902-A测缺失补偿/notes.md`（约 5 条）、`result.md`

## 台账格式（必须严格遵守）

文件头部固定为：

```markdown
# TriModalSurv 坑台账（Pitfalls Ledger）

> 一行一坑。用法（回流三环，规则见 CLAUDE.md）：
> ①注入——派单前 Claude 从此处挑 3~5 条相关条目写进 plan.md「相关坑」节；
> ②入账——收单 review 时新 Post-Mortem 各提炼一行追加至此；
> ③升级——影响全局的坑经用户确认固化进 CLAUDE.md/AGENTS.md。
> 详细 Post-Mortem 原文见「出处」列。
```

正文按类别分节（按需取舍，允许增删类别）：数据与口径 / 通道与派单 / 沙箱与权限 / 环境与依赖 / 评测与复现 / 监控与运维。每节一张表：

```markdown
| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| D1 | ... | ... | collab/20260827-三方对比战役/notes.md |
```

ID 规则：类别首字母 + 序号（数据 D、通道 C、沙箱 S、环境 E、评测 V、监控 M）。

文件末尾附「合并映射」节：列出哪些原始 PM 被合并成同一条（如"notes.md 第 3、17 条同为 bfloat16 导出问题 → E2"），保证每条原始 PM 都能对上台账某一行，无一遗漏。

## 提炼要求

- 「坑」列写**现象+场景**（读者一眼知道踩的是什么）；「Prevention Rule」列写**可执行的动作**（不是"要小心"这类空话），忠实于原 PM，不自行发挥。
- result.md 与 notes.md 重复的条目只入账一次，出处标 notes.md。
- 逐条核对出处路径真实存在。

## 白名单

- 只允许新建 `collab/pitfalls.md` 一个文件。
- 本目录 `notes.md`（过程档案，append-only）与 `result.md`（交付记录）按惯例可写。

## 禁止事项

- 禁止修改任何既有文件。
- 禁止碰训练代码、数据目录、`tmp_sur_cache/`、结果目录。
- 禁止 git commit / push。
- 禁止启动任何训练或长任务。

## 验收标准（Claude 收单时实跑）

1. `git status` 仅新增 `collab/pitfalls.md` 与本目录 `notes.md`。
2. 合并映射节覆盖全部原始 PM（Claude 抽查 ≥10 条对照原文，无失真、无遗漏）。
3. 出处列路径逐条有效（`ls` 核查）。
4. 台账头部用法说明与 CLAUDE.md 三环规则一致。

## 相关坑（本任务需遵守的历史教训）

| 坑 | Prevention Rule | 出处 |
|---|---|---|
| companion task 默认只读沙箱，写任务写不进文件 | 本单已由派单人首启带 `--write`；执行中若发现无法写文件，如实报告而非绕过 | CLAUDE.md 固化坑 |
| 通道断被误判为任务死亡导致二次派单 | 执行中断后等待派单人查进程续接，不自行重启重做 | AGENTS.md 执行纪律 |
| 交付自述与实际不符（result.md 声称通过但未实测） | result.md 中所有"已核对"必须附实际命令输出 | AGENTS.md 互审纪律 |
