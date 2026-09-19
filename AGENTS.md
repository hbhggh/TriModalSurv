# TriModalSurv 公共纪律（唯一源头）

Claude Code 与 Codex/Codex Companion 都必须遵守本文件。冲突时以本文件为准。

## 执行前必读（坑台账）

开始任何实现、复现、评测、派单或修 bug 之前，必须先完整阅读：

`collab/pitfalls.md`

这是本仓库唯一的坑台账。读完再动手。禁止凭记忆声称已经知道这些约束。
新发现的失效模式收单时追加到同一文件：一行一条，含 ID、一句话坑、一句话 Prevention Rule、出处。
不要另起清单，不要把同一 Post-Mortem 重复入账。

最小执行口径：以本小节 + `collab/pitfalls.md` 为准。不再要求每次手工挑 3–5 条写入 plan.md。

## 角色

- Claude Code 是唯一指挥官：定策略、监视任务、控制停机门、验收、部署下一步。
- Codex / Codex Companion 是执行者：只允许改代码、打补丁、做 adversarial review。
- Codex 不得自行决定开始正式训练、重下数据、重启任务。
- 任何一方执行完，必须由另一方 review。禁止同一方执行完直接宣布通过。

## 停机门

- 冒烟通过后必须停。
- 未获得用户明确允许，禁止开始 BLCA / BRCA / LUAD / LGG / UCEC 正式实验。
- 禁止启动 5-seed 全量与任何会占满 GPU 的长任务。
- MCAT / NPJ 骨架 / PORPOISE 都走同一条门。

## 正式实验 GPU 合同（2026-09-02 起对新实验生效）

旧「GPU 训练速度决策」三条中：第 1 条（batch 严格为 1、严禁 padding、gc=32 模拟大 batch）**作废**；第 2 条（I/O 合同）保留并升级为默认实现；第 3 条（同卡 2-3 run）降为后备手段。新合同：

1. 默认目标：单卡利用率优先。正式跑之前必须把 batch_size 调到该模型在这块卡上能稳定跑的最大值（探测 OOM 前一档）。
2. 只有加大 batch 会让 forward / collate / mask / loss 直接跑不通或静默算错时，才允许 batch_size=1，并在启动日志写明 `BATCH_SIZE_BLOCKED_REASON`。禁止把「和某论文对齐」当成阻断原因。
3. 可变长 WSI 的默认做法是 custom collate + attention padding mask（或等长 bucket），不是退回 batch=1；padding 必须带 mask，pad 位不得进入有效 attention 与风险分数。
4. DataLoader 正式配置必须具备：num_workers、pin_memory、persistent_workers、prefetch_factor；张量传输 `to(device, non_blocking=True)`。step 热循环内禁止 `.item()` / `.cpu()` / 打印张量；标量日志只在 epoch 边界或固定 log 间隔同步。
5. 单进程接近显存上限后 util 仍低，再查 I/O 与同步；仍空再考虑同卡并行第二个独立 run。禁止用多进程或梯度累积掩盖 batch_size=1（gradient_accumulation 仅为优化器选项，默认 1）。
6. 正式发车必须走门禁（NPJ 侧 `NPJ/scripts/launch_formal.sh`）：warmup 采样 GPU-Util，低于门禁不得写入正式结果；故意小 batch / 单跑必须显式 `allow_low_gpu_util` 并写原因。
7. 评断三档不混用——门禁：warmup 120s util 中位数 ≥50%，否则正式实验失败；目标：单进程 ≥80% 且显存吃到接近安全上限；方向：能稳定更高就更高。达不到 100% 不是退回小 batch 的理由，停在 10-20% 才是失败。**NPJ 现架构成文豁免**（用户裁决 2026-09-02）：实测 bs 32→256 活跃 util 恒 11-15%、峰值 ≤31%，50% 对该计算图物理不可达——其正式 yaml 以 `allow_low_gpu_util+reason` 走豁免通道（数据：`collab/20260902-NPJ-GPU合同/notes.md`）；模型显著加大后豁免失效须重测。
8. 范围：自本日起的新实验（NPJ 骨架的后续对比 / 消融 / 创新臂）。已收官的 S5 三方对比配置为历史事实不追溯；若未来重启 MIL 变长 bag 类训练，batched+mask 路径已存在（两库 `--batched_collate`，任务 G），启用后同样受本合同约束，util 门禁按该架构实测基线另定。

## 执行纪律

- 通道超时先查进程；禁止把通道断当成任务死亡；禁止二次派单。
- Codex 执行派单前必读 plan.md「相关坑」节并遵守其中 Prevention Rule；产出的新教训按 Post-Mortem 格式写入 notes.md。
- 监视器默认只报警，不自动重启。
- 新下载 / 训练 / 转换必须经 landau 的 `jobrun.sh` 启动。
- **正式训练一律经 `NPJ/scripts/train_launcher.py` 发车**（用户裁决 2026-09-02；仍由 `jobrun.sh` 托管）：清单驱动（臂×癌×seed）、缓存预热、每卡并发上限、幂等跳过、完成即评测；禁止手写 bash lane 串行 seed 发正式训练。默认 label=`data/TCGA_9523_ex12.csv`；dataset 缓存键已去 network_type，换骨架名不再触发冷重建。
- 不改 `tmp_sur_cache/`，不覆盖已有结果目录。
- 不把"窗口还在"当成"任务还在"。

## 互审

- Claude 派给 Codex 的任务，Codex 执行完后必须回到 Claude 做检查。
- Codex 的 patch / review 结论，必须由 Claude 再看一遍才能进入下一 Gate。
- adversarial review 通过，不等于可以开正式实验；还要等用户点头。

每次执行任务前，必须完整阅读并遵守 [TPBHQ-认知分析引擎](TPBHQ-认知分析引擎.md) 中的约束。

## [T/B/P/A/Q] 热路径协议（编译后的 A，本文件内必须执行）

完整陈述性定义见 `TPBHQ-认知分析引擎.md`。本节省略原理，不省略动作。不得以“将去阅读 sidecar”代替本节的执行；本节省力出现在本文件正文里，才视为已挂载。

### 开局动作

涉及方案提议、架构修改、重构路径、算法变体选择或写代码之前，必须按序执行：

1. 先输出约束清单，格式固定为：
   `[ T + Q_{draft} (目标状态, 指标名称) + ∩P_i ∥ S_state ]`
2. 再做策略筛选：由 $T$ 唤起候选策略 ${k\_1, k\_2, k\_3, k\_4}$ → 执行 $P\_i \times S\_{state}$，刷掉当前状态不支持的候选 → 应用 `Q 约束 + 适用域` 得到 Boundary，只输出一个胜出策略。
3. 锁定 $P\_{specific} + Q\_{specific}$ 后才允许执行 $A$。$A$ 结束后严格用 $Q$ 验收；未达预期或需求变更时，必须声明 $Q\_{new} = \text{新一轮目标}$ 并重启循环。

### 防漂移（强制）

1. 思维锚点前缀：上述回复的第一句话必须是状态确认，例如 `[系统状态：S_state 已就绪 | 当前阶段：执行 A / 验证 Q]`。未经核验不得写“已就绪”。
2. 拒绝无边界编码：缺少前提 $P$ 或验收标准 $Q$ 时，禁止直接写代码，必须反问补齐约束清单。
3. 强制唤醒词：用户说出 `Code Red: Recalibrate` 时，立刻停止发散，重新读取 `TPBHQ-认知分析引擎.md` 与本节，并只回复：`引擎已重新挂载，等待第 1 组约束清单`。
