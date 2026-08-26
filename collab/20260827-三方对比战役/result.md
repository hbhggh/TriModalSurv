# 三方对比战役任务 A/B 执行结果

执行日期：2026-08-27（JST）  
工作区：`/Users/wuhao/Desktop/TriModalSurv`  
执行范围：`plan.md` 的任务 A（A0/A1/A2/A3）与任务 B。

## 1. 结论

**整体状态：PARTIAL / BLOCKED，不是全项 PASS。** A1、A2、任务 B 与 A0 证据报告可交付；A3 的 MCAT 命令受当前 baseline 源码与 1536 维契约阻断，故 `plan.md` 不能宣称全部验收。

- A0 契约分析：完成，七问逐条回答见第 3 节。
- A1 `make_splits.py`：完成。BLCA 的 train/valid/test 均 0 缺失；输出 train=204（our train+valid）、val=138（our test）。
- A2 `uni2h_to_ptfiles.py`：完成。计划指定的默认 `python3` 缺少 `h5py/torch`，原命令真实退出 2；未安装依赖。使用本机已有训练环境完成合成 `[1,50,1536] -> FloatTensor [50,1536]` 自检，PASS。
- A3 冒烟命令：PORPOISE 给出不修改 baseline 的完整 1-epoch 命令序列；MCAT 当前快照无法在“UNI2-h 1536 + 禁止修改 baseline”约束下形成真实可执行命令，明确标记为 **BLOCKED**，未伪造可运行性。
- B `gdc_fetch_star_counts.py`：完成。BRCA dry-run 得到 labels 965、命中 963、缺失 2；真实下载严格限制为 5 个文件，脚本校验及独立重算 MD5 均通过。
- 四条计划原命令已全部实际执行：第 1、3、4 条 exit 0；第 2 条因默认 Python 缺依赖 exit 2，并已有合规降级自检证据。

## 2. 改动与产物清单

### 2.1 交付文件

- `adapters/make_splits.py`
- `adapters/uni2h_to_ptfiles.py`
- `adapters/gdc_fetch_star_counts.py`
- `notes.md`
- `result.md`

### 2.2 白名单内自测文件与产物

- `scratch/task_a_behavior_test.py`
- `scratch/task_b_behavior_test.py`
- `scratch/splits_mcat_blca/`：`splits_0.csv` 与三个缺失清单。
- `scratch/gdc_star_counts/`：dry-run manifest 与缺失清单。
- `scratch/gdc_test/`：manifest、缺失清单和 5 个经 MD5 校验的 STAR-Counts TSV。
- `scratch/*pycache*/`：测试/语法检查缓存，均位于允许的 scratch 范围。

只读的 `baselines/MCAT`、`baselines/PORPOISE`、`NPJ/`、既有 `labels_424.csv` 均未修改；未执行 git commit/push，未执行 ssh/scp，未访问 landau，未安装依赖。

## 3. A0 契约分析七问

### 3.1 特征加载

MCAT 与 PORPOISE 的基本加载契约相同：

1. 官方 dataset CSV 的原始 `slide_id` 列用于构造每位患者的 `patient_dict[case_id] -> slide_id[]`；随后患者级 `slide_data` 把 `slide_id` 改成 `case_id`，因此 split CSV 的 train/val 列应填患者 `case_id`，不是切片名。
2. 主程序把 WSI 数据目录设为 `<data_root_dir>/<study>_20x_features`；BLCA 即 `<data_root_dir>/tcga_blca_20x_features`。
3. 每张切片的实际读取路径是 `<data_dir>/pt_files/<slide_id.rstrip('.svs')>.pt`。源码使用的是 Python `rstrip('.svs')`，虽然语义是删除末尾字符集合而非严格后缀，但官方 TCGA `.svs` 名称下会得到不含 `.svs` 的完整切片 ID。
4. 一位患者有多张切片时，逐张 `torch.load()` 后用 `torch.cat(path_features, dim=0)` 沿 patch 维拼接。
5. 官方样例切片名形如 `TCGA-2F-A9KO-01Z-00-DX1.195576CF-....svs`。因此 A2 只删除 `.h5`，保留 `DX1.` 后的完整 UUID，输出 `pt_files/TCGA-...-DX1.<UUID>.pt`。

