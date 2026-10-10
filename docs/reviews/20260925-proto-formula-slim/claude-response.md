# Claude 对 Codex 审查的逐条处理（2026-09-25，2.5 节原型补偿公式瘦身）

- 审查原文：同目录 `codex-review.public.json`（原文只把仓库根替换为 `<仓库根>`）。companion `adversarial-review`，`--scope working-tree`，`gpt-5.6-sol`；结论 `needs-attention`，1 项 medium。
- 审查对象：主检出 `main` 工作树中 `manuscript/bmc_initial_draft/main.tex` 的未提交改动（2.5 节 15 式 → 5 式；Scope 两处措辞；Results 删两处 `\eqref` 并补 C-index 全称），以及重编的 `main.pdf`。工作树中其他文件的改动不在范围内。
- 前置：执行前 decision-reviewer 审查了计划（CONCERNS 82/100），提出的 1 高 2 中 5 低已全部并入获批计划。
- 用户裁决（2026-09-25）：Frozen encoder and fusion、Risk score and aggregation 两段连公式带文字全删，正文不写 pooling 降权 w=0.5 与风险口径。
- 闭环判定：唯一 finding 为 medium，采纳与否都只涉及稿件措辞、不改运行逻辑，不属于核心逻辑问题 → 首审放行，不复审。

| # | 级别 | finding | 处理 | 理由与证据 |
|---|---|---|---|---|
| 1 | medium | Top-1 检索缺失确定性与失败边界：式 (2)(3) 只写 cosine 与 argmax，删去了 HEAD 版的三条规则：范数 ≤1e-12 报错、候选集为空报错、并列时按排序 patient ID 取首个 | **不采纳**；另附可选的半句补充，由用户决定 | ① 三项都在用户批准计划的「修订记录：正文删去的事实」里逐条列为删除项，属于本次瘦身要去掉的工程细节。② 两类报错是失败守卫，不是计算规则。触发时直接 `raise ValueError` 中止，不做正则化（`02_wsi_meanpool_key/model.py:19`、`04_wsi_rna_joint_sim/model.py:17`、`inference.py:130–131`）。`4.progress/runs/test/complete.json` 的 300 行齐全（SHA-256 `8604aae4…2260eb6`，与 tex 注释一致），所以进入 Table 1 的每个值在计算时都没有触发守卫；复现者即使改用正则化，也不会在这些值上得到不同结果。③ 并列规则只在 float64 相似度完全相等时起作用。它的代码落点仍保留在 tex 注释（`R2/inference.py: _custom_retrieve`，“patient ID 已排序，argmax 取最前”）和代码 `inference.py:155–156` 里，可以追溯。可选做法：如果希望 argmax 在正文里就是单值，可在式 (3) 后加 “ties are broken by patient identifier”。 |

## 验证（审查前自测；审查后稿件未再改动）

- 编译：`pdflatex` 连跑两次，退出码 0/0；log 无 error、无 undefined reference、无 Rerun。12 条 natbib 引用未定义是既有状态，上次编译同样没跑 bibtex。
- 公式：2.5 节 `\begin{equation}` 共 5 个，编号 (1)–(5)，位于第 3–4 页。`eq:pr-*` 引用已全部清理，没有悬空引用；`sec:prototype-compensation` 的 3 处引用都解析为 2.5。
- 逐字核对（坑 V27）：
  - 被替换的正文块之外，只有计划内的 5 处改动：头注释、Scope 两处、Results 两处。
  - Results 与 Table 1 的 96 个六位数值逐字相同。
  - `concordance` 出现 1 次，即 C-index 全称。
- 新增内容中没有本机绝对路径（坑 I05-04）。PDF 第 2–4 页用 Ghostscript 渲染后逐页目视核对（坑 V29）。

## 执行中的 Post-Mortem

### Bug Post-Mortem 1
- **现象**：Read 工具读取 main.pdf 页面时报 “pdftoppm is not installed”，无法目视核对渲染结果。
- **根因**：Read 的 PDF 渲染依赖 poppler 的 pdftoppm，本机没有安装。
- **修复**：改用 MacTeX 自带的 `/usr/local/bin/gs`（`-sDEVICE=png16m -r110 -dFirstPage/-dLastPage`），把指定页渲染成 PNG 后再读图。
- **Prevention Rule**：PDF 目视验收先用 gs 渲染 PNG；缺少渲染工具不能作为跳过目视验收的理由。

### Bug Post-Mortem 2
- **现象**：用 `grep -c 'Citation .* undefined' main.log` 统计引用警告得到 7 条，与编译前的 12 条不一致，险些误判为引用发生了变化。
- **根因**：TeX 日志按 79 字符折行。key 较长时，“undefined” 会被拆到下一行（例如 “undefine / d”），要求两个锚点在同一行的正则因此漏计。
- **修复**：改用单锚点 `natbib Warning: Citation` 计数，得到 12 条；再按 key 和页码逐条列出，确认与编译前一致。
- **Prevention Rule**：统计 TeX 日志警告时，用警告前缀单锚点计数并逐条列出核对，不用跨越折行的同行多锚点正则。
