# 执行记录

## 2026-08-27 00:42:01 JST — 计划读取与执行边界

- 已完整读取 `plan.md`，本轮仅执行任务 A 与任务 B。
- 已确认文件白名单；`baselines/MCAT`、`baselines/PORPOISE`、`collab/20260826-NPJ三模态复现/convert_uni2h_to_npj.py` 与 `labels_424.csv` 仅作只读参考。
- 当前 Git 分支为 `main`。用户已明确指定当前本地工作区并要求执行，故不创建 worktree；严格禁止 commit/push。
- 发现任务外既有状态：`.gitignore` 已修改，`collab/20260826-NPJ三模态复现/dual_metric_eval.py` 未跟踪。两者均不触碰、不回退。

### 计划一致性扫描

| 任务/接口 | 生产者 → 消费者 | 结论 |
|---|---|---|
| A0 → A1 | A0 确认 split 是否参与模型选择，A1 据此映射 train/val | 一致；必须先完成 A0 再固化映射。 |
| A0 → A2/A3 | A0 确认 slide_id、`pt_files` 路径和 `--path_input_dim`，A2/A3 据此输出与构造命令 | 一致；A2 自测不依赖真实 UNI2-h 归档。 |
| A1 → A3 | A1 输出 `splits_0.csv`，A3 命令消费指定 split 目录 | 一致。 |
| A/B → `labels_424.csv` | A1 使用 BLCA/LGG 等标签，B 使用 BRCA/LUAD/LGG/UCEC 标签 | 只读共享，无写冲突。 |
| A 自身 | 两个脚本及两条本地冒烟命令 | 与白名单和禁止事项一致。 |
| B 自身 | `--dry-run` 查询 + `--limit 5` 下载并校验 md5 | 与“GDC 实测 ≤5 个文件”一致；绝不扩大实测上限。 |

### 执行裁定

- Ruling：Superpowers 默认 worktree、内部台账与 commit 流程和本任务白名单/禁止事项冲突，改用本文件作为唯一进度台账、使用 `scratch/` 内自测材料，且不提交。代价：审查范围用当前文件内容与实际命令证据界定，而不是 commit range。
- Ruling：`plan.md` 总纲注明 v3 已获批准，用户本轮又明确要求严格执行，因此视为设计和计划均已确认，不重复暂停索要批准。

## 2026-08-27 00:53:44 JST — 任务 A 实现者交付与初步证据

- 任务 A 采用测试先行：先在 `scratch/task_a_behavior_test.py` 对缺失入口得到预期 RED，再实现 `make_splits.py` 与 `uni2h_to_ptfiles.py`；现有 `protomasksurv-exp1` Python 环境下 5 项行为测试 GREEN。
- 计划指定的默认 `python3` 可运行 `make_splits.py`，BLCA 统计为 train 136/136、valid 68/68、test 138/138，最终输出 train=204（train+valid）、val=138（test），三个 split 均无缺失。
- 默认 `python3` 是缺少 `h5py/torch` 的 Python 3.13，故 `python3 adapters/uni2h_to_ptfiles.py --selftest` 退出 2；未安装依赖。按计划的降级规则，另用已有训练环境运行同一自检并得到真实 PASS。
- A0 已确认：两库均在每个 epoch 消费 val，且可用 val loss 做 early stopping；故 A1 采用 `train=our train+valid`、`val=our test`。
- A0 已确认：两库从 CSV `slide_id` 构造 `<data_dir>/pt_files/<slide_id 去 .svs>.pt`，多切片沿 patch 维拼接；UNI2-h 转换必须只去 `.h5` 并保留点号后的 UUID。
- A0 已确认：MCAT WSI 输入固定 1024 且无 `--path_input_dim`；PORPOISE 的 `porpoise_mmf` 支持 `--path_input_dim 1536`。当前禁止改 baseline，不能把 MCAT+UNI2-h 1536 描述成可直接训练。
- 发现 A3 报告待审查事实：`args.dataset_path` 由两库 `get_custom_exp_code()` 动态写入；命令行传 `--dataset_path` 反而不被 parser 接受。已派独立 reviewer 核对 A0/A3 及代码实现，不直接采信实现者报告。

## 2026-08-27 00:57:59 JST — 任务 A 独立审查与修复轮次 1

- 独立 reviewer 判定 A 尚未过门。必须修复的代码问题：tar 成员在 `shutil.copyfileobj()` 复制阶段异常时，临时文件的删除 `finally` 尚未覆盖该阶段，违反“逐成员解压用完即删”。
- 同轮补强：非法 slide 名应在写 `.pt` 前完成 patient 校验；同一输入内重复 slide_id 不应在 `--overwrite` 下静默覆盖；回归测试需直接断言点号后 UUID 完整保留，并覆盖异常后的临时目录为空。
- 测试可用性问题：`scratch/task_a_behavior_test.py` 顶层导入 `h5py/torch`，导致默认 Python 连 A1 测试也无法单独发现；要求改为 A2 测试内延迟导入。
- A3 事实纠正：PORPOISE 的 `args.dataset_path` 由 `get_custom_exp_code()` 注入，CLI 不接受 `--dataset_path`；MCAT 另有固定 1024、未定义 `args.inst_loss/args.testing`、所有模式无条件读取 `fast_cluster_ids.pkl` 三项真实阻断。
- A0 表述纠正：val 确实每 epoch 被消费，开启 early stopping 时可按 val loss 停止；但默认 `early_stopping=False`，`Monitor_CIndex` 未实际调用，最终 checkpoint 是最后 epoch，不是“按最佳 val c-index 选模”。A1 映射仍按计划依据保持 `train=train+valid, val=test`，但必须明示 our test 被 baseline 当作验证/报告集。
- 已将上述代码问题退回原任务 A 实现者，进入 fix round 1/5；A3 与 `result.md` 的最终事实由主流程负责，不要求实现者越界写文件。

