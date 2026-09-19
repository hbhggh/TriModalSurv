# 推理核心实现报告

时间：2026-09-16 19:04:30 JST

## 状态与边界

- [确定] 已实现 `inference.py`、五个规则目录的真实算法、`tests/test_rules.py`。
- [确定] 未改公共源码、缓存、权重或旧结果；公共三文件 SHA-256 与根配置冻结值一致。
- [确定] 未训练，未运行 valid/test，未产生 C-index。
- [未验证] 真实 NPJC/Torch parity 等待主 Agent 在远端 CPU 环境执行；本机无 Torch，测试明确失败而非 skip。

## 实现摘要

- `prepare_batch(...)`：固定基线原样调用 `FixedPatientBank.compensate(query_split=...)`；新候选逐患者执行规则 1--5，返回独立 inputs、audit 和 `[B,3]` pool weights。
- 规则 1：`text_100` 默认整场 `m0real`；仅冻结的 UCEC 例外进入检索。
- 规则 2：有效行 mean-key、train 患者等权均值去中心、`float64` 余弦；mean-key 自身退化报错。
- 规则 3：内部点以 `float64` 计算 `mu + lambda * (donor - mu)`；`lambda=0/1` 直接复制端点并保持目标 dtype，双缺共享 donor。
- 规则 4：只在 `text_100` 且本人 RNA 天然真实可用时，以完整 RNA token mean 加权；候选必须 RNA/Text 都真实存在。
- 规则 5：保持 bool attention mask，仅替换 Transformer 末端 pooling 数值权重；不新增模型参数。
- 数字前缀规则目录由 `importlib` 按路径加载，并在 `exec_module` 前注册 `sys.modules`。

## RED 证据

命令：

```text
/Users/wuhao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 .../result/tests/test_rules.py
```

结果：exit 1；`推理核心 inference.py 尚不存在`。同一轮本机 Torch 项明确失败：`No module named 'torch'`，未设 skip。

## GREEN 与回归证据

1. 新规则 NumPy 测试：exit 0，`Ran 12 tests ... OK`。
2. 原 `test_patient_retrieval_bank.py`：exit 0，`Ran 11 tests ... OK`。
3. 原 `test_patient_retrieval_padding.py`：exit 0，`Ran 8 tests ... OK`。
4. 内存语法编译与 JSON 解析：`syntax_ok=7 json_ok=5`。
5. 完整新测试：12项通过，Torch parity 1项因本机无 Torch 失败；不据此声明当前源码的真实 NPJC 已通过。
6. 公共文件 SHA-256：
   - `experiments/I01_patient_retrieval/model.py`：`e4e08b0c9ee78da8b2a7c4d01250516693fc087bf567d18ef6a944b27cc10c13`
   - `experiments/I01_patient_retrieval/evaluate.py`：`e92812ef5316b3d0d212deda0e37793e3de84dd9b44410b25ebe7caecb658b5a`
   - `src/trimodalsurv/models/npjc.py`：`f0c03c1516a3976ca71ac5f0b8a4b752f3f98a91f44e6abb7f0edcda399eac2f`

## 真实 Torch 待核验项

- 运行 `tests/test_rules.py` 全文件，要求当前 13/13 通过，不能 skip。
- 重点核对 `w=1` 与原 NPJC logits `atol=1e-6, rtol=0`。
- 同一测试还检查 `w<1` 确实改变最终 pooling 路径，且调用前后 `state_dict` 逐 tensor 不变。
- 本报告不替代远端 CPU/GPU 设备与 dtype 证据；GPU 当前未验证。

### Bug Post-Mortem
- **现象**: 首轮本地测试在新目录及公共 `experiments/I01_patient_retrieval/__pycache__` 写入 `.pyc`，越出约定交付文件白名单。
- **根因**: 首轮命令遗漏 `PYTHONDONTWRITEBYTECODE=1`，违反已读坑台账 S1 的防写缓存规则。
- **修复**: 精确删除本轮生成的 7 个 `.pyc` 与 6 个空 `__pycache__` 目录；后续所有 Python 核验均显式设置 `PYTHONDONTWRITEBYTECODE=1`，复查无本轮 `.pyc` 残留。
- **Prevention Rule**: 严格白名单任务的首条 Python 命令即设置 `PYTHONDONTWRITEBYTECODE=1`；语法检查只用内存 `compile()`。

### Bug Post-Mortem
- **现象**: 两个旧检索测试首次用绝对文件入口执行时未加载任何业务测试，报 `No module named 'experiments'`。
- **根因**: 文件入口把 `sys.path[0]` 设为 tests 目录，命令未显式加入仓库根；这是测试启动方式错误，不是生产回归。
- **修复**: 使用同一绝对解释器并设置 `PYTHONPATH=/Users/wuhao/Desktop/TriModalSurv` 后重跑，分别 11/11、8/8 通过。
- **Prevention Rule**: 旧包测试用文件入口时同时固定 `PYTHONPATH=<repo_root>`；先核对实际执行测试数，导入失败不算业务 RED。

## 2026-09-16 19:10:34 JST 独立静态审核修复

- 审核反例：`mean=[1e20,-1e20] (float64)`、`donor=[1,-1] (float32)`、`lambda=1`，旧实现返回 `[0,0] (float32)`。
- RED：新增端点精确复制测试后，NumPy 套件 `Ran 10 tests`，仅该反例失败；另新增的规则 2 真实 padding/有效行置换与混合自然缺失拆批一致性均已先通过。
- GREEN：`lambda=0/1` 在完成形状/有限值校验后分别直接复制 mean/donor，再转为请求 dtype；NumPy 10/10、旧检索 11/11、旧 padding 8/8 通过。
- 新覆盖：规则 2 保持 128 行零后缀及原缓存不变，有效行内部置换不改 donor/分数；同一混合自然缺失 batch 与逐患者拆批的 inputs/audit/pool weights 完全一致。
- 完整套件仍只有本机缺 Torch 的 1 项明确失败；未远程运行，未新增 skip。

