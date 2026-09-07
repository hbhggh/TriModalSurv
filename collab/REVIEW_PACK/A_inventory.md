# A. 只读盘点（2026-09-06；先于任何改动输出）

只列实际存在的东西；找不到的写"未找到"，不猜。路径为仓库相对路径。

## A1. 目录与角色

| 路径 | 角色 | 备注 |
|---|---|---|
| `/`（仓库根） | 项目根 | `README.md`、`AGENTS.md`（公共纪律）、`CLAUDE.md`（指挥官规则） |
| `code/NPJ/` | **主实验代码快照**（本次归档新增） | NPJ 骨架工作树快照（上游 `zongzi13545329/NPJ` @ `4a3d95e` + 本地 3 commit + 未提交改动），排除 `.git`/`__pycache__`；对上游 patch 在 `code/NPJ_changes_vs_upstream.patch`；来源说明 `code/NPJ_SNAPSHOT.md` |
| `NPJ/` | 本地嵌套 git 克隆（**被 .gitignore 忽略，不在仓库内**） | 与 `code/NPJ/` 内容一致 |
| `baselines/MCAT/`、`baselines/PORPOISE/` | 基线克隆（**被忽略，不在仓库内**，1.5GB 含上游 .git/ckpt/数据） | 我方改动只以 patch 形式入库：`collab/20260827-三方对比战役/{mcat_patch.diff,porpoise_patch.diff}`（与当前 `git diff` 逐字节一致，基点 MCAT `b9cca63` / PORPOISE `3390dc4`） |
| `collab/20260826-NPJ三模态复现/` | 复现阶段（数据/管线交接） | `HANDOFF.md`、`plan/notes/result.md`、`审查/codex-对抗审查报告-20260826.md`、`dual_metric_eval.py` |
| `collab/20260827-三方对比战役/` | **S4/S5 三方对比**（MCAT / PORPOISE / NPJ 骨架） | 最终报告 `s5_report.md`；结果 `s5_results/`；`labels_424{,_ex12}.csv`；`s4/`（发车脚本）；`adapters/`（特征转换、split、冻结评测）；`scratch/`（测试脚本、split 小表；二进制/数据已从 git 移除） |
| `collab/20260828-A测缺失补偿/` | A 测早期草案，**已废弃**（plan.md 首行自标 2026-09-02） | 保留作过程证据 |
| `collab/20260902-A测缺失补偿/` | **A 测：缺失补偿创新臂** | 最终报告 `a_test_report.md`（r4）；r3 留档 `a_test_report_r3.md`；结果 `results_npjc/`、`results_npjc_both/`、`results_npjc_e0d/`、`results_gate/`；10 张 `table_*.md`；`r2_numbers.txt`、`r4_numbers.txt`；`figures/`；`probe/`；`tools/`；`ab_first_task.md`（写码引擎 A/B 记录）；`notes_eps_{opus,codex}.md` |
| `collab/20260902-NPJ-GPU合同/` | GPU 利用率合同与配置驱动改造 | `plan.md`、`plan-r2.md`、`notes.md`、`result.md`、`scratch/test_gpu_contract.py` |
| `collab/20260902-坑台账初版/` | 坑台账初版整理 | `plan/notes/result.md` |
| `collab/pitfalls.md` | 坑台账（90 条，D/C/S/E/V/M 六节） | 每条含 Prevention Rule 与出处 |
| `collab/monitor/` | 巡检脚本与记录 | `routine-sweep.md`（321KB 巡检流水）、`check.log`、`rules.env`（仅开关，无凭据） |
| `experiments/{mcat-1536,npj-uni2,porpoise-mutsig-1536}/manifest.md` | S4 三实验身份 manifest | 分支@hash、特征、配置 |

## A2. 方法 / 臂名（以报告实际名字为准）

| 名字 | 含义 | 出处 |
|---|---|---|
| MCAT | Mahmood lab MCAT（co-attention），UNI2-h 1536 维 WSI + 六组 signature 基因组 | `s5_report.md` §实验身份 |
| PORPOISE | Mahmood lab PORPOISE（mutsig 配置，2181 维） | 同上 |
| S5 NPJ-A / NPJ-B | NPJ 骨架 `MainModalityMoE`（作者 gate 版）；A=作者口径读数，B=sigmoid 修正读数（同一 ckpt） | `s5_report.md`、`a_test_report.md` §实验臂 |
| E0 = NPJ-C | 移除 GatedFusion，三模态 token 进 `TransformerEncoder`，缺失位 key_padding_mask 屏蔽（不填充） | `a_test_report.md` §实验臂 |
| E0d | E0 + modality dropout 0.15（无召回、无一致性 loss）消融臂 | 同上 |
| E1 = NPJ-C + CAP-Recall | E0 + 癌种分库原型召回（WSI 锚 cross-attention）+ dropout 0.15 + 一致性 loss λ=0.1 | 同上 |
| M0-real / M1 / M1b / M2 | gate 版四臂：S5 ckpt 原样测试遮挡 / 评测期均值盲补 / 可学习 MissingBank / gate 版 CAP-Recall | `a_test_report.md` §四、`table_gate_4arms.md` |

