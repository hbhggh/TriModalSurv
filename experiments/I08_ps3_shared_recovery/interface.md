# I08 接口定义：A1 + B1 + C1 接入 PS3-style 骨架

> 故事线：主目录 `03_index-故事线 A-1｜患者级动态恢复_v1.md`（A1-B1-C1）。超参数与张量登记：`config.yaml`；强制核对：`contract.py`。
> 状态（2026-11-08）：已实现 handoff v1（主目录 `患者级动态恢复_v1.handoff.md`）的 A1 + B1/B3/B5/B6 + C1 与 M0–M10 消融；开发期 val 实验（用户裁定 2026-11-08：val 同时用于选参与报告，不进论文主表）；全程不读 test。

## 1. 网络中的位置

```
原始数据 → 冻结 encoder → token → PS3 融合（单层 9 块注意力）→ f_β → head_ln → 有效 token 均值
                                                                         │
                                                         pooled[m] ∈ R^{B×256}   ←── 接入点（旧编号 B4）
                                                                         │
     ┌───────────── Ω = {R,W,T}（完整）──────── 直通，不经 A/B ──────────┤
     │                                                                    │
     │  Ω ⊂ {R,W,T}（缺失）：p^Ω_m（可见，原样） ─────────────────────────┤
     │        └─ A：z_m = U_mᵀ(p^Ω_m − μ^Ω_{Ω,m}) ∈ R^{B×r}               │
     │             └─ B：ẑ_u = R_{Ω→u}·[z_m]_{m∈Ω} + b_{Ω,u} ∈ R^{B×r}    │
     │                  └─ 解码：p̂_u = μ^F_u + U_u ẑ_u ∈ R^{B×256} ───────┤（只填缺失位）
     │                                                                    ▼
     │                                   拼接 [rna | wsi | text] ∈ R^{B×768} → 冻结 Linear(768→1) → risk ∈ R^B
     │
     └ 训练期 C（虚线，不进推理）：L_modal 作用在 z^F；L_cons 作用在 ẑ 与 sg(U_uᵀx^F_u)
```

## 2. 张量接口（与 `config.yaml: tensors` 一一对应）

| 名称 | 形状 | 类型 | 位置 / 来源 | 回传梯度 |
| --- | --- | --- | --- | --- |
| p_full | [B, 256] | float32 | I07 `pooled[m]`，present = 三模态 | 否 |
| p_vis | [B, 256] | float32 | I07 `pooled[m]`，present = Ω，m ∈ Ω | 否 |
| mu_full | [256] | float32 | 本折 train 的 p^F_m 均值 | 否 |
| mu_pattern | [256] | float32 | 本折 train 的 p^Ω_m 均值，按 (Ω, m) 存 | 否 |
| U | [256, r] | float32 | A，每模态一套，正交参数化 | 是 |
| z_vis | [B, r] | float32 | A 输出，可见模态共享坐标 | 是 |
| z_full | [B, r] | float32 | A 输出，完整表示的共享坐标（只供 C 与 L_cons 目标） | 是 |
| b_in | [B, k·r] | float32 | B 输入，可见 z 按 rna→wsi→text 拼接，k = \|Ω\| | 是 |
| R | [r, k·r] | float32 | B，每个 (Ω, u) 一个 | 是 |
| bias | [r] | float32 | B，每个 (Ω, u) 一个 | 是 |
| z_hat | [B, r] | float32 | B 输出，缺失共享坐标 | 是 |
| p_hat | [B, 256] | float32 | 解码，填入风险头缺失位 | 是 |
| head_in | [B, 768] | float32 | 风险头输入 | 是 |
| risk | [B] | float32 | 冻结风险头输出，越大预后越差 | 是 |
| e_pool | [N_tr, r] | float32 | B6：本折 train 在 (Ω, u) 下的无泄漏残差池 | 否 |
| sim_mat | [B, N_tr] | float32 | B6：查询与 train 锚点的逐模态平均余弦（自查询位 −inf） | 否 |
| attn_w | [B, K] | float32 | B6：Top-K 邻居 softmax 权重 a_ij | 否 |
| alpha_gate | [B, 1] | float32 | B6：患者级密度门控 α_i ∈ [0, α_max] | 否 |

## 3. 七种场景路由

