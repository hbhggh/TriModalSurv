请以 Claude 独立审阅本次全项目重构增量。上一轮结论 REVISE，F1–F12下列逐项修复。只审阅，不执行命令、不修改文件。本次不训练真实患者、不GPU、不安装。请判断这些必要项是否真正闭环，检查新增run记录是否改变模型计算或违反不覆盖历史合同。最后给 JSON {verdict: PASS|REVISE, required_changes:[], limitations:[]}。不要因测试绿而忽略入口问题，也不要要求未经授权的新科研方案/训练。根切换尚未执行；代码通过后才可逆移动并另交最终资产证据审阅。
F1/F2: population先解析→set_seed→run；真实scripts分发测试含配置-only，显式CLI优先。
F3:根/非根CLI预检完整JSON相等，增加I03/I04显式preset和I02公共入口。
F4:experiments-report.md已实际落盘，末尾附全文。
F5:actual_model_spec对fusion实际类名回读；NPJC没有fusion时不改变I01 exact spec。
F6:runtime_source_fingerprints冻结src/实验/脚本保守源码超集+实际配置，I02标签指纹也入。
F7:real worker各侧evidence/imports及环境JSON已取回，worker manifest22文件；原患者ID/hash指纹保留，不在审阅摘要中泄露患者数据。
F8:bin_mode等号形式和不重复追加已有回归。
F9:调用真实runtime.load_model与I03工厂比较类型、组合、state_dict shape/dtype。
F10:I03/I04配置可显式--preset，不自动挑选；Dm evaluation m1仍复用D ckpt，不假造训练机制。
F11:progress已更新阶段，未切换/未复审明确。
F12:明确完整checkout，缺model/gpu配置报错。src安装包只库。
额外：新运行独占run目录记录pending→completion，真实参数及来源清单齐全；checkpoint命名不变，预测CSV与plots按seed+完整task身份隔离，产物先预检拒绝已有，主进程独占写。不重训历史；历史best_metric=0等问题保留科研语义，不借重构改结果。
验证范围：I01/I02模型及填补算子未变，旧新32患者16格最大误差0；7组合成forward/loss/grad/optimizer+严格重载最大误差0；25个I02strict load通过。此次改入口/记录，新增相关测试，旧6skip不增skip掩盖。
以下是冻结v3到当前完整源码差异及新增测试，后附实际验证证据。

### src/trimodalsurv/config.py
```diff
--- v3/src/trimodalsurv/config.py
+++ current/src/trimodalsurv/config.py
@@ -5,6 +5,9 @@
 import copy
 import hashlib
 import json
+import sys
+import uuid
+from datetime import datetime, timezone
 from pathlib import Path
 
 
@@ -54,7 +57,7 @@
     dropouts = {float(model.m_projector[mm][2].p) for mm in model.modalities}
     if len(dropouts) != 1:
         raise ValueError('模态投影 dropout 不一致')
-    return {
+    spec = {
         'network_type': type(model).__name__,
         'compensator': 'none' if model.compensator is None else type(model.compensator).__name__,
         'hidden_size': hidden,
@@ -65,6 +68,9 @@
         'n_head': int(first.self_attn.num_heads),
         'modality_order': list(model.modalities),
     }
+    if hasattr(model, 'fusion'):
+        spec['fusion'] = type(model.fusion).__name__
+    return spec
 
 
 def _jsonable(value):
@@ -101,3 +107,109 @@
     with path.open('x', encoding='utf-8') as handle:
         json.dump(_jsonable(value), handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
         handle.write('\n')
+
+
+def runtime_source_fingerprints(args, *, experiment_dir=None):
+    """冻结活动源码闭包与实际配置；不依赖 Git 是否已提交。"""
+    root = Path(__file__).resolve().parents[2]
+    paths = set((root / 'src').rglob('*.py'))
+    paths.update((root / 'scripts').glob('*.py'))
+    # 所有活动实验的 Python 文件形成保守超集，涵盖组合工厂与生命周期。
+    for directory in (root / 'experiments').glob('*'):
+        if directory.is_dir() and directory.name != '_template':
+            paths.update(path for path in directory.glob('*.py'))
+    if experiment_dir is not None:
+        paths.update(Path(experiment_dir).glob('*.py'))
+    for name in ('config', 'model_config', 'gpu_config'):
+        value = getattr(args, name, None)
+        if value:
+            paths.add(Path(value).resolve())
+    entry = Path(sys.argv[0])
+    if entry.is_file():
+        paths.add(entry.resolve())
+    return [file_fingerprint(path) for path in sorted(paths)]
+
+
+def run_record_root(args, *, experiment_dir=None):
+    explicit = getattr(args, 'run_record_root', None)
+    if explicit:
+        return Path(explicit).expanduser().resolve()
+    if experiment_dir is not None:
+        return Path(experiment_dir).resolve() / 'results'
+    config = getattr(args, 'config', None)
+    if config:
+        parent = Path(config).resolve().parent
+        if parent.parent.name == 'experiments':
+            return parent / 'results'
+    # 无实验身份的通用入口不猜测创新 ID；与显式输出目录并置。
+    return Path(args.result_path).resolve() / 'results'
+
+
+def start_run_record(root, payload, *, checkpoint_path, modalities=None, run_id=None):
+    """只在真实启动时调用；目录独占，失败留下 pending，不伪装成功。"""
+    run_id = run_id or (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8])
+    if Path(run_id).name != run_id or run_id in {'.', '..'}:
+        raise ValueError('run_id 必须是单个目录名')
+    target = Path(root).resolve() / run_id
+    target.parent.mkdir(parents=True, exist_ok=True)
+    target.mkdir(exist_ok=False)
+    for name in ('raw', 'logs', 'audit'):
+        (target / name).mkdir()
+    write_resolved_config(target / 'resolved_config.yaml', payload)
+    write_resolved_config(target / 'source_manifest.json', {'files': payload['source_fingerprints']})
+    write_resolved_config(target / 'data_manifest.json', {
+        'inputs': payload['inputs'], 'modalities': modalities or {},
+        'feature_content_hash_status': '未扫描特征内容；仅记录实际输入位置和标签指纹',
+    })
+    write_resolved_config(target / 'checkpoint_manifest.json', {
+        'status': 'pending', 'path': str(Path(checkpoint_path).resolve()),
+        'completion_manifest': 'audit/completion.json',
+        'note': '本文件为启动记录；仅 completion.json 能证明正常结束及 checkpoint 内容',
+    })
+    with (target / 'analysis.md').open('x', encoding='utf-8') as handle:
+        handle.write('# 本次运行记录\n\n状态见 `audit/completion.json`。缺少完成证据表示尚未正常结束。\n'
+                     '旧 checkpoint 输出路径保持不变；本目录记录真实配置、来源及最终产物指纹。\n'
+                     '此页不生成科研结论，指标解释须基于本次原始结果。\n')
+    return target
+
+
+def finalize_run_record(run_dir, *, checkpoint_path, artifacts=()):
+    """正常结束时写一次完成证据；checkpoint 缺失或重复提交均拒绝。"""
+    target = Path(run_dir)
+    checkpoint = file_fingerprint(checkpoint_path)
+    copied = []
+    # 复制小型原始结果到独占 run；checkpoint 只留原位和 hash，不复制大权重。
+    for index, artifact in enumerate(artifacts):
+        source = Path(artifact).resolve()
+        destination = target / 'raw' / f'{index:02d}-{source.name}'
+        before = file_fingerprint(source)
+        with source.open('rb') as reader, destination.open('xb') as writer:
+            import shutil
+            shutil.copyfileobj(reader, writer)
+        after = file_fingerprint(destination)
+        if before['sha256'] != after['sha256']:
+            raise RuntimeError(f'产物复制校验失败: {source}')
+        copied.append({'source': before, 'copy': after})
+    write_resolved_config(target / 'audit' / 'completion.json', {
+        'status': 'complete', 'checkpoint': checkpoint, 'artifacts': copied,
+        'finished_at_utc': datetime.now(timezone.utc).isoformat(),
+    })
+
+
+def training_artifact_paths(task_path):
+    """与 checkpoint 同一 seed/配置身份；不采用跨 seed 的癌种级文件名。"""
+    task = Path(task_path)
+    return {'predictions': task.parent / f'test_pred_and_label_{task.name}.csv',
+            'metrics': task.parent / f'{task.name}_results.json',
+            'plots': task.parent / f'{task.name}_plots'}
+
+
+def preflight_training_outputs(task_path, checkpoint_path, *, training, sidecar):
+    paths = training_artifact_paths(task_path)
+    candidates = list(paths.values()) + [Path(sidecar)]
+    if training:
+        candidates.append(Path(checkpoint_path))
+    conflicts = [str(path) for path in candidates if path.exists() or path.is_symlink()]
+    if conflicts:
+        raise FileExistsError(f'拒绝覆盖已有运行产物: {conflicts}')
+    return paths

```

