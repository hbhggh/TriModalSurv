# Codex 中间独立复核（不代替 Claude）

| 问题 | 修复 | 证据 |
|---|---|---|
| 未开启①的单点被误标为固定m0real | 报告先判断是否开启①，否则UCEC例外不适用 | tests/test_reporting.py |
| λ=1遭受大均值减加抵消 | λ=0/1直接复制各自端点，再转输入dtype | tests/test_rules.py，极端尺度反例 |
| 人数超过总数/同格诊断不一致仍可汇总 | 人数上界、同格人数和误差一致性校验 | tests/test_selection.py、test_reporting.py |
| selected未绑定valid台账 | 逐项绑定ID、规则、参数和UCEC判断 | tests/test_reporting.py |
| 恢复单元未核对格点与候选全集 | verify_cell核对身份、患者、完整人数、候选及预测/审计引用 | tests/test_runner.py |
| 半写JSON可能冒充完成标志 | 临时文件fsync后通过不覆盖硬链接原子发布 | tests/test_runtime.py |
| 历史重放差异未向MD披露 | 三份MD增加历史可比性边界，保留本批内部比较 | tests/test_runner.py |

## Bug Post-Mortem：恢复和证据绑定
- **现象**: 静态复核指出同一运行的错癌格点或删行cell可能被冒烟恢复接纳；半写最终JSON无法可靠恢复。
- **根因**: 最初只核对campaign指纹及已列出的工件SHA，没有核对完整单元契约；最终名直接写入。
- **修复**: 显式expected cell/specs/patients/ckpt/metricmode校验；原子不覆盖发布；测试覆盖错癌、缺候选与发布失败。
- **Prevention Rule**: 完成标志必须由完整内容契约和原子发布产生，不能由文件存在推断；沿用坑台账D15/V6，不重复入账。

## Bug Post-Mortem：新参数被局部变量遮蔽
- **现象**: 加强verify_cell后原恢复单测出现TypeError。
- **根因**: 原工件循环名expected遮蔽新expected契约参数。
- **修复**: 工件摘要变量改为expected_sha，运行门10项回归通过。
- **Prevention Rule**: 扩展校验函数时，保留旧行为回归并审查名称复用；属于V9集成契约防线，本次不改公共代码。

## Bug Post-Mortem：历史结构解析
- **现象**: 首版历史重放读取器按平铺grid/c_index_b取值，不能读原正式JSON。
- **根因**: 新行schema与旧arm级grids/cindex_B schema不同。
- **修复**: 读取旧grids嵌套；合成原schema反例先红后绿；旧JSON未写入。
- **Prevention Rule**: 跨格式消费者先按真实生产schema构造验收，沿用V9，不重复入账。

## 状态边界
- 本记录是实现中间检查，不是Claude审核结论。
- 真实CPU测试、资产核验和valid冒烟分别记录；未启动正式valid选择或test。
