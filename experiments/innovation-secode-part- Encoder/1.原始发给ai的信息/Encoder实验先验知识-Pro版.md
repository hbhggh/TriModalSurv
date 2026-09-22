# Encoder 辅助创新点：Pro 版实验先验知识

版本：v2。统一方法简称为“原型检索方法”，完整定义及证据快照时间差见 [v2版本说明](Pro证据/v2版本说明.md)。

核验日期：2026-09-20。此文件是共同事实底稿，不是候选选型、训练授权或新实验结果。跳过 Gemini；与 [Pro Prompt](给ChatGPT-Pro的结构化Prompt.md) 一起阅读。原始资料的旧任务指令只作历史记录，不覆盖最新锁定要求。

## 1. Trigger / Q_draft

| 符号 | 本次含义 |
| --- | --- |
| T | 已有 NPJ-C＋原型检索方法（完整S0-force实现），准备寻找低成本 encoder 辅助改进 |
| Q_draft | 仅历史 none，在五癌中争取至少4/5癌种的五 seed 平均 B C-index 高于现有系统；新成绩未产生 |
| 共同前提 ∩P_i | 输入可获得、特征语义和维度可衔接、成本可接受、对照公平、可复现来源；目前不能宣称全部满足 |
| S_state | 下列核验过的代码/配置/结果及明确未核验的资产，不把期望当事实 |
| P_i | 各候选对原始数据、权重、空间适配、训练和资源的具体要求 |
| B | 候选在本数据、低成本约束和目标下适用及不适用的条件 |
| A | 本轮仅制作并归档交接；后续实施由用户另外拍板 |

### 不能漂移的目标

- **原型检索方法（包含既有固定路由）整体取得4/5。** 4/5归属于该完整方法；“原型检索方法”是方法级简称，包含固定路由及相关填补/融合处理，不等同于单独Top-1模块。独立组件贡献尚未拆分。
- 两条固定对照m1/m0real在全部单元采用各自统一策略；方法内同名分支仅局部条件触发。共同pooling结构不是新增创新；特定规则是检索填入位w=0.5。
- 此处原型指患者内WSI中心缓存（可有补零），不是将donor患者当成可学习原型；本轮不训练新原型，donor提供原始完整目标特征。
- `none`＝无额外人工遮挡，保留天然缺失；不换成完整子集。
- 对照＝Table 1 `None / Proto.†`。已有结果不能代表新 encoder。
- 未来主比较是现有 encoder 系统与替换后的系统，不是重新比较三种补偿方式。
- 不扩癌种/seed，不自动加入 rna_100/text_100/both_100 新实验。历史四场景只用于交代来源。
- 前沿性是偏好；不保证涨点、不保证创新性，不拿已见 test 挑出“必胜”候选。

## 2. S_state：来源与核验边界

| 项目 | 状态与依据 |
| --- | --- |
| 历史协议 | `patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-force-v1`；归档配置见 [config](Pro证据/code/config_s0_force.yaml) |
| 底座 | E0/NPJ-C，compensator=none；25个既有权重。此交接不重新访问远端权重和缓存 |
| 癌种/seed | BLCA、BRCA、LGG、LUAD、UCEC；123、132、213、231、321 |
| 历史方法类别 | 冻结患者库的非参数检索＋固定路由；历史推理过程零训练，无新增可学习原型、EMA、CAP、InfoNCE |
| 特征形状 | 归档配置 WSI `[128,1536]`、Text `[200,768]`、RNA `[2048,256]`；隐藏维256。见 [上游配置](Pro证据/code/config_rules1to5.yaml) |
| WSI 生成接口 | 当前 dataset 在行数不足时补零，否则 MiniBatchKMeans；历史来源材料记录 UNI2。仅凭形状不能验证基础模型权重版本；没有重新核验原始 slides 或提取权重 |
| RNA/Text 身份 | 精确基础模型、权重版本、预处理、原始RNA/文本可得性尚未独立核实；BERT/BulkRNABERT 是原始需求中的论文描述，不作为本次运行已证实身份 |
| 当前模型接口 | [npjc.py](Pro证据/code/npjc_current.py)：缓存 token 先 mean，再 Linear→ReLU→Dropout→256维；每模态一个 token 进入融合 Transformer |
| 模型/检索区别 | 模型 WSI mean 仍包含128行的历史padding；检索 key 只对有效行mean，排除补零 |
| 冻结参数 | λ=1、α=1、w=0.5；UCEC/text_100例外启用；LUAD外层路由强制启用 |
| 科研状态 | 新 encoder、MLP消融、其他 encoder 均未实验；没有模型优劣结论 |
| 资源和规模缺口 | 本轮未核验各癌 train/valid/test 完整人数、事件数、原始输入可取性、GPU可用性和新encoder预算；不能以缓存存在代替这些事实 |

