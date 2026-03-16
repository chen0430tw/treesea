from __future__ import annotations

"""cluster — distributed cluster execution layer.

Architecture position:
  Infrastructure layer below runtime.  Provides Slurm job management,
  MPI rank dispatch, candidate sharding, and distributed state pooling.

Public exports:
  SlurmAdapter, SlurmJobSpec
  MPIDispatcher
  ShardManager, CandidateShard
  DistributedReservoir
"""

from .slurm_adapter import SlurmAdapter, SlurmJobSpec
from .mpi_dispatch import MPIDispatcher
from .shard_manager import ShardManager, CandidateShard
from .distributed_reservoir import DistributedReservoir

__all__ = [
    "SlurmAdapter",
    "SlurmJobSpec",
    "MPIDispatcher",
    "ShardManager",
    "CandidateShard",
    "DistributedReservoir",
]