### 3.2 基因组输入、signatures 与关键开关

- 官方 CSV 含 `case_id`、`slide_id`、临床/生存字段和大量基因组列；常见后缀为 `*_cnv`、`*_rnaseq`，PORPOISE 的 mutsig CSV 还包含 `*_mut`。
- `signatures.csv` 有六组：Tumor Suppressor Genes、Oncogenes、Protein Kinases、Cell Differentiation Markers、Transcription Factors、Cytokines and Growth Factors。
- `--apply_sig` 会读取 signatures；每组基因名扩展为 `_mut/_cnv/_rnaseq`，与当前 genomic columns 取交集，形成六个 omic group 及 `omic_sizes`，供 co-attention 使用。
- `--apply_sigfeats` 只切换 dataset CSV 路径并给实验名加 `_sig`，不会自动等价于 `--apply_sig`。
- MCAT 当前代码期望 `dataset_csv_sig/`，仓库实际目录却是 `datasets_csv_sig/`；其 `--apply_sig` 和 `--apply_sigfeats` 路径均存在单复数不一致。
- PORPOISE 的默认目录是 `datasets_csv/`；`--apply_mutsig` 切换到实际存在的 `datasets_csv_mutsig/`。`--apply_sig`/`--apply_sigfeats` 会指向当前不存在的 `datasets_csv_sig/`。
- PORPOISE BLCA 的 `datasets_csv` 与 `datasets_csv_mutsig` 患者集合完全一致：373 vs 373，集合差异为 0；A1 split 可安全供 `--apply_mutsig` 使用。

### 3.3 split 消费与 val 是否参与模型选择

- 两库都只读取 `splits_<fold>.csv` 的 `train`、`val` 两列；`test_split` 未启用。
- val 每个 epoch 都会跑验证并计算 val loss/c-index；`--early_stopping` 默认 False。开启后 `validate_*` 会按 val loss 更新状态并写 `s_<fold>_minloss_checkpoint.pt`，但外层训练循环只接收 `stop`、没有 `break`，所以当前源码实际上不会提前停止。
- `Monitor_CIndex` 虽被实例化，但训练循环未调用它；结束时无条件保存/载入最后 epoch 的 `s_<fold>_checkpoint.pt`。因此当前源码既不按最佳 val c-index 选模，也不回载 min-loss checkpoint；val 只进入逐 epoch 监控和最终报告，不影响最终权重选择。
- `plan.md` 的 A1 条件写作“val 参与 epoch/模型选择”。这里 val 明确参与每个 epoch 的验证消费，故按该条件采用 `train=our train+valid`、`val=our test`；但必须明确：它在当前源码中不构成有效的 early stopping 或 checkpoint 选择。our test 实际成为 baseline 的验证/报告集，不再是完全独立、训练过程不可见的最终 test。

### 3.4 生存标签、分 bin 与 censorship 方向

- 连续时间列：`survival_months`。
- 先对患者去重，仅用 `censorship < 1` 的未删失患者做 `pd.qcut(..., q=4)` 求四分位边界；再把首尾边界扩到全队列最小/最大值，对全部患者用 `pd.cut(..., right=False)` 分成 4 个离散时间 bin。
- `censorship=0` 表示观察到事件，`censorship=1` 表示删失。
- 评估时传给 scikit-survival 的事件指示为 `(1-censorship).astype(bool)`。

### 3.5 seed、评估函数与输出

