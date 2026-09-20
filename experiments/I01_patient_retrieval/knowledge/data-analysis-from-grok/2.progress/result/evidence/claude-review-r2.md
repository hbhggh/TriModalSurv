# Claude 只读复审 R2

- 日期：2026-09-16。
- 入口：landau，隔离只读副本；仅 Read/Glob/Grep。
- 结论：CONCERNS，不生成 PASS 票据。
- 原始证据：claude-review-r2-raw.json；实际退出码 0，is_error=false，permission_denials=[]。
- 核验范围：代码、回归证据与 CPU valid 冒烟；未启动正式 valid/test。
- Codex 补充核验：审核副本 35 项源码/规则配置 SHA 与 source-final.json 全部一致。
- 旧认证失败记录保留，认证恢复不等于审核通过。

# 结论：CONCERNS

这个结论只针对"代码 + 回归 + CPU valid 冒烟"这一阶段。冒烟证据本身成立，也没发现伪造或漏跑。但有 2 个问题必须在正式 valid 授权前修掉：一个是研究计划已拍板但代码没实现的要求，另一个会卡住正式授权门。两处都是局部小改，不到 REWORK 的程度。

## 一、需要修正的问题（正式 valid 前必须处理）

### B1. "未生效参数标注"没有实现，锁定表会误导读者
- **计划要求**：研究计划.md:42 写了"未生效参数标注，不解释'最优'"。整个交付目录里 grep"未生效"，只在计划本身出现。
- **原因**：
  - 组合候选里规则①总是开着。除 UCEC 且例外成立外，text_100 全部走 m0real（inference.py:211-224）。
  - 规则④只在 text_100 生效（inference.py:250）。
  - 所以 UCEC 例外不成立的组合候选里，α 在全部 100 格都不起作用。
  - 平局规则（selection.py:396-405）会把 α 不同、其余相同的三个候选判为原值完全并列，然后默认选 α=0.5。
  - 单点候选同样有无效参数，比如 single-r2 会带着占位值 λ=1、α=0、w=1。
- **例子**：`combo-l0-a0p5-w0p2`、`combo-l0-a1-w0p2`、`combo-l0-a2-w0p2` 这三个候选，在 UCEC 例外不成立时，100 格 C-index 完全相同，最后锁成 α=0.5。报告 reporting.py:349-359（冻结参数表）和 :416-435（58 候选表）会把这个 α 当成正常参数打印，没有任何标注。
- **最小修正**：
  1. 在 selection.py:360-379 的候选分数里加一个"未生效"字段，直接按规则结构判断：
     - `3 not in enabled_rules` → λ 未生效；
     - `5 not in enabled_rules` → w 未生效；
     - `4 not in enabled_rules`，或"开了①且 UCEC 例外不成立" → α 未生效。
  2. 锁文件带上这个字段；reporting 在两张表里对应位置显示"未生效"。
  3. 补一个 α 并列的合成测试。

### B2. 远端源码指纹混入 macOS `._` 元数据，正式授权门会卡住
- **位置**：runtime.py:126 的 `rglob('*.py')` 和 :132 的 `glob('*.py')` 没有排除点开头的文件，`._npjc.py`、`._run.py` 这类元数据都会被算进去。
- **已核实**：runs/preflight/complete.json 里有 22 处 `._`，evidence/preflight-final.json 和 smoke-final.json 各匹配到 20 处，本机 source-final.json 里 0 处。也就是说远端源码指纹是 57 项，本机是 35 项。
- **会怎样出错**：
  - 用本机 35 项做 Claude PASS 记录，到 tako 上跑正式阶段时，runtime.py:153 会报"审核对应源码指纹已改变"并拒绝运行。
  - 用远端 57 项做记录，审核就绑定到了非代码文件上，以后增删一个元数据文件都会让门失效。
- **最小修正**：在两处 glob 里跳过以 `._` 或 `.` 开头的文件名，或者先清掉远端元数据。
- **需要你拍板**：不管用哪种办法，指纹都会变。现有 preflight 和 smoke 的指纹会对不上（run.py:212 会拒绝，smoke 目录的 campaign.json 也已绑定旧指纹），需要在新运行目录里重做 preflight 和冒烟。这一步是否做、何时做，由你决定。

## 二、不阻断的限制

