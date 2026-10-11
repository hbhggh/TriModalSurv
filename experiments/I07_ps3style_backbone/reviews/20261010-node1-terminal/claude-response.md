# I07 节点一首审（用户终端运行）：逐条处理（Claude，2026-10-10）

- 审查对象：dev 候选 H = eb811290（`--base main`）。结论 needs-attention，3 条 high，全部采纳。修复提交 62c26fb6。
- 前两次调用失败（xcrun git 在只读沙箱写缓存被拒；本会话进程读 `~/.codex` 被拒）的经过见 `../20261010-node1/claude-response.md`；本次由用户在自己的终端运行。

| # | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|
| 1 | high：训练入口加载并驻留 test 折 | 采纳 | `data.load_fold(parts=...)`；`train.main` 只传 `('train','val')`，`parts` 必须含 train；cohort 标签也只取所需病人 | `test_train_load_reads_no_test_files`：记录全部 `np.load` 路径，断言没有打开任何 test 病人的 WSI 文件、返回结果不含 test 病人。说明：RNA 与文本按癌种存成单个 npz，读文件时 test 行会进内存，但只取 train/val 行建张量，test 行不上设备 |
| 2 | high：测试授权只绑定 ckpt | 采纳 | `provenance.auth_digest` = ckpt 集合 + 五份资产 manifest 的 sha256 + 源码 commit + 评测协议版本；`launch` 的 train/digest/evaluate 先按 manifest 逐文件校验资产内容（`verify_assets`）；`evaluate.main` 另核对 run.json 记录的 commit 与资产指纹等于当前值 | `test_auth_digest_binds_ckpt_assets_and_commit`（三者任一变化摘要即变）、`test_evaluate_rejects_wrong_auth_digest`、`test_verify_assets_catches_modified_file` |
| 3 | high：dirty / unknown 身份照常训练 | 采纳 | `provenance.require_clean`：复用 `trimodalsurv.gitstamp.require_git_identity`（有 .git 读 HEAD，否则读 GIT_STAMP.json，逐文件 sha256 核对 I07 源码闭包），要求 commit 已知、dirty=false、未放行 dirty、等于必填的 `--expected-commit`；train / evaluate / launch 三个入口最前面调用。测试只经 monkeypatch 注入身份，无命令行旁路（坑 I05-06）。"commit 位于 main"由 freeze 流程保证，并在节点二按 AGENTS.md Git 工作流第 9 条用 `git branch --contains` 复核 | `test_require_clean_refuses_*`（dirty / 无 commit / 放行 dirty / commit 不符）、`test_train_entry_refuses_before_any_side_effect`；另用真实 gitstamp 实测：提交前 5 个文件不一致被拒，提交后 62c26fb6 放行 |

- 测试：I07 35 passed；`scripts/ci.sh` 全绿。
- 下一步：按自动审查闭环第 3 条复审一次，输出到 `round2/`。
