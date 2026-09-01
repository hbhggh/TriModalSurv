
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

## 2026-08-27 12:46:15
[12:46] 窗口/后台巡检
运行中: task=ae5b9f195a9b3919b idle=15min, task=b8pkea19b idle=0min（本次巡检自身）
卡住: task=b1613m4y2 sess=144dfc4c idle=31min；task=a7adb6aa841340bb0 sess=9bcbdb32 idle=842min；task=ab4d54ab9bc7c1dde sess=917bf129 idle=886min；task=bx79vf0nf sess=917bf129 idle=932min；task=bqjh1h2ro sess=917bf129 idle=1071min
通道异常: 无（[B] status.json ts=2026-08-27 12:40:01 正常，6 个 pt_conv 任务全部 state=done）
需要我看的: task=b8q92pj7b / bvop9g3nz / bm8sciowb（sess=6c59a6c3，28min 前三个同时 [killed]）；task=b5pyj28n8（sess=9bcbdb32，51min 前 [killed]）；task=bntqb0c8j（sess=9bcbdb32，81min 前 [killed]）

## 2026-08-27 13:16
[13:16] 窗口/后台巡检
运行中: task=b0uj1x8pi idle=4min, task=b7i4l2im5 idle=9min
卡住: task=b8pkea19b idle=30min(sess d9c85104), task=ae5b9f195a9b3919b idle=45min(sess 95a27e95), task=b1613m4y2 idle=61min(sess 144dfc4c), task=a7adb6aa841340bb0 idle=872min(sess 9bcbdb32), task=ab4d54ab9bc7c1dde idle=916min, task=bx79vf0nf idle=962min, task=bqjh1h2ro idle=1101min(均 sess 917bf129)
通道异常: 无（landau status.json ts=2026-08-27 13:10:01，6 个 pt_conv 任务全部 state=done，无 dup）
需要我看的: 近 2 小时内被 kill 的后台任务 —— by9850089/bvrdro2gx(17min, sess 95a27e95)、b8q92pj7b/bvop9g3nz/bm8sciowb(58min, sess 6c59a6c3)、b5pyj28n8(81min)/bntqb0c8j(111min, sess 9bcbdb32)，尾部仅 [killed] 无错误信息，需确认是主动终止还是异常被杀

## 2026-08-27 13:46
[13:46] 窗口/后台巡检
运行中: 无
卡住: b1noao03z(29min), b8pkea19b(60min), ae5b9f195a9b3919b(75min), b1613m4y2(91min), a7adb6aa841340bb0(902min), ab4d54ab9bc7c1dde(946min), bx79vf0nf(992min), bqjh1h2ro(1131min)
通道异常: 无（status.json ts=2026-08-27 13:40:01 正常回传）
需要我看的: landau d_verify_blca5 state=failed（RuntimeError: value cannot be converted to type at::Half without overflow，attention_mask 用 -1e30 在 fp16 下溢出）；近 2 小时被杀后台任务 by9850089/bvrdro2gx(47min)、b8q92pj7b/bvop9g3nz/bm8sciowb(88min)、b5pyj28n8(111min) 均 [killed]

## 2026-08-27 14:16
[14:16] 窗口/后台巡检
运行中: task=b23qnl8nc idle=0min（本次巡检自身）；landau 侧 s4_g0_laneA/laneB/laneE、s4_g1_laneC/laneD/laneF、s4_gpu1_stage2 均 state=running
卡住: bfxx5i4bw(29min), b1noao03z(59min), b8pkea19b(89min), ae5b9f195a9b3919b(105min), b1613m4y2(121min), a7adb6aa841340bb0(932min), ab4d54ab9bc7c1dde(976min), bx79vf0nf(1022min), bqjh1h2ro(1161min)
通道异常: 无（[B] status.json ts=2026-08-27 14:10:01 正常回传，无 dup；[D] 10:56:30 的 CHANNEL_DOWN 已于 12:55:13 恢复为 OK）
需要我看的: landau d_verify_blca5 state=failed（ValueError: pkl 的 identifier/embedding 必须是列表: data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl，log_age=1560s；与 13:46 那次 fp16 溢出报错不同，已换成新的 pkl 格式错误）；近 2 小时内 [killed] 的后台任务 by9850089/bvrdro2gx(77min, sess 95a27e95)、b8q92pj7b/bvop9g3nz/bm8sciowb(118min, sess 6c59a6c3)，尾部仅 [killed] 无错误信息

## 2026-08-27 14:46
[14:46] 窗口/后台巡检
运行中: task=brb1i6872 idle=7min, task=bhyl2zwu9 idle=0min（本巡检自身）
卡住: task=bfxx5i4bw idle=59min, task=b23qnl8nc idle=30min, task=b1noao03z idle=89min, task=b8pkea19b idle=120min, task=b1613m4y2 idle=151min, task=ae5b9f195a9b3919b idle=135min, task=bx79vf0nf idle=1052min, task=ab4d54ab9bc7c1dde idle=1006min, task=a7adb6aa841340bb0 idle=962min
通道异常: 无（status.json ts=2026-08-27 14:40:01，[D] 最后一节为 OK；10:56 那次 CHANNEL_DOWN 已恢复）
需要我看的: d_verify_blca5 — state=failed，bulkrnabert_infer.py 报 "pkl 的 identifier/embedding 必须是列表: data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl"；s4_gpu1_stage2 — state=stalled（alive=true 但 log_age=2184s）；task=by9850089 idle=107min 与 task=bvrdro2gx idle=107min — 近 2 小时内 [killed]，尾部无输出

## 2026-08-27 15:16:43
[15:16] 窗口/后台巡检
运行中: landau s4_g0A/s4_g0D/s4_g0E/s4_g1A/s4_g1D/s4_g1E（state=running），mac task=bi3zswtr7 idle=0
卡住: mac 侧 11 个后台任务 idle≥20min 无退出标记（bhyl2zwu9 29min、b23qnl8nc 59min、bfxx5i4bw 89min、b1noao03z 119min、b8pkea19b 149min、ae5b9f195a9b3919b 165min、b1613m4y2 181min、ab4d54ab9bc7c1dde 1036min、bx79vf0nf 1082min、bqjh1h2ro 1221min、a7adb6aa841340bb0 991min）——多为历史巡检/会话残留
通道异常: 无（status.json ts=2026-08-27 15:10:01 可读）
需要我看的: landau d_verify_blca5 state=failed —— bulkrnabert_infer.py 报 "pkl 的 identifier/embedding 必须是列表: data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl"

## 2026-08-27 15:46 — 巡检
[15:46] 窗口/后台巡检
运行中: task=bl3ndodbt idle=0（S4事件流），task=bzswfo0q0 idle=0（本次巡检）；landau: s4_g0_{blca,brca,lgg,luad,ucec} + s4_g1_{blca,brca,lgg,luad,ucec} + s4_stage2 均 running
卡住: task=bqjh1h2ro idle=1251, bx79vf0nf idle=1112, ab4d54ab9bc7c1dde idle=1066, a7adb6aa841340bb0 idle=1022, b1613m4y2 idle=211, ae5b9f195a9b3919b idle=195, b8pkea19b idle=180, b1noao03z idle=149, bfxx5i4bw idle=119, b23qnl8nc idle=90, bhyl2zwu9 idle=59, bi3zswtr7 idle=30, b8lbsxnpi idle=29
通道异常: 无（status.json ts=2026-08-27 15:40:01，正常）
需要我看的: landau job `d_verify_blca5` state=failed —— bulkrnabert_infer.py:244 ValueError: pkl 的 identifier/embedding 必须是列表 (data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl)；后台任务 task=bdb6w2eki (sess=95a27e95, idle=10min) 尾部 [killed]，近 2 小时内被杀

