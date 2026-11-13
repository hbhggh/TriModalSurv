# 任务 A 结果：scripts/gitflow.sh 单主干改写

执行者：coder-core（Claude Opus 5.5），2026-11-12。过程记录见同目录 `notes-gitflow.md`。未 commit、未 add。

## 改动点

- `scripts/gitflow.sh`：整体改写（旧 222 行，新 660 行）。删除 init、squash、DEV_BRANCH；新增代码范围干净门、`freeze --no-worktree` / `--link-assets`、`wt-add` / `wt-rm`、单主干 `status`；cleanup 与 wt-rm 共用「先查全部剩余项、再摘链接、再 worktree remove」的收尾函数。cleanup 原有身份核对块与报错原文保留。
- `scripts/codex_review.sh`：只改第 6 行注释，「如 dev 候选用 --base main」改为「如审查 main 上某个提交之后的改动用 --base <commit>」。
- 未改 `tests/test_workflow_scripts.py`。

## 规格 1–10 对应位置（scripts/gitflow.sh 行号，最后一次修改后用 grep 重取）

| 规格 | 实现位置 |
| --- | --- |
| 1 删 init、squash、DEV_BRANCH；帮助改写 | 帮助文本 2–35；子命令白名单与「未知子命令」51–56（先于仓库探测）；分派 653–660 |
| 2 CODE_PATHS、WT_BRANCH_PREFIX 默认值 | 41–42；拆成数组 69–70 |
| 3 代码范围干净门 | `code_dirty` 111–113（`core.quotePath=false`、`--untracked-files=all`、只给 CODE_PATHS）；`require_code_clean` 115–125（报错并列出路径） |
| 4 candidate | `cmd_candidate` 417–434：`run_ci` 419，代码门 420，`H = <短哈希>` 428，其后打印分支、最近提交、代码范围外改动数 |
| 5 freeze | `cmd_freeze` 474–541。参数解析 479（`parse_link_args` 436–455，未知选项报错带原文，`--no-worktree` 与 `--link-assets` 互斥 453）；主目录与分支 481–482；解析唯一 sha 484；校验链接 487；代码门 489；tag、目录、分支已存在与引用名合法 491–499；副作用从 501 起（mkdir 501、tag 502）；`--no-worktree` 分支 503–509（stamp 在主目录生成，`write_stamp` 457–472）；默认建 worktree 510–516；创建后不干净断言 517–520；建链 522 与「扣除登记链接后仍须干净」自检 524–528；stamp 532 |
| 6 wt-add | `cmd_wt_add` 576–609：名字规则 `valid_name` 76–82 与 579；引用名 582；目录或分支已存在 584–585；链接校验 586；副作用从 588 起；建链与自检 595–600 |
| 7 --link-assets 校验、建链、登记 | `relpath_ok` 85–107（空串、绝对路径、尾斜杠、空分量、`.`、`..`、`.git`、控制字符、引号、反斜杠）；`validate_link_paths` 186–225（至少一个路径 188，主目录存在 194，非 ASCII 路径的 git 写法一致 197–205，逐级对照提交 206 → `check_against_commit` 144–170：只差大小写拒绝 157–159，提交里已存在 162–164，上级为非目录条目 165–166；同次调用重复与互为祖先、按大小写不敏感比较 210–224，`prefix_case_conflict` 172–184）；`make_links` 233–247（`mkdir -p` 父目录 242，`ln -s <主目录物理路径>/<relpath>` 243，建成后逐行登记 244，登记文件位于 `rev-parse --absolute-git-dir` 下，`link_registry` 227–231）；主目录物理路径 62–65 |
| 8 cleanup、wt-rm 收尾顺序 | cleanup 身份核对在 `cmd_cleanup` 543–574 内原样保留（tag、HEAD 相等、检出形态、冻结提交在 MAIN 上 562），另加 `require_own_worktree` 554（函数 370–379）；wt-rm 身份核对在 `cmd_wt_rm` 611–630：检出 ref 619–622，已合入 MAIN 623–624；合法链接 `legit_link` 249–260（readlink 值与「主目录物理路径/relpath」逐字相等 253，且各级上级不是链接）；剩余项 `collect_leftovers` 276–335（status 与 ls-files 两份清单只扣合法链接，忽略文件再按 `regenerable` 262–271 放行）；`finish_removal` 383–413：有剩余项即拒绝且不动任何东西 386–394，之后才逐个摘链接（摘前再判 397–400，`rm --` 401，失败补回 402–403），`git worktree remove` 不加 --force 407，失败补回 408–409，prune 411；`git branch -d` 567、626 |
| 9 status | `cmd_status` 632–651：当前分支、worktree 列表、最近 10 个 run tag 638、run 分支、wt 分支、代码范围是否干净 646（不干净也退出 0） |
| 10 红线 | 帮助与未知子命令先于仓库探测 51–56；变量后紧跟中文一律 `${var}`（静态扫描测试通过）；空数组一律 `${arr[@]+"${arr[@]}"}`；无 mapfile、关联数组、`${var,,}`，`$(...)` 里没有 case；--force、-D、-r 只以否定说明出现在注释和提示里，没有实际调用 |