1. **正式 valid 耗时可能很长**：规则②每次打分都重算查询和 donor 的均值（02_wsi_meanpool_key/model.py:23-26，在 inference.py:131-140 的 donor 循环里），没有缓存。④的 RNA 均值（04/model.py:13-14）也一样。donor 的均值键与查询无关，但 46 个含②的候选都会重复计算。建议正式授权前先实测一格耗时，或预先算好 donor 键（结果不变）。
2. **历史重放不区分阶段**：run.py:137-147 读旧 JSON 时不按 `stage` 过滤。如果旧目录里还有 smoke 子目录，会触发"历史格点重复"，结论变成 BLOCKED，但报告仍会声明"不可比"，属于安全失败。审核副本里没有旧结果目录，所以没法核对真实结构。
3. **恢复时不重算 C-index**：verify_cell（runtime.py:303-361）会核对工件 SHA、患者全集、候选全集和诊断，但不从 NPZ 重算 C-index。改动 cell.json 里的 `c_index_b` 查不出来。
4. **兜底路径不报错**：inference.py:195-197 里，如果某个 spec 没开任何规则、协议名又不是三参考之一，会静默当作 retrieval 处理。候选构造器不会产生这种 spec，只是防御上不够。
5. **valid 与 test 必须同设备同卡**：science_config 绑定了 device 和 gpu_id（runtime.py:115）。如果 test 时原卡被占，换卡会让选择锁失效。
6. **CPU 冒烟不等于 GPU 通过**：CPU 上完整患者 logits 最大误差是 2.38e-7，这和公共 evaluate.py:301-304 已记录的 FP32 嵌套张量路径一致，但 GPU 未验证。BLCA 的冒烟患者全部完整、无补零，none 场景下的检索靠其他癌种覆盖。
7. **我没法核对的部分**：只读工具不能计算 SHA，所以 35 项一致性、74 个资产前后不变、39/39 和 68/68 测试都是依据现有日志和 JSON 核对的，不是我重新执行得到的。valid 缓存与 train/test 是否同源，只能靠 valid-source.json 的 SHA 清单。

## 三、已核验通过的项目

- **三个参考没被污染**：
  - 不开规则时走 `bank.compensate` 原逻辑，pool 权重全为 1。
  - weighted_forward 在 w=1 时与 npjc.py:121-125 逐项等价（img 始终有效，`clamp_min(1)` 不会触发），有 w1 对原 NPJC 的测试。
  - 风险口径和 C-index 调用与 evaluate.py:311/331 一致。
- **五个单点只开自己**，组合为 `[1,2,3,4,5]`；共 58 个候选，组合是 5×3×3 联合网格。未开②的单点仍用原 padmask 展平打分（`_flatten_wsi_score` 与 `masked_cosine` 等价）。
- **①**：text_100 整个场景走 m0real，天然缺 RNA 的患者也不补（有测试，冒烟 BRCA 的审计记录为 `rule1_m0real`）。UCEC 例外只看 UCEC/text_100 五 seed 均值是否严格大于 m0real。其余四癌在推理和选择两处都固定为 m0。
- **②**：只用有效行 1536 维均值，用 bank.mean（train 患者等权）去中心，float64 计算；原模型 128 行 mean 输入不变。
- **③**：float64 计算，λ=0/1 直接复制端点；λ=0 与 m1 填值相同；双缺同一 donor、同一 λ。
- **④**：仅 text_100 且本人天然 RNA 可用时生效；donor 必须 RNA 和 Text 都有。冒烟里 BRCA 天然缺 RNA 的患者正确回落到普通检索。
- **⑤**：只改末端 pooling 权重，布尔 mask 不变，state_dict 前后一致。
- **选择**：先筛双基线可行，再比 100 格等权均值，平局依次比小 λ、小 w、小 α；test 只读经 SHA 校验的 valid 锁，并核对配置、源码、资产和环境。
- **诊断**：没有完整患者时误差为 null；有完整患者时每人只计一次；场景人数与实际可用性一致，同格所有协议的诊断二元组一致，容差 1e-6。
- **恢复与写入**：已完成单元不覆盖；JSON 先 fsync 临时文件再用硬链接原子发布；没有 cell.json 的残片会被隔离；恢复时核对格点、患者、候选、权重和工件全集。
- **报告**：要求同一 test 批次指纹、9×100 完整格；用原值排序标红，Δ 先减后舍入；历史重放不一致时声明不可比。
- **状态文档**：三份结果 MD 都是"未跑"；`formal_approved=false`；runs/ 下没有任何 `c_index` 字段；precondition 和 postcondition 没有虚报。

---

**即使 B1、B2 修完、本阶段转为 PASS，正式 valid 选参和 test 仍须你另行明确授权；本次审核不构成执行许可。** 另外说明：本轮只读，没有写审核 PASS 记录文件，也没有打分。
