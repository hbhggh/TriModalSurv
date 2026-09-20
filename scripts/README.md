# scripts：公共运行入口

存放连接共享代码与实验实现的启动、评测和门禁脚本。创新算法放实验的 `model.py`，公共计算逻辑放 `src/trimodalsurv/`。

## 内容索引

| 文件 | 用途 |
|---|---|
| [train_launcher.py](train_launcher.py) | 按实验清单组织训练任务；支持 dry-run 核查 |
| [main_survival.py](main_survival.py) | 生存任务入口与实验分发 |
| [eval_missing.py](eval_missing.py) | 缺失模态评测入口 |
| [gen_missing_manifest.py](gen_missing_manifest.py) | 生成缺失设置清单 |
| [launch_formal.sh](launch_formal.sh) | 正式运行门禁入口 |
| [gpu_util_gate.py](gpu_util_gate.py) | GPU 利用率门禁检查 |

## 使用规则

先读所属[实验 README](../experiments/README.md)确定配置、输入和输出目录；参数以各脚本实际支持项为准。正式训练经 `train_launcher.py` 和受管任务发起，启动前核对 dry-run，仍需 Claude 审查与用户授权，见 [AGENTS.md](../AGENTS.md)。

新结果写入所属实验的新批次；不要覆盖旧结果或改写现有缓存。本地入口更新不代表远端部署已经同步。

[返回项目首页](../README.md) · [项目状态](../STATUS.md)