## 2026-08-27 01:01:18 JST — 任务 A 修复轮次 1 通过与范围错误复盘

- 修复轮次 1 完成：tar 临时文件清理覆盖复制/读取/保存异常；非法 slide 在写出前失败；重复 slide 即使 `--overwrite` 也拒绝；UUID 输出名有直接回归断言；A1 测试可由默认 Python 单独运行。
- 训练环境完整行为测试为 8 项 GREEN，UNI2-h 自检 PASS；默认 `python3` 单独运行 A1 的 3 项测试 GREEN。
- 原 reviewer 范围化复审结论：5/5 指定项全部 ADDRESSED，未发现新增 Critical/Important；任务 A 代码审查门通过。

### Bug Post-Mortem
- **现象**: 主流程运行 `python3 -m py_compile` 后，在文件白名单未授权的 `adapters/__pycache__/` 生成了两个 `.pyc` 缓存文件。
- **根因**: 语法检查未设置 `PYTHONPYCACHEPREFIX`，忽略了 `py_compile` 会在被检查脚本旁写缓存这一副作用。
- **修复**: 精确列出两个本轮生成的 `.pyc`，使用 `find <精确目录> -maxdepth 1 -type f -delete` 后 `rmdir`；`test ! -e <精确目录>` 返回 0。第一次尝试的 `rm -rf <精确目录>` 被安全策略拒绝，未造成删除。
- **Prevention Rule**: 本任务后续所有 Python 语法/导入检查必须把 `PYTHONPYCACHEPREFIX` 指向白名单内 `scratch/pycache/`，或采用不会在源码目录写缓存的检查方式；运行前先判断命令是否会产生隐式文件。

## 2026-08-27 01:14:32 JST — 任务 B 首次实现、网络核对与审查

- 任务 B 先完成本地 fake HTTP server TDD：缺失脚本 RED，初版 3 项 CLI 集成测试 GREEN；实现阶段未访问 GDC `/data`，未下载真实文件。
- 实现者两次官方 BRCA dry-run 均卡在 Python TLS `socket.connect` 后人工中断（exit 130），没有得到 manifest 统计；该现象不能直接表述为 GDC 不可达。
- 主流程随后用与脚本相同的 JSON POST、`and`/`=`/`in` filter schema 查询官方 `/files`，约 0.6 秒返回目标 BRCA hit；默认 Python `urllib` 查询官方 `/status` 约 0.7 秒返回 HTTP 200。由此确认请求 schema 可用、Python TLS 并非稳定不可用，但完整 dry-run 仍须重新验证。
- 独立 reviewer 判定初版 B 未过门：完整/损坏 `.part` 在 416 或 MD5 mismatch 后可能永久卡死；206 未核对 `Content-Range` 起点；`--limit 5` 对 3 条 manifest 未实际证明限额；另有文件名静默 basename/碰撞和 `size=10000` 无分页保护问题。
- 已将上述问题退回原任务 B 实现者进入 fix round 1/5。修复前禁止执行计划中的 5 文件真实下载；只允许本地测试和官方 `/files` dry-run 查询。

## 2026-08-27 01:29:40 JST — 任务 B 修复轮次 1 交付

- 修复轮次 1 使用旧实现先得到针对性 RED，再完成 8 项本地 fake-server 回归 GREEN：分页收齐及 filter/fields 结构、完整正确 `.part` 直接完成、损坏 `.part` 遇 416 后隔离并从零重试、错误 206 `Content-Range` 拒绝、服务端忽略 Range 返回 200 时覆盖重写、MD5 mismatch 隔离后次轮可恢复、`--limit 1` 保留完整 manifest 且只发一个 data 请求、危险文件名及同名目标在下载前拒绝。
- `PYTHONPYCACHEPREFIX` 已指向白名单内 `scratch/task_b_pycache`；语法检查 exit 0，未再向 `adapters/` 写入缓存。
- 官方 BRCA `--dry-run` 本轮 exit 0，仅访问 `/files`：labels CSV 病人数 965、命中 963、缺失 2，manifest 共 963 条；未访问 `/data`。
- 主流程通读修复后下载状态机，确认 `--limit` 只截取待下载 rows，不截断查询或 manifest；真实 5 文件下载继续等待原 reviewer 范围化复审放行。

## 2026-08-27 01:34:25 JST — 任务 B 复审通过并放行受限下载