### src/trimodalsurv/training/runtime.py
```diff
--- v3/src/trimodalsurv/training/runtime.py
+++ current/src/trimodalsurv/training/runtime.py
@@ -50,6 +50,8 @@
 def parsing_args(argv=None):
     parser = argparse.ArgumentParser()
     parser.add_argument("--config", type=str, default=None, help="实验配置；显式CLI优先")
+    parser.add_argument("--preset", default=None, help="必须显式选择实验配置中的预设")
+    parser.add_argument("--run_record_root", default=None, help="独占运行记录目录的父目录")
     parser.add_argument("--dry_run", action="store_true", help="只解析配置和构造模型，不构建数据或写产物")
     parser.add_argument('--seed', type=int, default=123)
     parser.add_argument('--epochs', type=int, default=50)
@@ -83,12 +85,51 @@
 
     config_parser = argparse.ArgumentParser(add_help=False)
     config_parser.add_argument("--config")
+    config_parser.add_argument("--preset")
     preliminary, _ = config_parser.parse_known_args(argv)
+    model_constraints = {}
+    if preliminary.preset is not None and preliminary.config is None:
+        raise ValueError("--preset 必须与 --config 一起提供")
     if preliminary.config is not None:
         from trimodalsurv.config import read_config
-        overrides = read_config(preliminary.config)
-        overrides = overrides.get("runtime", overrides)
-        known = {action.dest for action in parser._actions}
+        document = read_config(preliminary.config)
+        known = {action.dest for action in parser._actions} - {"help", "config", "preset"}
+        structured = any(key in document for key in ("runtime", "presets", "model"))
+        if structured:
+            allowed = {"experiment", "provenance", "runtime", "bin_mode", "model", "presets", "evaluation"}
+            unknown = set(document) - allowed
+            if unknown:
+                raise ValueError(f"未知实验配置字段: {sorted(unknown)}")
+            overrides = dict(document.get("runtime", {}))
+            model = dict(document.get("model", {}))
+            if "pred_dim" in model:
+                model_constraints["pred_dim"] = model.pop("pred_dim")
+            overrides.update(model)
+            if "bin_mode" in document:
+                overrides["bin_mode"] = document["bin_mode"]
+            presets = document.get("presets", {})
+            if not isinstance(presets, dict):
+                raise ValueError("presets 必须是映射")
+            for name, values in presets.items():
+                if not isinstance(values, dict) or set(values) - known:
+                    raise ValueError(f"未知或无效预设字段: {name}")
+            if presets:
+                if preliminary.preset not in presets:
+                    raise ValueError(f"必须显式 --preset 选择: {sorted(presets)}")
+                overrides.update(presets[preliminary.preset])
+            elif preliminary.preset is not None:
+                raise ValueError("当前配置没有可选 preset")
+            # evaluation 仅是评测入口映射，禁止当作训练参数静默应用。
+            evaluation = document.get("evaluation", {})
+            if not isinstance(evaluation, dict) or set(evaluation) - set(presets):
+                raise ValueError("evaluation 必须引用已声明的 preset")
+            for name, values in evaluation.items():
+                if not isinstance(values, dict) or set(values) != {"arm"} or values["arm"] not in {"m0real", "m1"}:
+                    raise ValueError(f"未知或无效 evaluation 字段: {name}")
+        else:
+            overrides = dict(document)
+            if preliminary.preset is not None:
+                raise ValueError("当前配置没有可选 preset")
         unknown = set(overrides) - known
         if unknown:
             raise ValueError(f"未知运行配置字段: {sorted(unknown)}")
@@ -98,10 +139,25 @@
     args = parser.parse_args(argv)
     if args.bin_mode not in {"author", "train_quantile"}:
         raise ValueError("bin_mode 必须显式指定 author/train_quantile")
-    for name in ('gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path'):
+    for name in ('config', 'gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path', 'run_record_root'):
         value = getattr(args, name, None)
         if value:
             setattr(args, name, str(Path(value).expanduser().resolve()))
+    for name in ('gpu_config', 'model_config'):
+        value = getattr(args, name)
+        if value and not Path(value).is_file():
+            raise ValueError(f"缺少 {name}: {value}；运行入口须使用完整 repo checkout，或显式提供配置路径")
+    if model_constraints:
+        with Path(args.model_config).open(encoding="utf-8") as handle:
+            model_document = yaml.safe_load(handle)
+        for key, expected in model_constraints.items():
+            actual = model_document["network"].get(key)
+            if actual != expected:
+                raise ValueError(f"实验 model.{key}={expected!r} 与 model_config 实际值 {actual!r} 不一致")
+    # argparse 不检查 YAML 注入的非字符串默认 choices，因此显式验最终值。
+    for action in parser._actions:
+        if action.choices is not None and getattr(args, action.dest) not in action.choices:
+            raise ValueError(f"无效运行配置 {action.dest}={getattr(args, action.dest)!r}")
     return args
 
 
@@ -691,6 +747,10 @@
     device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
     gpu_config = resolve_gpu_config(args)
     model_config = YmlConfig(args.model_config)
+    model_dumper = ModelDumper(args.result_path, args.seed, args.cpt_name, model_config.obj.modality, args, model_config)
+    from trimodalsurv.config import preflight_training_outputs
+    artifacts = preflight_training_outputs(model_dumper.task_path_str, model_dumper.model_path,
+        training=args.train, sidecar=str(model_dumper.model_path) + '.resolved.json')
 
     # 解析modalities
     modality_config = {k: model_config.parse_to_modality(v) for k, v in model_config.obj.modality.items()}
@@ -786,19 +846,25 @@
         model, optimizer, train_loader, valid_loader, test_loader
     )
 
-    model_dumper = ModelDumper(args.result_path, args.seed, args.cpt_name, model_config.obj.modality, args, model_config)
 
     if args.train and Path(model_dumper.model_path).exists():
         raise FileExistsError(f"拒绝覆盖已有checkpoint: {model_dumper.model_path}")
-    from trimodalsurv.config import resolved_config, file_fingerprint, write_resolved_config
-    provenance = resolved_config(
-        args, _unwrap_model(model),
-        inputs=[file_fingerprint(args.report_label_path), file_fingerprint(args.model_config), file_fingerprint(args.gpu_config)],
-        checkpoints=[], sources=[file_fingerprint(Path(__file__))],
-    )
-    provenance['gpu_config'] = gpu_config
-    provenance['historical_training'] = {'status': '本次实际运行配置', 'optimizer': 'Adam', 'weight_decay': 1, 'mixed_precision': 'bf16'}
-    write_resolved_config(str(model_dumper.model_path) + '.resolved.json', provenance)
+    from trimodalsurv.config import (resolved_config, file_fingerprint, write_resolved_config,
+        runtime_source_fingerprints, run_record_root, start_run_record, finalize_run_record)
+    run_record = None
+    if accelerator.is_main_process:
+        provenance = resolved_config(
+            args, _unwrap_model(model),
+            inputs=[file_fingerprint(args.report_label_path), file_fingerprint(args.model_config), file_fingerprint(args.gpu_config)],
+            checkpoints=[], sources=runtime_source_fingerprints(args),
+        )
+        provenance['gpu_config'] = gpu_config
+        provenance['historical_training'] = {'status': '本次实际运行配置', 'optimizer': 'Adam', 'weight_decay': 1, 'mixed_precision': 'bf16'}
+        write_resolved_config(str(model_dumper.model_path) + '.resolved.json', provenance)
+        run_record = start_run_record(run_record_root(args), provenance,
+            checkpoint_path=model_dumper.model_path,
+            modalities={key: {'path': str(value.path), 'feature_dim': value.feature_dim}
+                        for key, value in modality_config.items()})
 
     best_metric = 0
     train_losses, val_losses, val_metrics = [], [], []
@@ -854,7 +920,9 @@
                 model_dumper.dump(model)
 
         # 绘制曲线
-        plot_metrics(train_losses, val_losses, val_metrics, save_dir='./plots')
+        if accelerator.is_main_process:
+            artifacts['plots'].mkdir(exist_ok=False)
+            plot_metrics(train_losses, val_losses, val_metrics, save_dir=str(artifacts['plots']))
 
     # ========== 测试 ==========
     model.load_state_dict(torch.load(model_dumper.model_path, weights_only=True))
@@ -870,13 +938,8 @@
         non_blocking=gpu_config['non_blocking'],
     )
 
-    # 保存为csv
-    network = args.network_type
-    cancer_types_str = args.cancer_types.replace("_", "-") if args.cancer_types != "None" else "all"
-    save_pred_csv = os.path.join(
-        args.result_path, 
-        f"test_pred_and_label_{network}_{cancer_types_str}.csv"
-    )
+    # 保存为与 checkpoint 同一身份的独占 CSV。
+    save_pred_csv = artifacts['predictions']
     df_save = pd.DataFrame({
         'patient_id': test_pred_info['patient_id'],
         'idx': test_pred_info['idx'],
@@ -885,8 +948,9 @@
         'survival_time': test_pred_info['time'],
         'censorship': test_pred_info['censorship']
     })
-    df_save.to_csv(save_pred_csv, index=False)
-    print(f"✅ Test prediction and label saved at {save_pred_csv}")
+    if accelerator.is_main_process:
+        df_save.to_csv(save_pred_csv, index=False, mode='x')
+        print(f"✅ Test prediction and label saved at {save_pred_csv}")
 
     # 打印并整理dump
     dump_dict = {}
@@ -896,7 +960,10 @@
             print(f"{kk}: {dump_dict[kk]:.2f}")
 
     # model_dumper.dump_json(test_metric)
-    model_dumper.dump_results(dump_dict)
+    if accelerator.is_main_process:
+        model_dumper.dump_results(dump_dict)
+        finalize_run_record(run_record, checkpoint_path=model_dumper.model_path,
+            artifacts=[save_pred_csv, model_dumper.task_path_str + '_results.json'])
 
 
 

```

