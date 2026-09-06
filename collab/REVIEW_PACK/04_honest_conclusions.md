# 04. 诚实结论：能下的 / 不能下的 / 已知实现债

> 本仓库不是 SOTA 声明，是待审的实验记录。数字全部来自 `collab/20260827-三方对比战役/s5_report.md`、`collab/20260902-A测缺失补偿/a_test_report.md`（r4）与其脚本生成的 `table_*.md` / `r4_numbers.txt`（对账见 `check_numbers.txt`）。口径：骨架 B（sigmoid 修正）为主，A 附列；baseline 单一 sksurv 读数；逐 seed 严格胜负计数 + 配对Δ中位；|Δ中位|<0.02 为噪声带；**无统计推断**。

## 一、完整模态 vs 缺失场景：实际数字

### 1. 三方对比（S5，完整模态，5 癌 × 5 seeds）

| 癌种 | MCAT 中位 | PORPOISE 中位 | S5 NPJ-B 中位 | NPJ-A vs MCAT | NPJ-A vs PORPOISE |
|---|---|---|---|---|---|
| BLCA | 0.6090 | 0.5880 | 0.6183 | 5:0 | 5:0 |
| BRCA | 0.6282 | 0.5907 | 0.6853 | 5:0 | 5:0 |
| LUAD | 0.5741 | 0.5722 | 0.5672 | 1:4 | 2:3 |
| LGG | 0.7911 | 0.8160 | 0.7174 | 0:5 | 0:5 |
| UCEC | 0.5767 | 0.6768 | 0.6156 | 3:2 | 0:5 |

（中位取自 `a_test_report.md` §三；胜负取自 `s5_report.md` §逐 seed 胜负计数。）S5 原文结论："NPJ 骨架的优势不是全面的……LGG 上对两 baseline 0:5 全败（差距最大 −0.1415），UCEC 上对 PORPOISE 0:5 全败"；"PORPOISE（mutsig 配置）是被低估的强 baseline"。骨架 seed 极差 LGG 0.1273、UCEC 0.1389，远大于 PORPOISE 的 0.0302 / 0.0284。

### 2. 创新臂（A 测，B 口径中位；`r4_numbers.txt` 中位节）

| 癌种 | E0 none | E0 both_100 | E0d none | E0d both_100 | E1 none | E1 both_100 |
|---|---|---|---|---|---|---|
| BLCA | 0.6076 | 0.5828 | 0.6091 | 0.5878 | 0.5909 | 0.5711 |
| BRCA | 0.6942 | 0.6147 | 0.6870 | 0.6203 | 0.6737 | 0.5689 |
| LUAD | 0.5788 | 0.5869 | 0.5795 | 0.5849 | 0.6062 | 0.6034 |
| LGG | 0.7926 | 0.5842 | 0.7864 | 0.5959 | 0.7647 | 0.6453 |
| UCEC | 0.6515 | 0.5698 | 0.6644 | 0.6096 | 0.6826 | 0.6343 |

两模态全缺（both_100）相对完整模态的配对Δ中位跌幅：LGG E0 −0.2032 / E0d −0.1905 / E1 −0.1194；UCEC −0.0686 / −0.0485 / −0.0415；BRCA −0.0813 / −0.0818 / −0.0596；BLCA −0.0229 / −0.0224 / −0.0300；LUAD ≈0。

### 3. 逐 seed 判定（胜:负:平，配对Δ中位）

- **E0（NPJ-C）vs S5 NPJ-B，完整模态**：BLCA 3:2:0 (+0.0042)、BRCA 4:1:0 (+0.0031)、LUAD 4:1:0 (+0.0179)、LGG 4:0:1 (+0.0908)、UCEC 5:0:0 (+0.0227)；合计 **20:4:1**。
- **E1（+CAP-Recall）vs E0**：none / rna_100 / text_100 / both_100 —— BLCA 1:4:0 (−0.0248) / 1:4:0 (−0.0217) / 1:4:0 (−0.0158) / 1:4:0 (−0.0193)；BRCA 1:4:0 (−0.0201) / 1:4:0 (−0.0077) / 1:4:0 (−0.0674) / 2:3:0 (−0.0421)；LUAD 4:1:0 (+0.0065) / 4:1:0 (+0.0095) / 3:2:0 (+0.0075) / 4:1:0 (+0.0140)；LGG 0:5:0 (−0.0369) / 2:3:0 (−0.0021) / 0:5:0 (−0.0400) / 5:0:0 (+0.0535)；UCEC 5:0:0 (+0.0280) / 5:0:0 (+0.0396) / 5:0:0 (+0.0556) / 5:0:0 (+0.0643)。both_100 合计 17:8:0。
- **E0d（仅 dropout）vs E0**：20 格点中 16 格 |Δ中位|<0.02；超带 4 格：UCEC none +0.0260、UCEC rna_100 +0.0214、UCEC text_100 +0.0376、LGG text_100 −0.0504。both_100 合计 15:10:0。
- **E1 vs E0d（同协议，只差召回 + 一致性 loss）**：UCEC 3:2:0 (+0.0183) / 5:0:0 (+0.0183) / 4:1:0 (+0.0183) / 5:0:0 (+0.0418)；LGG both_100 4:1:0 (+0.0597)、text_100 3:2:0 (+0.0248)，none 1:4:0 (−0.0338)；BLCA 四格点全负（−0.0248 / −0.0165 / −0.0248 / −0.0264）；BRCA 四格点全负（−0.0201 / −0.0117 / −0.0731 / −0.0568）；LUAD 4:1:0 / 4:1:0 / 3:2:0 / 4:1:0（+0.0058~+0.0160，带内）。both_100 合计 16:9:0。
- **gate 版 both_100 盲补对照**（vs M0-real）：均值盲补 M1 五癌全正（BLCA +0.0078、BRCA +0.0153、LUAD +0.0072、LGG +0.0480、UCEC +0.0323）；学习式召回 M2：+0.0179、+0.0602、−0.0005、+0.0366、+0.0218。

