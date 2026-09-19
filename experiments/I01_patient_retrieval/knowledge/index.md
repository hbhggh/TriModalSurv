# I01 知识索引

## 当前实现

- [机制说明](method.md) · [可编辑 SVG](method.excalidraw.svg) · [Excalidraw 原场景](method.excalidraw)
- [新 model.py](../model.py)：文字标记 `# [创新 I01-01]`；以真实运算位置为准。
- [结果与历史档案](../results/index.md)
- [根 STATUS 追加段](../../../STATUS.md#refactor-20260916-002337)：本次重构的状态入口。

## 原始代码证据

- [固定患者库源码](/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ/model/patient_retrieval_bank.py)：`PROTOCOL_ID`、`valid_row_mask`、`masked_cosine`、`FixedPatientBank`。
- [原评测入口](/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ/scripts/eval_patient_retrieval.py)：`prepare_batch`、`build_model`、`strict_e0_load`。
- [原 NPJC 实现](/Users/wuhao/.codex/worktrees/774f/TriModalSurv/code/NPJ/model/fusion_model.py)：`NPJC.forward` 的 `mean → projector`。

## 旧知识：只保留单向索引

- [旧 code.md](legacy-source/1-M³Surv｜患者级配对检索-code.md)
- [旧 code SVG](legacy-source/1-M³Surv｜患者级配对检索-code.excalidraw.svg)
- [I02 旧人群原型笔记（用于区分机制）](../../I02_population_prototypes/knowledge/legacy-source/1-M³Surv｜患者级配对检索-paper.md)
- [I02 旧人群原型图（用于区分机制）](../../I02_population_prototypes/knowledge/legacy-source/1-M³Surv｜患者级配对检索-paper.excalidraw.svg)

旧文件保留原字节，没有加入反向链接。它们包含不同时间的设计与训练提议；当前协议以本目录标明的代码来源为准，不能把旧提议作为已实现或已授权训练的证据。
