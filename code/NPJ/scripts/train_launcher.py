#!/usr/bin/env python3
"""统一展开、预热、调度 NPJ 训练，并可在训练完成后接力缺失评测。

正式运行时仍须由仓库外层 ``jobrun.sh`` 托管，例如：
``jobrun.sh python scripts/train_launcher.py --arms e0,e1 --cancers BLCA --seeds 123``。
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


NPJ_ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = NPJ_ROOT / "main_survival.py"
EVAL_SCRIPT = NPJ_ROOT / "scripts" / "eval_missing.py"
FORMAL_LAUNCHER = NPJ_ROOT / "scripts" / "launch_formal.sh"
DEFAULT_MODEL_CONFIG = NPJ_ROOT / "model" / "config" / "surv_multimodal_mainmoe_uni2.yml"
DEFAULT_GPU_CONFIG = NPJ_ROOT / "config" / "gpu_train.yaml"
DEFAULT_LABEL = NPJ_ROOT / "data" / "TCGA_9523_ex12.csv"
CACHE_MODALITIES: Tuple[str, ...] = ("img", "text", "rna")
CACHE_SPLITS: Tuple[str, ...] = ("train", "valid", "test")
RUN_STATUSES = {"pending", "running", "done", "failed", "skipped"}
# 指挥官小修（NPJ-D 消融，2026-09-06）：训练 extra_args 中需要原样透传给评测器的开关
EVAL_FORWARDED_OPTIONS: Tuple[str, ...] = ("--fusion_type",)

GPU_POLICY_DEFAULTS = {
    "batch_size": None,
    "gradient_accumulation_steps": 1,
    "num_workers": 4,
    "pin_memory": True,
    "persistent_workers": True,
    "prefetch_factor": 4,
    "non_blocking": True,
    "concurrent_runs": 1,
    "gpu_util_warmup_sec": 120,
    "gpu_util_min_percent": 50,
    "gpu_util_target_percent": 80,
    "allow_low_gpu_util": False,
    "low_gpu_util_reason": "",
}

ARM_PRESETS: Mapping[str, Mapping[str, object]] = {
    "e0": {
        "network_type": "NPJC",
        "compensator": "none",
        "extra_args": (),
    },
    "e0d": {
        "network_type": "NPJC",
        "compensator": "none",
        "extra_args": ("--modality_dropout", "0.15"),
    },
    "e1": {
        "network_type": "NPJC",
        "compensator": "capr",
        "extra_args": (
            "--modality_dropout",
            "0.15",
            "--consistency_lambda",
            "0.1",
        ),
    },
    # 指挥官小修（NPJ-D 消融，2026-09-06）：d0 = NPJ-A 去 GatedFusion（等权均值融合）
    "d0": {
        "network_type": "MainModalityMoE",
        "compensator": "none",
        "extra_args": ("--fusion_type", "mean"),
    },
}


@dataclass(frozen=True)
class RunSpec:
    name: str
    arm: str
    network_type: str
    compensator: str
    cancer: str
    seed: int
    extra_args: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Slot:
    gpu: str
    index: int


@dataclass
class ActiveRun:
    spec: RunSpec
    slot: Slot
    process: subprocess.Popen
    started_at: float
    log_path: Path
    checkpoint: Path
    command: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(path: Path | str, base: Path = NPJ_ROOT) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def _strip_yaml_comment(line: str) -> str:
    quote = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote == '"':
            escaped = True
            continue
        if character in {'"', "'"}:
            quote = None if quote == character else character if quote is None else quote
            continue
        if character == "#" and quote is None:
            return line[:index]
    return line


def _simple_yaml_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return None
    if value[0:1] in {'"', "'"}:
        return ast.literal_eval(value)
    lowered = value.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        return [] if not body else [_simple_yaml_scalar(item) for item in body.split(",")]
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _simple_yaml_load(text: str) -> object:
    """解析本项目 plan/config 使用的 YAML 子集，不支持锚点或多行标量。"""
    lines = []
    for raw in text.splitlines():
        content = _strip_yaml_comment(raw).rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        if "\t" in content[:indent]:
            raise ValueError("简化 YAML 解析器不接受 tab 缩进")
        lines.append((indent, content.lstrip()))

    def parse_block(index: int, indent: int):
        is_list = lines[index][1].startswith("- ") or lines[index][1] == "-"
        container = [] if is_list else {}
        while index < len(lines) and lines[index][0] == indent:
            content = lines[index][1]
            if is_list:
                if not content.startswith("-"):
                    break
                item = content[1:].strip()
                index += 1
                if not item:
                    if index >= len(lines) or lines[index][0] <= indent:
                        container.append(None)
                    else:
                        nested, index = parse_block(index, lines[index][0])
                        container.append(nested)
                    continue
                if ":" not in item:
                    container.append(_simple_yaml_scalar(item))
                    continue
                key, value = item.split(":", 1)
                entry = {key.strip(): _simple_yaml_scalar(value)}
                if index < len(lines) and lines[index][0] > indent:
                    nested, index = parse_block(index, lines[index][0])
                    if not isinstance(nested, dict):
                        raise ValueError("YAML 列表映射项后必须继续映射")
                    entry.update(nested)
                container.append(entry)
            else:
                if content.startswith("-") or ":" not in content:
                    break
                key, value = content.split(":", 1)
                key = key.strip()
                index += 1
                if value.strip():
                    container[key] = _simple_yaml_scalar(value)
                elif index < len(lines) and lines[index][0] > indent:
                    container[key], index = parse_block(index, lines[index][0])
                else:
                    container[key] = {}
        return container, index

    if not lines:
        return {}
    payload, final_index = parse_block(0, lines[0][0])
    if final_index != len(lines):
        raise ValueError(f"无法解析 YAML 第 {final_index + 1} 个有效行")
    return payload


def _load_yaml(path: Path) -> Mapping[str, object]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
    except ModuleNotFoundError:
        payload = _simple_yaml_load(text) or {}
    else:
        payload = yaml.safe_load(text) or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"YAML 顶层必须是映射: {path}")
    return payload


def resolved_gpu_policy(path: Path) -> Dict[str, object]:
    policy = dict(GPU_POLICY_DEFAULTS)
    policy.update(_load_yaml(path))
    return policy


def _split_csv(value: str | None, *, field: str, upper: bool = False) -> List[str]:
    if value is None:
        raise ValueError(f"缺少 {field}")
    values = [item.strip() for item in value.split(",") if item.strip()]
    if upper:
        values = [item.upper() for item in values]
    if not values:
        raise ValueError(f"{field} 不能为空")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} 不得重复")
    return values


def _parse_extra_args(value: object) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(shlex.split(value))
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(item) for item in value)
    raise ValueError("extra_args 必须是字符串或字符串列表")


def _validate_spec(spec: RunSpec) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", spec.name):
        raise ValueError(f"run name 只能含字母、数字、点、下划线和短横线: {spec.name!r}")
    if spec.compensator not in {"none", "capr", "bank"}:
        raise ValueError(f"不支持的 compensator: {spec.compensator!r}")
    if not spec.cancer:
        raise ValueError("cancer 不能为空")
    protected = {"--seed", "--cancer_types", "--network_type", "--compensator"}
    for argument in spec.extra_args:
        option = argument.split("=", 1)[0]
        if option in protected:
            raise ValueError(f"extra_args 不得覆盖 run 身份字段: {option}")


def load_plan(path: Path) -> List[RunSpec]:
    payload = _load_yaml(path)
    raw_runs = payload.get("runs")
    if raw_runs is None and isinstance(payload, Mapping):
        raise ValueError("plan YAML 必须包含 runs 列表")
    if not isinstance(raw_runs, list) or not raw_runs:
        raise ValueError("plan.runs 必须是非空列表")

    runs: List[RunSpec] = []
    for index, raw in enumerate(raw_runs):
        if not isinstance(raw, Mapping):
            raise ValueError(f"plan.runs[{index}] 必须是映射")
        missing = {"name", "arm", "cancer", "seed"} - set(raw)
        if missing:
            raise ValueError(f"plan.runs[{index}] 缺少字段: {sorted(missing)}")
        arm = str(raw["arm"]).lower()
        preset = ARM_PRESETS.get(arm, {})
        network_type = raw.get("network_type", preset.get("network_type"))
        compensator = raw.get("compensator", preset.get("compensator"))
        if network_type is None or compensator is None:
            raise ValueError(
                f"plan.runs[{index}] 的自定义 arm 必须显式给出 network_type/compensator"
            )
        spec = RunSpec(
            name=str(raw["name"]),
            arm=arm,
            network_type=str(network_type),
            compensator=str(compensator),
            cancer=str(raw["cancer"]).upper(),
            seed=int(raw["seed"]),
            extra_args=_parse_extra_args(raw.get("extra_args")),
        )
        _validate_spec(spec)
        runs.append(spec)
    _validate_unique_names(runs)
    return runs


def generate_runs(arms: str, cancers: str, seeds: str) -> List[RunSpec]:
    arm_values = [item.lower() for item in _split_csv(arms, field="--arms")]
    cancer_values = _split_csv(cancers, field="--cancers", upper=True)
    seed_values = [int(item) for item in _split_csv(seeds, field="--seeds")]
    runs: List[RunSpec] = []
    for arm in arm_values:
        if arm not in ARM_PRESETS:
            raise ValueError(
                f"生成器不支持 arm={arm!r}; 可选值: {sorted(ARM_PRESETS)}"
            )
        preset = ARM_PRESETS[arm]
        for cancer in cancer_values:
            for seed in seed_values:
                spec = RunSpec(
                    name=f"{arm}_{cancer}_s{seed}",
                    arm=arm,
                    network_type=str(preset["network_type"]),
                    compensator=str(preset["compensator"]),
                    cancer=cancer,
                    seed=seed,
                    extra_args=tuple(str(item) for item in preset["extra_args"]),
                )
                _validate_spec(spec)
                runs.append(spec)
    _validate_unique_names(runs)
    return runs


def _validate_unique_names(runs: Sequence[RunSpec]) -> None:
    names = [run.name for run in runs]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"run name 重复: {duplicates}")


def build_slots(gpus: Sequence[str], per_gpu: int) -> List[Slot]:
    if per_gpu < 1:
        raise ValueError("--per_gpu 必须大于 0")
    return [Slot(gpu=gpu, index=index) for index in range(per_gpu) for gpu in gpus]


def build_training_command(args: argparse.Namespace, spec: RunSpec) -> List[str]:
    command = [
        args.python,
        str(MAIN_SCRIPT),
        "--seed",
        str(spec.seed),
        "--cpt_name",
        args.cpt_name,
        "--result_path",
        str(_resolve(args.result_path)),
        "--report_label_path",
        str(_resolve(args.label)),
        "--model_config",
        str(_resolve(args.model_config)),
        "--gpu_config",
        str(_resolve(args.gpu_config)),
        "--cancer_types",
        spec.cancer,
        "--network_type",
        spec.network_type,
        "--hidden_size",
        "256",
        "--compensator",
        spec.compensator,
    ]
    # 指挥官小修（2026-09-02）：与 S4/S5/E0/E1 正式训练口径对齐的固定超参（launcher 级默认，可 CLI 覆盖）
    command.extend(["--lr", str(args.lr), "--epochs", str(args.epochs), "--batch_size", str(args.batch_size)])
    command.extend(spec.extra_args)
    return command


def _option_value(command: Sequence[str], option: str, default: str = "") -> str:
    value = default
    for index, argument in enumerate(command):
        if argument == option and index + 1 < len(command):
            value = command[index + 1]
        elif argument.startswith(option + "="):
            value = argument.split("=", 1)[1]
    return value


def _has_option(command: Sequence[str], option: str) -> bool:
    return any(argument == option or argument.startswith(option + "=") for argument in command)


def checkpoint_path(command: Sequence[str]) -> Path:
    model_config_path = _resolve(_option_value(command, "--model_config"))
    config = _load_yaml(model_config_path)
    modalities = config.get("modality")
    if not isinstance(modalities, Mapping) or not modalities:
        raise ValueError(f"model config 缺少 modality 映射: {model_config_path}")
    modality_name = "".join(
        f"{name}_{settings['feature_dim']}"
        for name, settings in modalities.items()
    )
    compensator = _option_value(command, "--compensator", "none")
    cpt_name = _option_value(command, "--cpt_name", "tcga")
    result_path = _resolve(_option_value(command, "--result_path", "out"))
    if compensator != "none":
        suffix = f"_{compensator}"
        if not cpt_name.endswith(suffix):
            cpt_name += suffix
        if not str(result_path).endswith(suffix):
            result_path = Path(str(result_path) + suffix)
    seed = _option_value(command, "--seed", "123")
    network_type = _option_value(command, "--network_type")
    cancer = _option_value(command, "--cancer_types", "None")
    task_type = _option_value(command, "--task_type", "surv")
    filename = f"{cpt_name}_{modality_name}_{network_type}_{cancer}_{task_type}"
    if _option_value(command, "--pretrain_path"):
        filename += "_pretrained"
    if _has_option(command, "--finetune_head_only"):
        filename += "_onlyhead"
    missing = _option_value(command, "--simulate_missing_modality")
    if missing:
        filename += f"_missing_{missing}"
    return result_path / seed / f"{filename}.pth"


def cache_file(
    cache_dir: Path,
    modality: str,
    split: str,
    img_select: str,
    cancer: str,
) -> Path:
    return cache_dir / f"{modality}_sur_{split}_{img_select}_{cancer}.pkl"


def missing_cache_files(
    cache_dir: Path,
    cancer: str,
    img_select: str,
    modalities: Iterable[str] = CACHE_MODALITIES,
) -> List[Path]:
    return [
        cache_file(cache_dir, modality, split, img_select, cancer)
        for split in CACHE_SPLITS
        for modality in modalities
        if not cache_file(cache_dir, modality, split, img_select, cancer).is_file()
    ]


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"version": 1, "runs": {}}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), dict):
        raise ValueError(f"状态文件格式错误: {path}")
    for name, entry in payload["runs"].items():
        if not isinstance(entry, dict) or entry.get("status") not in RUN_STATUSES:
            raise ValueError(f"状态文件 run={name!r} 的 status 无效")
    return payload


def _write_state(path: Path, state: MutableMapping[str, object]) -> None:
    state["version"] = 1
    state["updated_at"] = _utc_now()
    atomic_write_json(path, state)


def _model_cache_settings(model_config: Path) -> Tuple[str, Tuple[str, ...]]:
    config = _load_yaml(model_config)
    img_select = str(config.get("img_select", "random"))
    raw_modalities = config.get("modality")
    if not isinstance(raw_modalities, Mapping):
        raise ValueError(f"model config 缺少 modality 映射: {model_config}")
    modalities = tuple(name for name in CACHE_MODALITIES if name in raw_modalities)
    return img_select, modalities


def _prewarm_one(args: argparse.Namespace, cancer: str) -> int:
    if args.cache_dir.name != "tmp_sur_cache":
        raise ValueError("TCGASurDataset 固定使用 tmp_sur_cache；--cache-dir basename 必须一致")
    config = _load_yaml(args.model_config)
    raw_modalities = config.get("modality")
    if not isinstance(raw_modalities, Mapping):
        raise ValueError("model config 缺少 modality 映射")
    modalities = {}
    for name, settings in raw_modalities.items():
        if not isinstance(settings, Mapping):
            raise ValueError(f"modality.{name} 必须是映射")
        feature_path = _resolve(str(settings["path"]))
        modalities[name] = SimpleNamespace(
            path=str(feature_path),
            feature_dim=settings.get("feature_dim"),
            modality_name=settings.get("modality_name", name),
        )
    sys.path.insert(0, str(NPJ_ROOT))
    from loc_utils_3yr.tcga_dataset import get_dataset_tcga_sur

    previous_cwd = Path.cwd()
    args.cache_dir.parent.mkdir(parents=True, exist_ok=True)
    os.chdir(args.cache_dir.parent)
    try:
        get_dataset_tcga_sur(
            str(args.label),
            modalities=modalities,
            task_type=str(config.get("task_type", "surv")),
            img_select=str(config.get("img_select", "random")),
            n_image_tokens=int(config.get("network", {}).get("n_token", 128)),
            cancer_types=cancer,
            network_type="CachePrewarm",
        )
    finally:
        os.chdir(previous_cwd)
    print(f"PREWARM_DONE cancer={cancer}")
    return 0


def _run_prewarm(args: argparse.Namespace, cancers: Sequence[str]) -> None:
    args.logs_dir.mkdir(parents=True, exist_ok=True)

    def launch(cancer: str) -> None:
        log_path = (args.logs_dir / f"prewarm_{cancer}.log").resolve()
        command = [
            args.python,
            str(Path(__file__).resolve()),
            "--_prewarm-cancer",
            cancer,
            "--label",
            str(args.label),
            "--model-config",
            str(args.model_config),
            "--cache-dir",
            str(args.cache_dir),
        ]
        with log_path.open("wb") as handle:
            completed = subprocess.run(
                command,
                cwd=NPJ_ROOT,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(
                f"缓存预热失败: cancer={cancer}, exit={completed.returncode}, log={log_path}"
            )

    with ThreadPoolExecutor(max_workers=args.prewarm_workers) as executor:
        futures = [executor.submit(launch, cancer) for cancer in cancers]
        for future in as_completed(futures):
            future.result()


def _training_pgid(log_path: Path) -> int | None:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    matches = re.findall(r"FORMAL_LAUNCH_PID=(\d+) PGID=(\d+)", text)
    return int(matches[-1][1]) if matches else None


def _terminate_active(active_runs: Iterable[ActiveRun]) -> None:
    for active in active_runs:
        pgids = [active.process.pid, _training_pgid(active.log_path)]
        for pgid in dict.fromkeys(value for value in pgids if value is not None):
            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass


def eval_arm_of(spec: RunSpec) -> str:
    return "m1" if spec.arm == "m1" else "m0real"


def _forwarded_eval_args(spec: RunSpec) -> List[str]:
    """指挥官小修（NPJ-D 消融，2026-09-06）：把训练侧 extra_args 里评测器也认识的开关透传过去。

    当前只有 `--fusion_type`（d0 臂）；未声明该开关的臂（e0/e0d/e1）逐字不变。
    """
    forwarded: List[str] = []
    for option in EVAL_FORWARDED_OPTIONS:
        value = _option_value(spec.extra_args, option)
        if value:
            forwarded.extend([option, value])
    return forwarded


def build_eval_command(
    args: argparse.Namespace,
    spec: RunSpec,
    checkpoint: Path,
    out_dir: Path,
) -> List[str]:
    """组装 eval_missing.py 命令（纯函数，无副作用，便于 dry-run 断言）。"""
    command = [
        args.python,
        str(EVAL_SCRIPT),
        "--arm",
        eval_arm_of(spec),
        "--cancer",
        spec.cancer,
        "--seed",
        str(spec.seed),
        "--ckpt",
        str(checkpoint),
        "--manifest",
        str(args.eval_manifest),
        "--grids",
        args.eval_grids,
        "--label",
        str(args.label),
        "--out-dir",
        str(out_dir),
        "--network_type",
        spec.network_type,
        "--compensator",
        spec.compensator,
    ]
    command.extend(_forwarded_eval_args(spec))
    return command


def _run_eval(
    args: argparse.Namespace,
    active: ActiveRun,
) -> Path:
    eval_arm = eval_arm_of(active.spec)
    eval_out = args.eval_out.resolve()
    eval_out.mkdir(parents=True, exist_ok=True)
    eval_log = active.log_path.with_suffix(".eval.log")
    with tempfile.TemporaryDirectory(prefix=f".{active.spec.name}.", dir=eval_out) as temp:
        temporary_out = Path(temp)
        command = build_eval_command(args, active.spec, active.checkpoint, temporary_out)
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = active.slot.gpu
        with eval_log.open("wb") as handle:
            completed = subprocess.run(
                command,
                cwd=NPJ_ROOT,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(
                f"评测失败: run={active.spec.name}, exit={completed.returncode}, log={eval_log}"
            )
        source = temporary_out / f"{eval_arm}_{active.spec.cancer}_s{active.spec.seed}.json"
        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["arm"] = active.spec.arm
        destination = eval_out / (
            f"{active.spec.arm}_{active.spec.cancer}_s{active.spec.seed}.json"
        )
        atomic_write_json(destination, payload)
    return destination


def _initial_state(
    args: argparse.Namespace,
    runs: Sequence[RunSpec],
    commands: Mapping[str, List[str]],
    checkpoints: Mapping[str, Path],
) -> Dict[str, object]:
    prior = load_state(args.state_file)
    entries = dict(prior.get("runs", {}))
    for spec in runs:
        skipped = checkpoints[spec.name].is_file() and not args.force
        entries[spec.name] = {
            "name": spec.name,
            "arm": spec.arm,
            "network_type": spec.network_type,
            "compensator": spec.compensator,
            "cancer": spec.cancer,
            "seed": spec.seed,
            "status": "skipped" if skipped else "pending",
            "pid": None,
            "exit": None,
            "duration_sec": 0.0,
            "checkpoint": str(checkpoints[spec.name]),
            "command": commands[spec.name],
            "reason": "checkpoint_exists" if skipped else "",
        }
    return {"version": 1, "runs": entries}


def run_scheduler(args: argparse.Namespace, runs: Sequence[RunSpec]) -> int:
    commands = {run.name: build_training_command(args, run) for run in runs}
    checkpoints = {name: checkpoint_path(command) for name, command in commands.items()}
    slots = build_slots(args.gpus, args.per_gpu)

    if args.dry_run:
        print(
            "RESOLVED_GPU_POLICY="
            + json.dumps(resolved_gpu_policy(args.gpu_config), ensure_ascii=False, sort_keys=True)
        )
        for index, spec in enumerate(runs):
            slot = slots[index % len(slots)]
            print(
                f"DRY_RUN index={index + 1} name={spec.name} arm={spec.arm} "
                f"cancer={spec.cancer} seed={spec.seed} gpu={slot.gpu} slot={slot.index} "
                f"checkpoint={checkpoints[spec.name]} command={shlex.join(commands[spec.name])}"
            )
        print(f"DRY_RUN_TOTAL={len(runs)}")
        return 0

    args.logs_dir.mkdir(parents=True, exist_ok=True)
    args.state_file.parent.mkdir(parents=True, exist_ok=True)
    state = _initial_state(args, runs, commands, checkpoints)
    _write_state(args.state_file, state)
    pending = [run for run in runs if state["runs"][run.name]["status"] == "pending"]

    img_select, modalities = _model_cache_settings(args.model_config)
    cancers_to_prewarm = sorted(
        {
            run.cancer
            for run in pending
            if missing_cache_files(args.cache_dir, run.cancer, img_select, modalities)
        }
    )
    if cancers_to_prewarm:
        _run_prewarm(args, cancers_to_prewarm)
        remaining = {
            cancer: [str(path) for path in missing_cache_files(
                args.cache_dir, cancer, img_select, modalities
            )]
            for cancer in cancers_to_prewarm
        }
        remaining = {cancer: paths for cancer, paths in remaining.items() if paths}
        if remaining:
            raise RuntimeError(f"预热完成后缓存仍不齐全: {remaining}")

    stop_requested = False
    active: Dict[str, ActiveRun] = {}
    available = list(slots)
    eval_executor = (
        ThreadPoolExecutor(max_workers=args.eval_workers) if args.eval_grids else None
    )
    eval_futures: Dict[Future, str] = {}

    def request_stop(signum, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True
        print(f"LAUNCHER_SIGNAL={signum}; forwarding SIGTERM", file=sys.stderr)
        _terminate_active(active.values())

    previous_handlers = {
        sig: signal.signal(sig, request_stop) for sig in (signal.SIGTERM, signal.SIGINT)
    }
    try:
        while pending or active:
            while pending and available and not stop_requested:
                spec = pending.pop(0)
                slot = available.pop(0)
                log_path = (args.logs_dir / f"{spec.name}.log").resolve()
                log_path.write_bytes(b"")
                formal_command = [
                    str(args.formal_launcher),
                    slot.gpu,
                    str(log_path),
                    "--",
                    *commands[spec.name],
                ]
                environment = os.environ.copy()
                environment["GPU_CONFIG"] = str(args.gpu_config)
                environment["PYTHON_BIN"] = args.python
                with log_path.open("ab") as log_handle:
                    process = subprocess.Popen(
                        formal_command,
                        cwd=NPJ_ROOT,
                        env=environment,
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                active_run = ActiveRun(
                    spec=spec,
                    slot=slot,
                    process=process,
                    started_at=time.monotonic(),
                    log_path=log_path,
                    checkpoint=checkpoints[spec.name],
                    command=commands[spec.name],
                )
                active[spec.name] = active_run
                entry = state["runs"][spec.name]
                entry.update(
                    status="running",
                    pid=process.pid,
                    gpu=slot.gpu,
                    slot=slot.index,
                    log=str(log_path),
                    started_at=_utc_now(),
                    reason="",
                )
                _write_state(args.state_file, state)

            if stop_requested and pending:
                for spec in pending:
                    state["runs"][spec.name].update(
                        status="skipped", reason="launcher_terminated"
                    )
                pending.clear()
                _write_state(args.state_file, state)

            finished_any = False
            for name, active_run in list(active.items()):
                return_code = active_run.process.poll()
                if return_code is None:
                    continue
                finished_any = True
                duration = time.monotonic() - active_run.started_at
                status = "done" if return_code == 0 else "failed"
                if stop_requested:
                    _terminate_active([active_run])
                state["runs"][name].update(
                    status=status,
                    exit=return_code,
                    duration_sec=round(duration, 3),
                    finished_at=_utc_now(),
                )
                available.append(active_run.slot)
                del active[name]
                _write_state(args.state_file, state)
                if status == "done" and eval_executor is not None:
                    future = eval_executor.submit(_run_eval, args, active_run)
                    eval_futures[future] = name
            if (pending or active) and not finished_any:
                time.sleep(0.5)

        eval_failed = False
        for future in as_completed(eval_futures):
            name = eval_futures[future]
            try:
                output_path = future.result()
            except Exception as exc:
                eval_failed = True
                state["runs"][name].update(eval_status="failed", eval_error=str(exc))
            else:
                state["runs"][name].update(
                    eval_status="done", eval_output=str(output_path)
                )
            _write_state(args.state_file, state)
    finally:
        if active:
            _terminate_active(active.values())
        if eval_executor is not None:
            eval_executor.shutdown(wait=True, cancel_futures=stop_requested)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)

    failed = any(
        state["runs"][run.name]["status"] == "failed" for run in runs
    )
    return 1 if failed or eval_failed or stop_requested else 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--arms")
    parser.add_argument("--cancers")
    parser.add_argument("--seeds")
    parser.add_argument("--gpus", default="0,1")
    parser.add_argument("--per_gpu", type=int, default=8)
    parser.add_argument("--prewarm_workers", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--label", type=Path, default=DEFAULT_LABEL)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", "--batch_size", dest="batch_size", type=int, default=32)
    parser.add_argument("--model-config", type=Path, default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--gpu-config", type=Path, default=DEFAULT_GPU_CONFIG)
    parser.add_argument("--result-path", type=Path, default=NPJ_ROOT / "out")
    parser.add_argument("--cpt-name", default="tcga_uni2")
    parser.add_argument("--cache-dir", type=Path, default=NPJ_ROOT / "tmp_sur_cache")
    parser.add_argument("--logs-dir", type=Path, default=NPJ_ROOT / "launcher_logs")
    parser.add_argument("--state-file", type=Path, default=NPJ_ROOT / "runs_state.json")
    parser.add_argument("--formal-launcher", type=Path, default=FORMAL_LAUNCHER)
    parser.add_argument("--eval_grids", "--eval-grids", dest="eval_grids")
    parser.add_argument("--eval_workers", type=int, default=4)
    parser.add_argument("--eval_out", "--eval-out", dest="eval_out", type=Path)
    parser.add_argument(
        "--eval_manifest", "--eval-manifest", dest="eval_manifest", type=Path
    )
    parser.add_argument("--_prewarm-cancer", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    args.label = _resolve(args.label)
    args.model_config = _resolve(args.model_config)
    args.gpu_config = _resolve(args.gpu_config)
    args.result_path = _resolve(args.result_path)
    args.cache_dir = _resolve(args.cache_dir)
    args.logs_dir = _resolve(args.logs_dir)
    args.state_file = _resolve(args.state_file)
    args.formal_launcher = _resolve(args.formal_launcher)
    args.gpus = _split_csv(args.gpus, field="--gpus")
    if args.prewarm_workers < 1:
        parser.error("--prewarm_workers 必须大于 0")
    if args.eval_workers < 1:
        parser.error("--eval_workers 必须大于 0")
    if args.eval_grids and (args.eval_out is None or args.eval_manifest is None):
        parser.error("启用 --eval-grids 时必须同时提供 --eval-out 和 --eval-manifest")
    if args.eval_out is not None:
        args.eval_out = _resolve(args.eval_out)
    if args.eval_manifest is not None:
        args.eval_manifest = _resolve(args.eval_manifest)
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args._prewarm_cancer:
        return _prewarm_one(args, args._prewarm_cancer.upper())
    if args.plan is not None:
        if any(value is not None for value in (args.arms, args.cancers, args.seeds)):
            raise ValueError("--plan 与 --arms/--cancers/--seeds 不能混用")
        runs = load_plan(_resolve(args.plan, Path.cwd()))
    else:
        if any(value is None for value in (args.arms, args.cancers, args.seeds)):
            raise ValueError("不使用 --plan 时必须同时提供 --arms/--cancers/--seeds")
        runs = generate_runs(args.arms, args.cancers, args.seeds)
    return run_scheduler(args, runs)


if __name__ == "__main__":
    raise SystemExit(main())
