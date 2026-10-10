# innovation-BioClinical ModernBERT：先验知识

[系统状态：S_state 已核验到"仓库代码与本地证据"一级；远端数据、HF 权重下载、GPU 未核 | 当前阶段：代码已落地并通过本地测试，未上机]

| 项目 | 内容 |
|---|---|
| 日期 | 2026-09-23 |
| 分支 | `exp/innovation-encoder`（开工时 HEAD `0a53b01`，与 main 相同） |
| 实验 ID | I05（`experiments/I05_text_encoder_bcmbert/`） |
| 用途 | 原始需求与原始证据的共同底稿。本文件只放原文、事实与用户裁决；Claude 的方案见 [研究计划书](研究计划书-BioClinical%20ModernBERT.md) |
| 原始需求 | [4.1.BioClinical ModernBERT-prompt.md](4.1.BioClinical%20ModernBERT-prompt.md)（原样保留）；选择记录见 [4.2.BioClinical ModernBERT-方案细化（Claude）.md](4.2.BioClinical%20ModernBERT-方案细化（Claude）.md) |
| 信息损失规则 | 所有模型读同一份证据，不做逐级转述；下一位可以读上一位的建议，但上一位的建议不能代替原始需求和原始证据 |

## 1. 原文照录（不改 T/Q）

### 大背景

> 实验的核心创新点，消融实验已经获得在五个癌症的种类中的五分之四的胜率，接下来实验也是消融实验，证明（NPJ骨架➕原型学习➕新的辅助创新点：我们选择的新的encoder）实验结果大于（NPJ骨架➕原型学习➕NPJ架构中，文本图像和rna三个模态的所使用的encoder），既可以证明新的辅助创新点：我们选择的新的encoder大于NPJ架构中文本图像和rna所使用的encoder，证明新的辅助创新点：我们选择的新的encoders以有效的

### Trigger：触发场景

> 发散的创新点k1的选择为BioClinical ModernBERT 嵌入版，设计出详细的BioClinical ModernBERT 嵌入版的实验方案，

### Q_draft：What should be true afterward?

> - 我们提出来的encoder的实验效果在none的情况下（排除both_100，text_100，rna_100三种缺失情况下）的五个癌症中的实现结果，最后的胜率c-index达到五分之四
> - 因为新的encoder是辅助创新点，所以无需像是主创新点原型学习那样，在四个不同场景做实验，只需要在none，也就是三模态都完整。
> - 研究计划书：
>
>   - 必须包含实验的整体的实现顺序和逻辑链条（mermaid）
>   - 创新点BioClinical ModernBERT 嵌入版在整个网路中的位置（mermaid格式）
> - 实验结果：
>
>   - 参考/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/癌症为单位.md和/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/seed单位-实验结果.md，在/Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT-程序性知识生成seed单位-实验结果.md和癌症为单位.md。
>   - 再生成两个md文件：【seed单位-实验结果.md】三种人工缺失场景，五种不同的癌症，五个不同的seed的结果，按照Seed作为基本单位，每一个seed的形成，5种癌症在3种缺失场景下的实验结果。并判断出seed，哪一种seed患者检索的效果最好？【癌症为单位.md】三种人工缺失场景，五种不同的癌症，五个不同的seed的结果，按照Seed作为基本单位，每一个癌症为单位形成，5个seed在3种缺失场景下的实验结果，并判断出5种癌症场景，哪一种癌症场景患者检索的效果最好？
>     【约束二】

原文"三种人工缺失场景"与前两条"只需要在 none"互斥。2026-09-23 用户裁决：模板保留四场景结构，只有 none 进入 Q（见第 2 节）。

### 不可变约束

> 1. none的定义指的就是在both_100，text_100，rna_100，none的中的历史 none 保留天然缺失，因为消融实验二-encoder的实验结果中，（NPJ骨架➕原型学习➕新的辅助创新点：我们选择的新的encoder）实验结果可以直接使用/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.pdf中的Table 1的Scenario为None的实验数据
> 2. 新 encoder 优于文本图像和rna三个模态的所使用的encoder，也就是/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.pdf中的Table 1的Scenario为None所使用的文本图像和rna三个模态的所使用的encoder）
> 3. 对照：Table 1 中 **None / Proto.†** 对应的现有系统；新 encoder 成绩尚未产生。
> 4. 不需要去执行ChatGPT Pro (发散创新)和workflow:Gemini (构建框架) 的工作

