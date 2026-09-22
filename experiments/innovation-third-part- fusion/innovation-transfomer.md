【trigger：触发场景/背景】

	实验的核心创新点，消融实验已经获得在五个癌症的种类中的五分之四的胜率，接下来我们打算加入第二个辅助创新点，指的是将原先的NPJ的骨架的特征融合模块，即一层普通的transformer替换成一个先进前沿的特惠融合方法，可以是先进变体的transformer，例如moe transformer，也可以是其他的特征融合策略。因为是辅助的创新点，所以不希望花费太多时间去修改算法，最好的情况就是基于现在已经验证后的包含模型（包含原型学习的架/Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/4progress-claude交接/实验先验知识与公式说明.md

#### S_state

当前代码/配置版本；原始结果与日志的位置；
已证实的事实、未核验的假设、已经失败的尝试。

【candidate strategy】]候选的创新点k1是打算将原模型中一层的transformer修改成更加更炫的Transformer变体的融合方式（例如moe transformer）。具体来说wsi和text，rna进入transform之前，可以**不压缩成一个特征向量**，直接让WSI 的多个 token和text 的多个 token和RNA 的多个 token交互➕换一个更加先进的，听起来**更炫的Transformer变体的融合方式。

	【约束1-前沿模型】。首先必须是比较新，比较炫酷的特征融合方式，因为只有这样才有创新性，编写论文故事的时候才可以。

	【前沿模型-how to do it】使用chatgpt网页端的pro的网页搜索能力，结合consensus插件搜索顶级论文（生物信息）和顶级最新的会议（CVPR / ICCV / ECCV等）尤其关注multimodal、missing modality、token fusion方面的论文

【前沿模型-how to do it-候选的fusion机制的]基于此项目的多模态癌症分析中模态缺失问题和数据集的数据量和数据特点，去刷选候选的前沿模型，检查标准是每个候选特征融合策略和S_state交集，将满足后的交集【ki】

why：因为是多个特征向量相互交织，所以最后的结果应该是原先基于NPJ架构的网络的大于先压缩，然后三个向量相互交织的效果。也就是

    what-老版本：

    WSI 的多个 token  → 汇总成 1 个向量
		text 的多个 token → 汇总成 1 个向量
		RNA 的多个 token  → 汇总成 1 个向量
                     ↓
共 3 个向量进入 Transformer

    what-after

    WSI 的多个 token

    text 的多个 token
		RNA 的多个 token

汇总成一个新的innovation的transformer中
