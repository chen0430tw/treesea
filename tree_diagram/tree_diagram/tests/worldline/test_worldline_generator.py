"""
Worldline tests: candidate generation, UMDST kernel, CBF balancer.
"""
from tree_diagram.core.worldline_generator import generate, run
from tree_diagram.core.cbf_balancer import CBFBalancer
from tree_diagram.core.problem_seed import default_seed
from tree_diagram.core.background_inference import infer_problem_background


def test_generate_candidates_nonempty():
    seed = default_seed()
    bg = infer_problem_background(seed)
    candidates = generate(seed, bg)
    assert isinstance(candidates, list)
    assert len(candidates) > 0


def test_candidates_have_required_keys():
    seed = default_seed()
    bg = infer_problem_background(seed)
    candidates = generate(seed, bg)
    for c in candidates[:3]:
        assert "family" in c
        assert "template" in c
        assert "params" in c


def test_run_worldline_returns_results():
    seed = default_seed()
    bg = infer_problem_background(seed)
    top_results, hydro = run(seed, bg, NX=8, NY=6, steps=4, top_k=4, dt=45.0)
    assert len(top_results) > 0
    assert isinstance(hydro, dict)


def test_cbf_balancer():
    seed = default_seed()
    bg = infer_problem_background(seed)
    balancer = CBFBalancer(seed=seed, background=bg)
    assert balancer is not None
