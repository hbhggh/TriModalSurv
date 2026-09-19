# strategy0：前置条件

协议：`patient-fixed-padmask-v2-infer-rules1to5-v1-luad-m1-v1`。本文件在本轮推理代码前创建。

| 条件 | 核验方式 | 状态 |
|---|---|---|
| 上游结果只读 | `2.progress/result` 的 config、代码、valid/test完成标记与三份报告均记录 SHA-256 | 是 |
| 上游 test 身份 | `runs/test/complete.json` SHA `99a8d0fec8c6adf65136c863a845c6ed105daf0593cfe90df8f08f521b1d2bca`；指纹 `32cb3f31579bec549214d8577ac3fe057edb84b8a3fac49989c7e86090c94f14` | 是 |
| 上游 valid 冻结 | `selection-lock.json` SHA `cd74151fb6c355c1234c1971d0bad36282d7da37718716867de42e289e03c0b3` | 是 |
| 科学边界 | 五癌、五seed、K=128、原权重/缓存/split、B口径、λ=1/α=1/w=0.5 均锁定 | 是 |
| 路由定义 | 仅 LUAD；`text_100→m0real`，`rna_100/both_100→m1`，`none` 仅缺RNA或双缺→m1 | 是 |
| valid 开关 | B均分严格大于A才启用；未启用亦只跑一次test | 是 |
| 不可写目标 | `2.progress`、checkpoint、缓存、split、历史JSON | 是 |
| 代码契约 | 先写失败测试，再实现路由；本轮不训练、不扩seed、不commit/push | 是 |

## 上游来源哈希

| 文件 | SHA-256 |
|---|---|
| `config.yaml` | `6d2c224fe3997cd58fc4a67bb0517183ec220480d2a30216dbb13f6b1d0c4b80` |
| `inference.py` | `b6581528aa0ba7aed718dbdd1f44b871a30c7de8839e949637c8cc4b849fcf99` |
| `run.py` | `3c6808fa453a40608b750665f9daa5bab2ad0edff1ef5fb9ee93d454d6290cb9` |
| `runtime.py` | `89ff2696657189792248a6bf9a2964ba091c1fa6e028d4e33843695db8d4dbf8` |
| `reporting.py` | `e3778e226aae83bc1f94c7fa968bbc2816f09a2e45a03a8ff3d61d60c1b38ca6` |
| `selection.py` | `9c6e241080a9a0c3f7ca46dd18269681c4ce27c04df593c9568ae8e53718fc40` |
| `runs/valid/complete.json` | `ef525bb07ca82dc3a9bd1315db53de2ad6813c5347fa74c24fecfe40fc28c70b` |
| `runs/test/complete.json` | `99a8d0fec8c6adf65136c863a845c6ed105daf0593cfe90df8f08f521b1d2bca` |

## 实现门与运行门

- 实现门：路由行为测试、上游一致性测试、冻结文件验证、报告验收均通过。
- 运行门：上游来源与资产哈希保持一致，远端配置与授权记录通过，目标GPU无外部计算 PID。
