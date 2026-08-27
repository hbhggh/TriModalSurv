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

## 12. 任务 C：MCAT 最小可运行补丁（2026-08-27 增补）

本节覆盖第 11 节中“MCAT A3 仍为 BLOCKED”的旧状态：任务 C 已修复该节列出的 5 个源码缺口。它不追溯改写 A/B 的历史记录。

### 12.1 持久改动文件清单

1. baselines/MCAT/main.py
2. baselines/MCAT/datasets/dataset_survival.py
3. baselines/MCAT/utils/core_utils.py
4. baselines/MCAT/models/model_coattn.py
5. collab/20260827-三方对比战役/mcat_patch.diff
6. collab/20260827-三方对比战役/scratch/task_c_mcat_patch_test.py
7. collab/20260827-三方对比战役/notes.md（仅追加）
8. collab/20260827-三方对比战役/result.md（本增补节）

未修改 plan.md；根仓库开始时已有的 plan.md 修改属于既有工作区状态。未执行 git commit、git push、ssh 或依赖安装。

### 12.2 五点验收逐条状态

| 任务 C 验收项 | 状态 | 实现与证据 |
|---|---|---|
| 1. parser 补 --inst_loss | PASS | main.py 新增字符串参数，choices 为 svm/ce/None，默认 Python 值为 None；help 与默认值探针 exit 0。 |
| 2. parser 补 --testing | PASS | main.py 新增 store_true，默认 False；help 与默认值探针 exit 0。 |
| 3. cluster pickle 条件化 | PASS | Generic_Split 仅在 mode == cluster 时读取；coattn 无 pickle 构建通过，cluster 正向读取守卫也通过。 |
| 4. signature 目录修正 | PASS | 引用改为实际存在的 datasets_csv_sig/signatures.csv；官方 BLCA CSV 在 apply_sig=True 下构建通过。 |
| 5. MCAT WSI 输入维参数化 | PASS | --path_input_dim 默认 1024；core 传给 MCAT_Surv；small/big size_dict 均使用该输入维。默认 1024 与显式 1536 的真实 forward 均通过。 |

### 12.3 默认兼容与范围核对

- 空参数运行时值：inst_loss=None、testing=False、path_input_dim=1024。
- MCAT_Surv 不传新参数时首层输入仍为 1024，默认模型 forward 通过。
- 未改变实验命名、settings 字段、optimizer、loss、loader、训练 epoch、其他模型或其他维度。
- baselines/MCAT 最终只有 4 个必要文件被修改；diff 为 11 insertions、6 deletions。
- git diff --check exit 0。
- mcat_patch.diff 与实时 git diff 经 cmp 字节级一致：86 行、5383 bytes。

### 12.4 自测环境限制

指定解释器为 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python，Torch 2.5.1，CPU，CUDA 不可用。该环境缺少 torchvision、torch_geometric、sksurv、tensorboardX，且官方 MCAT vendored attention 仍导入 Torch 2.5 已删除的私有 _LinearWithBias。遵守禁止安装依赖、禁止超出 5 点改动：

- help 和模块导入只在 scratch 测试进程为未执行边界提供最小测试桩；
- _LinearWithBias 只在测试进程映射为现有 nn.Linear；
- dataset、scaler、pt 加载、MCAT 网络和两次 forward 均执行真实仓库代码；
- 未声称当前环境可脱离测试桩完成正式训练。

依赖预检命令：

~~~bash
/Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
mods=['torchvision','torch_geometric','lifelines','sksurv','tensorboardX','h5py','pandas','sklearn','scipy']
for name in mods:
    try:
        mod=__import__(name)
        print(name, 'OK', getattr(mod, '__version__', ''))
    except Exception as exc:
        print(name, 'MISSING_OR_BROKEN', type(exc).__name__, str(exc))
PY
~~~

退出码：0

~~~text
torchvision MISSING_OR_BROKEN ModuleNotFoundError No module named 'torchvision'
torch_geometric MISSING_OR_BROKEN ModuleNotFoundError No module named 'torch_geometric'
lifelines OK 0.30.0
sksurv MISSING_OR_BROKEN ModuleNotFoundError No module named 'sksurv'
tensorboardX MISSING_OR_BROKEN ModuleNotFoundError No module named 'tensorboardX'
h5py OK 3.16.0
pandas OK 2.1.4
sklearn OK 1.3.2
scipy OK 1.15.2
~~~

### 12.5 自测命令与真实原始输出

#### 12.5.1 main.py --help

实际执行先导入 scratch/task_c_mcat_patch_test.py 提供的测试进程兼容桩，再以 sys.argv = ['main.py', '--help'] 执行 main.py；未触发 dataset 或训练。

退出码：0

