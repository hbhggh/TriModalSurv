# NPJ GPU 合同战役 · 过程档案（append-only）

## Phase A 红旗核查结果（Claude，2026-09-02 上午，只读 ssh landau）

背景：巡检发现今早 10:32 landau 上 10 个 `am_bank_*`/`am_capr_*` 正式训练未经停机门确认发车，m2_smoke fail.flag 在先（10:04），≤28 分钟全部 done，疑似空转。用户裁决先查。

核查结论：

1. **am_* 10 unit 为真实完整训练**。`a_lane.sh`（claim 锁）→ `a_unit.sh`（逐 seed 循环 123/132/213/231/321，`--epochs 50 --batch_size 32 --compensator bank|capr --modality_dropout 0.15 --consistency_lambda 0.1`，two-fails-stop）。逐 log 验证：每 job 恰 5 次 Training Arguments（5 seeds），每 seed 保存 checkpoint 与 `_results.json`（如 bank/BLCA seed321 c-index 0.62），末行 `A_UNIT_<comp>_<cancer>_DONE`。`jobs/amiss_units/` 10 个 `.done` 全在，am_eval log 报 `failed=0`。耗时合理性：BLCA train=136 人、bs=32 → 每 epoch 5 batch，50 epochs 秒级/epoch，双卡并行 28 分钟跑完 10 unit 不异常。
2. **m2_smoke 为假失败**：训练成功（log 末 `M2_TRAIN_EXIT=0`、c-index 0.63、`out_capr/123/..._results.json` 已存），死因是 `m2_smoke.sh` 末行验证 `ls out/123/ | grep capr`——`--compensator capr` 触发 `_append_compensator_suffix()` 把 result_path 自动改为 `out_capr/`，grep 落空 → 脚本 exit 1 → jobrun 记 fail.flag。
3. **landau NPJ 工作树含未经互审的 β 改动**（`main_survival.py`、`loc_utils_3yr/tcga_dataset.py`、`model/fusion_model.py` 等 M 状态）——正式批用未复审代码上机，互审纪律违规成立；结果表面正常，建议保留结果+补事后审查，去留待用户裁决。
4. am_eval（四臂评测 m0real/m1/m2/m1b → `/home/wuhao/amiss_eval_full`）仍在 running。GPU 现况：两卡 util 0%，卡0 2204MiB、卡1 8232MiB 驻留。
5. 顺带实锤：am_* 日志 Namespace 显示 `num_workers=4`，但 `main_survival.py:357-359` DataLoader 硬编码 `num_workers=0`——CLI 参数被忽略、日志与实际不符（本战役 Phase C 修复项）。

### Bug Post-Mortem（m2_smoke 假失败）
- **现象**: m2_smoke 训练 exit 0 且结果落盘，但 job 被记 fail.flag exit_code=1，监控连续 3 轮无法判因。
- **根因**: 冒烟脚本验证行 `ls out/123/ | grep capr` 未考虑 `--compensator` 自动追加 `_capr` 输出目录后缀；且 job log 用相对路径注册，keeper 的 `os.path.exists` 判空导致 log_tail 恒空、无法远程判因。
- **修复**: 本次人工 ssh 判因；后续冒烟脚本断言实际输出目录（先打印再断言），jobrun 发车一律用 log 绝对路径。
- **Prevention Rule**: 验证断言的产物路径必须与代码实际输出路径推导一致（含自动后缀逻辑）；jobrun 发车 log 必须绝对路径。

## Phase C 派单留档（Claude，2026-09-02）

- jobId: `task-mtjhbnc1-5e5760`
- 完整派单命令：

```
node /Users/wuhao/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs task --write --background --cwd /Users/wuhao/Desktop/TriModalSurv --model gpt-5.6-sol --effort high "读取并严格执行 collab/20260902-NPJ-GPU合同/plan.md 派单契约：NPJ 训练链路 GPU 合同落地（配置驱动 gpu_train.yaml + main_survival.py I/O接线与热循环去同步与batch探测与合同校验 + surv_heads快速路径 + launch_formal.sh/gpu_util_gate.py 发车门禁）。执行前必读 plan.md 的「相关坑」节与 collab/pitfalls.md 全账。白名单以 plan.md 为准；禁止碰 compensator 逻辑语义与 baselines/、禁止 git commit/push、禁止 ssh、禁止启动 GPU 训练。T5 验收命令亲跑并把原始输出写入 result.md。完成后写 collab/20260902-NPJ-GPU合同/result.md。"
```