- `--seed` 进入 Python `random`、`PYTHONHASHSEED`、NumPy、Torch CPU、CUDA 单卡/多卡；CUDA 时还设置 `cudnn.benchmark=False`、`cudnn.deterministic=True`。每个 fold 开始前再次调用相同 seed 函数。
- c-index 使用 `sksurv.metrics.concordance_index_censored(..., tied_tol=1e-08)[0]`。
- 结果根路径由 `<results_dir>/<which_splits>/<param_code>/<exp_code>_s<seed>/` 组成。
- fold 0 的主要文件为 `split_latest_val_0_results.pkl`、`s_0_checkpoint.pt`、`splits_0.csv`，另有 `summary_latest.csv`、`experiment_<exp_code>.txt` 和 TensorBoard 子目录 `0/`；若开启 early stopping，还会产生 `s_0_minloss_checkpoint.pt`。

### 3.6 1536 维支持

- MCAT 没有 `--path_input_dim`。`MCAT_Surv.size_dict_WSI` 的输入固定为 1024，不能直接接收 A2 的 `[N,1536]`。
- PORPOISE 有 `--path_input_dim`，但它只在 `model_type=porpoise_mmf` 的 small path branch 中传入并生效；因此可用 `--model_type porpoise_mmf --mode pathomic --fusion concat --path_input_dim 1536`。
- PORPOISE 的其他模型不能仅凭该参数推断为支持 1536；尤其 MCAT/AMIL 类仍有各自固定维度实现。

### 3.7 MCAT 与 PORPOISE 差异点

1. PORPOISE 额外提供 `porpoise_mmf`、`porpoise_amil`、`pathomic_fast`、`--apply_mutsig`、gating/scale/dropinput/use_mlp 和 `--path_input_dim`；MCAT 没有这些接口，但其 loss choices 多一个 `cox_surv`。
2. PORPOISE 的 `pathomic_fast` 会读 `split_<fold>_case_pt/<case_id>.pt`，并在 split 上设置 `split_id`；MCAT 没有该路径。
3. PORPOISE 的 `Generic_Split` 只在 `mode=cluster` 时读取 `fast_cluster_ids.pkl`；MCAT 当前快照无条件读取该文件，即便 `mode=coattn/pathomic` 也会要求它存在。
4. PORPOISE parser 定义了 `--testing`；MCAT 的 core 使用 `args.testing`，但 parser 未定义。
5. MCAT main 记录 settings 时访问 `args.inst_loss`，但 parser 未定义，进入 dataset/training 前即可能抛 `AttributeError`。
6. PORPOISE 默认 CSV 在当前快照与硬编码 metadata 顺序不一致；`--apply_mutsig` 的 CSV 顺序与断言一致。MCAT 没有同一条硬编码 assert，但存在 signature 目录单复数错误。
7. 两库的 censorship、离散时间 bin、split 读取和 c-index 主逻辑高度相似；关键差异集中在模型、特征路径、参数完整性和当前快照缺陷。

## 4. A1 `make_splits.py`

实现内容：

- 支持 MCAT/PORPOISE 与 BLCA/BRCA/LUAD/LGG/UCEC。
- LGG 自动读取 `tcga_gbmlgg_all_clean.csv.zip`，再按 `labels_424.csv` 的 LGG patient_id 过滤。
- 同一癌种内若 patient_id 重复出现，或同时出现在 train/valid/test 多个 split，立即失败，防止患者泄漏。
- 逐 split 打印我们病人数、库病人数、交集、缺失，并写 `missing_<CANCER>_<split>.csv`。
- 输出两列 `splits_0.csv`；映射固定为 train=`our train+valid`，val=`our test`。

BLCA 实测：our train 136/交集 136/缺失 0；valid 68/68/0；test 138/138/0；最终 train 204、val 138。

## 5. A2 `uni2h_to_ptfiles.py`

实现内容：

