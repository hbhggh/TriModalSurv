# notes — NPJ-D 消融战役（2026-09-06 22:00:38 JST 建）

## 指挥官记录
- 2026-09-06 22:00:38 JST 用户裁决（见 ~/.claude/plans/imperative-crunching-coral.md）：NPJ-D = NPJ-A 去 GatedFusion 其余全同；E0=D（25 seed，125 run）；E1=现 NPJ-C+CAP 补 20 seed（100 run）；Dm 零训练评测（已授权）；C 线附录；主贡献定位原型补偿（UCEC 条件性）。指挥官异议留档：E1 vs D 相差五项（attention/模态嵌入/缺失语义/dropout/λ），报告标"系统级对比"。
- 派单前基线：`/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/npj_sha_before.txt`、`/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/npj_status_before.txt`、`/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/fusion_model_before.py`。

---

## 执行者（Opus 子 agent）——2026-09-06 22:08:14 JST 环境探测与实现

### ① 环境
- 解释器探测（22:08:14）：`/usr/bin/python3`、`/opt/homebrew/bin/python3`、`~/miniconda3/bin/python3`、`envs/momix`、`envs/tcga_env` **均无 torch**；唯一带 torch 的是 `/Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python` → **py 3.10.20 / torch 2.5.1 / pytest 可用**。验收 ①② 用它实跑（CPU、tiny 张量），**未 SKIP**。
- 本机缺 `transformers / sksurv / accelerate / torchmetrics / tqdm / easydict`，`scattermoe` 因缺 `triton` 导入即失败 → 单测在**测试进程边界**装最小替身（真实可用时用真实包），不动生产导入结构（坑 E8/E9/E3；替身均设 `__spec__`，未触发 Dynamo 发现）。
- 全程 `export PYTHONDONTWRITEBYTECODE=1`；基线快照 `scratchpad/fusion_model_before.py`、时间戳基准 `scratchpad/collab_marker`、派单前 `git status` 存 `scratchpad/git_status_before.txt`。

### 实现（白名单 4 改 + 1 新增）
1. `NPJ/model/fusion_model.py`：新增 `class MeanFusion(nn.Module)`（952-967，插在 GatedFusion 与 SurvivalHead 之间，无可学习参数，`torch.stack(reps_list, dim=1).mean(dim=1)`，全 None 抛 ValueError）；`MainModalityMoE.__init__` 参数表末尾加 `fusion_type: str = "gate"`（982），fusion 选择 998-1004（gate→GatedFusion 原样 / mean→MeanFusion / 其他→ValueError）。`forward` 一行未改，NPJC/GatedFusion/SurvivalHead 未动。
2. `NPJ/main_survival.py`：`--fusion_type`（choices gate/mean，默认 gate）；`load_model(..., fusion_type='gate')` + 非 MainModalityMoE 用 mean 抛 ValueError；MainModalityMoE 分支以关键字透传；`main()` 调用加 `fusion_type=args.fusion_type`。
3. `NPJ/scripts/eval_missing.py`：`--fusion_type`（同上）+ `load_model(..., fusion_type=getattr(args,"fusion_type","gate"))`；`--m1-mark-valid` 未动。
4. `NPJ/scripts/train_launcher.py`：`ARM_PRESETS["d0"]`（MainModalityMoE / none / `--fusion_type mean`）；新增常量 `EVAL_FORWARDED_OPTIONS=("--fusion_type",)`、纯函数 `build_eval_command(args, spec, checkpoint, out_dir)`、`eval_arm_of(spec)`、`_forwarded_eval_args(spec)`；`_run_eval` 改为调用该纯函数（行为不变，其余臂命令逐字不变）。`checkpoint_path` 未动。
5. 新增 `NPJ/tests/test_mean_fusion.py`（CPU、无数据，独立运行与 pytest 双入口）。

### ② 验收命令与原样 stdout（2026-09-06 22:14:03 JST）

cwd = `/Users/wuhao/Desktop/TriModalSurv/NPJ`，全程 `export PYTHONDONTWRITEBYTECODE=1`；
`PY=/Users/wuhao/miniconda3/envs/protomasksurv-exp1/bin/python`（本机唯一带 torch 的解释器），
`SP=/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad`。

**验收①②（单测：gate 逐位对拍 + mean 四项语义）**
```
$ $PY tests/test_mean_fusion.py       # 生产代码自身的 "['BLCA'] cancer_types" print 已滤除
PASS test_gate_path_bitwise_identical
PASS test_mean_state_dict_drops_gate_params
PASS test_mean_forward_matches_manual_average
PASS test_zero_rna_constant_token_still_averaged
PASS test_load_model_rejects_mean_for_npjc
RESULT=ALL_PASS SKIPPED=0

$ $PY -m pytest tests/test_mean_fusion.py -q -p no:cacheprovider
.....                                                                    [100%]
5 passed in 1.50s
```
反向对照（坑 V20/V31：证明对拍有鉴别力，不是恒真）：
```
$ NPJ_FUSION_BASELINE=$SP/fusion_model_mutant.py $PY tests/test_mean_fusion.py   # 基线 GatedFusion 输出 ×1.01
FAIL test_gate_path_bitwise_identical: AssertionError: gate 前向 hazard 不逐位相同
RESULT=FAILURES=1 SKIPPED=0

$ NPJ_FUSION_BASELINE=$SP/no_such_file.py $PY tests/test_mean_fusion.py          # 基线缺失
SKIP test_gate_path_bitwise_identical: 基线快照不存在: .../no_such_file.py（设 NPJ_FUSION_BASELINE 指定）
RESULT=ALL_PASS SKIPPED=1
```
（另一次对照留档：把基线的 `gate_logits + inf_mask` 改成 `+ inf_mask + 0.01` **仍 PASS**——softmax 对 logits 常数平移不变，属数学等价而非漏检；故改用乘性扰动重做对照。）

