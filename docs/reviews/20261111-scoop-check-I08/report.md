# I08 TriModalSurv 新颖性查重报告（scoop-check，SCI 三区 / BMC Bioinformatics 口径）

- 日期：2026-11-11｜执行：Claude Code（Opus 5.5）｜只读：未改代码、handoff、03_index，未读 test
- 对象：M6-a = A1 + B6-LOO + C1（handoff-论文生成.md §1.1–1.3）
- 逐步日志：同目录 step1–7.md；全部论文清单：papers_all.md；全文 PDF 存 scratchpad，不入库

## 1. Verdict
**Level 2 — High Overlap**（由 MUST 决定）。计数规则：按每条轴的核心主张判断，细节差别写进 delta、不把轴降为"部分"（规则与理由见 step6.md）。若改用"凡有细节差别即记部分"的宽松规则，MUST 会降到 Level 3–4，但那样会系统性偏乐观，本报告不采用。

## 2. Delta
> Unlike MUST, which trains a bimodal network end-to-end with a learned low-rank shared subspace and fills the modality-specific remainder with a conditional diffusion model, and unlike memory-bank methods such as M2Surv/M3Surv, which impute a missing modality by directly averaging the stored features of the most similar training patients, TriModalSurv attaches post hoc to a frozen tri-modal survival backbone, recovers only the low-rank shared coordinates with a pattern-specific linear map, and refines each patient's estimate with the prediction residuals of that map borrowed from similar training patients, improving the 6-missing-pattern C-index over static filling by +0.0138 (22/25 folds) and over neighbour-feature averaging by +0.0068 (13/25 folds) on the development validation folds.

数字全部来自开发期 val（val 同时用于选参），未经 test 验证。

## 3. Decomposed claim
- **问题框架**：冻结的三模态生存骨架（I07），测试患者缺 1–2 个模态（6 种模式），推理期恢复以维持 C-index；完整输入恒等直通；TCGA 五癌 5 折。
- **核心机制**：A1 Cayley 正交基 U_m（256×32），只恢复共享坐标、截断正交补；B1 按模式的线性映射；B6-LOO 在 B1 训练残差池（Hat 矩阵留一去偏）里按可见模态平均余弦取 Top-K 邻居加权修正，IQR 密度门控回退到 B1；C1 训练期正交重构锚定 + 共享方向对齐 + 停梯度恢复一致性。
- **关键洞见**：只恢复可跨模态预测的低秩共享部分；线性趋势之外的个体偏差用相似患者的预测残差补。
- **应用领域**：计算病理 / 多组学癌症生存分析（TCGA BLCA/BRCA/LUAD/LGG/UCEC）。

## 4. Structured papers
完整去重清单见 papers_all.md（paper_search 117 篇 + Consensus 替补约 70 条 + 记忆召回 2 篇）。四轴打分 ≥1 的见 step3.md，摘录如下：

| 论文 | 日期 | 分 | 来源 |
|---|---|---|---|
| MUST | 2026-03 | 3 | arXiv 2603.26071 |
| PRIME | 2026-04 | 3 | arXiv 2604.04999 |
| M3Surv（期刊版）/ M2Surv（MICCAI 版） | 2025 | 2–3 | 10.1016/j.media.2025.103846 / arXiv 2506.19324 |
| M3Care | 2022-08 | 2 | 10.1145/3534678.3539388 |
| C-MAMs | 2025-09 | 2 | 10.1145/3746456 |
| bbag124（cancer-type-aware） | 2026-03 | 2 | 10.1093/bib/bbag124 |
| LD-CVAE、DisPro、CIMA、HGCN、miss-SNF | 2023–2026 | 2 | 见 step3.md |
| ShaSpec、ARSIL、RMRU、SMCMSA、MER-RAG 等 | — | 1–2 | 见 step3.md |
| B6 机制补充检索：TOBMI、MoE-Retriever、Borrowing Treasures from Neighbors、CAR-MFL、MIND、PRESS/LOO 系列 | — | 0–1 | papers_all.md B 节 |

## 5. Comparison result
（计数规则与逐轴理由见 step6.md）

- **Proposed work**：TriModalSurv M6-a——见第 3 节。
- **MUST**：P 匹配（双模态、端到端是细节差别）/ M 部分 / I 匹配 / D 匹配 → 3 轴 → **Level 2，one axis differs**
- **PRIME**：P 匹配 / M 部分 / I 部分 / D 匹配 → 2 轴 → Level 3，two axes differ
- **M2Surv / M3Surv**：P 匹配 / M 部分 / I 部分 / D 匹配 → 2 轴 → Level 3，two axes differ
- **M3Care**：P 部分 / M 部分 / I 部分 / D 不同 → 0 轴 → Level 5，all axes differ
- **C-MAMs**（只读摘要，低置信）：P 匹配 / M 部分（未核实）/ I 部分 / D 不同 → 1 轴 → Level 4，three axes differ

