# 公共代码迁移报告

## 已实现

- `models/fusion.py`：根 T0 的 GatedFusion / MeanFusion / SurvivalHead / MainModalityMoE，参数名称与 forward 原样抽取。
- `models/npjc.py`：684e 的 NPJC 完整类；保留无 inference_only 时根行为，添加无参数状态的 encode_patient_modalities 和 I02 train/eval 分支。SurvivalHead 共用一个实现。
- `models/compensator.py`：CAPRecall、MissingBank及两个mask辅助函数；consistency_loss复用原公共实现。CAPRecallMulti由I04承载，通过工厂注入。
- `data/tcga_dataset.py`：仅迁移生存 Dataset/get_dataset 和分箱函数；分类数据集不纳入活动包。author 与 train_quantile 原实现保留。
- `training/runtime.py`：根公共训练、预测、batch探测、GPU合同；I04生命期通过hook、额外算子通过factory注入。I02生命周期由实验入口协调，公共包不导入实验。
- `evaluation/missing.py`：根缺失评估主体；公共风险、hash、原子写入函数引用 common，weights_only=True且strict=True，不保留不安全pickle回退。
- 公共 scripts 提供 launcher、GPU gate、manifest、训练及评估入口。脚本引导src与checkout根，库不修改sys.path。

## 接口与路径变化

- 新训练/评测CLI必须给 bin_mode；内置launcher预设按历史协议显式附author，dq保留train_quantile；自定义plan须给bin_mode或extra_args。旧CLI参数拼写保持 `--dry_run`。
- 训练支持 `--config`（运行参数mapping或runtime节点），显式CLI覆盖配置；`--dry_run`只解析/构造模型，不构建Dataset、不预热、不写结果。
- config.resolve_config保留显式null/false/0；actual_model_spec同时读取TransformerEncoder与Sequential骨干。
- config目录迁为configs，model YAML迁为configs/models。共享脚本依赖checkout布局，未宣称远端部署。
- 训练在原checkpoint旁独占创建 `.resolved.json`，包含实际模型层、CLI、GPU配置、输入和运行器hash；已有文件拒绝覆盖。历史参数没有补写为effective。
- 公共eval支持model_factory、result_writer、result_metadata、output_suffix供实验注入。

## 验证证据

- `shared-static-validation.json`：16个共享模型/数据/训练符号AST原样一致；语法文件数记录于该证据。后续变更须再跑语法。
- `shared-symbols.json`：初始逐符号来源，补充完整映射另见shared-all-symbols.json。
- `shared-test-map.json`：15个旧测试节点迁移；断言与skip保持，源码定位和模块import随路径调整。CAPL测试由I04负责；test_mlp为归档scattermoe CUDA测试，不纳活动测试。
- 本地标准库实测 false/0/null覆盖通过；`bash -n scripts/launch_formal.sh`通过；launcher e0/dq0 两项dry-run通过，hidden256/lr1e-4/epochs50/batch32，分别author/train_quantile。
- 本地未装Torch，没有声称张量、梯度或checkpoint兼容通过；远端CPU验证由主Agent统筹。

## 仍需验收

- 根/684e的NPJC默认及inference_only、真实checkpoint严格加载、公共合成单步对拍。
- 新旧迁移测试远端实跑及CLI非根cwd；I02/I04注入接口集成。
- 旧根best_metric=0等历史行为保留，本轮不借重构更改科研协议或修复无关逻辑。

### Bug Post-Mortem
- **现象**：首次launcher预检传`--dry-run`被argparse拒绝。
- **根因**：未沿用原接口的下划线参数拼写。
- **修复**：改为原`--dry_run`，实际dry-run两项通过。
- **Prevention Rule**：迁移入口验收以原parser实际参数名为准，不凭命名习惯改拼写。