## 2026-08-27 16:16 — 巡检
[16:16] 窗口/后台巡检
运行中: task=bwomjxz2q idle=1（S4事件流 LUAD_LIST_0），task=b7rs77e87 idle=0（本次巡检自身）；landau: s4_g0_{blca,lgg,ucec}、s4_g1_{blca,lgg,ucec}、tar_scan 均 state=running（s4_g0/g1_{brca,luad} 已 done）
卡住: bqjh1h2ro 1281min, bx79vf0nf 1141min, ab4d54ab9bc7c1dde 1096min, a7adb6aa841340bb0 1051min, b1613m4y2 241min, ae5b9f195a9b3919b 225min, b8pkea19b 209min, b1noao03z 179min, bfxx5i4bw 149min, b23qnl8nc 119min, bhyl2zwu9 89min, bi3zswtr7 59min, b8lbsxnpi 59min, bzswfo0q0 29min, bl3ndodbt 24min ——多为历史巡检/会话残留
通道异常: 无（[B] status.json ts=2026-08-27 16:10:01 正常回传，无 dup；[D] 最后一节为 12:55:13 OK，10:56 那次 CHANNEL_DOWN 已恢复）
需要我看的: landau `s4_stage2` state=stalled（alive=true 但日志停更）；landau `d_verify_blca5` state=failed —— bulkrnabert_infer.py:244 ValueError: pkl 的 identifier/embedding 必须是列表 (data/RNA_embedding/RNA_BLCA_embedding_token_lvl.pkl)，log_age=8760s 为旧错误未清；task=bqgjzwskj (sess=95a27e95, idle=15min) [exited with code 255] —— ssh 到 130.158.13.17 超时 Broken pipe；task=bdb6w2eki (sess=95a27e95, idle=40min) 尾部 [killed]

## 2026-08-27 16:46
[16:46] 窗口/后台巡检
运行中: mac task=bl3ndodbt idle=3min；landau s4_g0_lgg / s4_g1_lgg / s4_stage2 state=running
卡住: 15 个 mac 后台任务无结束标记且 idle≥20min（b7rs77e87 29min、bzswfo0q0 59min、bi3zswtr7 89min、b8lbsxnpi 89min、bhyl2zwu9 119min、b23qnl8nc 149min、bfxx5i4bw 179min、b1noao03z 209min、b8pkea19b 239min、ae5b9f195a9b3919b 255min、b1613m4y2 271min、a7adb6aa841340bb0 1081min、ab4d54ab9bc7c1dde 1126min、bx79vf0nf 1171min、bqjh1h2ro 1311min）
通道异常: 无（landau status.json ts=2026-08-27 16:40:01 正常）
需要我看的: d_verify_blca5（landau state=failed，ValueError: pkl 的 identifier/embedding 必须是列表 RNA_BLCA_embedding_token_lvl.pkl）；bqgjzwskj（45min 前 [exited with code 255]，ssh 130.158.13.17 Operation timed out / Broken pipe）；bdb6w2eki（70min 前 [killed]）

## 2026-08-27 17:12 — 巡检
[17:12] 窗口/后台巡检
运行中: 无
卡住: 无（mac 侧后台任务全部已 exited/killed，idle 均 >1000 分钟）
通道异常: 无（landau status.json 时刻 2026-08-27 17:10:01 正常返回）
需要我看的: s4_stage2 state=failed（RNA_INFER_FAILED ec=1，manifests/tsv-dirs/cancers 数量 4/4/5 不一致，log_age 1311s）；d_verify_blca5 state=failed（RNA_BLCA_embedding_token_lvl.pkl 的 identifier/embedding 不是列表，log_age 12360s）

## 2026-08-27 17:46
[17:46] 窗口/后台巡检
运行中: 无
卡住: task=b3cqe0xzb/b4keldsm2(sess=b766cc8d) idle=29min，task=bl3ndodbt(sess=95a27e95) idle=53min，task=b5z8ka90x idle=59min，task=b7rs77e87 idle=89min，task=bzswfo0q0 idle=119min，task=bi3zswtr7/b8lbsxnpi idle=149min，task=bhyl2zwu9 idle=179min，task=b23qnl8nc idle=209min，task=bfxx5i4bw idle=239min，task=b1noao03z idle=269min，task=b8pkea19b idle=299min，task=ae5b9f195a9b3919b idle=315min，task=b1613m4y2 idle=331min，另 sess=917bf129 3 个 idle>1180min（均为历史 SSH 探针/巡检残留）
通道异常: 无（landau status.json 正常，ts=2026-08-27 17:40:01；当日 10:56 的 CHANNEL_DOWN 已于 12:55 恢复 OK）
需要我看的: landau job `d_verify_blca5` state=failed（bulkrnabert_infer.py:244 ValueError: RNA_BLCA_embedding_token_lvl.pkl 的 identifier/embedding 必须是列表）；landau job `s4_stage2` state=failed；task=bqgjzwskj(sess=95a27e95, idle=105min) exit 255（ssh 130.158.13.17 超时 Broken pipe，近 2h 内）

## 2026-08-27 20:33 — 巡检
[20:33] 窗口/后台巡检
运行中: task=bbrl68j0p idle=0（本次巡检自身）
卡住: 19 个 mac 后台任务无结束标记且 idle≥20min（blmh4uanv 93、b3cqe0xzb/b4keldsm2 123、bl3ndodbt 147、b5z8ka90x 153、b7rs77e87 183、bzswfo0q0 213、bi3zswtr7/b8lbsxnpi 243、bhyl2zwu9 273、b23qnl8nc 303、bfxx5i4bw 333、b1noao03z 363、b8pkea19b 393、ae5b9f195a9b3919b 409、b1613m4y2 425、a7adb6aa841340bb0 1235、ab4d54ab9bc7c1dde 1280、bx79vf0nf 1325）——多为历史巡检/会话残留
通道异常: CHANNEL_DOWN —— landau status.json 不可达。通道断了，任务未必死，不判死、不拉起；[D] 最后一节仍为 12:55:13 OK（6 个 pt_conv_* 全 done）
需要我看的: CHANNEL_DOWN 本身（landau 侧状态自 12:55 起无新回传）；[C] 无 ALERT，近 2 小时内无 [killed]/非 0 退出