**验收③-1 发车器 d0 dry-run（125 条）**
```
$ $PY scripts/train_launcher.py --arms d0 --cancers BLCA,BRCA,LUAD,LGG,UCEC \
    --seeds 123,132,213,231,321,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20 \
    --gpus 0,1 --per_gpu 6 --cpt-name tcga_uni2_d0 --result-path out_d0 --python python3 \
    --eval_grids none,rna_100,text_100,both_100 --eval_workers 6 \
    --eval_out /home/wuhao/npjd_eval_d0 --eval_manifest data/missing_manifest_v1.csv --dry_run
RESOLVED_GPU_POLICY={"allow_low_gpu_util": true, "batch_size": 32, "concurrent_runs": 1, "gpu_util_min_percent": 50, "gpu_util_target_percent": 80, "gpu_util_warmup_sec": 120, "gradient_accumulation_steps": 1, "low_gpu_util_reason": "NPJ small compute graph: measured active-util median 11-15%, peak 31% across bs 32-256 on V100; wall time increases with larger bs (probe 2026-09-02, collab/20260902-NPJ-GPU合同/notes.md)", "non_blocking": true, "num_workers": 4, "persistent_workers": true, "pin_memory": true, "prefetch_factor": 4}
DRY_RUN index=1 name=d0_BLCA_s123 arm=d0 cancer=BLCA seed=123 gpu=0 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0/123/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth command=python3 /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 123 --cpt_name tcga_uni2_d0 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0 --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type MainModalityMoE --hidden_size 256 --compensator none --lr 0.0001 --epochs 50 --batch_size 32 --fusion_type mean
DRY_RUN index=2 name=d0_BLCA_s132 arm=d0 cancer=BLCA seed=132 gpu=1 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0/132/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth command=python3 /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 132 --cpt_name tcga_uni2_d0 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0 --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type MainModalityMoE --hidden_size 256 --compensator none --lr 0.0001 --epochs 50 --batch_size 32 --fusion_type mean
...（共 125 条 DRY_RUN 行；全量落 `/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/dry_d0.txt`，逐条机器断言见 ③-3）
DRY_RUN index=125 name=d0_UCEC_s20 arm=d0 cancer=UCEC seed=20 gpu=0 slot=2 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0/20/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_UCEC_surv.pth command=python3 /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 20 --cpt_name tcga_uni2_d0 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0 --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types UCEC --network_type MainModalityMoE --hidden_size 256 --compensator none --lr 0.0001 --epochs 50 --batch_size 32 --fusion_type mean
DRY_RUN_TOTAL=125
```
**验收③-2 发车器 e1 dry-run（100 条，既有口径回归）**
```
$ $PY scripts/train_launcher.py --arms e1 --cancers BLCA,BRCA,LUAD,LGG,UCEC \
    --seeds 1,2,3,...,20 --gpus 0,1 --per_gpu 6 --cpt-name tcga_uni2 --result-path out \
    --python python3 --eval_grids none,rna_100,text_100,both_100 --eval_workers 6 \
    --eval_out /home/wuhao/npjc_eval_e1_25 --eval_manifest data/missing_manifest_v1.csv --dry_run
DRY_RUN index=1 name=e1_BLCA_s1 arm=e1 cancer=BLCA seed=1 gpu=0 slot=0 checkpoint=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_capr/1/tcga_uni2_capr_img_1536text_768rna_256_NPJC_BLCA_surv.pth command=python3 /Users/wuhao/Desktop/TriModalSurv/NPJ/main_survival.py --seed 1 --cpt_name tcga_uni2 --result_path /Users/wuhao/Desktop/TriModalSurv/NPJ/out --report_label_path /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv --model_config /Users/wuhao/Desktop/TriModalSurv/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml --gpu_config /Users/wuhao/Desktop/TriModalSurv/NPJ/config/gpu_train.yaml --cancer_types BLCA --network_type NPJC --hidden_size 256 --compensator capr --lr 0.0001 --epochs 50 --batch_size 32 --modality_dropout 0.15 --consistency_lambda 0.1
...（共 100 条；全量落 `/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/dry_e1.txt`）
DRY_RUN_TOTAL=100
```
**验收③-3 逐参断言脚本（含 `build_eval_command` 纯函数）**
```
$ $PY $SP/assert_launcher.py $SP
OK   d0 命令条数=125 | total=125 rows=125
OK   d0 每条含 network_type/compensator/fusion_type/lr/epochs/batch_size/cpt_name | bad=[]
OK   d0 --result_path=<NPJ>/out_d0 | bad=[]
OK   d0 checkpoint 路径逐条匹配（含实际推导目录，坑 V18） | bad=[]
d0 SAMPLE_CKPT=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0/123/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth
OK   d0 唯一 name 数=125
OK   e1 命令条数=100 | total=100
OK   e1 逐参与现有口径一致 | bad=[]
OK   e1 训练命令不含 --fusion_type
OK   e1 checkpoint = out_capr/<seed>/tcga_uni2_capr_..._NPJC_... | bad=[]
e1 SAMPLE_CKPT=/Users/wuhao/Desktop/TriModalSurv/NPJ/out_capr/1/tcga_uni2_capr_img_1536text_768rna_256_NPJC_BLCA_surv.pth
EVAL_CMD_D0=python3 /Users/wuhao/Desktop/TriModalSurv/NPJ/scripts/eval_missing.py --arm m0real --cancer BLCA --seed 123 --ckpt /Users/wuhao/Desktop/TriModalSurv/NPJ/out_d0/123/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_BLCA_surv.pth --manifest /Users/wuhao/Desktop/TriModalSurv/NPJ/data/missing_manifest_v1.csv --grids none,rna_100,text_100,both_100 --label /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv --out-dir /tmp/eval_tmp --network_type MainModalityMoE --compensator none --fusion_type mean
EVAL_CMD_E1=python3 /Users/wuhao/Desktop/TriModalSurv/NPJ/scripts/eval_missing.py --arm m0real --cancer BLCA --seed 1 --ckpt /x/ckpt.pth --manifest /Users/wuhao/Desktop/TriModalSurv/NPJ/data/missing_manifest_v1.csv --grids none,rna_100,text_100,both_100 --label /Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv --out-dir /tmp/eval_tmp --network_type NPJC --compensator capr
OK   d0 评测命令含 --fusion_type mean
OK   d0 评测命令 --network_type MainModalityMoE
OK   d0 评测命令 --compensator none
OK   d0 评测 arm=m0real
OK   e1 评测命令不含 --fusion_type（坑 V31 不触发侧）
OK   e1 评测命令与补丁前逐字一致 | got=['python3', '/Users/wuhao/Desktop/TriModalSurv/NPJ/scripts/eval_missing.py', '--arm', 'm0real', '--cancer', 'BLCA', '--seed', '1', '--ckpt', '/x/ckpt.pth', '--manifest', '/Users/wuhao/Desktop/TriModalSurv/NPJ/data/missing_manifest_v1.csv', '--grids', 'none,rna_100,text_100,both_100', '--label', '/Users/wuhao/Desktop/TriModalSurv/NPJ/data/TCGA_9523_ex12.csv', '--out-dir', '/tmp/eval_tmp', '--network_type', 'NPJC', '--compensator', 'capr']
OK   eval_missing.py CLI 接受 --fusion_type mean | ns={'arm': 'm0real', 'cancer': 'BLCA', 'seed': 1, 'ckpt': PosixPath('/x.pth'), 'manifest': PosixPath('/m.csv'), 'grids': 'all', 'label': PosixPath('/l.csv'), 'out_dir': PosixPath('/o'), 'compensator': 'none', 'network_type': 'MainModalityMoE', 'fusion_type': 'mean', 'm1_mark_valid': False}
ASSERT_RESULT=ALL_OK
```