### Bug Post-Mortem
- **现象**: `lambda=1` 在合法极端尺度下未返回 donor；`mu=1e20`、`donor=1` 时得到 0。
- **根因**: 端点沿用通用公式 `mu + lambda * (donor - mu)`；`donor - mu` 舍入为 `-mu`，回加发生灾难性消去。
- **修复**: 完成参数、形状与有限值校验后，`lambda=0` 直接复制 mean，`lambda=1` 直接复制 donor；两者显式转换为请求 dtype，内部点仍用 `float64`。
- **Prevention Rule**: 具有数学恒等端点的数值插值必须用极端尺度反例测试，并对端点走直接复制分支，不能只用普通量级验证公式等价。

## 2026-09-16 19:13:57 JST 远端隔离路径修复

- 远端现象：隔离镜像中的 `result` 路径层级更浅，测试模块在收集阶段执行 `Path(__file__).resolve().parents[7]` 抛出 `IndexError`，11项测试均未加载。
- RED：先加入浅层 `result` 且通过 `PYTHONPATH` 指向真实仓库的解析用例，因 `_resolve_repo_root` 尚不存在而失败。
- GREEN：仓库根改为依次检查 `PYTHONPATH`、`config.paths.repo_root`、`result_root` 及其全部祖先；每个候选必须真实含 `experiments/I01_patient_retrieval/model.py`。
- 本地证据：NumPy 11/11 通过；内存语法 7/7；源码已无 `parents[7]`。完整本地 12项仍仅 Torch 依赖项失败，未设 skip。
- 边界：这次只修测试入口的路径定位；未修改 `inference.py`、规则算法或 `run.py`，等待主 Agent 同步后远端重跑。

### Bug Post-Mortem
- **现象**: 远端隔离镜像因测试文件路径较浅，在模块导入阶段抛 `IndexError`，业务测试数为 0。
- **根因**: 测试夹具把当前主仓库目录深度误当成接口，硬编码 `parents[7]` 推导仓库根。
- **修复**: 新增带存在性标记的仓库根解析器，优先使用远端已提供的 `PYTHONPATH`，再读根配置，最后安全遍历现有祖先。
- **Prevention Rule**: 可迁移测试不得用固定 `parents[n]` 推导仓库；必须从显式环境/配置定位并用真实 marker 验证，缺失时输出已检查候选后失败。

## 2026-09-16 19:18:29 JST 第二次远端夹具修复与配置消费

- 第二次远端证据：38项仅路径 fallback 测试失败；当次生产规则、真实 Torch 与 runner 合成 cell 均通过。失败测试在清空 `PYTHONPATH` 后仍假设镜像 config 的本机 `repo_root` 可用。
- 测试修复：`TemporaryDirectory` 内分别构造浅层镜像、指向已知 `REPO` 的临时 config；当环境、config、祖先均无 marker 时显式断言 `FileNotFoundError`。
- 文档修复：五个 `分析核心修改.md` 均新增 `函数｜旧行为｜新行为｜影响场景｜其他四点交互` 表，不改变规则。
- 配置消费 RED：`forward_with_pool_weights` 与 `weighted_forward` 缺少 keyword-only `non_blocking`，本地接口测试失败。
- 配置消费 GREEN：两层接口新增默认 `non_blocking=False`，并传入每个 input 的 `.to(..., non_blocking=...)`；真实 Torch 测试新增窄边界 spy，等待主 Agent 同步远端执行。
- 当前本地证据：NumPy 12/12，内存语法 7/7；五份分析表标题全部命中。完整 13 项仅本机缺 Torch 的 1 项明确失败。

### Bug Post-Mortem
- **现象**: 路径解析 fallback 测试在远端清空 `PYTHONPATH` 后失败，而解析器按合同正确报找不到仓库。
- **根因**: 测试复用了线上镜像 config，并错误假设其中用户本机绝对 `repo_root` 在远端也有效。
- **修复**: fallback 测试改在临时目录写入指向当前已知 `REPO` 的 config；无任何来源时单独断言失败。
- **Prevention Rule**: 测试配置 fallback 时必须自建完整、可用的临时配置；不得依赖部署配置中的机器绝对路径。

### Bug Post-Mortem
- **现象**: 只读文档循环首轮打印文件名后报 `sed: command not found`。
- **根因**: zsh 中 `path` 是与 `PATH` 绑定的特殊数组，循环变量名 `path` 覆盖了命令搜索路径。
- **修复**: 改用 `analysis_file` 并以绝对 `/usr/bin/sed` 重跑；未发生文件修改。
- **Prevention Rule**: zsh 脚本变量禁止使用 `path/status/home` 等特殊或系统名；任务变量使用带语义前缀的名称。

### Bug Post-Mortem
- **现象**: 根配置声明 `runtime.non_blocking=true`，规则 5 输入搬运仍调用 `.to(device, dtype)`，没有消费该配置。
- **根因**: 推理接口初版只实现 device/dtype 契约，遗漏 runtime I/O 参数从 runner 到规则函数的显式传递。
- **修复**: 公共与规则 5 forward 均新增 keyword-only `non_blocking=False`，实际传入每个 input tensor 的 `.to(...)`；runner 由主 Agent 读取根配置后调用。
- **Prevention Rule**: 根配置新增或冻结 runtime 字段时，必须从配置读取点追到最终框架 API 消费点，并用参数传播测试验证。

## 接口疑问

- 无。当前实现按 `evidence/接口契约.md` 的导出签名、模态顺序和审计字段落地。
