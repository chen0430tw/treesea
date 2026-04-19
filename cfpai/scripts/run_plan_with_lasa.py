"""
End-to-end demo: LASA portfolio → CFPAI plan → LASA events (zero-leverage).

Pipeline:
  1. Fetch current LASA portfolio snapshot via HTTP
  2. Convert to CFPAI budget via lasa_to_cfpai_budget
  3. Safety check leverage (default 1.0x = no leverage)
  4. Obtain weights (mock for now; real plan() requires market data)
  5. Convert weights → LASA events via cfpai_to_lasa_tags
  6. POST events back to LASA

Usage
-----
    python scripts/run_plan_with_lasa.py
    python scripts/run_plan_with_lasa.py --lasa-host http://localhost:3000
    python scripts/run_plan_with_lasa.py --real   # use real CFPAI plan()
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from cfpai.lasa_client import LASAClient, LASAClientError
from cfpai.lasa_bridge import (
    lasa_to_cfpai_budget,
    cfpai_to_lasa_tags,
    check_leverage_safety,
)


def mock_plan_weights(investable: float) -> dict[str, float]:
    """Fallback when we don't want to run real plan() (e.g. offline, no market data)."""
    # Simple 60/30/10 split into 3 tradeable buckets
    return {"SPY": 0.6, "QQQ": 0.3, "GLD": 0.1}


def real_plan_weights(investable: float, symbols: list[str] | None = None) -> dict[str, float]:
    """Call CFPAI's real plan() — requires market data to be downloadable."""
    from cfpai.api.planning_api import plan
    result = plan(symbols=symbols or ["SPY", "QQQ", "GLD"])
    return result.get("latest_weights", {})


def main():
    ap = argparse.ArgumentParser(description="LASA ↔ CFPAI end-to-end planning")
    ap.add_argument("--lasa-host", default="http://localhost:3000")
    ap.add_argument("--leverage", type=float, default=1.0,
                    help="Requested leverage ratio (1.0 = no leverage)")
    ap.add_argument("--real", action="store_true",
                    help="Use real CFPAI plan() (requires market data)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip posting events back to LASA")
    args = ap.parse_args()

    client = LASAClient(args.lasa_host)

    # 1. Portfolio snapshot
    print("=" * 60)
    print(f"[1/6] Fetching LASA portfolio from {args.lasa_host}...")
    try:
        portfolio = client.get_portfolio()
    except LASAClientError as e:
        print(f"  ✗ {e}")
        return 1
    print(f"  base currency: {portfolio['baseCurrency']}")
    print(f"  as of: {portfolio['asOf']}")
    inp = portfolio["input"]
    print(f"  input: {json.dumps(inp, indent=2)}")
    hist = portfolio.get("history", {})
    print(f"  history: {len(hist.get('monthlyCashflow', []))} months, "
          f"{len(hist.get('periods', []))} closed periods")
    if hist.get("monthlyCashflow"):
        print(f"  latest month: {hist['monthlyCashflow'][-1]}")

    # 2. Budget
    print("\n[2/6] Converting to CFPAI budget...")
    input_obj = client.get_portfolio_input()
    budget = lasa_to_cfpai_budget(input_obj)
    print(f"  budget: {json.dumps(budget, indent=2)}")

    # 3. Leverage safety
    print(f"\n[3/6] Leverage safety check (requested {args.leverage}x)...")
    safety = check_leverage_safety(input_obj, args.leverage)
    print(f"  {json.dumps(safety, indent=2)}")
    actual_leverage = safety["actual_leverage"]

    # 4. Planning (mock or real)
    investable = budget["investable"]
    if investable <= 0:
        print("\n  ✗ investable <= 0, cannot plan. Run /reset with initial cash first.")
        return 1
    print(f"\n[4/6] Planning weights (investable={investable})...")
    if args.real:
        print("  (using real CFPAI plan() — requires market data)")
        weights = real_plan_weights(investable)
    else:
        print("  (using MOCK weights for smoke test)")
        weights = mock_plan_weights(investable)
    print(f"  weights: {json.dumps(weights, indent=2)}")

    # 5. Convert to LASA events
    print("\n[5/6] Converting weights to LASA events...")
    events = cfpai_to_lasa_tags(weights, investable, actual_leverage)
    ts = datetime.utcnow().isoformat() + "Z"
    for i, ev in enumerate(events):
        ev["id"] = f"cfpai_{ts[:10]}_{i}"
        ev["timestamp"] = ts
        # LASA rule: TRADEABLE_ASSET_BUY for long, BORROWED_MONEY_IN for leverage, etc.
        if ev["accountClass"] == "ASSET" and ev["subClass"] == "tradeable":
            ev["rawCategoryHint"] = "TRADEABLE_ASSET_BUY"
        elif ev["accountClass"] == "LIABILITY":
            ev["rawCategoryHint"] = "BORROWED_MONEY_IN"
        ev["assetType"] = "tradeable" if ev["accountClass"] == "ASSET" else "cash"
        ev["destination"] = ev.get("symbol", "")
        ev["source"] = "CFPAI"
        ev["timeTag"] = "ONE_OFF"
    print(f"  → {len(events)} events generated")
    for ev in events:
        print(f"    {ev['id']} [{ev['rawCategoryHint']}] {ev['symbol']} "
              f"{ev['amount']} ({ev['description']})")

    # 6. Post back to LASA
    print(f"\n[6/6] {'(dry-run) skipping post' if args.dry_run else 'Posting events to LASA...'}")
    if not args.dry_run:
        for ev in events:
            try:
                resp = client.post_event(ev)
                print(f"  ✓ {ev['id']}: accountClass={resp.get('accountClass')}")
            except LASAClientError as e:
                print(f"  ✗ {ev['id']}: {e}")
                return 1
        # Final state
        final = client.get_portfolio_input()
        print(f"\nFinal portfolio input:")
        for k, v in final.__dict__.items():
            print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