**验收④ 语法编译 + 字节码泄漏**
```
$ python3 -c 'import sys;[compile(open(p,"rb").read(),p,"exec") for p in sys.argv[1:]];print("COMPILE_OK")' \
    model/fusion_model.py main_survival.py scripts/eval_missing.py scripts/train_launcher.py
COMPILE_OK
$ find . -name "__pycache__" -newer $SP/collab_marker -o -name "*.pyc" -newer $SP/collab_marker | wc -l
       0
```

**验收⑤ git 状态（只读；本单全程无任何 git 写操作）**
```
$ git -c core.quotePath=false status --porcelain      # 坑 V30：加 quotePath=false
 M loc_utils_3yr/tcga_dataset.py
 M main_survival.py
 M model/fusion_model.py
?? config/gpu_train.yaml
?? loc_utils/__pycache__/model_util.cpython-310.pyc
?? loc_utils_3yr/__pycache__/tcga_dataset.cpython-310.pyc
?? model/__pycache__/compensator.cpython-310.pyc
?? model/__pycache__/fusion_model.cpython-310.pyc
?? model/compensator.py
?? scattermoe/__pycache__/
?? scattermoe/kernels/__pycache__/
?? scripts/
?? tests/test_mean_fusion.py
$ diff $SP/git_status_before.txt <(git -c core.quotePath=false status --porcelain)
12a13
> ?? tests/test_mean_fusion.py
```
`loc_utils_3yr/tcga_dataset.py` 的 M 为**派单前既有**（mtime 2026-09-02 18:58:16，早于本单基准 22:02:32），本单未碰。

### ③ 断言结果表

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| ① | gate 模型 state_dict 键集合相同 + 逐张量 `torch.equal` | **OK** | `test_gate_path_bitwise_identical` |
| ① | gate 路径 eval 前向 hazard/surv `torch.equal` | **OK** | 同上（乘性扰动可 FAIL、缺基线会 SKIP，双向对照） |
| ②a | mean 键集合 = gate 键集合 − `fusion.gate.*`；MeanFusion 零参数 | **OK** | `test_mean_state_dict_drops_gate_params` |
| ②b | mean 前向 == 手算等权平均（hazard 与 surv，allclose 1e-6） | **OK** | `test_mean_forward_matches_manual_average` |
| ②c | rna 置零 → token = `ReLU(bias)` 常量且逐样本相同 | **OK** | `test_zero_rna_constant_token_still_averaged` |
| ②c | 该常量 token **仍参与平均**（与剔除 rna 的输出不 allclose，max abs Δ > 1e-6） | **OK** | 同上 |
| ②d | `fusion_type='mean'` + `network_type='NPJC'` → ValueError | **OK** | `test_load_model_rejects_mean_for_npjc`（含 NPJC 默认 gate、MoE+mean 两条不触发侧） |
| ③ | d0 dry-run 125 条，逐条含 MainModalityMoE / none / mean / lr 1e-4 / 50 / 32 / cpt_name | **OK** | `assert_launcher.py` |
| ③ | d0 ckpt = `out_d0/<seed>/tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_<C>_surv.pth` | **OK** | 125 条逐条比对（坑 V18：路径由代码实际推导后打印） |
| ③ | e1 dry-run 100 条逐参一致、训练命令无 `--fusion_type`、ckpt 落 `out_capr/...NPJC...` | **OK** | 同上（坑 D16） |
| ③ | `build_eval_command(d0)` 含 `--fusion_type mean --network_type MainModalityMoE --compensator none` | **OK** | `EVAL_CMD_D0=` 行 |
| ③ | `build_eval_command(e1)` 不含 `--fusion_type` 且与补丁前逐字一致 | **OK** | `EVAL_CMD_E1=` 行 + 字面列表相等 |
| ③ | `eval_missing.py` CLI 实际接受 `--fusion_type mean` | **OK** | 解析器实跑 |
| ④ | 四文件内存 `compile()` 通过（禁 `py_compile`，坑 S1） | **OK** | `COMPILE_OK` |
| ④ | 基准时刻后无新增 `__pycache__` / `.pyc` | **OK**（清理后） | 计数 0；见 Post-Mortem |
| ⑤ | git 状态仅多 `tests/test_mean_fusion.py`；改动的 tracked 文件仅 2 个 | **OK** | `diff` 仅 1 行新增 |

