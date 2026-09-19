# 等价加速阶段记录

| 项目 | 当前证据 |
|---|---|
| 旧正式批次 | 已按用户授权停止，退出143；7格valid保留，无test |
| 新目录 | `/home/wuhao/npj_rules15_accel_20260916_Ob6fjB` |
| 完整回归 | 50条通过，无跳过；`acceleration-regression-r2.log` |
| 五癌真实对拍 | 20格，25名valid患者，各61候选；`acceleration-parity-complete.json` |
| 输出等价 | donor审计与预测数组逐元素一致，模型state_dict不变 |
| 资产 | 74项哈希执行前后相同；36项源码哈希对应新用户豁免 |
| 评测段测速 | 旧563.592862秒，新119.383877秒；仅对拍样本，不是正式全批次耗时 |
| 正式重跑 | 调度PID3466335已退出1；2026-09-16 13:32:41 UTC进入preflight后，因GPU4存在其他计算进程被门禁阻断；valid/test均未启动 |

## 尚待完成

- 新批次前置检查及冒烟。
- 6100条valid读数与6协议冻结。
- 单次test共900条读数。
- 最终独立复算、三个结果报告及postcondition。

不将局部对拍通过或调度进程启动写成正式评测完成。

## 当前资源阻断

- 连续三轮核验 tako 八张卡均有其他计算进程；本批次没有运行中的 valid/test 进程。
- 已询问用户：继续等待 tako，或允许检查并迁移到 hitode/landau；尚未收到选择。
- 真实对拍原始预测、审计、通过记录及失败日志已回传本机 `acceleration-verification-evidence.tar`（约21MB）。
- 任务未完成；需空卡或新的资源安排后恢复。不得把占用卡瞬时 GPU-Util=0 当作空卡。
