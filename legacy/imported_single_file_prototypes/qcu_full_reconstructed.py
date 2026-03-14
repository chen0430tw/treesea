# qcu_full_reconstructed.py
"""
QCU full reconstructed source
Reconstructed from:
1) untitled2.py  -> QCU / IQPU virtual quantum chip core
2) Untitled4.ipynb -> later Shor / hash / reverse-hash / HMPL experiment blocks

Notes:
- This file is an archival full-bundle reconstruction.
- It intentionally preserves the Colab-era experiment sections as separate blocks.
- The goal is source recovery completeness first, not final library cleanliness.
"""

# =========================
# Part I. QCU / IQPU core
# =========================

"""
QCU / IQPU reconstructed source
Reconstructed from the final complete Colab section in untitled2.py.

Notes:
- Preserves the latest visible IQPUConfig / IQPURunResult / IQPU implementation.
- This is the virtual quantum chip core reconstructed from the uploaded Colab archive.
- The public-facing alias `QCU = IQPU` is added at the bottom for continuity with later naming.
"""

import numpy as np
import math
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt


# -------------------- utils --------------------
def dagger(a): return np.conjugate(a.T)
def kron(a, b): return np.kron(a, b)

def basis(n, i):
    v = np.zeros((n, 1), dtype=np.complex128)
    v[i, 0] = 1.0
    return v

def destroy(d):
    a = np.zeros((d, d), dtype=np.complex128)
    for n in range(1, d):
        a[n - 1, n] = math.sqrt(n)
    return a

def coherent_state(d, alpha):
    alpha = complex(alpha)
    v = np.zeros((d, 1), dtype=np.complex128)
    pref = np.exp(-abs(alpha) ** 2 / 2.0)
    fact = 1.0
    for n in range(d):
        if n > 0:
            fact *= n
        v[n, 0] = pref * (alpha ** n) / math.sqrt(fact)
    v /= (np.linalg.norm(v) + 1e-15)
    return v

def enforce_density_matrix(rho):
    rho[:] = 0.5 * (rho + dagger(rho))
    rho /= (np.trace(rho) + 1e-15)

def wrap_pi(x):
    return (x + np.pi) % (2*np.pi) - np.pi


# -------------------- entanglement monitor (negativity) --------------------
def partial_transpose_qubit0(rho: np.ndarray) -> np.ndarray:
    DIM = rho.shape[0]
    assert DIM % 2 == 0
    dim_rest = DIM // 2
    R = rho.reshape(2, dim_rest, 2, dim_rest)
    R_pt = np.transpose(R, (2, 1, 0, 3))
    return R_pt.reshape(DIM, DIM)

def negativity_qubit0_vs_rest(rho: np.ndarray) -> float:
    rho_pt = partial_transpose_qubit0(rho)
    rho_pt = 0.5 * (rho_pt + dagger(rho_pt))
    evals = np.linalg.eigvalsh(rho_pt)
    return float(np.sum(np.abs(evals[evals < 0.0])))


# -------------------- Lindblad RK4 core --------------------
def lindblad_rhs(rho, H, c_cache, tmp1, tmp2, out):
    np.matmul(H, rho, out=tmp1)
    np.matmul(rho, H, out=tmp2)
    out[:] = -1j * (tmp1 - tmp2)

    for c, cd, cd_c in c_cache:
        np.matmul(c, rho, out=tmp1)
        np.matmul(tmp1, cd, out=tmp2)
        out[:] += tmp2

        np.matmul(cd_c, rho, out=tmp1)
        out[:] += -0.5 * tmp1

        np.matmul(rho, cd_c, out=tmp1)
        out[:] += -0.5 * tmp1

    return out

def rk4_step(rho, dt, H, c_cache, buffers):
    tmp1, tmp2, k1, k2, k3, k4, work, out = buffers

    lindblad_rhs(rho, H, c_cache, tmp1, tmp2, k1)

    work[:] = rho + 0.5 * dt * k1
    lindblad_rhs(work, H, c_cache, tmp1, tmp2, k2)

    work[:] = rho + 0.5 * dt * k2
    lindblad_rhs(work, H, c_cache, tmp1, tmp2, k3)

    work[:] = rho + dt * k3
    lindblad_rhs(work, H, c_cache, tmp1, tmp2, k4)

    out[:] = rho + (dt/6.0) * (k1 + 2*k2 + 2*k3 + k4)
    enforce_density_matrix(out)
    return out


# -------------------- IQPU --------------------
@dataclass
class IQPUConfig:
    Nq: int = 2
    Nm: int = 2
    d: int = 6

    chi: Optional[np.ndarray] = None
    wc: Optional[np.ndarray] = None
    wq: Optional[np.ndarray] = None

    kappa: Optional[np.ndarray] = None
    T1: Optional[np.ndarray] = None
    Tphi: Optional[np.ndarray] = None

    phi_ref: float = 0.30
    eps_drive: Optional[List[complex]] = None

    t_max: float = 10.0
    dt: float = 0.05
    obs_every: int = 1

    qubits_init: Optional[List[str]] = None  # "g","e","+"
    alpha0: Optional[List[complex]] = None

    track_entanglement: bool = True


@dataclass
class IQPURunResult:
    label: str
    DIM: int
    elapsed_sec: float

    ts: np.ndarray
    rel_phase: np.ndarray
    C_log: np.ndarray
    neg_log: Optional[np.ndarray]

    final_sz: List[float]
    final_n: List[float]
    final_rel_phase: List[float]
    C_end: float
    dtheta_end: float
    N_end: Optional[float]


class IQPU:
    def __init__(self, cfg: IQPUConfig):
        self.cfg = self._finalize_cfg(cfg)

        self.Nq = self.cfg.Nq
        self.Nm = self.cfg.Nm
        self.d = self.cfg.d

        self.dimQ = 2 ** self.Nq
        self.dimM = (self.d ** self.Nm)
        self.DIM = self.dimQ * self.dimM

        self._build_ops()
        self._build_H_base()
        self._alloc_buffers()

    def _finalize_cfg(self, cfg: IQPUConfig) -> IQPUConfig:
        if cfg.chi is None:
            cfg.chi = 0.5 * np.ones((cfg.Nq, cfg.Nm), dtype=np.float64)
        if cfg.wc is None:
            cfg.wc = np.zeros(cfg.Nm, dtype=np.float64)
        if cfg.wq is None:
            cfg.wq = np.zeros(cfg.Nq, dtype=np.float64)
        if cfg.kappa is None:
            cfg.kappa = np.zeros(cfg.Nm, dtype=np.float64)
        if cfg.T1 is None:
            cfg.T1 = np.array([np.inf] * cfg.Nq, dtype=np.float64)
        if cfg.Tphi is None:
            cfg.Tphi = np.array([np.inf] * cfg.Nq, dtype=np.float64)
        if cfg.eps_drive is None:
            cfg.eps_drive = [0.0 + 0.0j] * cfg.Nm
        if cfg.qubits_init is None:
            cfg.qubits_init = ["g"] * cfg.Nq
        if cfg.alpha0 is None:
            base = [2.0, 1.5, 1.2, 1.0]
            cfg.alpha0 = [base[k] * np.exp(1j * cfg.phi_ref) for k in range(cfg.Nm)]

        cfg.chi = np.array(cfg.chi, dtype=np.float64)
        cfg.wc = np.array(cfg.wc, dtype=np.float64)
        cfg.wq = np.array(cfg.wq, dtype=np.float64)
        cfg.kappa = np.array(cfg.kappa, dtype=np.float64)
        cfg.T1 = np.array(cfg.T1, dtype=np.float64)
        cfg.Tphi = np.array(cfg.Tphi, dtype=np.float64)
        return cfg

    def _build_ops(self):
        self.I2 = np.eye(2, dtype=np.complex128)
        self.sz1 = np.array([[1, 0], [0, -1]], dtype=np.complex128)
        self.sx1 = np.array([[0, 1], [1, 0]], dtype=np.complex128)

        # sigma_minus = |g><e| with g=|0>, e=|1|
        self.sm1 = np.array([[0, 1],
                             [0, 0]], dtype=np.complex128)

        self.Id = np.eye(self.d, dtype=np.complex128)
        self.a1 = destroy(self.d)
        self.adag1 = dagger(self.a1)
        self.n1 = self.adag1 @ self.a1

        def embed_qubit(op2, j):
            Q = None
            for q in range(self.Nq):
                factor = op2 if q == j else self.I2
                Q = factor if Q is None else kron(Q, factor)
            return kron(Q, np.eye(self.dimM, dtype=np.complex128))

        def embed_mode(opd, k):
            M = None
            for m in range(self.Nm):
                factor = opd if m == k else self.Id
                M = factor if M is None else kron(M, factor)
            return kron(np.eye(self.dimQ, dtype=np.complex128), M)

        self.szJ = [embed_qubit(self.sz1, j) for j in range(self.Nq)]
        self.sxJ = [embed_qubit(self.sx1, j) for j in range(self.Nq)]
        self.smJ = [embed_qubit(self.sm1, j) for j in range(self.Nq)]

        self.aJ = [embed_mode(self.a1, k) for k in range(self.Nm)]
        self.adJ = [dagger(self.aJ[k]) for k in range(self.Nm)]
        self.nJ = [embed_mode(self.n1, k) for k in range(self.Nm)]

    def _build_H_base(self):
        cfg = self.cfg
        H = np.zeros((self.DIM, self.DIM), dtype=np.complex128)

        for k in range(self.Nm):
            H += cfg.wc[k] * self.nJ[k]
        for j in range(self.Nq):
            H += 0.5 * cfg.wq[j] * self.szJ[j]
        for j in range(self.Nq):
            for k in range(self.Nm):
                H += cfg.chi[j, k] * (self.szJ[j] @ self.nJ[k])

        # reference drive (per-mode)
        for k in range(self.Nm):
            eps = complex(cfg.eps_drive[k])
            H += 1j * (eps * self.adJ[k] - np.conjugate(eps) * self.aJ[k])

        self.H_base = H

    def _build_H_boost_trim(self, eps_boost: float, trim: float):
        """
        BOOST drive = eps_boost * eps_drive, with per-mode phase trim:
          mode0: +trim/2
          mode1: -trim/2
        """
        cfg = self.cfg
        H = self.H_base.copy()

        for k in range(self.Nm):
            base_eps = complex(cfg.eps_drive[k])
            if self.Nm == 1:
                delta = 0.0
            else:
                delta = (+0.5*trim) if k == 0 else (-0.5*trim)
            target_eps = (eps_boost * base_eps) * np.exp(1j * delta)
            delta_eps = target_eps - base_eps
            H += 1j * (delta_eps * self.adJ[k] - np.conjugate(delta_eps) * self.aJ[k])

        return H

    def _collapse_cache_for(self, gamma_sync: float, gamma_reset_q0: float = 0.0, gamma_phi0: float = 0.0):
        cfg = self.cfg
        c_ops = []

        for k in range(self.Nm):
            if cfg.kappa[k] > 0:
                c_ops.append(np.sqrt(cfg.kappa[k]) * self.aJ[k])

        for j in range(self.Nq):
            if np.isfinite(cfg.T1[j]) and cfg.T1[j] > 0:
                c_ops.append(np.sqrt(1.0 / cfg.T1[j]) * self.smJ[j])

        for j in range(self.Nq):
            if np.isfinite(cfg.Tphi[j]) and cfg.Tphi[j] > 0:
                c_ops.append(np.sqrt((1.0 / cfg.Tphi[j]) / 2.0) * self.szJ[j])

        if gamma_sync > 0 and self.Nm >= 2:
            g = np.sqrt(gamma_sync)
            for k in range(self.Nm - 1):
                c_ops.append(g * (self.aJ[k] - self.aJ[k + 1]))

        if gamma_reset_q0 > 0:
            c_ops.append(np.sqrt(gamma_reset_q0) * self.smJ[0])

        if gamma_phi0 > 0:
            c_ops.append(np.sqrt(gamma_phi0 / 2.0) * self.szJ[0])

        cache = []
        for c in c_ops:
            cd = dagger(c)
            cache.append((c, cd, cd @ c))
        return cache

    def _alloc_buffers(self):
        self._tmp1 = np.zeros_like(self.H_base)
        self._tmp2 = np.zeros_like(self.H_base)
        self._k1 = np.zeros_like(self.H_base)
        self._k2 = np.zeros_like(self.H_base)
        self._k3 = np.zeros_like(self.H_base)
        self._k4 = np.zeros_like(self.H_base)
        self._work = np.zeros_like(self.H_base)
        self._out = np.zeros_like(self.H_base)
        self.buffers = (self._tmp1, self._tmp2, self._k1, self._k2, self._k3, self._k4, self._work, self._out)

    def init_state(self):
        cfg = self.cfg
        q = None
        for s in cfg.qubits_init:
            if s == "g":
                v = basis(2, 0)
            elif s == "e":
                v = basis(2, 1)
            else:
                v = (basis(2, 0) + basis(2, 1)) / math.sqrt(2.0)
            q = v if q is None else kron(q, v)

        m = None
        for alpha in cfg.alpha0:
            v = coherent_state(self.d, alpha)
            m = v if m is None else kron(m, v)

        psi = kron(q, m)
        return psi @ dagger(psi)

    def expect(self, rho, op):
        return np.trace(rho @ op)

    def run_qcl_v6(
        self,
        label: str,
        t1: float,
        t2: float,
        omega_x: float,
        gamma_pcm: float,
        gamma_qim: float,
        gamma_boost: float,
        boost_duration: float,
        gamma_reset: float,
        gamma_phi0: float,
        eps_boost: float,
        boost_phase_trim: float,
    ) -> IQPURunResult:
        cfg = self.cfg
        rho = self.init_state()

        c_pcm = self._collapse_cache_for(gamma_pcm, 0.0, 0.0)
        c_qim = self._collapse_cache_for(gamma_qim, 0.0, 0.0)
        c_boost = self._collapse_cache_for(gamma_boost, gamma_reset, gamma_phi0)

        H_pulse = 0.5 * float(omega_x) * self.sxJ[0]
        H_boost = self._build_H_boost_trim(eps_boost, boost_phase_trim)

        t3 = min(cfg.t_max, t2 + boost_duration)

        steps = int(np.ceil(cfg.t_max / cfg.dt))
        ts_full = np.linspace(0.0, steps * cfg.dt, steps + 1)

        t_log, C_log, N_log, rel_phase_log = [], [], [], []

        t0 = time.time()
        for i, t in enumerate(ts_full):
            if (i % cfg.obs_every) == 0:
                a0 = self.expect(rho, self.aJ[0])
                a1 = self.expect(rho, self.aJ[1])
                C_log.append(abs(a0 - a1))
                rel_phase_log.append([wrap_pi(np.angle(a0) - cfg.phi_ref),
                                      wrap_pi(np.angle(a1) - cfg.phi_ref)])
                t_log.append(float(t))
                if cfg.track_entanglement:
                    N_log.append(negativity_qubit0_vs_rest(rho))

            if i < len(ts_full) - 1:
                if t < t1:
                    Ht, cache = self.H_base, c_pcm
                elif t < t2:
                    Ht, cache = self.H_base + H_pulse, c_qim
                elif t < t3:
                    Ht, cache = H_boost, c_boost
                else:
                    Ht, cache = self.H_base, c_pcm

                rho_next = rk4_step(rho, cfg.dt, Ht, cache, self.buffers)
                rho[:] = rho_next

        elapsed = time.time() - t0

        ts = np.array(t_log, dtype=np.float64)
        C_arr = np.array(C_log, dtype=np.float64)
        rel_phase = np.array(rel_phase_log, dtype=np.float64)
        neg_arr = np.array(N_log, dtype=np.float64) if cfg.track_entanglement else None

        n_end = [float(np.real(self.expect(rho, self.nJ[k]))) for k in range(self.Nm)]
        sz_end = [float(np.real(self.expect(rho, self.szJ[j]))) for j in range(self.Nq)]

        C_end = float(C_arr[-1])
        dtheta_end = float(abs(wrap_pi((np.angle(self.expect(rho, self.aJ[0])) - np.angle(self.expect(rho, self.aJ[1]))))))
        N_end = float(neg_arr[-1]) if (neg_arr is not None and len(neg_arr) > 0) else None

        return IQPURunResult(
            label=label,
            DIM=self.DIM,
            elapsed_sec=elapsed,
            ts=ts,
            rel_phase=rel_phase,
            C_log=C_arr,
            neg_log=neg_arr,
            final_sz=sz_end,
            final_n=n_end,
            final_rel_phase=rel_phase[-1].tolist(),
            C_end=C_end,
            dtheta_end=dtheta_end,
            N_end=N_end
        )


# -------------------- plotting --------------------
def plot_qcl(res: IQPURunResult, t1: float, t2: float, t3: float, prefix: str):
    fig, ax = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

    ax[0].plot(res.ts, res.rel_phase[:, 0], label="mode0")
    ax[0].plot(res.ts, res.rel_phase[:, 1], label="mode1")
    ax[0].axvspan(t1, t2, alpha=0.2, label="QIM")
    ax[0].axvspan(t2, t3, alpha=0.15, label="BOOST")
    ax[0].set_ylabel("arg<a>-phi_ref")
    ax[0].grid(True, alpha=0.3)
    ax[0].legend()

    ax[1].plot(res.ts, res.C_log, label="C(t)=|<a0>-<a1>|")
    ax[1].axvspan(t1, t2, alpha=0.2)
    ax[1].axvspan(t2, t3, alpha=0.15)
    ax[1].set_ylabel("C(t)")
    ax[1].grid(True, alpha=0.3)
    ax[1].legend()

    if res.neg_log is not None:
        ax[2].plot(res.ts, res.neg_log, label="Negativity (q0|rest)")
    ax[2].axvspan(t1, t2, alpha=0.2)
    ax[2].axvspan(t2, t3, alpha=0.15)
    ax[2].set_ylabel("Negativity")
    ax[2].set_xlabel("t")
    ax[2].grid(True, alpha=0.3)
    ax[2].legend()

    fig.suptitle(res.label)
    fig.tight_layout()
    out = f"{prefix}_window.png"
    fig.savefig(out, dpi=170)
    print("Saved", out)
    plt.show()


