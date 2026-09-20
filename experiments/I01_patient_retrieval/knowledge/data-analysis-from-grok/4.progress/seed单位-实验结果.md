# seed单位-实验结果

## 强制路由、泄漏与解释边界

- valid A=0.654042、B=0.645226、valid B−A=-0.008815；valid 反对仍**强制启用** `enabled=true`。
- 路由由已见 test 启发，因此本轮存在 **test 泄漏**；不是盲测、不是独立确认。
- LUAD 的 `rna_100` 与 `both_100` 是固定 **m1** 的精确副本，`text_100` 是固定 **m0real** 的精确副本；这些平局不能算作患者检索胜利。
- 若 LUAD 或五癌胜率改善，只能归因于“LUAD 按场景切换到固定 m1/m0real”；不得写成患者检索机制成立。
- **4/5仅为探索性反事实**，不是效果验收；上游 3.progress 的历史记录仅作对照。
- LUAD 对 m1 的四场景等权差仅为 +0.000035，应视为近似平局、不稳；不能据此作机制优越性声称。
- LUAD test 的 `none` 中“缺 RNA → m1”分支实际触发0次；本轮相对 3.progress 的变化只来自 `rna_100`／`both_100` 改走 m1，`text_100` 未变。
- 标题“LUAD-m1-force 组合”仅标识本轮协议；非 LUAD 的80格原样复用 2.progress 冻结组合。
协议：`patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-force-v1`；冻结 test 指纹：`a825b3cc4df41cf56afe228be531a4fc13f69c520bf35a2f2305101652387ec2`。

- 主表为五癌×五seed×四场景共100格等权平均；`none`保留天然缺失，不是完整数据。
- 人工缺失表仅为75格（排除`none`），不替代主表。
- 标红、排名与Δ均基于未四舍五入原值；展示六位，Δ先减后舍入。
- 本轮是受既有test启发的探索性评测；若LUAD改善也只能归因于固定路由换填，不能证明患者检索机制成立。

## 按 seed 展开

### Seed 123

| 癌种 | 场景 | LUAD-m1-force 组合 | 均值填补 | 不补偿 | 三臂最佳 | LUAD-m1-force−均值 | LUAD-m1-force−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLCA | none | <span style="color:#c62828"><strong>0.607391</strong></span> | <span style="color:#c62828"><strong>0.607391</strong></span> | <span style="color:#c62828"><strong>0.607391</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补、不补偿</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.607564 | 0.608779 | <span style="color:#c62828"><strong>0.611728</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.001214 | -0.004164 |
| BLCA | text_100 | <span style="color:#c62828"><strong>0.581714</strong></span> | 0.581020 | <span style="color:#c62828"><strong>0.581714</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.000694 | +0.000000 |
| BLCA | both_100 | 0.581714 | <span style="color:#c62828"><strong>0.584490</strong></span> | 0.581888 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002776 | -0.000173 |
| BRCA | none | <span style="color:#c62828"><strong>0.697059</strong></span> | 0.691495 | 0.695015 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.005564 | +0.002044 |
| BRCA | rna_100 | <span style="color:#c62828"><strong>0.691836</strong></span> | 0.688884 | 0.682752 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.002952 | +0.009084 |
| BRCA | text_100 | <span style="color:#c62828"><strong>0.650959</strong></span> | 0.587260 | <span style="color:#c62828"><strong>0.650959</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.063699 | +0.000000 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.636426</strong></span> | 0.573067 | 0.544907 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.063359 | +0.091518 |
| LGG | none | 0.808834 | <span style="color:#c62828"><strong>0.810904</strong></span> | 0.808144 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002070 | +0.000690 |
| LGG | rna_100 | 0.801242 | <span style="color:#c62828"><strong>0.804003</strong></span> | 0.789510 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002761 | +0.011732 |
| LGG | text_100 | <span style="color:#c62828"><strong>0.731194</strong></span> | 0.704624 | <span style="color:#c62828"><strong>0.731194</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.026570 | +0.000000 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.677709</strong></span> | 0.677019 | 0.606970 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.000690 | +0.070738 |
| LUAD | none | 0.571429 | <span style="color:#c62828"><strong>0.574061</strong></span> | 0.569323 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002633 | +0.002106 |
| LUAD | rna_100 | <span style="color:#c62828"><strong>0.573008</strong></span> | <span style="color:#c62828"><strong>0.573008</strong></span> | 0.568270 | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补</strong></span> | +0.000000 | +0.004739 |
| LUAD | text_100 | <span style="color:#c62828"><strong>0.596174</strong></span> | 0.595823 | <span style="color:#c62828"><strong>0.596174</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.000351 | +0.000000 |
| LUAD | both_100 | 0.589856 | 0.589856 | <span style="color:#c62828"><strong>0.591787</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000000 | -0.001931 |
| UCEC | none | 0.650122 | <span style="color:#c62828"><strong>0.656354</strong></span> | 0.651458 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.006232 | -0.001335 |
| UCEC | rna_100 | 0.646784 | <span style="color:#c62828"><strong>0.650790</strong></span> | 0.648119 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.004006 | -0.001335 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.614734</strong></span> | 0.556866 | 0.565769 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.057868 | +0.048965 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.614066</strong></span> | 0.548186 | 0.563766 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.065880 | +0.050300 |

