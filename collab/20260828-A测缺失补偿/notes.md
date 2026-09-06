# 执行记录

## 2026-09-01 23:46:34 JST — α 单启动、边界与现状

- 已完整读取 `plan.md`；本轮仅执行 α 单，β 单不启动。
- 用户明确指定当前工作区与文件白名单，因此不创建 worktree；禁止 `git commit/push`、`ssh/scp`、训练与 GPU 任务。
- 根仓库已有 `collab/monitor/routine-sweep.md` 修改及其他未跟踪产物；`NPJ/` 内层仓库当前 clean。所有既有状态均不触碰、不回退。
- 当前分支为 `main`；用户已明确要求在本工作区执行已批准的 `plan.md`，因此将该指令视为当前分支实施授权，但提交权仍归 Claude 与用户。
- `NPJ/scripts/dual_metric_eval_s4.py` 在当前仓库及本机工作区均不存在；找到同仓库参考 `collab/20260826-NPJ三模态复现/dual_metric_eval.py`，其中 A/B 风险公式分别为 raw logits 与 sigmoid 后累积。
- 默认 Python 3.13 缺少 `pandas/numpy/torch`；已有 `protomasksurv-exp1` 环境含 `torch/pandas/sklearn/pytest`，但缺 `sksurv/tqdm/transformers`。manifest 脚本必须保持标准库可运行；合成测试使用 CPU 环境；真实 c-index 依赖不以伪实现替代。
- `labels_424_ex12.csv` 共 4985 行，BLCA test=138；五癌 test 数分别为 BLCA=138、BRCA=383、LUAD=172、LGG=166、UCEC=198。
- 13 格点解释固定为一个共享无缺失基线 `none_r0`，加三种 mode 各自的 25/50/75/100 四档，共 1+3×4=13；避免重复计算三个数值等价的 rate=0。

## 2026-09-01 23:49:12 JST — 改动前默认行为基线

- 在临时目录构造 3 名 BLCA 患者、3 模态合成特征，以不带新增参数的 `TCGASurDataset(...)` 构造 test dataset；仓库 `tmp_sur_cache/` 未被读写。
- 对 3 个样本全部 tensor 的键名、dtype、shape 与连续字节按固定顺序汇总，得到 `PRE_DEFAULT_DATASET_SHA256=169be29fe3ac79c3c15dc80064bc3962f15338c4e42330f5d7073c70e5bb4d20`，样本数为 3。修改后必须用同一夹具得到完全相同摘要。