当前代码快照用于接口解释，不冒充历史正式运行源码。完整路径、快照哈希与来源版本见 [来源清单](Pro证据/source_manifest.json)。历史 test 运行指纹为 `a825b3cc4df41cf56afe228be531a4fc13f69c520bf35a2f2305101652387ec2`，与文件 SHA-256 含义不同。

## 3. 原型检索方法的整体结果与实现记录

| 事实 | 正确解读 |
| --- | --- |
| B口径，五癌×五seed×四场景等权宏平均 原型检索方法（S0-force）=0.640506，m1=0.631824，m0real=0.630751 | 成绩归属于原型检索完整方法；评测为探索性，不是本次 encoder 效果 |
| 原型检索方法整体取得4/5：BRCA、LGG、LUAD、UCEC；BLCA未胜 | 统计单位为每癌四场景均值；不是none单场景4/5，也不意味着所有场景都胜出 |
| LUAD overall 对 m1 仅约 +0.0000351 | 接近并列，不能称稳健优势；其rna/both场景数值等于固定m1，text场景等于固定m0real，与实际路由一致 |
| LUAD valid A=0.65404181184669，B=0.6452264808362369 | B−A=−0.008815331010453065；仍强制启用，存在已见 test 驱动的选择/泄漏，不是独立盲测 |
| 原 Top-1 方案总体曾劣于均值填补与不补偿 | 原始Top-1方案与当前原型检索完整方法不是同一协议，不能互换成绩；独立组件贡献未拆分 |
| 3.progress 门禁关闭路由，4.progress 强制开启 | 这是策略裁决变化，不应叙述为修复实现 bug |

原始300格结果的无患者信息投影见 [aggregate_rows.json](Pro证据/aggregate_rows.json)；只保留癌种、seed、场景、策略、C-index。原文件没有被改写。来源 JSON 哈希绑定整个归档文件，本包不是新的模型评测。

## 4. 当前 None 对照：唯一取数契约

从 `4.progress/runs/test/complete.json` 的顶层 `rows` 筛选 `grid=none, protocol=strategy0`，恰好25条；指标 `c_index_b`。不叠加 `luad_executed_rows` 或 `retrieval_reference_rows`。先对五个未舍入值平均，再显示六位。

| 当前系统对照 | LGG | BRCA | BLCA | LUAD | UCEC |
| --- | --- | --- | --- | --- | --- |
| Table 1 None / Proto.† | 0.797723 | 0.688112 | 0.589972 | 0.582485 | 0.650968 |

25个原值、五癌均值和复算方式见 [None基线明细](Pro证据/None基线明细.md) 与 [CSV](Pro证据/none_baseline.csv)。已核对 [完整PDF](Pro证据/main.pdf) 第7页、[Table 1 TeX摘录](Pro证据/table1.tex) 和原始 JSON。PDF是完整论文，不代表其中其他实验或占位描述都已经独立核实；本文证据只对应指定协议和表格。

LUAD/none 的 m1 分支触发0次，该列与 `upstream_combo` 的五个seed读数逐一相同，不能归因于S0-force的强制路由增益；见 [同格核验](Pro证据/luad_none_upstream_parity.json)。

