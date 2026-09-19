
import pandas as pd
import numpy as np
import json
from torch.utils.data import Dataset
import pathlib
import torch
import random, pickle
from tqdm import tqdm
from sklearn.cluster import MiniBatchKMeans

import os
from sklearn.model_selection import train_test_split

from torch.utils.data import Dataset
import numpy as np
import pandas as pd

import torch
from torch.utils.data import Dataset
import numpy as np
import pandas as pd
from pathlib import Path

def compute_quantile_edges(survival_months, censorship):
    """训练集**未删失**患者（censorship==0）生存月数的 25/50/75 分位（线性插值）。"""
    months = np.asarray(survival_months, dtype=float)
    censor = np.asarray(censorship, dtype=float)
    if months.shape != censor.shape:
        raise ValueError(
            f"survival_months 与 censorship 长度不一致: {months.shape} vs {censor.shape}"
        )
    uncensored = months[censor == 0]
    uncensored = uncensored[np.isfinite(uncensored)]
    if uncensored.size < 4:
        raise ValueError(
            "bin_mode='train_quantile' 需要至少 4 名未删失患者(censorship==0)，"
            f"实际 {uncensored.size}"
        )
    return np.quantile(uncensored, [0.25, 0.5, 0.75])


def assign_bins(survival_months, edges):
    """右开区间入箱：edges 上的月数落入右侧箱；返回 int 数组，取值 0..3。"""
    months = np.asarray(survival_months, dtype=float)
    edge_array = np.asarray(edges, dtype=float)
    if edge_array.shape != (3,):
        raise ValueError(f"edges 必须是 3 个边界，实际 {edge_array.tolist()}")
    return np.digitize(months, edge_array, right=False).astype(int)


