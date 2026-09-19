# strategy0：后置验收

| 验收项 | 证据位置 | 状态 |
| --- | --- | --- |
| 上游2.progress未改 | `evidence/preflight.json` 的 `source_hashes` 与 `precondition.md` | 是 |
| 25权重、45缓存、split通过核验 | `evidence/preflight.json` | 是 |
| valid仅决定唯一开关 | `frozen-routing.json` | 是 |
| test只执行一次LUAD 20格 | `runs/test/LUAD/*/*/cell.json` | 是 |
| 固定m1/m0与非LUAD组合复用上游 | `runs/test/reused-matrix.json` | 是 |
| 无训练、无checkpoint、无缓存写入 | `evidence/preflight.json` 与执行入口 | 是 |
| 主表100格、人工缺失75格与三份报告 | 三份根目录MD | 是 |
| 严格癌种胜率达到4/5 | `癌症为单位.md` | 否 |

## 效果目标

- 严格胜率：**3/5**。
- 未胜癌种：BLCA、LUAD。
- valid开关：关闭；本轮不根据test改规则。
- 探索性声明：本轮受已见test启发；LUAD若有变化只能归因于固定路由换填，不可作为患者检索机制成立的证据。

## 指纹

- test 运行指纹：`bfe858ced7933207a151c76dad3d0e291a9ade99664e17e36d6a31b9b24be800`。
- GPU记录：`{"device": "cuda", "gpu_gate": "TWO_IDLE_PID_CHECKS", "gpu_id": 0}`。
- 上游来源数量：8；资产数量：74。
