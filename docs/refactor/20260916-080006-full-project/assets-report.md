# 资料逐文件映射与集成交接

[确定] 仅生成清单和复制工具，未执行资料复制、旧目录移动、旧 Markdown 改写或根导航更新。

## 产物与核验

- `assets-map.json`：14,189 条文件处理记录（同一来源有原件保全与使用副本两条时分别登记）；5,671 条独占复制、6,834 条由主事务归档、1,684 条原位保留。每项含来源、目标、SHA-256、文件大小、理由和操作 ID。
- `build_assets_map.py`：从 T0 的 `files.jsonl` 与 `f2e2358` Git blob 生成清单，只写新清单。目标按 NFC + casefold 全量检查，无目标碰撞。
- `copy_assets.py`：默认 dry-run；只有 `--apply` 才复制 `execute_copy=true` 条目，不执行 `archive_by_parent`。每次写出记录 planned → done → verified 并 fsync；已存在但没有本批次日志的目标直接拒绝。重入核验来源与目标 SHA-256；半写目标停止，不自行覆盖。
- `test_copy_assets.py`：在系统临时夹具实测独占冲突拒绝、半写拒绝、重入 hash 核验、逆向隔离，四项 PASS。
- `python3 .../copy_assets.py`：实跑 dry-run，5,671 个来源 hash 均通过，目标未存在。该证据不是“迁移完成”。
- 复制回滚用 `--rollback`，只把本批次 hash 一致的新副本移到 `archive/runtime_artifacts/assets-copy-rollback/`；源始终保留。旧目录 rename 与其回滚由主事务负责。中断在回滚 rename 与日志之间时需主事务检查隔离位置，不自动猜测。

## 分类依据

| 来源 | 使用位置 | 原件位置/说明 |
|---|---|---|
| root `collab/` 全量（含缓存） | 正式比较另外复制 | `archive/legacy_collab/`，主事务最终整体 rename |
| root S5 结果 51 文件与 `s5_report.md` | `experiments/_comparisons/legacy-s5-20260827/raw/` | 保留三基线身份，不拆成创新结果 |
| root 20260902 缺失补偿 | `experiments/_comparisons/legacy-missing-compensation-20260902/raw/` | 混合 gate/C/E0/E1/E0d 归跨臂比较，禁止只按 JSON arm 判实验身份 |
| 774f 固定患者检索批次 | I01 已有 results 保持；完整源另归档 | `archive/legacy_collab/source-774f/` |
| 684e 人群原型批次 | I02 已有 results 保持；完整源另归档 | `archive/legacy_collab/source-684e/` |
| 2af8 D/Dm/旧 E1 整批 | `I03_npj_d_dm_e1/results/legacy-r6-20260906/raw/` | 完整原批次另存 `archive/legacy_collab/source-2af8/`；r6 所需旧 C/S5 同源参照复制为相邻批次 |
| f2e2358 CAP4 批次 | `I04_cap4_multi_prototypes/results/legacy-cap4-20260907/raw/` | 原提交 `f2e2358db706127862631b3dd577d9f9c2a6b239`，实测 **44 文件**；既有 D 版/冒烟，不能写成正式效果结论 |
| `innovation- computation/1-M³Surv｜患者级配对检索-code/` | I01 `knowledge/legacy-source/` | 原件 `archive/legacy_docs/` |
| `innovation- computation/E1-M³Surv｜人群配对原型 -PAPER/` | I02 `knowledge/legacy-source/` | 按目录内容归人群原型；其中文件名虽然含“患者”，不归 I01 |
| Transformer 提议 | `docs/research-ideas/` | 未分配新实验 ID |
| VS Code/日语/Office 说明 | `docs/workflow/`、`docs/workflow/office-viewer/` | 只准备逐字复制 |
| `exam.docx`、`diagrams/111.excalidraw.svg` | `docs/workflow/fixtures/` | 测试夹具 |
| `diagrams/222.excalidraw.svg` | I01 `knowledge/legacy-source/` | 检索草图，SVG 字节保留 |
| `image/STATUS/` | `docs/assets/status/` | STATUS 附件 |
| `NPJ-A&NPJ-B区别.md` | `docs/metrics/` | 共享指标口径 |
| `论文初版本.docx`、`manuscript/bbag124_word/` | `manuscript/references/bbag124/` | 他人论文还原稿及副本，不标自有初稿 |
| 空 `paper.tex` | `archive/legacy_docs/paper.tex` | 0 字节，不能视为有效论文源 |

