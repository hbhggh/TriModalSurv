# tests：公共回归与接口验证

验证共享模块、配置解析和运行产物约定，帮助发现重构造成的行为变化。

## 内容索引

| 测试 | 主要覆盖 |
|---|---|
| [test_bin_mode.py](test_bin_mode.py) | 时间分箱模式 |
| [test_mean_fusion.py](test_mean_fusion.py) | 均值融合行为 |
| [test_shared_config.py](test_shared_config.py) | 公共配置解析 |
| [test_experiment_presets.py](test_experiment_presets.py) | 实验预设与参数覆盖 |
| [test_script_dispatch.py](test_script_dispatch.py) | 脚本分发与初始化顺序 |
| [test_run_provenance.py](test_run_provenance.py) | 运行参数、来源与产物记录 |
| [test_gitstamp.py](test_gitstamp.py) | commit 身份、拒跑门、无 `.git` 拷贝的 stamp 与可重建账本 |
| [test_shared_runtime_main.py](test_shared_runtime_main.py) | 公共主流程的受控产物写入与冲突拒绝 |
| [test_workflow_scripts.py](test_workflow_scripts.py) | Git 工作流脚本（临时仓库）：`cleanup` 冻结身份核对、`CODE_PATHS` 代码范围干净门（论文与笔记不阻塞，代码脏改动拒绝）、`freeze --candidate` 候选绑定（H 须在 main 上且之后代码范围无改动；`CODE_PATHS` 缩窄与排除型 pathspec 都不能绕过）、CI 期间并发提交时 candidate 拒绝、打完 tag 后被信号中断仍保留完整冻结、`candidate` 只许在检出 main 的主目录运行、同名 freeze / wt-add 并发互斥（受控屏障）与残留锁拒绝、`freeze` / `wt-add` 中途失败的回滚（故障注入：建 worktree、建链接、stamp、打 tag 各步）、run 级 stamp（真实 gitstamp 模块，不可覆盖，记录候选 H 与冻结提交）、`--link-assets` 链接回归（只摘链接、主目录目标完好、真实 checkpoint 与被篡改链接拒绝）、`wt-add` → `merge --ff-only` → `wt-rm` 闭环、`ci.sh` 参数先于副作用、`gitflow.sh` 帮助路径、bash 3.2 多字节变量名 |

## 验证边界

实验专有测试位于对应 `experiments/<ID>/tests/`。先核对测试需要的环境和依赖，再运行对应范围；测试通过不代表真实数据全量训练或 GPU 行为通过。

受控合成测试、真实 checkpoint 对拍和正式科研实验分别记录，不混用结论。历史重构验收证据见 [docs/refactor/](../docs/refactor/)，正式实验启动规则见 [AGENTS.md](../AGENTS.md)。

[返回项目首页](../README.md)
