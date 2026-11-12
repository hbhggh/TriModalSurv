# TriModalSurv 论文生成、实验制表与期刊框图执行交接规范（`handoff-论文生成.md`）

> **版本**：v1.1（2026-11-11，经 `/grill-me` 策略 1️⃣ 访谈定稿：锁定 LaTeX `booktabs` 制表、Claude Design 交互微调矢量框图、Claude 初稿 + Antigravity Gemini 受控润色、本机 `nature-skills` 软链挂载与 SCI 学术版去 AI 味门禁）
> **目标期刊**：**SCI 三区 *BMC Bioinformatics***（Research Article，英文撰写，`latexmk -pdf` 零报错编译）
> **核心模型**：**`TriModalSurv`（主配置 `M6-a`：`A1` 恢复导向正交共享子空间 + `B6-LOO [in_fold_masked]` 线性基座与留一杠杆残差检索校准插件 + `C1` 训练期跨模态对齐与恢复一致性约束）**
> **路径占位符约定（遵守坑 `I05-04`，本文档零本机用户名硬编码）**：
>
> - `<REPO_ROOT>`：仓库主检出目录 `.../TriModalSurv`（检出 `main`，禁止在此改代码；仅同步 `03_index` 与本 `handoff` 文件）
> - `<DEV_WORKTREE>`：唯一开发与撰稿工作树 `.../TriModalSurv.worktrees/dev`（所有脚本、表格 `.tex`、框图 `.html/.pdf/.png`、论文 `.tex/.bib` 均在此生成与修改）
> - `<LIT_DIR>`：本地参考论文目录 `<REPO_ROOT>/../vscode 重构/Template_refactor/科研/论文阅读`（含 `Prime/Prime.pdf` 与 `M3Surv/M3Surv.pdf`）
> - `<CONDA_PYTHON>`：`protomasksurv-exp1` 环境解释器（`.../miniconda3/envs/protomasksurv-exp1/bin/python`）
> - `~/.claude/skills/`：已软链挂载的学术写作与核验技能根（含 `_shared`、`nature-writing`、`nature-polishing`、`nature-ref-verifier` 及 `artifact-page`）
>   **全局进度导航栏（双车间表格消消乐）**：`<REPO_ROOT>/03_index-故事线 A-1｜患者级动态恢复_v1.md` 锚点 `#blk-ea197a743df240a3`（兼容 `#blk-3cd4b8eddb8f4e36`）
>   **唯一故事线源头锚点**：`<REPO_ROOT>/03_index-故事线 A-1｜患者级动态恢复_v1.md` 锚点 `#blk-c2e9fbcb8af24464`（第 6 行 `## 1. 本版故事线` 及 `## A1 + B6-LOO + C1故事线`）
>   **唯一权威实验状态真源（`S_state`）**：
> - `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/results/val_dev-5c508587/val_ablation_report_v1.md`（源码 commit `5c508587deec0c88e0b85ca7e162a90ae7ba5185`；缓存 manifest sha256 `b52767a8c5f871f164762b2b180237002bf3a02adb0040a13d757ab1a75e1f6f`；config sha256 `3afdcb16e9b080a3f92e20802f3d19be3bbb0b29815e8169b3f108c3ed5f4085`；结果摘要 sha256 `832da25189ca694268faba506ea936c2324d02cea8c29d4de0453b218f29ee91`）
> - 折级原始 JSON（25 份）：`<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/results/val_dev-5c508587/val_runs/<CANCER>_fold<f>.json`
> - 同划分冻结骨架与独立单模态真源：`<DEV_WORKTREE>/experiments/I07_ps3style_backbone/results/i07-ps3-20261011/render/results.md` 及 `runs/<CANCER>/fold<f>/<arm>/test_metrics.json`
>   **停机门死锁**：全程保持 `test_access: false`；未经用户另行书面授权，**严禁读取、解锁或前向 `I08` 的 `test` 分割！**

---

## 0. 全局进度导航栏与防漂移铁律（双车间「表格消消乐」协议）<span id="blk-ad1aefbbc4c74881"></span>

### 0.1 以 `03_index` 核销沙盘作为唯一动态进度条

执行 AI 在启动前、每阶段收尾后，**必须**读取并对照 `<REPO_ROOT>/03_index-故事线 A-1｜患者级动态恢复_v1.md` 中的 **`#blk-ea197a743df240a3`（科研写论文·实验与撰稿核销沙盘）**：

1. **只读对齐当前待办态**：

   - `总表一` 第 ① 列锁死 6 大解剖学模块（`① Storyline & Gap`、`② Method`、`③ Main Experiments`、`④ Ablation & Analysis`、`⑤ Figures & Tables`、`⑥ Drafting & Polish`），**常亮不划删除线**。
   - 已带 `~~删除线~~` 的颗粒代表前序阶段已闭环（Prop. 1 核验、式 1–14 对齐、`B6-LOO` 留一杠杆修复与 `val_dev-5c508587` 25 折重跑、外部 Baseline 原文溯源排雷），**严禁回退或篡改已闭环事实**。
   - 未带删除线的待办颗粒严格按用户拍板的**「图表定锚先行，文随图定（Figure & Tables First → Draft → Controlled Polish）」**时序推进：
     - **阶段二（`P2` 自动制表，Claude Code 执行）**：更新并运行 `generate_paper_tables.py` 自动导出标准学术 LaTeX `booktabs` 三线表（正文 `Table 1–4` 与附录 `Table S1–S5`），同步编写 `export_framework_pdf.sh` 与 `check_anti_ai_and_numbers.py` 两个辅助门禁脚本；
     - **阶段四（`P4` Claude Design 交互出图与无损入文，与 `P2` 并行定锚）**：废弃旧版生硬的 Matplotlib 脚本 `generate_framework_svg.py`；在 Claude Desktop 使用 `/artifact-page`（调用 `artifact-design` + `artifact-diagramming`）生成单文件 `framework.html`（内联矢量 `<svg>` + KaTeX 数学公式）并在对话中交互微调至审美满意，再用本机 `Chrome Headless + pdfcrop` 一键转出纯矢量 `framework.pdf` 与 300 DPI `framework.png`；
     - **阶段五 A（`P5-Draft` 技术初稿，Claude Code 主笔）**：待 `Table 1–4` 与定稿 `Fig. 1` 落盘后，由 **Claude Code** 调用 `~/.claude/skills/nature-writing/SKILL.md`（轴配置：`paper_type=methods, journal=generic, language=en`）与 `nature-ref-verifier`，100% 对照代码、式 `(1)–(14)` 与定稿 `Fig. 1` 模块框名撰写 `main.tex`、`appendix.tex`、`references.bib`；
     - **阶段五 B（`P5-Polish` 同仓受控句法润色，Antigravity Gemini 执行）**：在 **Antigravity** 同一 `<DEV_WORKTREE>` 内读取 `.tex` 初稿，调用 `~/.claude/skills/nature-polishing/SKILL.md`（含 `references/latex-layout.md`），在**硬锁全部数学公式、表格引用、实验数值、统计限定词与术语账本**的前提下按 `git diff` 做受控学术润色，跑通 SCI 学术版去 AI 味黑名单门禁与 `latexmk -pdf` 零报错编译；
     - **阶段三（`P3` 贯穿核销）**：**仅在对应阶段通过全部机器断言门禁且获用户明确验收后**，由主控 AI 将 `03_index` 总表一第 ④ 列（及第 ⑤ 列状态）对应颗粒打上 `~~删除线~~` 核销，并同步 `<REPO_ROOT>/03_index-...` 与 `<DEV_WORKTREE>/03_index-...`（`diff -u` 退出码必须为 `0`）。
2. **Office Viewer (Vditor) 表格防截断硬约束（重要新发现）**：

   - 在维护 `03_index` 或任何 Markdown 表格时，**单元格内部严禁出现任何裸竖线字符 `|`（即使包裹在反引号 `` `A | B` `` 内也会被 Vditor 保存时解析为拆列分隔符并截断整行！）**。单元格内枚举表头或拼接关系时，一律改写为斜杠 `/` 或中点 `·`（例如 `` `Method / Img / RNA / Txt` `` 或 `[rna · wsi · text]`）。
   - 写入 `03_index` 前后严格遵守坑 `E38` 与 `V34`：每处字符串替换必须断言精确命中 1 次；写后间隔核对文件字节数与双端 `diff -u`。

### 0.2 全局铁律 `G0`（数据溯源与单列超参展示锁）

1. **零人工抄数（坑 `V23`）**：正文与附录所有表格单元格数值必须 100% 由 `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/tools/generate_paper_tables.py` 从磁盘 `val_runs/*.json`、`I07` 结果文件及核实常量自动生成，通过 `\input{tables/tableX.tex}` 引入 LaTeX，**严禁在 `main.tex` 或 `appendix.tex` 中手写 `\begin{tabular}` 抄录实验数字**。
2. **彻底清除旧批次与幻觉基线**：
   - 全仓严禁残留修复前旧批次 `0.6626` 或 `val_dev-f4b30740` 的数值；
   - 严禁声称数据导自不存在的 `summary.json` 或 `per_fold_metrics.csv`；
   - 严禁出现 `Prime.pdf` 原文不存在的 5 个幻觉方法（`DrFuse`、`RedCore`、`M3Care`、`MedFuse`、`ShaSpec`）。
3. **单列超参展示铁律（需求四锁死）**：
   - 在全部对比表与消融表（`Table 1, 2, 3, 4` 及 `Appendix Tables S1, S2, S3`）中，**每个方法只展示单列指标（严禁并列放 `@default` 与 `@selected` 双列）**；
   - **唯独本文主模型 `Ours: TriModalSurv (M6-a: A1 + B6-LOO [in_fold_masked] + C1)` 采用验证集选参后结果（`6-Missing Avg = 0.6657`）**；
   - **其余所有对比方法与消融变体一律固定采用未调参的默认超参结果（即 JSON 中的 `<ID>@default`，或无超参网格的 `M0-a`、`M0-b`、`M9-base`）**，并在表注与实验设置小节如实说明该评估口径。

---

## 1. 论文核心故事线与审稿防御口径（锚定 `03_index#blk-c2e9fbcb8af24464`）

### 1.1 一句话立论主线

> 在测试患者缺失部分模态（如缺少昂贵的转录组测序或完整病理报告）的真实临床场景下，**先利用恢复导向的正交投影子空间（`A1`）结合跨模态对齐与恢复一致性监督（`C1`），将缺失模态中适合跨模态预测的 32 维共享预后信号与 224 维模态特异噪声严格正交解耦；再在推理期基于患者自身可见模态，通过“模式特定全局线性趋势（`B1`）+ 经留一杠杆去偏的相似训练患者预测残差核注意力校准与零参数 IQR 密度门控（`B6-LOO`）”实现因人而异的动态恢复，同时对完整三模态患者保持零损恒等直通。**

### 1.2 两大临床与方法痛点证伪（`Introduction` & `Methods` 核心动机）

1. **痛点一：静态占位填充在缺失位上丧失患者间判别力（Proposition 1）**
   - 现有多模态生存管线在推理期常对缺失模态填入全零向量（Zero-Fill, `M0-a`）或训练集均值向量（Train-Mean, `M0-b`）。
   - **代数恒等性质（Prop. 1）**：对于任意具有线性风险头 $h_i = \sum_{m \in \mathcal{M}} p_{i,m}^\top w_m + b$ 的冻结融合骨架，将缺失模态 $u \notin \Omega$ 替换为任意跨患者常数向量 $c_u \in \mathbb{R}^d$（无论是 $0$ 还是 $\mu_u^F$），仅在所有同模式患者的对数风险分上叠加同一个常数偏移 $\sum_{u \notin \Omega} c_u^\top w_u$，**患者间的相对风险排序与 C-index 完全不变**（实测 25 折同模式逐患者风险差极差 $\le 1.3 \times 10^{-6}$，`M0-a` 与 `M0-b` 的 `6-Missing Avg` 同为 `0.6519`）。静态占位无法利用患者手头可见模态恢复个体化的缺失表征。
2. **痛点二：高维全空间直接恢复参数冗余、对正则强度高度敏感，易注入模态特异幻觉噪声**
   - 池化特征 $p_{i,m} \in \mathbb{R}^{256}$ 中既包含跨模态共享的肿瘤生物学信号，也包含大量仅能由该模态自身观测到的特异细节或噪声（如局部染色伪影、单通路随机波动、报告文书措辞）。
   - 若不加子空间解耦而直接在 256 维全空间回归恢复全部维度，9 组模式特定映射共需 **$788,736$** 个参数，相对于单癌种单折仅数百例训练样本极易过拟合、对岭正则系数高度敏感：**在默认超参下直接产生明显负迁移**（`M7@default = 0.6406 < M0-a = 0.6519`；256 维闭式岭回归 `M1-a@default = 0.6423`，风险残差岭回归 `M1-b@default = 0.6394`）。
   - 相反，引入 32 维正交共享子空间 `A1` 后，子空间秩仅占全维度的 **$12.5\%$**（$32/256$），显式截断其余 **$224$** 维正交补噪声，Stage 2a 总可训练参数量降至 **$37,152$**（仅为全维线性恢复 `788,736` 参数量的 **$4.71\%$**，压缩率达 **$95.29\%$**），**无需任何验证集网格搜参即可稳定超越静态填充基线**（`M10-a@default = 0.6559 > 0.6519`）。
   - *(审稿防御红线：严禁夸大写成“256 维全空间在任何超参下必然负迁移”，必须准确写成“对正则化强度高度敏感、默认超参下发生负迁移，而低秩正交子空间免调参即获稳健正收益”)*。

### 1.3 锁定的三条核心贡献（`Introduction` 末段 3 个 Bullet Points）