## 五组复算可用来源

统一冻结来源根：`/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006/`。下列是已找到的输入与脚本，**本子任务没有执行历史复算**。

| 组 | 原始输入 | 可用脚本/原报告 | 边界 |
|---|---|---|---|
| S5 三基线表 | `root/collab/20260827-三方对比战役/s5_results/`；`root/collab/20260902-A测缺失补偿/s5_full_reference.csv` | `s5_report.md`；需验证组按 CSV/JSON 重聚合 | 三方法×五癌×五种子，原报告统计口径须独立核对 |
| 20260902 跨臂 | `root/collab/20260902-A测缺失补偿/results_gate/`、`results_npjc/`、`results_npjc_both/`、`results_npjc_e0d/` | `tools/summarize_arms.py`、`tools/r4_numbers.py`、`tools/check_r4_numbers.py` | 显式 `--arm` 映射；`tie-eps`/`legacy-winloss` 不能默认混用；E0m 是外部历史追加 |
| I01 固定患者检索 | 现有 `experiments/I01_patient_retrieval/results/legacy-tako-formal-20260915/raw/tako-formal/evidence/formal/` | 冻结 774f `NPJ/scripts/summarize_patient_retrieval.py`；同批 `evidence/summary/{summary.json,per_cell.csv,paired_deltas.csv}` | 使用原 25 seeds/缺失格点集合，禁止把本次 32 患者 CPU 对拍当全量汇总 |
| I02 K8 历史比较 | `684e/collab/20260915-population-prototypes/results-summary/evidence/population/`；**684e** `collab/20260902-A测缺失补偿/{results_npjc/e0,results_npjc_both/e0,results_npjc_e0m}/` | `684e/.../results-summary/summarize.py`、`metrics_long.csv`、`summary_mean_sd.csv`、`historical_deltas.csv` | 脚本会写 HERE，必须在隔离新批次运行；根 root 没有 E0m，不能代用；脚本按同 manifest 校验 |
| I03 r6 | `2af8/collab/20260906-NPJ-D消融/{results_npjd_d0,results_npjd_dm,results_npjc_e1_25}/` 及相邻 `20260902` 的旧 E0/E1/S5 | `tools/r6_numbers.py`、`tools/abs_table.py`、`r6_numbers.txt`、`table_npjd_D_Dm_E1_absolute_25seed.md` | r6 脚本按 `HERE.parent` 读相邻批次；同源结构已列入复制。1500 原始读数/60 均值须由验证组按原指标维度核算，不能以文件数代替 |

## 使用版与主事务衔接

1. 原件只按字节复制/归档；当前清单不改任何 Markdown 正文、JSON 历史字段、旧日志、hash 文档或 SVG。
2. 知识 `legacy-source/` 附件保持内部相对结构，因此其本地图片相对链接天然保持。跨目录代码定位需在活动新索引补当前代码链接；SVG 可见旧路径不动。
3. Markdown 使用版如果进行链接修复，必须基于本清单的“source_path → target”映射，另外写逐链接变更记录并更新使用版后 hash；原件 hash 仍按本清单验收。本脚本不能在那之后重复要求“使用版仍等于原件”而覆盖它。
4. I01/I02 已有结果和 I01 现有 Markdown 均未改。本子任务不生成新的实验 run，不补写未知历史 effective 配置。
5. 新 I03/I04 results 索引与新 analysis 由负责实验骨架的主 Agent/执行 Agent 引用上述真实历史批次；本子任务不写它们以避免同文件争用。
6. 这是资料子清单；自有源码、NPJ/code 下资料、嵌套仓库、Git 元数据、根 README/STATUS/AGENTS/CLAUDE 的全量覆盖仍需主清单合并，不能将 14,189 条操作数误作 T0 全量文件分母。