### how to do it

> 1.证明新的encoder的实验表格的设计图,必须严格参考上传文件和文件夹和zip
>
> 2基于***exp/innovation-encoder*** 分支开发，不可污染main分支。
>
> 3.编写一个名为innovation-BioClinical ModernBERT.md文档。
>
> - 其内容是k1的选择为BioClinical ModernBERT 嵌入版的S_state（当前实际上具备哪些数据、资源和准备状态？）和Q_draft / Q_specific和不可变约束，且不许改 T/Q，
> - 输出的位置在/Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT
> - 4. 【how to 避免信息损失】为了避免ai在数据传输中的信息损失，所以选择所有模型读同一份证据，不做逐级转述，下一位可以读上一位的建议，但上一位的建议不能代替原始需求和原始证据
>
> 5. **遵循最小改动原则（不改槽；在能填这个槽的临床 encoder 里取最强冻结权重）**和改动后实验结果大概率在五个cancer中，c-index上升

原文的输出位置 `4.BioClinical ModernBERT` 不存在，本文件放在已有的 `4.BioClinical ModernBERT-程序性知识/`，原始需求也在这里。

## 2. 用户裁决记录

| 日期 | 裁决 | 影响 |
|---|---|---|
| 2026-09-23 | 两份结果模板保留四场景结构；只有 `none` 进入 Q，其余三场景作附录 | 推理顺带跑 rna_100/text_100/both_100（零训练） |
| 2026-09-23 | 填槽用方案 A：token 级，截断或补齐到 200，pad 行置零，形状 `[200,768]` 不变 | 唯一变量是 encoder（外加其分词器）。**已被 2026-09-24 的方案 C 取代** |
| 2026-09-24 | Phase 0 发现旧特征 pad 位非零后，填槽改用方案 C：截断或补齐到 200 token，有效 token 均值（pad 不参与）广播写入全部 200 行，形状 `[200,768]` 不变 | NPJ-C 槽内均值恰为前 200 token 的 masked mean，短报告不缩小；覆盖长度仍为 200，不引入 encoder 之外的新变量 |
| 2026-09-24 | 审查闭环只审一次、只看核心逻辑；授权 Phase 0（数据在 landau）与手工 squash / freeze，不推送 main；Phase 1 新建 conda 环境（transformers ≥ 4.48），在 tetra:3 提特征后拷回 landau | 已写入 CLAUDE.md、AGENTS.md |
| 2026-09-23 | Claude Code 任指挥官并构建代码；Codex 只做实验前研究计划书审查与实验后结果审查 | 已写入 CLAUDE.md、AGENTS.md、STATUS.md |
| 2026-09-23 | 原话照录："对于代码开发并不是由codex去执行，还是由ous5.5去执行代码开发，codex只负责对于生成的计划书进行review和对实验结果进行一个review，不参与任何代码生成的工作，只是用来审核" | 代码开发由 Claude Code（Claude Opus 5.5）执行；Codex 只审核计划书与实验结果，不参与任何代码生成；已同步到 CLAUDE.md、AGENTS.md、STATUS.md 与本目录文档 |
| 2026-09-23 | 模型 ID 锁定为 `NeuML/bioclinical-modernbert-base-embeddings`，revision 锁定为 `048ad4491de0fb4e2695bfe4705da67caf4804b8` | 你在 `4.2.BioClinical ModernBERT-方案细化（Claude）.md`「问题二：具体的模型的来源」中选择 1（NeuML 嵌入版）；其 base_model 为 `thomas-sounack/BioClinical-ModernBERT-base`，同为 base 尺寸，满足同一文件里"用 base，不要 large" |
| 2026-09-23 | 上机顺序：Phase 0 只读核验可用 exp 分支已提交版本；从 Phase 1 提特征起，先经 Codex 候选审查、squash 进 main、freeze，再同步上机 | 特征与 ckpt 的溯源都落在 main 的冻结 commit 上 |
| 2026-09-23 | 本轮改动提交到 `exp/innovation-encoder`，不 push | 提交时机见研究计划书第 8 节 |
| 2026-09-23 | 4×5 表中「其他方法的 Encoder」只是占位行，具体算法尚未确定 | 本轮不预设任何候选，五格写"未实验（算法待定）" |
| 2026-09-23 | BioClinical ModernBERT 的实验种子必须是 123、132、213、231、321 | 与 Table 1 对照同一组；评测器与渲染脚本遇到其他种子直接拒绝 |
| 2026-09-23 | 必须使用 GPU 运行，不可以使用 CPU 运行实验；在 landau、tako 等四台云端服务器中优先找空闲显卡；没有空闲显卡时，正在使用且 GPU 使用量在 70% 以下的卡也可以跑实验 | 提取、训练、推理都只在 GPU 上跑；I05 用自己的选卡规则复核卡号 |

