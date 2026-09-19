# A/B 首单记录：单 ε（both_100 并入报告 + 缺失率曲线绘图脚本）

同一契约（`plan.md` 单 ε 定稿）、同刻派发、互不知晓、输出前缀隔离；复核用同一脚本（指挥官 `verify_eps.sh`：越界 SHA 基线、字节重放、再生成比对、oracle 66 单元、行为测试、确定性、尺寸）+ 人工读代码与「歧义与自行裁决」。

| 字段 | Opus（Agent 工具，claude-opus-5，general-purpose） | Codex（companion task，gpt-5.6-sol，effort high） |
|---|---|---|
| 派发时刻 | 2026-09-04 10:10:20 JST | 2026-09-04 10:10:18 JST（jobId task-mtm9br8p-9s68kg） |
| 交付时刻（EPS_DONE） | 10:27:11 JST（16.9 min；agent 结束 10:28） | 首派作业 10:15:45 后静默死亡（pid 消失、status 仍 running）；10:31:15 `--resume-last` 被拒（companion 仍认为原作业 running）；10:33:02 cancel 陈旧记录后 10:33:03 再续接（task-mtma50g9-5se746）→ 会话落只读沙箱无法写；10:34:15 改开 `--write` 新会话（task-mtma6k61-160x0n）从磁盘状态续做；EPS_DONE 10:39:58 JST（新会话 5.7 min；首派起算 29.7 min 墙钟，其中 ~18 min 为死作业无人接管） |
| token / 工具调用 | 172,436 / 55 | companion 不报 token；两线程合计约 45 条命令 |
| 硬断言（复核脚本） | 全部通过：REPLAY_OK、T4/PW/T3 再生成逐字节一致、ORACLE 66/66、TIE=1、CONFLICT=2、MISSING=3、DETERMINISTIC、无 dc:date、PNG 2025×2400 / 2400×600、SVG ≥20KB、缺格 0、pycache 0、无末尾换行 | 全部通过（同一清单，结果逐项相同）；**三张表与 Opus 逐字节相同** |
| 越界 | 0（基线 495 文件仅本引擎前缀 + 指挥官 notes.md 变化） | 0 |
| 复核发现缺陷（逻辑/契约/格式） | 0 / 0 / 0 | 0 / 0 / 0（图 1 x 刻度用默认 0/20/…/100 而非数据点 0/25/50/75/100，契约未冻结刻度，不计缺陷） |
| 是否需续接 | 否（一次交付） | **是**：首派 5.5 min 后进程死亡、companion 状态陈旧 15 min（Monitor IDLE15 触发），续接 3 次尝试（被拒 / 只读 / 新会话 --write）|
| 自查返工 | 2 次（配对表末尾换行与契约"臂块尾空行"互斥 → 取文件级无末尾换行；图 2 刻度标签 10pt 粘连 → 8pt）+ 1 次 shell 失误（未引号 heredoc 触发命令替换，无产物影响） | 1 次 apply_patch 格式失败（同一补丁内 Delete+Add 同一路径，文件未受损）；业务实现各 1 次通过；TDD RED→GREEN 纪律 |
| 图表可用性 | 图 1/图 2 元素齐全、可直接入附录；图 2 刻度 8pt 缩略时 `rna_100` 形似 `ma_100`（SVG 源正确），成稿时建议加宽或 9pt | 图 1/图 2 元素齐全；图 2 刻度旋转更易读；图 1 刻度非数据点 |
| 「歧义与自行裁决」质量 | 15 条，均有依据与实测（如 SKIP 走 stderr 保字节重放；`--pairwise-*` 只给其一即 ap.error；CONFLICT 首条即退；自补 CKPT_MISMATCH 与 E0d 缺席分支测试） | 6 条，简洁有据；**抓到环境坑**：其 shell 里 `python3` 解析为 Homebrew 3.14.6（无 matplotlib），自行前置 `/usr/bin` 并记录；matplotlib 缓存目录不可写改用临时目录 |
| 代码结构（人工读） | summarize_arms 10 函数分层清楚（加载→合并→配对统计→渲染），退出码集中 `_die`，`--pairwise-*` 成对校验；plot 脚本 `import summarize_arms` 复用加载逻辑（单一来源）、显示名/颜色/图注常量集中；瑕疵：表头中文全部以 `\uXXXX` 转义写死，可读性差；`_resolve_dir` 的 cwd→ROOT 回退是契约外的便利行为（无害） | 12 函数 + `LoadError` 异常类，`build_parser/main(argv)` 可测式入口；绘图脚本自带 `_load_gate/_load_npjc`（未复用汇总器，两份加载逻辑）；字符串直接写中文（可读性优于 Opus 的 `\u` 转义） |
| 额外发现 | 指出 gate 版 `none` 格点 M1 vs M0-real 为 0:0:5（旧写法记 0:5，平局计负）——正是 V23 要修的口径 | 环境坑（python3 PATH 非对称）→ 入台账 E18 |

复核脚本自身缺陷 1 处（指挥官侧）：逐格断言正则未容忍末列尾随空格，首轮误报 15 处 "WL differ"，修正后 ALL SECTIONS OK；不计入引擎缺陷。

## 裁定（2026-09-04 10:45 JST）
- **正确性**：平手——两引擎全部硬断言通过，三张留档表逐字节相同，图均可用；均零越界、零复核缺陷。
- **交付可靠性（用户核心诉求）**：**Opus 胜**——单次派发 16.9 min 完整交付，全程有 notes 心跳与 agent 完成通知；Codex 首派 5.5 min 后 worker 静默死亡，companion 状态陈旧 15 min（正是"status 一直 running 但无产出"），续接又踩"死作业不 cancel 不让续接"与"`--resume-last` 落只读沙箱"两坑，需指挥官三次干预才恢复，墙钟 29.7 min。
- **工程质量**：接近——Opus 自补测试更多（CKPT_MISMATCH、E0d 缺席分支）、裁决记录更细（15 vs 6）；Codex 代码可读性略好（中文字面量、可测式 `main(argv)`）、TDD 纪律清晰、抓到 PATH 环境坑。
- **晋升**：Opus 产物晋升为正式 `tools/`、`figures/` 与四张表（含 `--base E0d` 再生成的 `table_npjc_E1_vs_E0d_4grids.md`）；Codex 产物原样保留于 `tools_codex/`、`figures_codex/`、`*_codex.md` 供审计。
- **对引擎选择的建议（供用户裁决，不改协议）**：主写码引擎用 Opus 子 agent（Agent 工具，前台可见、完成即通知、无静默死亡）；Codex 保留为对抗审查（`adversarial-review` 原生子命令）与第二意见；若继续用 companion `task`，必须配套 C13 存活判定（pid + 日志 mtime）与"需要写就开新会话 `--write`"的续接口径。
- 局限：单任务、小规模（两脚本 + 三表两图）、契约钉死后主要比"照契约执行 + 可靠性"，未测长任务与复杂多文件联动；Codex 的 worker 死亡原因未能从日志定位（日志在 10:15:45 后无任何错误行）。
