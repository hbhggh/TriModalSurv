# I08 节点一首审：逐条处理（Claude，2026-11-08）

- 审查对象：dev 分支 `3848fbac..9fff63a0`（4 个 I08 提交：契约扩展、算子与损失、缓存导出器、训练评测与报告）。
- 审查方式：`scripts/codex_review.sh <本目录> --base 3848fbac`（companion adversarial-review，gpt-5.6-sol，只读），经 Terminal 面板运行。
- 结论：needs-attention，3 条 high，均为核心逻辑问题（test 隔离、provenance），全部采纳，修复后按闭环复审一次（`round2/`）。
- 原文：`codex-review.json`（本地，含本机路径，按 .gitignore 不入库）；入库版 `codex-review.public.json`（仅仓库根替换为 `<仓库根>`）。

| # | 级别 | finding | 处理 | 修复位置 | 补测 |
| --- | --- | --- | --- | --- | --- |
| 1 | high | train/val 缓存路径仍会读取 test 标签与特征（I07 `load_fold` 先解析完整 splits/cohort 与癌种级 RNA/text 数组） | **采纳**（附残留边界，见下） | `cache.TrainValReader`：包住 I07 `AssetReader`，完整性核对后立即剔除 test 行——splits / cohort 只留本折 train/val 患者，RNA / 文本 npz 按行重建，test 患者的 WSI 文件拒读（`PermissionError`）；`cache.main` 改用该代理调用 `load_fold(reader=...)` | `test_trainval_reader_never_hands_test_rows_to_loader`：间谍记录交给 `load_fold` 的每一份字节——CSV 中不含任何 test id，npz 解析后 `patient_ids` 恰为 train/val 且特征行数相符，未请求任何 test WSI；张量与原路径逐值相同（预处理不变）。变异检验：关闭 npz 行过滤后该测试变红 |
| 2 | high | checkpoint 登记表未绑定源码身份门（`checkpoint-sha256.txt` 不在 SOURCES，且 GIT_STAMP 不覆盖 .txt）；run.json 未绑定 | **采纳** | 新增 `i07_registry.py`（25 个 tri 的 best.pt 与 run.json sha256，.py 受身份门与 GIT_STAMP 覆盖）；`load_backbone` 两项哈希都必须等于登记值；`config.backbone.results_run` 须等于登记批次 | `test_registry_module_matches_repo_files`（登记模块与仓库 txt / run.json 逐项一致，SOURCES 只含 .py/.yaml）；`test_load_backbone_rejects_tampered_ckpt_or_run_json`（ckpt、run.json 任一不符或未登记即拒）。变异检验：只核 ckpt 时该测试变红 |
| 3 | high | train_eval 可从未验身份的自签缓存生成报告（`--expected-commit` 可省、manifest 只自证） | **采纳** | `run`：`--expected-commit` 与 `--cache-manifest-sha256` 改为必填；manifest 字节摘要须等于给定值；`cache.verify_cache_manifest` 完整核对 schema、导出 commit（干净、为当前 HEAD 祖先）、导出时缓存相关源码逐文件 sha256 与当前一致、config 的 backbone/features 视图、划分/视角、癌×折恰为 config 全集、每折 ckpt/run.json 哈希等于登记、D0 < 1e-6；`--cancers/--folds` 不得超出 config。`report`：拒绝 `verified` 非真、config 不同、非全集、冒烟（`--max-epochs`）或缺折的运行。测试放宽只经 monkeypatch（I05-06），不挂 CLI | `test_verify_cache_manifest`（9 种篡改均拒）；`test_cli_requires_identity_and_frozen_manifest`；`test_report_rejects_unverified_or_smoke_runs`；`test_real_cli_path_rejects_self_signed_manifest`（不放宽时自造 manifest 被拒） |

## finding 1 的残留边界（需用户知悉）

癌种级共享文件（`splits.csv`、`cohort.csv`、`rna_<癌>.npz`、`text_<癌>.npz`）把 train/val/test 患者存在同一个文件里。
`AssetReader` 为做 sha256 完整性核对仍会把整份字节读入内存；`TrainValReader` 在核对后立即丢弃 test 行，
test 患者的 id、标签、特征不会进入 I07 `load_fold` 或任何后续数据结构，也没有任何 test 前向。
要做到字节级不接触，只能把资产按 split 重新打包（一次新的数据转换，本身也要读一次完整文件），超出本任务授权，未做；如需要请用户裁定。
I07 正式训练入口（`train.py`，经节点一审查）对同一组文件的处理与此相同，本修复比它更严。

## 测试

- I08 全部单测：70 passed。
- 全仓 CI：见提交前运行记录（`PYTHON_BIN=<protomasksurv-exp1>/bin/python bash scripts/ci.sh`）。
