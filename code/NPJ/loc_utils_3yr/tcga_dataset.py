
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

class TCGADataset(Dataset):
    def __init__(self, patient_list, label_list, img_dict, text_dict, rna_dict,
                 modalities, n_image_tokens=128):
        super().__init__()
        self.patient_id = patient_list
        self.labels = label_list
        self.dict_data = {'img': img_dict, 'text': text_dict, 'rna': rna_dict}
        self.modalities = modalities
        self.n_image_tokens = n_image_tokens

        # Define the expected full shapes for missing data
        self.fallback_shapes = {
            'text': (200, 768),
            'rna': (2048, 256)
        }
        self.feature_dims = {}
        for mm in ['text', 'rna']:
            if len(self.dict_data[mm]) > 0:
                example_key = next(iter(self.dict_data[mm]))
                self.feature_dims[mm] = self.dict_data[mm][example_key].shape
            else:
                self.feature_dims[mm] = self.fallback_shapes[mm]
                print(f"[WARN] No data for modality '{mm}'. Using fallback shape = {self.fallback_shapes[mm]}")

    def __len__(self):
        return len(self.patient_id)

    def safe_modality_get(self, mm, pid, return_mask=False):
        """
        Get modality feature. If missing, return zero tensor with fallback shape and 0-mask.
        Ensures return type is torch.Tensor.
        """
        data = self.dict_data[mm].get(pid, None)
        if data is None:
            feature_shape = self.feature_dims[mm]
            data = np.zeros(feature_shape, dtype=np.float32)
            mask = 0
        else:
            mask = 1
            data = np.array(data, dtype=np.float32)

        data = torch.from_numpy(data).clone()
        return (data, mask) if return_mask else data

    def __getitem__(self, idx):
        pid = self.patient_id[idx]
        ret_item = {
            'patient_id': pid,
            'label': torch.tensor(self.labels[idx], dtype=torch.long),
            'idx': torch.tensor(idx, dtype=torch.long)
        }

        for mm in self.modalities:
            if mm == 'img':
                img_data = np.concatenate(self.dict_data['img'][pid], axis=0)
                if len(img_data) < self.n_image_tokens:
                    img_data = np.pad(img_data, ((0, self.n_image_tokens - len(img_data)), (0, 0)), mode='constant', constant_values=0)
                else:
                    mini_kmeans = MiniBatchKMeans(n_clusters=self.n_image_tokens, random_state=42)
                    mini_kmeans.fit(img_data)
                    img_data = mini_kmeans.cluster_centers_
                ret_item[mm] = torch.from_numpy(np.array(img_data, dtype=np.float32)).clone()
                ret_item[f"{mm}_mask"] = torch.tensor(1.0, dtype=torch.float32)
            else:
                data, mask = self.safe_modality_get(mm, pid, return_mask=True)
                ret_item[mm] = data
                ret_item[f"{mm}_mask"] = torch.tensor(mask, dtype=torch.float32)

        return ret_item


def get_dataset(label_report_path, modalities, task_type, cancer_types, n_image_tokens=128):
    cancer_list = cancer_types.upper().split('_')
    img_root = pathlib.Path(modalities['img'].path)
    text_root = pathlib.Path(modalities['text'].path)
    rna_root = pathlib.Path(modalities['rna'].path)

    img_dict = {}
    text_dict = {}
    rna_dict = {}
    labels = []
    patients = []

    label_mapping = {cancer: idx for idx, cancer in enumerate(cancer_list)}

    for cancer in cancer_list:
        cancer_folder = img_root.joinpath(cancer)
        pkl_files = list(cancer_folder.glob("*.pkl"))
        for pkl_path in tqdm(pkl_files, desc=f"Loading {cancer}"):
            filename = pkl_path.stem
            pid = '-'.join(filename.split('-')[:3])
            with open(pkl_path, 'rb') as f:
                img_feature = pickle.load(f).values
            if pid not in img_dict:
                img_dict[pid] = []
            img_dict[pid].append(img_feature)
            if pid not in patients:
                patients.append(pid)
                labels.append(label_mapping[cancer])

    # Load text and RNA
    missing_text = 0
    missing_rna = 0
    for pid in patients:
        text_pkl = text_root.joinpath(f"{pid}.pkl")
        rna_pkl = rna_root.joinpath(f"{pid}.pkl")

        if text_pkl.exists():
            with open(text_pkl, 'rb') as f:
                text_dict[pid] = pickle.load(f)
        else:
            missing_text += 1

        if rna_pkl.exists():
            with open(rna_pkl, 'rb') as f:
                rna_dict[pid] = pickle.load(f)
        else:
            missing_rna += 1

    print(f"Missing text embeddings: {missing_text}")
    print(f"Missing RNA embeddings: {missing_rna}")

    # Split train/val/test
    train_pids, temp_pids, train_labels, temp_labels = train_test_split(patients, labels, test_size=0.3, random_state=42, stratify=labels)
    val_pids, test_pids, val_labels, test_labels = train_test_split(temp_pids, temp_labels, test_size=1/3, random_state=42, stratify=temp_labels)

    ds_train = TCGADataset(train_pids, train_labels, img_dict, text_dict, rna_dict, modalities, n_image_tokens)
    ds_val = TCGADataset(val_pids, val_labels, img_dict, text_dict, rna_dict, modalities, n_image_tokens)
    ds_test = TCGADataset(test_pids, test_labels, img_dict, text_dict, rna_dict, modalities, n_image_tokens)

    return ds_train, ds_val, ds_test


