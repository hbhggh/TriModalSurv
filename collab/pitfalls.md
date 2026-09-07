# TriModalSurv 坑台账（Pitfalls Ledger）

> 一行一坑。用法（回流三环，规则见 CLAUDE.md）：
> ①注入——派单前 Claude 从此处挑 3~5 条相关条目写进 plan.md「相关坑」节；
> ②入账——收单 review 时新 Post-Mortem 各提炼一行追加至此；
> ③升级——影响全局的坑经用户确认固化进 CLAUDE.md/AGENTS.md。
> 详细 Post-Mortem 原文见「出处」列。

## 数据与口径

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| D1 | 患者可在同一或不同 split 重复，导致重复训练或泄漏。 | 写 split 前验证 patient_id 唯一、split 两两不交、无空值和未知 split。 | collab/20260827-三方对比战役/notes.md |
| D2 | 特征路径/维度未进缓存键，旧特征缓存会跨来源命中。 | 缓存键纳入绝对路径、维度、token 数、预处理版和标签 hash，并用实验级目录、manifest、原子写。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D3 | train/valid/test 分别拟合 pd.cut，时间 bin 语义不一致且 NaN 被吞入 bin。 | 仅用训练集拟合并保存 bin edges，valid/test 复用；拒绝 NaN/Inf 并校验 censorship 取值。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D4 | 各模态 patient_id 规范不一致，会把整模态静默落到零向量。 | 所有模态统一为 TCGA 前 12 位，检查碰撞/跨 split 重复，并落盘每 split 交集清单。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D5 | UNI2 转换默认输出目录与 YAML 读取目录不一致，会污染原始特征或找不到特征。 | 默认、文档和配置统一到版本化目录；禁止向非空原始目录写入并全量校验维度。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D6 | Text 转换只抽样或只验元素数，异常 `[200,768]` 外形可静默流入训练。 | 写出前对全部输出断言 shape、dtype、有限值，不能以打印式抽检替代。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D7 | 已存在 UNI2 文件未校验来源/shape/dtype 就被计为 kept，覆盖率会虚报。 | 复用前做内容校验并记录 source hash；发现冲突立即失败。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D8 | simulate_missing_modality 只作用训练集，未来会误把普通 test 指标说成缺失率性能。 | train/valid/test 分别使用固定、落盘的 missing manifest。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D9 | Ensembl ID 用宽泛分割清版本时会误删 `_PAR_Y` 等合法后缀。 | 只删除明确数值版本段，并用真实 GDC `_PAR_Y` 行回归。 | collab/20260827-三方对比战役/notes.md |
| D10 | 将相似 fork 的列重排规则套到 PORPOISE，会使 test patient 契约失效。 | fork 数据契约以运行时库对象为真源，不能由相似代码推断。 | collab/20260827-三方对比战役/notes.md |
| D11 | LUAD 被映射为 tcga_lung 而部署按 luad 命名，lane 假完成却 unit 已失败。 | 新癌种逐项核对 study→combined_study→路径，并以 unit `.done` 判成功。 | collab/20260827-三方对比战役/notes.md |
| D12 | NLL 与 CE survival loss 的签名/风险语义被混同，产生接口错误或错误 risk shape。 | 每种 loss 均核对真实 `__call__` 签名和预测语义，不能按类名猜接口。 | collab/20260827-三方对比战役/notes.md |
| D13 | dataset 发 `{mm}_valid` 而模型读 `{mm}_mask`，缺失零向量仍参与融合。 | 统一键名，将逐样本 mask 传至 gate softmax 前屏蔽，并做混合缺失 batch 测试。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| D14 | dataset 缓存键含 network_type，换骨架名触发全量逐 patient 冷重建（3 s/人）。 | 缓存键只含数据相关维度；新骨架名上机前核对缓存命中（δ 已去 network_type 并回退旧后缀）。 | collab/20260902-A测缺失补偿/notes.md |
| D15 | 多条 lane 并发冷重建同一 dataset 缓存，一方读到半写 pkl（EOFError），单 seed 失败被"两败才停线"放过、unit 假 done。 | 共享缓存先独占预热再并发（launcher 内置）；unit done 以全部 seed ckpt 存在判定；缓存写入临时文件+原子 rename。 | collab/20260902-A测缺失补偿/notes.md |
| D16 | 发车器契约只写 arm→compensator 映射未列训练超参，`--dry_run` 生成的命令缺 `--lr 1e-4 --epochs 50 --batch_size 32`，将以默认 lr=5e-4 跑出与既有正式训练不同口径。 | 发车器契约逐项列出与既有正式训练命令（`c_unit.sh`/`s4_run_method_cancer.sh`）的参数对齐清单，发车前 dry-run 逐参 diff 断言。 | collab/20260902-A测缺失补偿/notes.md |
| D17 | `train_launcher.py` YAML plan 模式只从 ARM_PRESETS 继承 network_type/compensator，不继承 `extra_args`：`arm: d0` 会静默变 gate，`arm: e1` 会丢 `--modality_dropout/--consistency_lambda`，且幂等跳过会复用错误 ckpt。 | 正式发车只走 CLI `--arms`；plan 模式必须显式写 extra_args；发车前 dry-run 逐条断言臂身份参数（fusion_type/dropout/λ）；加固：plan 缺省继承 preset.extra_args + 身份断言。 | collab/20260906-NPJ-D消融/审查/adversarial-review-findings.md |
## 通道与派单

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| C1 | shell 搜索 pattern 中的反引号或 `$()` 被双引号触发命令替换。 | 此类 pattern 使用单引号，或拆成不含命令替换符的固定参数。 | collab/20260827-三方对比战役/notes.md |
| C2 | 任务中途为只读核验新增联网域名，仍违反全程网络白名单。 | 联网白名单贯穿整个任务链；新增站点即使官方只读也先获授权。 | collab/20260827-三方对比战役/notes.md |
| C3 | 并发 append-only 文档用旧尾部锚点写入，会导致补丁失配。 | 写前立即刷新文档尾部，并为独立文件拆分补丁。 | collab/20260827-三方对比战役/notes.md |
| C4 | 长命令超出 yield 后未保留 session id，无法续读而易被重复派发。 | 首次调用输出完整返回对象；超时后只续读原 session，禁止重复派发。 | collab/20260902-A测缺失补偿/notes.md |
| C5 | 以 mac 本地旧脚本推断 landau 实际行为，claim 锁残留使重发全部跳过。 | 必须读取部署环境的实际文件；两端脚本变更立即回同步 collab 档案。 | collab/20260827-三方对比战役/notes.md |
| C6 | "中等实现默认不传 --effort"实际回落 config.toml 的 max 档，任务长跑数小时。 | 每单显式传 `--model` 与 `--effort`，绝不依赖隐式默认（已固化进 CLAUDE.md 派单矩阵）。 | CLAUDE.md（20260902 调查固化） |
| C7 | companion task 前台模式无任何超时/watchdog，空转任务可挂 7+ 小时无人拦截。 | >10 分钟任务一律 `--background` 发单，`status --wait --timeout-ms` 追踪，45 分钟无输出报告用户。 | collab/monitor/routine-sweep.md |
| C8 | companion 对不认识的 `--flag` 不报错，静默拼进 prompt 正文，拼错参数无声失效。 | 发单前自查参数拼写；发单后 status 核对 prompt 未混入 flag 文本。 | CLAUDE.md（20260902 调查固化） |
| C9 | companion effort 白名单不含 `max`（config.toml 却接受），模型别名仅 spark，`--model sol` 会原样透传成非法 slug。 | effort 只用 none/minimal/low/medium/high/xhigh；模型写全名 `gpt-5.6-sol`/`gpt-5.6-terra`/`gpt-5.3-codex-spark`。 | CLAUDE.md（20260902 调查固化） |
| C10 | `--fresh` 实为空操作；且 `task --resume-last` **不继承** 原线程的 `--write`（job json `write:false`，会话内三处 READ_ONLY），"续接可写"是幻觉。 | 需要写的续接一律不带 `--resume-last` 开新会话并首启 `--write`，prompt 交代磁盘现状；`--resume-last` 只用于只读问答。 | CLAUDE.md（20260902 调查固化）；collab/20260902-A测缺失补偿/notes.md（20260904 实测修订） |
| C11 | 用 task prompt 自造 Codex 审查单代替 companion 原生 `adversarial-review`，丢失内置攻击面框架与结构化 JSON 输出，且单次被进程退出杀掉即全丢。 | 对抗审查一律走 `adversarial-review --cwd <仓> --scope working-tree --model gpt-5.6-sol --json`，用 setsid 脱离会话、输出直接落审查目录；该子命令不接受 `--effort`。 | collab/20260902-NPJ-GPU合同/notes.md |
| C12 | companion task 遇 Codex"请回复确认"即结束会话（exit 0 零改动）。 | 派单 prompt 必含"无需确认直接实现"；需续接用 --resume-last。 | collab/20260902-A测缺失补偿/notes.md |
| C13 | companion 后台作业 worker 死亡后 job json 仍 `running`，`status` 照报 running/editing 且 Elapsed 递增；`--resume-last` 被以"still running"拒绝。 | 存活判定=job json 的 pid 存活 + 日志 mtime 15 min 内；死作业先 `cancel` 清状态再续接，不信 status 字段。 | collab/20260902-A测缺失补偿/notes.md |
| C14 | 用户指令与论文主贡献或既有证据冲突时未先提异议直接执行，导致 batch 测速空转、主贡献由"原型补偿"改向"拆伪门控"、A/B 口径三改返工。 | 可能偏离主贡献或与既有证据相悖的指令，先给一句预测/反对（含代价估计）再执行；主贡献改向必须显式征求用户裁决。 | collab/20260902-A测缺失补偿/notes.md |
| C15 | 单个 `apply_patch` 对同一路径同时发 Delete 与 Add 两个互斥操作，补丁被编辑器整体拒绝。 | 完整替换已有文件只用一个 Update 操作；新增文件另起独立补丁。 | collab/20260902-A测缺失补偿/notes_eps_codex.md |

