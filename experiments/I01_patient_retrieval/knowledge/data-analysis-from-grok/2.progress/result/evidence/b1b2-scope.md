# 本轮两点修复范围

- 用户已明确批准：只修B1/B2、回归、新目录冒烟；本轮不需要Claude再审。
- 不调用Claude、不生成PASS票据、不修改正式授权门；正式valid/test依然未获授权。
- 生产改动仅selection.py、reporting.py、runtime.py；其余只有测试、记录及独立运行配置。
- 旧源码快照：b1b2-before.tar；旧JSON/旧冒烟不覆盖。
- 新远端镜像：/home/wuhao/npj_rules15_b1b2_20260916_fiYJ87；资产仍只读复用，不修改缓存或权重。
- 验收：业务RED→GREEN、完整新旧回归、五癌seed123四场景CPU valid冒烟，不计算C-index。