## 测试

命令（仓库根，解释器为 protomasksurv-exp1 环境）：

```
PYTHONDONTWRITEBYTECODE=1 <protomasksurv-exp1 环境>/bin/python -m pytest tests/test_workflow_scripts.py -q -p no:cacheprovider
bash -n scripts/gitflow.sh
```

- 旧脚本基线：23 failed, 33 passed（与 plan 一致）。
- 新脚本（最后一次修改之后）连跑 3 遍，每遍 56 passed，0 failed；`bash -n` 退出 0。最后一遍原始输出尾部：

```
=== run 3 ===
........................................................                 [100%]
56 passed in 15.86s
bash -n exit=0
```

- 套件之外的沙箱手测（scratchpad 里 mktemp 建仓库）：第一组 42 项、第二组 23 项，最后一次修改之后全部重跑通过。明细见 notes「沙箱手测」与「第二轮修改」两节。

## 核心逻辑自查

| 不变量 | 守住它的测试 |
| --- | --- |
| I1 拒绝发生在任何 tag、分支、目录创建之前 | test_freeze_unknown_option_is_refused_without_tagging、test_freeze_refuses_modified_source_without_tagging、test_freeze_refuses_untracked_file_under_experiments_without_tagging、test_code_paths_can_be_overridden、test_invalid_link_paths_are_refused_before_anything_is_created、test_wt_add_refuses_bad_or_duplicate_names、test_retired_dev_subcommands_are_unknown；手测 C（非规范路径）、L（大小写只差 7 种）、N（NFD 输入） |
| I2 代码门只看 CODE_PATHS，逐个列出未跟踪文件 | GitflowCodeGateTests 全部 11 条 |
| I3 合法链接的定义（登记、仍是链接、readlink 逐字相等、上级不是链接） | test_retargeted_link_is_refused、test_link_replaced_by_a_real_directory_is_refused、test_unregistered_symlink_is_refused；手测 H、I、J |
| I4 有任何拒绝就不动链接、文件、分支 | test_real_checkpoint_next_to_a_link_is_refused_and_links_are_kept，GitflowCleanupTests 中全部拒绝用例；手测 E（worktree 被 lock 时链接补回） |
| I5 只扣除合法链接本身，逐字相等 | test_freeze_links_assets_and_cleanup_only_removes_the_links、test_wt_add_links_assets_and_wt_rm_only_removes_the_links；手测 A（status 里带引号的行）、B（链接出现在被忽略清单） |
| I6 摘链接不触碰目标 | test_file_written_through_a_link_lands_in_main_and_survives，以及每条链接测试里的 assert_assets_intact；手测 A、B、E、F、N 的主目录快照比对 |
| I7 git 失败不等于干净 | 手测 M（git 垫片：cleanup 与 wt-rm 中 status、ls-files 各自失败；freeze 代码门 status 失败；链接校验 ls-tree 失败；candidate 代码门 status 失败），手测 D（登记文件不可读）、D2（worktree 的 .git 指针损坏，由身份核对拦下） |
| I8 relpath 只收规范形式，同次不重复、不互为祖先 | test_invalid_link_paths_are_refused_before_anything_is_created；手测 C（`logs/`、`./logs`、`logs//a`、`.git`，以及 `logs` 与 `logs2` 不误判）、L（大小写不敏感的重复与祖先） |
| I9 relpath 不在提交里、祖先不是非目录条目，校验与 tag 用同一 sha | test_invalid_link_paths_are_refused_before_anything_is_created（src、src/model.py）；补测祖先为文件与符号链接；手测 L（`SRC/m.py`） |
| I10 cleanup 原有身份核对不减 | GitflowCleanupTests 16 条（未改、全部通过） |
| I11 wt-rm 身份核对 | test_wt_rm_refuses_other_branch_checked_out、test_wt_cycle_add_commit_fast_forward_remove、test_wt_rm_refuses_uncommitted_change |
| I12 帮助、未知子命令、多字节、bash 3.2 | GitflowHelpTests 5 条、GitflowMultibyteTests 2 条、test_wt_cycle_add_commit_fast_forward_remove（UTF-8 locale）；手测全部在 UTF-8 locale、`/bin/bash` 3.2 下运行 |
| I13 反复运行无残留 | 套件连跑 3 遍；手测 F（同一沙箱 freeze/cleanup 与同名 wt-add/wt-rm 各 3 轮，主目录资产不变，tag 全保留） |

