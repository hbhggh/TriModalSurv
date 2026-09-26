# I06：LLM 浓缩病理报告（A1 / A2，Text 表征创新）

**问题**：在 NPJ-C + 原型检索（论文 Table 1 基线系统）上，只把 Text 输入换成「LLM 浓缩 → 冻结公开 encoder」管线，四个候选（NeuML / Qwen3-Embedding × 结构化 / 摘要）中是否有候选的 Overall（四场景等权平均，照论文 Table 1）对 Table 1 Proto. 列严格胜 ≥4/5。

**研究计划书**：[研究计划书-A1-LLM浓缩.md](../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/6.LLM浓缩-A1/研究计划书-A1-LLM浓缩.md)（v3.3）。

**分工**：代码开发由 Claude Code 执行；Codex 只审核计划书与实验结果。

## 文件

| 文件 | 作用 |
|---|---|
| `model.py` | 核心算子：字段清单与顺序、结构化 schema、序列化（省略 not mentioned）、prompt 读取与请求构造（查找 `# [创新 I06-01]`） |
| `prompts/` | prompt 原文；freeze manifest 记录各文件 sha256 |
| `export_texts.py` | 从标签 CSV 导出纯文本清单（5 列），逐人对齐 B1 manifest；浓缩与核验只读这份清单 |
| `config.yaml` | 候选与档案、锁定的 B1 manifest 与标签哈希、LLM 参数、长度与退回上限、质量检查参数、Table 1 Overall |

特征提取、训练与评测复用 I05（新增 `a1struct` / `a1summ` / `a2struct` / `a2summ` 四个档案）。
