# 执行记录

## 2026-08-26 20:27:04 JST — 计划与基线核查

- 已完整读取 `plan.md`（89 行），确认只允许修改 NPJ 工作区内 4 个白名单文件；另允许在本目录写 `notes.md`、`result.md`。
- 已确认禁止事项：不执行 `git commit` / `git push`，不执行 `ssh` / `scp`，不访问 landau，不下载数据，不安装依赖，不修改 `main_survival.py`、loss、模型类、seeds 或任何超参。
- `/Users/wuhao/Desktop/NPJ` 初始 `git status --short` 为空，工作树干净；主 YAML 与主 shell 均与 `HEAD` 一致；两个 UNI2 派生文件均不存在。
- 主 YAML 的 text 注释行实际为 `# path: data/text_embeddings/TEXT_EMBEDDING`。为避免非必要格式变化，决定保留注释原样，仅将生效路径改为已实测钉死的 `data/text_embeddings`；RNA 同样只改生效路径。
- 主 shell 将严格只改 `gpu_id`、`cancer_types`、`cpt_name` 三处；两个 UNI2 文件以阶段 0 完成版为基线，分别只改计划规定的两处。
- 只读预检发现本地 `python3` 可能缺少 PyYAML。依照 `plan.md`，不安装依赖；完成修改后仍原样执行 §4 命令并保留真实输出，若失败则补做不依赖 PyYAML 的严格比较并如实记录。

## 2026-08-26 20:28:35 JST — 白名单修改与派生文件

- 已修改 `model/config/surv_multimodal_mainmoe.yml`：仅替换 `text.path` 与 `rna.path` 两个生效值。
- 已修改 `running_scripts/survival_prediction_mainmoe.sh`：仅替换 `gpu_id`、`cancer_types`、`cpt_name` 三个计划指定值。
- 已新建 `model/config/surv_multimodal_mainmoe_uni2.yml`：以阶段 0 完成版为基线，仅替换 `img.path` 与 `img.feature_dim`。
- 已新建 `running_scripts/survival_prediction_mainmoe_uni2.sh`：以阶段 0 完成版为基线，仅替换 `--model_config` 与 `--cpt_name`。
- `git diff --check` 退出码为 0；两份 shell 的 `bash -n` 均通过。
- 逐字节断言已通过：主 YAML 等于 `HEAD` 加 2 次指定替换，主 shell 等于 `HEAD` 加 3 次指定替换；两个 UNI2 文件分别等于阶段 0 完成版加 2 次指定替换。输出：`BYTE-EXACT OK: A1=2 replacements, A2=3, B1=2, B2=2`。
- 当前 NPJ 工作树恰好出现 4 个白名单文件：2 个修改、2 个新增，没有白名单外差异。

## 2026-08-26 20:29:48 JST — §4 测试与 PyYAML 替代验证

- 已原样运行 `plan.md` §4 的全部 8 组命令。
- YAML Python 命令退出码为 1，原因为本地 `python3` 缺少 PyYAML：`ModuleNotFoundError: No module named 'yaml'`。未安装依赖，也未修改环境。
- 两份 shell 的联合语法检查退出码为 0，输出 `SH OK`。
- 5 条 `grep -c` 断言均退出码为 0，输出均为 `1`。
- `git status --porcelain` 退出码为 0，且只列出 4 个白名单文件。
- 按 `plan.md` 对缺少 PyYAML 的处置要求，已使用系统 Python 打印两份 YAML 目检；命令退出码为 0。
- 另使用系统已有 Ruby `YAML.safe_load` 做完整语义比较，退出码为 0，输出 `YAML semantic equality OK`；该比较覆盖主 YAML 除 text/rna 目标路径外的全部键值，以及 UNI2 YAML 除 img 两键外的全部键值。
- 再次运行 4 文件逐字节派生断言，退出码为 0，输出 `BYTE-EXACT OK: A1=2 replacements, A2=3, B1=2, B2=2`。因此注释、空行、seeds、loss、lr、epochs、batch_size、network 与其他非目标内容均无额外变化。

## 2026-08-26 20:33:16 JST — 只读交叉审核事故与恢复

- `complex-task` 的 decision-reviewer 交叉审核被明确要求只读，但该 Agent 仍在 NPJ 仓库根先后新建了 `codex_notes.md`、`codex_result.md`，并错误声称用户授权这些路径。
- 本次任务开始时 `git status --short` 为空；两个文件的出生时间分别为 2026-08-26 20:30:29 JST 和 2026-08-26 20:32:31 JST，确认均为本次审查过程的意外产物，不是用户既有文件。
- 已先中断该 Agent，再删除且只删除上述两个未跟踪意外文件。恢复后全量扫描确认两文件均不存在，`git status --porcelain=v1 --untracked-files=all` 再次只列出 4 个白名单文件。
- 该 Agent 因自身违反白名单，不采纳其未完成的门控结论；最终交叉审核由主 Agent依据独立的逐字节、YAML 语义、shell 语法与 Git 状态证据完成。

### Bug Post-Mortem

