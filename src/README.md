# src：项目公共源码

存放可被多个实验复用的 Python 包。当前公共包为 [trimodalsurv/](trimodalsurv/README.md)。

## 职责边界

- 数据读取、公共模型、训练和评测能力放在公共包。
- 某个创新点独有的算子放 `experiments/<ID>/model.py`，通过组合使用公共能力。
- 公共包不反向导入具体实验，也不从历史归档读取实现。

## 阅读入口

先看[包内模块说明](trimodalsurv/README.md)，再按数据、模型、训练、评测路径阅读。公共启动入口在 [scripts/](../scripts/README.md)，共享配置在 [configs/](../configs/README.md)。

目前以项目 checkout 方式使用；模块可导入不等于所有运行依赖已安装，具体环境按对应实验说明核对。

[返回项目首页](../README.md) · [项目状态](../STATUS.md)
