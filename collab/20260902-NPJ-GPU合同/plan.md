# NPJ GPU 合同落地 · 派单契约

派单人 Claude，执行人 Codex。目标：按 `AGENTS.md`「正式实验 GPU 合同」把 NPJ 训练链路改成配置驱动、I/O 达标、带发车门禁。**执行前必读本文件与 `collab/pitfalls.md`。**

## 背景事实（已探明，不要重新调查）

- NPJ 三模态定长（img [128,1536] / text [200,768] / rna [2048,256]），default_collate 天生吃 [B,...]，**无需任何 collate/mask 工作**。
- `main_survival.py:357-359` DataLoader 硬编码 `num_workers=0`（`--num_workers` 参数被忽略，生产日志因此撒谎）、无 pin_memory/persistent_workers/prefetch。
- 热循环同步点：`main_survival.py:211-214`（loss.item / hazard.cpu / labels.cpu 每 step）；`to(device)` 无 non_blocking（`:168-170`、`:177`）。
- `fusion_model.py:1060-1063` surv_heads 逐样本 Python 循环（单癌种 unit 可合并为单次调用）。
- 无梯度累积（每 step 即 update，语义 accum=1）。
- Dataset 构造时全量预载内存 `dict_data`，workers fork 有 RAM 复制风险（COW 缓解，真实 RSS 由 Claude 在 landau 实测，不是本单职责）。
- 工作树含未合入的 β compensator 改动（同文件共存）——**本单 diff 必须与之独立可辨识，禁止改动 compensator 相关逻辑语义**。

## 任务

### T1. 新建 `NPJ/config/gpu_train.yaml`

```yaml
batch_size: null          # null = 启动时探测 OOM 前一档并写入 run 日志；禁止默认为 1
gradient_accumulation_steps: 1
num_workers: 4
pin_memory: true
persistent_workers: true
prefetch_factor: 4
non_blocking: true
concurrent_runs: 1        # 默认 1；仅单进程显存已满仍低 util 时才 >1（本期不实现多 run，仅保留键）
gpu_util_warmup_sec: 120
gpu_util_min_percent: 50  # 门禁
gpu_util_target_percent: 80
allow_low_gpu_util: false
low_gpu_util_reason: ""
```

### T2. 改 `NPJ/main_survival.py`（配置驱动 + I/O + 去同步 + 合同校验 + batch 探测）

1. 新增 `--gpu_config`（默认 `config/gpu_train.yaml`）。解析优先级（防坑 V3）：CLI 显式传参 > yaml > 探测。`--batch_size` default 从 32 改为 **None**（区分"未给"）；未给且 yaml 有数值→用 yaml；两者皆空（yaml 为 null）→ CUDA 可用时现场探测，CUDA 不可用时**明确报错退出**（禁止假装探测成功）。启动时打印一行 resolved 配置（batch_size 来源标注 cli/yaml/probe）。
2. batch 探测：用真实 train dataset 头部样本，从 32 倍增（32/64/128/256）各做 2-3 个 step 前向+反向，try/except CUDA OOM，取 OOM 前一档；每档后 `empty_cache()`；打印 `BATCH_PROBE_RESULT=<n> PEAK_MEM=<MiB>`。探测失败（连 32 都 OOM）打印报错与 shape 后退出，不静默回退 1。
3. 合同校验：环境变量 `FORMAL_RUN=1` 时，若 resolved batch_size==1 且环境变量 `BATCH_SIZE_BLOCKED_REASON` 为空 → 打印合同违规说明并 `sys.exit(3)`。非正式运行（无 FORMAL_RUN）不拦截。
4. DataLoader（三处）：`num_workers`/`pin_memory` 按 resolved 配置；`persistent_workers` 与 `prefetch_factor` **仅在 workers>0 时传入**（PyTorch 约束，workers=0 时传 prefetch_factor 会 ValueError）。
5. `to(device, non_blocking=cfg)` 应用到 `:168-170` 与 `:177`。
6. 热循环去同步（train 与 eval 循环同样处理）：loss 累加为 GPU 标量张量、hazard/labels 收集为 GPU 张量 list（detach），epoch 末一次性 `.cpu()`；删除 per-step `.item()/.cpu()`；不加 tqdm postfix。
7. `gradient_accumulation_steps` 最小实现：==1 时代码路径与现行为**逐位等价**（这是硬验收）；>1 时标准语义（loss/accum、按窗 step、末窗必 step）。
8. 兼容性硬约束：显式 `--batch_size 32` 的旧调用（如 a_unit.sh、s4 脚本）行为与现在完全一致（不探测、不改数值）；`--help` 正常。

