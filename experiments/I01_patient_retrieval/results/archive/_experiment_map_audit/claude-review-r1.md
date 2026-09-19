## 复审结论：**CONCERNS**（可修，不阻断；未发现会推翻结论的错误陈述）

两份文档的事实主张我逐条比对了留档证据与源码，**没有找到假陈述**；问题集中在「哪些数字本轮真被机器核过」与「给 Grok 的代码料是否够诊断」。

---

### 一、我亲自核对并成立的部分

| 主张 | 我查的证据 |
|---|---|
| 四份源码 SHA 与正式 preflight 一致 | `preflight.json:376-381` 四个 hash 与 map:185-188、`verify_documents.py:16-21` 三处完全相同（我先前对该目录的 grep 未命中是 ripgrep 跳过忽略文件所致，直接 Read 后确认存在） |
| 300 项复算 PASS、最大 logit 差、`n_checked_per_grid` 语义 | `formal-verification.json:4-7,11-28,30`，与 map:390/392/398 逐项吻合 |
| 63,420 是重复预测记录数 | `formal-verification.json:5`；且 60×(138+383+166+172+198)=63,420 与 map:397 的「单 split test 合计 1057 人」自洽 |
| 旧两报告哈希未变 | `_grouped_report_audit/report-checks.json:19-20` 记录的哈希 = `verify_documents.py:13-14` 的常量 |
| 历史命令口径 | `c_unit.sh:10-12`（lr/epochs/batch/NPJC/ex12/五 seed）；e0 臂 `EXTRA` 为空 → 无 CAP、无 modality_dropout，支持 map:346 |
| 「源码重建」项 | `main_survival.py:717`（Adam, weight_decay=1）、`:718`（bf16）、`:681`（NLLSurvLoss α=0/eps=1e-7）、`:665-675`（load_model 未传 dropout）、`:769-771`（valid 严格改善才 dump）、`:527-536` + `fusion_model.py:968-976`（SurvivalHead 输出未过 sigmoid ⇒ 选模确为 A 风险）。map:347-350 标注「源码重建、非训练时指纹」的强度限定是恰当的 |
| 无早停分支 | 该快照全文 grep `patience|early` 无命中，支持 map:346 |
| padmask 只作用检索支路 | `eval_patient_retrieval.py:123`（模型吃原 128 行缓存）+ `patient_retrieval_bank.py:139-148`（仅检索副本去中心），支持 map:153 |
| 双缺同 donor、自排除、train-only | `patient_retrieval_bank.py:163-164,203-209` |
| 三臂表格内部自洽 | 我手算了总体/seed/癌种/癌种×场景四层聚合与两列 Δ 的相互一致性，并与 `_grouped_report_audit/verification.json:89-159`、`_experiment_map_audit/verification.json:156-167` 交叉比对，未发现矛盾；`best_retrieval_seed/cancer` 与 map:430/442 一致 |
| **划分与 seed 无关（防泄漏关键）** | map:39/41 无出处，但我独立确认成立：`tcga_dataset.py:335` 划分直接读标签 CSV 的 `split` 列，`:148-149` 生成时 `random_state=42`，`seed` 仅流向 `:474` 的 `modality_dropout_seed`（E0 为 0）；`preflight.json` 各癌 `label_sha256` 同为一值 |

---

### 二、可操作问题

**P1｜四个胜平负计数全仓无第二处出处，且本轮脚本不验**
map:416-417、Grok:275-276 的「32/5/63、37/5/58、28/0/47、30/0/45」我全库检索后只在这两份新文档里出现；`build_reports.py` 只产 `unique_wins`/`tied_groups`（17/39/39、并列 5，这四个数有 `_grouped_report_audit/verification.json:154-159` 背书），`verify_documents.py` 也未计算配对胜负。→ 在 `verify_documents.py` 加一段从 75 份 JSON 直接数配对胜/平/负并 assert 进文档正文，否则这两行是全文最像「结论」却最无机器背书的数字。

**P2｜`verify_documents.py:70` 的断言近乎恒真**
`assert "200" in text and "未来" in text` —— `"200"` 会被 Text 缓存形状 `200×768`（map:49、Grok:44）直接命中，与「200 轮属未来方案」毫无关系。→ 改成断言 `"max_epochs=200"`/`"patience=15"` 与「不属于本轮」同句共现，或直接删掉，别留假护栏。同理 `:69` 的 `"K=8"` 只证明字符串存在，不证明它被标为笔误。

**P3｜map:394「本轮从原 JSON 重聚合」的覆盖面被说大了**
`verify_documents.py` 本轮实际 assert 进文档的只有 40 行癌种×场景表（`:71-76`）；两行总体是 `:83-85` 算出来**只 print 不 assert**（值落在 `_experiment_map_audit/verification.json:156-167`，需人工肉眼比对）；seed 表与癌种表本轮**根本没算**，其数值来自上一轮 `_grouped_report_audit/verification.json:94-147`。→ 要么把 seed/癌种/总体三张表一并 assert，要么把 map:394 改成「癌种×场景表本轮重算并断言；seed/癌种/总体沿用上一轮审计值，本轮仅核源 JSON 哈希未变」。

