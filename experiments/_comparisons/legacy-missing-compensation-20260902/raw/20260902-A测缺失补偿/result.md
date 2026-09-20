# 任务 α 交付结果

完成时间：2026-09-02 09:04:20 JST  
执行边界：仅完成 `plan.md` 的“单 α”；未训练、未 SSH/scp、未下载、未提交或推送。

## 1. 改动文件清单

### 源码

- 新建 `NPJ/scripts/gen_missing_manifest.py`
- 新建 `NPJ/scripts/eval_missing.py`
- 修改 `NPJ/loc_utils_3yr/tcga_dataset.py`：仅新增 α2 的 `missing_manifest/missing_grid` 参数、人工遮挡判断及 train/valid/test 透传

### 过程、交付与计划要求的测试产物

- 新建 `collab/20260902-A测缺失补偿/notes.md`
- 新建 `collab/20260902-A测缺失补偿/result.md`
- 生成 `collab/20260902-A测缺失补偿/missing_manifest_v1.csv`
- 生成 `collab/20260902-A测缺失补偿/missing_manifest_v1.csv.stats.json`

未修改 `NPJ/model/fusion_model.py`、`NPJ/main_survival.py`、MCAT、PORPOISE、`tmp_sur_cache/`、`plan.md` 或 `s5_full_reference.csv`。Git 只读审计中，禁止路径 diff exit 均为 0。`NPJ/loc_utils_3yr/__pycache__/tcga_dataset.cpython-310.pyc` 在本任务开始前已是未跟踪文件，本任务未触碰。

## 2. `plan.md` 验收标准逐条结果

### α1 `gen_missing_manifest.py`

| 验收项 | 状态 | 证据 |
|---|---|---|
| 从实际 `cancer_type` 读取五癌 test 患者 | PASS | BLCA=138、BRCA=383、LGG=166、LUAD=172、UCEC=198，总计 1057 |
| 输出契约列 `patient_id,cancer` 加 9 个布尔格点 | PASS | 独立 CSV 审计通过；布尔值写为 0/1 |
| 每模式 25% ⊆ 50% ⊆ 75% | PASS | 同一癌种/模式使用同一乱序前缀；`--verify` 重读断言通过 |
| `both` 独立抽样 | PASS | 每个 `seed/cancer/mode` 使用独立 SHA256 派生随机流 |
| 每癌每列人数误差 ≤1 | PASS | 人数使用 `n*rate//100`，实际误差严格小于 1；`--verify` 通过 |
| 仅含五癌 test 患者 | PASS | manifest 患者集合与标签真源五癌 test 集合严格相等 |
| SHA256 与 stats JSON | PASS | SHA256=`c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156`；统计 JSON 与 CSV SHA 一致 |
| 固定 seed 可复现 | PASS | 第二次输出与交付 CSV 经 `cmp` 逐字节一致 |

### α2 dataset 遮挡通道

| 验收项 | 状态 | 证据 |
|---|---|---|
| `TCGASurDataset.__init__` 新增两个默认 None 参数 | PASS | 签名断言通过 |
| manifest 命中时走零特征 + `valid=0` | PASS（合成） | 真实 `TCGASurDataset` 合成 BLCA：`rna_50` 命中样本 RNA 全零且 invalid |
| `both` 同时遮 RNA/Text，img 永不遮 | PASS（合成） | `both_75` 两模态均全零/invalid；img 保持非零/valid |
| `*_100` 不查 manifest、遮当前 split 全体 | PASS（合成） | `get_dataset_tcga_sur(..., missing_grid='rna_100')` 对 train/valid/test 共 6 样本全部遮 RNA |
| 两参数透传 train/valid/test | PASS（合成） | 三 split 实际长度 `[2,1,3]`，逐样本断言通过 |
| 不改 `simulate_missing_modality` 既有语义 | PASS（代码边界） | 原解析和采样块未改；仅在 `safe_modality_get` 与 manifest 条件并列 |
| 默认 None 行为完全一致 | PASS（合成逐样本） | 改前/改后 SHA256 均为 `5e28d5af5e65464b63ad1f793910b94e49084ac31f30367ff6093a09d250ce71`，N=3 |

说明：本机没有真实 NPJ 特征目录，故这里的 BLCA 是真实 dataset 类配合合成特征，不是 landau 真实 BLCA 队列性能评测。

### α3 `eval_missing.py`

| 验收项 | 状态 | 证据 |
|---|---|---|
| CLI 参数与 `m0real/m1` 两臂 | PASS | 默认 Python 下 `--help` exit 0，参数名称与契约一致 |
| 13 格点 | PASS（函数级） | `all` 严格解析为 13 个唯一格点；非法/重复格点被拒绝 |
| DataParallel `module.` 前缀 | PASS（合成 checkpoint） | `torch.save` 的 `state_dict` 前缀 checkpoint strict 加载到裸 `nn.Linear`，参数 allclose |
| A raw cumprod | PASS（函数级） | 固定 logits 得到 `[-2.25,-3.1424,3000996.0]` |
| B sigmoid+clamp cumprod | PASS（函数级） | 固定及 ±1000 极值 logits 与参考常数对拍通过 |
| `sksurv concordance_index_censored` 接线 | 代码完成，landau 待实跑 | 真实运行时直接 import 官方函数；本机无 `sksurv`，未伪造实现 |
| M1 train-only 原始特征逐元素均值 | PASS（函数级） | RNA/Text 非缺失样本数均为 2，固定均值张量对拍通过 |
| M1 仅替换 invalid 特征且 valid 保持 False | PASS（函数级） | batch 行级替换与 valid 不变断言通过 |
| 真实标签缺 `label` 的兼容 | PASS（函数级） | 仅在系统临时目录补 `label=0`，输入 CSV 不改 |
| 不触碰仓库 `tmp_sur_cache` | PASS（代码审计） | 真实评测切换到系统临时目录后构建 dataset，退出时清理 |
| 每格 JSON 六字段 | PASS（函数级/伪运行时） | `cindex_A,cindex_B,n_test,n_masked_rna,n_masked_text,grid_sha` 齐全；相对路径端到端 JSON 通过 |
| 复用 `main_survival.load_model`、hidden=256 | PASS（代码审计） | 延迟 import 原函数；未复制模型类；hidden 固定 256 |

### 总体结论

- α1：本地真实标签 manifest 生成与验证通过。
- α2：真实 dataset 类的合成行为、三 split 透传和默认回归通过。
- α3：函数级、合成 checkpoint 与伪运行时 JSON 通道通过。
- landau 真实 checkpoint、真实特征、`sksurv` c-index、M0-real@0% 锚定：**未执行，按计划归指挥官**。

## 3. 测试命令与真实原始输出

