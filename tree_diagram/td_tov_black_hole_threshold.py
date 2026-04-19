"""黑洞诞生阈值 — TOV 方程直接数值积分。

纯 SI 单位版本。Tolman-Oppenheimer-Volkoff 方程描述相对论性静态星体：

  dm/dr = 4π r² ρ
  dP/dr = -G (ρ + P/c²) (m + 4π r³ P/c²) / [r² (1 - 2Gm/(rc²))]

EOS: polytropic P = K ρ^γ
  γ = 2.75, K 调到再现 ~2 Msun TOV 极限（approximates stiff nuclear EOS）

扫描中心密度 ρ_c，对每个 ρ_c 积分得 (M, R)。M-R 曲线的 max M 即 TOV 极限：
  超过 M_TOV 的致密天体**必然**塌缩成 BH。

给定合并质量，判定是否跨越阈值。
"""
from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

# 物理常数 (SI)
G = 6.67430e-11          # m^3 kg^-1 s^-2
c = 2.99792458e8         # m/s
Msun = 1.98892e30        # kg

# Polytropic EOS 参数（SI：P in Pa, ρ in kg/m³）
# γ=2：Oppenheimer-Volkoff 1939 原始中子 polytrope 指数
#   数值稳定（γ>2.5 在 P→0 附近积分发散）
# K 标定：使 M_TOV ~ 2 Msun 匹配现代观测约束（PSR J0740+6620 ~ 2.08 Msun）
#   对 γ=2 polytrope, M_TOV ∝ √K; K=0.015 给出 M_TOV ≈ 2.0 Msun
GAMMA = 2.0
K_POLY = 0.015   # SI: P[Pa] = K * ρ[kg/m³]²


def eos_P(rho_si: float) -> float:
    return K_POLY * rho_si ** GAMMA


def eos_rho(P_si: float) -> float:
    if P_si <= 0:
        return 0.0
    return (P_si / K_POLY) ** (1.0 / GAMMA)


def tov_rhs(r: float, y: np.ndarray) -> list[float]:
    """TOV RHS in SI.

    y = [m (kg), P (Pa)]
    r in meters.
    """
    m, P = y
    if P <= 0 or r <= 0:
        return [0.0, 0.0]

    rho = eos_rho(P)

    # dm/dr
    dm_dr = 4.0 * np.pi * r**2 * rho

    # dP/dr
    num = -G * (rho + P / c**2) * (m + 4.0 * np.pi * r**3 * P / c**2)
    den = r**2 * (1.0 - 2.0 * G * m / (r * c**2))
    if den <= 0:
        return [0.0, 0.0]
    dP_dr = num / den

    return [dm_dr, dP_dr]


def integrate_star(rho_c_si: float, r_max_m: float = 100_000.0) -> tuple[float, float]:
    """Integrate outward from center to surface.

    Returns (M in Msun, R in km).

    Numerical note: polytropic EOS becomes stiff as P→0 (dρ/dP diverges).
    We use LSODA + a pressure floor (P < P_c × 1e-10 treated as surface).
    """
    P_c = eos_P(rho_c_si)
    P_floor = P_c * 1e-10           # 10 orders of magnitude below center = "surface"

    r0 = 1.0
    m0 = (4.0 / 3.0) * np.pi * r0**3 * rho_c_si
    y0 = [m0, P_c]

    def surface_event(r, y):
        return y[1] - P_floor
    surface_event.terminal = True
    surface_event.direction = -1

    try:
        sol = solve_ivp(
            tov_rhs,
            (r0, r_max_m),
            y0,
            events=surface_event,
            rtol=1e-8, atol=1e-8,
            method="LSODA",         # stiff-capable
        )
    except Exception:
        return np.nan, np.nan

    if len(sol.t_events[0]) > 0:
        R_m = float(sol.t_events[0][0])
        M_kg = float(sol.y_events[0][0][0])
    elif sol.y[1, -1] < P_c * 1e-6:
        # Integrator stalled but we're effectively at surface
        R_m = float(sol.t[-1])
        M_kg = float(sol.y[0, -1])
    else:
        return np.nan, np.nan

    return M_kg / Msun, R_m / 1000.0


