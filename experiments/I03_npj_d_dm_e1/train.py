"""历史对照训练入口，参数与公共训练保持一致。"""
from trimodalsurv.training.runtime import parsing_args, main, set_seed
if __name__ == '__main__':
    args = parsing_args()
    set_seed(args.seed)
    main(args)
