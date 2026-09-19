# 用户最新执行边界

- 用户原文：回 tako 继续，保持原容差不变，如果GPU还是满了的话，只在taKO中等待闲置的GPU出现。
- 只使用 tako；不再迁移 hitode/landau，不放宽数值容差。
- 复用 tako 原加速候选、配置及原机逐值一致的对拍证据；检查源码与资产哈希后才执行。
- hitode 跨硬件失败证据完整保留；不得伪造通过或将其与 tako 结果混合。
- 本次日志独立命名 tako-resume-*，不覆盖旧 GPU 占用导致的失败日志。
- 仅资源满载时等待；科学/数值门禁失败仍停机报告，不自动放宽。

## 启动证据

- tako GPU4复查：3MiB显存、0%利用率、无计算进程。
- 本次恢复进程：bash PID3553353，flock PID3553352；已确认存活并进入preflight。
- 原容差、原源码、原科研配置均未修改；启动脚本重新核对原机对拍的源码/资产指纹及用户授权。
- 阶段日志：tako:/home/wuhao/npj_rules15_accel_20260916_Ob6fjB/result/evidence/tako-resume-stages.log。
- 自动跟进ID i01-hitode沿用但名称/内容已改为tako-only；不得依据旧名称迁移服务器。
- 当前仅为恢复启动证据，不代表完整valid/test完成。

## 第二次资源接力

- 第一轮恢复完成 preflight 与20格 smoke，SMOKE_PASS；valid 初始化时 GPU4被其他进程占用，按门禁退出1，未创建正式 valid/test。
- 后续连续两次复查 GPU4：3MiB、0%、无计算进程；确认旧任务已退出后，仅续跑 valid/test。
- 新脚本 execute_tako_resume_r2.sh；bash PID3618545，flock PID3618544；日志 tako-resume-r2-*，旧日志保留。
- 科研配置、权重、缓存、原容差不变；仍只在 tako 等待/运行。
