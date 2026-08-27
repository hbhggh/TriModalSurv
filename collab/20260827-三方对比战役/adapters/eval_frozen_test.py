#!/usr/bin/env python3
"""MCAT/PORPOISE 冻结 checkpoint 的 test-only 生存评估与分箱审计。"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
import pandas as pd


SUPPORTED_LIBS = ("MCAT", "PORPOISE")
SUPPORTED_SPLITS = {"train", "valid", "test"}
N_BINS = 4
BIN_EPSILON = 1e-6


@dataclass(frozen=True)
class BinSpec:
    """记录原始 qcut 边界和与 baseline 一致的应用边界。"""

    qcut_edges: tuple[float, ...]
    applied_bins: tuple[float, ...]
    source_patient_ids: tuple[str, ...]


def repository_root() -> Path:
    """返回 TriModalSurv 根目录。"""

    return Path(__file__).resolve().parents[3]


def task_root() -> Path:
    """返回本次协作任务目录。"""

    return Path(__file__).resolve().parents[1]


def _normalise_patient_ids(series: pd.Series, *, field: str) -> pd.Series:
    values = series.astype(str).str.strip().str.upper()
    if values.eq("").any() or values.eq("NAN").any():
        raise ValueError(f"{field} 含空 patient id")
    return values


def _read_labels(path: Path, cancer: str) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 labels: {path}")
    labels = pd.read_csv(path, low_memory=False)
    required = {
        "patient_id",
        "cancer_type",
        "split",
        "survival_months",
        "censorship",
    }
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"labels 缺少必需列: {sorted(missing)}")
    labels = labels.copy()
    labels["patient_id"] = _normalise_patient_ids(labels["patient_id"], field="labels")
    labels["cancer_type"] = labels["cancer_type"].astype(str).str.strip().str.upper()
    labels["split"] = labels["split"].astype(str).str.strip().str.lower()
    labels = labels.loc[labels["cancer_type"] == cancer].copy()
    if labels.empty:
        raise ValueError(f"labels 中没有癌种 {cancer}")
    if labels["patient_id"].duplicated().any():
        duplicates = sorted(labels.loc[labels["patient_id"].duplicated(False), "patient_id"].unique())
        raise ValueError(f"labels 的 patient_id 重复: {duplicates}")
    invalid_splits = sorted(set(labels["split"]) - SUPPORTED_SPLITS)
    if invalid_splits:
        raise ValueError(f"labels 含不支持的 split: {invalid_splits}")
    labels["survival_months"] = pd.to_numeric(labels["survival_months"], errors="raise")
    labels["censorship"] = pd.to_numeric(labels["censorship"], errors="raise")
    if not np.isfinite(labels["survival_months"].to_numpy(dtype=float)).all():
        raise ValueError("labels survival_months 必须全部为有限数")
    if (labels["survival_months"] < 0).any():
        raise ValueError("labels survival_months 不得为负数")
    if not labels["censorship"].isin([0, 1]).all():
        raise ValueError("labels censorship 必须为 0 或 1")
    return labels.reset_index(drop=True)


def _read_adapted_csv(path: Path, *, role: str) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 {role} CSV: {path}")
    frame = pd.read_csv(path, low_memory=False)
    required = {"case_id", "slide_id", "survival_months", "censorship"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{role} CSV 缺少必需列: {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{role} CSV 为空")
    frame = frame.copy()
    frame["case_id"] = _normalise_patient_ids(frame["case_id"], field=f"{role} CSV")
    frame["slide_id"] = frame["slide_id"].astype(str).str.strip()
    if frame["slide_id"].eq("").any() or frame["slide_id"].eq("nan").any():
        raise ValueError(f"{role} CSV 含空 slide_id")
    frame["survival_months"] = pd.to_numeric(frame["survival_months"], errors="raise")
    frame["censorship"] = pd.to_numeric(frame["censorship"], errors="raise")
    if not np.isfinite(frame["survival_months"].to_numpy(dtype=float)).all():
        raise ValueError(f"{role} CSV survival_months 必须全部为有限数")
    if not frame["censorship"].isin([0, 1]).all():
        raise ValueError(f"{role} CSV censorship 必须为 0 或 1")
    for column in ("survival_months", "censorship"):
        inconsistent = frame.groupby("case_id", sort=False)[column].nunique(dropna=False)
        if (inconsistent > 1).any():
            offenders = sorted(inconsistent.index[inconsistent > 1])
            raise ValueError(f"{role} CSV 同一病人的 {column} 不一致: {offenders}")
    return frame


def _patient_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop_duplicates("case_id", keep="first").reset_index(drop=True)


def _assert_outcomes_match_labels(
    frame: pd.DataFrame, labels: pd.DataFrame, *, role: str
) -> None:
    patient_frame = _patient_rows(frame).set_index("case_id")
    label_frame = labels.set_index("patient_id")
    missing = sorted(set(patient_frame.index) - set(label_frame.index))
    if missing:
        raise ValueError(f"{role} CSV 含 labels/{labels.iloc[0]['cancer_type']} 之外的病人: {missing}")
    aligned = label_frame.loc[patient_frame.index]
    survival_equal = np.isclose(
        patient_frame["survival_months"].to_numpy(dtype=float),
        aligned["survival_months"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-10,
    )
    censorship_equal = (
        patient_frame["censorship"].to_numpy(dtype=int)
        == aligned["censorship"].to_numpy(dtype=int)
    )
    bad = patient_frame.index[~(survival_equal & censorship_equal)].tolist()
    if bad:
        raise ValueError(f"{role} CSV 与 labels 结局不一致: {bad}")


def compute_bin_spec(trainval: pd.DataFrame) -> BinSpec:
    """仅使用 trainval 未删失病人计算 qcut 边界。"""

    patients = _patient_rows(trainval)
    uncensored = patients.loc[patients["censorship"] < 1].copy()
    if len(uncensored) < N_BINS:
        raise ValueError(
            f"trainval 未删失病人数 {len(uncensored)} 少于 n_bins={N_BINS}"
        )
    try:
        _, qcut_edges = pd.qcut(
            uncensored["survival_months"], q=N_BINS, retbins=True, labels=False
        )
    except ValueError as exc:
        raise ValueError(f"trainval 未删失病人无法形成 {N_BINS} 个 qcut bins: {exc}") from exc
    if len(qcut_edges) != N_BINS + 1 or not np.all(np.diff(qcut_edges) > 0):
        raise ValueError(f"qcut 边界非严格递增: {qcut_edges.tolist()}")
    applied_bins = np.asarray(qcut_edges, dtype=float).copy()
    applied_bins[0] = float(patients["survival_months"].min()) - BIN_EPSILON
    applied_bins[-1] = float(patients["survival_months"].max()) + BIN_EPSILON
    if not np.all(np.diff(applied_bins) > 0):
        raise ValueError(f"应用边界非严格递增: {applied_bins.tolist()}")
    return BinSpec(
        qcut_edges=tuple(float(value) for value in qcut_edges),
        applied_bins=tuple(float(value) for value in applied_bins),
        source_patient_ids=tuple(sorted(uncensored["case_id"].tolist())),
    )


def _json_floats(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values]


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _ensure_output_is_safe(out: Path, ckpt: Path, features_root: Path) -> None:
    if out.suffix.lower() != ".json":
        raise ValueError(f"--out 必须是 .json 文件: {out}")
    resolved = out.resolve()
    repo = repository_root()
    for forbidden in (repo / "baselines", repo / "NPJ"):
        if _is_within(resolved, forbidden):
            raise ValueError(f"禁止将评估结果写入 {forbidden}: {resolved}")
    synthetic_root = task_root() / "scratch" / "e_eval_frozen_synthetic"
    if _is_within(resolved, ckpt.resolve().parent) and not _is_within(resolved, synthetic_root):
        raise ValueError("--out 不得写入 checkpoint/训练目录")
    if _is_within(resolved, features_root.resolve()) and not _is_within(resolved, synthetic_root):
        raise ValueError("--out 不得写入特征目录")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            json.dump(payload, temporary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            temporary.write("\n")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _ensure_dataset_utils_import(baseline_root: Path) -> bool:
    """本机缺无关可选包时，隔离 baseline utils 的重导入副作用。"""

    optional_modules = ("torchvision", "torch_geometric")
    if all(importlib.util.find_spec(name) is not None for name in optional_modules):
        return False
    try:
        utils_package = importlib.import_module("utils")
    except ModuleNotFoundError:
        utils_package = types.ModuleType("utils")
        utils_package.__path__ = [str(baseline_root / "utils")]
        sys.modules["utils"] = utils_package
    module = types.ModuleType("utils.utils")

    def generate_split(*_args, **_kwargs):
        raise RuntimeError("frozen evaluation 不应调用 generate_split")

    def nth(iterator, n, default=None):
        if n is None:
            return default
        return next(importlib.import_module("itertools").islice(iterator, n, None), default)

    module.generate_split = generate_split
    module.nth = nth
    sys.modules["utils.utils"] = module
    utils_package.utils = module
    return True


def _import_baseline(args: argparse.Namespace) -> dict[str, Any]:
    baseline_root = repository_root() / "baselines" / args.lib
    python_paths = {
        Path(entry or Path.cwd()).resolve()
        for entry in sys.path
        if entry is not None
    }
    if baseline_root.resolve() not in python_paths:
        raise RuntimeError(
            f"PYTHONPATH 必须显式包含 {baseline_root}，不得复制或内置 baseline 类"
        )
    dataset_utils_shimmed = _ensure_dataset_utils_import(baseline_root)
    dataset_module = importlib.import_module("datasets.dataset_survival")
    dataset_path = Path(dataset_module.__file__).resolve()
    if baseline_root.resolve() not in dataset_path.parents:
        raise RuntimeError(f"dataset 导入来源不是 {args.lib}: {dataset_path}")
    if args.lib == "MCAT":
        model_module = importlib.import_module("models.model_coattn")
        model_class = model_module.MCAT_Surv
        mode = "coattn"
        apply_sig = True
    else:
        model_module = importlib.import_module("models.model_porpoise")
        model_class = model_module.PorpoiseMMF
        mode = "pathomic"
        apply_sig = False
    model_path = Path(model_module.__file__).resolve()
    if baseline_root.resolve() not in model_path.parents:
        raise RuntimeError(f"model 导入来源不是 {args.lib}: {model_path}")
    return {
        "baseline_root": baseline_root,
        "dataset_module_path": dataset_path,
        "model_module_path": model_path,
        "dataset_class": dataset_module.Generic_MIL_Survival_Dataset,
        "split_class": dataset_module.Generic_Split,
        "model_class": model_class,
        "mode": mode,
        "apply_sig": apply_sig,
        "dataset_utils_import_shimmed": dataset_utils_shimmed,
    }


def _import_concordance_index():
    try:
        from sksurv.metrics import concordance_index_censored

        return concordance_index_censored, "environment"
    except ModuleNotFoundError as exc:
        if exc.name != "sksurv" and not str(exc.name).startswith("sksurv."):
            raise
    vendor = task_root() / "scratch" / "e_sksurv_vendor"
    if not vendor.is_dir():
        raise ModuleNotFoundError(
            "常规 import sksurv 失败，且找不到本机自测 vendor: " + str(vendor)
        )
    sys.path.insert(0, str(vendor))
    from sksurv.metrics import concordance_index_censored

    return concordance_index_censored, "scratch/e_sksurv_vendor fallback"


def _build_patient_dict(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        case_id: group["slide_id"].astype(str).to_numpy()
        for case_id, group in frame.groupby("case_id", sort=False)
    }


def _prepare_test_patient_rows(
    test_rows: pd.DataFrame, dataset: Any
) -> tuple[pd.DataFrame, list[int]]:
    patients = test_rows.drop_duplicates("case_id", keep="first").copy().reset_index(drop=True)
    if "label" in patients.columns or "disc_label" in patients.columns:
        raise ValueError("adapted full CSV 不得预先含 label/disc_label 列")
    internal_edges = np.asarray(dataset.bins, dtype=float)[1:-1]
    disc_labels = np.searchsorted(
        internal_edges,
        patients["survival_months"].to_numpy(dtype=float),
        side="right",
    ).astype(int)
    if ((disc_labels < 0) | (disc_labels >= N_BINS)).any():
        raise ValueError(f"test 分箱超出 [0,{N_BINS - 1}]")
    patients.insert(2, "label", disc_labels)
    patients["slide_id"] = patients["case_id"]
    patients["disc_label"] = disc_labels.astype(float)
    for index, disc_label in enumerate(disc_labels):
        censorship = int(patients.at[index, "censorship"])
        patients.at[index, "label"] = dataset.label_dict[(int(disc_label), censorship)]
    expected_columns = list(dataset.slide_data.columns)
    missing_columns = [column for column in expected_columns if column not in patients.columns]
    extra_columns = [column for column in patients.columns if column not in expected_columns]
    if missing_columns or extra_columns:
        raise ValueError(
            "test patient-level 列契约与 baseline dataset 不一致: "
            f"missing={missing_columns}, extra={extra_columns}"
        )
    patients = patients[expected_columns]
    return patients, disc_labels.tolist()


def _load_checkpoint(torch: Any, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 checkpoint: {path}")
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        checkpoint = torch.load(path, map_location="cpu")
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    elif isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    else:
        state_dict = checkpoint
    if not isinstance(state_dict, dict) or not state_dict:
        raise ValueError("checkpoint 不是非空 state_dict")
    if all(str(key).startswith("module.") for key in state_dict):
        state_dict = {str(key)[7:]: value for key, value in state_dict.items()}
    return state_dict


def _preflight_feature_paths(patient_dict: dict[str, np.ndarray], features_root: Path) -> int:
    if not features_root.is_dir():
        raise FileNotFoundError(f"找不到 features root: {features_root}")
    checked = 0
    for patient_id, slide_ids in patient_dict.items():
        for slide_id in slide_ids:
            path = features_root / "pt_files" / f"{str(slide_id).rstrip('.svs')}.pt"
            if not path.is_file():
                raise FileNotFoundError(f"test 病人 {patient_id} 缺特征: {path}")
            checked += 1
    return checked


def _make_dataset_and_test_split(
    args: argparse.Namespace,
    imports: dict[str, Any],
    full: pd.DataFrame,
    labels: pd.DataFrame,
) -> tuple[Any, Any, BinSpec, int]:
    split_by_patient = labels.set_index("patient_id")["split"].to_dict()
    full_patients = set(full["case_id"])
    trainval_ids = {
        patient_id
        for patient_id in full_patients
        if split_by_patient.get(patient_id) in {"train", "valid"}
    }
    train_ids = {
        patient_id for patient_id in full_patients if split_by_patient.get(patient_id) == "train"
    }
    valid_ids = {
        patient_id for patient_id in full_patients if split_by_patient.get(patient_id) == "valid"
    }
    test_ids = {
        patient_id for patient_id in full_patients if split_by_patient.get(patient_id) == "test"
    }
    if not train_ids or not valid_ids or not test_ids:
        raise ValueError(
            "评估需要非空 train/valid/test 交集: "
            f"train={len(train_ids)}, valid={len(valid_ids)}, test={len(test_ids)}"
        )
    trainval_rows = full.loc[full["case_id"].isin(trainval_ids)].copy()
    test_rows = full.loc[full["case_id"].isin(test_ids)].copy()
    bin_spec = compute_bin_spec(trainval_rows)
    with tempfile.TemporaryDirectory(prefix="eval_frozen_test_trainval_") as temporary_dir:
        trainval_csv = Path(temporary_dir) / "trainval.csv"
        trainval_rows.to_csv(trainval_csv, index=False)
        with _working_directory(imports["baseline_root"]):
            dataset = imports["dataset_class"](
                csv_path=str(trainval_csv),
                mode=imports["mode"],
                apply_sig=imports["apply_sig"],
                data_dir=str(args.features_root.resolve()),
                shuffle=False,
                seed=123,
                print_info=False,
                patient_strat=False,
                n_bins=N_BINS,
                label_col="survival_months",
                ignore=[],
            )
    if not np.allclose(
        np.asarray(dataset.bins, dtype=float),
        np.asarray(bin_spec.applied_bins, dtype=float),
        rtol=0.0,
        atol=1e-12,
    ):
        raise AssertionError(
            f"baseline bins 与 trainval-only 独立重算不一致: "
            f"baseline={dataset.bins}, expected={bin_spec.applied_bins}"
        )
    train_split = dataset.get_split_from_df(
        {"train": pd.Series(sorted(train_ids))}, split_key="train"
    )
    if train_split is None:
        raise ValueError("无法用 labels/train 构造 scaler 来源 split")
    patient_dict = _build_patient_dict(test_rows)
    test_patient_rows, _ = _prepare_test_patient_rows(test_rows, dataset)
    test_split = imports["split_class"](
        test_patient_rows,
        metadata=dataset.metadata,
        mode=imports["mode"],
        signatures=dataset.signatures,
        data_dir=str(args.features_root.resolve()),
        label_col=dataset.label_col,
        patient_dict=patient_dict,
        num_classes=dataset.num_classes,
    )
    test_split.apply_scaler(train_split.get_scaler())
    checked_slides = _preflight_feature_paths(patient_dict, args.features_root.resolve())
    return train_split, test_split, bin_spec, checked_slides


def _build_model(args: argparse.Namespace, imports: dict[str, Any], split: Any) -> tuple[Any, dict[str, Any]]:
    if args.lib == "MCAT":
        omic_sizes = [int(value) for value in split.omic_sizes]
        if len(omic_sizes) != 6 or any(value <= 0 for value in omic_sizes):
            raise ValueError(f"MCAT signature 维度必须是 6 个正整数: {omic_sizes}")
        config = {
            "fusion": "concat",
            "omic_sizes": omic_sizes,
            "n_classes": 4,
            "path_input_dim": 1536,
        }
        model = imports["model_class"](**config)
    else:
        omic_input_dim = int(split.genomic_features.shape[1])
        if omic_input_dim <= 0:
            raise ValueError(f"PORPOISE mutsig 维度非法: {omic_input_dim}")
        config = {
            "omic_input_dim": omic_input_dim,
            "path_input_dim": 1536,
            "fusion": "concat",
            "n_classes": 4,
            "gate_path": False,
            "gate_omic": False,
            "scale_dim1": 8,
            "scale_dim2": 8,
            "skip": False,
            "dropinput": 0.0,
            "use_mlp": False,
        }
        model = imports["model_class"](**config)
    return model, config


def _forward_patients(args: argparse.Namespace, model: Any, test_split: Any) -> list[dict[str, Any]]:
    torch = importlib.import_module("torch")
    records: list[dict[str, Any]] = []
    model.eval()
    with torch.inference_mode():
        for index in range(len(test_split)):
            patient_id = str(test_split.slide_data.iloc[index]["case_id"])
            disc_label = int(test_split.slide_data.iloc[index]["disc_label"])
            if args.lib == "MCAT":
                item = test_split[index]
                path_features = item[0].to(dtype=torch.float32, device="cpu")
                omics = [tensor.to(dtype=torch.float32, device="cpu") for tensor in item[1:7]]
            else:
                path_features, genomic_features, _, _, _ = test_split[index]
                path_features = path_features.to(dtype=torch.float32, device="cpu")
                genomic_features = genomic_features.to(dtype=torch.float32, device="cpu")
            if path_features.ndim != 2 or path_features.shape[0] < 1 or path_features.shape[1] != 1536:
                raise ValueError(
                    f"{patient_id} 聚合特征必须为 [N,1536] 且 N>=1，"
                    f"实际 {tuple(path_features.shape)}"
                )
            if not torch.isfinite(path_features).all():
                raise ValueError(f"{patient_id} 聚合特征含 NaN/Inf")
            if args.lib == "MCAT":
                _, survival, _, _ = model(
                    x_path=path_features,
                    **{f"x_omic{position}": tensor for position, tensor in enumerate(omics, start=1)},
                )
            else:
                logits = model(x_path=path_features, x_omic=genomic_features)
                hazards = torch.sigmoid(logits)
                survival = torch.cumprod(1 - hazards, dim=1)
            if tuple(survival.shape) != (1, N_BINS):
                raise ValueError(
                    f"{patient_id} survival shape 应为 [1,{N_BINS}]，实际 {tuple(survival.shape)}"
                )
            risk = float((-torch.sum(survival, dim=1)).item())
            if not np.isfinite(risk):
                raise ValueError(f"{patient_id} risk 为 NaN/Inf")
            records.append(
                {
                    "patient_id": patient_id,
                    "risk": risk,
                    "survival_months": float(test_split.slide_data.iloc[index]["survival_months"]),
                    "censorship": int(test_split.slide_data.iloc[index]["censorship"]),
                    "event_observed": bool(1 - int(test_split.slide_data.iloc[index]["censorship"])),
                    "disc_label": disc_label,
                }
            )
    return records


def evaluate_frozen(args: argparse.Namespace) -> dict[str, Any]:
    _ensure_output_is_safe(args.out, args.ckpt, args.features_root)
    labels = _read_labels(args.labels, args.cancer)
    full = _read_adapted_csv(args.adapted_full_csv, role="full")
    _assert_outcomes_match_labels(full, labels, role="full")
    imports = _import_baseline(args)
    train_split, test_split, bin_spec, checked_slides = _make_dataset_and_test_split(
        args, imports, full, labels
    )
    model, model_config = _build_model(args, imports, test_split)
    torch = importlib.import_module("torch")
    model.load_state_dict(_load_checkpoint(torch, args.ckpt), strict=True)
    records = _forward_patients(args, model, test_split)
    if not records:
        raise ValueError("test-only dataset 为空")
    concordance_index_censored, sksurv_source = _import_concordance_index()
    event_observed = np.asarray([row["event_observed"] for row in records], dtype=bool)
    event_times = np.asarray([row["survival_months"] for row in records], dtype=float)
    risks = np.asarray([row["risk"] for row in records], dtype=float)
    c_index = float(
        concordance_index_censored(
            event_observed,
            event_times,
            risks,
            tied_tol=1e-8,
        )[0]
    )
    if not np.isfinite(c_index):
        raise ValueError("c-index 为 NaN/Inf")
    result: dict[str, Any] = {
        "schema_version": 1,
        "lib": args.lib,
        "cancer": args.cancer,
        "checkpoint": str(args.ckpt.resolve()),
        "adapted_full_csv": str(args.adapted_full_csv.resolve()),
        "labels": str(args.labels.resolve()),
        "features_root": str(args.features_root.resolve()),
        "device": "cpu",
        "dataset_class": type(test_split).__name__,
        "dataset_module": str(imports["dataset_module_path"]),
        "model_class": type(model).__name__,
        "model_module": str(imports["model_module_path"]),
        "model_config": model_config,
        "path_input_dim": 1536,
        "scaler_source_split": "train",
        "n_scaler_source": len(train_split),
        "bin_source_splits": ["train", "valid"],
        "n_bin_source_uncensored": len(bin_spec.source_patient_ids),
        "bin_source_patient_ids_sha256": hashlib.sha256(
            "\n".join(bin_spec.source_patient_ids).encode("utf-8")
        ).hexdigest(),
        "qcut_edges": _json_floats(bin_spec.qcut_edges),
        "applied_bins": _json_floats(bin_spec.applied_bins),
        "test_excluded_from_bins": True,
        "dataset_utils_import_shimmed": imports["dataset_utils_import_shimmed"],
        "sksurv_import_source": sksurv_source,
        "n_test_slides_checked": checked_slides,
        "feature_tensor_shape_checked_per_patient": True,
        "n_test": len(records),
        "patients": records,
        "c_index": c_index,
    }
    _write_json_atomic(args.out, result)
    print(
        f"{args.lib}/{args.cancer}: n_test={len(records)}, "
        f"c_index={c_index:.6f}, sksurv={sksurv_source}"
    )
    for row in records:
        print(
            f"patient={row['patient_id']} risk={row['risk']:.9f} "
            f"time={row['survival_months']:.9f} censorship={row['censorship']}"
        )
    print(f"JSON={args.out.resolve()}")
    return result


def assert_bins(args: argparse.Namespace) -> dict[str, Any]:
    labels = _read_labels(args.labels, args.cancer)
    trainval = _read_adapted_csv(args.adapted_trainval_csv, role="trainval")
    full = _read_adapted_csv(args.adapted_full_csv, role="full")
    _assert_outcomes_match_labels(trainval, labels, role="trainval")
    _assert_outcomes_match_labels(full, labels, role="full")

    split_by_patient = labels.set_index("patient_id")["split"].to_dict()
    full_patients = set(full["case_id"])
    trainval_patients = set(trainval["case_id"])
    test_in_trainval = sorted(
        patient_id
        for patient_id in trainval_patients
        if split_by_patient.get(patient_id) == "test"
    )
    if test_in_trainval:
        raise ValueError(f"trainval 含 test 病人: {test_in_trainval}")
    expected_trainval = {
        patient_id
        for patient_id in full_patients
        if split_by_patient.get(patient_id) in {"train", "valid"}
    }
    if trainval_patients != expected_trainval:
        raise ValueError(
            "trainval 病人集必须精确等于 full∩(train+valid): "
            f"缺失={sorted(expected_trainval - trainval_patients)}, "
            f"额外={sorted(trainval_patients - expected_trainval)}"
        )

    bin_spec = compute_bin_spec(trainval)
    full_bin_spec = compute_bin_spec(full)
    source_digest = hashlib.sha256(
        "\n".join(bin_spec.source_patient_ids).encode("utf-8")
    ).hexdigest()
    test_patients = sorted(
        patient_id
        for patient_id in full_patients
        if split_by_patient.get(patient_id) == "test"
    )
    result: dict[str, Any] = {
        "status": "PASS",
        "lib": args.lib,
        "cancer": args.cancer,
        "n_full": len(full_patients),
        "n_trainval": len(trainval_patients),
        "n_train": sum(split_by_patient[patient_id] == "train" for patient_id in trainval_patients),
        "n_valid": sum(split_by_patient[patient_id] == "valid" for patient_id in trainval_patients),
        "n_test": len(test_patients),
        "n_bin_source_uncensored": len(bin_spec.source_patient_ids),
        "bin_source_splits": ["train", "valid"],
        "bin_source_patient_ids_sha256": source_digest,
        "qcut_edges": _json_floats(bin_spec.qcut_edges),
        "applied_bins": _json_floats(bin_spec.applied_bins),
        "full_qcut_edges_audit_only": _json_floats(full_bin_spec.qcut_edges),
        "trainval_exact_match": True,
        "test_excluded_from_bins": True,
    }
    print(
        f"{args.lib}/{args.cancer}: train={result['n_train']}, "
        f"valid={result['n_valid']}, test={result['n_test']}"
    )
    print(f"qcut_edges(trainval uncensored only)={result['qcut_edges']}")
    print(f"applied_bins(trainval only)={result['applied_bins']}")
    print(f"full_qcut_edges(audit only, never applied)={result['full_qcut_edges_audit_only']}")
    print("trainval_contract=PASS; test_excluded_from_bins=PASS")
    print("ASSERT_BINS_JSON=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MCAT/PORPOISE 冻结 checkpoint 的 test-only 评估与分箱审计"
    )
    parser.add_argument("--lib", required=True, choices=SUPPORTED_LIBS)
    parser.add_argument("--cancer", required=True, type=lambda value: value.strip().upper())
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--adapted-full-csv", required=True, type=Path)
    parser.add_argument("--adapted-trainval-csv", type=Path)
    parser.add_argument("--assert-bins", action="store_true")
    parser.add_argument("--ckpt", type=Path)
    parser.add_argument("--features-root", type=Path)
    parser.add_argument("--out", type=Path)
    return parser


def _validate_mode_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.assert_bins:
        if args.adapted_trainval_csv is None:
            parser.error("--assert-bins 需要 --adapted-trainval-csv")
        return
    missing = [
        option
        for option, value in (
            ("--ckpt", args.ckpt),
            ("--features-root", args.features_root),
            ("--out", args.out),
        )
        if value is None
    ]
    if missing:
        parser.error("冻结评估缺少参数: " + ", ".join(missing))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_mode_args(parser, args)
    try:
        if args.assert_bins:
            assert_bins(args)
        else:
            evaluate_frozen(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
