# plan.md — 三方对比战役：适配管线（Codex 派单契约）

> 总纲：`~/.claude/plans/twinkling-greeting-kahan.md`（用户已批准 v3）。派单人 Claude，执行人 Codex。
> Codex 义务：执行中追加本目录 `notes.md`，完成后写 `result.md`（含全部自测输出）。

## 背景

对比三方：MCAT（`baselines/MCAT`）、PORPOISE（`baselines/PORPOISE`）、NPJ 骨架（landau 已复现）。五癌种 BLCA/BRCA/LUAD/LGG/UCEC、我们的 CSV 4:2:4 split、5 seeds。已侦查：两库官方队列恰为 blca/brca/gbmlgg/luad/ucec，自带基因组 CSV（`datasets_csv*/tcga_*_all_clean.csv.zip`）；split 格式为 `splits_{i}.csv`（train/val 两列 case_id）。WSI 统一用 UNI2-h 1536（转 pt_files）。我们的标签 CSV 在 landau `/home/wuhao/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv`，本地副本见本目录 `labels_424.csv`（Claude 提供，含 patient_id/cancer_type/split/survival_months/censorship 五列脱敏版）。

## 任务 A：MCAT/PORPOISE 数据契约分析 + 适配脚本三件套

### A0 契约分析（先做，写进 result.md）
通读 `baselines/MCAT/{main.py,datasets/dataset_survival.py,utils/core_utils.py}` 与 PORPOISE 对应文件，回答：
1. 特征加载：pt_files 的路径拼接规则（data_root_dir/？/pt_files/<slide_id>.pt？）、slide_id 从 CSV 哪列来、多切片病人如何聚合
2. 基因组输入：dataset CSV 哪些列、signatures.csv 如何分组、`--apply_sig` 等关键开关
3. split 消费方式：val 是否参与模型选择（决定我们 train/val 列怎么填，见 A1 注）
4. 生存标签：用哪列、如何分 bin、censorship 语义方向
5. seed 与评估：--seed 传播到哪、最终 c-index 用什么函数、结果文件落在哪
6. `--path_input_dim`/特征维度参数是否支持 1536
7. MCAT 与 PORPOISE 的差异点清单

### A1 脚本 `make_splits.py`
输入：labels_424.csv + 库名 + 癌种。输出：`splits_0.csv`（我们的 split → 其格式）。
- 默认映射 train列=our train, val列=our test；**若 A0 发现 val 参与 epoch/模型选择，改为 train列=our train+valid, val列=our test，并在 result.md 说明依据**
- LGG：用 gbmlgg 的 dataset CSV，按 labels_424.csv 的 LGG patient_id 过滤
- 打印交集统计：我们 split 病人 vs 库 CSV case_id 的交集/缺失数（逐癌种逐 split）
**验收**：BLCA 上运行产出 splits_0.csv；交集统计打印；缺失病人清单落盘。

### A2 脚本 `uni2h_to_ptfiles.py`
输入：UNI2-h 的 TCGA-<C>.tar.gz（格式同 `collab/20260826-NPJ三模态复现/convert_uni2h_to_npj.py` 所述：每切片 .h5，features [1,N,1536]）。输出：`<out>/pt_files/<slide_id>.pt`（torch.FloatTensor [N,1536]）。
- slide_id 命名与库 CSV 的 slide_id 列对齐（A0 查明格式后决定保留全名或截断）
- 逐成员解压用完即删；自检块：切片数/病人数/维度
**验收**：用合成 h5（构造 [1,50,1536]）跑通并打印自检。

### A3 冒烟命令序列（写进 result.md，不执行真实训练）
给出 BLCA 上 MCAT 与 PORPOISE 各一条完整可执行命令（含 --seed 123、指向我们的 splits/特征/CSV、1 epoch 试跑参数如支持），及预期输出位置。

## 任务 B：GDC STAR-Counts 下载管线（骨架 4 新癌种 RNA）

