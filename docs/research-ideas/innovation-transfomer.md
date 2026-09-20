
wsi和text，rna进入transform之前，可以**不压缩成一个特征向量**，直接让WSI 的多个 token和text 的多个 token和RNA 的多个 token交互➕换一个更加先进的，听起来**更炫的Transformer变体的融合方式**，

why：因为是多个特征向量相互交织，所以最后的结果应该是大于先压缩，然后三个向量相互交织的效果

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
