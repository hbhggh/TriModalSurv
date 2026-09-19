from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
from trimodalsurv.training import runtime

def main():
    import argparse
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument('--compensator')
    probe.add_argument('--config')
    selected, _ = probe.parse_known_args()
    compensator = selected.compensator
    if compensator is None and selected.config is not None:
        from trimodalsurv.config import read_config
        content = read_config(selected.config)
        compensator = content.get('runtime', content).get('compensator')
    if compensator == 'population':
        from experiments.I02_population_prototypes.train import parsing_args, main as run
        args = parsing_args()
        runtime.set_seed(args.seed)
        return run(args)
    args = runtime.parsing_args()
    runtime.set_seed(args.seed)
    if args.compensator == 'capl':
        from experiments.I04_cap4_multi_prototypes.train import main as run
        return run(args)
    return runtime.main(args)

if __name__ == '__main__':
    main()
