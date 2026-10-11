# I07 结果索引

## i07-ps3-20261011（正式，2026-10-11）

- 源码：S = `3d01b19f44b76f0500a57278b5944406b9ae93d9`（tag `run/i07-ps3-20261011`，run worktree `train/i07-ps3-20261011`）；
  landau `~/NPJ/i07_code/3d01b19f/`（git archive + GIT_STAMP，tar 与 17441 文件逐一 sha256 一致）。100 个 `run.json` 的 commit 均为 S、dirty=False、source=stamp。
- 资产：landau `~/NPJ/i07_assets/v1/`（五份 manifest，加载时逐文件核对）。config.yaml sha256 `8f3b25aa…`（PS3 原值，50 epoch）。
- 范围：5 癌 × 5 折 × {tri, wsi, rna, text} = 100 次训练，经 `launch.py train` + `jobrun.sh`，GPU0，每卡并发 4，`--allow-low-gpu-util`（理由见 `runs/campaign_train.json`）；失败 0。
- 测试授权：摘要 `0b63400dcaa1065cb38f59bc688d84c41391f409c28245a108615057a91fb2ee`（100 个 best.pt + 100 个 run.json + 五份 manifest + S + 评测协议 v2），
  `launch.py evaluate` 按摘要评测 100 个，失败 0。checkpoint 留在 landau，哈希见 `checkpoint-sha256.txt`。
- **输出绑定（节点二首审 high）**：`verify/` 由 `verify_outputs.py` 生成——`output_manifest.json`（100 个 test_metrics.json + 100 个 preds_test.npz 的 sha256；
  与 landau 原件逐一比对 200/200 一致）、`preds_test_all.csv`（全部逐病人风险分，可独立复算）、`verify_report.json`。
  最终结果摘要 results_digest = sha256(核对协议 + 授权摘要 + commit + 输出 manifest + preds_test_all.csv + 逐运行指标) =
  `b71bccf8035d6d07520d9e5a92f5e783d1daf8082a4fed7031faa8d307b78214`（节点二复审后版本）。
  独立复核只需入库文件：`python -m experiments.I07_ps3style_backbone.verify_outputs --recheck experiments/I07_ps3style_backbone/results/i07-ps3-20261011/verify`。
  核对内容：100 个运行齐全、run.json commit/dirty、病人恰为该折 test 划分、time/event 与 cohort 一致、250 项 C-index 用独立逐对实现重算完全相等、填充差极差 1.31e-6。
- 结果表与判定：`render/results.md`；逐运行曲线 `render/curves/`，总览 `render/curves_overview.png`；逐运行原始文件 `runs/`（`preds_test.npz` 按 .gitignore 只留本地）。

### 主结论

- 完整三模态五癌宏平均 C-index = **0.6807**，阈值 0.627 → 按事先规则**保留骨架**。
- 独立单模态宏平均：WSI 0.635 / RNA 0.665 / 文本 0.660；骨架屏蔽单模态：WSI 0.641 / RNA 0.638 / 文本 0.637。
- 三模态并非处处最好：BLCA 三模态 0.596 低于独立文本 0.624 与独立 RNA 0.607；LGG 三模态 0.808 低于独立 RNA 0.824。
- PRIME 参照行只作引用，划分不同，不构成同划分对比。

### 必须一并报告的事实

1. **零填充与训练集均值填充两张表完全相同，这不是代码 bug，是设计必然。** 缺失路的填充向量对所有病人相同，经线性风险头只给全部风险分加同一个常数，排序不变，C-index 必然一致。
   已核实：75 组屏蔽评估中，同一次评估内 "均值填充 − 零填充" 风险差在病人间的极差 ≤ 1.3e-6（浮点误差）。计划书把两者当成两种结果是设计疏漏，结果只算一张表。
2. **普遍早期过拟合，被选模型训练很短。** 冻结规则判定：overfit 70、normal 29、failed 1（BLCA fold0 rna，训练损失降 <5%）。
   所选 epoch：26 个为第 1 个 epoch，76 个 ≤ 5，中位数 3。
3. **规则把 28 个过拟合判成了 normal。** 这 28 个 normal 的最佳 epoch ≤ 25、末轮验证损失 > 1.10 × 最低值，只因最后 10 个 epoch 训练损失已走平（规则第三条"训练斜率 < 0"不满足）。
   规则已冻结，表格照原样报告，这里注明。