**P4｜给 Grok 的代码料缺了三臂真正的分叉点（对诊断质量影响最大）**
Grok:110-257 给了 `retrieve()`、projector、融合、B 风险，但**没给** `compensate()`（`patient_retrieval_bank.py:179-215`）和 `PatientSource.batch()`（`eval_patient_retrieval.py:120-133`）。缺这两段会导致：
- Grok 无从知道 m0real 的「占位特征」**是全零张量**（`eval_patient_retrieval.py:130-132`），而 Grok:99 只写「保留占位」。它的 Q5（偏差—方差）和 Q3（LGG/BRCA 反向现象）恰恰要靠「零向量过 projector 后被 mask 掉、只改 pooling 分母」这一事实才能推。
- Grok 无从知道 m1/retrieval 只改被判缺失那一行、其余保持原值（`:193-194,205-213`）。
→ 建议把这两段原文补进 Grok:五节。

**P5｜融合代码节选断裂，作为「原文」自相矛盾**
map:288-316、Grok:212-240 的两段从 `fusion_model.py:1148` 直接跳到 `:1193`，**跳过了 `:1149-1158`**——而 `valids[mm]` 正是在 `:1156-1158` 赋值的。单看节选，`valids` 在 1141 建空 dict、1196 就被消费，中间无赋值；同时被跳过的 `:1160-1191` 是 compensator 分支（本轮 `compensator=None` 故失效，但节选未说明跳过了什么）。→ 把 `:1149-1158` 补入（顺带让 Grok 看到 `img` 恒 valid=True），并在跳号处加一句「1160-1191 为 CAP 分支，本轮 compensator=None 不进入」。

**P6｜源码链接全部指向易失的 git worktree**
map:185-188 等 12 处链接指向 `/Users/wuhao/.codex/worktrees/774f/...`；该 worktree 是临时的，删了链接全断。仓内已有同名快照 `archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ/...`（我只确认路径存在，**未比对字节**）。→ 核对一致后改指仓内快照，或至少在 map:183 附近写明快照对应的 commit（`6a04a0b`）。

**P7｜两处引用行号锚点没指到被引主张上**
- map:353 指 `c_unit.sh:9`（`for sd in` 那行），真正含 lr/epochs/batch 的是 `:10-12`。
- map:354 指 `main_survival.py:665`（`load_model(`），它只能锚住「未传 dropout」这一条；表里同栏的「A 选模」「固定轮数循环」「Adam/wd=1/bf16」应分别锚 `:769-771`+`:527-536`（配 `fusion_model.py:968-976`）、`:717-718`。
→ 该表证据强度写得很克制，但锚点要跟主张对齐，否则复核者会重走我这一遍。

**P8｜天然缺失三列是否「含双缺」未定义**
map:59-65、Grok:75-81 的「缺 RNA / 缺 Text / 双缺」，只有按「前两列含双缺」去算，才能推出 none 核验人数（BRCA 383−36、UCEC 198−9）；按互斥读法会算错。→ 表头加一句「前两列为各自缺失总数，已含双缺列」。

**P9（小）｜map:386「25 份权重内容去重检查有记录」**
本轮脚本 `:53` 只 assert 了同癌同 seed 三臂 `checkpoint_sha256` 相同（25 组配对），「25 份互不相同」属留档主张，本轮未验。该行混在「本次/留档证据」同一栏里，建议拆开标注。

---

### 三、用户列的重点项，逐条状态

K=128 全篇锁定、未与 I02 的 K=8 混用（map:3、Grok:14，配置 `prototype_k:128`、`metadata k:128`）✅；零训练与历史 50 轮分离 ✅；200/patience15/B 选模明确划为未来（map:372、Grok:67）✅，但其自动护栏见 P2；「源码重建 ≠ 训练时快照」及 A 选模证据强度限定 ✅（锚点见 P7）；padmask 只动检索、模型 WSI 不变 ✅；双缺同 donor ✅；none 保留天然缺失 ✅；两口径分列、seed321 绝对 / seed213 增益、LGG 绝对 / UCEC 增益方向 ✅（与两份审计 JSON 一致）；valid=1≠置信度 1 ✅（map:166、Grok:106）；不把假设当因果、未默认 gating/CAP 必要 ✅（map:477-479、Grok:19/344）；未把工程 PASS 或挑 seed 当学术成功 ✅（map:403/430、Grok:299/332）。**唯一不达标的是「代码片段足够供 Grok 诊断」——见 P4、P5。**

---

### 四、我的审查边界（请按此看待上面每一句）

- 我**没有运行任何命令**：没跑 `verify_documents.py`、没算任何 SHA256、没复算任何 C-index、没做模型前向。全部结论来自 Read/Glob/Grep 的静态阅读。
- 因此「哈希一致」我能证的只是：**文档里写的 hash 字符串 = preflight.json / report-checks.json 里写的 hash 字符串**；文件内容是否真等于该 hash，我未验证，依赖执行者自述的那次运行。
- 表格数值我做的是**内部自洽性手算**（各层聚合互推、Δ 复算）与**跨审计 JSON 字符串比对**；我**没有**从 75 份正式 JSON 逐格重算 300 个读数，也没打开 600 份 artifact。P1 所说「无出处」指全库文本检索未命中，不等于该计数错误。
- 源码我只读了被引用的行段及邻近上下文（`patient_retrieval_bank.py` 40-226、`fusion_model.py` 968-976/1130-1209、`eval_patient_retrieval.py` 110-169 及结构 grep、`main_survival.py` 抽段、`tcga_dataset.py` 抽段），**未通读任一文件**，也未验证节选与源码逐字符相同（那是 `verify_documents.py:77-78` 的活，我只核了行号区间对不对得上）。
- P6 里仓内归档副本我**只确认路径存在，未比对内容**。
- 全程只读：未修改任何文件、未训练、未跑实验、未派子 agent。
