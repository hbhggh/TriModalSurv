# 02. 方法与代码地图（`code/NPJ/` 快照；行号以快照为准）

目的：不读全部代码也能定位"声称的创新在代码里是否真的接上了"。

## 数据流

```
main_survival.py:631 main
  ├─ :642 get_dataset_tcga_sur(...)   # 只传 simulate_missing / modality_dropout / seed；训练期不按 manifest 遮挡
  │    └─ loc_utils_3yr/tcga_dataset.py:316 TCGASurDataset
  │         ├─ :411-416  pd.cut(bins=4) → survival_months_bin（pred_dim=4）
  │         ├─ :426-459  missing_grid 解析（评测期 manifest 格点）
  │         ├─ :471-483  modality_dropout（仅 train，按 (pid, modality) 确定性）
  │         ├─ :535      safe_modality_get：缺失 → 置零 + mask=0
  │         └─ :590-591  产出 {mm} 与 {mm}_valid（从不产出 {mm}_mask）
  ├─ :656 load_model → :198-213  只能构造 MainModalityMoE / NPJC
  │    ├─ model/fusion_model.py:962  MainModalityMoE（作者 gate 版）
  │    │    ├─ :973-979 m_projector = Linear→ReLU→Dropout（每模态 → 256d）
  │    │    ├─ :1011-1015 读 {mm}_mask 判缺失  ← 死代码（键不存在，条件恒假）
  │    │    ├─ :1017-1049 补偿器分支（M1b/M2 在此接入，读 {mm}_valid）
  │    │    ├─ :981 GatedFusion → :1055-1056 backbone 在长度 1 序列上运行（自注意力退化为恒等）
  │    │    └─ :995-997 per-cancer SurvivalHead
  │    └─ model/fusion_model.py:1078 NPJC（新骨架）
  │         ├─ :1088-1094 m_projector；:1095-1097 modality_embed
  │         ├─ :1119-1135 tokens/valids（img 恒 valid；text/rna 读 {mm}_valid）
  │         ├─ :1137-1168 补偿器（CAPRecall）替换缺失 token 并把 valids 置 1   ← 在 attention 之前
  │         ├─ :1170-1176 stack 3 token + modality_embed → TransformerEncoder(src_key_padding_mask=~valid)
  │         └─ :1177-1180 masked-mean → per-cancer SurvivalHead
  ├─ :671 NLLSurvLoss（loc_utils_3yr/loss_func.py:70 内含 sigmoid）
  ├─ :483-492 consistency loss（仅 training 且 λ≠0 且模型返回 3 元组）
  ├─ :707 Adam(weight_decay=1)   ← 作者硬编码
  └─ :759-761 按 valid c-index（A 口径）选最佳 ckpt → :768 prediction（A 口径写 csv）

scripts/eval_missing.py（冻结 ckpt 一次性多格点评测）
  ├─ :87 manifest_members → :345 configure_missing_grid_inplace → :387 iter_reused_grid_datasets
  ├─ :138 dual_risk_from_logits：A = raw logits cumprod；B = clamp(sigmoid) cumprod → :150 dual_cindex
  ├─ :192 compute_training_feature_means + :224 apply_m1_feature_means（--arm m1：均值盲补；_valid 保持 False）
  └─ :245 format_grid_result → JSON {cindex_A, cindex_B, n_test, n_masked_*, grid_sha}
```

## 创新插入点表

| 声称 | 代码位置 | 触发 flag | 用在哪些臂 |
|---|---|---|---|
| 拆 gate，token 进 attention | `model/fusion_model.py:1078-1180 NPJC` | `--network_type NPJC` | E0 / E0d / E1 |
| CAP-Recall 原型召回 | `model/compensator.py:34-172 CAPRecall`；插入 `fusion_model.py:1137-1168`（NPJC）与 `:1017-1049`（MainModalityMoE） | `--compensator capr` | E1（NPJC）、M2（gate 版） |
| MissingBank | `model/compensator.py:175-221` | `--compensator bank` | M1b（gate 版） |
| 一致性 loss | `compensator.py:18-32,223-226`；消费 `main_survival.py:483-492` | `--consistency_lambda 0.1`（需 `--modality_dropout>0` 才有 pair） | E1、M2 |
| modality dropout | `tcga_dataset.py:471-483,573-589` | `--modality_dropout 0.15` | E0d、E1、M1b、M2 |
| 评测期均值盲补 | `scripts/eval_missing.py:192,224` | `--arm m1` | M1（gate 版） |
| 原型更新只在训练 | `compensator.py:72-119`（`@torch.no_grad`，`bin_labels` 由 `main_survival.py:470-471` 注入） | — | E1、M2 |

