# HANDOFF.md — 三模态癌症生存预测：数据与复现管线（阶段 0 → 1 → 2）

> 交接对象：Claude Code（在 landau 服务器上通过 SSH 执行）。
> 本文件只覆盖"把数据和复现管线跑通"。**不做任何模型创新**（原型学习、门控改造、选择性补偿等一律不碰）。
> 文中标注"已核对"的事实来自对骨架仓库代码、论文原文和 Google Drive 目录的实际读取；标注"待验证"的项目需要在 landau 上确认。

---

## 1. 项目目标

- 骨架论文：Song et al., *A cancer-type-aware framework for robust multimodal survival prediction under missing modalities*, Briefings in Bioinformatics 2026, DOI 10.1093/bib/bbag124。
- 骨架代码：`https://github.com/zongzi13545329/NPJ`（分支 `main`）。
- 模态固定为三种：WSI（病理切片，锚模态，恒在）、RNA（可能缺失）、文本（病理报告，可能缺失）。任务固定为生存预测，指标 C-index。
- 本阶段目标（按顺序，不得跳步）：
  1. **阶段 0**：用作者公开的 BLCA 原特征复现骨架结果。
  2. **阶段 1**：只把 WSI 特征换成 UNI2-h（`feature_dim` 2048 → 1536），仍只做 BLCA。
  3. **阶段 2**：文本换 `Bio_ClinicalBERT`、RNA 换自跑的 `BulkRNABert`（本文件只预留说明，脚本等阶段 1 数字回来后再写）。
- 癌种范围：先 **BLCA**；后续最多扩展到 **4–5 个癌种**。**禁止**写 10 癌种循环。

## 2. 当前状态（交接时）

已核对的事实：

| 事项 | 结论 |
|---|---|
| 作者 Drive 公开的数据 | 只有 BLCA 的 WSI 特征（`tcga-dataset/BLCA.zip`）和 RNA 嵌入（`RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl`）；文本嵌入是一个"5 癌种约 2k 份报告"的 zip；另有两个标签/划分 CSV（4:2:4 和 7:1:2） |
| 标签 CSV | `TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv`：4,997 人、13 个癌种；列含 `patient_id, cancer_type, survival_months, censorship, split, text`（`text` 列是病理报告原文） |
| BLCA 人数 | train 136 / valid 68 / test 138，合计 **342** |
| 骨架 loader 期望的格式 | 见附录 A（已按代码逐行核对） |
| 数据缓存目录 | 硬编码为工作目录下的 `tmp/`，缓存文件名只含癌种/划分，**不含特征路径**（阶段切换必须清缓存，见 §8） |
| 结果目录 | `out/<seed>/…`，文件名里带 `cpt_name` 和各模态 `feature_dim`，不同阶段不会互相覆盖 |
| 混合精度 | `main_survival.py` 第 310 行 `Accelerator(mixed_precision='bf16')`；V100 无原生 bf16，可能报错（待验证，处理办法见 §10） |
| 论文 BLCA 参考值 | 4:2:4 划分下 0.612 ± 0.020（5 seeds）；脚本默认 `--hidden_size 256` 与论文写的 32 不一致，因此复现落在 0.59–0.63 即算通过 |
| WSI 转换脚本 | `convert_uni2h_to_npj.py` 已用合成 UNI2-h 格式数据测通（tar.gz 与目录两种输入），并用 loader 的原始读取路径回放得到 `[128, 1536]` token |

尚未在 landau 上执行任何步骤。

## 3. 环境信息

| 项目 | 值 |
|---|---|
| 服务器 | `landau`，通过 SSH 登录，无 GUI |
| 工作目录 | `WORKDIR=<待填写，例如 /home/<user>/work>/NPJ`（下文所有相对路径均相对于 `$WORKDIR`） |
| conda 环境名 | `tcga_env`（由仓库 `tcga.yaml` 定义，已核对） |
| GPU | 2 × Tesla V100-PCIE-32GB；本项目训练是单进程，单卡足够 |
| 磁盘 | > 1 TB |
| 长任务 | 一律放在 `tmux` 会话或 `nohup … > logs/xxx.log 2>&1 &` 中运行，日志写到 `$WORKDIR/logs/` |
| 需要用户本人完成的动作 | Hugging Face 登录（`huggingface-cli login`，粘贴 token）——执行者**不得**代为输入任何 token/密码；UNI2-h-features 是 gated 数据集，用户已获批访问 |

