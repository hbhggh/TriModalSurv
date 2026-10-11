# I07 节点一复审（round2）：处理（Claude，2026-10-11）

- 审查对象：候选 H = 486b234c（含首审修复 62c26fb6）。结论 needs-attention，1 条 high。
- 按 AGENTS.md「自动审查闭环」第 3 条：复审仍有核心逻辑问题 → 停下交用户裁决，不自动第三轮。

| finding | 判断 | 拟议修复（待用户裁决） |
|---|---|---|
| high：评估子进程不自行核对授权摘要、资产内容与 ckpt 哈希；直接调用 `evaluate.main` 可绕过授权，调度后替换 ckpt / 资产也不会被发现 | 成立，拟采纳 | `launch evaluate` 把授权摘要与该 run 的 ckpt sha256 作为必填参数传给每个子进程；`evaluate.main` 在读取模型与数据之前：`verify_assets()` 逐文件校验、重算 `best.pt` sha256 与传入值比对、按清单重算完整授权摘要并比对，任一不符即拒；加载权重改为从已核对的字节加载（读一次、算哈希、再反序列化），消除"先查后读"的替换窗口。补测：直接调用入口不带摘要被拒、篡改资产内容但不改 manifest 被拒、核对后替换 ckpt 被拒 |

## 用户裁决与修复（2026-10-11）

- 用户裁决：采纳修复，并由用户在终端再审一次（第 3 轮，用户特批的新审查点），输出到 `../round3/`。
- 修复提交 7b5b48cf：
  - `evaluate.main` 新增必填 `--auth-digest`、`--ckpt-sha256`、`--plan-cancers/--plan-folds/--plan-arms`；读模型与数据之前依次：身份门 → (癌种, 折, 臂) 必须在授权清单内 → `verify_assets()` 逐文件校验 → `best.pt` 只读一次并核对 sha256 → 在完整清单上重算授权摘要并比对；权重从已核对的字节反序列化（`weights_only=True`），没有先查后读的窗口。
  - `launch evaluate` 把授权摘要、该 run 的 ckpt sha256 与清单传给每个子进程。
- 补测（`tests/test_eval_gate.py`，端到端：合成资产 + manifest → 训练 → 授权 → 评估）：正常路径放行；直接调用不带摘要 / 摘要错误被拒；篡改资产内容但不改 manifest 被拒；授权后替换 ckpt 被拒；不在授权清单的 (癌种, 折, 臂) 被拒；发车器把 ckpt 哈希与摘要传给子进程。
- 测试：I07 41 passed；`scripts/ci.sh` 全绿。
