# A 测缺失补偿战役 · 派单契约（r2 方案已获用户批准）

总方案见 `~/.claude/plans/prompt-m0-s5-majestic-nygaard.md`。骨架：NPJ（本地副本 `/Users/wuhao/Desktop/TriModalSurv/NPJ/`，与 landau 同步已验证）。模态 token 实际 256 维（yml 的 32 是死配置）；dataset 发 `{mm}_valid`、模型读 `{mm}_mask` 的死链路**保持原样不修**。

## 单 α · 缺失评测基建（先行）

### 目标
不改模型前向的前提下，建立"固定 manifest 测试遮挡 + 13 格点评测 + A/B 双口径输出"的完整评测通道，使 M0-real（S5 原 ckpt 遮挡评测）与 M1（测试期均值盲补）两个零训练臂可跑。

### 分步任务与验收标准

**α1. `scripts/gen_missing_manifest.py`（新文件）**
- 输入：`--labels <labels_424_ex12.csv>` `--seed <int>` `--out <csv>`；对 5 癌（BLCA/BRCA/LUAD/LGG/UCEC）的 **test split 患者**生成缺失名单
- 模式 {rna, text, both} × 率 {25,50,75}%：每患者布尔列 `<mode>_<rate>`（9 列）；**嵌套约束**：同模式下 25% 名单 ⊂ 50% ⊂ 75%（按同一乱序前缀取）；`both` 模式独立抽样（也满足自身嵌套）
- 输出 CSV 列：patient_id, cancer, rna_25, rna_50, rna_75, text_25, text_50, text_75, both_25, both_50, both_75；末行后打印总表 SHA256
- 验收：脚本对 labels_424_ex12 实跑产出 manifest；自带 `--verify` 模式断言嵌套性 + 每癌每列比例误差 ≤1 人 + 仅含 test 患者
- 同时产出 `<out>.stats.json`：每癌每格点实际遮挡人数

**α2. dataset 遮挡通道（改 `loc_utils_3yr/tcga_dataset.py`）**
- `TCGASurDataset.__init__` 新增可选参数 `missing_manifest=None, missing_grid=None`（grid 形如 `"rna_50"` / `"both_75"` / `"rna_100"` / `None`）；`*_100` 表示该模式全体患者遮挡，不查 manifest
- 生效逻辑：命中名单的 (pid, modality) 在 `safe_modality_get` 返回零特征 + `valid=0`（与现有 simulate/天然缺失同通道）；`both` 同时遮 rna 与 text；**img 永不遮**
- `get_dataset_tcga_sur` 把两参数透传给 train/val/test 三个 dataset（评测只用 test，但通道要通）
- 不改 `simulate_missing_modality` 既有行为；不碰 `fusion_model.py`
- 验收：新增参数默认 None 时，dataset 行为与改动前完全一致（对 BLCA 构建一次，逐样本 `{mm}_valid` 与改动前位对齐）

**α3. `scripts/eval_missing.py`（新文件）**
- 参数：`--arm {m0real,m1}` `--cancer` `--seed` `--ckpt` `--manifest` `--grids all|逗号列表` `--label <csv>` `--out-dir`
- 对每个格点（13 个：none/0% + 9 个 manifest 格点 + rna_100/text_100/both_100）：构建 test loader（用 α2 通道）→ 加载 ckpt（处理 DataParallel `module.` 前缀）→ 前向收 logits → **同时输出 A 口径（raw cumprod）与 B 口径（sigmoid cumprod）c-index**（sksurv concordance_index_censored）
- `--arm m1`：缺失模态不置零，改填**训练集均值特征**（按癌种、按模态，从 train split 的非缺失样本在线计算原始特征均值，text (200,768)/rna (2048,256) 形状逐元素均值；valid 仍标 0 供记录，但特征为均值）——特征级实现，模型零改动
- 输出 JSON：`<out-dir>/<arm>_<cancer>_s<seed>.json`，含每格点 {cindex_A, cindex_B, n_test, n_masked_rna, n_masked_text, grid_sha}
- 复用 `main_survival.py` 的模型构建/加载函数（import，不复制类定义）；hidden_size 用默认 256
- 验收（landau 实跑由指挥官执行，你只需保证本地合成自测过）：本地用随机小张量+假 ckpt 的合成冒烟（构建 3 癌 20 病人假数据集目录不可行则做函数级单测：格点解析、manifest 过滤、A/B 口径公式对拍 dual_metric_eval_s4.py 的实现）

### 文件白名单
- 新建：`NPJ/scripts/gen_missing_manifest.py`、`NPJ/scripts/eval_missing.py`
- 修改：`NPJ/loc_utils_3yr/tcga_dataset.py`（仅 §α2 范围）
- 记录：`collab/20260902-A测缺失补偿/notes.md`（过程）、`result.md`（交付）
- **禁止**：改 `model/fusion_model.py`、`main_survival.py`、MCAT/PORPOISE 任何文件；修 `_mask` 死链路；跑训练；SSH/scp；下载；git commit/push

