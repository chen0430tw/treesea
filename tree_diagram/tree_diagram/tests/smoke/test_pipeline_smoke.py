"""
Smoke test: run the full CandidatePipeline on the default seed with a
minimal grid to verify end-to-end connectivity.
"""
from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import default_seed


def test_pipeline_runs():
    pipe = CandidatePipeline(
        seed=default_seed(),
        top_k=4,
        NX=8,
        NY=6,
        steps=4,
        dt=45.0,
    )
    top_results, hydro, oracle = pipe.run()

    assert isinstance(top_results, list)
    assert len(top_results) > 0
    assert isinstance(hydro, dict)
    assert isinstance(oracle, dict)
    assert oracle.get("mode") == "abstract"
    assert "best_worldline" in oracle