### Seed 132

| 癌种 | 场景 | LUAD-m1-force 组合 | 均值填补 | 不补偿 | 三臂最佳 | LUAD-m1-force−均值 | LUAD-m1-force−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLCA | none | <span style="color:#c62828"><strong>0.607564</strong></span> | <span style="color:#c62828"><strong>0.607564</strong></span> | <span style="color:#c62828"><strong>0.607564</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补、不补偿</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.607391 | 0.607564 | <span style="color:#c62828"><strong>0.615024</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.000173 | -0.007634 |
| BLCA | text_100 | 0.584143 | <span style="color:#c62828"><strong>0.586919</strong></span> | 0.584143 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002776 | +0.000000 |
| BLCA | both_100 | 0.574254 | 0.585704 | <span style="color:#c62828"><strong>0.595767</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.011450 | -0.021513 |
| BRCA | none | 0.680368 | <span style="color:#c62828"><strong>0.685818</strong></span> | 0.685591 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.005450 | -0.005223 |
| BRCA | rna_100 | 0.676053 | <span style="color:#c62828"><strong>0.682412</strong></span> | 0.675485 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.006359 | +0.000568 |
| BRCA | text_100 | <span style="color:#c62828"><strong>0.661860</strong></span> | 0.630635 | <span style="color:#c62828"><strong>0.661860</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.031225 | +0.000000 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.636539</strong></span> | 0.627115 | 0.627228 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.009424 | +0.009311 |
| LGG | none | 0.783989 | <span style="color:#c62828"><strong>0.786404</strong></span> | 0.784334 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002415 | -0.000345 |
| LGG | rna_100 | 0.767771 | <span style="color:#c62828"><strong>0.779848</strong></span> | 0.759834 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.012077 | +0.007937 |
| LGG | text_100 | <span style="color:#c62828"><strong>0.679779</strong></span> | 0.622843 | <span style="color:#c62828"><strong>0.679779</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.056936 | +0.000000 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.635956</strong></span> | 0.593513 | 0.584196 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.042443 | +0.051760 |
| LUAD | none | 0.578624 | <span style="color:#c62828"><strong>0.580379</strong></span> | 0.577396 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001755 | +0.001229 |
| LUAD | rna_100 | <span style="color:#c62828"><strong>0.577396</strong></span> | <span style="color:#c62828"><strong>0.577396</strong></span> | 0.568094 | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补</strong></span> | +0.000000 | +0.009302 |
| LUAD | text_100 | <span style="color:#c62828"><strong>0.594770</strong></span> | 0.589856 | <span style="color:#c62828"><strong>0.594770</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.004914 | +0.000000 |
| LUAD | both_100 | 0.586346 | 0.586346 | <span style="color:#c62828"><strong>0.590734</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000000 | -0.004388 |
| UCEC | none | 0.677053 | <span style="color:#c62828"><strong>0.681282</strong></span> | 0.674605 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.004229 | +0.002448 |
| UCEC | rna_100 | 0.676163 | <span style="color:#c62828"><strong>0.677943</strong></span> | 0.673047 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001781 | +0.003116 |
| UCEC | text_100 | 0.622301 | 0.625640 | <span style="color:#c62828"><strong>0.631427</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.003339 | -0.009125 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.623637</strong></span> | 0.619631 | 0.617405 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.004006 | +0.006232 |

