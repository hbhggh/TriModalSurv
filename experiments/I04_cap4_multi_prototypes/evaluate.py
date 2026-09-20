"""I04 评测注入多中心银行，已有checkpoint严格加载。"""
from trimodalsurv.evaluation.missing import parse_args, run_evaluation
from .train import load_model
if __name__ == '__main__':
    run_evaluation(parse_args(), model_factory=load_model)