无 FAIL，无 SKIPPED。

### Bug Post-Mortem（本单新发现，建议入台账）
- **现象**：验收④ 首跑 `find ... -newer collab_marker` 计到 2 项——`NPJ/tests/__pycache__/test_mean_fusion.cpython-313.pyc`（mtime 22:06:50，解释器 3.13，而本单跑测试用的是 3.10 env）。
- **根因**：全局 `~/.claude/settings.json` 的 PostToolUse hook（matcher `Write|Edit`）执行 `~/.claude/hooks/py_compile_check.py`，其中裸调 `py_compile.compile(file_path, doraise=True)` 未传 `cfile=`，在源码旁写 `__pycache__`；hook 跑在**独立进程**，Bash 里 export 的 `PYTHONDONTWRITEBYTECODE` 管不到它（且 `py_compile` 本就无视该变量）。与坑 S1 同一根因，这次触发者是工具链 hook 而非人工命令。
- **修复**：精确删除该 `.pyc` 与空目录（`rm` 单文件 + `rmdir`，不用 `rm -rf`，遵守坑 S2），复跑验收④ 计数归 0。
- **Prevention Rule**：严格白名单任务中用 Write/Edit 工具写 `.py`，会经全局 py_compile hook 在源码旁落 `.pyc`；交付前必跑 `find -newer <基准>` 并精确清理，或改用 Bash 写文件绕开该 hook。

### ④ 歧义与自行裁决
1. **基线快照路径写死在测试文件里不合适** → 测试读环境变量 `NPJ_FUSION_BASELINE`（默认本单 scratchpad 快照），快照缺失时该用例 SKIP 而非假通过（本机实跑 SKIPPED=0）。
2. **本机缺 6 个第三方包、`scattermoe` 缺 triton** → 按坑 E8/E9/E3 只在**测试进程边界**装最小替身（`_available()` 先探测，真实包存在时一律用真实包，故 landau 上跑的是真依赖），生产导入结构零改动；替身均设 `__spec__`（坑 E4/E9，未触发 Dynamo 发现）。
3. **dry-run 的 `--python` 取值** → 统一传 `--python python3` 便于比对；landau 实跑仍按 `tools/launch_d0.sh` 的 `--python "$(which python)"`，该参数不影响本单断言的训练/评测参数。
4. **`_run_eval` 抽函数边界** → 抽出 `build_eval_command(args, spec, checkpoint, out_dir)` 纯函数 + `eval_arm_of(spec)`；临时目录、环境变量、子进程、JSON 落盘等副作用留在 `_run_eval`，保证纯函数可在无 SSH 环境断言。
5. **d0 评测开关透传实现** → 采用「从 `extra_args` 提取」而非新增 `eval_extra_args` 键，白名单常量 `EVAL_FORWARDED_OPTIONS=("--fusion_type",)`；其余臂 extra_args 无该开关，命令逐字不变（已用字面列表断言）。
6. **`MeanFusion` 收到全 None** → 契约未定义；取最保守的显式 `ValueError`（GatedFusion 该情形会 IndexError；两者都属不可达路径：生存数据集从不产 `{mm}_mask`）。
7. **新增 `self.fusion_type` 属性** → 便于日志/排错；非 Module 非 Parameter，不进 state_dict，已由验收① 逐位对拍证明对 gate 路径零影响。
8. **dry-run 全量 stdout 未逐行贴进 notes** → 225 条长行约 100 KB，notes 只贴首/尾样本 + 总数，全量落 scratchpad 并由 `assert_launcher.py` 逐条机器断言（脚本源码见文末，可离线重跑）。
9. **`fusion_type` 未纳入 ckpt 文件名**（契约要求 `checkpoint_path()` 不动）→ d0 靠 `--cpt-name tcga_uni2_d0 --result-path out_d0` 隔离。**残留风险**：若有人用 `--cpt-name tcga_uni2 --result-path out` 跑 d0，ckpt 名会与 A 臂（gate）完全相同而互相覆盖，且 `--fusion_type` 不进文件名无法事后分辨——建议发车一律走 `tools/launch_d0.sh`。

### ⑤ 耗时与迭代次数
- 墙钟：2026-09-06 22:02:32 → 22:14:03（约 10 分钟）；无训练、无 SSH、无联网、无 pip、无 git 写操作、无转派。
- 迭代：4 个源文件补丁各 1 次成型（无返工）；测试文件 1 次成型 + 1 次小改（独立入口加 SKIPPED 计数）；反向对照 2 次（首个扰动落在 softmax 平移不变的等价类上，换乘性扰动重做）；验收④ 1 次返工（清理 hook 落下的 `.pyc`）。
- 单测耗时：独立入口约 3.8 s（含解释器启动），pytest 1.50 s；纯 CPU、无数据依赖，均 < 10 s。