- 输入可为 `TCGA-<C>.tar.gz` 或 h5 目录；严格要求 `features` 形状 `[1,N,1536]` 且 `N>0`。
- 输出 `<out>/pt_files/<完整 slide_id>.pt`，类型为 `torch.float32`，形状 `[N,1536]`。
- tar 按成员流式复制到临时 h5；复制、读取、校验或保存任一步异常都进入 `finally` 删除该临时文件。
- 非法患者名在写 `.pt` 前失败；同次输入内重复 slide_id 即使加 `--overwrite` 也拒绝，避免静默覆盖。
- 普通转换结束打印切片数、患者数、维度集合与输出目录；`--selftest` 构造 `[1,50,1536]`。

## 6. A3 冒烟命令序列

### 6.1 PORPOISE：完整命令（按计划不执行训练）

该序列只在任务目录的 `scratch/porpoise_smoke/` 建运行影子，不修改 baseline。`PORPOISE_PY` 必须替换为已装好 PORPOISE 依赖（含 torchvision/torch_geometric）的 Python；`UNI2H_BLCA_TAR` 替换为真实归档绝对路径。

```bash
set -euo pipefail
TRIMODAL_REPO=/Users/wuhao/Desktop/TriModalSurv
TRIMODAL_TASK="$TRIMODAL_REPO/collab/20260827-三方对比战役"
PORPOISE_PY=/ABS/PYTHON/WITH/PORPOISE/DEPENDENCIES
UNI2H_BLCA_TAR=/ABS/PATH/TCGA-BLCA.tar.gz
PORPOISE_RUN="$TRIMODAL_TASK/scratch/porpoise_smoke"
PORPOISE_FEATURE_ROOT="$PORPOISE_RUN/features"

python3 "$TRIMODAL_TASK/adapters/make_splits.py" \
  --lib PORPOISE --cancer BLCA --labels "$TRIMODAL_TASK/labels_424.csv" \
  --out "$PORPOISE_RUN/generated_splits"

"$PORPOISE_PY" "$TRIMODAL_TASK/adapters/uni2h_to_ptfiles.py" \
  --src "$UNI2H_BLCA_TAR" --cancer BLCA \
  --out "$PORPOISE_FEATURE_ROOT/tcga_blca_20x_features" \
  --tmp-dir "$PORPOISE_RUN/tmp_members"

mkdir -p "$PORPOISE_RUN/work/splits/custom424/tcga_blca" "$PORPOISE_RUN/results"
cp "$PORPOISE_RUN/generated_splits/splits_0.csv" \
  "$PORPOISE_RUN/work/splits/custom424/tcga_blca/splits_0.csv"
test -L "$PORPOISE_RUN/work/datasets_csv_mutsig" || \
  ln -s "$TRIMODAL_REPO/baselines/PORPOISE/datasets_csv_mutsig" \
  "$PORPOISE_RUN/work/datasets_csv_mutsig"

cd "$PORPOISE_RUN/work"
PYTHONPATH="$TRIMODAL_REPO/baselines/PORPOISE" \
"$PORPOISE_PY" "$TRIMODAL_REPO/baselines/PORPOISE/main.py" \
  --seed 123 --k 1 --k_start 0 --k_end 1 --max_epochs 1 \
  --data_root_dir "$PORPOISE_FEATURE_ROOT" \
  --which_splits custom424 --split_dir tcga_blca \
  --results_dir "$PORPOISE_RUN/results" \
  --model_type porpoise_mmf --mode pathomic --fusion concat \
  --apply_mutsig --path_input_dim 1536 \
  --batch_size 1 --gc 1 --overwrite
```

预期输出目录：

```text
scratch/porpoise_smoke/results/custom424/
  PorpoiseMMF_nll_surv_a0.0_custom424_mutsig_concat/
    tcga_blca_PorpoiseMMF_nll_surv_a0.0_custom424_mutsig_concat_s123/
```

其中预期包含 `split_latest_val_0_results.pkl`、`s_0_checkpoint.pt`、`splits_0.csv`、`summary_latest.csv`。

### 6.2 MCAT：BLOCKED，当前约束下不存在真实可执行命令

当前 MCAT 快照同时存在以下阻断：