## A3. 数据、split、seed、口径

- 癌种：BLCA / BRCA / LUAD / LGG / UCEC。
- split：`labels_424` 4:2:4（train/valid/test），test 冻结一次评估；12 例剔除（BRCA 7、LUAD 5，用户裁决）→ `labels_424_ex12.csv`（4985 行）；landau 侧 NPJ 用 `data/TCGA_9523_ex12.csv`。
- seeds：123 / 132 / 213 / 231 / 321（5 seeds 逐值呈现，不报均值±方差）。
- 口径：A = 作者口径（raw logits 直接 cumprod 成风险）；B = 修正口径（sigmoid+clamp 后 cumprod）。**ckpt 由 A 口径 valid 选出**；创新臂主口径 B、A 附列；baseline（MCAT/PORPOISE）无 A/B 之分，单一 sksurv `concordance_index_censored` 读数。
- 缺失协议：`missing_manifest_v1.csv`（SHA256 `c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156`，嵌套抽样 25⊂50⊂75，仅 test 患者）；gate 版 13 格点（none + rna/text/both × 25/50/75/100），NPJ-C 版 4 格点（none / rna_100 / text_100 / both_100）。
- 判定规则：逐 seed 严格 `>` 计数（胜:负:平，|Δ|≤1e-6 记平），配对Δ中位；|Δ中位|<0.02 为噪声带；**未做 bootstrap CI / 配对检验**。
- test n：BLCA 138、BRCA 383（baseline 347）、LUAD 172（baseline 167）、LGG 166（163）、UCEC 198（190）——baseline test n 小于骨架（数据口径注记）。

## A4. 结果文件（只列存在的）

| 路径 | 内容 | 数量 |
|---|---|---|
| `collab/20260827-三方对比战役/s5_results/` | MCAT/PORPOISE 冻结 test 评测 json + `npj_dual_metric.json` | 51 json |
| `collab/20260827-三方对比战役/s5_report.md` | S5 三方判定报告（r2+r3 补注） | 1 |
| `collab/20260902-A测缺失补偿/results_npjc/{e0,e1}/` | E0/E1 三格点评测 json（+ 评测 log） | 50 json |
| `collab/20260902-A测缺失补偿/results_npjc_both/{e0,e1}/` | E0/E1 both_100 补评测 | 50 json |
| `collab/20260902-A测缺失补偿/results_npjc_e0d/` | E0d 四格点评测 json + 25 训练 log + 25 评测 log + `runs_state_snapshot.json` | 25 json |
| `collab/20260902-A测缺失补偿/results_gate/{m0real,m1,m1b,m2}/` | gate 版四臂 13 格点评测 json | 100 json |
| `collab/20260902-A测缺失补偿/results_npjc_e0m/` | E0m（E0 ckpt + 评测期均值盲补）四格点评测 json + log（2026-09-06） | 25 json |
| `collab/20260902-A测缺失补偿/table_*.md` | 汇总表（脚本生成） | 10 |
| `collab/20260902-A测缺失补偿/r2_numbers.txt`、`r4_numbers.txt` | 对账留档（脚本生成；r4 版十七节） | 2 |
| `collab/20260902-A测缺失补偿/figures/` | `npjc_e0_e1_4grids.{png,svg}`、`gate_missing_curves.{png,svg}` | 4 |
| `collab/20260902-A测缺失补偿/probe/` | gate 探针 jsonl（S5 ckpt / M2 ckpt，BLCA s123） | 2 |
| `collab/20260902-A测缺失补偿/s5_full_reference.csv` | S5 三方逐 seed 参照（76 行） | 1 |
| 训练 ckpt | **仓库内无**；全部在 landau `/home/wuhao/NPJ/{out,out_capr,out_bank,out_e0d}/` 与 `/home/wuhao/p3_results/` | 未上传 |
| 特征（UNI2-h / BulkRNABert / 文本嵌入） | **仓库内无**；仅 landau | 未上传 |

## A5. 关键代码路径（`code/NPJ/` 内；`文件:行 函数`）