1. **恢复导向的 Cayley 正交共享子空间解耦（`A1`）**：在冻结三模态骨干池化层与风险头之间构建列正交投影基 $U_m \in \mathbb{R}^{256 \times 32}$（$U_m^\top U_m = I_{32}$，25/25 折统一锁定 $r=32$），实现代数级防混叠（$\langle p_m^{\text{sha}}, p_m^{\text{res}} \rangle \equiv 0$）、可见模态 100% 原样保真直通与缺失模态 224 维正交补噪声截断，将恢复模块参数量压缩 95.3%（从 $788,736$ 降至 $37,152$）。
2. **训练期跨模态对齐与恢复一致性联合约束（`C1`）**：设计零推理开销的训练期三项协同正则——正交重构能量锚定 $\mathcal{L}_{\text{anchor}}$、全模态共享方向余弦对齐 $\mathcal{L}_{\text{modal}}$ 与停梯度恢复一致性损失 $\mathcal{L}_{\text{cons}}$，在不引入任何推理计算负担的前提下驱动 $U_m$ 旋转至高预后能量占比（风险权重能量占比 $\rho_r \in [62.8\%, 69.5\%]$，远超随机期望 $12.5\%$）且跨模态可预测的共享方向。
3. **推理期零重训留一杠杆残差检索与自适应门控插件（`B6-LOO`）**：在固定 Stage 2a 潜空间坐标系与模式特定线性趋势基座（`B1`）之上，提出无需梯度反传的插件式患者级局部校准算子——通过闭式岭回归 Hat 矩阵对角元 $(1 - H_{jj}^\Omega)^{-1}$ 对 `B1` 训练残差做留一杠杆去偏，结合逐可见模态平均余弦 Top-$K$ 检索与训练集最近邻四分位距（IQR）自适应密度门控，在 5 个 TCGA 队列 25 折验证中取得 `0.6657` 的 `6-Missing Avg`（`22/25` 折胜过静态基线，单侧 Wilcoxon $p = 1.25 \times 10^{-4}$，5/5 癌种全部正提升），并具备离群样本自动回退 `B1` 的安全边界。

### 1.4 严格区分两种“残差”术语（全文英文命名禁止混用）

- **`A1` 的正交补剩余分量（Orthogonal Complement Component）**：英文固定称作 *orthogonal complement* 或 *modality-specific residual subspace*，记为 $x_{i,m}^{\text{res}} = (I_{256} - U_m U_m^\top) x_{i,m} \in \mathbb{R}^{256}$（对应代码 `x_orth_res`，位于 $\operatorname{col}(U_m)^\perp$，缺失模态直接置零截断，绝不恢复）。
- **`B6-LOO` 的潜空间留一预测残差（LOO Prediction Error Residual）**：英文固定称作 *LOO-calibrated prediction residual*，记为 $e_{j,u}^{\text{LOO},\Omega} \in \mathbb{R}^{32}$（对应代码 `e_pool`，位于 $\operatorname{col}(U_u)$ 内部 32 维共享坐标空间，代表全局线性映射 `B1` 未解释的局部非线性个体偏差）。

---

## 2. 【需求 1️⃣】`A1`、`C1`、`B` 三大算子精确数学公式与端到端维度对齐规范

> **代码真源逐行绑定**：本节所有公式、上下标、归一化分母与张量维度已 100% 核对 `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/` 下的 `contract.py`、`operators.py`、`losses.py`、`train_eval.py` 与 `config.yaml`。撰写 `Methods`（`Sec. 3`）与绘制 `Fig. 1` 时必须逐符号严格一致，禁止凭记忆改写！

### 2.1 全局集合、索引与维度常数定义

- **三模态有序元组（顺序由风险头权重切片钉死，严禁调换）**：
  $$
  \mathcal{M} = (\text{rna},\ \text{wsi},\ \text{text}), \qquad |\mathcal{M}| = 3
  $$
- **池化特征维度与共享子空间秩**：
  $$
  d = 256, \qquad r = 32 \quad (\text{正交补维度 } d - r = 224,\ \text{风险头输入维度 } 3d = 768)
  $$
- **7 种模态可用视角与 6 种缺失模式**：
  - 完整视角：$\Omega = \mathcal{M}$（记作 `full`）；
  - 6 种缺失模式集合 $\mathcal{P}_{\text{miss}}$（即非空真子集 $\Omega \subsetneq \mathcal{M}$）：
    $$
    \mathcal{P}_{\text{miss}} = \bigl\{\underbrace{\{\text{rna}\},\ \{\text{wsi}\},\ \{\text{text}\}}_{k = |\Omega| = 1\ (\text{Only-One: OR, OI, OT})},\ \underbrace{\{\text{rna},\text{wsi}\},\ \{\text{rna},\text{text}\},\ \{\text{wsi},\text{text}\}}_{k = |\Omega| = 2\ (\text{Leave-One-Out: LT, LI, LR})}\bigr\}
    $$
  - 对任意缺失模式 $\Omega \in \mathcal{P}_{\text{miss}}$，可见模态按 $\mathcal{M}$ 子序列保序排列，个数为 $k = |\Omega| \in \{1, 2\}$；待恢复缺失模态集合为 $\mathcal{U}(\Omega) = \mathcal{M} \setminus \Omega$，个数为 $3 - k \in \{2, 1\}$。全集共有 $3 \times 2 + 3 \times 1 = 9$ 个有序恢复对 $(\Omega, u)$。
- **样本索引**：单癌种单折训练集患者数记为 $N_{\text{tr}}$（索引 $j \in \{1, \dots, N_{\text{tr}}\}$），当前批/查询集患者数记为 $B$（索引 $i \in \{1, \dots, B\}$；Stage 2a 全批量训练时 $B = N_{\text{tr}}$）。

### 2.2 预提取多视角池化特征、硬旁路路由与模式专属中心化（式 1）

设冻结的 `I07` PS3-style 骨干网络处于 `eval()` 模式（全部参数与线性风险头 $w \in \mathbb{R}^{768}, b \in \mathbb{R}$ 满足 `requires_grad=False`）。由于自注意力在剔除缺失模态 token 后上下文分布会发生偏移（$p_{i,m}^\Omega \neq p_{i,m}^F$），对患者 $i$ 在完整输入与缺失模式 $\Omega$ 下的池化输出分别记为 $p_{i,m}^F \in \mathbb{R}^{256}$ 与 $p_{i,m}^\Omega \in \mathbb{R}^{256}$（$m \in \Omega$）。

**完整模态硬旁路与路由准则（式 1a，对齐 `operators.py:8-9`）**：

$$
h_i(\Omega) =
\begin{cases}
\bigl[p_{i,\text{rna}}^F \,\|\, p_{i,\text{wsi}}^F \,\|\, p_{i,\text{text}}^F\bigr] w + b \equiv h_i^{\text{I07,full}}, & \text{if } \Omega = \mathcal{M}\ (\text{Identity Bypass } D_0), \\[6pt]
\text{head\_in}_i^\Omega \cdot w + b, & \text{if } \Omega \in \mathcal{P}_{\text{miss}},
\end{cases}
\tag{1a}
$$

其中 $\|$ 表示沿特征维拼接（行向量视角 $[1, 256] \times 3 \to [1, 768]$）。

**仅由本折训练集统计的模式专属中心化（式 1b，对齐 `operators.py:31-43`）**：

$$
\mu_m^F = \frac{1}{N_{\text{tr}}} \sum_{j=1}^{N_{\text{tr}}} p_{j,m}^F \in \mathbb{R}^{256}, \qquad
\mu_{\Omega,m}^\Omega = \frac{1}{N_{\text{tr}}} \sum_{j=1}^{N_{\text{tr}}} p_{j,m}^\Omega \in \mathbb{R}^{256} \quad (\forall m \in \Omega)
$$

$$
x_{i,m}^F = p_{i,m}^F - \mu_m^F \in \mathbb{R}^{256}, \qquad
x_{i,m}^\Omega = p_{i,m}^\Omega - \mu_{\Omega,m}^\Omega \in \mathbb{R}^{256} \quad (\forall m \in \Omega)
\tag{1b}
$$

> **维度与防泄漏要点**：可见输入 $p_{i,m}^\Omega$ 必须减去该缺失模式专属的训练集均值 $\mu_{\Omega,m}^\Omega$ 以消除注意力上下文偏移；而完整目标与解码回投统一使用完整前向训练集均值 $\mu_u^F$。验证/测试集严格复用本折训练集算出的 $(\mu^F, \mu^\Omega)$。

### 2.3 算子 `A1`：恢复导向的 Cayley 正交共享子空间（式 2–5）

对每个模态 $m \in \mathcal{M}$，维护一个列正交基矩阵 $U_m \in \mathbb{R}^{d \times r} = \mathbb{R}^{256 \times 32}$，满足 Stiefel 流形约束：

$$
U_m^\top U_m = I_{32} \in \mathbb{R}^{32 \times 32}, \qquad \|U_m^\top U_m - I_{32}\|_{\max} < 10^{-5}
\tag{2}
$$

- **初始化与数值稳定实现（对齐 `operators.py:48-85`，坑 `E50`）**：$U_m$ 初始化为本折训练集中心化矩阵 $X_{\text{tr},m}^F \in \mathbb{R}^{N_{\text{tr}} \times 256}$ 的前 $r=32$ 个确定性定向右奇异向量（PCA 主方向），内部通过 `float64` 精度的 **Cayley 正交参数化**（`orthogonal_map='cayley'`）更新，前向时转为 `float32` 张量 $U_m \in \mathbb{R}^{256 \times 32}$。

**正交防混叠分解与低维坐标投影（式 3）**：
对任意中心化特征 $x_{i,m} \in \mathbb{R}^{256}$，幂等正交投影算子 $P_m = U_m U_m^\top \in \mathbb{R}^{256 \times 256}$ 将其唯一正交分解为可恢复共享分量与模态特异正交补分量：

$$
x_{i,m} = \underbrace{U_m z_{i,m}}_{x_{i,m}^{\text{sha}} \in \operatorname{col}(U_m)} + \underbrace{(I_{256} - U_m U_m^\top) x_{i,m}}_{x_{i,m}^{\text{res}} \in \operatorname{col}(U_m)^\perp}, \qquad \langle x_{i,m}^{\text{sha}},\, x_{i,m}^{\text{res}} \rangle \equiv 0
\tag{3a}
$$

写成批量矩阵形式（批大小 $B$，对齐 `operators.py:162, 165`）：

$$
Z_{m}^\Omega = X_{m}^\Omega U_m \in \mathbb{R}^{B \times 32} \quad (m \in \Omega), \qquad
Z_{m}^F = X_{m}^F U_m \in \mathbb{R}^{B \times 32} \quad (m \in \mathcal{M})
\tag{3b}
$$

其中单样本行向量记为 $z_{i,m}^\Omega = (x_{i,m}^\Omega)^\top U_m \in \mathbb{R}^{32}$（若按列向量习惯记作 $z_{i,m}^\Omega = U_m^\top x_{i,m}^\Omega \in \mathbb{R}^{32}$，全文须在一处声明约定并保持一致；推荐使用列向量数学记号并在括号内标注批量张量形状 `[B, 32]`）。

**缺失模态正交补截断与无新参数解码回投（式 4，对齐 `operators.py:167`）**：
给定算子 `B` 恢复出的缺失模态 $u \in \mathcal{U}(\Omega)$ 的 32 维共享坐标 $\hat{z}_{i,u}^\Omega \in \mathbb{R}^{32}$（批量形状 `[B, 32]`），显式令缺失模态的 224 维正交补分量 $\hat{x}_{i,u}^{\text{res},\Omega} = 0$，利用转置正交基 $U_u$ 无参数回投至原 256 维池化空间：

$$
\hat{p}_{i,u}^\Omega = \mu_u^F + U_u \hat{z}_{i,u}^\Omega \in \mathbb{R}^{256} \qquad \bigl(\text{批量形式：}\hat{P}_u^\Omega = \mathbf{1}_B (\mu_u^F)^\top + \hat{Z}_u^\Omega U_u^\top \in \mathbb{R}^{B \times 256}\bigr)
\tag{4}
$$

**可见模态原样直通与风险头保序拼接（式 5，对齐 `contract.py:267-272` `W1-4`）**：
对可见模态 $m \in \Omega$，**绝不用低秩重构值覆盖原特征**，而是 100% 原样保留 $p_{i,m}^\Omega$（等价于完整保留 $x_{i,m}^{\text{sha}} + x_{i,m}^{\text{res}}$ 全部个体预后细节）；仅在缺失槽位 $u \notin \Omega$ 填入 $\hat{p}_{i,u}^\Omega$，严格按 $(\text{rna}, \text{wsi}, \text{text})$ 顺序组装 768 维输入送入冻结风险头：

$$
\tilde{p}_{i,m}^\Omega =
\begin{cases}
p_{i,m}^\Omega \in \mathbb{R}^{256}, & \text{if } m \in \Omega\ (\text{Visible Passthrough}), \\
\hat{p}_{i,m}^\Omega \in \mathbb{R}^{256}, & \text{if } m \notin \Omega\ (\text{Subspace Recovered}),
\end{cases}
\tag{5a}
$$

$$
\text{head\_in}_i^\Omega = \bigl[\tilde{p}_{i,\text{rna}}^\Omega \,\|\, \tilde{p}_{i,\text{wsi}}^\Omega \,\|\, \tilde{p}_{i,\text{text}}^\Omega\bigr] \in \mathbb{R}^{768}, \qquad
h_i^\Omega = (\text{head\_in}_i^\Omega)^\top w + b \in \mathbb{R}
\tag{5b}
$$

### 2.4 算子 `B`：Stage 2a 模式特定线性基座 `B1` + Stage 2b 留一杠杆残差校准插件 `B6-LOO`（式 6–10）

#### (1) Stage 2a 全局线性趋势基座 `B1`（式 6，对齐 `operators.py:98-122`）

