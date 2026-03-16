"""tree-diagram inspect  — display and summarise a result JSON file.

Usage:
    python -m tree_diagram inspect <result.json> [OPTIONS]
    tree-diagram inspect <result.json> [OPTIONS]

Options:
    --top-k   N     Show only top N results (default: all)
    --json          Re-emit the full JSON to stdout (pipe-friendly)
    --field  KEY    Print a single top-level field value and exit
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def _fmt(v, width: int = 8) -> str:
    if isinstance(v, float):
        return f"{v:.4f}".rjust(width)
    return str(v).rjust(width)


def _print_header(profile: str, elapsed: float, n_results: int) -> None:
    print(f"\n{'─'*72}")
    print(f"  Tree Diagram result  │  profile={profile}  elapsed={elapsed:.3f}s"
          f"  candidates={n_results}")
    print(f"{'─'*72}")


def _print_top_results(top_results: list, top_k: int | None) -> None:
    rows = top_results if top_k is None else top_results[:top_k]
    header = (
        f"{'rank':>4}  {'family':<12}  {'template':<10}  {'n':>6}  "
        f"{'final':>8}  {'balanced':>8}  {'feasib':>8}  {'stab':>8}  "
        f"{'risk':>8}  {'status':<10}"
    )
    print(header)
    print("─" * len(header))
    for r in rows:
        n_val   = r.get("n", r.get("params", {}).get("n", 0)) if isinstance(r.get("n"), int) else r.get("params", {}).get("n", 0)
        final   = r.get("final_score", r.get("final_balanced_score", r.get("balanced_score", 0.0)))
        bal     = r.get("balanced_score", 0.0)
        feas    = r.get("feasibility", 0.0)
        stab    = r.get("stability", 0.0)
        risk    = r.get("risk", 0.0)
        tmpl    = r.get("template", "")[:10]
        status  = r.get("branch_status", "")[:10]
        print(
            f"{r.get('rank',0):>4}  {r.get('family',''):<12}  {tmpl:<10}  "
            f"{n_val:>6}  {_fmt(final)}  {_fmt(bal)}  {_fmt(feas)}  "
            f"{_fmt(stab)}  {_fmt(risk)}  {status:<10}"
        )


def _print_hydro(hydro: dict) -> None:
    if not hydro:
        return
    print(f"\n{'─'*40}  Hydro")
    for k, v in hydro.items():
        if isinstance(v, float):
            print(f"  {k:<30}  {v:.4f}")
        else:
            print(f"  {k:<30}  {v}")


def _print_oracle(oracle: dict) -> None:
    if not oracle:
        return
    print(f"\n{'─'*40}  Oracle")
    for k, v in oracle.items():
        if isinstance(v, list):
            print(f"  {k:<30}  {v}")
        elif isinstance(v, bool):
            print(f"  {k:<30}  {v}")
        else:
            print(f"  {k:<30}  {v}")


def _print_explanation(text: str) -> None:
    print(f"\n{'─'*40}  LLM Explanation")
    # Word-wrap at 72 chars
    words = text.split()
    line  = "  "
    for w in words:
        if len(line) + len(w) + 1 > 72:
            print(line)
            line = "  " + w + " "
        else:
            line += w + " "
    if line.strip():
        print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tree-diagram inspect",
        description="Display and summarise a Tree Diagram result JSON",
    )
    parser.add_argument("result_file",
                        help="Path to result JSON (td_result_*.json)")
    parser.add_argument("--top-k",  type=int, default=None,
                        help="Show only top-N results")
    parser.add_argument("--json",   action="store_true",
                        help="Re-emit full JSON to stdout")
    parser.add_argument("--field",  default=None,
                        help="Print value of a single top-level field and exit")
    args = parser.parse_args(argv)

    path = Path(args.result_file)
    if not path.exists():
        print(f"[inspect] file not found: {path}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[inspect] invalid JSON: {e}", file=sys.stderr)
        return 1

    # --field shortcut
    if args.field:
        val = payload.get(args.field)
        if val is None:
            print(f"[inspect] field '{args.field}' not found", file=sys.stderr)
            return 1
        if isinstance(val, (dict, list)):
            print(json.dumps(val, indent=2, ensure_ascii=False))
        else:
            print(val)
        return 0

    # --json passthrough
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    # Pretty print
    profile  = payload.get("profile", "?")
    elapsed  = payload.get("elapsed_s", 0.0)
    results  = payload.get("top_results", [])
    hydro    = payload.get("hydro", {})
    oracle   = payload.get("oracle_summary", {})
    llm_text = payload.get("llm_explanation", "")

    _print_header(profile, elapsed, len(results))

    if results:
        _print_top_results(results, args.top_k)
    else:
        print("  (no top_results found)")

    _print_hydro(hydro)
    _print_oracle(oracle)

    if llm_text:
        _print_explanation(llm_text)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
