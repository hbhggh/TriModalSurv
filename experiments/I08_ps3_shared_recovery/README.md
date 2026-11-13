# I08：PS3-style 骨架上的 Shared-only 患者级恢复（A1 + B1 + C1）

故事线 A-1 v1（主目录 `03_index-故事线 A-1｜患者级动态恢复_v1.md`）：冻结 I07 三模态骨架，在 pooled 与风险头之间接入
A1 低秩正交共享基、B1 按缺失模式的线性恢复，训练期用 C1（模态对齐 + 恢复一致性）约束。完整输入直通原 I07。

| 文件 | 内容 |
|---|---|
| `interface.md` | 接入位置、张量接口、七场景路由、梯度路径、静默错误守卫 |
| `config.yaml` | 维度、类型、位置、训练策略与候选网格；键与类型由 `contract.py` 强制 |
| `contract.py` | 配置核对、缺失模式枚举、参数量、符号形状核对、风险头拼接、I07 冻结检查 |
| `tests/test_contract.py` | 契约单测（含与 I07 fill 路径逐值一致） |
| `operators.py` / `losses.py` | A1 / A5、B1、B3、B5、B6-LOO、B0 / C0 Ridge；C1 与 Cox 损失 |
| `cache.py` | Step 1：冻结 I07 导出 7 视角 pooled 缓存（train / val，D0 守卫，sha256 manifest） |
| `train_eval.py` | Stage 2a / 2b、M0–M10 全部方法、val 评测与报告（`run` / `report`） |
| `interpretability.py` | handoff §6.2 机理与三项可解释性核验 |
| `tests/test_operators_and_b6.py` 等 | 正交性、α_max=0 退化、反事实防泄漏、L_cons 梯度、Ridge 精确留一、端到端冒烟 |

状态（2026-11-08）：已实现 handoff v1 全部算子与 M0–M10；开发期 val 实验，未访问 test。框架图在主目录 `index.excalidraw`（PS3 frame 右侧新 frame）。