对缺失模式 $\Omega \in \mathcal{P}_{\text{miss}}$（可见模态数 $k = |\Omega| \in \{1, 2\}$），将患者 $i$ 的可见共享坐标按 $\mathcal{M}$ 顺序拼接为输入向量：

$$
b_{\text{in},i}^\Omega = \operatorname{Concat}_{m \in \Omega}\bigl(z_{i,m}^\Omega\bigr) \in \mathbb{R}^{k r} = \mathbb{R}^{32k} \qquad \bigl(\text{批量形状 } [B, 32k] \in \{[B, 32],\ [B, 64]\}\bigr)
\tag{6a}
$$

对每个缺失目标模态 $u \in \mathcal{U}(\Omega)$，配置零初始化（`nn.init.zeros_`）的线性映射参数 $R_{\Omega \to u} \in \mathbb{R}^{r \times kr} = \mathbb{R}^{32 \times 32k}$ 与偏置 $b_{\Omega,u} \in \mathbb{R}^{32}$，输出群体级全局线性预测：

$$
\hat{z}_{i,u}^{\text{B1},\Omega} = R_{\Omega \to u} b_{\text{in},i}^\Omega + b_{\Omega,u} \in \mathbb{R}^{32} \qquad \bigl(\text{批量形式：}\hat{Z}_u^{\text{B1},\Omega} = B_{\text{in}}^\Omega R_{\Omega \to u}^\top + \mathbf{1}_B b_{\Omega,u}^\top \in \mathbb{R}^{B \times 32}\bigr)
\tag{6b}
$$

> **零初始化安全起点性质**：训练第 0 步时 $R_{\Omega \to u} = 0, b_{\Omega,u} = 0 \implies \hat{z}_{i,u}^{\text{B1},\Omega} = 0 \implies \hat{p}_{i,u}^\Omega = \mu_u^F$，即模型精确从训练集均值填充基线 `M0-b` 出发平滑优化。
> **参数量核验（`contract.py:n_params(256, 32)`）**：
>
> - $|\Theta_{\text{A1}}| = 3 \times (256 \times 32) = 24,576$；
> - $|\Theta_{\text{B1}}| = 6 \times (32 \times 32 + 32) + 3 \times (32 \times 64 + 32) = 6,336 + 6,240 = 12,576$；
> - 总可训练参数量 $|\Theta_{\text{Stage2a}}| = 24,576 + 12,576 = \mathbf{37,152}$（对比 256 维全空间 9 组线性映射参数量 $6 \times (256^2 + 256) + 3 \times (256 \times 512 + 256) = \mathbf{788,736}$，仅占 **$4.71\%$**，减少 **$95.29\%$**）。

#### (2) Stage 2b 留一法（LOO）Hat 杠杆去偏训练残差池构造（式 7–8，对齐 `operators.py:248-291`）

Stage 2a 收敛并按本折 `val` 锁定最佳 $(U_m, R_{\Omega \to u}, b_{\Omega,u})$ 后，**冻结全部参数**进入 Stage 2b。若直接使用 `B1` 在训练集上的样本内残差 $z_{j,u}^F - \hat{z}_{j,u}^{\text{B1},\Omega}$，高杠杆边缘样本因在训练中过度拉拽回归超平面而呈现虚小的表观残差。为此，我们在本折训练集设计矩阵 $B_{\text{in,tr}}^\Omega \in \mathbb{R}^{N_{\text{tr}} \times 32k}$ 上中心化得到 $X_c = B_{\text{in,tr}}^\Omega - \mathbf{1}_{N_{\text{tr}}} \bar{b}_{\text{in,tr}}^{\Omega \top} \in \mathbb{R}^{N_{\text{tr}} \times 32k}$，以固定岭系数 $\lambda_{\text{hat}} = 1.0$（`float64` 精度）计算带截距闭式岭回归的 Hat 矩阵对角线杠杆值 $H_{jj}^\Omega$：

$$
H_{jj}^\Omega =
\begin{cases}
\bigl[X_c (X_c^\top X_c + \lambda_{\text{hat}} I_{32k})^{-1} X_c^\top\bigr]_{jj} + \dfrac{1}{N_{\text{tr}}}, & \text{if } 32k \le N_{\text{tr}}\ (\text{Primal}), \\[10pt]
\bigl[K_c (K_c + \lambda_{\text{hat}} I_{N_{\text{tr}}})^{-1}\bigr]_{jj} + \dfrac{1}{N_{\text{tr}}}, & \text{if } 32k > N_{\text{tr}}\ (\text{Dual, } K_c = X_c X_c^\top),
\end{cases}
\tag{7}
$$

随后按 PRESS 留一去偏原理，将本折每名训练患者 $j \in \{1, \dots, N_{\text{tr}}\}$ 的 `B1` 预测残差除以留一缩放因子 $\max(1 - H_{jj}^\Omega, 10^{-4})$，构建无泄漏留一校准残差池（对应主模型 `M6-a: in_fold_masked`）：

$$
e_{j,u}^{\text{LOO},\Omega} = \frac{z_{j,u}^F - \hat{z}_{j,u}^{\text{B1},\Omega}}{\max\bigl(1 - H_{jj}^\Omega,\ 10^{-4}\bigr)} \in \mathbb{R}^{32}, \qquad
E_{\text{pool}}^{\Omega,u} = \bigl[e_{1,u}^{\text{LOO},\Omega};\, \dots;\, e_{N_{\text{tr}},u}^{\text{LOO},\Omega}\bigr] \in \mathbb{R}^{N_{\text{tr}} \times 32}
\tag{8}
$$

#### (3) 逐可见模态平均余弦检索、自查询掩码与 IQR 自适应密度门控（式 9–10，对齐 `operators.py:182-244, 311-316`）

对任意查询患者 $i$ 与训练锚点患者 $j \in \{1, \dots, N_{\text{tr}}\}$，在当前缺失模式 $\Omega$ 下计算**逐可见模态 L2 归一化后的平均余弦相似度**（`per_modality_mean_cos`），并按 `patient_id` 强制执行自查询屏蔽（防止训练集内统计或检索发生自泄漏）：

$$
\tilde{z}_{i,m}^\Omega = \frac{z_{i,m}^\Omega}{\max(\|z_{i,m}^\Omega\|_2,\ 10^{-8})} \in \mathbb{R}^{32}, \qquad
s_{ij}^\Omega =
\begin{cases}
-\infty, & \text{if } \text{id}_i = \text{id}_j, \\[6pt]
\dfrac{1}{|\Omega|} \sum\limits_{m \in \Omega} (\tilde{z}_{i,m}^\Omega)^\top \tilde{z}_{j,m}^\Omega, & \text{otherwise},
\end{cases}
\tag{9a}
$$

由此得到相似度矩阵 $S^\Omega = [s_{ij}^\Omega] \in \mathbb{R}^{B \times N_{\text{tr}}}$。对每个查询 $i$ 取相似度最高的 Top-$K$ 训练邻居索引集 $\mathcal{N}_K^\Omega(i)$（$|\mathcal{N}_K^\Omega(i)| = K$），经温度 $\tau > 0$ 计算核注意力权重 $a_{ij}^\Omega$，并提取最近邻相似度 $s_{i,(1)}^\Omega$：

$$
a_{ij}^\Omega = \frac{\exp(s_{ij}^\Omega / \tau)}{\sum_{l \in \mathcal{N}_K^\Omega(i)} \exp(s_{il}^\Omega / \tau)} \quad \bigl(j \in \mathcal{N}_K^\Omega(i),\ A^\Omega \in \mathbb{R}^{B \times K}\bigr), \qquad
s_{i,(1)}^\Omega = \max_{1 \le j \le N_{\text{tr}}} s_{ij}^\Omega \in \mathbb{R}
\tag{9b}
$$

**零可学习参数的 IQR 自适应密度门控（式 9c）**：在本折训练集内部计算留一最近邻相似度集合 $\{s_{q,(1)}^{\text{train-LOO},\Omega}\}_{q=1}^{N_{\text{tr}}}$（对角线已置 $-\infty$）的 25%、50%、75% 分位数 $Q_{0.25}^\Omega, Q_{0.50}^\Omega, Q_{0.75}^\Omega$，令阈值 $\delta_\Omega = Q_{0.50}^\Omega$、四分位距 $\operatorname{IQR}_\Omega = Q_{0.75}^\Omega - Q_{0.25}^\Omega$，由正态一致尺度常数 $1.349$ 确定自适应斜率 $\gamma_\Omega$ 并裁剪至安全区间 $[5.0, 30.0]$：

$$
\delta_\Omega = Q_{0.50}^\Omega, \qquad
\gamma_\Omega = \operatorname{clip}\!\left(\frac{1.349}{\max(\operatorname{IQR}_\Omega,\ 10^{-3})},\ 5.0,\ 30.0\right), \qquad
\alpha_i^\Omega = \alpha_{\max} \cdot \sigma\Bigl(\gamma_\Omega \bigl(s_{i,(1)}^\Omega - \delta_\Omega\bigr)\Bigr) \in [0, \alpha_{\max}]
\tag{9c}
$$

其中 $\sigma(u) = (1 + e^{-u})^{-1}$，批量门控张量形状为 $[B, 1]$。

**最终患者级动态恢复输出（式 10）**：

$$
\hat{z}_{i,u}^\Omega = \hat{z}_{i,u}^{\text{B1},\Omega} + \alpha_i^\Omega \sum_{j \in \mathcal{N}_K^\Omega(i)} a_{ij}^\Omega \, e_{j,u}^{\text{LOO},\Omega} \in \mathbb{R}^{32} \qquad \bigl(\text{批量形状 } [B, 32]\bigr)
\tag{10}
$$

> **双重安全退化定理（Methods 必写亮点）**：
>
> 1. **网格保底退化**：验证集候选网格包含 $\alpha_{\max} = 0.0$（$K \in \{3, 5, 10, 15, 20\}$，$\tau \in \{0.02, 0.05, 0.1, 0.2\}$，$\alpha_{\max} \in \{0.0, 0.25, 0.5, 1.0\}$；固定默认超参 `@default` 为 $K=10, \tau=0.1, \alpha_{\max}=0.5$）。当 $\alpha_{\max}=0$ 时，$\alpha_i^\Omega \equiv 0$，`B6-LOO` 逐患者逐浮点数精确退化为 `M2 (A1 + B1 + C1)`；
> 2. **离群样本阻尼**：当测试查询患者在潜空间处于稀疏孤立区（$s_{i,(1)}^\Omega \ll \delta_\Omega$）时，$\alpha_i^\Omega \to 0$ 自动抑制不可靠远邻残差的注入，平滑回退至稳健的全局线性预测 $\hat{z}_{i,u}^{\text{B1},\Omega}$。

### 2.5 算子 `C1`：训练期跨模态对齐与恢复一致性损失（式 11–14，对齐 `losses.py:20-52`）

**关键边界（Claude Code 审查重点）**：`C1` 仅在 **Stage 2a 训练 `A1 + B1`** 时计算并反传梯度，监督对象是 **`B1` 的输出 $\hat{z}_{i,u}^{\text{B1},\Omega}$**（绝不经过 `B6-LOO`），推理期完全不执行（零额外参数、零推理开销）：

1. **六种缺失模式等权平均 Cox 偏似然损失（式 11，`Full` 视角不进入损失）**：

   $$
   \mathcal{L}_{\text{Cox}}^{\text{missing}} = \frac{1}{|\mathcal{P}_{\text{miss}}|} \sum_{\Omega \in \mathcal{P}_{\text{miss}}} \mathcal{L}_{\text{Cox}}\bigl(\{h_i^{\text{B1},\Omega}\}_{i=1}^{N_{\text{tr}}},\, \{t_i, c_i\}_{i=1}^{N_{\text{tr}}}\bigr), \qquad |\mathcal{P}_{\text{miss}}| = 6
   \tag{11}
   $$
2. **正交子空间重构能量锚定损失（式 12，`losses.py:28-35`，严禁误写为风险蒸馏！）**：

   $$
   \mathcal{L}_{\text{anchor}} = \frac{1}{3 N_{\text{tr}} d} \sum_{m \in \mathcal{M}} \sum_{i=1}^{N_{\text{tr}}} \bigl\|x_{i,m}^F - U_m U_m^\top x_{i,m}^F\bigr\|_2^2, \qquad d = 256
   \tag{12}
   $$
3. **跨模态共享方向余弦对齐损失（式 13，`C1-a`，`losses.py:38-44`）**：
   记三对模态组合 $\mathcal{P}_2 = \{(\text{rna}, \text{wsi}),\, (\text{rna}, \text{text}),\, (\text{wsi}, \text{text})\}$，推动同一患者三模态的完整共享坐标 $z_{i,m}^F = U_m^\top x_{i,m}^F \in \mathbb{R}^{32}$ 方向一致：

   $$
   \mathcal{L}_{\text{modal}} = \frac{1}{3 N_{\text{tr}}} \sum_{(m,n) \in \mathcal{P}_2} \sum_{i=1}^{N_{\text{tr}}} \left(1 - \frac{\langle z_{i,m}^F,\, z_{i,n}^F \rangle}{\max(\|z_{i,m}^F\|_2 \|z_{i,n}^F\|_2,\ 10^{-8})}\right)
   \tag{13}
   $$