### src/trimodalsurv/training/model_util.py
```diff
--- v3/src/trimodalsurv/training/model_util.py
+++ current/src/trimodalsurv/training/model_util.py
@@ -54,7 +54,7 @@
     def dump_results(self, dict_data):
         output_path = f"{self.task_path_str}_results.json"
         print("✅ Saving single result metrics to:", output_path)
-        with open(output_path, 'w') as fout:
+        with open(output_path, 'x') as fout:
             json.dump(dict_data, fout, indent=2)
 
     def load_results(self):

```

### experiments/I02_population_prototypes/train.py
```diff
--- v3/experiments/I02_population_prototypes/train.py
+++ current/experiments/I02_population_prototypes/train.py
@@ -62,6 +62,7 @@
 def parsing_args(argv=None):
     parser = argparse.ArgumentParser()
     parser.add_argument('--config', default=None)
+    parser.add_argument('--run_record_root', default=None)
     parser.add_argument('--dry_run', action='store_true')
     parser.add_argument('--bin_mode', choices=['author'], required=True)
     parser.add_argument('--seed', type=int, default=123)
@@ -109,7 +110,7 @@
     args = parser.parse_args(argv)
     if args.bin_mode != 'author':
         parser.error('I02 requires explicit author bin_mode')
-    for name in ('gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path'):
+    for name in ('gpu_config', 'model_config', 'report_label_path', 'result_path', 'pretrain_path', 'run_record_root'):
         value = getattr(args, name, None)
         if value:
             setattr(args, name, str(Path(value).expanduser().resolve()))
@@ -234,6 +235,10 @@
     device = accelerator.device if population else torch.device('cuda' if torch.cuda.is_available() else 'cpu')
     gpu_config = resolve_gpu_config(args)
     model_config = YmlConfig(args.model_config)
+    model_dumper = ModelDumper(args.result_path, args.seed, args.cpt_name, model_config.obj.modality, args, model_config)
+    from trimodalsurv.config import preflight_training_outputs
+    preflight_training_outputs(model_dumper.task_path_str, model_dumper.model_path,
+        training=args.train, sidecar=model_dumper.task_path_str + '.resolved.json')
 
     # 解析modalities
     modality_config = {k: model_config.parse_to_modality(v) for k, v in model_config.obj.modality.items()}
@@ -325,20 +330,27 @@
         bank_loader = accelerator.prepare(make_population_loader(
             train_dataset, args.batch_size, loader_kwargs, seed=args.seed))
 
-    model_dumper = ModelDumper(args.result_path, args.seed, args.cpt_name, model_config.obj.modality, args, model_config)
-
-    from trimodalsurv.config import resolved_config, write_resolved_config, file_fingerprint
+
+    from trimodalsurv.config import (resolved_config, write_resolved_config, file_fingerprint,
+        runtime_source_fingerprints, run_record_root, start_run_record, finalize_run_record)
     target = Path(model_dumper.task_path_str + '.resolved.json')
+    run_record = None
     def persist_configuration():
+        nonlocal run_record
         target.parent.mkdir(parents=True, exist_ok=True)
         unwrapped = accelerator.unwrap_model(model)
-        payload = resolved_config(args, unwrapped, inputs=[], checkpoints=[],
-            sources=[file_fingerprint(__file__), file_fingerprint(Path(__file__).with_name('model.py')),
-                     file_fingerprint(Path(__file__).with_name('runtime.py'))])
+        payload = resolved_config(args, unwrapped,
+            inputs=[file_fingerprint(args.report_label_path), file_fingerprint(args.model_config), file_fingerprint(args.gpu_config)],
+            checkpoints=[], sources=runtime_source_fingerprints(args, experiment_dir=Path(__file__).parent))
         payload['effective_gpu_config'] = gpu_config
         payload['execution'] = {'precision': 'float32', 'optimizer': 'Adam', 'weight_decay': 1,
                                 'prototype_k': args.prototype_k, 'train_compensation': False}
+        payload['historical_training'] = {'status': '本次实际运行配置；不推填历史训练参数'}
         write_resolved_config(target, payload)
+        run_record = start_run_record(run_record_root(args, experiment_dir=Path(__file__).parent),
+            payload, checkpoint_path=model_dumper.model_path,
+            modalities={key: {'path': str(Path(value.path).resolve()), 'feature_dim': value.feature_dim}
+                        for key, value in modality_config.items()})
     main_process_call(accelerator, persist_configuration)
     best_metric = float('-inf') if population else 0
     early_stopper = PopulationEarlyStopping(getattr(args, 'early_stopping_patience', 0)) if population else None
@@ -402,9 +414,10 @@
         # 绘制曲线
         if population:
             _, plots_path = _population_artifact_paths(model_dumper)
-            main_process_call(accelerator, lambda: plot_metrics(
-                train_losses, val_losses, val_metrics,
-                save_dir=str(plots_path)))
+            def save_population_plots():
+                plots_path.mkdir(exist_ok=False)
+                plot_metrics(train_losses, val_losses, val_metrics, save_dir=str(plots_path))
+            main_process_call(accelerator, save_population_plots)
         else:
             plot_metrics(train_losses, val_losses, val_metrics, save_dir='./plots')
 
@@ -431,8 +444,10 @@
                 'patient_id': test_pred_info['patient_id'], 'idx': test_pred_info['idx'],
                 'cancer_type': test_pred_info['cancer_type'], 'risk': test_pred_info['risk'],
                 'survival_time': test_pred_info['time'], 'censorship': test_pred_info['censorship'],
-            }).to_csv(output, index=False)
+            }).to_csv(output, index=False, mode='x')
             model_dumper.dump_results({k: v for k, v in test_metric.items() if k != 'metric'})
+            finalize_run_record(run_record, checkpoint_path=model_dumper.model_path,
+                artifacts=[output, model_dumper.task_path_str + '_results.json'])
         main_process_call(accelerator, save_population_results)
         return
 

```