### 3.1 计划指定 manifest 命令

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python NPJ/scripts/gen_missing_manifest.py --labels "collab/20260827-三方对比战役/labels_424_ex12.csv" --seed 20260902 --out "collab/20260902-A测缺失补偿/missing_manifest_v1.csv" --verify
```

原始输出（exit 0）：

```text
VERIFY_OK
{"BLCA": {"both_25": 34, "both_50": 69, "both_75": 103, "rna_25": 34, "rna_50": 69, "rna_75": 103, "text_25": 34, "text_50": 69, "text_75": 103}, "BRCA": {"both_25": 95, "both_50": 191, "both_75": 287, "rna_25": 95, "rna_50": 191, "rna_75": 287, "text_25": 95, "text_50": 191, "text_75": 287}, "LGG": {"both_25": 41, "both_50": 83, "both_75": 124, "rna_25": 41, "rna_50": 83, "rna_75": 124, "text_25": 41, "text_50": 83, "text_75": 124}, "LUAD": {"both_25": 43, "both_50": 86, "both_75": 129, "rna_25": 43, "rna_50": 86, "rna_75": 129, "text_25": 43, "text_50": 86, "text_75": 129}, "UCEC": {"both_25": 49, "both_50": 99, "both_75": 148, "rna_25": 49, "rna_50": 99, "rna_75": 148, "text_25": 49, "text_50": 99, "text_75": 148}}
STATS_JSON=collab/20260902-A测缺失补偿/missing_manifest_v1.csv.stats.json
SHA256=c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156
```

### 3.2 固定 seed 逐字节复现

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python NPJ/scripts/gen_missing_manifest.py --labels "collab/20260827-三方对比战役/labels_424_ex12.csv" --seed 20260902 --out "/private/tmp/missing_manifest_v1_repeat.csv" --verify
cmp "collab/20260902-A测缺失补偿/missing_manifest_v1.csv" "/private/tmp/missing_manifest_v1_repeat.csv"
echo DETERMINISTIC_MANIFEST_OK
```

原始输出（exit 0）：

```text
VERIFY_OK
{"BLCA": {"both_25": 34, "both_50": 69, "both_75": 103, "rna_25": 34, "rna_50": 69, "rna_75": 103, "text_25": 34, "text_50": 69, "text_75": 103}, "BRCA": {"both_25": 95, "both_50": 191, "both_75": 287, "rna_25": 95, "rna_50": 191, "rna_75": 287, "text_25": 95, "text_50": 191, "text_75": 287}, "LGG": {"both_25": 41, "both_50": 83, "both_75": 124, "rna_25": 41, "rna_50": 83, "rna_75": 124, "text_25": 41, "text_50": 83, "text_75": 124}, "LUAD": {"both_25": 43, "both_50": 86, "both_75": 129, "rna_25": 43, "rna_50": 86, "rna_75": 129, "text_25": 43, "text_50": 86, "text_75": 129}, "UCEC": {"both_25": 49, "both_50": 99, "both_75": 148, "rna_25": 49, "rna_50": 99, "rna_75": 148, "text_25": 49, "text_50": 99, "text_75": 148}}
STATS_JSON=/private/tmp/missing_manifest_v1_repeat.csv.stats.json
SHA256=c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156
DETERMINISTIC_MANIFEST_OK
```

### 3.3 α2 等价内联断言脚本

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 内联构造 train/valid/test 三 split 的 BLCA 合成特征，执行默认摘要、rna_50、both_75、rna_100 与工厂透传断言。
# 测试源码未另存文件，以遵守本单文件白名单。
PY
```

原始输出（exit 0）：

```text
ALPHA2_EQUIVALENT_ASSERTIONS_OK
POST_DEFAULT_DATASET_SHA256 5e28d5af5e65464b63ad1f793910b94e49084ac31f30367ff6093a09d250ce71
FACTORY_SPLIT_LENGTHS [2, 1, 3]
RNA50_MASKED 1
BOTH75_MASKED_RNA_TEXT 1 1
RNA100_FACTORY_MASKED_ALL_SPLITS 6
```

### 3.4 α3 等价内联断言脚本

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 内联执行三文件内存编译、13 格点、manifest 过滤、A/B 固定公式、M1、合成 checkpoint、标签补列、JSON 字段与相对路径回归断言。
# 测试源码未另存文件，以遵守本单文件白名单。
PY
```

原始输出（exit 0）：

```text
rna_25: A=0.500000 B=0.500000 n=1 rna=1 text=0
OUTPUT_JSON=/private/var/folders/l3/r93pf6rj6072k5mqwm47wxth0000gn/T/alpha3-final-oq8i0i3e/relative_out/m0real_BLCA_s1.json
ALPHA3_EQUIVALENT_ASSERTIONS_OK
IN_MEMORY_COMPILE_OK 3
GRID_COUNT 13
RISK_A [-2.25, -3.1424, 3000996.0]
RISK_B [-0.837873306693, -0.856482546698, -2.749998e-06]
M1_TRAIN_NONMISSING_COUNTS {'rna': 2, 'text': 2}
DATAPARALLEL_PREFIX_LOAD_OK
RELATIVE_PATH_JSON_OK m0real_BLCA_s1.json
```

### 3.5 评测 CLI 轻依赖检查

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python NPJ/scripts/eval_missing.py --help
```

原始输出（exit 0）：

```text
usage: eval_missing.py [-h] --arm {m0real,m1}
                       --cancer {BLCA,BRCA,LUAD,LGG,UCEC} --seed SEED
                       --ckpt CKPT --manifest MANIFEST [--grids GRIDS]
                       --label LABEL --out-dir OUT_DIR

使用冻结 NPJ checkpoint 评测固定缺失格点的 M0-real 与 M1。

options:
  -h, --help            show this help message and exit
  --arm {m0real,m1}
  --cancer {BLCA,BRCA,LUAD,LGG,UCEC}
  --seed SEED
  --ckpt CKPT
  --manifest MANIFEST
  --grids GRIDS         all 或逗号分隔格点
  --label LABEL
  --out-dir OUT_DIR
```

### 3.6 白名单与禁止文件审计

命令：

```bash
git -C NPJ status --short
git -C NPJ diff --name-only
git -C NPJ ls-files --others --exclude-standard scripts
git -C NPJ diff --check
git -C NPJ diff --quiet -- model/fusion_model.py main_survival.py
git diff --quiet -- baselines/MCAT baselines/PORPOISE
```

原始输出（组合命令 exit 0）：

```text
 M loc_utils_3yr/tcga_dataset.py