未来若完成可比新结果，定义每癌 `Δ_c = mean_seed(C_new,c,none) − mean_seed(C_baseline,c,none)`，胜率为 `Σ_c 1[Δ_c>0]/5`，并列不算胜。不用最佳 seed 代替五 seed，不因未达4/5删癌/删seed。这个目标与历史“四场景同时超过 m1/m0real”的4/5是不同统计量。

若新 encoder 需要重新训练或改选择协议，这25个历史值仍可作历史参照，但不能自动作为严格单因素因果对照；公平训练条件须在后续授权前另行明确。

## 5. 指定表格结构

已目视 [原始 SVG](Pro证据/Framework-encoder-tabel.excalidraw.svg)，[PNG预览](Pro证据/Framework-encoder-tabel.png)仅帮助网页阅读；SVG是结构真源。

| Encoder（结构占位） | LGG | BRCA | BLCA | LUAD | UCEC |
| --- | --- | --- | --- | --- | --- |
| MLP | 未实验 | 未实验 | 未实验 | 未实验 | 未实验 |
| 原论文的 Encoder | 未实验 | 未实验 | 未实验 | 未实验 | 未实验 |
| 其他方法的 Encoder | 未实验 | 未实验 | 未实验 | 未实验 | 未实验 |
| 我们提出来的 Encoder | 未实验 | 未实验 | 未实验 | 未实验 | 未实验 |

此表是未来实验结构，不是成绩表。MLP的层级、输入和训练方式尚未定义；原论文行与当前系统身份尚未核实，不能将上节成绩强塞入该行。SVG顶部“三个模态都齐全”的旧字样由用户最新 none 定义覆盖，原图保留不改。

## 6. 当前逻辑链与 encoder 替换影响

以下是已执行方法的数学化，不是新 encoder 的设计，也不是最优性证明。完整 P1–P13 见 [历史方法先验原文](Pro证据/实验先验知识与公式说明-历史原文.md)。该原文末尾“main.tex尚未新增”是更早时点状态；包内已核验的PDF/TeX快照含Table 1，但不代表用户本机后来编辑的最新工作稿。

本节保留原型检索方法的实现细节供工程交接。λ控制donor值向均值的收缩；路由还决定是否填值、布尔mask及pooling权重，故不是λ一个参数的同义写法。v2未修改或删除历史代码、公式快照。

### E1：冻结患者 key 与检索

令 `P_i∈R^(128×1536)` 是 WSI 缓存，`a_ik` 是去中心前识别的有效行掩码。只允许合法非零前缀/补零后缀。

\[
u_i=\frac{\sum_k a_{ik}P_{ik}}{\sum_k a_{ik}},\quad
\mu_c^W=\frac{1}{|I_c|}\sum_{j\in I_c}u_j,\quad
q_i=u_i-\mu_c^W,\quad
j^*=\arg\max_{j\in\mathcal D_i}\cos(q_i,q_j). \tag{E1}
\]

`I_c` 仅同癌 train，患者等权；候选排除本人且真实具有全部缺失目标模态，双缺用同一donor；同分按patient ID排序。none不使用RNA联合相似度（仅text_100的适用路径使用α）；没有重新K-means或展平余弦。源码：[key](Pro证据/code/wsi_meanpool_key.py)、[推理路由](Pro证据/code/inference_rules1to5.py)、[库](Pro证据/code/patient_bank.py)。

### E2：none 的实际填值与路由

本人可用特征原样保留。非LUAD的自然缺失走冻结检索组合；LUAD自然缺RNA或双缺走m1，仅缺Text或完整输入沿用组合。检索填入 `μ_c^m+λ(X_donor^m−μ_c^m)`，λ=1，实际即donor完整投影前特征；m1为同癌train真实可用目标张量逐元素均值。填入位fusion_valid=true。空候选和非法值报错，不静默退回均值。

历史LUAD/none每seed 172人，5人仅缺Text；自然缺RNA路由实际触发0次（归档报告所载，不是本次重新读取患者级文件）。源码：[S0-force](Pro证据/code/s0_force_route.py)。

### E3：单模态编码与冻结融合

