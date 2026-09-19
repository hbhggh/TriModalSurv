# 执行台账 — plan: ../研究计划.md

## 当前阶段
2026-09-16：用户批准只修B1/B2、回归、新目录冒烟，并免除本轮Claude再审。三文件最小补丁、43+68回归及20格180记录冒烟完成；旧预测逐数组一致，74项资产未变。当前状态见closure-status-b1b2.json，旧closure快照原样保留；正式valid/test未跑。

## 任务
- [x] Task 0：读取计划、公共纪律与两版台账差异，创建precondition，保存源码快照。
- [x] Task 1：五规则与无参数pooling适配器、失败先行测试。
- [x] Task 2：valid选择器、冻结接口、三份未跑报告与测试。
- [x] Task 3：25权重/45缓存核验、共享评测入口、运行门及证据持久化。
- [x] Task 4：原68+新39测试全部通过；五癌seed123、四场景、九协议CPU冒烟通过，无C-index。
- [x] Task 5本轮增量：B1/B2修复、回归、新目录冒烟完成；用户免除本轮Claude再审，不生成PASS。

## 接口/冲突检查
| 任务 | 产出与消费 | 结论 |
|---|---|---|
| Task 1→3 | prepare_batch返回inputs/audit/pool_weights；无参数forward | 统一见接口契约.md；不同文件所有者 |
| Task 2→3 | build_candidates/choose_validation/render_reports | 行schema共用，test只读选择锁 |
| Task 1自身 | mask bool vs w float；λ0与组合非等价 | 测试明确区分 |
| Task 2自身 | 全局100格、45联合组合、UCEC候选条件 | 不逐癌/seed选参；不混历史test |
| Task 3自身 | 用户写死本机输出根 vs 远端计算 | 本机为唯一交付根；远端隔离运行镜像，回传证据；不覆盖原资产 |
| 门禁 | 实施授权 vs 正式需另行放行 | 按用户计划停在冒烟＋Claude审核，不能自动formal |
| 复审阻塞 | 认证恢复 vs 审核通过 | landau实际请求成功，R2为CONCERNS；认证问题已解除，不生成假PASS |
| 隔离 | 当前linked worktree vs 指定Desktop输出根 | 遵从用户绝对路径，只新增指定目录；公共源码只读并校验SHA |
| 技能流程 | 技能默认commit/评分/删工作目录 | 遵从用户禁止commit、禁止评分、保留证据；不执行这些默认步骤 |

## Bug Post-Mortem
- **现象**: 第一次源码打包命令含不存在的summary.py，tar退出1。
- **根因**: 未先按当前文件清单核对，真实文件名为summarize.py。
- **修复**: 不完整归档改名保留为source-before-incomplete.tar；第二次仅用已核实文件重新创建source-before.tar，exit 0。
- **Prevention Rule**: 源快照必须依据磁盘文件清单，归档退出码成功后才作为验收证据；此项已有V9/V10覆盖，不重复入账。

## 原文件SHA（实施前）
| 文件 | SHA256 |
|---|---|
| experiments/I01_patient_retrieval/model.py | e4e08b0c9ee78da8b2a7c4d01250516693fc087bf567d18ef6a944b27cc10c13 |
| experiments/I01_patient_retrieval/evaluate.py | e92812ef5316b3d0d212deda0e37793e3de84dd9b44410b25ebe7caecb658b5a |
| src/trimodalsurv/models/npjc.py | f0c03c1516a3976ca71ac5f0b8a4b752f3f98a91f44e6abb7f0edcda399eac2f |
| experiments/I01_patient_retrieval/config.yaml | 285ca9f918d4565cf2b1e58f321cc5430153371adf9e19f19bfa48ad8a2d4aa7 |
| src/trimodalsurv/evaluation/common.py | 179d878ef3be4639579a89b7d6b21d9908ebc7fb5d019500d45a85e94d982029 |