def scan_tov_curve():
    """扫描中心密度，构建 M-R 曲线。"""
    # ρ_c 范围：1e17 到 1e19 kg/m³（对应核物质密度到超核）
    rho_cs = np.logspace(17.0, 19.0, 80)
    Ms, Rs, rhos = [], [], []
    for rho_c in rho_cs:
        M, R = integrate_star(rho_c)
        if np.isfinite(M) and np.isfinite(R) and 0 < M < 20 and 1 < R < 200:
            Ms.append(M)
            Rs.append(R)
            rhos.append(rho_c)
    return np.array(rhos), np.array(Ms), np.array(Rs)


def bh_threshold_analysis():
    print("=" * 70)
    print("TOV INTEGRATION — Black Hole Birth Threshold via Static NS Limit")
    print("=" * 70)
    print(f"EOS: polytropic P = K ρ^γ")
    print(f"  γ = {GAMMA}")
    print(f"  K = {K_POLY:.3e} SI  (tuned to nuclear density)")
    print()

    rho_cs, Ms, Rs = scan_tov_curve()

    if len(Ms) == 0:
        print("ERROR: no viable stars in scan range")
        return {}

    idx_max = int(np.argmax(Ms))
    M_TOV = float(Ms[idx_max])
    R_at_max = float(Rs[idx_max])
    rho_c_max = float(rho_cs[idx_max])

    print(f"Scanned {len(Ms)} central densities: "
          f"ρ_c ∈ [{rho_cs[0]:.2e}, {rho_cs[-1]:.2e}] kg/m³")
    print()
    print(f"TOV LIMIT: M_TOV = {M_TOV:.3f} Msun")
    print(f"  Radius at TOV max:  R = {R_at_max:.2f} km")
    print(f"  Central density:    ρ_c = {rho_c_max:.3e} kg/m³")
    print()

    # Schwarzschild radius comparison
    R_s_km = 2.0 * G * M_TOV * Msun / c**2 / 1000.0
    compactness = R_s_km / R_at_max
    print(f"Schwarzschild radius for M_TOV: R_s = {R_s_km:.2f} km")
    print(f"Compactness R_s/R = {compactness:.3f}  (BH when → 1)")
    print()

    # M-R curve sample
    print("M-R curve sample (every 10 points):")
    print(f"  {'ρ_c (kg/m³)':<16s} {'M (Msun)':<12s} {'R (km)':<10s}")
    for i in range(0, len(Ms), max(1, len(Ms) // 10)):
        marker = "  <-- TOV max" if i == idx_max else ""
        print(f"  {rho_cs[i]:<16.3e} {Ms[i]:<12.3f} {Rs[i]:<10.2f}{marker}")
    if idx_max % max(1, len(Ms) // 10) != 0:
        print(f"  {rho_cs[idx_max]:<16.3e} {Ms[idx_max]:<12.3f} "
              f"{Rs[idx_max]:<10.2f}  <-- TOV max")
    print()

    # 真实场景判决
    print("=" * 70)
    print("BH FORMATION VERDICTS")
    print("=" * 70)
    scenarios = [
        ("Canonical 1.4 Msun pulsar",                      1.40, "single NS"),
        ("PSR J0740+6620 (observational ceiling)",         2.08, "heaviest known NS"),
        ("GW170817 remnant (~2.6 Msun total mass)",        2.60, "BNS merger"),
        ("GW190425 remnant (~3.4 Msun)",                   3.40, "massive BNS"),
        ("1.4 + 1.4 = 2.8 Msun canonical BNS merger",      2.80, "typical BNS"),
        ("GW200105 NSBH (10.8 Msun total)",               10.80, "NSBH"),
        ("Stellar mass BH progenitor (~25 Msun core)",    25.00, "core collapse"),
    ]
    for name, M_obj, note in scenarios:
        if M_obj > M_TOV:
            verdict = "→ EXCEEDS TOV, must collapse to BH"
        else:
            verdict = "→ below TOV, remains NS"
        print(f"  {name:<45s} M = {M_obj:5.2f}  {verdict}")

    return {
        "M_TOV_Msun": M_TOV,
        "R_at_M_TOV_km": R_at_max,
        "rho_c_at_M_TOV_kg_per_m3": rho_c_max,
        "compactness": compactness,
        "schwarzschild_radius_km": R_s_km,
        "gamma": GAMMA,
        "K_poly_SI": K_POLY,
        "n_points_on_curve": len(Ms),
        "MR_curve": [
            {"rho_c": float(rho_cs[i]), "M_Msun": float(Ms[i]), "R_km": float(Rs[i])}
            for i in range(len(Ms))
        ],
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    result = bh_threshold_analysis()

    out = Path("D:/treesea/runs/tree_diagram/tov_bh_threshold.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nSaved → {out}")