## 2026-08-27 20:35:54
[20:35] 窗口/后台巡检
运行中: task=blep2iukx idle=0min（本轮巡检自身）
卡住: task=blmh4uanv idle=169min, task=b3cqe0xzb idle=199min, task=b4keldsm2 idle=199min, task=bl3ndodbt idle=223min, task=b5z8ka90x idle=229min, task=b7rs77e87 idle=259min, task=bzswfo0q0 idle=289min, task=bi3zswtr7 idle=319min, task=b8lbsxnpi idle=319min, task=bhyl2zwu9 idle=349min, task=b23qnl8nc idle=379min, task=bfxx5i4bw idle=409min, task=b1noao03z idle=439min, task=b8pkea19b idle=469min, task=ae5b9f195a9b3919b idle=485min, task=b1613m4y2 idle=501min, task=a7adb6aa841340bb0 idle=1311min, task=ab4d54ab9bc7c1dde idle=1356min, task=bx79vf0nf idle=1401min
通道异常: [B] CHANNEL_DOWN — ssh 不可达或 status.json 缺失；通道断了，任务未必死，不判死、不拉起，沿用上次状态（2026-08-27 12:50:01 landau 时刻，6 个 pt_conv 任务均 state=done）
需要我看的: landau 通道 — CHANNEL_DOWN 持续，无法确认远端当前状态；19 个后台 task idle≥20min 无结束标记（多为各会话残留的监视/巡检 task，尾部停在同一条 pt_conv_ucec 状态行）

## 2026-08-27 20:46
[20:46] 窗口/后台巡检
运行中: task=bhlvyp6b5 idle=0（本巡检会话）, task=bl3ndodbt idle=0（sess=95a27e95，tail 含 s4_stage2/fail.flag + SENTINEL: landau ssh 连续3次失败）
卡住: 18 个后台任务尾部无结束标记且 idle≥20min —— ab4d54ab9bc7c1dde(1366m)/bx79vf0nf(1411m)/a7adb6aa841340bb0(1321m)/ae5b9f195a9b3919b(495m)/b8pkea19b(479m)/b1noao03z(449m)/bfxx5i4bw(419m)/b23qnl8nc(389m)/bhyl2zwu9(359m)/bi3zswtr7(329m)/b8lbsxnpi(329m)/bzswfo0q0(299m)/b7rs77e87(270m)/b5z8ka90x(240m)/b3cqe0xzb(210m)/b4keldsm2(209m)/blmh4uanv(180m)/b1613m4y2(511m)；多数尾部为历史 sweep 输出残留
通道异常: [B] CHANNEL_DOWN —— ssh 不可达或 status.json 缺失。通道断了，任务未必死，沿用上次状态（2026-08-27 12:50:01 六个 pt_conv 任务均 state=done），不判死、不拉起
需要我看的: landau 通道 —— CHANNEL_DOWN 持续，无法确认远端最新状态；task=bl3ndodbt —— 输出中出现 rna_infer.failed 与 ssh 连续失败哨兵

## 2026-08-28 10:16
[10:16] 窗口/后台巡检
运行中: landau: rna_infer / s4_stage3 / s4_stage3b / s4_r2_mcat_brca / s4_r2_mcat_luad / s4_r2_porp_brca / s4_r2_porp_luad / _adhoc_bulkrnabert（status.json ts=10:10:01）；mac: task=b3dgnik0n idle=0（本巡检自身）
卡住: task=bltsa35mi idle=27min（S4事件流无 exit 标记）；另有 16 个历史监视任务 idle 990–1421min（前几轮 sweep 残留，无 exit 标记）
通道异常: 无（status.json 正常，非 CHANNEL_DOWN）
需要我看的: task=bl3ndodbt [killed] idle=30min，尾部 "S4事件: rna_infer.failed SENTINEL: landau ssh 连续3次失败，监视中断风险"；landau s4_stage2 state=failed；landau d_verify_blca5 state=failed（pkl identifier/embedding 必须是列表: RNA_BLCA_embedding_token_lvl.pkl）

## 2026-08-28 10:46
[10:46] 窗口/后台巡检
运行中: landau s4_r2_mcat_brca / s4_r2_mcat_luad / s4_r2_porp_brca / s4_r2_porp_luad / s4_stage3 / s4_stage3b（alive=true）；mac task=bltsa35mi idle=6min
卡住: task=b3dgnik0n idle=29min（上一轮巡检未收尾）；另有 14 个 idle>17h 的历史后台任务无退出标记（bfxx5i4bw,b1613m4y2,b3cqe0xzb,b4keldsm2,b7rs77e87,b23qnl8nc,b8pkea19b,bhyl2zwu9,bi3zswtr7,b8lbsxnpi,blmh4uanv,b5z8ka90x,b1noao03z,bzswfo0q0）
通道异常: 无（status.json ts=2026-08-28 10:40:01）
需要我看的: task=bl3ndodbt（60min 前 [killed]，尾部 "S4事件: rna_infer.failed SENTINEL: landau ssh 连续3次失败，监视中断风险"）；landau s4_stage2 state=failed；landau d_verify_blca5 state=failed（RNA_BLCA pkl identifier/embedding 非列表）；landau _adhoc_npj_train dup_count=3 且 alive（重复训练进程）

## 2026-08-28 11:16 巡检
[11:16] 窗口/后台巡检
运行中: landau: s4_r2_mcat_brca / s4_r2_mcat_luad / s4_r2_porp_brca / s4_r2_porp_luad / s4_stage3 / s4_stage3b / _adhoc_npj_train（均 alive=true）；mac 后台: task=bltsa35mi idle=6min
卡住: task=b3dgnik0n idle=59min、task=bxx92pm66 idle=29min；另有 15 个历史巡检 task（bfxx5i4bw/b1613m4y2/b3cqe0xzb/b4keldsm2/b7rs77e87/ae5b9f195a9b3919b/b23qnl8nc/b8pkea19b/bhyl2zwu9/bi3zswtr7/b8lbsxnpi/blmh4uanv/b5z8ka90x/b1noao03z/bzswfo0q0）idle 1050-1415min 无退出标记
通道异常: 无（status.json ts=2026-08-28 11:10:02 正常返回）
需要我看的: task=bl3ndodbt（90min 前 [killed]，尾部 SENTINEL: landau ssh 连续3次失败）；landau job d_verify_blca5（state=failed，RNA pkl identifier/embedding 非列表）；landau job s4_stage2（state=failed）；landau job _adhoc_npj_train（dup_count=2，疑重复）

## 2026-08-28 11:46
[11:46] 窗口/后台巡检
运行中: task=b73hdrfqk idle=0min, task=bltsa35mi idle=6min；landau: s4_stage3b(running), _adhoc_npj_train(running)
卡住: 17 个后台任务无退出标记且 idle≥20min（均为历史巡检自身的 sweep 调用）：bdjoffo6o(29m), bxx92pm66(59m), b3dgnik0n(89m), blmh4uanv(1080m), b4keldsm2(1109m), b3cqe0xzb(1110m), b5z8ka90x(1140m), b7rs77e87(1170m), bzswfo0q0(1199m), bi3zswtr7/b8lbsxnpi(1229m), bhyl2zwu9(1259m), b23qnl8nc(1289m), bfxx5i4bw(1319m), b1noao03z(1349m), b8pkea19b(1379m), b1613m4y2(1411m)
通道异常: 无（landau status.json 正常，ts=2026-08-28 11:40:01）
需要我看的:
- task=bb2q10vbn（1min 前 exited code 1，尾部 EVALFAIL porpoise_ucec_s213/s231/s321）
- task=bl3ndodbt（120min 前 [killed]，尾部 SENTINEL: landau ssh 连续3次失败，监视中断风险；S4事件 rna_infer.failed）
- landau job s4_stage2（state=failed：--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED）
- landau job d_verify_blca5（state=failed：RNA_BLCA_embedding_token_lvl.pkl identifier/embedding 必须是列表）

