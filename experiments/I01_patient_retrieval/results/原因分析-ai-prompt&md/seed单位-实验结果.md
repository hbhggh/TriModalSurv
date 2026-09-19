# Seed 单位实验结果

协议：`patient-fixed-padmask-v2`；指标：B 口径 C-index，越大越好。

## 阅读与标红规则

- 每行把患者检索（retrieval）、均值填补（m1）、不补偿（m0real）放在同一组比较；组内最高的数值及实验名称标红加 ★，并列最高全部标红。表外红色结论句表示对应汇总范围的最高结果，不表示该方法在每组都胜出。
- 排名、标红和 Δ 均使用未四舍五入的原始值；展示保留六位小数，显示相同不一定是精确并列。Δ 先用原值相减再舍入，可能与展示值直接相减相差 0.000001。HTML 样式被阅读器屏蔽时，可用 ★ 识别最佳。
- `none`＝无额外人工遮挡，保留天然缺失，天然缺失仍按三臂规则处理；不是完整数据，也不是第四种人工缺失。本批次 BLCA/none 各 seed 的138/138位患者均为完整输入，无缺失可补，构成全部5组三臂并列；按用户要求仍纳入总体均值。
- `rna_100`＝人工遮挡 RNA；`text_100`＝人工遮挡文本；`both_100`＝同时人工遮挡 RNA 和文本。
- 按本次确认，四种场景全部等权参与汇总，不按患者数量加权，不剔除任何 seed。两列 Δ 分别相减，不计算“检索−均值−不补偿”。

## 总体三臂比较（含 none）

五癌 × 五 seed × 四场景＝100 组，每臂100个 C-index，共300个读数。

| 范围 | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- |
| 全部100组等权均值 | 0.628964 | <span style="color:#c62828"><strong>0.631825 ★</strong></span> | 0.630751 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.002861 | -0.001788 |

组内独胜：患者检索 17 组、均值填补 39 组、不补偿 39 组；并列最高 5 组（不重复计入独胜）。

结论：<span style="color:#c62828"><strong>总体均值填补最好，C-index = 0.631825 ★</strong></span>；检索总体低于两种基线。红色表示描述性最高，不表示统计显著。

## 哪个 seed 的患者检索成绩最好？

<span style="color:#c62828"><strong>按检索绝对 C-index 排名：seed 321 最高，四场景×五癌等权均值 0.632424。 ★</strong></span>

相对均值填补增益最大的 seed 是 213；相对不补偿增益最大的 seed 是 213。这是增益排名，不是检索绝对分排名。

每个 seed 汇总20组。表按患者检索均值降序；每行红色仍只表示该 seed 内三臂最佳。

| 检索排名 | seed | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 321 | 0.632424 | 0.633229 | <span style="color:#c62828"><strong>0.634407 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.000806 | -0.001983 |
| 2 | 231 | 0.631430 | <span style="color:#c62828"><strong>0.639490 ★</strong></span> | 0.634074 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.008060 | -0.002644 |
| 3 | 123 | 0.630686 | <span style="color:#c62828"><strong>0.633197 ★</strong></span> | 0.632342 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.002511 | -0.001656 |
| 4 | 132 | 0.629121 | 0.636741 | <span style="color:#c62828"><strong>0.639414 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.007620 | -0.010293 |
| 5 | 213 | <span style="color:#c62828"><strong>0.621158 ★</strong></span> | 0.616466 | 0.613520 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.004692 | +0.007638 |

## 按 seed 展开的全部实验数据

### Seed 123

5癌 × 4场景＝20组；每组三臂使用同一 checkpoint。