1. `main.py` 使用未定义的 `args.inst_loss`；
2. `core_utils.py` 使用未定义的 `args.testing`；
3. `Generic_Split` 在所有 mode 下无条件读取 `fast_cluster_ids.pkl`；
4. `MCAT_Surv` WSI 输入固定 1024，无 `--path_input_dim`，与 UNI2-h 1536 直接冲突；
5. signature 路径期望 `dataset_csv_sig/`，仓库实际为 `datasets_csv_sig/`。

所以不能在“不修改 baselines/”的硬约束下给出声称可运行的 MCAT+UNI2-h 1536 一轮命令。修复上述 baseline 问题后，目标参数应至少包括 `--seed 123 --k 1 --k_start 0 --k_end 1 --max_epochs 1 --model_type mcat --mode coattn --fusion concat --apply_sig`，并新增真正传入模型的 `--path_input_dim 1536`；预期输出文件与第 3.5 节相同。此处没有执行真实训练，符合 `plan.md`。

## 7. 任务 B：`gdc_fetch_star_counts.py`

实现内容：

- 输入 labels 与癌种列表；查询条件固定为 `TCGA-<C>`、`Gene Expression Quantification`、`STAR - Counts`、`open`，并把 labels patient_id 作为 GDC filter。
- 只保留样本条码位置 14–15 为 `01` 且 `sample_type == Primary Tumor` 的文件。
- 一患者多文件规则写死为 `(sample_submitter_id, file_name, file_id)` 字典序最小。
- 输出列严格为 `patient_id,file_id,file_name,md5`；manifest 完整生成后，`--limit N` 只限制下载，不截断查询或 manifest。
- 按 `pagination.total` 翻页，拒绝 total 不一致、空页未收齐或数量溢出。
- 拒绝绝对路径、路径分隔符和同名目标碰撞，且在任何 `/data` 请求前完成检查。
- 已有最终文件 MD5 正确则跳过；错误则隔离为 `.corrupt*`。
- 支持 `.part` 续传；完整正确 `.part` 直接原子完成；206 严格核对 `Content-Range` 起点；服务端忽略 Range 返回 200 时从头覆盖；416 对 `.part` 复核，坏文件隔离后只从零重试一次；下载后 MD5 不符则隔离 `.part` 并失败。

BRCA 结果：labels 965、命中 963、缺失 2（`TCGA-AC-A5EI`、`TCGA-AR-A0U1`）。真实下载数量严格为 5，manifest 保持 963 条。

## 8. 验收标准逐条状态

| 验收项 | 状态 | 证据 |
|---|---|---|
| A0 七问 | PASS | 第 3 节逐条回答。 |
| A1 BLCA 产出 `splits_0.csv` | PASS | 原命令 exit 0；train/valid/test 缺失均为 0。 |
| A1 交集统计与缺失清单 | PASS | stdout 与 `scratch/splits_mcat_blca/missing_BLCA_*.csv`。 |
| A2 合成 `[1,50,1536]` 自检 | PASS（降级环境） | 默认 Python 缺依赖 exit 2；已有训练环境同一脚本 exit 0、SELFTEST PASS。 |
| A3 PORPOISE 完整 1-epoch 命令 | PASS（仅书写，未训练） | 第 6.1 节。 |
| A3 MCAT 完整 1-epoch 命令 | BLOCKED | 当前 baseline 固定 1024 及四项源码缺陷；禁止修改 baseline。 |
| B dry-run 不下载 | PASS | 原命令 exit 0，输出明确“未访问 data 下载端点”。 |
| B BRCA 前 5 文件下载及 MD5 | PASS | 原命令 exit 0，5/963；独立 MD5 重算五项均 True。 |
| GDC 实测下载不超过 5 | PASS | `tsv_files=5`、`part_files=0`，未执行其他真实 `/data` 下载。 |

## 9. `plan.md` 四条测试命令：真实原始输出

### 9.1 A1 BLCA split