脚本 `gdc_fetch_star_counts.py`：
- 输入：labels_424.csv + 癌种列表（BRCA/LUAD/LGG/UCEC）
- GDC API（api.gdc.cancer.gov）按 project TCGA-<C> + data_type "Gene Expression Quantification" + workflow "STAR - Counts" + open access 查询；样本条码仅保留 01（原发瘤）；一病人多文件取一（规则写死并记录）
- 输出：manifest CSV（patient_id, file_id, file_name, md5）+ 下载函数（断点续传：已存在且 md5 对则跳过）+ 末尾自检（每癌种：CSV 病人数 vs 命中数 vs 缺失清单）
- 只查询与下载，不做表达预处理（BulkRNABert 预处理是后续独立步骤）
**验收**：--dry-run 模式只打 manifest 统计不下载；用 BRCA 前 5 个病人实测小批量下载 5 个文件校验 md5。

## 文件白名单

```
/Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/adapters/make_splits.py        （新建）
/Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/adapters/uni2h_to_ptfiles.py   （新建）
/Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/adapters/gdc_fetch_star_counts.py（新建）
/Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/{notes.md,result.md}
本目录下 scratch/ 内任意自测临时文件
```

## 禁止事项

- 不得修改 `baselines/MCAT`、`baselines/PORPOISE`、`NPJ/` 下任何文件（只读）
- 不得 git commit/push；不得 ssh/scp/访问 landau；不得下载超过自测所需（GDC 实测 ≤5 个文件）
- 不得安装依赖（可用系统 python3 + 已有库；缺库时在 notes.md 记录并给出降级自测）
- 解压库自带的 csv.zip 到 scratch/ 允许

## 测试命令（Codex 自测，Claude 复跑）

```bash
cd /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役
python3 adapters/make_splits.py --lib MCAT --cancer BLCA --labels labels_424.csv --out scratch/splits_mcat_blca/   # 交集统计+splits_0.csv
python3 adapters/uni2h_to_ptfiles.py --selftest                                                                    # 合成数据自检
python3 adapters/gdc_fetch_star_counts.py --labels labels_424.csv --cancers BRCA --dry-run                         # manifest 统计
python3 adapters/gdc_fetch_star_counts.py --labels labels_424.csv --cancers BRCA --limit 5 --out scratch/gdc_test/ # 5 文件实测
```

## 任务 C：MCAT 最小可运行补丁（用户已批准，2026-08-27）

修复清单（全部源自 A0 契约分析，每处最小 diff）：
1. `main.py`：parser 补 `--inst_loss`，默认值与现有引用处兼容（None/字符串，读代码定）
2. parser 补 `--testing`（默认 False），与 `core_utils.py` 的 `args.testing` 引用一致
3. `Generic_Split` 的 `fast_cluster_ids.pkl` 读取改为条件化（仅 `mode=='cluster'`，对齐 PORPOISE 写法）
4. signature 目录引用改指实际存在的 `datasets_csv_sig/`（改代码不动目录）
5. `MCAT_Surv` WSI 输入维参数化：新增 `--path_input_dim`（**默认 1024 = 官方原行为**），贯通到模型 size_dict；1536 由命令行显式传入

约束：
- 白名单 = `baselines/MCAT/` 内为实现上述 5 点所必需的最少文件 + 本目录 `mcat_patch.diff`（git diff 留档）+ notes.md/result.md 增补
- 默认行为必须与官方一致（不传新参数时零行为变化）；禁止任何超出 5 点的重构/清理
- 自测（mac protomasksurv-exp1 env，CPU）：①`--help` 跑通 ②合成 pt 特征（[50,1536] 与 [50,1024] 各一）+ 官方 BLCA CSV + A1 splits 构造 mini 冒烟：dataset 构建 + 模型 forward 各一遍（1024 默认路径与 1536 新路径都要过），不做完整训练
- 完成后 `git -C baselines/MCAT diff > collab/20260827-三方对比战役/mcat_patch.diff`

---

# 修复轮 Round 2（2026-08-27，adversarial review 5 findings，用户批准 3 路并行）

公共约束（三路都读）：遵守项目根 AGENTS.md 全部条款；禁止开任何正式训练；禁止 ssh/landau；禁止 git commit/push；每路完成后 result.md 增补节必含四项——改了哪些文件 / 对应哪条 finding / 怎么验证的 / 有没有动到白名单外目录。

## 路 A：统一结局表 + split 契约修正（finding 1 + 2）

