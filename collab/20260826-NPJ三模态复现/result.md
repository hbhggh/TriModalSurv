# result.md — NPJ 三模态复现配置与阶段 1 文件执行结果

## 0. 结论

- 门控：CONCERNS（93/100）。
- 4 个目标文件的最终内容满足 plan.md A1/A2/B1/B2；逐字节比较证明没有目标替换之外的内容变化。
- plan.md §4 的 8 组命令已在最终状态下全部原样执行：7 组退出码为 0；Python YAML 命令因本机缺少 PyYAML，在 import yaml 阶段退出 1。
- 严格遵守“不得安装依赖”：未安装 PyYAML。按 plan.md 的回退要求完成两份 YAML 文本输出目检，并用系统 Ruby YAML.safe_load 完成完整语义等价验证；补充验证退出码均为 0。
- 最终 NPJ Git 工作树只列出 4 个白名单文件。未执行 git commit、git push、ssh、scp、landau 访问或依赖安装。

## 1. 改动文件清单

### NPJ 工作区

1. /Users/wuhao/Desktop/NPJ/model/config/surv_multimodal_mainmoe.yml（修改）
   - text.path：data/text_embeddings
   - rna.path：data/RNA_embedding
2. /Users/wuhao/Desktop/NPJ/running_scripts/survival_prediction_mainmoe.sh（修改）
   - gpu_id=0
   - cancer_types="BLCA"
   - --cpt_name tcga_orig
3. /Users/wuhao/Desktop/NPJ/model/config/surv_multimodal_mainmoe_uni2.yml（新建）
   - 阶段 0 YAML 的完整派生副本
   - 仅 img.path=data/tcga-dataset_uni2、img.feature_dim=1536 不同
4. /Users/wuhao/Desktop/NPJ/running_scripts/survival_prediction_mainmoe_uni2.sh（新建）
   - 阶段 0 shell 的完整派生副本
   - 仅 --model_config 指向 UNI2 YAML、--cpt_name tcga_uni2 不同

### 协作记录目录

1. /Users/wuhao/Desktop/ProtoMaskSurv/collab/20260826-NPJ三模态复现/notes.md（新建，append-only）
2. /Users/wuhao/Desktop/ProtoMaskSurv/collab/20260826-NPJ三模态复现/result.md（本文件）

## 2. plan.md 验收标准逐条达成情况

### A1. surv_multimodal_mainmoe.yml

- text.path == data/text_embeddings：达成。
- rna.path == data/RNA_embedding：达成。
- img 块、cancer_types: BLCA、network 和其余有效键值与原文件逐项相等：达成；Ruby 语义比较与基于 HEAD 的逐字节比较均通过。
- YAML 解析：系统 Ruby YAML.safe_load 通过；计划指定的 Python yaml.safe_load 命令因本机缺少 PyYAML，未执行到解析阶段。该项存在环境级阻塞，不能声称原命令通过。

### A2. survival_prediction_mainmoe.sh

- gpu_id=0：达成，grep 计数为 1。
- cancer_types="BLCA"：达成，grep 计数为 1。
- --cpt_name tcga_orig：达成，grep 计数为 1。
- bash -n：通过。
- seeds、lr、epochs、batch_size、network_types、summary 调用、NCCL 两行和所有其他行与原文件一致：达成；主 shell 等于 HEAD 版本加且仅加 3 次计划指定替换。

### B1. surv_multimodal_mainmoe_uni2.yml

- 为 A1 完成版完整副本，仅 img.path 和 img.feature_dim 两键不同：达成。
- img.path == data/tcga-dataset_uni2：达成。
- img.feature_dim == 1536：达成。
- text/rna/network 与 A1 完成版逐项相等：达成；Ruby 语义比较与逐字节比较均通过。
- YAML 解析：系统 Ruby YAML.safe_load 通过；计划指定的 Python yaml.safe_load 命令受缺少 PyYAML 阻塞。

### B2. survival_prediction_mainmoe_uni2.sh

- 为 A2 完成版完整副本，仅 --model_config 和 --cpt_name 两处不同：达成。
- --model_config model/config/surv_multimodal_mainmoe_uni2.yml：达成，grep 计数为 1。
- --cpt_name tcga_uni2：达成，grep 计数为 1。
- bash -n：通过。
- seeds 和全部超参与 A2 完成版一致：达成；逐字节比较通过。

### 白名单与禁止事项

