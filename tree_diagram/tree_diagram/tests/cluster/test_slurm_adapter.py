"""
Cluster tests: Slurm adapter, MPI dispatch, shard manager — import and
basic instantiation only (no real cluster required).
"""
from tree_diagram.cluster.slurm_adapter import SlurmAdapter
from tree_diagram.cluster.mpi_dispatch import MPIDispatch
from tree_diagram.cluster.shard_manager import ShardManager
from tree_diagram.cluster.distributed_reservoir import DistributedReservoir


def test_slurm_adapter_builds():
    adapter = SlurmAdapter()
    assert adapter is not None


def test_mpi_dispatch_builds():
    dispatch = MPIDispatch()
    assert dispatch is not None


def test_shard_manager_builds():
    manager = ShardManager()
    assert manager is not None


def test_distributed_reservoir_builds():
    reservoir = DistributedReservoir()
    assert reservoir is not None