## 沙箱与权限

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| S1 | 裸 `py_compile` 即使设 PYTHONDONTWRITEBYTECODE 仍会在源码旁写 `.pyc`，越出白名单。 | 语法检查优先内存 `compile()`；必须写缓存时设 PYTHONPYCACHEPREFIX 到白名单 scratch。 | collab/20260827-三方对比战役/notes.md |
| S2 | 用 `rm -rf` 清理已核对的 scratch 缓存仍会被安全策略拒绝。 | 缓存优先写 `/private/tmp`；清理用精确目标的可恢复移动或逐文件删除，不递归强删。 | collab/20260827-三方对比战役/notes.md |
| S3 | JavaScript 模板正文含未转义 Markdown 反引号，命令封装在执行前被截断。 | 模板正文不放未转义反引号；复杂文本改用安全参数或无反引号前缀。 | collab/20260902-A测缺失补偿/notes.md |
| S4 | 被限制只读的交叉审核 Agent 在仓库根创建白名单外文件。 | 严格白名单任务不委派会落盘的通用审核；必要时前后比较完整 Git 状态，越界即中断并恢复基线。 | collab/20260826-NPJ三模态复现/notes.md |
| S5 | 沙箱禁止创建 Torch shared-memory object，显式 `fork` 的多 worker 夹具报 `Operation not permitted`，拿不到真实 DataLoader 证据。 | 连续两次被 multiprocessing 环境阻断即停止该路线，改用 `copy.deepcopy` 等可审计的状态复制最小模型并写明证据边界；禁止把沙箱失败报成生产失败。 | collab/20260902-A测缺失补偿/notes.md |
| S6 | 全局 PostToolUse hook `~/.claude/hooks/py_compile_check.py` 对 Write/Edit 的 `.py` 裸调 `py_compile.compile()`（独立进程，不受会话内 PYTHONDONTWRITEBYTECODE 约束），在源码旁 `__pycache__/` 落 `.pyc`，越出白名单。 | 白名单任务交付前必跑 `find <仓> -name '*.pyc' -newer <基准标记>` 精确清理（`rm` 单文件 + `rmdir`，不 `rm -rf`）；或用 Bash heredoc 写 `.py` 绕开该 hook。 | collab/20260906-NPJ-D消融/notes.md |

