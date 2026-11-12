# 任务 A 过程记录：scripts/gitflow.sh 单主干改写

执行者：coder-core（Claude Opus 5.5）。spec：同目录 plan.md「共同禁止事项」与「任务 A」。

## 2026-11-12 20:20 JST 开工

- 读完 plan.md、旧 gitflow.sh（222 行）、tests/test_workflow_scripts.py（701 行），完整读坑台账 docs/engineering/pitfalls.md。
- 台账核对：G1（身份与冻结锚点逐值相等）、G2（先解析参数再探测环境）、G3（变量后紧跟中文写 `${var}`）、G5（删除前逐个枚举被忽略文件）、E37（不在 `$(...)` 里写 case）、V28（git 路径加 `-c core.quotePath=false`）、I05-04（自写内容不写本机绝对路径）。
- plan 点名的 E52（表格单元格内不写竖线）在台账里查不到这个 ID（台账 E 系列到 E41 为止）。按 plan 原文要求照做，不另行入账；在 result 里提一句。
- 基线：旧脚本上 `pytest tests/test_workflow_scripts.py` 为 23 failed, 33 passed，与 plan 一致。
- 环境实测：本机 `/bin/bash` 3.2.57，git 2.39.5。实测 `git status --porcelain` 会给含空格的路径加双引号（`?? "a b"`），`git ls-files --others` 不加；含 `"`、`\`、换行的路径两者都做 C 转义。这决定了「扣除合法链接」的比较方式（见下）。

约束清单：`[ T = 让 gitflow.sh 符合单主干规格 1–10 + Q_draft（tests/test_workflow_scripts.py 全绿且连跑 3 遍，bash -n 通过）+ ∩P（白名单只有 gitflow.sh 与 codex_review.sh 第 6 行注释；bash 3.2；拒绝路径保留现场）∥ S_state（旧脚本 23 红 33 绿）]`

## 核心逻辑的不变量与边界（实现前写定）

| 编号 | 不变量 | 守住它的测试或手测 |
| --- | --- | --- |
| I1 | freeze / wt-add 的任何拒绝（参数、链接路径、代码门、名字、已存在）都发生在 tag、分支、目录、WT_ROOT 创建之前 | test_freeze_unknown_option_is_refused_without_tagging、test_freeze_refuses_*_without_tagging、test_code_paths_can_be_overridden、test_invalid_link_paths_are_refused_before_anything_is_created、test_wt_add_refuses_bad_or_duplicate_names |
| I2 | 代码门只看 CODE_PATHS，未跟踪文件逐个列出（--untracked-files=all），范围外改动不阻塞 | GitflowCodeGateTests 全部 |
| I3 | 合法链接 = 登记过 + 仍是符号链接 + readlink 值与「主目录物理路径/relpath」逐字符相等 + 路径各级祖先都不是符号链接 | test_retargeted_link_is_refused、test_link_replaced_by_a_real_directory_is_refused、test_unregistered_symlink_is_refused；手测：经祖先链接的登记路径 |
| I4 | 收尾时先做完全部身份与剩余项检查；有任何拒绝就不动链接、文件、分支 | test_real_checkpoint_next_to_a_link_is_refused_and_links_are_kept、GitflowCleanupTests 全部拒绝用例 |
| I5 | 只扣除合法链接本身：status 里只扣整行等于 `?? rel` 或 `?? "rel"` 的行，忽略清单里只扣整行等于 rel 的行，字符串逐字相等，不做 glob 或正则 | test_freeze_links_assets_and_cleanup_only_removes_the_links；手测：链接名命中无尾斜杠的忽略规则、含空格加中文的 relpath |
| I6 | 摘链接用 `rm -- 路径`，路径不带尾斜杠，执行前再判 `-L` 与 readlink；目标目录内容不变 | test_file_written_through_a_link_lands_in_main_and_survives、assert_assets_intact 在每条链接测试里 |
| I7 | git 命令失败绝不等于「干净」：取清单时先把 git 输出赋给变量、赋值失败即 die，过滤在 bash 循环里逐字比较 | 手测：让登记目录不可读或 git 调用失败 |
| I8 | relpath 只收规范形式：非空、不以 `/` 开头或结尾、无空分量、无 `.` 或 `..` 或 `.git` 分量、无控制字符、无 `"` 与 `\`；同次调用不重复、不互为祖先（按 `"$a/"` 前缀判） | test_invalid_link_paths_are_refused_before_anything_is_created；手测 `logs/`、`./logs` |
| I9 | relpath 在待检出提交里不存在，且任何祖先在该提交里不是非目录条目；校验与 tag、worktree add 用同一个 sha | test_invalid_link_paths_are_refused_before_anything_is_created（src、src/model.py） |
| I10 | cleanup 原有身份核对（tag 存在、HEAD 等于 tag、检出形态、冻结提交在 MAIN 上）一字不减 | GitflowCleanupTests 16 条 |
| I11 | wt-rm 身份：目录是本仓库的 worktree 且顶层就是它、检出 `refs/heads/<WT_BRANCH_PREFIX><name>`、该分支是 MAIN 的祖先 | test_wt_rm_refuses_other_branch_checked_out、test_wt_cycle_add_commit_fast_forward_remove |
| I12 | 帮助与未知子命令先于仓库探测处理；变量后紧跟中文一律 `${var}`；bash 3.2 兼容 | GitflowHelpTests、GitflowMultibyteTests |
| I13 | 多次运行：同一沙箱里 freeze → cleanup → 再 freeze 新 run_id、wt-add → wt-rm → 再 wt-add 同名都能走通，无残留状态 | 测试套件连跑 3 遍；手测重复闭环 |