## 2026-08-28 12:16
[12:16] 窗口/后台巡检
运行中: task=bg0gvuuha idle=0min（landau p3_eval2 alive=true）
卡住: 19 个后台任务 idle≥20min 无退出标记（近端: bqrs1t9hi idle=29, b9qpwgpbj idle=30, bdjoffo6o idle=60, bxx92pm66 idle=90, b3dgnik0n idle=120；其余 15 个为 idle>16h 历史巡检残留）
通道异常: 无（status.json ts=2026-08-28 12:10:01，通道正常）
需要我看的: task=bb2q10vbn（31min 前 exit code 1，EVALFAIL porpoise_ucec_s213/s231/s321）；landau job d_verify_blca5（state=failed，RNA pkl identifier/embedding 必须是列表）；landau job s4_stage2（state=failed，--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致）

## 2026-08-28 12:40 巡检
[12:40] 窗口/后台巡检
运行中: task=b4kj027si idle=0（本巡检），task=bg0gvuuha idle=2；landau p3_eval2 state=running
卡住: 19 个 mac 后台 sweep 任务 idle≥20min 未收尾（近端：bqrs1t9hi 59min、b9qpwgpbj 60min、bdjoffo6o 90min、bxx92pm66 120min、b3dgnik0n 149min、bkd1w9jdh 29min；其余 1000min+ 为历史残留）
通道异常: 无（status.json ts=2026-08-28 12:40:01 正常）
需要我看的: landau s4_stage2 state=failed；landau d_verify_blca5 state=failed（RNA pkl identifier/embedding 必须是列表）；task=bb2q10vbn idle=61min [exited with code 1]（EVALFAIL porpoise_ucec_s213/s231/s321）

## 2026-08-28 13:10 巡检
[13:10] 窗口/后台巡检
运行中: task=b4d165hek idle=0min、task=byd0hlvu1 idle=0min（本巡检）；landau p3_eval2 alive=true
卡住: 21 个 mac 后台任务 idle≥20min 且无退出标记（近端: b4kj027si 30min、bkd1w9jdh 59min、bqrs1t9hi 89min、b9qpwgpbj 90min、bdjoffo6o 120min、bxx92pm66 150min、b3dgnik0n 180min；其余 14 个 idle 1170-1439min 为历史巡检残留）
通道异常: 无（status.json ts=2026-08-28 13:10:01，41 个 job，无同名重复、无 dup_count>1）
需要我看的: task=bb2q10vbn（91min 前 [exited with code 1]，尾部 EVALFAIL porpoise_ucec_s213 / s231 / s321）；landau job s4_stage2（state=failed，RNA_INFER_FAILED ec=1 n=0）；landau job d_verify_blca5（state=failed，RNA_BLCA_embedding_token_lvl.pkl identifier/embedding 必须是列表）

## 2026-08-28 13:46 巡检
[13:46] 窗口/后台巡检
运行中: task=b1aflm9vn idle=0min（本巡检）、task=a07198bfcb3874d28 idle=18min；landau 41 个 job 全部 alive=false（无运行中任务）
卡住: 20 个 mac 后台任务 idle≥20min 且无退出标记（近端: byd0hlvu1 29min、bhi6wgw7g 29min、b4kj027si 60min、bkd1w9jdh 90min、bqrs1t9hi 119min、b9qpwgpbj 120min、bdjoffo6o 150min、bxx92pm66 180min、b3dgnik0n 210min；其余 11 个 idle 1200-1439min 为历史巡检残留）
通道异常: 无（status.json ts=2026-08-28 13:40:01 正常返回，无同名重复、无 dup_count>1）
需要我看的: landau job s4_stage2（state=failed，--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED ec=1 n=0）；landau job d_verify_blca5（state=failed，RNA_BLCA_embedding_token_lvl.pkl identifier/embedding 必须是列表）

## 2026-08-28 14:17 巡检
[14:17] 窗口/后台巡检
运行中: task=bf4sn7lbf idle=0min（本巡检）；landau 41 个 job 全部 alive=false，无运行中任务
卡住: 21 个 mac 后台任务 idle≥20min 且无退出标记（近端: b1aflm9vn 30min、a07198bfcb3874d28 48min、bhi6wgw7g 59min、byd0hlvu1 60min、b4kj027si 90min、bkd1w9jdh 120min、bqrs1t9hi 149min、b9qpwgpbj 150min、bdjoffo6o 180min、bxx92pm66 210min、b3dgnik0n 240min；其余 10 个 idle 1230-1439min 为历史巡检残留）
通道异常: 无（status.json ts=2026-08-28 14:10:01，41 个 job，无同名重复、无 dup_count>1）
需要我看的: landau job s4_stage2（state=failed，--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED ec=1 n=0）；landau job d_verify_blca5（state=failed，RNA_BLCA_embedding_token_lvl.pkl identifier/embedding 必须是列表）
（近 2 小时内无新的 fail/killed 后台任务；bb2q10vbn[code 1]/bl3ndodbt[killed] 均已超 2 小时，按规则不再重复提醒）

## 2026-08-28 14:45
[14:45] 窗口/后台巡检
运行中: 无（landau status.json 中 41 个 job 全部 alive=false）
卡住: 无实验任务卡住；21 个 mac 后台 output 文件无 exit 标记且 idle≥20min，尾部均为历次巡检脚本自身输出/旧 pt_conv 日志尾，非活跃实验
通道异常: 无（status.json ts=2026-08-28 14:40:01，正常）
需要我看的: landau job `d_verify_blca5` state=failed（RNA pkl identifier/embedding 格式错，log_age≈24.9h）、`s4_stage2` state=failed（log_age≈21.9h）——均为旧失败，非本轮新增

## 2026-08-28 15:16 巡检
[15:16] 窗口/后台巡检
运行中: task=buth9qi6m idle=0min（本巡检自身）；landau status.json 41 个 job 全部 alive=false，无运行中实验
卡住: 21 个 mac 后台任务无退出标记且 idle≥20min（近端: b8ek2w8rk 29min、bf4sn7lbf 59min、b1aflm9vn 89min、a07198bfcb3874d28 108min、byd0hlvu1/bhi6wgw7g 119min、b4kj027si 150min、bkd1w9jdh 179min、bqrs1t9hi 209min、b9qpwgpbj 210min、bdjoffo6o 240min、bxx92pm66 270min、b3dgnik0n 300min；其余 8 个 idle 1290-1439min 为历史残留。尾部均为历次巡检脚本自身输出或旧 pt_conv 日志，非活跃实验）
通道异常: 无（status.json ts=2026-08-28 15:10:01 正常返回，无同名重复、无 dup_count>1）
需要我看的: landau job d_verify_blca5（state=failed，RNA_BLCA_embedding_token_lvl.pkl identifier/embedding 必须是列表，log_age≈25.4h）；landau job s4_stage2（state=failed，--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，log_age≈22.4h）——均为旧失败，本轮无新增。近 2 小时内无新的 fail/killed 后台任务

