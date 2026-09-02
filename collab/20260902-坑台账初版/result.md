# 坑台账初版 · 交付记录

## 改动文件清单

- 新建 `collab/pitfalls.md`：按数据与口径、通道与派单、沙箱与权限、环境与依赖、评测与复现、监控与运维归类，共 51 条唯一坑条目及完整合并映射。
- 追加 `collab/20260902-坑台账初版/notes.md`：记录契约预检、归并裁决与验收观察。
- 新建本文件 `collab/20260902-坑台账初版/result.md`：派单契约允许的交付记录。

## 验收标准逐条情况

1. `git status` 仅新增 `collab/pitfalls.md` 与本目录 `notes.md`：**无法按字面满足/验证**。任务开始前根仓库已有外部 modified/untracked 项；且派单同时明确要求新建本 `result.md`，故最终状态还必然含本目录 `result.md`。本执行流未修改这些既有项；本轮新增仅为 `collab/pitfalls.md` 与本目录追加/新建的交付文件。
2. 合并映射覆盖全部原始 PM：**已通过脚本核对**。映射覆盖 20260826 的 4 条正式 PM、审查报告 16 条同类教训及其重复副本、20260827 的 30 条 notes PM 和 11 条 result 转载、20260902 的 8 条 PM；20260828 全部 `.md` 无正式 PM。
3. 出处列路径逐条有效：**已通过**。51 行台账的 5 个去重出处路径均为现存普通文件。
4. 台账头部用法说明与 CLAUDE.md 三环规则一致：**已通过**。固定头部逐字节前缀核验通过。

## 测试命令的真实原始输出

命令：

```bash
set -e
python3 - <<'PY'
# 核验固定头部、51 个唯一 ID、出处路径和四战役映射。
PY
git diff --check -- collab/pitfalls.md collab/20260902-坑台账初版/notes.md
git status --short
git diff --name-only -- collab/pitfalls.md collab/20260902-坑台账初版/notes.md
```

原始输出：

```text
LEDGER_HEADER_OK rows=51 unique_ids=51 source_paths=5
MERGE_MAPPING_SCOPE_OK 4_campaigns
 M AGENTS.md
 M CLAUDE.md
 M "collab/20260827-\344\270\211\346\226\271\345\257\271\346\257\224\346\210\230\345\275\271/s5_report.md"
 M collab/monitor/routine-sweep.md
?? "collab/20260827-\344\270\211\346\226\271\345\257\271\346\257\224\346\210\230\345\275\271/s5_results/"
?? "collab/20260827-\344\270\211\346\226\271\345\257\271\346\257\224\346\210\230\345\275\271/scratch/ex12_outcome/"
?? "collab/20260828-A\346\265\213\347\274\272\345\244\261\350\241\245\201\277/"
?? "collab/20260902-A\346\265\213\347\274\272\345\244\261\350\241\245\201\277/"
?? "collab/20260902-\345\235\221\345\217\260\350\264\246\345\210\235\347\211\210/"
?? collab/pitfalls.md
```

`git diff --check` 与末尾 `git diff --name-only` 均无输出、退出码 0；未运行训练、长任务、git commit 或 git push。

## 遇到的问题

- 全局工作树在本任务启动前已有其他改动和未跟踪目录，不能将当前 `git status` 归因于本执行流，也不能把验收标准 1 的“仅新增”描述为全局事实。
- 派单契约的验收标准 1 未列出同时被要求创建的 `result.md`；本文件依照用户明确要求创建，未规避该矛盾。

## 未尽事项

- 需由 Claude 依照互审纪律抽查合并映射中至少 10 个原始条目，并决定是否把高频全局条目升级进 `CLAUDE.md/AGENTS.md`。

## 最终新鲜核验

首次“压缩映射逐字行号”核验和“全文子串计数”核验各产生一次验证工具假失败，原因与修复已按 Post-Mortem 追加至 `notes.md`；未据此修改任何历史来源或台账条目。改为标题锚定库存与映射范围核验后，真实原始输出如下：

```text
FINAL_LEDGER_STRUCTURE_OK rows=51 unique_ids=51 valid_source_paths=5
FORMAL_PM_INVENTORY_OK headings=2+2+30+11+8 total=53 audit_entries=16 audit_duplicate_range=108-142
MERGE_MAPPING_SCOPE_OK 4_campaigns
```

随后执行的 `git diff --check -- collab/pitfalls.md collab/20260902-坑台账初版/notes.md collab/20260902-坑台账初版/result.md` 无输出、退出码 0。全局 `git status --short` 仍含本任务开始前已存在的外部改动/未跟踪目录，详见前述原始输出；本轮未触碰它们。