## 4. 不可违反的约束

1. 严格按阶段 0 → 1 → 2 的顺序推进；上一阶段验收未通过不得进入下一阶段。
2. 只做 BLCA；扩展癌种需用户明确指示，且上限 4–5 个。
3. RNA 编码器已定为 **BulkRNABert**，不得更换或"先用替代方案"。
4. 文本编码器为 **`emilyalsentzer/Bio_ClinicalBERT`**，输出 `[200, 768]`。
5. WSI 新特征为 **UNI2-h**，`feature_dim: 1536`。
6. 不修改模型结构、损失函数、训练超参（`lr/epochs/batch_size/seeds`）。允许修改的文件与范围仅限 §8 列出的内容。
7. 不删除、不覆盖作者原始特征目录；新特征放在并存目录 `data/tcga-dataset_uni2`。
8. 不在 `data/`、`out/`、`tmp/` 之外新建大文件；下载物统一放在 `$WORKDIR/downloads/`。
9. 任何数字（人数、维度、C-index）都以脚本实际打印为准，不得凭估计填写回报。

## 5. 阶段 0 执行清单：用作者原特征复现 BLCA

目标：一天内完成。

### 5.1 取代码、建环境

```bash
cd $WORKDIR/..
git clone https://github.com/zongzi13545329/NPJ.git
cd NPJ
mkdir -p logs downloads
conda env create -f tcga.yaml
conda activate tcga_env
pip install -e scattermoe/
pip install gdown h5py                      # gdown 用于命令行下载 Drive；h5py 阶段 1 需要
nvidia-smi                                  # 确认两张 V100 可见
```

### 5.2 下载作者公开数据（Drive 根目录 ID `1cPX564Bj2jNXfWKmqzVJse56UB3vyXZU`）

```bash
cd $WORKDIR
gdown --folder https://drive.google.com/drive/folders/1cPX564Bj2jNXfWKmqzVJse56UB3vyXZU -O downloads/drive_data
```

若整目录下载失败，逐文件下载（文件 ID 已核对）：

```bash
mkdir -p downloads/drive_data/{RNA_embedding,tcga-dataset,text_embeddings}
gdown 1xBXgAqCk-FDAvNjWxW5qiOpBPv29jTFI -O downloads/drive_data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv
gdown 1s5dqINpLakwVn8XZvWgpbikmu1DDsGGB -O downloads/drive_data/TCGA_9523sample_label_7-1-2_Censorship_HKUST.csv
gdown 1BzbCzWNx271HH1CvBz9P2Ib6UwGJovFR -O downloads/drive_data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl
gdown 1Ab7p0KuSbLznUmvATtdW2_RzR-lg_BRU -O downloads/drive_data/tcga-dataset/BLCA.zip
gdown 1llsQIjIAorBuYK7Pzbu2ilbwhzUMqFv6 -O downloads/drive_data/text_embeddings/TCGA_Reports_5types_2k_text_embeddings_pickle_files.zip
```

### 5.3 摆放数据（目标布局）

```
$WORKDIR/data/
├── TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv
├── TCGA_9523sample_label_7-1-2_Censorship_HKUST.csv
├── tcga-dataset/BLCA/TCGA-XX-XXXX*.pkl                  # 每张切片一个 pickle（DataFrame）
├── RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl
└── text_embeddings/<解压出的目录>/TCGA-XX-XXXX.pkl       # 每个病人一个 pickle
```

```bash
cd $WORKDIR
mkdir -p data/tcga-dataset data/RNA_embedding data/text_embeddings
cp downloads/drive_data/*.csv data/
cp downloads/drive_data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl data/RNA_embedding/
unzip -q downloads/drive_data/tcga-dataset/BLCA.zip -d data/tcga-dataset/
unzip -q downloads/drive_data/text_embeddings/TCGA_Reports_5types_2k_text_embeddings_pickle_files.zip -d data/text_embeddings/
```

zip 内部层级未核对（待验证）。解压后必须满足两条，否则手动挪目录：