### 附：验收③ 断言脚本源码（scratchpad 随进程重启清空，按坑 M7 全文留档）
```python
#!/usr/bin/env python3
"""NPJ-D 验收③：dry-run 逐参断言 + build_eval_command 纯函数断言（D16/V18/V31）。"""
import importlib.util
import re
import shlex
import sys
from pathlib import Path
from types import SimpleNamespace

NPJ = Path("/Users/wuhao/Desktop/TriModalSurv/NPJ")
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

spec = importlib.util.spec_from_file_location("train_launcher", NPJ / "scripts" / "train_launcher.py")
tl = importlib.util.module_from_spec(spec)
sys.modules["train_launcher"] = tl
spec.loader.exec_module(tl)

fails = []


def check(label, condition, detail=""):
    print(("OK   " if condition else "FAIL ") + label + (f" | {detail}" if detail else ""))
    if not condition:
        fails.append(label)


def parse(path):
    rows = []
    for line in path.read_text().splitlines():
        m = re.match(r"DRY_RUN index=(\d+) name=(\S+) .* seed=(\S+) gpu=\S+ slot=\S+ checkpoint=(\S+) command=(.*)$", line)
        if m:
            rows.append(SimpleNamespace(index=int(m.group(1)), name=m.group(2), seed=m.group(3),
                                        checkpoint=m.group(4), command=shlex.split(m.group(5))))
    total = re.search(r"DRY_RUN_TOTAL=(\d+)", path.read_text())
    return rows, int(total.group(1))


def pair(cmd, option):
    for i, a in enumerate(cmd):
        if a == option and i + 1 < len(cmd):
            return cmd[i + 1]
    return None


# ---- d0 ----
rows, total = parse(SCRATCH / "dry_d0.txt")
check("d0 命令条数=125", total == 125 and len(rows) == 125, f"total={total} rows={len(rows)}")
expect = {"--network_type": "MainModalityMoE", "--compensator": "none", "--fusion_type": "mean",
          "--lr": "0.0001", "--epochs": "50", "--batch_size": "32", "--cpt_name": "tcga_uni2_d0"}
bad = [(r.name, o, pair(r.command, o)) for r in rows for o, v in expect.items() if pair(r.command, o) != v]
check("d0 每条含 network_type/compensator/fusion_type/lr/epochs/batch_size/cpt_name", not bad, f"bad={bad[:3]}")
bad = [(r.name, pair(r.command, "--result_path")) for r in rows if pair(r.command, "--result_path") != str(NPJ / "out_d0")]
check("d0 --result_path=<NPJ>/out_d0", not bad, f"bad={bad[:3]}")
bad = []
for r in rows:
    cancer = pair(r.command, "--cancer_types")
    want = str(NPJ / "out_d0" / r.seed / f"tcga_uni2_d0_img_1536text_768rna_256_MainModalityMoE_{cancer}_surv.pth")
    if r.checkpoint != want:
        bad.append((r.name, r.checkpoint, want))
check("d0 checkpoint 路径逐条匹配（含实际推导目录，坑 V18）", not bad, f"bad={bad[:2]}")
print("d0 SAMPLE_CKPT=" + rows[0].checkpoint)
check("d0 唯一 name 数=125", len({r.name for r in rows}) == 125)

# ---- e1 ----
rows_e1, total_e1 = parse(SCRATCH / "dry_e1.txt")
check("e1 命令条数=100", total_e1 == 100 and len(rows_e1) == 100, f"total={total_e1}")
expect_e1 = {"--network_type": "NPJC", "--compensator": "capr", "--lr": "0.0001", "--epochs": "50",
             "--batch_size": "32", "--cpt_name": "tcga_uni2", "--modality_dropout": "0.15",
             "--consistency_lambda": "0.1"}
bad = [(r.name, o, pair(r.command, o)) for r in rows_e1 for o, v in expect_e1.items() if pair(r.command, o) != v]
check("e1 逐参与现有口径一致", not bad, f"bad={bad[:3]}")
check("e1 训练命令不含 --fusion_type", all("--fusion_type" not in r.command for r in rows_e1))
bad = []
for r in rows_e1:
    cancer = pair(r.command, "--cancer_types")
    want = str(NPJ / "out_capr" / r.seed / f"tcga_uni2_capr_img_1536text_768rna_256_NPJC_{cancer}_surv.pth")
    if r.checkpoint != want:
        bad.append((r.name, r.checkpoint, want))
check("e1 checkpoint = out_capr/<seed>/tcga_uni2_capr_..._NPJC_...", not bad, f"bad={bad[:2]}")
print("e1 SAMPLE_CKPT=" + rows_e1[0].checkpoint)

# ---- build_eval_command 纯函数 ----
args = SimpleNamespace(python="python3", eval_manifest=NPJ / "data/missing_manifest_v1.csv",
                       eval_grids="none,rna_100,text_100,both_100", label=NPJ / "data/TCGA_9523_ex12.csv")
d0_spec = tl.generate_runs("d0", "BLCA", "123")[0]
e1_spec = tl.generate_runs("e1", "BLCA", "1")[0]
ckpt_d0 = Path(tl.checkpoint_path(shlex.split(str(Path(SCRATCH / "dry_d0.txt").read_text().splitlines()[1]).split("command=", 1)[1])))
cmd_d0 = tl.build_eval_command(args, d0_spec, ckpt_d0, Path("/tmp/eval_tmp"))
cmd_e1 = tl.build_eval_command(args, e1_spec, Path("/x/ckpt.pth"), Path("/tmp/eval_tmp"))
print("EVAL_CMD_D0=" + shlex.join(cmd_d0))
print("EVAL_CMD_E1=" + shlex.join(cmd_e1))
check("d0 评测命令含 --fusion_type mean", pair(cmd_d0, "--fusion_type") == "mean")
check("d0 评测命令 --network_type MainModalityMoE", pair(cmd_d0, "--network_type") == "MainModalityMoE")
check("d0 评测命令 --compensator none", pair(cmd_d0, "--compensator") == "none")
check("d0 评测 arm=m0real", pair(cmd_d0, "--arm") == "m0real")
check("e1 评测命令不含 --fusion_type（坑 V31 不触发侧）", "--fusion_type" not in cmd_e1)
expected_e1 = ["python3", str(NPJ / "scripts" / "eval_missing.py"), "--arm", "m0real", "--cancer", "BLCA",
               "--seed", "1", "--ckpt", "/x/ckpt.pth", "--manifest", str(NPJ / "data/missing_manifest_v1.csv"),
               "--grids", "none,rna_100,text_100,both_100", "--label", str(NPJ / "data/TCGA_9523_ex12.csv"),
               "--out-dir", "/tmp/eval_tmp", "--network_type", "NPJC", "--compensator", "capr"]
check("e1 评测命令与补丁前逐字一致", cmd_e1 == expected_e1, f"got={cmd_e1}")
# 评测器确实接受 --fusion_type mean（CLI 契约）
sys.argv = ["eval_missing.py", "--arm", "m0real", "--cancer", "BLCA", "--seed", "1", "--ckpt", "/x.pth",
            "--manifest", "/m.csv", "--label", "/l.csv", "--out-dir", "/o", "--fusion_type", "mean"]
src = (NPJ / "scripts" / "eval_missing.py").read_text()
ns = {"__name__": "eval_missing_parse_only"}
start = src.index("def parse_args()")
exec("import argparse\nfrom pathlib import Path\nCANCERS=('BLCA','BRCA','LUAD','LGG','UCEC')\n" + src[start:src.index("def main()", start)], ns)
parsed = ns["parse_args"]()
check("eval_missing.py CLI 接受 --fusion_type mean", parsed.fusion_type == "mean", f"ns={vars(parsed)}")

print("ASSERT_RESULT=" + ("ALL_OK" if not fails else f"FAILED={fails}"))
sys.exit(1 if fails else 0)
```

