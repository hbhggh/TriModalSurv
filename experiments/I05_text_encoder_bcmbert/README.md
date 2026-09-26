# I05：Text encoder 换成 BioClinical ModernBERT 嵌入版（消融实验二）

**问题**：只把 Text 特征提取器换成冻结的 `NeuML/bioclinical-modernbert-base-embeddings`（revision `048ad4491de0fb4e2695bfe4705da67caf4804b8`），NPJ-C、原型检索方法（S0-force）与训练配方全部不变，在历史 `none`（保留天然缺失）下，五癌五 seed 平均 B 口径 C-index 能否相对论文 Table 1 `None / Proto.†` 严格胜出至少 4/5。

**当前阶段**：**第二轮 A0 进行中（2026-09-24）**。轮 C（bcmbert200，前 200 token）已按 negative 收官（none 严格胜 2/5），账本见 [experiments/BioClinical ModernBERT/results/index.md](../BioClinical%20ModernBERT/results/index.md)；第二轮新增档案 `bcmbert8192`（全文 ≤8192 token）与对照臂 `legacytext-rerun`，见下文「第二轮 A0」。

**分工（用户裁决 2026-09-23）**：代码开发由 Claude Code（Claude Opus 5.5）执行；Codex 只审核生成的计划书与实验结果，不参与任何代码生成。

**用户锁定（2026-09-23）**：

- 实验种子必须是 123、132、213、231、321；评测器与渲染脚本遇到其他种子直接拒绝。
- 实验必须在 GPU 上运行，禁止 CPU。在 landau、tako、hitode、tetra 四台云端服务器中先找空闲卡；没有空闲卡时，可以用利用率低于 70% 的在用卡。两类卡都要求显存余量不低于 8192 MiB。

- 原始需求、先验知识与研究计划书：[4.BioClinical ModernBERT-程序性知识/](../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/4.BioClinical%20ModernBERT-程序性知识/)
- [model.py](model.py)：查找 `# [创新 I05-01]`，即冻结编码器填槽的实现。
- [config.yaml](config.yaml)：锁定的模型 ID 与 revision、冻结 combo、S0-force 路由表、上游源码 sha256 锁、历史证据哈希。
- [知识索引](knowledge/index.md) · [机制说明](knowledge/method.md) · [结果账本](../BioClinical%20ModernBERT/results/index.md)

## 文件

| 文件 | 作用 |
|---|---|
| `model.py` | 方案 C（用户裁决 2026-09-24）：分词到 200 token（截断或右侧补齐，保留 [CLS]/[SEP]）→ `last_hidden_state` → 有效 token 均值（pad 不参与）→ 广播写入全部 200 行 → FP32 `[200, 768]` |
| `extract_text_features.py` | `audit` 只读核验；`extract` 只为旧 Text 特征已有的患者生成 `{pid}.pkl` 与 `manifest.json` |
| `model_config.yml` | 默认 model 配置的逐字副本，只改 `modality.text.path` |
| `train_plan.yaml` / `train_plan_smoke.yaml` | 25 行正式清单（seed 主序）/ 1 行冒烟清单 |
| `evaluate.py` | 冻结方法推理器：assets / preflight / smoke / replay / test |
| `tools/render_encoder_tables.py` | 两份四场景结果表、4×5 表与 none 下的 Q 判定 |
| `tools/check_launch_contract.py` | 与既有 e0 臂的 dry-run 逐参对比（坑 D16） |
| `gpu_policy.py` | GPU 规则：禁止 CPU；本机复核所选卡号（空闲卡优先，其次利用率 < 70%）并设置 `CUDA_VISIBLE_DEVICES` |
| `tools/gpu_survey.py` | 在 Mac 本机经 SSH 别名只读查询四台服务器，按规则推荐主机与卡号（坑 E31） |

## 上机步骤（每道门需用户授权；命令在服务器运行根执行，路径用占位符）

服务器绝对路径不写进仓库（仓库公开）。

**运行根布局（Codex 候选审查 finding 4）**：`<运行根>` 指同步到服务器的 run worktree。它按 AGENTS.md「Git 工作流」第 8 条只读，本实验的任何可变资产都不得落在里面：

