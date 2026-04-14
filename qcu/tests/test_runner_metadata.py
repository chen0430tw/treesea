from types import SimpleNamespace

from qcu.core.state_repr import IQPUConfig
from qcu.runtime.runner import QCURunner
from qcu.scheduler.models import Candidate, CandidateCluster, CollapseRequest


def test_runner_preserves_candidate_payload_in_entry_metadata():
    runner = QCURunner(IQPUConfig(Nq=1, Nm=1, d=2), fused=False)

    def fake_run_qcl_v6(**kwargs):
        return SimpleNamespace(
            DIM=4,
            C_end=0.123,
            dtheta_end=0.045,
            N_end=1.0,
            final_sz=[0.1],
            final_n=[0.2],
            final_rel_phase=[0.3],
            elapsed_sec=0.01,
        )

    runner.iqpu.run_qcl_v6 = fake_run_qcl_v6

    payload = {
        "label": "joint_2033",
        "gamma_pcm": 0.16,
        "gamma_boost": 0.70,
        "boost_duration": 2.6,
        "gamma_phi0": 0.25,
    }
    request = CollapseRequest(
        request_id="req-1",
        qcu_session_id="sess-1",
        clusters=[
            CandidateCluster(
                cluster_id="joint",
                candidates=[Candidate(candidate_id="joint_2033", payload=payload)],
            )
        ],
    )

    bundle = runner.run(request)
    entry = bundle.entries[0]

    assert entry.metadata["candidate_id"] == "joint_2033"
    assert entry.metadata["cluster_id"] == "joint"
    assert entry.metadata["gamma_pcm"] == payload["gamma_pcm"]
    assert entry.metadata["gamma_boost"] == payload["gamma_boost"]
    assert entry.metadata["boost_duration"] == payload["boost_duration"]
    assert entry.metadata["gamma_phi0"] == payload["gamma_phi0"]
    assert entry.metadata["label"] == payload["label"]