## 2026-08-28 15:46 巡检
[15:46] 窗口/后台巡检
运行中: task=b2vun4brs idle=0min（本巡检自身）；landau status.json 41 个 job 全部 alive=false，无运行中实验
卡住: 23 个 mac 后台任务无退出标记且 idle≥20min（近端: buth9qi6m 29min、b8ek2w8rk 59min、bf4sn7lbf 89min、b1aflm9vn 119min、a07198bfcb3874d28 138min、byd0hlvu1/bhi6wgw7g 149min、b4kj027si 179min、bkd1w9jdh 209min、bqrs1t9hi 239min、b9qpwgpbj 240min、bdjoffo6o 270min、bxx92pm66 300min、b3dgnik0n 329min；其余 idle 1320-1439min 为历史残留。尾部均为历次巡检脚本自身输出或旧 pt_conv 日志，非活跃实验）
通道异常: 无（status.json ts=2026-08-28 15:40:01 正常返回，41 个 job，无同名重复、无 dup_count>1；[C] 无 ALERT，[D] 今日尚无 cron 记录）
需要我看的: landau job d_verify_blca5（state=failed，RNA_BLCA_embedding_token_lvl.pkl identifier/embedding 必须是列表，log_age≈25.9h）；landau job s4_stage2（state=failed，log_age≈22.9h）——均为旧失败，本轮无新增。近 2 小时内无新的 fail/killed 后台任务（bl3ndodbt[killed] 360min、bb2q10vbn[code 1] 241min 均已超 2 小时）

## 2026-08-29 11:31
[11:31] 窗口/后台巡检
运行中: task=blrjyguam idle=0min（本轮巡检自身）
卡住: bf4sn7lbf(1350min), b2vun4brs(1260min), a07198bfcb3874d28(1399min), b1aflm9vn(1380min), byd0hlvu1(1410min), bhi6wgw7g(1410min), b8ek2w8rk(1320min), buth9qi6m(1290min), b1opyirkc(1232min)
通道异常: CHANNEL_DOWN — landau status.json 取不到；通道断了，任务未必死，禁止判死
需要我看的: landau 通道（CHANNEL_DOWN，无法读取远端任务状态）；上述 9 个历史后台任务尾部无退出标记且 idle 均 >20h

## 2026-08-29 13:16
[13:16] 窗口/后台巡检
运行中: task=b4n3y3o44 idle=0min（本次巡检自身）
卡住: task=bf4sn7lbf idle=1380min, task=b2vun4brs idle=1290min, task=a07198bfcb3874d28 idle=1429min, task=b1aflm9vn idle=1410min, task=b8ek2w8rk idle=1350min, task=buth9qi6m idle=1320min, task=b1opyirkc idle=1262min（均为历史巡检会话遗留后台任务，尾部无 exited/killed）
通道异常: landau status.json = CHANNEL_DOWN —— 通道断了，任务未必死，不判死
需要我看的: landau 通道（status.json 不可达，无法确认远端任务状态）；7 个 stale 后台任务（idle 均 >20 小时）

## 2026-08-29 13:46
[13:46] 窗口/后台巡检
运行中: task=b6qb1td3t idle=0min（本轮巡检自身）
卡住: task=bf4sn7lbf idle=1410min, task=b8ek2w8rk idle=1380min, task=buth9qi6m idle=1350min, task=b2vun4brs idle=1320min, task=b1opyirkc idle=1292min（均为历史巡检 sweep 后台任务，尾部无 exited/killed）
通道异常: CHANNEL_DOWN — landau status.json 读不到；通道断了，任务未必死，禁止判死
需要我看的: landau 通道（CHANNEL_DOWN，无法确认远端任务状态）；5 个 stale 巡检后台任务（idle 21-23 小时未退出）

## 2026-08-29 12:47
[12:47] 窗口/后台巡检
运行中: task=bfex8mttg idle=0min（本轮巡检自身）
卡住: task=b2vun4brs idle=1350min, task=b8ek2w8rk idle=1410min, task=buth9qi6m idle=1380min, task=b1opyirkc idle=1322min（均为历史巡检残留后台任务，尾部无 exited/killed）
通道异常: CHANNEL_DOWN — landau status.json 读不到；通道断了，任务未必死，禁止判死
需要我看的: landau 通道（status.json 不可达，无法确认远端任务状态）；4 个 stale 后台任务（idle 均超 22 小时，疑为未回收的旧巡检 shell）

## 2026-08-29 13:16
[13:16] 窗口/后台巡检
运行中: task=bheptye06 idle=0min（本次巡检自身）
卡住: task=b2vun4brs idle=1380min, task=buth9qi6m idle=1410min, task=b1opyirkc idle=1352min（均为历史 sweep.sh 残留后台任务，尾部无 exited/killed）
通道异常: CHANNEL_DOWN — landau status.json 不可达，通道断了，任务未必死，不判死
需要我看的: 3 个 stale sweep 后台任务（idle 均 >22 小时，疑似残留未回收）；landau 通道 CHANNEL_DOWN 需人工确认

## 2026-08-29 15:16
[15:16] 窗口/后台巡检
运行中: task=b74fo4m3u idle=0min
卡住: task=b2vun4brs idle=1410min, task=b1opyirkc idle=1382min（均为历史巡检后台任务，未见 exited/killed）
通道异常: CHANNEL_DOWN（landau status.json 不可读；通道断了，任务未必死，禁止判死）
需要我看的: landau 通道 —— status.json 无法获取，无法确认远端任务状态；b2vun4brs / b1opyirkc —— idle 超 23 小时仍未收尾

## 2026-08-29 14:16
[14:16] 窗口/后台巡检
运行中: task=bmfs3dx84 idle=0min（本次巡检自身）
卡住: task=b1opyirkc sess=90807810 idle=1412min（尾部为旧巡检脚本输出，无 exited/killed 标记）
通道异常: CHANNEL_DOWN — landau status.json 取不到；通道断了，任务未必死，不判死
需要我看的: task=b1opyirkc（idle 超 23 小时，疑为旧巡检残留后台任务未回收）；landau 通道 CHANNEL_DOWN

## 2026-08-29 14:53
[14:53] 窗口/后台巡检
运行中: 无（仅本次巡检自身 task=bk3i93vjg idle=0min）
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 读不到，通道断了，任务未必死，禁止判死
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-29 16:46
[16:46] 窗口/后台巡检
运行中: task=b67qy94g6(巡检器自身) idle=0min
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 不可达；通道断了，任务未必死，不判死
需要我看的: landau 通道 — status.json 无法读取，无法确认远端任务状态

## 2026-08-29 17:16
[17:16] 窗口/后台巡检
运行中: task=bhn8mw9wj idle=0min（本轮巡检脚本自身）
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 取不到，通道断了，任务未必死，不判死
需要我看的: landau 通道 — status.json 不可读，无法确认远端任务状态

## 2026-08-29 21:34
[21:34] 窗口/后台巡检
运行中: task=bck4tuntu idle=0min
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 不可达，通道断了，任务未必死，禁止判死
需要我看的: landau 通道 — status.json 读取失败，需人工确认 landau 侧任务状态

## 2026-08-29 23:55
[23:55] 窗口/后台巡检
运行中: task=bh64ge3hq(巡检自身) idle=0min
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 拉取失败（通道断了，任务未必死，禁止判死）
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-30 01:14
[01:14] 窗口/后台巡检
运行中: task=biuqkptzi idle=0min（本次采集脚本自身）
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 读不到；通道断了，任务未必死，不判死
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-30 20:15
[20:15] 窗口/后台巡检
运行中: task=b95acw1o7 idle=0min（本次巡检自身）
卡住: 无
通道异常: CHANNEL_DOWN（landau status.json 取不到；通道断了，任务未必死，不判死）
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-30 20:45
[20:45] 窗口/后台巡检
运行中: 无
卡住: 无
通道异常: CHANNEL_DOWN（landau status.json 取不到；通道断了，任务未必死，不判死）
需要我看的: landau 通道 — status.json 不可达，需人工确认远端任务状态