- 原 reviewer 范围化复审确认前轮全部 Critical/Important 均已 ADDRESSED；仅保留“响应侧未复核 project/data_type”的非阻塞防御性建议，官方查询 filters 与本地结构测试已覆盖当前契约。
- reviewer 起初要求先取得真实 Python `--dry-run` 成功证据；补充本轮已有 exit 0、manifest 963、965/963/2 且未访问 `/data` 的原始证据后，明确放行原计划 `--limit 5 --out scratch/gdc_test/` 真下载。
- 下一阶段严格逐条执行 `plan.md` 四条命令；真实 GDC 下载上限保持 5 个文件。

## 2026-08-27 01:56:40 JST — 最终 A0 勘误与事实复盘

- 逐行复核两库 `utils/core_utils.py` 后纠正早先表述：`validate_*` 在 early-stopping 状态满足时会返回 `True`，但外层 epoch 循环只赋值给 `stop`，没有 `if stop: break`；因此当前快照即使加 `--early_stopping` 也不会真正提前停止。
- min-loss checkpoint 仍可能按 val loss 写出，但训练结束后源码无条件保存并载入最后 epoch 的 `s_<fold>_checkpoint.pt`；`Monitor_CIndex` 也未调用。最终模型不由 val checkpoint 选择。
- A1 映射不变：`plan.md` 的条件为 val “参与 epoch/模型选择”，而 val 确实进入每个 epoch 的验证消费；报告现已明确区分“逐 epoch 监控”与“真正模型选择”。

### Bug Post-Mortem
- **现象**: 初版 A0 把“EarlyStopping 对象更新并返回 stop”写成了“训练可按 val loss 提前停止”。
- **根因**: 只检查了 `validate_*` 内部返回值，没有继续追踪调用方是否消费 `stop` 并 `break`。
- **修复**: 继续沿调用链核对外层 epoch 循环，修正 `result.md` 的 split/模型选择描述，并在本 append-only 记录中保留勘误。
- **Prevention Rule**: 判断控制流是否生效时，必须从信号产生点追踪到最终消费者；仅有返回值或 checkpoint 写入不等于训练流程实际停止或选模。

### Bug Post-Mortem（只读搜索命令转义）
- **现象**: 一条用于核对勘误文本的 `rg` shell 命令把含反引号的 pattern 放在双引号中，zsh 尝试执行其中的 `break` 并输出 `zsh:break:1: not in while...`。
- **根因**: 忽略了 shell 双引号内反引号仍会执行命令替换。
- **修复**: 该命令本身没有任何写操作，确认未改变文件；后续不复用此写法。
- **Prevention Rule**: shell 搜索 pattern 含反引号或 `$()` 时必须用安全单引号，或改为不含命令替换符的多个固定字符串参数。

## 2026-08-27 02:05:20 JST — 最终审查与 split 泄漏防线

- 最终独立审查结论为 PARTIAL/BLOCKED：A1、A2、B 可交付；A3 的 MCAT 完整可执行命令因已证实的 baseline 缺陷与固定 1024 维而未达成，不能宣称计划全项 PASS。
- reviewer 发现 `make_splits.py` 初版不拒绝重复 patient_id 或跨 split 重叠。只读核对当前 `labels_424.csv` 后确认所有癌种均无重复/跨 split 重叠，因此已有 BLCA 产物未被污染；但该缺口对后续科研数据有泄漏风险，必须修复。
- TDD RED：新增“同 split 重复”和“跨 split 重叠”两项测试后，旧实现运行 5 项 A1 测试得到 `FAILED (failures=2)`，两处均为预期 `AssertionError: 0 == 0`。
- 最小修复：`read_labels()` 为当前癌种维护 patient_id→split，第二次出现时区分重复与跨 split 并明确失败；正常行为测试改用三个不同患者。
- GREEN：默认 Python 的 A1 测试 5/5 PASS；已有训练环境的任务 A 全套 10/10 PASS；计划 A1 原命令重跑 exit 0，BLCA 136/68/138 且缺失仍全部为 0。

### Bug Post-Mortem
- **现象**: A1 初版允许同一 patient_id 在同一 split 重复，或同时出现在 train/valid/test，可能把同一患者重复训练或泄漏到验证集。
- **根因**: `read_labels()` 只按 split 追加行，没有维护 patient_id 唯一性和 split 互斥不变量；初版正常测试还错误地复用了同一患者覆盖三列。
- **修复**: 在解析阶段强制 patient_id 对当前癌种全局唯一并跨 split 互斥；正常测试改用三个不同患者，新增两项失败路径回归。
- **Prevention Rule**: 所有患者级数据划分适配器必须在写 split 前验证 patient_id 唯一、split 两两不交、空值与未知 split；测试夹具不得用跨 split 重复患者模拟正常案例。

## 2026-08-27 02:10:10 JST — 最终范围化复审通过

- final review round 2 结论：新增 patient 唯一性/跨 split 互斥修复 ADDRESSED，0 Critical、0 Important；A1 5/5、任务 A 10/10 的报告输出一致，A0 early-stopping 勘误正确。
- 唯一 Minor 为 `make_splits.py` 旧注释仍写“验证/模型选择”，可能误导；已只改为“每个 epoch 消费 val 并以其作最终报告”，不改变运行逻辑。
- 最终本地验证：三脚本语法 exit 0；任务 B fake-server 8/8；labels 全癌种 patient 唯一且 overlap=0；GDC manifest 963、TSV 5、`.part` 0、前五 MD5 PASS。

