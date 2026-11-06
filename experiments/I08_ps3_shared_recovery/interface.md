# I08 接口定义：A1 + B1 + C1 接入 PS3-style 骨架

> 故事线：主目录 `03_index-故事线 A-1｜患者级动态恢复_v1.md`（A1-B1-C1）。超参数与张量登记：`config.yaml`；强制核对：`contract.py`。
> 状态（2026-11-06）：接口稿，未实现训练；上机前须走节点一审查 + 用户点头。

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
