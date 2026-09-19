"""I02 推理入口：author分箱、严格既有库、禁止均值预填补。"""
import argparse
from pathlib import Path
from typing import Mapping
from trimodalsurv.evaluation import missing as shared
from trimodalsurv.evaluation.common import _atomic_json_dump
from .train import load_model
CANCERS = shared.CANCERS

def _write_evaluation_result(args, path: Path, payload: Mapping[str, object]) -> None:
    if getattr(args, 'compensator', 'none') == 'population' and path.exists():
        raise FileExistsError(
            f'population evaluation output exists; refusing overwrite: {path}'
        )
    _atomic_json_dump(path, payload)


def validate_population_args(args):
    if getattr(args, 'compensator', 'none') != 'population':
        return
    if getattr(args, 'network_type', None) != 'NPJC':
        raise ValueError('population requires network_type NPJC')
    if getattr(args, 'prototype_k', None) is None or args.prototype_k < 1:
        raise ValueError('population requires a positive --prototype-k')
    if args.arm != 'm0real' or getattr(args, 'm1_mark_valid', False):
        raise ValueError('population requires m0real without mean prefill or m1-mark-valid')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin_mode", choices=("author",), required=True)
    parser.add_argument("--arm", required=True, type=str.lower, choices=("m0real", "m1"))
    parser.add_argument("--cancer", required=True, type=str.upper, choices=CANCERS)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--ckpt", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--grids", default="all", help="all 或逗号分隔格点")
    parser.add_argument("--label", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    # 指挥官小修（2026-09-02）：评测带补偿器的 ckpt（M2/M1b）时构建同结构模型
    parser.add_argument("--compensator", default="none", choices=("none", "capr", "bank", "population"))
    parser.add_argument('--prototype-k', type=int, default=None)
    # 指挥官小修（单 γ 配套）：评测 NPJ-C 骨架 ckpt
    parser.add_argument("--network_type", default="MainModalityMoE", choices=("MainModalityMoE", "NPJC"))
    # 指挥官小修（NPJ-D 消融，2026-09-06）：评测 d0（去 GatedFusion 等权均值）ckpt 时构建同结构模型
    parser.add_argument("--fusion_type", default="gate", choices=("gate", "mean"))
    # 指挥官小修（E0m，2026-09-06）：m1 均值盲补后把 text/rna 标记为 valid（NPJC 专用；默认关）
    parser.add_argument("--m1-mark-valid", dest="m1_mark_valid", action="store_true")
    args = parser.parse_args()
    try:
        validate_population_args(args)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run_evaluation(args):
    validate_population_args(args)
    def factory(**kwargs):
        kwargs.pop('proto_per_bin', None)
        return load_model(**kwargs, prototype_k=args.prototype_k, seed=args.seed)
    population = args.compensator == 'population'
    return shared.run_evaluation(args, model_factory=factory,
        result_writer=lambda path, payload: _write_evaluation_result(args, path, payload),
        result_metadata={'compensator': 'population', 'prototype_k': args.prototype_k} if population else None,
        output_suffix=f'_population_k{args.prototype_k}' if population else '')

if __name__ == '__main__':
    run_evaluation(parse_args())
