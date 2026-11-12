# Step 2 — Search and Deduplicate
- 时间：2026-11-11
- 检索工具：paper_search 的 search_papers()（researchstudio 环境）+ Consensus MCP（替补 Semantic Scholar）
- 年份：2019–2026

## 查询
| 编号 | 类型 | 查询 | 结果 |
|---|---|---|---|
| Q1 | 原问题 | missing modality multimodal survival prediction pathology genomics | S2 10 / OpenAlex 10 / arXiv 10 / Crossref 10；DBLP 解析失败、OpenReview 0 |
| Q2 | 宽领域 | incomplete multimodal learning missing modality imputation | S2 两次 429 失败；OpenAlex 10 / arXiv 10 / Crossref 10 |
| Q3 | 方法签名（B6） | nearest neighbor residual retrieval missing modality reconstruction | S2 429；OpenAlex 10 / arXiv 10 / Crossref 10（噪声大） |
| Q4 | 补充（B6 检索） | similar patients retrieval missing modality imputation multimodal | OpenAlex 10 / arXiv 10 |
| Q5 | 补充（A1 子空间） | shared specific subspace missing modality survival analysis | OpenAlex 10 / arXiv 10 |
| C1 | Consensus 替补 | missing modality cancer survival prediction histopathology genomics retrieval of similar patients imputation | 20 |
| C2 | Consensus 替补 | post-hoc missing modality completion frozen multimodal model low-rank shared subspace | 20 |

去重（标题小写、空白归一）：paper_search 117 篇；Consensus 新增约 25 篇（与前者重叠：MUST、M2Surv、LD-CVAE、Survival of Brain Cancer、Cross-modal alignment、Interpretable bridged、NSCLC 等）。
原始 JSON：scratchpad q1–q5.json、merged.json（不入库）。

## 记忆召回（Source: model-recall，Step 5 前未核实）
- HEALNet: Multimodal Fusion for Heterogeneous Biomedical Data（Hemker et al., NeurIPS 2024）——跳过式融合处理缺失。
- PORPOISE / Pan-cancer integrative histology-genomic analysis（Chen et al., Cancer Cell 2022）——多模态生存基线。
- 回归诊断教材中的 PRESS / 留一残差 e_i/(1−h_ii)（经典统计方法，非某篇论文）。
- kNN 残差校正 / 混合参数-非参数回归（经典思路，无单篇代表）。
