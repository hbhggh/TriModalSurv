# TriModalSurv 公共纪律（唯一源头）

Claude Code 与 Codex/Codex Companion 都必须遵守本文件。冲突时以本文件为准。

## 角色

- Claude Code 是唯一指挥官：定策略、监视任务、控制停机门、验收、部署下一步。
- Codex / Codex Companion 是执行者：只允许改代码、打补丁、做 adversarial review。
- Codex 不得自行决定开始正式训练、重下数据、重启任务。
- 任何一方执行完，必须由另一方 review。禁止同一方执行完直接宣布通过。

## 停机门

- 冒烟通过后必须停。
- 未获得用户明确允许，禁止开始 BLCA / BRCA / LUAD / LGG / UCEC 正式实验。
- 禁止启动 5-seed 全量与任何会占满 GPU 的长任务。
- MCAT / NPJ 骨架 / PORPOISE 都走同一条门。

## 执行纪律

- 通道超时先查进程；禁止把通道断当成任务死亡；禁止二次派单。
- 监视器默认只报警，不自动重启。
- 新下载 / 训练 / 转换必须经 landau 的 `jobrun.sh` 启动。
- 不改 `tmp_sur_cache/`，不覆盖已有结果目录。
- 不把"窗口还在"当成"任务还在"。

## 互审

- Claude 派给 Codex 的任务，Codex 执行完后必须回到 Claude 做检查。
- Codex 的 patch / review 结论，必须由 Claude 再看一遍才能进入下一 Gate。
- adversarial review 通过，不等于可以开正式实验；还要等用户点头。
