请完成独立代码复审并给出结构化最终结论。这是上一轮唯一必要项的修复复审，不开展新的科研方案。只读工具可用，不执行命令或改文件，不伪造工具记录。
上轮唯一必要项为公共runtime.main运行记录流程缺真实执行覆盖。已新增tests/test_shared_runtime_main.py，真正调用main和模型保存/重载/plots/CSV/metrics/manifest，epoch与prediction数值受控，仅验证产物事务；数值等价由既有epoch parity另证。两seed完整流程+3种产物碰撞，总4用例。
本轮额外：明确I02缺配置/shared缺network映射错误；I02移除config.yaml无效展示参数重复表，仅runtime生效，拒绝误写顶层training/model。没有模型计算、权重键、正式协议变更。补4项配置/拒绝测试。最新v8完整CPU pytest已在工具实际输出中观察到186 passed,6 skipped,1 warning in14.35s；无GPU无真实患者训练。完整v8日志与22条CLI终态正在因SSH临时超时取回，没把未完成CLI当作通过；切换门必须独立查完整记录及本地与candidate hash。
上轮limitation中I02非population创建pending不成立：candidate-v6已有main第一行if compensator != population raise ValueError，尚未创建任何资产。附真实代码及新增拒绝测试。Dm evaluation是声明性字段，评测需显式m1；checkpoint历史命名不含bin_mode，结果路径不同，否则拒绝，不改科研协议。
请审查必要修复是否正确；PASS只代表代码增量必要项闭环，不代表测试/资产门跳过，根目录仍未切换。最后必须提交JSON verdict/required_changes/limitations。
上轮审查原件：
{
  "verdict": "REVISE",
  "required_changes": [
    "为共享入口 src/trimodalsurv/training/runtime.py 的 main() 增加一个 CPU、合成数据、不触碰真实患者数据与 GPU 的真实执行测试，覆盖本轮新增的 preflight_training_outputs → start_run_record(pending) → plots 目录独占创建 → 预测 CSV 以 mode='x' 写出 → dump_results → finalize_run_record(completion) 全链路，并断言：预测/指标/plots 路径与 checkpoint 同一 seed+完整 task 身份、已存在产物被 FileExistsError 拒绝、completion.json 中 checkpoint 与产物 sha256 自洽。现状是全仓仅 I02 的 main 有真实执行夹具（experiments/I02_population_prototypes/tests/test_population_early_stopping.py:125），而 I01/I03/I04 全部经 runtime.main 运行，该段新代码零执行覆盖，失败点位于训练完成之后，会丢失整轮结果。"
  ],
  "limitations": [
    "I02 非 population 分支会调用 start_run_record 但永不 finalize，且该分支本就不写预测 CSV/指标（旧行为），导致已完成运行长期停在 pending 状态。",
    "F12 的‘缺 model/gpu 配置即显式报错、提示完整 checkout’只加在共享 runtime.parsing_args，experiments/I02_population_prototypes/train.py 的解析器未同步，缺配置时仍是 YmlConfig 的原始 FileNotFoundError。",
    "runtime.parsing_args 的 model_constraints 校验直接索引 model_document['network']，model_config 缺该节时抛 KeyError 而非明确契约错误。",
    "178 passed / 6 skipped、22 条 CLI 预检、real/synthetic/epoch parity 均为远端 candidate-v6 副本产物；本次审阅仅有 Read/Glob/Grep，无法重算本地文件 sha256 验证工作树与被测候选一致，该一致性由 check_cutover_gate.py:13 在切换前重算 candidate-v6-manifest 覆盖。",
    "I03 config.yaml 的 evaluation 段目前只被 runtime 校验、无入口实际消费，属声明性记录；Dm 复用 D checkpoint 的语义靠 README 与 provenance 约束，而非代码强制。",
    "checkpoint 文件名不含 bin_mode，d0 与 dq0 在同一 result_path 下身份相同（CLI 证据可见），新 preflight 会在第二次运行时拒绝；此为历史命名合同的既有冲突，本轮按要求未改动。"
  ]
}
### tests/test_shared_runtime_main.py
```diff
--- v6/tests/test_shared_runtime_main.py
+++ v8/tests/test_shared_runtime_main.py
@@ -0,0 +1,150 @@
+"""公共 main 的 CPU 产物事务验收；受控 epoch/预测，不是数值对拍。
+
+真正执行 main、模型构造、checkpoint 保存/严格重载、绘图、CSV、结果 JSON、
+运行来源和完成记录。数据与分数使用合成替身；数值等价另由 epoch parity 验证。
+"""
+import hashlib
+import json
+from pathlib import Path
+from types import SimpleNamespace
+from unittest.mock import patch
+
+import pytest
+import torch
+from torch.utils.data import TensorDataset
+
+from trimodalsurv.training import runtime
+from trimodalsurv.config import training_artifact_paths
+
+
+def _sha(path):
+    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
+
+
+class CPUAccelerator:
+    """仅为隔离 Accelerate 全局混精度状态；不替换 main 的产物分支。"""
+    is_main_process = True
+
+    def __init__(self, **kwargs):
+        assert kwargs == {'mixed_precision': 'bf16'}
+
+    def prepare(self, *objects):
+        return objects
+
+
+@pytest.fixture
+def main_fixture(tmp_path, monkeypatch):
+    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
+    monkeypatch.setattr(torch.cuda, 'device_count', lambda: 0)
+    monkeypatch.delenv('FORMAL_RUN', raising=False)
+    label = tmp_path / 'synthetic-label.csv'
+    label.write_text('patient_id,split\nsynthetic,fixture\n')
+    config = tmp_path / 'synthetic-model.json'
+    config.write_text(json.dumps({'fixture': '4-dimensional, 3-modalities'}))
+    gpu = tmp_path / 'gpu.json'
+    gpu.write_text(json.dumps({'pin_memory': False, 'persistent_workers': False}))
+
+    class FixtureConfig:
+        def __init__(self, path):
+            assert Path(path) == config
+            self.obj = SimpleNamespace(
+                modality={name: SimpleNamespace(feature_dim=4, path=str(tmp_path / name))
+                          for name in ('img', 'rna', 'text')},
+                task_type='surv', img_select='random',
+                network=SimpleNamespace(pred_dim=4, n_token=3))
+
+        def parse_to_modality(self, value):
+            return value
+
+    def args(seed=123):
+        return runtime.parsing_args([
+            '--network_type', 'NPJC', '--compensator', 'none', '--bin_mode', 'author',
+            '--hidden_size', '16', '--epochs', '1', '--batch_size', '2', '--num_workers', '0',
+            '--cancer_types', 'A', '--seed', str(seed), '--cpt_name', 'artifact-contract',
+            '--report_label_path', str(label), '--model_config', str(config), '--gpu_config', str(gpu),
+            '--result_path', str(tmp_path / 'out'), '--run_record_root', str(tmp_path / 'records')])
+
+    monkeypatch.setattr(runtime, 'YmlConfig', FixtureConfig)
+    monkeypatch.setattr(runtime, 'Accelerator', CPUAccelerator)
+    return args, FixtureConfig, label
+
+
+def test_real_main_artifact_transaction_two_seeds(tmp_path, main_fixture):
+    args_factory, config_factory, label = main_fixture
+    torch.set_num_threads(1)
+    produced = []
+    for seed in (123, 132):
+        args = args_factory(seed)
+        runtime.set_seed(seed)
+        calls = []
+        dataset = TensorDataset(torch.zeros(2, 1))
+
+        def controlled_epoch(model, criterion, optimizer, loader, epoch, **kwargs):
+            calls.append(kwargs['training'])
+            manifests = list((tmp_path / 'records').glob('*/checkpoint_manifest.json'))
+            pending = [p for p in manifests if not (p.parent / 'audit/completion.json').exists()]
+            assert len(pending) == 1
+            assert json.loads(pending[0].read_text())['status'] == 'pending'
+            # 稳定触发真实 checkpoint 保存；本测试不声称优化数值等价。
+            return {'loss': 0.4, 'c-index': 0.6, 'metric': 0.6}
+
+        def controlled_prediction(*objects, **kwargs):
+            return ({'loss': 0.3, 'c-index': 0.6, 'metric': 0.6},
+                    {'patient_id': ['synthetic-0', 'synthetic-1'], 'idx': [0, 1],
+                     'cancer_type': ['A', 'A'], 'risk': [-1.0, -2.0],
+                     'time': [1.0, 2.0], 'censorship': [0.0, 1.0]})
+
+        original_csv = runtime.pd.DataFrame.to_csv
+        csv_modes = []
+
+        def csv_with_mode_check(frame, *positional, **kwargs):
+            csv_modes.append(kwargs.get('mode'))
+            return original_csv(frame, *positional, **kwargs)
+
+        with patch.object(runtime, 'get_dataset_tcga_sur', return_value=(dataset, dataset, dataset)), \
+             patch.object(runtime, 'finetune_epoch', controlled_epoch), \
+             patch.object(runtime, 'prediction', controlled_prediction), \
+             patch.object(runtime.pd.DataFrame, 'to_csv', csv_with_mode_check):
+            runtime.main(args)
+        assert calls == [True, False]
+        assert csv_modes == ['x']
+        dumper = runtime.ModelDumper(args.result_path, seed, args.cpt_name,
+            config_factory(args.model_config).obj.modality, args, config_factory(args.model_config))
+        paths = training_artifact_paths(dumper.task_path_str)
+        assert paths['predictions'].parent.name == str(seed)
+        assert paths['predictions'].name == f'test_pred_and_label_{Path(dumper.task_path_str).name}.csv'
+        assert (paths['plots'] / 'training_curves.png').is_file()
+        assert json.loads(paths['metrics'].read_text()) == {'loss': 0.3, 'c-index': 0.6}
+        with pytest.raises(FileExistsError):
+            dumper.dump_results({'must_not_overwrite': 1})
+        completions = [json.loads(path.read_text()) for path in (tmp_path / 'records').glob('*/audit/completion.json')]
+        completion = next(value for value in completions if value['checkpoint']['path'] == str(dumper.model_path.resolve()))
+        assert completion['status'] == 'complete'
+        assert completion['checkpoint']['sha256'] == _sha(dumper.model_path)
+        assert len(completion['artifacts']) == 2
+        for entry in completion['artifacts']:
+            assert entry['source']['sha256'] == entry['copy']['sha256'] == _sha(entry['copy']['path'])
+        produced.append(set(paths.values()))
+        # 已有运行应在构建 Dataset 前失败，不能再开训练再发现冲突。
+        with patch.object(runtime, 'get_dataset_tcga_sur', side_effect=AssertionError('must not load data')):
+            with pytest.raises(FileExistsError):
+                runtime.main(args_factory(seed))
+    assert produced[0].isdisjoint(produced[1])
+
+
+@pytest.mark.parametrize('kind', ['predictions', 'metrics', 'plots'])
+def test_real_main_rejects_existing_artifact_before_data(tmp_path, main_fixture, kind):
+    args_factory, config_factory, _ = main_fixture
+    args = args_factory()
+    config = config_factory(args.model_config)
+    dumper = runtime.ModelDumper(args.result_path, args.seed, args.cpt_name, config.obj.modality, args, config)
+    path = training_artifact_paths(dumper.task_path_str)[kind]
+    if kind == 'plots':
+        path.mkdir()
+    else:
+        path.write_text('preserved')
+    with patch.object(runtime, 'get_dataset_tcga_sur', side_effect=AssertionError('must not load data')):
+        with pytest.raises(FileExistsError, match='拒绝覆盖已有运行产物'):
+            runtime.main(args)
+    assert not (tmp_path / 'records').exists()
+    assert path.is_dir() if kind == 'plots' else path.read_text() == 'preserved'

```

