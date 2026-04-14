# agent/

This directory now targets the **internal CFPAI package**, not external subprocess wrappers.

Current chain:

```text
agent/orchestrator.py
→ agent/tools/*.py
→ cfpai/service/*.py
→ cfpai/multiasset_stooq.py
→ cfpai/multiasset_stooq_utm.py
```

This means:
- planning runs are handled inside the package
- backtests can run with or without UTM
- tuning runs are handled inside the package
- diagnostics/reporting read generated artifacts from `runs/`
