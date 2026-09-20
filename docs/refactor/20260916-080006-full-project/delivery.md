# 全项目重构交付

## 范围

全项目按职责归位：共享实现 `src/trimodalsurv/`，公共入口 `scripts/`，I01–I04 的模型/配置/知识/结果归入各实验，工作流与研究构想分开，历史原件进入 `archive/`。MCAT/PORPOISE 保持独立仓库。新实验按 `_template/` 六文件骨架创建，本轮未虚构新 ID。

## 验收证据

- [v8测试](validation-evidence/new-v8-tests.log)：186 passed，6 个原有 skip，1 个 PyTorch warning；[源码指纹](validation-evidence/local-v8-fingerprint-check.json)覆盖94文件。
- [切换后入口](post-cutover-verification.json)：22 条 CLI 通过，跨工作目录解析结果相同；本机 launcher dry_run 通过。
- [资产审计](asset-audit.json)：21614 项 T0 备份逐字节校验；7956 项归档内容、5820 份使用副本、2669 项原位历史内容分别核验。计数可能重叠，不相加。
- [仅存在性检查](active-existence-only.json)：2708 个原路径没有按原字节不变验收，其中2406项为Git元数据；外部worktree仅备份核验，未原位重验。
- [链接审计](link-audit.json)：活动导航142个有效链接，0新增断链；归档内部历史链接未改。
- [旧→新映射](all-files-map.json)与[迁移事务](cutover-operations.jsonl)可追溯全部20项归位。

## 实验边界

真实CPU对拍范围为 BLCA seed123 前32位test，I01三臂×四格及I02四格共16格，最大差0；另有7组合成数值校验。公共main产物测试使用受控epoch/prediction和CPU替身，不等于正式训练或多卡验收。没有启动正式训练、安装依赖、重建真实缓存或变更远端部署。新SVG已验证嵌入scene，未完成原生Excalidraw编辑保存验收。

根工作区保留未提交变更，未盲目提交用户原有修改，未推送；源码保护快照与完整备份单独保留。

## 审查结论

实际 Claude [代码第四轮](claude-code-review-4.json)与[资产第二轮](claude-final-asset-review-2.json)均为 PASS，required_changes 为空。保留审阅中的限制，最终本机资产/链接/94源码指纹再核验。