## 2026-08-30 21:15
[21:15] 窗口/后台巡检
运行中: 无
卡住: 无
通道异常: CHANNEL_DOWN（landau status.json 拉不到）——通道断了，任务未必死，不判死
需要我看的: landau 通道（status.json 不可达，无法确认远端任务状态）

## 2026-08-30 12:45
[12:45] 窗口/后台巡检
运行中: task=b724ngsql idle=0min
卡住: 无
通道异常: CHANNEL_DOWN（landau status.json 不可达；通道断了，任务未必死，禁止判死）
需要我看的: landau 通道 — status.json 拉不到，无法确认远端任务状态

## 2026-08-31 09:45
[09:45] 窗口/后台巡检
运行中: 无
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 取不到，通道断了，任务未必死
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态，禁止判死

## 2026-08-31 10:17
[10:17] 窗口/后台巡检
运行中: 无（[A] 仅本巡检自身 task=bbyiiy6df sess=c764a3e3 idle=0min）
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 取不到，通道断了，任务未必死，禁止判死
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-31 10:46
[10:46] 窗口/后台巡检
运行中: task=baejc4irh idle=0min
卡住: 无
通道异常: CHANNEL_DOWN（landau status.json 取不到；通道断了，任务未必死，不判死）
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-31 11:17
[11:17] 窗口/后台巡检
运行中: task=bpw1jv7mq(巡检自身) idle=0min
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 不可达，通道断不等于任务死亡，未判死
需要我看的: landau 通道 — status.json 拉取失败，无法确认远端任务状态

## 2026-08-31 11:48
[11:48] 窗口/后台巡检
运行中: 无（仅巡检自身 task=bsmoguy2w idle=0min）
卡住: 无
通道异常: CHANNEL_DOWN — landau status.json 取不到，通道断了，任务未必死，不判死
需要我看的: landau 通道 — status.json 不可达，无法确认远端任务状态

## 2026-08-31 15:34
[15:34] 窗口/后台巡检
运行中: 无（仅巡检自身 task=b0ta4gd25 idle=0min）
卡住: 无
通道异常: CHANNEL_DOWN（landau status.json 不可读；通道断了，任务未必死，禁止判死）
需要我看的: landau 通道 — status.json 读不到，无法确认远端任务状态

## 2026-08-31 15:49
[15:49] 窗口/后台巡检
运行中: task=bd2tyr22f idle=0min（巡检采集脚本自身）
卡住: 无
通道异常: 无（status.json ts=2026-08-31 15:40，正常）
需要我看的: landau d_verify_blca5 state=failed（RNA_BLCA pkl identifier/embedding 非列表，日志 ~4 天前）；landau s4_stage2 state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，日志 ~4 天前）

## 2026-08-31 16:18
[16:18] 窗口/后台巡检
运行中: task=bqs9mu62q idle=0min
卡住: task=bd2tyr22f (sess=f00dad84) idle=29min，无退出标记
通道异常: 无（landau status.json ts=2026-08-31 16:10:01 正常返回）
需要我看的: d_verify_blca5(state=failed，RNA_BLCA pkl identifier/embedding 非列表)；s4_stage2(state=failed)；task=bd2tyr22f(idle≥20min 判 stale)

## 2026-08-31 16:48
[16:48] 窗口/后台巡检
运行中: task=bsbhznjio idle=0min（巡检自身采集脚本）
卡住: task=bd2tyr22f (sess=f00dad84) idle=59min；task=bqs9mu62q (sess=58cf4dbc) idle=30min（均无 exited/killed 标记，均为历次巡检采集脚本）
通道异常: 无（landau status.json ts=2026-08-31 16:40:01 正常返回）
需要我看的: d_verify_blca5(state=failed，RNA_BLCA pkl identifier/embedding 非列表，日志 ~4 天前)；s4_stage2(state=failed，--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，日志 ~4 天前)；task=bd2tyr22f、task=bqs9mu62q(idle≥20min 判 stale)

## 2026-08-31 17:19
[17:19] 窗口/后台巡检
运行中: task=b0yvwv204 idle=0min（巡检自身采集脚本）
卡住: task=bd2tyr22f (sess=f00dad84) idle=89min；task=bqs9mu62q (sess=58cf4dbc) idle=60min；task=bsbhznjio (sess=4ddc87fd) idle=29min（均无 exited/killed 标记，均为历次巡检采集脚本）
通道异常: 无（landau status.json ts=2026-08-31 17:10:01 正常返回，41 个 job 中 39 done / 2 failed / 0 alive，无 dup）
需要我看的: d_verify_blca5(state=failed，RNA_BLCA pkl identifier/embedding 非列表，日志 ~4 天前)；s4_stage2(state=failed，--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，日志 ~4 天前)；task=bd2tyr22f、bqs9mu62q、bsbhznjio(idle≥20min 判 stale)

## 2026-08-31 17:49
[17:49] 窗口/后台巡检
运行中: task=b93ugkspz idle=0min（本轮巡检自身）
卡住: task=bd2tyr22f idle=119min, task=bqs9mu62q idle=89min, task=bsbhznjio idle=59min, task=b0yvwv204 idle=29min（均为历次巡检遗留的 bash 任务，尾部为完整 sweep 输出、无 exit 标记）
通道异常: 无（landau status.json 正常，ts=2026-08-31 17:40:01，41 个 job 无重名、无 dup_count）
需要我看的: d_verify_blca5（state=failed，4.2 天前，RNA_BLCA embedding pkl 格式 ValueError）; s4_stage2（state=failed，4.0 天前，RNA_INFER_FAILED ec=1 n=0）

## 2026-08-31 18:18
[18:18] 窗口/后台巡检
运行中: task=bxixm9up5 idle=0min
卡住: task=bd2tyr22f idle=148min, task=bqs9mu62q idle=119min, task=bsbhznjio idle=89min, task=b0yvwv204 idle=59min, task=b93ugkspz idle=29min（均为历次巡检会话的 sweep 后台任务残留，尾部无 exited/killed）
通道异常: 无（status.json ts=2026-08-31 18:10:01 正常）
需要我看的: landau job s4_stage2 state=failed（ValueError: --manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志已 4 天未更新）；landau job d_verify_blca5 state=failed（陈旧，日志约 4 天未更新）

## 2026-08-31 18:48
[18:48] 窗口/后台巡检
运行中: task=bbqc3wut7 idle=0min（本轮巡检自身）
卡住: task=bd2tyr22f idle=178min, task=bqs9mu62q idle=149min, task=bsbhznjio idle=119min, task=b0yvwv204 idle=89min, task=b93ugkspz idle=59min, task=bxixm9up5 idle=29min（均为历次巡检会话的 sweep 后台任务残留，尾部无 exited/killed 标记）
通道异常: 无（landau status.json ts=2026-08-31 18:40:01 正常返回，42 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: landau job s4_stage2 state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志已约 4 天未更新）；landau job d_verify_blca5 state=failed（RNA_BLCA embedding pkl 格式 ValueError，日志已约 4.2 天未更新）

