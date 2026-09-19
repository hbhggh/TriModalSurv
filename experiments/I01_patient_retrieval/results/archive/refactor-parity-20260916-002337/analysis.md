# I01 重构兼容性回归

BLCA seed123，按ID排序的前32个test患者，完整合法train库，3臂×4格点，CPU FP32，零训练。

旧、新实现 strict E0 加载、donor、mask、填补输入、库指纹一致；投影输入/输出、logits、A/B风险全部通过 atol=1e-6、rtol=0。逐格差异见 [parity.json](audit/parity.json)。

只验证固定回归范围；没有重算正式C-index，不能据此声称五癌五seed或GPU行为已验证。
