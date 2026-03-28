# noise_infer.py
"""
QCU 噪声模型推导：从 QCircuit 自动生成 IQPUConfig 噪声参数。

推导优先级（高 → 低）
---------------------
1. 显式标注   circ.set_noise(T1=50., ...)         最高优先
2. 预设档位   circ.set_noise(preset="nisq")        覆盖默认值
3. 电路结构   双比特门数 → 等效退相干时间校正      仅在无注解时生效
4. 保守默认   T1=100, Tphi=200, kappa=0.01         兜底

预设档位
--------
"ideal"   理想封闭系统（T1=10⁶, kappa≈0）—— 用于算法正确性验证
"nisq"    当前 NISQ 典型值（T1=50μs, Tphi=100μs）
"noisy"   早期 NISQ / 有意加噪（T1=10μs, Tphi=20μs）
"default" 保守默认，不加任何电路结构校正

电路结构校正（无注解时自动应用）
---------------------------------
每个双比特门（色散耦合）引入额外退相干：
  T1_eff  = T1  / (1 + n_2q × 0.05)    下限 10μs
  Tphi_eff= Tphi/ (1 + n_2q × 0.025)   下限 20μs

这反映了真实硬件中双比特门引入的 leakage 和串扰。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ir.circuit import QCircuit

# ── 预设档位 ──────────────────────────────────────────────────
_PRESETS: dict[str, dict] = {
    "ideal":   {"T1": 1e6,  "Tphi": 1e6,  "kappa": 1e-5, "d": 6},
    "nisq":    {"T1": 50.,  "Tphi": 100., "kappa": 0.02,  "d": 6},
    "noisy":   {"T1": 10.,  "Tphi": 20.,  "kappa": 0.05,  "d": 6},
    "default": {"T1": 100., "Tphi": 200., "kappa": 0.01,  "d": 6},
}

# 双比特门退相干校正系数
_ALPHA_T1   = 0.05    # T1  每增加一个双比特门的相对退化
_ALPHA_TPHI = 0.025   # Tphi 同上（退相干比弛豫更慢衰减）
_T1_FLOOR   = 10.     # T1 下限（μs）
_TPHI_FLOOR = 20.     # Tphi 下限（μs）


def infer_noise_params(circ: "QCircuit") -> dict:
    """从 QCircuit 推导噪声参数字典。

    Returns
    -------
    dict
        包含 "T1", "Tphi", "kappa", "d" 的参数字典。
    """
    noise_ann: dict = circ.metadata.get("noise", {})

    # 步骤 1：加载默认值
    params = dict(_PRESETS["default"])

    # 步骤 2：应用预设档位（若指定）
    preset = noise_ann.get("preset")
    if preset is not None:
        if preset not in _PRESETS:
            raise ValueError(
                f"未知预设档位 {preset!r}，可选：{list(_PRESETS)}"
            )
        params.update(_PRESETS[preset])

    # 步骤 3：显式注解覆盖（优先级最高）
    for key in ("T1", "Tphi", "kappa", "d"):
        if key in noise_ann:
            params[key] = noise_ann[key]

    # 步骤 4：电路结构校正（仅在无任何 T1/Tphi 注解且无预设时生效）
    if "T1" not in noise_ann and "Tphi" not in noise_ann and preset is None:
        n_2q = circ.two_qubit_count
        if n_2q > 0:
            params["T1"]   = max(params["T1"]   / (1 + n_2q * _ALPHA_T1),   _T1_FLOOR)
            params["Tphi"] = max(params["Tphi"] / (1 + n_2q * _ALPHA_TPHI), _TPHI_FLOOR)

    return params


def infer_iqpu_config(circ: "QCircuit", Nq: int = 2,
                      device: str = "cpu") -> object:
    """从 QCircuit 推导完整的 IQPUConfig。

    Parameters
    ----------
    circ : QCircuit
        已标注（或未标注）噪声信息的电路
    Nq : int
        目标 qubit 数（segment 级传 2，emerge 级传真实 n_qubits）
    device : str
        "cpu" 或 "cuda"

    Returns
    -------
    IQPUConfig
    """
    import numpy as np
    from qcu.core.state_repr import IQPUConfig

    p  = infer_noise_params(circ)
    Nq = max(Nq, 2)
    d  = int(p["d"])

    return IQPUConfig(
        Nq=Nq, Nm=Nq, d=d,
        kappa=np.full(Nq, p["kappa"]),
        T1=np.full(Nq,    p["T1"]),
        Tphi=np.full(Nq,  p["Tphi"]),
        t_max=8.0, dt=0.05, obs_every=20,
        track_entanglement=False,
        device=device,
    )


def noise_summary(circ: "QCircuit") -> str:
    """返回噪声参数的可读摘要字符串（用于日志/调试）。"""
    p = infer_noise_params(circ)
    ann  = circ.metadata.get("noise", {})
    src  = "preset=" + ann["preset"] if "preset" in ann else \
           "annotated" if ann else "circuit-inferred"
    return (
        f"NoiseModel({src}): "
        f"T1={p['T1']:.1f}μs  Tphi={p['Tphi']:.1f}μs  "
        f"κ={p['kappa']:.4f}  d={p['d']}"
    )