```bash
ls data/tcga-dataset/BLCA | head            # 必须直接看到 TCGA-XX-XXXX*.pkl
find data/text_embeddings -name 'TCGA-*.pkl' | head -3   # 记下所在目录，填入 config 的 text.path
find data/text_embeddings -name 'TCGA-*.pkl' | wc -l     # 记录数量，写入回报
```

### 5.4 修改配置与脚本（具体改动见 §8）

- `model/config/surv_multimodal_mainmoe.yml`：text/rna 路径改回公开目录。
- `running_scripts/survival_prediction_mainmoe.sh`：`cancer_types="BLCA"`，`gpu_id=0`，`--cpt_name tcga_orig`。

### 5.5 冒烟测试（单 seed、1 epoch，先抓环境错误）

```bash
cd $WORKDIR && conda activate tcga_env
CUDA_VISIBLE_DEVICES=0 python main_survival.py \
  --model_config model/config/surv_multimodal_mainmoe.yml \
  --lr 1e-4 --epochs 1 --batch_size 32 --cpt_name smoke \
  --report_label_path data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv \
  --cancer_types BLCA --network_type MainModalityMoE --seed 123 \
  2>&1 | tee logs/stage0_smoke.log
```

冒烟通过的标志：loader 打印 BLCA 实例数、`Missing text embeddings` / `Missing RNA embeddings` 计数，训练跑完 1 epoch 且输出 c-index 不是 NaN。

### 5.6 正式 5 seeds

```bash
cd $WORKDIR && conda activate tcga_env
nohup bash running_scripts/survival_prediction_mainmoe.sh > logs/stage0_5seeds.log 2>&1 &
```

脚本会依次跑 seed 123/132/213/231/321，然后调用 `summary_results_3yr.py` 打印 `===== Aggregated Results =====`，其中带 `-mean` / `-std` 的 C-index 行就是回报值。

## 6. 阶段 1 执行清单：WSI 换成 UNI2-h（只做 BLCA）

### 6.1 下载 UNI2-h 的 BLCA 特征（用户已获批；登录由用户本人完成）

```bash
cd $WORKDIR
huggingface-cli login            # ← 用户本人执行，粘贴 token
huggingface-cli download MahmoodLab/UNI2-h-features TCGA/TCGA-BLCA.tar.gz \
  --repo-type dataset --local-dir downloads/UNI2-h_features
```

（新版 CLI 若提示 `huggingface-cli` 已弃用，改用 `hf download`，参数相同。）该 tar.gz 内是每张切片一个 `.h5`，`features` 形状 `[1, N_patch, 1536]`，`coords` 形状 `[1, N_patch, 2]`，256×256 patch、20×。

### 6.2 转换为骨架格式

把交接附带的 `convert_uni2h_to_npj.py` 放到 `$WORKDIR/scripts/`，然后：

```bash
cd $WORKDIR && conda activate tcga_env
mkdir -p scripts
python scripts/convert_uni2h_to_npj.py \
  --src    downloads/UNI2-h_features/TCGA/TCGA-BLCA.tar.gz \
  --cancer BLCA \
  --labels data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv \
  --out    data/tcga-dataset_uni2 \
  2>&1 | tee logs/stage1_convert_BLCA.log
```

脚本行为（已实现并测试）：切片名前 12 位映射 `patient_id`；只保留 CSV 中 BLCA 的病人；默认只留 `DX` 切片、丢弃样本类型 10–19（正常组织）；tar.gz 逐文件解压、用完即删；每张切片存为 `data/tcga-dataset_uni2/BLCA/<pid>.<slide_id>.pkl`（DataFrame，`.values` 为 `[N_patch, 1536]`）；同目录下生成 `_manifest_BLCA.csv` 与 `_missing_patients_BLCA.csv`；末尾打印"自检"块。

### 6.3 新建阶段 1 专用配置与脚本（不改阶段 0 文件）

```bash
cd $WORKDIR
cp model/config/surv_multimodal_mainmoe.yml model/config/surv_multimodal_mainmoe_uni2.yml
cp running_scripts/survival_prediction_mainmoe.sh running_scripts/survival_prediction_mainmoe_uni2.sh
```