边界情况：空参数（`--link-assets` 后无路径）、空串路径、重复路径、互为祖先、`logs` 与 `logs2`（不是祖先）、路径带尾斜杠、名字以 `-` 或 `.` 开头、目录或分支已存在、未登记链接、登记了但被删除的链接、worktree 被 lock 导致 `git worktree remove` 失败（链接已摘）。

## 设计取舍（偏离或补充 spec 之处）

- 登记过、但路径已不存在（用户手动删了链接）：按 spec「登记过但已不是合法链接一律拒绝」处理为拒绝，报错提示如何处理。
- `git worktree remove` 在摘完链接后仍失败（例如 worktree 被 lock）：按登记把已摘的链接原样补回再报错退出，使现场与收尾前一致、可以重试。spec 未写，属补充。
- freeze 的 run_id 与 wt-add 的 name 都用 `git check-ref-format` 再核一遍（如 `a..b`、`x.lock` 这类正则放行但 git 不认的名字），在副作用前拒绝；freeze 的 run_id 也套用与 wt-add 相同的字符集，防止 `a/b`、`../x` 落成嵌套目录。spec 只对 wt-add 写了正则，对 run_id 属补充。
- 收尾删除阶段在主目录执行（`git -C <主目录>`），防止人站在被删的 worktree 里运行；也让 `git branch -d` 以 MAIN 检出判断是否已合入。

## 2026-11-12 20:22 JST 动手前咨询审阅者

采纳的要点：git 失败不能当成干净（赋值失败即 die，不用 `|| true` 管道过滤）；扣除只做逐字相等，status 同时接受 `?? rel` 与 `?? "rel"`，忽略清单也要扣（链接名命中无尾斜杠规则时出现在 ls-files 里）；relpath 只收规范形式；拒绝信息攒齐后一次报出（否则 test_link_replaced_by_a_real_directory_is_refused 看不到 `logs/train.log`）；摘完链接后 worktree remove 仍失败时补回链接；校验、tag、worktree add 用同一个 sha；删除阶段在主目录执行。

## 2026-11-12 20:25 JST 改写 scripts/gitflow.sh

- 整体重写（保留 cleanup 原有身份核对块与报错原文，旧 16 条测试钉着这些文案）。
- 删除 init、squash、DEV_BRANCH；子命令名在仓库探测前先过白名单，未知名字（含 init、squash）走「未知子命令」分支。
- 新增 CODE_PATHS、WT_BRANCH_PREFIX；代码门 `code_dirty` / `require_code_clean`。
- 新增 `validate_link_paths`、`make_links`、`legit_link`、`collect_leftovers`、`finish_removal`、`relink`、`require_own_worktree`；cleanup 与 wt-rm 共用 `finish_removal`，freeze 与 wt-add 共用链接校验与建链。
- freeze 与 wt-add 建完链接后立即跑一遍 `collect_leftovers` 自检：扣除登记链接后必须干净，等于在建链时就证明收尾认得出这些链接（例如路径被 git 加引号的情形），而不是等到收尾才发现。
- `scripts/codex_review.sh` 第 6 行注释改为单主干说法，其余未动。
- 首轮测试即 56 passed。

## 2026-11-12 20:27 JST 沙箱手测（scratchpad，mktemp 建仓库，未用递归删除）