\[
z_i^m=\phi_m(\operatorname{mean}_{token}X_{i,in}^m),\quad
\phi_m=\mathrm{Dropout}\circ\mathrm{ReLU}\circ\mathrm{Linear}_m,\quad
h_i=\mathrm{Transformer}(\{z_i^m+d_m\};\neg f_i). \tag{E3}
\]

模型mean与E1的有效行mean不同：历史模型WSI仍含128行padding。完整donor序列先mean再projector，每模态一个融合token；eval时Dropout关闭。源码：[当前NPJC](Pro证据/code/npjc_current.py)。

### E4：末端 pooling 与 B 风险

\[
v_i=\frac{\sum_m\omega_i^m h_i^m}{\max(1,\sum_m\omega_i^m)},\quad
\eta_{it}=\mathrm{clip}(\sigma(H_c(v_i)_t),10^{-6},1-10^{-6}),\quad
S_{it}=\prod_{\tau\le t}(1-\eta_{i\tau}),\quad R_i=-\sum_tS_{it}. \tag{E4}
\]

本人有效模态权重1；检索填入位0.5；m1填入位1；仍屏蔽位0。仅调整末端pooling，不改变attention。代码实际模态顺序img/text/rna。源码：[pooling](Pro证据/code/imputed_pooling.py)、[B口径](Pro证据/code/evaluation_common_current.py)。

| 替换位置 | 必须由 Pro 评估的影响，不是本轮授权 |
| --- | --- |
| 原始 WSI encoder | 模型输入和检索key都可能变化；若同时改变donor，收益不能简单归为单一编码模块 |
| 原始 RNA/Text encoder | 本人特征、train均值、donor value须在兼容空间；旧projector维度相同也不保证语义匹配 |
| 缓存后的 token encoder/projector | 可能无需重提原始特征，但不是换基础特征提取器；需界定训练参数和对照 |
| 跨模态融合模块 | 超出单纯encoder替换，不能悄悄改 NPJ-C 骨架；只可说明边界，不落地 |

## 7. 同源证据与版本优先级

1. 本次用户锁定要求（本Pro版）优先于原始草稿的已更正描述；数字和代码事实仍须可追溯。
2. [原始需求快照](Pro证据/原始需求-innovation-Encoder.md) 保留原文；其中工具/流程指令不是本轮额外执行授权。
3. [来源清单](Pro证据/source_manifest.json) 提供绝对来源路径、来源SHA、摘录/复制方式和当前仓库HEAD；[包内哈希](Pro证据/package_manifest.json)验证附件内部内容。
4. [必要代码与配置](Pro证据/代码与来源说明.md)是只读快照；没有权重、缓存或运行资产，不应直接执行训练/评测。
5. [历史方法原文](Pro证据/实验先验知识与公式说明-历史原文.md)保留旧时点与旧绝对路径，不保证其外链可在网页读取；请使用本包相对入口。历史材料与现状冲突时列出而不静默融合。
6. 所有模型读取同一包，上一模型建议只能作为附加意见，不能替代原始证据。私有仓库链接需要授权；不能读取时使用附件，不宣称已获取证据。
7. v2只调整方法名称与整体成绩归属；包内论文/公式/结果仍为v1核验的历史快照。用户本地main.tex之后已变更，None行数值未变；不能把包内TeX称为最新工作稿，详见版本说明。

## 8. 接收者验收

- [ ] 逐项报告Prompt、本文、原SVG或同图PNG、PDF第7页、None原值和代码配置的能读/不能读状态；关键材料缺失时不假装完成审阅。
- [ ] 明白历史4/5、新encoder的目标4/5、None单场景的区别。
- [ ] 不把RNA/Text提取器身份、训练预算和原始输入可得性当作已锁定事实。
- [ ] 每个k有P/B、原始文献/代码、可行性与公平性边界；最多两个合格候选。
- [ ] 不执行训练、评测、缓存重建，不编造成绩，不代用户锁定科研方案。

这些复选项由接收者实际阅读后勾选，本次不代替 ChatGPT Pro 声称完成阅读。