## 2026-08-27 10:38:47 JST — 任务 C 启动、边界与根因审计

- 已完整读取 `plan.md`，本轮只执行任务C的 5 点 MCAT 最小补丁。`baselines/MCAT` 起始状态为 clean；根仓库已有 `plan.md` 修改，视为用户/协作者既有改动，不覆盖、不回退。
- 用户明确指定当前工作区并禁止 commit/push，因此不另建 worktree、不进入提交/合并流程；仅保留工作区 diff 和 `mcat_patch.diff`。
- 根因 1：`main.py` 的 settings 读取 `args.inst_loss`，parser 未定义；PORPOISE 同源 parser 使用字符串 choices、默认 `None`。
- 根因 2：`utils/core_utils.py` 构造 loader 时读取 `args.testing`，parser 未定义；PORPOISE 同源 parser 使用 `store_true`、默认 `False`。
- 根因 3：MCAT `Generic_Split` 对所有 mode 无条件打开 `fast_cluster_ids.pkl`；PORPOISE 对照实现只在 `mode == 'cluster'` 时读取。
- 根因 4：MCAT 代码读取 `./dataset_csv_sig/signatures.csv`，实际目录为 `datasets_csv_sig/`。
- 根因 5：MCAT parser 无 `--path_input_dim`，`core_utils.py` 未把维度传给 `MCAT_Surv`，模型的 `size_dict_WSI` 又把 small/big 输入均固定为 1024；三层断链导致 UNI2-h 1536 forward 失败。
- 默认兼容假设：新增默认分别为 `None`、`False`、`1024`；`MCAT_Surv` 未显式传维度时仍构造 1024 输入层。除清单要求修复的错误路径外，不改变其他参数、模型结构或训练流程。
- 环境预检：指定 `/Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python` 为 CPU（Torch 2.5.1，CUDA 不可用）；已有 torch/pandas/h5py/sklearn/scipy/lifelines，但缺 torchvision、torch_geometric、sksurv、tensorboardX。遵守“禁止安装依赖”，自测仅对未执行的导入边界使用 `scratch/` 测试桩，并在结果中如实标注；dataset 与 MCAT forward 使用真实 torch/pandas 代码。

## 2026-08-27 10:48:44 JST — 任务 C TDD RED

- 新增白名单内 `scratch/task_c_mcat_patch_test.py`，以运行行为而非源码字符串覆盖 parser、split 分支、signature 路径、core 构造参数、真实模型 forward 和官方 BLCA CSV+A1 split mini 冒烟。
- 第一次 RED 未到目标：Torch 2.5.1 已删除 MCAT vendored attention 导入的私有 `_LinearWithBias`，模型模块在测试收集期失败。该兼容问题不在获批 5 点内，因此未改 baseline，只在测试进程把该旧私有名映射到现有 `nn.Linear`。
- 第二次 RED 为有效失败：10 项测试运行 11.159 秒，`FAILED (failures=4, errors=4)`；失败分别为 `--inst_loss/--testing/--path_input_dim` 不在 help、core 未传 `path_input_dim`、coattn split 强读 cluster pickle、signature 旧目录不存在、1536 构造参数不接受。默认 1024 forward 与 cluster 正向守卫已通过。

### Bug Post-Mortem
- **现象**: 首次运行任务C行为测试时，收集阶段报 `ImportError: cannot import name '_LinearWithBias'`，没有触发预期的五点 RED。
- **根因**: 官方 MCAT vendored attention 依赖旧版 PyTorch 私有 API，而指定环境是 Torch 2.5.1；测试夹具未先隔离这一已知环境差异。
- **修复**: 只在 `scratch` 测试进程及 help 子进程的 `sitecustomize.py` 中把 `_LinearWithBias` 映射为 `nn.Linear`，未修改 baseline；第二次运行已到达并准确暴露五个目标缺口。
- **Prevention Rule**: 对旧科研仓库做最小范围补丁时，先把计划外的依赖兼容问题限制在测试夹具；除非任务白名单明确授权，不把环境迁移修复混入生产 diff。

## 2026-08-27 10:53:54 JST — 任务 C GREEN、最小 diff 与留档

- 生产代码只改 4 个必要文件：`main.py`、`datasets/dataset_survival.py`、`utils/core_utils.py`、`models/model_coattn.py`；最终 diff 为 11 insertions/6 deletions，`git diff --check` exit 0。
- 同一行为测试 GREEN：10/10，包含 parser 三参数、coattn 不读 cluster pickle、cluster 仍读取、实际 signature 目录、core 传参、默认 1024 forward、显式 1536 forward、官方 BLCA CSV+A1 split 的两维 mini 冒烟。
- 官方 BLCA split 实际构建为 train 204、val 138、genomic 20394 维；两条 synthetic pt 均为 50 patches，输出分别打印 `bag=(50, 1024)` 和 `bag=(50, 1536)`，hazards 均为 `(1, 4)`。
- 空参数运行时探针确认 `inst_loss=None`、`testing=False`、`path_input_dim=1024`；未把新维度写入实验命名或 settings，未触碰其他训练行为。
- 首次 GREEN 未屏蔽 warning，观察到官方旧代码的 Torch transformer、`torch.load(weights_only=False)`、Pandas positional Series FutureWarning；均非本任务 5 点，未改。最终验收命令用 `PYTHONWARNINGS=ignore` 只压制 warning，不改变断言或执行路径。
- `apply_patch` 曾给原本无 EOF newline 的三个官方文件补换行；已精确机械移除，最终 diff 不含该噪声。
- 已生成 `mcat_patch.diff`；`git diff | cmp - mcat_patch.diff` exit 0，留档为 86 行、5383 bytes。
- 本轮生成的三个 pycache 树共约 97 MB，均位于白名单 scratch 且无 symlink；已用精确 `find ... -delete` 清除，测试脚本保留。

