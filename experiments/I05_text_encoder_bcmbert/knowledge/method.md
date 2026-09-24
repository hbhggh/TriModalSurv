# I05 机制说明

## 改了什么

只改 Text 的离线特征提取器。现有系统的 Text 特征是作者公开嵌入（编码器身份未核），每人 `[200, 768]`；本实验用冻结的 BioClinical ModernBERT 嵌入版重新提取同形特征：

1. 报告原文用该模型的分词器截断或右侧补齐到 200 token，保留 [CLS]/[SEP]。
2. 冻结前向取 `last_hidden_state`，FP32。
3. 按 `attention_mask` 对有效 token 求均值（pad 位不参与，即该模型自带的 mean-token 池化），把这个均值广播写入全部 200 行，写成 `{pid}.pkl`（方案 C，用户裁决 2026-09-24）。

NPJ-C 内部仍对 200 行做 `mean(dim=1)` 再进 `Linear(768, 256)`。200 行相同，所以这个均值恰好等于前 200 token 的 masked mean，短报告不会按有效长度缩小。改用方案 C 的原因：Phase 0 发现旧特征全部 200 行非零、互不相同（连 1 个词的报告也是），旧 pad 位不为零；而原方案 A 把 pad 行置零，会让 18% 不足 150 词的短报告的槽内均值接近零向量。

## 没改什么

- WSI（UNI2-h，128×1536）与 RNA（自制 BulkRNABert，2048×256）缓存逐内容复用历史冻结件。
- NPJ-C 结构与训练配方：lr 1e-4、epochs 50、batch 32、hidden 256、Adam wd=1、bf16、best-valid、bin_mode author。
- 原型检索方法：历史选参锁里的 combo（rules 1–5，λ=1、α=1、w=0.5，UCEC 例外开）原样使用，不重新选参；LUAD 按 S0-force 路由。
- 检索 key 只用 WSI，所以 donor 身份不变；变的是 donor 的 Text 值与同癌 train 的 Text 均值，它们随新特征在同一空间重建。

## 为什么结论只到"组合"

只换了 Text，结论支持"换 Text 后的三模态 encoder 组合优于现有组合"，不支持"每个模态的 encoder 都更好"。`none` 下完整患者不走检索，Proto.† 在这些患者上等于基础模型；新臂的 25 个 ckpt 在现行代码上重训，所以 Δ 同时包含 encoder 效应与重训方差。