### 测试命令（交付时须全部实跑通过并附输出）
```
python NPJ/scripts/gen_missing_manifest.py --labels "collab/20260827-三方对比战役/labels_424_ex12.csv" --seed 20260902 --out "collab/20260902-A测缺失补偿/missing_manifest_v1.csv" --verify
python -m pytest <你的单测文件> 或等价断言脚本（α2 默认行为不变断言 + α3 函数级单测）
```

## 单 β · CAP-Recall 补偿器（α 验收后另发，本单不做）

预告不执行：`model/compensator.py`（CAPRecall + MissingBank）、fusion_model.py:1013 插入、main_survival.py 训练接线（--compensator、dropout p=0.15、一致性 loss）。

## 冒烟与停机门（指挥官执行，Codex 不碰）
α 交付复核后：部署 landau → M0-real BLCA seed123 全 13 格点实跑 → 锚定断言 M0-real@0% vs S5 **NPJ-B** 逐 seed |Δ|<0.001（A 列旁证；BLCA s123 恰 A=B=0.5985，已跑冒烟双口径同过） → 通过后发单 β；β 交付后 M2 冒烟 1 run → **停，汇报用户，等允许再铺全量**。

## 单 β · CAP-Recall 补偿器与训练接线（α 冒烟通过后派发）

### β1 `NPJ/model/compensator.py`（新文件）
- `CAPRecall(nn.Module)`：构造参数 `modalities=('text','rna'), dim=256, n_bins=4, ema=0.99`
  - 每模态原型表 buffer `[n_bins, dim]`（register_buffer，非梯度参数）+ 初始化计数 buffer
  - `update_prototypes(tokens, valids, bin_labels)`：训练模式下，用**该模态 valid=1 的样本**按 bin EMA 更新（首次命中直接赋值）
  - `recall(anchor_img_token, modality)`：query=Linear_q(img_token)，keys=Linear_k(原型表)，scaled dot-product → softmax → 凸组合原型 → Linear_o 输出 256d 补偿 token；Linear_q/k/o 为可学习层
  - `forward(tokens_dict, valids_dict, bin_labels=None, training=False)`：对每个 (样本 i, 模态 mm∈text/rna) valid=0 的位置，用 recall 替换 token；training 且 bin_labels 给出时先 update_prototypes；返回替换后 tokens_dict + `consistency_pairs`（仅训练期 dropout 位：合成 token 与被 dropout 前真 token 的配对，供 loss）
- `MissingBank(nn.Module)`：每模态一个 `nn.Parameter[dim]`，同 forward 接口（M1b）
- `consistency_loss(pairs)`：1 - cosine 均值；空配对返回 0 标量
- 单测要求：valid 全 1 时输出 tokens 与输入逐位相同；替换位输出有限值且形状正确；EMA 更新后原型变化方向正确

### β2 `NPJ/model/fusion_model.py`（限定改动）
- `MainModalityMoE.__init__` 加 `compensator=None`；forward 在 m_projector 循环结束、`input_list` 组装前：若 `self.compensator is not None` 且 batch 提供 `{mm}_valid`，调 compensator 替换缺失位 token
- **compensator=None 时 forward 行为逐位不变**（回归断言：随机输入下新旧代码输出 allclose）
- 不修 `_mask` 死链路、不动 gate/backbone/heads

### β3 训练接线（`NPJ/main_survival.py` + `tcga_dataset.py` 小段）
- CLI：`--compensator {none,capr,bank}`（默认 none）、`--modality_dropout 0.0`（重训臂用 0.15）、`--consistency_lambda 0.1`
- 模态 dropout 在 dataset train split 实现：per-sample per-modality（text/rna 独立）以 p 随机置零+`_valid=0`，RNG 由 args.seed 派生；**保留被 drop 前的真 token 副本传给一致性 loss**（实现方式可选：batch 里额外发 `{mm}_orig` 仅训练期）
- loss = NLL + λ·consistency（compensator=none 或 λ=0 时训练路径与现状逐位一致）
- `load_model` 按 --compensator 构建并挂到模型；ckpt 保存包含 compensator 参数与原型 buffer
- 实验身份：results/cpt 命名追加 `_capr`/`_bank` 后缀，避免覆盖 S5 产物

### 白名单（β）
新建 `NPJ/model/compensator.py`；修改 `NPJ/model/fusion_model.py`（仅 §β2）、`NPJ/main_survival.py`（仅 §β3）、`NPJ/loc_utils_3yr/tcga_dataset.py`（仅 train dropout 段）；notes.md/result.md 照旧。禁止项同单 α；另加：不改 eval_missing.py/gen_missing_manifest.py（如需评测支持 compensator ckpt，写明需求由指挥官另裁）。

### 测试命令（β 交付实跑）
- 合成单测：compensator 三断言 + fusion forward 回归 allclose + dropout 协议断言（p=0 时 batch 与现状一致）
- 语法内存 compile 全改动文件

