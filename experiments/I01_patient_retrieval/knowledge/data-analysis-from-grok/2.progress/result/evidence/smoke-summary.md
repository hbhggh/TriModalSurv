# 真实valid冒烟结果

> 状态：SMOKE_PASS（CPU前向与契约）；不是正式评测，不含C-index。

| 项目 | 证据 |
|---|---|
| 环境 | tako 既有tcga_env，PyTorch 2.5.0，CPU 4线程、batch_size=16；未占GPU |
| 范围 | 五癌各seed123；四场景；六个新协议代表值＋三固定参考 |
| 数量 | 20个格点、180个协议记录、25位独立valid患者（含天然缺失及LGG补零） |
| 指标 | metrics_computed=false，C-index字段数0；无valid选参、无test前向 |
| 参数 | 冒烟λ=.5、α=1、w=.3；不是赢家。UCEC检索分支仅为冒烟覆盖，不是启用裁决 |
| 资产 | 25原checkpoint及45缓存等74个资产指纹前后一致，使用中state_dict一致 |
| 实际工件 | ../runs/smoke/complete.json、20个cell.json、逐协议NPZ与audit.json |
| 本机/远端 | 35项可执行代码/配置SHA一致；22项macOS元数据单列于deployment-parity.json |

| 癌种 | 场景 | 患者数 | 实际完整检查人数 | 最大logit误差 |
|---|---|---:|---:|---:|
| BLCA | none | 4 | 4 | 0 |
| BLCA | rna_100 | 4 | 0 | null |
| BLCA | text_100 | 4 | 0 | null |
| BLCA | both_100 | 4 | 0 | null |
| BRCA | none | 6 | 4 | 2.384185791015625e-7 |
| BRCA | rna_100 | 6 | 0 | null |
| BRCA | text_100 | 6 | 0 | null |
| BRCA | both_100 | 6 | 0 | null |
| LGG | none | 6 | 5 | 2.384185791015625e-7 |
| LGG | rna_100 | 6 | 0 | null |
| LGG | text_100 | 6 | 0 | null |
| LGG | both_100 | 6 | 0 | null |
| LUAD | none | 4 | 4 | 0 |
| LUAD | rna_100 | 4 | 0 | null |
| LUAD | text_100 | 4 | 0 | null |
| LUAD | both_100 | 4 | 0 | null |
| UCEC | none | 5 | 4 | 2.384185791015625e-7 |
| UCEC | rna_100 | 5 | 0 | null |
| UCEC | text_100 | 5 | 0 | null |
| UCEC | both_100 | 5 | 0 | null |

- 完整检查共21位患者，只计一次；最大误差2.384185791015625e-7 < 1e-6。
- 三个人工100%遮挡场景均0人/null，没有把“未检查”写为零。
- BLCA valid中没有补零患者；LGG valid的1位补零患者已纳入。BLCA train补零参与bank全量校验，新路径另有合成padding测试。
- GPU快照曾有空卡，但本轮仅执行CPU冒烟；GPU门未验收，正式运行需即时再查。
- 后续：Claude只读复审后停止，正式valid/test仍须另行授权。
