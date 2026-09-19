# 删除cpa

“关于缺失模态补偿后的融合逻辑，我已决定 **彻底删除 CAP (Cross-Attention Projection) 模块** 。
**理由如下：** 因为我们确立了‘训练期不读库’，如果强行保留 CAP，它在训练时只能学习自身完美配对的注意力，在推理时面对检索来的带有一定域偏差的 RNA 会发生分布不匹配（Train-Test Mismatch），反而大概率成为拉低 C-index 的副作用。

MUST:[arxiv.org/pdf/2603.26071](https://arxiv.org/pdf/2603.26071)

A cancer-type：[doi.org/10.1093/bib/bbag124](https://doi.org/10.1093/bib/bbag124)

[M³Surv：]([https://pdf.sciencedirectassets.com/272154/1-s2.0-S1361841525X00086/1-s2.0-S1361841525003925/main.pdf?X-Amz-Security-Token=IQoJb3JpZ2luX2VjEC4aCXVzLWVhc3QtMSJIMEYCIQCl7NNWdlBFmO9Ji5Fr7b8To1I0%2FeswqxsTBe2ROgeq2QIhAMQo2gQWF9N5W%2FtIFOwoV8KE5r4U5D6G8z2gGOyG%2FVsuKrwFCPb%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQBRoMMDU5MDAzNTQ2ODY1Igw81kMUPXwlW2dTW6sqkAVPtyLv3lqtHIQeQQjWMmaiY27txq2jcJE0%2FQqgTefjuQoDHS5z3c0Wx65Xop0Zh9C5%2ByMoi5Grntdww55oY9DuDBpphGR%2Bht%2B36F2DERT5hkF%2BXO8lSpoqqFXBMdi6vCM0PStFEwpMB%2BtDcX5%2BoBga1ZNQZQyG04mTEGtJjoemPC0wQBxBabj171PLplzyfL28P2Kbn7C6%2BxCBuGeGtylZXvi%2BJ9%2F2l%2BRXnoeCuBxew4SmkBUSz8lnXbZ8R7i1sx6mYOQrt%2BCpPGFHwi7UwxpXnfWRkJOsSk%2FoOQFr%2BLnObOzgRPTOhHPb1tAKrhP%2B8SdVvCkcLrc%2ByVBt%2FRWl%2FfDSfp05AaBJNpictvpfWN4Bw1gB2l%2BjTUMlINjK6Two9gm%2B3xvw9Mn%2BYbHppWBD30tk7jW%2FGE7lJaLcRSkgOMFbEkJMOAA8WPQIWBy%2F9t5DxMLT1Qx3rhEPPLnnCCIckAk8g1j5c7tYjCJXoF7MJBv6xidvExLLow1y1iCxTIDynCvvrnkI5OtzWzZ%2BDxjS6qTbMaYJU8TloJSg4JjmHEiiR1vwuvIK16YzSRpH2Mo61t784Jm3M7h3A0sxZGYZOF8KZjTbwe5yK4LcvhosB0ooeEz25D98B08a5%2FhXVNAgQAmNohrVDJJFux8Scm7PNB8MQHxjbA18nJFrCSxqZuO2eY62uCzvwhmplXUQ29tegm3DRgVt811IRUiOh5K2o5hsGIrKcjfvx5LEx8Z1%2FDcGoRiPMEprb2vZjVQ%2BsHBJVxHXkwaGK9tFT%2FikiLZ4lDyMKlUAC2KrgDXuXQ1%2FX80jKWqC9a86hL2mkZvP%2FeCpvla%2FU%2FR9siKVkLAX546aXaU8csQzXLPv1TBhaZYtygv50TCyq6PVBjqwARD4DlCj3yxSgiRIu%2BdwaKNeyyzkHoaa4d4XUBIbeaxicPjQsUJR%2Bewp1r9%2BH1s1vm9yMxG%2BVSUIYdnqvG%2F9zossIq99W5GGP1hVSJEYG1X07a7dcNsQn4pnvkDjuxLTPXmV76IT%2BX6%2FbTgBE1jkARrRAoh0SrpmIHKK39yEwjRIOnAGh3eNle8Rww6otEneMdrgNxW5Ub0oC6kfz1ECrH12Nrz1CaK3CBDttYgBnOtI&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20260915T055753Z&X-Amz-SignedHeaders=host&X-Amz-Expires=300&X-Amz-Credential=ASIAQ3PHCVTY6KK6EOQ4%2F20260915%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Signature=ab0729e9eafb603e2c1b373ce848ebe42daebf546c602b9661c99142e4f098c8&hash=208d0314ca890a9e37ec8041f033d000181490e7d5ad68f28598e5d2e29fd0f8&host=68042c943591013ac2b2430a89b270f6af2c76d8dfd086a07176afe7c76c2c61&pii=S1361841525003925&tid=spdf-24a86581-75fb-47d9-a7a9-2d1f73a5a0c9&sid=381420de27dbf941039ab451f8df06c502a1gxrqa&type=client&tsoh=d3d3LnNjaWVuY2VkaXJlY3QuY29t&rh=d3d3LnNjaWVuY2VkaXJlY3QuY29t&ua=101f03570d5a52575502&rr=a3b5657d6e7de3bb&cc=jp](https://pdf.sciencedirectassets.com/272154/1-s2.0-S1361841525X00086/1-s2.0-S1361841525003925/main.pdf?X-Amz-Security-Token=IQoJb3JpZ2luX2VjEC4aCXVzLWVhc3QtMSJIMEYCIQCl7NNWdlBFmO9Ji5Fr7b8To1I0%2FeswqxsTBe2ROgeq2QIhAMQo2gQWF9N5W%2FtIFOwoV8KE5r4U5D6G8z2gGOyG%2FVsuKrwFCPb%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQBRoMMDU5MDAzNTQ2ODY1Igw81kMUPXwlW2dTW6sqkAVPtyLv3lqtHIQeQQjWMmaiY27txq2jcJE0%2FQqgTefjuQoDHS5z3c0Wx65Xop0Zh9C5%2ByMoi5Grntdww55oY9DuDBpphGR%2Bht%2B36F2DERT5hkF%2BXO8lSpoqqFXBMdi6vCM0PStFEwpMB%2BtDcX5%2BoBga1ZNQZQyG04mTEGtJjoemPC0wQBxBabj171PLplzyfL28P2Kbn7C6%2BxCBuGeGtylZXvi%2BJ9%2F2l%2BRXnoeCuBxew4SmkBUSz8lnXbZ8R7i1sx6mYOQrt%2BCpPGFHwi7UwxpXnfWRkJOsSk%2FoOQFr%2BLnObOzgRPTOhHPb1tAKrhP%2B8SdVvCkcLrc%2ByVBt%2FRWl%2FfDSfp05AaBJNpictvpfWN4Bw1gB2l%2BjTUMlINjK6Two9gm%2B3xvw9Mn%2BYbHppWBD30tk7jW%2FGE7lJaLcRSkgOMFbEkJMOAA8WPQIWBy%2F9t5DxMLT1Qx3rhEPPLnnCCIckAk8g1j5c7tYjCJXoF7MJBv6xidvExLLow1y1iCxTIDynCvvrnkI5OtzWzZ%2BDxjS6qTbMaYJU8TloJSg4JjmHEiiR1vwuvIK16YzSRpH2Mo61t784Jm3M7h3A0sxZGYZOF8KZjTbwe5yK4LcvhosB0ooeEz25D98B08a5%2FhXVNAgQAmNohrVDJJFux8Scm7PNB8MQHxjbA18nJFrCSxqZuO2eY62uCzvwhmplXUQ29tegm3DRgVt811IRUiOh5K2o5hsGIrKcjfvx5LEx8Z1%2FDcGoRiPMEprb2vZjVQ%2BsHBJVxHXkwaGK9tFT%2FikiLZ4lDyMKlUAC2KrgDXuXQ1%2FX80jKWqC9a86hL2mkZvP%2FeCpvla%2FU%2FR9siKVkLAX546aXaU8csQzXLPv1TBhaZYtygv50TCyq6PVBjqwARD4DlCj3yxSgiRIu%2BdwaKNeyyzkHoaa4d4XUBIbeaxicPjQsUJR%2Bewp1r9%2BH1s1vm9yMxG%2BVSUIYdnqvG%2F9zossIq99W5GGP1hVSJEYG1X07a7dcNsQn4pnvkDjuxLTPXmV76IT%2BX6%2FbTgBE1jkARrRAoh0SrpmIHKK39yEwjRIOnAGh3eNle8Rww6otEneMdrgNxW5Ub0oC6kfz1ECrH12Nrz1CaK3CBDttYgBnOtI&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20260915T055753Z&X-Amz-SignedHeaders=host&X-Amz-Expires=300&X-Amz-Credential=ASIAQ3PHCVTY6KK6EOQ4%2F20260915%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Signature=ab0729e9eafb603e2c1b373ce848ebe42daebf546c602b9661c99142e4f098c8&hash=208d0314ca890a9e37ec8041f033d000181490e7d5ad68f28598e5d2e29fd0f8&host=68042c943591013ac2b2430a89b270f6af2c76d8dfd086a07176afe7c76c2c61&pii=S1361841525003925&tid=spdf-24a86581-75fb-47d9-a7a9-2d1f73a5a0c9&sid=381420de27dbf941039ab451f8df06c502a1gxrqa&type=client&tsoh=d3d3LnNjaWVuY2VkaXJlY3QuY29t&rh=d3d3LnNjaWVuY2VkaXJlY3QuY29t&ua=101f03570d5a52575502&rr=a3b5657d6e7de3bb&cc=jp))

# 癌症种类：：   #TODO 癌症种类扩大5️⃣->🔟

## 10cancer种类现状

* <span style="color: #980000;">BLCA、BRCA、LGG、LUAD、UCEC</span>：标准目录中有各 5 个 E0 checkpoint，也有配置所需的 WSI/RNA 特征。
* GBM、COAD、READ、HNSC：标签和划分已有，但当前配置的特征路径缺失，未找到对应 NPJ-C 权重。
* STAD：当前标签表、特征路径和权重记录均未覆盖。

  先进行五个癌症的5seed实验

  本地旧标签表将 **GBM/LGG、COAD/READ 分开记录**

  GBMLGG分开，也可合并

# 固定规则

同时缺 RNA 和文本：从两者<span style="color: #ff0000;">均真实存在的候选中选一个患者</span>，两种特征由同一 donor 提供。

五癌固定患者库：实施交接

## 当前主线

**实现已落地；正式评测暂停。** 固定库、三臂评测、严格汇总器与更新后的讨论文档均在本 worktree。训练入口和 NPJC 融合实现未改；新模型直接 compensator=None。

证据：远端 42 项测试全部通过；25 份约定 E0 权重 strict load、有限值和跨 seed 内容去重通过；3 个未阻断癌种做过小样本 CPU 冒烟。没有正式 C-index。

警告：BLCA test 1 人、LGG train 2 人及 test 1 人含 WSI 全零行；不能删除这些行/患者后继续冒充原协议。权重的历史 seed→SHA 映射未独立闭合，交原资产负责人/Claude 核验。

## 主因链

```mermaid
flowchart LR
    A[冻结 train WSI 128×D] --> B[患者等权 D 均值去中心<br/>原顺序展平余弦]
    B --> C[合法 Top-1 donor<br/>双缺失取同一人]
    C --> D[原始 value → mean → projector<br/>只将补后位置置 valid]
    D --> E[原无 CAP NPJC → B risk]
```


## 

# 数据集策略定义 (Dataset Policy)

## 动态 Modality Dropout

**推荐采用“动态 Modality Dropout”（即训练时以 30% 的概率随机 Mask 辅助模态），而不是“静态裁剪 30% 的数据集”。**

在多模态生存分析中，这种策略能有效解决上一轮“患者检索（Retrieval）败给基线”的核心痛点。

---

**核心逻辑与对比**

* **绝对不要做“静态删减”**：不要在数据预处理阶段直接永久删掉 30% 样本的模态。这会白白损失训练数据量，降低模型能力。
* **务必采用“动态 Modality Dropout”**：保留全量训练数据，在训练循环（Forward Pass）中，**以 30% 的概率随机将 RNA 或 Text 模态进行 Mask（置零或填空）**。

---

**为什么 30% 动态缺失率能救活检索实验？**

1. **消除 Transformer 的“全模态依赖症”**
   若 100% 完整训练，Transformer 会过度拟合“同一患者内完美的 WSI-RNA-Text 联合分布”。推理态一旦出现人工缺失或塞入检索来的外部特征，模型就会产生强烈的“排异反应”（视为噪声导致 C-index 暴跌）。
2. **为检索换填（Retrieval）建立缓冲区**
   训练时让模型见过 30% 的缺失情况，逼迫融合层学会“在缺少某模态时自动降低该模态权重”，或者“容忍不完美/外来的填补特征”。此时检索回来的特征即使带有一些噪声，模型也有足够的鲁棒性去消化它。
3. **保障 WSI 主干的锚点作用**
   建议**仅对辅助模态（RNA / Text）施加 30% 随机 Dropout**，保持 WSI 100% 参与训练。因为 WSI 是检索的 Key，也是最基础的形态学特征。

---

**更新后的 Config 策略参数 (用于 Prompt 补充)**

在发送给 Codex 的 `config` 中，可将训练集数据策略显式补充为：

* `train_modality_dropout_prob`: `0.3`（训练期 RNA/Text 动态掩码概率）
* `train_mask_strategy`: `"dynamic_random"`（每个 Epoch 随机 Mask，非静态删减）
* `protected_modality`: `"wsi"`（WSI 模态不参与 Dropout，保持 100% 输入）

--------------------------------------------------

## 测试评估矩阵 (Evaluation Grid & Scenarios)  #TODO   放入到config

测试阶段必须在 config 中配置以下完整矩阵，推理脚本自动遍历执行：

四个人为缺失格点 (Mask Grids)：

	none：无人为 Mask（保持数据集天然缺失状态，用于校验上界）。

	rna_100：强制遮挡 100% RNA 模态（仅保留 WSI + Text）。

	text_100：强制遮挡 100% Text 模态（仅保留 WSI + RNA）。

	both_100：强制同时遮挡 100% RNA 与 Text 模态（仅保留单 WSI 模态）。

三臂填补策略 (Three Evaluation Arms)：

	m0real（不补偿）：缺失模态直接置零/空掩码，不引入外部信息。

	m1（均值填补）：缺失模态采用训练集全局均值（Train-set Mean）进行盲补。

	retrieval（患者检索）：基于 WSI 展平余弦相似度（共同有效行归一化），从训练集 Key/Value 库中检索 Top-1 真实患者的原始序列进行换填。




# 配置中心化 (Centralized Config Requirements).  

所有训练与评估参数必须在 `config` 中集中声明，主代码逻辑仅通过读取配置运行：

* **训练控制参数** ：
* `max_epochs`: `200`
* `early_stopping_patience`: `15`（监控指标：Validation C-index，无提升自动截断并恢复 Best Checkpoint）
* `learning_rate`, `weight_decay`, `batch_size`, `optimizer` 类型
* `prototype_k`: `128`（原型矩阵维度固定 **$128 \times D$**）
* **实验范围与随机种子** ：
* `cancers`: `["BRCA", "LUAD", "UCEC", "BLCA", "LGG"]`
* `seeds`: `[123, 132, 213, 231, 321]`
* **损失函数与权重** ：
* 生存分析 Loss 权重、对比学习 / 检索损失权重（如有）

#### 

#### 


| 癌种 |   不补偿 |     均值 |     检索 | 检索−均值 | 检索−不补偿 |
| ------ | ---------: | ---------: | ---------: | -----------: | -------------: |
| BLCA | 0.581194 | 0.579598 | 0.564365 | −0.015232 |   −0.016829 |
| BRCA | 0.644957 | 0.639541 | 0.646236 |  +0.006695 |    +0.001279 |
| LGG  | 0.683092 | 0.696779 | 0.687969 | −0.008811 |    +0.004877 |
| LUAD | 0.587586 | 0.588066 | 0.576857 | −0.011209 |   −0.010729 |
| UCEC | 0.604273 | 0.602760 | 0.614986 |  +0.012226 |    +0.010713 |