## 环境与依赖

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| E1 | 计划指定 YAML 验证因缺 PyYAML 在导入阶段失败，实际断言未运行。 | 先只读检查依赖；禁止安装时保留原失败，并区分指定命令与替代内容验证。 | collab/20260826-NPJ三模态复现/result.md |
| E2 | 旧科研仓库的计划外兼容问题把测试挡在业务 RED 之外。 | 兼容仅在临时、显式、可审计的测试夹具隔离，未经白名单授权不混入生产 diff。 | collab/20260827-三方对比战役/notes.md |
| E3 | 可选依赖逐包 shim 或 import error 遮蔽了目标功能 RED。 | 先证明夹具抵达业务缺口；连续两个无关依赖阻断时按最小符号边界隔离，重证 RED。 | collab/20260827-三方对比战役/notes.md |
| E4 | 用 spec_from_file_location 动态执行含 dataclass 的模块时未注册 sys.modules。 | 动态执行前先注册 sys.modules；夹具故障不得归因生产代码。 | collab/20260827-三方对比战役/notes.md |
| E5 | 全长模型 fp32 GPU 前向 OOM，本地合成 dtype 检查无法证明真实路径可跑。 | GPU 冒烟记录 device/dtype/峰值显存；未完成真实前向不得称 OOM 已解决。 | collab/20260827-三方对比战役/notes.md |
| E6 | tiny float16 测试通过却在目标 attention 的极值 mask/softmax 溢出。 | 低精度测试覆盖目标极值、mask、softmax 和最终导出，真实 GPU 未跑不宣称兼容。 | collab/20260827-三方对比战役/notes.md |
| E7 | bfloat16 可前向却在 `.cpu().numpy()` 序列化出口失败。 | 低精度路径端到端覆盖转换、前向、CPU 搬运和 NumPy 序列化。 | collab/20260827-三方对比战役/notes.md |
| E8 | CLI 契约测试被无关的 Matplotlib/easydict 顶层导入截断。 | 在测试进程边界替代无关模块，只保留解析器所需符号，不改生产导入结构。 | collab/20260902-A测缺失补偿/notes.md |
| E9 | 隔离测试的最小 `tqdm` 替身触发 Torch Dynamo 插件发现而失败。 | 函数级测试只提供目标协议所需的最小真实替代，避免触发框架级编译/发现。 | collab/20260902-A测缺失补偿/notes.md |
| E10 | 缺失非业务展示依赖时，导入错误被误当成业务 RED。 | 先用 find_spec 定位；只在测试进程边界做最小替代，不改生产依赖。 | collab/20260902-A测缺失补偿/notes.md |
| E11 | macOS 默认 `spawn` 下，here-doc/`<stdin>` 内联夹具无法被 DataLoader worker 子进程重新导入，报 `FileNotFoundError: .../<stdin>`。 | 需要 spawn 的多 worker 测试必须写成白名单内可导入的真实脚本文件入口；`<stdin>` 内联夹具只用于单进程测试。 | collab/20260902-A测缺失补偿/notes.md |
| E12 | 远端 `pkill -f "<字面>"` 匹配到承载自身的 ssh bash，会话自杀 exit 255 无输出。 | 远端 pkill 用 `[x]` 正则技巧或 pgrep 精确 pid。 | collab/20260902-A测缺失补偿/notes.md |
| E13 | zsh 对以 `=` 开头的裸词做 =command 展开，`echo ===` 使整条命令未执行。 | 分隔符一律加引号。 | collab/20260902-A测缺失补偿/notes.md |
| E14 | 评估器 `os.chdir(临时目录)` 使 dataset 相对路径缓存 `tmp_sur_cache` 永不命中，每次评测冷重建 5–8 min 且缓存写进临时目录丢失。 | 包装脚本 chdir 前核对被包装代码的相对路径依赖并做符号链接/绝对化；性能异常先查 `/proc/<pid>/cwd` 与缓存命中。 | collab/20260902-A测缺失补偿/notes.md |
| E15 | zsh 测试封装用 `status` 承接退出码，触发 `read-only variable: status`，业务 RED 被外层报错污染。 | zsh 封装的退出码变量一律用任务前缀专名（如 `red_exit`），禁止使用 `status` 等 shell 特殊参数名。 | collab/20260902-A测缺失补偿/notes.md |
| E16 | 自制标准库 YAML fallback 沿用 Python 习惯把 `none` 解析为空值，`compensator: none` 被误报为未提供。 | 自制兼容解析器按目标格式标准定义字面量（只有 `null`/`~` 为空），每个领域关键字配一条回归样例。 | collab/20260902-A测缺失补偿/notes.md |
| E17 | 本机 `python` 仅是交互 zsh 别名，非交互 shell（bash -c / 沙箱）下 `command not found`，派单命令写 `python` 会让引擎假失败。 | 派单契约、脚本与验收命令一律写 `python3`；契约环境节写明可用解释器与依赖清单。 | collab/20260902-A测缺失补偿/plan.md 单 ε 审查 |
| E18 | 不同引擎的 shell PATH 不同：Codex 会话里 `python3` 解析为 Homebrew 3.14（无 matplotlib），Claude 侧为 `/usr/bin/python3` 3.9；同一契约在两边跑出不同解释器。 | 契约与验收命令写绝对解释器路径（`/usr/bin/python3`）或首步打印 `which python3` + 版本并断言；派单前用目标引擎实跑一次 `python3 -c 'import matplotlib'`。 | collab/20260902-A测缺失补偿/notes_eps_codex.md |