42 项全部通过，覆盖：含空格加中文的 relpath 完整闭环（status 里显示为带引号的 `?? "数据 资产/feat cache"`，被正确扣除）；链接名命中无尾斜杠忽略规则（`checkpoints`、`*.pth`，出现在 ls-files 被忽略清单里，被正确扣除）；`logs/`、`./logs`、`logs//a`、`.git`、`..` 分量、`--no-worktree` 与 `--link-assets` 同用均在副作用前拒绝；`logs` 与 `logs2` 不误判为祖先；登记文件不可读、worktree 的 .git 指针损坏时拒绝且链接保留；worktree 被 lock 时摘链后 remove 失败、链接按登记补回、解锁后重试成功；同一沙箱 freeze/cleanup 与同名 wt-add/wt-rm 各连跑 3 轮无残留、主目录资产逐字节不变；站在被删的 worktree（及其子目录）里运行收尾成功；在非主目录 freeze 被拒；登记链接被用户删掉时拒绝；上级目录被换成链接时拒绝且不去摘外部链接；经符号链接路径进入主目录时链接值仍是物理路径；status 在代码范围不干净时仍退出 0。
另补测：上级在提交里是文件或符号链接（blob）、主目录里已变成目录时拒绝，未打 tag、未建目录。

## 2026-11-12 20:29 JST 收尾验证

- 测试套件连跑 3 遍：56 passed / 56 passed / 56 passed；`bash -n scripts/gitflow.sh` 退出 0。
- grep 结果：`--force`、`-D`、`-r` 只以「不加 --force」「不 -D」「不加 -r」这类否定说明出现在注释与提示里（旧脚本同样如此），没有实际调用；无 mapfile、关联数组、`${var,,}`。
- 发现：工作树里 `scripts/README.md` 有改动，不是本任务所为（属任务 B 白名单），未触碰。

### 待主控决定的入账候选（台账不在本任务白名单）

- `git status --porcelain` 对含空格的路径加双引号，`git ls-files` 不加；按行比对路径的门禁若只认一种形式，含空格的路径会永远对不上（本任务已同时接受两种形式并用手测钉住）。建议 Prevention Rule：按行比对 git 路径输出时，逐命令实测引号规则，或改用 `-z`。

## 2026-11-12 20:41 JST 完成前审阅后的第二轮修改

审阅者指出的问题与处理：

1. result 行号有几处差一行：最后一步用 grep 与按函数区间统一重取（见 result）。
2. I7「git 失败不等于干净」原先只有 D2 用例，而 D2 被身份核对拦下，没走到 collect_leftovers 里 status / ls-files 失败的分支。新增 git 垫片（PATH 前置，按环境变量让指定子命令返回 1、其余转给真 git），补测：cleanup 与 wt-rm 中 status、ls-files 各自失败 → 拒绝，链接、目录、分支都在；freeze 代码门 status 失败、链接校验 ls-tree 失败、candidate 代码门 status 失败 → 拒绝且无 tag。
3. 大小写拼错（提交里是 experiments，输入 Experiments/...）在沙箱里复现：旧实现打了 tag、建了 worktree 后才报「异常」，之后 cleanup 永远拒绝，违反 I1。修复：新增 `check_against_commit`，逐级列出提交里的树，同一级里只差大小写的名字一律在副作用前拒绝；同次调用里的路径按大小写不敏感比较查重、查祖先，并新增 `prefix_case_conflict` 拒绝「上级只差大小写」的两条路径（如 AA/x 与 aa/y）。
4. 同类问题还有 Unicode 分解形式：输入 NFD（macOS Finder 建的含浊点假名等常见）时，git（core.precomposeunicode=true）在 status 里显示 NFC，收尾永远对不上；沙箱复现同样是打了 tag 之后才报异常。本机 iconv 不支持 UTF-8-MAC，无法本地规范化；改用 git 自身的视角：对含非 ASCII 字符的路径跑 `git check-ignore --no-index -n -v`，它回显的是 git 预组合之后的路径，与输入不一致即在副作用前拒绝，并提示改用 git 显示的写法。只对非 ASCII 路径做这项检查，因为 check-ignore 对「穿过主目录里符号链接」的路径会返回 128；纯 ASCII 路径不受影响（手测 ext/sub 守住）。
5. `rm --` 自身失败时原先靠 set -e 直接退出、已摘链接停在半途：补上与另外两处相同的「补回已摘链接再报错」分支。
6. 登记链接已被删时，报错里给出按登记补回的 `ln -s` 命令（只对「路径已不存在」的条目给，已被换成真实目录的不给，避免把链接建进目录里）。手测：按提示补回后 wt-rm 成功。
7. 偏离 8 的限制：链接落在 CODE_PATHS 之内时（测试夹具的 experiments/.../checkpoints 就是），它在该 worktree 里显示为 `??`，在那个 worktree 里跑 candidate 会被代码门拒绝、status 也显示不干净。规格 3 写的是输出为空才算干净，没有给代码门加扣除，作为疑问报给主控。

第二轮验证：测试套件连跑 3 遍各 56 passed；`bash -n` 退出 0；第一组手测 42 项、第二组手测 23 项全部通过。