## 二、哪些臂跑了、哪些没跑

| 跑了 | 规模 | 没跑 |
|---|---|---|
| S5 三方：MCAT / PORPOISE / NPJ（A、B 读数） | 3 方 × 5 癌 × 5 seeds = 75 run，完整模态 | 三方在缺失场景的对比（baseline 无缺失协议） |
| gate 版四臂 M0-real / M1 / M1b / M2 | 4 臂 × 25 ckpt × 13 格点 = 1300 格点评测（M1b/M2 各 25 次重训） | — |
| NPJ-C 三臂 E0 / E0d / E1 | 各 25 run × 4 格点 = 300 格点 | E0m（E0 + 评测期均值盲补，零训练）；25/50/75% 部分缺失格点（NPJ-C 版只做 100%） |
| gate 探针（BLCA s123，只读） | 1 ckpt | — |
| 消融 | E0d（dropout 协议） | E1 去一致性 loss；E0 去 attention 仅 masked-mean；原型 bin 数 / EMA / λ 超参扫描 |
| 统计 | 逐 seed 计数 | bootstrap CI、配对检验、多重比较校正 |
| 外部验证 | 无 | 任何非 TCGA 队列 |

## 三、创新点在代码里是否真正接上

| 声称 | 判定 | 依据（`code/NPJ/`） |
|---|---|---|
| 拆 gate，token 进 attention（NPJ-C） | **接上了** | `model/fusion_model.py:1078 class NPJC`；`:1170-1176` `TransformerEncoder(src_key_padding_mask=~valid)`；`:1177-1180` masked-mean；`main_survival.py:204-209` 分支；`scripts/train_launcher.py:56` e0/e0d/e1 全为 NPJC；结果 JSON 的 ckpt 路径含 `_NPJC_` |
| CAP-Recall 在声称的层（attention 之前）替换缺失 token | **接上了** | `fusion_model.py:1137-1168`（stack/backbone 之前调用补偿器并把 valids 置 1）；`compensator.py:121 recall`（WSI 锚 query，原型既是 K 也是 V）；原型仅训练期 EMA 更新（`:72-119`）；e1 ckpt 路径 `out_capr/.../NPJC_` |
| 作者 gate 是否"还在" | E0/E0d/E1 **不含** `GatedFusion`；S5 与 gate 版四臂含之，但其缺失判据 `{mm}_mask` 为死代码（`fusion_model.py:1011-1015`），缺失模态以常量 token 参与加权；**未修复** | `tcga_dataset.py:591` 只产 `{mm}_valid`；探针修对 mask 后 c-index 最大变化 0.0071 |
| MainModalityMoE 的"MoE" | **名不副实**：`num_experts/topk` 传入但从未引用；backbone 在长度 1 序列上运行，自注意力恒等 | `fusion_model.py:965`、`:1055-1056`；`SparseMoeBlock`/`MAGGate` 只被不可达的 MAGFusion/LiMoEFusion/CancerMoE 使用 |
| yml 里的 hidden_size=32 / dropout=0.2 / num_experts | **不生效**（CLI 覆盖，实际 hidden 256、dropout 0.1） | `main_survival.py:656-665` 只取 `pred_dim`、`n_token` |
| 一致性 loss | 接上了，但只在训练期 dropout 位置产生 pair；**未单独消融** | `compensator.py:18-32`、`main_survival.py:483-492` |
| 编码器升级（UNI2-h、自制 BulkRNABert） | 全部臂都用；**不作为创新** | `model/config/surv_multimodal_mainmoe_uni2.yml` |

## 四、能下的结论

