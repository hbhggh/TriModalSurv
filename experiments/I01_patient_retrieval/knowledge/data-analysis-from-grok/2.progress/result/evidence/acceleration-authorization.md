# 推理加速授权与旧批次停止记录

- 用户明确选择：暂停并加速：缓存复用＋GPU 批量检索，验证后重跑。
- 科研协议、25 份权重、原缓存、split、float64 相似度、padmask、候选域及并列规则不变。
- 旧批次：`/home/wuhao/npj_rules15_formal_20260916_R0Q4Fg`。
- 已核实目标：supervisor PID 3305871，valid PID 3319348；只对 valid PID 发 TERM。
- 停止后两 PID 均不存在，supervisor 记录退出码 143；stage 日志只有 preflight、smoke、valid，没有 test。
- 保留全部旧文件；7 个完整 valid 格点仅作为旧版一致性证据，不混入新正式结果。
- 修改前源码快照：`acceleration-before.tar`。
- 新代码必须新指纹、新运行目录、新 preflight/冒烟；donor 和输出一致性验证通过后才重跑 valid。
- 原用户 Claude 再审豁免保留，但须重新绑定实际加速版本源码；不得伪造 Claude PASS。

## 实施进度

- 新隔离目录：`/home/wuhao/npj_rules15_accel_20260916_Ob6fjB`。
- 新增 `acceleration.py` 的 float64 候选批量余弦内核，以及 `tests/test_acceleration.py`。
- 旧版 RED：3 条测试均因缺少批量实现失败；新内核 CPU 3 条测试通过。
- GPU 合成共同有效行余弦通过，结果 `[1.0, 0.8]`、float64。
- 已完成候选打分缓存和生产推理接线；新增缓存隔离、重复查询、返回副本等测试，各自先 RED 后 GREEN。
- tako `tcga_env` 执行新目录完整回归：49 条通过、无跳过；包含真实 NPJC 合成前向。
- 新引擎一次性比较 GPU 与原 NumPy float64 归约，最终选择保留原归约结果，避免 GPU 舍入改变近并列 donor；核对结果也缓存复用。
- 尚未完成：五癌真实 donor/输出对拍、端到端测速、新指纹门禁和正式重跑。上述合成通过不等于已完成加速交付。

### Bug Post-Mortem
- **现象**：模型前向在 GPU，但 valid 网格运行缓慢；检查时 CPU 约 375%，GPU 采样利用率 0%。
- **根因**：检索在 NumPy/Python 双层患者循环中执行；固定 key、相似度及 donor 随多个 λ/w 和 seed 被重复计算。仅模型合成前向测速未覆盖端到端检索瓶颈。
- **修复**：已停止旧批次并留存证据；缓存复用和 GPU 批量检索尚待实现和验证，不能宣称已加速。
- **Prevention Rule**：网格评测上线前同时计时检索准备、模型前向和落盘；固定检索量只算一次，复用必须绑定患者内容、split、候选域及规则参数；优化必须做 donor 与输出对拍。

### Bug Post-Mortem：配置形状表示
- **现象**：真实 BLCA/text_100 对拍报“非法 query RNA”，未启动正式加速批次。
- **根因**：配置 shapes 的值是 list，数组 shape 是 tuple，直接比较把相同尺寸误判为不同；合成夹具原先只覆盖 tuple。
- **修复**：比较时规范化为 tuple；补充真实配置 list 形状的联合检索回归，先复现失败再修复。
- **Prevention Rule**：形状校验使用规范化维度序列，夹具同时覆盖配置反序列化的 list 和 NumPy 的 tuple，不能只测构造器自动推断形状。