| 环节 | 位置 |
|---|---|
| 训练入口 / CLI | `main_survival.py:53 parsing_args`（`--network_type`、`--compensator {none,capr,bank}`、`--modality_dropout`、`--consistency_lambda`）；`:631 main`；`:656 load_model` |
| 数据集：manifest 遮挡 / dropout / 键名 | `loc_utils_3yr/tcga_dataset.py:316 TCGASurDataset`；`:426-459` missing_grid；`:471-483` modality_dropout；`:535 safe_modality_get`（缺失置零 + mask=0）；`:590-591` 产出 `{mm}` 与 `{mm}_valid` |
| 作者融合（gate 版） | `model/fusion_model.py:962 MainModalityMoE`；`:917 GatedFusion`；**`:1011-1015` 读 `{mm}_mask`（数据集从不产出该键 → 死代码）**；`:1055-1056` backbone 在长度 1 序列上运行 |
| 新融合（NPJ-C） | `model/fusion_model.py:1078 NPJC`；`:1137-1168` 补偿器插入点（在 attention 之前）；`:1170-1176` stack + `TransformerEncoder(src_key_padding_mask)`；`:1177-1180` masked-mean |
| 补偿器 | `model/compensator.py:34 CAPRecall`（`:72 update_prototypes` EMA；`:121 recall`；`:135 forward`）；`:175 MissingBank`；`:223 consistency_loss` |
| 生存头 / loss / A-B 口径 | `model/fusion_model.py:952 SurvivalHead`（无 sigmoid）；`loc_utils_3yr/loss_func.py:70`（训练 loss 内 sigmoid）；`main_survival.py:476,518-525,585-586`（训练/验证/测试 c-index 均 A 口径）；`scripts/eval_missing.py:138 dual_risk_from_logits`（A/B 双口径） |
| 评测入口 | `scripts/eval_missing.py`（`--arm {m0real,m1}`、`--network_type`、`--compensator`、`--manifest`、`--grids`） |
| 发车器 / 门禁 | `scripts/train_launcher.py:56 ARM_PRESETS`（e0/e0d/e1）；`scripts/launch_formal.sh`；`scripts/gpu_util_gate.py`；`config/gpu_train.yaml` |
| 缺失 manifest 生成 | `scripts/gen_missing_manifest.py` |
| 基线入口（仓内） | `collab/20260827-三方对比战役/s4/s4_run_method_cancer.sh`；`adapters/eval_frozen_test.py`（冻结 ckpt test-only 评估 + 分箱审计）；`adapters/{uni2h_to_ptfiles,bulkrnabert_infer,make_splits,build_outcome_table}.py` |

## A6. 已有 MD（思考链）

`README.md`；`collab/20260826-NPJ三模态复现/HANDOFF.md`；各战役 `plan.md` / `notes.md` / `result.md`；`collab/20260827-三方对比战役/s5_report.md`；`collab/20260902-A测缺失补偿/{a_test_report.md, a_test_report_r3.md, ab_first_task.md, notes_eps_opus.md, notes_eps_codex.md}`；`collab/20260902-NPJ-GPU合同/plan-r2.md`；`collab/pitfalls.md`；`collab/pitfalls-routine.md`；`collab/monitor/routine-sweep.md`；`experiments/*/manifest.md`。

## A7. 未找到 / 不在仓库内

- 根目录 `LICENSE`：未找到（`code/NPJ/LICENSE` 为上游 Apache-2.0；本仓库其余内容许可未声明）。
- 根目录 `requirements.txt` / `environment.yml`：未找到；唯一环境定义 `code/NPJ/tcga.yaml`（conda）。
- `run_eval_parallel.sh`、`eval_one.sh`、`gen_eval_tasks.sh`、`launch_e0d.sh`：仓库内未找到，仅在 landau `/home/wuhao/NPJ/`（notes 有描述）。
- `tmp_sur_cache/`（dataset 缓存）：本地未找到，仅 landau。
- NPJ 训练 ckpt、UNI2-h/BulkRNABert/文本特征、原始 WSI/RNA：仓库内无。
- 统计推断（bootstrap CI / 配对检验）结果：未做，无文件。
- E0dm（E0d + 评测期均值盲补）结果：未跑，无文件（E0m 已跑，见 `results_npjc_e0m/`）。
- （r6，2026-09-07）NPJ-D 线：`collab/20260906-NPJ-D消融/results_npjd_d0/`（125 JSON + `logs/` 250 log + runs_state 快照）、`results_npjd_dm/`（125 JSON + 125 log）、`results_npjc_e1_25/`（100 JSON + 200 log）、`table_npjd_D_Dm_E1_3grids_{A,B}.md`、`table_npjd_D_Dm_E1_both100_{A,B}.md`、`table_npjd_D_Dm_E1_absolute_25seed.md`（绝对值逐 seed，`tools/abs_table.py`）、`r6_numbers.txt`、`smoke/`、`审查/adversarial-review-{raw.json,findings.md,focus.txt}`、`tools/`（`launch_d0.sh`、`launch_e1_seeds.sh`、`eval_dm_one.sh`、`run_dm.sh`、`parity_d.py`、`count_natural_missing.py`、`r6_numbers.py`）。landau 侧（不在仓库）：`out_d0/` 125 ckpt、`backup_20260906_npjd/`。D+原型单因素臂、E0dm：未跑，无文件。
