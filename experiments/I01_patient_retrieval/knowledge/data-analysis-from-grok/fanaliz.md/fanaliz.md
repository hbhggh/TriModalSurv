
【已有信息】阅读/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok，准确来说是观看/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress文档，尤其是/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/癌症为单位.md和/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/seed单位-实验结果.md，消融实验的中原型学习的在五个癌症中的胜率到达了五分之四，此方案可以收尾了。

【触发场景】因为想要将原型学习放入到论文中，但为了避免自己从头造车，所以打算在/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/trimodalsurv-论文初版本-modify-from-bbag124.docx作为我投稿论文的基础，将现在有的原型学习在五癌症的四种情况（none，rna_100，text_100，both_100）中的实验表格。

【]what is must be true afterward】]以/Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/消融实验-prototype.excalidraw.svg作为实验结果输出的参考框架，必须参看！包含不补偿，原型补偿和均值补偿在五个癌症四个状况下的实验结果。

在/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.tex中，新增一个部分table1:comparsion 5 cancers from 4 situation with 3 agrithem。

[本次交接]

1. 不需修改么删除/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/trimodalsurv-论文初版本-modify-from-bbag124.docx作为我投稿论文中的任何内容，包括参考文献，
2. 生成table1:comparsion 5 cancers from 4 situation with 3 agrithemz以后，在/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.tex中，配上文字说明实验结果的说明，低调克制的强调原型学习的优点。
3. 生成table1:comparsion 5 cancers from 4 situation with 3 agrithemz以后，在/Users/wuhao/Desktop/TriModalSurv/manuscript/bmc_initial_draft/main.tex中，添加整个原型学习的基本的公式的逻辑推导，并标注好序列号，

【备注】]我之前将上述文本发送给Claude code，虽然可以读取本地的文件但是claude因为没有完整的聊天的上下文，所以claude对我的意图发生了偏移。



任务1:将上述prompt润色成有结构的prompt。

任务1:是将实验的数据保存路径提取出来，以及原型学习的/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress的实验中公式逻辑标注清楚

任务3:生成table1:comparsion 5 cancers from 4 situation with 3 agrithem必须严格对照/Users/wuhao/Desktop/TriModalSurv/manuscript/消融实验/消融实验-prototype.excalidraw.svgd的结构去生成消融实验的实验结果的table



首先润色上述的prompt，然后并同步生成实验的markdown作为先验知识，说明文件，防止claude发生目标偏移。
