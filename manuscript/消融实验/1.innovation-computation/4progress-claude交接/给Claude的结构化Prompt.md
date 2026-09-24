# 给 Claude Code：将 4.progress 结果写入论文 LaTeX

## 1. 任务与终点

实验已经收尾。本任务只将既有 4.progress 结果整理进论文；完成表格、结果文字、方法公式和编译核验后停止。

目标文件：
/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.tex

先完整阅读同目录交接材料：
/Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/4progress-claude交接/实验先验知识与公式说明.md

在目标 main.tex 中新增：
1. Table 1：五癌 × 四场景 × 三种补偿方法，另加癌种内 overall 行，严格按指定 SVG 的分组结构。
2. 对 Table 1 的英文结果说明，克制陈述有利结果，并保留结果适用范围。
3. 与实际执行代码一致的方法公式，定义符号、按逻辑顺序编号、逐式解释，并用 LaTeX label/eqref 引用。

建议英文表题：
Comparison of three compensation strategies across five cancers under four modality-availability settings.

## 2. 必读文件与证据优先级

| 用途 | 绝对路径 |
| --- | --- |
| 实验先验、公式、数据口径 | /Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/4progress-claude交接/实验先验知识与公式说明.md |
| 必须实际打开查看的表格框架 | /Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/消融实验-prototype.excalidraw.svg |
| 逐癌种读数 | /Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/癌症为单位.md |
| 逐 seed 读数 | /Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/seed单位-实验结果.md |
| 未舍入数值的唯一主来源 | /Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/runs/test/complete.json |
| 路由与参数 | /Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/luad_m1_force/config.yaml |
| 路由实现 | /Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/luad_m1_force/model.py |
| 冻结及审阅边界 | /Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/frozen-routing.json；同目录 claude-result-review-r2.md |
| 用户论文基础文件，只读 | /Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/trimodalsurv-论文初版本-modify-from-bbag124.docx |

数字从 complete.json 的 rows/c_index_b 提取；两份 MD 用来交叉检查，不能把它们已经舍入的数字再次平均。公式从实际执行链重述，不照抄论文理想机制。SVG 决定表格布局，不提供结果数字。

用户最后写的文件后缀“.svgd”是笔误；磁盘核实存在的是上表的“.svg”。

## 3. 命名与历史上下文：防止偏移

- 当前协议是 patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-force-v1；不是原始 v2、K=8、人群原型、E1/CAP 或新训练实验。
- 用户口语中的“原型学习”在此具体指：冻结患者内 WSI 缓存原型引导的患者检索，加上固定的补偿/不补偿路由。本轮检索模块无可学习参数；已有 NPJ-C 网络是历史训练好的冻结权重。
- 表格保留用户的三方法结构。第三列可短标“原型补偿† / Prototype-guided compensation†”，但图注和 Methods 必须定义它实际是带固定路由的 S0-force 组合；不允许用“纯原型学习”代替实际协议。
- 五癌 overall 严格超过两条基线的是 BRCA、LGG、LUAD、UCEC，BLCA 未胜。4/5 是每癌五 seed × 四场景均值的胜率，不是每癌所有场景都赢。
- valid 不支持 LUAD 路由：B−A=-0.008815；本轮仍由用户决定强制启用。规则来自已见 test，因此存在 test 泄漏，是探索性、事后分析，不是盲测或独立确认。
- LUAD 的改善来自 rna_100/both_100 改走固定 m1，text_100 固定 m0real；LUAD 对 m1 的 overall 优势仅约 0.0000351。不能把它当作独立的患者检索有效性证明。

## 4. Table 1：必须遵循 SVG 的表格契约

| 项目 | 要求 |
| --- | --- |
| 行方向 | rna_100、text_100、both_100、none、overall；与 SVG 上下排列相同 |
| 列方向 | 首列 Scenario；其后五个癌种分组，每组恰好三列 |
| 癌种顺序 | SVG 已明示 BRCA、UCEC、LUAD；其余按“依次类推”补 BLCA、LGG。此顺序是交接排版约定，不改变统计 |
| 每癌三列顺序 | 不补偿（m0real）、均值补偿（m1）、原型补偿†（strategy0） |
| 单场景单元格 | 对该癌、该场景、该方法的五个 seed C-index 等权求均值 |
| overall 单元格 | 同癌同方法四场景的未舍入均值等权平均，等价于其20格均值 |
| none | 无额外人工遮挡，保留天然缺失；不得称 complete data |
| 展示 | 六位小数；每癌每行三方法按未舍入值比较，最高加粗，并列全部加粗 |
| 聚合单位 | 五个 seed，不是五折，不挑最好的 seed，不合并患者后重算 pooled C-index |
| 范围 | BLCA、BRCA、LGG、LUAD、UCEC；不得将 LGG 写成 GBMLGG，不加癌种 |
| 禁止 | 不转置成癌种作行；不删 none；不把 overall 当成第五个实验场景；不以75格表替换100格主口径 |