class TCGASurDataset(Dataset):
    def __init__(self, label_report_path, modalities, split, task_type,
                 img_select='random', n_image_tokens=128,
                 cancer_types="BLCA_LUAD", network_type="DefaultNet",
                 simulate_missing_modality=None,
                 missing_manifest=None, missing_grid=None,
                 modality_dropout=0.0, seed=123,
                 bin_mode='author', bin_edges=None):
        super().__init__()
        # 指挥官小修（ProSurv-CAP4 派单 v2）：下方 author 分箱段仍用局部名 bin_edges
        # 接 pd.cut 的返回值（一字不动），故先把入参别名到 bin_edges_override。
        bin_edges_override = bin_edges
        self.label_report = pd.read_csv(label_report_path)
        self.img_select = img_select
        self.n_image_tokens = n_image_tokens
        self.split = split
        self.task_type = task_type
        self.modalities = modalities
        self.network_type = network_type
        self.cancer_types = cancer_types.upper().split('_')
        self.main_modality = 'img'

        self.label_report = self.label_report[
            (self.label_report['split'] == split) &
            (self.label_report['cancer_type'].isin(self.cancer_types))
        ]
        self.patient_id = self.label_report['patient_id'].values

        self.dict_data = {mm: {} for mm in modalities}
        self.cls_label = []
        self.survival_months = []
        self.censorship = []
        self.selected_pids = []
        self.filter_cancer_type = []

        self.cache_dir = Path('tmp_sur_cache')
        self.cache_dir.mkdir(exist_ok=True)

        cache_suffix = f"{split}_{img_select}_{cancer_types}"
        self.cache_suffix = cache_suffix
        self.img_cache_file = self.cache_dir.joinpath(f'img_sur_{cache_suffix}.pkl')
        self.text_cache_file = self.cache_dir.joinpath(f'text_sur_{cache_suffix}.pkl')
        self.rna_cache_file = self.cache_dir.joinpath(f'rna_sur_{cache_suffix}.pkl')
        self._loaded_cache_files = {}

        self._load_cache()

        img_root = Path(self.modalities['img'].path) if 'img' in self.modalities else None
        text_root = Path(self.modalities['text'].path) if 'text' in self.modalities else None
        rna_root = Path(self.modalities['rna'].path) if 'rna' in self.modalities else None

        if 'rna' in self.modalities and 'rna' not in self._loaded_cache_files:
            self.dict_data['rna'] = {}
            pids_in_split = set(self.patient_id)
            for cancer_type in self.cancer_types:
                rna_file = rna_root.joinpath(f"RNA_{cancer_type}_embedding_token_lvl.pkl")
                if not rna_file.exists():
                    continue
                with open(rna_file, 'rb') as f:
                    rna_raw = pickle.load(f)
                for pid, emb in zip(rna_raw['identifier'], rna_raw['embedding']):
                    if pid in pids_in_split:
                        self.dict_data['rna'][pid] = emb
            with open(self.rna_cache_file, 'wb') as f:
                pickle.dump(self.dict_data['rna'], f)

        for idx, pid in tqdm(enumerate(self.patient_id), total=len(self.patient_id), desc=f"Loading split {split}"):
            cancer_type = self.label_report.iloc[idx]['cancer_type']

            if pid not in self.dict_data['img']:
                cancer_folder = img_root.joinpath(cancer_type)
                img_files = list(cancer_folder.glob(f"{pid}*.pkl"))
                if len(img_files) == 0:
                    continue
                img_list = [pickle.load(open(f, 'rb')).values for f in img_files]
                img_data = np.concatenate(img_list, axis=0)
                if img_data.shape[0] < self.n_image_tokens:
                    img_data = np.pad(img_data, ((0, self.n_image_tokens - img_data.shape[0]), (0, 0)), mode='constant')
                else:
                    kmeans = MiniBatchKMeans(n_clusters=self.n_image_tokens, random_state=42)
                    kmeans.fit(img_data)
                    img_data = kmeans.cluster_centers_
                self.dict_data['img'][pid] = img_data

            for mod in ['text', 'rna']:
                if mod in self.modalities and pid not in self.dict_data[mod]:
                    root = text_root if mod == 'text' else rna_root
                    pkl_path = root.joinpath(f"{pid}.pkl") if mod == 'text' else None
                    if mod == 'text' and pkl_path and pkl_path.exists():
                        self.dict_data[mod][pid] = pickle.load(open(pkl_path, 'rb'))

            self.cls_label.append(self.label_report.iloc[idx]['label'])
            self.survival_months.append(self.label_report.iloc[idx]['survival_months'])
            self.censorship.append(self.label_report.iloc[idx]['censorship'])
            self.filter_cancer_type.append(cancer_type)
            self.selected_pids.append(pid)

        self._save_cache()

        survival_months_array = np.array(self.survival_months)
        self.survival_months_bin, bin_edges = pd.cut(
            survival_months_array, bins=4, retbins=True, labels=False,
            right=False, include_lowest=True
        )
        self.survival_months_bin = np.nan_to_num(self.survival_months_bin, nan=3).astype(int)

        # 指挥官小修（ProSurv-CAP4 派单 v2，2026-09-07）：新增 train_quantile 分箱协议。
        # 上面 4 行 author 路径逐字未改；bin_mode='author' 时下面整段只写 self.bin_* 元数据。
        self.bin_mode = bin_mode
        self.bin_edges = None
        if bin_mode == 'train_quantile':
            if split == 'train':
                if bin_edges_override is not None:
                    raise ValueError(
                        "train split must derive bin_edges itself; "
                        "bin_edges is only for valid/test"
                    )
                edges = compute_quantile_edges(
                    survival_months_array, np.array(self.censorship)
                )
            else:
                if bin_edges_override is None:
                    raise ValueError(
                        f"bin_mode='train_quantile' requires bin_edges for split={split!r}"
                    )
                edges = np.asarray(bin_edges_override, dtype=float)
                if edges.shape != (3,):
                    raise ValueError(
                        f"bin_edges must contain exactly 3 values, got {edges.tolist()}"
                    )
            self.bin_edges = edges
            self.survival_months_bin = assign_bins(survival_months_array, edges)
        elif bin_mode != 'author':
            raise ValueError(f"Unsupported bin_mode: {bin_mode!r}")

        self.fallback_shapes = {'text': (200, 768), 'rna': (2048, 256)}
        self.simulate_missing_modality = simulate_missing_modality
        self.simulate_missing_set = set()
        self.missing_manifest = missing_manifest
        self.missing_grid = missing_grid
        self.missing_mode = None
        self.missing_set = set()

        if missing_grid is not None:
            try:
                missing_mode, missing_rate = missing_grid.rsplit('_', 1)
            except ValueError as exc:
                raise ValueError(f"Invalid missing_grid={missing_grid!r}") from exc
            if missing_mode not in {'rna', 'text', 'both'} or missing_rate not in {'25', '50', '75', '100'}:
                raise ValueError(f"Invalid missing_grid={missing_grid!r}")
            self.missing_mode = missing_mode

            if missing_rate == '100':
                self.missing_set = set(self.selected_pids)
            else:
                if missing_manifest is None:
                    raise ValueError(f"missing_manifest is required for missing_grid={missing_grid!r}")
                manifest = pd.read_csv(missing_manifest)
                required_columns = {'patient_id', missing_grid}
                missing_columns = required_columns - set(manifest.columns)
                if missing_columns:
                    raise ValueError(
                        f"Missing manifest columns: {sorted(missing_columns)}"
                    )
                if manifest['patient_id'].duplicated().any():
                    raise ValueError("Missing manifest contains duplicate patient_id values")
                normalized = manifest[missing_grid].astype(str).str.strip().str.lower()
                valid_values = {'0', '1', 'false', 'true'}
                invalid_values = sorted(set(normalized) - valid_values)
                if invalid_values:
                    raise ValueError(
                        f"Invalid boolean values in manifest column {missing_grid}: {invalid_values}"
                    )
                selected = normalized.isin({'1', 'true'})
                self.missing_set = set(
                    manifest.loc[selected, 'patient_id'].astype(str)
                )

        if split == 'train' and simulate_missing_modality:
            try:
                modality_name, ratio = simulate_missing_modality.split('_')
                ratio = float(ratio)
                if modality_name in self.modalities and 0 < ratio < 1:
                    num_to_simulate = int(len(self.selected_pids) * ratio)
                    self.simulate_missing_set = set(random.sample(self.selected_pids, num_to_simulate))
            except Exception as e:
                print(f"[ERROR] Failed to parse simulate_missing_modality={simulate_missing_modality}: {e}")

        self.modality_dropout = float(modality_dropout)
        if not 0.0 <= self.modality_dropout <= 1.0:
            raise ValueError("modality_dropout must be in [0, 1]")
        self.modality_dropout_seed = int(seed)
        self.modality_dropout_rngs = {}
        if split == 'train' and self.modality_dropout > 0.0:
            for pid in self.selected_pids:
                for modality in ('text', 'rna'):
                    if modality not in self.modalities:
                        continue
                    self.modality_dropout_rngs[(pid, modality)] = random.Random(
                        f"{self.modality_dropout_seed}:{pid}:{modality}"
                    )

    def _cache_candidates(self, modality):
        """按新名、已知旧网络名、当前网络名、其他旧名的顺序返回候选。"""
        new_path = self.cache_dir.joinpath(f'{modality}_sur_{self.cache_suffix}.pkl')
        candidates = [new_path]
        legacy_network_types = ['MainModalityMoE', 'NPJC']
        if self.network_type not in legacy_network_types:
            legacy_network_types.append(self.network_type)
        candidates.extend(
            self.cache_dir.joinpath(
                f'{modality}_sur_{self.cache_suffix}_{network_type}.pkl'
            )
            for network_type in legacy_network_types
        )
        candidates.extend(
            sorted(
                self.cache_dir.glob(
                    f'{modality}_sur_{self.cache_suffix}_*.pkl'
                )
            )
        )
        return list(dict.fromkeys(candidates))

    def _load_cache(self):
        for modality in ['img', 'text', 'rna']:
            if modality not in self.modalities:
                continue
            self.dict_data[modality] = {}
            for cache_path in self._cache_candidates(modality):
                if not cache_path.exists():
                    continue
                try:
                    with open(cache_path, 'rb') as f:
                        self.dict_data[modality] = pickle.load(f)
                except Exception:
                    self.dict_data[modality] = {}
                    continue
                self._loaded_cache_files[modality] = cache_path
                break

    def _save_cache(self):
        selected_pids_set = set(self.selected_pids)
        for modality, cache_path in zip(['img', 'text', 'rna'], [self.img_cache_file, self.text_cache_file, self.rna_cache_file]):
            if modality in self.modalities:
                data_to_cache = {pid: data for pid, data in self.dict_data[modality].items() if pid in selected_pids_set}
                with open(cache_path, 'wb') as f:
                    pickle.dump(data_to_cache, f)

    def __len__(self):
        return len(self.selected_pids)

    def safe_modality_get(self, mm, pid, return_mask=False):
        manifest_missing = (
            mm != 'img'
            and pid in self.missing_set
            and (self.missing_mode == 'both' or mm == self.missing_mode)
        )
        simulated_missing = (
            pid in self.simulate_missing_set
            and mm in self.simulate_missing_modality
        )
        if manifest_missing or simulated_missing:
            data = np.zeros(self.fallback_shapes.get(mm, (1, 1)), dtype=np.float32)
            mask = 0
        else:
            data = self.dict_data[mm].get(pid, None)
            if data is None:
                shape = self.fallback_shapes.get(mm, (1, 1))
                data = np.zeros(shape, dtype=np.float32)
                mask = 0
            else:
                mask = 1
                data = np.array(data, dtype=np.float32)
        data = torch.from_numpy(data).clone()
        return (data, mask) if return_mask else data

    def __getitem__(self, idx):
        pid = self.selected_pids[idx]
        sample = {
            'idx': torch.tensor(idx),
            'patient_id': pid,
            'cancer_type': self.filter_cancer_type[idx],
            'label': torch.tensor(self.cls_label[idx]).long(),
            'survival_months': torch.tensor(self.survival_months[idx]).float(),
            'survival_months_bin': torch.tensor(self.survival_months_bin[idx]).long(),
            'censorship': torch.tensor(self.censorship[idx]).float(),
        }
        for modality in self.modalities:
            data, mask = self.safe_modality_get(modality, pid, return_mask=True)
            if (
                self.split == 'train'
                and self.modality_dropout > 0.0
                and modality in {'text', 'rna'}
            ):
                original = data.clone()
                dropout_rng = self.modality_dropout_rngs.get((pid, modality))
                dropped = bool(
                    mask
                    and dropout_rng is not None
                    and dropout_rng.random() < self.modality_dropout
                )
                if dropped:
                    data = torch.zeros_like(data)
                    mask = 0
                sample[f"{modality}_orig"] = original.float()
                sample[f"{modality}_dropped"] = torch.tensor(dropped).bool()
            sample[modality] = data.float()
            sample[f"{modality}_valid"] = torch.tensor(mask).bool()
            # print(f"[DEBUG] pid={pid} | modality={modality} | shape={tuple(data.shape)} | valid={mask}")
        return sample


