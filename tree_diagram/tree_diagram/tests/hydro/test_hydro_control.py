"""
Hydro tests: H-UTM hydrology controller, pressure balancer, stability phase mapper.
"""
from tree_diagram.control.utm_hydrology_controller import UTMHydrologyController
from tree_diagram.control.pressure_balancer import PressureBalancer
from tree_diagram.control.stability_phase_mapper import StabilityPhaseMapper


def _dummy_metrics(n: int = 6) -> list:
    return [
        {
            "name": f"branch_{i}",
            "balanced_score": 0.5 + 0.05 * i,
            "feasibility": 0.6,
            "stability": 0.7,
            "risk": 0.3,
            "branch_status": "active" if i < 3 else "restricted",
        }
        for i in range(n)
    ]


def test_hydrology_controller_builds():
    ctrl = UTMHydrologyController()
    assert ctrl is not None


def test_pressure_balancer():
    balancer = PressureBalancer()
    metrics = _dummy_metrics()
    result = balancer.balance(metrics)
    assert isinstance(result, (dict, list))


def test_stability_phase_mapper():
    mapper = StabilityPhaseMapper()
    metrics = _dummy_metrics()
    phase = mapper.map(metrics)
    assert isinstance(phase, (str, dict))