### tests/test_experiment_presets.py
```diff
--- v6/tests/test_experiment_presets.py
+++ v8/tests/test_experiment_presets.py
@@ -75,3 +75,36 @@
 def test_explicit_missing_checkout_config_has_clear_error(tmp_path):
     with pytest.raises(ValueError, match='完整 repo checkout'):
         parse(I03, 'D', '--model_config', str(tmp_path / 'absent.yml'))
+
+
+def test_missing_network_mapping_has_clear_error(tmp_path):
+    target = tmp_path / 'model.json'
+    target.write_text('{}')
+    with pytest.raises(ValueError, match='network 配置映射'):
+        parse(I03, 'D', '--model_config', str(target))
+
+
+def test_i02_missing_checkout_config_has_clear_error(tmp_path):
+    from experiments.I02_population_prototypes.train import parsing_args
+    with pytest.raises(ValueError, match='完整 repo checkout'):
+        parsing_args(['--bin_mode', 'author', '--model_config', str(tmp_path / 'absent.yml')])
+
+
+def test_i02_rejects_non_population_before_any_side_effect():
+    from experiments.I02_population_prototypes.train import main
+    with pytest.raises(ValueError, match='I02 train requires population'):
+        main(SimpleNamespace(compensator='none'))
+
+
+def test_i02_has_one_effective_parameter_section(tmp_path):
+    from experiments.I02_population_prototypes.train import parsing_args
+    path = ROOT / 'experiments/I02_population_prototypes/config.yaml'
+    doc = json.loads(path.read_text())
+    assert set(doc) == {'experiment', 'provenance', 'runtime'}
+    args = parsing_args(['--config', str(path)])
+    assert args.hidden_size == 256 and args.epochs == 100 and args.prototype_k == 8
+    doc['training'] = {'epochs': 3}
+    bad = tmp_path / 'ambiguous.json'
+    bad.write_text(json.dumps(doc))
+    with pytest.raises(ValueError, match='生效参数仅放 runtime'):
+        parsing_args(['--config', str(bad)])

```

