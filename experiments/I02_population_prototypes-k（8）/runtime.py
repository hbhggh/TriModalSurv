"""NPJ-C 配对人群原型的训练集视图、全量建库和分布式边界。"""
from pathlib import Path
import math

import torch
from torch.utils.data import DataLoader, Dataset
from accelerate.utils import broadcast, broadcast_object_list


class PopulationEarlyStopping:
    """严格 C-index 改善才重置；patience=0 保留旧的固定轮数行为。"""

    def __init__(self, patience):
        if type(patience) is not int or patience < 0:
            raise ValueError('patience must be a nonnegative integer')
        self.patience = patience
        self.best = float('-inf')
        self.best_epoch = 0
        self.bad_epochs = 0

    def update(self, cindex, epoch):
        if not math.isfinite(cindex):
            raise ValueError('Validation C-index must be finite')
        if cindex > self.best:
            self.best, self.best_epoch, self.bad_epochs = cindex, epoch + 1, 0
        else:
            self.bad_epochs += 1
        return dict(epoch=epoch + 1, best_epoch=self.best_epoch, best_cindex=self.best,
                    bad_epochs=self.bad_epochs, patience=self.patience,
                    should_stop=self.patience > 0 and self.bad_epochs >= self.patience)


class PopulationTrainView(Dataset):
    """绕过随机训练 dropout，但沿用数据集的固定缺失协议。"""

    def __init__(self, dataset):
        if dataset.split != 'train':
            raise ValueError('Population memory requires the train split')
        if not {'img', 'rna', 'text'}.issubset(dataset.modalities):
            raise ValueError('Population memory requires img, rna and text')
        self.dataset = dataset

    def __len__(self):
        return len(self.dataset.selected_pids)

    def __getitem__(self, index):
        patient = self.dataset.selected_pids[index]
        sample = {'idx': torch.tensor(index, dtype=torch.long)}
        for modality in ('img', 'rna', 'text'):
            data, valid = self.dataset.safe_modality_get(modality, patient, return_mask=True)
            sample[modality] = data
            sample[modality + '_valid'] = torch.tensor(valid, dtype=torch.bool)
        return sample


def validate_population_splits(train, valid, test):
    patient_sets = []
    for name, dataset in zip(('train', 'valid', 'test'), (train, valid, test)):
        patients = dataset.selected_pids
        if any(not isinstance(p, str) or not p.strip() for p in patients):
            raise ValueError(f'{name}: invalid patient ID')
        if len(set(patients)) != len(patients):
            raise ValueError(f'{name}: duplicate patient IDs')
        patient_sets.append(set(patients))
    if any(patient_sets[i] & patient_sets[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise ValueError('Population split patient overlap')


def make_population_loader(dataset, batch_size, loader_kwargs, seed):
    return DataLoader(
        PopulationTrainView(dataset), batch_size=batch_size, shuffle=False,
        drop_last=False, generator=torch.Generator().manual_seed(seed), **loader_kwargs,
    )


def ordered_patient_outputs(pieces, expected_size):
    """仅消除 distributed sampler 的重复索引，确保全数据集覆盖。"""
    if not pieces:
        raise ValueError('Empty patient coverage')
    merged = {key: torch.cat([part[key] for part in pieces]) for key in pieces[0]}
    order = torch.argsort(merged['idx'], stable=True)
    indices = merged['idx'][order]
    keep = torch.ones_like(indices, dtype=torch.bool)
    keep[1:] = indices[1:] != indices[:-1]
    order = order[keep]
    expected = torch.arange(expected_size, device=indices.device)
    if not torch.equal(indices[keep], expected):
        raise ValueError('Incomplete or invalid patient coverage')
    return {key: value[order] for key, value in merged.items()}


def main_process_call(accelerator, function):
    """主进程异常也广播，其他 rank 不得一直等待下一次 collective。"""
    result = [None, None]
    if accelerator.is_main_process:
        try:
            result[0] = function()
        except Exception as exc:
            result[1] = f'{type(exc).__name__}: {exc}'
    broadcast_object_list(result, from_process=0)
    if result[1] is not None:
        raise RuntimeError(result[1])
    return result[0]


@torch.no_grad()
def update_population_memory(model, loader, accelerator):
    unwrapped = accelerator.unwrap_model(model)
    modes = [(module, module.training) for module in unwrapped.modules()]
    pieces = []
    try:
        unwrapped.eval()
        for batch in loader:
            batch = {key: value.to(accelerator.device, non_blocking=True)
                     for key, value in batch.items()}
            tokens, valids = unwrapped.encode_patient_modalities(batch)
            payload = {'idx': batch['idx'], 'wsi': tokens['img'],
                       'rna': tokens['rna'], 'text': tokens['text'],
                       'complete': valids['img'] & valids['rna'] & valids['text']}
            # 先收集等长 batch，不能先在各 rank 独立过滤完整患者。
            pieces.append(accelerator.gather(payload))

        def rebuild():
            full = ordered_patient_outputs(pieces, len(loader.dataset))
            complete = full['complete']
            bank = unwrapped.compensator
            bank.update_memory_bank(*(full[m][complete] for m in ('wsi', 'rna', 'text')))
            return {'train_patients': len(full['idx']),
                    'complete_patients': int(complete.sum().item()),
                    'counts': bank.counts.cpu().tolist()}

        report = main_process_call(accelerator, rebuild)
        for buffer in unwrapped.compensator.buffers():
            broadcast(buffer, from_process=0)
        return report
    finally:
        for module, training in modes:
            module.training = training


def save_population_checkpoint(model, path, metric, best_metric, accelerator):
    def save():
        if not torch.isfinite(torch.tensor(metric)):
            raise ValueError('Validation metric must be finite')
        if metric > best_metric:
            target = Path(path)
            if best_metric == float('-inf') and target.exists():
                raise FileExistsError(f'Refusing to overwrite existing checkpoint: {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.tmp')
            torch.save(accelerator.unwrap_model(model).state_dict(), temporary)
            temporary.replace(target)
            return metric
        return best_metric
    return main_process_call(accelerator, save)


def load_population_checkpoint(model, path, accelerator):
    accelerator.wait_for_everyone()
    # MULTI_CPU 的 device 可能为 cpu:0，不能作为 torch.load storage 标签。
    # 先载入 CPU，再由 load_state_dict 复制到模型各 rank 的目标设备。
    state = torch.load(path, map_location='cpu', weights_only=True)
    accelerator.unwrap_model(model).load_state_dict(state, strict=True)