### Seed 213

| 癌种 | 场景 | LUAD-m1-force 组合 | 均值填补 | 不补偿 | 三臂最佳 | LUAD-m1-force−均值 | LUAD-m1-force−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLCA | none | <span style="color:#c62828"><strong>0.490978</strong></span> | <span style="color:#c62828"><strong>0.490978</strong></span> | <span style="color:#c62828"><strong>0.490978</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补、不补偿</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.485774 | 0.486468 | <span style="color:#c62828"><strong>0.493060</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.000694 | -0.007287 |
| BLCA | text_100 | <span style="color:#c62828"><strong>0.525850</strong></span> | 0.519951 | <span style="color:#c62828"><strong>0.525850</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.005899 | +0.000000 |
| BLCA | both_100 | 0.479702 | <span style="color:#c62828"><strong>0.513706</strong></span> | 0.503470 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.034004 | -0.023768 |
| BRCA | none | 0.692971 | 0.689452 | <span style="color:#c62828"><strong>0.696037</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.003520 | -0.003066 |
| BRCA | rna_100 | <span style="color:#c62828"><strong>0.692744</strong></span> | 0.687181 | 0.692404 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.005564 | +0.000341 |
| BRCA | text_100 | <span style="color:#c62828"><strong>0.656977</strong></span> | 0.633814 | <span style="color:#c62828"><strong>0.656977</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.023163 | +0.000000 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.661746</strong></span> | 0.625866 | 0.614738 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.035881 | +0.047008 |
| LGG | none | 0.807108 | <span style="color:#c62828"><strong>0.808834</strong></span> | 0.808144 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001725 | -0.001035 |
| LGG | rna_100 | <span style="color:#c62828"><strong>0.805383</strong></span> | 0.802968 | 0.781573 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.002415 | +0.023810 |
| LGG | text_100 | <span style="color:#c62828"><strong>0.709800</strong></span> | 0.670807 | <span style="color:#c62828"><strong>0.709800</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.038992 | +0.000000 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.691166</strong></span> | 0.628364 | 0.535887 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.062802 | +0.155280 |
| LUAD | none | 0.579326 | <span style="color:#c62828"><strong>0.579853</strong></span> | 0.578800 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.000527 | +0.000527 |
| LUAD | rna_100 | 0.580906 | 0.580906 | <span style="color:#c62828"><strong>0.587399</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000000 | -0.006494 |
| LUAD | text_100 | <span style="color:#c62828"><strong>0.592664</strong></span> | 0.592138 | <span style="color:#c62828"><strong>0.592664</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.000527 | +0.000000 |
| LUAD | both_100 | <span style="color:#c62828"><strong>0.589154</strong></span> | <span style="color:#c62828"><strong>0.589154</strong></span> | 0.578624 | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补</strong></span> | +0.000000 | +0.010530 |
| UCEC | none | 0.649232 | <span style="color:#c62828"><strong>0.656354</strong></span> | 0.651903 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.007122 | -0.002671 |
| UCEC | rna_100 | 0.650345 | <span style="color:#c62828"><strong>0.655241</strong></span> | 0.648119 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.004897 | +0.002226 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.616737</strong></span> | 0.564656 | 0.574227 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.052081 | +0.042511 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.611841</strong></span> | 0.552637 | 0.549744 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.059203 | +0.062097 |

