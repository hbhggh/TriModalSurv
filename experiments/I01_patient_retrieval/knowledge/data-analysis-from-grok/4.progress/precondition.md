# precondition：S0-force 强制 LUAD 路由

## 实现门

| 条件 | 如何核验 | 是否满足 |
|---|---|---|
| 协议与唯一改动已锁定 | `研究计划.md`：仅将 `enabled` 固定为 JSON 布尔 `true`；路由表与 3.progress 相同。 | 是 |
| Claude 计划审核允许进入下一阶段 | `claude-plan-review.md` 的最终结论允许进入；C1–C9 均已转入本表或后续硬断言。 | 是（附条件） |
| 2.progress 只读基线已登记 | 全目录 15,163 个文件的确定性目录哈希：`a8b5f0f99b2034f1b154299827f075771a7761f32a647018d3b5d70a390adf00`。上游 test 指纹：`32cb3f31579bec549214d8577ac3fe057edb84b8a3fac49989c7e86090c94f14`。 | 是 |
| 3.progress 只读对照已登记 | 全目录 151 个文件的确定性目录哈希：`9667b05a011cd29df3ebf2b1b0713ed6d84ced2f09045498fd847803f140c6e0`；test 指纹：`bfe858ced7933207a151c76dad3d0e291a9ade99664e17e36d6a31b9b24be800`。 | 是 |
| 可复用 valid B 的来源明确 | `3.progress/runs/valid/complete.json` 指纹 `f8f21987e3028ed8fb1512dbb4ce36c61073ab2c96c583a73dd678d36b766941`；其 61 个 `LUAD` valid 工件聚合哈希为 `1f5a0b2c66f66a8ab46aafaeccf96efb7b25f7cbc45a437a42cbe3183f994f0b`。该批 B 本来就在 `strategy0_enabled=true` 下运行；本轮只复用它作 valid 审计，不复用 3.progress 的 LUAD test。 | 是 |
| 复用来源代码一致 | 本机与 Tako 的上游八项来源 SHA 一致：`config.yaml`、`inference.py`、`reporting.py`、`run.py`、`runtime.py`、`selection.py`、`runs/test/complete.json`、`runs/valid/complete.json`，值见 `claude-plan-review.md` 与既有 3.progress 记录。 | 是 |
| 新写入范围隔离 | 本机仅写 `/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress`；Tako 仅写 `/home/wuhao/npj_strategy0_force_luad_20260917`。后者在检查时不存在，且与 `/home/wuhao/npj_rules15_accel_20260916_Ob6fjB`、`/home/wuhao/npj_strategy0_luad_20260917` 不同。 | 是 |
| 禁止范围已写明 | 不改 E0 权重、缓存、split、K=128、BLCA、λ、α、w、seed、网络；不训练、不 commit/push。 | 是 |

## Claude C1–C9 的硬约束

| 编号 | 约束 | 运行前落实方式 | 是否满足 |
|---|---|---|---|
| C1 | LUAD `rna_100`／`both_100` 必须等价 m1；`text_100` 必须等价 m0real；`none` 输出逐患者路由计数。 | 新测试已通过；test 后仍以逐 logit／C-index 断言为准，不以“与 3.progress 不全等”替代。 | 单元测试通过；真实 test 待运行 |
| C2 | 非 LUAD 的复用行不得将开关写成 `false`。 | 序列化为 `route=upstream_combo`、`strategy0_enabled=null`。 | 单元测试通过；真实矩阵待运行 |
| C3 | valid B 复用凭据完整且理由正确。 | 仅消费上述 `enabled=true` 的 valid 61 工件及其来源／资产哈希；协议名不同不将 run fingerprint 误判为不一致。 | 是 |
| C4 | 本机／Tako 执行根和白名单分离。 | 本表“新写入范围隔离”；任何输出落入 2.progress 或 3.progress 均报错。 | 是 |
| C5 | 上游两目录前后均核验。 | test 前后重新计算本表两项目录哈希；任何差异阻断。 | 待运行前后核验 |
| C6 | Tako 资产与本机上游一致。 | 运行门使用上游 74 项 `asset_hashes`（25 checkpoint、45 cache、标签、manifest 等）重新预检；不通过不启动 test。 | 待远端预检 |
| C7 | 归因边界准确。 | 冻结文件、总报告、seed／癌种报告、postcondition 都写“LUAD 按场景切换到固定 m1/m0real”。 | 待报告生成器断言 |
| C8 | 平局结构显式披露。 | 三份报告列出：`rna_100`／`both_100` 是 m1 副本、`text_100` 是 m0real 副本；由已见 test 启发。 | 待报告生成器断言 |
| C9 | 泄漏与 4/5 非验收声明覆盖全部产物。 | `frozen-routing.json`、三份结果报告、postcondition 必须含 valid B−A<0、强制开启、test 泄漏、4/5 仅探索性反事实。 | 待报告生成器断言 |

## 运行门

| 条件 | 如何核验 | 是否满足 |
|---|---|---|
| 25 权重与 45 份缓存 | 远端运行前预检必须与 3.progress 的 74 项资产哈希完全一致；不接受“文件存在”替代。 | 待预检 |
| 共享 GPU（用户显式授权） | 四机任一张卡相隔 2 秒两次采样均满足利用率严格 `<75%`、可用显存 `>=8192 MiB`；记录 PID、利用率及显存，但 PID 不再单独否决。8 GiB 是运行安全下限，不改变科研协议。 | 12:12 的 Tako GPU1 两次采样分别为 97%／0%，重采样为 81%／100%，均未通过；后续采样按用户更新的 `<75%` 门槛执行，证据见 `evidence/prelaunch-shared-gpu1*.txt`。 |
| 强制冻结 | `frozen-routing.json` 的 `enabled` 必须为布尔真，`decision_rule` 必须含“强制启用”。 | 待代码生成 |
| 行为门 | C1/C2 测试、上游只读哈希复核、真实 valid 冒烟全部通过。 | 待实现与冒烟 |

## 研究声明（不可删除）

- `3.progress` 的 valid B−A=`−0.008815`，仍强制 `enabled=true`；本轮是使用已见 test 设计的**探索性反事实**，存在 test 泄漏，不是盲测或独立确认。
- LUAD 任何改善只能表述为**按场景切换到固定 m1/m0real**；不能归因于患者检索机制成立。
- `rna_100`／`both_100` 设计为 m1 的精确副本，`text_100` 设计为 m0real 的精确副本；平局不是患者检索胜利。

## 门禁结论

- 实现门：**通过**。可进入测试先行的路由实现。
- 运行门：**未通过／未到达**。远端资产预检、冻结文件与用户授权的共享 GPU 双采样通过前，禁止 valid 或 test。
