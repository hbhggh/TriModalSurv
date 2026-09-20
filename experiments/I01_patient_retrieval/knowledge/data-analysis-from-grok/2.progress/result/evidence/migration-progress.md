# hitode 迁移记录

| 项目 | 已核验事实 / 当前状态 |
|---|---|
| 用户授权 | 允许检查并迁移到 hitode/landau；沿用已批准的零训练加速与复审豁免 |
| hitode | GPU 2，A100 40GB；开始复制时无计算进程，3MiB 显存 |
| landau | 两张 V100 均有计算进程，不抢占 |
| 环境 | 不使用版本不同的 dnabert2；复制 tako tcga_env 到同一绝对路径 |
| 资产 | 复制既有缓存、权重、标签、清单、冻结源码与历史参考，不重建 |
| 新运行根 | /tmp/npj_rules15_migrate_20260916_ZDKqbH |
| 传输 | 初始本机中转慢，停止其四个已核对 SSH PID；改为内网 rsync 校验传输 |
| SSH 安全 | 目标 ED25519 公钥经已认证 hitode 会话读取并与内网扫描一致；临时 agent 生命周期仅限复制进程，不复制私钥 |
| 结果边界 | 旧 formal 的七格 valid 不进入新矩阵；旧 tako 对拍作为独立参考 |
| 门禁 | 源码/74资产哈希 → 50测试 → preflight → 20格 valid 对拍 → 跨GPU核验 → smoke → valid → 冻结 → test → 审计 |
| 当前状态 | 复制完成；hitode supervisor PID 597654 已启动，50 回归测试通过，正执行 preflight；valid/test 尚未启动 |
| 资产传输 | 9,358,282,198 bytes；第二次 rsync checksum 检查 exit 0、0 文件需重新传输 |
| 环境传输 | 7,395,546,905 bytes，exit 0；PyTorch 2.5.0、NumPy 2.0.1、scikit-survival 0.23.1，与 tako 一致，CUDA 可用 |
| 后续核验 | 五癌 preflight ASSETS_VERIFIED，50 tests OK；迁移对拍进行中，全部通过后脚本才进入 smoke/valid/test |
| 持续跟进 | 当前线程 heartbeat i01-hitode，每15分钟；无变化保持安静，失败/完成才通知；完成交付后暂停 |

## 迁移核验停机（最新状态）

- supervisor 597654 已退出，exit=1；未进入 smoke、正式 valid 或 test。
- hitode 同机原版/加速版：20格×61候选共1220份预测逐值一致，源码与74项资产哈希未变。
- tako V100 对 hitode A100：logits 最大绝对差 2.86102294921875e-6（485份数组超过1e-6）；risk 最大差7.152557373046875e-7。
- 1220份审计的 donor、mask、路由及其他非分数字段全部相同；仅 similarity/score_wsi/score_rna 存在差异，最大分别8.881784197001252e-16、2.220446049250313e-16、5.551115123125783e-16。
- valid 冒烟患者风险排序及1e-8并列关系均未变化；未计算C-index，不据此推断全量结果相同。
- 证据：migration-difference-diagnostic.json、hitode-crossgpu-parity.log、hitode-process-exit.txt。
- 待用户选择跨机器容差；原门禁未修改，heartbeat i01-hitode 已暂停，禁止自动重启。

### Bug Post-Mortem
- **现象**: 跨机器核验在logits绝对差1e-6处失败，同机原版/加速版却逐值一致。
- **根因**: 新增迁移门禁将跨硬件输出要求与同机一致性门混用，并要求跨CPU相似度逐值一致；已证实差异限于浮点值，具体底层算子尚未逐层定位，不能声称已证明无全量指标影响。
- **修复**: 未放宽门禁；完成全部1220份预测和审计的只读差异统计，保留失败记录，暂停自动跟进并请求用户单独裁决跨机器容差。
- **Prevention Rule**: 同机加速等价性与跨硬件可复现性分别定义并预先批准容差；身份、donor、mask、路由严格相同，数值差异单列且不得据冒烟外推全量指标。

### Bug Post-Mortem
- **现象**: 迁移时发现旧配置的 source_snapshot 路径不存在，rsync 对该项报缺失。
- **根因**: 旧配置保留了未落盘的快照路径；该字段不在实际资产门禁消费者中。
- **修复**: 新 hitode 配置显式引用本地已存在的 acceleration-before.tar 副本；旧配置与证据不改。
- **Prevention Rule**: 迁移时除运行资产哈希外，逐项核对所有声明的证据路径，缺失引用不能当作已归档。