?? loc_utils_3yr/__pycache__/tcga_dataset.cpython-310.pyc
?? scripts/
loc_utils_3yr/tcga_dataset.py
scripts/eval_missing.py
scripts/gen_missing_manifest.py
FORBIDDEN_NPJ_DIFF_EXIT=0
FORBIDDEN_BASELINE_DIFF_EXIT=0
```

## 4. 遇到的问题

1. 本机现有环境没有同时具备 `torch`、NPJ 训练依赖与 `sksurv` 的解释器。处理：α1 使用标准库；α2 使用真实 dataset 类和合成特征；α3 使用函数级张量、合成 checkpoint 与伪运行时测试。没有安装或下载依赖。
2. 计划所称 `dual_metric_eval_s4.py` 不存在。按用户确认，公式改以 `collab/20260826-NPJ三模态复现/dual_metric_eval.py` 为准，B 口径包含 sigmoid 后 clamp。
3. 标签真源实际列为 `cancer_type`，且无 dataset 强制读取的 `label`。生成器按 `cancer_type` 读、输出 `cancer`；评测脚本只在临时副本补无业务作用的 `label=0`。
4. 首次 α2 测试被本地缺少 `tqdm` 截断。仅在测试进程替换展示层后重跑，未修改生产依赖；完整 Post-Mortem 见 `notes.md`。
5. α3 自审发现相对 manifest 路径在 `chdir` 后解析错误。已通过 RED→修复→GREEN，现于切换 cwd 前冻结所有输入/输出绝对路径；完整 Post-Mortem 见 `notes.md`。
6. 第一次最终总审计因工具封装中的未转义 Markdown 反引号触发 JavaScript `SyntaxError`，命令本体未执行、仓库未受影响。改用无反引号标题前缀后重跑，exit 0；完整 Post-Mortem 见 `notes.md`。

## 5. 未尽事项与停机状态

- 未在 landau 加载真实 S5 checkpoint、真实三模态特征或运行 `sksurv`。
- 未运行 M0-real BLCA seed123 的真实 13 格点。
- 未执行 M0-real@0% 与 S5 NPJ-A 的逐 seed `|Δ|<0.001` 锚定。
- 未运行 M1 真实 13 格点。
- 未启动 α 后冒烟、β、训练、5-seed 全量或 GPU 长任务。
- 尚需 Claude Code 按互审协议检查本 patch；本结果不能替代 Claude 验收。
- 工作树保持原样，未 commit/push。下一 Gate 只能由指挥官在复核后决定。

---

# 任务 β 交付结果

完成时间：2026-09-02 09:53:07 JST  
执行边界：仅完成 `plan.md` 的“单 β”β1/β2/β3 本地实现与合成验证；未训练、未运行 GPU、未 SSH/scp、未下载、未提交或推送。

## 1. 改动文件清单

### 源码

- 新建 `NPJ/model/compensator.py`
- 修改 `NPJ/model/fusion_model.py`：仅为 `MainModalityMoE` 增加 compensator 构造参数、projector 后/gate 前替换与补偿臂 consistency 返回；未改 `_mask`、`GatedFusion`、backbone、`surv_heads`
- 修改 `NPJ/main_survival.py`：CLI、compensator 构建、bin label/consistency loss、dataset 参数与 `_capr/_bank` 实验身份接线
- 修改 `NPJ/loc_utils_3yr/tcga_dataset.py`：仅在单 α 既有改动之外追加 train-only modality dropout；单 α 的 manifest 遮挡段未改

### 过程与交付

- 追加 `collab/20260902-A测缺失补偿/notes.md`
- 追加 `collab/20260902-A测缺失补偿/result.md`

未修改 `NPJ/scripts/eval_missing.py`、`NPJ/scripts/gen_missing_manifest.py`、MCAT、PORPOISE、`tmp_sur_cache/` 或任何结果目录。任务期间由外部出现的 `AGENTS.md`、`CLAUDE.md`、`s5_report.md` 修改未触碰。

## 2. `plan.md` 验收标准逐条结果

### β1 `NPJ/model/compensator.py`

| 验收项 | 本地状态 | 证据 |
|---|---|---|
| `CAPRecall(modalities=('text','rna'), dim=256, n_bins=4, ema=0.99)` | PASS | 构造签名与默认值一致 |
| 每模态 prototype `[n_bins,dim]` 与 count 为 buffer | PASS | state_dict 包含 `*_prototypes`、`*_prototype_counts`，非梯度参数 |
| 仅 train 模式、valid=1、按 bin 首次直赋/后续 EMA | PASS（合成） | `[2,0]` 首次写入，第二批 `[4,0]` 后以 ema=0.5 得 `[3,0]`；invalid 大值未参与；count=2 |
| img query → prototype key → scaled softmax → 凸组合 → output | PASS（函数级） | 缺失位输出 shape 正确且全有限；q/k/o 均为可学习层 |
| valid 全 1 时逐位不变 | PASS | CAPRecall 与 MissingBank 均以 `rtol=0,atol=0` 对拍通过 |
| 只为训练 dropout 位形成 consistency pair | PASS | `invalid & dropped` 仅 1 行配对，天然/普通 invalid 不自动配对 |
| `MissingBank` 每模态一个 `nn.Parameter[dim]` | PASS | state_dict 含 `bank.text/bank.rna`，缺失行在 gate 前精确替换 |
| `consistency_loss=1-cosine mean`；空配对为 0 | PASS | 同向/反向/空列表函数级断言通过 |

### β2 `NPJ/model/fusion_model.py`

| 验收项 | 本地状态 | 证据 |
|---|---|---|
| `MainModalityMoE.__init__` 新增 `compensator=None` | PASS | 尾部默认参数，不改变既有位置参数 |
| projector 后、`input_list` 前按 `{mm}_valid` 调 compensator | PASS | fusion pre-hook 观察到 text invalid 行在 gate 前变为 `[9,10,11,12]` |
| orig 在相同 projector 后参与 consistency | PASS | `{mm}_orig` 投影为 `[B,D]`，只抽取 `{mm}_dropped` 行 |
| `compensator=None` 前向逐位不变 | PASS（严格合成） | 改前/改后 `hazard/surv` 零容差 allclose，SHA256 均为 `9976563c591db0d733943b05d44ed33069a330bb47507d3efb39633d9b261252` |
| `compensator=None` 单步训练逐位不变 | PASS（严格合成） | train `hazard/surv/loss` 与 SGD 后 22 个 state tensor 全部 `rtol=0,atol=0` |
| 不改 `_mask`/gate/backbone/heads | PASS（AST） | 与 inner Git HEAD 对比，`GatedFusion`、`SurvivalHead`、fusion/backbone/surv_heads assignment、原 `_mask` if 均完全一致 |

### β3 `main_survival.py` + train dropout

| 验收项 | 本地状态 | 证据 |
|---|---|---|
| 三项 CLI 与默认值 | PASS | `none/0.0/0.1`；自定义 `capr/0.15/0.25` 解析通过 |
| train-only、per-sample/per-modality 随机 dropout | PASS（合成） | p=1 仅 train text/rna 全遮；valid/test 不发新键；img 不遮 |
| RNG 由 seed 派生且动态/可复现 | PASS（合成） | patient×modality 独立 RNG 流；同 seed/访问序列完全相同，重复访问同时出现 True/False |
| 保存真 token 与 dropout 身份 | PASS（合成） | p>0 train 发 `{mm}_orig/{mm}_dropped`；只对原 valid 且命中抽样的行置零+invalid |
| p=0 batch 与现状逐位一致 | PASS（严格合成） | 3 人真实 dataset 类的全部键/dtype/shape/字节一致，SHA256 均为 `e0760505b8ffa05186f518ec8f4f1c916c3d64108625b4787c894e98667f88f6` |
| NLL + λ·consistency | PASS（函数级） | λ=0 loss=`0.27254724502563477`；λ=0.1 loss=`0.29754725098609924` 且参数更新不同 |
| compensator none 训练路径不变 | PASS（严格函数对拍） | 从 Git HEAD 提取旧 `finetune_epoch`，旧新 loss 与更新后参数逐位相同 |
| `load_model` 构建 none/capr/bank | PASS | CAPRecall/MissingBank 类型断言通过；非 MainModalityMoE 的非 none 请求被拒绝，防止假实验身份 |
| checkpoint 包含参数与 prototype buffer | PASS（内存 round-trip） | CAP state_dict 26 键、Bank 12 键；`torch.save/load` 后 strict load 通过 |
| 结果/ckpt 追加 `_capr/_bank` | PASS | 幂等得到 `tcga_capr`、`results/s5_capr`；none 不改名 |

### 本地总体结论

- β1、β2、β3 的计划合成验收和默认硬回归均有 exit 0 证据。
- 这不是正式训练、真实 checkpoint 评测或 GPU 冒烟通过证明；按公共纪律仍须 Claude Code 互审后才能进入下一 Gate。

## 3. 测试命令与真实原始输出

### 3.1 β1 + β2 合成断言与默认 allclose

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 实际内联执行：compensator 三类断言、EMA/pair、fusion pre-hook、
# 改前快照对拍 eval + 单步训练的 22 个 state tensor、两文件内存 compile。
PY
```