### Bug Post-Mortem
- **现象**: 尝试用 `rm -rf` 清理三个明确的 scratch pycache 目录时被安全策略拒绝；命令未执行。
- **根因**: 忽略了本协作历史已记录 `rm -rf` 会被拒绝，仍选择了被禁止的删除形式。
- **修复**: 先用 `realpath`、`du` 和 `find -type l` 核对精确目标，再用 `find <三个精确目录> -type f -delete` 与 `find ... -depth -type d -empty -delete` 完成清理。
- **Prevention Rule**: scratch 临时树清理固定采用“解析精确路径 → 排查 symlink → `find` 删除普通文件 → 删除空目录”，不再尝试 `rm -rf`。

## 2026-08-27 10:58:21 JST — 任务 C 最终验证门

- 最终树重跑行为测试：10/10，exit 0，运行 10.233 秒；1024/1536 官方 BLCA mini forward 再次 PASS。
- 四个改动文件逐一 `compile()`：全部 exit 0；`git -C baselines/MCAT diff --check` exit 0；`git diff | cmp - mcat_patch.diff` exit 0。
- MCAT 子仓库最终仅 4 个获批文件为 modified；notes/result 均为纯追加；scratch 中任务C只保留 `task_c_mcat_patch_test.py`。
- 按用户禁止 commit/push 的既定选择，保留根仓库 main 与 MCAT master 当前未提交工作树，不执行任何集成操作。

## 2026-08-27 11:59:09 JST — 修复轮 Round 2 路 C 启动与边界审计

- 已完整读取 `plan.md`，本轮只执行「路 C：PORPOISE 全 collator 修复 + UNI2 事务化」，对应 adversarial review finding 4 + 5。
- 写入白名单严格限定为 `baselines/PORPOISE/utils/utils.py`、`adapters/uni2h_to_ptfiles.py`、本目录 `porpoise_patch.diff`、`scratch/`、`notes.md`、`result.md`；明确不碰 `adapters/make_splits.py`、`baselines/MCAT/`、`NPJ/`。
- PORPOISE 子仓库起始已有 5 个 modified 文件：`models/model_coattn.py`、`utils/cluster_train_utils.py`、`utils/coattn_train_utils.py`、`utils/core_utils.py`、`utils/utils.py`。前 4 个属于既有改动，本轮不触碰、不回退；`utils/utils.py` 已有普通 survival collator 的 Torch 2 兼容补丁，本轮在其上最小增量修复 `_sig` 与 `_cluster` 并验证三个 collator。
- `adapters/uni2h_to_ptfiles.py` 当前直接向最终 `pt_files/` 逐文件写入，失败会留下部分产物；`--overwrite` 当前是逐文件覆盖而非整套替换；无 h5 输入会返回 `written == 0` 且成功退出，均与 finding 5 冲突。
- 实施契约：同一输出根目录内建立唯一 staging 目录，所有 `.pt` 写入 staging；逐成员记录 slide/patient/shape/checksum manifest，并在发布前重新读取全体 `.pt` 完整核验；仅全通过后原子 rename 为 `pt_files`。无 `--overwrite` 时最终目录已存在即在转换前失败；有 `--overwrite` 时先完整构建新套件，发布阶段移走旧套件、rename 新套件，失败时恢复旧套件，避免新旧混合。
- 验证契约：扩展 `--selftest` 覆盖正常发布、半途失败不留最终目录、`written == 0` 非零失败、`--overwrite` 整套替换；另在 `scratch/` 构造官方 BLCA CSV + A1 split + 合成 pt 的真实 `Generic_Split`/DataLoader 首批，覆盖 `pathomic` 与 `coattn`，并以最小合成 dataset 覆盖 cluster collator。
- 严格禁止训练、SSH、下载、commit/push；冒烟和首批取数完成即停止。路 C 两个生产文件有顺序依赖且共享验收脚本，不启用并行 Sub Agent，避免白名单内同文件冲突。

## 2026-08-27 12:08:00 JST — PORPOISE collator TDD RED 与测试夹具勘误