4. **停梯度恢复一致性损失与 Stage 2a 总目标（式 14，`C1-b`，`losses.py:47-52`）**：
   对全部 9 个 $(\Omega, u)$ 恢复对（$\Omega \in \mathcal{P}_{\text{miss}}, u \in \mathcal{U}(\Omega)$），约束 `B1` 恢复坐标逼近真实完整共享坐标，并对目标侧施加停梯度算子 $\operatorname{sg}(\cdot)$（`detach()`）以防正交基 $U_u$ 向零坍缩：

   $$
   \mathcal{L}_{\text{cons}} = \frac{1}{9 N_{\text{tr}} r} \sum_{\Omega \in \mathcal{P}_{\text{miss}}} \sum_{u \in \mathcal{U}(\Omega)} \sum_{i=1}^{N_{\text{tr}}} \bigl\|\hat{z}_{i,u}^{\text{B1},\Omega} - \operatorname{sg}(z_{i,u}^F)\bigr\|_2^2, \qquad r = 32
   \tag{14a}
   $$

   $$
   \mathcal{L}_{\text{total}} = \mathcal{L}_{\text{Cox}}^{\text{missing}} + \lambda_a \mathcal{L}_{\text{anchor}} + \lambda_m \mathcal{L}_{\text{modal}} + \lambda_c \mathcal{L}_{\text{cons}}
   \tag{14b}
   $$

   **锁定权重与优化超参（25/25 折一致，`config.yaml:82-104`）**：$\lambda_a = 1.0$，$\lambda_m = 0.1$，$\lambda_c = 1.0$；全批量 AdamW（`lr = 1e-3`, `weight_decay = 0.0`, `max_epochs = 200`, `seed = 2026`），每折按验证集六种缺失模式平均 Cox 损失 `val_cox_missing_mean` 最小选取最佳 epoch。

### 2.6 对照与消融变体的精确算子公式速查（供 `Methods` 末小节或 `Appendix` 准确引用）

- **`M1-a` (`B0`: 256-d Full-Space Ridge)**：无 `A1/C1`，直接在中心化 256 维空间拟合带截距闭式岭回归 $\operatorname{Concat}_{m\in\Omega}(x_{i,m}^\Omega) \mapsto x_{i,u}^F$（`@default` 岭系数 $\lambda = 1.0$）。
- **`M1-b` (`C0`: Risk-Residual Ridge)**：无 `A1/C1`，直接以冻结风险头缺失风险差 $\sum_{u \notin \Omega} (x_{j,u}^F)^\top w_u \in \mathbb{R}$ 为标量目标拟合闭式岭回归（`@default` $\lambda = 1.0$）。
- **`M7` (`w/o A1`: 256-d Full-Space `B6-LOO`)**：在 `B0` 的 256 维 PRESS 精确留一残差池上执行逐模态余弦 Top-$K$ 检索与 IQR 门控校准（`@default`: $\lambda=1.0, K=10, \tau=0.1, \alpha_{\max}=0.5$）。
- **`M9` (`A5`: Frozen PCA-32 + `B6-LOO`)**：冻结初始训练 PCA 基 $U_m^{\text{PCA}}$（不经梯度旋转，故 $\mathcal{L}_{\text{anchor}}, \mathcal{L}_{\text{modal}}$ 为常数），仅训练 `B1` 后挂载 `B6-LOO`。
- **`M3` (`A1 + B3 + C1`: Direct Neighbor Aggregation)**：去掉全局线性趋势 `B1`，直接用核注意力聚合训练邻居完整坐标 $\hat{z}_{i,u}^{\text{B3},\Omega} = \sum_{j \in \mathcal{N}_K^\Omega(i)} a_{ij}^\Omega z_{j,u}^F$（`@default`: $K=10, \tau=0.1$）。
- **`M4-a` (`B5-MapPrecision`) / `M4-b` (`B5-DirectCoord`)**：双模态可见时按单模态预测均方误差倒数精度 $\tau_{m \to u} = \sigma_{\text{prior}}^2 / \max(\sigma_{m \to u}^2, 10^{-6})$ 做高斯后验收缩 $\hat{z}_u = \frac{\sum_{m \in \Omega} \tau_m \tilde{z}_m}{1 + \sum_{m \in \Omega} \tau_m}$（`M4-a` 中 $\tilde{z}_m$ 为单模态 `B1` 预测，`M4-b` 中 $\tilde{z}_m = z_m^\Omega$）。
- **`M5` (`B6-Naive`)**：不做 $(1 - H_{jj}^\Omega)^{-1}$ 留一杠杆去偏（直接使用原始样本内残差 $z_{j,u}^F - \hat{z}_{j,u}^{\text{B1},\Omega}$），且去掉 IQR 自适应密度门控（令 $\alpha_i^\Omega \equiv \alpha_{\max}$，`train_eval.py:194-198`）。
- **`M6-b` (`B6-LOO [exact_loo_hat]`)**：基座仍为梯度训练的 `B1`，但残差池改由固定 $U_m$ 上闭式岭回归（$\lambda_{\text{hat}}=1.0$）的精确 PRESS 残差生成（预测器与残差池生成源不一致，效果 `0.6583/@default`、`0.6621/tuned` 均低于同源去偏的 `M6-a`）。

### 2.7 18 个核心张量端到端维度与梯度契约总表（100% 映射 `config.yaml:tensors`）

| 序号 | 代码张量键名   | 数学记号                                                                                                                                                                                                                                                                                                                                                                                                   | 代入常数后的精确形状（$d=256, r=32, k\in\{1,2\}$）                                                 |                                `dtype`                                | 所在阶段与物理含义                                                           | Stage 2a 训练梯度 | Stage 2b 推理梯度 |
| :--: | :------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------: | :--------------------------------------------------------------------------- | :----------------: | :---------------: |
|  1  | `p_full`     | $P_m^F$                                                                                                                                                                                                                                                                                                                                                                                                  | `[B, 256]`                                                                                         |                               `float32`                               | 冻结`I07` 完整三模态前向 `pooled[m]`                                     |     `False`     |     `False`     |
|  2  | `p_vis`      | $P_m^\Omega$ | `[B, 256]`（$m \in \Omega$）                                                                                                                                                                                                                                                                                                                                                          | `float32`                                                                                          |         冻结`I07` 缺失模式 $\Omega$ 前向可见 `pooled[m]`         | `False`                                                                    |     `False`     |                  |
|  3  | `mu_full`    | $\mu_m^F$                                                                                                                                                                                                                                                                                                                                                                                                | `[256]`                                                                                            |                               `float32`                               | 本折`train` 上 $P_m^F$ 均值（目标中心化与解码）                          |     `False`     |     `False`     |
|  4  | `mu_pattern` | $\mu_{\Omega,m}^\Omega$                                                                                                                                                                                                                                                                                                                                                                                  | `[256]`（共 $3\times 1 + 3\times 2 = 9$ 个向量）                                                 |                               `float32`                               | 本折`train` 上按 $(\Omega, m)$ 统计的可见输入均值                        |     `False`     |     `False`     |
|  5  | `U`          | $U_m$ | `[256, 32]`（每模态 1 套，共 3 套；内部 `float64` Cayley） | `float32` | `A1` 列正交共享基（$U_m^\top U_m = I_{32}$）                                                                                                                                                                                                                                                                  | **`True`**                                                                                   |                                `False`                                |                                                                              |                    |                  |
|  6  | `z_vis`      | $Z_m^\Omega$ | `[B, 32]`（$m \in \Omega$）                                                                                                                                                                                                                                                                                                                                                           | `float32`                                                                                          |  `A1` 可见模态共享坐标 $(P_m^\Omega - \mu_{\Omega,m}^\Omega) U_m$  | **`True`**                                                           |     `False`     |                  |
|  7  | `z_full`     | $Z_m^F$ | `[B, 32]`（$m \in \mathcal{M}$）                                                                                                                                                                                                                                                                                                                                                           | `float32`                                                                                          | `A1` 完整模态共享坐标 $(P_m^F - \mu_m^F) U_m$（供 `C1` 与残差池） | **`True`**                                                           |     `False`     |                  |
|  8  | `b_in`       | $B_{\text{in}}^\Omega$                                                                                                                                                                                                                                                                                                                                                                                   | `[B, 32k]`（单模态可见 `[B, 32]`，双模态可见 `[B, 64]`）                                       |                               `float32`                               | `B1` 输入：可见共享坐标按 $(\text{rna},\text{wsi},\text{text})$ 保序拼接 | **`True`** |     `False`     |
|  9  | `R`          | $R_{\Omega \to u}$                                                                                                                                                                                                                                                                                                                                                                                       | `[32, 32k]`（6 个 `[32, 32]` + 3 个 `[32, 64]`，共 9 个）                                      |                               `float32`                               | `B1` 模式特定全局线性恢复矩阵                                              | **`True`** |     `False`     |
|  10  | `bias`       | $b_{\Omega,u}$                                                                                                                                                                                                                                                                                                                                                                                           | `[32]`（共 9 个偏置向量）                                                                          |                               `float32`                               | `B1` 模式特定全局线性恢复偏置                                              | **`True`** |     `False`     |
|  11  | `e_pool`     | $E_{\text{pool}}^{\Omega,u}$                                                                                                                                                                                                                                                                                                                                                                             | `[N_tr, 32]`（共 9 个池）                                                                          |                               `float32`                               | `B6-LOO`：经 $(1-H_{jj}^\Omega)^{-1}$ 去偏的本折训练预测残差池           |       不启用       |     `False`     |
|  12  | `sim_mat`    | $S^\Omega$                                                                                                                                                                                                                                                                                                                                                                                               | `[B, N_tr]`（自查询位 $\text{id}_i=\text{id}_j$ 强制为 `-inf`）                                |                               `float32`                               | `B6-LOO`：逐可见模态平均余弦相似度矩阵                                     |       不启用       |     `False`     |
|  13  | `attn_w`     | $A^\Omega$                                                                                                                                                                                                                                                                                                                                                                                               | `[B, K]`（默认 $K=10$，行和为 $1$） | `float32` | `B6-LOO`：Top-$K$ 训练邻居核注意力权重 |                                 不启用                                 | `False`                                                                    |                    |                  |
|  14  | `alpha_gate` | $\alpha^\Omega$                                                                                                                                                                                                                                                                                                                                                                                          | `[B, 1]`（取值 $\in [0, \alpha_{\max}]$）                                                        |                               `float32`                               | `B6-LOO`：零参数 IQR 自适应患者级密度门控系数                              |       不启用       |     `False`     |
|  15  | `z_hat`      | $\hat{Z}_u^\Omega$ | `[B, 32]`（$u \in \mathcal{U}(\Omega)$）                                                                       | `float32`                                                                                          | 恢复的缺失模态共享坐标（Stage 2a 为$\hat{Z}_u^{\text{B1},\Omega}$，2b 为校准后）                                                                      | **`True`**                                                                                   |                                `False`                                |                                                                              |                    |                  |
|  16  | `p_hat`      | $\hat{P}_u^\Omega$ | `[B, 256]`（$u \in \mathcal{U}(\Omega)$）                                                                      | `float32`                                                                                          |            无新参数解码回投特征$\mu_u^F + \hat{Z}_u^\Omega U_u^\top$                                                                                  | **`True`**                                                                                   |                                `False`                                |                                                                              |                    |                  |
|  17  | `head_in`    | $\text{head\_in}^\Omega$                                                                                                                | `[B, 768]`（严格按 `rna · wsi · text` 三槽位各 256 维拼接）                                    |                                    `float32`                                    | 风险头输入：可见槽直通$P_m^\Omega$，缺失槽填 $\hat{P}_u^\Omega$ | **`True`**                                                                                   |                                `False`                                |                                                                              |                    |                  |
|  18  | `risk`       | $h^\Omega$                                                                                                                                                                                                                                                                                                                                                                                               | `[B]`（标量风险分，越大预后越差）                                                                  |                               `float32`                               | 冻结`I07` 线性风险头 `head_in @ w + b` 输出                              | **`True`** |     `False`     |

---

## 3. 【需求二】学术期刊级 Framework 框图绘制强约束规范（`Fig. 1`）

### 3.1 必读视觉参考源与一键提取核验命令

在 Claude Design（`/artifact-page`）设计并微调 `<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.html`（及无损导出 `framework.pdf`、`framework.png`）前，执行 AI **必须**先用多模态读图工具目视研读以下 **3 份参考源**，严禁闭门造车画成“工程流程图 / 大段文字海报”：

1. **第一优先级核心视觉母版（`<REPO_ROOT>/index.excalidraw` 内 `element=3FAgJOquwRE_a8wscpw8D`）**：
   执行 AI 可在终端运行以下 5 行只读单行命令将母版原图提取到 `/private/tmp/ref_3FAgJOquwRE.png` 并用读图工具查看：
   ```bash
   python3 -c '
   import json, base64, pathlib
   d = json.loads(pathlib.Path("<REPO_ROOT>/index.excalidraw").read_text())
   fid = next(e["fileId"] for e in d["elements"] if e["id"] == "3FAgJOquwRE_a8wscpw8D")
   b64 = d["files"][fid]["dataURL"].split(",", 1)[1]
   pathlib.Path("/private/tmp/ref_3FAgJOquwRE.png").write_bytes(base64.b64decode(b64))
   '
   ```
2. **第二参考源（`<LIT_DIR>/Prime/Prime.pdf` 第 3 页 `Fig. 1`）**：重点吸收其顶部紧凑图例条（`Missing` 虚线框 / `Trainable` / `Frozen` / `Weighted Aggregate`）、三栏虚线外框与单位圆余弦对齐微图（`close / far`）。
3. **第三参考源（`<LIT_DIR>/M3Surv/M3Surv.pdf` 第 4 页 `Fig. 2` & 第 5 页 `Fig. 3`）**：重点吸收其 `Memory Bank` $\mathcal{M}$ 圆柱/矩阵检索图标与 `Training vs. Inference` 记忆库建库检索对照小图。

### 3.2 旧版草稿图的致命问题诊断（严禁重犯！）

工作树现有旧草稿 `manuscript/bmc_initial_draft/figures/framework.svg` 存在严重工程海报风缺陷，**必须彻底推倒重绘**：