| 运行根内的路径 | 形态 | 指向 |
|---|---|---|
| `data/` | 真实目录（不是整体软链） | 目录内逐项软链到服务器上的只读数据（标签 CSV、missing manifest、`text_embeddings_parsed/` 等） |
| `data/text_embeddings_bcmbert200` | 软链 | `<可变资产根>/text_embeddings_bcmbert200/`（Phase 1 提取器写这里） |
| `tmp_sur_cache` | 软链 | `<可变资产根>/tmp_sur_cache/`（全新空目录；播种 img/rna、预热 text 都写这里；不是仓库原有的 `tmp_sur_cache/`） |

`<可变资产根>`、`<输出根>` 和各结果根都在运行根之外，因为 run worktree 收尾时会删除。训练子进程的工作目录固定为运行根，缓存键又不含特征路径（坑 D2），所以隔离只能靠“运行根下的 `tmp_sur_cache` 指向全新目录”，不能靠 `--cache-dir`。`evaluate.py` 检测到运行根是冻结工作树（有 `GIT_STAMP.json` 或 `.git`）时，要求 `tmp_sur_cache` 与新特征目录解析后都在工作树之外，否则拒跑，结果只记布尔值、不记绝对路径。特征内容由 assets 阶段绑定：新特征 `manifest.json` 的逐人哈希必须等于特征文件，15 个 text 缓存逐条等于特征文件。

**选卡**（每个用 GPU 的阶段之前都要做；在 Mac 本机运行，只读）：

```bash
python3 experiments/I05_text_encoder_bcmbert/tools/gpu_survey.py
```

输出里的 `recommended` 就是按规则选出的主机与卡号。没有空闲卡也没有利用率低于 70% 的卡时退出码为 3，此时不上机。进入主机后，评测器与提取器会用 `--gpu-id` 再复核一次；同一台机器上有空闲卡时，它们拒绝占用共享卡。

**Phase 0 只读核验**（exp 分支已提交版本即可，不产生实验工件）：

```bash
python3 experiments/I05_text_encoder_bcmbert/extract_text_features.py audit --labels data/TCGA_9523_ex12.csv --reference-dir data/text_embeddings_parsed --with-tokenizer --cache-dir <历史缓存目录> --legacy-preflight experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/2.progress/result/evidence/legacy-preflight.json --legacy-valid-source experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/2.progress/result/evidence/valid-source.json --out <审计输出目录>/phase0-audit.json
```

`decision_hints` 出现任何一条都停下，由用户裁决（原文不可得、旧槽位不是 token 级、旧 pad 位不为零）。

**Git 门与节点一复审**（Phase 1 之前）：candidate → squash 进 `main` → `freeze <run_id>`（tag `run/<run_id>`、run worktree、`GIT_STAMP.json`）→ 按上表建好运行根布局 → 执行方机械核对**冻结后的 commit** 的 provenance（main HEAD、run worktree HEAD 与干净状态、GIT_STAMP 与 tag 一致、测试与 `--dry_run` 原始输出），原始输出交用户 → 用户授权上机。审查只审一次（用户裁决 2026-09-23），不再请 Codex 复审。

**Phase 1 提特征与缓存**（从冻结的 run worktree 运行，经 jobrun.sh 托管）：

1. `extract_text_features.py extract --labels data/TCGA_9523_ex12.csv --reference-dir data/text_embeddings_parsed --out-dir <可变资产根>/text_embeddings_bcmbert200 --device cuda --gpu-id <GPU>`（运行根里的 `data/text_embeddings_bcmbert200` 软链指向同一目录）
2. 把 30 个历史 img/rna 缓存复制进 `<可变资产根>/tmp_sur_cache/`，按 legacy-preflight 与 valid-source 的哈希核对。
3. 逐癌预热 text 缓存：`scripts/train_launcher.py --_prewarm-cancer <癌种> --model-config experiments/I05_text_encoder_bcmbert/model_config.yml --label data/TCGA_9523_ex12.csv`
4. `evaluate.py --profile bcmbert200 --stage assets --run-root . --execution-root <输出根>`：除 `assets.json` 外，还只写一次 `<输出根>/runs/assets/assets-lock.json`（训练前资产锁，含锁定时间、冻结 commit、新特征 manifest 哈希与 15 个 text 缓存的内容摘要）。**这一步必须在任何训练（含冒烟）之前完成**；之后建议 `chmod -R a-w <可变资产根>/text_embeddings_bcmbert200`（训练不写特征；缓存会被训练重写，不能设只读）。

