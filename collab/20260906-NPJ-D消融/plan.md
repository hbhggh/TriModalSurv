# 派单契约：NPJ-D（MainModalityMoE 去 GatedFusion → 等权均值融合）实现 + 发车器/评测器透传

派发：2026-09-06。执行者：Opus 子 agent（本单你就是执行者；`CLAUDE.md` 中"派给 Codex/Companion"条款对本单不适用；禁止转派、禁止调用其他引擎/SSH/联网；**不得中途向指挥官提问**，契约未覆盖处按最保守默认执行并写进 `notes.md`「歧义与自行裁决」节）。

## 目标
在不改变任何现有路径数值的前提下，为 `MainModalityMoE` 增加 `fusion_type="mean"`（NPJ-D = NPJ-A 去掉 GatedFusion，其余全同：无跨 token attention、无模态嵌入、无缺失位处理——缺失=零特征过 projector 的常量 token，照常等权参与平均），并把该开关透传到训练入口、评测入口与发车器预设。**不训练、不 SSH、不 commit。**

## 白名单（只能改这 4 个文件 + 新增 1 个测试文件 + 本目录 notes.md）
- `NPJ/model/fusion_model.py`：只允许 (a) 新增 `class MeanFusion(nn.Module)`；(b) `MainModalityMoE.__init__` 增加**关键字参数** `fusion_type: str = "gate"`（必须放在参数表最后、带默认值，不得改动现有位置参数顺序），`gate` 时 `self.fusion = GatedFusion(...)`（原样），`mean` 时 `self.fusion = MeanFusion()`，其他值 `ValueError`。`forward` 一行不改。**NPJC、GatedFusion、SurvivalHead、其余类一律不动。**
- `NPJ/main_survival.py`：(a) `parsing_args` 增 `--fusion_type`，`choices=['gate','mean']`，默认 `'gate'`；(b) `load_model(...)` 增关键字参数 `fusion_type='gate'`，只在 `network_type == 'MainModalityMoE'` 分支以关键字传给 `MainModalityMoE(..., fusion_type=fusion_type)`；若 `fusion_type != 'gate'` 且 `network_type != 'MainModalityMoE'` → `ValueError`；(c) `main()` 里对 `load_model` 的调用加 `fusion_type=args.fusion_type`。其他不动（不改 ckpt 命名、不改 ModelDumper、不改训练循环）。
- `NPJ/scripts/eval_missing.py`：`parse_args` 增 `--fusion_type`（同上）；`main_survival.load_model(...)` 调用加 `fusion_type=getattr(args, "fusion_type", "gate")`。其他不动（`--m1-mark-valid` 保持现状）。
- `NPJ/scripts/train_launcher.py`：(a) `ARM_PRESETS` 增 `"d0": {"network_type": "MainModalityMoE", "compensator": "none", "extra_args": ("--fusion_type", "mean")}`；(b) 保证完成即评测（`_run_eval`）为该臂生成的 `eval_missing.py` 命令带 `--fusion_type mean`（实现方式自定：可给预设加 `eval_extra_args` 键或从 `extra_args` 中提取 `--fusion_type`；其他臂的评测命令逐字不变）；(c) 把评测命令的组装抽成可测试的纯函数（例如 `build_eval_command(spec, ...)`，若已存在则复用），使验收③能在不 SSH 的情况下断言。`checkpoint_path()` 不动（d0 的 ckpt 名靠 `--cpt-name tcga_uni2_d0 --result-path out_d0` 隔离，不需要改名逻辑）。
- 新增 `NPJ/tests/test_mean_fusion.py`（CPU、无数据、<10 s）。
- 过程记录：`collab/20260906-NPJ-D消融/notes.md`（追加式，每步带 `date '+%Y-%m-%d %H:%M:%S %Z'` 实取时刻；结尾 `TASK_DONE`）。

**禁止**：改动 `NPJ/loc_utils_3yr/*`、`NPJ/model/compensator.py`、`NPJ/model/config/*`、`NPJ/config/*`、任何 `collab/` 结果或报告；训练、SSH、pip、联网、git 写操作（含 `git -C NPJ add`）；`py_compile`（会落 `.pyc`，用内存 `compile()`）；在源码旁生成 `__pycache__`（`export PYTHONDONTWRITEBYTECODE=1`）。

## MeanFusion 精确语义
- 接口与 `GatedFusion.forward(reps)` 相同：输入长度 M 的列表（元素 `[B, D]` 或 `None`），输出 `[B, D]`。
- 对非 `None` 的元素做**等权算术平均**（`torch.stack(...).mean(dim=1)`）；`None` 元素跳过（与 GatedFusion 用 −1e9 屏蔽 None 的效果一致）；只有一个非 `None` 时直接返回它。无可学习参数。
- 注意：生存数据集从不产出 `{mm}_mask`，`MainModalityMoE.forward` 里 `input_data[mm]` 恒非 `None`（`fusion_model.py:1011-1015` 死代码），因此缺失模态的常量 bias token **必然参与平均**——这正是 NPJ-D 定义（A 去 gate、其余全同）。不要"修复"这一点。

