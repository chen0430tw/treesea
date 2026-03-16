from __future__ import annotations

"""llm_bridge — LLM interface layer for Tree Diagram.

Architecture position:
  External-facing layer that sits above oracle.  Translates between
  LLM-native formats (JSON text, natural language) and the internal
  Tree Diagram data structures.

Public exports:
  InputTranslator
  CandidateProposer
  HypothesisExpander
  ExplanationLayer
"""

from .input_translator import InputTranslator
from .candidate_proposer import CandidateProposer, ProposedCandidate
from .hypothesis_expander import HypothesisExpander, Hypothesis
from .explanation_layer import ExplanationLayer

__all__ = [
    "InputTranslator",
    "CandidateProposer",
    "ProposedCandidate",
    "HypothesisExpander",
    "Hypothesis",
    "ExplanationLayer",
]
