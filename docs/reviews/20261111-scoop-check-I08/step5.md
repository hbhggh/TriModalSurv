# Step 5 — Full-Paper Deep Dive
- 时间：2026-11-11
- 全文来源：arXiv PDF 经 fetch_paper.sh 抽取（存 scratchpad，不入库）。C-MAMs 未找到开放全文，只读摘要。

## 1. MUST（Kim & Hwang, arXiv 2603.26071, 2026-03，预印本）
- Problem (verified)：TCGA BLCA/BRCA/GBMLGG/LUAD/UCEC，WSI + 分子（RNA/CNV/SNV 按 6 功能组），5 折，C-index；缺失 = 测试时整模态缺（缺病理或缺基因组），双模态。
- Mechanism (verified)：端到端训练；可学习低秩投影 P∩ = B∩B∩ᵀ（B∩ ∈ R^{D×r}，D=256，r=64）；每模态表示分解 g = û（特异）+ ĉ（跨模态上下文）；损失 L_decomp + L_shared（ĉ_{P←G} 与 ĉ_{G←P} 一致）+ L_orth（余弦软正交）；推理时由可见模态确定性得到共享分量 c̃ = g − (I−P∩)u（式 20），缺失模态的特异分量用条件潜扩散模型生成（式 21），风险 = φ([û; c̃; ũ])。
- Insight (verified)："shared components are deterministically derivable from any available modality"；只把随机生成留给特异残差。
- Venue：arXiv 预印本。
- 与我方：A1/C1 轴高度同构（低秩共享子空间、同为 256 维、正交约束、共享一致性）；**相反的选择**：MUST 生成特异部分，我方截断不恢复；MUST 无检索、无冻结骨架后挂、无三模态六模式。
- Refined overlap：P 匹配（核心框架同为 TCGA 测试期整模态缺失生存预测；双模态、端到端训练而非冻结后挂属细节差别，写入 delta）/ M 部分（A1+C1 匹配，B6 不同）/ I 匹配 / D 匹配。

## 2. PRIME（Yu et al., arXiv 2604.04999, 2026-04，预印本）
- Problem (verified)：TCGA 32 癌自监督预训练 + 5 队列下游 5 折；WSI + RNA + 病理报告（与我方同三模态）；冻结单模态编码器；任意模态子集。
- Mechanism (verified)：共享原型记忆库（可学习 token 序列码本）；对每个可见模态算原型软分配，按可见模态取平均得患者级共识分布 q̄（式 5）；缺失模态 = Σ q̄_k C_k（式 6）+ 模态特异 Transformer 精修；预训练目标：融合前跨模态 InfoNCE 对齐 + 结构化缺失增广下的融合后一致性 + MoE 路由正则。
- Insight (verified)：潜空间语义补全，不重建原始信号，避免幻觉；Related Work 明说检索/记忆类方法"depends on reference-set coverage and similarity metric stability"（引 M2Surv）。
- Venue：arXiv 预印本（我方外部基线，原文 0.653）。
- 与我方：C1 轴（对齐 + 一致性）与"按可见模态聚合相似度"两处相近；PRIME 是预训练框架、原型是学出来的码本，不检索训练患者、无线性基座/残差/留一。
- Refined overlap：P 部分 / M 部分 / I 部分 / D 匹配。

## 3. M2Surv（Qu et al., arXiv 2506.19324 / MICCAI 2025）；期刊扩展版 M3Surv（MedIA 2025, 10.1016/j.media.2025.103846，未读全文，只读摘要）
- Problem (verified)：TCGA 五癌 FFPE+FF 多切片 + 基因组，推理时整模态缺失。
- Mechanism (verified, §2.4)：训练期把成对病理-基因组特征以动量更新存入记忆库；推理缺模态时用可见模态与库内条目算余弦，取 top-µ 后按 softmax(相似度) 加权**直接聚合库内缺失模态特征**（式 5）；µ=1 最好。M3Surv 摘要改为"prototype-based memory bank … impute information from the most similar prototype"。
- Insight：用训练患者的历史成对特征补缺；作者自述局限"retrieval efficacy of memory banks depends on the coverage of training data"。
- 与我方：B6 的"按可见模态余弦检索相似训练患者"同类；差别在我方检索的是线性基座 B1 的**留一去偏预测残差**而非特征本身，并有密度门控回退到 B1。我方 M3（A1+B3+C1，B3 = 直接邻居特征聚合、无线性项）正是这一做法的同口径对照。
- Refined overlap：P 匹配 / M 部分 / I 部分 / D 匹配。

## 4. M3Care（Zhang et al., KDD 2022, arXiv 2210.17292）
- Problem (verified)：多模态 EHR，训练/测试都可能整模态缺失；临床预测任务。
- Mechanism (verified, 摘要 + 引言)：在潜空间用"task-guided modality-adaptive similarity metric"度量各已观测模态的局部相似，再聚合成全局患者相似度，用相似邻居的辅助信息补全缺失模态的任务相关信息。
- 与我方：相似度在可见模态上分别算再聚合 = 我方"逐可见模态平均余弦"的同类思想（我方是无参数平均，M3Care 是学习的任务引导度量）；无残差、无线性基座、无留一、非生存、非病理。
- Refined overlap：P 部分 / M 部分 / I 部分 / D 不同。

## 5. C-MAMs（Geraghty et al., ACM TIST 2025, 10.1145/3746456）——只读摘要
- 摘要："generate missing modality features post-training, preserving the integrity of the original multimodal model"，轻量事后重建缺失嵌入。
- 与我方：问题框架（冻结原模型、事后补全）相同；机制、领域未核实。限制：未读全文，判定置信度低。
- Refined overlap：P 匹配 / M 未核实（按部分） / I 部分 / D 不同。

## 经典统计构件（无单篇论文）
- 留一残差 e_i/(1−h_ii)（PRESS 残差）、kNN 残差修正：回归诊断与局部回归的教科书方法；我方应作为已知构件引用，不声称首创。