命令：

```bash
python3 adapters/make_splits.py --lib MCAT --cancer BLCA --labels labels_424.csv --out scratch/splits_mcat_blca/
```

退出码：`0`

```text
库 CSV: /Users/wuhao/Desktop/TriModalSurv/baselines/MCAT/dataset_csv/tcga_blca_all_clean.csv.zip
BLCA train: 我们=136 | 库=373 | 交集=136 | 缺失=0 | 缺失清单=scratch/splits_mcat_blca/missing_BLCA_train.csv
BLCA valid: 我们=68 | 库=373 | 交集=68 | 缺失=0 | 缺失清单=scratch/splits_mcat_blca/missing_BLCA_valid.csv
BLCA test: 我们=138 | 库=373 | 交集=138 | 缺失=0 | 缺失清单=scratch/splits_mcat_blca/missing_BLCA_test.csv
已写入 splits: scratch/splits_mcat_blca/splits_0.csv
映射: train=train+valid，val=test（val 被 baseline 的逐 epoch 验证消费）
```

### 9.2 A2 默认 Python 自检

命令：

```bash
python3 adapters/uni2h_to_ptfiles.py --selftest
```

退出码：`2`

```text
错误: 此脚本需要现有环境中的 h5py 和 torch；请使用已配置的训练环境运行。
```

### 9.3 B dry-run

命令：

```bash
python3 adapters/gdc_fetch_star_counts.py --labels labels_424.csv --cancers BRCA --dry-run
```

退出码：`0`

```text
一病人多文件选择规则: (sample_submitter_id, file_name, file_id) 字典序最小
完整 manifest: /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/scratch/gdc_star_counts/manifest.csv (963 条)
BRCA: labels CSV 病人数=965, 命中数=963, 缺失数=2, 缺失清单=/Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/scratch/gdc_star_counts/missing_BRCA.csv
dry-run: 未访问 data 下载端点。
```

### 9.4 B 真实 5 文件下载

命令：

```bash
python3 adapters/gdc_fetch_star_counts.py --labels labels_424.csv --cancers BRCA --limit 5 --out scratch/gdc_test/
```

退出码：`0`

```text
一病人多文件选择规则: (sample_submitter_id, file_name, file_id) 字典序最小
完整 manifest: /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/scratch/gdc_test/manifest.csv (963 条)
BRCA: labels CSV 病人数=965, 命中数=963, 缺失数=2, 缺失清单=/Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/scratch/gdc_test/missing_BRCA.csv
下载数量: 5 / manifest 963
下载完成（MD5 正确）: 1be6a56c-a7b1-45e5-b96c-db20337073b8.rna_seq.augmented_star_gene_counts.tsv
下载完成（MD5 正确）: f2dda955-5a39-43c1-93a2-83953b2b91d1.rna_seq.augmented_star_gene_counts.tsv
下载完成（MD5 正确）: ae8996bd-b0b7-4f9b-91fa-606f95d49f8c.rna_seq.augmented_star_gene_counts.tsv
下载完成（MD5 正确）: 75d91076-9d8a-415e-9ee6-00b877e55874.rna_seq.augmented_star_gene_counts.tsv
下载完成（MD5 正确）: dc857517-6b3d-4008-85a4-a2b35efb1e7a.rna_seq.augmented_star_gene_counts.tsv
```

## 10. 补充验证：真实原始输出

### 10.1 已有训练环境的 A2 降级自检

命令：

```bash
/Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python adapters/uni2h_to_ptfiles.py --selftest
```

退出码：`0`

```text
SELFTEST PASS: [1, 50, 1536] -> FloatTensor [50, 1536]；临时成员已清理
```

### 10.2 任务 A 行为测试

命令：

```bash
PYTHONPYCACHEPREFIX="$PWD/scratch/final2_pycache_a" /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python scratch/task_a_behavior_test.py
```

退出码：`0`