原始输出（exit 0）：

```text
FINAL_BETA1_ASSERTIONS_OK
FINAL_BETA1_EMA [3.0, 0.0] [2, 0]
FINAL_BETA1_DROPOUT_PAIR_COUNT 1
FINAL_BETA2_FORWARD_ALLCLOSE_OK 9976563c591db0d733943b05d44ed33069a330bb47507d3efb39633d9b261252
FINAL_BETA2_TRAIN_STEP_ALLCLOSE_OK 22
FINAL_BETA2_PRE_GATE_REPLACEMENT_OK [9.0, 10.0, 11.0, 12.0]
FINAL_BETA12_IN_MEMORY_COMPILE_OK 2
```

### 3.2 dataset 默认回归与动态 dropout 协议

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 实际内联构造 train/valid/test 合成缓存：p=0 改前快照逐键对拍、
# p=1 train-only 协议、p=0.5 独立动态 RNG/同 seed 复现、dataset 内存 compile。
PY
```

原始输出（exit 0）：

```text
FINAL_BETA3_DATASET_DEFAULT_EXACT_OK e0760505b8ffa05186f518ec8f4f1c916c3d64108625b4787c894e98667f88f6
FINAL_BETA3_DROPOUT_P1_TRAIN_ONLY_OK 20 2 2
FINAL_BETA3_DROPOUT_FIRST_DRAW_INDEPENDENT_OK 6 3
FINAL_BETA3_DYNAMIC_DROPOUT_REPRO_OK [(True, True), (False, False), (False, True), (True, False), (True, False), (False, True), (True, True), (True, True), (False, False), (False, False), (True, True), (False, True)]
FINAL_BETA3_DATASET_IN_MEMORY_COMPILE_OK 1
```

### 3.3 CLI、模型/ckpt、训练 loss 与身份接线

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 测试进程替代本机缺失的无关顶层依赖，调用真实 parsing_args/load_model/
# finetune_epoch；并从 Git HEAD 提取旧 finetune_epoch 做默认路径对拍。
PY
```

原始输出（exit 0）：

```text
['BLCA'] cancer_types
['BLCA'] cancer_types
['BLCA'] cancer_types
None cancer_types
FINAL_BETA3_CLI_OK none 0.0 0.1 capr 0.15 0.25
FINAL_BETA3_LOAD_CHECKPOINT_OK CAPRecall MissingBank 26 12
FINAL_BETA3_IDENTITY_GUARDS_OK tcga_capr results/s5_capr
FINAL_BETA3_NONE_TRAINING_EXACT_OK 0.27254724502563477 0.49602216482162476
FINAL_BETA3_CONSISTENCY_WIRING_OK 0.27254724502563477 0.29754725098609924
FINAL_BETA3_MAIN_IN_MEMORY_COMPILE_OK 1
```

### 3.4 语法、禁止区与白名单审计

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
# 四文件 compile；AST 对拍 gate/head/backbone/surv_heads/_mask。
PY
git -C NPJ diff --check
git -C NPJ diff --name-only
git -C NPJ ls-files --others --exclude-standard model/compensator.py
git -C NPJ diff --quiet -- scripts/eval_missing.py scripts/gen_missing_manifest.py
git diff --quiet -- baselines/MCAT baselines/PORPOISE MCAT PORPOISE
```

原始输出（组合命令 exit 0）：

```text
FINAL_IN_MEMORY_COMPILE_OK 4
FINAL_FORBIDDEN_FUSION_AST_UNCHANGED_OK GatedFusion SurvivalHead backbone surv_heads _mask
FINAL_NPJ_TRACKED_DIFF_FILES
loc_utils_3yr/tcga_dataset.py
main_survival.py
model/fusion_model.py
FINAL_NPJ_NEW_BETA_FILES
model/compensator.py
FINAL_COMPILE_EXIT=0
FINAL_DIFF_CHECK_EXIT=0
FINAL_ALPHA_SCRIPTS_DIFF_EXIT=0
FINAL_MCAT_PORPOISE_DIFF_EXIT=0
```

### 3.5 最终交付文档、源码 SHA 与禁止区复核

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
# 复核四个源码文件的交付 SHA256 与内存 compile；检查 notes/result 必备标记。
PY
git -C NPJ diff --check
git -C NPJ diff --quiet -- scripts/eval_missing.py scripts/gen_missing_manifest.py
git diff --quiet -- baselines/MCAT baselines/PORPOISE MCAT PORPOISE
```

原始输出（组合命令 exit 0）：

```text
FINAL_DELIVERY_DOCUMENT_AUDIT_OK
FINAL_SOURCE_SHA_AND_COMPILE_OK 4
FINAL_DOCUMENT_AUDIT_EXIT=0
FINAL_NPJ_DIFF_CHECK_EXIT=0
FINAL_ALPHA_SCRIPTS_DIFF_EXIT=0
FINAL_MCAT_PORPOISE_DIFF_EXIT=0
```

## 4. 遇到的问题

