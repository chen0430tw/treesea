# qcu_lang — QCU 量子语言桥接库
"""
qcu_lang 三层指令集架构：

  Layer 0 — 标准量子门      (GateType.*)
  Layer 1 — QCU 相位指令    (PhaseOp.*)
  Layer 2 — QCU 涌现指令    (EmergeOp.*)
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