### scripts/main_survival.py
```diff
--- v3/scripts/main_survival.py
+++ current/scripts/main_survival.py
@@ -9,10 +9,18 @@
     import argparse
     probe = argparse.ArgumentParser(add_help=False)
     probe.add_argument('--compensator')
+    probe.add_argument('--config')
     selected, _ = probe.parse_known_args()
-    if selected.compensator == 'population':
+    compensator = selected.compensator
+    if compensator is None and selected.config is not None:
+        from trimodalsurv.config import read_config
+        content = read_config(selected.config)
+        compensator = content.get('runtime', content).get('compensator')
+    if compensator == 'population':
         from experiments.I02_population_prototypes.train import parsing_args, main as run
-        return run(parsing_args())
+        args = parsing_args()
+        runtime.set_seed(args.seed)
+        return run(args)
     args = runtime.parsing_args()
     runtime.set_seed(args.seed)
     if args.compensator == 'capl':

```

### scripts/train_launcher.py
```diff
--- v3/scripts/train_launcher.py
+++ current/scripts/train_launcher.py
@@ -376,6 +376,9 @@
             raise ValueError(
                 f"plan.runs[{index}] 的自定义 arm 必须显式给出 network_type/compensator"
             )
+        extra_args = _parse_extra_args(raw.get("extra_args"))
+        if not _has_option(extra_args, "--bin_mode") and "bin_mode" in raw:
+            extra_args += ("--bin_mode", str(raw["bin_mode"]))
         spec = RunSpec(
             name=str(raw["name"]),
             arm=arm,
@@ -383,7 +386,7 @@
             compensator=str(compensator),
             cancer=str(raw["cancer"]).upper(),
             seed=int(raw["seed"]),
-            extra_args=_parse_extra_args(raw.get("extra_args")) + (() if "--bin_mode" in _parse_extra_args(raw.get("extra_args")) else (("--bin_mode", str(raw["bin_mode"])) if "bin_mode" in raw else ())),
+            extra_args=extra_args,
         )
         _validate_spec(spec)
         runs.append(spec)
@@ -469,7 +472,7 @@
             raise ValueError('early stopping requires population')
         command.extend(['--early-stopping-patience', str(args.early_stopping_patience)])
     command.extend(spec.extra_args)
-    if "--bin_mode" not in command:
+    if not _has_option(command, "--bin_mode"):
         raise ValueError("运行必须显式指定 bin_mode（author/train_quantile）")
     return command
 

```

### experiments/I03_npj_d_dm_e1/config.yaml
```diff
--- v3/experiments/I03_npj_d_dm_e1/config.yaml
+++ current/experiments/I03_npj_d_dm_e1/config.yaml
@@ -9,14 +9,12 @@
     "D": {
       "network_type": "MainModalityMoE",
       "fusion_type": "mean",
-      "compensator": "none",
-      "eval_arm": "m0real"
+      "compensator": "none"
     },
     "Dm": {
       "network_type": "MainModalityMoE",
       "fusion_type": "mean",
-      "compensator": "none",
-      "eval_arm": "m1"
+      "compensator": "none"
     },
     "E1": {
       "network_type": "NPJC",
@@ -26,5 +24,13 @@
       "consistency_lambda": 0.1
     }
   },
-  "provenance": "root T0 launcher d0/e1 + historical r6; Dm reuses D checkpoint"
+  "provenance": "root T0 launcher d0/e1 + historical r6; Dm reuses D checkpoint",
+  "evaluation": {
+    "D": {
+      "arm": "m0real"
+    },
+    "Dm": {
+      "arm": "m1"
+    }
+  }
 }

```

### pyproject.toml
```diff
--- v3/pyproject.toml
+++ current/pyproject.toml
@@ -5,6 +5,7 @@
 [project]
 name = "trimodalsurv"
 version = "0.1.0"
+description = "Shared library; experiment and script entry points require a complete repository checkout"
 requires-python = ">=3.10"
 dependencies = ["numpy", "torch", "PyYAML"]
 

```

