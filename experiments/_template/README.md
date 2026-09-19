# 实验模板（未初始化）

状态：仅目录与职责占位，没有已确定模型或运行结果。

先确认数据、任务、已有资产、模型/创新机制是否确定、环境与写入范围；不得从本模板推定超参数或正式运行权限。完整约定见 [通用初始化模板](../../docs/templates/experiment-oriented-ml-template.md)。

- [model.py](model.py)：机制确定后填写实际创新算法；当前调用明确抛出 `NotImplementedError`。
- [config.yaml](config.yaml)：当前为空映射；只写获准的实验覆盖项。
- [知识索引](knowledge/index.md)：机制与证据入口。
- [结果索引](results/index.md)：尚无运行，不创建假 run_id。

一个创新点一个目录，公共代码从 `src/<package>/` 复用。复制前确认新实验标识与包名，同名目录不得覆盖。初始化不安装依赖、不下载、不训练。