## 评测与复现

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| V1 | 评测将原始 logits 当 hazard 计算 c-index 并据此选 checkpoint。 | 评测先 sigmoid logits 再算 survival/risk，NLL 保持接收 logits，并重跑受影响 seeds。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V2 | `MainModalityMoE` 的 experts/topk 未参与计算，却被作为 MoE 报告。 | 要么实现并调用 expert/router 后重跑，要么改称 gated multimodal fusion 并删除 MoE claim。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V3 | shell/CLI 默认覆盖 YAML，实际 5-seed 架构与声明配置不一致。 | CLI 默认设为 None 并由 YAML 提供值；显式 CLI 才覆盖，且保存 resolved config。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V4 | summary 将 `<0.5` 的 c-index/loss 翻转，事后美化失败 seed。 | 原样汇总；风险方向在预测定义处一次固定，反向验证只能统一重算全体风险。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V5 | 缺失/陈旧 seed 结果仍可汇总成所谓 5-seed 结论。 | shell fail-fast；汇总强制五个指定 seed 和一致 config hash，并记录 run ID、seed 列表、n。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V6 | CSV/曲线文件名不含 seed/config，串行或并行运行会覆盖或混写产物。 | 所有产物路径纳入 seed、cpt_name、数据/config hash，并原子写入。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V7 | valid c-index 为 0/NaN 时未保存 checkpoint，训练末尾才无条件加载失败。 | best metric 初始化为 `-inf` 并保存首个有限值；NaN/无可比较对立即报错。 | collab/20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md |
| V8 | 只看到 EarlyStopping 返回值/写 checkpoint，便误断训练实际停止或选到最佳模型。 | 从控制信号产生点追到最终消费者，确认外层确实 `break`/加载目标 checkpoint。 | collab/20260827-三方对比战役/notes.md |
| V9 | 集成夹具的磁盘 schema 或硬编码相对路径不符，测试未抵达目标 RED。 | 先核验工件 schema 与路径；兼容层必须临时、显式、可审计。 | collab/20260827-三方对比战役/notes.md |
| V10 | 组合验证 cwd 语义错误，末尾成功子命令掩盖前序失败。 | 固定 cwd/路径语义并 `set -e`，逐项读取退出码。 | collab/20260827-三方对比战役/notes.md |
| V11 | 错误路径测试按 traceback/文件名中的宽泛词判断，产生假阳性 RED。 | 断言业务错误特征；导入/属性异常和偶然字符串均不算有效 RED。 | collab/20260827-三方对比战役/notes.md |
| V12 | 对尚不存在的模块 API，AttributeError 被当作可读的 TDD RED。 | 先用显式存在性断言形成业务可读 RED。 | collab/20260827-三方对比战役/notes.md |
| V13 | 会 chdir 的评测入口在切换后才 resolve 用户相对路径，读错临时目录。 | chdir 前冻结并验证所有用户路径；测试至少覆盖一次相对路径端到端运行。 | collab/20260902-A测缺失补偿/notes.md |
| V14 | 随机测试固化某 Python 版本的 PRNG 字面序列，跨运行时出现伪失败。 | 断言复现关系、边界和统计行为，不把版本相关序列作为生产契约。 | collab/20260902-A测缺失补偿/notes.md |
| V15 | 核验脚本把"范围标记"按逐整数字面断言，对压缩表示产生假阴性。 | 验证断言必须匹配被验对象声明的表示语义，不得把范围标记按逐值文本误检。 | collab/20260902-坑台账初版/notes.md |
| V16 | 全文子串清点把正文提及误计为条目标题，库存数虚高。 | 结构化文档清点用标题锚定模式（`^#{3,6}...`），正文引用/摘要不计入。 | collab/20260902-坑台账初版/notes.md |
| V17 | 在 I/O 未调优环境下测的 batch bench（bs=1 最快）被固化为长期配置决策，环境修复后未复测。 | 影响长期配置的性能 bench 必须在 I/O 合同达标环境下测；环境改变后旧 bench 结论过期，须复测再定档。 | collab/20260827-三方对比战役/notes.md |
| V18 | 冒烟脚本验证行查 `out/` 但 `--compensator` 自动把输出改到 `out_capr/`，训练成功被记 fail.flag 假失败。 | 验证断言的产物路径必须与代码实际输出路径推导一致（含自动后缀），断言前先打印实际输出目录。 | collab/20260902-NPJ-GPU合同/notes.md |
| V19 | 固定 warmup 窗口的门禁不感知被监控进程生命周期，正常提前完成的短训练被结束后的空闲采样拉低中位数误杀。 | 采样类门禁必须 watch 目标进程存活，进程早退时按其真实退出码判定，不用采样统计裁决。 | collab/20260902-NPJ-GPU合同/notes.md |
| V20 | 同一工作树多战役并行，回归基线取 git HEAD 会把另一战役的等价重构（surv_heads 批量路径 3.6e-7）误判为本单回归失败。 | 回归基线取本单派发前工作树快照；等价重构用 allclose(1e-6) 而非 torch.equal。 | collab/20260902-A测缺失补偿/notes.md |
| V21 | 单 seed 冒烟的正向信号（+0.02）在 5 seeds 下翻转为 1:4。 | 冒烟只判通/不崩；效果方向必须 ≥5 seeds 严格 `>` 计数。 | collab/20260902-A测缺失补偿/notes.md |
| V22 | `cmd \| tail; echo $?` 取到的是 tail 的退出码，掩盖真实失败。 | 取退出码禁止管道，或用 PIPESTATUS。 | collab/20260902-A测缺失补偿/notes.md |
| V23 | 判定报告手算派生数字（胜负计数/Δ中位/中位差混用/平局计负/抄错基线中位）在两份报告中重复出错，均被 decision-reviewer 重算抓出。 | 进结论的数字必须来自脚本生成的留档表并可指回文件行；成文前跑对账脚本；平局规则显式声明。 | collab/20260902-A测缺失补偿/notes.md |
| V24 | 外部 CLI 的测试替身按 Python dest 名拼参数（`--out_dir`），与真实解析器的 `--out-dir` 不符，接力测试 exit 2 假失败。 | 测试替身的参数名逐项从真实解析器镜像抄写，不按 dest 名反推命令行拼写。 | collab/20260902-A测缺失补偿/notes.md |
| V25 | 测试按 `ALL_GRIDS` 插入顺序断言 JSON keys，而生产 `_atomic_json_dump(sort_keys=True)` 按字母排序，把表示顺序当业务语义导致假失败。 | JSON mapping 验收断言键集合相等与字段值，只有格式契约明文规定顺序时才断言顺序。 | collab/20260902-A测缺失补偿/notes.md |
| V26 | matplotlib SVG 默认写入 `<dc:date>` 与随机 `svg.hashsalt` 生成的 clip id，同图两跑字节不同，"确定性"断言假失败；只设 `metadata={'Date': None}` 仍不够。 | 绘图脚本首部固定 `rcParams['svg.hashsalt']` 并保存时传 `metadata={'Date': None}`；确定性定义为同机连跑两次字节一致，不跨机器/引擎比字节。 | collab/20260902-A测缺失补偿/plan.md 单 ε 审查 |
| V27 | 修订版报告标"r(n−1) 不变"的段落实际按记忆复述并删了限定语（两轮 reviewer 各抓一次），且把共享中间臂的两个配对Δ中位当可加份额分解。 | "不变/原文保留"必须由 diff 证明逐字相同、删改必进修订记录；两分量共享中间臂时只做方向判定，禁止 "X% 来自 A" 式分解；成文前先列上一版闭合项保留清单逐项勾选。 | collab/20260902-A测缺失补偿/notes.md |
| V28 | 格式契约同时要求"每臂块尾随空行"与"文件无末尾换行"，最后一块上两者互斥，落盘文件多出末尾换行。 | 块级与文件级格式约束冲突时以文件级为准，序列化前裁掉尾部空元素，并用 `open(...,"rb").read().endswith(b"\n")` 实测而非目视。 | collab/20260902-A测缺失补偿/notes_eps_opus.md |
| V29 | 图形交付只核对 figsize/dpi/像素尺寸与元素集合，x 轴刻度标签实际首尾相接、`rna_100` 被挤成 `ma_100`。 | 图形验收除机器断言外必须对刻度标签/图例/图注做一次裁图目视复检，并把"刻度间距 px vs 标签估算宽度 px"当硬指标算一次。 | collab/20260902-A测缺失补偿/notes_eps_opus.md |
| V30 | `git ls-files`/`git status` 对含非 ASCII 的路径默认加引号并转义（core.quotePath），`grep -c '\.log$'`/`'\.pyc$'` 这类按行尾匹配的门禁会把中文目录下的文件全部漏计（249 个 log 只计到 1）。 | 涉及路径过滤/计数的 git 命令一律加 `-c core.quotePath=false`，并用一个已知存在的样本文件做正样本自检。 | collab/REVIEW_PACK（20260906 归档） |
| V31 | 评测侧填充开关的对拍只用了无自然缺失的 BLCA（none 格点逐位一致即判通过），全量后才发现 BRCA/LUAD/LGG/UCEC 的 test 集有自然缺失，`none` 格点也会因填充而变化，自检脚本按"应为 0"写错。 | 对拍样本必须同时覆盖"填充会触发"与"不会触发"两类（含有自然缺失的癌种）；任何"应为 0"的自检先核对数据里是否存在天然触发条件。 | collab/20260902-A测缺失补偿/notes.md（20260906 E0m） |
| V32 | 消融臂删掉带参数模块（如 GatedFusion）后不再消耗其初始化随机数，同 seed 下共享层初始化与后续 shuffle/dropout 随机流都变了：「同 seed 配对」只是协议配对，不是初始化配对。 | 报告里写明配对口径；需要初始化配对时让消融分支消耗同样的 RNG（构造后丢弃）并用测试断言共享 state_dict 逐位相同；否则靠 seed 数量平均随机性。 | collab/20260906-NPJ-D消融/审查/adversarial-review-findings.md |