def get_dataset_tcga_sur(label_report_path, modalities, task_type,
                         img_select='random', n_image_tokens=128,
                         cancer_types="BLCA_LUAD", network_type="DefaultNet",
                         simulate_missing_modality=None,
                         missing_manifest=None, missing_grid=None,
                         modality_dropout=0.0, seed=123,
                         bin_mode='author', bin_edges=None):
    ds_train = TCGASurDataset(label_report_path, modalities, 'train', task_type, img_select,
                              n_image_tokens, cancer_types, network_type,
                              simulate_missing_modality=simulate_missing_modality,
                              missing_manifest=missing_manifest,
                              missing_grid=missing_grid,
                              modality_dropout=modality_dropout,
                              seed=seed,
                              bin_mode=bin_mode, bin_edges=bin_edges)

    # 指挥官小修（ProSurv-CAP4 派单 v2）：train 的分位边界传给 valid/test，三 split 共用。
    shared_edges = ds_train.bin_edges if bin_mode == 'train_quantile' else None

    ds_val = TCGASurDataset(label_report_path, modalities, 'valid', task_type, img_select,
                            n_image_tokens, cancer_types, network_type,
                            missing_manifest=missing_manifest,
                            missing_grid=missing_grid,
                            bin_mode=bin_mode, bin_edges=shared_edges)

    ds_test = TCGASurDataset(label_report_path, modalities, 'test', task_type, img_select,
                             n_image_tokens, cancer_types, network_type,
                             missing_manifest=missing_manifest,
                             missing_grid=missing_grid,
                             bin_mode=bin_mode, bin_edges=shared_edges)

    return ds_train, ds_val, ds_test