1. 在统一 split / 统一评测口径下，NPJ 骨架相对 MCAT/PORPOISE **不具备全面优势**：BLCA/BRCA 领先，LGG 全败，UCEC 不敌 PORPOISE，LUAD 打平；且 seed 方差远大于 baseline。
2. 作者 gate 的缺失处理链路在生存数据集上是死代码；用 attention 融合替换后（E0），完整模态逐 seed 20:4:1 优于 S5 NPJ-B，LGG 配对Δ中位 +0.0908、UCEC +0.0227；BLCA/BRCA/LUAD 在噪声带内。**但**"移除 gate"与"引入 attention 交互"的贡献未分离（缺 E0 去 attention 消融）。
3. CAP-Recall 相对不填充（E0）的效果**强烈依赖癌种与信息缺口**：UCEC 20/20 全胜；两模态全缺时 LGG 5:0（+0.0535）、UCEC 5:0（+0.0643），且这一收益不能由 dropout 协议解释（E0d 在同格点仅 +0.0121 / +0.0114，带内）；BLCA/BRCA 在所有格点为负，负向由"召回 + 一致性 loss"引入而非训练协议。
4. dropout 协议本身对 UCEC 有独立正向（4 格全正、3 格超带），对 LGG 缺文本有害（−0.0504）。
5. 学习式召回相对**任何填充**的优势**未验证**：gate 版对照里均值盲补 M1 五癌全正且在 LGG/UCEC/LUAD 不低于 M2；NPJ-C 侧无盲补臂。

## 五、不能下的结论

- 不能说"gate 有害"（只能说替换后一致更好；贡献未分离）。
- 不能说"CAP-Recall 优于盲补"（E0m 未跑）。
- 不能做协议/召回的份额分解（两分量共享 E0d 且逐 seed 负相关，配对Δ中位不可相加）。
- 不能把跨骨架方向一致性推广到缺失格点（gate 版与 NPJ-C 版缺失基线不同：常量 token vs 不填充；单模态缺失 6 比较 3 反号）。
- 不能把"遮掉某模态反升 ⇒ 召回有害"当规则（BRCA 遮任一模态都掉分却仍被召回伤害；LUAD 反升却受益）。
- 不能宣称任何显著性（无 CI / 检验）；所有 |Δ中位|<0.02 的比较都不作判定依据。
- 不能宣称 UCEC 反超 PORPOISE（E1 0.6826 vs 0.6768，+0.006 在噪声带内）；LGG 追平 MCAT 仅在 B 口径成立（A 口径 0.780 < 0.791）。

## 六、结果不理想的候选原因（候选，不是定论）

1. **口径**：ckpt 由 A 口径（未 sigmoid）的 valid c-index 选出，B 口径只是事后读数修正；作者训练管线 `weight_decay=1` 硬编码；yml 多数超参不生效。这些都可能压低骨架上限。
2. **底座弱且不稳**：骨架在 LGG/UCEC 5-seed 极差 0.10~0.14，单 seed 崩坏（BLCA s213 ≈0.49 在 E0/E0d 同现）；补偿方法建在高方差底座上，方向判定被噪声主导。
3. **作者门控学废**：缺失判据死代码、gate 权重由 RNA token 范数主导（探针 img/text/rna = 0.772/0.203/0.025，RNA 范数 8.2 vs img 0.26）、backbone 在长度 1 序列上退化；S5 与 gate 版四臂的"骨架"实质是 projector + 加权求和。
4. **补偿在信息充足癌种有害**：BLCA/BRCA 的 RNA/文本 token 补回后一致掉分，机理未定（BRCA 并非"遮掉反升"型）。
5. **召回 vs 盲补未分离**：全缺时的收益可能主要来自"有填充"而非"学习式召回"。
6. **baseline 口径偏保守**：baseline 的 test/train n 小于骨架（BRCA train −8.1%），LGG/UCEC 上 baseline 的优势是保守估计，BLCA/BRCA 骨架的领先幅度需打折。
7. **规模**：5 seeds、单一 TCGA 队列、无外部验证、无 CI。

## 七、已知实现债

- E0m 盲补对照未跑（`eval_missing.py --arm m1 --network_type NPJC` 需约 4 行改动：m1 填充位需标记 valid，否则被 NPJC 的 key_padding_mask 屏蔽）。
- 一致性 loss、attention 交互两项消融未做。
- 统计推断未做。
- 作者 gate 的 mask 死代码未修（用户裁决不修、不重训 M0）。
- `eval_missing.py` 写入 JSON 的 `arm` 字段沿用入口参数（E0/E1/M1b/M2 全写 `m0real`），臂身份靠 ckpt 路径。
- `train_launcher.py` 首版契约漏写超参（已补 `--lr 1e-4 --epochs 50 --batch_size 32`）；e0d 门禁按 NPJ 低 util 豁免通道放行。
- 并行评测脚本、训练 ckpt、特征仅在 landau。
