
## 2026-08-27 11:08 — 巡检
[11:08] 窗口/后台巡检
运行中: task=b2ox7swrn idle=5min
卡住: task=bx79vf0nf idle=834min, task=bqjh1h2ro idle=974min, task=ab4d54ab9bc7c1dde idle=788min, task=a7adb6aa841340bb0 idle=744min, task=bntqb0c8j idle=509min
通道异常: 无（[B] status.json 11:00:02 正常；[D] 昨节 CHANNEL_DOWN 已恢复）
需要我看的: byfd83ydv（33min 前 [killed]，属近 2 小时）；landau _adhoc_gdc_fetch（dup_count=2 重复实例）

## 2026-08-27 11:45
[11:45] 窗口/后台巡检
运行中: 无（近 20 分钟内的后台任务均已 [exited with code 0]）
卡住: task=b5pyj28n8 idle=27min 尾部空；另有老会话残留无退出标记 task=bx79vf0nf idle=872min / ab4d54ab9bc7c1dde idle=826min / bqjh1h2ro idle=1011min / a7adb6aa841340bb0 idle=781min
通道异常: 无（[B] status.json 正常，ts=11:40:01；[D] 10:56:30 的 CHANNEL_DOWN 已恢复）
需要我看的: landau pt_conv_brca_idc / pt_conv_luad / pt_conv_ucec —— state=stalled，alive=true 但 log_mtime_age=1319s 且 log_tail3 为空；task=bntqb0c8j idle=21min [killed]；task=byfd83ydv idle=71min [killed]；task=b5pyj28n8 停滞 27 分钟

## 2026-08-27 12:14
[12:14] 窗口/后台巡检
运行中: task=b8q92pj7b idle=16min, task=bvop9g3nz idle=16min, task=bm8sciowb idle=16min（均属 sess=6c59a6c3）
卡住: task=ab4d54ab9bc7c1dde idle=854min, task=bx79vf0nf idle=900min, task=bqjh1h2ro idle=1039min（sess=917bf129）, task=a7adb6aa841340bb0 idle=810min（sess=9bcbdb32）— 无退出标记且 idle≥20min
通道异常: 无（[B] status.json 12:10:02 正常；[D] 昨条 CHANNEL_DOWN 为 10:56:30 历史记录，通道已恢复）
需要我看的: task=b5pyj28n8 idle=19min [killed]、task=bntqb0c8j idle=49min [killed]、task=byfd83ydv idle=99min [killed]（sess=9bcbdb32，近 2 小时内被杀）；上列 4 个 stale 任务