TASK_DONE


## 指挥官复核（Claude，2026-09-06 22:20:52 JST）

独立验证（不信 result 自述，逐条亲跑）：
- diff 逐文件：`fusion_model.py`（vs scratch 基线快照）只增 `MeanFusion` + `fusion_type` 分支，`forward` 未动；`main_survival.py` / `scripts/eval_missing.py` / `scripts/train_launcher.py`（vs `code/NPJ/` 快照，SHA 与派单前一致）改动均限于契约白名单；`checkpoint_path()` 未动；`tcga_dataset.py` 的 M 为 09-02 既有。
- ①②：`protomasksurv-exp1` python（torch 2.5.1）`pytest tests/test_mean_fusion.py -p no:cacheprovider` → 5 passed（含 gate 逐位对拍，基线经 `NPJ_FUSION_BASELINE` 指向 scratchpad 快照）。
- ③：d0 dry-run 125 条，每条含 `--network_type MainModalityMoE --compensator none --fusion_type mean --lr 0.0001 --epochs 50 --batch_size 32 --cpt_name tcga_uni2_d0`，**不含** `--modality_dropout` / `--consistency_lambda`（0 条）；ckpt 落 `out_d0/<seed>/tcga_uni2_d0_..._MainModalityMoE_<C>_surv.pth`。e1 dry-run 100 条含 `--modality_dropout 0.15 --consistency_lambda 0.1`、不含 `--fusion_type`，ckpt 落 `out_capr/<seed>/..._NPJC_...`。留档：scratchpad `dry_d0.txt` / `dry_e1.txt`。
- ④：内存 compile 5 文件 COMPILE_OK；`-newer collab_marker` 的 pyc/pycache = 0（工作树里 cpython-310 pyc 均为 09-01/09-02 旧物，非本单产物）。
- ⑤：`git -C NPJ status` 新增仅 `tests/test_mean_fusion.py`。

**D / Dm 设计约束二次审核（用户 2026-09-06 22:20:52 JST 提问）**，逐项对代码：

| 约束 | D（d0 训练） | 证据 |
|---|---|---|
| 无跨 token attention | 成立 | `MainModalityMoE.forward`：fusion 后 `unsqueeze(1)` → backbone 在长度 1 序列上跑，自注意力退化为恒等式变换 |
| 无可学习模态嵌入 | 成立 | `MainModalityMoE.__init__` 无 `modality_embed`（仅 NPJC 有） |
| 无 modality dropout | 成立 | d0 命令不传 `--modality_dropout`，argparse 默认 0.0；数据集 `split=='train' and modality_dropout>0` 才建 rng |
| 无一致性 loss | 成立 | `--compensator none` → `MainModalityMoE` 返回 2 元组，`main_survival.py` 只在 `len(outputs)>2` 时加 consistency；`--consistency_lambda` 默认 0.1 但无消费点 |
| 无缺失位处理 | 成立（裁决 (a)） | 无 compensator；`<mm>_mask` 死代码；缺失=零特征 → projector 常量 token 等权入 mean |
| 网络层 dropout 0.1 | 与 A 同 | projector `nn.Dropout(0.1)` 与 TransformerEncoderLayer dropout 0.1 为 NPJ-A 原有普通 dropout，不是协议 dropout；A/D/C/E1 都有，不属差异项 |

Dm：同一 d0 ckpt，`eval_missing.py --arm m1 --network_type MainModalityMoE --fusion_type mean`；均值来自 train split 天然非缺失样本（`compute_training_feature_means`），只替换 `valid=False` 位；D 不读 `valid`，无需 `--m1-mark-valid`；零训练。输出名 `m1_<C>_s<seed>.json` → `eval_dm_one.sh` 改名 `dm_<C>_s<seed>.json`。
提示：D 训练里 valid 标志整段未被消费，所以「均值填」只在 Dm 评测生效，训练期自然缺失始终是零特征（与 A 相同）。

结论：D/Dm 约束与用户裁决一致，无需改设计。下一步（已批计划步骤 4）：部署 4 文件 + tests 到 landau → 冒烟 d0 BLCA s123 1 run + 4 格点 + Dm 1 次评测 → 停机汇报。


