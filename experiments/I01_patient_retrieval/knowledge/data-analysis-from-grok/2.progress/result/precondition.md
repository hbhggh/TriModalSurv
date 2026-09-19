# 零训练改-------------------------------推理 1–5：前置条件
--
状态：实现门与真实运行门均已在正式执行前满足；用户随后正式授权 valid→冻结→单次 test，并明确豁免本轮 Claude 再审。该文件保留为前置门记录；正式产物与结束核验见 `postcondition.md`、`runs/valid/`、`runs/test/`。

## 实现门-----
----
| 条件-------------------- | 如何核验 | 是否满足 |
|---|---|---|
| 用户批准研究计划及实现范围 | 本轮用户完整计划；协议 patient-fixed-padmask-v2-infer-rules1to5-v1 | [x] 是 |
| 五癌、五 seed、K=128、四场景、B 口径固定 | BLCA/BRCA/LGG/LUAD/UCEC；123/132/213/231/321；none 保留天然缺失 | [x] 是 |
| 五个单点与一个组合的规则明确 | 只用1536维有效行均值 WSI key；RNA投影前均值；λ/α/w 网格及 UCEC 条件已拍板 | [x] 是 |
| 对照不受新规则污染 | 原 retrieval/m1/m0real 固定；新规则只作用新策略 | [x] 是 |
| 公共代码接口已读 | I01 model.py/evaluate.py 与 src/trimodalsurv/models/npjc.py | [x] 是 |
| 改动边界明确 | 新文件仅写本目录；公共模型、原评测器、旧 JSON、缓存、权重不改；不 commit/push | [x] 是 |
| 有效标记与数值 pooling 权重分开 | valid 保持布尔 attention mask；pool_weights 仅控制末端聚合 | [x] 是 |
| 选择/验收规则明确 | valid 全局选参；100格完整性；test一次；数值原值排序；真实模型测试不能跳过 | [x] 是 |
| 已读项目纪律及坑台账 | AGENTS.md、TPBHQ-认知分析引擎.md、docs/engineering/pitfalls.md 全文；另核对工作树 collab/pitfalls.md 的 D18/D19、V31–V38 差异 | [x] 是 |
| 资产不足的处理已批准 | 允许代码与合成测试；真实评测保持阻塞，不编数、不勾完整验收 | [x] 是 |

## 真实运行门

| 条件 | 如何核验 | 是否满足 |
|---|---|---|
| 25份 E0 权重内容、strict load、seed来源和 SHA | evidence/preflight-final.json；与既有正式证据匹配并拒绝跨seed重复。未新增追认训练历史 | [x] 是 |
| 45份三模态 train/valid/test 缓存 | evidence/preflight-final.json、valid-source.json；三split全量内容、形状、有限值、padding及SHA | [x] 是 |
| 标签与历史 test manifest 一致 | evidence/preflight-final.json；valid审计清单另存于冒烟证据 | [x] 是 |
| 运行环境与资源安全 | CPU实跑，4线程，不占GPU；evidence/gpu-observation.log仅为时点快照，正式GPU门另行核验 | [x] CPU路径是；GPU未验收 |
| 原行为与新规则回归通过 | evidence/b1b2-tests-new-tcga.log 43/43；b1b2-tests-legacy-tcga.log 68/68；均无skip | [x] 是 |
| valid 冒烟通过 | evidence/b1b2-run/runs/smoke/complete.json；20格/180记录，无C-index；与旧预测逐数组一致 | [x] CPU路径是 |
| Claude只读复审通过 | R2是修复前CONCERNS；本轮用户明确免除再审，不生成新PASS；豁免记录与正式结果见 `postcondition.md` | [x] 用户正式豁免（非 Claude PASS） |
| 正式 valid/test 明确授权 | 用户后续明确授权；`runs/valid/selection-lock.json` 与 `runs/test/complete.json` 记录实际执行 | [x] 是 |

## 不变边界

- 不训练、不创建checkpoint、不改原WSI/RNA/Text缓存与患者划分。
- 模型WSI输入仍为原128行mean（含历史padding）；检索侧排除补零。
- 本文件仅定义前置边界；正式 B 口径 C-index 结果以三个生成报告与 `runs/test/complete.json` 为准。
- 发现科学决策缺口或资产冲突先报告；不以工具或代码替用户拍板。