## 3. Q_specific 与执行验收门

**Q_specific（效果，只看 none）**：

```text
Δ_c = mean_seed C_B(新 encoder 系统, c, none, strategy0) − mean_seed C_B(Table 1 None / Proto.†, c)
胜 = Δ_c > 0（未舍入）；平局不算胜
达标 = 胜的癌种数 ≥ 4（五癌：LGG、BRCA、BLCA、LUAD、UCEC）
五 seed：123、132、213、231、321；不删癌、不删 seed、不用最佳 seed 代替五 seed
```

对照值（Table 1 None 行 Proto.† 列，与原始 JSON 的五 seed 均值逐位相同）：

| 对照 | LGG | BRCA | BLCA | LUAD | UCEC |
|---|---|---|---|---|---|
| 现有系统 None / Proto.† | 0.797723 | 0.688112 | 0.589972 | 0.582485 | 0.650968 |

**执行验收门（不是 Q）**：25 个新 ckpt 全部完成，溯源 commit 在 main 且 `dirty=0`；5 癌 × 5 seed × 4 场景 × 3 臂齐全；旧资产回放通过；进结论的数字只来自脚本留档表。执行验收通过与否，和 Q 是否达标分开报告。

**统计口径**：零效应下、各癌胜负独立且对称时，至少 4/5 严格胜出的偶然概率为 6/32（约 18.8%）；BLCA 五 seed 均值的标准误约 0.025。所以 4/5 本身是弱证据，结果表会同时列出逐 seed 的 Δ。

## 4. S_state

### 4.1 已证实的事实

