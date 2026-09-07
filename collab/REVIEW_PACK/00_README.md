# 00. 给 ChatGPT 的阅读地图（REVIEW_PACK）

## 本仓库是什么、不是什么

- 这是 **TriModalSurv 的工作快照**（2026-09-07；2026-09-06 版基础上并入 NPJ-D 底座 25-seed 战役），仓库仍在重构中；**不是最终给审稿人的仓库，不是 SOTA 声明，是待审的实验记录**。
- 目的：让外部审阅者（网页 ChatGPT）基于**完整的思考链与证据**做文献/事实查核。因此仓库有意保留了全部阶段性文件：计划、过程笔记（含 Post-Mortem）、Codex 交付记录、审查报告、被废弃的草案、报告的历史版本（r3）、训练/评测日志、两个写码引擎的并行交付副本、坑台账。
- 结果按报告原文如实呈现，既不美化也不贬低：三方对比里骨架在 LGG/UCEC 全败是真不理想；拆 gate 对 S5 是正向（20:4:1）；CAP-Recall 强烈癌种依赖（UCEC 全胜、BLCA/BRCA 全负）。详见 `04`。

## 阅读顺序（写死）

1. `collab/REVIEW_PACK/04_honest_conclusions.md` — 能下 / 不能下的结论、实现债、不理想的候选原因。
2. `collab/REVIEW_PACK/03_results.md` — 逐表原文抄录（机械抽取），含来源标注。
3. `collab/REVIEW_PACK/01_research_idea.md` — 研究问题、"计划中的创新" vs "代码里真做了的"、主线改向史。
4. `collab/REVIEW_PACK/02_method_and_code_map.md` — 数据流、插入点、`文件:行`、配置生效表、死代码原文。
5. `collab/20260902-A测缺失补偿/a_test_report.md` — 创新臂判定报告 r6（r4 经 decision-reviewer 四轮；r5 新增二 c 节 E0m 同底座判别；**r6 新增二 d 节 NPJ-D 底座 25-seed 系统级对比 + 填充护栏**，预注册规则；修订记录在文末）。
6. `collab/20260906-NPJ-D消融/` — NPJ-D 战役全过程：`plan.md`（Opus 契约）、`notes.md`（裁决、复核、冒烟、发车、对抗审查核实、异常 seed 裁决）、`smoke/`、`审查/adversarial-review-findings.md`、`results_npjd_d0/`（125）、`results_npjd_dm/`（125）、`results_npjc_e1_25/`（100）、`table_npjd_*.md`、`r6_numbers.txt`。
6. 按需下钻：`collab/20260827-三方对比战役/s5_report.md`（三方对比）→ `code/NPJ/`（代码）→ 各战役 `plan/notes/result.md`（过程）→ `collab/pitfalls.md`（坑台账）。

盘点原件：`collab/REVIEW_PACK/A_inventory.md`。数字对账：`collab/REVIEW_PACK/check_numbers.txt`（由 `check_numbers.py` 生成）。

## 完整思考链导航（按时间）

| 时间 | 目录 | 看什么 |
|---|---|---|
| 2026-08-26 | `collab/20260826-NPJ三模态复现/` | `HANDOFF.md`（数据/管线交接书，阶段 0→1→2）；`审查/codex-对抗审查报告-20260826.md`（首轮对抗审查，发现 A 口径 c-index、mask 键不匹配、MoE 未参与等问题）；`result.md` |
| 2026-08-27～09-02 | `collab/20260827-三方对比战役/` | `plan.md`（三方对比契约）；`notes.md`（77KB 过程：12 例剔除裁决、claim 锁坑、评估器部署坑、批量化为负优化、Post-Mortem）；`result.md`（Codex 交付记录 107KB）；**`s5_report.md`**（判定报告 r2+r3）；`s4/`、`adapters/`、`*_patch.diff` |
| 2026-08-28 | `collab/20260828-A测缺失补偿/` | **已废弃**的 A 测第一版契约（以 NPJ-A 锚定；为何废弃见首行与 20260902 战役 notes） |
| 2026-09-02～09-04 | `collab/20260902-A测缺失补偿/` | `plan.md`（α/β/γ/δ/ε 五单契约 + 口径裁定）；`notes.md`（75KB：gate 探针→拆 gate 改向、评测提速、launcher 首秀、指挥官三段目标漂移 Post-Mortem、reviewer 四轮）；`result.md`；`a_test_report_r3.md`→`a_test_report.md`（r4）；`ab_first_task.md`（Opus vs Codex 写码引擎 A/B，含 Codex 作业静默死亡记录）；`notes_eps_{opus,codex}.md`、`tools_codex/`、`figures_codex/`（并行交付原件） |
| 2026-09-06～09-07 | `collab/20260906-NPJ-D消融/` | NPJ-D（NPJ-A 去 GatedFusion）作 E0 的 25-seed 战役：`plan.md`（Opus 派单契约）；`notes.md`（用户裁决序列、指挥官异议留档、约束二次审核、Opus 交付复核、冒烟、d0/e1/Dm 三阶段发车与监视、对抗审查逐条核实、BLCA 异常 seed 裁决）；`审查/`（Codex adversarial-review 原始 JSON + 核实报告）；`smoke/`；三套结果目录；`r6_numbers.txt` |
| 2026-09-02 | `collab/20260902-NPJ-GPU合同/` | GPU 利用率合同、配置驱动改造、发车门禁；`plan-r2.md` |
| 2026-09-02 | `collab/20260902-坑台账初版/`、`collab/pitfalls.md` | 90 条坑与 Prevention Rule（数据口径 / 通道 / 沙箱 / 环境 / 评测 / 运维） |
| 持续 | `collab/monitor/` | 巡检脚本与流水（`routine-sweep.md`） |
| 规则 | `AGENTS.md`、`CLAUDE.md` | 停机门、GPU 合同、互审纪律（解释为什么很多实验"跑完即停" |