```text
test_blca_maps_train_and_valid_to_train_and_writes_missing_lists (__main__.MakeSplitsBehavior) ... ok
test_duplicate_patient_within_split_is_rejected (__main__.MakeSplitsBehavior) ... ok
test_invalid_cancer_is_rejected (__main__.MakeSplitsBehavior) ... ok
test_lgg_uses_gbmlgg_archive_and_filters_lgg_labels (__main__.MakeSplitsBehavior) ... ok
test_patient_overlap_across_splits_is_rejected (__main__.MakeSplitsBehavior) ... ok
test_copy_failure_removes_temporary_member (__main__.Uni2HBehavior)
旧实现会在 copyfileobj 抛错时跳过 unlink；此测试应在旧代码下 RED。 ... ok
test_duplicate_slide_id_is_rejected_even_with_overwrite (__main__.Uni2HBehavior) ... ok
test_illegal_feature_dimensions_fail (__main__.Uni2HBehavior) ... ok
test_invalid_slide_name_leaves_no_pt_file (__main__.Uni2HBehavior) ... ok
test_tar_h5_is_float_tensor_and_temporary_extraction_is_cleaned (__main__.Uni2HBehavior) ... ok

----------------------------------------------------------------------
Ran 10 tests in 13.482s

OK
```

### 10.3 任务 B fake-server 行为测试

命令：

```bash
PYTHONPYCACHEPREFIX="$PWD/scratch/final_pycache_b" python3 scratch/task_b_behavior_test.py
```

退出码：`0`

```text
test_416_corrupt_part_is_quarantined_then_retried_from_zero_once (__main__.GdcFetchCliTests.test_416_corrupt_part_is_quarantined_then_retried_from_zero_once)
若 416 造成永久续传死锁或不隔离坏 part，此测试失败。 ... ok
test_bad_206_content_range_is_rejected_without_appending (__main__.GdcFetchCliTests.test_bad_206_content_range_is_rejected_without_appending)
若 206 起点未核验就追加，损坏 part 会被静默扩大，此测试失败。 ... ok
test_complete_correct_part_finalizes_without_data_request (__main__.GdcFetchCliTests.test_complete_correct_part_finalizes_without_data_request)
若完整正确的 .part 仍发 Range 或不原子完成，此测试失败。 ... ok
test_dry_run_paginates_and_emits_structured_gdc_filter_with_deterministic_manifest (__main__.GdcFetchCliTests.test_dry_run_paginates_and_emits_structured_gdc_filter_with_deterministic_manifest)
若分页、筛选树、01+Primary、白名单或稳定择一退化，此测试失败。 ... ok
test_limit_one_keeps_three_row_manifest_but_makes_exactly_one_data_request (__main__.GdcFetchCliTests.test_limit_one_keeps_three_row_manifest_but_makes_exactly_one_data_request)
若 limit 截断 manifest 或下载多于一个目标，此测试失败。 ... ok
test_md5_mismatch_quarantines_part_and_next_run_can_recover (__main__.GdcFetchCliTests.test_md5_mismatch_quarantines_part_and_next_run_can_recover)
若 MD5 失败保留同名 .part，下一次会错误续传而非完整重下。 ... ok
test_server_200_to_range_request_rewrites_part_from_zero (__main__.GdcFetchCliTests.test_server_200_to_range_request_rewrites_part_from_zero)
若服务端忽略 Range 仍追加，最终文件会把旧 part 和完整文件拼接。 ... ok
test_unsafe_filename_and_manifest_collision_fail_before_data_request (__main__.GdcFetchCliTests.test_unsafe_filename_and_manifest_collision_fail_before_data_request)
若路径穿越或不同 row 的同名目标未拒绝，文件可能被覆盖。 ... ok

----------------------------------------------------------------------
Ran 8 tests in 1.177s

OK
```

### 10.4 5 文件独立 MD5 重算

退出码：`0`

