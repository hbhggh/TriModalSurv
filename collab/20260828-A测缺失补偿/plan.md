> **[已废弃 2026-09-02]** 本目录为早期草案，被 `collab/20260902-A测缺失补偿/` 战役取代；其中口径表述（含 NPJ-A 锚定）以新战役与 `~/.claude/plans/prompt-m0-s5-majestic-nygaard.md` 的 B 主口径裁定为准。

# A 测派单契约：缺失 manifest + 评测入口（α 单）与 CAP-Recall 补偿器（β 单）

已获用户批准的执行方案（完整版见 ~/.claude/plans/commit-the-working-tree-concurrent-mango.md）。本文件是 Codex 派单的唯一契约。

## 全局背景（两单共用）

- 骨架：`NPJ/`（本地副本，与 landau 运行真源三关键文件 md5 一致）。三模态 img(1536)/text(768)/rna(256) 各经 `m_projector` 投影为 **256 维** token（`model/fusion_model.py:970-976`，yml 的 hidden_size:32 是死配置勿信），随后 GatedFusion 加权求和。
- **已知死代码（保持原样，禁止修复）**：模型读 `{mm}_mask`（fusion_model.py:1008）但 dataset 发 `{mm}_valid`（tcga_dataset.py:482），gate 掩码从未生效；缺失=零向量过投影出常量 token 照常融合。M0-real 臂就是这个 as-is 行为，**任何改动不得改变无补偿路径的现行为**（回归锚定：M0-real@0% 必须与 S5 NPJ-A 逐 seed 完全相等）。
- 实验臂：S5-Full（引用不跑）/ M0-real（S5 ckpt+测试遮挡）/ M1（S5 ckpt+测试期全局均值 token 盲补）/ M1b（可学习 bank，β 单）/ M2（CAP-Recall，β 单）。
- 口径：评测同时计算 A（raw logits 累积）与 B（sigmoid 后累积）两口径 c-index 存 JSON，主表用 A。参考实现 `NPJ/scripts/dual_metric_eval_s4.py`。
- S5 ckpt：landau `out/<seed>/tcga_uni2_img_1536text_768rna_256_MainModalityMoE_<CANCER>_surv.pth`（本地评测脚本按参数接收 ckpt 路径，不假设位置）。
- 禁止（两单通用）：git commit/push；ssh/scp；启动任何训练或 GPU 任务；实现 VAE/扩散/MoE 路由/对比学习；修改 `{mm}_mask` 死分支；改动 baselines/ 下任何文件；改 tmp_sur_cache。

## α 单：缺失 manifest + 评测入口

### 步骤与验收

1. **`NPJ/scripts/gen_missing_manifest.py`**
   - 输入：`--labels <labels_424_ex12.csv>`（列 patient_id,cancer_type,split,...）`--seed 20260828` `--out missing_manifest_v1.csv`
   - 对 5 癌（BLCA/BRCA/LUAD/LGG/UCEC）的 **test split** patient 生成 9 个布尔列：`{rna,text,both}_r{25,50,75}`；同一模式内名单**嵌套**（r25 ⊆ r50 ⊆ r75），三模式独立抽样；比例按癌种内 test 人数向下取整。
   - 末行打印 manifest 的 SHA256 与逐癌逐列计数表。
   - 验收：固定 seed 重跑两次输出逐字节一致；嵌套断言（脚本内 assert）；BLCA test=138 时 r25=34/r50=69/r75=103。
2. **`NPJ/loc_utils_3yr/tcga_dataset.py` manifest 通道**（最小侵入）
   - `TCGASurDataset.__init__` 新增可选参数 `missing_manifest: dict | None`（{pid: set(modalities_to_drop)}），仅当提供时在 `safe_modality_get`（:452 附近）对命中的 (pid, mm) 走与 simulate 相同的零填充+mask=0 路径；`get_dataset_tcga_sur`（:492-498）新增透传参数把 manifest 传给 **test**（train/val 不传）。
   - 默认 None 时行为与现状逐字节一致（这是硬验收：不带参数构建 dataset，抽 3 个样本张量与改动前 md5 相同）。
3. **`NPJ/scripts/eval_missing.py`**（独立脚本，不改 main_survival.py 训练路径）
   - 参数：`--arm {M0real,M1,M2} --cancer --seed --ckpt <path> --label-csv <path> --manifest <csv> --modes rna,text,both --rates 0,25,50,75,100 --out <dir>`
   - 每个 (mode, rate) 格点：构建 test dataset（manifest 遮挡 + rate=100 时该模式全体、rate=0 无遮挡）→ 前向收集 logits → 计算 A/B 双口径 c-index（sksurv，参照 dual_metric_eval_s4.py:62-64）→ 汇总写 `<out>/<arm>_<cancer>_s<seed>.json`（13 格点 × {cindex_A, cindex_B, n_test, n_masked_rna, n_masked_text}）。
   - **M1 实现**：forward hook 在 `m_projector[mm]` 输出处，把缺失样本（per-sample，依据本格点遮挡名单∨天然 `_valid=0`）的 token 替换为该模态**训练集完整样本投影 token 均值**（脚本内用同 ckpt 对 train split 前向一次现算并缓存 npz）；M0real 不挂 hook。M2 的加载逻辑留接口（`--arm M2` 时报 NotImplementedError，β 单接线）。
   - 验收（CPU 或无 GPU 环境用合成小数据）：①合成 dataset 单测——3 患者×3 模态假特征，遮挡后对应 `_valid` 翻 0、张量为零；②M0real 与 M1 在 rate=0 且无天然缺失的合成样本上输出完全一致（hook 无触发）；③13 格点 JSON 键完整性 assert。
4. 过程留痕 `collab/20260828-A测缺失补偿/notes.md`，完成写 `result.md`（改动清单/验收输出原文/未尽事项）。

### 文件白名单（α）
- 新建：`NPJ/scripts/gen_missing_manifest.py`、`NPJ/scripts/eval_missing.py`
- 修改：`NPJ/loc_utils_3yr/tcga_dataset.py`（仅上述通道）
- 追加：`collab/20260828-A测缺失补偿/{notes.md,result.md}`
- 此外一律不许碰。

### 测试命令（α，Codex 须实跑并贴输出）
```
python NPJ/scripts/gen_missing_manifest.py --labels "collab/20260827-三方对比战役/labels_424_ex12.csv" --seed 20260828 --out /tmp/mmv1_a.csv
python NPJ/scripts/gen_missing_manifest.py --labels "collab/20260827-三方对比战役/labels_424_ex12.csv" --seed 20260828 --out /tmp/mmv1_b.csv && cmp /tmp/mmv1_a.csv /tmp/mmv1_b.csv && echo DETERMINISTIC_OK
python -m pytest 或等价单测脚本（合成数据三项验收）
```

## β 单：CAP-Recall 补偿器 + M1b bank（α 验收后才发）

要点预告（发单时另附细化）：插入点 `model/fusion_model.py:1013`（256 维 token 后、gate 前）唯一一处；CAP-Recall = 癌种特异 [4 风险 bin × 256] 原型表（训练期完整样本 EMA）+ WSI 锚 cross-attn 召回 + λ=0.1 余弦一致性 loss（仅对训练期 dropout 样本）；训练协议 text/rna 各 p=0.15 独立 per-sample dropout；M1b = 每模态 1 个可学习 256 维向量 + MSP 式正交正则；新实验身份后缀区分（不覆盖 S5 结果）；仍禁训练启动——接线完成即停，冒烟由指挥官在 landau 跑。