- `surv_multimodal_mainmoe_uni2.yml`：`img.path: data/tcga-dataset_uni2`，`img.feature_dim: 1536`；text/rna 与阶段 0 相同。
- `survival_prediction_mainmoe_uni2.sh`：`--model_config model/config/surv_multimodal_mainmoe_uni2.yml`，`--cpt_name tcga_uni2`，其余与阶段 0 完全一致（同 5 个 seed、同超参）。

### 6.4 清理缓存后运行（必做）

```bash
cd $WORKDIR
mv tmp tmp_stage0_orig          # loader 缓存按癌种/划分命名、不含特征路径，不清会读到 2048 维旧缓存
nohup bash running_scripts/survival_prediction_mainmoe_uni2.sh > logs/stage1_5seeds.log 2>&1 &
```

## 7. 阶段 2 预留说明（本阶段不写代码，只登记任务）

等阶段 1 三个数字回报后再开写；届时脚本同样先用合成数据测通再交付。

**文本（替换作者的 768 维嵌入）**
- 模型：`emilyalsentzer/Bio_ClinicalBERT`（768 维）。
- 输入：CSV 的 `text` 列（病理报告原文，无空值）。
- 处理：逐 token 编码，只取前 200 个 token（与原实现一致；报告实际中位 453 词，截断是已知且暂不处理的问题），存为 `numpy.float32 [200, 768]`。
- 输出：`data/text_embeddings_clinbert/<pid>.pkl`；config `text.path` 指向该目录，`feature_dim: 768` 不变。
- 切换前删除 `tmp/text_BLCA_*.cache`。

**RNA（自跑 BulkRNABert，与原论文同源）**
- 数据：GDC 开放数据，按 `patient_id` 查询 `Gene Expression Quantification` / `STAR - Counts`，仅原发瘤样本（条码样本类型 `01`），一人多样本取其一（记录规则）。
- 预处理：官方仓库 `https://github.com/instadeepai/multiomics-open-research` 的 `scripts/preprocess_tcga_rna_seq.py`，按其 `data/bulkrnabert/common_gene_id.txt` 的基因顺序，使用 `tpm_unstranded` 列。
- 模型：Hugging Face **PyTorch** 版 `InstaDeepAI/BulkRNABert`，`AutoConfig/AutoTokenizer/AutoModel.from_pretrained(..., trust_remote_code=True)`，`config.embeddings_layers_to_save = (4,)` 取最后一层 token 嵌入（256 维）。不使用 JAX 版。
- 输出：`data/RNA_embedding_bulkrnabert/RNA_BLCA_embedding_token_lvl.pkl`，格式为 `{'identifier': [pid, …], 'embedding': [array(≥2048, 256), …]}`（loader 只取前 2048 个基因 token，建议直接存 `[:2048, :]`）。
- 切换前删除 `tmp/rna_BLCA_*.cache`。

## 8. 需要修改的文件和具体改什么

| 阶段 | 文件 | 位置 | 改动 |
|---|---|---|---|
| 0 | `model/config/surv_multimodal_mainmoe.yml` | `modality.text.path` | 由 `data/text_embeddings/TCGA_32types_text_embedding`（未公开）改为 §5.3 `find` 得到的实际目录 |
| 0 | 同上 | `modality.rna.path` | 由 `data/RNA_embedding/TCGA_32types_embeddings_2048`（未公开）改为 `data/RNA_embedding` |
| 0 | `running_scripts/survival_prediction_mainmoe.sh` | `cancer_types=` | 由 10 癌种拼接字符串改为 `"BLCA"` |
| 0 | 同上 | `gpu_id=` | `0`（训练为单进程，单卡即可；第二张卡留给并行任务） |
| 0 | 同上 | `args` 中 `--cpt_name` | `tcga` → `tcga_orig`（区分阶段） |
| 0（条件触发） | `main_survival.py` | 第 310 行 `Accelerator(mixed_precision='bf16')` | 仅当报 bf16/bfloat16 不支持错误时改为 `mixed_precision='no'`，并在回报中注明 |
| 1 | `model/config/surv_multimodal_mainmoe_uni2.yml`（新建） | `modality.img.path` / `feature_dim` | `data/tcga-dataset_uni2` / `1536` |
| 1 | `running_scripts/survival_prediction_mainmoe_uni2.sh`（新建） | `--model_config`、`--cpt_name` | 指向新 yml；`tcga_uni2` |
| 1 | `scripts/convert_uni2h_to_npj.py`（新增） | — | 交接附带，不改内容 |

