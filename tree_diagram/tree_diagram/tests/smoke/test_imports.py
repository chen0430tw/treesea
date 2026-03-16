"""
Smoke test: verify all top-level modules import without error.
"""
import importlib
import pytest

MODULES = [
    "tree_diagram.core.umdst_kernel",
    "tree_diagram.core.worldline_kernel",
    "tree_diagram.core.worldline_generator",
    "tree_diagram.core.group_field",
    "tree_diagram.core.group_field_encoder",
    "tree_diagram.core.ipl_phase_indexer",
    "tree_diagram.core.cbf_balancer",
    "tree_diagram.core.subject_phase_mapper",
    "tree_diagram.core.background_inference",
    "tree_diagram.core.problem_seed",
    "tree_diagram.core.oracle_output",
    "tree_diagram.vein.vein_backbone",
    "tree_diagram.vein.tri_vein_kernel",
    "tree_diagram.vein.veinlet_experts",
    "tree_diagram.vein.angio_resource_controller",
    "tree_diagram.control.utm_controller",
    "tree_diagram.control.utm_hydrology_controller",
    "tree_diagram.control.pressure_balancer",
    "tree_diagram.control.stability_phase_mapper",
    "tree_diagram.oracle.oracle_output",
    "tree_diagram.oracle.report_builder",
    "tree_diagram.oracle.mythic_formatter",
    "tree_diagram.oracle.audit_logger",
    "tree_diagram.llm_bridge.input_translator",
    "tree_diagram.llm_bridge.candidate_proposer",
    "tree_diagram.llm_bridge.hypothesis_expander",
    "tree_diagram.llm_bridge.explanation_layer",
    "tree_diagram.runtime.single_node_runner",
    "tree_diagram.runtime.multi_node_runner",
    "tree_diagram.runtime.scheduler_adapter",
    "tree_diagram.runtime.cache_manager",
    "tree_diagram.runtime.state_store",
    "tree_diagram.cluster.slurm_adapter",
    "tree_diagram.cluster.mpi_dispatch",
    "tree_diagram.cluster.shard_manager",
    "tree_diagram.cluster.distributed_reservoir",
    "tree_diagram.pipeline.candidate_pipeline",
    "tree_diagram.runtime.runner",
]


@pytest.mark.parametrize("module", MODULES)
def test_import(module):
    importlib.import_module(module)
