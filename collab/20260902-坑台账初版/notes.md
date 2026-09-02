# 坑台账初版 · 过程档案（append-only）

## 派单留档（Claude，2026-09-02）

- jobId: `task-mtjdvh0t-rsccfp`
- 完整派单命令：

```
node /Users/wuhao/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs task --write --background --cwd /Users/wuhao/Desktop/TriModalSurv --model gpt-5.6-terra --effort high "读取并严格执行 collab/20260902-坑台账初版/plan.md 的派单契约：提炼四个战役目录的全部历史 Post-Mortem，生成集中坑台账 collab/pitfalls.md。白名单：只允许新建 collab/pitfalls.md，以及写本任务目录的 notes.md 与 result.md。禁止修改任何既有文件、禁止 git commit/push、禁止启动训练或长任务。执行前先读 plan.md 的「相关坑」节并遵守。完成后写 collab/20260902-坑台账初版/result.md。"
```

- 档位依据（CLAUDE.md 新派单矩阵）：文本归纳提炼、归类判断质量要求高 → `gpt-5.6-terra` + `--effort high`；写任务首启 `--write`；预计 >10 分钟 → `--background`。
- 本单是新派单矩阵（显式 model/effort + 后台化 + 命令留档）的端到端首测。

## 2026-09-02 09:55:44 JST — 契约预检与提取启动（Codex）

- 已完整读取 `plan.md`，并先执行“相关坑”节：仅在白名单中写入；不将通道状态视作任务死亡；所有交付断言附真实命令输出。
- 已确认 `collab/pitfalls.md` 与本目录 `result.md` 尚不存在；本目录 `notes.md` 已存在，后续只追加。
- 已记录开始时根仓库存在与本任务无关的既有改动/未跟踪项（含 `AGENTS.md`、`CLAUDE.md`、`s5_report.md`、`routine-sweep.md`、既有 `s5_results/`、`scratch/ex12_outcome/`、两个 A 测目录和本任务目录）；不触碰、不归因于本单。
- 提取范围严格限定为派单契约列出的四组来源。为避免漏条，三个只读提取流分别核对 20260826、20260827、两组 A 测；主执行流保留 `collab/pitfalls.md`、本 `notes.md` 与 `result.md` 的唯一写入权。

## 2026-09-02 10:00 JST — 归并裁决与首次验收（Codex）

- Ruling：`20260827-三方对比战役/result.md` 的 11 条 PM 全部是 `notes.md` 已有条目的转载，按契约只以 notes 为出处入账；映射逐条标注 result 行号，不重复建账。
- Ruling：`20260828-A测缺失补偿/` 全部 Markdown 已扫描但没有正式 Post-Mortem；其计划性/背景性教训不越权补写成“原始 PM”。
- Ruling：20260826 审查报告的 P0/P1/P2 属契约明确要求纳入的非 PM 同类教训；报告中第二份逐字重复副本不重复建账，在合并映射中显式覆盖。
- 已新建 `collab/pitfalls.md`，共 51 个唯一 ID；首次只读验收输出为 `LEDGER_HEADER_OK rows=51 unique_ids=51 source_paths=5` 和 `MERGE_MAPPING_SCOPE_OK 4_campaigns`；`git diff --check -- collab/pitfalls.md collab/20260902-坑台账初版/notes.md` 无输出、退出 0。
- 发现验收标准 1 的字面 `git status` 在本任务开始前已有外部改动/未跟踪目录，且本派单又要求新建 `result.md`，因此无法把全局 dirty tree 说成“仅新增 pitfalls.md 与 notes.md”；该限制将在 result.md 如实报告。

### Bug Post-Mortem（最终映射核验脚本假失败，2026-09-02 09:59:39 JST）

- **现象**: 最终映射核验脚本报 `审查映射缺行号 110`，但台账已将审查报告的逐字重复副本以 `108–142` 范围明确映射。
- **根因**: 验证脚本把“范围覆盖”错误实现为“每一个中间行号字面出现”的断言，产生了验证工具假阴性。
- **修复**: 改为同时核对首份 16 条原始教训的精确行号列表、重复副本的完整范围标记及其顺序对应关系。
- **Prevention Rule**: 验证映射压缩表示时，断言必须匹配其声明的表示语义；不得把范围标记按逐整数文本误检。

### Bug Post-Mortem（PM 清点全文子串误计，2026-09-02 10:00:54 JST）

- **现象**: 首版来源清点把 `result.md` 的“问题与 Post-Mortem”说明行和“完整 Post-Mortem 已追加”等正文提及误算为 PM 标题，得到 31/14/9 而非 30/11/8。
- **根因**: 清点逻辑使用全文 `Post-Mortem` 子串，而非锚定 Markdown 标题结构。
- **修复**: 改为仅匹配 `^#{3,6}.*Bug Post-Mortem`，并对 20260902 的“最终审计工具封装 Post-Mortem”保留明确特例。
- **Prevention Rule**: 结构化文档库存必须使用标题锚定模式；正文引用、目录标题和交付摘要不得计为原始复盘条目。

## 2026-09-02 10:01:30 JST — 最终新鲜核验（Codex）

- 最终核验通过：`FINAL_LEDGER_STRUCTURE_OK rows=51 unique_ids=51 valid_source_paths=5`；正式 PM 标题库存为 `2+2+30+11+8=53`，审查报告首份 16 条同类教训及其 `108–142` 重复副本均在合并映射范围中说明。
- `git diff --check -- collab/pitfalls.md collab/20260902-坑台账初版/notes.md collab/20260902-坑台账初版/result.md` 无输出、退出 0。
- 本轮停止：未运行训练或长任务，未执行 git commit/push；交回 Claude 按契约抽查合并映射。