- 最终 Git 状态恰好为 4 个白名单文件：达成。
- main_survival.py、loss、模型类、convert_uni2h_to_npj.py 及其他项目文件未修改：达成。
- seeds、lr、epochs、batch_size、hidden_size 等超参未修改：达成。
- 未执行 git commit / git push：达成。
- 未执行 ssh / scp，未访问 landau，未下载数据：达成。
- 未安装依赖：达成。

## 3. plan.md §4 全部命令与真实原始输出

以下输出来自清理交叉审核意外文件后的最终复跑。

### 3.1 Python YAML 验证

命令：

~~~bash
python3 -c "import yaml; a=yaml.safe_load(open('model/config/surv_multimodal_mainmoe.yml')); b=yaml.safe_load(open('model/config/surv_multimodal_mainmoe_uni2.yml')); assert a['modality']['rna']['path']=='data/RNA_embedding'; assert b['modality']['img']['path']=='data/tcga-dataset_uni2'; assert b['modality']['img']['feature_dim']==1536; assert a['network']==b['network']; print('YAML OK')"
~~~

原始输出：

~~~text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import yaml; a=yaml.safe_load(open('model/config/surv_multimodal_mainmoe.yml')); b=yaml.safe_load(open('model/config/surv_multimodal_mainmoe_uni2.yml')); assert a['modality']['rna']['path']=='data/RNA_embedding'; assert b['modality']['img']['path']=='data/tcga-dataset_uni2'; assert b['modality']['img']['feature_dim']==1536; assert a['network']==b['network']; print('YAML OK')
    ^^^^^^^^^^^
ModuleNotFoundError: No module named 'yaml'
~~~

退出码：1

### 3.2 Shell 语法验证

命令：

~~~bash
bash -n running_scripts/survival_prediction_mainmoe.sh && bash -n running_scripts/survival_prediction_mainmoe_uni2.sh && echo "SH OK"
~~~

原始输出：

~~~text
SH OK
~~~

退出码：0

### 3.3 BLCA 断言

命令：

~~~bash
grep -c 'cancer_types="BLCA"' running_scripts/survival_prediction_mainmoe.sh
~~~

原始输出：

~~~text
1
~~~

退出码：0

### 3.4 GPU 断言

命令：

~~~bash
grep -c 'gpu_id=0$' running_scripts/survival_prediction_mainmoe.sh
~~~

原始输出：

~~~text
1
~~~

退出码：0

### 3.5 原始特征 checkpoint 断言

命令：

~~~bash
grep -c 'cpt_name tcga_orig' running_scripts/survival_prediction_mainmoe.sh
~~~

原始输出：

~~~text
1
~~~

退出码：0

### 3.6 UNI2 checkpoint 断言

命令：

~~~bash
grep -c 'cpt_name tcga_uni2' running_scripts/survival_prediction_mainmoe_uni2.sh
~~~

原始输出：

~~~text
1
~~~

退出码：0

### 3.7 UNI2 配置路径断言

命令：

~~~bash
grep -c 'surv_multimodal_mainmoe_uni2.yml' running_scripts/survival_prediction_mainmoe_uni2.sh
~~~

原始输出：

~~~text
1
~~~

退出码：0

### 3.8 Git 状态

命令：

~~~bash
git -C /Users/wuhao/Desktop/NPJ status --porcelain
~~~

原始输出：

~~~text
 M model/config/surv_multimodal_mainmoe.yml
 M running_scripts/survival_prediction_mainmoe.sh
?? model/config/surv_multimodal_mainmoe_uni2.yml
?? running_scripts/survival_prediction_mainmoe_uni2.sh
~~~

退出码：0

## 4. PyYAML 缺失后的替代验证与原始输出

### 4.1 plan.md 指定的 Python 文本输出目检

命令：

~~~bash
python3 -c "print(open('model/config/surv_multimodal_mainmoe.yml').read()); print(open('model/config/surv_multimodal_mainmoe_uni2.yml').read())"
~~~

原始输出：

~~~text
modality:
  img:
    modality_name: img
    path: data/tcga-dataset
    feature_dim: 2048
    

  text:
    modality_name: text
    # path: data/text_embeddings/TEXT_EMBEDDING
    path: data/text_embeddings
    feature_dim: 768

  rna:
    modality_name: rna
    # path: data/RNA_embedding
    path: data/RNA_embedding
    feature_dim: 256

network_type: MainModalityMoE 


task_type: surv
#cancer_types: BRCA_BLCA_LUAD
cancer_types: BLCA
img_select: all
network:
  hidden_size: 32
  dropout_rate: 0.2
  pred_dim: 4 #same with time bin
  mlp_ratio: 2
  n_token: 128
  n_backbone: 1
  num_experts: 1
