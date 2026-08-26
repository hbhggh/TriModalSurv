# TriModalSurv

三模态（WSI + RNA + 病理报告文本）癌症生存预测研究项目。

- **骨架**：Song et al., *A cancer-type-aware framework for robust multimodal survival prediction under missing modalities*, Briefings in Bioinformatics 2026（DOI 10.1093/bib/bbag124），代码 [`NPJ/`](NPJ/)（上游 `zongzi13545329/NPJ` 的本地克隆，独立 git，不纳入本仓库跟踪）
- **核心创新方向**：recoverability-aware selective compensation（选择性补偿），编码器升级（UNI2-h / BulkRNABert / Bio_ClinicalBERT）作为辅助
- **执行环境**：landau 服务器 `/home/wuhao/NPJ`（2×V100），本地 `NPJ/` 为 Codex/审查工作区
- **当前阶段**：数据与复现管线（阶段 0 复现 → 阶段 1 WSI 换 UNI2-h → 阶段 2 文本/RNA 编码器），见 [collab/20260826-NPJ三模态复现/HANDOFF.md](collab/20260826-NPJ三模态复现/HANDOFF.md)
- **前史**：本项目从 ProtoMaskSurv 剥离（2026-08-26）；更早的 MCAT 两模态方案与三组学证伪记录仍在 ProtoMaskSurv/collab/ 中。

## 目录

```
TriModalSurv/
├── NPJ/        # 骨架代码克隆（独立 git；配置修改在此审查后 scp 到 landau）
├── collab/     # 派单任务目录（plan / notes / result 闭环）
└── README.md
```