| 癌种 | 场景 | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA | none | 0.690246 | 0.691495 | <span style="color:#c62828"><strong>0.695015 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.001249 | -0.004769 |
| BRCA | rna_100 | 0.686613 | <span style="color:#c62828"><strong>0.688884 ★</strong></span> | 0.682752 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.002271 | +0.003861 |
| BRCA | text_100 | 0.619394 | 0.587260 | <span style="color:#c62828"><strong>0.650959 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.032134 | -0.031566 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.611559 ★</strong></span> | 0.573124 | 0.544907 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.038435 | +0.066652 |
| LUAD | none | 0.572833 | <span style="color:#c62828"><strong>0.574061 ★</strong></span> | 0.569323 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.001229 | +0.003510 |
| LUAD | rna_100 | 0.572657 | <span style="color:#c62828"><strong>0.573008 ★</strong></span> | 0.568270 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.000351 | +0.004388 |
| LUAD | text_100 | 0.583012 | 0.595823 | <span style="color:#c62828"><strong>0.596174 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.012812 | -0.013163 |
| LUAD | both_100 | 0.581783 | 0.589856 | <span style="color:#c62828"><strong>0.591787 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.008073 | -0.010004 |
| UCEC | none | 0.648787 | <span style="color:#c62828"><strong>0.656354 ★</strong></span> | 0.651458 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.007567 | -0.002671 |
| UCEC | rna_100 | 0.645448 | <span style="color:#c62828"><strong>0.650790 ★</strong></span> | 0.648119 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.005342 | -0.002671 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.582462 ★</strong></span> | 0.556866 | 0.565769 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.025595 | +0.016693 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.586468 ★</strong></span> | 0.548186 | 0.563766 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.038282 | +0.022702 |
| BLCA | none | <span style="color:#c62828"><strong>0.607391 ★</strong></span> | <span style="color:#c62828"><strong>0.607391 ★</strong></span> | <span style="color:#c62828"><strong>0.607391 ★</strong></span> | <span style="color:#c62828"><strong>患者检索、均值填补、不补偿（并列） ★</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.607391 | 0.608779 | <span style="color:#c62828"><strong>0.611728 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.001388 | -0.004337 |
| BLCA | text_100 | 0.569570 | 0.581020 | <span style="color:#c62828"><strong>0.581714 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.011450 | -0.012144 |
| BLCA | both_100 | 0.570611 | <span style="color:#c62828"><strong>0.584490 ★</strong></span> | 0.581888 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.013879 | -0.011277 |
| LGG | none | 0.807108 | <span style="color:#c62828"><strong>0.810904 ★</strong></span> | 0.808144 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.003796 | -0.001035 |
| LGG | rna_100 | 0.795376 | <span style="color:#c62828"><strong>0.804003 ★</strong></span> | 0.789510 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.008627 | +0.005866 |
| LGG | text_100 | 0.648378 | 0.704624 | <span style="color:#c62828"><strong>0.731194 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.056246 | -0.082816 |
| LGG | both_100 | 0.626639 | <span style="color:#c62828"><strong>0.677019 ★</strong></span> | 0.606970 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.050380 | +0.019669 |

### Seed 132

5癌 × 4场景＝20组；每组三臂使用同一 checkpoint。

| 癌种 | 场景 | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA | none | 0.684228 | <span style="color:#c62828"><strong>0.685818 ★</strong></span> | 0.685591 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.001590 | -0.001363 |
| BRCA | rna_100 | 0.679800 | <span style="color:#c62828"><strong>0.682412 ★</strong></span> | 0.675485 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.002612 | +0.004315 |
| BRCA | text_100 | 0.614511 | 0.630635 | <span style="color:#c62828"><strong>0.661860 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.016124 | -0.047349 |
| BRCA | both_100 | 0.608493 | 0.627115 | <span style="color:#c62828"><strong>0.627228 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.018622 | -0.018735 |
| LUAD | none | 0.579502 | <span style="color:#c62828"><strong>0.580379 ★</strong></span> | 0.577396 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.000878 | +0.002106 |
| LUAD | rna_100 | <span style="color:#c62828"><strong>0.578449 ★</strong></span> | 0.577396 | 0.568094 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.001053 | +0.010355 |
| LUAD | text_100 | 0.572482 | 0.589856 | <span style="color:#c62828"><strong>0.594770 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.017375 | -0.022289 |
| LUAD | both_100 | 0.571955 | 0.586346 | <span style="color:#c62828"><strong>0.590734 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.014391 | -0.018779 |
| UCEC | none | 0.677276 | <span style="color:#c62828"><strong>0.681282 ★</strong></span> | 0.674605 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.004006 | +0.002671 |
| UCEC | rna_100 | 0.676163 | <span style="color:#c62828"><strong>0.677943 ★</strong></span> | 0.673047 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.001781 | +0.003116 |
| UCEC | text_100 | 0.617405 | 0.625640 | <span style="color:#c62828"><strong>0.631427 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.008235 | -0.014022 |
| UCEC | both_100 | 0.616292 | <span style="color:#c62828"><strong>0.619631 ★</strong></span> | 0.617405 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.003339 | -0.001113 |
| BLCA | none | <span style="color:#c62828"><strong>0.607564 ★</strong></span> | <span style="color:#c62828"><strong>0.607564 ★</strong></span> | <span style="color:#c62828"><strong>0.607564 ★</strong></span> | <span style="color:#c62828"><strong>患者检索、均值填补、不补偿（并列） ★</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.608432 | 0.607564 | <span style="color:#c62828"><strong>0.615024 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.000867 | -0.006593 |
| BLCA | text_100 | 0.555170 | <span style="color:#c62828"><strong>0.586919 ★</strong></span> | 0.584143 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.031749 | -0.028973 |
| BLCA | both_100 | 0.559334 | 0.585704 | <span style="color:#c62828"><strong>0.595767 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.026371 | -0.036433 |
| LGG | none | 0.782264 | <span style="color:#c62828"><strong>0.786404 ★</strong></span> | 0.784334 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.004141 | -0.002070 |
| LGG | rna_100 | 0.772947 | <span style="color:#c62828"><strong>0.779848 ★</strong></span> | 0.759834 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.006901 | +0.013112 |
| LGG | text_100 | 0.620083 | 0.622843 | <span style="color:#c62828"><strong>0.679779 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.002761 | -0.059696 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.600069 ★</strong></span> | 0.593513 | 0.584196 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.006556 | +0.015873 |