阶段 0 改完后的 `surv_multimodal_mainmoe.yml` 应形如：

```yaml
modality:
  img:
    modality_name: img
    path: data/tcga-dataset
    feature_dim: 2048
  text:
    modality_name: text
    path: data/text_embeddings/<find 得到的目录>
    feature_dim: 768
  rna:
    modality_name: rna
    path: data/RNA_embedding
    feature_dim: 256
network_type: MainModalityMoE
task_type: surv
cancer_types: BLCA
img_select: all
network:
  hidden_size: 32
  dropout_rate: 0.2
  pred_dim: 4
  mlp_ratio: 2
  n_token: 128
  n_backbone: 1
  num_experts: 1
```

（`network` 块与仓库原样一致，不改；注意脚本实际使用的是命令行默认 `--hidden_size 256`，这是仓库自身的不一致，保持原样。）

## 9. 验收标准

**阶段 0**
- `ls data/tcga-dataset/BLCA | head` 直接列出 `TCGA-XX-XXXX*.pkl`。
- 冒烟测试 1 epoch 跑通，c-index 非 NaN。
- 5 seeds 全部有结果文件（`summary_results_3yr.py` 未打印 `Results file not found for seed`）。
- 汇总 C-index 均值落在 **0.59–0.63**。落在区间外不算失败，但必须原样回报，不得调参。

**阶段 1**
- 转换自检块：`有切片的病人数: 342 / 342`；`feature_dim: 1536`；按 split 覆盖 `train=136/136, valid=68/68, test=138/138`。
- 若 `skip:non_dx(...)` 数量很大，只记录，不改脚本规则。
- 缺失病人若 > 0，把 `_missing_patients_BLCA.csv` 内容附在回报里。
- `tmp/` 已重命名/清空后再训练；日志中 loader 打印的是 `data/tcga-dataset_uni2` 路径。
- 5 seeds 汇总 C-index 有值即可，无预设阈值（这是对照实验，高低都要报）。

**阶段 2**：待阶段 1 回报后另行给出。

## 10. 失败时怎么停、不要继续放大

遇到以下任一情况：**停止当前阶段，保存日志，写清现象与已尝试的动作，等待用户决定**。不要跨阶段、不要换方案、不要"顺手修模型"。

1. `conda env create` 或 `pip install -e scattermoe/` 失败两次以上。
2. 解压后找不到 §5.3 要求的布局，或 `TCGA-*.pkl` 数量与预期明显不符（BLCA 切片文件数远小于 342）。
3. 冒烟测试报错且不属于下面唯一允许的自修项：bf16 不支持 → 改 `mixed_precision='no'`（§8），只允许这一处修改。
4. loader 打印的 `Missing text embeddings` 或 `Missing RNA embeddings` 超过 BLCA 人数的 10%。
5. 任一 seed 的 c-index 为 NaN、< 0.52 或 > 0.75（后者提示泄漏或标签错位）。
6. 阶段 1 自检人数 ≠ 342，或 `feature_dim` ≠ 1536。
7. 磁盘剩余 < 100 GB，或下载连续失败。
8. 任何需要改动 §8 之外文件的情况。

禁止的"救火"动作：改 `lr/epochs/batch_size`、改 seeds、改 `hidden_size`、改 loss、改模型类、扩展癌种、删除作者原特征、把 RNA 换成非 BulkRNABert 方案。

## 11. Claude Code 第一批应该先做什么

按顺序，前三项可并行：

1. 填写 `$WORKDIR`，`git clone`，`mkdir -p logs downloads`，`nvidia-smi` 确认 GPU。
2. 请用户在 landau 上完成 `huggingface-cli login`，随后立刻在 tmux 中启动 §6.1 的 UNI2-h BLCA 下载（耗时最长，最先开始）。
3. 在另一 tmux 窗口执行 §5.1 建环境、§5.2 下载 Drive 数据。
4. §5.3 摆放数据并用两条 `ls/find` 命令核对布局，记录文本 pkl 数量。
5. §8 中阶段 0 的四处修改。
6. §5.5 冒烟测试；通过后 §5.6 启动 5 seeds。
7. 等 UNI2-h 下载完成后执行 §6.2 转换（CPU 任务，可与阶段 0 训练并行），保存自检块。
8. 阶段 0 汇总出来后，做 §6.3–6.4，启动阶段 1 的 5 seeds。
9. 按 §12 模板回报。