LaTeX 应有两层表头：第一层用 multicolumn 合并癌种，第二层重复三方法；总计16列。用 booktabs 和必要的横向页面/跨栏布局保证可读性。SVG 是结构参考，不需要照搬手写歪线。

现有 main.tex 已有 tab:two、tab:three 两张旧表。把新增表放在旧第一张表之前，使用唯一标签 tab:prototype-compensation，使自动编号为 Table 1；保留旧表内容/标签，让旧表自动顺延。仅修正因新增表引起的必要交叉引用，不通过重置计数器制造多个 Table 1。原有模板中未完成的八癌、两模态、five-fold 字句不是本轮实验证据；本新增小节明确自己的五癌/三模态/五 seed 范围，不凭空补全旧稿。

## 5. 方法公式与结果文字

Methods 增加与现有结构协调的小节，参照先验文件 P1–P13：
有效原型行 → 患者等权 train 去中心 → WSI 余弦／条件 RNA 联合相似度 → 合法候选与 Top-1 → 原始模态特征取回 → 收缩表达式（本轮λ=1）→ S0-force 分段路由 → 原 mean/projector → Transformer → 末端加权 pooling → B 口径风险。

必须同时说明：
- 当前检索 key 是有效行 mean 的1536维向量，已不使用128×1536展平余弦。
- 128是缓存行数上限，可能有 padding；检索排除 padding，模型本人的 WSI 输入仍沿用历史128行 mean。
- 所有 donor/均值/中心只来自同癌 train，双缺同一合法 donor，自检索排除；候选不使用结局标签。
- 返回的是 donor 的投影前目标模态完整特征，随后按原接口 mean→projector；不是直接把聚类中心当 RNA/Text 补值。
- 无 CAP、无 EMA、无 InfoNCE、无重训和新增损失；不编造其公式。
- w=0.5 只在组合的填入模态末端 pooling 生效；固定 m1 路由是 w=1，m0real 的缺失位屏蔽。
- 路由在最外层明确建模，否则公式描述不了表内 LUAD 和 text_100 的实际结果。

Results 给1–2段克制的英文解释：报告宏平均和癌种差异，指出部分缺失场景的收益；同时交代 BLCA 未改善、LUAD 近似平局及探索性选择。可以说“组合补偿策略在当前评测中提高了平均判别性能”，不能说“证明原型学习显著优越”。没有统计检验则不使用 statistically significant。不新增实验、不建议重训来完成写作任务。

## 6. 写入边界

- DOCX 全文件保持字节不变，包括原正文、参考文献、样式及元数据；只读参考。
- 原 references.bib、SVG、实验代码/配置/权重/缓存/split、2/3/4.progress 结果保持不变。
- 论文修改限定 main.tex 中的新方法、新表、新结果文字及必要的排版/交叉引用调整；不得重写整篇论文。
- DOCX 含来源论文作者、结果和参考文献。不要把这些内容自动搬成我方作者、我方实验或未经核实的引文。
- 新增英文和公式使用自己的表述；需要引用时核对现有 bib 的条目，不编造文献。
- 编译中间文件放独立 build 目录；无编译器则如实说明，不能声称编译成功。
- 完成后给出 main.tex 改动位置、表格/公式标签、数据核验、编译状态及 DOCX/SVG/bib 不变证明，然后停止。

## 7. 验收清单

- [ ] 实际查看指定 SVG，而不只读文件名。
- [ ] 新表为5个癌种组×3方法，四场景＋overall；60个场景值＋15个overall值齐全。
- [ ] 三方法字段映射正确，五 seed 均纳入；75个展示数都可由原始 rows 复算。
- [ ] 100格宏平均 strategy0/m1/m0real 分别为0.640506/0.631824/0.630751；四癌 overall 获胜，BLCA未胜。
- [ ] 第三方法图注明确为 S0-force 组合，披露固定路由与 test 泄漏，未把4/5归因为纯检索。
- [ ] Methods 公式带自动编号、唯一 label 和正文引用；每个公式有代码来源对应。
- [ ] Table 1 实际自动编号正确，旧表/参考文献保留，表格可读。
- [ ] DOCX、SVG、references.bib 与实验文件哈希不变。
- [ ] 交付编译验证或实际阻断证据；未训练、未重新评测。