| 场景 | 可见 Ω | 恢复目标 u | B 的映射个数 | 风险分来源 |
| --- | --- | --- | --- | --- |
| full | R, W, T | — | 0 | I07 原前向（逐患者恒等，D0） |
| rna | R | W, T | 2（R: 32×32） | p^Ω_R + p̂_W + p̂_T |
| wsi | W | R, T | 2 | 同上 |
| text | T | R, W | 2 | 同上 |
| rna+wsi | R, W | T | 1（R: 32×64） | p^Ω_R + p^Ω_W + p̂_T |
| rna+text | R, T | W | 1 | 同上 |
| wsi+text | W, T | R | 1 | 同上 |

参数量（r = 32）：A = 3 × 256 × 32 = 24,576；B = 6 × (32·32 + 32) + 3 × (32·64 + 32) = 12,576；合计 37,152（`contract.n_params` 有单测）。

## 4. 训练目标与梯度路径

| 项 | 公式 | 作用对象 | 梯度流向 |
| --- | --- | --- | --- |
| L_Cox^missing | 六种模式 Cox 部分似然等权平均 | risk | U（经 z_vis、p̂）、R、b |
| L_anchor（λ_a） | E‖x^F − U_mU_mᵀx^F‖²/256，三模态平均 | U | U |
| L_modal（λ_m，C1-a） | E_{i,m<n}[1 − cos(z^F_m, z^F_n)]，三对 | z_full | U |
| L_cons（λ_c，C1-b） | E_{i,Ω,u}(1/r)‖ẑ^Ω_u − sg(U_uᵀx^F_u)‖² | z_hat | U（经输入侧）、R、b；目标侧停梯度 |

| 对象 | 是否更新 |
| --- | --- |
| I07 全部参数、buffer、风险头 | 否（eval，`contract.check_frozen`） |
| A 的 U_m | 是 |
| B 的 R_{Ω→u}、b_{Ω,u} | 是 |
| μ^F、μ^Ω、患者列表、mask | 否（只来自本折 train） |
| C | 无参数 |

训练策略见 `config.yaml: train`：full-batch，AdamW，lr 1e-3，≤ 200 epoch，候选 r ∈ {16, 32} × λ_m ∈ {0.05, 0.1}，按本折 val 六模式平均 Cox 损失选模，seed 2026；全程不读 test。

## 5. 静默错误清单 → 守卫

| 可能的静默错误 | 后果 | 守卫 |
| --- | --- | --- |
| 拼接顺序与风险头权重切片不一致 | 风险分错位但仍是有限数 | `assemble_head_in` 固定 MODALITIES 顺序；单测与 I07 fill 路径逐值比对 |
| 可见位误用 p^F（完整前向）而非 p^Ω | test 时没有 p^F，train/test 口径不一致 | 同上单测（可见位取 present=Ω 的 pooled）；`position.visible_route` 钉死 |
| I07 未 eval、dropout 开着 | p^Ω 随机，缓存不可复现 | `check_frozen` |
| I07 参数被优化器更新 | Full 不再恒等 | `check_frozen` + D0 逐患者恒等 |
| 均值用到 val/test | 泄漏 | `features.mean_source = train` 钉死；实现时均值函数只收 train 部分 |
| 可见输入减 μ^F 而非 μ^Ω | 输入分布偏移被当成信号 | `features.input_mean = pattern` 钉死；`mu_pattern` 单列 |
| 缺失模式键写反（`text+rna`） | 查不到映射或映射错配 | `contract.visible` 只认 MODALITIES 顺序 |
| L_cons 目标未停梯度，或误停了整条 U | 目标随 ẑ 一起塌缩 / U 收不到恢复信号 | `stop_grad_target` 钉死；实现须单测 U 有梯度（故事线 Step 2） |
| 余弦遇到零向量 | NaN 传播 | `cos_eps` + 零向量断言 |
| 默认 r / λ_m 不在候选网格 | 报告的配置与选模不一致 | `check_config` 断言默认值 ∈ 候选 |
| YAML 整数冒充浮点 | 类型漂移 | 逐键 `type(v) is t` |

## 6. Stage 2a / 2b 与 B 变体（handoff v1 §3.3–3.4、§6.1）

