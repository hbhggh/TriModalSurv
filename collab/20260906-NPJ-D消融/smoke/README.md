# 冒烟留档（步骤 4，2026-09-07 08:42:28 JST）

只判通/不崩（V21），数字仅列出不评。

- 部署：landau `/home/wuhao/NPJ/` 覆盖 4 文件（覆盖前远端 md5 = 本地 `code/NPJ/` 派单前快照；旧版备份 `backup_20260906_npjd/`），新增 `tests/test_mean_fusion.py`、`launch_d0.sh`、`eval_dm_one.sh`、`scripts_tmp/{parity_d.py,count_natural_missing.py}`；部署后 11 文件 md5 与本地逐一相等。
- 远端单测：tcga_env（py3.12.9 / torch 2.5.0）`pytest tests/test_mean_fusion.py` 5 passed（9.33 s）。
- 对拍①（gate 路径，不传 `--fusion_type`，S5 ckpt，卡 1）：BLCA s123 与 LGG s123 四格点 cindex_A/B、n_test、grid_sha 与 `results_gate/m0real/` 留档逐位一致 → `parity/*.out` 两个 PARITY_PASS（本地复核同）。
- 冒烟发车：`jobrun.sh npjd_smoke_d0 1 … -- bash launch_d0.sh --cancers BLCA --seeds 123 --gpus 1 --per_gpu 1`（pid 2676323，08:38:28 起）→ launch_formal 门禁（`allow_low_gpu_util` 豁免，`FORMAL_GATE_EARLY_COMPLETE`）→ 训练 50 epoch（tqdm bar 起始计数 train 51 = 50+test 1 / valid 50，与参照 e1_LUAD_s123.log 同构）→ ckpt `out_d0/123/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth`（5.80 MB）→ 自动评测 4 格点 → `npjd_eval_d0/d0_BLCA_s123.json`（arm=d0）→ runs_state d0_BLCA_s123 status=done/eval_status=done → done.flag 08:39:49（全程 81 s）。
- 训练参数（log Namespace）：epochs=50 batch_size=32 lr=0.0001 network_type=MainModalityMoE compensator=none fusion_type=mean modality_dropout=0.0（consistency_lambda=0.1 无消费点）。
- Dm：`eval_dm_one.sh BLCA 123 1` → `npjd_eval_dm/dm_BLCA_s123.json`（m1 均值来自 train 天然非缺失样本 rna 134 / text 136）。自检：BLCA test 无自然缺失 ⇒ Dm none 与 D none 逐位相等 = True；rna_100/text_100/both_100 三格点均不同（V31 两侧覆盖）。

| 格点 | D A | D B | Dm A | Dm B | n_masked rna/text |
|---|---|---|---|---|---|
| none | 0.6263 | 0.6270 | 0.6263 | 0.6270 | 0/0 |
| rna_100 | 0.6319 | 0.6213 | 0.6209 | 0.6213 | 138/0 |
| text_100 | 0.5999 | 0.5980 | 0.5984 | 0.5975 | 0/138 |
| both_100 | 0.5892 | 0.5878 | 0.5940 | 0.5925 | 138/138 |

自然缺失计数见 `natural_missing_counts.txt`（BLCA 0/0 锚点成立）。
