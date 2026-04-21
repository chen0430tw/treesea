"""Regression: Vein rerank must produce top_k-invariant top[0].

§11.21 — old code sliced by balanced_score to user's top_k, then reranked
that slice by vein-adjusted score. Different top_k → different slice →
different winner after rerank. Fix was to rerank on a wider pool then
slice. This test asserts the invariant: same seed/config, only top_k
changes, top[0] must be identical across top_k values.
"""
from tree_diagram.core.problem_seed import default_seed
from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline


def _top0(seed, k):
    top, _, _ = CandidatePipeline(
        seed=seed,
        top_k=k,
        NX=16, NY=12,
        steps=20,
        dt=45.0,
        device="cpu",
    ).run()
    r = top[0]
    return (r.family, r.template, round(r.balanced_score, 6),
            round(r.final_balanced_score, 6))


def test_vein_rerank_top0_stable_across_top_k():
    seed = default_seed()
    t3 = _top0(seed, 3)
    t5 = _top0(seed, 5)
    t8 = _top0(seed, 8)
    assert t3 == t5, f"top[0] diverged between top_k=3 and top_k=5: {t3} vs {t5}"
    assert t3 == t8, f"top[0] diverged between top_k=3 and top_k=8: {t3} vs {t8}"


def test_vein_rerank_prefix_consistent():
    """Stronger: top_k=3 result should be prefix of top_k=5 result."""
    seed = default_seed()
    top3, _, _ = CandidatePipeline(
        seed=seed, top_k=3, NX=16, NY=12, steps=20, dt=45.0, device="cpu").run()
    top5, _, _ = CandidatePipeline(
        seed=seed, top_k=5, NX=16, NY=12, steps=20, dt=45.0, device="cpu").run()

    keys3 = [(r.family, r.template, round(r.final_balanced_score, 6)) for r in top3]
    keys5 = [(r.family, r.template, round(r.final_balanced_score, 6)) for r in top5[:3]]
    assert keys3 == keys5, (
        f"top_3 not a prefix of top_5:\n  top3={keys3}\n  top5[:3]={keys5}"
    )
