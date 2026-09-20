# S0-force 收尾验收

| 验收项 | 证据位置 | 状态 |
| --- | --- | --- |
| 仅修改 LUAD 强制路由与报告语义；未训练、未新增 checkpoint | `runs/test/complete.json`：`stage=test`、`state_dict_unchanged=true`；Claude r1/r2 | 通过 |
| 冻结开关为布尔真，valid B−A 仍保留 | `frozen-routing.json`；valid A=0.654042、B=0.645226、B−A=-0.008815、`enabled=true` | 通过 |
| LUAD 20格只执行一次，rna/both 走 m1、text 走 m0real | `runs/test/complete.json`：20执行格、`luad_route_counts`；`claude-result-review.md` | 通过 |
| 固定 m1/m0 与非 LUAD 组合复用上游矩阵 | `claude-result-review.md`：200个固定基线与80个非LUAD组合逐格一致；`runs/test/reused-matrix.json` | 通过 |
| 上游归档未被覆盖 | 重新计算根摘要：2.progress=`a8b5f0f99b2034f1b154299827f075771a7761f32a647018d3b5d70a390adf00`；3.progress=`9667b05a011cd29df3ebf2b1b0713ed6d84ced2f09045498fd847803f140c6e0` | 通过 |
| 74项远端资产与25个 checkpoint 的运行前后约束 | `runs/test/complete.json`：`asset_hashes`共74项；`claude-result-review.md` | 通过 |
| GPU 自动化门禁 | `luad_m1_force/config.yaml`：连续两次、利用率严格 `<75%`、可用显存 `>=8192 MiB`；本机/Tako 13项测试均通过 | 通过 |
| 三份结果报告语义 | 三份结果 MD；`claude-result-review-r2.md` | 通过 |
| 报告生成器回归 | 本机与 Tako：13/13 unittest 通过；`luad_m1_force/tests/` | 通过 |
| Claude 结果与代码复审 | `claude-result-review-r2.md`：PASS、无阻断项 | 通过 |
| 本轮源码指纹 | `evidence/post-test-reporting-source-fingerprint.json`记录修订后本机/Tako一致；test发车时自身源码指纹缺失，不能追补 | 边界已披露 |

## 结果摘要

| 范围 | LUAD-m1-force 组合 | m1 | m0real |
| --- | --- | --- |
| 100格主表（含 none） | 0.640506 | 0.631824 | 0.630751 |
| 75格人工缺失（排除 none） | 0.633391 | 0.621348 | 0.620220 |

## 停止结论

- 五癌胜率 = **4/5**（胜：BRCA、LGG、LUAD、UCEC；负：BLCA）。
- 是否达到 4/5 = **是**。
- LUAD 对 m1 仅 `+0.0000351`；valid B<A 已记录，仍为 test 驱动的强制启用。
- 停止：不按 test 改 BLCA、lambda、alpha、w、seed 或训练；不得把本轮结果写成患者检索机制成立。