## 口径裁定更新（2026-09-02，用户最终版）
- **B 口径为主口径**：M0-real/M1/M1b/M2 的主表与缺失曲线全用 cindex_B；CAP-Recall 验证基于 NPJ-B。
- A 口径=作者原版评估读数，仅作复现对照列与锚定旁证；表内不混排。
- eval_missing.py 已双列输出，无需改码；后续汇总脚本与曲线图以 B 列为主轴。
- 锚定断言基准=S5 NPJ-B 逐 seed（冒烟已同时满足双口径）。
- 训练侧协议不动（M2 与 S5 ckpt 同保存协议），报告声明。

## 单 γ · NPJ-C 干净骨架 + E1 接入（用户 2026-09-02 裁定：拆 gate，token 进 attention）

### 冻结声明
`MainModalityMoE` 类、GatedFusion、已训 M1b/M2(gate 版) ckpt 与评测结果**全部冻结不动**。本单只新增一个网络类，旧路径逐字节不变。

### γ1 `NPJ/model/fusion_model.py`：新增 `class NPJC(nn.Module)`（放在 MainModalityMoE 之后，不改旧类任何行）
- `__init__(device, modalities, hidden_size, dropout_rate=0.1, pred_dim=15, mlp_ratio=4, n_backbone=1, n_head=4, cancer_types=None, compensator=None)`（签名与 MainModalityMoE 对齐以便 load_model 同构调用；num_experts/topk/n_token 不收）
  - `m_projector`：与 :973-979 同构（每模态 Linear(feat→D)+ReLU+Dropout）
  - `modality_embed = nn.Parameter(torch.zeros(M, D))`（模态身份嵌入，零初始化，加到各 token）
  - `backbone`：`nn.TransformerEncoderLayer(d_model=D, nhead=n_head, dim_feedforward=D*mlp_ratio, dropout=dropout_rate, batch_first=True)` × n_backbone（与 :983-992 同超参，**序列长度=M 而非 1**）
  - `surv_heads`：与 :992-995 同构（per-cancer `SurvivalHead(D, pred_dim)`，输出 hazard/surv）
  - **不实例化 GatedFusion**；不读 `{mm}_mask`
- `forward(all_modalities, cancer_type='Default')`：
  1. 各模态 `x.mean(dim=1)`（若 3 维）→ projector → token `[B,D]`（同 :1008-1015 的池化+投影，去掉 `_mask` 判定）
  2. `valids[mm]` = `all_modalities.get(f"{mm}_valid", ones)` 转 bool `[B]`；img 恒视为有效
  3. 若 `self.compensator is not None`：按 β 的插入逻辑（tokens_dict/valids_dict/`{mm}_orig`/`{mm}_dropped`/bin_labels/training）调 compensator 替换缺失位；**被替换的位 valid 置 True**（召回 token 参与 attention）
  4. `seq = stack(tokens, dim=1) + modality_embed` → `[B,M,D]`；`key_padding_mask = ~valid` `[B,M]`（True=屏蔽；缺失且未补偿的 token 不进 attention）
  5. `h = backbone(seq, src_key_padding_mask=key_padding_mask)`；**masked mean pooling**（只对 valid 位平均）→ `[B,D]`
  6. per-cancer head → hazard, surv；有 compensator 时返回 `(hazard, surv, consistency)` 三元组（与 β 约定一致），否则 `(hazard, surv)`
- 单测：①无 compensator、valid 全 1 时输出有限且形状 [B,pred_dim]；②valid 含 0 时被屏蔽位不影响输出（把该位 token 换成随机值输出不变）；③compensator=CAPRecall 时缺失位被替换且参与 attention（替换前后输出不同）；④AST 断言 NPJC 类体内无 GatedFusion 引用

### γ2 `NPJ/main_survival.py`：`load_model` 增加 `network_type == 'NPJC'` 分支
- 构建 NPJC（传 compensator_module 同 capr/bank 逻辑）；compensator 校验从"仅 MainModalityMoE"放宽为 `{'MainModalityMoE','NPJC'}`
- 其余训练循环零改动（三元组 loss 接线、dropout、suffix 已通用）；cpt/result 命名天然含 `_NPJC_` 隔离

### 白名单（γ）
修改 `NPJ/model/fusion_model.py`（仅追加 NPJC 类 + 必要 import）、`NPJ/main_survival.py`（仅 load_model 分支与校验放宽）；notes.md/result.md。**禁止**：改 MainModalityMoE/GatedFusion/compensator.py/tcga_dataset.py/eval_missing.py；修 `_mask` 死代码；跑训练；SSH；git commit/push。回归红线：`network_type='MainModalityMoE'` 路径与现状逐位一致（allclose 断言）。

### 测试命令（γ 交付实跑）
合成单测四断言 + MainModalityMoE 回归 allclose + 内存 compile。

## 单 δ · 统一 Python 发车器 + 缓存共享 + 评测重构（用户 2026-09-02 批准 A+B+C+D）

### 动机（实证）
NPJ 计算图极小（V100 实测 bs 32→256 util 恒 11-15%），单进程 util 天花板不可调；等待来源=①缓存键含 network_type 导致换骨架名全量冷重建（3 s/patient，BRCA ~48 min）②unit 内 seed 串行、每卡仅 5 并发（实测 5 并发 GPU 54%）③eval_missing 每格点重建 dataset（50 次 × 13 次）。