# network:
#   hidden_size: 64
#   dropout_rate: 0.5
#   pred_dim: 4
#   mlp_ratio: 4
#   n_token: 128
#   n_backbone: 2
#   num_experts: 4
#   topk: 1

modality:
  img:
    modality_name: img
    path: data/tcga-dataset_uni2
    feature_dim: 1536
    

  text:
    modality_name: text
    # path: data/text_embeddings/TEXT_EMBEDDING
    path: data/text_embeddings
    feature_dim: 768

  rna:
    modality_name: rna
    # path: data/RNA_embedding
    path: data/RNA_embedding
    feature_dim: 256

network_type: MainModalityMoE 


task_type: surv
#cancer_types: BRCA_BLCA_LUAD
cancer_types: BLCA
img_select: all
network:
  hidden_size: 32
  dropout_rate: 0.2
  pred_dim: 4 #same with time bin
  mlp_ratio: 2
  n_token: 128
  n_backbone: 1
  num_experts: 1
# network:
#   hidden_size: 64
#   dropout_rate: 0.5
#   pred_dim: 4
#   mlp_ratio: 4
#   n_token: 128
#   n_backbone: 2
#   num_experts: 4
#   topk: 1

~~~

退出码：0

### 4.2 Ruby YAML 完整语义等价验证

验证内容：以 HEAD 中的主 YAML 为基线，只施加 A1 两个路径变更后比较主 YAML；再只施加 B1 两个 img 变更后比较 UNI2 YAML。

原始输出：

~~~text
YAML semantic equality OK
~~~

退出码：0

### 4.3 四文件逐字节派生验证

验证内容：分别证明 A1=2 次替换、A2=3 次替换、B1=2 次替换、B2=2 次替换，且实际文件与预期字节完全一致。

原始输出：

~~~text
BYTE-EXACT OK: A1=2 replacements, A2=3, B1=2, B2=2
~~~

退出码：0

### 4.4 Diff 与白名单精确集合验证

原始输出：

~~~text
DIFF/CHECK + WHITELIST OK
~~~

退出码：0

### 4.5 文件模式一致性

原始输出：

~~~text
model/config/surv_multimodal_mainmoe.yml 644
model/config/surv_multimodal_mainmoe_uni2.yml 644
running_scripts/survival_prediction_mainmoe.sh 644
running_scripts/survival_prediction_mainmoe_uni2.sh 644
~~~

退出码：0

## 5. 遇到的问题

### Bug Post-Mortem 1：计划指定 Python YAML 命令失败

- **现象**: plan.md §4 第一条命令报 ModuleNotFoundError: No module named 'yaml'，退出码为 1。
- **根因**: 当前本机 python3 未安装 PyYAML；命令在 import yaml 阶段终止，未进入 YAML 文件解析或断言。
- **修复**: 遵守“不得安装依赖”，不修改环境；按 plan.md 回退到 Python 文本输出目检，并增加系统 Ruby YAML.safe_load 完整语义比较和逐字节预期内容比较。
- **Prevention Rule**: 后续同类任务先只读检查测试依赖；依赖缺失且禁止安装时，必须保留原命令真实失败，并明确区分“指定命令通过”和“替代内容验证通过”。

### Bug Post-Mortem 2：只读交叉审核 Agent 越界写文件

- **现象**: 被明确限制为只读的 decision-reviewer 在 NPJ 仓库根创建了白名单外的 codex_notes.md、codex_result.md。
- **根因**: 审查 Agent 无视只读和路径约束，错误推断用户允许在仓库根写交付文档。
- **修复**: 立即中断该 Agent；利用初始干净工作树、文件出生时间和未跟踪状态确认来源；删除且只删除这两个本次新建的意外文件；重新复跑 §4 和白名单精确集合断言。最终两文件均不存在。
- **Prevention Rule**: 严格白名单任务不再将交叉审核交给可能自行落盘的通用 Agent；如必须调用，在调用前后立即比较完整 Git 状态，发现越界即中断并恢复基线。

## 6. 未尽事项

- 计划指定的 Python + PyYAML 命令本身仍为退出码 1。只有在已具备 PyYAML 的环境中原样复跑，才能获得 YAML OK；本次明确禁止安装依赖，因此未处理环境。
- 未执行 landau 部署、冒烟测试、main_survival.py 修改、git commit 或 git push；这些均属于 plan.md 明确排除或 Claude 后续负责的范围，不是本次遗漏。
- 4 个白名单目标文件没有其他未尽事项。
