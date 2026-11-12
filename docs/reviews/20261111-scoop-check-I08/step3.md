# Step 3 — Abstract-Level Triage
- 时间：2026-11-11
- 打分：四轴（P 问题框架 / M 核心机制 / I 关键洞见 / D 应用领域）中摘要层面可能匹配的轴数。
- 未列出的其余 ~100 篇（情感分析、推荐、图像重建、检索、综述、非缺失模态生存等）打分 0–1，完整标题清单见同目录 papers_all.md。

| 论文 | 年 | P | M | I | D | 分 | 来源 |
|---|---|---|---|---|---|---|---|
| MUST: Modality-Specific Representation-Aware Transformer for Diffusion-Enhanced Survival Prediction with Missing Modality | 2026-03 | ✓ | 部分（低秩共享子空间拆分，缺失特异部分用扩散生成） | ✓（显式区分可推断/特异信息） | ✓ TCGA 五癌 | 3 | arXiv 2603.26071 |
| PRIME: Prototype-Driven Multimodal Pretraining for Cancer Prognosis with Missing Modalities | 2026-04 | ✓ | 部分（原型记忆库、患者级共识检索、潜空间补全；跨模态对齐 + 融合后一致性） | 部分 | ✓ TCGA 同三模态同五癌 | 3 | arXiv 2604.04999 |
| M3Surv: Fusing Multi-slide and Multi-omics for Memory-augmented robust Survival prediction | 2025-10 | ✓ | 部分（原型记忆库，按可见特征检索最相似原型补全） | 部分 | ✓ TCGA 五癌 | 2–3 | MedIA 10.1016/j.media.2025.103846；预印本 arXiv 2506.19324 |
| M3Care: Learning with Missing Modalities in Multimodal Healthcare Data | 2022 | 部分 | ✓（潜空间按相似患者补全缺失模态信息） | 部分 | 部分（EHR） | 2 | KDD 10.1145/3534678.3539388 |
| Learning to Associate: Multimodal Inference with Fully Missing Modalities (C-MAMs) | 2025-09 | 部分（推理期缺失、事后补全、不动原模型） | 部分 | ✓（保持原模型完整） | ✗ | 2 | ACM TIST 10.1145/3746456 |
| A cancer-type-aware framework for robust multimodal survival prediction under missing modalities（bbag124） | 2026-03 | ✓ | ✗（门控融合） | ✗ | ✓ 同三模态 | 2 | BiB 10.1093/bib/bbag124 |
| Robust Multimodal Survival Prediction with Conditional LD-CVAE | 2025 | ✓ | ✗（生成式） | ✗ | ✓ | 2 | CVPR 2025 |
| Multi-modal Learning with Missing Modality via Shared-Specific Feature Modelling (ShaSpec) | 2023 | 部分 | 部分（共享/特异特征） | 部分 | ✗ | 1–2 | CVPR 2023 / arXiv 2307.14126 |
| Adaptive risk-aware sharable and individual subspace learning for cancer survival analysis | 2022 | ✗（无缺失） | 部分 | ✗ | ✓ | 1–2 | BiB 10.1093/bib/bbac489 |
| Robust Multimodal Representation under Uncertain Missing Modalities (RMRU) | 2024 | 部分 | 部分（共享子空间重建） | ✗ | ✗ | 1 | ACM TOMM 10.1145/3702003 |
| Similar modality completion-based MSA (SMCMSA) | 2024 | 部分 | 部分（从完整样本库检索相似模态补全） | ✗ | ✗ | 1 | Inf. Fusion 10.1016/j.inffus.2024.102454 |
| Leveraging Retrieval Augment Approach for MER Under Missing Modalities | 2024 | 部分 | 部分（检索） | ✗ | ✗ | 1 | arXiv 2410.02804 |
| Memory-Augmented Incomplete Multimodal Survival Prediction (M2Surv) | 2025-06 | ✓ | 部分（记忆库补全） | ✗ | ✓ | 2 | arXiv 2506.19324（M3Surv 前身） |
| Distilled Prompt Learning for Incomplete Multimodal Survival Prediction (DisPro) | 2025 | ✓ | ✗（LLM 提示蒸馏） | ✗ | ✓ | 2 | CVPR 2025 |
| Cancer Survival Prediction by Cyclic Generation and Multi-grained Alignment (CIMA) | 2026 | ✓ | ✗（循环生成） | ✗ | ✓ | 2 | AAAI 2026 |
| Hybrid GCN with Online Masked Autoencoder (HGCN) | 2023 | ✓ | ✗ | ✗ | ✓ | 2 | TMI 10.1109/tmi.2023.3253760 |
| impuTMAE | 2025 | ✓ | ✗ | ✗ | 部分（胶质瘤） | 1–2 | arXiv 2508.09195 |
| miss-SNF | 2025 | 部分 | 部分（患者相似网络） | ✗ | ✓ TCGA | 2 | Bioinformatics 10.1093/bioinformatics/btaf150 |
| Robust Multimodal Learning via Parameter-Efficient Adaptation | 2023 | 部分（预训练模型 + 缺失） | ✗ | ✗ | ✗ | 1 | TPAMI |
| Cheerla & Gevaert 2019 multimodal dropout | 2019 | 部分 | ✗ | ✗ | ✓ | 1–2 | Bioinformatics |
