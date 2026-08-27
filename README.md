# TriModalSurv

三模态（WSI + RNA + 病理报告文本）癌症生存预测研究项目。

- **骨架**：Song et al., *A cancer-type-aware framework for robust multimodal survival prediction under missing modalities*, Briefings in Bioinformatics 2026（DOI 10.1093/bib/bbag124），代码 [`NPJ/`](NPJ/)（上游 `zongzi13545329/NPJ` 的本地克隆，独立 git，不纳入本仓库跟踪）
- **核心创新方向**（2026-08-27 用户定稿）：**原型学习等一系列的补偿方法进行缺失模态的补偿操作**（prototype 或者其他生成的方法-based missing-modality compensation——为缺失的 RNA/文本模态生成虚拟表征），编码器升级（UNI2-h / BulkRNABert / Bio_ClinicalBERT）作为辅助创新。*选择性补偿（recoverability-aware selective compensation）留作下一篇论文，本篇不做。*
- **执行环境**：landau 服务器 `/home/wuhao/NPJ`（2×V100），本地 `NPJ/` 为 Codex/审查工作区
- **当前阶段**：三方对比战役 S4 正式训练（MCAT / PORPOISE / NPJ 骨架 × 5 癌种 4:2:4 × 5 seeds 逐值），见 [collab/20260827-三方对比战役/plan.md](collab/20260827-三方对比战役/plan.md)
- **前史**：本项目从 ProtoMaskSurv 剥离（2026-08-26）；更早的 MCAT 两模态方案与三组学证伪记录仍在 ProtoMaskSurv/collab/ 中。

## 目录

```
TriModalSurv/
├── NPJ/        # 骨架代码克隆（独立 git；配置修改在此审查后 scp 到 landau）
├── collab/     # 派单任务目录（plan / notes / result 闭环）
└── README.md
```
