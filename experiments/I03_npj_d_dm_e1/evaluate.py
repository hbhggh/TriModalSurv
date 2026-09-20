"""D/Dm/旧 E1 使用公共评测；Dm由 --arm m1 激活输入均值填补。"""
from trimodalsurv.evaluation.missing import parse_args, run_evaluation
if __name__ == '__main__':
    run_evaluation(parse_args())