- ❌ **严禁大段说明文字（Wall-of-Text）**：旧图在框内塞满多行英文句子与 bullet points；期刊图每个子模块内**只允许放模块名 + 数学符号短标签（如 $U_m \in \mathbb{R}^{256 \times 32}$、$\hat{z}_{i,u}^\Omega$）**，机理全部靠**矩阵格块、分段特征条、簇散点图、算子圆圈（$\otimes, \oplus$）与曲线微图**可视化表达！
- ❌ **严禁泄露任何内部工程代号**：严禁在图中出现 `I08`、`I07`、`losses.py:28`、`operators.py`、`W1-4`、`Left (~18%)`、`0.6657` 等代码文件名、版面比例注释或具体实验跑分！

### 3.3 锁定的双层 `(A) + (B)` 期刊级构图蓝图（像素级对齐 `3FAgJOquwRE_a8wscpw8D`）

整体画布推荐尺寸 `1600 × 980 px`（纯白背景 `#FFFFFF`，高宽比约 `1.63:1`，完美适配 *BMC Bioinformatics* 双栏跨页 `\textwidth`），分为顶部图例条、上半部主架构 **`(A)`** 与水平虚线分隔下的底部工作流 **`(B)`**：

#### 顶部紧凑图例条（吸收 `PRIME Fig. 1`）

居中横排 5 个精致小图例项（高约 `28 px`）：
`[虚线空框] Missing Modality` · `[冷灰锁标实框] Frozen Backbone & Cox Head` · `[浅天蓝实框 #DBEAFE] Trainable Subspace & Base (A1 + B1)` · `[暖杏色实框 #FFEDD5] Zero-Retraining Plug-in (B6-LOO)` · `[珊瑚红虚线箭头] Training-Only Supervision (C1)`。

#### 上半部 `(A)`：三大圆角深灰虚线阶段外框（严格复刻 `3FAgJOquwRE_a8wscpw8D` 横向比例 `18% : 62% : 20%`）

外框统一样式：圆角 `rx=16`，深炭灰描边 `#1E293B`（`stroke-width=1.8`, `stroke-dasharray="8,5"`），外框正上方居中配粗体衬线标题（`Times New Roman` / `STIX Two Text` Bold `16pt`）：

1. **左虚线大框（宽约 `18%`）：标题 `Tri-Modal Feature Encoding`**

   - 按固定顺序自上而下排布三路具象医学输入微图 + 紧凑竖排 3 柱编码器图标（复刻母版左下角 `Feature encoder` 三立柱样式，标小锁表示 Frozen）：
     - **Row 1 (`RNA` Pathways)**：4 条彩色分格通路表达条（绿/青色系）$\to$ 竖排 3 柱冻结编码器 $\to$ 池化特征短条 $p_{i,R}^\Omega \in \mathbb{R}^{256}$；
     - **Row 2 (`WSI` Histology)**：H&E 染色切片矢量缩略轮廓 + $2 \times 4$ 采样组织图块微网格 $\to$ 竖排 3 柱冻结编码器 $\to$ 池化特征短条 $p_{i,W}^\Omega \in \mathbb{R}^{256}$；
     - **Row 3 (`Text` Pathology Report，示例设为缺失模态 $u \notin \Omega$)**：带标题横线的简洁病理报告文档页图标（标 `Structured Report`）+ 虚线 `Missing` 遮罩框；
   - **顶部纤细完整旁路**：从左侧框顶引出一条浅灰蓝色细实线直达右侧框顶，线上标紧凑胶囊签 `Complete Input (Ω = M): Identity Bypass`，直观体现完整三模态零损直通。
2. **中虚线大框（宽约 `62%`）：标题 `Orthogonal Subspace Decomposition & Dynamic Recovery`**
   内部模仿母版采用**上下/左右衔接的两张柔和莫兰迪色圆角模块卡**（`rx=14`，卡片左上角采用**粗斜体衬线标题**，如 ***`A1: Orthogonal Subspace Module`***）：

   - **模块卡一（浅天蓝底 `#DBEAFE`，边框 `#93C5FD`）：***`A1: Orthogonal Subspace Module`***（复刻母版 ***`AEI module`*** 视觉语法）**
     - 左侧画中心化特征彩色分段竖条 $x_{i,m}^\Omega \in \mathbb{R}^{256}$ $\to$ 乘号圆圈 $\otimes$ $\to$ **$6 \times 4$ 彩色方格正交矩阵图元** $U_m \in \mathbb{R}^{256 \times 32}$（标注 $U_m^\top U_m = I_{32}$）$\to$ 分叉出两支：
       - 主支：4 格紧凑共享坐标竖条 $z_{i,m}^\Omega \in \mathbb{R}^{32}$；
       - 正交补支：灰色斜纹竖条 $x_{i,u}^{\text{res}} \in \mathbb{R}^{224}$ 接红色截断符 `× (Truncated = 0 for u ∉ Ω)`；
     - 底部复刻母版红色虚线弯弧箭头，标注 `Orthogonal Energy Retention`（$\mathcal{L}_{\text{anchor}}$）；右上角配一个小巧的跨模态单位圆余弦拉近图标（$\mathcal{L}_{\text{modal}}$，连接三模态完整共享坐标 $z_{i,m}^F$）。
   - **模块卡二（暖杏桃色底 `#FFEDD5`，边框 `#FDBA74`）：***`B1 + B6-LOO: Residual Calibration Module`***（复刻母版 ***`CTP module`*** 双白底内嵌子框结构）**
     - **上白底内嵌子框 `Global Linear Trend (B1)`**：可见坐标拼接条 $b_{\text{in},i}^\Omega \in \mathbb{R}^{32k}$ 经紧凑矩阵块 $R_{\Omega \to u}$ + $b_{\Omega,u}$ 输出基础坐标条 $\hat{z}_{i,u}^{\text{B1},\Omega} \in \mathbb{R}^{32}$；**`C1` 的珊瑚红虚线双箭头 $\mathcal{L}_{\text{cons}}$ 必须严格连接此处的 $\hat{z}_{i,u}^{\text{B1},\Omega}$ 与停梯度目标 $\operatorname{sg}(z_{i,u}^F)$**！
     - **下白底内嵌子框 `LOO Residual Bank & IQR Density Gate (B6-LOO)`**（右上角挂醒目胶囊角标 `Plug-in · Zero Retraining · No Backprop`）：
       - 左侧复刻母版 `Gaussian Mixture Model` 的**彩色患者簇方格 + 查询圆点与 Top-$K$ 连线微图**（辅以 `M3Surv` 记忆库符号 $\mathcal{M}_\Omega$），旁边标出 $s_{ii} = -\infty$、注意力权重条 $a_{ij}^\Omega$ 与 Hat 去偏残差格条 $e_{j,u}^{\text{LOO},\Omega}$；
       - 右侧画一个迷你 **Sigmoid IQR 门控曲线图标**（横轴 $s_{i,(1)}^\Omega - \delta_\Omega$，纵轴 $\alpha_i^\Omega \in [0, \alpha_{\max}]$）$\to$ 乘号圆圈 $\otimes$；
     - 上下两子框输出在右侧汇入加号圆圈 $\oplus$，输出校准后的共享坐标竖条 $\hat{z}_{i,u}^\Omega \in \mathbb{R}^{32}$。
3. **右虚线大框（宽约 `20%`）：标题 `Survival Prediction`（100% 复刻母版右侧结构）**

   - **无参数解码与拼接合并为一根修长的三段彩色垂直向量长条**（`768-d`，高约 `340 px`）：
     - 上段（绿色 `RNA 256-d`）与中段（天蓝色 `WSI 256-d`）：由可见特征 $p_{i,R}^\Omega, p_{i,W}^\Omega$ 实线直接汇入（`Passthrough`）；
     - 下段（珊瑚粉色 `Text 256-d`，带细虚线高光框）：由 $\hat{z}_{i,T}^\Omega$ 经箭头标注无参数回投公式 $\hat{p}_{i,u}^\Omega = \mu_u^F + U_u \hat{z}_{i,u}^\Omega$ 直接汇入该段，**不画额外笨重解码器方框**！
   - 右接竖排圆角白底黑框胶囊 **`Frozen Cox Layer`**（复刻母版竖排 `MLP Layer`）$\to$ 圆角框 **`Risk Score` $h_i^\Omega$** $\to$ 右下角绘制精美的**红绿双阶梯带半透明置信区间的 Kaplan–Meier 高低风险生存曲线图元**，下方标注训练损失 $\mathcal{L}_{\text{Cox}}^{\text{missing}}$。

#### 下半部 `(B)`：水平粗虚线分隔下的两栏紧凑工作流（复刻母版底部 `(B)` + `M3Surv Fig. 3`）

- **左圆角框 `(B.1) Stage 2a Training & LOO Residual Bank Population`**：简明公式流展示 `Complete/Masked Train Views` $\to$ 优化 `(A1, B1)` 最小化 $\mathcal{L}_{\text{total}}$ $\to$ 冻结 $(U_m, R, b)$ $\to$ 计算闭式岭 Hat 对角元 $(1 - H_{jj}^\Omega)^{-1}$ 填充去偏残差库 $\mathcal{M}_\Omega = \{e_{j,u}^{\text{LOO},\Omega}\}_{j=1}^{N_{\text{tr}}}$ 并统计 $(\delta_\Omega, \gamma_\Omega)$。
- **右圆角框 `(B.2) Stage 2b Test-Time Dynamic Calibration & Outlier Safety Fallback`**：简明公式流展示 `Incomplete Test Patient (Ω ⊂ M)` $\to$ 逐模态余弦 Top-$K$ 检索 $\to$ 高密度邻域激活局部非线性校准（$s_{i,(1)}^\Omega > \delta_\Omega$），离群稀疏区自动阻尼回退全局线性预测（$s_{i,(1)}^\Omega \ll \delta_\Omega \implies \alpha_i^\Omega \to 0 \implies \hat{z}_{i,u}^\Omega \to \hat{z}_{i,u}^{\text{B1},\Omega}$）。

### 3.4 Claude Design 交互生成与本机无损纯矢量 `framework.pdf` 导出规范（策略 1️⃣ 锁定）

1. **彻底废弃旧版 Matplotlib 绘图脚本**：旧版 `experiments/I08_ps3_shared_recovery/tools/generate_framework_svg.py` 产出的工程框图审美生硬、微调成本极高，**不再作为 `Fig. 1` 生产入口**。
2. **Claude Design (`/artifact-page`) 单文件载体契约**：

   - 在 Claude Desktop 的 Code 标签中使用 `/artifact-page`（自动加载 `artifact-design` 与 `artifact-diagramming`），输出自包含单文件 `<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.html`；
   - **矢量与打印样式硬约束**：
     - 页面根容器固定精确尺寸 `width: 1600px; height: 980px; background: #FFFFFF; overflow: hidden;`，同时在 `<style>` 声明 `@page { size: 1600px 980px; margin: 0; }` 与 `* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }`；
     - 所有几何框线、矩阵格块、特征长条、散点簇、Sigmoid 门控曲线与 Kaplan–Meier 阶梯曲线**一律采用内联矢量 `<svg>` 绘制**（严禁使用 `<canvas>` 位图或外部失效图片 URL）；
     - 所有数学符号与上下标（如 $U_m^\top U_m = I_{32}$、$\hat{z}_{i,u}^{\text{B1},\Omega}$、$e_{j,u}^{\text{LOO},\Omega}$）**一律采用 KaTeX / STIX 数学字体矢量渲染**。
   - **交互微调定锚**：用户在 Claude 预览窗口直接对话微调间距、配色与字号，直至视觉质感达到顶刊水准，将最终定稿 HTML 保存至 `<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.html`。
3. **本机无损纯矢量 `framework.pdf` 转换与裁图目视门禁（遵守坑 `V29` / `E35`，严禁截图贴位图！）**：
   由 Claude Code 在 `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/tools/export_framework_pdf.sh` 封装以下无损转换与渲染核验流水线：

   ```bash
   # Step 1: Google Chrome Headless 原生矢量打印 PDF（保留全部矢量路径、圆角背景与数学字体，零光栅化模糊）
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless=new --disable-gpu --no-pdf-header-footer \
     --virtual-time-budget=3000 \
     --print-to-pdf="/private/tmp/framework_raw.pdf" \
     "file://<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.html"

   # Step 2: MacTeX pdfcrop 精确裁除白边，产出供 LaTeX \includegraphics 直接调用的纯矢量 PDF
   /Library/TeX/texbin/pdfcrop --margins "4 4 4 4" \
     "/private/tmp/framework_raw.pdf" \
     "<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.pdf"

   # Step 3: Ghostscript 300 DPI 光栅化导出预览 PNG，执行分块放大目视验收（坑 E35 / V29）
   /usr/local/bin/gs -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r300 \
     -sOutputFile="<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.png" \
     "<DEV_WORKTREE>/manuscript/bmc_initial_draft/figures/framework.pdf"
   ```

   导出后**必须**用读图工具放大检查左、中、右及底部四块区域：确认**零文字压线、零箭头穿字、零下标截断、800% 放大仍为锐利矢量曲线**后方可进入阶段五撰稿。

---

## 4. 【需求三】Baseline 实验设计——严格仿照 `PRIME` 的双主表结构

原研 `PRIME`（`<LIT_DIR>/Prime/Prime.pdf`）将外部方法对比拆分为两张职责清晰、版面匀称的表格：第 6 页 **`TABLE II`**（五癌种完整与单模态基准对比）与第 8 页 **`TABLE IV`**（推理期 6 种缺失模态鲁棒性对比）。`<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/tools/generate_paper_tables.py` **必须严格仿照 `PRIME` 拆分为 `Table 1` 与 `Table 2`**（不再把 40 行塞进同一张超长表格）：

### 4.1 正文 `Table 1`（仿 `PRIME Table II`：五癌种总体性能对比表，`tables/table1.tex`）

- **横轴 10 列（与 `PRIME Table II` 顺序 100% 一致）**：
  `Method / Img / RNA / Text / UCEC / LUAD / LGG / BRCA / BLCA / Avg.`
