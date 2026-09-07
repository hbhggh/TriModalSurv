# 01. 研究问题、场景与创新声称（计划中的 vs 代码里真做了的）

## 研究问题

三模态（WSI 病理图像 + bulk RNA 表达 + 病理报告文本）癌症生存预测，在**测试期模态缺失**下的鲁棒性。骨架来自 Song et al., *A cancer-type-aware framework for robust multimodal survival prediction under missing modalities*（Briefings in Bioinformatics 2026，代码 `zongzi13545329/NPJ`）。本项目的立论方式是"挤水分"：先用统一 split / 统一评测口径复核骨架相对 MCAT、PORPOISE 的真实优势，再在骨架上做缺失补偿创新。

## 场景与协议（实际执行）

- 5 癌（BLCA/BRCA/LUAD/LGG/UCEC）、4:2:4 split、5 seeds 逐值呈现；12 例（BRCA 7、LUAD 5）因作者特征包缺失而三方一致剔除。
- 缺失：只在测试期按固定 manifest 遮挡（`missing_manifest_v1.csv`），训练期不见 manifest；创新臂训练用 modality dropout 0.15 模拟缺失。
- 口径：A = 作者 raw cumprod，B = sigmoid 修正；创新臂主口径 B。判定为逐 seed 严格胜负计数 + 配对Δ中位 + 0.02 噪声带，**不做统计推断**。

## 创新声称 · 一：计划中的（文档层面）

来源：`README.md`（2026-08-27 用户定稿）、`collab/20260828-A测缺失补偿/plan.md`（废弃草案）、`collab/20260902-A测缺失补偿/plan.md`。

1. **主线**：原型学习等补偿方法为缺失的 RNA/文本模态生成虚拟表征（"prototype 或其他生成方法 based missing-modality compensation"）。
2. **辅助**：编码器升级（UNI2-h / BulkRNABert / Bio_ClinicalBERT）——用户裁决"不把 UNI2-h / BulkRNABert 再写成创新"。
3. **明确留给下一篇**：选择性补偿（recoverability-aware selective compensation）。
4. **只进候选表、未实现**：VAE / 扩散式生成补偿；PRIME "必引不必比"。
5. 计划中的对照臂：M0（作者原样）、M1（均值盲补）、M1b（可学习 bank）、M2（CAP-Recall）。

## 创新声称 · 二：代码里真做了的（以 `code/NPJ/` 为准）

| 项 | 代码事实 | 是否进入正式结果 |
|---|---|---|
| **拆 gate 换 attention 融合（NPJ-C）** | `model/fusion_model.py:1078 class NPJC`：三模态 256d token + 可学习模态嵌入 → `nn.TransformerEncoder(src_key_padding_mask=~valid)` → masked-mean → per-cancer 生存头；不使用 `GatedFusion` | 是：E0/E0d/E1 三臂 × 5 癌 × 5 seeds（`scripts/train_launcher.py:56 ARM_PRESETS`） |
| **CAP-Recall（癌种分库原型召回）** | `model/compensator.py:34 CAPRecall`：每模态 `[4 bin × 256]` 原型表（训练期 EMA 0.99 更新，bin 来自生存时间 `pd.cut`），以 WSI token 为 query 对原型做 cross-attention 召回缺失 token；在 NPJC 的 attention **之前**替换缺失位并解除屏蔽（`fusion_model.py:1137-1168`） | 是：E1（NPJ-C 版）与 M2（gate 版） |
| 一致性 loss | `compensator.py:223`：仅对训练期被 dropout 的位置，召回 token 与原 token 的 `1 − cosine`；λ=0.1 | 随 E1/M2 一起，**未单独消融** |
| modality dropout | `loc_utils_3yr/tcga_dataset.py:471-483`：训练期按 (patient, modality) 确定性丢弃 | E0d（单独消融）、E1、M1b、M2 |
| MissingBank（可学习常量补偿） | `compensator.py:175` | M1b（gate 版） |
| 评测期均值盲补 | `scripts/eval_missing.py:192,224`（`--arm m1`；NPJ-C 版加 `--m1-mark-valid`） | M1（gate 版）；**E0m（NPJ-C 版，2026-09-06 已跑）** |
| 作者 gate 的缺失判据死代码 | `fusion_model.py:1011-1015` 读 `{mm}_mask`，数据集只产 `{mm}_valid`（`tcga_dataset.py:591`）→ 条件恒假，缺失模态以"全零特征过 projector 得到常量 token"参与 gate 加权 | 探针实证（`probe/`），**未修复、未当创新** |

## 主线改向史（如实记录）

1. 2026-08-27：核心创新定稿为"原型/生成式补偿"，编码器升级为辅助。
2. 2026-08-28：A 测第一版契约（以 NPJ-A 锚定）→ 2026-09-02 废弃，改为以 NPJ-B（sigmoid 修正）为创新臂主口径。
3. 2026-09-02：只读 gate 探针发现作者 gate 的 mask 链路为死代码、权重由 RNA token 范数主导（BLCA s123：img/text/rna = 0.772/0.203/0.025，RNA 范数 8.2 vs img 0.26）；用户裁决"不修作者 mask、不重训 M0"，另起 NPJ-C（拆 gate）作为 E0，CAP-Recall 接在 NPJ-C 上作为 E1；gate 版 M1/M1b/M2 结果冻结原样保留。
4. 2026-09-02～04：报告 r1→r4，decision-reviewer 四轮；主贡献表述最终为"以 attention 融合替换伪门控"，CAP-Recall 降为"条件性补偿"。这一改向发生在实验中途，`collab/20260902-A测缺失补偿/notes.md` 的指挥官 Post-Mortem 对此有自省记录。

## 明确没做的

- E0m（E0 ckpt + 评测期均值盲补）：**已跑（2026-09-06，r5 二 c）**；结论：原型相对均值填仅 UCEC 成立。E0dm（E0d + 均值填）未跑。
- bootstrap CI / 配对检验：未做。
- E0 去 attention 仅 masked-mean 消融、E1 去一致性 loss 消融：未做。
- 编码器升级（UNI2-h、自制 BulkRNABert）已用于所有臂，但**不作为创新声称**。
- 5 癌以外的癌种、外部验证集：无。

## r6 追加（2026-09-07）：NPJ-D 底座线

- 代码里真做了的（新增）：`MeanFusion` + `MainModalityMoE(fusion_type="mean")`（`model/fusion_model.py`），即 NPJ-A 去 GatedFusion、其余逐字相同；`--fusion_type` 透传训练/评测；launcher 预设 `d0`。用作更弱的 E0 底座 D；Dm = D ckpt 评测期均值填（零训练）；E1 补至 25 seed。
- 主线改向（如实）：用户明言动机是"NPJ-C 太强、E1 打不过，换更弱的 E0"；指挥官异议留档（E1 vs D 相差五项 → 只能称系统级对比；以 Dm 为护栏），用户裁决 C 线作附录、D 线为主。结果：原型相对均值填的增量在 C 底座落在 UCEC、在 D 底座落在 BLCA，两线不重合；去 gate 本身改善 4/5 癌（D vs NPJ-A）。主贡献措辞待用户裁决（见报告 r6 六节）。
