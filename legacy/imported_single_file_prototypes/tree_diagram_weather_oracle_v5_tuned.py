# tree_diagram_weather_oracle_v5_tuned.py

# Tree Diagram Weather-Oracle v4
# Mesoscale meteorology-grade prototype for Colab
#
# Features:
# - 2D shallow-atmosphere surrogate with prognostic:
#     h (layer height / geopotential thickness surrogate)
#     u, v (horizontal wind)
#     T (temperature)
#     q (specific humidity)
# - semi-Lagrangian advection
# - Coriolis force
# - terrain/topography forcing
# - moisture condensation + latent heating
# - diffusion / drag / nudging
# - ensemble worldlines + Tree Diagram ranking
# - branch states: active / restricted / starved / withered
# - H-UTM-like hydro control
# - oracle summary + saved outputs
#
# This is still a compact prototype, but it is squarely in the NWP-style / mesoscale
# direction rather than a game toy.

from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# -------------------------
# Grid / constants
# -------------------------
NX, NY = 112, 84
DX, DY = 12000.0, 12000.0   # 12 km
DT = 45.0                   # 45 s
STEPS = 240                 # 3 h
G = 9.81
F0 = 8.0e-5                 # Coriolis
CP = 1004.0
LV = 2.5e6
BASE_H = 5400.0

OUT_DIR = Path("./tree_diagram_weather_v4_out")

x = np.linspace(-1.0, 1.0, NX)
y = np.linspace(-1.0, 1.0, NY)
XX, YY = np.meshgrid(x, y)

# -------------------------
# Helpers
# -------------------------
def clip(a, lo, hi):
    return np.clip(a, lo, hi)

def lap(f):
    return (
        (np.roll(f, -1, axis=0) - 2.0*f + np.roll(f, 1, axis=0)) / DY**2 +
        (np.roll(f, -1, axis=1) - 2.0*f + np.roll(f, 1, axis=1)) / DX**2
    )

def grad_x(f):
    return (np.roll(f, -1, axis=1) - np.roll(f, 1, axis=1)) / (2.0 * DX)

def grad_y(f):
    return (np.roll(f, -1, axis=0) - np.roll(f, 1, axis=0)) / (2.0 * DY)

def bilinear_sample(field, px, py):
    px = np.clip(px, 0.0, field.shape[1] - 1.001)
    py = np.clip(py, 0.0, field.shape[0] - 1.001)
    x0 = np.floor(px).astype(int)
    y0 = np.floor(py).astype(int)
    x1 = np.clip(x0 + 1, 0, field.shape[1] - 1)
    y1 = np.clip(y0 + 1, 0, field.shape[0] - 1)
    wx = px - x0
    wy = py - y0
    f00 = field[y0, x0]
    f10 = field[y0, x1]
    f01 = field[y1, x0]
    f11 = field[y1, x1]
    return (
        (1.0 - wx) * (1.0 - wy) * f00 +
        wx * (1.0 - wy) * f10 +
        (1.0 - wx) * wy * f01 +
        wx * wy * f11
    )

def semi_lagrangian(field, u, v, dt):
    jj, ii = np.meshgrid(np.arange(field.shape[0]), np.arange(field.shape[1]), indexing="ij")
    dep_x = ii - (u * dt / DX)
    dep_y = jj - (v * dt / DY)
    return bilinear_sample(field, dep_x, dep_y)

def smooth(field, alpha=0.10):
    return (1.0 - alpha) * field + alpha * (
        np.roll(field, 1, 0) + np.roll(field, -1, 0) +
        np.roll(field, 1, 1) + np.roll(field, -1, 1)
    ) / 4.0

# -------------------------
# Topography / synthetic obs
# -------------------------
topography = (
    1400.0 * np.exp(-7.0 * ((XX + 0.36) ** 2 + (YY - 0.06) ** 2)) +
     720.0 * np.exp(-10.5 * ((XX - 0.18) ** 2 + (YY + 0.24) ** 2)) +
     350.0 * np.exp(-14.0 * ((XX + 0.05) ** 2 + (YY + 0.28) ** 2))
)