## 偏离或补充 spec 之处（请主控裁定）

1. 登记过、但路径已整个不存在（用户手动删了链接）：按 spec「登记过但已不是合法链接一律拒绝」处理为拒绝。报错里给出按登记补回的 `ln -s` 命令，补回后即可收尾（手测 H' 守住）。
2. 摘完链接后 `git worktree remove` 仍被 git 拒绝（如 worktree 被 lock），或 `rm --` 自身失败：按登记把已摘的链接原样补回再报错，现场与收尾前一致、可直接重试。spec 未写，属补充（手测 E 守住）。
3. freeze 的 run_id 也套用 wt-add 的名字规则，并对 tag 名、分支名再跑一次 `git check-ref-format`，都在副作用前。spec 只对 wt-add 写了正则；这样能挡住 `a/b`、`../x` 这类会落成嵌套目录的 run_id。
4. relpath 额外拒绝以下形式：尾斜杠、空分量、`.` 分量、`.git` 分量、控制字符、双引号、反斜杠（spec 只点了绝对路径、空串、`..`）。理由：这些形式要么让字符串查重失效（`logs/` 与 `logs`），要么被 git 转义后收尾永远对不上。
5. 大小写与 Unicode 写法（spec 未写，补充）：macOS 默认文件系统不分大小写、不分 Unicode 规范形式，git 显示的是提交里的拼写和预组合（NFC）形式。这两种写法上的差异都会让「打了 tag 才报异常、之后收尾永远拒绝」，沙箱里都已复现。现在都在副作用前拒绝，并提示正确写法：
   - 与提交里同级名字只差大小写的路径；
   - 同次调用里按大小写不敏感比较重复或互为祖先的路径；
   - 含非 ASCII 字符、且写法与 git 回显不一致的路径（多为 NFD）。

   对 Linux 等大小写敏感的文件系统，「只差大小写」这条略偏严。
6. cleanup 与 wt-rm 都加了 `require_own_worktree`：目录须是本仓库某个 worktree 的顶层，且不是主目录。
7. freeze 与 wt-add 建完链接后，立即用收尾的同一套判定自检一遍；认不出链接就当场报异常，而不是等到收尾才发现。
8. 主目录要求 git 目录名为 `.git`（标准布局），否则报错退出。旧脚本对此是隐含假设。
9. candidate 不要求当前分支是 main（spec 只说不再要求 dev），可以在 wt-* worktree 里跑；status 显示的代码门是当前 worktree 的。

## 对测试与 spec 的疑问

- 没有发现与 spec 矛盾的测试；56 条全部按 spec 语义通过，没有为迁就测试做语义上的让步。
- **疑问（需主控裁定）**：链接落在 CODE_PATHS 之内时，它在该 worktree 里显示为 `??`。测试夹具的 `experiments/I01/results/r0/checkpoints` 就属于这种情况。这样在那个 worktree 里跑 candidate 会被代码门拒绝，status 也会显示不干净。规格 3 写的是「输出为空才算干净」，我没有自行给代码门加「扣除登记链接」。是否要在 wt-* worktree 里用 candidate，请主控决定。
- 测试套件不覆盖以下场景：git 调用失败、含空格或非 ASCII 的 relpath、大小写只差、链接名命中无尾斜杠的忽略规则、收尾中途被 git 拒绝。这些目前靠手测守住，建议主控考虑补成回归测试（测试文件不在本任务白名单）。手测脚本在本次会话的 scratchpad，里面含本机路径，不入库。
- plan 点名的坑 E52 在坑台账里查不到这个 ID（E 系列到 E41 为止）；我按 plan 原文要求照做了。
- 待入账候选（台账不在本任务白名单），一句话坑见 notes 末节：
  - `git status --porcelain` 给含空格的路径加双引号，`git ls-files` 不加；
  - macOS 上大小写、NFD 写法差异会让按字符串比对的路径门禁永远对不上。
- 工作树里 `scripts/README.md` 有改动，不是本任务所为（属任务 B 白名单）。
