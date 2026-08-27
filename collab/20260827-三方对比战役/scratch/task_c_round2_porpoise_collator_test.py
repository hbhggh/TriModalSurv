#!/usr/bin/env python3
"""Round 2 路 C：PORPOISE collator 的真实首批取数测试。"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest

import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[1]
PORPOISE_ROOT = REPO_ROOT / "baselines" / "PORPOISE"
BLCA_CSV = PORPOISE_ROOT / "datasets_csv" / "tcga_blca_all_clean.csv.zip"
BLCA_SPLIT = TASK_ROOT / "scratch" / "splits_mcat_blca" / "splits_0.csv"


def install_import_stubs() -> None:
    """只替代当前环境缺失、且本测试不会调用的导入边界。"""
    torchvision = types.ModuleType("torchvision")
    transforms = types.ModuleType("torchvision.transforms")
    torchvision.transforms = transforms
    sys.modules.setdefault("torchvision", torchvision)
    sys.modules.setdefault("torchvision.transforms", transforms)

    torch_geometric = types.ModuleType("torch_geometric")
    torch_geometric_data = types.ModuleType("torch_geometric.data")

    class Batch:
        pass

    torch_geometric_data.Batch = Batch
    torch_geometric.data = torch_geometric_data
    sys.modules.setdefault("torch_geometric", torch_geometric)
    sys.modules.setdefault("torch_geometric.data", torch_geometric_data)


@contextlib.contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


install_import_stubs()
sys.path.insert(0, str(PORPOISE_ROOT))

from datasets.dataset_survival import Generic_MIL_Survival_Dataset
from utils.utils import collate_MIL_survival_cluster, get_split_loader


class OfficialBlcaFirstBatchTests(unittest.TestCase):
    def fetch_first_batch(self, mode: str):
        self.assertTrue(BLCA_CSV.is_file(), f"缺少官方 BLCA CSV: {BLCA_CSV}")
        self.assertTrue(BLCA_SPLIT.is_file(), f"缺少 A1 split: {BLCA_SPLIT}")

        with tempfile.TemporaryDirectory(
            prefix=f"round2_porpoise_{mode}_", dir=TASK_ROOT / "scratch"
        ) as data_dir:
            data_root = Path(data_dir)
            pt_dir = data_root / "pt_files"
            pt_dir.mkdir(parents=True)
            official_df = pd.read_csv(BLCA_CSV, low_memory=False)
            official_df.insert(0, "Unnamed: 0", range(len(official_df)))
            legacy_metadata = [
                "Unnamed: 0",
                "case_id",
                "slide_id",
                "age",
                "site",
                "survival_months",
                "censorship",
                "is_female",
                "oncotree_code",
                "train",
            ]
            official_df = official_df[
                legacy_metadata
                + [column for column in official_df.columns if column not in legacy_metadata]
            ]
            compatible_csv = data_root / "tcga_blca_all_clean.csv.zip"
            official_df.to_csv(
                compatible_csv,
                index=False,
                compression={
                    "method": "zip",
                    "archive_name": "tcga_blca_all_clean.csv",
                },
            )
            if mode == "coattn":
                signature_dir = data_root / "datasets_csv_sig"
                signature_dir.mkdir()
                shutil.copyfile(
                    PORPOISE_ROOT / "datasets_csv" / "signatures.csv",
                    signature_dir / "signatures.csv",
                )
            with working_directory(data_root):
                dataset = Generic_MIL_Survival_Dataset(
                    csv_path=compatible_csv,
                    mode=mode,
                    apply_sig=(mode == "coattn"),
                    data_dir=data_dir,
                    shuffle=False,
                    seed=1,
                    print_info=False,
                    patient_strat=False,
                    n_bins=4,
                    label_col="survival_months",
                    ignore=[],
                )
            train_split, _ = dataset.return_splits(
                from_id=False, csv_path=BLCA_SPLIT
            )
            case_id = train_split.slide_data.loc[0, "case_id"]
            slide_ids = dataset.patient_dict[case_id]
            for slide_id in slide_ids:
                pt_path = pt_dir / f"{slide_id.rstrip('.svs')}.pt"
                torch.save(torch.randn(4, 1536, dtype=torch.float32), pt_path)

            loader = get_split_loader(
                train_split,
                training=False,
                testing=False,
                weighted=False,
                mode=mode,
                batch_size=1,
            )
            batch = next(iter(loader))
            return case_id, batch

    def test_pathomic_official_blca_first_batch(self):
        case_id, batch = self.fetch_first_batch("pathomic")
        path, omic, label, event_time, censorship = batch
        self.assertEqual(path.ndim, 2)
        self.assertEqual(path.shape[1], 1536)
        self.assertEqual(omic.ndim, 2)
        self.assertEqual(label.shape, (1,))
        self.assertEqual(event_time.shape, (1,))
        self.assertEqual(censorship.shape, (1,))
        self.assertEqual(omic.dtype, torch.float32)
        self.assertEqual(label.dtype, torch.int64)
        self.assertEqual(event_time.dtype, torch.float32)
        self.assertEqual(censorship.dtype, torch.float32)
        print(
            "PORPOISE FIRST BATCH PASS: "
            f"mode=pathomic case={case_id} path={tuple(path.shape)} "
            f"omic={tuple(omic.shape)} label={tuple(label.shape)}/{label.dtype} "
            f"event_time={tuple(event_time.shape)}/{event_time.dtype} "
            f"censorship={tuple(censorship.shape)}/{censorship.dtype}"
        )

    def test_coattn_official_blca_first_batch(self):
        case_id, batch = self.fetch_first_batch("coattn")
        path, *rest = batch
        omics = rest[:6]
        label, event_time, censorship = rest[6:]
        self.assertEqual(path.ndim, 2)
        self.assertEqual(path.shape[1], 1536)
        self.assertTrue(all(omic.dtype == torch.float32 for omic in omics))
        self.assertEqual(label.shape, (1,))
        self.assertEqual(event_time.shape, (1,))
        self.assertEqual(censorship.shape, (1,))
        self.assertEqual(label.dtype, torch.int64)
        self.assertEqual(event_time.dtype, torch.float32)
        self.assertEqual(censorship.dtype, torch.float32)
        print(
            "PORPOISE FIRST BATCH PASS: "
            f"mode=coattn case={case_id} path={tuple(path.shape)} "
            f"omics={[tuple(omic.shape) for omic in omics]} "
            f"label={tuple(label.shape)}/{label.dtype} "
            f"event_time={tuple(event_time.shape)}/{event_time.dtype} "
            f"censorship={tuple(censorship.shape)}/{censorship.dtype}"
        )


class SyntheticClusterDataset(Dataset):
    def __len__(self):
        return 1

    def __getitem__(self, index: int):
        return (
            torch.randn(4, 1536, dtype=torch.float32),
            torch.tensor([0, 1, 1, 0]),
            torch.randn(8),
            torch.tensor([index + 1.0]),
            torch.tensor([12.5]),
            torch.tensor([0.0]),
        )


class SyntheticClusterFirstBatchTests(unittest.TestCase):
    def test_cluster_first_batch(self):
        loader = DataLoader(
            SyntheticClusterDataset(),
            batch_size=1,
            collate_fn=collate_MIL_survival_cluster,
        )
        path, cluster_ids, omic, label, event_time, censorship = next(iter(loader))
        self.assertEqual(path.shape, (4, 1536))
        self.assertEqual(cluster_ids.shape, (4,))
        self.assertEqual(cluster_ids.dtype, torch.int64)
        self.assertEqual(omic.dtype, torch.float32)
        self.assertEqual(label.shape, (1,))
        self.assertEqual(event_time.shape, (1,))
        self.assertEqual(censorship.shape, (1,))
        self.assertEqual(label.dtype, torch.int64)
        self.assertEqual(event_time.dtype, torch.float32)
        self.assertEqual(censorship.dtype, torch.float32)
        print(
            "PORPOISE CLUSTER SYNTH FIRST BATCH PASS: "
            f"path={tuple(path.shape)} cluster_ids={tuple(cluster_ids.shape)}/"
            f"{cluster_ids.dtype} omic={tuple(omic.shape)}/{omic.dtype} "
            f"label={tuple(label.shape)}/{label.dtype} "
            f"event_time={tuple(event_time.shape)}/{event_time.dtype} "
            f"censorship={tuple(censorship.shape)}/{censorship.dtype}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