## 验收（交付前逐条实跑，命令与原样 stdout 贴进 notes；任一 FAIL 不得宣布完成）
`cd /Users/wuhao/Desktop/TriModalSurv/NPJ && export PYTHONDONTWRITEBYTECODE=1`；解释器一律 `python3`（本机 `/usr/bin/python3` 3.9 + torch 可用则用之；若本机无 torch，先 `python3 -c "import torch"` 确认；无则只做 ③④ 并在 notes 写明 ①② 留给指挥官在 landau 做）。
1. **gate 路径逐位不变（本地）**：补丁前先把原 `model/fusion_model.py` 复制到 scratchpad（`/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/fusion_model_before.py`）；测试里分别从原文件与补丁后文件构造 `MainModalityMoE`（伪 modalities：`img/text/rna` feature_dim 1536/768/256，hidden 256，pred_dim 4，cancer_types ['BLCA']），`torch.manual_seed(0)` 后 `state_dict` 键集合相同、逐张量 `torch.equal`；同一随机输入（`img [2,128,1536]`、`text [2,200,768]`、`rna [2,2048,256]`，含 `text_valid/rna_valid`）在 `eval()` 下前向输出 `torch.equal`。
2. **mean 路径单测**：(a) `fusion_type='mean'` 的模型 `state_dict` 键 = gate 模型键去掉 `fusion.gate.*`；(b) 手算：取三模态 projector 输出的等权平均送入 backbone/head 得到的 hazard 与模型 forward 的 hazard `allclose(1e-6)`；(c) 把 `rna` 特征整体置零（模拟缺失）后，rna 的 token 等于 `ReLU(bias)` 常量 token 且**仍参与平均**（输出 ≠ 把 rna 从平均中剔除时的输出）；(d) `fusion_type='mean'` + `network_type='NPJC'` → `ValueError`。
3. **发车器**：`python3 scripts/train_launcher.py --arms d0 --cancers BLCA,BRCA,LUAD,LGG,UCEC --seeds 123,132,213,231,321,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20 --gpus 0,1 --per_gpu 6 --cpt-name tcga_uni2_d0 --result-path out_d0 --dry_run`（其余参数照 `e0d` 曾用法：`--eval_grids none,rna_100,text_100,both_100 --eval_workers 6 --eval_out /home/wuhao/npjc_eval_d0 --eval_manifest data/missing_manifest_v1.csv`；若 dry-run 需要 `--python` 等参数按现有用法补齐）→ 125 条训练命令，每条含 `--network_type MainModalityMoE --compensator none --fusion_type mean --lr 0.0001 --epochs 50 --batch_size 32 --cpt_name tcga_uni2_d0 --result_path .../out_d0`；`checkpoint_path` 指向 `out_d0/<seed>/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_<C>_surv.pth`。同样 `--arms e1 --seeds 1..20 --cpt-name tcga_uni2 --result-path out` dry-run 100 条命令与现有 e1 口径逐参一致（`out_capr/<seed>/tcga_uni2_capr_..._NPJC_...`）。评测命令：对 d0 spec 调用你抽出的纯函数，断言含 `--fusion_type mean --network_type MainModalityMoE --compensator none`；对 e1 spec 断言**不含** `--fusion_type`。
4. `python3 -c 'import sys;[compile(open(p,"rb").read(),p,"exec") for p in sys.argv[1:]];print("COMPILE_OK")' model/fusion_model.py main_survival.py scripts/eval_missing.py scripts/train_launcher.py`；`find . -name "__pycache__" -newer collab_marker -o -name "*.pyc" -newer collab_marker | wc -l` 为 0（用 `touch /private/tmp/.../scratchpad/collab_marker` 作时间戳基准）。
5. `git -C /Users/wuhao/Desktop/TriModalSurv/NPJ status --porcelain` 只应比派单前多出 `tests/test_mean_fusion.py`（原本 `scripts/` 与 `model/compensator.py` 已是 untracked）；被改的 tracked 文件只有 `model/fusion_model.py`、`main_survival.py`。

## 相关坑（`collab/pitfalls.md`；执行前必读）
D16（发车器命令必须与既有正式口径逐参一致）、V18（输出路径自动后缀，断言前先打印实际路径）、V20（回归基线取派发前工作树快照，等价重构用 allclose）、V21（冒烟只判通/不崩）、V23（进结论的数字来自脚本留档）、V25（JSON keys 不断言顺序）、V31（对拍样本须覆盖触发/不触发两类）、S1（禁 py_compile）、C12（本单免确认直接实现）、E17（`python3`）、M6（会话恢复先盘点）。

## notes.md 固定结构
① 环境（python3/torch 版本）；② 每条验收命令 + 原样 stdout；③ 断言结果表（逐条 OK/FAIL/SKIPPED+原因）；④ 歧义与自行裁决；⑤ 耗时与迭代次数；末行 `TASK_DONE`。
