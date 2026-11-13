# P2 论文制表：Codex 首审逐条处理（2026-11-12）

- 审查对象：`experiments/I08_ps3_shared_recovery/tools/generate_paper_tables.py`、`experiments/I08_ps3_shared_recovery/tests/test_paper_tables.py`、`manuscript/bmc_initial_draft/tables/`，均为未提交的工作树改动。
- 首审原文：`codex-review.json`（gpt-5.6-sol，working-tree），只留本地。结论 needs-attention，2 条 high。
- 另有一次在首审之前的调用失败：companion 返回 400，`gpt-5.6-sol` 在当时的 ChatGPT 账号下不可用，没有产出结论。失败现场保留在 `.codex-review.iahRvd`。用户开通会员后明确要求重跑，这一次才是首审。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | high | PRIME 原文校验没有接入构建门禁：`--verify-prime-text` 是可选参数；测试用待验证的常量反向合成原文，不是独立证据 | **采纳** |
| 2 | high | 数字溯源审计漏掉整数、指数和重复挪用：只匹配小数和 a/b，按集合比较 | **采纳** |

## 1. PRIME 原文校验改为构建必经门禁

- 新增固定制品 `tools/prime_tables_extract.txt`：Prime.pdf 第 6、8 页 `pdftotext -layout` 的表格块原文，只含表题与表行，不含正文段落。
  - 生成器钉死该文件的 sha256（`PRIME_EXTRACT_SHA256`）和原 PDF 的 sha256（`PRIME_PDF_SHA256`）。
- `build()` 第一步无条件调用 `load_prime_extract()`：先核对哈希，再用 `verify_prime_text()` 比对全部常量。
- `verify_prime_text()` 收紧为按块、按顺序严格比对：
  - Table II 块内正好 19 行，逐行核对名称与 6 个数值；
  - Table IV 只取表头后的前 3 行（Task-1）。
  - 改紧前，用 Task-2 的同名行替换常量也能过；现在会被拒绝。
- CLI 的 `--verify-prime-text` 改为 `--verify-prime-pdf`：对钉死的 PDF 重新运行 pdftotext，要求提取文件的每一行都原样出现在输出里。
- 补测：
  - `test_build_rejects_prime_constant_drift`：把 Img-only 的 Avg 改成 0.999，`build()` 必须抛 ProvenanceError；
  - `test_prime_extract_is_pinned`：改动提取文件，哈希校验必须失败；
  - `test_prime_text_verifier_detects_typo_and_wrong_row`：数值笔误、Task-2 行放到 Task-1 位置，都必须失败；
  - `test_prime_extract_reproduced_from_pdf`：本机有 PDF 和 pdftotext 时，从 PDF 重新提取并逐行比对。本机实跑通过，没有跳过。

## 2. 数字审计改为占位符模板审计

- `Reg.add()` 不再返回数字文本，而是返回唯一占位符。生成器先渲染出含占位符的模板，`audit_template()` 通过后才用 `resolve()` 填入登记文本。
- `audit_template()` 的两条规则：
  - (a) 每个输出文件里，属于它的每个占位符恰好出现一次（预览 md 对应全部登记单元格）。重复挪用、遗漏、混入别表的占位符都会被拒绝。
  - (b) 去掉占位符后，模板里不允许再出现任何数字。只放行三类：
    - 方法与算子标识符（如 `M7`、`A1`、`I07`、`PS3`）；
    - LaTeX 版式参数（`\multicolumn{n}`、`\cmidrule`、列宽、`\label`、`\ref`）；
    - `STRUCTURAL_PHRASES` 里逐字列出的结构短语。架构常量 d=256、r=32 写成 `256-$d$`、`32-$d$`；台账已断言 25/25 折 r=32。
  - 整数（`n=7555`）、超参（`K=11`）、改写过的指数、复制的已登记数字都会被抓住。
- 改造当场抓出 4 处原来漏掉的手写或重复数字，均已改为从数据登记：
  - 表 3、S1、S4 表注里的 "25 cohort×fold"，改为 `len(runs)` 登记；
  - S5 两行共用了同一个 n；
  - S5 的 "ΔE > 0" 阈值，改为文字表述；
  - S1 的 Δ 列多登记了用不到的 p 值，`Reg.paired` 改为只登记实际用到的字段。