### T3. 改 `NPJ/model/fusion_model.py`（仅 surv_heads 快速路径）

全 batch 同一 cancer_type 时单次 head 调用替代逐样本循环，混合 batch 回退原循环。输出与原实现 allclose(atol=1e-6)。**不碰本文件其他任何逻辑（含 compensator）。**

### T4. 新建 `NPJ/scripts/launch_formal.sh` + `NPJ/scripts/gpu_util_gate.py`

- `launch_formal.sh <gpu_id> <log绝对路径> -- <python main_survival.py 完整命令>`：
  - log 必须绝对路径否则 exit 64（修 keeper 盲区）；
  - `export FORMAL_RUN=1`；`setsid` 起训练（记 pgid），stdout/err 进 log；
  - 调 `gpu_util_gate.py --gpu <id> --warmup <sec> --interval 5 --min <pct>`（参数从 gpu_train.yaml 读，python 内读 yaml）采样 warmup 窗口；
  - 门禁不过且未豁免 → `kill -TERM -<pgid>`、exit 2；豁免（yaml allow_low_gpu_util=true 且 reason 非空）→ 放行但把豁免与原因打进 log；reason 为空仍拒绝；
  - 采样结果（util 中位数、显存峰值、样本数）无论成败追加进 log；
  - 门禁通过后 `wait` 训练进程并透传退出码。
- `gpu_util_gate.py`：循环采 `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits -i <gpu>`，输出一行 JSON `{"util_median":..,"mem_peak_mib":..,"samples":..,"pass":..}`，按 pass 定退出码。nvidia-smi 不存在时明确报错（exit 3），不假装通过。

### T5. 验收（Codex 亲跑，CPU 环境，全部命令与原始输出写入 result.md）

1. **数值不变性**：合成小数据/ToyModel，同 seed 3 epoch：HEAD 版原函数 vs 改造后（accum=1）loss 序列逐位一致（`==`，非 allclose）。
2. surv_heads 快速路径 allclose 单测（单癌种 + 混合癌种两档）。
3. 门禁三态单测：PATH 前置 mock nvidia-smi（可控输出）→ 低 util 拒绝 / 达标放行 / 豁免+原因放行 / 豁免无原因拒绝，四态退出码断言。
4. `bash -n scripts/launch_formal.sh`；`python main_survival.py --help` 正常；显式 `--batch_size 2 --epochs 1` CPU 合成冒烟可跑通（探测逻辑在 CPU 上正确报「无 GPU」）。
5. 语法检查用内存 compile 或 PYTHONPYCACHEPREFIX 指向 scratch（坑 S1）。

## 白名单

`NPJ/main_survival.py`、`NPJ/model/fusion_model.py`（仅 T3 范围）、新建 `NPJ/config/gpu_train.yaml`、`NPJ/scripts/launch_formal.sh`、`NPJ/scripts/gpu_util_gate.py`、本目录 `notes.md`（append）与 `result.md`、`collab/20260902-NPJ-GPU合同/scratch/` 下测试文件。

## 禁止

- 改 compensator/CAP-Recall/bank 相关逻辑语义（同文件共存的 β diff 不许回滚、不许重构）。
- 碰 `baselines/`、`adapters/`、seeds、lr、loss 数学、模型结构、`tmp_sur_cache/`、已有结果目录。
- git commit / push；ssh / scp；启动任何 GPU 训练或长任务；下载数据。

## 相关坑（台账精选，执行前必读全账）

| ID | 坑 | 本单对应 |
|---|---|---|
| V3 | CLI 硬默认静默覆盖 yaml | T2.1 的解析优先级与 resolved 打印就是为此设计 |
| V18 | 验证断言查错自动后缀目录 | T5 断言先打印实际输出路径 |
| V15 | 断言须匹配表示语义 | 门禁单测断言退出码而非 stdout 措辞 |
| C4 | 超长命令须保留 session 返回对象 | 验收命令逐条短跑，不打包超长 |
| S1 | py_compile 写 pyc 越白名单 | T5.5 |