### Seed 213

5癌 × 4场景＝20组；每组三臂使用同一 checkpoint。

| 癌种 | 场景 | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA | none | 0.692971 | 0.689452 | <span style="color:#c62828"><strong>0.696037 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.003520 | -0.003066 |
| BRCA | rna_100 | 0.691041 | 0.687181 | <span style="color:#c62828"><strong>0.692404 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.003861 | -0.001363 |
| BRCA | text_100 | 0.652549 | 0.633814 | <span style="color:#c62828"><strong>0.656977 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.018735 | -0.004428 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.649824 ★</strong></span> | 0.625866 | 0.614738 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.023958 | +0.035086 |
| LUAD | none | <span style="color:#c62828"><strong>0.580555 ★</strong></span> | 0.579853 | 0.578800 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.000702 | +0.001755 |
| LUAD | rna_100 | 0.583187 | 0.580906 | <span style="color:#c62828"><strong>0.587399 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.002282 | -0.004212 |
| LUAD | text_100 | 0.572482 | 0.592138 | <span style="color:#c62828"><strong>0.592664 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.019656 | -0.020183 |
| LUAD | both_100 | 0.575114 | <span style="color:#c62828"><strong>0.589154 ★</strong></span> | 0.578624 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.014040 | -0.003510 |
| UCEC | none | 0.650568 | <span style="color:#c62828"><strong>0.656354 ★</strong></span> | 0.651903 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.005787 | -0.001335 |
| UCEC | rna_100 | 0.651903 | <span style="color:#c62828"><strong>0.655241 ★</strong></span> | 0.648119 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.003339 | +0.003784 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.602270 ★</strong></span> | 0.564656 | 0.574227 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.037614 | +0.028044 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.597596 ★</strong></span> | 0.552637 | 0.549744 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.044959 | +0.047852 |
| BLCA | none | <span style="color:#c62828"><strong>0.490978 ★</strong></span> | <span style="color:#c62828"><strong>0.490978 ★</strong></span> | <span style="color:#c62828"><strong>0.490978 ★</strong></span> | <span style="color:#c62828"><strong>患者检索、均值填补、不补偿（并列） ★</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.492713 | 0.486468 | <span style="color:#c62828"><strong>0.493060 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.006246 | -0.000347 |
| BLCA | text_100 | 0.490978 | 0.519951 | <span style="color:#c62828"><strong>0.525850 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.028973 | -0.034872 |
| BLCA | both_100 | 0.503296 | <span style="color:#c62828"><strong>0.513706 ★</strong></span> | 0.503470 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.010409 | -0.000173 |
| LGG | none | 0.806073 | <span style="color:#c62828"><strong>0.808834 ★</strong></span> | 0.808144 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.002761 | -0.002070 |
| LGG | rna_100 | 0.797101 | <span style="color:#c62828"><strong>0.802968 ★</strong></span> | 0.781573 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.005866 | +0.015528 |
| LGG | text_100 | 0.679434 | 0.670807 | <span style="color:#c62828"><strong>0.709800 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.008627 | -0.030366 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.662526 ★</strong></span> | 0.628364 | 0.535887 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.034161 | +0.126639 |