- 档位依据（CLAUDE.md 派单矩阵）：复杂实现 / 多文件联动 → `gpt-5.6-sol` + `--effort high`；写任务首启 `--write`；预计 >10 分钟 → `--background`。

## Claude 互审记录（2026-09-02 午后）

- 独立复核通过：12/12 测试亲跑复现（60s，含 HEAD vs 新实现 loss 逐位一致）；mtime 佐证白名单（tcga_dataset.py 09:44 β 时代未被本单触碰，main_survival.py 11:39 / gpu_train.yaml 11:37 本单产物）；launch_formal.sh 全文与 probe 实现抽查合格。
- **互审发现真实场景缺口**：小数据训练（BLCA 5 seeds ≈ 2.8 分钟、单 seed 秒级）会在 gate 的 120 秒 warmup 窗口内正常结束，采样中位数被训练结束后的空闲拉为 0 → 正常成功被误判杀车 exit 2。已打回补丁（jobId `task-mtjipq0o-6gqcas`，`--resume-last` 续接原线程）：gate 加 `--watch-pid` 感知训练存活，早退时按训练真实退出码判定（0=FORMAL_GATE_EARLY_COMPLETE 放行）。
- 部署留档：landau 备份 `/home/wuhao/NPJ/backup_20260902_gpucontract/`（main_survival.py、fusion_model.py 旧版）；scp 覆盖/新增 5 文件；探测经 `jobrun.sh probe_gpu_contract`（pid 2891615，卡0，am_eval 占卡1 不受影响）发车，脚本 `probe_gpu.sh`（legacy_bs32 对照 / new_bs32 / bs64 / bs128 / probe_auto 五档，各 50 epochs BLCA seed123，产物 `/home/wuhao/probe_gpu_out/`）。

## Phase D 探测结果（Claude，landau V100 卡0，2026-09-02）

| 档位 | wall | util中位(活跃段) | util峰值 | 显存峰值 |
|---|---|---|---|---|
| legacy I/O + bs32（workers0/无pin/无non_blocking） | 56s | 11% | 15% | 2962MiB |
| 新 I/O + bs32 | 64s | 14% | 31% | 2962MiB |
| 新 I/O + bs64 | 77s | 15% | 28% | 3090MiB |
| 新 I/O + bs128 | 94s | 13% | 26% | 3220MiB |
| probe 自动档（`BATCH_PROBE_RESULT=256 PEAK_MEM=1729.8MiB`） | 99s | 14% | 25% | 3554MiB |

采样：2s 间隔 nvidia-smi，n=28~48/档；全程 exit 0；`RESOLVED_GPU_CONFIG` 打印含 `batch_size_source=probe` 验证配置链生效。

**判读**：
1. probe 功能正常；BLCA train=136 全量一批可容纳，bs=256 显存峰仅 3.5GB，V100 上 OOM 不可达。
2. **util 与 batch 解耦**：bs 32→256 活跃段中位数恒 11-15%、峰值 ≤31%。NPJ 计算图本身太小（img 128 token mean-pool、序列长 1 的 backbone、hidden 256、百级样本），物理上填不满 V100——**50% util 门禁在 NPJ 现架构上不可达**，此为实测事实而非 I/O/batch 缺陷。
3. 抬 batch 无墙钟收益（56→99s 反增）：优化器更新次数骤减（250→50 次）而 epoch 边界开销不变；且 bs 改变优化语义需重调 lr。多 workers 对内存预载 dataset 是净开销（fork+IPC > 直接索引）。
4. NPJ 吞吐真实杠杆 = 同卡并发多 unit（am_* 双卡 10 unit 28 分钟已示范）与 epoch 边界开销，不是单进程 batch。

## Phase D 收尾：补丁互审 + 门禁真机全链演练（Claude，2026-09-02）

- 补丁互审通过：亲跑 14 项回归（EARLY_SUCCESS_CODE=0 / EARLY_FAILURE_CODE=7 复现）；watch-pid 逐轮存活检查与 launcher exit-4 → wait → 按训练真实退出码判定的实现抽查合格。已入台账 V19。
- 补丁 re-scp landau 后真机演练（`jobrun.sh gate_demo`，经 `gate_demo.sh` 走 `launch_formal.sh` 全链）：`FORMAL_LAUNCH_PID/PGID` 记录 → `RESOLVED_GPU_CONFIG`（batch_size_source=cli）→ 训练 ~60s 正常完成早退 → gate exit 4 → `FORMAL_GATE_EARLY_COMPLETE` → launcher exit 0 → jobrun `done.flag`。放行路径全链验证通过；拒绝/豁免/采样失败三态已由 CPU 单测覆盖。

