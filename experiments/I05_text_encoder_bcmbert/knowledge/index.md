# I05 知识索引

## 原始需求与原始证据（所有模型读同一份，不做逐级转述）

- [原始需求：4.1.BioClinical ModernBERT-prompt.md](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/4.BioClinical%20ModernBERT-程序性知识/4.1.BioClinical%20ModernBERT-prompt.md)
- [选择记录：4.2.BioClinical ModernBERT-方案细化（Claude）.md](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/4.BioClinical%20ModernBERT-程序性知识/4.2.BioClinical%20ModernBERT-方案细化（Claude）.md)
- [交接给 ChatGPT Pro 的结构化 Prompt 与 Pro 版先验知识](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/1.原始发给ai的信息/)
- [三份 AI 回答（ChatGPT、Claude、综合）](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/2.来自ai的回答/)

## 本实验文档

- [先验知识：innovation-BioClinical ModernBERT.md](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/4.BioClinical%20ModernBERT-程序性知识/innovation-BioClinical%20ModernBERT.md)
- [研究计划书（两张 mermaid）](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/4.BioClinical%20ModernBERT-程序性知识/研究计划书-BioClinical%20ModernBERT.md)
- [本轮给 Claude 的结构化 Prompt](../../../manuscript/消融实验/2.innovation-secode-part-%20Encoder/4.BioClinical%20ModernBERT-程序性知识/给Claude的结构化Prompt.md)
- [机制说明](method.md)

## 复用的冻结实现（只读，sha256 锁见 config.yaml）

- [2.progress 零训练推理器](../../I01_patient_retrieval/knowledge/data-analysis-from-grok/2.progress/result/)：`runtime.load_cancer`、`run.evaluate_cell`、`inference.prepare_batch`
- [历史选参锁](../../I01_patient_retrieval/knowledge/data-analysis-from-grok/2.progress/result/runs/valid/selection-lock.json)：冻结 combo `combo-l1-a1-w0p5`
- [S0-force 路由函数](../../I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/luad_m1_force/model.py)：`route_patient`
- [Table 1 对照原始结果](../../I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress/runs/test/complete.json)