## 监控与运维

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| M1 | 手工估计 notes 时间戳，使过程档案时间晚于真实执行时间。 | 每次追加阶段标题前运行 `date '+%Y-%m-%d %H:%M:%S %Z'`，禁止估时。 | collab/20260827-三方对比战役/notes.md |
| M2 | 并发范围审计把旧 mtime 快照和错误相对路径误报为最终工作区状态。 | 证据标明审计时点并区分本执行流与全局状态；使用根相对或绝对路径。 | collab/20260827-三方对比战役/notes.md |
| M3 | kill tmux 外层 bash 误杀整个进程组，且瞬时速度把剩余时长严重高估。 | 操作前用 `ps -o pgid` 查信号传播；需保活用 setsid/disown；按已完成单元实测均值估时。 | collab/20260826-NPJ三模态复现/notes.md |
| M4 | GPU 瞬时空闲被当作全场停机，漏杀 lane runner 后实验复活并双写 unit。 | 以 `pgrep -af "queue|run_method|main.py"` 全空判停机；删除 `.claim` 前确认 runner 全死。 | collab/20260827-三方对比战役/notes.md |
| M5 | 部署评估器未核对模式互斥、root 推导和输出白名单，跨机连续失败。 | 部署前读 root/白名单逻辑，保持源仓库相对深度，评估输出放 baselines 树外。 | collab/20260827-三方对比战役/notes.md |
| M6 | Claude 进程重启后 Monitor/后台任务全部 stopped，训练/评测无人盯。 | 会话恢复第一动作：盘点 flags/pgrep 后重挂哨兵。 | collab/20260902-A测缺失补偿/notes.md |
| M7 | 产出留档表/对账数字的脚本只写在 scratchpad，进程重启后 scratchpad 清空，脚本随之丢失，只能从会话记录逐字找回。 | 任何生成留档表/数字的脚本写完立即复制进战役目录 `tools/`，与留档表同目录同提交。 | collab/20260902-A测缺失补偿/notes.md |
| M8 | 多阶段战役只部署当步用到的脚本，接力阶段脚本（launch_e1_seeds.sh/run_dm.sh）留在本地，收官接力时才发现缺文件。 | 部署以战役 `tools/` 目录全量 md5 对比为准；每个接力脚本发车前先远端 `--dry_run`。 | collab/20260906-NPJ-D消融/notes.md |