## 2026-09-02 11:34:21 JST｜Codex 执行预检

- 已完整读取本目录 `plan.md`（含“相关坑”）和 `collab/pitfalls.md` 全账；本单重点执行 V3、V15、V18、C4、S1，并保留 E8/E10 的测试进程边界依赖替代策略。
- 顶层仓库与嵌套 `NPJ` 均为 `main` 普通工作树。派单要求在当前含 β compensator 未合入改动的工作树中形成独立可辨识 diff；另建 worktree 会缺失这些未合入依赖，因此本单在当前工作树原位实施，不执行 commit/push。
- 已核对 β 基线：`NPJ/main_survival.py`、`NPJ/model/fusion_model.py` 已含 compensator/CAP-Recall/bank 改动；本单只追加 GPU 合同、热循环、batch probe 与 surv_heads 快速路径，不回滚、不重构补偿语义。
- 本机系统 Python 无 torch/PyYAML；`protomasksurv-exp1` 环境有 torch/PyYAML/numpy/pandas/sklearn，但缺 sksurv/transformers/accelerate/torchmetrics/easydict。T5 将在测试进程边界对无关顶层依赖做最小替代，不修改生产依赖，也不安装包。
- 实施顺序采用 TDD：先在白名单 `scratch/` 写真实行为测试并取得业务 RED，再做最小生产实现；完成前逐条亲跑 T5，并保留每条命令、退出码和原始输出。

## 2026-09-02 11:44:11 JST｜RED → GREEN 与接口复核

- 有效 RED：10 项测试中，混合癌种旧回退 1 项通过；其余因 `gpu_train.yaml`/门禁脚本缺失、GPU 配置与正式合同 API 缺失、热循环尚不接受 accum/non_blocking、单癌种 surv head 仍逐样本调用而失败。失败原因均命中业务缺口。
- 最小实现后首轮 10/10 通过；随后按派单逐字复核，把 launcher 收紧为先由 Python 读取 YAML，再以显式 `--warmup`/`--min` 调 `gpu_util_gate.py`，并补 accum 末窗与相对 log exit 64 测试，现为 12/12 通过。
- 静态热循环搜索只在两个 epoch 末汇总区发现 `.cpu()`；未发现 per-step `.item()`。三处正式 DataLoader 均统一使用 `build_dataloader_kwargs()`，workers=0 时不传 persistent/prefetch。
- `fusion_model.py` 本单仅改 surv_heads 分派：同癌种 batch 单次 head，混合 batch 保留原逐样本循环；compensator/CAP-Recall/bank 区域未改语义。

### Bug Post-Mortem
- **现象**: 首次 RED 夹具在构造 `torch.optim.SGD` 时被 Torch Dynamo 的插件发现中断，报 `ValueError: tqdm.__spec__ is None`，未抵达 accum 业务断言。
- **根因**: 测试进程注入的最小 `tqdm` 模块替身缺少合法 `ModuleSpec`；Torch 内部 `find_spec()` 扫描已加载模块时拒绝无 spec 替身。
- **修复**: 所有测试进程模块替身统一设置 `importlib.machinery.ModuleSpec(name, loader=None)`，复跑后抵达并观察到预期业务 RED。
- **Prevention Rule**: 会触发 Torch optimizer/Dynamo 的隔离测试中，`sys.modules` 替身必须带合法 `__spec__`；夹具错误未清除前不得计作业务 RED。（与台账 E9 同类，不重复入账）

## 2026-09-02 11:58:36 JST｜最终验收与白名单修正

- 最终完整回归 12/12、exit 0。HEAD/新路径三轮 loss 序列逐位相同；单癌种 head 最大差 `2.9802322387695312e-08` 且只调用 1 次；混合癌种最大差 0 且保持逐样本调用；门禁四态退出码为 `2/0/0/2`。
- `bash -n`、真实 `main_survival.py --help`（测试进程依赖替代）、内存 compile、`git diff --check` 均 exit 0。CPU + YAML `batch_size: null` 的真实入口以明确 `RuntimeError: batch_size is unset and CUDA is unavailable; GPU batch probing cannot run` 拒绝，exit 1 属预期合同结果。
- 嵌套 NPJ 是普通 `main` 工作树（`GIT_DIR == GIT_COMMON`）。依派单禁止项不做 commit/push/merge；工作树原位保留，交回 Claude 互审。