**Phase 2 冒烟**（冒烟通过即停）：

1. `scripts/train_launcher.py --plan experiments/I05_text_encoder_bcmbert/train_plan_smoke.yaml --model-config experiments/I05_text_encoder_bcmbert/model_config.yml --result-path <冒烟结果根>/out --state-file <冒烟结果根>/runs_state.json --logs-dir <冒烟结果根>/launcher_logs --gpus <选出的卡号> --per_gpu 1`
2. `evaluate.py --profile bcmbert200 --stage smoke --run-root . --checkpoint-root <冒烟结果根>/out --execution-root <输出根>/smoke --cancers BLCA --seeds 123 --assets-lock <输出根>/runs/assets/assets-lock.json --gpu-id <GPU>`
3. `evaluate.py --profile legacy-replay --stage replay --replay-tier same-host --run-root <历史资产运行根> --checkpoint-root <历史 ckpt 根> --execution-root <输出根>/replay --gpu-id <GPU>`

历史资产运行根要把 train/valid/test 三个 split 的历史缓存放进同一个 `tmp_sur_cache/`（可用软链）。回放须 `IDENTICAL`；跨硬件时只接受 `PASS_WITH_FLOAT_DIFFS`（donor、mask、路由完全一致，logits 差 ≤ 1e-6）。

**Phase 3 正式训练**（用户授权后；`--gpus` 只填按规则选出的卡；总槽位 ≤ 5；结果根在运行根之外）：

```bash
python3 scripts/train_launcher.py --plan experiments/I05_text_encoder_bcmbert/train_plan.yaml --model-config experiments/I05_text_encoder_bcmbert/model_config.yml --result-path <正式结果根>/out --state-file <正式结果根>/runs_state.json --logs-dir <正式结果根>/launcher_logs --gpus <选出的卡号，逗号分隔> --per_gpu 2
```

**Phase 4 冻结方法推理**：先 `--stage preflight`，再 `--stage test --gpu-id <GPU>`，两步都带 `--assets-lock <输出根>/runs/assets/assets-lock.json`。

训练数据身份（Codex 候选复核 r3 finding 1）：训练端 run record 不扫描特征内容，所以用训练前资产锁闭合。从 preflight 起，新训练 ckpt 的档案必须提供资产锁，并且：锁的 commit、协议、档案与本轮相同；锁的 `locked_at_utc` 早于每个 run record 的 `recorded_at_utc`；当前资产逐癌等于锁（text 缓存按内容摘要比，因为训练会重写缓存，坑 D15）。残余风险：训练期间替换、训练后又恢复原内容，前后两次核对发现不了。

期望 commit 只取当前源码身份（有 `.git` 读 HEAD，否则读 `GIT_STAMP.json`），并要求 `dirty=false`、未放行 dirty；`--expected-commit` 与运行根的 `GIT_STAMP.json` 只作核对，任一不等即拒跑，没有例外分支。替身历史证据参数（`--legacy-preflight` / `--legacy-valid-source`）不打开任何旁路：commit 门照常，CPU 照样禁止（只有测试代码经 monkeypatch 注入才放行），输出状态一律带 `_SYNTHETIC` 后缀。

preflight 对每个新 ckpt 核对训练身份（Codex 候选审查 finding 2）：由 ckpt 哈希找到唯一的完成运行记录，要求 `git.json` 的 commit 等于上述 commit 且 `dirty=false`，并且 `resolved_config.yaml` 的 `runtime` 逐键等于 `config.yaml` 的 `training_contract.runtime`（再加本格的 `seed` 与 `cancer_types`）。`inputs` 里的 model_config、gpu_config 必须与仓库文件逐字节相同，标签哈希必须等于历史标签。训练入口会把模态路径 resolve 成绝对路径再写 `data_manifest.json`（软链已解析），所以 Text 路径必须等于本运行根下 `data/text_embeddings_bcmbert200` 的解析结果；评测输出只记逻辑路径与布尔结论。这要求 preflight 与训练使用同一运行根布局。

