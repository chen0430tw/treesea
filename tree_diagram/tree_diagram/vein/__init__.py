from __future__ import annotations

"""vein — nutrient-flow and structural backbone layer.

Architecture position:
  Mid-layer between core (physics/algorithms) and control (governance).
  Responsible for resource allocation along the vein structure, withering
  logic, and multi-channel (tri-vein) candidate representation.

Public exports:
  VeinBackbone, TriVeinScore, VeinletExpert, AngioResourceController
"""

from .vein_backbone import VeinBackbone, extract_main_branches
from .tri_vein_kernel import TriVeinScore, compute_tri_vein
from .veinlet_experts import VeinletExpert, VeinletEnsemble
from .angio_resource_controller import AngioResourceController, NutrientState

__all__ = [
    "VeinBackbone",
    "extract_main_branches",
    "TriVeinScore",
    "compute_tri_vein",
    "VeinletExpert",
    "VeinletEnsemble",
    "AngioResourceController",
    "NutrientState",
]