class TCGAAllDataset(Dataset):
    def __init__(self, label_report_path, modalities, split, task_type, img_select='random', n_image_tokens=128, cancer_types="LUAD"):
        super().__init__()
        self.label_report = pd.read_csv(label_report_path)
        self.img_select = img_select
        self.n_image_tokens = n_image_tokens
        self.split = split
        self.task_type = task_type
        self.modalities = modalities
        self.all_cancer_type = cancer_types.upper().split('_')

        self.split_index = self.label_report['split'] == split
        self.cancer_type = self.label_report['cancer_type']
        self.patient_id = self.label_report['patient_id'][self.split_index].values

        self.cache_dir = pathlib.Path('tmp')
        self.cache_dir.mkdir(exist_ok=True)

        self.cls_label = []
        self.filter_cancer_type = []
        self.selected_pids = []
        self.dict_data = {}
        cancer_instances = {}

        for cancer_type in self.all_cancer_type:
            dict_data = {}
            selected_pids = []
            skip_img = []
            selected_pids_set = set(self.patient_id)

            # ----- Image -----
            if 'img' in self.modalities:
                img_cache = self.cache_dir.joinpath(f'img_{cancer_type}_{split}_{img_select}.cache')
                img_root = pathlib.Path(self.modalities['img'].path).joinpath(cancer_type)
                if img_cache.exists():
                    print(f"[TCGA] Loading Image cache: {img_cache}")
                    with open(img_cache, 'rb') as f:
                        dict_data['img'] = pickle.load(f)
                else:
                    print(f"[TCGA] Loading Image from raw: {img_root}")
                    dict_data['img'] = {}
                    for pid in tqdm(self.patient_id, desc=f"Loading img {cancer_type}"):
                        img_paths = list(img_root.glob(f"{pid}*.pkl"))
                        if not img_paths:
                            skip_img.append(pid)
                            continue
                        img_data_list = []
                        n_clusters = n_image_tokens if img_select != 'all' else max(1, n_image_tokens // len(img_paths))
                        for img_pkl in img_paths:
                            with open(img_pkl, 'rb') as f:
                                feature = pickle.load(f).values
                            if len(feature) < n_clusters:
                                feature = np.pad(feature, ((0, n_clusters - len(feature)), (0, 0)), 'constant')
                            else:
                                mini_kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42)
                                mini_kmeans.fit(feature)
                                feature = mini_kmeans.cluster_centers_
                            img_data_list.append(feature)
                        dict_data['img'][pid] = img_data_list
                    img_split_data = {pid: data for pid, data in dict_data['img'].items() if pid in selected_pids_set}
                    with open(img_cache, 'wb') as f:
                        pickle.dump(img_split_data, f)
                    dict_data['img'] = img_split_data

            # ----- Text -----
            if 'text' in self.modalities:
                text_cache = self.cache_dir.joinpath(f'text_{cancer_type}_{split}.cache')
                text_root = pathlib.Path(self.modalities['text'].path)
                if text_cache.exists():
                    with open(text_cache, 'rb') as f:
                        dict_data['text'] = pickle.load(f)
                else:
                    dict_data['text'] = {}
                    for pid in tqdm(self.patient_id, desc=f"Loading text {cancer_type}"):
                        pkl_path = text_root.joinpath(f"{pid}.pkl")
                        if pkl_path.exists():
                            with open(pkl_path, 'rb') as f:
                                dict_data['text'][pid] = pickle.load(f)
                    with open(text_cache, 'wb') as f:
                        pickle.dump(dict_data['text'], f)

            # ----- RNA -----
            if 'rna' in self.modalities:
                rna_cache = self.cache_dir.joinpath(f'rna_{cancer_type}_{split}.cache')
                rna_root = pathlib.Path(self.modalities['rna'].path)
                if rna_cache.exists():
                    with open(rna_cache, 'rb') as f:
                        dict_data['rna'] = pickle.load(f)
                else:
                    dict_data['rna'] = {}
                    rna_data_path = rna_root.joinpath(f"RNA_{cancer_type}_embedding_token_lvl.pkl")
                    with open(rna_data_path, 'rb') as f:
                        rna_raw = pickle.load(f)
                    for pid, embed in zip(rna_raw['identifier'], rna_raw['embedding']):
                        if pid in selected_pids_set:
                            dict_data['rna'][pid] = embed[:2048, :]
                    with open(rna_cache, 'wb') as f:
                        pickle.dump(dict_data['rna'], f)

            for pid in self.patient_id:
                if all(pid in dict_data[mm] for mm in dict_data):
                    selected_pids.append(pid)

            print(f"[{cancer_type}/{split}] Selected instances: {len(selected_pids)}")
            cancer_instances[cancer_type] = len(selected_pids)

            self.selected_pids.extend(selected_pids)
            self.cls_label.extend(self.label_report.loc[self.label_report['patient_id'].isin(selected_pids)][f'label-survive_over_3_year' if self.task_type == '3_year_prediction' else 'PFI_label'].tolist())
            self.filter_cancer_type.extend([cancer_type] * len(selected_pids))

            for mm in dict_data:
                if mm not in self.dict_data:
                    self.dict_data[mm] = {}
                self.dict_data[mm].update({pid: dict_data[mm][pid] for pid in selected_pids})

    def __len__(self):
        return len(self.selected_pids)

    def __getitem__(self, idx):
        pid = self.selected_pids[idx]
        item = {
            'label': torch.tensor(self.cls_label[idx]),
            'patient_id': str(pid),
            'cancer_type': str(self.filter_cancer_type[idx]),
            'idx': torch.tensor(idx),
        }
        for mm in self.dict_data:
            if mm == 'img':
                img_data = self.dict_data[mm][pid]
                if self.img_select == 'random':
                    data = random.choice(img_data)
                elif self.img_select == 'first':
                    data = img_data[0]
                elif self.img_select == 'all':
                    data = np.concatenate(img_data, axis=0)
                    if len(data) < self.n_image_tokens:
                        data = np.pad(data, ((0, self.n_image_tokens - len(data)), (0, 0)), 'constant')
                else:
                    data = img_data[0]
            else:
                data = self.dict_data[mm][pid]

            if isinstance(data, np.ndarray):
                data = torch.tensor(data.copy(), dtype=torch.float32)
            item[mm] = data

        return item



