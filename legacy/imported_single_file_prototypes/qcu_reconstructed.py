# qcu_reconstructed.py
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
