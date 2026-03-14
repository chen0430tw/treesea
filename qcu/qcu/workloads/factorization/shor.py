# shor.py
"""
QCU Shor 因式分解工作负载。

基于 QFT 精确周期分布 + 连分数恢复的经典模拟 Shor 算法。
支持任意小整数 N 的单次运行和全 a 批量扫描。

公开 API
--------
modular_order(a, N)
continued_fraction_candidates(value, max_den)
recover_period_from_measurement(m, Q, a, N, max_den)
shor_classical_postprocess(a, N, r)
period_measurement_distribution(a, N, t)
sample_measurement(probs, rng)
shor_one_shot(N, a, t, rng)
shor_scan_all_a(N, t, shots_per_a, seed)
"""

from __future__ import annotations

from fractions import Fraction
from math import gcd
from typing import Optional, Tuple

import numpy as np


# ────────────────────────────────────────────
# 1. 核心数学
# ────────────────────────────────────────────

def modular_order(a: int, N: int) -> Optional[int]:
    """求满足 a^r ≡ 1 (mod N) 的最小正整数 r。"""
    if gcd(a, N) != 1:
        return None
    x = 1
    for r in range(1, N * N + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 100) -> Tuple[int, int]:
    """利用连分数逼近返回 (numerator, denominator)。"""
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(
    m: int,
    Q: int,
    a: int,
    N: int,
    max_den: int = 100,
) -> Optional[int]:
    """从测量值 m 通过连分数恢复周期 r。"""
    x = m / Q
    _, r = continued_fraction_candidates(x, max_den=max_den)

    if r <= 0:
        return None

    candidates = {r}
    for k in range(2, 6):
        candidates.add(k * r)
        if r % k == 0:
            candidates.add(r // k)

    for cand in sorted(c for c in candidates if c > 0):
        if pow(a, cand, N) == 1:
            return cand
    return None


def shor_classical_postprocess(
    a: int,
    N: int,
    r: Optional[int],
) -> Optional[Tuple[int, int]]:
    """已知偶周期 r，提取非平凡因子。"""
    if r is None or r % 2 != 0:
        return None

    x = pow(a, r // 2, N)
    if x == N - 1 or x == 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ────────────────────────────────────────────
# 2. QFT 精确周期分布
# ────────────────────────────────────────────

def period_measurement_distribution(a: int, N: int, t: int):
    """计算 QFT 测量第一寄存器的精确概率分布。

    Returns
    -------
    Q : int
        寄存器大小 2^t
    probs : ndarray, shape (Q,)
        归一化概率
    """
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups: dict = {}
    for x, v in enumerate(values):
        groups.setdefault(v, []).append(x)

    probs = np.zeros(Q, dtype=float)

    for idxs in groups.values():
        idxs = np.array(idxs, dtype=int)
        for m in range(Q):
            phase = np.exp(2j * np.pi * idxs * m / Q)
            amp = np.sum(phase) / Q
            probs[m] += np.abs(amp) ** 2

    probs /= probs.sum()
    return Q, probs


def sample_measurement(probs: np.ndarray, rng=None) -> int:
    """按概率分布采样一次测量值。"""
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ────────────────────────────────────────────
# 3. 单次运行与批量扫描
# ────────────────────────────────────────────

def shor_one_shot(N: int = 15, a: int = 2, t: int = 8, rng=None) -> dict:
    """单次 Shor 因式分解演示。

    Returns
    -------
    dict
        包含 N, a, t, Q, measurement_m, r_true, r_recovered, factors, success。
    """
    if rng is None:
        rng = np.random.default_rng()

    if gcd(a, N) != 1:
        g = gcd(a, N)
        return {
            "N": N, "a": a,
            "trivial_factor": g,
            "success": True,
            "factors": tuple(sorted((g, N // g))),
        }

    Q, probs = period_measurement_distribution(a, N, t=t)
    m = sample_measurement(probs, rng=rng)
    r_true = modular_order(a, N)
    r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 4)
    factors = shor_classical_postprocess(a, N, r_rec)

    return {
        "N": N,
        "a": a,
        "t": t,
        "Q": Q,
        "measurement_m": m,
        "measurement_ratio": m / Q,
        "r_true": r_true,
        "r_recovered": r_rec,
        "factors": factors,
        "success": factors is not None,
        "probs": probs,
    }


def shor_scan_all_a(
    N: int = 15,
    t: int = 8,
    shots_per_a: int = 200,
    seed: int = 42,
) -> list:
    """对所有与 N 互质的 a 批量统计 Shor 成功率。

    Returns
    -------
    list of dict
        每项包含 a, r_true, period_recovery_rate, factor_success_rate,
        most_common_factor。
    """
    rng = np.random.default_rng(seed)
    rows = []

    valid_as = [a for a in range(2, N) if gcd(a, N) == 1]

    for a in valid_as:
        r_true = modular_order(a, N)
        success_count = 0
        recovered_count = 0
        factor_counter: dict = {}

        Q, probs = period_measurement_distribution(a, N, t=t)

        for _ in range(shots_per_a):
            m = sample_measurement(probs, rng=rng)
            r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 4)
            fac = shor_classical_postprocess(a, N, r_rec)

            if r_rec == r_true:
                recovered_count += 1
            if fac is not None:
                success_count += 1
                factor_counter[fac] = factor_counter.get(fac, 0) + 1

        most_common_factor = None
        if factor_counter:
            most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

        rows.append({
            "a": a,
            "r_true": r_true,
            "period_recovery_rate": recovered_count / shots_per_a,
            "factor_success_rate": success_count / shots_per_a,
            "most_common_factor": most_common_factor,
        })

    return rows