test 需要三份记录，都是 JSON：

- `--replay-record`：Phase 2 的 `replay-comparison.json`，状态通过且 `source_hashes_sha256` 与当前相同。
- `--review-record`：由 Codex 输出或用户本人写，Claude 不代写。

  ```json
  {"reviewer": "Codex", "decision": "PASS", "protocol_id": "<bcmbert200 协议 ID>", "source_hashes_sha256": "<preflight 打印的值>", "commit": "<冻结的 main commit>"}
  ```

- `--user-approval-record`：由用户本人写（Codex 候选审查 finding 3），任一字段不符都拒绝；旧式纯文本不再有效。

  ```json
  {"authority": "user", "decision": "APPROVE_FORMAL_TEST", "stage": "test", "protocol_id": "<bcmbert200 协议 ID>", "source_hashes_sha256": "<preflight 打印的值>", "commit": "<冻结的 main commit>", "review_record_sha256": "<上面审查记录文件的 sha256>", "approved_at": "<ISO 8601 时间>"}
  ```

- `--review-rebind-record`（第二轮起，Codex 首审 finding 1）：审查发生在候选 H、正式运行在 squash 后的 S 时，审查记录的 `commit` 写 H，另用 `tools/rebind_review.py build --review-record <审查记录> --commit <S> --out <换绑记录>` 在有 `.git` 的机器上生成换绑记录（git 重算 tree(H) == tree(S) 且 S 在 main 上才写出；`verify` 子命令可复核）。此时用户授权记录还要加一个键 `"rebind_record_sha256": "<换绑记录的 sha256>"`；审查记录直接绑定 S 时不给换绑记录，授权也不写这个键。
- 用户授权记录还要写 `"checkpoints_sha256"` 与 `"assets_lock_sha256"`，取 preflight 打印的值（I06 节点一 finding 1）：授权只对这一套 ckpt 有效，换一套 ckpt 必须重新授权；没有资产锁的档案写 `null`。另写 `"runtime_sha256"`（round2 R1）：取**不带** `--retrieval-backend` / `--batch-size` / `--cpu-threads` 的 preflight 打印值；正式 test 不接受这三个覆盖参数。

**Phase 5 渲染**：`tools/render_encoder_tables.py --new <输出根>/runs/test/complete.json --out-dir "experiments/BioClinical ModernBERT/results/<run_id>/"`；按用户裁决同时渲染到 `manuscript/消融实验/2.innovation-secode-part- Encoder/4.BioClinical ModernBERT-程序性知识/`。

## 第二轮 A0：bcmbert8192 与 legacytext-rerun（用户裁决 2026-09-24）

**改了什么**：同一权重、同一 revision，分词不再截断到 200，而是全文（≤8192 token，2506 份报告最长 6822）逐份单样本前向、不补齐，对全部有效 token 求均值后广播回 200 行 → `[200,768]`。槽位、NPJ-C、原型检索方法、训练配方全部不变。对照臂 `legacytext-rerun` 用原有 Text 特征在现行代码上按同一配方重训 25 个，用来拆分重训方差。

**三臂的比较口径**：Q 只看 bcmbert8192 vs Table 1 None/Proto.†；bcmbert8192 vs 轮 C bcmbert200（只差上下文长度）与 vs legacytext-rerun（只差 Text 管线）是同代码对照，只作信息性报告。

**顺序（AGENTS.md「Git 工作流」第 4–8 条）**：dev 上 `scripts/gitflow.sh candidate` → Codex 审查（`scripts/codex_review.sh`）→ **从候选 H 的干净快照上机冒烟**（`git archive H` + `GIT_STAMP.json` commit=H）→ 冒烟通过后在主目录 `squash` → `freeze` → 正式实验从 run worktree 部署，资产锁在 S 上重写。

**运行根布局**（两份，均按上文「运行根布局」只读；可变资产在运行根外）：