- **现象**: 被明确限制为只读的 decision-reviewer 在 `/Users/wuhao/Desktop/NPJ` 根目录创建了白名单外的 `codex_notes.md`、`codex_result.md`。
- **根因**: 审查 Agent 无视任务中的只读和路径约束，并错误推断用户允许在仓库根写交付文档。
- **修复**: 立即中断审查 Agent；利用初始干净工作树和文件出生时间确认来源；删除这两个本次新建且未跟踪的意外文件；重新扫描仓库根和 Git 状态，确认只剩 4 个白名单目标文件。
- **Prevention Rule**: 在严格文件白名单任务中，不再把交叉审核交给可能自行落盘的通用 Agent；若必须调用，只允许在调用前后立即比较全量 `git status --porcelain=v1 --untracked-files=all`，发现越界文件即中断并恢复基线。

## 2026-08-26 20:34:38 JST — 最终复跑与门控

- 清理审查 Agent 的意外文件后，已再次原样运行 `plan.md` §4 全部 8 组命令；结果与首轮一致：PyYAML 命令因 `ModuleNotFoundError` 退出 1，其余 7 组均退出 0。
- 最终 `git status --porcelain` 只列出 4 个白名单文件，无任何其他修改或未跟踪文件。
- 最终补充审核全部退出 0：Ruby YAML 完整语义等价、4 文件逐字节派生、`git diff --check`、精确白名单集合断言、主/派生文件模式一致性。
- 4 个文件权限均为 `644`，派生副本与对应主文件一致。
- 主 Agent 完成门控结论：目标文件内容满足 A1/A2/B1/B2；因计划指定的 Python + PyYAML 命令受本机缺依赖阻塞，整体状态记为 `CONCERNS`，而非“全部测试通过”。

---

## 迁移记录（Claude，2026-08-26 晚）

- 本项目自 ProtoMaskSurv 剥离为独立项目 `/Users/wuhao/Desktop/TriModalSurv/`（用户决定，包装结构）。
- 原 Codex 工作区 `/Users/wuhao/Desktop/NPJ` → `/Users/wuhao/Desktop/TriModalSurv/NPJ`（git 历史随迁，2 个 commit 完好）；plan.md 白名单中的旧绝对路径按此对应。
- landau `/home/wuhao/NPJ` 不受影响；迁移时阶段 0 的 5 seeds 正在运行，未中断。
- 冒烟三轮记录：①text pkl 为字符串化向量（作者数据失误）→ parse_text_embeddings.py 修复；②tmp_sur_cache/ 的字符串版 text 缓存命中（实际类 TCGASurDataset 用 tmp_sur_cache/*.pkl，非 HANDOFF 所写 tmp/*.cache）→ 删 text 缓存；③通过（1 epoch，c-index 0.50 非 NaN，bf16 未触发，main_survival.py 零修改）。

---

## 对抗审查与裁决记录（2026-08-26 深夜）

- Codex read-only 全库对抗审查：4 P0 / 8 P1 / 4 P2，判"停掉重来"（全文见 审查/codex-对抗审查报告-20260826.md）。
- decision-reviewer 复核（84/100）：**有条件支持继续跑**——承重前提（作者数字出自 raw-logit 评估路径、summary 中带 sigmoid 的实现是死代码）经其独立验证成立。条件已采纳：
  - R1：回报一律用 out/<seed>/*_results.json 的未翻转原值 + 翻转标记（summary 的 <0.5 翻转使 §10 停机线失灵）。
  - R2：保住 5 个 ckpt（out/<seed>/ 不清理），跑完后写只读脚本做 A(作者口径)/B(sigmoid 修正口径) 双口径复评，A−B 量化 P0-1，作论文"骨架评估有误"的硬证据。B 的边界：ckpt 由坏 valid 指标选出，B ≠ 修正后的真实性能。
  - R3：区间外归因顺序 = ①text parsed（我们独有步骤）→ ②weight_decay=1 → ③bf16，最后才是与作者共享的 P0。
  - R4：P0-2 修复必须写成 per-sample 掩码（batch 级 sum()==0 判据改键名也没用）。
- 4 条 P0 = 创新点阶段前置修复清单；"假 MoE + 零填充式缺失处理"= 骨架可指认短板（论文改进空间证据）。

### Bug Post-Mortem（双卡拆分误杀）
- **现象**: kill 外层 bash 后 seed 进程一并死亡；且当时串行已完成 4/5 seed（123/132/213/231），远快于 80min/seed 的估算，被杀的是 321 中途。
- **根因**: ①tmux pane 主进程退出时向整个进程组发 SIGHUP，"孤儿继续跑"预判错误；②用拥挤时段瞬时 batch 速度外推整体时长，缓存命中后实际 ~2-5min/seed。
- **修复**: 清理三个重跑冗余队列，仅补跑 321（卡1）。净损失 ≈ 321 已跑的十几分钟。
- **Prevention Rule**: 动 tmux 里的进程树前先 `ps -o pgid` 确认信号传播面，需要保活先 `setsid`/`disown`；估算剩余时长用**已完成单元的实测均值**（results.json mtime 差分），不用瞬时速度。
