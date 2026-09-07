# 对抗审查（步骤 5，后台并行）与指挥官核实（2026-09-07 09:04:25 JST）

- 命令：companion `adversarial-review --cwd NPJ --scope working-tree --model gpt-5.6-sol --json`（thread 01a07923-1913-7291-8df5-b0480bb9de6e），审 0 staged / 3 unstaged / 16 untracked。
- Codex verdict：**needs-attention** — 不应发布：存在三个会破坏 d0 实验身份或纯消融解释的阻断问题；当前测试还会在干净环境中漏掉最关键的 gate 回归。

| # | 严重度 | 标题 | 文件:行 | Codex 置信 | 指挥官核实 |
|---|---|---|---|---|---|
| 0 | critical | [P0] YAML plan 模式会把 d0 静默变成 gate 模型 | `scripts/train_launcher.py:301-317` | 0.99 | **属实但不触发** |
| 1 | critical | [P0] d0 默认 checkpoint 与 NPJ-A 完全同址 | `scripts/train_launcher.py:410-441` | 1 | **属实但不触发** |
| 2 | critical | [P0] mean 分支改变共享网络初始化及后续随机流 | `model/fusion_model.py:997-1020` | 0.95 | **属实，判为不影响有效性** |
| 3 | medium | [P2] 最关键的 gate 回归测试在干净环境中会静默跳过 | `tests/test_mean_fusion.py:170-172` | 1 | **属实** |

## 逐条核实说明

### [0] [P0] YAML plan 模式会把 d0 静默变成 gate 模型

Codex：load_plan() 只从 ARM_PRESETS 继承 network_type 和 compensator，extra_args 却只读取 YAML 原值。实测最小 `arm: d0` plan 得到 `extra_args=()`，训练命令和评测命令均无 `--fusion_type mean`，因此两端都按默认 gate 运行；严格加载不会报错，产物却仍被标为 d0。该错误 checkpoint 之后还会被幂等逻辑继续跳过复用。

建议：缺省时继承 preset.extra_args，并强制校验 d0 必须是 MainModalityMoE、compensator=none、fusion_type=mean；增加 YAML plan 模式回归测试。

核实：仅 YAML plan 模式：`load_plan()` 不从 preset 继承 `extra_args`（同样会丢 e0d/e1 的 `--modality_dropout`）。本战役全部走 `--arms d0` CLI 路径；landau 54 个 d0 run 日志 52 个已写参数行，全部 `fusion_type='mean'`、`cpt_name='tcga_uni2_d0'`、0 个 gate。**不影响在跑实验**；战役后加固（plan 模式继承 preset.extra_args + d0 身份断言 + 回归测试）。

### [1] [P0] d0 默认 checkpoint 与 NPJ-A 完全同址

Codex：checkpoint_path() 没有把 arm 或 fusion_type 纳入身份，launcher 默认又是 `result-path=out`、`cpt-name=tcga_uni2`。实测默认 d0 mean 与同 seed/cancer 的 NPJ-A gate 都解析为 `out/123/tcga_uni2_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth`。已有 S5 文件会被仅凭 is_file() 判为 d0 已完成并静默跳过；使用 --force 则可能覆盖 S5 checkpoint。

建议：至少对 d0 强制要求独立 cpt_name/result_path 并在冲突时失败；更稳妥的是把 arm/fusion_type 纳入 checkpoint 身份，并在幂等跳过前验证 checkpoint 的结构或元数据。

核实：默认 `cpt-name/result-path` 下 d0 与 NPJ-A 同址（Opus 交付时已标残留风险）。本战役固定 `--cpt-name tcga_uni2_d0 --result-path out_d0`；冒烟与全量 ckpt 均落 `out_d0/`，`out/` 自发车后 0 个新文件。**不影响在跑实验**；战役后加固（d0 强制独立路径或把 fusion_type 纳入 ckpt 名）。

### [2] [P0] mean 分支改变共享网络初始化及后续随机流

Codex：gate 分支在 backbone/head 之前构造带参数的 GatedFusion，mean 分支不消耗对应随机数。同一 torch seed 下实测 20 个共享 state_dict 张量中有 8 个不同，包括全部随机初始化的 backbone 张量和 survival head；构造后的 RNG state 也不同。这还会改变后续 shuffle/dropout 随机流，因此配对 seed 的 d0 不再是“只删除 GatedFusion、其余相同”，性能差异被额外随机性混杂。

建议：在不改变 gate 路径的前提下，让 mean 分支消耗与 GatedFusion 初始化完全相同的 RNG，再注册 MeanFusion；测试必须断言 gate/mean 所有共享 state_dict 张量及构造后 RNG state 逐位相同。

核实：本地复现：同 seed 下 gate/mean 共享 20 张量中 8 个不同（backbone 全部随机初始化张量 + head），构造后 RNG 状态不同 → 后续 shuffle/dropout 随机流也不同。性质是**同 seed 的另一次随机抽样**，不是系统偏差；25 seed 下随机性被平均。E1（NPJC）vs D 本就是不同网络，seed 配对只能是协议配对；D vs S5 NPJ-A（辅助，5 seed 交集）同理。**不重跑**；报告口径改为「同 seed = 协议配对，非初始化配对」，预注册判定不变。

### [3] [P2] 最关键的 gate 回归测试在干净环境中会静默跳过

Codex：补丁前基线来自机器私有的 /private/tmp 路径；文件不存在时抛 SkipTest，而自带 runner 只按 failures 决定退出码。实测指定不存在的基线后输出 `RESULT=ALL_PASS SKIPPED=1` 且退出 0，因此 CI 或换机时唯一验证旧 S5 gate 逐位兼容的测试会消失而仍显示成功。

建议：把可审计的基线夹具或 golden state/output 放入仓库，并把基线缺失设为硬失败；同时加入旧 checkpoint strict-load 和 launcher 身份测试。

核实：`test_mean_fusion.py` 基线缺失时 SkipTest 且 runner 退出 0。本次本地与 landau 两处运行均提供了基线（5 passed，SKIPPED=0）。战役后加固：基线缺失改硬失败，或把 golden state_dict 摘要入仓。

## 指挥官裁决（待用户确认）

- 四条发现无一改变正在跑的 d0/e1/Dm 的有效性：[0][1] 在本战役的发车参数下不触发，[2] 是随机抽样差异而非偏差，[3] 是测试卫生。**不中断、不重跑。**
- 战役收官后做一单「发车器/测试加固」（plan 模式继承 extra_args、d0 身份断言、ckpt 身份冲突失败、基线缺失硬失败），再跑单测与 dry-run 回归。
- 报告 r6 口径：seed 配对写成「协议配对（同 seed），非初始化配对」；D vs S5 NPJ-A 为辅助比较。