B6 机制轴补查三条：没有找到"线性恢复基座 + 近邻预测残差修正"用于缺失模态的工作。检索类方法检索的都是特征、嵌入或原型本身；留一残差 e/(1−h)（PRESS）是教科书方法，应作为已知构件引用。

## 6. 三区口径解读（BMC Bioinformatics）
**官方标准**（2026-11-11 从 Springer 官方 Aims and scope 页面读取）：期刊收"novel computational algorithms and software, models and tools"；作为 BMC 系列期刊，"does not make editorial decisions based on the perceived interest or potential impact of a study"，只看科学是否可靠（研究问题明确、方法与分析恰当、符合领域公认标准）。

**结论（有条件）**：在三区门槛下，Level 2 不构成否决，但前提是写作要把 delta 讲成单轴，而且对比要经得起审稿人追问。逐条：

1. **贡献表述要改（只报告，本轮不改文件）**。handoff §1.3 把 A1、C1 写成"提出"。MUST 已有低秩共享子空间 + 正交 + 共享一致性，PRIME 已有跨模态对齐 + 一致性，所以这两条应改为"采用 / 适配已知构件"并引用它们。主贡献落在 B6：在线性恢复基座之上检索相似患者的预测残差；外加冻结骨架事后挂载的用法（引用 C-MAMs）。Prop. 1 可作为动机观察保留。
2. **不要把增益归给留一去偏 + IQR 门控**。同口径下 M5（B6-Naive）选参后 0.6664，略高于 M6-a 的 0.6657。这两个设计只能写成稳健性 / 安全回退（默认口径 0.6594 对 0.6589；选参口径下对 M0-a 的胜场 22/25 对 19/25），不能写成性能来源。
2b. **A1 的"学习子空间"同样站不住**：M9（PCA-32 代替 A1，再接 B6-LOO）选参后 0.6664，高于 M6-a；默认口径 0.6586 对 0.6594，几乎打平。A1 只能写成"低秩共享子空间"这一设计选择（256 维全空间默认口径 0.6406，说明低秩免调参稳健），不宜强调 Cayley 学习优于 PCA。handoff Table 4 用 Ours 选参值对比 PCA-32 的 @default 值，同样落在第 4 条的口径问题里。
3. **M3Surv 式检索已有同口径对照**：M3 = A1 + B3 + C1（直接聚合邻居特征），正好回应"B6 就是记忆库检索"的质疑。但差距不大：同口径差为 +0.0068（选参对选参、默认对默认都是这个数），选参口径下只赢 13/25 折，要如实写。val 表里 M6-a@default 行的"+0.0005 (11/25)"是对 M3 选参值的跨口径比较，不要引用。
4. **公平性风险（底线问题，需你裁决）**：handoff 的"单列铁律"让 Ours 用选参后结果、其余行全用 @default。同口径选参后 M7 是 0.6643、M8 是 0.6651、M5 是 0.6664，与 Ours 差 ≤0.0014 或反超。审稿人一旦要求同口径，Table 3 / Table 4 的"逐级增益"会消失。建议两种口径都报，或所有方法用同一选参协议。这会改变实验口径，按 AGENTS.md 须由你决定。
   - **用户裁决（2026-11-11）：维持单列铁律**（Ours 用选参后结果，其余行用 @default），不改表格口径。在此前提下，写作上要守两条：① 表注和实验设置小节写明这一口径（handoff G0 第 3 条已有此要求）；② 正文不写"在同等调参条件下每个组件都带来增益"之类的话，组件作用按本节第 2、2b 条表述；同口径数字（M5 0.6664、M7 0.6643、M8 0.6651、M9 0.6664）留作回复审稿意见时的备用材料。
5. **证据仍只来自 val**：val 同时用于选参。投稿前需要你授权解锁 test。
6. **Related Work 必须交代的最近邻工作**：MUST、PRIME、M2Surv/M3Surv、M3Care、C-MAMs、ShaSpec、bbag124；PRESS / 留一残差作为经典统计构件引用。

**故事线**（按你要求的"完整、通顺"口径）：静态填充在线性风险头下排序不变 → 全维恢复对正则敏感 → 只恢复低秩共享部分 + 线性基座 + 相似患者残差个体化 → 同口径消融。这条链本身是闭合的。唯一会被追问的断点是第 4 条的口径问题。

## 7. 局限
- Semantic Scholar 在 Q2–Q5 持续 429，改用 Consensus 替补；DBLP 解析失败；OpenReview 返回 0。
- M3Surv 期刊版、C-MAMs 只读了摘要；M3Care 只读了摘要和引言。
- MUST、PRIME 都是 arXiv 预印本（未经同行评审），但仍算已公开的先行工作。
