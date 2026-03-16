"""Tree Diagram abstract layer.

Each module in this package defines a Protocol (or ABC) that the
corresponding concrete implementation in tree_diagram.core must satisfy.
These protocols enable:
  - Static type-checking (mypy / pyright)
  - Alternative implementations (e.g. distributed, mocked, ML-augmented)
  - Documentation of the minimal interface contract per component
"""
from .problem_seed       import ProblemSeedProtocol
from .worldline_kernel   import EvaluationResultProtocol, WorldlineKernelProtocol
from .background_inference import ProblemBackgroundProtocol, BackgroundInferenceProtocol
from .group_field        import GroupFieldEncoderProtocol, GROUP_FIELD_AXES
from .branch_ecology     import BranchEcologyProtocol
from .balance_layer      import BalanceLayerProtocol
from .resource_controller import (
    BranchResourceProtocol, FlowReportProtocol,
    ResourceControllerProtocol, BRANCH_STATUSES,
)
from .oracle_output      import OracleOutputProtocol

__all__ = [
    "ProblemSeedProtocol",
    "EvaluationResultProtocol",
    "WorldlineKernelProtocol",
    "ProblemBackgroundProtocol",
    "BackgroundInferenceProtocol",
    "GroupFieldEncoderProtocol",
    "GROUP_FIELD_AXES",
    "BranchEcologyProtocol",
    "BalanceLayerProtocol",
    "BranchResourceProtocol",
    "FlowReportProtocol",
    "ResourceControllerProtocol",
    "BRANCH_STATUSES",
    "OracleOutputProtocol",
]