### δ1 缓存共享（改 `NPJ/loc_utils_3yr/tcga_dataset.py`，仅缓存文件名解析）
- 读 `_save_cache`/加载逻辑，缓存文件名**去掉 network_type 后缀**（缓存内容与 network_type 无关，只与 modality/split/cancer/label 源相关——先核实内容确实与 network_type 无关，若有关则在 notes 说明并改为映射表）
- **向后兼容**：加载时优先找新名（无后缀）；找不到则依次回退 `_MainModalityMoE`/`_NPJC` 等已有后缀名（landau 上两套缓存都在）；保存一律用新名。目标：换任何新 network_type 零重建
- 单测：合成小缓存目录，断言新名/旧名回退顺序与保存名

### δ2 `NPJ/scripts/train_launcher.py`（新文件，统一发车器）
- 输入：`--plan <yaml>`（每条 run：name/arm/network_type/compensator/cancer/seed/extra_args）或生成器参数（`--arms e0,e1 --cancers BLCA,... --seeds 123,...` 自动展开，arm→参数映射表内置：e0=NPJC 无补偿；e1=NPJC+capr+dropout0.15+λ0.1；可扩展）
- 调度：`--gpus 0,1 --per_gpu 8`；子进程=`python main_survival.py <现有 CLI>`（不改 main_survival），CUDA_VISIBLE_DEVICES 按槽位分配；状态文件 `runs_state.json`（pending/running/done/failed/skipped + pid + exit + 时长）原子写；日志每 run 独立文件（绝对路径）
- **缓存预热**：启动训练前按 (cancer) 检查 δ1 缓存是否齐全（train/valid/test × 模态）；缺则先用 `--prewarm_workers K` 并行预热（每 cancer 一个进程构建一次 dataset），完成后再放训练——避免多 run 同时重建同一缓存
- 幂等：目标 ckpt 已存在则 skipped（`--force` 重跑）；`--dry_run` 只打印计划与槽位分配不启动
- 门禁整合：读 `config/gpu_train.yaml` 并打印 resolved（含 allow_low_gpu_util/reason）；不重复实现 util 采样（main_survival 已有）
- 完成即评测（可选）：`--eval_grids none,rna_100,text_100 --eval_workers 4 --eval_out <dir>`：每 run done 后调 δ3 的 eval_missing（多进程池），产物命名 `<arm>_<cancer>_s<seed>.json`
- 托管：launcher 自身设计为经 `jobrun.sh` 启动（文档写明命令模板）；launcher 收到 SIGTERM 时向全部子进程转发（组杀）
- 单测：`--dry_run` 对 2 臂×2 癌×2 seeds 输出 8 条计划且槽位分配正确；状态 JSON 往返；缓存齐全性检查函数在合成目录上的判定

### δ3 `NPJ/scripts/eval_missing.py`（重构，CLI 与 JSON 输出格式**完全不变**）
- 一次构建 test dataset（grid=None），各格点通过**内存内切换** dataset 的 `missing_mode/missing_set`（与 α2 字段一致）实现遮挡，不重建 dataset；M1 均值仍按原逻辑
- 对拍验收：对 landau 已有结果无法本地跑——用合成 dataset 断言"重构版逐格点输出 == 原版（重建方式）逐格点输出"（保留原实现为 `_legacy` 路径供对拍，默认走新路径）

### 白名单（δ）
新建 `NPJ/scripts/train_launcher.py`；修改 `NPJ/loc_utils_3yr/tcga_dataset.py`（仅缓存名解析）、`NPJ/scripts/eval_missing.py`（仅 dataset 复用重构）；notes.md/result.md。**禁止**：改 main_survival.py/fusion_model.py/compensator.py、改 MainModalityMoE/NPJC 语义、SSH/scp、启动训练、下载、git commit/push。
### 测试命令
δ1/δ2/δ3 单测各自实跑并附输出；`train_launcher.py --dry_run` 实跑；内存 compile 三文件。

## 单 ε · A/B 首单契约（定稿 2026-09-04；本节是引擎唯一执行依据，α–δ 各节与你无关）

你拿到的 `<engine>` 值由派单 prompt 指定（`opus` 或 `codex`）。本节文本对两个引擎完全相同。

### ε0 执行者声明与纪律
- **你就是本单的执行者**。`CLAUDE.md` 中"执行编码工作派给 Codex/Companion"、"Claude 不直接大改代码"等条款**对本单不适用**；禁止转派、禁止调用 codex/companion/子 agent/SSH/联网工具；本单全部代码由你本人编写。
- **不得中途向指挥官提问**。契约未覆盖的歧义按最保守默认执行，并逐条写进 `notes_eps_<engine>.md` 的「歧义与自行裁决」节（这一节是交付的重要部分）。
- 只准 Python 标准库 + matplotlib（本机 `/usr/bin/python3` 3.9.6、matplotlib 3.5.1、numpy 1.22.3、pandas 1.4.2 已装）；**禁止 pip install、禁止联网**；解释器一律写 `python3`（`python` 仅是交互 zsh 别名，非交互 shell 下不存在）。
- 工作目录（cwd）= `/Users/wuhao/Desktop/TriModalSurv/collab/20260902-A测缺失补偿/`；脚本内部路径由 `ROOT = pathlib.Path(__file__).resolve().parents[1]` 推导，`--root` 可覆盖。
- 禁止 commit / push / stash / 任何 git 写操作；禁止 `py_compile`（会在源码旁写 `.pyc`）；禁止创建 `__pycache__`（运行脚本前 `export PYTHONDONTWRITEBYTECODE=1`）。
- 所有 `open()` 显式 `encoding="utf-8"`；输出文件 UTF-8 无 BOM、`\n` 换行。