### src/trimodalsurv/training/runtime.py
```diff
--- v6/src/trimodalsurv/training/runtime.py
+++ v8/src/trimodalsurv/training/runtime.py
@@ -150,6 +150,8 @@
     if model_constraints:
         with Path(args.model_config).open(encoding="utf-8") as handle:
             model_document = yaml.safe_load(handle)
+        if not isinstance(model_document, dict) or not isinstance(model_document.get("network"), dict):
+            raise ValueError("model_config 必须包含 network 配置映射")
         for key, expected in model_constraints.items():
             actual = model_document["network"].get(key)
             if actual != expected:

```

### experiments/I02_population_prototypes/train.py
```diff
--- v6/experiments/I02_population_prototypes/train.py
+++ v8/experiments/I02_population_prototypes/train.py
@@ -100,6 +100,10 @@
     if config_args.config is not None:
         from trimodalsurv.config import read_config
         content = read_config(config_args.config)
+        if 'runtime' in content:
+            extra = set(content) - {'experiment', 'provenance', 'runtime'}
+            if extra:
+                raise ValueError(f'未知实验配置字段: {sorted(extra)}；生效参数仅放 runtime')
         overrides = content.get('runtime', content)
         unknown = set(overrides) - {a.dest for a in parser._actions}
         if unknown:
@@ -110,10 +114,14 @@
     args = parser.parse_args(argv)
     if args.bin_mode != 'author':
         parser.error('I02 requires explicit author bin_mode')
-    for name in ('gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path', 'run_record_root'):
+    for name in ('config', 'gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path', 'run_record_root'):
         value = getattr(args, name, None)
         if value:
             setattr(args, name, str(Path(value).expanduser().resolve()))
+    for name in ('gpu_config', 'model_config'):
+        value = getattr(args, name)
+        if not value or not Path(value).is_file():
+            raise ValueError(f'缺少 {name}: {value}；运行入口须使用完整 repo checkout，或显式提供配置路径')
     if args.early_stopping_patience < 0:
         parser.error('--early-stopping-patience must be nonnegative')
     if args.early_stopping_patience and (args.compensator != 'population' or args.task_type != 'surv'):

```

### experiments/I02_population_prototypes/config.yaml
```diff
--- v6/experiments/I02_population_prototypes/config.yaml
+++ v8/experiments/I02_population_prototypes/config.yaml
@@ -1,25 +1,5 @@
 {
   "experiment": "I02_population_prototypes",
-  "bin_mode": "author",
-  "model": {
-    "network_type": "NPJC",
-    "compensator": "population",
-    "prototype_k": 8,
-    "hidden_size": 256,
-    "pred_dim": 4,
-    "dropout_rate": 0.1,
-    "mlp_ratio": 4,
-    "n_backbone": 1,
-    "n_head": 4
-  },
-  "training": {
-    "epochs": 100,
-    "early_stopping_patience": 15,
-    "lr": 0.0001,
-    "batch_size": 32,
-    "modality_dropout": 0.0,
-    "precision": "float32"
-  },
   "provenance": "684e formal-config.json + main_survival.py actual constructor defaults; historical original preserved",
   "runtime": {
     "network_type": "NPJC",

```

I02 main当前入口：

    if args.compensator != 'population':
        raise ValueError('I02 train requires population')
    if getattr(args, 'dry_run', False):
        from tr