| 运行根 | `data/` 里额外的软链 | `tmp_sur_cache` |
|---|---|---|
| bcmbert8192 | `text_embeddings_bcmbert8192` → `<可变资产根>/text_embeddings_bcmbert8192/` | 全新目录：复制 30 个历史 img/rna 缓存，text 由预热从 8192 特征生成。**不得**复用 bcmbert200 的 text 缓存（缓存键不含特征路径，坑 D2；assets 会逐条拒绝） |
| legacytext-rerun | 无（用 `text_embeddings_parsed`） | 历史 45 个缓存（img/rna/text 三模态 × 三 split） |

**命令**（占位符同上文；每个 GPU 阶段前先 `tools/gpu_survey.py` 选卡）：

1. 审计（只读，统计 NeuML 分词长度）：`extract_text_features.py audit --profile bcmbert8192 --with-tokenizer --labels data/TCGA_9523_ex12.csv --reference-dir data/text_embeddings_parsed --out <审计输出>/a0-audit.json`
2. 提取（B=1 由档案锁定，不要传 `--batch-size`）：`extract_text_features.py extract --profile bcmbert8192 --labels data/TCGA_9523_ex12.csv --reference-dir data/text_embeddings_parsed --out-dir <可变资产根>/text_embeddings_bcmbert8192 --device cuda --gpu-id <GPU>`；完成后把特征目录设为只读。
3. 预热 text 缓存：`scripts/train_launcher.py --_prewarm-cancer <癌种> --model-config experiments/I05_text_encoder_bcmbert/model_config_bcmbert8192.yml --label data/TCGA_9523_ex12.csv`
4. 资产锁：`evaluate.py --profile bcmbert8192 --stage assets --run-root <8192 运行根> --execution-root <输出根>/exec`；legacytext 同理（`--profile legacytext-rerun`，运行根换成 legacytext 的）。schema 2 的特征 manifest 在这里还要过三道生成身份门（Codex 首审 finding 2/3）：提取器源码闭包与当前代码逐字节相同且 `dirty=false`；`model_files` 等于 config 固定的 8 个模型文件 sha256（提取器在编码前也核对）；标签哈希等于冻结标签，患者集合恰为「标签 ∩ `text_embeddings_parsed`」，逐人癌种 / split 等于冻结标签，text 缓存每个 split 的患者由「有 WSI、有旧特征、标签 split 相符」独立推出后逐人比对，并且其集合摘要必须等于 config `legacy.text_keys_sha256` 固定的历史 text 缓存患者集合（复审 round2；无条件执行，不依赖任何参数）。
5. 冒烟：`train_launcher.py --plan experiments/I05_text_encoder_bcmbert/train_plan_smoke_bcmbert8192.yaml --model-config experiments/I05_text_encoder_bcmbert/model_config_bcmbert8192.yml --result-path <冒烟结果根>/out --state-file … --logs-dir … --gpus <卡> --per_gpu 1` → `evaluate.py --profile bcmbert8192 --stage smoke … --cancers BLCA --seeds 123 --assets-lock <输出根>/exec/runs/assets/assets-lock.json`；回放 `evaluate.py --profile legacy-replay --stage replay --replay-tier same-host …`（源码摘要变了，必须重跑）。
6. 正式训练（freeze 之后）：`train_plan_bcmbert8192.yaml` + `model_config_bcmbert8192.yml`；`train_plan_legacytext.yaml` + 默认 `configs/models/surv_multimodal_mainmoe_uni2.yml`。两者各用独立的 `--result-path` / `--state-file`（三档 ckpt 文件名相同）。
7. 评测：两档各自 `preflight` → `test`（test 门记录按协议 ID 各一份；审查记录绑定 H 时附 `--review-rebind-record`）。
8. 渲染：`tools/render_encoder_tables.py --profile bcmbert8192 --new <8192 complete.json> --reference bcmbert200=<轮 C complete.json> --reference legacytext-rerun=<legacytext complete.json> --out-dir <账本 run 目录>`，并同样渲染到 `manuscript/消融实验/2.innovation-secode-part- Encoder/5.如何修补BioClinical-ModernBERT.md/`。

## 本地验证

```bash
PYTHONDONTWRITEBYTECODE=1 <protomasksurv-exp1 环境的 python> -m pytest -q -p no:cacheprovider experiments/I05_text_encoder_bcmbert/tests
```