- 补测 `test_template_audit_rejects_unregistered_numbers`，覆盖 8 种变异，每种都必须抛 ProvenanceError：新小数、整数计数、超参、改写指数、复制已登记数字、分数、重复占位符、缺失占位符。

## 守卫有效性（删掉守卫就变红）

把 `audit_template`、`load_prime_extract`、`verify_prime_text` 逐个换成空函数，对应测试全部变红（pytest 退出码 1）。首轮的 `check_single_column`、`_reject_test_content` 同样已验证过。

## 复测结果

- `test_paper_tables.py`：26 passed，PDF 复现测试实跑。
- 生成器 `--verify-prime-pdf <Prime.pdf>`：通过。
- 重新生成后，除 S5（一处措辞）和预览外，其余 8 个 .tex 与改造前逐字节相同。
- article 和 sn-jnl 两种类：pdflatex 两遍退出码 0，零 Overfull，表号 1–9 连续。
- `PYTHON_BIN=…/protomasksurv-exp1/bin/python bash scripts/ci.sh`：退出码 0，663 passed / 7 skipped。

## 复审

两条都是核心逻辑问题，修复后按「自动审查闭环」第 3 条自动复审一次，输出写到 `round2/`。

## 复审（round2）结论与状态：停下交用户裁决

复审原文：`round2/codex-review.json`，结论 needs-attention，2 条 high。两条都指向首审修复后仍留着的口子，执行方认可，均判定为核心逻辑问题：

| # | 级别 | 意见 | 执行方判断 |
|---|---|---|---|
| R2-1 | high | PRIME 门禁只核对 `pdf_name` 子串和数值，没有核对输出实际使用的 `name`、`mods`、`group`；改成虚构方法名、错误的模态勾选或错误分组都能通过 | 认可。修法：从钉死的提取文件解析方法名（含引用标记）和 ✓ 列位置，逐项核对 name、mods、group；分别篡改三者时 `build()` 都必须失败 |
| R2-2 | high | `Reg.add()` 接受自由文本，`CellRecord.text` 内部的数字不受审计，可以夹带整数、指数和第二个数值 | 认可。修法：记录改为保存类型化原始值加固定格式器（格式器由 kind/metric 决定），审计时用原始值重新格式化，与记录文本逐字比对；补上在记录文本内注入整数、指数和第二个数值的必红测试 |

按 AGENTS.md「自动审查闭环」第 3、5 条：复审仍有核心逻辑问题，停下交用户裁决，不自动修复后进入第三轮。目前没有提交任何东西，表格数值本身没有受影响（两轮审查都确认表值可重建、单列铁律无违规）。

## 用户裁决与 round2 修复（2026-11-12）

用户明确指示"修复并第三轮复审"。两条 round2 意见均采纳，修复如下。

### R2-1 PRIME 行元数据对照原文校验（采纳）
- `verify_prime_text()` 在数值比对之外，从钉死的提取文件逐行解析：
  - 方法名：去掉 `[n]` 引用编号；
  - 模态 ✓ 列：按表头 Img / RNA / Text 的列位置就近归列。
- 逐项核对每个常量的 `pdf_name`、`name`、`mods`、`group`：
  - `name` 规则：PRIME 自身的 4 行（`PRIME_OWN_ROWS`）为 "PRIME " 加原文方法名，其余行与原文一致；
  - `group` 规则：恰好一个 ✓ 为 uni，否则为 multi。
- Table IV 核对前 3 行的方法名，并要求这一块确实是 Task-1。
- 补测：
  - `test_build_rejects_prime_row_metadata_drift`：分别篡改 name、mods、group、pdf_name，`build()` 都必须失败；
  - `test_build_rejects_prime_table_iv_name_drift`。
- 削弱验证：换回只比数值的旧版校验时，name、mods、group 三项篡改都漏检，测试变红。

### R2-2 记录不再接受自由文本（采纳）
- `CellRecord` 增加 `fmt`、`value`、`bold` 三个字段。`Reg.add(role, kind, key, metric, fmt, value, bold)` 不再接受文本参数，文本由固定格式器 `render_value(fmt, value, bold)` 生成。
  - 格式器只有 `f<d>`、`+f<d>`、`pm<d>.<d>`、`frac`、`int`、`p`、`g` 这几种，并检查参数个数、数值类型和有限性。
  - 每个 kind 只能使用 `ALLOWED_FMTS` 中列出的格式。