1. 本机 conda 环境有 Torch/pandas/sklearn，但缺 transformers、scattermoe、sksurv、accelerate、torchmetrics、tqdm/easydict。测试只在进程边界替代与目标无关的导入，生产文件没有依赖替身。
2. `load_model` 初版会对非 `MainModalityMoE` 静默丢弃 compensator，造成后缀与真实模型不一致。已按 RED→GREEN 增加明确拒绝。
3. modality dropout 初版固定每患者决策，不符合训练 dropout 的动态语义。已改为 patient×modality 独立 RNG 流，每次访问重采样且同 seed 序列可复现。
4. 三次测试夹具/工具问题（未保留 session id、Matplotlib/easydict 重型导入、`tqdm.__spec__` 触发 Dynamo）均未修改生产逻辑；完整 Post-Mortem 与 Prevention Rule 已追加到 `notes.md`。
5. 多 GPU `nn.DataParallel` 下 CAP prototype buffer EMA 的跨 replica 同步未在本地验证；本任务禁止 GPU/训练，不能声称多卡已通过。若指挥官计划暴露多张 GPU，应先裁定单卡 smoke 或补 prototype 同步验收。

## 5. 未尽事项与停机状态

- `eval_missing.py` 当前调用 `load_model` 时默认 `compensator='none'`。因此它不能直接 strict-load CAP/Bank checkpoint；按 β 白名单未修改。指挥官若要用该脚本评测 M2，需另行批准 compensator 参数/ckpt 构建接线。
- 未运行 M2 正式训练、GPU 冒烟、真实特征、真实 checkpoint 或任何癌种实验。
- 未验证多 GPU prototype buffer 同步行为。
- 尚需 Claude Code 按互审协议检查本 patch；本地 adversarial review 不能替代另一方验收。
- 未 commit/push；当前普通 `main` 工作树原地保留。下一 Gate、部署与 M2 冒烟只能由指挥官和用户决定。

# 任务 γ：NPJ-C 干净骨架交付（2026-09-02）

## 1. 改动文件清单

1. `NPJ/model/fusion_model.py`
   - 仅在 `MainModalityMoE` 之后追加 `class NPJC(nn.Module)`。
   - 新类包含逐模态 projector、零初始化 modality embedding、`TransformerEncoder`、per-cancer survival heads、逐样本 valid mask、CAP/Bank 补偿接入、attention padding mask 与 masked mean pooling。
   - 未修改 `GatedFusion`、`MainModalityMoE` 或旧 `_mask` 逻辑。
2. `NPJ/main_survival.py`
   - 仅把 compensator 允许网络从 `MainModalityMoE` 放宽到 `{'MainModalityMoE', 'NPJC'}`。
   - 仅在 `load_model` 增加 `network_type == 'NPJC'` 构建分支，并复用既有 none/capr/bank compensator 构建逻辑。
3. `collab/20260902-A测缺失补偿/notes.md`
   - append-only 追加任务 γ 的基线、RED、GREEN、验证与停机记录。
4. `collab/20260902-A测缺失补偿/result.md`
   - append-only 追加本交付章节。

## 2. `plan.md` 单 γ 验收逐条结果

### γ1 `NPJC`

- **本地达成，待 Claude Code 互审**：`NPJC.__init__` 参数精确为 `device/modalities/hidden_size/dropout_rate/pred_dim/mlp_ratio/n_backbone/n_head/cancer_types/compensator`，不接收 `num_experts/topk/n_token`。
- **本地达成，待互审**：每模态执行 mean pooling（3D 输入）与 `Linear + ReLU + Dropout`；`modality_embed` 为 `[M,D]` 零初始化参数；backbone 为指定超参的 `TransformerEncoderLayer × n_backbone`；survival heads 为 per-cancer `SurvivalHead(D,pred_dim)`。
- **本地达成，待互审**：`{mm}_valid` 按样本转 bool，img 恒有效；未补偿缺失位经 `src_key_padding_mask` 屏蔽，masked mean 只平均 valid token。
- **本地达成，待互审**：有 compensator 时复用 `tokens_dict/valids_dict/{mm}_orig/{mm}_dropped/bin_labels/training` 协议；被替换模态 valid 置 True，返回三元组；无 compensator 返回二元组。
- **本地达成，待互审**：AST 断言 `NPJC` 类体内无 `GatedFusion` 与 `self.fusion` 引用。

### γ2 `load_model`

- **本地达成，待互审**：`load_model('NPJC', ...)` 对 none/capr/bank 分别构建无 compensator、`CAPRecall`、`MissingBank` 的 NPJC；其他不支持网络仍被 compensator guard 拒绝。
- **本地达成，待互审**：未改训练循环、dropout、suffix 或其他网络分支。

### 回归红线与禁止项

- **本地达成，待互审**：`network_type='MainModalityMoE'` 的 hazard 与 surv 均对改前字面输出执行 `torch.allclose(rtol=0, atol=0)`，输出 SHA256 完全一致。
- **本地达成，待互审**：`GatedFusion` 与 `MainModalityMoE` 的 AST 源段 SHA256 与任务启动前一致。
- 本轮未改 `compensator.py`、`tcga_dataset.py`、`scripts/`、`eval_missing.py`，未修 `_mask`；未运行训练、GPU、SSH、下载或 git commit/push。仓库开始时已有其他脏改动与未跟踪产物，本轮原样保留。

## 3. 测试命令与真实原始输出

### 3.1 TDD RED

命令入口：

```bash
python - <<'PY'
# AST 显式断言 fusion_model.py 存在 NPJC，且 load_model 含 NPJC 分支。
PY
```

原始输出（业务 RED，`RED_EXIT=1`）：

```text
Traceback (most recent call last):
  File "<stdin>", line 5, in <module>
AssertionError: EXPECTED_RED_GAMMA1: class NPJC is absent
RED_EXIT=1
```