| 项目 | 事实 | 出处 |
|---|---|---|
| Text 槽位 | 模型对 token 维做无 mask 的 `mean(dim=1)`，再进 `Linear(768,256)→ReLU→Dropout`；三模态各一个 token 进 1 层 4 头 Transformer（d=256，FFN 1024） | `src/trimodalsurv/models/npjc.py:17-38, 52-56` |
| 槽位形状 | `(200, 768)` 写死在 dataset 零填充、I01 检索库与推理器配置中 | `src/trimodalsurv/data/tcga_dataset.py:187`；`experiments/I01_patient_retrieval/evaluate.py:30`；2.progress `runtime.py:71` |
| 现有 Text 特征 | 作者公开嵌入，解析为 `data/text_embeddings_parsed/{pid}.pkl`；解析脚本只抽查 20 个（坑 D6） | `experiments/npj-uni2/manifest.md`；archive 中的 `parse_text_embeddings.py` |
| 现有 WSI / RNA | UNI2-h 公开特征包，KMeans 到 128 行；自制 BulkRNABert，2048×256 | `experiments/npj-uni2/manifest.md`；`tcga_dataset.py` |
| 训练配方 | lr 1e-4、epochs 50、batch 32、hidden 256、Adam wd=1、bf16、best-valid、bin_mode author、无早停；GPU 走 `configs/gpu_train.yaml` 的 NPJ 小计算图豁免 | `scripts/train_launcher.py:463-469, 1028-1031`；`src/trimodalsurv/training/runtime.py:856-857, 934-936` |
| 训练工作目录 | 训练子进程工作目录固定为仓库根，dataset 用相对路径 `tmp_sur_cache`；缓存键不含特征路径且有 glob 兜底；dataset 构造末尾无条件、非原子地重写三类缓存 | `train_launcher.py:914-916`；`tcga_dataset.py:87-95, 254-298` |
| ckpt 文件名 | 由 feature_dim 拼出，Text 仍为 768 时与历史同名 | `train_launcher.py:509-542` |
| 冻结方法 | 历史选参锁里的 combo：`combo-l1-a1-w0p5`，rules 1–5，λ=1、α=1、w=0.5，UCEC 例外开；LUAD 按 S0-force 路由 | 2.progress `runs/valid/selection-lock.json`；4.progress `luad_m1_force/config.yaml` |
| 推理器可复用 | 推理器绑定的 5 个公共源码当前 sha256 与锁定值全等；6 个推理器文件与 4.progress 锁定值全等 | 2.progress `config.yaml` 的 `baseline_source_sha256`；4.progress `config.yaml` 的 `upstream.source_sha256` |
| 推理器不能直接跑 | test 阶段必须读取绑定资产哈希的 valid 选参锁；preflight 硬绑历史 ckpt 与缓存 | 2.progress `run.py:216-223`；`runtime.py:454-513` |
| 组合可复现 | 用 2.progress 的 combo/m1/m0real 逐患者组合，20 个 LUAD 单元的 logits 与 risk_b 逐值等于 4.progress 的 strategy0；非 LUAD 的 80 行 Proto.† 等于 2.progress combo | I05 测试 `test_strategy0_and_replay.py` |
| 浮点差 | 在 CPU 上从 logits 重算 B 风险，与历史存值在 2 个单元出现 ≤ 3.6e-7 的 float32 差；所以组合取已存 risk_b，不重算 | 本轮核算（见研究计划书 Post-Mortem） |
| 对照原值 | 25 个 none 原值与五 seed 均值与 Table 1、交接包 `None基线明细.md` 逐位相同 | 4.progress `runs/test/complete.json`（sha256 `8604aae4…`，指纹 `a825b3cc…`） |
| split 人数 | train/valid/test：BLCA 136/68/138，BRCA 383/192/383，LGG 166/83/166，LUAD 171/84/172，UCEC 197/99/198 | 2.progress `evidence/legacy-preflight.json` |
| test 天然缺失 | RNA/Text：BLCA 0/0，BRCA 1/36，LGG 0/3，LUAD 0/5，UCEC 1/8 | 同上 |
| LUAD 路由 | 历史 LUAD test 在 none 下 172 人全部走组合，缺 RNA 转 m1 的分支触发 0 次 | 4.progress `complete.json` 的 `luad_route_counts` |
| 新模型 | revision `048ad449…`：ModernBertModel，hidden 768，22 层，12 头，max_position 8192；池化只开 mean-token；Apache-2.0；base_model 为 thomas-sounack 基础版；需 transformers ≥ 4.48 | Hugging Face API 与该 revision 的 `config.json`、`1_Pooling/config.json`（2026-09-23 读取） |
| 缓存来源 | valid 缓存记录的来源主机为 landau，且未重建 | 2.progress `evidence/valid-source.json` |
| 发车契约 | I05 清单与既有 e0 臂的 25 对 dry-run 命令只差 `--model_config` 与 `--result_path` | `tools/check_launch_contract.py` 本地实跑 |
| 历史 GPU 门 | 2.progress 推理器的 GPU 门只接受没有其他计算进程的卡，与本轮"利用率 < 70% 的在用卡也可用"的规则不同；I05 改用自己的 `gpu_policy.gate`，不调用上游门禁 | 2.progress `runtime.py:516-529` |
| 四台服务器 | 从 Mac 本机经 SSH 别名查询的四台是 landau、tako、hitode、tetra；这些别名只在 Mac 上配置 | 坑台账 E31 |
| 本机 | 没有 `data/`；可用测试环境为 `protomasksurv-exp1`（无 transformers、无 sksurv）；改动前 CI 为 145 通过、4 失败、6 跳过，4 个失败与本实验无关（3 个因 I02 目录改名，1 个因缺 sksurv） | 本轮 `scripts/ci.sh` 基线 |