### tests/test_script_dispatch.py
```diff
--- v3/tests/test_script_dispatch.py
+++ current/tests/test_script_dispatch.py
@@ -0,0 +1,167 @@
+"""实际脚本分发契约；替换模型执行边界，不训练或导入 Torch。"""
+import importlib.util
+from pathlib import Path
+import sys
+from types import ModuleType, SimpleNamespace
+import unittest
+from unittest.mock import patch
+
+ROOT = Path(__file__).resolve().parents[1]
+
+
+def module(name, **attributes):
+    result = ModuleType(name)
+    result.__dict__.update(attributes)
+    return result
+
+
+def load_script(filename):
+    name = '_dispatch_contract_' + Path(filename).stem
+    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
+    loaded = importlib.util.module_from_spec(spec)
+    with patch.dict(sys.modules, {name: loaded}), patch.object(sys, 'path', sys.path.copy()):
+        spec.loader.exec_module(loaded)
+    return loaded
+
+
+class ScriptDispatchTests(unittest.TestCase):
+    def test_training_routes_seed_after_parse_before_execution(self):
+        for route in ('population', 'capl', 'none'):
+            with self.subTest(route=route):
+                events = []
+                args = SimpleNamespace(compensator=route, seed=123)
+
+                def parse(label):
+                    events.append(('parse', label))
+                    return args
+
+                def run(label, actual):
+                    self.assertIs(actual, args)
+                    events.append(('run', label))
+                    return 'finished-' + label
+
+                runtime = module('trimodalsurv.training.runtime',
+                    parsing_args=lambda: parse('shared'),
+                    set_seed=lambda seed: events.append(('seed', seed)),
+                    main=lambda actual: run('shared', actual))
+                modules = {
+                    'trimodalsurv': module('trimodalsurv'),
+                    'trimodalsurv.training': module('trimodalsurv.training', runtime=runtime),
+                    'trimodalsurv.training.runtime': runtime,
+                    'experiments.I02_population_prototypes.train': module('population_train',
+                        parsing_args=lambda: parse('population'),
+                        main=lambda actual: run('population', actual)),
+                    'experiments.I04_cap4_multi_prototypes.train': module('capl_train',
+                        main=lambda actual: run('capl', actual)),
+                }
+                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['main_survival.py', '--compensator=' + route]):
+                    entry = load_script('main_survival.py')
+                    expected = 'shared' if route == 'none' else route
+                    self.assertEqual(entry.main(), 'finished-' + expected)
+                self.assertEqual(events, [
+                    ('parse', 'population' if route == 'population' else 'shared'),
+                    ('seed', 123), ('run', expected)])
+
+    def test_training_config_routes_and_explicit_cli_precedence(self):
+        cases = [
+            ('population', None, 'population', 'population'),
+            ('capl', None, 'shared', 'capl'),
+            ('population', 'none', 'shared', 'shared'),
+        ]
+        for configured, explicit, parser_name, route in cases:
+            with self.subTest(configured=configured, explicit=explicit):
+                events = []
+                args = SimpleNamespace(compensator=explicit or configured, seed=132)
+
+                def parse(name):
+                    events.append(('parse', name))
+                    return args
+
+                def run(name, actual):
+                    self.assertIs(actual, args)
+                    events.append(('run', name))
+
+                runtime = module('runtime', parsing_args=lambda: parse('shared'),
+                    set_seed=lambda seed: events.append(('seed', seed)),
+                    main=lambda actual: run('shared', actual))
+                modules = {
+                    'trimodalsurv': module('trimodalsurv'),
+                    'trimodalsurv.training': module('trimodalsurv.training', runtime=runtime),
+                    'trimodalsurv.config': module('trimodalsurv.config',
+                        read_config=lambda _: {'runtime': {'compensator': configured}}),
+                    'experiments.I02_population_prototypes.train': module('population_train',
+                        parsing_args=lambda: parse('population'),
+                        main=lambda actual: run('population', actual)),
+                    'experiments.I04_cap4_multi_prototypes.train': module('capl_train',
+                        main=lambda actual: run('capl', actual)),
+                }
+                argv = ['main_survival.py', '--config', 'experiment.yaml']
+                if explicit is not None:
+                    argv += ['--compensator', explicit]
+                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', argv):
+                    load_script('main_survival.py').main()
+                self.assertEqual(events, [('parse', parser_name), ('seed', 132), ('run', route)])
+
+    def test_evaluation_routes_and_capl_factory(self):
+        for route in ('population', 'capl', 'none'):
+            with self.subTest(route=route):
+                events = []
+                args = SimpleNamespace(compensator=route)
+                factory = object()
+
+                def parse(label):
+                    events.append(('parse', label))
+                    return args
+
+                def run(label, actual, **kwargs):
+                    self.assertIs(actual, args)
+                    events.append(('run', label, kwargs))
+
+                shared = module('trimodalsurv.evaluation.missing',
+                    parse_args=lambda: parse('shared'),
+                    run_evaluation=lambda actual, **kwargs: run('shared', actual, **kwargs))
+                modules = {
+                    'trimodalsurv.evaluation.missing': shared,
+                    'experiments.I02_population_prototypes.evaluate': module('population_eval',
+                        parse_args=lambda: parse('population'),
+                        run_evaluation=lambda actual: run('population', actual)),
+                    'experiments.I04_cap4_multi_prototypes.train': module('capl_train', load_model=factory),
+                }
+                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['eval_missing.py', '--compensator', route]):
+                    entry = load_script('eval_missing.py')
+                    self.assertEqual(entry.main(), 0)
+                expected = 'population' if route == 'population' else 'shared'
+                kwargs = {} if route == 'population' else {'model_factory': factory if route == 'capl' else None}
+                self.assertEqual(events, [('parse', expected), ('run', expected, kwargs)])
+
+
+class LauncherBinModeTests(unittest.TestCase):
+    @classmethod
+    def setUpClass(cls):
+        cls.launcher = load_script('train_launcher.py')
+
+    def test_equals_and_separate_forms_are_preserved_without_duplicate(self):
+        for extra in (['--bin_mode=author'], ['--bin_mode', 'author']):
+            with self.subTest(extra=extra):
+                raw = {'name': 'e0_BLCA_s123', 'arm': 'e0', 'cancer': 'BLCA',
+                       'seed': 123, 'bin_mode': 'train_quantile', 'extra_args': extra}
+                with patch.object(self.launcher, '_load_yaml', return_value={'runs': [raw]}):
+                    spec = self.launcher.load_plan(Path('unused.yaml'))[0]
+                self.assertEqual(spec.extra_args, tuple(extra))
+                args = SimpleNamespace(python=sys.executable, cpt_name='test', result_path='/tmp/test-result',
+                    label='/tmp/label.csv', model_config='/tmp/model.yaml', gpu_config='/tmp/gpu.yaml',
+                    lr=1e-4, epochs=1, batch_size=2)
+                command = self.launcher.build_training_command(args, spec)
+                self.assertEqual(sum(token.split('=', 1)[0] == '--bin_mode' for token in command), 1)
+                self.assertEqual(self.launcher._option_value(command, '--bin_mode'), 'author')
+
+    def test_plan_field_adds_mode_only_when_missing(self):
+        raw = {'name': 'e0_BLCA_s123', 'arm': 'e0', 'cancer': 'BLCA',
+               'seed': 123, 'bin_mode': 'train_quantile', 'extra_args': ['--epochs', '1']}
+        with patch.object(self.launcher, '_load_yaml', return_value={'runs': [raw]}):
+            spec = self.launcher.load_plan(Path('unused.yaml'))[0]
+        self.assertEqual(spec.extra_args, ('--epochs', '1', '--bin_mode', 'train_quantile'))
+
+
+if __name__ == '__main__':
+    unittest.main()

```

### tests/test_experiment_presets.py
```diff
--- v3/tests/test_experiment_presets.py
+++ current/tests/test_experiment_presets.py
@@ -0,0 +1,77 @@
+"""真实公共训练工厂与实验预设合同，不启动训练或读取患者数据。"""
+import json
+from types import SimpleNamespace
+from pathlib import Path
+import pytest
+from trimodalsurv.training import runtime
+from experiments.I03_npj_d_dm_e1.model import build_model
+from experiments.I04_cap4_multi_prototypes.train import load_model as capl_load_model
+from experiments.I04_cap4_multi_prototypes.model import CAPRecallMulti
+
+ROOT = Path(__file__).resolve().parents[1]
+I03 = ROOT / 'experiments/I03_npj_d_dm_e1/config.yaml'
+I04 = ROOT / 'experiments/I04_cap4_multi_prototypes/config.yaml'
+MODALITIES = {name: SimpleNamespace(feature_dim=size) for name, size in {'img': 8, 'rna': 4, 'text': 6}.items()}
+
+
+def parse(config, preset, *extra):
+    return runtime.parsing_args(['--config', str(config), '--preset', preset, *extra])
+
+
+@pytest.mark.parametrize('arm', ['D', 'Dm', 'E1'])
+def test_i03_actual_runtime_factory_matches_experiment(arm):
+    args = parse(I03, arm)
+    actual = runtime.load_model(args.network_type, 'cpu', MODALITIES,
+        args.hidden_size, 4, compensator=args.compensator, fusion_type=args.fusion_type)
+    expected = build_model(arm, device='cpu', modalities=MODALITIES)
+    assert type(actual) is type(expected)
+    assert type(actual.compensator) is type(expected.compensator)
+    assert type(getattr(actual, 'fusion', None)) is type(getattr(expected, 'fusion', None))
+    assert {k: (v.shape, v.dtype) for k, v in actual.state_dict().items()} == {
+        k: (v.shape, v.dtype) for k, v in expected.state_dict().items()}
+    assert args.hidden_size == 256 and args.bin_mode == 'author'
+
+
+@pytest.mark.parametrize('preset,slots', [('dq0', None), ('dq_capl1', 1), ('dq_capl8', 8), ('dq_capl32', 32)])
+def test_i04_actual_factory_from_preset(preset, slots):
+    args = parse(I04, preset)
+    actual = capl_load_model(args.network_type, 'cpu', MODALITIES, args.hidden_size,
+        4, compensator=args.compensator, fusion_type=args.fusion_type,
+        proto_per_bin=args.proto_per_bin)
+    assert args.bin_mode == 'train_quantile' and args.hidden_size == 256
+    assert type(actual.fusion).__name__ == 'MeanFusion'
+    if slots is None:
+        assert actual.compensator is None
+    else:
+        assert isinstance(actual.compensator, CAPRecallMulti)
+        expected = CAPRecallMulti(('text', 'rna'), 256, n_bins=4, proto_per_bin=slots, ema=0.99)
+        assert {k: v.shape for k, v in actual.compensator.state_dict().items()} == {
+            k: v.shape for k, v in expected.state_dict().items()}
+
+
+def test_explicit_cli_wins_without_default_arm():
+    args = parse(I03, 'E1', '--modality_dropout', '0', '--train', 'false')
+    assert args.modality_dropout == 0 and args.train is False
+    with pytest.raises(ValueError, match='必须显式 --preset'):
+        runtime.parsing_args(['--config', str(I03)])
+    with pytest.raises(ValueError, match='必须显式 --preset'):
+        parse(I03, 'unknown')
+
+
+@pytest.mark.parametrize('mutation', ['top', 'model', 'preset', 'pred_dim', 'choice'])
+def test_invalid_config_is_rejected(tmp_path, mutation):
+    doc = json.loads(I03.read_text())
+    if mutation == 'top': doc['typo'] = 1
+    if mutation == 'model': doc['model']['typo'] = 1
+    if mutation == 'preset': doc['presets']['D']['typo'] = 1
+    if mutation == 'pred_dim': doc['model']['pred_dim'] = 17
+    if mutation == 'choice': doc['presets']['D']['compensator'] = 'typo'
+    target = tmp_path / 'config.json'
+    target.write_text(json.dumps(doc))
+    with pytest.raises(ValueError):
+        parse(target, 'D')
+
+
+def test_explicit_missing_checkout_config_has_clear_error(tmp_path):
+    with pytest.raises(ValueError, match='完整 repo checkout'):
+        parse(I03, 'D', '--model_config', str(tmp_path / 'absent.yml'))

```