## 发车器与门禁

- `scripts/train_launcher.py:56 ARM_PRESETS`：`e0` = NPJC + none；`e0d` = NPJC + none + `--modality_dropout 0.15`；`e1` = NPJC + capr + `--modality_dropout 0.15 --consistency_lambda 0.1`。`:383` 固定注入 `--lr 1e-4 --epochs 50 --batch_size 32`；`:601 _run_eval` 完成即评测。
- `scripts/launch_formal.sh` + `scripts/gpu_util_gate.py`：warmup 采样 GPU util 门禁；`config/gpu_train.yaml:19-20` `allow_low_gpu_util: true` + 原因（NPJ 计算图小，实测 util 11–15%，用户裁决豁免）。
- S5 三方训练脚本在 `collab/20260827-三方对比战役/s4/`（landau 路径），非 launcher。

## 配置生效/不生效（`model/config/surv_multimodal_mainmoe_uni2.yml`）

| 项 | 值 | 是否生效 |
|---|---|---|
| modality.img/text/rna dim | 1536 / 768 / 256 | 生效 |
| network_type | MainModalityMoE | **不生效**（CLI `--network_type` 决定） |
| network.hidden_size | 32 | **不生效**（`--hidden_size` 默认 256；launcher/eval 均 256） |
| network.dropout_rate | 0.2 | **不生效**（load_model 默认 0.1） |
| network.pred_dim | 4 | 生效 |
| network.n_token | 128 | 生效 |
| network.num_experts / topk | 1 / — | **不生效且未被引用**（MainModalityMoE、NPJC 都不用 experts；`SparseMoeBlock`/`MAGGate` 等仅被不可达的 MAGFusion/LiMoEFusion/CancerMoE 使用） |

## A/B 口径的代码位置

- 训练 loss：`loss_func.py:70` 对 logits 做 sigmoid（正确）。
- 训练/验证/测试 c-index 与 ckpt 选择：`main_survival.py:476,518-525,585-586` 用 raw logits cumprod（A 口径，作者原样）。
- 评测脚本：`eval_missing.py:138-150` 同时输出 A 与 B；离线对拍 `collab/20260826-NPJ三模态复现/dual_metric_eval.py`。
- 结论：**模型选择是 A 口径**；报告主口径 B 只是读数修正，不影响训练。

## 作者 gate 的缺失判据死代码（原文）

`model/fusion_model.py:1011-1015`
```python
mask_key = f"{mm}_mask"
if mask_key in all_modalities and all_modalities[mask_key].sum() == 0:
    input_data[mm] = None
else:
    input_data[mm] = self.m_projector[mm](x)
```
生存数据集只产出 `{modality}_valid`（`tcga_dataset.py:591`）；`{mm}_mask` 仅由分类数据集 `TCGADataset`（`:87,:91`）产出，`main_survival.py` 不引用。因此条件恒假，`GatedFusion` 的 mask 恒为全 1；缺失模态以全零特征过 projector 得到常量 bias token 照常参与加权。探针脚本 `collab/20260902-A测缺失补偿/scratch_gate_probe.py:51-52` 人工补键做过对比：修对 mask 后 gate 权重归零但 c-index 最大变化 0.0071。

## 基线（不在仓库内的部分）

- MCAT / PORPOISE 代码为 mahmoodlab 官方克隆（基点 `b9cca63` / `3390dc4`），我方改动 = `collab/20260827-三方对比战役/mcat_patch.diff`、`porpoise_patch.diff`（含 `--batched_collate` 与适配）。复现：`git clone https://github.com/mahmoodlab/MCAT && git -C MCAT checkout b9cca63 && git -C MCAT apply mcat_patch.diff`（PORPOISE 同理）。
- 冻结评测：`collab/20260827-三方对比战役/adapters/eval_frozen_test.py`（分箱只由 train∪valid 决定，`--assert-bins` 审计）。
- 特征转换：`adapters/uni2h_to_ptfiles.py`（WSI → UNI2-h 1536）、`adapters/bulkrnabert_infer.py`（RNA → 256 维自制嵌入）。

## landau 侧不可见资源

训练 ckpt（`out*/`）、特征目录（`data/tcga-dataset_uni2`、`data/text_embeddings_parsed`、`data/RNA_embedding_selfmade`）、`tmp_sur_cache/`、并行评测脚本（`eval_one.sh`、`gen_eval_tasks.sh`、`run_eval_parallel.sh`）、`launcher_logs/`（其中 e0d 的 50 个 log 已拉回 `results_npjc_e0d/`）。