## 步骤 4 冒烟（指挥官执行，2026-09-07 08:42:28 JST）

用户 2026-09-07 批准步骤 4。执行摘要与全部产物见 `smoke/README.md`、`smoke/*`（d0 json/训练 log/评测 log/jobrun log/job.json/训练侧 results json、dm json+log、parity 两癌 json/out/log、自然缺失计数）。结论：**全链通、不崩**——单测 5 pass、两处 PARITY_PASS、jobrun done.flag、ckpt 落地、d0 与 dm 各 4 格点齐全、Dm none 逐位等于 D none。停机门：未开 125/100/125 全量，等用户点头。
landau 侧新建目录：`out_d0/`、`/home/wuhao/npjd_eval_d0/`、`/home/wuhao/npjd_eval_dm/`、`/home/wuhao/npjd_parity/`、`backup_20260906_npjd/`、`scripts_tmp/`；`runs_state.json` 新增 d0_BLCA_s123（全量时幂等跳过该 run）。GPU 0 当时被他人占 2.6 GB 显存但 util 0%。


## 步骤 6 全量发车（2026-09-07 08:51:28 JST）

- 用户 2026-09-07 08:46 JST 裁决「开步骤 6 全量」。指挥官异议留档：步骤 5 对抗审查尚未做，不阻塞发车，改为训练期间后台并行审查（companion `adversarial-review --cwd NPJ --scope working-tree --model gpt-5.6-sol --json`），发现问题立即报用户。
- 发车前只读预检：GPU0 他人任务 util 90% / 3.7 GB（共享，显存充足）、GPU1 空闲；无我方进程、无 running.flag；e1 既有 ckpt 25；`launch_d0.sh --dry_run` 125 条。
- 08:47:31 经 jobrun 发 **npjd_full_d0**（pid 2689220）：`bash /home/wuhao/NPJ/jobrun.sh npjd_full_d0 0,1 /home/wuhao/NPJ/launcher_logs/npjd_full_d0.jobrun.log -- bash /home/wuhao/NPJ/launch_d0.sh`（launcher：d0 × 5 癌 × 25 seed，`--gpus 0,1 --per_gpu 6`，完成即评测 4 格点进 `/home/wuhao/npjd_eval_d0/`，`--eval_workers 6`）。85 s 验证：running.flag 在、12 run 并发、5 done、d0_BLCA_s123 skipped（冒烟幂等）、GPU0 77%/8.3 GB、GPU1 14%/3.8 GB。
- 监视：Monitor 任务 b5kpk1lc4，每 4 min 轮询 runs_state（done/running/pending/failed）、json 计数、done/fail.flag、最新 log 空闲秒数；failed>0 或 idle ≥45 min 只报警不杀（AGENTS.md）。
- 阶段计划：d0 done.flag → 发 `launch_e1_seeds.sh`（npjd_full_e1，100 run，评测进 `/home/wuhao/npjc_eval_e1_25/`）→ 发 `run_dm.sh`（npjd_full_dm，125 评测，BLCA s123 幂等 SKIP）→ 拉回 `results_npjd_d0/`、`results_npjc_e1_25/`、`results_npjd_dm/`。
- 2026-09-07 08:52:46 JST 步骤 5 对抗审查后台并行启动（macOS 无 `setsid`，用子 shell `nohup … &`）：`node ~/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs adversarial-review --cwd NPJ --scope working-tree --model gpt-5.6-sol --json "<focus>"`，pid 34996，focus 见 `审查/adversarial-review-focus.txt`（只审 NPJ-D 改动集，P0 = gate 逐位不变 / d0 身份隔离 / 评测图与训练图一致），产物 `审查/adversarial-review-raw.json` + `stderr.log`；等待器后台任务 b4zyhsant。
- 2026-09-07 09:04:25 JST 对抗审查收官（09:01:15 退出，raw 24.7 KB）：verdict needs-attention，3 critical + 1 medium。指挥官逐条核实见 `审查/adversarial-review-findings.md`：[0] plan 模式不继承 extra_args（不触发，本战役走 CLI；54 个 d0 日志 52 个已写参数行全为 mean/tcga_uni2_d0，0 gate）；[1] 默认路径同址（不触发，固定 out_d0；`out/` 0 新文件）；[2] mean 分支不消耗 GatedFusion 初始化随机数 → 同 seed 共享张量 8/20 不同（本地复现），判为抽样差异非偏差，不重跑，报告改口径「协议配对非初始化配对」；[3] 基线缺失静默 skip（两处实跑均 SKIPPED=0）。裁决：不中断、不重跑；收官后加固单。坑入账 D17、V32。
- 2026-09-07 09:12:56 JST 会话重启（上一进程退出致 Monitor b5kpk1lc4 失效）：盘点 d0 = 71 done / 12 running / 41 pending / 0 failed，e1 未发；重挂 Monitor b6745drmb。应用户提问「门控有没有起作用」，对已完成的 BLCA/BRCA/LUAD × S5 五 seed 做了一次 D(mean) vs NPJ-A(gate, `results_gate/m0real`) 四格点**初步窥视**（B 口径 Δ中位：BLCA −0.012/−0.015/−0.052/−0.038，BRCA +0.032/+0.028/+0.025/+0.097，LUAD +0.040/+0.011/+0.027/+0.011）。声明：只用于回答机制问题，不进结论；正式判定仍按预注册在 25 seed 齐后由 `r6_numbers.py` 出。
- 2026-09-07 09:32:08 JST **d0 阶段收官**：done.flag 09:25:31（08:47:31 发车，38 min）；runs_state d0 = 124 done + 1 skipped，0 failed；`npjd_eval_d0/` 125 json，`out_d0/` 125 ckpt，eval 日志 0 失败。拉回 `results_npjd_d0/`（125 json + `logs/` 125 训练 log + 125 eval log + jobrun log + `runs_state_after_d0.json`），完整性自检 125×4 格点齐全、arm=d0、ckpt 全在 out_d0。
- 09:29:16 **e1 补 seed 发车**：`jobrun.sh npjd_full_e1 0,1 … -- bash launch_e1_seeds.sh`（pid 2789892；100 run，评测进 `/home/wuhao/npjc_eval_e1_25/`）。发车前 dry-run 100 条：全部 `--modality_dropout 0.15 --consistency_lambda 0.1`、0 条 `--fusion_type`、ckpt 全落 `out_capr/`。85 s 验证：running.flag、12 并发、首个 log 参数行 NPJC/capr/0.15/0.1；GPU0 100%（含他人任务）、GPU1 88%。Monitor b653usjrh（5 min 轮询）。
### Bug Post-Mortem（接力脚本漏部署）
- **现象**: d0 收官后 `bash launch_e1_seeds.sh --dry_run` 报文件不存在，e1 发车延迟 4 分钟。
- **根因**: 步骤 1 部署清单只传了当步用到的 `launch_d0.sh`/`eval_dm_one.sh`，接力阶段的 `launch_e1_seeds.sh`/`run_dm.sh` 留在本地。
- **修复**: 补传两脚本（md5 核对）后 dry-run 100 条逐参通过再发车；`run_dm.sh` 已随手补传。
- **Prevention Rule**: 多阶段战役部署时以 `tools/` 目录**全量** md5 对比为准，而不是按当步需要挑文件；发车前每个接力脚本都先 `--dry_run`（M8）。
- 2026-09-07 09:33:59 JST `tools/r6_numbers.py` 小修：S5 参考 csv 实际在 `collab/20260902-A测缺失补偿/s5_full_reference.csv`（原写 S5 战役目录），改路径后在部分数据（D 125 / E1 25 / E0 25 / Dm 0）上试跑通过。**观察（不进结论、不剔除）**：D 在 BLCA 25 seed 完整模态 B 口径 min 0.4318(s16)/q1 0.5147/中位 0.5704/q3 0.6066/max 0.6270；3 个 seed（s4/s13/s16）<0.5；其余四癌四分位距 ≤0.02（BRCA 0.706–0.716，LUAD 0.592–0.607，LGG 0.797–0.809，UCEC 0.676–0.692）。异常 seed 训练日志：50 epoch 跑满、无 NaN/warning、test loss 0.89–0.98（正常 seed 0.81），属真实训练不稳定而非崩溃。裁决：按预注册不剔除 seed，报告异常 seed 清单；e1 补的 BLCA seed 1–20 作为同 seed 自然对照，看 NPJC 家族在这些 seed 上是否同样塌。
- 2026-09-07 10:07:22 JST **e1 阶段收官**：done.flag 10:04:59（09:29:16 发车，36 min）；runs_state e1 = 101 done（100 新 + 首秀 1），0 failed；`npjc_eval_e1_25/` 100 json，eval 日志 0 失败；`out_capr/` ckpt 125。拉回 `results_npjc_e1_25/`（100 json + logs + `runs_state_after_e1.json`）。
- 10:06:43 **Dm 发车**：`jobrun.sh npjd_full_dm 0,1 … -- bash run_dm.sh`（pid 2878373；125 任务 xargs -P 10 双卡奇偶；BLCA s123 幂等 SKIP）。Monitor blj7tu9t3（每分钟）。
- 2026-09-07 10:11:49 JST **Dm 阶段收官**：done.flag 10:10（10:06:43 发车，3.5 min）；125 json（含冒烟 1 份 SKIP 复用），0 EVALFAIL；拉回 `results_npjd_dm/`（125 json + logs + dm_tasks.txt），自检 125×4 齐全、arm=m1、ckpt 与 D 逐一相同 125/125、m1 均值计数在。**三阶段全部完成**（d0 38 min / e1 36 min / Dm 3.5 min，共 125+100 训练 run、375 次 4 格点评测，0 失败）。
- 出表：`tools/r6_numbers.py` → `r6_numbers.txt`（188 行；覆盖 D 125/Dm 125/E1 125/E0 25；自检 Dm none vs D none：BLCA 0.00e+00，BRCA 5.8e-3 / LUAD 1.8e-3 / LGG 2.8e-3 / UCEC 1.0e-2 非零属预期 V31）；`summarize_arms.py --seeds <25>` → `table_npjd_D_Dm_E1_3grids_{A,B}.md`、`table_npjd_D_Dm_E1_both100_{A,B}.md`（base D）。两脚本独立计算的 W:L:T 与 Δ中位 80 个格逐一相同。
- 2026-09-07 10:16:50 JST 报告升 r6：`a_test_report.md` 新增二 d 节（定义/预注册/注记/五张表/A-B 差异/逐癌判定/与 C 线对照）、实验臂表加 D/Dm/E1(25)、六节 r6 修订（主贡献措辞待用户裁决）、七节更新、r6 修订记录。`code/NPJ/` 快照刷新（4 文件 + tests）、`NPJ_changes_vs_upstream.patch` 15 diff（`git apply --check -R` 通过）、`NPJ_SNAPSHOT.md` 更新。REVIEW_PACK 同步：00/01/02/04/A_inventory、`build_03.py`（抽二 d + r6 派生量九节）、`check_numbers.py`（源加 r6_numbers.txt 与 table_npjd_*.md）。
- 2026-09-07 12:32:44 JST 应用户要求出绝对数值表 `table_npjd_D_Dm_E1_absolute_25seed.md`（`tools/abs_table.py` 生成；B 主表 + A 附录；四格点 × 5 癌 × 三臂 × 25 seed 逐值 + 中位/最小/最大；不含相对列）；另发布逐 seed 交互页面（artifact 830e33da）。