~~~text
usage: main.py [-h] [--data_root_dir DATA_ROOT_DIR] [--seed SEED] [--k K]
               [--k_start K_START] [--k_end K_END] [--results_dir RESULTS_DIR]
               [--which_splits WHICH_SPLITS] [--split_dir SPLIT_DIR]
               [--log_data] [--overwrite]
               [--model_type {snn,deepset,amil,mi_fcn,mcat}]
               [--mode {omic,path,pathomic,cluster,coattn}]
               [--fusion {None,concat,bilinear}] [--apply_sig]
               [--apply_sigfeats] [--drop_out]
               [--model_size_wsi MODEL_SIZE_WSI]
               [--model_size_omic MODEL_SIZE_OMIC]
               [--path_input_dim PATH_INPUT_DIM] [--opt {adam,sgd}]
               [--batch_size BATCH_SIZE] [--gc GC] [--max_epochs MAX_EPOCHS]
               [--lr LR] [--inst_loss {svm,ce,None}]
               [--bag_loss {svm,ce,ce_surv,nll_surv,cox_surv}]
               [--label_frac LABEL_FRAC] [--bag_weight BAG_WEIGHT] [--reg REG]
               [--alpha_surv ALPHA_SURV] [--reg_type {None,omic,pathomic}]
               [--lambda_reg LAMBDA_REG] [--weighted_sample]
               [--early_stopping] [--testing]

Configurations for Survival Analysis on TCGA Data.