### ε1 输入（全部只读；改动任一即判本单失败）
- `results_npjc/{e0,e1}/*.json`：三格点 none/rna_100/text_100；`results_npjc_both/{e0,e1}/*.json`：仅 both_100 格点；`results_npjc_e0d/*.json`：4 格点（e0d = E0 + modality dropout 0.15、无召回，作为结论 2 的消融臂）；`results_gate/{m0real,m1,m1b,m2}/*.json`：13 格点 none、rna_25/50/75/100、text_25/50/75/100、both_25/50/75/100。目录内混有 `.log`，只读 `*.json`。
- JSON 结构：`grids` 为字典 `{grid: {cindex_A, cindex_B, n_test, grid_sha, ...}}`；顶层 `checkpoint`、`cancer`、`seed`、`arm`。**臂身份只来自命令行 `--arm NAME=dir` 的 NAME**：JSON 的 `arm` 字段不可信（E0/E1/m1b/m2 的都写 `m0real`，评测入口复用所致），文件名前缀也不作臂身份。
- 文件名规则 `<prefix>_<CANCER>_s<seed>.json`，用正则 `^(?P<arm>.+)_(?P<cancer>BLCA|BRCA|LUAD|LGG|UCEC)_s(?P<seed>\d+)\.json$` 解析，不匹配则打印 `SKIP <path>` 并跳过。
- 固定顺序：癌种 `BLCA, BRCA, LUAD, LGG, UCEC`（LUAD 在 LGG 前，不是字母序）；seed `123, 132, 213, 231, 321`。
- 起点脚本 `tools_<engine>/summarize_arms.py` 已预置（与 `tools/summarize_arms.py` 同一份），sha256 = `99f20a614be891071172ed41db0e31fcae57dd3cd45bdfbd5150cbccd2bbfc07`；第一步先 `shasum -a 256` 自校验并把结果写进 notes。`tools/summarize_arms.py` 本身只读。
- 以下文件只读且 sha256 已钉死（交付前自查一次，逐条写进 notes）：
  - `table_npjc_E0_E1.md` = `52c6f36e41e00f4759e5bc6b5a7e031427b40980e2c41b9ac8270974212ab4bc`
  - `table_gate_4arms.md` = `9c11ef9e3bcb7c6141008377bfba0f2a741770b6ce7b657d3444dadd9898f30f`
  - `table_npjc_E0_vs_S5.md` = `a6668233d04c00409c54d9ad8ebccffb5e3385cfbee3a23ab3bd3d3c1598c1c2`
  - `a_test_report.md` = `3eeaba9fb45d59e49d56e4db95aa2a1888483bf666f82726ccecb3974188b622`
  - `result.md` = `5abd55371cb3d30416e24bd50ea82c3dcb20fc0b7b25bd712746474b43b7dd16`
  - `r2_numbers.txt` = `01a50796556d915efd319386f67a6a4ec870e339024bfd6623489c6b7e89874b`
  - `s5_full_reference.csv` = `49045d39cf4ca7915861815370209857fe0bcf06dde9d3ae81288e40796b9436`
  - `missing_manifest_v1.csv` = `c789eae9a5b1517d82cfa137a92dfa8cc7ffae58e5f300163b25729ffc5d8156`
  另：`a_test_report.md`、`notes.md`、`plan.md`、`result.md`、`probe/`、`审查/`、任何 `results_*/` 一律只读。

### ε2 产物清单（唯一可写范围；其余路径一律禁写）
`tools_<engine>/summarize_arms.py`（在预置副本上增强）、`tools_<engine>/plot_missing_curves.py`（新）、`figures_<engine>/gate_missing_curves.png|.svg`、`figures_<engine>/npjc_e0_e1_4grids.png|.svg`、`table_npjc_E0_E1_4grids_<engine>.md`、`table_npjc_E0_E1_E0d_4grids_<engine>.md`、`table_both100_E1_vs_E0_<engine>.md`、`notes_eps_<engine>.md`。`figures_<engine>/` 由脚本 `os.makedirs(exist_ok=True)` 创建。