### tests/test_run_provenance.py
```diff
--- v3/tests/test_run_provenance.py
+++ current/tests/test_run_provenance.py
@@ -0,0 +1,95 @@
+"""运行记录独占、来源闭包与完成证据契约；不读取患者数据。"""
+import argparse
+import json
+import tempfile
+import unittest
+from pathlib import Path
+from types import SimpleNamespace
+
+from trimodalsurv.config import (actual_model_spec, start_run_record, finalize_run_record,
+    runtime_source_fingerprints, run_record_root, training_artifact_paths, preflight_training_outputs)
+
+
+class RunProvenanceTests(unittest.TestCase):
+    def test_model_spec_reports_real_fusion_without_changing_npjc_contract(self):
+        layer = SimpleNamespace(self_attn=SimpleNamespace(embed_dim=8, num_heads=2),
+                                linear1=SimpleNamespace(out_features=16))
+        model = SimpleNamespace(backbone=[layer], modalities=['rna'], compensator=None,
+                                m_projector={'rna': [None, None, SimpleNamespace(p=0.1)]}, logits_dim=4)
+        self.assertNotIn('fusion', actual_model_spec(model))
+        model.fusion = type('MeanFusion', (), {})()
+        self.assertEqual(actual_model_spec(model)['fusion'], 'MeanFusion')
+        model.fusion = type('GatedFusion', (), {})()
+        self.assertEqual(actual_model_spec(model)['fusion'], 'GatedFusion')
+
+    def test_exclusive_record_pending_and_finalized_artifacts(self):
+        with tempfile.TemporaryDirectory() as directory:
+            root = Path(directory)
+            checkpoint = root / 'model.pth'
+            artifact = root / 'metrics.json'
+            payload = {'inputs': [], 'source_fingerprints': [], 'runtime': {'seed': 123}}
+            run = start_run_record(root / 'results', payload, checkpoint_path=checkpoint, run_id='test')
+            self.assertEqual(json.loads((run / 'resolved_config.yaml').read_text()), payload)
+            self.assertEqual(json.loads((run / 'checkpoint_manifest.json').read_text())['status'], 'pending')
+            with self.assertRaises(FileExistsError):
+                start_run_record(root / 'results', payload, checkpoint_path=checkpoint, run_id='test')
+            with self.assertRaises(FileNotFoundError):
+                finalize_run_record(run, checkpoint_path=checkpoint)
+            self.assertFalse((run / 'audit/completion.json').exists())
+            checkpoint.write_bytes(b'synthetic-checkpoint')
+            artifact.write_text('{"loss": 1}')
+            finalize_run_record(run, checkpoint_path=checkpoint, artifacts=[artifact])
+            completion = json.loads((run / 'audit/completion.json').read_text())
+            self.assertEqual(completion['status'], 'complete')
+            self.assertEqual(completion['artifacts'][0]['source']['sha256'], completion['artifacts'][0]['copy']['sha256'])
+            self.assertEqual((run / 'raw/00-metrics.json').read_bytes(), artifact.read_bytes())
+            with self.assertRaises(FileExistsError):
+                finalize_run_record(run, checkpoint_path=checkpoint)
+
+    def test_run_id_cannot_escape(self):
+        with tempfile.TemporaryDirectory() as directory:
+            with self.assertRaises(ValueError):
+                start_run_record(directory, {}, checkpoint_path='unused', run_id='../escape')
+
+    def test_source_closure_contains_models_experiments_entry_and_config(self):
+        with tempfile.TemporaryDirectory() as directory:
+            config = Path(directory) / 'config.yaml'
+            config.write_text('{}')
+            sources = runtime_source_fingerprints(argparse.Namespace(config=str(config)))
+            names = {item['path'] for item in sources}
+            repo = Path(__file__).resolve().parents[1]
+            for rel in ('src/trimodalsurv/models/npjc.py', 'experiments/I04_cap4_multi_prototypes/model.py',
+                        'scripts/main_survival.py'):
+                self.assertIn(str(repo / rel), names)
+            self.assertIn(str(config.resolve()), names)
+            self.assertTrue(all(len(item['sha256']) == 64 for item in sources))
+
+    def test_seed_artifacts_separate_and_preflight_refuses_existing(self):
+        with tempfile.TemporaryDirectory() as directory:
+            root = Path(directory)
+            first = training_artifact_paths(root / '123' / 'baseline')
+            second = training_artifact_paths(root / '132' / 'baseline')
+            self.assertTrue(set(first.values()).isdisjoint(second.values()))
+            for path in first.values():
+                path.parent.mkdir(parents=True, exist_ok=True)
+                if path.name.endswith('_plots'):
+                    path.mkdir()
+                else:
+                    path.write_text('existing')
+                with self.assertRaises(FileExistsError):
+                    preflight_training_outputs(root / '123' / 'baseline', root / '123' / 'baseline.pth',
+                                               training=True, sidecar=root / 'sidecar')
+            self.assertEqual(preflight_training_outputs(root / '132' / 'baseline',
+                root / '132' / 'baseline.pth', training=True, sidecar=root / 'sidecar'), second)
+
+    def test_run_root_does_not_invent_experiment_identity(self):
+        args = argparse.Namespace(result_path='/tmp/output', config=None)
+        self.assertEqual(run_record_root(args), Path('/tmp/output/results').resolve())
+        args.config = '/project/experiments/I03_npj_d_dm_e1/config.yaml'
+        self.assertEqual(run_record_root(args), Path('/project/experiments/I03_npj_d_dm_e1/results'))
+        args.run_record_root = '/tmp/explicit'
+        self.assertEqual(run_record_root(args), Path('/tmp/explicit').resolve())
+
+
+if __name__ == '__main__':
+    unittest.main()

```