## 12. 需要回报给我的三样结果

按下面模板原样填写，数字直接从日志复制：

```
【阶段 0】作者原特征 BLCA，5 seeds
- 汇总行（复制 summary 的 -mean / -std 行）：
- 各 seed c-index：123=  132=  213=  231=  321=
- 是否修改过 mixed_precision：是/否
- 文本 pkl 数量 / Missing text / Missing RNA：

【阶段 1】UNI2-h 转换自检块（完整粘贴 logs/stage1_convert_BLCA.log 末尾"自检"到结尾）：

【阶段 1】UNI2-h BLCA，5 seeds
- 汇总行：
- 各 seed c-index：123=  132=  213=  231=  321=
- 是否已清理 tmp/：是/否
```

---

## 附录 A · 骨架仓库事实速查（已按代码核对）

- 入口：`main_survival.py`；数据集类在 `loc_utils_3yr/tcga_dataset.py`；模型在 `model/fusion_model.py`（`MainModalityMoE`）；损失 `loc_utils_3yr/loss_func.py`（离散时间 NLL，4 个时间 bin，由 `survival_months` 分箱得到）。
- 标签 CSV 列：`patient_id, cancer_type, split(train/valid/test), survival_months, censorship, text, …`。
- WSI 输入：`<img.path>/<CANCER>/` 下用 `glob(f"{pid}*.pkl")` 收集同一病人的所有切片；每个 pkl 是 DataFrame，`.values` → `[N_patch, feature_dim]`；`img_select: all` 时每张切片 K-means 到 `128 // 切片数` 个中心，模型内再对 token 取均值。
- 文本输入：`<text.path>/<pid>.pkl`，数组 `[L, 768]`，模型内 mean-pool；缺失时回退零张量 `(200, 768)` 并置 mask=0。
- RNA 输入：`<rna.path>/RNA_<CANCER>_embedding_token_lvl.pkl`，dict `{'identifier': [...], 'embedding': [...]}`，loader 取 `embedding[:2048, :]`；缺失回退 `(2048, 256)`。
- 缓存：`tmp/img_<CANCER>_<split>_all.cache`、`tmp/text_<CANCER>_<split>.cache`、`tmp/rna_<CANCER>_<split>.cache`（相对当前工作目录，硬编码）。
- 结果：`out/<seed>/<cpt_name>_img_<dim>text_<dim>rna_<dim>_MainModalityMoE_<cancer_types>_surv.*`；跨 seed 汇总 JSON 在 `out/` 根；测试集预测 CSV `out/test_pred_and_label_MainModalityMoE_<cancer>.csv`（每个 seed 会覆盖同名文件，以 summary 汇总为准）。
- `summary_results_3yr.py` 固定聚合 seeds `123 132 213 231 321`，并对 <0.5 的指标做 `1 - x` 翻转（仓库原有逻辑，保持原样，但回报时注明）。
- 训练脚本默认：`--lr 1e-4 --epochs 50 --batch_size 32 --n_image_tokens 128 --hidden_size 256`。

## 附录 B · 外部资源速查

| 资源 | 位置 |
|---|---|
| 作者数据 Drive 根目录 | `https://drive.google.com/drive/folders/1cPX564Bj2jNXfWKmqzVJse56UB3vyXZU` |
| UNI2-h 预提取特征（gated） | HF 数据集 `MahmoodLab/UNI2-h-features`，路径 `TCGA/TCGA-<PROJECT>.tar.gz` |
| UNI2-h 模型说明 | `https://huggingface.co/MahmoodLab/UNI2-h`（CC-BY-NC-ND 4.0，仅限非商业学术用途，不得再分发特征） |
| BulkRNABert（PyTorch） | `https://huggingface.co/InstaDeepAI/BulkRNABert` |
| BulkRNABert 预处理脚本与基因顺序 | `https://github.com/instadeepai/multiomics-open-research` |
| Bio_ClinicalBERT | `https://huggingface.co/emilyalsentzer/Bio_ClinicalBERT` |
| GDC API | `https://api.gdc.cancer.gov/` |
