你是本项目 Claude 独立审阅者。本次仅只读审阅，不执行或建议正式训练，不编辑文件。
范围：/Users/wuhao/Desktop/TriModalSurv 当前新 src/trimodalsurv、scripts、experiments/I01_patient_retrieval 至 I04、tests、configs、pyproject.toml。
完整执行计划 docs/refactor/20260916-080006-full-project/plan.md，末节A-D优先；用户补充允许真实checkpoint对拍在tako CPU，landau托管/合成验证。现在处于根目录切换前的代码审阅，不是最终资产交付审阅。
T0源码可只读 /Users/wuhao/.codex/backups/trimodalsurv/20260916-080006/root/NPJ 与 684e/code/NPJ，774f/code/NPJ。仅阅读代码/配置/报告，不读取患者数据/权重内容。
证据：本批 validation-evidence/new-v2-tests.log（153 passed、6原有skip）、synthetic-parity.json（7模型路径旧新独立进程，固定seed、loss/grad/单optimizerstep）、real-parity.json（I01 3x4 + I02 4格，32患者）、checkpoints-verified.json（25个weights_only strict）。逐符号/测试来源见 shared-all-symbols.json、experiment-source-map.json、experiment-test-node-map.json。
请独立检查：1 公共训练/评测实际可用，无archive/旧NPJ依赖；2 默认根NPJC、I02仅eval补偿与参数键、I04现有D行为不变；3 launcher合并root与684e没有丢分箱/CAPL/K/早停或错误路由；4 config优先级/实际运行产物/resolved_config.yaml和结果目录是否兑现计划；5 测试是否存在空洞、弱化或仅测假入口；6 路径与非root cwd、数据缓存和输出不覆盖。
只报告具体可复现的必要修改，文件行号、原因、最小修正。已有缺失、科研协议缺陷如果没由重构引入，标历史事实，不要求借机重训。明确区分迁移bug和未兑现的计划。最终给JSON {verdict:PASS或REVISE,findings:[{id,priority,file,line,problem,fix}],verified_scope,limits}。不能凭测试绿宣布全面正确。