### ε3 `summarize_arms.py` 增强规格
CLI（保留现有参数语义，新增项如下）：`--arm NAME=dir[,dir2,...]`（可重复；逗号分隔多目录合并）、`--grids`（默认 `none,rna_100,text_100`）、`--base`（默认第一个臂）、`--metric`（默认 `cindex_B`，本单不得改默认）、`--out`、`--tie-eps`（默认 `1e-6`）、`--legacy-winloss`（开关）、`--pairwise-grid GRID` + `--pairwise-out FILE`。
1. **多目录合并**：逐目录加载后按 (cancer, seed) 做 **grids 级合并**（不是整体覆盖）。同一 (cancer, seed, grid) 在两个目录都出现 → stderr 打印 `CONFLICT arm=.. cancer=.. seed=.. grid=.. dir1=.. dir2=..` 并 `exit 2`；同一 (cancer, seed) 跨目录 `checkpoint` 字段不一致 → stderr 打印 `CKPT_MISMATCH ...` 并 `exit 2`。目录不存在或无可解析 json → stderr `ERROR: no result json in <dir>` 并 `exit 3`（不得 traceback、不得造数据）。
2. **胜负单元格**（非对照臂行末列）：默认写法 `f"{w}:{l}:{t} (Δ中位 {d:+.4f})"`，判据 `win: x−y > tie_eps`、`tie: |x−y| ≤ tie_eps`、`loss: y−x > tie_eps`，`d = statistics.median([x−y for 配对])`（逐 seed 差的中位，平局对计入；仅双方都非缺值的 seed 参与配对；配对数为 0 时单元格为空串）。`--legacy-winloss` 时**完全沿用旧写法** `f"{w}:{len(pairs)-w} (Δ中位 {d:+.4f})"`（`w = sum(x > y)`），用于字节重放。
3. **其余格式逐字冻结**（与现有脚本/留档完全一致）：首行 `# 臂对比（主口径 {metric}；对照臂 {base}）` + 空行；每格点 `## 格点 {grid}`、空行、表头 `| 癌种 | 臂 | s123 | s132 | s213 | s231 | s321 | 中位 | vs {base} 严格胜负 |`（末列文字**不改**）、分隔行 `|` + `---|`×9、数据行、节末空行；数值 `{v:.4f}`，缺值 `—`（U+2014）；中位只取非缺值，全缺 `—`；对照臂行末列为两个空格 `|  |`；臂序=`--arm` 顺序，格点节序=`--grids` 顺序；末行 `缺格：N`（N=0 时不带 ` → [...]`，N>0 时 ` → ` 后接前 8 个 (arm, cancer, seed) 元组的 Python repr，遍历序 arm→cancer→seed）；stdout 打印全文；`--out` 写文件时**无末尾换行**（与留档一致）。不新增 A 口径列。
4. **配对表**（`--pairwise-grid G --pairwise-out F`，与主表同一次运行生成）：首行 `# 格点 {G} 配对比较（主口径 {metric}；对照臂 {base}；5 seeds；胜:负:平，|Δ|≤{tie_eps} 记平）` + 空行；对每个非对照臂（按 `--arm` 顺序）：`## {arm} vs {base}`、空行、表头 `| 癌种 | {base} 中位 | {arm} 中位 | 胜:负:平 | 配对Δ中位 |`、分隔行 `|---|---|---|---|---|`、5 个癌种行（中位 `{:.4f}`，缺值 `—`；胜负 `W:L:T`；Δ `{:+.4f}`）、合计行 `| 合计 | — | — | {W}:{L}:{T} / {配对总数} | — |`、空行；文件无末尾换行；`tie_eps` 用 Python 默认 repr（`1e-06`）。

