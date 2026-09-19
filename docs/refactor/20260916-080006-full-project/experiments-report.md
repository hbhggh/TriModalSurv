# I01–I04 迁移验证

## 实现边界

- I01：774f 的原始特征配对检索；投影前填补，共享 NPJC。
- I02：684e 的 PopulationPrototypeBank、每轮建库、早停与严格重载协调；共享编码/融合，训练前向不填补。
- I03：已有 D/Dm/旧 E1 的组合入口与历史身份；不新增研究机制。
- I04：根 NPJ 的 CAPRecallMulti、初始化与诊断，只整理已有 D 版预设；没有执行 C 版实验。

逐符号、源哈希、旧测试节点见 [source map](experiment-source-map.json)、[AST 核验](experiment-ast-verification.json)、[测试映射](all-test-nodes-map.json)。原 GPU scattermoe 测试随未用实现归档；未增加 skip。

## 本轮可见证据

- [迁移测试](validation-evidence/new-v8-tests.log)：186 passed、6 个原有 skipped。
- [独立进程真实对拍](validation-evidence/real-parity.json)：BLCA seed123、排序前32 test，I01 三臂×四格，I02 四格，CPU FP32；最大绝对差 0，容差 atol=1e-6 / rtol=0。
- [合成单步](validation-evidence/synthetic-parity.json)：7 个模型/补偿路径的初始状态、输出、loss、全部非空梯度、一次 Adam 更新及严格重载；最大差 0。
- [公共 epoch 单步](validation-evidence/epoch-parity.json)：透明测试包装下实际 finetune_epoch，单合成 batch，旧新差异 0。不等于多卡/正式患者训练验证。
- [权重](checkpoint-transfer-verification.json)：25 份 I02 本地与 tako 大小/MD5/SHA256一致；weights_only=True、strict=True 加载及原型 buffers 检查通过。
- [CLI](validation-evidence/cli-preflight-v8.json)：项目根与非根 cwd，22 项 help/dry-run 退出码 0，解析后的 runtime/model JSON 跨 cwd 完全相同。

I01 E0 沿用原加载器已有 `module.` 前缀处理合同；不修改 checkpoint。I02 原生 state_dict 不 remap。真实输入沿用 tako 既有冻结缓存；没有重建缓存、下载数据或启动正式训练。

以上是候选代码的固定范围证据，最终源码版本及 Claude 审阅结论以[执行状态](progress.md)为准。
