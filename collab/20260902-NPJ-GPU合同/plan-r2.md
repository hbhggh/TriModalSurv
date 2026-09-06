# NPJ GPU 合同 r2 · 派单契约（yaml 双摊 + 三对照旋钮 + profiler 钩子）

派单人 Claude，执行人 Codex。**执行前必读本文件与 `collab/pitfalls.md` 全账。** 本单叠加在 r1 已交付代码之上（配置驱动/门禁/去同步均已在），只做增量。

## 背景事实（已探明，不要重新调查）

- V100（cap 7.0，torch 2.5.0）`torch.cuda.is_bf16_supported()=False`，而 `main_survival.py:699` `Accelerator(mixed_precision='bf16')` 静默走模拟路径。
- `main_survival.py:658-659` 单卡也无条件 `nn.DataParallel(model)`，再 `accelerator.prepare`。
- epoch 循环 `:713-752`：每 epoch 全量 valid 评估 + 条件 `model_dumper.dump`；test 只在末尾 `:762`。
- optimizer `:698` `torch.optim.Adam(lr=args.lr, weight_decay=1)`——weight_decay=1 为上游原值（异常大），**本单显性化但不改值**。
- `main()`（`:622-800`）内联全部构建逻辑，独立 profile 脚本无法复用 → profiler 走可选钩子。
- 工作树同时含未审 β compensator 改动，本单 diff 必须独立可辨识；禁改 compensator 语义。

## 任务

### T1. `NPJ/config/gpu_train.yaml` 重组为双摊（保留文件头部注释与裁决理由）

```yaml
optimizer:            # 收敛超参（与 GPU 占用无关）
  lr: 1.0e-4
  epochs: 50
  weight_decay: 1     # 上游原值，未裁决不改
perf:                 # 吞吐/占用旋钮
  batch_size: 32
  gradient_accumulation_steps: 1
  num_workers: 4
  pin_memory: true
  persistent_workers: true
  prefetch_factor: 4
  non_blocking: true
  mixed_precision: bf16     # bf16 | fp16 | no（新）
  data_parallel: auto       # auto=仅多卡才包 | on | off（新）
  eval_every: 1             # 每 N epoch 做一次 valid，末 epoch 必评（新）
  concurrent_runs: 1
  gpu_util_warmup_sec: 120
  gpu_util_min_percent: 50
  gpu_util_target_percent: 80
  allow_low_gpu_util: true
  low_gpu_util_reason: "<保留现有字符串>"
```

**向后兼容**：`resolve_gpu_config` 同时接受旧平铺键（顶层直接出现 perf 键视为 perf 摊），`gpu_util_gate.py --policy-json` 同样兼容。

### T2. `NPJ/main_survival.py`

1. `resolve_gpu_config` 读嵌套；`--lr`/`--epochs` CLI default 改 **None**，优先级 CLI > yaml > 内置默认（lr 1e-4、epochs 50、weight_decay 1），resolved 打印每键来源（坑 V3）。旧调用显式 `--lr 1e-4 --epochs 50` 行为不变。
2. `Accelerator(mixed_precision=perf.mixed_precision)`；`'no'` 传 `"no"`。
3. DataParallel：`data_parallel=auto` 且 `device_count()>1` 才包；`on` 强制包；`off` 不包。注意 `_unwrap_model` 与 checkpoint 保存路径对无 DP 情况的兼容（state_dict 键无 `module.` 前缀——保存/加载须两种都能处理，若现有 `_unwrap_model` 已覆盖则说明即可）。
4. `eval_every`：epoch 循环中仅当 `(epoch+1) % eval_every == 0` 或末 epoch 时跑 valid 与 best-ckpt 判定；训练 loss 记录不受影响。默认 1 行为逐位等价。
5. `--profile_epochs N`（默认 0 零开销）：N>0 时用 `torch.profiler.profile(activities=[CPU, CUDA(若可用)], record_shapes=False)` 包住前 N 个 epoch 的 `finetune_epoch` 调用；结束后写 `<result_path>/profile_<cpt_name>_<seed>.txt`（`key_averages().table(sort_by="cuda_time_total", row_limit=20)`，CPU-only 时 sort_by cpu_time_total）与 `.json`（cpu_time_total_ms、cuda_time_total_ms、profiled_epochs、profiled_steps、avg_step_ms、top20 列表）。profile 完成后训练继续正常跑完。
6. **默认组合（bf16/auto/eval_every=1/CLI 显式 lr、epochs）下 loss 序列与 r1 版本逐位相同**——硬验收（复用现有 HEAD 对拍夹具，注意 CPU 环境 auto=不包 DP，需与 r1 的"单卡包 DP"在 CPU 上对拍等价——CPU 上 DP 是 no-op 语义，允许以此说明）。

### T3. 测试适配 `collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py`

- 全部适配双摊结构（Claude 已先修 2 项漂移：yaml defaults 断言不为 1 + 豁免有原因；gate 四态训练命令 `sleep 3`）。
- 新增：嵌套/平铺两种 yaml 均可解析；`mixed_precision` 三值透传到 Accelerator（mock）；`data_parallel` 三值在 `device_count()` 为 1/2 下的包裹判定；`eval_every=5` 下 50 epoch 恰评估 10 次且末 epoch 必评；`--profile_epochs 1` CPU 上产出 txt+json 且字段齐全；lr/epochs 优先级三态。
- 亲跑全套并把原始输出写入 result.md；`PYTHONDONTWRITEBYTECODE=1`（坑 S1）。

## 白名单

`NPJ/config/gpu_train.yaml`、`NPJ/main_survival.py`、`NPJ/scripts/gpu_util_gate.py`（仅 policy-json 兼容双摊）、`collab/20260902-NPJ-GPU合同/scratch/test_gpu_contract.py`、本目录 `notes.md`（append）与 `result.md`（新增 r2 节）。

## 禁止

改 compensator/CAP-Recall/bank 语义；碰 `baselines/`、seeds、loss 数学、模型结构、`tmp_sur_cache/`、结果目录；改 weight_decay 的值；git commit/push；ssh/scp；启动 GPU 训练；安装包。

## 相关坑（台账精选）

| ID | 坑 | 本单对应 |
|---|---|---|
| V3 | CLI 硬默认静默覆盖 yaml | T2.1 lr/epochs default None + 来源打印 |
| V19 | 门禁不感知进程生命周期 | 已修；T3 gate 用例训练命令须长于 gate 启动 |
| V15 | 断言须匹配表示语义 | eval_every 用例断言评估次数而非日志措辞 |
| E8/E9/E10 | 测试进程边界依赖替代 | 沿用 r1 的 sitecustomize shim，替身带 `__spec__` |
| S1 | py_compile/导入写 pyc 越白名单 | `PYTHONDONTWRITEBYTECODE=1` |