- `build()` 新增两道检查：
  - `audit_records()`：每条记录的文本必须与格式化后的值逐字相同；
  - `recheck_i08_values()`：所有 i08_val 记录按 key 和 metric 从台账重算均值与 SD，与记录值精确比对。
- 补测：
  - `test_record_audit_rejects_free_text`：9 种变异，包括额外整数、额外指数、第二个数值、文本与值不符、kind 不允许的格式、未知格式、参数个数错误、非数值、无格式；
  - `test_reg_add_takes_typed_values_only`；
  - `test_i08_values_are_rechecked_against_ledger`。
- 削弱验证：分别置空 `audit_records`、`recheck_i08_values`，对应测试变红。

### 复测
- 改造后 10 个输出与改造前逐字节相同（`--check`：stale none）。`--verify-prime-pdf` 重新提取 PDF 并比对，通过。
- `test_paper_tables.py`：34 passed。
- article 和 sn-jnl 两种类：编译两遍退出码 0，零 Overfull，表号 1–9 连续。
- `ci.sh`：退出码 0，671 passed / 7 skipped。

第三轮复审输出到 `round3/`（用户授权）。

## 第三轮复审（round3）结论：停下交用户裁决

复审原文：`round3/codex-review.json`，结论 needs-attention。round2 的两条 high 已确认封住，PRIME PDF 复提取、类型化记录审计和 I08 台账重算的定向变异核验都通过。另有 1 条新的 high：

| # | 级别 | 意见 | 执行方判断 |
|---|---|---|---|
| R3-1 | high | `load_i07()` 只拿 100 份 `test_metrics.json` 与同样可以改的 `render/results.md` 交叉核对，没有绑定 I07 已入账的 `verify/verify_report.json`、`output_manifest.json` 和 results digest。两者同时被改时漂移会进入 Table 1。磁盘上现有的 100 份指标与 manifest 一致，现有表值没有错 | 认可。修法：钉死 `verify_report.json` 的 sha256，核对其中的 commit、`output_manifest_sha256` 与 manifest 实际哈希；对每份被读取的 `test_metrics.json` 按 manifest 校验哈希；补上"同时篡改指标与 results.md 仍必须失败"的回归测试 |

用户的授权到第三轮复审为止。新问题是否修、是否再审，交用户裁决。目前没有提交任何东西。

## 用户裁决与 R3-1 修复（2026-11-12）：只修复，不再审

用户明确指示"只修复不再审"。R3-1 已采纳并修复，没有发起第四轮审查。

- `load_i07()` 第一步调用 `_load_i07_verified()`，按以下顺序核对：
  - 钉死 `verify/verify_report.json` 的 sha256（`I07_PIN`）；
  - 核对其中的 commit（3d01b19f）与 `output_manifest_sha256`；
  - 再核对 `verify/output_manifest.json` 的实际哈希。
- 每份 `test_metrics.json` 只读一次字节：先按 manifest 校验哈希，再从同一份字节解析（坑 V43）。解析出的 C-index 必须与 `verify_report.json` 中的逐运行指标逐值相等，宏平均与报告的 `macro.full` 一致（误差 ≤ 1e-12）。原有的 `results.md` 交叉核对保留。
- 补测（共 4 项）：
  - `test_i07_rejects_metric_drift_hidden_by_rounding`：数值只改 1e-6，`results.md` 显示不变，仍必须失败；
  - `test_i07_rejects_metric_and_results_md_tampered_together`：复审中给出的场景，指标与 `results.md` 同步篡改，仍必须失败；
  - `test_i07_rejects_tampered_verification_ledger`：分别篡改 verify_report 与 manifest。
- 削弱验证：把 `load_i07` 换回修复前只与 results.md 交叉核对的版本，上述 4 项全部变红，复现了复审指出的绕过。
- 复测：
  - 10 个输出与修复前逐字节相同（`--check`：stale none）；
  - PRIME PDF 重新提取比对通过；
  - `test_paper_tables.py`：38 passed；
  - article 与 sn-jnl 两种类：编译两遍退出码 0，零 Overfull，表号 1–9 连续；
  - 新增与修改的文件无本机路径；
  - `ci.sh`：退出码 0，675 passed / 7 skipped。

审查状态：首审 2 条、round2 2 条、round3 1 条，共 5 条 high 全部采纳并修复。R3-1 的修复没有经过 Codex 复审，这是用户的决定。