### Seed 231

5癌 × 4场景＝20组；每组三臂使用同一 checkpoint。

| 癌种 | 场景 | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA | none | 0.684910 | 0.680141 | <span style="color:#c62828"><strong>0.685932 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.004769 | -0.001022 |
| BRCA | rna_100 | <span style="color:#c62828"><strong>0.680027 ★</strong></span> | 0.678097 | 0.674918 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.001930 | +0.005110 |
| BRCA | text_100 | 0.634382 | 0.642216 | <span style="color:#c62828"><strong>0.671625 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.007835 | -0.037243 |
| BRCA | both_100 | 0.629953 | <span style="color:#c62828"><strong>0.642444 ★</strong></span> | 0.618372 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.012490 | +0.011582 |
| LUAD | none | 0.585820 | <span style="color:#c62828"><strong>0.586873 ★</strong></span> | 0.585118 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.001053 | +0.000702 |
| LUAD | rna_100 | 0.578449 | 0.578624 | <span style="color:#c62828"><strong>0.579151 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.000176 | -0.000702 |
| LUAD | text_100 | 0.579853 | 0.601615 | <span style="color:#c62828"><strong>0.602492 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.021762 | -0.022640 |
| LUAD | both_100 | 0.571955 | <span style="color:#c62828"><strong>0.588452 ★</strong></span> | 0.579326 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.016497 | -0.007371 |
| UCEC | none | 0.638326 | <span style="color:#c62828"><strong>0.645003 ★</strong></span> | 0.641220 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.006677 | -0.002893 |
| UCEC | rna_100 | 0.641665 | <span style="color:#c62828"><strong>0.645003 ★</strong></span> | 0.623859 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.003339 | +0.017805 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.597151 ★</strong></span> | 0.585800 | 0.596706 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.011351 | +0.000445 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.594703 ★</strong></span> | 0.583797 | 0.580904 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.010906 | +0.013799 |
| BLCA | none | <span style="color:#c62828"><strong>0.614677 ★</strong></span> | <span style="color:#c62828"><strong>0.614677 ★</strong></span> | <span style="color:#c62828"><strong>0.614677 ★</strong></span> | <span style="color:#c62828"><strong>患者检索、均值填补、不补偿（并列） ★</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.617106 | 0.615198 | <span style="color:#c62828"><strong>0.618841 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.001908 | -0.001735 |
| BLCA | text_100 | 0.561242 | 0.582582 | <span style="color:#c62828"><strong>0.585704 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.021339 | -0.024462 |
| BLCA | both_100 | 0.560895 | <span style="color:#c62828"><strong>0.586919 ★</strong></span> | 0.582755 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.026024 | -0.021860 |
| LGG | none | 0.791925 | <span style="color:#c62828"><strong>0.795031 ★</strong></span> | 0.792616 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.003106 | -0.000690 |
| LGG | rna_100 | 0.768461 | <span style="color:#c62828"><strong>0.781228 ★</strong></span> | 0.738440 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.012767 | +0.030021 |
| LGG | text_100 | 0.663561 | 0.689096 | <span style="color:#c62828"><strong>0.719462 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.025535 | -0.055901 |
| LGG | both_100 | 0.633540 | <span style="color:#c62828"><strong>0.667012 ★</strong></span> | 0.589372 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.033471 | +0.044168 |

### Seed 321

5癌 × 4场景＝20组；每组三臂使用同一 checkpoint。

