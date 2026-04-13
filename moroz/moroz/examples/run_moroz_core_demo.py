"""最小 MOROZ-Core demo — 猫词组 toy 实验。对位迁移自 archive/uploads/MOROZ代码.txt。"""
from __future__ import annotations

from moroz.core.moroz_core import MOROZCore, MOROZCoreConfig
from moroz.core.mscm import MSCM
from moroz.core.types import Candidate, FeatureWeights, SourceToken


def contains_any(text: str, keys: list[str]) -> float:
    return 1.0 if any(k in text for k in keys) else 0.0


# ── 五层源 ────────────────────────────────────────────────────────────────────
common_pinyin = [
    SourceToken("cat", "common_pinyin", 0.90),
    SourceToken("kitty", "common_pinyin", 0.85),
    SourceToken("kitten", "common_pinyin", 0.80),
    SourceToken("lazy", "common_pinyin", 0.60),
    SourceToken("sleepy", "common_pinyin", 0.70),
]
whois_domain = [
    SourceToken("mail", "whois_domain", 0.50),
    SourceToken("cloud", "whois_domain", 0.55),
]
personal = [
    SourceToken("mimi", "personal", 0.95),
]
context = [
    SourceToken("photo", "context", 0.80),
]
common_char: list[SourceToken] = []


# ── 五层特征函数 ──────────────────────────────────────────────────────────────
def phi_freq(c: Candidate) -> float:
    if not c.tokens:
        return 0.0
    return sum(t.prior for t in c.tokens) / len(c.tokens)

def phi_domain(c: Candidate) -> float:
    return contains_any(c.text, ["mail", "cloud"])

def phi_personal(c: Candidate) -> float:
    return contains_any(c.text, ["mimi"])

def phi_context(c: Candidate) -> float:
    return contains_any(c.text, ["photo", "cat", "kitty"])

def phi_syntax(c: Candidate) -> float:
    return 1.0 if len(c.tokens) <= 3 else 0.0


# ── 构建 MSCM ────────────────────────────────────────────────────────────────
mscm = MSCM(
    common_char=common_char,
    common_pinyin=common_pinyin,
    whois_domain=whois_domain,
    personal=personal,
    context=context,
    weights=FeatureWeights(freq=1.0, domain=0.7, personal=0.8, context=1.0, syntax=1.0),
    phi_freq=phi_freq,
    phi_domain=phi_domain,
    phi_personal=phi_personal,
    phi_context=phi_context,
    phi_syntax=phi_syntax,
)


# ── Gate 定义 ─────────────────────────────────────────────────────────────────
def prefix_gate(c: Candidate) -> bool:
    return len(c.tokens) <= 3

def full_gate(c: Candidate) -> bool:
    return len(c.tokens) == 3

def structure_valid(c: Candidate) -> bool:
    return True


# ── 运行 ─────────────────────────────────────────────────────────────────────
core = MOROZCore(
    mscm=mscm,
    config=MOROZCoreConfig(max_len=3, budget=200, top_k=10, collapse_q=5),
    prefix_gate=prefix_gate,
    full_gate=full_gate,
    structure_valid=structure_valid,
)

result = core.run()

print("=== MOROZ-Core Top Candidates ===")
for score, cand in result.issc_result.ranked[:10]:
    print(f"  {score:.4f}  {cand.text}")

print("\n=== Collapse Stats ===")
s = result.issc_result.stats
print(f"  Entropy (H):        {s.entropy:.4f}")
print(f"  Top-q Coverage:     {s.top_q_coverage:.4f}")
print(f"  Retention Ratio:    {s.retention_ratio:.4f}")
print(f"  Effective Throughput: {s.theta_eff:.1f} cand/s")

print(f"\n=== Search Metrics ===")
m = result.kw_result.metrics
print(f"  Expanded:          {m.expanded}")
print(f"  Accepted:          {m.accepted}")
print(f"  Reject (prefix):   {m.reject_prefix}")
print(f"  Reject (full):     {m.reject_full}")
print(f"  Reject (structure): {m.reject_structure}")
print(f"  Reject (bound):    {m.reject_bound}")

print(f"\nElapsed: {result.elapsed_seconds:.6f}s")