- 新增白名单内 `scratch/task_c_round2_porpoise_collator_test.py`：用官方 PORPOISE BLCA CSV 的全部原始行/基因组列、A1 `splits_0.csv`、合成 `[4,1536]` pt，实际构造 `Generic_MIL_Survival_Dataset` 和 `DataLoader` 首批；另用最小合成 Dataset 覆盖 cluster collator。
- 第一次 RED 被官方 CSV 与旧 loader 的 schema 漂移提前阻断：当前 ZIP 缺 loader 固定断言要求的 `Unnamed: 0`，且元数据列顺序不同。测试只在临时 `scratch/` 副本插入行号列并恢复 loader 预期顺序，官方结局值、病例、切片和基因组值均不改。
- 第二次 RED 被签名目录漂移提前阻断：loader 读取不存在的 `datasets_csv_sig/signatures.csv`，实际官方文件为 `datasets_csv/signatures.csv`。由于该路径不在路 C 白名单，测试仅把实际文件复制到临时 scratch 夹具的预期相对路径，不改 baseline。
- 第三次 RED 准确到达目标：pathomic 首批已经 PASS；coattn 在 `collate_MIL_survival_sig`、cluster 在 `collate_MIL_survival_cluster` 均因 `torch.LongTensor([tensor])` 报 `TypeError: only integer tensors of a single element can be converted to an index`。总结果为 3 项中 1 PASS、2 ERROR，exit 1。

### Bug Post-Mortem（首批测试夹具）

- **现象**: 初版双 mode 首批测试先后被官方 CSV 元数据顺序断言和缺失的签名相对目录阻断，第一次没有到达目标 collator RED。
- **根因**: 测试夹具假设当前官方 ZIP 可直接满足 PORPOISE 旧 loader 的固定 schema/相对路径，但仓库实际文件布局已与代码假设漂移。
- **修复**: 仅在临时 scratch 中把同一官方 CSV 恢复为 loader 预期列顺序，并把仓库现有官方 signatures 文件映射到其预期相对目录；不改结局/基因组数据，不碰白名单外源码。
- **Prevention Rule**: 旧科研仓库的集成测试必须先核对“磁盘工件 schema + 代码硬编码相对路径”；测试兼容层需显式、临时、可审计，不能把夹具适配伪装成生产代码已修复。

## 2026-08-27 12:06:41 JST — collator GREEN 与时间戳勘误

- 上一节标题的 `12:08:00` 是手工估计，实际工具时钟显示本节记录时为 `12:06:41 JST`；保留原文并在此勘误，遵守 notes append-only。
- `baselines/PORPOISE/utils/utils.py` 仅在三个目标 collator 内修改：普通、signature、cluster 的 tensor 列表均改为 `torch.cat(...).to(dtype=...)`；普通/签名 omic 为 `float32`，cluster id 与 label 为 `int64`，event time/censorship 为 `float32`。
- 同一 RED 测试原样重跑后 3/3 GREEN，exit 0：官方 BLCA + A1 split + 合成 1536 pt 的 coattn/pathomic 首批均通过，cluster 合成 DataLoader 首批通过；未构造模型、未执行 optimizer、未进入训练循环。
- 首批证据：coattn path `(4,1536)`、六组 omic `(94,334,521,468,1496,479)`；pathomic path `(4,1536)`、omic `(1,20395)`；三路 label/event/c 均为 `(1,)` 且 dtype 分别为 `torch.int64/torch.float32/torch.float32`。

### Bug Post-Mortem（notes 时间戳）

- **现象**: 上一节标题手工写成 `12:08:00`，晚于随后读取的真实系统时间。
- **根因**: 写 notes 前没有先读取工具时钟，使用了估计时间。
- **修复**: 不改写 append-only 历史，在本节显式勘误并记录真实 `date` 输出。
- **Prevention Rule**: 后续每次追加阶段标题前先执行 `date '+%Y-%m-%d %H:%M:%S %Z'`，禁止手工估时。

## 2026-08-27 12:13:37 JST — UNI2 事务自检、adversarial review 与最终范围审计

- `adapters/uni2h_to_ptfiles.py` 已实现同输出根目录 staging、逐 `.pt` SHA-256/shape/dtype manifest、发布前全量重新加载校验、`os.replace` 原子发布；overwrite 时旧正式目录先原子移到唯一 backup，新目录发布失败则恢复旧目录，成功后删除 backup，因此最终 `pt_files` 不会混入旧成员。
- 最终 `--selftest` exit 0，四条 PASS：正常 publish+manifest；第二个成员非法时半途失败且无最终目录；空输入子进程 exit 2 且无最终目录；overwrite 后最终集合只含新成员、manifest 同步替换。selftest 临时根固定在白名单 `scratch/`，结束后未留 staging/backup/selftest 目录。
- code-inspect 七维复核未发现修改范围内的 Critical/Warning；审查中收紧半途失败断言，要求错误文本命中第二个 1024 维非法成员，避免“任意 ValueError 即 PASS”的假阳性；并机械恢复 `utils.py` 原始无 EOF newline，去掉非目标 diff 噪声。
- `porpoise_patch.diff` 延续原有“PORPOISE 当前完整工作树 diff”口径更新；`git diff | cmp - porpoise_patch.diff` exit 0，`git diff --check` exit 0。该留档仍包含本轮开始前已有的另外四个 PORPOISE modified 文件，本轮生产写入只发生在 `utils/utils.py`。
- 最终白名单审计：本路写入为 `baselines/PORPOISE/utils/utils.py`、`adapters/uni2h_to_ptfiles.py`、`porpoise_patch.diff`、`scratch/task_c_round2_porpoise_collator_test.py`、`notes.md`，待追加 `result.md`。`adapters/make_splits.py` mtime 为 `01:45:42 JST`，NPJ 在本轮开始后无新文件。
- 审计同时观察到其他并行路在本轮期间写入 `scratch/round2_route_a_contract_test.py`、`mcat_patch.diff` 与 `baselines/MCAT/main.py`；这些不是本路命令或 patch 产生，本路没有读取后覆盖、修改或回退它们。PORPOISE 子仓库其余 4 个 modified 文件的状态与启动时一致。
- 未运行训练、下载、SSH、git commit、git push；首批取数通过后按停机门停止。