### Bug Post-Mortem
- **现象**: 首次真实 CLI help 验收后，白名单审计发现新增 `NPJ/__pycache__/main_survival.cpython-310.pyc`。
- **根因**: help 命令导入生产模块时未设置禁写缓存；虽非 `py_compile`，仍在源码旁生成了白名单外 `.pyc`。
- **修复**: 将该单一缓存可恢复地移动到 `/private/tmp/trimodalsurv-main_survival.cpython-310.pyc-20260902-1148`；用 `PYTHONDONTWRITEBYTECODE=1` 重新跑 help，复审确认源码旁缓存不存在。
- **Prevention Rule**: 严格白名单任务中，任何会导入生产模块的 Python 验收也必须设 `PYTHONDONTWRITEBYTECODE=1` 或将 `PYTHONPYCACHEPREFIX` 指向白名单 scratch；不能只防 `py_compile`。（S1 的扩展场景，不重复入账）

## 2026-09-02 12:19:20 JST｜互审打回：短任务提前完成

- 根因复核：现有 gate 只按 warmup deadline 停止，launcher 只处理 0/2/3；训练 PID 未进入状态流。短任务退出后的空闲采样会继续进入中位数，确实可把正常训练误判为 exit 2。
- TDD RED：新增“训练提前 exit 0”和“训练提前 exit 7”两个端到端用例；旧实现两者均返回 2，日志只含低 util 拒绝。
- 最小修复：`gpu_util_gate.py` 新增 `--watch-pid`，每轮采样前以 `os.kill(pid, 0)` 检查；PID 消失时输出含 `early_exit:true` 的 JSON 并 exit 4。`launch_formal.sh` 传训练 PID；收到 4 后 `wait`，训练 exit 0 记录 `FORMAL_GATE_EARLY_COMPLETE`，非零记录 `FORMAL_TRAINING_FAILED EXIT_CODE=<n>` 并透传。
- 测试夹具最初用 0.2 秒 warmup，mock `nvidia-smi` 进程启动开销可耗尽整个窗口，未形成第二轮 PID 检查；改为 1 秒窗口后稳定命中目标状态。该调整只影响测试夹具，不改变生产 120 秒合同。
- 最终完整回归 14/14、exit 0。新增结果：提前成功 exit 0；提前失败透传 exit 7；两者 gate JSON 均为 `{"util_median":null,"mem_peak_mib":null,"samples":0,"pass":false,"early_exit":true}`。`bash -n`、内存 compile、`git diff --check` 和白名单 mtime 审计均 exit 0。

### Bug Post-Mortem
- **现象**: BLCA 等短训练可在 120 秒 warmup 内正常结束，gate 仍采满窗口，使后续 0% util 拉低中位数并把成功任务记为 exit 2。
- **根因**: 采样器生命周期只绑定固定 wall-clock deadline，没有绑定被监视训练进程；launcher 也没有“训练先结束”的独立状态和退出码通道。
- **修复**: gate 增加 `--watch-pid` 与 early-exit exit 4；launcher 对 exit 4 执行 `wait` 并以训练真实退出码裁决。
- **Prevention Rule**: 监控/门禁必须同时观察指标窗口与被监视任务生命周期；任务先结束时停止采样，并保留任务自身退出码，禁止用后续空闲指标覆盖任务结果。

## r2 阶段（2026-09-02 下午，Claude）

### 背景与讨论结论
- 用户粘贴「成熟团队榨 GPU」框架并要求继续讨论。结论：框架的「util 低+显存低→数据管道」在 NPJ 被 Phase D 实测推翻；NPJ 属于模型相对硬件过小（百万级参数、序列长 1）、每 step 被 launch/Python 开销主导。
- 本轮新查出三个真实可疑点：①V100 实测 `torch.cuda.is_bf16_supported()=False`（cap 7.0，torch 2.5.0），`Accelerator(mixed_precision='bf16')` 静默走模拟路径、日志零警告；②`main_survival.py:658-659` 单卡也无条件 DataParallel；③50 epoch 每 epoch 全量 valid。
- 顺带观察：`main_survival.py:698` `weight_decay=1` 为上游原值（异常大），未裁决不改，仅在 yaml 双摊中显性化。
- 遗留：β 事后审查单 `task-mtjjmrtp-z0n25q` 随上个 Claude Code 进程退出被杀（companion job 记录清空、报告目录空）；留痕显示 accum/head 对拍通过，另发现 2 项测试期望漂移（Claude 改 yaml 裁决值后引入）。
- 用户裁决：①profile + 三组对照短跑；②补 yaml 双摊、不新建 train.py；③重新派审查单 + Claude 修测试漂移。