def make_obs():
    h_obs = (
        BASE_H
        + 200.0 * np.exp(-6.8 * ((XX + 0.18) ** 2 + (YY + 0.10) ** 2))
        - 150.0 * np.exp(-8.0 * ((XX - 0.28) ** 2 + (YY - 0.14) ** 2))
        - 0.23 * topography
    )
    T_obs = (
        289.0
        + 7.5 * np.exp(-8.2 * ((XX + 0.16) ** 2 + (YY + 0.11) ** 2))
        - 5.8 * np.exp(-8.8 * ((XX - 0.24) ** 2 + (YY - 0.17) ** 2))
        - 0.0038 * topography
        + 0.8 * np.sin(1.2 * np.pi * XX) * np.cos(0.8 * np.pi * YY)
    )
    q_obs = (
        0.010
        + 0.011 * np.exp(-7.6 * ((XX - 0.10) ** 2 + (YY + 0.21) ** 2))
        + 0.0016 * np.sin(np.pi * YY)
    )
    u_obs = 12.0 * np.sin(0.9 * np.pi * YY) * np.cos(0.8 * np.pi * XX)
    v_obs = -8.5 * np.sin(0.8 * np.pi * XX) * np.cos(0.9 * np.pi * YY)
    return h_obs, u_obs, v_obs, T_obs, q_obs

H_OBS, U_OBS, V_OBS, T_OBS, Q_OBS = make_obs()

# -------------------------
# Initial condition
# -------------------------
def init_state():
    h = (
        BASE_H
        + 170.0 * np.exp(-7.0 * ((XX + 0.25) ** 2 + (YY + 0.02) ** 2))
        - 105.0 * np.exp(-7.8 * ((XX - 0.25) ** 2 + (YY - 0.18) ** 2))
        - 0.18 * topography
    )
    T = (
        288.0
        + 6.2 * np.exp(-7.5 * ((XX + 0.23) ** 2 + (YY + 0.04) ** 2))
        - 4.3 * np.exp(-9.2 * ((XX - 0.29) ** 2 + (YY - 0.16) ** 2))
        - 0.0032 * topography
    )
    q = 0.009 + 0.0085 * np.exp(-8.0 * ((XX - 0.08) ** 2 + (YY + 0.20) ** 2))
    u = 10.5 * np.sin(0.8 * np.pi * YY) * np.cos(0.7 * np.pi * XX)
    v = -7.2 * np.sin(0.7 * np.pi * XX) * np.cos(0.8 * np.pi * YY)

    return {
        "h": clip(h, BASE_H - 350.0, BASE_H + 350.0),
        "u": clip(u, -30.0, 30.0),
        "v": clip(v, -30.0, 30.0),
        "T": clip(T, 265.0, 315.0),
        "q": clip(q, 1e-5, 0.025),
    }

# -------------------------
# Branches
# -------------------------
BRANCHES = [
    {"name": "weak_mix",   "Kh": 240.0, "Kt": 120.0, "Kq": 95.0,  "drag": 1.2e-5, "humid_couple": 0.80, "nudging": 0.00014, "pg_scale": 1.00},
    {"name": "balanced",   "Kh": 360.0, "Kt": 180.0, "Kq": 130.0, "drag": 1.5e-5, "humid_couple": 1.00, "nudging": 0.00016, "pg_scale": 1.00},
    {"name": "high_mix",   "Kh": 520.0, "Kt": 260.0, "Kq": 180.0, "drag": 1.8e-5, "humid_couple": 1.05, "nudging": 0.00017, "pg_scale": 1.00},
    {"name": "humid_bias", "Kh": 340.0, "Kt": 175.0, "Kq": 220.0, "drag": 1.5e-5, "humid_couple": 1.24, "nudging": 0.00016, "pg_scale": 1.00},
    {"name": "strong_pg",  "Kh": 300.0, "Kt": 150.0, "Kq": 125.0, "drag": 1.2e-5, "humid_couple": 0.95, "nudging": 0.00015, "pg_scale": 1.18},
    {"name": "terrain_lock","Kh": 330.0,"Kt": 170.0, "Kq": 135.0, "drag": 1.6e-5, "humid_couple": 1.02, "nudging": 0.00015, "pg_scale": 1.04},
]

# -------------------------
# Physics
# -------------------------
def saturation_specific_humidity(T):
    return 0.0045 * np.exp(0.060 * (T - 273.15) / 10.0)

def condensation_and_heating(T, q, humid_couple):
    qsat = saturation_specific_humidity(T)
    excess = np.maximum(q - qsat, 0.0)
    cond = 0.20 * excess * humid_couple
    latent = (LV / CP) * cond * 1.0e-4
    return cond, latent

