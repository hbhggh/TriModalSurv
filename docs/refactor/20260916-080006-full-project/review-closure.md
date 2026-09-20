# Claude 第一轮代码审查闭环

| 项 | 修复与证据 |
|---|---|
| F1/F2 | population 种子初始化恢复；真实 scripts 路由、CLI优先与配置入口测试 |
| F3 | v6 22条CLI退出0，根/非根完整runtime/model相等 |
| F4 | experiments-report.md 已建立，实验README可定位 |
| F5 | 实际fusion类名；NPJC原规格不变 |
| F6 | 全src、活动实验、公共脚本及实际配置源码指纹；I02标签来源 |
| F7 | worker-evidence/保存22份逐侧输入/导入元数据，环境另存，SHA清单可追踪 |
| F8 | --bin_mode=author识别与防重复测试 |
| F9 | 实际runtime.load_model与I03工厂类型、组合及state schema比较 |
| F10 | I03/I04显式--preset，CLI最终覆盖，未知项拒绝；Dm沿D权重 |
| F11 | progress.md区分已完成验证与待切换/复审 |
| F12 | checkout运行边界及缺实际配置的明确错误 |

额外修复：CSV/plots采用seed＋完整task身份；运行前冲突拒绝；新run目录独占，参数与来源启动时记录，checkpoint完成哈希由completion证据证明。

## 验证边界

CPU v6为178通过/6历史skip。旧CUDA scattermoe测试随不用的模型归档，未用新增skip掩盖。真实I01/I02仅BLCA seed123前32人16格，合成7路径；不代表全癌种正式训练验收。可编辑SVG已验证嵌入scene可解码，未做原生Excalidraw打开验收。

阶段代码审核和最终资产审核分别留存，不能用进程退出0替代PASS。

## 第三轮补充

- 新增公共 runtime.main 的合成全流程测试：输出预检、pending记录、绘图目录、CSV/指标、completion及冲突拒绝。
- v6 已有 I02 非 population 入口前置拒绝；复审所述非 population pending 路径不可达，新增拒绝测试固定该事实。
- I02 缺配置、共享配置缺 network 段的异常改成明确契约错误。
- d0/dq0 沿历史 checkpoint 命名，须使用不同 result_path，冲突时拒绝；本轮不改权重命名。
