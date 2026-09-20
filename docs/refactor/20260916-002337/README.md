# TriModalSurv 重构交付｜20260916-002337

代码试点、资产保全和通用初始化文档已落盘。I01 零训练对拍通过；SVG 已验证嵌入场景和渲染，GUI 编辑保存尚未验收。

## 入口

- [I01 代码与知识入口](../../../experiments/I01_patient_retrieval/README.md)
- [I01 新机制图与文字](../../../experiments/I01_patient_retrieval/knowledge/method.md)
- [I01 结果索引](../../../experiments/I01_patient_retrieval/results/index.md)
- [I02 权重保全](../../../experiments/I02_population_prototypes/results/formal-k8-es15-e100-v1/analysis.md)
- [新实验空壳](../../../experiments/_template/README.md)
- [可直接提供给 AI 的通用初始化 MD](../../templates/experiment-oriented-ml-template.md)
- [STATUS 追加段](../../../STATUS.md#refactor-20260916-002337)

## 已执行与证据

| 内容 | 实际结果 | 证据 |
|---|---|---|
| I02 资产 | 25/25 权重，145677260 字节，大小/MD5/SHA-256 一致；本地与 landau 持久保存 | [权重清单](../../../experiments/I02_population_prototypes/results/formal-k8-es15-e100-v1/checkpoint_manifest.json) |
| 774f 快照 | 6a04a0bf5c283a57e90207899ddffe3867fd5e0a；清单380项，267项进入本次变更提交 | [源码快照](source_snapshots.json) |
| 684e 快照 | 443b27d8fbafa12a458c35e29890146f065c2f17；清单143项，33项进入本次变更提交 | [源码快照](source_snapshots.json) |
| I01 回归 | BLCA seed123 E0，32个test患者，3臂×4格，完整train库；投影/logits/A/B风险差异全部0 | [对拍报告](../../../experiments/I01_patient_retrieval/results/refactor-parity-20260916-002337/audit/parity.json) |
| 配置入口 | 新CLI实际preflight通过；hidden_size=256；从实际模型记录生效值及来源 | [resolved_config.yaml](../../../experiments/I01_patient_retrieval/results/refactor-preflight-20260916-002337/resolved_config.yaml) |
| 测试 | 初次完整66项通过；汇总修复后针对29项通过 | [完整测试](pytest.log)、[修复测试](summary-fix-test.log) |
| 历史保护 | 7758项旧资产逐项检查，333个MD/SVG及35个图片附件；除STATUS末尾追加，无旧资产内容变化 | [保护核验](preservation-verification.json) |
| 通用模板 | 两种初始化场景文字走查，无特定项目数据/服务器/模型预设 | [走查记录](template-review.md) |

## 旧 → 新边界

| 来源 | 新入口 | 处理方式 |
|---|---|---|
| 774f model/fusion_model.py 的 NPJC、SurvivalHead | src/trimodalsurv/models/npjc.py | 逐符号保持，参数键与forward顺序不变 |
| 774f model/compensator.py 的 consistency_loss | src/trimodalsurv/models/consistency.py | 只抽公共辅助函数；I01仍compensator=None |
| 774f model/patient_retrieval_bank.py | experiments/I01_patient_retrieval/model.py | 真实算法迁入；标注投影前填补 |
| 774f scripts/eval_patient_retrieval.py | experiments/I01_patient_retrieval/evaluate.py | 保留核心API，补真实配置和运行清单 |
| 774f scripts/summarize_patient_retrieval.py | experiments/I01_patient_retrieval/summarize.py | 保留完整性校验，识别新布局的3类manifest |
| 根NPJ、根code/NPJ、774f、684e源码 | archive/legacy_npj_snapshot/ | 版本化副本与哈希；旧入口继续保留 |
| 两份历史结果档案 | 各实验results独立历史批次/raw/ | 字节校验复制，原档案保留 |
| 所有旧知识文档与图 | knowledge/index.md的新链接 | 不搬改正文，不回写旧文件 |

精确符号、源文件行号及目标SHA见 [migration-map.json](migration-map.json)。归档文件与额外许可/依赖元数据见 [其他源码清单](other-source-archives.json)、[补充元数据](archive-sidecars.json)。

## 复核与限制

独立审查确认 NPJC、SurvivalHead、检索库、核心评估函数保持原语义，并发现新manifest与旧汇总器的冲突；已修复、补测并复核。详见 [实现与Post-Mortem](implementation.md)。

- I01 对拍使用真实资产的固定工程回归，不新增正式C-index，不验证全部癌种、seed或GPU路径。
- data/training 目前只建立边界包，未迁移其他训练流程；旧入口、原目录继续可用。
- 所有运行目录为新增目录，未覆盖已有结果，未改 tmp_sur_cache。
- [SVG结构记录](../../../experiments/I01_patient_retrieval/knowledge/diagram-validation.md)与[完整渲染](diagram-full.png)已检查；本地 VS Code 访问超时，未证明 GUI 编辑/保存。原场景文件与内嵌数据均保留。
- 根工作区保留在 codex/experiment-oriented-refactor-20260916-002337；仅两份源worktree快照已提交，本轮根目录新增/修改留在工作区，未合并、推送或启动训练。

## 已实跑命令

- [完整远端验证脚本](run_validation.sh)：pytest → 独立旧新对拍 → 新CLI preflight，退出码0。
- [对拍实现](verify_i01_parity.py)：实际模型属性回读、strict加载、中间张量、donor/mask、原始结果和输入哈希验证。
- [保护核验脚本](verify_preservation.py)：只读旧资产并生成独占创建的验收报告；再次执行须先选择新的报告路径，不覆盖既有报告。

本批次到此停止；I02逻辑迁移、其余创新点迁移和正式实验均未启动。
