# 正式零训练评测进度

| 项目 | 当前证据 |
|---|---|
| 用户授权 | formal-user-approval.md；明确批准正式实验及本次Claude豁免 |
| 豁免绑定 | formal-user-waiver.json；绑定35项源码、协议、valid/test阶段、授权文件SHA |
| 门禁变更 | runtime.py新增独立用户豁免分支；默认Claude审核路径仍保留，未伪造PASS |
| 门禁测试 | 本机失败先行；远端新44项测试通过；旧68项上一轮通过，公共代码未改 |
| 远端批次 | /home/wuhao/npj_rules15_formal_20260916_R0Q4Fg/result |
| 监督进程 | PID3305871，execute_formal.sh；阶段失败即退出，不自动重启 |
| 当前状态 | 2026-09-16 12:49:34 UTC：preflight和GPU冒烟均通过，正式valid已启动；valid完成并冻结后自动进入一次test |
| 实际阶段进程 | valid PID3319348，监督PID3305871；启动日志formal-stages-snapshot.log |
| GPU探测 | batch383、120秒、585次前向、峰值1456679936字节、利用率中位数59%，无需低利用率豁免 |
| 科研口径 | 五癌五seed四场景，58 valid候选，冻结六协议后900 test记录；不改科学网格 |
| 停止边界 | 完整结果与报告后停止；无训练，不根据test更改规则或选参 |

- GPU最大实际查询队列为BRCA/test的383人；batch_size=383，不为超过队列大小的空批探OOM。
- GPU探测只用合成输入、原BRCA/123权重，不计算C-index；正式valid/test共用同设备和同batch配置。
- precondition.md存在用户侧格式编辑，本轮保留；当前授权以本记录及formal-user-approval.md为准。