1. 新建 `adapters/build_outcome_table.py`：
   - 以 labels_424.csv 为唯一真源，输出 `scratch/outcome_table.csv`（patient_id / survival_months / censorship）
   - 为 MCAT 与 PORPOISE 各生成 adapted dataset CSV（读官方 csv.zip → 把其中 survival_months / censorship 列**替换**为 labels_424 值，保留其余全部基因组与元数据列）→ 写 `scratch/adapted_csv/<lib>_tcga_<cancer>_adapted.csv.zip`（5 癌种；LGG 从 gbmlgg 过滤）
   - 逐患者硬校验：替换后 CSV 的结局与 labels_424 完全一致，否则非零退出
   - 替换前差异审计：按癌种输出旧值/新值差异分布（30 vs 30.44 换算假设的符合率）与异常值清单 `scratch/outcome_audit_<cancer>.csv`（含 review 提到的 UCEC 异常值）
2. 修改 `adapters/make_splits.py`：映射改为 **train=our train, val=our valid**；删除 train+valid 合并逻辑；--adapted-csv 参数指向 1 的产物
3. 新建 `adapters/eval_frozen_test.py`：加载指定 checkpoint（s_0_checkpoint.pt），在 our test 病人上构造该库 dataset 并 forward 一次，`sksurv.concordance_index_censored` 计算 c-index，打印逐患者数与结果 JSON；test 绝不在训练期出现
**验收**：BLCA+LGG 上跑通 1→2→3 链（3 用合成 checkpoint 或跳过 forward 的 --dry-run 结构校验）；校验/审计文件落盘；make_splits 输出显示 train=136 val=68（BLCA）

## 路 B：MCAT 实验身份隔离（finding 3）

修改 `baselines/MCAT`（最小 diff）：
- `path_input_dim` 写入实验身份：param_code/exp_code 追加 `_pid{path_input_dim}`；settings 记录 path_input_dim 与 data_root_dir
- 结果目录已存在时：读取其 settings/experiment 记录，元数据（path_input_dim、data_root_dir）不完全匹配 → 硬失败退出，禁止复用 fold 产物
- 默认 1024 时行为与官方目录命名的差异仅限追加后缀（可接受，写入 result.md 说明）
**验收**：mac CPU 干跑 main.py 到目录创建段（--testing 或早退方式），证明 1024 与 1536 落不同目录、元数据不匹配时硬失败；`git -C baselines/MCAT diff > collab/20260827-三方对比战役/mcat_patch.diff` 更新

## 路 C：PORPOISE 全 collator 修复 + UNI2 事务化（finding 4 + 5）

1. `baselines/PORPOISE/utils/utils.py`：collate_MIL_survival / _sig / _cluster 三个统一修（tensor 列表 → torch.stack/cat 后显式 dtype；与已修的 survival 版一致化）；新增/更新 `porpoise_patch.diff`
2. 首批集成自测：官方 BLCA CSV + 合成 pt + A1 splits，DataLoader 首批真实取数，覆盖 pathomic 与 coattn 两种 mode 的 collator 路径（cluster 无数据则构造最小合成）
3. `adapters/uni2h_to_ptfiles.py` 事务化：staging 目录转换 → 全成员校验 + manifest（成员/shape/checksum）→ 原子 rename 发布 pt_files；written==0 非零退出；--overwrite 语义 = 整套替换（发布前删旧集），绝不留混合
**验收**：--selftest 扩展为含事务语义测试（半途失败不留最终目录、written==0 失败、overwrite 全替换）；PORPOISE 首批测试双 mode 输出

## 文件白名单（Round 2）

- 路 A：`adapters/build_outcome_table.py`（新）、`adapters/make_splits.py`、`adapters/eval_frozen_test.py`（新）、scratch/、notes.md、result.md
- 路 B：`baselines/MCAT/` 内必需最少文件、`mcat_patch.diff`、notes.md、result.md
- 路 C：`baselines/PORPOISE/utils/utils.py`、`adapters/uni2h_to_ptfiles.py`、`porpoise_patch.diff`、scratch/、notes.md、result.md
- 三路互不触碰对方白名单；违者判越权