def branch_step(state, p):
    h, u, v, T, q = state["h"], state["u"], state["v"], state["T"], state["q"]

    # semi-Lagrangian advection
    h_adv = semi_lagrangian(h, u, v, DT)
    T_adv = semi_lagrangian(T, u, v, DT)
    q_adv = semi_lagrangian(q, u, v, DT)
    u_adv = semi_lagrangian(u, u, v, DT)
    v_adv = semi_lagrangian(v, u, v, DT)

    # pressure-gradient / geopotential
    geop = G * (h_adv + 0.18 * topography)
    pgx = p["pg_scale"] * grad_x(geop)
    pgy = p["pg_scale"] * grad_y(geop)

    # terrain-dependent drag
    topo_drag = 1.0 + 0.00035 * topography

    # momentum with Coriolis, drag, diffusion
    u_new = (
        u_adv
        - DT * pgx
        + DT * F0 * v_adv
        - DT * p["drag"] * topo_drag * u_adv
        + DT * p["Kh"] * lap(u_adv)
    )
    v_new = (
        v_adv
        - DT * pgy
        - DT * F0 * u_adv
        - DT * p["drag"] * topo_drag * v_adv
        + DT * p["Kh"] * lap(v_adv)
    )

    # shallow continuity surrogate
    div = grad_x(u_adv) + grad_y(v_adv)
    h_new = h_adv - DT * 0.55 * h_adv / BASE_H * div + DT * p["Kh"] * 0.35 * lap(h_adv)

    # latent heating
    cond, latent = condensation_and_heating(T_adv, q_adv, p["humid_couple"])

    T_eq = 286.5 - 0.0032 * topography
    T_new = T_adv + DT * p["Kt"] * lap(T_adv) + DT * latent - DT * 1.4e-5 * (T_adv - T_eq)
    q_source = 2.0e-6 * np.exp(-6.0 * (XX**2 + YY**2))
    q_new = q_adv + DT * p["Kq"] * lap(q_adv) + DT * q_source - DT * cond

    # observation nudging
    nud = p["nudging"]
    h_new += DT * nud * (H_OBS - h_new)
    T_new += DT * nud * (T_OBS - T_new)
    q_new += DT * nud * (Q_OBS - q_new)
    u_new += DT * nud * (U_OBS - u_new)
    v_new += DT * nud * (V_OBS - v_new)

    # light smoothing
    h_new = smooth(h_new, 0.06)
    T_new = smooth(T_new, 0.05)
    q_new = smooth(q_new, 0.05)
    u_new = smooth(u_new, 0.04)
    v_new = smooth(v_new, 0.04)

    # clamps
    h_new = clip(h_new, BASE_H - 500.0, BASE_H + 500.0)
    T_new = clip(T_new, 250.0, 320.0)
    q_new = clip(q_new, 1e-5, 0.030)
    u_new = clip(u_new, -40.0, 40.0)
    v_new = clip(v_new, -40.0, 40.0)

    return {"h": h_new, "u": u_new, "v": v_new, "T": T_new, "q": q_new}

# -------------------------
# Scoring / branch state
# -------------------------
def score_state(state):
    h, u, v, T, q = state["h"], state["u"], state["v"], state["T"], state["q"]

    h_err = float(np.mean((h - H_OBS) ** 2))
    t_err = float(np.mean((T - T_OBS) ** 2))
    q_err = float(np.mean((q - Q_OBS) ** 2))
    w_err = float(np.mean((u - U_OBS) ** 2 + (v - V_OBS) ** 2))
    instability = float(
        np.mean(np.abs(lap(T))) +
        0.8 * np.mean(np.abs(lap(q))) +
        0.5 * np.mean(np.abs(lap(u))) +
        0.5 * np.mean(np.abs(lap(v))) +
        0.35 * np.mean(np.abs(lap(h)))
    )
    score = -(
        0.80 * h_err / 1.0e4 +
        1.20 * t_err +
        280.0 * q_err +
        0.020 * w_err +
        0.030 * instability
    )
    return {
        "h_err": h_err,
        "t_err": t_err,
        "q_err": q_err,
        "w_err": w_err,
        "instability": instability,
        "score": score,
    }

def classify_branch(metric, best_score=None, score_span=None):
    # Adaptive Tree-Diagram status for meteorology ensemble:
    # judge branches relative to current ensemble, not by fixed absolute gates.
    s = metric["score"]
    inst = metric["instability"]
    if best_score is None:
        best_score = s
    if score_span is None:
        score_span = 1.0
    rel = best_score - s

    if rel <= max(0.20, 0.22 * score_span) and inst < 5.0e-8:
        return "active"
    if rel <= max(0.55, 0.45 * score_span) and inst < 1.2e-7:
        return "restricted"
    if rel <= max(1.20, 0.90 * score_span):
        return "starved"
    return "withered"

