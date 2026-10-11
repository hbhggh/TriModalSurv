# 节点一第 3 轮审查处理（审查对象：dev 候选 ce695373，--base main）

- 审查原文：`codex-review.json`（本地），入库版 `codex-review.public.json`。
- 本轮由来：用户特批的第 3 轮，焦点为 round2 high 的修复 + 2026-10-11 用户裁决 A 新增的接口契约与 config.yaml。
- 结论：needs-attention，2 high + 1 medium。按 AGENTS.md「自动审查闭环」第 5 条停下交用户。
- **用户裁决（2026-10-11）**：「全修，测试兜底，进冒烟」——三条全部修复并补测，不再开第 4 轮；正式结果由节点二整体复核 provenance。

| # | 级别 | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|---|
| 1 | high | 资产先校验、后按路径重读，中间有替换窗口 | 采纳 | `provenance.AssetReader`：构造时一次读入五份 manifest 字节，资产指纹由这份字节算出；`read()` 每个文件只读一次字节、核对 sha256 后返回同一份字节。`data.load_fold` 全部文件（splits / cohort / rna / genes.json / text / wsi）改经 reader 读取并从字节解析；评估入口用同一个 reader 的指纹重算授权摘要、核对 run.json 的 assets_fp，再把 reader 交给 load_fold。训练入口同样走 reader，run.json 的 assets_fp 取自加载所依据的 manifest | `test_asset_replaced_after_manifest_read_is_refused`（manifest 读入之后再替换 WSI 文件 → ValueError，且不写 test_metrics）；`test_train_load_reads_no_test_files` 监视点改为 `AssetReader.read` 并断言确实覆盖了数据读取 |
| 2 | high | 授权摘要未绑定 run.json 与 config 哈希 | 采纳 | `launch.ckpt_hashes` 每个运行同时记录 best.pt 与 run.json 的 sha256，`auth_digest` 两者都入摘要（EVAL_PROTOCOL 升为 v2）；`launch evaluate` 给子进程加传 `--run-sha256`。评估入口 run.json 只读一次、核对哈希后从该字节解析；用这两份已核对字节的哈希替换本项后在完整清单上重算摘要；再要求 `config_sha256` 等于当前 config.yaml、config 等于 yaml 值（唯一允许的差异是欠拟合预案 epochs=100） | `test_run_json_edited_after_authorization_is_refused`；`test_run_config_differs_from_config_yaml_is_refused_even_if_reauthorized`（改 lr、改 config_sha256 → 拒绝；epochs=100 → 放行）；`test_auth_digest_binds_ckpt_run_json_assets_and_commit` 补 run.json 变化 → 摘要变 |
| 3 | medium | `check_output` 只比较 pooled 的键 | 采纳 | `contract.check_output` 逐模态核对：浮点 Tensor、形状 [N, d]、有限值，各模态 d 一致 | `test_model_output_matches_contract` 补 5 个反例（错 batch、错 d、非 Tensor、NaN、整型） |

## 验证

- 变异检查（去掉校验后对应测试必须变红，已还原）：读取不核对哈希 → 2 failed；评估不核对 config → 2 failed（epochs=100 的放行用例照常通过）；不核对 run.json 哈希 → 1 failed；pooled 不查有限值 → 1 failed。
- I07 测试 69 passed；`scripts/ci.sh` 结果见提交说明。