### Seed 231

| 癌种 | 场景 | LUAD-m1-force 组合 | 均值填补 | 不补偿 | 三臂最佳 | LUAD-m1-force−均值 | LUAD-m1-force−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLCA | none | <span style="color:#c62828"><strong>0.614677</strong></span> | <span style="color:#c62828"><strong>0.614677</strong></span> | <span style="color:#c62828"><strong>0.614677</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补、不补偿</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.615892 | 0.615198 | <span style="color:#c62828"><strong>0.618841</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000694 | -0.002949 |
| BLCA | text_100 | <span style="color:#c62828"><strong>0.585704</strong></span> | 0.582582 | <span style="color:#c62828"><strong>0.585704</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.003123 | +0.000000 |
| BLCA | both_100 | 0.580500 | <span style="color:#c62828"><strong>0.586919</strong></span> | 0.582755 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.006419 | -0.002255 |
| BRCA | none | 0.681049 | 0.680141 | <span style="color:#c62828"><strong>0.685932</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000908 | -0.004882 |
| BRCA | rna_100 | 0.676394 | <span style="color:#c62828"><strong>0.678097</strong></span> | 0.674918 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001703 | +0.001476 |
| BRCA | text_100 | <span style="color:#c62828"><strong>0.671625</strong></span> | 0.642216 | <span style="color:#c62828"><strong>0.671625</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.029408 | +0.000000 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.643693</strong></span> | 0.642444 | 0.618372 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.001249 | +0.025321 |
| LGG | none | 0.793996 | <span style="color:#c62828"><strong>0.795031</strong></span> | 0.792616 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001035 | +0.001380 |
| LGG | rna_100 | 0.775707 | <span style="color:#c62828"><strong>0.781228</strong></span> | 0.738440 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.005521 | +0.037267 |
| LGG | text_100 | <span style="color:#c62828"><strong>0.719462</strong></span> | 0.689096 | <span style="color:#c62828"><strong>0.719462</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.030366 | +0.000000 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.675293</strong></span> | 0.667012 | 0.589372 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.008282 | +0.085921 |
| LUAD | none | 0.584591 | <span style="color:#c62828"><strong>0.586873</strong></span> | 0.585118 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.002282 | -0.000527 |
| LUAD | rna_100 | 0.578624 | 0.578624 | <span style="color:#c62828"><strong>0.579151</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000000 | -0.000527 |
| LUAD | text_100 | <span style="color:#c62828"><strong>0.602492</strong></span> | 0.601615 | <span style="color:#c62828"><strong>0.602492</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.000878 | +0.000000 |
| LUAD | both_100 | <span style="color:#c62828"><strong>0.588452</strong></span> | <span style="color:#c62828"><strong>0.588452</strong></span> | 0.579326 | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补</strong></span> | +0.000000 | +0.009126 |
| UCEC | none | 0.638994 | <span style="color:#c62828"><strong>0.645003</strong></span> | 0.641220 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.006009 | -0.002226 |
| UCEC | rna_100 | 0.643668 | <span style="color:#c62828"><strong>0.645003</strong></span> | 0.623859 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001335 | +0.019809 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.608947</strong></span> | 0.585800 | 0.596706 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.023147 | +0.012241 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.610505</strong></span> | 0.583797 | 0.580904 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.026708 | +0.029602 |

### Seed 321