# -------------------------
# H-UTM-like hydro control
# -------------------------
def hydro_control(metrics):
    ranked = sorted(metrics, key=lambda x: x["score"], reverse=True)
    margin = ranked[0]["score"] - ranked[1]["score"]
    spread = ranked[0]["score"] - ranked[-1]["score"]
    pressure_balance = 1.0
    if margin < 0.08:
        pressure_balance += 0.04
    if spread > 1.4:
        pressure_balance -= 0.03
    pressure_balance = float(np.clip(pressure_balance, 0.94, 1.08))
    return {
        "pressure_balance": pressure_balance,
        "top_margin": margin,
        "score_spread": spread,
        "mean_score": float(np.mean([m["score"] for m in metrics])),
        "mean_instability": float(np.mean([m["instability"] for m in metrics])),
    }

# -------------------------
# Run
# -------------------------
def run_all(pressure_balance=1.0):
    states = {}
    metrics = []
    for br in BRANCHES:
        state = init_state()
        tuned = dict(br)
        tuned["pg_scale"] = br.get("pg_scale", 1.0) * pressure_balance
        for _ in range(STEPS):
            state = branch_step(state, tuned)
        met = score_state(state)
        met["branch"] = br["name"]
        metrics.append(met)
        states[br["name"]] = state

    metrics = sorted(metrics, key=lambda x: x["score"], reverse=True)
    best_score = metrics[0]["score"]
    score_span = max(1e-6, metrics[0]["score"] - metrics[-1]["score"])
    for met in metrics:
        met["status"] = classify_branch(met, best_score=best_score, score_span=score_span)
    return states, metrics

def main():
    states0, metrics0 = run_all(1.0)
    hydro = hydro_control(metrics0)
    states, metrics = run_all(hydro["pressure_balance"])

    best = metrics[0]
    best_name = best["branch"]
    best_state = states[best_name]

    oracle = {
        "best_worldline": best_name,
        "best_status": best["status"],
        "hydro_control": hydro,
        "branch_histogram": {
            "active": sum(m["status"] == "active" for m in metrics),
            "restricted": sum(m["status"] == "restricted" for m in metrics),
            "starved": sum(m["status"] == "starved" for m in metrics),
            "withered": sum(m["status"] == "withered" for m in metrics),
        },
        "ranking": metrics,
    }

    print("=== Tree Diagram Weather-Oracle v4 ===")
    for m in metrics:
        print(m)
    print("\nOracle summary:")
    print(json.dumps(oracle, ensure_ascii=False, indent=2, default=float))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "oracle_output.json").write_text(json.dumps(oracle, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    h, u, v, T, q = best_state["h"], best_state["u"], best_state["v"], best_state["T"], best_state["q"]
    np.savez_compressed(OUT_DIR / "best_state.npz", h=h, u=u, v=v, T=T, q=q, H_obs=H_OBS, T_obs=T_OBS, Q_obs=Q_OBS, U_obs=U_OBS, V_obs=V_OBS, topo=topography)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    im0 = axes[0, 0].imshow(T, origin="lower")
    axes[0, 0].set_title("Best Branch Temperature")
    plt.colorbar(im0, ax=axes[0, 0], fraction=0.046)

    im1 = axes[0, 1].imshow(q, origin="lower")
    axes[0, 1].set_title("Best Branch Specific Humidity")
    plt.colorbar(im1, ax=axes[0, 1], fraction=0.046)

    im2 = axes[0, 2].imshow(h, origin="lower")
    axes[0, 2].set_title("Best Branch Layer Height")
    plt.colorbar(im2, ax=axes[0, 2], fraction=0.046)

    skip = 4
    axes[1, 0].quiver(u[::skip, ::skip], v[::skip, ::skip])
    axes[1, 0].set_title("Best Branch Wind")

    im4 = axes[1, 1].imshow(T_OBS, origin="lower")
    axes[1, 1].set_title("Pseudo Observation Temperature")
    plt.colorbar(im4, ax=axes[1, 1], fraction=0.046)

    names = [m["branch"] for m in metrics]
    scores = [m["score"] for m in metrics]
    colors = []
    for m in metrics:
        if m["status"] == "active":
            colors.append("tab:green")
        elif m["status"] == "restricted":
            colors.append("tab:orange")
        elif m["status"] == "starved":
            colors.append("tab:red")
        else:
            colors.append("gray")

    axes[1, 2].bar(names, scores, color=colors)
    axes[1, 2].set_title("Branch Scores / Status")
    axes[1, 2].tick_params(axis='x', rotation=25)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "summary.png", dpi=150)
    plt.show()

if __name__ == "__main__":
    main()