### 4.1b Phase 0 已证实（landau，只读审计，代码版本 `3de43a2`，2026-09-24）

- 标签 `data/TCGA_9523_ex12.csv`（sha256 `35c28659…`）有 `text` 列，内容是病理报告原文；五癌 2,636 行。
- 2,506 名有旧 Text 特征的患者全部有报告原文（`missing_text` 为空）；另有 130 人有原文但无旧特征，不生成，天然缺失口径不变。
- 旧特征全部 `(200,768)` float32、无非有限值；**全部 200 行非零且互不相同**，连 1 个词的报告也是；每行范数约 27.6（≈√768）。旧 pad 位不为零，与原方案 A 不符 → 用户改定方案 C。
- 报告长度：中位 558 词、25 分位 222 词，18% 不足 150 词。
- landau 的 `tmp_sur_cache` 中 45 个历史缓存全部存在，哈希与 legacy 证据逐一相同。
- landau 现有环境：`tcga_env` 的 transformers 为 4.46.1（< 4.48，不能加载 ModernBERT），`protomasksurv-exp3` 无 transformers；需新建环境。
- GPU（2026-09-24 选卡）：landau 两卡利用率 100%；无空闲卡；规则内可用 tetra:3（0%，39.5 GB 空余）、tako:2/3。

### 4.2 未核验的假设

- 旧 Text 特征的编码器身份（行范数约 √768，像 LayerNorm 之后的逐 token 隐藏状态，但未证实）。
- 现在哪台主机同时保存了 25 个历史 ckpt。已知 tako 与 landau 各有部分记录。
- 各服务器是否允许访问 Hugging Face。
- dataset 重写缓存后，播种的 img/rna 缓存字节是否保持不变。评测器在字节不同时会按内容比对。
- 历史 25 个 ckpt 的训练源码指纹。它们在现行代码入库之前训练，Δ 因此包含重训方差。

### 4.3 已失败或已否决的尝试

- 原 Top-1 检索方案总体劣于均值填补与不补偿；它与现行原型检索方法不是同一协议。
- 3.progress 的 valid 门禁（B−A = −0.008815）曾关闭 LUAD 路由；4.progress 强制开启，因此存在 test 泄漏，属探索性结果。
- 候选淘汰：Qwen3-Embedding-0.6B 改了槽位（1024 维 last-token 单向量）；LLM 先浓缩报告多了一个变量；Clinical ModernBERT 的公开基准弱于 k1；方案 B（整篇单向量平铺）一次改了编码器、覆盖长度与粒度三个因素。
- 早期 Claude 回答把 PS3 的去生物通路数字 0.644 误读为去文本数字，并把"图像与文本编码器同时更换"误读为只换文本；综合回答已更正。

## 5. 解释边界

- 只换了 Text。结论支持"换 Text 后的三模态 encoder 组合优于现有组合"，不支持"每个模态的 encoder 都更好"，也不支持不可变约束 2 所说的三个模态都已替换。
- `none` 保留天然缺失，不是三模态齐全的完整子集。
- `none` 下完整患者不走检索，Proto.† 在这些患者上等于基础模型。
- Δ 同时包含 encoder 效应与重训方差。
- 方案 C 只编码前 200 token（超过 75% 的报告被截断），结论不代表整篇报告的编码能力。
- 结论只按 Q 陈述，不写"必然涨点"。

## 6. 证据索引

- 交接包与 Pro 版先验知识：[../1.原始发给ai的信息/](../1.原始发给ai的信息/)
- 三份 AI 回答：[../2.来自ai的回答/](../2.来自ai的回答/)
- I05 代码与测试：[experiments/I05_text_encoder_bcmbert/](../../../../experiments/I05_text_encoder_bcmbert/README.md)
- 坑台账：[docs/engineering/pitfalls.md](../../../../docs/engineering/pitfalls.md)