### experiments/I02_population_prototypes/tests/test_population_early_stopping.py
```diff
--- v3/experiments/I02_population_prototypes/tests/test_population_early_stopping.py
+++ current/experiments/I02_population_prototypes/tests/test_population_early_stopping.py
@@ -1,5 +1,7 @@
 """早停边界与真实训练循环：防止只保存最佳模型却没有停止。"""
 import sys
+import json
+import hashlib
 from pathlib import Path
 from unittest.mock import patch
 
@@ -72,11 +74,25 @@
 def test_real_main_stops_and_reloads_best_checkpoint(tmp_path, patience, max_epochs, expected_epochs, scores):
     torch.set_num_threads(1)
     main.set_seed(19)
+    label_path = tmp_path / 'synthetic-label.csv'
+    label_path.write_text('patient_id,split\nsynthetic,fixture\n')
+    config_path = tmp_path / 'synthetic-model.json'
+    config_path.write_text(json.dumps({'fixture': 'SyntheticConfig', 'feature_dim': 4,
+                                      'pred_dim': 4, 'n_token': 3}))
+
+    class FixtureConfig(SyntheticConfig):
+        def __init__(self, path):
+            super().__init__(path)
+            for name, modality in self.obj.modality.items():
+                modality.path = str(tmp_path / f'synthetic-{name}')
+
     args = _parse_author_args([
         '--network_type', 'NPJC', '--compensator', 'population', '--prototype-k', '2',
         '--hidden_size', '16', '--epochs', str(max_epochs), '--early-stopping-patience', str(patience),
         '--batch_size', '4', '--num_workers', '0', '--cancer_types', 'A_B_UNUSED',
         '--result_path', str(tmp_path / 'out'), '--cpt_name', 'earlystop',
+        '--report_label_path', str(label_path), '--model_config', str(config_path),
+        '--run_record_root', str(tmp_path / 'run-records'),
         '--gpu_config', str(ROOT.parents[1] / 'configs/gpu_train.yaml'), '--seed', '19',
     ])
     datasets = tuple(synthetic_dataset(s, n) for s, n in [('train', 13), ('valid', 9), ('test', 7)])
@@ -101,7 +117,7 @@
         assert all(torch.equal(value.cpu(), saved[-1][key]) for key, value in state.items())
         loaded.append(True)
 
-    with patch.object(main, 'YmlConfig', SyntheticConfig), \
+    with patch.object(main, 'YmlConfig', FixtureConfig), \
          patch.object(main, 'get_dataset_tcga_sur', lambda *a, **k: datasets), \
          patch.object(main, 'finetune_epoch', controlled_validation), \
          patch.object(torch, 'save', record_save), \
@@ -112,3 +128,26 @@
     if scores is not None:
         assert any(not torch.equal(value, saved[0][key]) for key, value in saved[1].items())
     assert len(list(Path(args.result_path).rglob('*.pth'))) == 1
+
+    run_dirs = list((tmp_path / 'run-records').iterdir())
+    assert len(run_dirs) == 1
+    run = run_dirs[0]
+    data_manifest = json.loads((run / 'data_manifest.json').read_text())
+    inputs = {item['path']: item['sha256'] for item in data_manifest['inputs']}
+    assert inputs[str(label_path.resolve())] == hashlib.sha256(label_path.read_bytes()).hexdigest()
+    sources = json.loads((run / 'source_manifest.json').read_text())['files']
+    assert any(item['path'] == str(config_path.resolve()) and
+               item['sha256'] == hashlib.sha256(config_path.read_bytes()).hexdigest() for item in sources)
+    completion = json.loads((run / 'audit/completion.json').read_text())
+    assert completion['status'] == 'complete'
+    checkpoint = Path(completion['checkpoint']['path'])
+    assert completion['checkpoint']['sha256'] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
+    source_paths = {item['path'] for item in sources}
+    assert str((ROOT / 'model.py').resolve()) in source_paths
+    assert str((ROOT.parents[1] / 'src/trimodalsurv/models/npjc.py').resolve()) in source_paths
+    csv_entries = [item for item in completion['artifacts'] if item['source']['path'].endswith('.csv')]
+    assert len(csv_entries) == 1
+    csv_entry = csv_entries[0]
+    assert csv_entry['source']['sha256'] == csv_entry['copy']['sha256']
+    assert Path(csv_entry['copy']['path']).parent == run / 'raw'
+    assert hashlib.sha256(Path(csv_entry['copy']['path']).read_bytes()).hexdigest() == csv_entry['copy']['sha256']

```

### experiments-report.md
# I01–I04 迁移验证

## 实现边界

- I01：774f 的原始特征配对检索；投影前填补，共享 NPJC。
- I02：684e 的 PopulationPrototypeBank、每轮建库、早停与严格重载协调；共享编码/融合，训练前向不填补。
- I03：已有 D/Dm/旧 E1 的组合入口与历史身份；不新增研究机制。
- I04：根 NPJ 的 CAPRecallMulti、初始化与诊断，只整理已有 D 版预设；没有执行 C 版实验。

逐符号、源哈希、旧测试节点见 [source map](experiment-source-map.json)、[AST 核验](experiment-ast-verification.json)、[测试映射](all-test-nodes-map.json)。原 GPU scattermoe 测试随未用实现归档；未增加 skip。

## 本轮可见证据

- [迁移测试](validation-evidence/new-v6-tests.log)：178 passed、6 个原有 skipped。
- [独立进程真实对拍](validation-evidence/real-parity.json)：BLCA seed123、排序前32 test，I01 三臂×四格，I02 四格，CPU FP32；最大绝对差 0，容差 atol=1e-6 / rtol=0。
- [合成单步](validation-evidence/synthetic-parity.json)：7 个模型/补偿路径的初始状态、输出、loss、全部非空梯度、一次 Adam 更新及严格重载；最大差 0。
- [公共 epoch 单步](validation-evidence/epoch-parity.json)：透明测试包装下实际 finetune_epoch，单合成 batch，旧新差异 0。不等于多卡/正式患者训练验证。
- [权重](checkpoint-transfer-verification.json)：25 份 I02 本地与 tako 大小/MD5/SHA256一致；weights_only=True、strict=True 加载及原型 buffers 检查通过。
- [CLI](validation-evidence/cli-preflight-v6.json)：项目根与非根 cwd，22 项 help/dry-run 退出码 0，解析后的 runtime/model JSON 跨 cwd 完全相同。

I01 E0 沿用原加载器已有 `module.` 前缀处理合同；不修改 checkpoint。I02 原生 state_dict 不 remap。真实输入沿用 tako 既有冻结缓存；没有重建缓存、下载数据或启动正式训练。

以上是候选代码的固定范围证据，最终源码版本及 Claude 审阅结论以[执行状态](progress.md)为准。