### ε4 `plot_missing_curves.py` 规格（新文件）
- 文件前三行必须是：`import matplotlib` / `matplotlib.use("Agg")` / `matplotlib.rcParams["svg.hashsalt"] = "trimodalsurv"`，之后才 `import matplotlib.pyplot as plt`。CLI：`--root`（默认 `parents[1]`）、`--out`（默认 `<root>/figures`）、`--metric`（默认 `cindex_B`）。可 `import` 同目录 `summarize_arms` 的加载函数或自行复制，不得 import 战役目录外代码。
- 数据：gate 四臂从 `results_gate/{m0real,m1,m1b,m2}`；NPJ-C 臂 E0 = `results_npjc/e0` + `results_npjc_both/e0`，E1 同理，E0d = `results_npjc_e0d`（若目录不存在：打印 `SKIPPED: results_npjc_e0d missing`，图 2 只画 E0/E1 且图注不提 E0d；不算失败）。
- 显示名映射（逐字）：`m0real→M0-real`、`m1→M1`、`m1b→M1b`、`m2→M2`、`e0→E0`、`e1→E1`、`e0d→E0d`。颜色 hex：M0-real `#4C72B0`、M1 `#DD8452`、M1b `#55A868`、M2 `#C44E52`；E0 `#4C72B0`、E0d `#55A868`、E1 `#C44E52`。图内文字**全部 ASCII 英文**（默认字体无 CJK 字形）；禁止出现日期、机器名、引擎名。
- **图 1** `gate_missing_curves`：`fig, axes = plt.subplots(5, 3, figsize=(13.5, 16), dpi=150, sharex=True, sharey="row")`；行=癌种（固定序），列=模式 `rna / text / both`；x = `[0, 25, 50, 75, 100]`，x=0 三列都取 `none` 格点，其余取 `<mode>_<rate>`；每臂折线 = 5 seeds 的 `statistics.median`（不是均值），`marker="o", linewidth=1.6`；阴影 `fill_between(x, min_over_seeds, max_over_seeds, alpha=0.15)` 同色；子图标题 `f"{cancer} | {mode} missing"`；首列 y 轴标签 `c-index (B)`，末行 x 轴标签 `missing rate (%)`；`fig.suptitle("Gate-version arms under test-time missingness (manifest v1, 5 cancers x 5 seeds)")`；图例一次 `fig.legend(loc="lower center", ncol=4, frameon=False)`；图注 `fig.text(0.5, 0.0, "Metric: c-index B (sigmoid-corrected, sksurv). Line = median of 5 seeds (123/132/213/231/321); band = min-max range across seeds. Grids: none = full modalities.", ha="center", va="bottom", fontsize=8)`。布局参数（tight_layout rect 等）允许微调，元素集合固定。
- **图 2** `npjc_e0_e1_4grids`：`fig, axes = plt.subplots(1, 5, figsize=(16, 4), dpi=150)`；每子图一癌，x 为 4 个分类刻度 `["none", "rna_100", "text_100", "both_100"]`（位置 0..3）；臂序 E0, E0d, E1（E0d 缺席则 E0, E1）；偏移：三臂 `-0.24, 0, +0.24`，两臂 `-0.15, +0.15`；每臂在每刻度画 5 seeds 散点（`s=18, alpha=0.75`）+ 中位横线（`hlines`，半宽 0.1，`linewidth=2`）；子图标题=癌种；首图 y 轴标签 `c-index (B)`；`fig.suptitle("NPJ-C arms across 4 missingness grids (E0 = NPJ-C; E1 = NPJ-C + CAP-Recall; E0d = E0 + modality dropout 0.15, no recall)")`；`fig.legend(loc="lower center", ncol=3, frameon=False)`；图注 `fig.text(0.5, 0.0, "Metric: c-index B (sigmoid-corrected, sksurv). Dots = 5 seeds (123/132/213/231/321); horizontal bar = median.", ha="center", va="bottom", fontsize=8)`。
- 保存：PNG `fig.savefig(path, dpi=150)`（**禁止 `bbox_inches="tight"`**，像素尺寸必须等于 figsize×dpi：图 1 2025×2400、图 2 2400×600）；SVG `fig.savefig(path, format="svg", metadata={"Date": None})`，`svg.fonttype` 保持默认。确定性定义：同机连跑两次四个文件字节一致。

### ε5 验收（交付前逐条实跑；命令与 **原样 stdout** 贴进 notes；任一 FAIL 不得宣布完成）
```bash
export PYTHONDONTWRITEBYTECODE=1
shasum -a 256 tools_<engine>/summarize_arms.py                                  # 起步自校验（改前）
python3 tools_<engine>/summarize_arms.py --arm E0=results_npjc/e0 --arm E1=results_npjc/e1 --legacy-winloss | diff - <(cat table_npjc_E0_E1.md; echo) && echo REPLAY_OK
python3 tools_<engine>/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --grids none,rna_100,text_100,both_100 --out table_npjc_E0_E1_4grids_<engine>.md --pairwise-grid both_100 --pairwise-out table_both100_E1_vs_E0_<engine>.md > /dev/null && echo TABLE4_OK
python3 tools_<engine>/summarize_arms.py --arm E0=results_npjc/e0,results_npjc_both/e0 --arm E1=results_npjc/e1,results_npjc_both/e1 --arm E0d=results_npjc_e0d --grids none,rna_100,text_100,both_100 --out table_npjc_E0_E1_E0d_4grids_<engine>.md > /dev/null && echo TABLE_E0D_OK
python3 tools_<engine>/summarize_arms.py --arm m0real=results_gate/m0real --arm m1=results_gate/m1 --arm m1b=results_gate/m1b --arm m2=results_gate/m2 --grids none,rna_100 | grep -c ":[1-9] (Δ中位"      # 期望 ≥1（gate 数据含 |Δ|≤1e-6 的配对，平局逻辑正样本）
python3 tools_<engine>/summarize_arms.py --arm E0=results_npjc/e0,results_npjc/e0 --arm E1=results_npjc/e1 > /dev/null 2>&1; echo "CONFLICT_EXIT=$?"   # 期望 2
python3 tools_<engine>/summarize_arms.py --arm E0=results_npjc/nonexistent --arm E1=results_npjc/e1 > /dev/null 2>&1; echo "MISSING_EXIT=$?"      # 期望 3
python3 tools_<engine>/plot_missing_curves.py --out figures_<engine> && A=$(shasum -a 256 figures_<engine>/*) && python3 tools_<engine>/plot_missing_curves.py --out figures_<engine> && B=$(shasum -a 256 figures_<engine>/*) && [ "$A" = "$B" ] && echo DETERMINISTIC_OK
grep -l "dc:date" figures_<engine>/*.svg; echo "DATE_LEAK_FILES_ABOVE(expect none)"
for f in figures_<engine>/*.png; do python3 -c 'import sys,struct;d=open(sys.argv[1],"rb").read();w,h=struct.unpack(">II",d[16:24]);print(sys.argv[1],w,h,len(d));assert len(d)>=50000' "$f"; done   # 2025x2400 / 2400x600
for f in figures_<engine>/*.svg; do python3 -c 'import sys,os;s=os.path.getsize(sys.argv[1]);print(sys.argv[1],s);assert s>=20000' "$f"; done
python3 -c 'import sys;[compile(open(p,"rb").read(),p,"exec") for p in sys.argv[1:]];print("COMPILE_OK")' tools_<engine>/summarize_arms.py tools_<engine>/plot_missing_curves.py
grep -c "^缺格：0$" table_npjc_E0_E1_4grids_<engine>.md table_npjc_E0_E1_E0d_4grids_<engine>.md     # 各 1
find . -name "__pycache__" -o -name "*.pyc" | wc -l                                                  # 0
```
逐格断言（自写一次性比对，可直接 `python3 -c` 内联，不落盘）：`table_npjc_E0_E1_4grids_<engine>.md` 的 `## 格点 none / rna_100 / text_100` 三节数据行按 `|` 切 9 段，前 8 段与 `table_npjc_E0_E1.md` 同行逐字相等；第 9 段：对照臂行两侧都是两个空格；非对照臂行新侧 `W:L:T (Δ中位 ±x.xxxx)` 与旧侧 `W:L (Δ中位 ±x.xxxx)` 满足 W、L、Δ 字符串相等且 T=0。打印 `SECTION <grid>: OK (10 rows)` 与 `ALL SECTIONS OK`。

