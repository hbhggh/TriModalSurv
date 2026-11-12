# Step 7 — Delta & Verdict
- 时间：2026-11-11

## Delta（英文，可直接改写进 Introduction）
> Unlike MUST, which trains a bimodal network end-to-end with a learned low-rank shared subspace and fills the modality-specific remainder with a conditional diffusion model, and unlike memory-bank methods such as M2Surv/M3Surv, which impute a missing modality by directly averaging the stored features of the most similar training patients, TriModalSurv attaches post hoc to a frozen tri-modal survival backbone, recovers only the low-rank shared coordinates with a pattern-specific linear map, and refines each patient's estimate with the prediction residuals of that map borrowed from similar training patients, improving the 6-missing-pattern C-index over static filling by +0.0138 (22/25 folds) and over neighbour-feature averaging by +0.0068 (13/25 folds) on the development validation folds.

（收益数字全部来自开发期 val，val 同时用于选参；test 未读取，投稿前必须换成 test 数字。）

## Verdict：Level 2 — High Overlap
最接近的是 MUST（Modality-Specific Representation-Aware Transformer for Diffusion-Enhanced Survival Prediction with Missing Modality）：同为 TCGA 五癌缺失模态生存预测，同样把表示拆成"可由可见模态推断的低秩共享部分 + 模态特异部分"，D=256、r=64，带正交与共享一致性约束——覆盖了 A1、C1 与"只恢复可推断部分"的洞见。PRIME 与 M2Surv/M3Surv 各在两轴上重叠（同数据/同框架 + 检索或对齐一致性）。剩下能完整站住的区分只有 B6：在线性恢复基座上检索相似训练患者的预测残差，而不是检索特征本身；加上"冻结骨架事后挂载"的用法（C-MAMs 摘要已有同类框架，未读全文）。delta 是单轴的，需要在写作里明确说出来。
