# configs：共享配置

存放跨实验复用的模型配置与运行配置；单个创新点的特有参数放在对应实验的 `config.yaml`。

## 内容索引

| 路径 | 用途 |
|---|---|
| [models/](models/) | 共享模型的结构与输入配置 |
| [gpu_train.yaml](gpu_train.yaml) | GPU 运行及门禁相关配置 |
| [refactor_defaults.yaml](refactor_defaults.yaml) | 重构预检配置，含 CPU、输入占位和审批状态 |

## 使用规则

配置文件表达设定值；每次运行的真实生效参数以 `results/<run_id>/resolved_config.yaml` 为准。显式命令行参数可覆盖配置，具体支持项以入口解析器为准。历史未知参数不能补写成已确认值。

配置文件存在不代表实验已获准运行；预检默认也不等于正式训练协议。配置解析实现见 [config.py](../src/trimodalsurv/config.py)，实验参数入口见 [experiments/](../experiments/README.md)。

[返回项目首页](../README.md) · [项目状态](../STATUS.md)