def get_dataset_alltcga(label_report_path, modalities, task_type, img_select='random', cancer_types="BLCA_LUAD"):
    ds_test = TCGAAllDataset(label_report_path, modalities=modalities, split='test', task_type = task_type, img_select = img_select, cancer_types = cancer_types)
    ds_train = TCGAAllDataset(label_report_path, modalities=modalities, split='train', task_type = task_type, img_select = img_select, cancer_types = cancer_types)
    ds_val = TCGAAllDataset(label_report_path, modalities=modalities, split='valid', task_type = task_type, img_select = img_select, cancer_types = cancer_types)
    
    return ds_train, ds_val, ds_test


class TCGASurDataset(Dataset):
    def __init__(self, label_report_path, modalities, split, task_type,
                 img_select='random', n_image_tokens=128,
                 cancer_types="BLCA_LUAD", network_type="DefaultNet",
                 simulate_missing_modality=None,
                 missing_manifest=None, missing_grid=None,
                 modality_dropout=0.0, seed=123):
        super().__init__()
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
                         modality_dropout=0.0, seed=123):
    ds_train = TCGASurDataset(label_report_path, modalities, 'train', task_type, img_select,
                              n_image_tokens, cancer_types, network_type,
                              simulate_missing_modality=simulate_missing_modality,
                              missing_manifest=missing_manifest,
                              missing_grid=missing_grid,
                              modality_dropout=modality_dropout,
                              seed=seed)

    ds_val = TCGASurDataset(label_report_path, modalities, 'valid', task_type, img_select,
                            n_image_tokens, cancer_types, network_type,
                            missing_manifest=missing_manifest,
                            missing_grid=missing_grid)

    ds_test = TCGASurDataset(label_report_path, modalities, 'test', task_type, img_select,
                             n_image_tokens, cancer_types, network_type,
                             missing_manifest=missing_manifest,
                             missing_grid=missing_grid)

    return ds_train, ds_val, ds_test