| 癌种 | 场景 | 患者检索 | 均值填补 | 不补偿 | 本组三臂最佳 | 检索−均值 | 检索−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA | none | 0.687294 | 0.683434 | <span style="color:#c62828"><strong>0.694221 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.003861 | -0.006926 |
| BRCA | rna_100 | 0.691950 | 0.687181 | <span style="color:#c62828"><strong>0.693653 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.004769 | -0.001703 |
| BRCA | text_100 | 0.621892 | 0.601680 | <span style="color:#c62828"><strong>0.633587 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.020211 | -0.011695 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.621551 ★</strong></span> | 0.605200 | 0.574884 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.016351 | +0.046667 |
| LUAD | none | 0.597578 | 0.597929 | <span style="color:#c62828"><strong>0.599684 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.000351 | -0.002106 |
| LUAD | rna_100 | 0.592313 | 0.591260 | <span style="color:#c62828"><strong>0.600386 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.001053 | -0.008073 |
| LUAD | text_100 | 0.572306 | 0.596350 | <span style="color:#c62828"><strong>0.597052 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.024044 | -0.024746 |
| LUAD | both_100 | 0.566866 | <span style="color:#c62828"><strong>0.590207 ★</strong></span> | 0.586873 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.023342 | -0.020007 |
| UCEC | none | 0.639439 | <span style="color:#c62828"><strong>0.645448 ★</strong></span> | 0.638326 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.006009 | +0.001113 |
| UCEC | rna_100 | 0.637881 | <span style="color:#c62828"><strong>0.648342 ★</strong></span> | 0.643000 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.010461 | -0.005119 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.588694 ★</strong></span> | 0.555753 | 0.578233 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.032940 | +0.010461 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.588694 ★</strong></span> | 0.571111 | 0.569775 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.017583 | +0.018918 |
| BLCA | none | <span style="color:#c62828"><strong>0.629251 ★</strong></span> | <span style="color:#c62828"><strong>0.629251 ★</strong></span> | <span style="color:#c62828"><strong>0.629251 ★</strong></span> | <span style="color:#c62828"><strong>患者检索、均值填补、不补偿（并列） ★</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.624046 | 0.627516 | <span style="color:#c62828"><strong>0.629077 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.003470 | -0.005031 |
| BLCA | text_100 | 0.573387 | <span style="color:#c62828"><strong>0.604094 ★</strong></span> | 0.602533 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.030708 | -0.029146 |
| BLCA | both_100 | 0.571305 | 0.603053 | <span style="color:#c62828"><strong>0.606350 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | -0.031749 | -0.035045 |
| LGG | none | 0.792616 | <span style="color:#c62828"><strong>0.796411 ★</strong></span> | 0.790890 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.003796 | +0.001725 |
| LGG | rna_100 | 0.777088 | <span style="color:#c62828"><strong>0.786749 ★</strong></span> | 0.766736 | <span style="color:#c62828"><strong>均值填补 ★</strong></span> | -0.009662 | +0.010352 |
| LGG | text_100 | 0.646308 | 0.633195 | <span style="color:#c62828"><strong>0.689096 ★</strong></span> | <span style="color:#c62828"><strong>不补偿 ★</strong></span> | +0.013112 | -0.042788 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.628019 ★</strong></span> | 0.610421 | 0.564527 | <span style="color:#c62828"><strong>患者检索 ★</strong></span> | +0.017598 | +0.063492 |

## 数据来源、核验与边界

- [原始75份正式结果 JSON](</Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/archive/legacy-tako-formal-20260915/raw/tako-formal/evidence/formal>)：每份读取 `grids.<场景>.cindex_B`。
- [原始汇总](</Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/archive/legacy-tako-formal-20260915/raw/tako-formal/evidence/summary/per_cell.csv>)：60个癌种×场景×臂的五 seed 均值均已复算对齐。
- [历史归档清单](</Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/archive/legacy-tako-formal-20260915/historical_artifact_manifest.json>)：结果JSON和状态/汇总文件均核对清单 SHA-256，并与清单指向的原档案一致；600个 audit/prediction 引用文件核对记录哈希。
- [复算脚本](</Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/archive/_grouped_report_audit/build_reports.py>)：`/usr/bin/python3 "/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results/archive/_grouped_report_audit/build_reports.py"` 输出两份报告文本及校验摘要，不修改文件。
- 本次重新分组与聚合已有 C-index，未重新跑模型、训练或从患者预测重新计算 C-index；未改变原档案。
- 五 seed 共用既有患者划分，不是五个独立患者队列。最高 seed 是测试结果的描述性排序，不可只保留最佳 seed 替代五 seed 结论。
- 癌种之间患者构成和事件分布不同；跨癌绝对 C-index 最高不等于检索补偿增益最大。增益需看同癌同 seed 同场景的配对 Δ。
- 本报告包含 none 的总体均值不能与历史仅含三种人工缺失的总体均值直接混用。