## 2026-08-27 12:16:35 JST — 并行写入后的审计快照勘误

- 本路 `result.md` 13 节写入后，其他执行方继续向同一文件追加路 B 结果，并在 `12:14:25 JST` 修改 `adapters/make_splits.py`；因此 13.5 中 `make_splits.py mtime=01:45:42` 仅代表本路首次范围审计快照，不是整个工作区最终静态状态。
- 这不改变本路自身的白名单结论：本路所有 `apply_patch`/机械编辑目标仍只在路 C 白名单内；后续出现的路 A/B 文件状态属于并发执行方，本路未覆盖或回退。
- 根仓库对 task artifact 做 `git diff --check` 会报告 `porpoise_patch.diff` 中三行 `+ ` 的 trailing whitespace；这些字符是“嵌套 unified diff 的文本内容”，且该文件必须逐字等于 PORPOISE `git diff`。PORPOISE 源码自身 `git diff --check` exit 0，artifact `cmp` exit 0，故不改写留档破坏一致性。

### Bug Post-Mortem（并发审计与相对路径）

- **现象**: 一条 `stat` 命令从任务目录使用了错误的 `../../../../baselines/MCAT/main.py`，exit 1；同时首次范围说明把并发修改前的 mtime 写成“最终”。
- **根因**: 相对路径层级多算一级，且在共享工作区中把瞬时审计快照措辞写得过于静态。
- **修复**: 从仓库根用 `baselines/MCAT/main.py` 重跑成功，并在 notes/result 追加快照勘误，不改写历史。
- **Prevention Rule**: 共享工作区的范围证据必须带审计时点并区分“本执行流写入”与“当前全局状态”；路径审计优先使用仓库根相对路径或绝对路径。

## 2026-08-27 12:03:53 JST — 修复轮 Round 2 路 B 启动、边界与实施取舍

- 已完整读取 `plan.md`，本轮只执行「路 B：MCAT 实验身份隔离」，对应 adversarial review finding 3。
- 写入白名单严格限定为 `baselines/MCAT/` 内实现本目标的最少文件，以及本目录 `mcat_patch.diff`、`notes.md`、`result.md`；明确不碰 `adapters/`、`baselines/PORPOISE/`、`NPJ/`。禁止 SSH、训练、commit/push。
- MCAT 子仓库已有 Round 1 与其他协作者的未提交改动；本轮不回退、不覆盖。当前 `mcat_patch.diff` 与子仓库全量 diff 一致，起始 SHA256 为 `28bdfe28079e04842ff719ed0d97984bf1cc5b2f46d9096306982b3612e28400`。
- 最小实现选择：只改 `baselines/MCAT/main.py`。在 `get_custom_exp_code()` 返回后同时向 `param_code` 与 `exp_code` 追加 `_pid{path_input_dim}`；settings 新增 `path_input_dim` 与 `data_root_dir`；既有最终结果目录用 `ast.literal_eval` 安全解析对应 experiment 记录，缺文件、损坏、缺键或值不同均 `RuntimeError` 硬失败，且检查位于 `summary_latest.csv` 早退之前，`--overwrite` 不能绕过。
- 验收不使用 `--testing`，因为它仍会进入 epoch/反传。改用 `--k_start 0 --k_end 0` 的空 folds 干跑：只走到 dataset 构建、目录/元数据创建与身份检查，不调用 `train()`、不生成 fold checkpoint。测试结果使用系统临时目录，并设 `PYTHONDONTWRITEBYTECODE=1`。

## 2026-08-27 12:07:44 JST — 修复轮 Round 2 路 A 启动与契约收敛