- **纵向分组与精确数据真源**：
  1. **Group 1 — `Unimodal Baselines`（8 行）**：
     - 逐字引用 `Prime.pdf` p. 6 `TABLE II` 前 5 行（全部标 `$^\dagger$` 注明为 PRIME 原文 5 折测试结果）：
       - `Img-only†`: `✓ / × / ×` — `0.668±0.083 / 0.599±0.056 / 0.670±0.100 / 0.615±0.087 / 0.547±0.060 / 0.620±0.052`
       - `RNA-only†`: `× / ✓ / ×` — `0.598±0.094 / 0.510±0.057 / 0.764±0.056 / 0.498±0.065 / 0.526±0.043 / 0.579±0.110`
       - `Text-only†`: `× / × / ✓` — `0.676±0.066 / 0.553±0.028 / 0.703±0.097 / 0.556±0.030 / 0.532±0.025 / 0.604±0.079`
       - `ABMIL [34]†`: `✓ / × / ×` — `0.637±0.049 / 0.604±0.066 / 0.692±0.056 / 0.617±0.092 / 0.537±0.035 / 0.617±0.056`
       - `SNN [35]†`: `× / ✓ / ×` — `0.571±0.070 / 0.520±0.065 / 0.719±0.073 / 0.466±0.103 / 0.536±0.053 / 0.563±0.096`
     - 本项目同划分 `I07` 独立单模态模型 3 行（由脚本自动读取 `I07 render/results.md` 与 `test_metrics.json` 交叉校验）：
       - `Standalone WSI-only (I07 Test)`: `✓ / × / ×` — `0.672±0.056 / 0.599±0.090 / 0.748±0.037 / 0.614±0.042 / 0.541±0.048 / 0.635±0.079`
       - `Standalone RNA-only (I07 Test)`: `× / ✓ / ×` — `0.692±0.071 / 0.628±0.059 / 0.824±0.023 / 0.573±0.054 / 0.607±0.032 / 0.665±0.099`
       - `Standalone Text-only (I07 Test)`: `× / × / ✓` — `0.694±0.074 / 0.644±0.053 / 0.710±0.038 / 0.628±0.080 / 0.624±0.041 / 0.660±0.040`
  2. **Group 2 — `Complete-Modality Multimodal Fusion & Pretraining Reference`（16 行）**：
     - 逐字引用 `Prime.pdf` p. 6 `TABLE II` 全部 14 行多模态基线（全部标 `$^\dagger$`，**严禁混入任何无出处方法**）：
       - `Early†` (`0.627±0.082`)、`Late†` (`0.618±0.076`)、`CrossAttn†` (`0.610±0.066`)、`TensorFusion [16]†` (`0.620±0.089`)、`MAGGate [17]†` (`0.624±0.080`)、`MulT [18]†` (`0.619±0.073`)、`MCAT [19]†` (`✓/✓/×`, `0.600±0.091`)、`Porpoise [20]†` (`✓/✓/×`, `0.618±0.039`)、`PathOmics [21]†` (`✓/✓/×`, `0.599±0.033`)、`Song [22]†` (`0.615±0.080`)、`PRIME Scratch (FT)†` (`0.623±0.072`)、`PRIME Scratch (LP)†` (`0.595±0.060`)、`PRIME Pretrained (FT)†` (`0.641±0.073`)、`PRIME Pretrained (LP)†` (`0.699±0.055 / 0.578±0.051 / 0.780±0.050 / 0.622±0.066 / 0.584±0.041 / 0.653±0.086`)；
     - 本项目冻结骨架完整模态恒等旁路参照 2 行（**强制不加粗**，表注明写由冻结 `I07` 骨架恒等旁路 $D_0$ 产生，不作为 `I08` 涨点邀功）：
       - `PS3-style Backbone / TriModalSurv Bypass (I07 Test)`: `0.704±0.074 / 0.645±0.105 / 0.808±0.026 / 0.651±0.049 / 0.596±0.027 / 0.681±0.080`
       - `PS3-style Backbone / TriModalSurv Bypass (I07 Val D_0)`: `0.689±0.163 / 0.680±0.021 / 0.838±0.065 / 0.595±0.096 / 0.586±0.094 / 0.678±0.102`
  3. **Group 3 — `Incomplete-Modality Evaluation (6-Missing-Scenario Macro-Avg, Same 5-Fold Val Split)`（4 行核心正面决战，组内最优加粗）**：
     - 模态列记为 `◐ / ◐ / ◐`（表示评测覆盖全部 6 种非空缺失子集均值）：
     - `PS3-style Backbone + Zero/Mean-Fill (M0-a/b)`: `0.653±0.132 / 0.659±0.030 / 0.787±0.048 / 0.589±0.064 / 0.571±0.089 / 0.652±0.085`
     - `Full-Space 256-d Ridge Imputation (B0, M1-a@default)`: `0.625±0.122 / 0.654±0.050 / 0.789±0.058 / 0.575±0.081 / 0.568±0.095 / 0.642±0.090`
     - `w/o A1: Full-Space 256-d B6-LOO (M7@default)`: `0.621±0.125 / 0.654±0.050 / 0.787±0.058 / 0.574±0.080 / 0.566±0.095 / 0.641±0.090`
     - **`TriModalSurv (Ours, M6-a)`**: **`0.670±0.152 / 0.661±0.040 / 0.798±0.043 / 0.612±0.074 / 0.588±0.090 / 0.666±0.082`**（5/5 癌种全部超越静态基线与全维恢复！）。

### 4.2 正文 `Table 2`（仿 `PRIME Table IV`：推理期 6 种缺失模态鲁棒性对比表，`tables/table2.tex`）

- **横轴 9 列（100% 镜像 `Prime.pdf` p. 8 `TABLE IV` 命名体系 + 缺失总均值列）**：
  `Method / Full / LI (RNA+Txt) / LR (WSI+Txt) / LT (WSI+RNA) / OI (WSI) / OR (RNA) / OT (Txt) / 6-Missing Avg`
  *(表注明晰解释 `PRIME` 缩写：`LI / LR / LT` 为 Leave-One-Out 缺图像 / 缺转录组 / 缺文本；`OI / OR / OT` 为 Only-One 仅图像 / 仅转录组 / 仅文本)*。
- **上半区（`External Reference: PRIME Table IV, Task-1 OS, 5-Fold CV Test†`）——逐字引自 `Prime.pdf` p. 8**：
  1. `PRIME Scratch (FT)†`: `0.623±0.072 / 0.608±0.069 / 0.631±0.068 / 0.607±0.051 / 0.607±0.050 / 0.540±0.085 / 0.606±0.066 / 0.600`
  2. `PRIME Pretrained (LP)†`: `0.653±0.086 / 0.612±0.086 / 0.641±0.086 / 0.619±0.090 / 0.603±0.058 / 0.564±0.084 / 0.611±0.077 / 0.608`
  3. `PRIME Pretrained (LP+Missing)†`: `0.653±0.089 / 0.623±0.085 / 0.639±0.085 / 0.636±0.087 / 0.611±0.055 / 0.571±0.063 / 0.610±0.089 / 0.615`
- **下半区（`Controlled Comparison on Frozen PS3-style Backbone, Same 5-Fold Val Split`，4 位小数均值 ± 五癌标准差，缺失列最优加粗，`Full` 列恒为 `0.6777±0.102` 不加粗）**：
  1. `Zero / Train-Mean Placeholder (M0-a/b)`: `0.6777 / 0.6715 / 0.6545 / 0.6736 / 0.6458 / 0.6554 / 0.6107 / 0.6519`
  2. `Full-Space 256-d Ridge (B0, M1-a@default)`: `0.6777 / 0.6493 / 0.6531 / 0.6680 / 0.6419 / 0.6282 / 0.6131 / 0.6423`
  3. `Risk-Residual 256-d Ridge (C0, M1-b@default)`: `0.6777 / 0.6407 / 0.6560 / 0.6679 / 0.6432 / 0.6248 / 0.6037 / 0.6394`
  4. `w/o A1: Full-Space 256-d B6-LOO (M7@default)`: `0.6777 / 0.6457 / 0.6527 / 0.6681 / 0.6406 / 0.6229 / 0.6134 / 0.6406`
  5. **`TriModalSurv (Ours: A1 + B6-LOO + C1, M6-a)`**: `0.6777` / **`0.6856`** / **`0.6606`** / **`0.6829`** / **`0.6518`** / **`0.6723`** / **`0.6412`** / **`0.6657`**
     *(亮点：在全部 6 种缺失模式下一致取得最高 C-index，尤其在单模态仅文本 `OT: 0.6107 → 0.6412 (+3.05%)` 与仅转录组 `OR: 0.6554 → 0.6723 (+1.69%)` 上提升最为显著！)*

---

## 5. 【需求四】消融实验与机理核验——单列 `Ours=0.6657 / 其余=@default` 铁律

### 5.1 正文 `Table 3`（6 行渐进式核心组件消融表，极简 10 列，`tables/table3.tex`）

完全对齐 `<REPO_ROOT>/03_index-故事线 A-1｜患者级动态恢复_v1.md#blk-68d9c2d39df14dbf`：**彻底删去 `A1/C1/B` 勾号列、`Full`、`Overall`、`val Cox` 与 `Δ` 列**，最右侧以 `6-Missing Avg` 收尾：

| Variant                                          |     `rna`     |     `wsi`     |     `text`     |   `rna+wsi`   |   `rna+text`   |   `wsi+text`   |  `1-Mod Avg`  |  `2-Mod Avg`  | `6-Missing Avg` |
| :----------------------------------------------- | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: | :--------------: | :---------------: |
| `Backbone + Zero / Train-Mean (M0-a/b)`        |      0.6554      |      0.6458      |      0.6107      |      0.6736      |      0.6715      |      0.6545      |      0.6373      |      0.6666      |      0.6519      |
| `w/o A1: 256-d Full-Space B6-LOO (M7@default)` |      0.6229      |      0.6406      |      0.6134      |      0.6681      |      0.6457      |      0.6527      |      0.6256      |      0.6555      |      0.6406      |
| `A1 + B1 (w/o C1, w/o B6, M10-a@default)`      |      0.6635      |      0.6482      |      0.6195      |      0.6775      |      0.6746      |      0.6523      |      0.6437      |      0.6681      |      0.6559      |
| `A1 + B1 + C1 (w/o B6, M2@default)`            |      0.6630      |      0.6430      |      0.6297      |      0.6749      |      0.6755      |      0.6530      |      0.6452      |      0.6678      |      0.6565      |
| `A1 + B6-LOO (w/o C1, M8@default)`             |      0.6654      |      0.6489      |      0.6252      |      0.6789      |      0.6740      |      0.6549      |      0.6465      |      0.6693      |      0.6579      |
| **`A1 + B6-LOO + C1 (Ours, M6-a)`**      | **0.6723** | **0.6518** | **0.6412** | **0.6829** | **0.6856** | **0.6606** | **0.6551** | **0.6763** | **0.6657** |

> **表注与正文必写统计量（已由脚本从 25 份折级 JSON 精确算出）**：
>
> - `Ours (M6-a)` vs `M0-a`：平均配对增益 `+0.0138`（`22/25` 折严格胜出，0 平局，单侧 Wilcoxon $p = 1.25 \times 10^{-4}$，双侧 $p = 2.50 \times 10^{-4}$）；
> - `Ours (M6-a)` vs `M7@default (w/o A1)`：`+0.0252`（`18/25` 折胜，单侧 $p = 2.15 \times 10^{-4}$）；
> - `Ours (M6-a)` vs `M2@default (w/o B6)`：`+0.0092`（`18/25` 折胜，3 折因选出 $\alpha_{\max}=0$ 精确平局，单侧 $p = 7.74 \times 10^{-4}$）；
> - **诚实统计措辞（遵守排雷第 6 条）**：由于 `Ours (M6-a)` 采用验证集选参而其余消融行采用固定 `@default` 超参，正文表述为“相对静态填充与纯线性基座显著提升，各核心组件逐步叠加呈一致单调增益趋势（`0.6406 → 0.6519 → 0.6559 → 0.6565 → 0.6579 → 0.6657`）”。

### 5.2 正文 `Table 4`（模块内算子横向对比表：Slot `A` 与 Slot `B`，`tables/table4.tex`）

横轴：`Slot & Operator Variant / 1-Mod Avg / 2-Mod Avg / 6-Missing Avg`（所有非 `Ours` 行严格取 `@default`）：

- **Block A — Subspace Decomposition Slot (`A`, paired with `B6-LOO`)**：
  1. `w/o A (256-d Full Space, M7@default)`: `0.6256 / 0.6555 / 0.6406`
  2. `A5: Frozen Unsupervised PCA-32 (M9@default)`: `0.6463 / 0.6710 / 0.6586`
  3. **`A1: Trainable Cayley Orthogonal-32 (Ours, M6-a)`**: **`0.6551 / 0.6763 / 0.6657`**
- **Block B — Dynamic Recovery Operator Slot (`B`, under identical `A1 + C1` subspace where applicable)**：
  1. `w/o B: Train-Mean Placeholder (M0-b)`: `0.6373 / 0.6666 / 0.6519`
  2. `B0: 256-d Closed-Form Ridge (M1-a@default)`: `0.6277 / 0.6568 / 0.6423`
  3. `C0: 256-d Risk-Residual Ridge (M1-b@default)`: `0.6239 / 0.6548 / 0.6394`
  4. `B5-DirectCoord: Precision Shrinkage on Raw z (M4-b@default)`: `0.6293 / 0.6653 / 0.6473`
  5. `B3: Direct Top-K Neighbor Feature Aggregation (M3@default)`: `0.6397 / 0.6654 / 0.6526`
  6. `B1: Global Pattern-Specific Linear Map (M2@default)`: `0.6452 / 0.6678 / 0.6565`
  7. `B5-MapPrecision: Precision Shrinkage on Mapped z (M4-a@default)`: `0.6451 / 0.6683 / 0.6567`
  8. `B6-Naive: Raw Residual Retrieval w/o LOO Leverage & IQR Gate (M5@default)`: `0.6457 / 0.6721 / 0.6589`
  9. **`B6-LOO: Hat-Debiased Residual Retrieval + IQR Gate (Ours, M6-a)`**: **`0.6551 / 0.6763 / 0.6657`**