| 阶段 | 内容 | 代码 |
| --- | --- | --- |
| Step 1 | 冻结 I07 前向 7 视角 → pooled 缓存（train / val），D0 守卫 + sha256 manifest | `cache.py` |
| Stage 2a | full-batch AdamW 训练 A1 + B1（+ C1），按 val 六模式 Cox 选 epoch 与配置 | `train_eval.train_base / stage2a_grid` |
| Stage 2b | 固定 Stage 2a 的 U_m、R、b，零重训挂载 B3 / B5 / B6，K × τ × α_max 网格按 val 选 | `train_eval.Plugin`、`operators.py` |

- B6-LOO：ẑ = ẑ^{B1} + α_i Σ_{j∈N_K(i)} a_ij e_j；残差池两种口径 `in_fold_masked`（B1 的 train 误差，检索排除自身）与
  `exact_loo_hat`（固定 U 上闭式 Ridge 的 PRESS 精确留一残差）；相似度默认 `per_modality_mean_cos`；
  门控 α_i = α_max σ(γ(s_{i,(1)} − δ))，δ / IQR 来自 train 留一最近邻相似度，零可学习参数。α_max = 0 时逐值退化为 B1（单测钉死）。
- 自查询：val 患者本不在残差池里，自掩码只影响 train 侧统计；守卫 `contract.check_b6_no_self_leak` 在每次检索后按 patient_id 核对。
- M5（用户裁定 2026-11-08）= 去门控（α_i ≡ α_max）+ δ/IQR 统计不做自掩码。
- 每个需要选参的方法另报 `@default` 行（固定默认超参，不在 val 上选择；Stage 2a 仍按 val 选 epoch）。
- 可解释性（`interpretability.py`）在 M2 默认基座 + B6-LOO 默认超参上计算。

| 编号 | 方法 | S1 | S2 | S5 |
| --- | --- | --- | --- | --- |
| M0-a / M0-b | 零填充 / 训练均值 | — | 常数 | — |
| M1-a / M1-b | B0 256 维 Ridge / C0 风险残差 Ridge | — | 闭式 Ridge | — |
| M2 | A1 + B1 + C1（共享基座） | A1 | B1 | C1 |
| M3 | A1 + B3 + C1 | M2 的 U | B3 | M2 |
| M4-a / M4-b | A1 + B5-MapPrecision / DirectCoord + C1 | M2 的 U | B5 | M2 |
| M5 | A1 + B6-Naive + C1 | M2 的 U | B6 无门控 | M2 |
| M6-a / M6-b | A1 + B6-LOO（in_fold_masked / exact_loo_hat）+ C1 | M2 的 U | B6 | M2 |
| M7 | 256 维 B6-LOO（w/o A1） | — | B0 + 256 维 LOO 残差 | — |
| M8 | A1 + B6-LOO（w/o C1） | M10-a 的 U | B6 | 无 C1 |
| M9 | PCA-32（A5）+ B6-LOO | 冻结 PCA | B1 + B6 | L_cons |
| M10-a/b/c | A1 + B1 的 C1 细粒度消融 | A1 | B1 | λ_m / λ_c 组合 |

新增静默错误守卫：

| 可能的静默错误 | 守卫 |
| --- | --- |
| train 检索命中自身，残差泄漏 | `mask_self` 按 id 置 −inf + `check_b6_no_self_leak`；反事实扰动单测（改 e_i 对自身输出影响 == 0.0） |
| α_max = 0 未精确退化 | 单测：z_hat / p_hat / risk 与 B1 差 == 0.0 |
| U 训练后失去正交 | cayley 映射（householder + weight decay 会失效，单测覆盖 wd > 0）；训练后断言 < orth_tol |
| 缓存混入 test | `TrainValReader` 在完整性核对后剔除 test 行、拒读 test WSI；`cache.export_fold` 只收 train/val，`load_fold_cache` 拒绝 test 键 |
| ckpt / run.json 被替换 | 两者哈希都须等于 `i07_registry.py`（受源码身份门保护） |
| 用未验身份的缓存出报告 | `run` 必填 `--expected-commit` 与 `--cache-manifest-sha256`，`verify_cache_manifest` 完整核对；`report` 拒绝未验证 / 冒烟 / 非全集运行 |
| 缓存与 I07 不一致 | 导出时 D0 三项 < 1e-6；`train_eval` 重算零填充风险与缓存差 < 1e-5 |
| 结果文件被替换 | `run_meta.json` 记录每个输出的 sha256，`report` 逐个核对 |
