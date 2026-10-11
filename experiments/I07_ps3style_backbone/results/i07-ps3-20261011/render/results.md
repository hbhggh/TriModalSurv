## 拟合判定

| 癌种 | 臂 | 各折判定 | 各折所选 epoch | 可靠 |
|---|---|---|---|---|
| BLCA | tri | overfit / overfit / overfit / overfit / overfit | 4 / 1 / 9 / 1 / 1 | 是 |
| BLCA | wsi | overfit / overfit / overfit / overfit / overfit | 4 / 1 / 1 / 1 / 1 | 是 |
| BLCA | rna | failed / overfit / overfit / overfit / overfit | 18 / 3 / 11 / 7 / 2 | 是 |
| BLCA | text | overfit / normal / overfit / normal / overfit | 3 / 16 / 18 / 9 / 7 | 是 |
| BRCA | tri | overfit / overfit / normal / normal / normal | 2 / 1 / 4 / 3 / 2 | 是 |
| BRCA | wsi | overfit / overfit / overfit / overfit / normal | 2 / 1 / 4 / 2 / 2 | 是 |
| BRCA | rna | overfit / normal / overfit / overfit / overfit | 5 / 1 / 6 / 1 / 1 | 是 |
| BRCA | text | overfit / overfit / overfit / overfit / normal | 2 / 3 / 2 / 2 / 1 | 是 |
| LUAD | tri | overfit / normal / normal / overfit / overfit | 1 / 3 / 2 / 3 / 3 | 是 |
| LUAD | wsi | overfit / normal / normal / overfit / overfit | 1 / 1 / 2 / 3 / 2 | 是 |
| LUAD | rna | overfit / overfit / normal / normal / normal | 1 / 3 / 5 / 4 / 10 | 是 |
| LUAD | text | overfit / overfit / normal / normal / overfit | 4 / 6 / 7 / 12 / 2 | 是 |
| LGG | tri | overfit / overfit / overfit / overfit / overfit | 3 / 12 / 2 / 2 / 11 | 是 |
| LGG | wsi | overfit / overfit / normal / overfit / overfit | 2 / 1 / 2 / 1 / 3 | 是 |
| LGG | rna | overfit / normal / normal / overfit / overfit | 8 / 5 / 4 / 5 / 5 | 是 |
| LGG | text | overfit / overfit / normal / normal / normal | 7 / 6 / 2 / 4 / 6 | 是 |
| UCEC | tri | normal / overfit / overfit / overfit / overfit | 5 / 1 / 1 / 5 / 3 | 是 |
| UCEC | wsi | normal / overfit / normal / overfit / overfit | 1 / 1 / 1 / 2 / 2 | 是 |
| UCEC | rna | normal / normal / overfit / normal / overfit | 12 / 2 / 11 / 4 / 9 | 是 |
| UCEC | text | overfit / overfit / overfit / overfit / overfit | 9 / 1 / 13 / 2 / 1 | 是 |

## 结果（屏蔽列为零填充）

| 癌种 | 完整三模态 | 独立纯 WSI | 独立纯 RNA | 独立纯文本 | 骨架屏蔽纯 WSI | 骨架屏蔽纯 RNA | 骨架屏蔽纯文本 |
|---|---|---|---|---|---|---|---|
| BLCA | 0.596 ± 0.027 | 0.541 ± 0.048 | 0.607 ± 0.032 | 0.624 ± 0.041 | 0.573 ± 0.028 | 0.570 ± 0.051 | 0.571 ± 0.047 |
| BRCA | 0.651 ± 0.049 | 0.614 ± 0.042 | 0.573 ± 0.054 | 0.628 ± 0.080 | 0.613 ± 0.059 | 0.571 ± 0.057 | 0.657 ± 0.107 |
| LUAD | 0.645 ± 0.105 | 0.599 ± 0.090 | 0.628 ± 0.059 | 0.644 ± 0.053 | 0.608 ± 0.110 | 0.608 ± 0.045 | 0.623 ± 0.067 |
| LGG | 0.808 ± 0.026 | 0.748 ± 0.037 | 0.824 ± 0.023 | 0.710 ± 0.038 | 0.738 ± 0.028 | 0.812 ± 0.029 | 0.651 ± 0.061 |
| UCEC | 0.704 ± 0.074 | 0.672 ± 0.056 | 0.692 ± 0.071 | 0.694 ± 0.074 | 0.674 ± 0.066 | 0.628 ± 0.054 | 0.683 ± 0.121 |
| 五癌宏平均 | 0.681 | 0.635 | 0.665 | 0.660 | 0.641 | 0.638 | 0.637 |
| PRIME 参照（只引用） | 0.653 | 0.620 | 0.579 | 0.604 | 0.603 | 0.564 | 0.611 |

## 结果（屏蔽列为训练集均值填充）

| 癌种 | 完整三模态 | 独立纯 WSI | 独立纯 RNA | 独立纯文本 | 骨架屏蔽纯 WSI | 骨架屏蔽纯 RNA | 骨架屏蔽纯文本 |
|---|---|---|---|---|---|---|---|
| BLCA | 0.596 ± 0.027 | 0.541 ± 0.048 | 0.607 ± 0.032 | 0.624 ± 0.041 | 0.573 ± 0.028 | 0.570 ± 0.051 | 0.571 ± 0.047 |
| BRCA | 0.651 ± 0.049 | 0.614 ± 0.042 | 0.573 ± 0.054 | 0.628 ± 0.080 | 0.613 ± 0.059 | 0.571 ± 0.057 | 0.657 ± 0.107 |
| LUAD | 0.645 ± 0.105 | 0.599 ± 0.090 | 0.628 ± 0.059 | 0.644 ± 0.053 | 0.608 ± 0.110 | 0.608 ± 0.045 | 0.623 ± 0.067 |
| LGG | 0.808 ± 0.026 | 0.748 ± 0.037 | 0.824 ± 0.023 | 0.710 ± 0.038 | 0.738 ± 0.028 | 0.812 ± 0.029 | 0.651 ± 0.061 |
| UCEC | 0.704 ± 0.074 | 0.672 ± 0.056 | 0.692 ± 0.071 | 0.694 ± 0.074 | 0.674 ± 0.066 | 0.628 ± 0.054 | 0.683 ± 0.121 |
| 五癌宏平均 | 0.681 | 0.635 | 0.665 | 0.660 | 0.641 | 0.638 | 0.637 |
| PRIME 参照（只引用） | 0.653 | 0.620 | 0.579 | 0.604 | 0.603 | 0.564 | 0.611 |

## 换骨架判定

完整三模态五癌宏平均 = 0.6807；阈值 0.627（严格低于即换骨架）→ **保留骨架**
