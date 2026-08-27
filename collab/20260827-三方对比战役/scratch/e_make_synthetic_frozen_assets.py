#!/usr/bin/env python3
"""使用真实 baseline 模型类构造未训练的合成 checkpoint。"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd
import torch


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def ensure_dataset_utils_import(baseline_root: Path) -> bool:
    """缺可选包时，仅提供 dataset_survival 导入所需的两个符号。"""

    if all(importlib.util.find_spec(name) is not None for name in ("torchvision", "torch_geometric")):
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
        return next(iter(iterator), default) if n == 0 else next(__import__("itertools").islice(iterator, n, None), default)

    module.generate_split = generate_split
    module.nth = nth
    sys.modules["utils.utils"] = module
    utils_package.utils = module
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, choices=("MCAT", "PORPOISE"))
    parser.add_argument("--trainval-csv", required=True, type=Path)
    parser.add_argument("--features-root", required=True, type=Path)
    parser.add_argument("--ckpt", required=True, type=Path)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    baseline_root = repo_root / "baselines" / args.lib
    dataset_utils_shimmed = ensure_dataset_utils_import(baseline_root)
    from datasets.dataset_survival import Generic_MIL_Survival_Dataset

    dataset_module = Path(__import__("datasets.dataset_survival", fromlist=["x"]).__file__).resolve()
    if baseline_root.resolve() not in dataset_module.parents:
        raise RuntimeError(f"dataset 导入来源错误: {dataset_module}")

    mode = "coattn" if args.lib == "MCAT" else "pathomic"
    with working_directory(baseline_root):
        dataset = Generic_MIL_Survival_Dataset(
            csv_path=str(args.trainval_csv.resolve()),
            mode=mode,
            apply_sig=args.lib == "MCAT",
            data_dir=str(args.features_root.resolve()),
            shuffle=False,
            seed=123,
            print_info=False,
            patient_strat=False,
            n_bins=4,
            label_col="survival_months",
            ignore=[],
        )
    split = dataset.get_split_from_df(
        {"train": pd.Series(dataset.slide_data["case_id"].tolist())},
        split_key="train",
    )
    if split is None:
        raise RuntimeError("无法构造合成 train split")

    torch.manual_seed(123)
    if args.lib == "MCAT":
        from models.model_coattn import MCAT_Surv

        model = MCAT_Surv(
            fusion="concat",
            omic_sizes=split.omic_sizes,
            n_classes=4,
            path_input_dim=1536,
        )
        shape = {"omic_sizes": list(split.omic_sizes), "path_input_dim": 1536}
        model_name = "MCAT_Surv"
    else:
        from models.model_porpoise import PorpoiseMMF

        omic_input_dim = int(split.genomic_features.shape[1])
        model = PorpoiseMMF(
            omic_input_dim=omic_input_dim,
            path_input_dim=1536,
            fusion="concat",
            n_classes=4,
            gate_path=False,
            gate_omic=False,
            scale_dim1=8,
            scale_dim2=8,
            skip=False,
            dropinput=0.0,
            use_mlp=False,
        )
        shape = {"omic_input_dim": omic_input_dim, "path_input_dim": 1536}
        model_name = "PorpoiseMMF"

    args.ckpt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.ckpt)
    print(
        json.dumps(
            {
                "status": "SYNTHETIC_CHECKPOINT_CREATED",
                "lib": args.lib,
                "dataset_module": str(dataset_module),
                "model_class": model_name,
                "shape": shape,
                "checkpoint": str(args.ckpt.resolve()),
                "trained": False,
                "dataset_utils_import_shimmed": dataset_utils_shimmed,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