### 相关坑（执行前必读；坑台账 `collab/pitfalls.md`）
| ID | 坑 | Prevention Rule | 出处 |
|---|---|---|---|
| S1 | 裸 `py_compile` 即使设 PYTHONDONTWRITEBYTECODE 仍会在源码旁写 `.pyc`，越出白名单。 | 语法检查优先内存 `compile()`；必须写缓存时设 PYTHONPYCACHEPREFIX 到白名单 scratch。 | collab/20260827-三方对比战役/notes.md |
| E1 | 计划指定 YAML 验证因缺 PyYAML 在导入阶段失败，实际断言未运行。 | 先只读检查依赖；禁止安装时保留原失败，并区分指定命令与替代内容验证。 | collab/20260826-NPJ三模态复现/result.md |
| V23 | 判定报告手算派生数字（胜负计数/Δ中位/中位差混用/平局计负/抄错基线中位）在两份报告中重复出错，均被 decision-reviewer 重算抓出。 | 进结论的数字必须来自脚本生成的留档表并可指回文件行；成文前跑对账脚本；平局规则显式声明。 | collab/20260902-A测缺失补偿/notes.md |
| V25 | 测试按 `ALL_GRIDS` 插入顺序断言 JSON keys，而生产 `_atomic_json_dump(sort_keys=True)` 按字母排序，把表示顺序当业务语义导致假失败。 | JSON mapping 验收断言键集合相等与字段值，只有格式契约明文规定顺序时才断言顺序。 | collab/20260902-A测缺失补偿/notes.md |
| S4 | 被限制只读的交叉审核 Agent 在仓库根创建白名单外文件。 | 严格白名单任务不委派会落盘的通用审核；必要时前后比较完整 Git 状态，越界即中断并恢复基线。 | collab/20260826-NPJ三模态复现/notes.md |
| C2 | 任务中途为只读核验新增联网域名，仍违反全程网络白名单。 | 联网白名单贯穿整个任务链；新增站点即使官方只读也先获授权。 | collab/20260827-三方对比战役/notes.md |
| C3 | 并发 append-only 文档用旧尾部锚点写入，会导致补丁失配。 | 写前立即刷新文档尾部，并为独立文件拆分补丁。 | collab/20260827-三方对比战役/notes.md |
| M1 | 手工估计 notes 时间戳，使过程档案时间晚于真实执行时间。 | 每次追加阶段标题前运行 `date '+%Y-%m-%d %H:%M:%S %Z'`，禁止估时。 | collab/20260827-三方对比战役/notes.md |

### `notes_eps_<engine>.md` 固定结构（每完成一小步就追加，每个标题带 `date '+%Y-%m-%d %H:%M:%S %Z'` 实取时刻）
① 环境（`python3 --version`、matplotlib 版本、起点脚本 sha256 自校验结果）；② 每条验收命令 + 原样 stdout；③ 断言结果表（逐条 OK/FAIL）；④ **歧义与自行裁决**（契约未覆盖之处你怎么定、为什么）；⑤ 耗时与迭代次数（返工几次、各因何）。完成后最后一行写 `EPS_DONE`。

### 完成定义
全部验收命令通过 + 产物清单齐全 + 只读文件 sha256 不变 + notes 五节齐全并以 `EPS_DONE` 收尾。不得改动本节以外任何路径。
