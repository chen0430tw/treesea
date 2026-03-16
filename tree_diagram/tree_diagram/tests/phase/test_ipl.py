"""
Phase tests: IPL phase indexer and subject phase mapper.
"""
from tree_diagram.core.ipl_phase_indexer import IPLPhaseIndexer
from tree_diagram.core.subject_phase_mapper import SubjectPhaseMapper
from tree_diagram.core.problem_seed import default_seed
from tree_diagram.core.background_inference import infer_problem_background


def test_ipl_indexer_builds():
    seed = default_seed()
    bg = infer_problem_background(seed)
    indexer = IPLPhaseIndexer(seed=seed, background=bg)
    assert indexer is not None


def test_ipl_phase_index_returns_dict():
    seed = default_seed()
    bg = infer_problem_background(seed)
    indexer = IPLPhaseIndexer(seed=seed, background=bg)
    idx = indexer.build_index()
    assert isinstance(idx, dict)


def test_subject_phase_mapper():
    seed = default_seed()
    bg = infer_problem_background(seed)
    mapper = SubjectPhaseMapper(seed=seed, background=bg)
    phase = mapper.map()
    assert isinstance(phase, dict)


def test_group_field_encoder():
    from tree_diagram.core.group_field_encoder import encode
    seed = default_seed()
    field = encode(seed)
    assert isinstance(field, dict)
    assert "field_coherence" in field
    assert all(0.0 <= v <= 1.0 for v in field.values())
