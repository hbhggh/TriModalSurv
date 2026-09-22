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

## 验证边界

实验专有测试位于对应 `experiments/<ID>/tests/`。先核对测试需要的环境和依赖，再运行对应范围；测试通过不代表真实数据全量训练或 GPU 行为通过。

受控合成测试、真实 checkpoint 对拍和正式科研实验分别记录，不混用结论。历史重构验收证据见 [docs/refactor/](../docs/refactor/)，正式实验启动规则见 [AGENTS.md](../AGENTS.md)。

[返回项目首页](../README.md) · [项目状态](../STATUS.md)
