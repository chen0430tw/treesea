"""tree-diagram run  — execute a pipeline run locally (or on a login node).

Usage:
    python -m tree_diagram.cli.run_local [OPTIONS]
    python -m tree_diagram run [OPTIONS]

Options:
    --profile   quick | default | cluster | deep  (default: default)
    --title     Problem title override
    --top-k     Override top_k from profile
    --out       Output JSON path (default: td_result_<profile>.json)
    --no-oracle Skip LLM bridge explanation layer
    --device    cpu | cuda | cuda:N  (auto-detect if omitted)
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tree-diagram run",
        description="Run Tree Diagram pipeline locally",
    )
    parser.add_argument("--profile", default="default",
                        choices=["quick", "default", "cluster", "deep"],
                        help="Compute profile (default: default)")
    parser.add_argument("--title",   default=None,
                        help="Override problem title in seed")
    parser.add_argument("--top-k",   type=int, default=None,
                        help="Override top_k from profile")
    parser.add_argument("--out",     default=None,
                        help="Output JSON path")
    parser.add_argument("--no-oracle", action="store_true",
                        help="Skip LLM bridge explanation layer")
    parser.add_argument("--device",  default=None,
                        help="Force device: cpu | cuda | cuda:N")
    args = parser.parse_args(argv)

    from .profiles import PROFILES, get_profile
    from ..core.problem_seed import default_seed
    from ..pipeline.candidate_pipeline import CandidatePipeline

    profile_kwargs = get_profile(args.profile)
    if args.top_k is not None:
        profile_kwargs["top_k"] = args.top_k
    if args.device is not None:
        profile_kwargs["device"] = args.device

    seed = default_seed()
    if args.title:
        seed.title = args.title

    desc = PROFILES[args.profile]["_desc"]
    print(f"[tree-diagram] profile={args.profile}  {desc}")
    print(f"[tree-diagram] NX={profile_kwargs['NX']}  NY={profile_kwargs['NY']}  "
          f"steps={profile_kwargs['steps']}  top_k={profile_kwargs['top_k']}")

    pipe = CandidatePipeline(seed=seed, **profile_kwargs)

    t0 = time.perf_counter()
    results, hydro, oracle = pipe.run()
    elapsed = time.perf_counter() - t0

    print(f"[tree-diagram] done in {elapsed:.2f}s  alive={hydro['alive_count']}")
    top = results[0]
    n_top = int(top.params.get("n", 0))
    print(f"[tree-diagram] #1  n={n_top}  family={top.family}/{top.template}"
          f"  final={top.final_balanced_score:.4f}"
          f"  aligned={n_top == 20000}")
    print(f"[tree-diagram] utm={hydro['utm_hydro_state']}"
          f"  background_emerged={oracle['background_naturally_emerged']}")

    out_path = args.out or f"td_result_{args.profile}.json"
    payload = {
        "profile":   args.profile,
        "elapsed_s": round(elapsed, 3),
        "top_results": [
            {
                "rank": i + 1,
                "family": r.family,
                "template": r.template,
                "n": int(r.params.get("n", 0)),
                "final_score": round(r.final_balanced_score, 6),
                "balanced_score": round(r.balanced_score, 6),
                "feasibility": round(r.feasibility, 6),
                "stability": round(r.stability, 6),
                "risk": round(r.risk, 6),
            }
            for i, r in enumerate(results)
        ],
        "hydro": {k: v for k, v in hydro.items()
                  if isinstance(v, (int, float, str, bool))},
        "oracle_summary": {
            "seed_title":        oracle.get("seed_title"),
            "background_emerged": oracle.get("background_naturally_emerged"),
            "inferred_goal":     oracle.get("inferred_goal_axis"),
            "dominant_pressures": oracle.get("dominant_pressures", [])[:3],
        },
    }
    if not args.no_oracle and "llm_explanation" in oracle:
        payload["llm_explanation"] = oracle["llm_explanation"]

    Path(out_path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[tree-diagram] output -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