```text
manifest_rows=963
tsv_files=5
part_files=0
TCGA-3C-AALI | 1be6a56c-a7b1-45e5-b96c-db20337073b8.rna_seq.augmented_star_gene_counts.tsv | expected=7d19c73c6b27f520b337fe7489430584 | actual=7d19c73c6b27f520b337fe7489430584 | match=True
TCGA-3C-AALJ | f2dda955-5a39-43c1-93a2-83953b2b91d1.rna_seq.augmented_star_gene_counts.tsv | expected=62f442c0a47673a11906a33993fb57e3 | actual=62f442c0a47673a11906a33993fb57e3 | match=True
TCGA-3C-AALK | ae8996bd-b0b7-4f9b-91fa-606f95d49f8c.rna_seq.augmented_star_gene_counts.tsv | expected=c57324c953948d6cd5d9053052d3effa | actual=c57324c953948d6cd5d9053052d3effa | match=True
TCGA-4H-AAAK | 75d91076-9d8a-415e-9ee6-00b877e55874.rna_seq.augmented_star_gene_counts.tsv | expected=fe75dd0900e8da4580e13c57eda6b9a3 | actual=fe75dd0900e8da4580e13c57eda6b9a3 | match=True
TCGA-5L-AAT0 | dc857517-6b3d-4008-85a4-a2b35efb1e7a.rna_seq.augmented_star_gene_counts.tsv | expected=a05e5bb7a8d0e00e1ad35ed3adb5096f | actual=a05e5bb7a8d0e00e1ad35ed3adb5096f | match=True
INDEPENDENT_MD5_CHECK PASS
```

## 11. 遇到的问题与未尽事项

### 已处理问题

- GDC 初版续传对 416、错误 `Content-Range`、MD5 mismatch 的恢复不足；已用失败测试暴露并修复，8 项行为测试通过。
- 最终审查发现 A1 初版不拒绝重复 patient_id 或跨 split 重叠；当前 labels 无此问题，但脚本已补上强制拒绝，新增两项测试后任务 A 为 10/10 PASS。
- 初次语法检查曾在白名单外的 `adapters/__pycache__/` 写两个 `.pyc`；已精确删除并验证目录不存在，后续全部把缓存定向到 scratch。

### 未尽事项

1. **MCAT A3 仍为 BLOCKED**：需要修改 baseline parser、cluster 文件读取、signature 路径和 1536 输入层；本任务禁止修改 baseline，因此停止在证据化阻断。
2. PORPOISE 一轮训练按计划只写命令、不执行；当前本机已知训练环境还缺 `torchvision`，未安装依赖。
3. A2 只完成合成 h5 自检，未转换真实 TCGA-BLCA UNI2-h tar；本地任务未提供该归档路径。
4. B 只按验收真实下载 BRCA 前 5 个文件；LUAD/LGG/UCEC 未真实下载，避免越过下载上限。
5. GDC 响应侧当前信任服务端 filter，没有再次核对返回对象的 project/data_type；请求结构、workflow/access 与患者/样本条件已由本地测试及官方 dry-run 验证。该项为非阻塞防御性增强建议。
6. `gdc_fetch_star_counts.py` 是通用下载器，省略 `--limit` 会下载完整 manifest；本轮四条计划命令显式使用 `--limit 5`，实际产物严格为 5 个。后续人工实测仍应显式给出限额。

### Bug Post-Mortem

- **现象**: 运行 `python3 -m py_compile` 后，在白名单未授权的 `adapters/__pycache__/` 生成两个 `.pyc`。
- **根因**: 未给 `py_compile` 设置 `PYTHONPYCACHEPREFIX`，忽略了语法检查的写缓存副作用。
- **修复**: 精确删除本轮生成的两个 `.pyc` 并移除空目录；用 `test ! -e` 验证清理完成。
- **Prevention Rule**: 本任务所有 Python 语法、导入与测试命令必须把 `PYTHONPYCACHEPREFIX` 指向白名单内 scratch，或使用不会在源码旁写缓存的检查方式。