### Phase 0（Claude 几行级小修，已亲跑 exit 0）
- `scratch/test_gpu_contract.py`：yaml defaults 断言改为 batch_size 为 null 或 >1 且豁免须有原因；gate 四态用例默认训练命令 `sleep 1`→`sleep 3`（原值短于慢机器上 gate 启动开销，会误入早退放行分支——时序脆弱）。四态码 2/0/0/2、早退 0/7 全部复现。

### Phase 1 派单留档
- jobId: `task-mtjmkwnv-ciessx`
- 完整派单命令：

```
node /Users/wuhao/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs task --write --background --cwd /Users/wuhao/Desktop/TriModalSurv --model gpt-5.6-sol --effort high "读取并严格执行 collab/20260902-NPJ-GPU合同/plan-r2.md 派单契约（r2 增量单，叠加在 r1 已交付代码之上）：gpu_train.yaml 重组为 optimizer/perf 双摊并向后兼容平铺键；main_survival.py 的 lr/epochs 走 CLI>yaml>默认优先级、mixed_precision 三值接 Accelerator、data_parallel 三值控制 DP 包裹、eval_every 评估降频、--profile_epochs N 可选 torch.profiler 钩子（默认 0 零开销）；默认组合下 loss 与 r1 逐位等价为硬验收；测试全部适配并新增契约列出的用例。执行前必读 plan-r2.md 的「相关坑」节与 collab/pitfalls.md 全账。白名单以 plan-r2.md 为准；禁止碰 compensator 语义与 baselines/、禁止改 weight_decay 值、禁止 git commit/push、禁止 ssh、禁止启动 GPU 训练。验收命令亲跑并把原始输出写入 result.md 新增 r2 节。"
```

- 档位依据：复杂实现 / 多文件联动 → `gpt-5.6-sol` + `--effort high`；`--write`；`--background`。

## 2026-09-02 13:59:25 JST｜Codex r2 执行预检

- 已完整读取 `plan-r2.md`（含“相关坑”）与 `collab/pitfalls.md` 全账；本轮重点执行 V3、V15、E8/E9/E10、S1，并保持 V19 已有门禁行为。
- 已确认 r2 是叠加于 r1 的增量实现；根工作树中 `notes.md` 与 `scratch/test_gpu_contract.py` 已含 Claude 前置改动，其他无关脏文件均不触碰、不回滚。
- 实施采用 TDD：先补齐双摊解析、三值 mixed precision、三值 DataParallel、评估降频、CPU profiler 产物及 lr/epochs 三态优先级测试并取得有效业务 RED，再修改生产代码。
- 硬边界：仅修改 `plan-r2.md` 白名单；`weight_decay` 保持 `1`；不改 compensator/CAP-Recall/bank 语义，不碰 `baselines/`，不 SSH、不启动 GPU 训练、不 commit/push。

### 用户裁决：审查通道切换（2026-09-02）
- 用户指示：β 事后审查直接用 codex 插件原生 adversarial review（companion `adversarial-review` 子命令），不用自造 task prompt 审查单，也不用手敲 `/codex:adversarial-review`。
- 只读核实子命令：`adversarial-review [--wait|--background] [--base <ref>] [--scope auto|working-tree|branch] [--model <m>] [--cwd <dir>] [focus]`；prompt 模板 `prompts/adversarial-review.md`（攻击面 + finding bar + 结构化 JSON 合同：needs-attention/approve + findings{file,line_start,line_end,confidence,recommendation}）；`--scope working-tree` 审 uncommittedChanges；**前台命令**（handleReviewCommand 直接 runForegroundCommand，`--background` 无 worker 分支）；valueOptions 无 `effort`（传了会静默拼进 focus，坑 C8）；`--model` 原样透传。
- 决定：Phase 1 收单后，`setsid nohup … adversarial-review --cwd NPJ --scope working-tree --model gpt-5.6-sol --json "<focus>" > collab/20260902-A测缺失补偿/审查/adversarial-review-raw.json &`，Monitor 等文件终态；审 NPJ 全部未提交改动（β + r1/r2 GPU 合同），focus 权重压在 compensator 语义与 am_* 结果可信度。
- 已固化：CLAUDE.md 派单矩阵「对抗审查」行改为原生子命令用法 + 用法坑补充；台账入账 C11。
