"""I04 的显式模型工厂与生命周期接线。"""
from trimodalsurv.training import runtime as shared
from .model import CAPRecallMulti
from .runtime import init_capl_prototypes, print_capl_stats, _capl_compensator
parsing_args = shared.parsing_args

def compensator_factory(name, *, modalities, dim, proto_per_bin=None, **kwargs):
    if name != 'capl':
        raise ValueError(f'Unsupported experiment compensator: {name}')
    return CAPRecallMulti(modalities, dim, n_bins=4,
                         proto_per_bin=proto_per_bin, ema=0.99)

def load_model(*args, **kwargs):
    return shared.load_model(*args, **kwargs, compensator_factory=compensator_factory)

class Lifecycle:
    def before_loaders(self, *, model, train_dataset, args, device, gpu_config, **kwargs):
        if args.train:
            init_capl_prototypes(model, train_dataset, args.seed, device,
                                 gpu_config['batch_size'], gpu_config['non_blocking'])
    def before_epoch(self, *, model, epoch, **kwargs):
        bank = _capl_compensator(model)
        if bank is not None:
            bank.reset_epoch_stats()
    def after_train_epoch(self, **kwargs):
        pass
    def after_validation(self, *, model, valid_loader, device, epoch, gpu_config, **kwargs):
        print_capl_stats(model, valid_loader, device, epoch,
                         non_blocking=gpu_config['non_blocking'])

def main(args):
    return shared.main(args, model_factory=load_model, lifecycle=Lifecycle())

if __name__ == '__main__':
    args = parsing_args()
    shared.set_seed(args.seed)
    main(args)
