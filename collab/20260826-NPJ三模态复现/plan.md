# plan.md — NPJ 复现管线：配置修改与阶段 1 文件（Codex 派单契约）

> 派单人：Claude（主控）。执行人：Codex。
> 上游依据：本目录 `HANDOFF.md` §8（改动清单）与 §6.3（阶段 1 文件）。
> Codex 义务（固化于 `~/.codex/AGENTS.md`）：执行中追加本目录 `notes.md`，完成后写本目录 `result.md`。

## 0. 背景（一段话）

骨架仓库 NPJ 已克隆到 **本地工作区 `/Users/wuhao/Desktop/NPJ`**（Codex 只在此编辑；landau 服务器由 Claude 负责，Codex 不得 ssh）。改完并通过 Claude 审查后，由 Claude scp 部署到 landau `/home/wuhao/NPJ`。当前 yml 的 text/rna 路径指向作者未公开的 `TCGA_32types_*` 目录，sh 里是 10 癌种拼接串，直接跑会报错——本任务就是按 HANDOFF §8 修成可跑的 BLCA 单癌种版，并派生阶段 1（UNI2-h）文件。

## 1. 目标

4 个文件：改 2 个（阶段 0）、新建 2 个（阶段 1 派生副本）。全部在 `/Users/wuhao/Desktop/NPJ` 下。

## 2. 分步任务（每步含验收标准）

### A1. 修改 `model/config/surv_multimodal_mainmoe.yml`

| 位置 | 现值 | 改为 |
|---|---|---|
| L10-11（text.path，注释行+生效行） | 生效 `data/text_embeddings/TCGA_32types_text_embedding` | 生效 `data/text_embeddings`（已实测：2,585 个 TCGA-*.pkl 平铺于该目录根，2026-08-26 landau 解压确认） |
| L16-17（rna.path，注释行+生效行） | 生效 `data/RNA_embedding/TCGA_32types_embeddings_2048` | 生效 `data/RNA_embedding` |

不动：img 块（`path: data/tcga-dataset`、`feature_dim: 2048`）、`cancer_types: BLCA`（已正确）、network 块、所有注释行可保留或删除但不得改语义。

**验收**：`yaml.safe_load` 通过；`text.path`、`rna.path` 为上述新值；其余键值与原文件逐项相等。

### A2. 修改 `running_scripts/survival_prediction_mainmoe.sh`

| 位置 | 现值 | 改为 |
|---|---|---|
| L3 | `gpu_id=0,1` | `gpu_id=0` |
| L6 | `cancer_types="UCEC_PAAD_BRCA_BLCA_LGG_LUAD_COAD_READ_KIRC_GBM"` | `cancer_types="BLCA"` |
| L25 | `--cpt_name tcga` | `--cpt_name tcga_orig` |

不动：seeds、lr、epochs、batch_size、network_types、summary 调用、NCCL 两行。

**验收**：`bash -n` 通过；三处 grep 断言命中；其余行与原文件一致。

### B1. 新建 `model/config/surv_multimodal_mainmoe_uni2.yml`

= A1 完成版的完整副本，仅改两处：`img.path: data/tcga-dataset_uni2`、`img.feature_dim: 1536`。text/rna 与 A1 完成版相同。

**验收**：`yaml.safe_load` 通过；img 两键为新值；text/rna/network 与 A1 完成版逐项相等。

### B2. 新建 `running_scripts/survival_prediction_mainmoe_uni2.sh`

= A2 完成版的完整副本，仅改两处：`--model_config model/config/surv_multimodal_mainmoe_uni2.yml`、`--cpt_name tcga_uni2`。

**验收**：`bash -n` 通过；两处 grep 断言命中；seeds/超参与 A2 完成版一致。

## 3. 文件白名单（只允许写这 4 个路径）

```
/Users/wuhao/Desktop/NPJ/model/config/surv_multimodal_mainmoe.yml
/Users/wuhao/Desktop/NPJ/running_scripts/survival_prediction_mainmoe.sh
/Users/wuhao/Desktop/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml      （新建）
/Users/wuhao/Desktop/NPJ/running_scripts/survival_prediction_mainmoe_uni2.sh （新建）
```

另允许写文档：`/Users/wuhao/Desktop/ProtoMaskSurv/collab/20260826-NPJ三模态复现/{notes.md,result.md}`。

## 4. 测试命令（Codex 自测；Claude 审查时原样复跑）

```bash
cd /Users/wuhao/Desktop/NPJ
python3 -c "import yaml; a=yaml.safe_load(open('model/config/surv_multimodal_mainmoe.yml')); b=yaml.safe_load(open('model/config/surv_multimodal_mainmoe_uni2.yml')); assert a['modality']['rna']['path']=='data/RNA_embedding'; assert b['modality']['img']['path']=='data/tcga-dataset_uni2'; assert b['modality']['img']['feature_dim']==1536; assert a['network']==b['network']; print('YAML OK')"
bash -n running_scripts/survival_prediction_mainmoe.sh && bash -n running_scripts/survival_prediction_mainmoe_uni2.sh && echo "SH OK"
grep -c 'cancer_types="BLCA"' running_scripts/survival_prediction_mainmoe.sh          # 期望 1
grep -c 'gpu_id=0$' running_scripts/survival_prediction_mainmoe.sh                    # 期望 1
grep -c 'cpt_name tcga_orig' running_scripts/survival_prediction_mainmoe.sh           # 期望 1
grep -c 'cpt_name tcga_uni2' running_scripts/survival_prediction_mainmoe_uni2.sh      # 期望 1
grep -c 'surv_multimodal_mainmoe_uni2.yml' running_scripts/survival_prediction_mainmoe_uni2.sh  # 期望 1
git -C /Users/wuhao/Desktop/NPJ status --porcelain   # 只允许出现白名单 4 个文件
```

## 5. 禁止事项

- 不得修改白名单之外的任何文件；尤其不得碰 `main_survival.py`（L310 的 bf16 条件修改由 Claude 在冒烟测试后处理）、loss、模型类、`scripts/convert_uni2h_to_npj.py`。
- 不得改 seeds / lr / epochs / batch_size / hidden_size 等任何超参。
- 不得 `git commit` / `git push`。
- 不得 ssh / scp / 访问 landau；不得下载任何数据。
- 不得安装依赖（测试命令只用系统 python3 + PyYAML；若 PyYAML 缺失，在 notes.md 记录，改用 `python3 -c "print(open(...).read())"` 目检并说明）。

## 6. 判定流程（Claude 侧）

1. 读 `result.md`，但结论以独立验证为准：`git -C /Users/wuhao/Desktop/NPJ diff` 逐文件审查 + 复跑 §4 全部命令。
2. 通过 → scp 4 个文件到 landau `/home/wuhao/NPJ` 对应路径 → 冒烟测试。
3. 不通过 → `codex-reply` 附具体失败输出打回；同一问题打回 2 次仍失败 → 停，向用户提替代方案。
