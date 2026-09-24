# Codex 首审逐条处理（A0 候选 H = `3d818dc`）

- 审查入口：`scripts/codex_review.sh`（companion `adversarial-review`，只读，`gpt-5.6-sol`），`--base main` 审 dev 分支。
- 原文：`codex-review.json`（含本机仓库根，按 `.gitignore` 只留本地）；入库副本 `codex-review.public.json` 只把仓库根替换为 `<仓库根>`，其余逐字不变。
- 首审结论：`needs-attention`，3 条 high，全部采纳。按 AGENTS.md「自动审查闭环」第 3 条，修复补测后复审一次，输出在 `round2/`。

| # | finding | 处理 | 修复位置 | 补测 |
|---|---|---|---|---|
| 1 | 审查记录绑定 H，但正式 test 强制要求绑定 S | 采纳 | 新增 `tools/rebind_review.py`：在有 `.git` 的机器上用 git 重算 tree(H) 与 tree(S)，相等且 S 在 `main` 上才写出换绑记录，记录绑定原审查记录的 sha256；`verify` 子命令用 git 复核。`evaluate.py` `check_review_rebind` / `check_test_gates`：审查 commit ≠ 冻结 commit 时必须给 `--review-rebind-record`，逐字段核对（kind、审查记录哈希、H、S、两个 tree 相等且是完整 sha）；用户授权记录必须引用换绑记录的 sha256（服务器无 `.git`，不能重算 tree，所以由用户签署的授权闭合）；审查直接绑定 S 时多给换绑记录也拒绝。README test 门一节写明用法 | `test_test_gates_review_on_candidate_needs_tree_rebind`：H≠S 且 tree 相同时通过；缺换绑、换绑任一字段不符、tree 不等或不完整、授权未引用换绑都拒绝。`test_rebind_tool_proves_tree_equality_with_git`：临时仓库里 squash 得到的 S 通过；tree 不同、tree 相同但不在 main、换绑记录被改都拒绝 |
| 2 | 特征 manifest 未与获审提取器及模型文件绑定 | 采纳 | `config.yaml` 两个 `text_encoders` 档案固定 `model_files_sha256`（锁定 revision 下 8 个模型文件，取自轮 C manifest）；`check_profile_contract` 要求恰好固定这 8 个文件。`evaluate.py` `_feature_manifest`（schema ≥ 2）：`extractor.files` 必须等于当前代码里提取器源码闭包的 sha256（`extractor_source_hashes`），`extractor.git.dirty` 必须是 `false`，`model_files` 必须等于 config 固定值。`extract_text_features.py`：真实后端在编码前就核对模型快照哈希，不符即拒绝 | `test_feature_manifest_generation_identity_gates`：旧提取器源码、dirty 提取器、`model.safetensors` 被换、`model_files` 为空都拒绝；`test_extract_refuses_unpinned_model_files`：快照哈希不符时在写任何特征之前拒绝 |
| 3 | Text 患者集合只做自洽检查，不能阻止 split 身份漂移 | 采纳 | `evaluate.py` `_expected_text_patients`（schema ≥ 2）：manifest 的标签哈希必须等于冻结标签；`reference_dir.listing_sha256` 必须等于运行根 `text_embeddings_parsed` 的清单；manifest 患者集合必须恰为「五癌标签 ∩ 旧 Text 特征」；逐人癌种 / split 必须等于冻结标签。`check_assets`：text 缓存每个 split 的期望患者改为由冻结输入独立推出（有 WSI 的历史缓存 ∩ 有旧特征 ∩ 冻结标签的癌种与 split 相符），再逐人比对；给了 `--legacy-cache-dir` 时再与历史 text 缓存的患者逐人比对（README 上机命令已加这个参数） | `test_feature_manifest_split_must_match_frozen_labels`；`test_equal_count_patient_identity_drift_is_refused`（train 里用无旧 Text 的 T5 等人数顶替 T0，manifest 与缓存自洽、计数不变，旧代码放行，现拒绝）；`test_forged_reference_listing_is_caught_by_legacy_text_keys`（连旧特征目录一起改名时靠历史 text 缓存逐人比对拒绝；正常运行根带该参数通过）；标签哈希、清单哈希负例并入上面的参数化测试 |

范围说明：新增的生成身份门与患者身份门只作用于 schema ≥ 2 的 manifest，也就是 bcmbert8192。bcmbert200（轮 C，已按 negative 收官）的 schema 1 manifest 早于这些字段，本轮不再重跑该档案，所以它的门不变。

## 测试

- I05：`127 passed`（新增 12 项，见上表）。
- 全仓 `scripts/ci.sh`：`356 passed, 6 skipped`，`CI PASS`（修复前 344 passed）。

## 复审（round2，审查候选 `c14b42c`）

- 结论 `needs-attention`，1 条 high：「历史 Text 患者集合核对仍是可选门」。与历史 text 缓存逐人比对的检查只在传了 `--legacy-cache-dir` 时才执行，CLI 不强制。运行根的 `text_embeddings_parsed`、manifest、新特征和缓存如果被同步替换（同一 cancer/split 内等人数换名），就能绕过。新测试只覆盖了传参的情形。
- 判断：成立。finding 1、2 复审未再报问题。
- 处理：按 AGENTS.md「自动审查闭环」第 3、5 条，复审仍有核心逻辑问题，停下交用户裁决，不自动进入第三轮。
- **用户裁决（2026-09-24）**：按推荐修法修复；修复后**不再审**，直接进入候选冒烟（等同用户放行这一条）。
- 修复（采纳）：
  - 在 tako 上只读核验 15 份历史 text 缓存。先核文件 sha256 与已锁定的 `legacy-preflight.json` / `valid-source.json` 逐个相同，再计算按字典序排序的 patient_id 集合摘要，共 2506 人，与提取 manifest 人数一致。
  - 这些摘要固定进 `config.yaml` 的 `legacy.text_keys_sha256`；`load_config` 要求恰好 15 项。
  - `check_assets`：schema ≥ 2 时 text 缓存每个 split 的患者集合摘要必须等于固定值，**无条件执行**。删去了依赖 `--legacy-cache-dir` 的可选分支。
  - 替身证据（`--legacy-preflight` 覆盖）下，摘要取自替身文件。这与既有的缓存哈希同一信任级：这类运行只得 `_SYNTHETIC` 状态，不能进入 test。
- 补测：
  - `test_synced_reference_manifest_cache_tampering_is_refused_without_arguments`：旧特征目录、manifest、新特征、缓存同步等人数换名，不传任何参数也拒绝。
  - `test_formal_runs_take_text_key_digests_from_config`：正式运行只取 config 的 15 个摘要，配置缺项即拒绝加载。
  - 变异检查：把新硬门临时改成不生效，上面第一个负例转红，恢复后转绿。
- 测试：I05 `128 passed`；全仓 `scripts/ci.sh` `357 passed, 6 skipped`，`CI PASS`。