def plot_sweep(durs, C_ends, dtheta_ends, N_ends, prefix="iqpu_qcl_v6_sweep"):
    fig, ax = plt.subplots(1, 1, figsize=(9, 4))
    ax.plot(durs, np.log10(np.array(dtheta_ends) + 1e-16), marker="o", label="log10(dtheta_end)")
    ax.set_title("QCL recovery curve: log10(dtheta_end) vs boost_duration")
    ax.set_xlabel("boost_duration")
    ax.set_ylabel("log10(dtheta_end)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out = f"{prefix}_log_dtheta.png"
    fig.savefig(out, dpi=170)
    print("Saved", out)
    plt.show()

    fig2, ax2 = plt.subplots(1, 1, figsize=(9, 4))
    ax2.plot(durs, C_ends, marker="o", label="C_end")
    ax2.plot(durs, N_ends, marker="o", label="N_end")
    ax2.set_title("QCL recovery curve: C_end and N_end vs boost_duration")
    ax2.set_xlabel("boost_duration")
    ax2.set_ylabel("metric")
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    fig2.tight_layout()
    out2 = f"{prefix}_C_N.png"
    fig2.savefig(out2, dpi=170)
    print("Saved", out2)
    plt.show()


# -------------------- main --------------------
if __name__ == "__main__":
    phi_ref = 0.30

    cfg = IQPUConfig(
        Nq=2, Nm=2, d=6,
        chi=np.array([[0.50, 0.20],
                      [0.15, 0.45]], dtype=np.float64),
        wc=np.zeros(2),
        wq=np.zeros(2),
        kappa=np.array([0.02, 0.02], dtype=np.float64),
        T1=np.array([200.0, 200.0], dtype=np.float64),
        Tphi=np.array([300.0, 300.0], dtype=np.float64),
        phi_ref=phi_ref,
        eps_drive=[0.03 * np.exp(1j * phi_ref), 0.03 * np.exp(1j * phi_ref)],
        t_max=10.0,
        dt=0.05,
        obs_every=1,
        qubits_init=["g", "g"],
        alpha0=[2.0 * np.exp(1j * phi_ref), 1.5 * np.exp(1j * phi_ref)],
        track_entanglement=True
    )

    iqpu = IQPU(cfg)

    # fixed QCL params (your validated set)
    t1, t2 = 3.0, 5.0
    omega_x = 1.0

    gamma_pcm = 0.2
    gamma_qim = 0.03
    gamma_boost = 0.9
    gamma_reset = 0.25
    gamma_phi0 = 0.6
    eps_boost = 4.0
    boost_phase_trim = 0.012

    # --- sweep boost_duration ---
    sweep_durs = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    C_ends, dtheta_ends, N_ends = [], [], []

    for bd in sweep_durs:
        t3 = min(cfg.t_max, t2 + bd)
        res = iqpu.run_qcl_v6(
            label=f"QCL v6 sweep (boost_duration={bd})",
            t1=t1, t2=t2,
            omega_x=omega_x,
            gamma_pcm=gamma_pcm,
            gamma_qim=gamma_qim,
            gamma_boost=gamma_boost,
            boost_duration=bd,
            gamma_reset=gamma_reset,
            gamma_phi0=gamma_phi0,
            eps_boost=eps_boost,
            boost_phase_trim=boost_phase_trim
        )
        C_ends.append(res.C_end)
        dtheta_ends.append(res.dtheta_end)
        N_ends.append(res.N_end if res.N_end is not None else 0.0)

        print(res.label)
        print("  C_end =", f"{res.C_end:.6f}",
              " dtheta_end =", f"{res.dtheta_end:.6e}",
              " N_end =", f"{(res.N_end if res.N_end is not None else 0.0):.6e}",
              " elapsed_sec =", f"{res.elapsed_sec:.3f}")
        print()

    plot_sweep(sweep_durs, C_ends, dtheta_ends, N_ends, prefix="iqpu_qcl_v6_sweep")

    # --- one canonical run at boost_duration=3.0 ---
    bd = 3.0
    res = iqpu.run_qcl_v6(
        label="QCL v6 canonical (boost_duration=3.0)",
        t1=t1, t2=t2,
        omega_x=omega_x,
        gamma_pcm=gamma_pcm,
        gamma_qim=gamma_qim,
        gamma_boost=gamma_boost,
        boost_duration=bd,
        gamma_reset=gamma_reset,
        gamma_phi0=gamma_phi0,
        eps_boost=eps_boost,
        boost_phase_trim=boost_phase_trim
    )

    t3 = min(cfg.t_max, t2 + bd)
    print(res.label)
    print("  DIM =", res.DIM, "elapsed_sec =", round(res.elapsed_sec, 3))
    print("  final <sz> =", res.final_sz)
    print("  final <n>  =", res.final_n)
    print("  final rel phase =", res.final_rel_phase)
    print("  C_end =", f"{res.C_end:.6f}")
    print("  dtheta_end =", f"{res.dtheta_end:.6e}")
    print("  N_end =", f"{(res.N_end if res.N_end is not None else 0.0):.6e}")
    print()


# -------------------- public alias --------------------
QCUConfig = IQPUConfig
QCURunResult = IQPURunResult
QCU = IQPU



# =========================
# Part II.1 Notebook cell 14
# =========================


# =========================
# Colab-ready single cell
# Minimal Shor prototype for N=15
# - period finding by QFT
# - continued fraction recovery
# - factor extraction
# - plots
# =========================

import math
import random
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd


# ============================================================
# 1) Core math
# ============================================================
def modular_order(a: int, N: int) -> int | None:
    """Find the smallest r > 0 such that a^r mod N = 1."""
    if gcd(a, N) != 1:
        return None
    x = 1
    for r in range(1, N * N + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 100):
    """
    Return candidate denominators from convergents of value.
    For small demo, using Fraction.limit_denominator is enough.
    """
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 100):
    """
    Use continued fraction on m/Q ~ s/r and verify candidates.
    """
    x = m / Q
    _, r = continued_fraction_candidates(x, max_den=max_den)

    if r <= 0:
        return None

    # verify r and a small set of multiples/divisors
    candidates = set([r])
    for k in range(2, 6):
        candidates.add(k * r)
        if r % k == 0:
            candidates.add(r // k)

    for cand in sorted(c for c in candidates if c > 0):
        if pow(a, cand, N) == 1:
            return cand
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    """
    Given an even period r with a^(r/2) != -1 mod N,
    attempt to extract nontrivial factors.
    """
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


# ============================================================
# 2) Exact period-finding distribution by QFT formula
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    """
    Exact distribution for first register measurement after QFT,
    for Shor period finding on small toy examples.

    We simulate the textbook state:
      (1/sqrt(Q)) sum_x |x>|a^x mod N>
    then apply QFT to first register and trace out second register.

    Returns:
      Q, probs
    """
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    # group x indices by same modular value
    groups = {}
    for x, v in enumerate(values):
        groups.setdefault(v, []).append(x)

    probs = np.zeros(Q, dtype=float)

    # After measuring / tracing the second register,
    # each value-class contributes incoherently.
    for idxs in groups.values():
        idxs = np.array(idxs, dtype=int)
        # amplitude for each m from this subgroup
        for m in range(Q):
            phase = np.exp(2j * np.pi * idxs * m / Q)
            amp = np.sum(phase) / Q
            probs[m] += np.abs(amp) ** 2

    probs /= probs.sum()
    return Q, probs


def sample_measurement(probs: np.ndarray, rng=None) -> int:
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 3) One-shot Shor demo
# ============================================================
def shor_one_shot(N: int = 15, a: int = 2, t: int = 8, rng=None):
    """
    One minimal run:
    - build exact measurement distribution
    - sample a measurement
    - recover r by continued fractions
    - extract factors
    """
    if rng is None:
        rng = np.random.default_rng()

    if gcd(a, N) != 1:
        return {
            "N": N,
            "a": a,
            "trivial_factor": gcd(a, N),
            "success": True,
            "factors": tuple(sorted((gcd(a, N), N // gcd(a, N)))),
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


# ============================================================
# 4) Batch scan over valid a
# ============================================================
def shor_scan_all_a(N: int = 15, t: int = 8, shots_per_a: int = 200, seed: int = 42):
    rng = np.random.default_rng(seed)
    rows = []

    valid_as = [a for a in range(2, N) if gcd(a, N) == 1]

    for a in valid_as:
        r_true = modular_order(a, N)
        success_count = 0
        recovered_count = 0
        factor_counter = {}

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


# ============================================================
# 5) Visualization helpers
# ============================================================
def plot_distribution(probs: np.ndarray, title: str, filename: str):
    xs = np.arange(len(probs))
    plt.figure(figsize=(10, 4))
    plt.bar(xs, probs)
    plt.xlabel("Measured m")
    plt.ylabel("Probability")
    plt.title(title)
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_scan_rates(rows, filename: str):
    a_vals = [r["a"] for r in rows]
    period_rates = [r["period_recovery_rate"] for r in rows]
    factor_rates = [r["factor_success_rate"] for r in rows]

    plt.figure(figsize=(8, 4))
    x = np.arange(len(a_vals))
    w = 0.38
    plt.bar(x - w/2, period_rates, width=w, label="period recovery")
    plt.bar(x + w/2, factor_rates, width=w, label="factor success")
    plt.xticks(x, a_vals)
    plt.xlabel("a")
    plt.ylabel("Rate")
    plt.title("Shor N=15 scan over coprime a")
    plt.ylim(0, 1.05)
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 6) Run demo
# ============================================================
N = 15
a_demo = 2
t = 8

print("=" * 72)
print("Minimal Shor prototype started")
print(f"N = {N}")
print(f"a_demo = {a_demo}")
print(f"t = {t}   (Q = 2^t = {2**t})")
print("=" * 72)

# one-shot
demo = shor_one_shot(N=N, a=a_demo, t=t, rng=np.random.default_rng(123))
probs_demo = demo["probs"]

print("\nOne-shot demo:")
for k, v in demo.items():
    if k != "probs":
        print(f"{k}: {v}")

# scan all valid a
rows = shor_scan_all_a(N=N, t=t, shots_per_a=200, seed=123)

print("\nScan summary:")
for r in rows:
    print(r)

# save CSV
import csv
csv_path = "shor_n15_scan.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# plots
dist_path = f"shor_n15_distribution_a{a_demo}.png"
plot_distribution(
    probs_demo,
    title=f"Shor measurement distribution for N={N}, a={a_demo}, t={t}",
    filename=dist_path
)

rates_path = "shor_n15_success_rates.png"
plot_scan_rates(rows, rates_path)

print("\nSaved:")
print(" -", csv_path)
print(" -", dist_path)
print(" -", rates_path)


# =========================
# Part II.2 Notebook cell 15
# =========================


# =========================
# Colab-ready single cell
# Harder Shor progression scan
# N = 15, 21, 33, 35
# =========================

import math
import csv
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd


# ============================================================
# 1) Core math
# ============================================================
def modular_order(a: int, N: int, max_iter: int | None = None):
    if gcd(a, N) != 1:
        return None
    if max_iter is None:
        max_iter = N * N

    x = 1
    for r in range(1, max_iter + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 256):
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 256):
    x = m / Q
    _, r0 = continued_fraction_candidates(x, max_den=max_den)

    if r0 is None or r0 <= 0:
        return None

    candidates = set([r0])
    for k in range(2, 9):
        candidates.add(k * r0)
        if r0 % k == 0:
            candidates.add(r0 // k)

    for r in sorted(c for c in candidates if c > 0):
        if pow(a, r, N) == 1:
            return r
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    if r is None or r % 2 != 0:
        return None
    x = pow(a, r // 2, N)
    if x == 1 or x == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ============================================================
# 2) Exact measurement distribution
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    """
    Exact first-register measurement distribution after QFT.
    Works fine for small demo-scale N.
    """
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups = {}
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


def sample_measurement(probs: np.ndarray, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 3) One instance
# ============================================================
def shor_one_instance(N: int, a: int, t: int, shots: int = 200, seed: int = 123):
    rng = np.random.default_rng(seed)

    if gcd(a, N) != 1:
        g = gcd(a, N)
        return {
            "N": N,
            "a": a,
            "trivial_factor": g,
            "r_true": None,
            "period_recovery_rate": 0.0,
            "factor_success_rate": 1.0,
            "most_common_factor": tuple(sorted((g, N // g))),
        }

    r_true = modular_order(a, N)
    Q, probs = period_measurement_distribution(a, N, t)

    recovered = 0
    success = 0
    factor_counter = {}

    for _ in range(shots):
        m = sample_measurement(probs, rng=rng)
        r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 8)
        fac = shor_classical_postprocess(a, N, r_rec)

        if r_rec == r_true:
            recovered += 1
        if fac is not None:
            success += 1
            factor_counter[fac] = factor_counter.get(fac, 0) + 1

    most_common_factor = None
    if factor_counter:
        most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

    return {
        "N": N,
        "a": a,
        "Q": Q,
        "r_true": r_true,
        "period_recovery_rate": recovered / shots,
        "factor_success_rate": success / shots,
        "most_common_factor": most_common_factor,
        "probs": probs,
    }


# ============================================================
# 4) Batch progression
# ============================================================
def shor_progression_scan(N_list=None, t_map=None, shots=200, seed=123):
    if N_list is None:
        N_list = [15, 21, 33, 35]
    if t_map is None:
        t_map = {
            15: 8,
            21: 9,
            33: 10,
            35: 10,
        }

    rows = []
    detailed = []

    for N in N_list:
        t = t_map[N]
        valid_as = [a for a in range(2, N) if gcd(a, N) == 1]

        print("=" * 72)
        print(f"Scanning N = {N}   t = {t}   Q = {2**t}")
        print("=" * 72)

        for a in valid_as:
            result = shor_one_instance(N=N, a=a, t=t, shots=shots, seed=seed + 1000 * N + a)
            row = {
                "N": N,
                "a": a,
                "r_true": result["r_true"],
                "period_recovery_rate": result["period_recovery_rate"],
                "factor_success_rate": result["factor_success_rate"],
                "most_common_factor": result["most_common_factor"],
            }
            rows.append(row)
            detailed.append(result)
            print(row)

    return rows, detailed


# ============================================================
# 5) Plots
# ============================================================
def plot_success_by_N(rows, filename):
    Ns = sorted(set(r["N"] for r in rows))
    period_means = []
    factor_means = []

    for N in Ns:
        sub = [r for r in rows if r["N"] == N]
        period_means.append(np.mean([r["period_recovery_rate"] for r in sub]))
        factor_means.append(np.mean([r["factor_success_rate"] for r in sub]))

    x = np.arange(len(Ns))
    w = 0.38

    plt.figure(figsize=(8, 4))
    plt.bar(x - w/2, period_means, width=w, label="period recovery")
    plt.bar(x + w/2, factor_means, width=w, label="factor success")
    plt.xticks(x, Ns)
    plt.ylim(0, 1.05)
    plt.xlabel("N")
    plt.ylabel("Average rate over valid a")
    plt.title("Shor progression: average success by N")
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_factor_success_heatmap(rows, filename):
    Ns = sorted(set(r["N"] for r in rows))
    a_lists = {N: sorted(r["a"] for r in rows if r["N"] == N) for N in Ns}
    max_cols = max(len(v) for v in a_lists.values())

    heat = np.full((len(Ns), max_cols), np.nan)
    xtick_labels = [[""] * max_cols for _ in Ns]

    for i, N in enumerate(Ns):
        sub = sorted([r for r in rows if r["N"] == N], key=lambda r: r["a"])
        for j, r in enumerate(sub):
            heat[i, j] = r["factor_success_rate"]
            xtick_labels[i][j] = str(r["a"])

    plt.figure(figsize=(10, 4))
    plt.imshow(heat, aspect="auto", origin="lower", vmin=0, vmax=1)
    plt.colorbar(label="factor success rate")
    plt.yticks(range(len(Ns)), Ns)
    plt.xlabel("a index within each N-row")
    plt.ylabel("N")
    plt.title("Factor success heatmap")
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_distribution_for_case(detailed, N_target, a_target, filename):
    match = None
    for d in detailed:
        if d["N"] == N_target and d["a"] == a_target:
            match = d
            break
    if match is None:
        return

    probs = match["probs"]
    xs = np.arange(len(probs))

    plt.figure(figsize=(10, 4))
    plt.bar(xs, probs)
    plt.xlabel("Measured m")
    plt.ylabel("Probability")
    plt.title(f"Measurement distribution: N={N_target}, a={a_target}, r={match['r_true']}, Q={match['Q']}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 6) Run
# ============================================================
print("=" * 72)
print("Harder Shor progression scan started")
print("=" * 72)

rows, detailed = shor_progression_scan(
    N_list=[15, 21, 33, 35],
    t_map={15: 8, 21: 9, 33: 10, 35: 10},
    shots=200,
    seed=123,
)

# Save CSV
csv_path = "shor_progression_scan.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# Summary by N
summary = {}
for N in sorted(set(r["N"] for r in rows)):
    sub = [r for r in rows if r["N"] == N]
    summary[N] = {
        "mean_period_recovery_rate": float(np.mean([r["period_recovery_rate"] for r in sub])),
        "mean_factor_success_rate": float(np.mean([r["factor_success_rate"] for r in sub])),
        "best_a_by_factor_success": max(sub, key=lambda r: r["factor_success_rate"]),
        "worst_a_by_factor_success": min(sub, key=lambda r: r["factor_success_rate"]),
    }

print("\nSummary by N:")
for N, s in summary.items():
    print(f"\n[N={N}]")
    print(s)

# Plots
plot1 = "shor_progression_avg_success.png"
plot_success_by_N(rows, plot1)

plot2 = "shor_progression_factor_heatmap.png"
plot_factor_success_heatmap(rows, plot2)

# representative distributions
plot3 = "shor_distribution_N21_a2.png"
plot_distribution_for_case(detailed, N_target=21, a_target=2, filename=plot3)

plot4 = "shor_distribution_N35_a2.png"
plot_distribution_for_case(detailed, N_target=35, a_target=2, filename=plot4)

print("\nSaved:")
print(" -", csv_path)
print(" -", plot1)
print(" -", plot2)
print(" -", plot3)
print(" -", plot4)


# =========================
# Part II.3 Notebook cell 16
# =========================


# =========================
# Colab-ready single cell
# Shor phase-noise / readout-blur validation
# =========================

import math
import csv
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd


# ============================================================
# 1) Core math
# ============================================================
def modular_order(a: int, N: int, max_iter: int | None = None):
    if gcd(a, N) != 1:
        return None
    if max_iter is None:
        max_iter = N * N

    x = 1
    for r in range(1, max_iter + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 256):
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 256):
    x = m / Q
    _, r0 = continued_fraction_candidates(x, max_den=max_den)

    if r0 is None or r0 <= 0:
        return None

    candidates = set([r0])
    for k in range(2, 9):
        candidates.add(k * r0)
        if r0 % k == 0:
            candidates.add(r0 // k)

    for r in sorted(c for c in candidates if c > 0):
        if pow(a, r, N) == 1:
            return r
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    if r is None or r % 2 != 0:
        return None

    x = pow(a, r // 2, N)
    if x == 1 or x == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ============================================================
# 2) Ideal Shor measurement distribution
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups = {}
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


# ============================================================
# 3) Noise model: circular Gaussian blur
# ============================================================
def circular_gaussian_kernel(Q: int, sigma_bins: float):
    xs = np.arange(Q, dtype=float)
    dist = np.minimum(xs, Q - xs)
    kernel = np.exp(-0.5 * (dist / sigma_bins) ** 2)
    kernel /= kernel.sum()
    return kernel


def apply_phase_blur(probs: np.ndarray, sigma_bins: float):
    """
    Simulate phase/readout blur by circular convolution in measurement space.
    sigma_bins = 0 means no blur.
    """
    if sigma_bins <= 0:
        return probs.copy()

    Q = len(probs)
    kernel = circular_gaussian_kernel(Q, sigma_bins)
    blurred = np.fft.ifft(np.fft.fft(probs) * np.fft.fft(kernel)).real
    blurred = np.clip(blurred, 0.0, None)
    blurred /= blurred.sum()
    return blurred


def sample_measurement(probs: np.ndarray, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 4) One noisy case
# ============================================================
def shor_noisy_case(N: int, a: int, t: int, sigma_bins: float, shots: int = 200, seed: int = 123):
    rng = np.random.default_rng(seed)

    if gcd(a, N) != 1:
        g = gcd(a, N)
        return {
            "N": N,
            "a": a,
            "sigma_bins": sigma_bins,
            "r_true": None,
            "period_recovery_rate": 0.0,
            "factor_success_rate": 1.0,
            "most_common_factor": tuple(sorted((g, N // g))),
            "ideal_probs": None,
            "noisy_probs": None,
        }

    r_true = modular_order(a, N)
    Q, ideal_probs = period_measurement_distribution(a, N, t)
    noisy_probs = apply_phase_blur(ideal_probs, sigma_bins=sigma_bins)

    recovered = 0
    success = 0
    factor_counter = {}

    for _ in range(shots):
        m = sample_measurement(noisy_probs, rng=rng)
        r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 8)
        fac = shor_classical_postprocess(a, N, r_rec)

        if r_rec == r_true:
            recovered += 1
        if fac is not None:
            success += 1
            factor_counter[fac] = factor_counter.get(fac, 0) + 1

    most_common_factor = None
    if factor_counter:
        most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

    return {
        "N": N,
        "a": a,
        "t": t,
        "Q": Q,
        "sigma_bins": sigma_bins,
        "r_true": r_true,
        "period_recovery_rate": recovered / shots,
        "factor_success_rate": success / shots,
        "most_common_factor": most_common_factor,
        "ideal_probs": ideal_probs,
        "noisy_probs": noisy_probs,
    }


# ============================================================
# 5) Batch noisy scan
# ============================================================
def shor_noise_scan(
    cases=None,
    sigma_list=None,
    shots=300,
    seed=123,
):
    """
    cases: list of tuples (N, a, t)
    """
    if cases is None:
        cases = [
            (15, 2, 8),
            (21, 2, 9),
            (33, 2, 10),
            (35, 2, 10),
            (35, 4, 10),
        ]
    if sigma_list is None:
        sigma_list = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]

    rows = []
    detailed = []

    print("=" * 72)
    print("Shor phase-noise scan started")
    print("=" * 72)

    for (N, a, t) in cases:
        print(f"\n--- Case: N={N}, a={a}, t={t} ---")
        for sigma in sigma_list:
            result = shor_noisy_case(
                N=N,
                a=a,
                t=t,
                sigma_bins=sigma,
                shots=shots,
                seed=seed + 10000 * N + 100 * a + int(10 * sigma),
            )
            row = {
                "N": N,
                "a": a,
                "t": t,
                "sigma_bins": sigma,
                "r_true": result["r_true"],
                "period_recovery_rate": result["period_recovery_rate"],
                "factor_success_rate": result["factor_success_rate"],
                "most_common_factor": result["most_common_factor"],
            }
            rows.append(row)
            detailed.append(result)
            print(row)

    return rows, detailed


# ============================================================
# 6) Plots
# ============================================================
def plot_rate_vs_noise(rows, filename, metric="factor_success_rate"):
    groups = sorted(set((r["N"], r["a"]) for r in rows))
    plt.figure(figsize=(9, 5))
    for (N, a) in groups:
        sub = sorted(
            [r for r in rows if r["N"] == N and r["a"] == a],
            key=lambda r: r["sigma_bins"]
        )
        xs = [r["sigma_bins"] for r in sub]
        ys = [r[metric] for r in sub]
        plt.plot(xs, ys, marker="o", label=f"N={N}, a={a}")
    plt.xlabel("sigma_bins")
    plt.ylabel(metric)
    plt.title(f"{metric} vs phase/readout blur")
    plt.ylim(0, 1.05)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_distribution_compare(detailed, N_target, a_target, sigma_values, filename):
    matches = {}
    for d in detailed:
        if d["N"] == N_target and d["a"] == a_target and d["sigma_bins"] in sigma_values:
            matches[d["sigma_bins"]] = d

    plt.figure(figsize=(10, 6))
    for sigma in sigma_values:
        if sigma not in matches:
            continue
        probs = matches[sigma]["noisy_probs"]
        xs = np.arange(len(probs))
        plt.plot(xs, probs, label=f"sigma={sigma}")
    plt.xlabel("Measured m")
    plt.ylabel("Probability")
    plt.title(f"Distribution broadening: N={N_target}, a={a_target}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 7) Run
# ============================================================
rows, detailed = shor_noise_scan(
    cases=[
        (15, 2, 8),
        (21, 2, 9),
        (33, 2, 10),
        (35, 2, 10),
        (35, 4, 10),
    ],
    sigma_list=[0.0, 0.5, 1.0, 2.0, 4.0, 8.0],
    shots=300,
    seed=123,
)

# save CSV
csv_path = "shor_phase_noise_scan.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# summary
summary = {}
for key in sorted(set((r["N"], r["a"]) for r in rows)):
    N, a = key
    sub = sorted([r for r in rows if r["N"] == N and r["a"] == a], key=lambda r: r["sigma_bins"])
    summary[key] = {
        "best_factor_success": max(sub, key=lambda r: r["factor_success_rate"]),
        "worst_factor_success": min(sub, key=lambda r: r["factor_success_rate"]),
        "sigma_at_half_factor_success": next(
            (r["sigma_bins"] for r in sub if r["factor_success_rate"] <= 0.5),
            None
        ),
    }

print("\nSummary by case:")
for (N, a), s in summary.items():
    print(f"\n[N={N}, a={a}]")
    print(s)

# plots
plot1 = "shor_noise_factor_success.png"
plot_rate_vs_noise(rows, plot1, metric="factor_success_rate")

plot2 = "shor_noise_period_recovery.png"
plot_rate_vs_noise(rows, plot2, metric="period_recovery_rate")

plot3 = "shor_noise_distribution_N21_a2.png"
plot_distribution_compare(detailed, N_target=21, a_target=2, sigma_values=[0.0, 1.0, 2.0, 4.0, 8.0], filename=plot3)

plot4 = "shor_noise_distribution_N35_a2.png"
plot_distribution_compare(detailed, N_target=35, a_target=2, sigma_values=[0.0, 1.0, 2.0, 4.0, 8.0], filename=plot4)

print("\nSaved:")
print(" -", csv_path)
print(" -", plot1)
print(" -", plot2)
print(" -", plot3)
print(" -", plot4)


# =========================
# Part II.4 Notebook cell 17
# =========================


# =========================
# Colab-ready single cell
# Shor readout sharpening optimizer
# =========================

import math
import csv
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd


# ============================================================
# 1) Core math
# ============================================================
def modular_order(a: int, N: int, max_iter: int | None = None):
    if gcd(a, N) != 1:
        return None
    if max_iter is None:
        max_iter = N * N

    x = 1
    for r in range(1, max_iter + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 256):
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 256):
    x = m / Q
    _, r0 = continued_fraction_candidates(x, max_den=max_den)

    if r0 is None or r0 <= 0:
        return None

    candidates = set([r0])
    for k in range(2, 9):
        candidates.add(k * r0)
        if r0 % k == 0:
            candidates.add(r0 // k)

    for r in sorted(c for c in candidates if c > 0):
        if pow(a, r, N) == 1:
            return r
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    if r is None or r % 2 != 0:
        return None

    x = pow(a, r // 2, N)
    if x == 1 or x == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ============================================================
# 2) Ideal Shor distribution
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups = {}
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


# ============================================================
# 3) Blur model
# ============================================================
def circular_gaussian_kernel(Q: int, sigma_bins: float):
    xs = np.arange(Q, dtype=float)
    dist = np.minimum(xs, Q - xs)
    kernel = np.exp(-0.5 * (dist / sigma_bins) ** 2)
    kernel /= kernel.sum()
    return kernel


def circular_blur(probs: np.ndarray, sigma_bins: float):
    if sigma_bins <= 0:
        return probs.copy()
    Q = len(probs)
    kernel = circular_gaussian_kernel(Q, sigma_bins)
    out = np.fft.ifft(np.fft.fft(probs) * np.fft.fft(kernel)).real
    out = np.clip(out, 0.0, None)
    out /= out.sum()
    return out


# ============================================================
# 4) Readout sharpening optimizer
# ============================================================
def sharpen_distribution(probs: np.ndarray, blur_sigma: float, lam: float = 0.6, gamma: float = 1.3):
    """
    Simple stable sharpen:
      p1 = p + lam * (p - blur(p))
      p2 ~ p1^gamma
    """
    base_blur = circular_blur(probs, sigma_bins=blur_sigma)
    p1 = probs + lam * (probs - base_blur)
    p1 = np.clip(p1, 1e-15, None)
    p1 /= p1.sum()

    p2 = np.power(p1, gamma)
    p2 = np.clip(p2, 1e-15, None)
    p2 /= p2.sum()
    return p2


def sample_measurement(probs: np.ndarray, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 5) Evaluation
# ============================================================
def evaluate_distribution(N: int, a: int, Q: int, probs: np.ndarray, shots: int = 300, seed: int = 123):
    rng = np.random.default_rng(seed)
    r_true = modular_order(a, N)

    recovered = 0
    success = 0
    factor_counter = {}

    for _ in range(shots):
        m = sample_measurement(probs, rng=rng)
        r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 8)
        fac = shor_classical_postprocess(a, N, r_rec)

        if r_rec == r_true:
            recovered += 1
        if fac is not None:
            success += 1
            factor_counter[fac] = factor_counter.get(fac, 0) + 1

    most_common_factor = None
    if factor_counter:
        most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

    return {
        "r_true": r_true,
        "period_recovery_rate": recovered / shots,
        "factor_success_rate": success / shots,
        "most_common_factor": most_common_factor,
    }


# ============================================================
# 6) Optimization scan
# ============================================================
def shor_sharpen_scan(
    cases=None,
    noise_sigma=2.0,
    lam_list=None,
    gamma_list=None,
    shots=300,
    seed=123,
):
    if cases is None:
        cases = [
            (21, 2, 9),
            (35, 2, 10),
            (35, 4, 10),
        ]
    if lam_list is None:
        lam_list = [0.0, 0.2, 0.4, 0.6, 0.8]
    if gamma_list is None:
        gamma_list = [1.0, 1.1, 1.2, 1.3, 1.5]

    rows = []
    detailed = []

    print("=" * 72)
    print("Shor readout sharpening optimization started")
    print(f"noise_sigma = {noise_sigma}")
    print("=" * 72)

    for (N, a, t) in cases:
        print(f"\n--- Case: N={N}, a={a}, t={t} ---")

        Q, ideal_probs = period_measurement_distribution(a, N, t)
        noisy_probs = circular_blur(ideal_probs, sigma_bins=noise_sigma)

        # baseline noisy result
        base_eval = evaluate_distribution(N, a, Q, noisy_probs, shots=shots, seed=seed + 10000*N + 100*a)
        print("[baseline noisy]", base_eval)

        for lam in lam_list:
            for gamma in gamma_list:
                sharp_probs = sharpen_distribution(noisy_probs, blur_sigma=noise_sigma, lam=lam, gamma=gamma)
                ev = evaluate_distribution(
                    N, a, Q, sharp_probs,
                    shots=shots,
                    seed=seed + 10000*N + 100*a + int(100*lam) + int(1000*gamma)
                )

                row = {
                    "N": N,
                    "a": a,
                    "t": t,
                    "noise_sigma": noise_sigma,
                    "lam": lam,
                    "gamma": gamma,
                    "r_true": ev["r_true"],
                    "period_recovery_rate": ev["period_recovery_rate"],
                    "factor_success_rate": ev["factor_success_rate"],
                    "most_common_factor": ev["most_common_factor"],
                }
                rows.append(row)
                detailed.append({
                    "N": N,
                    "a": a,
                    "t": t,
                    "Q": Q,
                    "lam": lam,
                    "gamma": gamma,
                    "ideal_probs": ideal_probs,
                    "noisy_probs": noisy_probs,
                    "sharp_probs": sharp_probs,
                    **ev
                })
                print(row)

    return rows, detailed


# ============================================================
# 7) Plot helpers
# ============================================================
def plot_heatmap(rows, N_target, a_target, metric, filename):
    sub = [r for r in rows if r["N"] == N_target and r["a"] == a_target]
    lam_vals = sorted(set(r["lam"] for r in sub))
    gamma_vals = sorted(set(r["gamma"] for r in sub))

    grid = np.zeros((len(lam_vals), len(gamma_vals)), dtype=float)
    for i, lam in enumerate(lam_vals):
        for j, gamma in enumerate(gamma_vals):
            r = next(x for x in sub if x["lam"] == lam and x["gamma"] == gamma)
            grid[i, j] = r[metric]

    plt.figure(figsize=(6, 5))
    plt.imshow(grid, aspect="auto", origin="lower",
               extent=[gamma_vals[0], gamma_vals[-1], lam_vals[0], lam_vals[-1]],
               vmin=0, vmax=1)
    plt.colorbar(label=metric)
    plt.xlabel("gamma")
    plt.ylabel("lam")
    plt.title(f"{metric} heatmap: N={N_target}, a={a_target}")
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_distribution_compare(detailed, N_target, a_target, picks, filename):
    """
    picks: list of tuples [('label', lam, gamma), ...]
    baseline noisy is drawn automatically.
    """
    subs = [d for d in detailed if d["N"] == N_target and d["a"] == a_target]
    if not subs:
        return

    noisy_probs = subs[0]["noisy_probs"]
    xs = np.arange(len(noisy_probs))

    plt.figure(figsize=(10, 6))
    plt.plot(xs, noisy_probs, label="noisy baseline", linewidth=2)

    for label, lam, gamma in picks:
        match = next((d for d in subs if abs(d["lam"] - lam) < 1e-12 and abs(d["gamma"] - gamma) < 1e-12), None)
        if match is not None:
            plt.plot(xs, match["sharp_probs"], label=f"{label}: lam={lam}, gamma={gamma}")

    plt.xlabel("Measured m")
    plt.ylabel("Probability")
    plt.title(f"Sharpened distributions: N={N_target}, a={a_target}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 8) Run
# ============================================================
rows, detailed = shor_sharpen_scan(
    cases=[
        (21, 2, 9),
        (35, 2, 10),
        (35, 4, 10),
    ],
    noise_sigma=2.0,
    lam_list=[0.0, 0.2, 0.4, 0.6, 0.8],
    gamma_list=[1.0, 1.1, 1.2, 1.3, 1.5],
    shots=300,
    seed=123,
)

# save CSV
csv_path = "shor_sharpen_optimization.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# summarize best points
summary = {}
for key in sorted(set((r["N"], r["a"]) for r in rows)):
    N, a = key
    sub = [r for r in rows if r["N"] == N and r["a"] == a]
    best_factor = max(sub, key=lambda r: r["factor_success_rate"])
    best_period = max(sub, key=lambda r: r["period_recovery_rate"])
    summary[key] = {
        "best_factor_point": best_factor,
        "best_period_point": best_period,
    }

print("\nSummary by case:")
for (N, a), s in summary.items():
    print(f"\n[N={N}, a={a}]")
    print(s)

# plots
plot1 = "shor_sharpen_heatmap_N21_a2_factor.png"
plot_heatmap(rows, 21, 2, "factor_success_rate", plot1)

plot2 = "shor_sharpen_heatmap_N35_a2_factor.png"
plot_heatmap(rows, 35, 2, "factor_success_rate", plot2)

plot3 = "shor_sharpen_heatmap_N35_a4_factor.png"
plot_heatmap(rows, 35, 4, "factor_success_rate", plot3)

# choose best factor points for visual compare
def best_lg(N, a):
    sub = [r for r in rows if r["N"] == N and r["a"] == a]
    b = max(sub, key=lambda r: r["factor_success_rate"])
    return b["lam"], b["gamma"]

lam21, gam21 = best_lg(21, 2)
lam352, gam352 = best_lg(35, 2)
lam354, gam354 = best_lg(35, 4)

plot4 = "shor_sharpen_distribution_N21_a2.png"
plot_distribution_compare(
    detailed, 21, 2,
    picks=[("best", lam21, gam21)],
    filename=plot4
)

plot5 = "shor_sharpen_distribution_N35_a2.png"
plot_distribution_compare(
    detailed, 35, 2,
    picks=[("best", lam352, gam352)],
    filename=plot5
)

plot6 = "shor_sharpen_distribution_N35_a4.png"
plot_distribution_compare(
    detailed, 35, 4,
    picks=[("best", lam354, gam354)],
    filename=plot6
)

print("\nSaved:")
print(" -", csv_path)
print(" -", plot1)
print(" -", plot2)
print(" -", plot3)
print(" -", plot4)
print(" -", plot5)
print(" -", plot6)


# =========================
# Part II.5 Notebook cell 18
# =========================


# =========================
# Colab-ready single cell
# Medium-size Shor panel scan
# N = 39, 51, 55, 65, 77
# =========================

import math
import csv
import json
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd


# ============================================================
# 1) Core math
# ============================================================
def modular_order(a: int, N: int, max_iter: int | None = None):
    if gcd(a, N) != 1:
        return None
    if max_iter is None:
        max_iter = N * N

    x = 1
    for r in range(1, max_iter + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 512):
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 512):
    x = m / Q
    _, r0 = continued_fraction_candidates(x, max_den=max_den)

    if r0 is None or r0 <= 0:
        return None

    candidates = set([r0])
    for k in range(2, 13):
        candidates.add(k * r0)
        if r0 % k == 0:
            candidates.add(r0 // k)

    for r in sorted(c for c in candidates if c > 0):
        if pow(a, r, N) == 1:
            return r
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    if r is None or r % 2 != 0:
        return None

    x = pow(a, r // 2, N)
    if x == 1 or x == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ============================================================
# 2) Exact Shor measurement distribution
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    """
    Exact first-register measurement distribution after QFT.
    Good for medium demo scale.
    """
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups = {}
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


def sample_measurement(probs: np.ndarray, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 3) Optional circular Gaussian blur
# ============================================================
def circular_gaussian_kernel(Q: int, sigma_bins: float):
    xs = np.arange(Q, dtype=float)
    dist = np.minimum(xs, Q - xs)
    kernel = np.exp(-0.5 * (dist / sigma_bins) ** 2)
    kernel /= kernel.sum()
    return kernel


def apply_phase_blur(probs: np.ndarray, sigma_bins: float = 0.0):
    if sigma_bins <= 0:
        return probs.copy()
    Q = len(probs)
    kernel = circular_gaussian_kernel(Q, sigma_bins)
    out = np.fft.ifft(np.fft.fft(probs) * np.fft.fft(kernel)).real
    out = np.clip(out, 0.0, None)
    out /= out.sum()
    return out


# ============================================================
# 4) Per-(N,a) evaluation
# ============================================================
def evaluate_case(
    N: int,
    a: int,
    t: int,
    shots: int = 200,
    sigma_bins: float = 0.0,
    seed: int = 123,
):
    rng = np.random.default_rng(seed)

    if gcd(a, N) != 1:
        g = gcd(a, N)
        return {
            "N": N,
            "a": a,
            "Q": 2 ** t,
            "r_true": None,
            "period_recovery_rate": 0.0,
            "factor_success_rate": 1.0,
            "most_common_factor": tuple(sorted((g, N // g))),
            "probs": None,
        }

    r_true = modular_order(a, N)
    Q, probs = period_measurement_distribution(a, N, t=t)
    probs = apply_phase_blur(probs, sigma_bins=sigma_bins)

    recovered = 0
    success = 0
    factor_counter = {}

    for _ in range(shots):
        m = sample_measurement(probs, rng=rng)
        r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 8)
        fac = shor_classical_postprocess(a, N, r_rec)

        if r_rec == r_true:
            recovered += 1
        if fac is not None:
            success += 1
            factor_counter[fac] = factor_counter.get(fac, 0) + 1

    most_common_factor = None
    if factor_counter:
        most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

    return {
        "N": N,
        "a": a,
        "Q": Q,
        "r_true": r_true,
        "period_recovery_rate": recovered / shots,
        "factor_success_rate": success / shots,
        "most_common_factor": most_common_factor,
        "probs": probs,
    }


# ============================================================
# 5) Smart a selection
# ============================================================
def select_representative_a_values(
    N: int,
    max_candidates: int = 10,
    min_period: int = 2,
):
    """
    Pick a representative subset of coprime a values:
    - prefer diverse periods
    - skip trivial gcd
    - bias toward longer periods
    """
    coprimes = [a for a in range(2, N) if gcd(a, N) == 1]
    info = []

    for a in coprimes:
        r = modular_order(a, N)
        if r is None or r < min_period:
            continue
        info.append((a, r))

    # sort by period descending, then a
    info.sort(key=lambda x: (-x[1], x[0]))

    picked = []
    seen_periods = set()

    # first, one per new period
    for a, r in info:
        if r not in seen_periods:
            picked.append((a, r))
            seen_periods.add(r)
        if len(picked) >= max_candidates:
            break

    # then fill remaining slots with strongest periods
    if len(picked) < max_candidates:
        picked_as = {a for a, _ in picked}
        for a, r in info:
            if a not in picked_as:
                picked.append((a, r))
            if len(picked) >= max_candidates:
                break

    return picked


# ============================================================
# 6) Medium-size panel
# ============================================================
def run_medium_shor_panel(
    N_list=None,
    t_map=None,
    sigma_bins: float = 0.0,
    shots: int = 200,
    max_a_per_N: int = 10,
    seed: int = 123,
):
    if N_list is None:
        N_list = [39, 51, 55, 65, 77]
    if t_map is None:
        t_map = {
            39: 11,
            51: 11,
            55: 11,
            65: 11,
            77: 12,
        }

    rows = []
    detailed = []
    summary = {}

    print("=" * 72)
    print("Medium-size Shor panel started")
    print(f"sigma_bins = {sigma_bins}")
    print("=" * 72)

    for N in N_list:
        t = t_map[N]
        picked = select_representative_a_values(N, max_candidates=max_a_per_N, min_period=2)

        print(f"\n--- N = {N} | t = {t} | Q = {2**t} ---")
        print("selected a values:", picked)

        sub_rows = []
        for a, r_hint in picked:
            result = evaluate_case(
                N=N,
                a=a,
                t=t,
                shots=shots,
                sigma_bins=sigma_bins,
                seed=seed + 10000 * N + a,
            )

            row = {
                "N": N,
                "a": a,
                "t": t,
                "Q": result["Q"],
                "r_true": result["r_true"],
                "period_recovery_rate": result["period_recovery_rate"],
                "factor_success_rate": result["factor_success_rate"],
                "most_common_factor": result["most_common_factor"],
            }
            rows.append(row)
            sub_rows.append(row)
            detailed.append(result)

            print(row)

        summary[N] = {
            "mean_period_recovery_rate": float(np.mean([r["period_recovery_rate"] for r in sub_rows])),
            "mean_factor_success_rate": float(np.mean([r["factor_success_rate"] for r in sub_rows])),
            "best_a_by_factor_success": max(sub_rows, key=lambda r: r["factor_success_rate"]),
            "worst_a_by_factor_success": min(sub_rows, key=lambda r: r["factor_success_rate"]),
            "best_a_by_period_recovery": max(sub_rows, key=lambda r: r["period_recovery_rate"]),
            "selected_a_values": [{"a": a, "r_hint": r} for a, r in picked],
        }

    return rows, detailed, summary


# ============================================================
# 7) Plot helpers
# ============================================================
def plot_summary_by_N(summary: dict, filename: str):
    Ns = sorted(summary.keys())
    period_means = [summary[N]["mean_period_recovery_rate"] for N in Ns]
    factor_means = [summary[N]["mean_factor_success_rate"] for N in Ns]

    x = np.arange(len(Ns))
    w = 0.38

    plt.figure(figsize=(9, 5))
    plt.bar(x - w/2, period_means, width=w, label="period recovery")
    plt.bar(x + w/2, factor_means, width=w, label="factor success")
    plt.xticks(x, Ns)
    plt.ylim(0, 1.05)
    plt.xlabel("N")
    plt.ylabel("Average rate over selected a")
    plt.title("Medium-size Shor panel summary")
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_factor_heatmap(rows, filename: str):
    Ns = sorted(set(r["N"] for r in rows))
    grouped = {N: sorted([r for r in rows if r["N"] == N], key=lambda x: x["a"]) for N in Ns}
    max_cols = max(len(v) for v in grouped.values())

    heat = np.full((len(Ns), max_cols), np.nan)
    labels = []

    for i, N in enumerate(Ns):
        sub = grouped[N]
        row_labels = []
        for j, r in enumerate(sub):
            heat[i, j] = r["factor_success_rate"]
            row_labels.append(str(r["a"]))
        labels.append(row_labels)

    plt.figure(figsize=(10, 5))
    plt.imshow(heat, aspect="auto", origin="lower", vmin=0, vmax=1)
    plt.colorbar(label="factor success rate")
    plt.yticks(range(len(Ns)), Ns)
    plt.xlabel("selected a index")
    plt.ylabel("N")
    plt.title("Factor success heatmap")
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_distribution_for_best_case(detailed, N_target, a_target, filename):
    match = None
    for d in detailed:
        if d["N"] == N_target and d["a"] == a_target:
            match = d
            break
    if match is None or match["probs"] is None:
        return

    probs = match["probs"]
    xs = np.arange(len(probs))

    plt.figure(figsize=(10, 4))
    plt.bar(xs, probs)
    plt.xlabel("Measured m")
    plt.ylabel("Probability")
    plt.title(f"Distribution: N={N_target}, a={a_target}, r={match['r_true']}, Q={match['Q']}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 8) Run
# ============================================================
rows, detailed, summary = run_medium_shor_panel(
    N_list=[39, 51, 55, 65, 77],
    t_map={
        39: 11,
        51: 11,
        55: 11,
        65: 11,
        77: 12,
    },
    sigma_bins=0.0,      # 改成 1.0 / 2.0 可直接测噪声下表现
    shots=200,
    max_a_per_N=10,
    seed=123,
)

# save CSV
csv_path = "medium_shor_panel.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

# save summary json
json_path = "medium_shor_panel_summary.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("\nSummary by N:")
for N, s in summary.items():
    print(f"\n[N={N}]")
    print(s)

# plots
plot1 = "medium_shor_panel_summary.png"
plot_summary_by_N(summary, plot1)

plot2 = "medium_shor_panel_factor_heatmap.png"
plot_factor_heatmap(rows, plot2)

# plot best factor case for each N
plot_files = []
for N, s in summary.items():
    best = s["best_a_by_factor_success"]
    path = f"medium_shor_distribution_N{N}_a{best['a']}.png"
    plot_distribution_for_best_case(detailed, N_target=N, a_target=best["a"], filename=path)
    plot_files.append(path)

print("\nSaved:")
print(" -", csv_path)
print(" -", json_path)
print(" -", plot1)
print(" -", plot2)
for p in plot_files:
    print(" -", p)


# =========================
# Part II.6 Notebook cell 19
# =========================


# =========================
# Colab-ready single cell
# A+B+C unified panel
# A: medium + larger-N Shor panel
# B: ideal / noisy / sharpened comparison
# C: Lychrel number scan
# =========================

import math
import csv
import json
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd


# ============================================================
# 1) Core Shor math
# ============================================================
def modular_order(a: int, N: int, max_iter: int | None = None):
    if gcd(a, N) != 1:
        return None
    if max_iter is None:
        max_iter = N * N

    x = 1
    for r in range(1, max_iter + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 1024):
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 1024):
    x = m / Q
    _, r0 = continued_fraction_candidates(x, max_den=max_den)

    if r0 is None or r0 <= 0:
        return None

    candidates = set([r0])
    for k in range(2, 17):
        candidates.add(k * r0)
        if r0 % k == 0:
            candidates.add(r0 // k)

    for r in sorted(c for c in candidates if c > 0):
        if pow(a, r, N) == 1:
            return r
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    if r is None or r % 2 != 0:
        return None

    x = pow(a, r // 2, N)
    if x == 1 or x == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ============================================================
# 2) Exact measurement distribution
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups = {}
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


def sample_measurement(probs: np.ndarray, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 3) Blur + sharpen
# ============================================================
def circular_gaussian_kernel(Q: int, sigma_bins: float):
    xs = np.arange(Q, dtype=float)
    dist = np.minimum(xs, Q - xs)
    kernel = np.exp(-0.5 * (dist / sigma_bins) ** 2)
    kernel /= kernel.sum()
    return kernel


def circular_blur(probs: np.ndarray, sigma_bins: float):
    if sigma_bins <= 0:
        return probs.copy()
    Q = len(probs)
    kernel = circular_gaussian_kernel(Q, sigma_bins)
    out = np.fft.ifft(np.fft.fft(probs) * np.fft.fft(kernel)).real
    out = np.clip(out, 0.0, None)
    out /= out.sum()
    return out


def sharpen_distribution(probs: np.ndarray, blur_sigma: float, lam: float = 0.6, gamma: float = 1.2):
    base_blur = circular_blur(probs, sigma_bins=blur_sigma)
    p1 = probs + lam * (probs - base_blur)
    p1 = np.clip(p1, 1e-15, None)
    p1 /= p1.sum()

    p2 = np.power(p1, gamma)
    p2 = np.clip(p2, 1e-15, None)
    p2 /= p2.sum()
    return p2


# ============================================================
# 4) Evaluation
# ============================================================
def evaluate_distribution(N: int, a: int, Q: int, probs: np.ndarray, shots: int = 200, seed: int = 123):
    rng = np.random.default_rng(seed)
    r_true = modular_order(a, N)

    recovered = 0
    success = 0
    factor_counter = {}

    for _ in range(shots):
        m = sample_measurement(probs, rng=rng)
        r_rec = recover_period_from_measurement(m, Q, a, N, max_den=N * 8)
        fac = shor_classical_postprocess(a, N, r_rec)

        if r_rec == r_true:
            recovered += 1
        if fac is not None:
            success += 1
            factor_counter[fac] = factor_counter.get(fac, 0) + 1

    most_common_factor = None
    if factor_counter:
        most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

    return {
        "r_true": r_true,
        "period_recovery_rate": recovered / shots,
        "factor_success_rate": success / shots,
        "most_common_factor": most_common_factor,
    }


# ============================================================
# 5) Smart a selection
# ============================================================
def select_representative_a_values(N: int, max_candidates: int = 8, min_period: int = 2):
    coprimes = [a for a in range(2, N) if gcd(a, N) == 1]
    info = []
    for a in coprimes:
        r = modular_order(a, N)
        if r is None or r < min_period:
            continue
        info.append((a, r))

    info.sort(key=lambda x: (-x[1], x[0]))

    picked = []
    seen_periods = set()

    for a, r in info:
        if r not in seen_periods:
            picked.append((a, r))
            seen_periods.add(r)
        if len(picked) >= max_candidates:
            break

    picked_as = {a for a, _ in picked}
    if len(picked) < max_candidates:
        for a, r in info:
            if a not in picked_as:
                picked.append((a, r))
            if len(picked) >= max_candidates:
                break

    return picked


# ============================================================
# 6) Unified Shor panel: ideal / noisy / sharpened
# ============================================================
def run_unified_shor_panel(
    N_list=None,
    t_map=None,
    sigma_bins: float = 2.0,
    lam: float = 0.6,
    gamma: float = 1.2,
    shots: int = 200,
    max_a_per_N: int = 8,
    seed: int = 123,
):
    if N_list is None:
        N_list = [51, 55, 77, 85, 91, 95, 119]
    if t_map is None:
        t_map = {
            51: 11,
            55: 11,
            77: 12,
            85: 12,
            91: 12,
            95: 12,
            119: 12,
        }

    rows = []
    summary = {}

    print("=" * 72)
    print("Unified Shor panel started")
    print(f"sigma_bins = {sigma_bins}, lam = {lam}, gamma = {gamma}")
    print("=" * 72)

    for N in N_list:
        t = t_map[N]
        picked = select_representative_a_values(N, max_candidates=max_a_per_N, min_period=2)

        print(f"\n--- N = {N} | t = {t} | Q = {2**t} ---")
        print("selected a values:", picked)

        per_mode_rows = []
        for a, r_hint in picked:
            Q, ideal_probs = period_measurement_distribution(a, N, t)
            noisy_probs = circular_blur(ideal_probs, sigma_bins=sigma_bins)
            sharp_probs = sharpen_distribution(noisy_probs, blur_sigma=sigma_bins, lam=lam, gamma=gamma)

            for mode, probs in [
                ("ideal", ideal_probs),
                ("noisy", noisy_probs),
                ("sharpened", sharp_probs),
            ]:
                ev = evaluate_distribution(
                    N, a, Q, probs,
                    shots=shots,
                    seed=seed + 10000 * N + 100 * a + hash(mode) % 1000
                )
                row = {
                    "N": N,
                    "a": a,
                    "t": t,
                    "Q": Q,
                    "mode": mode,
                    "r_true": ev["r_true"],
                    "period_recovery_rate": ev["period_recovery_rate"],
                    "factor_success_rate": ev["factor_success_rate"],
                    "most_common_factor": ev["most_common_factor"],
                }
                rows.append(row)
                per_mode_rows.append(row)
                print(row)

        # summary by mode
        summary[N] = {}
        for mode in ["ideal", "noisy", "sharpened"]:
            sub = [r for r in per_mode_rows if r["mode"] == mode]
            summary[N][mode] = {
                "mean_period_recovery_rate": float(np.mean([r["period_recovery_rate"] for r in sub])),
                "mean_factor_success_rate": float(np.mean([r["factor_success_rate"] for r in sub])),
                "best_a_by_factor_success": max(sub, key=lambda r: r["factor_success_rate"]),
                "worst_a_by_factor_success": min(sub, key=lambda r: r["factor_success_rate"]),
            }
        summary[N]["selected_a_values"] = [{"a": a, "r_hint": r} for a, r in picked]

    return rows, summary


# ============================================================
# 7) Lychrel utilities
# ============================================================
def is_palindrome(n: int) -> bool:
    s = str(n)
    return s == s[::-1]


def reverse_number(n: int) -> int:
    return int(str(n)[::-1])


def lychrel_trace(n: int, max_iter: int = 50):
    x = n
    trace = [x]
    for i in range(1, max_iter + 1):
        x = x + reverse_number(x)
        trace.append(x)
        if is_palindrome(x):
            return {
                "start": n,
                "is_lychrel_candidate": False,
                "iterations_to_palindrome": i,
                "final_value": x,
                "trace": trace,
            }
    return {
        "start": n,
        "is_lychrel_candidate": True,
        "iterations_to_palindrome": None,
        "final_value": x,
        "trace": trace,
    }


def run_lychrel_scan(start_n: int = 1, end_n: int = 500, max_iter: int = 50):
    rows = []
    candidates = []

    print("\n" + "=" * 72)
    print(f"Lychrel scan started: range = [{start_n}, {end_n}], max_iter = {max_iter}")
    print("=" * 72)

    for n in range(start_n, end_n + 1):
        res = lychrel_trace(n, max_iter=max_iter)
        row = {
            "n": n,
            "is_lychrel_candidate": res["is_lychrel_candidate"],
            "iterations_to_palindrome": res["iterations_to_palindrome"],
            "final_value": res["final_value"],
        }
        rows.append(row)
        if res["is_lychrel_candidate"]:
            candidates.append(res)

    print(f"Total scanned: {len(rows)}")
    print(f"Lychrel candidates: {len(candidates)}")
    print("First few candidates:", [c["start"] for c in candidates[:20]])

    return rows, candidates


# ============================================================
# 8) Plot helpers
# ============================================================
def plot_shor_summary(summary: dict, filename: str, metric: str = "mean_factor_success_rate"):
    Ns = sorted(summary.keys())
    ideal = [summary[N]["ideal"][metric] for N in Ns]
    noisy = [summary[N]["noisy"][metric] for N in Ns]
    sharp = [summary[N]["sharpened"][metric] for N in Ns]

    x = np.arange(len(Ns))
    w = 0.25

    plt.figure(figsize=(10, 5))
    plt.bar(x - w, ideal, width=w, label="ideal")
    plt.bar(x, noisy, width=w, label="noisy")
    plt.bar(x + w, sharp, width=w, label="sharpened")
    plt.xticks(x, Ns)
    plt.ylim(0, 1.05)
    plt.xlabel("N")
    plt.ylabel(metric)
    plt.title(f"Unified Shor panel: {metric}")
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_lychrel_hist(rows, filename: str):
    vals = [r["iterations_to_palindrome"] for r in rows if r["iterations_to_palindrome"] is not None]
    plt.figure(figsize=(8, 4))
    plt.hist(vals, bins=30)
    plt.xlabel("Iterations to palindrome")
    plt.ylabel("Count")
    plt.title("Lychrel scan: iterations to palindrome")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 9) Run all
# ============================================================
shor_rows, shor_summary = run_unified_shor_panel(
    N_list=[51, 55, 77, 85, 91, 95, 119],
    t_map={
        51: 11,
        55: 11,
        77: 12,
        85: 12,
        91: 12,
        95: 12,
        119: 12,
    },
    sigma_bins=2.0,
    lam=0.6,
    gamma=1.2,
    shots=200,
    max_a_per_N=8,
    seed=123,
)

ly_rows, ly_candidates = run_lychrel_scan(
    start_n=1,
    end_n=1000,
    max_iter=60,
)

# save files
shor_csv = "unified_shor_panel.csv"
with open(shor_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(shor_rows[0].keys()))
    writer.writeheader()
    writer.writerows(shor_rows)

shor_json = "unified_shor_panel_summary.json"
with open(shor_json, "w", encoding="utf-8") as f:
    json.dump(shor_summary, f, indent=2, ensure_ascii=False)

ly_csv = "lychrel_scan.csv"
with open(ly_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(ly_rows[0].keys()))
    writer.writeheader()
    writer.writerows(ly_rows)

ly_json = "lychrel_candidates.json"
with open(ly_json, "w", encoding="utf-8") as f:
    json.dump(ly_candidates[:200], f, indent=2, ensure_ascii=False)

print("\nSummary by N:")
for N, s in shor_summary.items():
    print(f"\n[N={N}]")
    print(s)

print("\nLychrel summary:")
print({
    "total_scanned": len(ly_rows),
    "candidate_count": len(ly_candidates),
    "first_20_candidates": [c["start"] for c in ly_candidates[:20]]
})

# plots
plot1 = "unified_shor_factor_summary.png"
plot_shor_summary(shor_summary, plot1, metric="mean_factor_success_rate")

plot2 = "unified_shor_period_summary.png"
plot_shor_summary(shor_summary, plot2, metric="mean_period_recovery_rate")

plot3 = "lychrel_iterations_hist.png"
plot_lychrel_hist(ly_rows, plot3)

print("\nSaved:")
print(" -", shor_csv)
print(" -", shor_json)
print(" -", ly_csv)
print(" -", ly_json)
print(" -", plot1)
print(" -", plot2)
print(" -", plot3)


# =========================
# Part II.7 Notebook cell 20
# =========================


# =========================
# Colab-ready single cell
# QCS-LR Stage-2 Full Expansion
# - Bigger Shor panel
# - ideal / noisy / sharpened
# - Lychrel / Collatz / Amicable / Aliquot
# =========================

import math
import csv
import json
import numpy as np
import matplotlib.pyplot as plt
from fractions import Fraction
from math import gcd, isqrt


# ============================================================
# 1) Shor core
# ============================================================
def modular_order(a: int, N: int, max_iter: int | None = None):
    if gcd(a, N) != 1:
        return None
    if max_iter is None:
        max_iter = N * N

    x = 1
    for r in range(1, max_iter + 1):
        x = (x * a) % N
        if x == 1:
            return r
    return None


def continued_fraction_candidates(value: float, max_den: int = 4096):
    frac = Fraction(value).limit_denominator(max_den)
    return frac.numerator, frac.denominator


def recover_period_from_measurement(m: int, Q: int, a: int, N: int, max_den: int = 4096):
    x = m / Q
    _, r0 = continued_fraction_candidates(x, max_den=max_den)

    if r0 is None or r0 <= 0:
        return None

    candidates = set([r0])
    for k in range(2, 25):
        candidates.add(k * r0)
        if r0 % k == 0:
            candidates.add(r0 // k)

    for r in sorted(c for c in candidates if c > 0):
        if pow(a, r, N) == 1:
            return r
    return None


def shor_classical_postprocess(a: int, N: int, r: int):
    if r is None or r % 2 != 0:
        return None

    x = pow(a, r // 2, N)
    if x == 1 or x == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)

    if 1 < p < N and 1 < q < N and p * q == N:
        return tuple(sorted((p, q)))
    return None


# ============================================================
# 2) Exact measurement distribution
# ============================================================
def period_measurement_distribution(a: int, N: int, t: int):
    Q = 2 ** t
    values = [pow(a, x, N) for x in range(Q)]

    groups = {}
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


def sample_measurement(probs: np.ndarray, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(len(probs), p=probs))


# ============================================================
# 3) Blur + sharpen
# ============================================================
def circular_gaussian_kernel(Q: int, sigma_bins: float):
    xs = np.arange(Q, dtype=float)
    dist = np.minimum(xs, Q - xs)
    kernel = np.exp(-0.5 * (dist / sigma_bins) ** 2)
    kernel /= kernel.sum()
    return kernel


def circular_blur(probs: np.ndarray, sigma_bins: float):
    if sigma_bins <= 0:
        return probs.copy()
    Q = len(probs)
    kernel = circular_gaussian_kernel(Q, sigma_bins)
    out = np.fft.ifft(np.fft.fft(probs) * np.fft.fft(kernel)).real
    out = np.clip(out, 0.0, None)
    out /= out.sum()
    return out


def sharpen_distribution(probs: np.ndarray, blur_sigma: float, lam: float = 0.6, gamma: float = 1.2):
    base_blur = circular_blur(probs, sigma_bins=blur_sigma)
    p1 = probs + lam * (probs - base_blur)
    p1 = np.clip(p1, 1e-15, None)
    p1 /= p1.sum()

    p2 = np.power(p1, gamma)
    p2 = np.clip(p2, 1e-15, None)
    p2 /= p2.sum()
    return p2


# ============================================================
# 4) Shor evaluation
# ============================================================
def evaluate_distribution(N: int, a: int, Q: int, probs: np.ndarray, shots: int = 150, seed: int = 123):
    rng = np.random.default_rng(seed)
    r_true = modular_order(a, N)

    recovered = 0
    success = 0
    factor_counter = {}

    for _ in range(shots):
        m = sample_measurement(probs, rng=rng)
        r_rec = recover_period_from_measurement(m, Q, a, N, max_den=max(4096, N * 12))
        fac = shor_classical_postprocess(a, N, r_rec)

        if r_rec == r_true:
            recovered += 1
        if fac is not None:
            success += 1
            factor_counter[fac] = factor_counter.get(fac, 0) + 1

    most_common_factor = None
    if factor_counter:
        most_common_factor = max(factor_counter.items(), key=lambda kv: kv[1])[0]

    return {
        "r_true": r_true,
        "period_recovery_rate": recovered / shots,
        "factor_success_rate": success / shots,
        "most_common_factor": most_common_factor,
    }


# ============================================================
# 5) Representative a selector
# ============================================================
def select_representative_a_values(N: int, max_candidates: int = 8, min_period: int = 2):
    coprimes = [a for a in range(2, N) if gcd(a, N) == 1]
    info = []

    for a in coprimes:
        r = modular_order(a, N)
        if r is None or r < min_period:
            continue
        info.append((a, r))

    info.sort(key=lambda x: (-x[1], x[0]))

    picked = []
    seen_periods = set()

    for a, r in info:
        if r not in seen_periods:
            picked.append((a, r))
            seen_periods.add(r)
        if len(picked) >= max_candidates:
            break

    picked_as = {a for a, _ in picked}
    if len(picked) < max_candidates:
        for a, r in info:
            if a not in picked_as:
                picked.append((a, r))
            if len(picked) >= max_candidates:
                break

    return picked


# ============================================================
# 6) Big Shor panel
# ============================================================
def run_big_shor_panel(
    N_list=None,
    t_map=None,
    sigma_bins: float = 2.0,
    lam: float = 0.6,
    gamma: float = 1.2,
    shots: int = 150,
    max_a_per_N: int = 8,
    seed: int = 123,
):
    if N_list is None:
        N_list = [143, 187, 209, 221, 247, 299]

    if t_map is None:
        t_map = {
            143: 13,
            187: 13,
            209: 13,
            221: 13,
            247: 13,
            299: 13,
        }

    rows = []
    summary = {}

    print("=" * 72)
    print("Big Shor panel started")
    print(f"sigma_bins={sigma_bins}, lam={lam}, gamma={gamma}, shots={shots}")
    print("=" * 72)

    for N in N_list:
        t = t_map[N]
        picked = select_representative_a_values(N, max_candidates=max_a_per_N, min_period=2)

        print(f"\n--- N = {N} | t = {t} | Q = {2**t} ---")
        print("selected a values:", picked)

        local_rows = []

        for a, r_hint in picked:
            Q, ideal_probs = period_measurement_distribution(a, N, t)
            noisy_probs = circular_blur(ideal_probs, sigma_bins=sigma_bins)
            sharp_probs = sharpen_distribution(noisy_probs, blur_sigma=sigma_bins, lam=lam, gamma=gamma)

            for mode, probs in [
                ("ideal", ideal_probs),
                ("noisy", noisy_probs),
                ("sharpened", sharp_probs),
            ]:
                ev = evaluate_distribution(
                    N, a, Q, probs,
                    shots=shots,
                    seed=seed + 10000 * N + 100 * a + hash(mode) % 1000
                )

                row = {
                    "N": N,
                    "a": a,
                    "t": t,
                    "Q": Q,
                    "mode": mode,
                    "r_true": ev["r_true"],
                    "period_recovery_rate": ev["period_recovery_rate"],
                    "factor_success_rate": ev["factor_success_rate"],
                    "most_common_factor": ev["most_common_factor"],
                }
                rows.append(row)
                local_rows.append(row)
                print(row)

        summary[N] = {}
        for mode in ["ideal", "noisy", "sharpened"]:
            sub = [r for r in local_rows if r["mode"] == mode]
            summary[N][mode] = {
                "mean_period_recovery_rate": float(np.mean([r["period_recovery_rate"] for r in sub])),
                "mean_factor_success_rate": float(np.mean([r["factor_success_rate"] for r in sub])),
                "best_a_by_factor_success": max(sub, key=lambda r: r["factor_success_rate"]),
                "worst_a_by_factor_success": min(sub, key=lambda r: r["factor_success_rate"]),
            }
        summary[N]["selected_a_values"] = [{"a": a, "r_hint": r} for a, r in picked]

    return rows, summary


# ============================================================
# 7) Lychrel
# ============================================================
def is_palindrome(n: int) -> bool:
    s = str(n)
    return s == s[::-1]


def reverse_number(n: int) -> int:
    return int(str(n)[::-1])


def lychrel_trace(n: int, max_iter: int = 60):
    x = n
    trace = [x]
    for i in range(1, max_iter + 1):
        x = x + reverse_number(x)
        trace.append(x)
        if is_palindrome(x):
            return {
                "start": n,
                "is_lychrel_candidate": False,
                "iterations_to_palindrome": i,
                "final_value": x,
                "trace": trace,
            }
    return {
        "start": n,
        "is_lychrel_candidate": True,
        "iterations_to_palindrome": None,
        "final_value": x,
        "trace": trace,
    }


def run_lychrel_scan(start_n=1, end_n=5000, max_iter=80):
    rows = []
    candidates = []

    print("\n" + "=" * 72)
    print(f"Lychrel scan started: range = [{start_n}, {end_n}], max_iter = {max_iter}")
    print("=" * 72)

    for n in range(start_n, end_n + 1):
        res = lychrel_trace(n, max_iter=max_iter)
        row = {
            "n": n,
            "is_lychrel_candidate": res["is_lychrel_candidate"],
            "iterations_to_palindrome": res["iterations_to_palindrome"],
            "final_value": res["final_value"],
        }
        rows.append(row)
        if res["is_lychrel_candidate"]:
            candidates.append(res)

    print(f"Total scanned: {len(rows)}")
    print(f"Lychrel candidates: {len(candidates)}")
    print("First 20 candidates:", [c["start"] for c in candidates[:20]])
    return rows, candidates


# ============================================================
# 8) Collatz
# ============================================================
def collatz_metrics(n: int):
    x = n
    steps = 0
    peak = x
    while x != 1:
        if x % 2 == 0:
            x //= 2
        else:
            x = 3 * x + 1
        peak = max(peak, x)
        steps += 1
    return steps, peak


def run_collatz_scan(start_n=1, end_n=10000):
    rows = []
    best_steps = None
    best_peak = None

    print("\n" + "=" * 72)
    print(f"Collatz scan started: range = [{start_n}, {end_n}]")
    print("=" * 72)

    for n in range(start_n, end_n + 1):
        steps, peak = collatz_metrics(n)
        row = {
            "n": n,
            "steps_to_1": steps,
            "peak_value": peak,
        }
        rows.append(row)

        if best_steps is None or steps > best_steps["steps_to_1"]:
            best_steps = row
        if best_peak is None or peak > best_peak["peak_value"]:
            best_peak = row

    print("Max steps row:", best_steps)
    print("Max peak row:", best_peak)
    return rows, best_steps, best_peak


# ============================================================
# 9) Divisor / aliquot / amicable
# ============================================================
def sum_proper_divisors(n: int) -> int:
    if n <= 1:
        return 0
    total = 1
    root = isqrt(n)
    for d in range(2, root + 1):
        if n % d == 0:
            total += d
            q = n // d
            if q != d:
                total += q
    return total


def aliquot_sequence(n: int, max_len: int = 20):
    seq = [n]
    seen = {n}
    x = n

    for _ in range(max_len):
        x = sum_proper_divisors(x)
        seq.append(x)
        if x == 0:
            return {"start": n, "sequence": seq, "status": "hit_zero"}
        if x == 1:
            return {"start": n, "sequence": seq, "status": "hit_one"}
        if x in seen:
            return {"start": n, "sequence": seq, "status": "cycle"}
        seen.add(x)

    return {"start": n, "sequence": seq, "status": "truncated"}


def run_amicable_scan(limit_n=20000):
    amicable_pairs = []
    spd_cache = {}

    print("\n" + "=" * 72)
    print(f"Amicable scan started: limit = {limit_n}")
    print("=" * 72)

    def spd(x):
        if x not in spd_cache:
            spd_cache[x] = sum_proper_divisors(x)
        return spd_cache[x]

    for a in range(2, limit_n + 1):
        b = spd(a)
        if b > a and b <= limit_n and spd(b) == a and a != b:
            amicable_pairs.append((a, b))

    print("Amicable pairs found:", amicable_pairs[:30])
    print("Total pairs:", len(amicable_pairs))
    return amicable_pairs


def run_aliquot_scan(start_n=2, end_n=500):
    rows = []
    print("\n" + "=" * 72)
    print(f"Aliquot scan started: range = [{start_n}, {end_n}]")
    print("=" * 72)

    for n in range(start_n, end_n + 1):
        res = aliquot_sequence(n, max_len=20)
        rows.append({
            "start": n,
            "status": res["status"],
            "sequence_len": len(res["sequence"]),
            "last_value": res["sequence"][-1],
            "sequence": res["sequence"],
        })

    cycle_count = sum(1 for r in rows if r["status"] == "cycle")
    truncated_count = sum(1 for r in rows if r["status"] == "truncated")
    print("cycle_count:", cycle_count)
    print("truncated_count:", truncated_count)
    return rows


# ============================================================
# 10) Plot helpers
# ============================================================
def plot_shor_summary(summary: dict, filename: str, metric: str):
    Ns = sorted(summary.keys())
    ideal = [summary[N]["ideal"][metric] for N in Ns]
    noisy = [summary[N]["noisy"][metric] for N in Ns]
    sharp = [summary[N]["sharpened"][metric] for N in Ns]

    x = np.arange(len(Ns))
    w = 0.25

    plt.figure(figsize=(10, 5))
    plt.bar(x - w, ideal, width=w, label="ideal")
    plt.bar(x, noisy, width=w, label="noisy")
    plt.bar(x + w, sharp, width=w, label="sharpened")
    plt.xticks(x, Ns)
    plt.ylim(0, 1.05)
    plt.xlabel("N")
    plt.ylabel(metric)
    plt.title(f"Big Shor panel: {metric}")
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_lychrel_hist(rows, filename):
    vals = [r["iterations_to_palindrome"] for r in rows if r["iterations_to_palindrome"] is not None]
    plt.figure(figsize=(8, 4))
    plt.hist(vals, bins=40)
    plt.xlabel("Iterations to palindrome")
    plt.ylabel("Count")
    plt.title("Lychrel iterations histogram")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


def plot_collatz_steps(rows, filename):
    xs = [r["n"] for r in rows]
    ys = [r["steps_to_1"] for r in rows]
    plt.figure(figsize=(10, 4))
    plt.plot(xs, ys)
    plt.xlabel("n")
    plt.ylabel("steps_to_1")
    plt.title("Collatz steps")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 11) Run everything
# ============================================================
big_shor_rows, big_shor_summary = run_big_shor_panel(
    N_list=[143, 187, 209, 221, 247, 299],
    t_map={
        143: 13,
        187: 13,
        209: 13,
        221: 13,
        247: 13,
        299: 13,
    },
    sigma_bins=2.0,
    lam=0.6,
    gamma=1.2,
    shots=150,
    max_a_per_N=8,
    seed=123,
)

ly_rows, ly_candidates = run_lychrel_scan(
    start_n=1,
    end_n=5000,
    max_iter=80,
)

collatz_rows, collatz_best_steps, collatz_best_peak = run_collatz_scan(
    start_n=1,
    end_n=10000,
)

amicable_pairs = run_amicable_scan(limit_n=20000)
aliquot_rows = run_aliquot_scan(start_n=2, end_n=500)

# ============================================================
# 12) Save
# ============================================================
files_to_report = []

# Shor
shor_csv = "big_shor_panel.csv"
with open(shor_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(big_shor_rows[0].keys()))
    writer.writeheader()
    writer.writerows(big_shor_rows)
files_to_report.append(shor_csv)

shor_json = "big_shor_panel_summary.json"
with open(shor_json, "w", encoding="utf-8") as f:
    json.dump(big_shor_summary, f, indent=2, ensure_ascii=False)
files_to_report.append(shor_json)

# Lychrel
ly_csv = "lychrel_scan_1_5000.csv"
with open(ly_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(ly_rows[0].keys()))
    writer.writeheader()
    writer.writerows(ly_rows)
files_to_report.append(ly_csv)

ly_json = "lychrel_candidates_1_5000.json"
with open(ly_json, "w", encoding="utf-8") as f:
    json.dump(ly_candidates[:500], f, indent=2, ensure_ascii=False)
files_to_report.append(ly_json)

# Collatz
collatz_csv = "collatz_scan_1_10000.csv"
with open(collatz_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(collatz_rows[0].keys()))
    writer.writeheader()
    writer.writerows(collatz_rows)
files_to_report.append(collatz_csv)

collatz_json = "collatz_summary.json"
with open(collatz_json, "w", encoding="utf-8") as f:
    json.dump({
        "best_steps": collatz_best_steps,
        "best_peak": collatz_best_peak,
    }, f, indent=2, ensure_ascii=False)
files_to_report.append(collatz_json)

# Amicable
amicable_json = "amicable_pairs_up_to_20000.json"
with open(amicable_json, "w", encoding="utf-8") as f:
    json.dump(amicable_pairs, f, indent=2, ensure_ascii=False)
files_to_report.append(amicable_json)

# Aliquot
aliquot_json = "aliquot_scan_2_500.json"
with open(aliquot_json, "w", encoding="utf-8") as f:
    json.dump(aliquot_rows[:500], f, indent=2, ensure_ascii=False)
files_to_report.append(aliquot_json)

# Plots
plot1 = "big_shor_factor_summary.png"
plot_shor_summary(big_shor_summary, plot1, "mean_factor_success_rate")
files_to_report.append(plot1)

plot2 = "big_shor_period_summary.png"
plot_shor_summary(big_shor_summary, plot2, "mean_period_recovery_rate")
files_to_report.append(plot2)

plot3 = "lychrel_hist_1_5000.png"
plot_lychrel_hist(ly_rows, plot3)
files_to_report.append(plot3)

plot4 = "collatz_steps_1_10000.png"
plot_collatz_steps(collatz_rows, plot4)
files_to_report.append(plot4)

# ============================================================
# 13) Console summary
# ============================================================
print("\nSummary by N:")
for N, s in big_shor_summary.items():
    print(f"\n[N={N}]")
    print(s)

print("\nLychrel summary:")
print({
    "total_scanned": len(ly_rows),
    "candidate_count": len(ly_candidates),
    "first_20_candidates": [c["start"] for c in ly_candidates[:20]],
})

print("\nCollatz summary:")
print({
    "total_scanned": len(collatz_rows),
    "best_steps": collatz_best_steps,
    "best_peak": collatz_best_peak,
})

print("\nAmicable summary:")
print({
    "pair_count": len(amicable_pairs),
    "first_20_pairs": amicable_pairs[:20],
})

print("\nAliquot summary:")
cycle_count = sum(1 for r in aliquot_rows if r["status"] == "cycle")
trunc_count = sum(1 for r in aliquot_rows if r["status"] == "truncated")
print({
    "total_scanned": len(aliquot_rows),
    "cycle_count": cycle_count,
    "truncated_count": trunc_count,
})

print("\nSaved:")
for fp in files_to_report:
    print(" -", fp)


# =========================
# Part II.8 Notebook cell 21
# =========================


# ============================================================
# QCS-LR hash benchmark
# - batch hash scan
# - avalanche test
# - toy prefix-zero search
# ============================================================

import os
import csv
import json
import time
import math
import hashlib
import random
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# 1) helpers
# ============================================================
def sha256_bytes(x: bytes) -> bytes:
    return hashlib.sha256(x).digest()

def sha3_256_bytes(x: bytes) -> bytes:
    return hashlib.sha3_256(x).digest()

def blake2s_bytes(x: bytes) -> bytes:
    return hashlib.blake2s(x).digest()

HASH_FNS = {
    "sha256": sha256_bytes,
    "sha3_256": sha3_256_bytes,
    "blake2s": blake2s_bytes,
}

def bytes_to_bits(b: bytes) -> str:
    return ''.join(f'{x:08b}' for x in b)

def hamming_bytes(a: bytes, b: bytes) -> int:
    return sum((x ^ y).bit_count() for x, y in zip(a, b))

def flip_one_bit(msg: bytes, bit_index: int) -> bytes:
    arr = bytearray(msg)
    byte_idx = bit_index // 8
    inner = bit_index % 8
    arr[byte_idx] ^= (1 << inner)
    return bytes(arr)

def leading_zero_bits(digest: bytes) -> int:
    cnt = 0
    for x in digest:
        if x == 0:
            cnt += 8
        else:
            cnt += 8 - x.bit_length()
            break
    return cnt


# ============================================================
# 2) batch scan
# ============================================================
def run_batch_hash_scan(num_msgs=2000, msg_len=32, seed=123):
    rng = random.Random(seed)
    rows = []

    print("=" * 72)
    print("Batch hash scan started")
    print(f"num_msgs={num_msgs}, msg_len={msg_len}")
    print("=" * 72)

    messages = [bytes(rng.getrandbits(8) for _ in range(msg_len)) for _ in range(num_msgs)]

    for hash_name, fn in HASH_FNS.items():
        t0 = time.perf_counter()
        leading_zeros = []
        first_byte_counts = np.zeros(256, dtype=int)

        for m in messages:
            d = fn(m)
            lz = leading_zero_bits(d)
            leading_zeros.append(lz)
            first_byte_counts[d[0]] += 1

        elapsed = time.perf_counter() - t0
        throughput = num_msgs / elapsed

        row = {
            "hash_name": hash_name,
            "num_msgs": num_msgs,
            "msg_len": msg_len,
            "elapsed_sec": elapsed,
            "throughput_hash_per_sec": throughput,
            "mean_leading_zero_bits": float(np.mean(leading_zeros)),
            "max_leading_zero_bits": int(np.max(leading_zeros)),
            "std_first_byte_count": float(np.std(first_byte_counts)),
        }
        rows.append(row)
        print(row)

    return rows


# ============================================================
# 3) avalanche test
# ============================================================
def run_avalanche_test(num_msgs=400, msg_len=32, flips_per_msg=8, seed=123):
    rng = random.Random(seed)
    rows = []
    detail_rows = []

    print("\n" + "=" * 72)
    print("Avalanche test started")
    print(f"num_msgs={num_msgs}, msg_len={msg_len}, flips_per_msg={flips_per_msg}")
    print("=" * 72)

    total_bits = msg_len * 8
    messages = [bytes(rng.getrandbits(8) for _ in range(msg_len)) for _ in range(num_msgs)]

    for hash_name, fn in HASH_FNS.items():
        distances = []

        for m in messages:
            base = fn(m)
            flip_positions = rng.sample(range(total_bits), k=min(flips_per_msg, total_bits))
            for pos in flip_positions:
                m2 = flip_one_bit(m, pos)
                d2 = fn(m2)
                hd = hamming_bytes(base, d2)
                distances.append(hd)
                detail_rows.append({
                    "hash_name": hash_name,
                    "bit_pos": pos,
                    "hamming_distance": hd,
                })

        row = {
            "hash_name": hash_name,
            "samples": len(distances),
            "mean_hamming_distance": float(np.mean(distances)),
            "std_hamming_distance": float(np.std(distances)),
            "min_hamming_distance": int(np.min(distances)),
            "max_hamming_distance": int(np.max(distances)),
            "normalized_mean": float(np.mean(distances) / 256.0),
        }
        rows.append(row)
        print(row)

    return rows, detail_rows


# ============================================================
# 4) toy prefix search
# ============================================================
def find_prefix_zero_sample(hash_fn, zero_bits_target: int, max_tries=2_000_000, seed=123):
    rng = random.Random(seed)
    t0 = time.perf_counter()

    for i in range(1, max_tries + 1):
        # safe toy nonce search on random 16-byte payload
        nonce = rng.getrandbits(64)
        payload = nonce.to_bytes(8, "big") + i.to_bytes(8, "big")
        d = hash_fn(payload)
        lz = leading_zero_bits(d)
        if lz >= zero_bits_target:
            elapsed = time.perf_counter() - t0
            return {
                "found": True,
                "tries": i,
                "elapsed_sec": elapsed,
                "nonce_hex": payload.hex(),
                "digest_hex": d.hex(),
                "leading_zero_bits": lz,
            }

    elapsed = time.perf_counter() - t0
    return {
        "found": False,
        "tries": max_tries,
        "elapsed_sec": elapsed,
        "nonce_hex": None,
        "digest_hex": None,
        "leading_zero_bits": None,
    }


def run_prefix_search_panel(targets=(16, 20, 24), max_tries=2_000_000, seed=123):
    rows = []

    print("\n" + "=" * 72)
    print("Toy prefix-zero search started")
    print(f"targets={targets}, max_tries={max_tries}")
    print("=" * 72)

    for hash_name, fn in HASH_FNS.items():
        for tbits in targets:
            res = find_prefix_zero_sample(
                fn,
                zero_bits_target=tbits,
                max_tries=max_tries,
                seed=seed + hash(hash_name) % 1000 + tbits
            )
            row = {
                "hash_name": hash_name,
                "target_zero_bits": tbits,
                **res
            }
            rows.append(row)
            print(row)

    return rows


# ============================================================
# 5) plots
# ============================================================
def plot_batch_throughput(rows, filename):
    names = [r["hash_name"] for r in rows]
    vals = [r["throughput_hash_per_sec"] for r in rows]

    plt.figure(figsize=(7, 4))
    plt.bar(names, vals)
    plt.ylabel("hashes / sec")
    plt.title("Batch hash throughput")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()

def plot_avalanche(rows, filename):
    names = [r["hash_name"] for r in rows]
    vals = [r["mean_hamming_distance"] for r in rows]

    plt.figure(figsize=(7, 4))
    plt.bar(names, vals)
    plt.axhline(128, linestyle="--")
    plt.ylabel("mean output bit flips")
    plt.title("Avalanche mean hamming distance")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()

def plot_prefix_search(rows, filename):
    labels = [f'{r["hash_name"]}\n{r["target_zero_bits"]}b' for r in rows]
    vals = [r["tries"] for r in rows]

    plt.figure(figsize=(10, 4))
    plt.bar(labels, vals)
    plt.ylabel("tries")
    plt.title("Toy prefix-zero search effort")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 6) run all
# ============================================================
batch_rows = run_batch_hash_scan(num_msgs=3000, msg_len=32, seed=123)
avalanche_rows, avalanche_detail_rows = run_avalanche_test(num_msgs=500, msg_len=32, flips_per_msg=8, seed=123)
prefix_rows = run_prefix_search_panel(targets=(16, 20, 24), max_tries=2_000_000, seed=123)

# save csv/json
with open("hash_batch_scan.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(batch_rows[0].keys()))
    writer.writeheader()
    writer.writerows(batch_rows)

with open("hash_avalanche_summary.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(avalanche_rows[0].keys()))
    writer.writeheader()
    writer.writerows(avalanche_rows)

with open("hash_avalanche_detail.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(avalanche_detail_rows[0].keys()))
    writer.writeheader()
    writer.writerows(avalanche_detail_rows)

with open("hash_prefix_search.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(prefix_rows[0].keys()))
    writer.writeheader()
    writer.writerows(prefix_rows)

with open("hash_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "batch_scan": batch_rows,
        "avalanche": avalanche_rows,
        "prefix_search": prefix_rows,
    }, f, indent=2, ensure_ascii=False)

# plots
plot_batch_throughput(batch_rows, "hash_batch_throughput.png")
plot_avalanche(avalanche_rows, "hash_avalanche.png")
plot_prefix_search(prefix_rows, "hash_prefix_search.png")

print("\nSaved:")
print(" - hash_batch_scan.csv")
print(" - hash_avalanche_summary.csv")
print(" - hash_avalanche_detail.csv")
print(" - hash_prefix_search.csv")
print(" - hash_summary.json")
print(" - hash_batch_throughput.png")
print(" - hash_avalanche.png")
print(" - hash_prefix_search.png")


# =========================
# Part II.9 Notebook cell 22
# =========================


# ============================================================
# HMPL full panel
# seed text = "apple123"
# A) single-string hash mapping
# B) Merkle tree
# C) rolling hash
# D) Bloom filter
# E) toy PoW difficulty curve
# ============================================================

import csv
import json
import math
import time
import hashlib
import random
import numpy as np
import matplotlib.pyplot as plt


SEED_TEXT = "apple123"
SEED_BYTES = SEED_TEXT.encode("utf-8")


# ============================================================
# 1) Hash helpers
# ============================================================
def sha256_bytes(x: bytes) -> bytes:
    return hashlib.sha256(x).digest()

def sha3_256_bytes(x: bytes) -> bytes:
    return hashlib.sha3_256(x).digest()

def blake2s_bytes(x: bytes) -> bytes:
    return hashlib.blake2s(x).digest()

HASH_FNS = {
    "sha256": sha256_bytes,
    "sha3_256": sha3_256_bytes,
    "blake2s": blake2s_bytes,
}

def hamming_bytes(a: bytes, b: bytes) -> int:
    return sum((x ^ y).bit_count() for x, y in zip(a, b))

def leading_zero_bits(digest: bytes) -> int:
    cnt = 0
    for x in digest:
        if x == 0:
            cnt += 8
        else:
            cnt += 8 - x.bit_length()
            break
    return cnt


# ============================================================
# 2) A) Single-string hash mapping
# ============================================================
def run_single_hash_mapping(seed_text: str):
    rows = []
    b = seed_text.encode("utf-8")

    print("=" * 72)
    print("A) Single-string hash mapping started")
    print(f"seed_text = {seed_text!r}")
    print("=" * 72)

    for name, fn in HASH_FNS.items():
        d = fn(b)
        row = {
            "hash_name": name,
            "input_text": seed_text,
            "input_len": len(b),
            "digest_hex": d.hex(),
            "leading_zero_bits": leading_zero_bits(d),
        }
        rows.append(row)
        print(row)

    return rows


# ============================================================
# 3) B) Merkle tree
# ============================================================
def hash_leaf(data: bytes, fn):
    return fn(b"\x00" + data)

def hash_node(left: bytes, right: bytes, fn):
    return fn(b"\x01" + left + right)

def build_merkle_tree(leaves: list[bytes], fn):
    if len(leaves) == 0:
        raise ValueError("leaves must be non-empty")

    level = [hash_leaf(x, fn) for x in leaves]
    tree_levels = [level]

    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hash_node(left, right, fn))
        level = nxt
        tree_levels.append(level)

    root = tree_levels[-1][0]
    return root, tree_levels

def merkle_proof(tree_levels, leaf_index: int):
    proof = []
    idx = leaf_index
    for level in tree_levels[:-1]:
        sib = idx ^ 1
        if sib < len(level):
            sibling_hash = level[sib]
        else:
            sibling_hash = level[idx]
        is_left = (sib < idx)
        proof.append((sibling_hash, is_left))
        idx //= 2
    return proof

def verify_merkle_proof(leaf_data: bytes, proof, root: bytes, fn):
    cur = hash_leaf(leaf_data, fn)
    for sib_hash, sib_is_left in proof:
        if sib_is_left:
            cur = hash_node(sib_hash, cur, fn)
        else:
            cur = hash_node(cur, sib_hash, fn)
    return cur == root

def run_merkle_panel(seed_text: str, leaf_count: int = 16):
    rows = []
    summary = []

    print("\n" + "=" * 72)
    print("B) Merkle tree panel started")
    print(f"seed_text = {seed_text!r}, leaf_count = {leaf_count}")
    print("=" * 72)

    leaves = [f"{seed_text}|leaf|{i}".encode("utf-8") for i in range(leaf_count)]
    mutated_leaves = leaves.copy()
    mutated_leaves[3] = f"{seed_text}|leaf|3|mut".encode("utf-8")

    for name, fn in HASH_FNS.items():
        root1, levels1 = build_merkle_tree(leaves, fn)
        root2, _ = build_merkle_tree(mutated_leaves, fn)

        hd = hamming_bytes(root1, root2)
        proof = merkle_proof(levels1, leaf_index=3)
        ok = verify_merkle_proof(leaves[3], proof, root1, fn)

        row = {
            "hash_name": name,
            "leaf_count": leaf_count,
            "root_hex": root1.hex(),
            "mutated_root_hex": root2.hex(),
            "root_hamming_distance": hd,
            "proof_len": len(proof),
            "proof_verify_ok": ok,
        }
        summary.append(row)
        print(row)

        for i, (sib, is_left) in enumerate(proof):
            rows.append({
                "hash_name": name,
                "proof_step": i,
                "sibling_is_left": is_left,
                "sibling_hash_hex": sib.hex(),
            })

    return summary, rows


# ============================================================
# 4) C) Rolling hash
# ============================================================
class RollingHash:
    def __init__(self, base=257, mod=(1 << 61) - 1):
        self.base = base
        self.mod = mod

    def build(self, s: bytes):
        n = len(s)
        pows = [1] * (n + 1)
        pref = [0] * (n + 1)
        for i in range(n):
            pows[i + 1] = (pows[i] * self.base) % self.mod
            pref[i + 1] = (pref[i] * self.base + s[i] + 1) % self.mod
        return pref, pows

    def slice_hash(self, pref, pows, l, r):
        return (pref[r] - pref[l] * pows[r - l]) % self.mod

def run_rolling_hash_panel(seed_text: str, repeat_times: int = 128, window: int = 16):
    print("\n" + "=" * 72)
    print("C) Rolling hash panel started")
    print(f"seed_text = {seed_text!r}, repeat_times = {repeat_times}, window = {window}")
    print("=" * 72)

    data = (seed_text * repeat_times).encode("utf-8")
    rh = RollingHash()
    pref, pows = rh.build(data)

    rows = []
    uniq = set()
    t0 = time.perf_counter()

    for i in range(0, len(data) - window + 1):
        h = rh.slice_hash(pref, pows, i, i + window)
        uniq.add(h)
        if i < 32:
            rows.append({
                "window_start": i,
                "window_text": data[i:i+window].decode("utf-8", errors="ignore"),
                "rolling_hash": int(h),
            })

    elapsed = time.perf_counter() - t0

    summary = {
        "total_windows": len(data) - window + 1,
        "unique_hashes": len(uniq),
        "collision_count_est": (len(data) - window + 1) - len(uniq),
        "elapsed_sec": elapsed,
    }
    print(summary)

    return summary, rows


# ============================================================
# 5) D) Bloom filter
# ============================================================
class BloomFilter:
    def __init__(self, m_bits: int, k_hashes: int):
        self.m_bits = m_bits
        self.k_hashes = k_hashes
        self.bits = np.zeros(m_bits, dtype=np.uint8)

    def _hashes(self, item: bytes):
        h1 = int.from_bytes(hashlib.sha256(b"A" + item).digest()[:8], "big")
        h2 = int.from_bytes(hashlib.sha256(b"B" + item).digest()[:8], "big")
        for i in range(self.k_hashes):
            yield (h1 + i * h2) % self.m_bits

    def add(self, item: bytes):
        for idx in self._hashes(item):
            self.bits[idx] = 1

    def contains(self, item: bytes):
        return all(self.bits[idx] for idx in self._hashes(item))

def run_bloom_panel(seed_text: str, n_insert=2000, n_query=5000, m_bits=30000, k_hashes=5):
    print("\n" + "=" * 72)
    print("D) Bloom filter panel started")
    print(f"seed_text={seed_text!r}, n_insert={n_insert}, n_query={n_query}, m_bits={m_bits}, k_hashes={k_hashes}")
    print("=" * 72)

    bf = BloomFilter(m_bits=m_bits, k_hashes=k_hashes)

    inserted = [f"{seed_text}|item|{i}".encode("utf-8") for i in range(n_insert)]
    queries_nonmember = [f"{seed_text}|query|{i}".encode("utf-8") for i in range(n_query)]

    t0 = time.perf_counter()
    for x in inserted:
        bf.add(x)
    insert_time = time.perf_counter() - t0

    true_positive = 0
    for x in inserted[: min(500, n_insert)]:
        if bf.contains(x):
            true_positive += 1

    false_positive = 0
    t1 = time.perf_counter()
    for x in queries_nonmember:
        if bf.contains(x):
            false_positive += 1
    query_time = time.perf_counter() - t1

    summary = {
        "n_insert": n_insert,
        "n_query": n_query,
        "m_bits": m_bits,
        "k_hashes": k_hashes,
        "bit_density": float(bf.bits.mean()),
        "tp_rate_on_known_items": true_positive / min(500, n_insert),
        "false_positive_rate": false_positive / n_query,
        "insert_time_sec": insert_time,
        "query_time_sec": query_time,
    }
    print(summary)

    return summary


# ============================================================
# 6) E) Toy PoW difficulty curve
# ============================================================
def find_prefix_zero_sample(hash_fn, prefix: bytes, zero_bits_target: int, max_tries=2_000_000, seed=123):
    rng = random.Random(seed)
    t0 = time.perf_counter()

    for i in range(1, max_tries + 1):
        nonce = rng.getrandbits(64)
        payload = prefix + nonce.to_bytes(8, "big") + i.to_bytes(8, "big")
        d = hash_fn(payload)
        lz = leading_zero_bits(d)
        if lz >= zero_bits_target:
            elapsed = time.perf_counter() - t0
            return {
                "found": True,
                "tries": i,
                "elapsed_sec": elapsed,
                "payload_hex": payload.hex(),
                "digest_hex": d.hex(),
                "leading_zero_bits": lz,
            }

    elapsed = time.perf_counter() - t0
    return {
        "found": False,
        "tries": max_tries,
        "elapsed_sec": elapsed,
        "payload_hex": None,
        "digest_hex": None,
        "leading_zero_bits": None,
    }

def run_pow_panel(seed_text: str, targets=(16, 20, 24, 28), max_tries=2_000_000):
    rows = []

    print("\n" + "=" * 72)
    print("E) Toy PoW difficulty curve started")
    print(f"seed_text = {seed_text!r}, targets = {targets}, max_tries = {max_tries}")
    print("=" * 72)

    prefix = seed_text.encode("utf-8") + b"|pow|"

    for name, fn in HASH_FNS.items():
        for tbits in targets:
            row = {
                "hash_name": name,
                "target_zero_bits": tbits,
                **find_prefix_zero_sample(
                    fn,
                    prefix=prefix,
                    zero_bits_target=tbits,
                    max_tries=max_tries,
                    seed=123 + hash(name) % 1000 + tbits
                )
            }
            rows.append(row)
            print(row)

    return rows


# ============================================================
# 7) Plot helpers
# ============================================================
def plot_merkle_hamming(summary_rows, filename):
    names = [r["hash_name"] for r in summary_rows]
    vals = [r["root_hamming_distance"] for r in summary_rows]

    plt.figure(figsize=(7, 4))
    plt.bar(names, vals)
    plt.ylabel("root hamming distance")
    plt.title("Merkle root mutation sensitivity")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()

def plot_pow_curve(rows, filename):
    labels = [f'{r["hash_name"]}\n{r["target_zero_bits"]}b' for r in rows]
    vals = [r["tries"] for r in rows]

    plt.figure(figsize=(11, 4))
    plt.bar(labels, vals)
    plt.ylabel("tries")
    plt.title("Toy PoW difficulty curve")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=160)
    plt.close()


# ============================================================
# 8) Run all
# ============================================================
hash_rows = run_single_hash_mapping(SEED_TEXT)
merkle_summary, merkle_proof_rows = run_merkle_panel(SEED_TEXT, leaf_count=16)
rolling_summary, rolling_rows = run_rolling_hash_panel(SEED_TEXT, repeat_times=128, window=16)
bloom_summary = run_bloom_panel(SEED_TEXT, n_insert=2000, n_query=5000, m_bits=30000, k_hashes=5)
pow_rows = run_pow_panel(SEED_TEXT, targets=(16, 20, 24, 28), max_tries=2_000_000)

# ============================================================
# 9) Save
# ============================================================
with open("hmpl_hash_mapping.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(hash_rows[0].keys()))
    writer.writeheader()
    writer.writerows(hash_rows)

with open("hmpl_merkle_summary.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(merkle_summary[0].keys()))
    writer.writeheader()
    writer.writerows(merkle_summary)

with open("hmpl_merkle_proof_rows.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(merkle_proof_rows[0].keys()))
    writer.writeheader()
    writer.writerows(merkle_proof_rows)

with open("hmpl_rolling_rows.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rolling_rows[0].keys()))
    writer.writeheader()
    writer.writerows(rolling_rows)

with open("hmpl_pow_rows.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(pow_rows[0].keys()))
    writer.writeheader()
    writer.writerows(pow_rows)

with open("hmpl_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "seed_text": SEED_TEXT,
        "hash_mapping": hash_rows,
        "merkle_summary": merkle_summary,
        "rolling_summary": rolling_summary,
        "bloom_summary": bloom_summary,
        "pow_rows": pow_rows,
    }, f, indent=2, ensure_ascii=False)

plot_merkle_hamming(merkle_summary, "hmpl_merkle_hamming.png")
plot_pow_curve(pow_rows, "hmpl_pow_curve.png")

print("\nSaved:")
print(" - hmpl_hash_mapping.csv")
print(" - hmpl_merkle_summary.csv")
print(" - hmpl_merkle_proof_rows.csv")
print(" - hmpl_rolling_rows.csv")
print(" - hmpl_pow_rows.csv")
print(" - hmpl_summary.json")
print(" - hmpl_merkle_hamming.png")
print(" - hmpl_pow_curve.png")


# =========================
# Part II.10 Notebook cell 23
# =========================


# ============================================================
# qcs_hm_safe_reverse_hash_chip.py
# 安全版：通过 QCS-HM 虚拟量子芯片执行 reverse-hash / HMPL 扫描
# 仅用于 toy hash / 极小白名单 / 合成数据研究
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable, Iterable
import hashlib
import itertools
import json
import string
import time
import csv


# ============================================================
# Core IR
# ============================================================

@dataclass
class QIROp:
    name: str
    qubits: List[int]
    params: List[float] = field(default_factory=list)
    clbits: List[int] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QIRProgram:
    n_qubits: int
    n_clbits: int
    ops: List[QIROp]
    observables: List[Dict[str, Any]] = field(default_factory=list)
    shots: int = 1024
    mode: str = "ideal"          # ideal / noisy / sharpened
    task: str = "hmpl"           # here we route everything through HMPL
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QCSResult:
    counts: Optional[Dict[str, int]] = None
    probabilities: Optional[Dict[str, float]] = None
    expectations: Optional[List[float]] = None
    state_meta: Dict[str, Any] = field(default_factory=dict)
    chip_meta: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Hash helpers
# ============================================================

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha3_256_hex(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()

def blake2s_hex(data: bytes) -> str:
    return hashlib.blake2s(data).hexdigest()

HASH_FNS: dict[str, Callable[[bytes], str]] = {
    "sha256": sha256_hex,
    "sha3_256": sha3_256_hex,
    "blake2s": blake2s_hex,
}


def toy_hash16(data: bytes) -> str:
    """
    超弱 toy hash，只用于安全实验。
    """
    h = 0x1234
    for i, b in enumerate(data):
        h = (h ^ ((b + i) * 257)) & 0xFFFF
        h = ((h << 5) | (h >> 11)) & 0xFFFF
        h = (h * 109 + 97) & 0xFFFF
    return f"{h:04x}"


TOY_HASH_FNS: dict[str, Callable[[bytes], str]] = {
    "toy_hash16": lambda b: toy_hash16(b),
    **HASH_FNS,
}


# ============================================================
# Candidate generators
# ============================================================

def generate_whitelist_strings(alphabet: str, min_len: int, max_len: int) -> Iterable[str]:
    for n in range(min_len, max_len + 1):
        for tup in itertools.product(alphabet, repeat=n):
            yield "".join(tup)


def generate_numeric_strings(min_len: int, max_len: int) -> Iterable[str]:
    yield from generate_whitelist_strings(string.digits, min_len, max_len)


# ============================================================
# QCS-HM runtime
# ============================================================

class QCSHMChipRuntime:
    """
    这里的重点不是“破解哈希”，而是把 reverse-hash / prefix-zero
    研究任务包装成 HMPL 芯片任务来执行。
    """

    def __init__(self):
        self.supported_modes = {"ideal", "noisy", "sharpened"}
        self.supported_tasks = {"hmpl"}

    def execute(self, program: QIRProgram) -> QCSResult:
        if program.mode not in self.supported_modes:
            raise ValueError(f"Unsupported mode: {program.mode}")
        if program.task not in self.supported_tasks:
            raise ValueError(f"Unsupported task: {program.task}")

        module = program.meta.get("module")
        if module == "reverse_hash_scan":
            return self._execute_reverse_hash_scan(program)
        elif module == "prefix_zero_scan":
            return self._execute_prefix_zero_scan(program)
        elif module == "toy_collision_scan":
            return self._execute_toy_collision_scan(program)
        else:
            raise ValueError(f"Unsupported HMPL module: {module}")

    # --------------------------------------------------------
    # HMPL module 1: reverse hash in tiny safe space
    # --------------------------------------------------------
    def _execute_reverse_hash_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        hash_name = meta["hash_name"]
        target_hash = meta["target_hash"]
        candidates = meta["candidates"]

        hash_fn = TOY_HASH_FNS[hash_name]

        t0 = time.perf_counter()
        tries = 0
        recovered = None

        for s in candidates:
            tries += 1
            if hash_fn(s.encode("utf-8")) == target_hash:
                recovered = s
                break

        elapsed = time.perf_counter() - t0

        return QCSResult(
            state_meta={
                "module": "reverse_hash_scan",
                "hash_name": hash_name,
                "target_hash": target_hash,
                "found": recovered is not None,
                "recovered_input": recovered,
                "tries": tries,
                "elapsed_sec": elapsed,
                "candidate_space_desc": meta.get("candidate_space_desc", "unknown"),
            },
            chip_meta={
                "mode": program.mode,
                "task": program.task,
                "engine": "QCS-HM HMPL reverse-scan core",
            },
        )

    # --------------------------------------------------------
    # HMPL module 2: prefix-zero search
    # --------------------------------------------------------
    def _execute_prefix_zero_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        hash_name = meta["hash_name"]
        target_zero_hex_chars = int(meta["target_zero_hex_chars"])
        candidates = meta["candidates"]

        hash_fn = TOY_HASH_FNS[hash_name]
        prefix = "0" * target_zero_hex_chars

        t0 = time.perf_counter()
        tries = 0
        found_input = None
        found_digest = None

        for s in candidates:
            tries += 1
            d = hash_fn(s.encode("utf-8"))
            if d.startswith(prefix):
                found_input = s
                found_digest = d
                break

        elapsed = time.perf_counter() - t0

        return QCSResult(
            state_meta={
                "module": "prefix_zero_scan",
                "hash_name": hash_name,
                "target_zero_hex_chars": target_zero_hex_chars,
                "found": found_input is not None,
                "input_text": found_input,
                "digest_hex": found_digest,
                "tries": tries,
                "elapsed_sec": elapsed,
            },
            chip_meta={
                "mode": program.mode,
                "task": program.task,
                "engine": "QCS-HM HMPL prefix-scan core",
            },
        )

    # --------------------------------------------------------
    # HMPL module 3: toy collision scan
    # --------------------------------------------------------
    def _execute_toy_collision_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        candidates = meta["candidates"]

        seen: Dict[str, str] = {}
        rows: List[Dict[str, str]] = []

        t0 = time.perf_counter()
        for s in candidates:
            d = toy_hash16(s.encode("utf-8"))
            if d in seen and seen[d] != s:
                rows.append({
                    "digest_hex": d,
                    "first_input": seen[d],
                    "second_input": s,
                })
            else:
                seen[d] = s
        elapsed = time.perf_counter() - t0

        return QCSResult(
            state_meta={
                "module": "toy_collision_scan",
                "collision_count": len(rows),
                "first_10_collisions": rows[:10],
                "elapsed_sec": elapsed,
            },
            chip_meta={
                "mode": program.mode,
                "task": program.task,
                "engine": "QCS-HM HMPL collision core",
            },
        )


# ============================================================
# High-level chip task builders
# ============================================================

def build_reverse_hash_program(
    *,
    hash_name: str,
    target_hash: str,
    candidates: List[str],
    candidate_space_desc: str,
    mode: str = "ideal",
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8,
        n_clbits=8,
        ops=[],
        mode=mode,
        task="hmpl",
        meta={
            "module": "reverse_hash_scan",
            "hash_name": hash_name,
            "target_hash": target_hash,
            "candidates": candidates,
            "candidate_space_desc": candidate_space_desc,
        },
    )


def build_prefix_zero_program(
    *,
    hash_name: str,
    target_zero_hex_chars: int,
    candidates: List[str],
    mode: str = "ideal",
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8,
        n_clbits=8,
        ops=[],
        mode=mode,
        task="hmpl",
        meta={
            "module": "prefix_zero_scan",
            "hash_name": hash_name,
            "target_zero_hex_chars": target_zero_hex_chars,
            "candidates": candidates,
        },
    )


def build_toy_collision_program(
    *,
    candidates: List[str],
    mode: str = "ideal",
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8,
        n_clbits=8,
        ops=[],
        mode=mode,
        task="hmpl",
        meta={
            "module": "toy_collision_scan",
            "candidates": candidates,
        },
    )


# ============================================================
# Main safe lab
# ============================================================

def main():
    runtime = QCSHMChipRuntime()

    reverse_rows = []
    prefix_rows = []

    print("=" * 72)
    print("QCS-HM safe reverse-hash chip lab started")
    print("=" * 72)

    # --------------------------------------------------------
    # A) Toy reverse search through virtual quantum chip
    # --------------------------------------------------------
    print("\n--- A) Toy reverse search via virtual quantum chip ---")
    toy_secret = "A17"
    toy_target = toy_hash16(toy_secret.encode("utf-8"))
    toy_candidates = list(generate_whitelist_strings(
        alphabet=string.ascii_uppercase + string.digits,
        min_len=1,
        max_len=3,
    ))

    prog = build_reverse_hash_program(
        hash_name="toy_hash16",
        target_hash=toy_target,
        candidates=toy_candidates,
        candidate_space_desc="A-Z0-9, len=1..3",
        mode="ideal",
    )
    res = runtime.execute(prog)
    reverse_rows.append(res.state_meta)
    print(res.state_meta)

    # --------------------------------------------------------
    # B) Real hash, but only on tiny safe whitelist
    # --------------------------------------------------------
    print("\n--- B) Real hash reverse search via virtual quantum chip (safe tiny whitelist) ---")
    safe_whitelist = [
        "red", "blue", "green", "apple", "mango",
        "cat", "dog", "bird", "alpha", "omega"
    ]
    secret = "mango"

    for hash_name, fn in HASH_FNS.items():
        target = fn(secret.encode("utf-8"))
        prog = build_reverse_hash_program(
            hash_name=hash_name,
            target_hash=target,
            candidates=safe_whitelist,
            candidate_space_desc="fixed safe whitelist of 10 synthetic words",
            mode="ideal",
        )
        res = runtime.execute(prog)
        reverse_rows.append(res.state_meta)
        print(res.state_meta)

    # --------------------------------------------------------
    # C) Prefix-zero search through virtual quantum chip
    # --------------------------------------------------------
    print("\n--- C) Prefix-zero search via virtual quantum chip ---")
    numeric_candidates = list(generate_numeric_strings(1, 6))

    for hash_name in ["sha256", "sha3_256", "blake2s"]:
        for z in [2, 3]:
            prog = build_prefix_zero_program(
                hash_name=hash_name,
                target_zero_hex_chars=z,
                candidates=numeric_candidates,
                mode="sharpened",   # just to show this is routed through chip readout mode
            )
            res = runtime.execute(prog)
            prefix_rows.append(res.state_meta)
            print(res.state_meta)

    # --------------------------------------------------------
    # D) Toy collision scan through virtual quantum chip
    # --------------------------------------------------------
    print("\n--- D) Toy collision scan via virtual quantum chip ---")
    collision_candidates = list(generate_whitelist_strings(
        alphabet="abcd0123",
        min_len=1,
        max_len=4,
    ))
    prog = build_toy_collision_program(
        candidates=collision_candidates,
        mode="ideal",
    )
    res = runtime.execute(prog)
    collision_meta = res.state_meta
    print(collision_meta)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------
    with open("qcs_hm_safe_reverse_rows.csv", "w", newline="", encoding="utf-8") as f:
        if reverse_rows:
            writer = csv.DictWriter(f, fieldnames=list(reverse_rows[0].keys()))
            writer.writeheader()
            writer.writerows(reverse_rows)

    with open("qcs_hm_safe_prefix_rows.csv", "w", newline="", encoding="utf-8") as f:
        if prefix_rows:
            writer = csv.DictWriter(f, fieldnames=list(prefix_rows[0].keys()))
            writer.writeheader()
            writer.writerows(prefix_rows)

    with open("qcs_hm_safe_reverse_summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "reverse_rows": reverse_rows,
            "prefix_rows": prefix_rows,
            "collision_meta": collision_meta,
        }, f, indent=2, ensure_ascii=False)

    print("\nSaved:")
    print(" - qcs_hm_safe_reverse_rows.csv")
    print(" - qcs_hm_safe_prefix_rows.csv")
    print(" - qcs_hm_safe_reverse_summary.json")


if __name__ == "__main__":
    main()


# =========================
# Part II.11 Notebook cell 24
# =========================


# ============================================================
# qcs_hm_hmpl_trimode.py
# QCS-HM HMPL 三模态增强版
# 安全用途：toy hash / 极小白名单 / 合成数据
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Iterable
import hashlib
import itertools
import json
import string
import time
import csv
import random


# ============================================================
# Core IR
# ============================================================

@dataclass
class QIROp:
    name: str
    qubits: List[int]
    params: List[float] = field(default_factory=list)
    clbits: List[int] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QIRProgram:
    n_qubits: int
    n_clbits: int
    ops: List[QIROp]
    observables: List[Dict[str, Any]] = field(default_factory=list)
    shots: int = 1024
    mode: str = "ideal"          # ideal / noisy / sharpened
    task: str = "hmpl"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QCSResult:
    counts: Optional[Dict[str, int]] = None
    probabilities: Optional[Dict[str, float]] = None
    expectations: Optional[List[float]] = None
    state_meta: Dict[str, Any] = field(default_factory=dict)
    chip_meta: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Hash helpers
# ============================================================

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha3_256_hex(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()

def blake2s_hex(data: bytes) -> str:
    return hashlib.blake2s(data).hexdigest()

HASH_FNS: dict[str, Callable[[bytes], str]] = {
    "sha256": sha256_hex,
    "sha3_256": sha3_256_hex,
    "blake2s": blake2s_hex,
}


def toy_hash16(data: bytes) -> str:
    h = 0x1234
    for i, b in enumerate(data):
        h = (h ^ ((b + i) * 257)) & 0xFFFF
        h = ((h << 5) | (h >> 11)) & 0xFFFF
        h = (h * 109 + 97) & 0xFFFF
    return f"{h:04x}"


ALL_HASH_FNS: dict[str, Callable[[bytes], str]] = {
    "toy_hash16": lambda b: toy_hash16(b),
    **HASH_FNS,
}


# ============================================================
# Candidate generators
# ============================================================

def generate_whitelist_strings(alphabet: str, min_len: int, max_len: int) -> Iterable[str]:
    for n in range(min_len, max_len + 1):
        for tup in itertools.product(alphabet, repeat=n):
            yield "".join(tup)


def generate_numeric_strings(min_len: int, max_len: int) -> Iterable[str]:
    yield from generate_whitelist_strings(string.digits, min_len, max_len)


# ============================================================
# Runtime
# ============================================================

class QCSHMChipRuntime:
    def __init__(self, rng_seed: int = 430):
        self.supported_modes = {"ideal", "noisy", "sharpened"}
        self.supported_tasks = {"hmpl"}
        self.rng = random.Random(rng_seed)

    def execute(self, program: QIRProgram) -> QCSResult:
        if program.mode not in self.supported_modes:
            raise ValueError(f"Unsupported mode: {program.mode}")
        if program.task not in self.supported_tasks:
            raise ValueError(f"Unsupported task: {program.task}")

        module = program.meta.get("module")
        if module == "reverse_hash_scan":
            return self._execute_reverse_hash_scan(program)
        elif module == "prefix_zero_scan":
            return self._execute_prefix_zero_scan(program)
        elif module == "toy_collision_scan":
            return self._execute_toy_collision_scan(program)
        else:
            raise ValueError(f"Unsupported HMPL module: {module}")

    # --------------------------------------------------------
    # mode helpers
    # --------------------------------------------------------
    def _mode_reverse_accept(self, mode: str, is_true_hit: bool) -> bool:
        if mode == "ideal":
            return is_true_hit

        if mode == "noisy":
            if is_true_hit:
                return self.rng.random() < 0.72
            return False

        if mode == "sharpened":
            if is_true_hit:
                return self.rng.random() < 0.90
            return False

        return is_true_hit

    def _mode_prefix_accept(self, mode: str, true_zero_chars: int, target_zero_chars: int) -> bool:
        if mode == "ideal":
            return true_zero_chars >= target_zero_chars

        if mode == "noisy":
            # 更容易漏检，也有极低概率把边缘样本误判成命中
            if true_zero_chars >= target_zero_chars:
                return self.rng.random() < 0.65
            elif true_zero_chars == target_zero_chars - 1:
                return self.rng.random() < 0.03
            return False

        if mode == "sharpened":
            if true_zero_chars >= target_zero_chars:
                return self.rng.random() < 0.88
            elif true_zero_chars == target_zero_chars - 1:
                return self.rng.random() < 0.01
            return False

        return true_zero_chars >= target_zero_chars

    def _mode_collision_keep(self, mode: str) -> bool:
        if mode == "ideal":
            return True
        if mode == "noisy":
            return self.rng.random() < 0.62
        if mode == "sharpened":
            return self.rng.random() < 0.86
        return True

    # --------------------------------------------------------
    # utils
    # --------------------------------------------------------
    @staticmethod
    def _leading_zero_hex_chars(digest_hex: str) -> int:
        n = 0
        for ch in digest_hex:
            if ch == "0":
                n += 1
            else:
                break
        return n

    # --------------------------------------------------------
    # HMPL module 1: reverse hash scan
    # --------------------------------------------------------
    def _execute_reverse_hash_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        hash_name = meta["hash_name"]
        target_hash = meta["target_hash"]
        candidates = meta["candidates"]
        mode = program.mode

        hash_fn = ALL_HASH_FNS[hash_name]

        t0 = time.perf_counter()
        tries = 0
        recovered = None
        true_hit_index = None

        for idx, s in enumerate(candidates, start=1):
            tries += 1
            is_true_hit = (hash_fn(s.encode("utf-8")) == target_hash)

            if is_true_hit and true_hit_index is None:
                true_hit_index = idx

            if self._mode_reverse_accept(mode, is_true_hit):
                recovered = s
                break

        elapsed = time.perf_counter() - t0

        return QCSResult(
            state_meta={
                "module": "reverse_hash_scan",
                "mode": mode,
                "hash_name": hash_name,
                "target_hash": target_hash,
                "found": recovered is not None,
                "recovered_input": recovered,
                "tries": tries,
                "true_hit_index": true_hit_index,
                "elapsed_sec": elapsed,
                "candidate_space_desc": meta.get("candidate_space_desc", "unknown"),
            },
            chip_meta={
                "task": "hmpl",
                "engine": "QCS-HM HMPL reverse core",
                "mode": mode,
            },
        )

    # --------------------------------------------------------
    # HMPL module 2: prefix zero scan
    # --------------------------------------------------------
    def _execute_prefix_zero_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        hash_name = meta["hash_name"]
        target_zero_hex_chars = int(meta["target_zero_hex_chars"])
        candidates = meta["candidates"]
        mode = program.mode

        hash_fn = ALL_HASH_FNS[hash_name]

        t0 = time.perf_counter()
        tries = 0
        found_input = None
        found_digest = None
        found_true_zero_chars = None

        best_true_zero_chars = -1
        best_candidate = None
        best_digest = None

        for s in candidates:
            tries += 1
            d = hash_fn(s.encode("utf-8"))
            z = self._leading_zero_hex_chars(d)

            if z > best_true_zero_chars:
                best_true_zero_chars = z
                best_candidate = s
                best_digest = d

            if self._mode_prefix_accept(mode, z, target_zero_hex_chars):
                found_input = s
                found_digest = d
                found_true_zero_chars = z
                break

        elapsed = time.perf_counter() - t0

        return QCSResult(
            state_meta={
                "module": "prefix_zero_scan",
                "mode": mode,
                "hash_name": hash_name,
                "target_zero_hex_chars": target_zero_hex_chars,
                "found": found_input is not None,
                "input_text": found_input,
                "digest_hex": found_digest,
                "true_zero_hex_chars": found_true_zero_chars,
                "tries": tries,
                "best_true_zero_hex_chars_seen": best_true_zero_chars,
                "best_candidate_seen": best_candidate,
                "best_digest_seen": best_digest,
                "elapsed_sec": elapsed,
            },
            chip_meta={
                "task": "hmpl",
                "engine": "QCS-HM HMPL prefix core",
                "mode": mode,
            },
        )

    # --------------------------------------------------------
    # HMPL module 3: toy collision scan
    # --------------------------------------------------------
    def _execute_toy_collision_scan(self, program: QIRProgram) -> QCSResult:
        candidates = program.meta["candidates"]
        mode = program.mode

        seen: Dict[str, str] = {}
        all_collisions: List[Dict[str, str]] = []
        kept_collisions: List[Dict[str, str]] = []

        t0 = time.perf_counter()

        for s in candidates:
            d = toy_hash16(s.encode("utf-8"))
            if d in seen and seen[d] != s:
                row = {
                    "digest_hex": d,
                    "first_input": seen[d],
                    "second_input": s,
                }
                all_collisions.append(row)
                if self._mode_collision_keep(mode):
                    kept_collisions.append(row)
            else:
                seen[d] = s

        elapsed = time.perf_counter() - t0

        return QCSResult(
            state_meta={
                "module": "toy_collision_scan",
                "mode": mode,
                "true_collision_count": len(all_collisions),
                "reported_collision_count": len(kept_collisions),
                "first_10_reported_collisions": kept_collisions[:10],
                "elapsed_sec": elapsed,
            },
            chip_meta={
                "task": "hmpl",
                "engine": "QCS-HM HMPL collision core",
                "mode": mode,
            },
        )


# ============================================================
# Program builders
# ============================================================

def build_reverse_hash_program(
    *,
    hash_name: str,
    target_hash: str,
    candidates: List[str],
    candidate_space_desc: str,
    mode: str,
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8,
        n_clbits=8,
        ops=[],
        mode=mode,
        task="hmpl",
        meta={
            "module": "reverse_hash_scan",
            "hash_name": hash_name,
            "target_hash": target_hash,
            "candidates": candidates,
            "candidate_space_desc": candidate_space_desc,
        },
    )


def build_prefix_zero_program(
    *,
    hash_name: str,
    target_zero_hex_chars: int,
    candidates: List[str],
    mode: str,
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8,
        n_clbits=8,
        ops=[],
        mode=mode,
        task="hmpl",
        meta={
            "module": "prefix_zero_scan",
            "hash_name": hash_name,
            "target_zero_hex_chars": target_zero_hex_chars,
            "candidates": candidates,
        },
    )


def build_toy_collision_program(
    *,
    candidates: List[str],
    mode: str,
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8,
        n_clbits=8,
        ops=[],
        mode=mode,
        task="hmpl",
        meta={
            "module": "toy_collision_scan",
            "candidates": candidates,
        },
    )


# ============================================================
# Main experiment
# ============================================================

def main():
    runtime = QCSHMChipRuntime(rng_seed=430)

    reverse_rows = []
    prefix_rows = []
    collision_rows = []

    modes = ["ideal", "noisy", "sharpened"]

    print("=" * 72)
    print("QCS-HM HMPL tri-mode lab started")
    print("=" * 72)

    # --------------------------------------------------------
    # A) reverse scan
    # --------------------------------------------------------
    toy_secret = "A17"
    toy_target = toy_hash16(toy_secret.encode("utf-8"))
    toy_candidates = list(generate_whitelist_strings(
        alphabet=string.ascii_uppercase + string.digits,
        min_len=1,
        max_len=3,
    ))

    safe_whitelist = [
        "red", "blue", "green", "apple", "mango",
        "cat", "dog", "bird", "alpha", "omega"
    ]
    real_secret = "mango"

    print("\n--- A) reverse_hash_scan ---")
    for mode in modes:
        prog = build_reverse_hash_program(
            hash_name="toy_hash16",
            target_hash=toy_target,
            candidates=toy_candidates,
            candidate_space_desc="A-Z0-9, len=1..3",
            mode=mode,
        )
        res = runtime.execute(prog)
        reverse_rows.append(res.state_meta)
        print(res.state_meta)

    for hash_name, fn in HASH_FNS.items():
        target = fn(real_secret.encode("utf-8"))
        for mode in modes:
            prog = build_reverse_hash_program(
                hash_name=hash_name,
                target_hash=target,
                candidates=safe_whitelist,
                candidate_space_desc="fixed safe whitelist of 10 synthetic words",
                mode=mode,
            )
            res = runtime.execute(prog)
            reverse_rows.append(res.state_meta)
            print(res.state_meta)

    # --------------------------------------------------------
    # B) prefix scan
    # --------------------------------------------------------
    numeric_candidates = list(generate_numeric_strings(1, 6))

    print("\n--- B) prefix_zero_scan ---")
    for hash_name in ["sha256", "sha3_256", "blake2s"]:
        for z in [2, 3]:
            for mode in modes:
                prog = build_prefix_zero_program(
                    hash_name=hash_name,
                    target_zero_hex_chars=z,
                    candidates=numeric_candidates,
                    mode=mode,
                )
                res = runtime.execute(prog)
                prefix_rows.append(res.state_meta)
                print(res.state_meta)

    # --------------------------------------------------------
    # C) collision scan
    # --------------------------------------------------------
    collision_candidates = list(generate_whitelist_strings(
        alphabet="abcd0123",
        min_len=1,
        max_len=4,
    ))

    print("\n--- C) toy_collision_scan ---")
    for mode in modes:
        prog = build_toy_collision_program(
            candidates=collision_candidates,
            mode=mode,
        )
        res = runtime.execute(prog)
        collision_rows.append(res.state_meta)
        print(res.state_meta)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------
    with open("qcs_hm_hmpl_trimode_reverse.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(reverse_rows[0].keys()))
        writer.writeheader()
        writer.writerows(reverse_rows)

    with open("qcs_hm_hmpl_trimode_prefix.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(prefix_rows[0].keys()))
        writer.writeheader()
        writer.writerows(prefix_rows)

    with open("qcs_hm_hmpl_trimode_collision.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(collision_rows[0].keys()))
        writer.writeheader()
        writer.writerows(collision_rows)

    with open("qcs_hm_hmpl_trimode_summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "reverse_rows": reverse_rows,
            "prefix_rows": prefix_rows,
            "collision_rows": collision_rows,
        }, f, indent=2, ensure_ascii=False)

    print("\nSaved:")
    print(" - qcs_hm_hmpl_trimode_reverse.csv")
    print(" - qcs_hm_hmpl_trimode_prefix.csv")
    print(" - qcs_hm_hmpl_trimode_collision.csv")
    print(" - qcs_hm_hmpl_trimode_summary.json")


if __name__ == "__main__":
    main()