### 3.2 改前 `MainModalityMoE` 固定前向基线

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 固定 seed=20260902/902，CPU、dropout=0、三模态合成 batch，打印 hazard/surv 与 SHA256。
PY
```

原始输出（exit 0）：

```text
GAMMA_BASELINE_HAZARD= [[-0.21874359250068665, 1.1139329671859741, -0.186922088265419, 0.9764500856399536], [0.6432084441184998, -0.07012945413589478, -0.3821220099925995, 0.05036593973636627]]
GAMMA_BASELINE_SURV= [[1.2187435626983643, -0.13885506987571716, -0.1648101508617401, -0.0038812649436295033], [0.35679155588150024, 0.3818131387233734, 0.527712345123291, 0.5011336207389832]]
GAMMA_BASELINE_SHA256= 3344fbadd1abc1d77e1016da35a78080bb7d5392e3485c08ec61366b2ea4c908
```

### 3.3 最终四条合成单测、AST、load_model、旧路径 allclose、compile

命令入口：

```bash
set -e
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 真实 NPJC/CAPRecall CPU 前向四断言；从当前源码 AST 提取并执行真实 load_model；
# 对改前字面 tensor 跑 MainModalityMoE 双零容差 allclose；复核旧类 SHA 与内存 compile。
PY
git -C NPJ diff --check
```

原始输出（组合命令 exit 0）：

```text
FINAL_GAMMA_NPJC_SIGNATURE_OK ['device', 'modalities', 'hidden_size', 'dropout_rate', 'pred_dim', 'mlp_ratio', 'n_backbone', 'n_head', 'cancer_types', 'compensator']
FINAL_GAMMA_ASSERT_1_ALL_VALID_OK (3, 5)
FINAL_GAMMA_ASSERT_2_MASK_INVARIANT_OK 0.0
FINAL_GAMMA_ASSERT_3_CAP_RECALL_ATTENDS_OK [[False, False, False], [False, False, False]] 0.7243994474411011
FINAL_GAMMA_ASSERT_4_AST_NO_GATED_FUSION_OK
['BLCA'] cancer_types
['BLCA'] cancer_types
['BLCA'] cancer_types
['BLCA'] cancer_types
FINAL_GAMMA_LOAD_MODEL_BRANCHES_OK NPJC CAPRecall MissingBank
['BLCA'] cancer_types
FINAL_GAMMA_MAIN_MODALITY_MOE_EXACT_ALLCLOSE_OK 3344fbadd1abc1d77e1016da35a78080bb7d5392e3485c08ec61366b2ea4c908
FINAL_GAMMA_OLD_CLASS_AST_UNCHANGED_OK {'GatedFusion': '4f2571d1b72705271771927e009f78005b4c30f694f625227b610ec54067dc97', 'MainModalityMoE': 'e535e82bf1930e87479f3dc5cd9ca03f27e671989cbaf66df35913f7737c2f8b'}
FINAL_GAMMA_IN_MEMORY_COMPILE_OK 2
FINAL_GAMMA_TEST_EXIT=0
FINAL_GAMMA_DIFF_CHECK_EXIT=0
```

## 4. 遇到的问题

1. 本机目标 conda 环境缺 `transformers`；合成测试只在测试进程边界替代 `transformers` 与未用于 NPJC/MainModalityMoE 前向的 `scattermoe.GLUMLP` 符号。真实 Torch、`fusion_model.py`、`compensator.py` 与 `load_model` 函数体均被执行，生产代码未加入兼容替身。
2. 首轮 GREEN 触发 PyTorch nested-tensor 原型 API 的 `UserWarning`，断言仍全部通过；最终复跑只在测试进程过滤这条框架警告，未改变生产模型参数或路径。
3. 本机没有 `ruff` 可执行文件，未安装依赖，也不伪报 lint；替代静态证据为两个文件内存 compile、AST 合同和 `git diff --check`。

## 5. 未尽事项与停机状态

- 未运行训练、真实数据、真实 checkpoint、GPU 或正式癌种实验；这些均被本单明确禁止。
- 尚需 Claude Code 按仓库互审协议检查本 patch；Codex 本地验证不能替代另一方验收，也不能授权进入下一 Gate。
- 未 commit/push；当前工作树原地保留。

# 任务 δ：统一 Python 发车器 + 缓存共享 + 评测重构（2026-09-02）

## 1. 改动文件清单

1. `NPJ/scripts/train_launcher.py`（新建）
   - 支持 `--plan <yaml>` 与 `--arms/--cancers/--seeds` 两种 run 来源；内置 E0/E1 参数映射。
   - 支持 `--gpus`、`--per_gpu` 多槽调度、绝对日志、原子 `runs_state.json`、checkpoint 幂等 skipped/`--force`、按癌种缓存预热、正式 GPU 门禁包装、可选完成后评测和 SIGTERM 进程组转发。
   - `--dry_run` 只打印 resolved GPU policy、计划、checkpoint、命令与槽位，不创建状态/日志/缓存，不启动子进程。
2. `NPJ/loc_utils_3yr/tcga_dataset.py`
   - 仅把 survival 缓存新文件名中的 `network_type` 后缀移除。
   - 加载顺序为新名优先，再回退 `_MainModalityMoE`、`_NPJC`、当前及其他现存旧后缀；损坏候选继续回退；保存只写新名。
   - 记录实际命中的缓存文件，避免旧 RNA 缓存命中后因新文件尚不存在而重复重建。
3. `NPJ/scripts/eval_missing.py`
   - 默认只构建一次 test dataset，13 格点通过 `missing_mode/missing_set` 内存切换。
   - 保留 `_make_test_dataset_legacy` 逐格点重建路径供合成对拍；M1 train 均值逻辑未改。
   - CLI 与 JSON schema 未改。
4. `collab/20260902-A测缺失补偿/notes.md`
   - append-only 追加现实审计、RED/GREEN、方案取舍、测试、Post-Mortem 与停机记录。
5. `collab/20260902-A测缺失补偿/result.md`
   - append-only 追加本交付章节。

## 2. `plan.md` 单 δ 验收逐条结果

### δ1 缓存共享

- **本地达成，待 Claude Code 互审**：缓存 payload 审计确认 `network_type` 不参与内容构建，只参与旧文件名；新保存名不含 `network_type`。
- **本地达成，待互审**：新名优先，已知旧名与动态发现旧后缀依次回退；损坏新文件可回退有效旧文件。
- **本地达成，待互审**：合成小缓存目录验证候选顺序、旧名回退与保存名；真实 `TCGASurDataset` 13 格点测试同时使用新缓存名。
- **边界说明**：坑 D2 指出缓存 payload 还受特征路径、维度、token 数等影响，但本单只获准移除 `network_type`；未擅自扩大缓存键格式。

### δ2 统一发车器

- **本地达成，待互审**：YAML plan 与生成器双入口；2 臂×2 癌×2 seeds 展开 8 runs。E0=`NPJC+none`；E1=`NPJC+capr+modality_dropout 0.15+consistency_lambda 0.1`。
- **本地达成，待互审**：`--gpus 0,1 --per_gpu 2` 四槽轮转；临时 formal wrapper 的 8-run 状态机全部 done/exit 0，四个槽均被使用。该测试不执行内层训练命令。
- **本地达成，待互审**：状态文件原子写，字段覆盖 pending/running/done/failed/skipped、pid、exit、duration；checkpoint 精确按 `ModelDumper` 规则推导，存在时 skipped，`--force` 回到 pending。
- **本地达成，待互审**：缓存齐全性函数在合成目录对 train/valid/test×img/text/rna 共 9 项判定通过；实际预热实现为每癌一个独立进程、受 `--prewarm_workers` 限流。因本单禁止真实数据任务，未实跑真实预热。
- **本地达成，待互审**：每 run 日志为绝对路径；正式执行复用 `scripts/launch_formal.sh`，不复制 GPU util 采样；resolved policy 含 `allow_low_gpu_util` 与 reason。
- **本地达成，待互审**：可选评测支持 plan 规定的 `--eval_grids/--eval_workers/--eval_out`，另要求显式 `--eval_manifest`；E0/E1 使用 m0real 特征语义评测，最终产物按 `<arm>_<cancer>_s<seed>.json` 原子落盘。
- **本地达成，待互审**：SIGTERM 合成测试确认包装器 PGID 与日志中的训练 PGID 均收到终止信号。
- **本地达成，待互审**：8-run `--dry_run` 实跑只打印，状态与日志路径均未创建。
- **代码现实裁定**：plan 写“util 采样在 main_survival”，实际采样在 `launch_formal.sh`；实现复用后者，内层仍是 `python main_survival.py ...`。

### δ3 评测 dataset 复用

- **本地达成，待互审**：默认 `run_evaluation` 在 m0real/all 合成端到端中只构建 1 个 test dataset，对同一对象切换全部 13 格点。
- **本地达成，待互审**：真实 `TCGASurDataset` 对 13 格点逐患者比较，新复用路径与 `_legacy` 重建路径的 img/text/rna 特征及三个 valid 完全一致。
- **本地达成，待互审**：既有 `eval_missing.py` 十个业务 CLI 参数、输出文件名和每格点六字段保持不变；M1 训练均值函数与调用位置未改。

### 禁止项与停机门

- 未修改 `main_survival.py`、`fusion_model.py`、`compensator.py`，未修改任何模型语义。
- 未 SSH/scp、未训练、未下载、未运行真实 checkpoint/GPU 评测、未 commit/push。
- 当前工作树在任务开始前已有其他战役和用户改动，本轮均保留。

## 3. 测试命令与真实原始输出

### 3.1 TDD RED

命令入口：三个独立 `python - <<'PY'` 存在性/行为断言；δ1 在测试进程提供最小 `tqdm` 替身。

原始业务 RED：

```text
AssertionError: EXPECTED_RED_DELTA1: cache fallback API is absent
DELTA1_BUSINESS_RED_EXIT=1
AssertionError: EXPECTED_RED_DELTA2: train_launcher.py is absent
DELTA2_RED_EXIT=1
AssertionError: EXPECTED_RED_DELTA3: in-memory grid switch API is absent
DELTA3_RED_EXIT=1
```

launcher 评测参数名契约 RED：

```text
train_launcher.py: error: unrecognized arguments: --eval_grids none --eval_out /private/tmp/eval --eval_manifest /private/tmp/manifest.csv
DELTA2_EVAL_CLI_RED_EXIT=2
```

### 3.2 δ1 缓存 + δ3 真实 dataset 全 13 格点对拍

命令入口：

```bash
LOKY_MAX_CPU_COUNT=1 PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 合成缓存候选/损坏回退/保存名；构造真实 TCGASurDataset 小特征目录；13 格点与 _legacy 逐键对拍。
PY
```

原始输出（exit 0）：

```text
FINAL_DELTA1_CANDIDATE_ORDER_OK ['img_sur_test_all_BLCA.pkl', 'img_sur_test_all_BLCA_MainModalityMoE.pkl', 'img_sur_test_all_BLCA_NPJC.pkl', 'img_sur_test_all_BLCA_FutureNet.pkl']
FINAL_DELTA1_CORRUPT_NEW_LEGACY_FALLBACK_OK
FINAL_DELTA1_SAVE_NEW_NAME_OK
FINAL_DELTA3_REAL_DATASET_SINGLE_REUSE_OK 13 13
FINAL_DELTA3_REAL_DATASET_LEGACY_EQUAL_OK ['none', 'rna_25', 'rna_50', 'rna_75', 'text_25', 'text_50', 'text_75', 'both_25', 'both_50', 'both_75', 'rna_100', 'text_100', 'both_100']
FINAL_DELTA1_DELTA3_REAL_EXIT=0
```

### 3.3 δ2 函数、状态机、幂等、评测接力与信号单测

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
# generator/plan、slot、atomic state、cache completeness、checkpoint skip/force、
# 8-run 假 formal scheduler、假 eval relay、两个 sleep PGID 的 SIGTERM。
PY
```