## 2026-08-31 19:18
[19:18] 窗口/后台巡检
运行中: task=b6xrjmdqd idle=0min（本轮巡检自身）
卡住: task=bd2tyr22f idle=209min, task=bqs9mu62q idle=179min, task=bsbhznjio idle=149min, task=b0yvwv204 idle=119min, task=b93ugkspz idle=89min, task=bxixm9up5 idle=60min, task=bbqc3wut7 idle=30min（均为历次巡检会话的 sweep 后台任务残留，尾部无 exited/killed 标记）
通道异常: 无（landau status.json ts=2026-08-31 19:10:01 正常返回，42 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: landau job s4_stage2 state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.1 天未更新）；landau job d_verify_blca5 state=failed（RNA_BLCA embedding pkl identifier/embedding 非列表 ValueError，日志约 4.2 天未更新）

## 2026-08-31 19:48
[19:48] 窗口/后台巡检
运行中: task=b9debuvok idle=0min（本轮巡检自身）
卡住: task=bd2tyr22f idle=238min, task=bqs9mu62q idle=209min, task=bsbhznjio idle=179min, task=b0yvwv204 idle=149min, task=b93ugkspz idle=119min, task=bxixm9up5 idle=89min, task=bbqc3wut7 idle=60min, task=b6xrjmdqd idle=29min（均为历次巡检会话的 sweep 后台任务残留，尾部无 exited/killed 标记）
通道异常: 无（landau status.json ts=2026-08-31 19:40:01 正常返回，42 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: landau job s4_stage2 state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.1 天未更新）；landau job d_verify_blca5 state=failed（RNA_BLCA embedding pkl identifier/embedding 非列表 ValueError，日志约 4.2 天未更新）

## 2026-08-31 20:18
[20:18] 窗口/后台巡检
运行中: task=bcxm7e8vr idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=269min, task=bqs9mu62q idle=239min, task=bsbhznjio idle=209min, task=b0yvwv204 idle=179min, task=b93ugkspz idle=149min, task=bxixm9up5 idle=120min, task=bbqc3wut7 idle=90min, task=b6xrjmdqd idle=59min, task=b9debuvok idle=30min（均为历轮 sweep 后台任务残留，无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-08-31 20:10:01，正常）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED）；9 个 stale 后台任务待清理

## 2026-08-31 20:48
[20:48] 窗口/后台巡检
运行中: task=b7m1jj5zp idle=0min
卡住: task=bd2tyr22f idle=299min, task=bqs9mu62q idle=270min, task=bsbhznjio idle=240min, task=b0yvwv204 idle=210min, task=b93ugkspz idle=180min, task=bxixm9up5 idle=150min, task=bbqc3wut7 idle=120min, task=b6xrjmdqd idle=90min, task=b9debuvok idle=60min, task=bcxm7e8vr idle=30min
通道异常: CHANNEL_DOWN — landau status.json 读不到，通道断了，任务未必死，禁止判死
需要我看的: landau 通道（status.json 不可达，无法确认远端任务状态）；10 个历史巡检后台任务 idle≥20min 未见退出标记

## 2026-08-31 21:19
[21:19] 窗口/后台巡检
运行中: task=bv2n26eqs idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=329min, task=bqs9mu62q idle=300min, task=bsbhznjio idle=270min, task=b0yvwv204 idle=240min, task=b93ugkspz idle=210min, task=bxixm9up5 idle=180min, task=bbqc3wut7 idle=150min, task=b6xrjmdqd idle=120min, task=b9debuvok idle=90min, task=bcxm7e8vr idle=60min（均为历轮 sweep 后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无 — 通道已恢复（status.json ts=2026-08-31 21:10:01，42 个 job 全部 alive=false，无重名、无 dup_count；上一轮 20:48 的 CHANNEL_DOWN 已解除）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 4.3 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.2 天未更新）；10 个 stale 巡检后台任务待清理

## 2026-08-31 21:48
[21:48] 窗口/后台巡检
运行中: task=b5dcu8pkj idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=359min, task=bqs9mu62q idle=330min, task=bsbhznjio idle=299min, task=b0yvwv204 idle=269min, task=b93ugkspz idle=240min, task=bxixm9up5 idle=210min, task=bbqc3wut7 idle=180min, task=b6xrjmdqd idle=150min, task=b9debuvok idle=120min, task=bcxm7e8vr idle=90min, task=bv2n26eqs idle=29min（均为历轮 sweep 后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-08-31 21:40:01，42 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 4.3 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.2 天未更新）；11 个 stale 巡检后台任务待清理

## 2026-08-31 22:20
[22:20] 窗口/后台巡检
运行中: task=bu68v7zm2 idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=389min, task=bqs9mu62q idle=360min, task=bsbhznjio idle=330min, task=b0yvwv204 idle=300min, task=b93ugkspz idle=270min, task=bxixm9up5 idle=240min, task=bbqc3wut7 idle=210min, task=b6xrjmdqd idle=180min, task=b9debuvok idle=150min, task=bcxm7e8vr idle=120min, task=bv2n26eqs idle=59min, task=b5dcu8pkj idle=30min（均为历轮 sweep 后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-08-31 22:10:01，42 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 4.3 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.2 天未更新）；12 个 stale 巡检后台任务待清理

## 2026-09-01 14:16
[14:16] 窗口/后台巡检
运行中: task=b3y5tz5m8 idle=0min（本轮自身）, task=adab9ac42cf7af17a idle=7min（sess=95a27e95）
卡住: task=bd2tyr22f idle=1347min, task=bqs9mu62q idle=1318min, task=bsbhznjio idle=1288min, task=b0yvwv204 idle=1258min, task=b93ugkspz idle=1228min, task=bxixm9up5 idle=1199min, task=bbqc3wut7 idle=1169min, task=b6xrjmdqd idle=1138min, task=b9debuvok idle=1109min, task=bcxm7e8vr idle=1078min, task=bv2n26eqs idle=1018min, task=b5dcu8pkj idle=988min, task=bu68v7zm2 idle=958min, task=bbk0jnzac idle=957min（均为历轮 sweep 后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 14:10:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 5.0 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.9 天未更新）；14 个 stale 巡检后台任务待清理

## 2026-09-01 14:46
[14:46] 窗口/后台巡检
运行中: task=bzg155k4h idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=1377min, task=bqs9mu62q idle=1348min, task=bsbhznjio idle=1318min, task=b0yvwv204 idle=1288min, task=b93ugkspz idle=1258min, task=bxixm9up5 idle=1229min, task=bbqc3wut7 idle=1199min, task=b6xrjmdqd idle=1168min, task=b9debuvok idle=1139min, task=bcxm7e8vr idle=1108min, task=bv2n26eqs idle=1048min, task=b5dcu8pkj idle=1018min, task=bu68v7zm2 idle=988min, task=bbk0jnzac idle=987min, task=adab9ac42cf7af17a idle=37min（sess=95a27e95）, task=b3y5tz5m8 idle=30min, task=buzfpp8ge idle=29min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 14:40:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 5.0 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED）；17 个 stale 巡检后台任务待清理

