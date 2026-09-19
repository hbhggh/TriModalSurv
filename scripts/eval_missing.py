from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
from trimodalsurv.evaluation.missing import parse_args, run_evaluation

def main():
    import argparse
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument('--compensator')
    selected, _ = probe.parse_known_args()
    if selected.compensator == 'population':
        from experiments.I02_population_prototypes.evaluate import parse_args as parse, run_evaluation as run
        run(parse())
        return 0
    args = parse_args()
    factory = None
    if args.compensator == 'capl':
        from experiments.I04_cap4_multi_prototypes.train import load_model
        factory = load_model
    run_evaluation(args, model_factory=factory)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