原始输出（exit 0）：

```text
FINAL_DELTA2_GENERATOR_PLAN_OK 8 RunSpec(name='custom', arm='custom', network_type='NPJC', compensator='none', cancer='BLCA', seed=7, extra_args=('--epochs', '2'))
FINAL_DELTA2_SLOT_ASSIGNMENT_OK [('0', 0), ('1', 0), ('0', 1), ('1', 1)]
FINAL_DELTA2_STATE_CACHE_IDEMPOTENCE_OK 9 skipped pending
FINAL_DELTA2_FAKE_SCHEDULER_OK 8 [('0', 0), ('0', 1), ('1', 0), ('1', 1)]
FINAL_DELTA2_EVAL_RELAY_SIGTERM_OK e0_BLCA_s123.json
FINAL_DELTA2_UNIT_EXIT=0
```

YAML fallback 与 PyYAML 对拍原始输出：

```text
DELTA2_YAML_FALLBACK_MATCHES_PYYAML_OK NPJ/config/gpu_train.yaml
DELTA2_YAML_FALLBACK_MATCHES_PYYAML_OK NPJ/model/config/surv_multimodal_mainmoe_uni2.yml
DELTA2_YAML_COMPARE_EXIT=0
```

### 3.4 δ2 真实 `--dry_run`：2 臂×2 癌×2 seeds

命令入口：

```bash
python NPJ/scripts/train_launcher.py --arms e0,e1 --cancers BLCA,BRCA \
  --seeds 123,456 --gpus 0,1 --per_gpu 2 --dry_run \
  --state-file <临时目录>/runs_state.json --logs-dir <临时目录>/logs
```

原始输出（exit 0；命令行逐条完整打印）：