## 合并映射

- `20260826-NPJ三模态复现/notes.md`：PM `40` 与 `result.md` PM `376` 同为只读审核越界 → S4；PM `76` → M3。`result.md` PM `369` → E1。
- `20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md`：首份 P0 行 `59/61/63/65` → V1/D13/V2/V3；P1 行 `69/71/73/75/77/79/81/83` → D2/D3/V4/V5/V6/D4/D5/D6；P2 行 `87/89/91/93` → V7/D8/M4/D7。其逐字重复副本行 `108–142` 依相同行号顺序合并到同一 ID。
- `20260827-三方对比战役/notes.md`：PM `51、462` → S1；`84` → V8；`90` → C1；`104` → D1；`134` → E2；`151、479` → S2；`181` → V9；`195` → M1；`218` → M2；`252` → V10；`266` → V11；`279、286、429` → E3；`293` → D10；`300` → E4；`330` → V12；`344` → D9；`359` → E5；`384` → E6；`391` → E7；`398` → C2；`405` → C3；`455` → D12；`493` → M4；`523` → D11；`555` → C5；`561` → M5。
- `20260827-三方对比战役/result.md` 的全部 11 条 PM 均为 notes 转载：`400→S1`，`727→E2`，`734→S2`，`929→V9`，`1116→V10`，`1243→D9`，`1328→E5`，`1677→E6`，`1684→E7`，`1691→C2`，`1698→C3`；不重复入账。
- `20260828-A测缺失补偿/` 已扫描全部 `.md`（`notes.md`、`plan.md`）：无 `### Bug Post-Mortem`；不产生原始 PM 映射。
- `20260902-A测缺失补偿/notes.md`：PM `20、279` → E10（`279` 为 tqdm 展示依赖截断 RED 的同一根因，另一次出现）；`45` → V13；`63` → S3；`92、160` → C4；`99` → E8；`132` → E9；`167` → V14；`195` → E11；`202` → S5；`286` → E15；`302` → E1（发车器把 PyYAML 作顶层硬依赖阻断 dry-run，缺 PyYAML 截断断言的同一根因，另一次出现；修复为惰性导入+标准库 fallback）；`309` → E16；`325` → V24；`332` → V25；`368` → D14；`373` → V20；`378` → V21；`383` → E12 与 V22；`388` → E13；`392` → C12 与 M6；`404` → D15；`410` → D16；`418` → E14；`435` → V23。`result.md` 仅摘要转载这些问题，未含独立 PM，故不重复入账。
- `20260902-NPJ-GPU合同/notes.md`：PM `15` → V18；`102` → V19；`76` → E9（Torch Dynamo 对无 `__spec__` 模块替身的同一根因，另一次出现）；`88` → S1（导入生产模块在源码旁写 `.pyc` 的同一根因，非 `py_compile` 触发）。C11 出自该文件正文裁决记录，无对应 PM 标题。
- `20260902-A测缺失补偿/notes.md`（20260905 续扫，9-03/9-04 新增段）：PM `446` → C14；`459` → M7；`477` → C13；`484` → C10（实测修订，出处列已含）；`500、510` → V27（同一 ID 已合并这两处出现）。
- `20260902-A测缺失补偿/notes_eps_codex.md` / `notes_eps_opus.md`（A/B 首单双引擎过程档）：codex PM `118` → C15；opus PM `347` → V28、`354` → V29；E18 出自 codex 文件正文环境记录，无对应 PM 标题。