options:
  -h, --help            show this help message and exit
  --data_root_dir DATA_ROOT_DIR
                        Data directory to WSI features (extracted via CLAM
  --seed SEED           Random seed for reproducible experiment (default: 1)
  --k K                 Number of folds (default: 5)
  --k_start K_START     Start fold (Default: -1, last fold)
  --k_end K_END         End fold (Default: -1, first fold)
  --results_dir RESULTS_DIR
                        Results directory (Default: ./results)
  --which_splits WHICH_SPLITS
                        Which splits folder to use in ./splits/ (Default:
                        ./splits/5foldcv
  --split_dir SPLIT_DIR
                        Which cancer type within ./splits/<which_splits> to
                        use for training. Used synonymously for "task"
                        (Default: tcga_blca_100)
  --log_data            Log data using tensorboard
  --overwrite           Whether or not to overwrite experiments (if already
                        ran)
  --model_type {snn,deepset,amil,mi_fcn,mcat}
                        Type of model (Default: mcat)
  --mode {omic,path,pathomic,cluster,coattn}
                        Specifies which modalities to use / collate function
                        in dataloader.
  --fusion {None,concat,bilinear}
                        Type of fusion. (Default: concat).
  --apply_sig           Use genomic features as signature embeddings.
  --apply_sigfeats      Use genomic features as tabular features.
  --drop_out            Enable dropout (p=0.25)
  --model_size_wsi MODEL_SIZE_WSI
                        Network size of AMIL model
  --model_size_omic MODEL_SIZE_OMIC
                        Network size of SNN model
  --path_input_dim PATH_INPUT_DIM
                        Dimension of WSI features (Default: 1024)
  --opt {adam,sgd}
  --batch_size BATCH_SIZE
                        Batch Size (Default: 1, due to varying bag sizes)
  --gc GC               Gradient Accumulation Step.
  --max_epochs MAX_EPOCHS
                        Maximum number of epochs to train (default: 20)
  --lr LR               Learning rate (default: 0.0001)
  --inst_loss {svm,ce,None}
                        instance-level clustering loss function (default:
                        None)
  --bag_loss {svm,ce,ce_surv,nll_surv,cox_surv}
                        slide-level classification loss function (default: ce)
  --label_frac LABEL_FRAC
                        fraction of training labels (default: 1.0)
  --bag_weight BAG_WEIGHT
                        clam: weight coefficient for bag-level loss (default:
                        0.7)
  --reg REG             L2-regularization weight decay (default: 1e-5)
  --alpha_surv ALPHA_SURV
                        How much to weigh uncensored patients
  --reg_type {None,omic,pathomic}
                        Which network submodules to apply L1-Regularization
                        (default: None)
  --lambda_reg LAMBDA_REG
                        L1-Regularization Strength (Default 1e-4)
  --weighted_sample     Enable weighted sampling
  --early_stopping      Enable early stopping
  --testing             Debugging tool
~~~

#### 12.5.2 不传新参数的运行时默认值

命令使用 runpy 执行 main.py，并在原始 ArgumentParser.parse_args([]) 返回后立即停止，未进入 dataset 或训练。

退出码：0

~~~text
inst_loss=None
testing=False
path_input_dim=1024
DEFAULTS PASS
~~~

#### 12.5.3 四个改动文件语法检查

命令：

~~~bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
from pathlib import Path
paths = [
    Path('baselines/MCAT/main.py'),
    Path('baselines/MCAT/datasets/dataset_survival.py'),
    Path('baselines/MCAT/utils/core_utils.py'),
    Path('baselines/MCAT/models/model_coattn.py'),
]
for path in paths:
    compile(path.read_bytes(), str(path), 'exec')
    print(f'SYNTAX PASS: {path}')
PY
~~~

退出码：0

~~~text
SYNTAX PASS: baselines/MCAT/main.py
SYNTAX PASS: baselines/MCAT/datasets/dataset_survival.py
SYNTAX PASS: baselines/MCAT/utils/core_utils.py
SYNTAX PASS: baselines/MCAT/models/model_coattn.py
~~~

#### 12.5.4 任务 C 行为测试与 CPU mini forward

命令：

~~~bash
cd /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=ignore /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python scratch/task_c_mcat_patch_test.py
~~~

退出码：0

~~~text
test_train_passes_path_input_dim_to_mcat_constructor (__main__.CorePropagationBehaviorTests) ... ok
test_cluster_split_still_loads_cluster_pickle (__main__.GenericSplitBehaviorTests) ... ok
test_coattn_split_does_not_require_cluster_pickle (__main__.GenericSplitBehaviorTests) ... ok
test_default_model_keeps_1024_input_and_forwards (__main__.ModelDimensionBehaviorTests) ... ok
test_explicit_1536_model_input_forwards (__main__.ModelDimensionBehaviorTests) ... ok
test_official_blca_dataset_and_model_forward_for_both_dimensions (__main__.OfficialBlcaMiniSmokeTests) ... ok
test_help_exposes_inst_loss (__main__.ParserBehaviorTests) ... ok
test_help_exposes_path_input_dim (__main__.ParserBehaviorTests) ... ok
test_help_exposes_testing (__main__.ParserBehaviorTests) ... ok
test_apply_sig_reads_repository_signature_directory (__main__.SignaturePathBehaviorTests) ... ok

----------------------------------------------------------------------
Ran 10 tests in 7.756s

OK

Training Fold 0!

Init train/val/test splits... 
Done!
Training on 1 samples
Validating on 1 samples

Init loss function... Done!

Init Model... Shape (1, 1)
Shape (1, 1)
(0, 0) : 0
(0, 1) : 1
(1, 0) : 2
(1, 1) : 3
(2, 0) : 4
(2, 1) : 5
(3, 0) : 6
(3, 1) : 7
Shape (204, 20394)
Shape (138, 20394)
****** Normalizing Data ******
MCAT MINI FORWARD PASS: path_dim=1024, bag=(50, 1024), hazards=(1, 4)
MCAT MINI FORWARD PASS: path_dim=1536, bag=(50, 1536), hazards=(1, 4)
(0, 0) : 0
(0, 1) : 1
(1, 0) : 2
(1, 1) : 3
(2, 0) : 4
(2, 1) : 5
(3, 0) : 6
(3, 1) : 7
~~~

#### 12.5.5 diff 范围与留档一致性

命令：

~~~bash
git -C baselines/MCAT diff --check
~~~

退出码：0；原始 stdout 为空。

命令：

~~~bash
git -C baselines/MCAT diff --stat
~~~

退出码：0

~~~text
 datasets/dataset_survival.py | 7 ++++---
 main.py                      | 3 +++
 models/model_coattn.py       | 5 +++--
 utils/core_utils.py          | 2 +-
 4 files changed, 11 insertions(+), 6 deletions(-)
~~~

命令：

~~~bash
git -C baselines/MCAT diff | cmp - collab/20260827-三方对比战役/mcat_patch.diff
~~~

退出码：0；原始 stdout 为空。

### 12.6 遇到的问题

1. 指定环境缺少四项训练依赖；按禁止安装依赖约束，使用 scratch 测试桩隔离未执行的 import，未改 baseline。
2. Torch 2.5.1 不再暴露 _LinearWithBias；仅在测试进程做别名兼容，未混入 5 点生产 diff。
3. 初次 GREEN 显示官方旧代码的 torch.load、Pandas positional Series 与 Transformer warning；均未影响断言，且不在 5 点范围内，所以不修。
4. apply_patch 自动补了三个官方文件的 EOF newline；已机械去除，最终 diff 无噪声。
5. rm -rf 清理 scratch pycache 被安全策略拒绝且未执行；改用精确 find 删除，约 97 MB 临时缓存已清理。

### 12.7 未尽事项

- 任务 C 的 5 点源码修复与计划指定 mini 冒烟均已完成，没有任务内未尽项。
- 未执行完整训练，符合 plan.md 明确的“不做完整训练”。
- 当前 protomasksurv-exp1 环境若要脱离测试桩运行官方 main.py，仍需由后续独立任务处理缺失依赖及旧 Torch 私有 API 兼容；本轮禁止安装依赖且禁止超出 5 点修改，故没有扩展。

### Bug Post-Mortem

- **现象**: 首次测试在导入 model_coattn.py 时因 _LinearWithBias 缺失而停止，未到达目标 RED。
- **根因**: 官方 MCAT vendored attention 依赖旧 PyTorch 私有 API，而指定环境为 Torch 2.5.1。
- **修复**: 只在 scratch 测试进程建立 _LinearWithBias → nn.Linear 的兼容别名，随后得到准确 RED 并完成 GREEN。
- **Prevention Rule**: 旧科研仓库的计划外环境兼容问题先在测试夹具隔离，未经白名单授权不得混入生产补丁。

### Bug Post-Mortem（缓存清理）

- **现象**: rm -rf 清理命令被安全策略拒绝；没有文件被该命令删除。
- **根因**: 选择了策略禁止的删除形式，且没有复用本任务历史中已验证的 find 清理方式。
- **修复**: 精确解析三个目标、核对大小和 symlink 后，用 find 删除普通文件与空目录。
- **Prevention Rule**: scratch 临时树固定采用 realpath 核对、symlink 检查、find -type f -delete、find -depth -type d -empty -delete。

## 13. 修复轮 Round 2 路 C：PORPOISE 全 collator 修复 + UNI2 事务化（2026-08-27 增补）

结论：路 C finding 4 + 5 的指定代码、扩展 `--selftest`、PORPOISE 双 mode 首批取数和 diff 留档均已完成，最终验收命令全部 exit 0。没有启动训练、下载、SSH、commit 或 push；首批冒烟通过后已停止。

### 13.1 改了哪些文件（必填项 1）

本路实际写入仅限以下白名单文件：

1. `baselines/PORPOISE/utils/utils.py`
   - 统一修复 `collate_MIL_survival`、`collate_MIL_survival_sig`、`collate_MIL_survival_cluster`。
   - tensor 列表先 `torch.cat`，再显式转成 `torch.float32` / `torch.long`；cluster/sig 的 `event_time` 不再返回 NumPy array。
2. `adapters/uni2h_to_ptfiles.py`
   - 新增 staging 转换、成员 manifest、SHA-256/shape/dtype 全量复核、原子发布、overwrite 整套替换与失败清理。
   - 扩展 `--selftest`，覆盖正常发布、中途失败、`written == 0`、整套 overwrite。
3. `porpoise_patch.diff`
   - 按既有口径更新为 PORPOISE 子仓库当前完整 diff；与 `git diff` 逐字一致。
4. `scratch/task_c_round2_porpoise_collator_test.py`
   - 官方 BLCA CSV + A1 split + 合成 1536 维 pt 的 pathomic/coattn DataLoader 首批行为测试；另含 cluster 最小合成首批。
5. `notes.md`、`result.md`
   - 仅追加本路过程、问题、验证和结果。

说明：`porpoise_patch.diff` 中的 `models/model_coattn.py`、`utils/cluster_train_utils.py`、`utils/coattn_train_utils.py`、`utils/core_utils.py` 四段补丁在本路启动前已经存在；本路没有修改这四个生产文件，只把同一留档中的 `utils/utils.py` 段更新到当前状态。

### 13.2 对应哪条 finding（必填项 2）

| Finding | 修复与证据 | 状态 |
|---|---|---|
| finding 4：PORPOISE 三个 collator 对 tensor 列表的构造不兼容 Torch 2.x | 三个 collator 全部改为 `torch.cat(...).to(dtype=...)`；官方 BLCA 的 pathomic/coattn 首批与 cluster 合成首批均验证 label/event/c shape `(1,)`、dtype `int64/float32/float32` | PASS |
| finding 5：UNI2 转换直接写最终目录、失败留半成品、`written==0` 成功、overwrite 逐文件混写 | 新数据只写唯一 staging；manifest 记录 `source_member/slide_id/patient_id/output_file/shape/dtype/sha256`；发布前逐 `.pt` 重新加载并校验 checksum/shape/dtype/成员集合；全通过后 `os.replace`；overwrite 先把旧正式集合移到唯一 backup，发布失败恢复，成功后删除旧集合 | PASS |

### 13.3 `plan.md` 路 C 验收标准逐条状态

1. `collate_MIL_survival / _sig / _cluster` 三个统一修：PASS。
2. 官方 BLCA CSV + 合成 pt + A1 split，DataLoader 首批真实取数覆盖 pathomic 与 coattn：PASS。
3. cluster 无现成数据时构造最小合成首批：PASS。
4. staging → 全成员校验 + manifest → 原子 rename 发布：PASS。
5. 半途失败不留最终目录：PASS；第二个成员为 `[1,3,1024]`，断言明确命中该非法维度。
6. `written == 0` 非零退出：PASS；子进程 exit 2。
7. `--overwrite` 整套替换、最终不混入旧成员：PASS。
8. `porpoise_patch.diff` 更新且与当前 PORPOISE diff 一致：PASS。

### 13.4 怎么验证（必填项 3）：命令与真实原始输出

#### 13.4.1 UNI2 扩展 `--selftest`

命令：

~~~bash
cd /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=ignore /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python adapters/uni2h_to_ptfiles.py --selftest
~~~

退出码：0

真实原始 stdout：

~~~text
SELFTEST PASS: normal publish + manifest [1,50,1536] -> FloatTensor [50,1536]；临时成员已清理
SELFTEST PASS: mid-conversion failure leaves no final pt_files
SELFTEST PASS: written==0 exits 2; 错误: 输入中未找到任何 .h5 成员；written == 0，拒绝发布
SELFTEST PASS: --overwrite replaces the whole pt_files set atomically
~~~

#### 13.4.2 PORPOISE 双 mode 首批 + cluster 合成首批

命令：

~~~bash
cd /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=ignore /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python scratch/task_c_round2_porpoise_collator_test.py
~~~

退出码：0

真实原始 stdout：

~~~text
test_coattn_official_blca_first_batch (__main__.OfficialBlcaFirstBatchTests) ... ok
test_pathomic_official_blca_first_batch (__main__.OfficialBlcaFirstBatchTests) ... ok
test_cluster_first_batch (__main__.SyntheticClusterFirstBatchTests) ... ok

----------------------------------------------------------------------
Ran 3 tests in 23.519s

OK
(0, 0) : 0
(0, 1) : 1
(1, 0) : 2
(1, 1) : 3
(2, 0) : 4
(2, 1) : 5
(3, 0) : 6
(3, 1) : 7
Shape (204, 20395)
Shape (138, 20395)
****** Normalizing Data ******
PORPOISE FIRST BATCH PASS: mode=coattn case=TCGA-2F-A9KO path=(4, 1536) omics=[(94,), (334,), (521,), (468,), (1496,), (479,)] label=(1,)/torch.int64 event_time=(1,)/torch.float32 censorship=(1,)/torch.float32
(0, 0) : 0
(0, 1) : 1
(1, 0) : 2
(1, 1) : 3
(2, 0) : 4
(2, 1) : 5
(3, 0) : 6
(3, 1) : 7
Shape (204, 20395)
Shape (138, 20395)
****** Normalizing Data ******
PORPOISE FIRST BATCH PASS: mode=pathomic case=TCGA-2F-A9KO path=(4, 1536) omic=(1, 20395) label=(1,)/torch.int64 event_time=(1,)/torch.float32 censorship=(1,)/torch.float32
PORPOISE CLUSTER SYNTH FIRST BATCH PASS: path=(4, 1536) cluster_ids=(4,)/torch.int64 omic=(8,)/torch.float32 label=(1,)/torch.int64 event_time=(1,)/torch.float32 censorship=(1,)/torch.float32
~~~

#### 13.4.3 语法、whitespace 与 diff 留档一致性

语法检查命令：

~~~bash
cd /Users/wuhao/Desktop/TriModalSurv
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
from pathlib import Path
for path in [
    Path('baselines/PORPOISE/utils/utils.py'),
    Path('collab/20260827-三方对比战役/adapters/uni2h_to_ptfiles.py'),
    Path('collab/20260827-三方对比战役/scratch/task_c_round2_porpoise_collator_test.py'),
]:
    compile(path.read_bytes(), str(path), 'exec')
    print(f'SYNTAX PASS: {path}')
PY
~~~

退出码：0；真实原始 stdout：

~~~text
SYNTAX PASS: baselines/PORPOISE/utils/utils.py
SYNTAX PASS: collab/20260827-三方对比战役/adapters/uni2h_to_ptfiles.py
SYNTAX PASS: collab/20260827-三方对比战役/scratch/task_c_round2_porpoise_collator_test.py
~~~

命令：

~~~bash
git -C /Users/wuhao/Desktop/TriModalSurv/baselines/PORPOISE diff --check
~~~

退出码：0；真实原始 stdout 为空。

命令：

~~~bash
cd /Users/wuhao/Desktop/TriModalSurv/baselines/PORPOISE
git diff | cmp - /Users/wuhao/Desktop/TriModalSurv/collab/20260827-三方对比战役/porpoise_patch.diff
~~~

退出码：0；真实原始 stdout 为空。

当前完整 PORPOISE diff stat（含本路开始前已有四文件补丁）：

~~~text
 models/model_coattn.py       |  2 +-
 utils/cluster_train_utils.py |  6 +++---
 utils/coattn_train_utils.py  |  6 +++---
 utils/core_utils.py          |  6 +++---
 utils/utils.py               | 39 ++++++++++++++++++++-------------------
 5 files changed, 30 insertions(+), 29 deletions(-)
~~~

### 13.5 有没有动到白名单外目录（必填项 4）

- 本路没有写入路 C 白名单之外的文件；没有修改 `adapters/make_splits.py`、`baselines/MCAT/` 或 `NPJ/`。
- `adapters/make_splits.py` 的最终 mtime 为 `2026-08-27 01:45:42 JST`，早于本路 `11:59:09 JST` 启动；NPJ 在该时点后无新文件。
- 审计发现三路并行期间，其他执行方新增/修改了 `scratch/round2_route_a_contract_test.py`、`mcat_patch.diff`、`baselines/MCAT/main.py`。这些不是本路命令或 patch 产生；本路没有覆盖、回退或纳入本路交付断言。
- PORPOISE 子仓库其余四个 modified 文件在本路启动时已经存在，最终仍保持 modified；本路仅写 `utils/utils.py`。
- 未执行 `git commit`、`git push`、SSH、下载或任何训练。

### 13.6 遇到的问题

1. 当前官方 PORPOISE BLCA ZIP 缺旧 loader 固定断言要求的 `Unnamed: 0`，元数据顺序也不同。测试只在临时 `scratch/` 副本插入行号列并恢复旧 loader 期望顺序，病例、切片、结局和全部基因组值不变；没有修改官方 ZIP 或 dataset 源码。
2. coattn loader 硬编码读取不存在的 `datasets_csv_sig/signatures.csv`，实际文件在 `datasets_csv/signatures.csv`。该路径修复不在路 C 白名单；测试仅把现有官方 signatures 复制到临时 scratch 夹具的预期相对路径，以验证真实 dataset/DataLoader/collator 路径。
3. 初版半途失败自测接受任意 `ValueError`，adversarial review 后收紧为必须命中第二个 1024 维非法成员，排除假阳性。
4. `apply_patch` 给原本无 EOF newline 的 `utils.py` 补了换行；已机械恢复，最终 diff 不含该噪声。

### 13.7 未尽事项与边界

- 路 C 指定 finding 4 + 5 没有未完成项。
- 未执行完整训练或模型 forward，符合公共停机门；本轮只验证 DataLoader 首批和转换事务。
- PORPOISE 当前官方 CSV schema 与签名相对路径的生产级适配仍是白名单外既有问题；本路首批测试使用了明确记录的 scratch 兼容夹具，不能把它表述为这两个生产问题已经修复。
- cluster collator 已通过最小 DataLoader 首批；当前 `cluster_train_utils.py` 的训练循环还存在既有的 tuple 解包契约差异，本轮禁止训练且 finding 4 只授权 collator 文件，因此未扩展修复或宣称 cluster 训练可运行。

### Bug Post-Mortem（PORPOISE 首批夹具）

- **现象**: 初版双 mode 测试先被官方 CSV metadata 断言和缺失 signatures 相对目录阻断，未到达 coattn collator。
- **根因**: 测试假设仓库磁盘工件仍满足旧 PORPOISE loader 的固定 schema/路径，但当前 ZIP 和目录布局已漂移。
- **修复**: 只在白名单 scratch 临时副本恢复 loader 预期列顺序和 signatures 相对路径；随后准确得到 `_sig` / `_cluster` RED，完成生产补丁后同一测试 GREEN。
- **Prevention Rule**: 旧科研仓库的集成测试先核对“工件 schema + 硬编码相对路径”；任何测试兼容层必须临时、显式并写入结果，禁止把夹具适配冒充生产修复。

## 修复轮 Round 2 — 路 B：MCAT 实验身份隔离

### 1. 改了哪些文件

1. `baselines/MCAT/main.py`
   - 向 `param_code` 和 `exp_code` 同时追加 `_pid{path_input_dim}`。
   - 向 experiment settings 写入 `path_input_dim` 与 `data_root_dir`。
   - 在已有结果目录上，先用 `ast.literal_eval` 解析对应 `experiment_<exp_code>.txt`，再严格比对两个身份键。缺文件、解析失败、非 dict、缺键、类型不同或值不同均抛出 `RuntimeError`。检查位于 `summary_latest.csv` 早退之前，`--overwrite` 不能绕过。
2. `collab/20260827-三方对比战役/mcat_patch.diff`
   - 按计划指定命令更新为 MCAT 子仓库当前全量 diff，包含必须保留的 Round 1/其他协作者既有 hunks 与本轮 `main.py` 增量。
3. `collab/20260827-三方对比战役/notes.md`
   - append-only 追加路 B 边界、RED/GREEN、取舍、验证与 Bug Post-Mortem。
4. `collab/20260827-三方对比战役/result.md`
   - append-only 追加本节。

路 B 的生产代码增量只涉及 `baselines/MCAT/main.py`。

### 2. 对应哪条 finding

对应 adversarial review **finding 3：MCAT 实验身份未隔离**。

- 修复前：1024 与 1536 共用同一无 `_pid` 目录，1536 请求可因 1024 的 `summary_latest.csv` 存在而 exit 0。
- 修复后：1024 和 1536 的 `param_code`/`exp_code` 均分离；相同 pid 目录的 `data_root_dir` 或 experiment 记录中 `path_input_dim` 不一致时 exit 1。
- 默认 `path_input_dim=1024` 的计算语义不变；目录命名相对官方行为的唯一有意差异是追加 `_pid1024`。
- `data_root_dir` 按 CLI 传入的原始字符串精确比较；同一物理目录若改用相对/绝对路径字符串，也会按“元数据不完全匹配”硬失败。

### 3. 怎么验证的

#### 3.1 RED：修复前身份碰撞

命令在 `/private/tmp` 临时目录中，用内存 import stubs 运行两次 `main.py`；两次都指定 `--k_start 0 --k_end 0`，参数只在 `--path_input_dim 1024/1536` 之间变化。退出码：0。

真实原始输出（验收摘取命令的 stdout）：

~~~text
RED RUN path_input_dim=1024 exit=0
RED RUN path_input_dim=1536 exit=0
RED experiment_file_count=1
RED leaf_dirs=['5foldcv/MCAT_nll_surv_a0.0_5foldcv_gc32_concat/tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_s1']
RED checkpoint_count=0
RED CONFIRMED: 1024 与 1536 复用同一无 pid 实验目录
~~~

#### 3.2 GREEN：1024/1536 隔离、元数据硬门与零训练证据

命令：

~~~bash
cd /Users/wuhao/Desktop/TriModalSurv
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=ignore \
  /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 内联 harness 用 subprocess 以实际退出码运行 main.py；
# 四组 main.py 参数均包含：
# --results_dir <private-tmp>/results --which_splits 5foldcv
# --split_dir tcga_blca --model_type mcat --mode coattn
# --k_start 0 --k_end 0
# 顺序验证：
# 1) path_input_dim=1024,data_root_dir=./features_A
# 2) path_input_dim=1536,data_root_dir=./features_A
# 3) 复用 1024 与 features_A
# 4) 复用 1024，features_B，带 --overwrite
# 然后篡改临时 1024 experiment 记录的 path_input_dim=1536 并重跑。
# harness 对目录名、settings、退出码、错误文本和训练产物计数均有 assert。
PY
~~~

外层验收命令退出码：0。真实原始 stdout：

~~~text
=== CREATE 1024: exit=0 ===
Experiment Name: tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024
data_root_dir:  ./features_A
path_input_dim:  1024
=== CREATE 1536: exit=0 ===
Experiment Name: tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1536
data_root_dir:  ./features_A
path_input_dim:  1536
experiment_file_count=2
experiment_dirs=['5foldcv/MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024/tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024_s1', '5foldcv/MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1536/tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1536_s1']
settings[1024]: path_input_dim=1024, data_root_dir='./features_A'
settings[1536]: path_input_dim=1536, data_root_dir='./features_A'
=== REUSE MATCHING 1024: exit=0 ===
Experiment Name: tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024
Exp Code <tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024> already exists! Exiting script.
=== REJECT data_root_dir MISMATCH WITH --overwrite: exit=1 ===
RuntimeError: Experiment identity mismatch for existing results directory </private/tmp/mcat_round2_green_cjr_6g5l/results/5foldcv/MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024/tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024_s1>: data_root_dir: existing='./features_A', requested='./features_B'
Experiment Name: tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024
=== REJECT path_input_dim MISMATCH: exit=1 ===
RuntimeError: Experiment identity mismatch for existing results directory </private/tmp/mcat_round2_green_cjr_6g5l/results/5foldcv/MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024/tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024_s1>: path_input_dim: existing=1536, requested=1024
Experiment Name: tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat_pid1024
checkpoint_count=0
fold_result_count=0
IDENTITY DRY-RUN PASS
~~~

`checkpoint_count=0` 且 `fold_result_count=0`；源码控制流中 `folds=np.arange(0,0)`，未调用 `train()`。本轮没有使用会进入训练的 `--testing`。

#### 3.3 help、语法与 diff 留档

命令：用内存 import stubs 运行 `main.py --help`，检查三个 Round 1 参数；用 `compile()` 检查 `main.py`；然后执行 `git diff --check`。退出码：0。

真实原始 stdout：

~~~text
HELP PASS: exit=0
required_flags=--path_input_dim,--testing,--inst_loss
SYNTAX PASS: /Users/wuhao/Desktop/TriModalSurv/baselines/MCAT/main.py
~~~

`git -C baselines/MCAT diff --check` 退出码 0，原始 stdout 为空。

留档与一致性命令：

~~~bash
git -C baselines/MCAT diff > collab/20260827-三方对比战役/mcat_patch.diff
git -C baselines/MCAT diff | cmp - collab/20260827-三方对比战役/mcat_patch.diff
wc -l -c collab/20260827-三方对比战役/mcat_patch.diff
shasum -a 256 collab/20260827-三方对比战役/mcat_patch.diff
git -C baselines/MCAT diff --stat
~~~

退出码：0。`cmp` 原始 stdout 为空。其余真实原始 stdout：

~~~text
     227   11864 collab/20260827-三方对比战役/mcat_patch.diff
4999105a1d75d3ac70ae21268e8ae57d9e419f109dff77c9e484bb692f6bf6fc  collab/20260827-三方对比战役/mcat_patch.diff
 datasets/dataset_survival.py |  7 ++++---
 main.py                      | 42 ++++++++++++++++++++++++++++++++++++++++--
 models/model_coattn.py       |  7 ++++---
 utils/cluster_train_utils.py |  6 +++---
 utils/coattn_train_utils.py  |  6 +++---
 utils/core_utils.py          | 14 +++++++++-----
 6 files changed, 63 insertions(+), 19 deletions(-)
~~~

说明：上述 stat 是子仓库当前必须留档的全量 diff，不等于路 B 改了 6 个生产文件。路 B 生产增量仅为 `main.py`；其余 5 个已改文件的实施前/后 SHA256 一致：

~~~text
9f9938b944708909246aa093eee0b9ef673ca3917cee84944c3bd2e5f551a261  baselines/MCAT/datasets/dataset_survival.py
bdf294a4b7b6c9e714ef8d8c85cc43715a64c759996dd8d46c4ee1de4ccfb181  baselines/MCAT/models/model_coattn.py
f0119549dab43c86e1723f6834900b693187a7062b1b756503a01cd7be3257ea  baselines/MCAT/utils/cluster_train_utils.py
14069bc393fd0a6f55166759f455ae0255b4e13cbbcf8779ea0d11ee678ad06d  baselines/MCAT/utils/coattn_train_utils.py
7bc8b98999cfcde10e5b51b477522756d0144a3fe5dd89a9c10d1815ab93e259  baselines/MCAT/utils/core_utils.py
~~~

### 4. 有没有动到白名单外目录

**没有。**

- 路 B 没有修改 `adapters/`、`baselines/PORPOISE/`、`NPJ/`。
- 执行期间根工作树可观察到路 A、路 C 和监视器的既有/并发改动；路 B 只读观察且未覆盖、回退或改写。
- 干跑的可变产物全部位于 `/private/tmp` 的自动清理目录；没有在 MCAT 或本任务目录新建测试脚本、结果目录或 pycache。
- 未执行 SSH/scp，未访问 landau，未下载，未执行 `git commit`、`git push` 或等效操作。

### 验收标准逐条状态

1. `param_code/exp_code` 追加 `_pid{path_input_dim}`：**PASS**。
2. settings 记录 `path_input_dim` 与 `data_root_dir`：**PASS**。
3. 已有结果目录元数据不完全匹配时硬失败：**PASS**；`data_root_dir` + `--overwrite` 和篡改 `path_input_dim` 均 exit 1。
4. 默认 1024 的行为差异仅限目录身份追加 `_pid1024`：**PASS**。
5. 1024 与 1536 落入不同目录：**PASS**。
6. CPU 干跑未训练：**PASS**；checkpoint=0，fold result=0。
7. `mcat_patch.diff` 更新并与当前 MCAT diff 一致：**PASS**。

### 独立交叉审核

写本节前，独立只读 reviewer 对 correctness、scope、compatibility、test sufficiency 的代码判定均为 PASS，未发现正常 CLI 下的身份校验绕过；当时总门控为 `CONCERNS 90/100`，唯一阻塞项就是本 `result.md` 增补节尚未写。本节写完后再做最终范围复审；仍需 Claude 按项目互审纪律验收，Codex 不自行宣布进入下一 Gate。

### 遇到的问题

1. 指定 Python 环境缺少 `torchvision`、`torch_geometric`、`sksurv`、`tensorboardX`。遵守“禁止安装依赖”，只对空 folds 不会调用的 import 边界使用进程内 stub；dataset 构建和 `main.py` 身份逻辑均运行真实代码。
2. `--testing` 仍会进入 epoch/反传，不符合“禁止训练”；改用 `--k_start 0 --k_end 0` 空 folds。
3. 首次组合验证命令混用 cwd 与根目录相对路径，且未设 `set -e`，导致前两项失败被末尾 help 的 exit 0 掩盖。发现后立即用正确路径和 `set -e` 重跑，语法与 diff 检查均 exit 0。

### 未尽事项

- 路 B 的源码、干跑、留档与文档义务已完成，无任务内未尽项。
- 未执行任何完整训练、正式实验或 GPU 任务；冒烟通过后已停止。
- 依项目公共约束，必须交回 Claude 做另一方 review；本结果不授权开始 BLCA / BRCA / LUAD / LGG / UCEC 正式实验或 5-seed 全量。

### Bug Post-Mortem（组合验证命令路径）

- **现象**: 验证命令已在 `baselines/MCAT` cwd 中，但前两项仍重复使用 `baselines/MCAT/...`；它们报路径不存在，末尾 help 却成功，整体 shell 误报 exit 0。
- **根因**: 混用两套相对路径语义，且未对组合验证设置 fail-fast。
- **修复**: 在正确 cwd 下用 `git diff --check` 和 `Path('main.py')` 重跑，两项均 exit 0；最终命令使用绝对路径且设 `set -e`。
- **Prevention Rule**: 多项验证固定一套 cwd/路径语义并强制 fail-fast；绝不以整段命令最后一项的退出码代替逐项验证。