| 癌种 | 场景 | LUAD-m1-force 组合 | 均值填补 | 不补偿 | 三臂最佳 | LUAD-m1-force−均值 | LUAD-m1-force−不补偿 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLCA | none | <span style="color:#c62828"><strong>0.629251</strong></span> | <span style="color:#c62828"><strong>0.629251</strong></span> | <span style="color:#c62828"><strong>0.629251</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补、不补偿</strong></span> | +0.000000 | +0.000000 |
| BLCA | rna_100 | 0.624219 | 0.627516 | <span style="color:#c62828"><strong>0.629077</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.003296 | -0.004858 |
| BLCA | text_100 | 0.602533 | <span style="color:#c62828"><strong>0.604094</strong></span> | 0.602533 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001561 | +0.000000 |
| BLCA | both_100 | 0.592817 | 0.603053 | <span style="color:#c62828"><strong>0.606350</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | -0.010236 | -0.013532 |
| BRCA | none | 0.689111 | 0.683434 | <span style="color:#c62828"><strong>0.694221</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.005677 | -0.005110 |
| BRCA | rna_100 | 0.691495 | 0.687181 | <span style="color:#c62828"><strong>0.693653</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.004315 | -0.002157 |
| BRCA | text_100 | <span style="color:#c62828"><strong>0.633587</strong></span> | 0.601680 | <span style="color:#c62828"><strong>0.633587</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.031906 | +0.000000 |
| BRCA | both_100 | <span style="color:#c62828"><strong>0.622914</strong></span> | 0.605200 | 0.574884 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.017713 | +0.048030 |
| LGG | none | 0.794686 | <span style="color:#c62828"><strong>0.796411</strong></span> | 0.790890 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.001725 | +0.003796 |
| LGG | rna_100 | 0.782954 | <span style="color:#c62828"><strong>0.786749</strong></span> | 0.766736 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.003796 | +0.016218 |
| LGG | text_100 | <span style="color:#c62828"><strong>0.689096</strong></span> | 0.633195 | <span style="color:#c62828"><strong>0.689096</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.055901 | +0.000000 |
| LGG | both_100 | <span style="color:#c62828"><strong>0.646308</strong></span> | 0.610421 | 0.564527 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.035887 | +0.081781 |
| LUAD | none | 0.598456 | 0.597929 | <span style="color:#c62828"><strong>0.599684</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000527 | -0.001229 |
| LUAD | rna_100 | 0.591260 | 0.591260 | <span style="color:#c62828"><strong>0.600386</strong></span> | <span style="color:#c62828"><strong>不补偿</strong></span> | +0.000000 | -0.009126 |
| LUAD | text_100 | <span style="color:#c62828"><strong>0.597052</strong></span> | 0.596350 | <span style="color:#c62828"><strong>0.597052</strong></span> | <span style="color:#c62828"><strong>LUAD-m1-force 组合、不补偿</strong></span> | +0.000702 | +0.000000 |
| LUAD | both_100 | <span style="color:#c62828"><strong>0.590207</strong></span> | <span style="color:#c62828"><strong>0.590207</strong></span> | 0.586873 | <span style="color:#c62828"><strong>LUAD-m1-force 组合、均值填补</strong></span> | +0.000000 | +0.003335 |
| UCEC | none | 0.639439 | <span style="color:#c62828"><strong>0.645448</strong></span> | 0.638326 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.006009 | +0.001113 |
| UCEC | rna_100 | 0.640107 | <span style="color:#c62828"><strong>0.648342</strong></span> | 0.643000 | <span style="color:#c62828"><strong>均值填补</strong></span> | -0.008235 | -0.002893 |
| UCEC | text_100 | <span style="color:#c62828"><strong>0.586023</strong></span> | 0.555753 | 0.578233 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.030269 | +0.007790 |
| UCEC | both_100 | <span style="color:#c62828"><strong>0.586690</strong></span> | 0.571111 | 0.569775 | <span style="color:#c62828"><strong>LUAD-m1-force 组合</strong></span> | +0.015580 | +0.016915 |

## seed结论

LUAD-m1-force绝对平均C-index最高的seed：`123`。
相对两基线平均Δ最大的seed：`123`。二者不混称，且不替代五seed结论。