## 2026-09-01 15:17
[15:17] 窗口/后台巡检
运行中: task=bqmiaeds3 idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=1408min, task=bqs9mu62q idle=1378min, task=bsbhznjio idle=1348min, task=b0yvwv204 idle=1318min, task=b93ugkspz idle=1288min, task=bxixm9up5 idle=1259min, task=bbqc3wut7 idle=1229min, task=b6xrjmdqd idle=1199min, task=b9debuvok idle=1169min, task=bcxm7e8vr idle=1139min, task=bv2n26eqs idle=1078min, task=b5dcu8pkj idle=1048min, task=bu68v7zm2 idle=1018min, task=bbk0jnzac idle=1017min, task=adab9ac42cf7af17a idle=67min（sess=95a27e95）, task=b3y5tz5m8 idle=60min, task=buzfpp8ge idle=59min, task=bzg155k4h idle=30min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 15:10:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 5.1 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 4.9 天未更新）；18 个 stale 巡检后台任务待清理

## 2026-09-01 15:46
[15:46] 窗口/后台巡检
运行中: task=b3j38k320 idle=0min（本轮自身）
卡住: task=bd2tyr22f idle=1438min, task=bqs9mu62q idle=1409min, task=bsbhznjio idle=1379min, task=b0yvwv204 idle=1349min, task=b93ugkspz idle=1319min, task=bxixm9up5 idle=1289min, task=bbqc3wut7 idle=1259min, task=b6xrjmdqd idle=1229min, task=b9debuvok idle=1199min, task=bcxm7e8vr idle=1169min, task=bv2n26eqs idle=1108min, task=b5dcu8pkj idle=1079min, task=bu68v7zm2 idle=1048min, task=bbk0jnzac idle=1047min, task=adab9ac42cf7af17a idle=97min（sess=95a27e95）, task=buzfpp8ge idle=90min, task=b3y5tz5m8 idle=90min, task=bzg155k4h idle=60min, task=bqmiaeds3 idle=30min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 15:40:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 5.1 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED，日志约 5.0 天未更新）；19 个 stale 巡检后台任务待清理

## 2026-09-01 16:16
[16:16] 窗口/后台巡检
运行中: task=but3m7tts idle=0min（本轮自身）
卡住: task=bqs9mu62q idle=1439min, task=bsbhznjio idle=1409min, task=b0yvwv204 idle=1379min, task=b93ugkspz idle=1349min, task=bxixm9up5 idle=1319min, task=bbqc3wut7 idle=1289min, task=b6xrjmdqd idle=1259min, task=b9debuvok idle=1229min, task=bcxm7e8vr idle=1199min, task=bv2n26eqs idle=1138min, task=b5dcu8pkj idle=1109min, task=bu68v7zm2 idle=1078min, task=bbk0jnzac idle=1077min, task=adab9ac42cf7af17a idle=127min（sess=95a27e95）, task=b3y5tz5m8 idle=120min, task=buzfpp8ge idle=119min, task=bzg155k4h idle=90min, task=bqmiaeds3 idle=60min, task=b3j38k320 idle=29min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 16:10:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 5.1 天未更新）；s4_stage2 — state=failed（RNA_INFER_FAILED，日志约 5.0 天未更新）；19 个 stale 巡检后台任务待清理

## 2026-09-01 16:46
[16:46] 窗口/后台巡检
运行中: task=bl7jvklrh idle=0min（本轮自身）
卡住: task=bsbhznjio idle=1439min, task=b0yvwv204 idle=1409min, task=b93ugkspz idle=1379min, task=bxixm9up5 idle=1349min, task=bbqc3wut7 idle=1319min, task=b6xrjmdqd idle=1289min, task=b9debuvok idle=1259min, task=bcxm7e8vr idle=1229min, task=bv2n26eqs idle=1168min, task=b5dcu8pkj idle=1139min, task=bu68v7zm2 idle=1108min, task=bbk0jnzac idle=1107min, task=adab9ac42cf7af17a idle=157min（sess=95a27e95）, task=buzfpp8ge idle=150min, task=b3y5tz5m8 idle=150min, task=bzg155k4h idle=120min, task=bqmiaeds3 idle=90min, task=b3j38k320 idle=60min, task=but3m7tts idle=30min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 16:40:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 非列表，BLCA token_lvl，日志约 5.1 天未更新）；s4_stage2 — state=failed（RNA_INFER_FAILED ec=1 n=0，日志约 5.0 天未更新）；19 个 stale 巡检后台任务待清理

## 2026-09-01 17:16
[17:16] 窗口/后台巡检
运行中: task=b47arzg67 idle=0min（本轮自身）, task=a9abee450a943801d idle=16min（sess=95a27e95）
卡住: task=b0yvwv204 idle=1439min, task=b93ugkspz idle=1409min, task=bxixm9up5 idle=1379min, task=bbqc3wut7 idle=1349min, task=b6xrjmdqd idle=1319min, task=b9debuvok idle=1289min, task=bcxm7e8vr idle=1259min, task=bv2n26eqs idle=1198min, task=b5dcu8pkj idle=1169min, task=bu68v7zm2 idle=1138min, task=bbk0jnzac idle=1137min, task=adab9ac42cf7af17a idle=187min（sess=95a27e95）, task=buzfpp8ge idle=180min, task=b3y5tz5m8 idle=180min, task=bzg155k4h idle=150min, task=bqmiaeds3 idle=120min, task=b3j38k320 idle=90min, task=but3m7tts idle=60min, task=bl7jvklrh idle=29min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: 无（status.json ts=2026-09-01 17:10:01，41 个 job 全部 alive=false，无重名、无 dup_count）
需要我看的: d_verify_blca5 — state=failed（RNA pkl identifier/embedding 必须是列表，BLCA token_lvl，日志约 5.1 天未更新）；s4_stage2 — state=failed（--manifests/--tsv-dirs/--cancers 数量 4/4/5 不一致，RNA_INFER_FAILED ec=1 n=0，日志约 5.0 天未更新）；19 个 stale 巡检后台任务待清理

## 2026-09-01 18:23
[18:23] 窗口/后台巡检
运行中: task=bfzmsd0e4 idle=0min（本轮自身）
卡住: task=bxixm9up5 idle=1430min, task=bbqc3wut7 idle=1400min, task=b6xrjmdqd idle=1370min, task=b9debuvok idle=1340min, task=bcxm7e8vr idle=1310min, task=bv2n26eqs idle=1249min, task=b5dcu8pkj idle=1219min, task=bu68v7zm2 idle=1189min, task=bbk0jnzac idle=1188min, task=adab9ac42cf7af17a idle=238min（sess=95a27e95）, task=b3y5tz5m8 idle=231min, task=buzfpp8ge idle=230min, task=bzg155k4h idle=201min, task=bqmiaeds3 idle=171min, task=b3j38k320 idle=140min, task=but3m7tts idle=110min, task=bl7jvklrh idle=80min, task=a9abee450a943801d idle=67min（sess=95a27e95）, task=b47arzg67 idle=50min（均为历轮 sweep/会话后台任务残留，尾部无 [exited]/[killed]）
通道异常: CHANNEL_DOWN — landau status.json 本轮取不到（上轮 17:10 尚正常）。通道断了，任务未必死，禁止判死。
需要我看的: landau 通道 — 本轮 CHANNEL_DOWN，需人工确认链路；d_verify_blca5 / s4_stage2 — 上轮记录 state=failed，本轮因通道断无法复核；19 个 stale 巡检后台任务待清理
