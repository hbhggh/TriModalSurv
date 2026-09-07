# code/NPJ 快照来源说明（2026-09-07 JST；NPJ-D 后刷新：model/fusion_model.py 新增 MeanFusion/fusion_type、main_survival.py 与 scripts/eval_missing.py 透传 --fusion_type、scripts/train_launcher.py 预设 d0 + build_eval_command、新增 tests/test_mean_fusion.py。上一版 2026-09-06 20:58：E0m 后刷新）

- 上游：https://github.com/zongzi13545329/NPJ.git（Apache-2.0，LICENSE 随快照保留）
- 基点（上游最后一个未改提交）：`4a3d95e`（Add center split code）
- 本地提交（在基点之上，配置/路径类）：
  - 823efec config: 骨架 uni2 RNA 指向全自制嵌入（用户裁决不用作者公开版）
  - ead3b15 fix: text.path 指向解析后的 text_embeddings_parsed（原公开 pkl 为字符串化向量）
  - a9a1569 config: BLCA 单癌种复现配置（阶段0）+ UNI2-h 阶段1派生文件（Codex 实施，Claude 审查通过）
- 快照 = NPJ 工作树（HEAD `823efec` + 未提交改动 + 未跟踪新文件），排除 `.git`、`__pycache__`、`*.pyc`；共 125 个文件。
- 未提交改动（`git diff --stat 4a3d95e`，含本地提交）：
```
 loc_utils_3yr/tcga_dataset.py                      | 149 +++++-
 main_survival.py                                   | 583 ++++++++++++++++++---
 model/config/surv_multimodal_mainmoe.yml           |   4 +-
 model/config/surv_multimodal_mainmoe_uni2.yml      |  43 ++
 model/fusion_model.py                              | 188 ++++++-
 running_scripts/survival_prediction_mainmoe.sh     |   6 +-
 .../survival_prediction_mainmoe_uni2.sh            |  38 ++
 7 files changed, 905 insertions(+), 106 deletions(-)
```
- 未跟踪新文件（我方新增）：
  - config/gpu_train.yaml
  - model/compensator.py
  - scripts/eval_missing.py
  - scripts/gen_missing_manifest.py
  - scripts/gpu_util_gate.py
  - scripts/launch_formal.sh
  - scripts/train_launcher.py
  - tests/test_mean_fusion.py（2026-09-07）
- `git -C NPJ status --short`（快照时刻，pyc 除外）：
```
 M loc_utils_3yr/tcga_dataset.py
 M main_survival.py
 M model/fusion_model.py
?? config/gpu_train.yaml
?? model/compensator.py
?? scripts/
?? tests/test_mean_fusion.py
```
- 对上游 patch：`code/NPJ_changes_vs_upstream.patch`（15 个 diff；tracked 改动用 `git diff --binary 4a3d95e`，新文件用 `git diff --no-index /dev/null <file>`）。验证：`git -C NPJ apply --check -R` 通过；上游 `4a3d95e` 归档 + patch 与本快照 `diff -rq` 无差异。
- 用法：`git clone https://github.com/zongzi13545329/NPJ && git -C NPJ checkout 4a3d95e && git -C NPJ apply <repo>/code/NPJ_changes_vs_upstream.patch` 即得本快照。
- 运行环境：`code/NPJ/tcga.yaml`（conda）。训练 ckpt / 特征不在仓库内（见 collab/REVIEW_PACK/00_README.md）。