### 5.3 附录五张详表（`Appendix Tables S1–S5`，`tables/table_s1.tex` ～ `table_s5.tex`）

1. **`Table S1`（6 种缺失模式全方法分项明细表 + 五癌×六模式 `Mean±SD` 详表）**：覆盖 `M0-a/b`、全部 `@default` 对比变体与 `Ours (M6-a)` 在 `rna, wsi, text, rna+wsi, rna+text, wsi+text` 下的完整数值（源自 `val_ablation_report_v1.md` 表 2 及 25 份折级 JSON）。
2. **`Table S2`（5 个 TCGA 癌种分项 `6-Missing Avg` 性能明细表）**：源自报告表 3（单列规则一致）。重点展示 `Ours (M6-a)` 在全部 5 个癌种上相对 `M0-a` **100% 取得正收益**：`BLCA` (`0.5713 → 0.5875, +0.0162`)、`BRCA` (`0.5886 → 0.6118, +0.0232`)、`LUAD` (`0.6591 → 0.6613, +0.0022`，增幅最小)、`LGG` (`0.7874 → 0.7984, +0.0110`)、`UCEC` (`0.6532 → 0.6696, +0.0164`；**严禁沿用旧稿误写“UCEC 负收益/文本饱和”！**）。
3. **`Table S3`（`C1` 损失细粒度拆解 & `B6` 残差池构造口径对比双小表）**：
   - Panel A (`C1` 拆解)：`M10-a@default (λ_m=0, λ_c=0: 0.6559)`、`M10-c@default (λ_m=0.1, λ_c=0: 0.6561)`、`M10-b@default (λ_m=0, λ_c=1.0: 0.6567)`、`M2@default (λ_m=0.1, λ_c=1.0: 0.6565)`、`M8@default (w/o C1 + B6-LOO: 0.6579)`、**`Ours M6-a (Full C1 + B6-LOO: 0.6657)`**；
   - Panel B (`B6` 残差池与门控口径)：`M5@default (B6-Naive: Raw Pool w/o LOO Leverage & IQR Gate: 0.6589)`、`M6-b@default (Closed-Form Ridge Exact-Hat Pool: 0.6583)`、**`Ours M6-a (In-Fold B1 Hat-Leverage Debiased Pool + IQR Gate: 0.6657)`**（解释为何残差池生成源与基座预测器 `B1` 保持同源去偏一致优于异源闭式 Ridge 池 `M6-b` 与未去偏无门控 `M5`）。
4. **`Table S4`（子空间机理验证表——原样呈现报告表 4，严禁删改负值！）**：
   - 如实报告 `rna` ($R_{\text{val}}^2(p^{\text{sha}}) = +0.0974$ vs $p^{\text{res}} = -0.5683$, $\cos = 0.6160$ vs $0.2590$, $\rho_r = 0.6281$)、`wsi` ($R_{\text{val}}^2(p^{\text{sha}}) = -0.2492$ vs $p^{\text{res}} = -0.4775$, $\cos = 0.3222$ vs $0.0710$, $\rho_r = 0.6945$)、`text` ($R_{\text{val}}^2(p^{\text{sha}}) = +0.2493$ vs $p^{\text{res}} = -0.3124$, $\cos = 0.6545$ vs $0.3186$, $\rho_r = 0.6800$)，随机子空间期望 $r/d = 0.1250$。
   - **Discussion 诚实科学解释口径**：三模态 $p^{\text{sha}}$ 的跨模态可预测性与方向余弦均大幅高于被截断的 $p^{\text{res}}$，且仅用 12.5% 维度即捕获了 62.8%–69.5% 的冻结风险头权重能量；WSI 的欧氏 $R_{\text{val}}^2$ 为负（$-0.2492$）是因为全切片组织形态具有极强的空间异质性，跨模态预测存在幅值尺度方差，但其方向余弦（$0.3222$ vs $0.0710$）依然有效保留了预后排序信号，这也解释了为何需要 `B6-LOO` 局部校准与门控阻尼。
5. **`Table S5`（可解释性三项定量核验表——原样呈现报告表 5，固定 `M2@default + B6-LOO@default` 口径）**：
   - ① 检索稳定性（**严格写 20 次 80% 训练集子采样**，严禁误写 50 次！）：Top-$K$ 邻居 `Jaccard = 0.6845 ± 0.0046`，残差修正方向余弦 `0.9335 ± 0.0111`；
   - ② 局部忠实性（Top-1 邻居擦除，$n = 7,554$）：中位 $|\Delta h|$ 为 `0.01296` vs 随机擦除另一邻居 `0.00423`（配对单侧 Wilcoxon $W = 24,013,865.5,\ p = 0.00\text{e+}00$，Top-1 线性贡献平均占比 `24.20%`）；
   - ③ 门控—收益关联：$\operatorname{Spearman}(s_{(1)}, \Delta\mathcal{E}) = 0.1686\ (p = 2.96 \times 10^{-49})$，$\operatorname{Spearman}(\alpha_i, \Delta\mathcal{E}) = 0.1647\ (p = 4.19 \times 10^{-47})$，平均风险逼近改善 $\overline{\Delta\mathcal{E}} = +0.03030 > 0$；同时如实披露高低置信半区 $\Delta\text{C-index}$ 为 `-0.0001`（$n=149$）与 `+0.0049`（$n=150$），将门控客观定位为**抑制低密度离群点劣化、保障逐患者风险逼近精度的安全阻尼阀**，而非夸大为半区 C-index 单调放大器。

---

### 5.4 【策略 1️⃣ 锁死】双模型接力成文硬锁协议与 SCI 学术版 Anti-AI 门禁规范

为兼顾「代码级公式/数据绝对准确」与「地道自然的 SCI 期刊英文质感」，同时彻底杜绝跨 AI 传话的信息熵增与社区通用 Humanizer 导致的口语化污染，全文撰稿与润色严格执行以下三道铁律：

#### 5.4.1 双模型角色分工与已挂载 Skill 路由（`~/.claude/skills/`）

1. **第一棒：Claude Code 撰写技术初稿与文献核真（`P5-Draft`）**
   - 必读并严格遵循 `~/.claude/skills/nature-writing/SKILL.md`（显式锁定轴参数：`paper_type = methods`、`journal = generic`、`language = en`）；
   - 整理 `references.bib` 时调用 `~/.claude/skills/nature-ref-verifier/SKILL.md` 核实全部条目的真实标题、作者、年份与期刊/DOI，严禁编造文献或乱配 Citation Key；
   - 直接落盘 `<DEV_WORKTREE>/manuscript/bmc_initial_draft/{main.tex, appendix.tex, references.bib}`，确保全部公式 `(1)–(14)`、18 个张量维度、定稿 `Fig. 1` 子块指代与 `\input{tables/...}` 编译零报错。
2. **第二棒：Antigravity (Gemini) 同工作树受控句法润色（`P5-Polish`）**
   - 在同一 `<DEV_WORKTREE>` 原位读取 `.tex` 文件（零跨窗口粘贴），必读并遵循 `~/.claude/skills/nature-polishing/SKILL.md`（`paper_type = methods`、`journal = generic`、`language = en`；若遇浮动体跨页或版面松散则加载 `references/latex-layout.md`）；
   - **五大不可触碰硬锁（Diff-Locked Invariants，违者回滚）**：
     1. **数学公式锁**：行内 `$...$` 与行间 `equation / align` 环境内的核心符号、上下标、系数零改动；
     2. **实验数字锁**：所有指标值（如 `0.6657`、`0.6519`、`+0.0138`）、样本数、折数（`25`）、胜场（`22/25`）、子采样次数（`20`）与 $p$ 值零改动；
     3. **统计边界与限定语锁**：严禁删改任何适用域限定词（如 *under default hyperparameters*、*consistent gain trend*、*outlier safety damping*），严禁在无配对显著性检验支撑处滥用 *significantly*（遵守 `nature-polishing/references/nat-comms-2025-diction.md` 红线）；
     4. **交叉引用锁**：所有 `\input{...}`、`\includegraphics{...}`、`\cite{...}`、`~\ref{...}` 键名零改动；
     5. **术语防漂移账本锁（Terminology Ledger，严禁为“换词优美”而使用近义词替换！）**：
        - `A1` 正交补分量固定译名：`orthogonal complement`（或 `modality-specific orthogonal complement`），绝不写 `prediction residual`；
        - `B6-LOO` 预测误差残差固定译名：`LOO-calibrated prediction residual`（或 `hat-debiased training residual`），绝不与正交补混称；
        - 完整模态直通固定译名：`complete-modality identity bypass`；
        - 可见模态保真直通固定译名：`visible-modality passthrough`；
        - `B1` 基座固定译名：`pattern-specific global linear map`；
        - 门控固定译名：`IQR-adaptive density gate`。

#### 5.4.2 SCI 学术版 Anti-AI 黑名单门禁（取代社区通用口水文 Humanizer）

**严禁使用社区通用检测绕过型 Humanizer**（其随机近义词替换与第一人称口语碎句会严重损害 SCI 方法论文严谨度）。改由 Claude Code 编写自动化检查脚本 `<DEV_WORKTREE>/experiments/I08_ps3_shared_recovery/tools/check_anti_ai_and_numbers.py`，在初稿与润色后双重执行以下硬检查（退出码必须为 `0`）：

1. **AI 高频套话词零容忍清零（Lexical Blacklist，不区分大小写词边界匹配）**：
   - 严禁出现：`delve` / `delving`, `pivotal`, `underscore` / `underscoring`, `intricate` / `intricacies`, `tapestry`, `realm`, `testament`, `seamless` / `seamlessly`, `paradigm shift`, `groundbreaking`, `unprecedented`, `revolutionary`, `harness` / `harnessing`, `bolster`, `foster`, `multifaceted`, `meticulous` / `meticulously`, `crucial role`, `vital role`, `shed light on`, `pave the way`, `treasure trove`, `landscape`（非数学损失地形语境）。
2. **AI 机械句式与标点清零（Syntactic Blacklist）**：
   - **禁破折号叙述**：正文文本行严禁使用英文长破折号 `—`（U+2014）或 LaTeX `---` 作插入语标点（数学减号与表内占位符除外），一律改用逗号、括号或独立短句；
   - **禁句尾伴随 `-ing` 空洞吹嘘尾巴**：严禁句末逗号后接 `, highlighting ...` / `, underscoring ...` / `, showcasing ...` / `, demonstrating the superiority of ...` / `, paving the way for ...` 等空泛评价从句，直接用具体数字或因果主谓句收尾；
   - **禁机械排比与废话起手式**：全文 `Not only ... but also ...` 出现次数 `= 0`；严禁连续段落以 `Importantly,` / `Notably,` / `Crucially,` / `It is worth noting that` / `This suggests that` 机械起手；
   - **句长与严谨语域硬边界**：按 `nature-polishing` 规范，正文陈述句词数控制在 **`10–30` 词**（超过 32 词的复合长句必须拆分为单命题短句）；全文零英文口语缩略（`don't`, `can't`, `isn't`, `won't`, `it's` 出现次数 `= 0`）。

---

## 6. 「图表定锚先行，文随图定」调度拓扑、坑台账注入与排雷终审卡

### 6.1 分阶段无冲突文件所有权拓扑（任何并发任务写入集合交集 $= \varnothing$）

```
  ╔══════════════════ 第一阶段：图表定锚先行（可双线并行，零文件交叉） ══════════════════╗
  ║                                                                                      ║
  ║  [路线 A · Claude Code 执行 P2 制表与门禁脚本]                                       ║
  ║    独占可写:                                                                         ║
  ║      • experiments/I08_ps3_shared_recovery/tools/generate_paper_tables.py            ║
  ║      • experiments/I08_ps3_shared_recovery/tools/export_framework_pdf.sh             ║
  ║      • experiments/I08_ps3_shared_recovery/tools/check_anti_ai_and_numbers.py        ║
  ║      • manuscript/bmc_initial_draft/tables/{table1..4.tex, table_s1..s5.tex, *.md}   ║
  ║                                                                                      ║
  ║  [路线 B · 用户在 Claude Desktop (/artifact-page) 交互微调 P4 框图]                  ║
  ║    独占可写:                                                                         ║
  ║      • manuscript/bmc_initial_draft/figures/framework.html (内联 SVG + KaTeX 定稿)   ║
  ║      • 经 export_framework_pdf.sh 无损转出: figures/{framework.pdf, framework.png}   ║
  ╚══════════════════════════════════════════╤═══════════════════════════════════════════╝
                                             │
                       (待 P2 表格断言全绿 + Fig. 1 视觉定版入库后)
                                             ▼
  ╔══════════════════ 第二阶段：Claude Code 技术初稿（P5-Draft） ════════════════════════╗
  ║  调用 Skill: ~/.claude/skills/{nature-writing, nature-ref-verifier}                  ║
  ║  独占可写:   manuscript/bmc_initial_draft/{main.tex, appendix.tex, references.bib}   ║
  ║  强约束:     100% 对照定稿 Fig. 1 模块名与式(1)-(14)，零手抄表格，过 Anti-AI 初检     ║
  ╚══════════════════════════════════════════╤═══════════════════════════════════════════╝
                                             │
                                             ▼
  ╔══════════════════ 第三阶段：Antigravity (Gemini) 受控润色（P5-Polish） ══════════════╗
  ║  调用 Skill: ~/.claude/skills/nature-polishing (+ references/latex-layout.md)        ║
  ║  同工作树原位润色: 硬锁公式/数字/限定语/术语账本，逐节审阅 git diff，latexmk 零报错   ║
  ╚══════════════════════════════════════════╤═══════════════════════════════════════════╝
                                             │
               (check_anti_ai_and_numbers.py 退出码 0 + 10 条排雷卡全绿 + 用户终验)
                                             ▼
  ╔══════════════════ 第四阶段：主控 P3 核销沙盘「表格消消乐」同步收口 ══════════════════╗
  ║  双端同步可写: <REPO_ROOT> 与 <DEV_WORKTREE> 下的 03_index-故事线 A-1｜..._v1.md     ║
  ╚══════════════════════════════════════════════════════════════════════════════════════╝
```

### 6.2 必读相关坑注入（摘自 `docs/engineering/pitfalls.md`，执行前必核）

- **`V23`（禁手算派生数字）**：进正文与表注的所有胜负场次、平局数、均值差与 Wilcoxon $p$ 值必须由 `generate_paper_tables.py` 脚本直接计算并落盘断言，严禁心算或手抄。
- **`V27` / `V42`（防跨棒复述漂移与限定语丢失）**：第二棒 Gemini 润色必须以原位 `git diff` 证明公式、数字与统计限定语零篡改，严禁凭印象整段重写。
- **`V29` / `E35`（纯矢量导出与强制渲染目视验收）**：`framework.html` 必须经 Chrome Headless `--print-to-pdf` + `pdfcrop` 转出纯矢量 `framework.pdf`，再用 `/usr/local/bin/gs` 渲染 300 DPI PNG 分块目视复检，确认零重叠、零越界、800% 放大无锯齿。
- **`V33`（TeX 编译日志跨行警告扫描）**：检查 `main.log` 时用单前缀锚点扫描 `Warning` / `Undefined` / `Overfull \hbox`，禁止用同行长正则漏检 79 字符折行警告。
- **`E38` / `V34` / `E52`（自定义编辑器覆盖、替换断言与禁竖线截断）**：改写 `03_index` 前确认每处替换命中次数严格为 1，表格单元格内（含反引号与公式）零裸竖线 `|`，写后复查双端 `diff -u` 退出码为 `0`。
- **`I05-04` / `I05-12`（公开入库文档隐私扫描）**：完成文稿后执行 `git grep -n "/Users/\|/home/" manuscript/ experiments/I08_ps3_shared_recovery/tools/`，确保新增脚本与 LaTeX 源码零本机用户名绝对路径泄漏。
- **`C14`（高频防偏移提问）**：若遇到期刊模板宏包选型、篇幅裁剪或叙事取舍存在多种合理方案，先向用户提出精炼选项确认，不擅自偏离本契约。

### 6.3 交付前 10 条排雷终审核对卡（全部打勾方可提请用户验收）

- [ ] **1. 秩与参数量**：全文统一 25/25 折锁定 $r=32$（占 256 维 $12.5\%$，截断 224 维），可训练参数量 $37,152$（占 256 维全空间线性映射 $788,736$ 参数量的 $4.71\%$，严禁残留旧错数 `296,448`）。
- [ ] **2. 式 (8) 留一杠杆去偏**：准确写出对 `B1` 训练残差除以 $\max(1 - H_{jj}^\Omega, 10^{-4})$（闭式岭回归 $\lambda_{\text{hat}}=1.0$ Hat 矩阵对角元）。
- [ ] **3. 式 (9) 相似度与门控**：准确写出**逐可见模态平均余弦**、自查询置 $-\infty$，以及最近邻中位数 $\delta_\Omega$ 与 **IQR 自适应缩放斜率** $\gamma_\Omega \in [5, 30]$。
- [ ] **4. 式 (11)–(14) 训练边界**：准确写出 `C1` 只在 Stage 2a 监督 `B1` 输出 $\hat{z}_{i,u}^{\text{B1},\Omega}$（`B6-LOO` 推理期零重训插拔、无梯度反传），且 $\mathcal{L}_{\text{anchor}}$ 为正交重构能量锚定（$\lambda_a=1.0, \lambda_m=0.1, \lambda_c=1.0$，无风险蒸馏项）。
- [ ] **5. 框图期刊质感与纯矢量入文**：`Fig. 1` 经 Claude Design（`/artifact-page`）交互定版为 `framework.html` 并由 `Chrome Headless + pdfcrop` 无损导出纯矢量 `framework.pdf`，对标 `3FAgJOquwRE_a8wscpw8D` + `PRIME` + `M3Surv` 双层圆角虚线容器与莫兰迪色块视觉语言，零大段文字墙、零代码文件名、解码与拼接合并为右侧三段长条。
- [ ] **6. Baseline 双表仿 `PRIME`**：`Table 1` 仿 `PRIME Table II`（零幻觉方法，含 `I07` 独立单模态与不加粗的完整模态恒等旁路 + 底部五癌缺失均值汇总），`Table 2` 仿 `PRIME Table IV`（`Full / LI / LR / LT / OI / OR / OT / 6-Missing Avg`）。
- [ ] **7. 单列超参消融铁律**：`Table 1–4` 与 `Appendix S1–S3` 中仅 `Ours (M6-a)` 采用验证集选参后 `0.6657`，其余全部对比/消融行一律采用 `@default` 未调参结果。
- [ ] **8. 五癌种全正结论**：正文与 `S2` 如实写 5/5 癌种 `6-Missing Avg` 全部正向提升（最小为 `LUAD +0.0022`，严禁写“UCEC 负收益”）。
- [ ] **9. 机理与可解释性诚实披露**：`S4` 完整保留并科学解释 WSI $R_{\text{val}}^2 = -0.2492$；`S5` 严格写 **20 次** 80% 子采样并客观阐述门控的高低置信半区安全阻尼作用。
- [ ] **10. Anti-AI 门禁、编译、隐私与停机门**：`check_anti_ai_and_numbers.py` 零黑名单词/零破折号/零口语缩略通过；`latexmk -pdf` 退出码 `0`；新增脚本与 `.tex` 零 `/Users/` 路径残留；`config.yaml` 保持 `test_access: false` 未动。

---

## 7. 分步开箱即用执行 Prompts（直接按序复制）<span id="blk-4bb033edc8344f58"></span>

### 7.1 【Prompt A：发给 Claude Desktop（Code 标签）交互生成并微调 `Fig. 1` 框图】

```text
/artifact-page 请先读取工作树 `handoff-论文生成.md` 的第 2 节（式 1–14 符号定义）与第 3 节（`Fig. 1` 期刊级 Framework 框图强约束规范），并先运行第 3.1 节的 5 行只读命令提取 `<REPO_ROOT>/index.excalidraw` 内的核心视觉母版 `3FAgJOquwRE_a8wscpw8D` 到 `/private/tmp/ref_3FAgJOquwRE.png`，同时目视阅读 `<LIT_DIR>/Prime/Prime.pdf` 第 3 页 `Fig. 1` 与 `<LIT_DIR>/M3Surv/M3Surv.pdf` 第 4–5 页 `Fig. 2–3`。

请严格加载 `artifact-design` 与 `artifact-diagramming` 规范，为我们的 *BMC Bioinformatics* 论文设计并生成自包含单文件 `manuscript/bmc_initial_draft/figures/framework.html`（固定画布 `1600 × 980 px`，纯白底 `#FFFFFF`，含 `@page { size: 1600px 980px; margin: 0; }` 与 `print-color-adjust: exact` 以便 Chrome 无损打印纯矢量 PDF）：
1. 构图 100% 对标母版 `3FAgJOquwRE_a8wscpw8D` 的双层 `(A) + (B)` 学术期刊风：顶部排 5 项紧凑图例条；上半部 `(A)` 按 `18% : 62% : 20%` 排布三个圆角深炭灰虚线容器（左 `Tri-Modal Feature Encoding` 含 RNA/WSI/缺失 Text 具象矢量微图与顶部 `Identity Bypass`；中 `Orthogonal Subspace Decomposition & Dynamic Recovery` 含浅蓝莫兰迪卡 `A1: Orthogonal Subspace Module` 与暖杏色莫兰迪卡 `B1 + B6-LOO: Residual Calibration Module` 双白底内嵌子框；右 `Survival Prediction` 将无参数解码 $\hat{p}_{i,u}^\Omega = \mu_u^F + U_u \hat{z}_{i,u}^\Omega$ 与可见直通合并为一根 3 段彩色 `768-d` 垂直长条，接竖排 `Frozen Cox Layer` 与红绿双阶梯置信阴影 KM 生存曲线）；下半部 `(B)` 排左右两栏紧凑公式工作流（Stage 2a 训练建库 vs Stage 2b 推理校准与离群阻尼回退）。
2. 硬红线：所有图元（矩阵方格、分段向量条、簇散点 Top-K 连线、Sigmoid IQR 门控小曲线、KM 曲线）一律用精细内联矢量 `<svg>` 绘制，数学上下标一律用 KaTeX 渲染；严禁出现任何大段说明文字墙、中文、代码文件名（`I08`/`losses.py`）或具体跑分数字；`C1` 的 $\mathcal{L}_{\text{cons}}$ 珊瑚红虚线箭头必须严格连向 `B1` 输出 $\hat{z}_{i,u}^{\text{B1},\Omega}$，`B6-LOO` 醒目挂 `Plug-in · Zero Retraining · No Backprop` 胶囊标。
生成初版后请直接发布预览，我将与你对话微调审美细节。
```

### 7.2 【Prompt B：发给 Claude Code 执行阶段二（`P2` 学术 LaTeX 表格 + 矢量转图脚本 + SCI 去 AI 味门禁脚本）】

```text
请先完整阅读仓库坑台账 `docs/engineering/pitfalls.md` 与 `handoff-论文生成.md`（v1.1），严格遵守 [T/B/P/A/Q] 热路径协议与停机门（`test_access: false`）。
本次仅执行「第一阶段路线 A（阶段二 P2 制表与配套自动化门禁脚本）」，暂不写 `main.tex` 正文（等我在 Claude Design 微调定稿 `Fig. 1` 后再启动撰稿）：
1. 更新并运行 `experiments/I08_ps3_shared_recovery/tools/generate_paper_tables.py`（使用 `protomasksurv-exp1` 环境 Python），严格按 `handoff-论文生成.md` 第 4–5 节导出标准学术 LaTeX `booktabs` 三线表：`manuscript/bmc_initial_draft/tables/table1.tex`（仿 `PRIME Table II`）、`table2.tex`（仿 `PRIME Table IV`）、`table3.tex`（6 行极简主消融）、`table4.tex`（Slot A & B 横向对比）、`table_s1.tex`～`table_s5.tex` 及 `paper_tables_preview.md`；内置硬断言核对单列超参铁律（仅 `Ours M6-a` 取选参后 `0.6657`，其余全取 `@default`）且零幻觉基线。
2. 编写可执行脚本 `experiments/I08_ps3_shared_recovery/tools/export_framework_pdf.sh`（按 `handoff` 第 3.4 节封装 Chrome Headless `--print-to-pdf` + `/Library/TeX/texbin/pdfcrop` + `/usr/local/bin/gs` 300 DPI PNG 导出与基础尺寸/非空校验）。
3. 编写可执行门禁脚本 `experiments/I08_ps3_shared_recovery/tools/check_anti_ai_and_numbers.py`（按 `handoff` 第 5.4.2 节实现 SCI 学术版 AI 套话词黑名单清零、正文破折号 `—`/`---` 拦截、伴随 `-ing` 吹嘘尾巴拦截、`Not only...but also` 与口语缩略拦截、>32 词超长句告警，以及关键实验数字与无用户名路径扫描，并附自测用例验证能抓出违规词且放行数学公式/表格注释）。
完成后跑通 `PYTHON_BIN=~/miniconda3/envs/protomasksurv-exp1/bin/python bash scripts/ci.sh` 并汇报校验结果，不触碰 `03_index` 与 `main.tex`。
```

### 7.3 【Prompt C：待 `Fig. 1` 定版转出 `framework.pdf` 后，发给 Claude Code 撰写 `.tex` 技术初稿（`P5-Draft`）】<span id="blk-928c516497fe42a5"></span>

```text
`Table 1–4 / S1–S5` 与定稿矢量框图 `manuscript/bmc_initial_draft/figures/framework.pdf`（及预览 `framework.png`）均已就位。
请先完整阅读 `docs/engineering/pitfalls.md`、`handoff-论文生成.md`（v1.1），以及已软链挂载的 `~/.claude/skills/nature-writing/SKILL.md`（锁定轴：`paper_type=methods, journal=generic, language=en`）和 `~/.claude/skills/nature-ref-verifier/SKILL.md`，并先用读图工具查看定稿 `figures/framework.png` 以对齐图中所有子图编号与模块卡片英文标题。
请执行【阶段五 A（`P5-Draft` 技术初稿撰写）】：
1. 独占编写 `manuscript/bmc_initial_draft/{main.tex, appendix.tex, references.bib}`：完整覆盖 `Abstract`（`Background / Results / Conclusions`）、`Background`、`Methods`（逐符号严格对齐 `handoff` 式 1–14、18 张量维度及定稿 `Fig. 1` 视觉流向）、`Results`、`Discussion`、`Conclusion` 与 `Appendix`；全部表格与框图一律通过 `\input{tables/...}` 与 `\includegraphics[width=\textwidth]{figures/framework.pdf}` 引入，严禁手抄任何单元格数字。
2. 用 `nature-ref-verifier` 逐条核真 `references.bib`，确保零编造文献与零断链引用。
3. 跑通 `latexmk -pdf -interaction=nonstopmode main.tex`（退出码 `0`）、`check_anti_ai_and_numbers.py`（退出码 `0`）并对照 `handoff` 第 6.3 节「10 条排雷终审核对卡」逐项核验后停下汇报；随后我将切回 Antigravity (Gemini) 调用 `nature-polishing` 进行同工作树 `git diff` 级受控句法润色。
```
