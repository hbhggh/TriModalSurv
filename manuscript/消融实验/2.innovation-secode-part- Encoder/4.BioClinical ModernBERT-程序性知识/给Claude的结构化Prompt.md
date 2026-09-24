# 给 Claude 的结构化 Prompt：BioClinical ModernBERT 嵌入版（代码落地）

版本：2026-09-23。本文件是 [4.1.BioClinical ModernBERT-prompt.md](4.1.BioClinical%20ModernBERT-prompt.md) 的润色版；原文原样保留在该文件，冲突时以原文和下列用户裁决为准。本轮跳过 Gemini（构建框架）与 ChatGPT Pro（发散创新），直接进入 Claude（代码落地）。

## 目标

落地消融实验二（辅助创新点）：k1 = BioClinical ModernBERT 嵌入版替换 Text encoder。证明（NPJ 骨架 + 原型学习 + 新的辅助创新点：我们选择的新的 encoder）的实验结果大于（NPJ 骨架 + 原型学习 + NPJ 架构中文本、图像和 RNA 三个模态所使用的 encoder）。

## 背景

- 主创新点"原型检索方法（S0-force，含既有固定路由）"已在五个癌症种类中取得五分之四的胜率（四场景口径，探索性，带 LUAD 路由的 test 泄漏声明）。
- 前序三轮 AI 回答（`2.来自ai的回答/`）已把模态优先级定为 Text > RNA > WSI，并锁定 k1 为 BioClinical ModernBERT 嵌入版。选型原则：**遵循最小改动原则（不改槽；在能填这个槽的临床 encoder 里取最强冻结权重）**和改动后实验结果大概率在五个 cancer 中 c-index 上升。
- 【how to 避免信息损失】所有模型读同一份证据，不做逐级转述；下一位可以读上一位的建议，但上一位的建议不能代替原始需求和原始证据。证据真源：`1.原始发给ai的信息/`（给 ChatGPT-Pro 的结构化 Prompt、Encoder 实验先验知识-Pro 版、ChatGPT-Pro 交接包.zip）、`2.来自ai的回答/`、本目录的 `4.1.BioClinical ModernBERT-prompt.md` 与 `4.2.BioClinical ModernBERT-方案细化（Claude）.md`。
- 项目规则：AGENTS.md（停机门、GPU 合同、jobrun.sh、train_launcher.py、Git 工作流）、CLAUDE.md（节点一/节点二审查清单）、`docs/engineering/pitfalls.md`（执行前完整阅读）。

## 用户裁决（本轮）

1. 两份结果模板保留四场景结构；只有 `none` 进入 Q 判定，其余三场景作附录。
2. 填槽方案 A：token 级，截断或补齐到 200，pad 行置零（2026-09-24 Phase 0 后改定为方案 C：有效 token 均值广播到 200 行），形状 `[200,768]` 不变。
3. 同时修改 CLAUDE.md、AGENTS.md、STATUS.md：Claude Code 当指挥官并构建代码；Codex 只负责实验开始之前研究计划书的审查和实验结束之后的审查。
4. 模型 ID 锁定 `NeuML/bioclinical-modernbert-base-embeddings`（revision `048ad4491de0fb4e2695bfe4705da67caf4804b8`）。
5. 上机顺序：Phase 0 只读核验可用 exp 分支已提交版本；从 Phase 1 起先经 Codex 候选审查、squash 进 main、freeze，再同步上机。
6. 本轮改动提交到 `exp/innovation-encoder`，不 push。
7. 4×5 表中「其他方法的 Encoder」只是占位，具体的 encoder 算法还没有确定。
8. 原话照录："BioClinical ModernBERT的实验种子必须是123、132、213、231、321"。
9. 原话照录："必须使用GPU运行，不可以使用CPU运行实验，并且在landau，tako的四个云端服务器中，优先找服务器中空缺的显卡，然后如果没有空缺的显卡正在使用的GPU使用量在70%以下，也可以在此GPU上跑实验"。
10. 原话照录："对于代码开发并不是由codex去执行，还是由ous5.5去执行代码开发，codex只负责对于生成的计划书进行review和对实验结果进行一个review，不参与任何代码生成的工作，只是用来审核"。即代码开发由 Claude Code（Claude Opus 5.5）执行，Codex 只审核，不参与任何代码生成。

## 具体步骤

1. 完整阅读坑台账；核对推理器、发车器、数据集与检索库的真实代码，确认 Text 槽位与冻结方法可以原样复用。
2. 写先验知识 `innovation-BioClinical ModernBERT.md`：原文照录背景、Trigger、Q_draft、不可变约束，再给 S_state（已证实的事实 / 未核验的假设 / 已经失败的尝试）、Q_specific 与用户裁决，且不改 T/Q。
3. 写研究计划书：必须包含实验的整体实现顺序和逻辑链条（mermaid），以及创新点在整个网络中的位置（mermaid）。
4. 建 I05 代码：冻结编码器、特征提取、模型配置、训练清单、冻结方法推理器、GPU 规则与选卡工具、结果渲染、发车契约核对，以及测试。
5. 参考 I01 4.progress 的 `癌症为单位.md` 与 `seed单位-实验结果.md`，用脚本在本目录生成 `seed单位-实验结果.md` 与 `癌症为单位.md`：现有系统列填真值，新 encoder 列写"未实验"；结论判断哪一种 seed、哪一种癌症效果最好。
6. 修改 CLAUDE.md、AGENTS.md、STATUS.md 的分工与 I05 登记。
7. 本地验证、提交，准备 Codex 候选审查包；然后停下，不上机。

## 涉及文件

- 本目录：`给Claude的结构化Prompt.md`、`innovation-BioClinical ModernBERT.md`、`研究计划书-BioClinical ModernBERT.md`、`seed单位-实验结果.md`、`癌症为单位.md`、`encoder-table.md`。
- `experiments/I05_text_encoder_bcmbert/`：代码、配置、清单、测试与索引。
- `CLAUDE.md`、`AGENTS.md`、`STATUS.md`、`experiments/README.md`、`pyproject.toml`（测试路径）、`docs/engineering/pitfalls.md`（新坑入账）。

## 约束

- 不可变约束 1–4 原文照录（见先验知识第 1 节）；none 为历史 none，保留天然缺失；对照是 Table 1 的 None / Proto.†。
- 证明新 encoder 的实验表格设计必须严格参考上传的文件、文件夹和 zip：行为 MLP / 原论文的 Encoder / 其他方法的 Encoder / 我们提出来的 Encoder，列为 LGG / BRCA / BLCA / LUAD / UCEC。
- 基于 `exp/innovation-encoder` 分支开发，不可污染 main 分支。
- 不改 NPJ-C、原型检索方法、训练超参与 I01 代码；不上服务器、不下载权重、不训练评测。
- 实验只在 GPU 上运行；种子固定为 123、132、213、231、321。

## 预期结果

- 五份文档齐备，数值全部由脚本从原始 JSON 生成，并与 Table 1 逐位相同。
- I05 代码通过本地测试；发车 dry-run 与既有 e0 臂只差特征配置与结果目录两项。
- 三份规则文件记录新分工；改动提交到 `exp/innovation-encoder`。
- 给出可直接运行的 Codex 候选审查命令，由用户发起审查。