- 已完整读取 `plan.md`；本轮只执行「路 A：统一结局表 + split 契约修正」，对应 finding 1 + 2。写入白名单严格限定为 `adapters/build_outcome_table.py`、`adapters/make_splits.py`、`adapters/eval_frozen_test.py`、本任务目录 `scratch/`、`notes.md`、`result.md`；禁止触碰 `baselines/`、`NPJ/`，禁止 SSH、训练、commit/push。
- 并行只读契约审计确认：MCAT 源为 `dataset_csv/`；PORPOISE 的既定 `--apply_mutsig` 路径必须用 `datasets_csv_mutsig/`。adapted CSV 必须保留官方列顺序、全部非结局列和每名患者的全部 slide 行，只过滤到 `labels patient_id ∩ official case_id`，再逐行覆盖 `survival_months` 与 `censorship`。
- 五癌种标签/官方交集患者数：BLCA 342/342、BRCA 965/878、LUAD 432/421、LGG 415/407、UCEC 494/470。LGG 只能从 `gbmlgg` 官方 CSV 按 labels 中 LGG patient_id 精确过滤；不能按 oncotree_code 等于 LGG 过滤。
- 30→30.44 审计假设定义为 `official_old × 30.44 / 30`，容差 `abs(residual) <= 0.0051`。BRCA/LUAD/LGG 全符合，UCEC 469/470 符合；异常患者 `TCGA-FI-A3PV` 旧值 41.03、新值 42.13333333333333、换算期望 41.631773333333335。实现只审计该假设，不据此换算，结局始终直接取 labels 唯一真源。
- split 修正固定为 `train=our train`、`val=our valid`，test 只做交集/缺失审计，绝不写入 `splits_0.csv`。BLCA 预期 136/68；LGG 因官方缺 4/1/3，预期 162/82。
- 发现额外泄漏风险：两库在 split 前会基于传入 dataset CSV 全体未删失患者做 qcut；若训练输入 CSV 含 test，test 结局仍影响训练标签分箱。因此 build 脚本除计划指定的完整 adapted CSV 外，还需在同一 `scratch/adapted_csv/` 生成排除 test 的 train-valid 训练副本；`make_splits --adapted-csv` 将硬校验输入不含 test。完整 adapted CSV仅用于冻结 test 评估。
- 当前本机无 `sksurv`，且无真实 `s_0_checkpoint.pt`/特征；按 plan 允许走 `eval_frozen_test.py --dry-run` 结构校验。dry-run 必须延迟导入训练依赖，验证 train/valid/test 互斥、split 精确映射、adapted 结局一致、test 病人/slide 覆盖，并明确输出 `forward_skipped=true`，不得伪报真实 c-index。
- `complex-task` 所列 sequential-thinking、decision-reviewer、insight 工具在当前工具集中不可调用；采用主 Agent 手工依赖分析、独立只读 Explorer 交叉核对、最终行为测试与白名单 diff 审计作为降级替代。

## 2026-08-27 12:08:53 JST — 路 B RED/GREEN、补丁留档与验证命令勘误

- RED 空 folds 干跑已复现 finding 3：未修改时，1024 与 1536 均得到 `tcga_blca_MCAT_nll_surv_a0.0_5foldcv_gc32_concat`，只有 1 个无 `_pid` 的 experiment 目录；1536 请求遇到 1024 的 `summary_latest.csv` 后 exit 0，checkpoint 数为 0。
- GREEN 只改 `baselines/MCAT/main.py`：1024/1536 分别生成 `_pid1024`/`_pid1536` 的 `param_code` 和 `exp_code` 目录；两个 experiment 记录均含正确 `path_input_dim` 和 `data_root_dir`。同身份复用 exit 0；`data_root_dir` 冲突在带 `--overwrite` 时仍 exit 1；篡改记录中 `path_input_dim` 后 exit 1。干跑产生的 checkpoint 与 fold result 数均为 0。
- 静态/入口验证：`main.py` `compile()` PASS，`main.py --help` exit 0 且保留 `--path_input_dim,--testing,--inst_loss`，`git -C baselines/MCAT diff --check` exit 0。
- 已按计划执行 `git -C baselines/MCAT diff > collab/20260827-三方对比战役/mcat_patch.diff`；留档为 227 行、11864 bytes，SHA256 `4999105a1d75d3ac70ae21268e8ae57d9e419f109dff77c9e484bb692f6bf6fc`，与子仓库当前全量 `git diff` 逐字节一致。
- 非路 B 的 MCAT 五个已改文件在实施前后 SHA256 全部不变；本轮没有新增 MCAT pycache。根仓库的路 A/路 C/监视器并发改动仅做观察，本轮未触碰。

### Bug Post-Mortem（组合验证命令路径）

- **现象**: 首次组合验证已把 cwd 设为 `baselines/MCAT`，但 `git -C baselines/MCAT diff --check` 和语法检查仍重复使用 `baselines/MCAT/...`，前两项因路径不存在失败；末尾 help 成功使 shell 整体返回 0。
- **根因**: 组合命令时混用了根目录相对路径与已切换 cwd 的相对路径，且首版未设 `set -e`。
- **修复**: 立即在 `baselines/MCAT` cwd 下使用 `git diff --check` 和 `Path('main.py')` 重跑，两项均 exit 0；后续最终验证使用绝对路径并设 `set -e`。
- **Prevention Rule**: 多项验证命令必须先固定 cwd 路径语义，并设 `set -e`；不得用末尾子命令的成功退出码掩盖前序失败。

## 2026-08-27 12:11:06 JST — 路 A 合成契约测试 RED

- 新增白名单内 `scratch/round2_route_a_contract_test.py`，覆盖：labels 结局逐行覆盖、非结局列/双切片保留、非 labels 官方患者过滤、MCAT/PORPOISE 两类 ZIP 内成员兼容、trainval 副本排除 test、split 精确映射为 train/valid、错误训练 CSV 含 test 时硬失败、冻结 test dry-run JSON。
- RED 命令：`PYTHONDONTWRITEBYTECODE=1 python3 scratch/round2_route_a_contract_test.py`；真实结果为 `Ran 1 test`、`FAILED (failures=1)`、exit 1。失败准确命中首个目标缺口：`adapters/build_outcome_table.py` 不存在，Python 返回 `[Errno 2] No such file or directory`；尚未执行到后续旧 split 错误与缺失 eval 脚本。
