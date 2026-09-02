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
| C10 | `--fresh` 实为空操作（源码不消费该 flag），"升权靠 --fresh"是幻觉。 | 升权=不带 `--resume-last` 开新会话并首启 `--write`；`--fresh` 可省略。 | CLAUDE.md（20260902 调查固化） |

## 沙箱与权限

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| S1 | 裸 `py_compile` 即使设 PYTHONDONTWRITEBYTECODE 仍会在源码旁写 `.pyc`，越出白名单。 | 语法检查优先内存 `compile()`；必须写缓存时设 PYTHONPYCACHEPREFIX 到白名单 scratch。 | collab/20260827-三方对比战役/notes.md |
| S2 | 用 `rm -rf` 清理已核对的 scratch 缓存仍会被安全策略拒绝。 | 缓存优先写 `/private/tmp`；清理用精确目标的可恢复移动或逐文件删除，不递归强删。 | collab/20260827-三方对比战役/notes.md |
| S3 | JavaScript 模板正文含未转义 Markdown 反引号，命令封装在执行前被截断。 | 模板正文不放未转义反引号；复杂文本改用安全参数或无反引号前缀。 | collab/20260902-A测缺失补偿/notes.md |
| S4 | 被限制只读的交叉审核 Agent 在仓库根创建白名单外文件。 | 严格白名单任务不委派会落盘的通用审核；必要时前后比较完整 Git 状态，越界即中断并恢复基线。 | collab/20260826-NPJ三模态复现/notes.md |

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

## 监控与运维

| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |
|---|---|---|---|
| M1 | 手工估计 notes 时间戳，使过程档案时间晚于真实执行时间。 | 每次追加阶段标题前运行 `date '+%Y-%m-%d %H:%M:%S %Z'`，禁止估时。 | collab/20260827-三方对比战役/notes.md |
| M2 | 并发范围审计把旧 mtime 快照和错误相对路径误报为最终工作区状态。 | 证据标明审计时点并区分本执行流与全局状态；使用根相对或绝对路径。 | collab/20260827-三方对比战役/notes.md |
| M3 | kill tmux 外层 bash 误杀整个进程组，且瞬时速度把剩余时长严重高估。 | 操作前用 `ps -o pgid` 查信号传播；需保活用 setsid/disown；按已完成单元实测均值估时。 | collab/20260826-NPJ三模态复现/notes.md |
| M4 | GPU 瞬时空闲被当作全场停机，漏杀 lane runner 后实验复活并双写 unit。 | 以 `pgrep -af "queue|run_method|main.py"` 全空判停机；删除 `.claim` 前确认 runner 全死。 | collab/20260827-三方对比战役/notes.md |
| M5 | 部署评估器未核对模式互斥、root 推导和输出白名单，跨机连续失败。 | 部署前读 root/白名单逻辑，保持源仓库相对深度，评估输出放 baselines 树外。 | collab/20260827-三方对比战役/notes.md |

## 合并映射

- `20260826-NPJ三模态复现/notes.md`：PM `40` 与 `result.md` PM `376` 同为只读审核越界 → S4；PM `76` → M3。`result.md` PM `369` → E1。
- `20260826-NPJ三模态复现/审查/codex-对抗审查报告-20260826.md`：首份 P0 行 `59/61/63/65` → V1/D13/V2/V3；P1 行 `69/71/73/75/77/79/81/83` → D2/D3/V4/V5/V6/D4/D5/D6；P2 行 `87/89/91/93` → V7/D8/M4/D7。其逐字重复副本行 `108–142` 依相同行号顺序合并到同一 ID。
- `20260827-三方对比战役/notes.md`：PM `51、462` → S1；`84` → V8；`90` → C1；`104` → D1；`134` → E2；`151、479` → S2；`181` → V9；`195` → M1；`218` → M2；`252` → V10；`266` → V11；`279、286、429` → E3；`293` → D10；`300` → E4；`330` → V12；`344` → D9；`359` → E5；`384` → E6；`391` → E7；`398` → C2；`405` → C3；`455` → D12；`493` → M4；`523` → D11；`555` → C5；`561` → M5。
- `20260827-三方对比战役/result.md` 的全部 11 条 PM 均为 notes 转载：`400→S1`，`727→E2`，`734→S2`，`929→V9`，`1116→V10`，`1243→D9`，`1328→E5`，`1677→E6`，`1684→E7`，`1691→C2`，`1698→C3`；不重复入账。
- `20260828-A测缺失补偿/` 已扫描全部 `.md`（`notes.md`、`plan.md`）：无 `### Bug Post-Mortem`；不产生原始 PM 映射。
- `20260902-A测缺失补偿/notes.md`：PM `20` → E10；`45` → V13；`63` → S3；`92、160` → C4；`99` → E8；`132` → E9；`167` → V14。`result.md` 仅摘要转载这些问题，未含独立 PM，故不重复入账。