### validation-evidence/new-v6-tests.log
ss......................s............................................... [ 39%]
........................................................................ [ 78%]
.................s.................s..s.                                 [100%]
=============================== warnings summary ===============================
experiments/I01_patient_retrieval/tests/test_patient_retrieval_eval.py::EvaluationContract::test_actual_npjc_forward_identity_mask_and_strict_checkpoint
  /home/wuhao/miniconda3/envs/tcga_env/lib/python3.12/site-packages/torch/nn/modules/transformer.py:502: UserWarning: The PyTorch API of nested tensors is in prototype stage and will change in the near future. (Triggered internally at /opt/conda/conda-bld/pytorch_1728945388038/work/aten/src/ATen/NestedTensorImpl.cpp:178.)
    output = torch._nested_tensor_from_mask(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
178 passed, 6 skipped, 1 warning in 13.34s


CLI 22命令退出码：[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]；完整runtime/model跨cwd相等断言已在driver正常退出前执行。

### 待执行归位脚本 cutover.py
```python
"""最终目录切换：固定T0漂移门、可逆rename、不删除。"""
from pathlib import Path
import json,sys,hashlib
from transaction import Transaction,fingerprint
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
backup=Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
plan=json.loads((B/'cutover-plan.json').read_text())
if '--apply' not in sys.argv:
 for op in plan:
  a=ROOT/op['source'];b=ROOT/op['target'];assert a.exists();assert not b.exists(),b
  frozen=(backup/'NPJ-after-manifest-commit') if op['source']=='NPJ' else backup/'root'/op['source'];assert fingerprint(a)==fingerprint(frozen),f'External drift {a}'
 print('CUTOVER_DRY_PASS',len(plan));raise SystemExit
assert (B/'cutover-gate.json').exists(),'Must review verification gate first'
gate=json.loads((B/'cutover-gate.json').read_text());assert gate['status']=='PASS'
tx=Transaction(B/'cutover-operations.jsonl')
for op in plan:
 a=ROOT/op['source'];b=ROOT/op['target']
 if a.exists():assert fingerprint(a)==fingerprint((backup/'NPJ-after-manifest-commit') if op['source']=='NPJ' else backup/'root'/op['source']),f'External drift {a}'
 tx.apply(a,b,'move')
print('CUTOVER_VERIFIED',len(plan))

```

### 待执行归位脚本 audit_assets.py
```python
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent;BACKUP=Path('/Users/wuhao/.codex/backups/trimodalsurv/20260916-080006')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for v in iter(lambda:f.read(1048576),b''):h.update(v)
 return h.hexdigest()
moves=json.loads((B/'cutover-plan.json').read_text());baseline=[json.loads(s) for s in (BACKUP/'files.jsonl').read_text().splitlines()];rows=[];missing=[]
for r in baseline:
 backup=BACKUP/r['source_id']/r['path'];ok=backup.exists() or backup.is_symlink()
 if ok:
  if r['type']=='symlink':ok=backup.is_symlink() and os.readlink(backup)==r['link_target']
  else:ok=sha(backup)==r['sha256']
 if not ok:missing.append(str(backup))
 active=None
 if r['source_id']=='root':
  active=ROOT/r['path']
  for m in moves:
   if active==ROOT/m['source'] or active.is_relative_to(ROOT/m['source']):active=ROOT/m['target']/active.relative_to(ROOT/m['source']);break
  if not active.exists() and not active.is_symlink():missing.append('current destination missing '+str(active))
  elif str(active.relative_to(ROOT)).startswith('archive/'):
   expected=backup
   if r['path'].startswith('NPJ/.git/'):
    expected=BACKUP/'NPJ-after-manifest-commit'/Path(r['path']).relative_to('NPJ')
   same=(active.is_symlink() and os.readlink(active)==os.readlink(expected)) if r['type']=='symlink' else sha(active)==sha(expected)
   if not same:missing.append('archived original changed '+str(active))
 category='git-metadata' if '.git' in Path(r['path']).parts else 'protected-original'
 rows.append({'source_id':r['source_id'],'old_path':r['path'],'original_sha256':r.get('sha256'),'backup':str(backup),'backup_verified':ok,'current_destination':str(active.relative_to(ROOT)) if active else None,'category':category})
assert not missing,missing[:20]
(B/'all-files-map.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
ledger=json.loads((B/'ledger-append.json').read_text());lp=ROOT/ledger['file'];assert sha(lp)==ledger['after_sha256'];assert hashlib.sha256(lp.read_bytes()[:ledger['before_bytes']]).hexdigest()==ledger['before_sha256']
assets=json.loads((B/'assets-map.json').read_text())['entries'];links=json.loads((B/'link-changes.json').read_text());changed={e['file']:e for e in links};copy_count=0
for e in assets:
 if not e['execute_copy']:continue
 p=ROOT/e['target'];expected=ledger['after_sha256'] if e['target']==ledger['file'] else changed.get(e['target'],{}).get('after_sha256',e['sha256']);assert p.exists() and sha(p)==expected,str(p);copy_count+=1
# 按原跨度重新构造使用版，保证只有已列链接目标改变。
for item in links:
 p=ROOT/item['file'];current=p.read_text()
 if item['file']=='STATUS.md':current=(B/'STATUS.after-links.bin').read_text()
 offset=0;spans=[]
 for c in item['changes']:
  start=c['start']+offset;end=start+len(c['new']);assert current[start:end]==c['new'];spans.append((start,end,c['old']));offset+=len(c['new'])-len(c['old'])
 for start,end,old in reversed(spans):current=current[:start]+old+current[end:]
 assert hashlib.sha256(current.encode()).hexdigest()==item['before_sha256'],item['file']
assert (ROOT/'STATUS.md').read_bytes().startswith((B/'STATUS.after-links.bin').read_bytes())
new=[];oldroot={r['path'] for r in baseline if r['source_id']=='root'}
for p in ROOT.rglob('*'):
 if not p.is_file() or '.git' in p.parts or p.is_symlink():continue
 rel=str(p.relative_to(ROOT))
 if rel not in oldroot and not rel.startswith('archive/') and p!=B/'new-files-manifest.json':new.append({'path':rel,'sha256':sha(p),'bytes':p.stat().st_size})
(B/'new-files-manifest.json').write_text(json.dumps(new,ensure_ascii=False,indent=2))
summary={'status':'PASS','fixed_T0_entries':len(rows),'verified_originals':len(rows),'coverage':1.0,'copies_checked':copy_count,'link_only_documents':len(links),'STATUS_append_prefix':True,'new_files':len(new),'external_worktrees':'not moved or modified'}
(B/'asset-audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

```

### 待执行归位脚本 finalize_navigation.py
```python
from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).parent
assert (B/'cutover-operations.jsonl').exists()
# 保存 STATUS 三阶段，旧内容只允许 repair_links.py 的目标跨度变化。
status=ROOT/'STATUS.md'
(B/'STATUS.before-links.bin').write_bytes(status.read_bytes())
subprocess.run(['python3','-B',str(B/'repair_links.py')],cwd=ROOT,check=True)
(B/'STATUS.after-links.bin').write_bytes(status.read_bytes())
append='''\n\n## 2026-09-16｜全项目结构化重构\n\n公共代码归 `src/trimodalsurv/`，I01–I04 各有模型、配置、知识与结果入口；旧源码/资料/批次移至 `archive/`，外部 MCAT/PORPOISE 保持独立。\n\n- [项目结构](docs/project-structure.md) · [逐项执行证据](docs/refactor/20260916-080006-full-project/progress.md)\n- [I01 知识](experiments/I01_patient_retrieval/knowledge/index.md) · [I02 知识](experiments/I02_population_prototypes/knowledge/index.md)\n- [I03 知识](experiments/I03_npj_d_dm_e1/knowledge/index.md) · [I04 知识](experiments/I04_cap4_multi_prototypes/knowledge/index.md)\n- [历史汇总复算](docs/refactor/20260916-080006-full-project/history-derived-03/summary.json)\n\n本轮仅重构与 CPU 兼容验证，没有新增正式训练。I04 只整理已有 D 版，C 版仍未实现；历史比较不是匹配训练协议的机制消融。具体通过范围、旧 skip 与审核结论以本轮证据为准。\n\n本次旧正文仅修链接，删除线及科研判断保留；从此继续只在末尾追加。\n'''
with status.open('ab') as f:f.write(append.encode())
assert status.read_bytes().startswith((B/'STATUS.after-links.bin').read_bytes())
(ROOT/'README.md').write_text((B/'README.next.md').read_text())
rule_changes=[]
for filename in ['AGENTS.md','CLAUDE.md']:
 p=ROOT/filename;before=p.read_text();after=before.replace('collab/pitfalls.md','docs/engineering/pitfalls.md').replace('NPJ/scripts/train_launcher.py','scripts/train_launcher.py').replace('NPJ/scripts/launch_formal.sh','scripts/launch_formal.sh')
 # 原collab具体历史证据现在在完整原件目录。
 after=after.replace('collab/', 'archive/legacy_collab/root-20260916-080006/')
 if before!=after:
  p.write_text(after);rule_changes.append({'path':filename,'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'kind':'path-only'})
(B/'rule-path-changes.json').write_text(json.dumps(rule_changes,indent=2))
p=ROOT/'.gitignore'
with p.open('a') as f:f.write('\n# 全项目重构：原始归档/仓库元数据/本轮传输包保留磁盘，不进源码提交。\n/archive/\n/docs/refactor/**/*.tar\n/docs/refactor/**/*.index\n/docs/refactor/**/*.bin\n/docs/refactor/**/validation-evidence/**/*.pt\n')
p=ROOT/'.ignore';s=p.read_text();s=s.replace('!/NPJ/','').replace('# ripgrep / Better Todo Tree：搜索嵌套的 NPJ 开发目录。','# ripgrep / Better Todo Tree：搜索当前公共代码与实验实现。').replace('# .gitignore 仍负责让外层仓库不跟踪 NPJ；这里只调整搜索范围。','# 历史归档和原始结果不进入默认源码搜索；Git 规则另由 .gitignore 管理。');p.write_text(s+'\n/docs/refactor/**/history-derived-*/\n')
p=ROOT/'.vscode/settings.json';settings=json.loads(p.read_text());exclude=settings.setdefault('search.exclude',{});exclude.update({'archive/**':True,'experiments/**/results/**/raw/**':True,'experiments/**/results/**/checkpoints/**':True,'**/__pycache__/**':True});p.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
ledger=ROOT/'docs/engineering/pitfalls.md'
old=ledger.read_bytes()
addition='\n\n## 全项目重构补充（2026-09-16）\n\n| ID | 坑（一句话） | Prevention Rule（一句话） | 出处 |\n|---|---|---|---|\n| R1 | 入口拆分后提前返回绕过 set_seed，模块测试无法发现运行初始化差异。 | 对真实入口验证参数解析→随机初始化→目标分发顺序，配置与显式CLI两条路径均覆盖。 | docs/refactor/20260916-080006-full-project/progress.md |\n| R2 | 按报告目录搬结果漏掉相邻历史对照文件，副本不能独立复算。 | 结果保全按实际读取依赖闭包核验，并在禁用旧来源的条件下复算。 | docs/refactor/20260916-080006-full-project/progress.md |\n'
with ledger.open('ab') as f:f.write(addition.encode())
new=ledger.read_bytes();assert new.startswith(old)
(B/'ledger-append.json').write_text(json.dumps({'file':str(ledger.relative_to(ROOT)),'before_bytes':len(old),'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(new).hexdigest()},indent=2))
print('NAVIGATION_UPDATED')

```
