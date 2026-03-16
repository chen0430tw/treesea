"""tree-diagram  — main CLI entry point.

Subcommands:
    run      Run pipeline locally (login node or workstation)
    submit   Generate + submit a Slurm job
    profiles List available compute profiles
    inspect  Display and summarise a result JSON file

Usage:
    python -m tree_diagram run --profile cluster
    python -m tree_diagram submit --profile cluster --dry-run
    python -m tree_diagram profiles
    python -m tree_diagram inspect td_result_cluster.json
"""
from __future__ import annotations
import sys


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    sub = args[0]

    if sub == "run":
        from .run_local import main as run_main
        return run_main(args[1:])

    elif sub == "submit":
        from .submit import main as submit_main
        return submit_main(args[1:])

    elif sub == "inspect":
        from .inspect import main as inspect_main
        return inspect_main(args[1:])

    elif sub == "profiles":
        from .profiles import PROFILES
        print(f"{'profile':<12}  {'NX':>5}  {'NY':>5}  {'steps':>6}  description")
        print("-" * 72)
        for name, cfg in PROFILES.items():
            print(f"{name:<12}  {cfg['NX']:>5}  {cfg['NY']:>5}  {cfg['steps']:>6}  {cfg['_desc']}")
        return 0

    else:
        print(f"Unknown subcommand '{sub}'. Use: run | submit | profiles", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
