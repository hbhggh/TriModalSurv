# 坑台账每日入账 Routine 说明

## 目的

每日一次扫描战役文档，把尚未入账的 `### Bug Post-Mortem` 追加进唯一台账 `collab/pitfalls.md`。单写入点、每日一次、追加不重写。

## 创建命令

```text
/schedule 每天 02:00 按 collab/pitfalls-routine.md 中的 Routine prompt 扫描并入账坑台账
```

## Routine prompt（原版，供上 GitHub 后使用）

```text
目标：把尚未入账的 Bug Post-Mortem 追加到 collab/pitfalls.md。

只做这些：
1. 扫描 collab/ 下所有 notes.md 与 result.md，定位标题为「### Bug Post-Mortem」的节（只认标题行，不认正文里提到「坑」「PM」的句子）。
2. 对照 collab/pitfalls.md 已有「出处」列和文末「合并映射」：已收录的跳过；同一 PM 被 result.md 转载的不新开行。
3. 对新坑按现表格式追加一行：ID | 一句话坑 | 一句话 Prevention Rule | 出处路径。
4. ID 按所属分节现有前缀续最大号（D/C/S/E/V/M），不改旧行，不重排，不重写全文，不删映射。
5. 若只是已有坑的另一处出现，只在「出处」或「合并映射」补指针。
6. 有改动则开 PR，分支名 claude/pitfalls-YYYYMMDD（日期用当天 UTC 或仓库时区日期），提交信息简短说明新增了哪些 ID。不要直推默认分支。
7. 没有新坑则不要改任何文件，也不开空 PR。
8. 改动范围仅限 collab/pitfalls.md（必要时更新文末合并映射）。禁止改代码、禁止改 CLAUDE.md / AGENTS.md、禁止改战役 notes 原文。

禁止：
- 把讨论、摘要、表格引用计成新条目
- 改写历史行的「坑」或 Prevention 表述
- 同一根因开两条 ID
- 并发假设文件未被他人修改：写前重读文件尾部再追加
```

## 当前生效版本的一处适配（本仓库无 git remote）

现行 routine 为本机会话（同 Task sweep monitor 机制），直接读写本地仓库，与上文原版仅两处差异：

- 第 1 条补充：标题锚定同时识别 `### / #### Bug Post-Mortem` 与「### … Post-Mortem」变体标题（实证存在，如 `collab/20260902-A测缺失补偿/notes.md:63`）。仍然只认标题行。
- 第 6 条替换为：有改动则**直接保存到工作树**（不开分支、不 commit、不 push），并在会话报告中列出新增 ID 与出处。

仓库上 GitHub 后：删除本机 routine，用上文原版 prompt 重建 cloud 版，恢复 PR 审核环。

## 审核方式

- 用户日常 `git diff collab/pitfalls.md` 即审核点：新增行确认无误则随下次提交入库；不认可则删行。
- 极少数需升格为 CLAUDE.md/AGENTS.md 条款的坑，保持人工判断（routine 不自动升格）。

## 限制

- 本机 routine：文件在磁盘即可见，无需 push；Claude Code 应用关闭时到点不跑，**下次启动应用时补跑**。
- 若日后迁移 cloud routine：只能看见已推到默认分支的文件——notes 未 push，当晚不会入账。
- 每日一次，不要加密度；不要新增第二个写入者或第二份清单。

## 首次扫描（2026-09-02 干跑，只读）

标题锚定清点 `collab/*/notes.md`、`result.md`（含变体标题）：共 55 个 PM 标题。对照 `collab/pitfalls.md` 出处列与合并映射逐一核对：

- 已入账/已映射为转载：**55/55**（20260826 notes 2、20260827 notes 30、20260902-A测 notes 8、20260902-坑台账初版 notes 2、20260826 result 2、20260827 result 11 条转载）；另有审查报告 16 条教训经行号映射入账。
- **疑似未入账：0 条。**

## Routine 创建状态

- **已创建**（2026-09-02）：本机 scheduled task `pitfalls-daily-ingest`，每日 02:08（本地时区，系统对 02:00 请求加了分钟抖动）。
- 任务定义：`~/.claude/scheduled-tasks/pitfalls-daily-ingest/SKILL.md`（prompt 即上文适配版全文）。
- 管理入口：Claude Code 侧边栏「Scheduled」区。建议首次手动点一次 **Run now** 预授权其工具，之后的自动运行不会卡在权限提示。
