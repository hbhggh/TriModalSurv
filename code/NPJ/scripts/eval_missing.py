#!/usr/bin/env python3
"""使用冻结 NPJ checkpoint 评测固定缺失格点的 M0-real 与 M1。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


NPJ_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG = NPJ_ROOT / "model" / "config" / "surv_multimodal_mainmoe_uni2.yml"
CANCERS: Tuple[str, ...] = ("BLCA", "BRCA", "LUAD", "LGG", "UCEC")
MASKABLE_MODALITIES: Tuple[str, ...] = ("rna", "text")
MANIFEST_RATES: Tuple[int, ...] = (25, 50, 75)
ALL_GRIDS: Tuple[str, ...] = (
    "none",
    "rna_25",
    "rna_50",
    "rna_75",
    "text_25",
    "text_50",
    "text_75",
    "both_25",
    "both_50",
    "both_75",
    "rna_100",
    "text_100",
    "both_100",
)
TRUE_VALUES = {"1", "true"}
FALSE_VALUES = {"0", "false", ""}


def grid_parts(grid: str) -> Tuple[str | None, int]:
    if grid == "none":
        return None, 0
    try:
        mode, rate_text = grid.rsplit("_", 1)
        rate = int(rate_text)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"无效缺失格点: {grid!r}") from exc
    if mode not in {"rna", "text", "both"} or rate not in {25, 50, 75, 100}:
        raise ValueError(f"无效缺失格点: {grid!r}")
    return mode, rate


def parse_grids(value: str) -> List[str]:
    if value.strip().lower() == "all":
        return list(ALL_GRIDS)
    grids = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not grids:
        raise ValueError("--grids 不能为空")
    if len(grids) != len(set(grids)):
        raise ValueError("--grids 不得包含重复格点")
    for grid in grids:
        grid_parts(grid)
    return grids


def masked_modalities(grid: str) -> Tuple[str, ...]:
    mode, _ = grid_parts(grid)
    if mode is None:
        return ()
    if mode == "both":
        return MASKABLE_MODALITIES
    return (mode,)


def _parse_bool(value: object, *, context: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{context} 不是布尔值: {value!r}")


def manifest_members(
    manifest_path: Path,
    grid: str,
    patient_ids: Iterable[str],
    cancer: str,
) -> Set[str]:
    """返回当前癌种、当前 dataset 中被指定格点选中的患者。"""
    mode, rate = grid_parts(grid)
    allowed = set(patient_ids)
    if mode is None:
        return set()
    if rate == 100:
        return allowed

    members: Set[str] = set()
    seen: Set[str] = set()
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"patient_id", "cancer", grid}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"manifest 缺少列: {sorted(missing)}")
        for line_number, row in enumerate(reader, start=2):
            patient_id = (row.get("patient_id") or "").strip()
            if patient_id in seen:
                raise ValueError(f"manifest 患者重复: {patient_id}")
            seen.add(patient_id)
            row_cancer = (row.get("cancer") or "").strip().upper()
            selected = _parse_bool(row[grid], context=f"第 {line_number} 行 {grid}")
            if row_cancer == cancer and patient_id in allowed and selected:
                members.add(patient_id)
    return members


def grid_sha256(grid: str, patient_ids: Iterable[str], members: Set[str]) -> str:
    allowed = set(patient_ids)
    digest = hashlib.sha256()
    for patient_id in sorted(allowed & members):
        for modality in masked_modalities(grid):
            digest.update(f"{patient_id}\t{modality}\n".encode("utf-8"))
    return digest.hexdigest()


def grid_mask_counts(grid: str, members: Set[str]) -> Dict[str, int]:
    modalities = set(masked_modalities(grid))
    return {
        "n_masked_rna": len(members) if "rna" in modalities else 0,
        "n_masked_text": len(members) if "text" in modalities else 0,
    }


def dual_risk_from_logits(logits):
    """复现 A=raw cumprod 与 B=sigmoid+clamp cumprod 两种风险。"""
    import torch

    if not torch.is_tensor(logits) or logits.ndim != 2:
        raise ValueError("logits 必须是二维 torch.Tensor")
    risk_a = -torch.sum(torch.cumprod(1.0 - logits, dim=1), dim=1)
    hazards_b = torch.clamp(torch.sigmoid(logits), 1e-6, 1.0 - 1e-6)
    risk_b = -torch.sum(torch.cumprod(1.0 - hazards_b, dim=1), dim=1)
    return risk_a, risk_b


def dual_cindex(logits, survival_months, censorship) -> Tuple[float, float]:
    from sksurv.metrics import concordance_index_censored

    risk_a, risk_b = dual_risk_from_logits(logits)
    event = (1.0 - censorship.numpy()).astype(bool)
    times = survival_months.numpy()
    cindex_a = concordance_index_censored(event, times, risk_a.numpy())[0]
    cindex_b = concordance_index_censored(event, times, risk_b.numpy())[0]
    return float(cindex_a), float(cindex_b)


def strip_data_parallel_prefix(state_dict: Mapping[str, object]) -> Dict[str, object]:
    normalized: Dict[str, object] = {}
    for key, value in state_dict.items():
        normalized_key = key[7:] if key.startswith("module.") else key
        if normalized_key in normalized:
            raise ValueError(f"checkpoint key 去除 module. 后冲突: {normalized_key}")
        normalized[normalized_key] = value
    return normalized


def extract_state_dict(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise TypeError("checkpoint 必须是 state_dict 或包含 state_dict 的映射")
    for key in ("state_dict", "model_state_dict"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            return nested
    return payload


def load_checkpoint(model, checkpoint: Path, device) -> None:
    import torch

    try:
        payload = torch.load(checkpoint, map_location=device, weights_only=True)
    except TypeError:
        payload = torch.load(checkpoint, map_location=device)
    state_dict = strip_data_parallel_prefix(extract_state_dict(payload))
    model.load_state_dict(state_dict, strict=True)


def compute_training_feature_means(dataset):
    """对 train split 中天然非缺失的原始特征做逐元素在线均值。"""
    import numpy as np
    import torch

    means = {}
    sample_counts: Dict[str, int] = {}
    for modality in MASKABLE_MODALITIES:
        expected_shape = tuple(dataset.fallback_shapes[modality])
        total = None
        count = 0
        modality_data = dataset.dict_data.get(modality, {})
        for patient_id in dataset.selected_pids:
            raw = modality_data.get(patient_id)
            if raw is None:
                continue
            array = np.asarray(raw, dtype=np.float32)
            if tuple(array.shape) != expected_shape:
                raise ValueError(
                    f"train {modality} 特征形状错误: pid={patient_id}, "
                    f"actual={tuple(array.shape)}, expected={expected_shape}"
                )
            tensor = torch.from_numpy(array.copy()).to(dtype=torch.float64)
            total = tensor if total is None else total + tensor
            count += 1
        if total is None or count == 0:
            raise ValueError(f"train split 没有可用于均值的 {modality} 完整样本")
        means[modality] = (total / count).to(dtype=torch.float32)
        sample_counts[modality] = count
    return means, sample_counts


def apply_m1_feature_means(batch: Dict[str, object], means: Mapping[str, object]) -> None:
    """仅替换 valid=False 的特征；valid 标志保留供结果记录。"""
    for modality in MASKABLE_MODALITIES:
        valid_key = f"{modality}_valid"
        if modality not in batch or valid_key not in batch:
            raise KeyError(f"batch 缺少 {modality} 或 {valid_key}")
        invalid = ~batch[valid_key].bool()
        if not invalid.any():
            continue
        values = batch[modality]
        mean = means[modality].to(dtype=values.dtype, device=values.device)
        if tuple(values.shape[1:]) != tuple(mean.shape):
            raise ValueError(
                f"M1 {modality} 均值形状不匹配: batch={tuple(values.shape[1:])}, "
                f"mean={tuple(mean.shape)}"
            )
        values = values.clone()
        values[invalid] = mean
        batch[modality] = values


def format_grid_result(
    cindex_a: float,
    cindex_b: float,
    n_test: int,
    counts: Mapping[str, int],
    grid_sha: str,
) -> Dict[str, object]:
    return {
        "cindex_A": float(cindex_a),
        "cindex_B": float(cindex_b),
        "n_test": int(n_test),
        "n_masked_rna": int(counts["n_masked_rna"]),
        "n_masked_text": int(counts["n_masked_text"]),
        "grid_sha": grid_sha,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_dataset_labels(source: Path, destination: Path) -> Path:
    """当前 survival dataset 强制读取 label；缺列时仅在临时副本补 0。"""
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or ())
        required = {
            "patient_id",
            "cancer_type",
            "split",
            "survival_months",
            "censorship",
        }
        missing = required - set(fieldnames)
        if missing:
            raise ValueError(f"label CSV 缺少列: {sorted(missing)}")
        if "label" in fieldnames:
            return source.resolve()
        rows = list(reader)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*fieldnames, "label"], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "label": 0})
    return destination.resolve()


def _load_runtime():
    npj_root_text = str(NPJ_ROOT)
    if npj_root_text not in sys.path:
        sys.path.insert(0, npj_root_text)
    import main_survival
    from loc_utils_3yr.tcga_dataset import TCGASurDataset

    return main_survival, TCGASurDataset


def _resolve_modalities(main_survival, config):
    modalities = {
        key: config.parse_to_modality(value)
        for key, value in config.obj.modality.items()
    }
    for modality in modalities.values():
        path = Path(modality.path)
        if not path.is_absolute():
            path = NPJ_ROOT / path
        modality.path = str(path.resolve())
    return modalities


def _make_dataset(
    dataset_class,
    label_path: Path,
    modalities,
    config,
    cancer: str,
    split: str,
    manifest: Path | None = None,
    grid: str | None = None,
):
    return dataset_class(
        str(label_path),
        modalities,
        split,
        config.obj.task_type,
        img_select=config.obj.img_select,
        n_image_tokens=int(config.obj.network.n_token),
        cancer_types=cancer,
        network_type="MainModalityMoE",
        missing_manifest=str(manifest) if manifest is not None else None,
        missing_grid=grid,
    )


def configure_missing_grid_inplace(
    dataset,
    manifest_path: Path,
    grid: str,
    cancer: str,
) -> Set[str]:
    """在同一个 dataset 上切换缺失格点，并返回应被遮挡的患者集合。"""
    mode, rate = grid_parts(grid)
    patient_ids = list(dataset.selected_pids)
    members = manifest_members(manifest_path, grid, patient_ids, cancer)
    dataset.missing_manifest = (
        str(manifest_path) if rate in MANIFEST_RATES else None
    )
    dataset.missing_grid = None if grid == "none" else grid
    dataset.missing_mode = mode
    dataset.missing_set = set(members)
    return members


def _make_test_dataset_legacy(
    dataset_class,
    label_path: Path,
    modalities,
    config,
    cancer: str,
    manifest_path: Path,
    grid: str,
):
    """保留逐格点重建方式，仅供新旧路径合成对拍。"""
    _, rate = grid_parts(grid)
    return _make_dataset(
        dataset_class,
        label_path,
        modalities,
        config,
        cancer,
        "test",
        manifest=manifest_path if rate in MANIFEST_RATES else None,
        grid=None if grid == "none" else grid,
    )


def iter_reused_grid_datasets(
    dataset,
    manifest_path: Path,
    grids: Iterable[str],
    cancer: str,
):
    """逐格点原地切换并产出同一个 dataset 对象。"""
    for grid in grids:
        members = configure_missing_grid_inplace(
            dataset, manifest_path, grid, cancer
        )
        yield grid, dataset, members


def _collect_logits(model, loader, device, arm: str, means, m1_mark_valid: bool = False):
    import torch

    logits_list = []
    times_list = []
    censorship_list = []
    with torch.no_grad():
        for batch in loader:
            if arm == "m1":
                apply_m1_feature_means(batch, means)
                if m1_mark_valid:
                    # 指挥官小修（E0m，2026-09-06）：均值盲补后标记 valid，
                    # 使 NPJC 的 key_padding_mask 不再屏蔽填充 token（默认关，gate 版 M1 行为不变）。
                    for modality in MASKABLE_MODALITIES:
                        batch[f"{modality}_valid"] = torch.ones_like(batch[f"{modality}_valid"])

            survival_months = batch.pop("survival_months")
            batch.pop("survival_months_bin")
            censorship = batch.pop("censorship")
            cancer_type = batch.pop("cancer_type")
            batch.pop("label", None)
            batch.pop("patient_id", None)
            batch.pop("idx", None)
            model_input = {
                key: value.to(device, dtype=torch.float)
                for key, value in batch.items()
            }
            output = model(model_input, cancer_type=cancer_type)
            logits = output[0] if isinstance(output, tuple) else output
            logits_list.append(logits.detach().float().cpu())
            times_list.append(survival_months.detach().float().cpu())
            censorship_list.append(censorship.detach().float().cpu())

    if not logits_list:
        raise ValueError("test loader 为空")
    return (
        torch.cat(logits_list, dim=0),
        torch.cat(times_list, dim=0),
        torch.cat(censorship_list, dim=0),
    )


def _atomic_json_dump(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def run_evaluation(args: argparse.Namespace) -> Path:
    import numpy as np
    import torch
    from torch.utils.data import DataLoader

    checkpoint_path = args.ckpt.resolve()
    manifest_path = args.manifest.resolve()
    label_source = args.label.resolve()
    output_dir = args.out_dir.resolve()
    for role, path in (
        ("checkpoint", checkpoint_path),
        ("manifest", manifest_path),
        ("label CSV", label_source),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{role} 不存在: {path}")

    main_survival, dataset_class = _load_runtime()
    config = main_survival.YmlConfig(str(MODEL_CONFIG))
    modalities = _resolve_modalities(main_survival, config)
    cancer = args.cancer.upper()
    grids = parse_grids(args.grids)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = main_survival.load_model(
        network_type=getattr(args, "network_type", "MainModalityMoE"),
        device=device,
        modalities=modalities,
        hidden_size=256,
        pred_dim=int(config.obj.network.pred_dim),
        n_token=int(config.obj.network.n_token),
        cancer_types=[cancer],
        compensator=getattr(args, "compensator", "none"),
        fusion_type=getattr(args, "fusion_type", "gate"),
    )
    load_checkpoint(model, checkpoint_path, device)
    model.to(device)
    model.eval()

    grid_results: Dict[str, Dict[str, object]] = {}
    mean_counts: Dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix="npj-eval-missing-") as temporary:
        temporary_root = Path(temporary)
        label_path = prepare_dataset_labels(
            label_source, temporary_root / "labels_with_dataset_label.csv"
        )
        previous_cwd = Path.cwd()
        os.chdir(temporary_root)
        # 指挥官小修（2026-09-02）：dataset 缓存目录是相对路径 tmp_sur_cache，chdir 到临时目录后永不命中。
        # 在临时目录放符号链接指向真实缓存，并在评测期禁写缓存（无需写、杜绝并发写）。
        real_cache = NPJ_ROOT / "tmp_sur_cache"
        if real_cache.is_dir() and not (temporary_root / "tmp_sur_cache").exists():
            (temporary_root / "tmp_sur_cache").symlink_to(real_cache, target_is_directory=True)
        if hasattr(dataset_class, "_save_cache"):
            dataset_class._save_cache = lambda self: None
        try:
            means = None
            if args.arm == "m1":
                train_dataset = _make_dataset(
                    dataset_class,
                    label_path,
                    modalities,
                    config,
                    cancer,
                    "train",
                )
                means, mean_counts = compute_training_feature_means(train_dataset)

            test_dataset = _make_dataset(
                dataset_class,
                label_path,
                modalities,
                config,
                cancer,
                "test",
            )
            for grid, reused_dataset, expected_members in iter_reused_grid_datasets(
                test_dataset, manifest_path, grids, cancer
            ):
                if reused_dataset is not test_dataset:
                    raise RuntimeError("内存格点切换意外替换了 dataset 对象")
                patient_ids = list(test_dataset.selected_pids)
                actual_members = set(test_dataset.missing_set) & set(patient_ids)
                if actual_members != expected_members:
                    raise ValueError(
                        f"dataset 与 manifest 格点成员不一致: grid={grid}, "
                        f"dataset={len(actual_members)}, manifest={len(expected_members)}"
                    )

                loader = DataLoader(
                    test_dataset,
                    shuffle=False,
                    batch_size=32,
                    num_workers=0,
                )
                logits, times, censorship = _collect_logits(
                    model, loader, device, args.arm, means,
                    m1_mark_valid=bool(getattr(args, "m1_mark_valid", False)),
                )
                cindex_a, cindex_b = dual_cindex(logits, times, censorship)
                counts = grid_mask_counts(grid, expected_members)
                grid_results[grid] = format_grid_result(
                    cindex_a,
                    cindex_b,
                    len(test_dataset),
                    counts,
                    grid_sha256(grid, patient_ids, expected_members),
                )
                print(
                    f"{grid}: A={cindex_a:.6f} B={cindex_b:.6f} "
                    f"n={len(test_dataset)} rna={counts['n_masked_rna']} "
                    f"text={counts['n_masked_text']}"
                )
        finally:
            os.chdir(previous_cwd)

    payload = {
        "arm": args.arm,
        "cancer": cancer,
        "seed": args.seed,
        "checkpoint": str(checkpoint_path),
        "manifest": str(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "label": str(label_source),
        "model_config": str(MODEL_CONFIG),
        "hidden_size": 256,
        "m1_train_nonmissing_counts": mean_counts,
        "grids": grid_results,
    }
    output_path = output_dir / f"{args.arm}_{cancer}_s{args.seed}.json"
    _atomic_json_dump(output_path, payload)
    print(f"OUTPUT_JSON={output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, type=str.lower, choices=("m0real", "m1"))
    parser.add_argument("--cancer", required=True, type=str.upper, choices=CANCERS)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--ckpt", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--grids", default="all", help="all 或逗号分隔格点")
    parser.add_argument("--label", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    # 指挥官小修（2026-09-02）：评测带补偿器的 ckpt（M2/M1b）时构建同结构模型
    parser.add_argument("--compensator", default="none", choices=("none", "capr", "bank"))
    # 指挥官小修（单 γ 配套）：评测 NPJ-C 骨架 ckpt
    parser.add_argument("--network_type", default="MainModalityMoE", choices=("MainModalityMoE", "NPJC"))
    # 指挥官小修（NPJ-D 消融，2026-09-06）：评测 d0（去 GatedFusion 等权均值）ckpt 时构建同结构模型
    parser.add_argument("--fusion_type", default="gate", choices=("gate", "mean"))
    # 指挥官小修（E0m，2026-09-06）：m1 均值盲补后把 text/rna 标记为 valid（NPJC 专用；默认关）
    parser.add_argument("--m1-mark-valid", dest="m1_mark_valid", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_evaluation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