```text
RESOLVED_GPU_POLICY={"allow_low_gpu_util": true, "batch_size": 32, "concurrent_runs": 1, "gpu_util_min_percent": 50, "gpu_util_target_percent": 80, "gpu_util_warmup_sec": 120, "gradient_accumulation_steps": 1, "low_gpu_util_reason": "NPJ small compute graph: measured active-util median 11-15%, peak 31% across bs 32-256 on V100; wall time increases with larger bs (probe 2026-09-02, collab/20260902-NPJ-GPU合同/notes.md)", "non_blocking": true, "num_workers": 4, "persistent_workers": true, "pin_memory": true, "prefetch_factor": 4}
DRY_RUN index=1 name=e0_BLCA_s123 arm=e0 cancer=BLCA seed=123 gpu=0 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out/123/tcga_uni2_img_1536text_768rna_256_NPJC_BLCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 123 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type NPJC --hidden_size 256 --compensator none
DRY_RUN index=2 name=e0_BLCA_s456 arm=e0 cancer=BLCA seed=456 gpu=1 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out/456/tcga_uni2_img_1536text_768rna_256_NPJC_BLCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 456 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type NPJC --hidden_size 256 --compensator none
DRY_RUN index=3 name=e0_BRCA_s123 arm=e0 cancer=BRCA seed=123 gpu=0 slot=1 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out/123/tcga_uni2_img_1536text_768rna_256_NPJC_BRCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 123 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BRCA --network_type NPJC --hidden_size 256 --compensator none
DRY_RUN index=4 name=e0_BRCA_s456 arm=e0 cancer=BRCA seed=456 gpu=1 slot=1 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out/456/tcga_uni2_img_1536text_768rna_256_NPJC_BRCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 456 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BRCA --network_type NPJC --hidden_size 256 --compensator none
DRY_RUN index=5 name=e1_BLCA_s123 arm=e1 cancer=BLCA seed=123 gpu=0 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_capr/123/tcga_uni2_capr_img_1536text_768rna_256_NPJC_BLCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 123 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type NPJC --hidden_size 256 --compensator capr --modality_dropout 0.15 --consistency_lambda 0.1
DRY_RUN index=6 name=e1_BLCA_s456 arm=e1 cancer=BLCA seed=456 gpu=1 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_capr/456/tcga_uni2_capr_img_1536text_768rna_256_NPJC_BLCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 456 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type NPJC --hidden_size 256 --compensator capr --modality_dropout 0.15 --consistency_lambda 0.1
DRY_RUN index=7 name=e1_BRCA_s123 arm=e1 cancer=BRCA seed=123 gpu=0 slot=1 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_capr/123/tcga_uni2_capr_img_1536text_768rna_256_NPJC_BRCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 123 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BRCA --network_type NPJC --hidden_size 256 --compensator capr --modality_dropout 0.15 --consistency_lambda 0.1
DRY_RUN index=8 name=e1_BRCA_s456 arm=e1 cancer=BRCA seed=456 gpu=1 slot=1 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_capr/456/tcga_uni2_capr_img_1536text_768rna_256_NPJC_BRCA_surv.pth command=/Users/wuhao/miniconda3/bin/python /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 456 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BRCA --network_type NPJC --hidden_size 256 --compensator capr --modality_dropout 0.15 --consistency_lambda 0.1
DRY_RUN_TOTAL=8
FINAL_DELTA2_DRY_RUN_NO_SIDE_EFFECT_OK
FINAL_DELTA2_DRY_RUN_EXIT=0
```

### 3.5 δ3 单构建端到端、CLI/JSON、编译与范围检查

命令入口：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python - <<'PY'
# 假模型 + FakeDataset 跑 run_evaluation(all)，统计构造次数并验证 13 格点 JSON；
# 内存 compile 三个目标源码；核对三个禁止文件 SHA256。
PY
python NPJ/scripts/eval_missing.py --help
python NPJ/scripts/train_launcher.py --help
git -C NPJ diff --check
git diff --check -- collab/20260902-A测缺失补偿/notes.md collab/20260902-A测缺失补偿/result.md
```

原始输出（组合 exit 0）：

```text
none: A=0.500000 B=0.600000 n=3 rna=0 text=0
rna_25: A=0.500000 B=0.600000 n=3 rna=1 text=0
rna_50: A=0.500000 B=0.600000 n=3 rna=1 text=0
rna_75: A=0.500000 B=0.600000 n=3 rna=1 text=0
text_25: A=0.500000 B=0.600000 n=3 rna=0 text=1
text_50: A=0.500000 B=0.600000 n=3 rna=0 text=1
text_75: A=0.500000 B=0.600000 n=3 rna=0 text=1
both_25: A=0.500000 B=0.600000 n=3 rna=1 text=1
both_50: A=0.500000 B=0.600000 n=3 rna=1 text=1
both_75: A=0.500000 B=0.600000 n=3 rna=1 text=1
rna_100: A=0.500000 B=0.600000 n=3 rna=3 text=0
text_100: A=0.500000 B=0.600000 n=3 rna=0 text=3
both_100: A=0.500000 B=0.600000 n=3 rna=3 text=3
OUTPUT_JSON=<临时目录>/out/m0real_BLCA_s123.json
FINAL_DELTA3_RUN_EVALUATION_SINGLE_BUILD_OK 1 1
FINAL_DELTA3_13_GRID_JSON_SCHEMA_OK 13 ['cindex_A', 'cindex_B', 'grid_sha', 'n_masked_rna', 'n_masked_text', 'n_test']
FINAL_THREE_FILE_IN_MEMORY_COMPILE_OK 3
FINAL_FORBIDDEN_SOURCE_SHA_UNCHANGED_OK 3
FINAL_RUNTIME_STATIC_EXIT=0
FINAL_EVAL_CLI_UNCHANGED_OK
FINAL_LAUNCHER_CLI_CONTRACT_OK
FINAL_HELP_EXIT=0
FINAL_NPJ_DIFF_CHECK_EXIT=0
FINAL_COLLAB_DIFF_CHECK_EXIT=0
```

## 4. 遇到的问题

1. 本地 conda 环境缺 `tqdm`，默认 Python 缺 PyYAML。函数级 dataset 测试只在进程边界替代展示依赖；launcher 对 PyYAML 改为惰性优先使用，并提供边界明确的标准库 YAML 子集 fallback。生产训练依赖未安装或伪造。
2. YAML fallback 初版把 `none` 误解析为空值，已按 YAML 标准只保留 `null/~` 为空，并与 PyYAML 对两个真实配置逐对象对拍。
3. plan 的 GPU 采样位置描述与代码现实不符：采样在 `launch_formal.sh`。实现复用该脚本，未复制门禁算法。
4. `eval_missing.py --arm` 既有 choices 只有 m0real/m1，而 launcher 要输出 e0/e1 文件名。launcher 对非 M1 arm 使用 m0real 特征语义调用，再原子改写 arm 字段并按真实 arm 命名；`eval_missing.py` CLI/schema 未改。
5. 三个测试夹具问题（缺 `tqdm`、zsh `status` 特殊变量、假评测器 `--out_dir` 拼写）和一个测试期望问题（JSON keys 顺序）均已在 `notes.md` 记录完整 Post-Mortem；没有为夹具问题修改模型或训练代码。
6. 本机未发现 `ruff`；未安装依赖、不伪报 lint。静态验证使用内存 compile、CLI 契约、SHA 与 `diff --check`。

## 5. 未尽事项与停机状态

- 按本单禁令，真实缓存预热、真实 `launch_formal.sh` GPU 门禁、训练、真实 checkpoint 评测均未执行；这里只验证了合成数据、假 formal 子进程和 dry-run。
- 尚需 Claude Code 按仓库互审协议检查本 patch；Codex 本地通过不能替代另一方 review，也不能授权部署或进入下一 Gate。
- 未 commit/push；普通 `main` 工作树及任务开始前的既有改动全部原地保留。