## 仓库拓扑

- `code/NPJ/`：主实验代码**快照**（NPJ 上游 `4a3d95e` + 本地改动 + 新文件），对上游 patch 见 `code/NPJ_changes_vs_upstream.patch`，来源说明 `code/NPJ_SNAPSHOT.md`。本地 `NPJ/` 目录为嵌套 git 克隆，被忽略。
- 基线 MCAT / PORPOISE：**不在仓库内**（官方克隆 1.5GB），我方改动 = `collab/20260827-三方对比战役/{mcat_patch.diff,porpoise_patch.diff}`（基点 `b9cca63` / `3390dc4`）；复现三行见 `02`。
- 结果：`collab/20260827-三方对比战役/s5_results/`（baseline 冻结评测 51 json）；`collab/20260902-A测缺失补偿/results_*/`（创新臂 250 json，含 `results_npjc_e0m/`）+ `table_*.md` + `r*_numbers.txt` + `figures/`；`collab/20260906-NPJ-D消融/results_npjd_d0|results_npjd_dm|results_npjc_e1_25/`（350 json + 训练/评测 log）+ `table_npjd_*.md` + `r6_numbers.txt`。
- 环境：`code/NPJ/tcga.yaml`。

## 口径速查

- 骨架 c-index 双口径：A = 作者 raw logits 累积（训练与 ckpt 选择用它）；B = sigmoid 修正（报告主口径）。baseline 单一 sksurv 读数。
- 判定：逐 seed 严格 `>`（胜:负:平，|Δ|≤1e-6 记平）+ 配对Δ中位；|Δ中位|<0.02 噪声带；无统计推断。NPJ-D 线 25 seed（原 5 + 1..20），同 seed 为协议配对而非初始化配对（坑 V32）。
- 缺失：测试期固定 manifest（SHA `c789eae9…`）；`none` = 完整模态；`both_100` = RNA 与文本全缺，只剩 WSI。E0/E0d 在 both_100 是"不填充"（mask），E1 是"召回"。

## 未上传的内容与原因

| 内容 | 原因 |
|---|---|
| NPJ 训练 ckpt（`out*/`，landau） | 权重体积大，且不是审阅对象 |
| UNI2-h / BulkRNABert / 文本嵌入特征、原始 WSI/RNA | 大数据；TCGA 公开数据派生 |
| 基线整仓（含上游 .git 700MB、ckpt、dataset_csv） | 第三方公开仓，只留 patch |
| `scratch/` 里的 TCGA 派生 `csv.zip`（含 118MB `ex12_outcome/`）、GDC 原始 `.tsv`、合成评测 `.pt`、GPL vendor 二进制、`.pyc` 快照 | 数据/二进制，无思考内容；**git 历史里仍有早期提交过的部分（~230MB），未重写历史** |
| 并行评测 shell（`run_eval_parallel.sh` 等） | 只在 landau，未回收进仓 |

**已上传**：全部 plan / notes / result / 审查 / 废弃草案 / 报告历史版本 / reviewer 修订记录 / 训练与评测 `.log` / A·B 双引擎副本 / 坑台账 / split 表 / 结果 json。

## 数据与许可

- `collab/20260827-三方对比战役/labels_424*.csv` 含 TCGA 去标识 barcode 与生存标签（公开数据派生）。
- `code/NPJ/` 沿用上游 Apache-2.0；本仓库其余内容未声明许可（私有仓，待作者决定）。
