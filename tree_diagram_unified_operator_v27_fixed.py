
# Tree Diagram Unified Operator Core v26
# Final packaging pass:
# - unify final outputs into a single oracle manifest format
# - all modes return the same top-level shell:
#   meta / routing / domains / selection / oracle_summary
# - previous compression layers retained:
#   domain manifest -> primitive term specs -> primitive evaluator registry
#   -> rollout -> metric evaluator registry -> reward bundle

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple
import argparse, itertools, json, math
import numpy as np

DEFAULT_REQUEST = {
    "problem": {
        "title": "Urban Resonance Upgrade Program",
        "target": "Find the most viable route to upgrade a city-scale resonance system from Level-5-equivalent stability to Level-6-equivalent stability.",
    },
    "subject": {
        "output_power": 0.93, "control_precision": 0.88, "load_tolerance": 0.61,
        "aim_coupling": 0.97, "phase_proximity": 0.69, "stress_level": 0.22,
        "instability_sensitivity": 0.28,
    },
    "environment": {
        "budget": 0.62, "infrastructure": 0.71, "data_coverage": 0.66,
        "population_coupling": 0.83, "field_noise": 0.34, "social_pressure": 0.58,
        "regulatory_friction": 0.47, "network_density": 0.76, "phase_instability": 0.41,
        "weather_relevance": 0.70, "terrain_relevance": 0.62,
    },
    "reward": {
        "components": {
            "feasibility": 1.15, "stability": 1.00, "field_fit": 0.95, "risk": -1.10, "spread_penalty": -0.25,
            "weather_h_err": -0.80 / 1.0e4, "weather_t_err": -1.20, "weather_q_err": -280.0,
            "weather_w_err": -0.020, "weather_instability": -0.030,
        },
        "nutrient": {
            "feasibility_threshold_gain": 1.00, "stability_threshold_gain": 0.88,
            "field_fit_threshold_gain": 0.84, "risk_penalty": -0.74, "oversize_penalty": -0.05,
        }
    },
    "runtime": {
        "plan_grid_shape": [8, 8], "weather_grid_shape": [112, 84],
        "weather_steps": 180, "weather_dt": 45.0, "grid_engine": "numpy_local"
    }
}

BASE_H = 5400.0
G = 9.81
F0 = 8.0e-5
CP = 1004.0
LV = 2.5e6
DX = 12000.0
DY = 12000.0

def deep_merge(base, override):
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load_request(path=None):
    if path is None:
        return DEFAULT_REQUEST
    return deep_merge(DEFAULT_REQUEST, json.loads(Path(path).read_text(encoding="utf-8")))

def clip(a, lo, hi): return np.clip(a, lo, hi)
def expand_scalar_to_field(arr1d, H, W): return np.repeat(np.repeat(arr1d[:, None, None], H, axis=1), W, axis=2)

def classify_relative(scores, idx):
    best = max(scores); worst = min(scores); span = max(1e-9, best - worst); rel = best - scores[idx]
    if rel <= max(0.20, 0.22 * span): return "active"
    if rel <= max(0.55, 0.45 * span): return "restricted"
    if rel <= max(1.20, 0.90 * span): return "starved"
    return "withered"

def histogram_of_status(rows, key="branch_status"):
    return {s: sum(r[key] == s for r in rows) for s in ["active", "restricted", "starved", "withered"]}

@dataclass
class GridSpec:
    shape: Tuple[int, int]
    dx: float = 1.0
    dy: float = 1.0
    dt: float = 1.0
    engine: str = "numpy_local"

@dataclass
class UnifiedState:
    dyn: Dict[str, np.ndarray]
    aux: Dict[str, np.ndarray]
    meta: Dict[str, Any]

class GridComputeEngine:
    def lap(self, f, spec):
        return ((np.roll(f, -1, axis=-2) - 2.0 * f + np.roll(f, 1, axis=-2)) / (spec.dy ** 2)
                + (np.roll(f, -1, axis=-1) - 2.0 * f + np.roll(f, 1, axis=-1)) / (spec.dx ** 2))
    def grad_x(self, f, spec): return (np.roll(f, -1, axis=-1) - np.roll(f, 1, axis=-1)) / (2.0 * spec.dx)
    def grad_y(self, f, spec): return (np.roll(f, -1, axis=-2) - np.roll(f, 1, axis=-2)) / (2.0 * spec.dy)
    def smooth(self, f, alpha=0.10):
        return (1.0 - alpha) * f + alpha * (np.roll(f, 1, -2) + np.roll(f, -1, -2) + np.roll(f, 1, -1) + np.roll(f, -1, -1)) / 4.0
    def bilinear_sample(self, field, px, py):
        px = np.clip(px, 0.0, field.shape[-1] - 1.001); py = np.clip(py, 0.0, field.shape[-2] - 1.001)
        x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int)
        x1 = np.clip(x0 + 1, 0, field.shape[-1] - 1); y1 = np.clip(y0 + 1, 0, field.shape[-2] - 1)
        wx = px - x0; wy = py - y0
        b = np.arange(field.shape[0])[:, None, None]
        f00 = field[b, y0, x0]; f10 = field[b, y0, x1]; f01 = field[b, y1, x0]; f11 = field[b, y1, x1]
        return ((1.0 - wx) * (1.0 - wy) * f00 + wx * (1.0 - wy) * f10 + (1.0 - wx) * wy * f01 + wx * wy * f11)
    def semi_lagrangian(self, field, u, v, spec):
        H, W = field.shape[-2], field.shape[-1]
        jj, ii = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")
        dep_x = ii[None, ...] - (u * spec.dt / spec.dx)
        dep_y = jj[None, ...] - (v * spec.dt / spec.dy)
        return self.bilinear_sample(field, dep_x, dep_y)

class GridAbstractionLayer:
    def __init__(self, spec):
        self.spec = spec
        self.engine = GridComputeEngine()
    def aggregate(self, rows):
        return {
            "count": len(rows),
            "mean_score": float(np.mean([r["score"] for r in rows])) if rows else 0.0,
            "score_span": float(max(r["score"] for r in rows) - min(r["score"] for r in rows)) if rows else 0.0,
        }

def route_mappings(req):
    env = req["environment"]
    text = (req["problem"]["title"] + " " + req["problem"]["target"]).lower()
    keyword_hit = any(k in text for k in ["weather", "meteorology", "storm", "climate", "atmosphere", "city-scale", "urban", "environment"])
    weather_signal = max(env.get("weather_relevance", 0.0), env.get("terrain_relevance", 0.0))
    needs_meteorology = keyword_hit or weather_signal >= 0.55 or env.get("field_noise", 0.0) >= 0.30
    return {"plan": True, "meteorology": needs_meteorology, "coupled": needs_meteorology}

def family_lock(family, n):
    nc_map = {"batch":18000.0,"network":15000.0,"phase":17000.0,"electrical":16000.0,"ascetic":20000.0,"hybrid":18000.0,"composite":18500.0,
              "weak_mix":15000.0,"balanced":15000.0,"high_mix":15000.0,"humid_bias":15000.0,"strong_pg":15000.0,"terrain_lock":15000.0}
    sharp_map = {"batch":2200.0,"network":2000.0,"phase":2400.0,"electrical":2200.0,"ascetic":2600.0,"hybrid":2300.0,"composite":2500.0,
                 "weak_mix":2500.0,"balanced":2500.0,"high_mix":2500.0,"humid_bias":2500.0,"strong_pg":2500.0,"terrain_lock":2500.0}
    x = (n - nc_map[family]) / sharp_map[family]
    return 1.0 / (1.0 + math.exp(-x))

def generate_plan_candidates():
    family_params = {
        "batch":{"n":[12000,18000,20000,24000],"rho":[0.5,1.0],"A":[0.7,0.9],"sigma":[0.01,0.03]},
        "network":{"n":[10000,16000,20000],"rho":[0.8,1.2],"A":[0.6,0.8],"sigma":[0.02]},
        "phase":{"n":[10000,18000],"rho":[0.5,1.0],"A":[0.6,0.75],"sigma":[0.04]},
        "electrical":{"n":[10000,16000,20000],"rho":[0.6,1.0],"A":[0.7],"sigma":[0.05]},
        "ascetic":{"n":[10000,20000],"rho":[0.2,0.4],"A":[0.4,0.55],"sigma":[0.03]},
        "hybrid":{"n":[14000,18000,22000],"rho":[0.7,1.0],"A":[0.75],"sigma":[0.08]},
        "composite":{"n":[18000,22000],"rho":[0.8,1.0],"A":[0.8],"sigma":[0.04]},
    }
    out = []
    for fam, spec in family_params.items():
        for n, rho, A, sigma in itertools.product(spec["n"], spec["rho"], spec["A"], spec["sigma"]):
            out.append({"family": fam, "template": f"{fam}_route", "params": {"n": float(n), "rho": float(rho), "A": float(A), "sigma": float(sigma)}, "domain": "plan"})
    return out

def generate_weather_candidates():
    return [
        {"family":"weak_mix","template":"weak_mix_route","params":{"Kh":240.0,"Kt":120.0,"Kq":95.0,"drag":1.2e-5,"humid_couple":0.80,"nudging":0.00014,"pg_scale":1.00},"domain":"meteorology"},
        {"family":"balanced","template":"balanced_route","params":{"Kh":360.0,"Kt":180.0,"Kq":130.0,"drag":1.5e-5,"humid_couple":1.00,"nudging":0.00016,"pg_scale":1.00},"domain":"meteorology"},
        {"family":"high_mix","template":"high_mix_route","params":{"Kh":520.0,"Kt":260.0,"Kq":180.0,"drag":1.8e-5,"humid_couple":1.05,"nudging":0.00017,"pg_scale":1.00},"domain":"meteorology"},
        {"family":"humid_bias","template":"humid_bias_route","params":{"Kh":340.0,"Kt":175.0,"Kq":220.0,"drag":1.5e-5,"humid_couple":1.24,"nudging":0.00016,"pg_scale":1.00},"domain":"meteorology"},
        {"family":"strong_pg","template":"strong_pg_route","params":{"Kh":300.0,"Kt":150.0,"Kq":125.0,"drag":1.2e-5,"humid_couple":0.95,"nudging":0.00015,"pg_scale":1.18},"domain":"meteorology"},
        {"family":"terrain_lock","template":"terrain_lock_route","params":{"Kh":330.0,"Kt":170.0,"Kq":135.0,"drag":1.6e-5,"humid_couple":1.02,"nudging":0.00015,"pg_scale":1.04},"domain":"meteorology"},
    ]

def encode_plan_state_batch(req, spec, B, external_boost=None):
    env = req["environment"]; subj = req["subject"]; H, W = spec.shape[1], spec.shape[0]; ones = np.ones((H, W))
    primary = 0.42 * subj["aim_coupling"] + 0.18 * subj["control_precision"] + 0.12 * subj["phase_proximity"] + 0.18 * env["population_coupling"] + 0.06 * env["data_coverage"] - 0.14 * env["field_noise"] - 0.08 * env["phase_instability"]
    secondary = 0.60 * env["network_density"] + 0.20 * env["infrastructure"] + 0.20 * env["data_coverage"]
    tertiary = 0.75 * env["phase_instability"] + 0.25 * env["field_noise"]
    resource = 0.60 * env["budget"] + 0.40 * env["infrastructure"]
    dyn = {
        "primary": clip(np.repeat((ones * primary)[None, ...], B, axis=0), 0.0, 1.0),
        "secondary": clip(np.repeat((ones * secondary)[None, ...], B, axis=0), 0.0, 1.0),
        "tertiary": clip(np.repeat((ones * tertiary)[None, ...], B, axis=0), 0.0, 1.0),
        "resource": clip(np.repeat((ones * resource)[None, ...], B, axis=0), 0.0, 1.0),
        "u": np.zeros((B, H, W)), "v": np.zeros((B, H, W))}
    if external_boost:
        for key, ch in [("field_coherence","primary"),("network_amplification","secondary"),("phase_turbulence","tertiary"),("resource_elasticity","resource")]:
            if key in external_boost: dyn[ch] = clip(dyn[ch] + external_boost[key], 0.0, 1.0)
    aux = {"governance": clip(np.repeat((ones * (0.65 * env["regulatory_friction"] + 0.35 * env["social_pressure"]))[None, ...], B, axis=0), 0.0, 1.0)}
    return UnifiedState(dyn=dyn, aux=aux, meta={"domain":"plan", "batch":B})

def encode_meteorology_state_batch(req, spec, B, _external_boost=None):
    H, W = spec.shape[1], spec.shape[0]
    x = np.linspace(-1.0, 1.0, W); y = np.linspace(-1.0, 1.0, H); XX, YY = np.meshgrid(x, y)
    topo = 1400.0*np.exp(-7.0*((XX+0.36)**2+(YY-0.06)**2)) + 720.0*np.exp(-10.5*((XX-0.18)**2+(YY+0.24)**2)) + 350.0*np.exp(-14.0*((XX+0.05)**2+(YY+0.28)**2))
    dyn = {
        "primary": np.repeat((clip(BASE_H + 170.0*np.exp(-7.0*((XX+0.25)**2+(YY+0.02)**2)) - 105.0*np.exp(-7.8*((XX-0.25)**2+(YY-0.18)**2)) - 0.18*topo, BASE_H-350.0, BASE_H+350.0))[None, ...], B, axis=0),
        "secondary": np.repeat((clip(288.0 + 6.2*np.exp(-7.5*((XX+0.23)**2+(YY+0.04)**2)) - 4.3*np.exp(-9.2*((XX-0.29)**2+(YY-0.16)**2)) - 0.0032*topo, 265.0, 315.0))[None, ...], B, axis=0),
        "tertiary": np.repeat((clip(0.009 + 0.0085*np.exp(-8.0*((XX-0.08)**2+(YY+0.20)**2)), 1e-5, 0.025))[None, ...], B, axis=0),
        "resource": np.zeros((B, H, W)),
        "u": np.repeat((clip(10.5*np.sin(0.8*np.pi*YY)*np.cos(0.7*np.pi*XX), -30.0, 30.0))[None, ...], B, axis=0),
        "v": np.repeat((clip(-7.2*np.sin(0.7*np.pi*XX)*np.cos(0.8*np.pi*YY), -30.0, 30.0))[None, ...], B, axis=0)}
    aux = {"topography": np.repeat(topo[None, ...], B, axis=0), "XX": np.repeat(XX[None, ...], B, axis=0), "YY": np.repeat(YY[None, ...], B, axis=0)}
    return UnifiedState(dyn=dyn, aux=aux, meta={"domain":"meteorology", "batch":B})

def prepare_candidate_arrays(candidates):
    fams = [c["family"] for c in candidates]; params = [c["params"] for c in candidates]
    out = {"family": np.array(fams, dtype=object)}
    for k in sorted(set().union(*[p.keys() for p in params])):
        out[k] = np.array([p.get(k, 0.0) for p in params], dtype=np.float64)[:, None, None]
    return out

def gen_plan_scalar_fields(spec, ctx):
    B, H, W = ctx["state"].dyn["primary"].shape
    subj = ctx["req"]["subject"]; fams = ctx["candidate_arrays"]["family"]; n = ctx["candidate_arrays"]["n"][:,0,0]
    rho = ctx["candidate_arrays"]["rho"][:,0,0]; A = ctx["candidate_arrays"]["A"][:,0,0]; sigma = ctx["candidate_arrays"]["sigma"][:,0,0]
    primary = ctx["state"].dyn["primary"].mean(axis=(1,2)); secondary = ctx["state"].dyn["secondary"].mean(axis=(1,2)); tertiary = ctx["state"].dyn["tertiary"].mean(axis=(1,2)); resource = ctx["state"].dyn["resource"].mean(axis=(1,2)); governance = ctx["state"].aux["governance"].mean(axis=(1,2))
    bias_table = {"batch":(0.16,0.08,0.02),"network":(0.12,0.11,-0.01),"phase":(0.09,0.12,-0.02),"electrical":(0.11,0.04,0.08),"ascetic":(0.05,0.13,-0.03),"hybrid":(0.13,0.06,0.04),"composite":(0.14,0.09,0.03)}
    yb = np.array([bias_table.get(f,(0.0,0.0,0.0))[0] for f in fams]); sb = np.array([bias_table.get(f,(0.0,0.0,0.0))[1] for f in fams]); rb = np.array([bias_table.get(f,(0.0,0.0,0.0))[2] for f in fams]); locks = np.array([family_lock(f, float(nn)) for f, nn in zip(fams, n)])
    scalars = {
        "feasibility": np.clip(0.25*subj["output_power"] + 0.18*subj["aim_coupling"] + 0.12*resource + 0.18*A + 0.15*locks + yb - 0.08*sigma, 0.0, 1.2),
        "stability": np.clip(0.28*subj["control_precision"] + 0.18*subj["load_tolerance"] + 0.20*primary + 0.15*(1.0-tertiary) + 0.12*(1.0-sigma) + sb, 0.0, 1.2),
        "field_fit": np.clip(0.32*secondary*np.where(fams=="network", 1.2, 1.0) + 0.22*primary + 0.18*subj["phase_proximity"] + 0.10*rho + 0.08*locks - 0.10*governance, 0.0, 1.2),
        "risk": np.clip(0.18*tertiary + 0.14*governance + 0.12*subj["instability_sensitivity"] + 0.10*subj["stress_level"] + 0.08*sigma + 0.05*np.maximum(0.0, (n-20000.0)/10000.0) + rb, 0.0, 1.2),
    }
    return {k: expand_scalar_to_field(v, H, W) for k, v in scalars.items()}

def gen_state_alias(spec, ctx):
    src = ctx["state"].dyn
    return {"weather_h": src["primary"], "weather_T": src["secondary"], "weather_q": src["tertiary"], "weather_u": src["u"], "weather_v": src["v"]}

def gen_zero_like(spec, ctx): return {k: np.zeros_like(ctx["predictions"][k]) for k in spec["channels"]}

def gen_weather_obs(spec, ctx):
    topo = ctx["state"].aux["topography"]; XX = ctx["state"].aux["XX"]; YY = ctx["state"].aux["YY"]
    return {
        "weather_h": BASE_H + 200.0*np.exp(-6.8*((XX+0.18)**2+(YY+0.10)**2)) - 150.0*np.exp(-8.0*((XX-0.28)**2+(YY-0.14)**2)) - 0.23*topo,
        "weather_T": 289.0 + 7.5*np.exp(-8.2*((XX+0.16)**2+(YY+0.11)**2)) - 5.8*np.exp(-8.8*((XX-0.24)**2+(YY-0.17)**2)) - 0.0038*topo + 0.8*np.sin(1.2*np.pi*XX)*np.cos(0.8*np.pi*YY),
        "weather_q": 0.010 + 0.011*np.exp(-7.6*((XX-0.10)**2+(YY+0.21)**2)) + 0.0016*np.sin(np.pi*YY),
        "weather_u": 12.0*np.sin(0.9*np.pi*YY)*np.cos(0.8*np.pi*XX),
        "weather_v": -8.5*np.sin(0.8*np.pi*XX)*np.cos(0.9*np.pi*YY),
    }

GENERATOR_FAMILIES = {"plan_scalar_fields": gen_plan_scalar_fields, "state_alias": gen_state_alias, "zero_like": gen_zero_like, "weather_obs": gen_weather_obs}

def build_from_specs(specs, ctx):
    out = {}
    for spec in specs: out.update(GENERATOR_FAMILIES[spec["family"]](spec, ctx))
    return out

def sat_q(Tv): return 0.0045*np.exp(0.060*(Tv-273.15)/10.0)

def cache_adv(ctx):
    if "_adv" not in ctx:
        st=ctx["state"]; spec=ctx["gal"].spec; eng=ctx["gal"].engine; u=st.dyn["u"]; v=st.dyn["v"]
        ctx["_adv"] = {"primary": eng.semi_lagrangian(st.dyn["primary"],u,v,spec),"secondary": eng.semi_lagrangian(st.dyn["secondary"],u,v,spec),"tertiary": eng.semi_lagrangian(st.dyn["tertiary"],u,v,spec),"u": eng.semi_lagrangian(u,u,v,spec),"v": eng.semi_lagrangian(v,u,v,spec)}
    return ctx["_adv"]

def cache_obs(ctx):
    if "_obs" not in ctx:
        aux=ctx["state"].aux; topo=aux["topography"]; XX=aux["XX"]; YY=aux["YY"]
        ctx["_obs"] = {"primary": BASE_H + 200.0*np.exp(-6.8*((XX+0.18)**2+(YY+0.10)**2)) - 150.0*np.exp(-8.0*((XX-0.28)**2+(YY-0.14)**2)) - 0.23*topo,
                       "secondary": 289.0 + 7.5*np.exp(-8.2*((XX+0.16)**2+(YY+0.11)**2)) - 5.8*np.exp(-8.8*((XX-0.24)**2+(YY-0.17)**2)) - 0.0038*topo + 0.8*np.sin(1.2*np.pi*XX)*np.cos(0.8*np.pi*YY),
                       "tertiary": 0.010 + 0.011*np.exp(-7.6*((XX-0.10)**2+(YY+0.21)**2)) + 0.0016*np.sin(np.pi*YY),
                       "u": 12.0*np.sin(0.9*np.pi*YY)*np.cos(0.8*np.pi*XX), "v": -8.5*np.sin(0.8*np.pi*XX)*np.cos(0.9*np.pi*YY)}
    return ctx["_obs"]

def eval_plan_affine(spec, ctx):
    ch = spec["channel"]
    out = np.zeros_like(ctx["state"].dyn[ch]); carr = ctx["carr"]
    for item in spec["terms"]:
        coeff = item["coeff"]; src = item["src"]
        if src == "A": out = out + coeff * carr["A"]
        elif src == "rho": out = out + coeff * carr["rho"]
        elif src == "sigma": out = out + coeff * carr["sigma"]
        elif src == "lock":
            fams = carr["family"]; n = carr["n"][:,0,0]
            locks = np.array([family_lock(f, float(nn)) for f, nn in zip(fams, n)], dtype=np.float64)[:,None,None]
            out = out + coeff * locks
        elif src == "network_mask":
            fams = carr["family"]; mask = np.array([1.0 if f=="network" else 0.0 for f in fams])[:,None,None]
            out = out + coeff * mask
        elif src == "phase_mask":
            fams = carr["family"]; mask = np.array([1.0 if f=="phase" else 0.0 for f in fams])[:,None,None]
            out = out + coeff * mask
        elif src == "oversize":
            out = out + coeff * np.maximum(0.0, (carr["n"]-20000.0)/10000.0)
    return out

def eval_plan_smooth(spec, ctx):
    ch = spec["channel"]
    return spec["alpha"] * (ctx["gal"].engine.smooth(ctx["state"].dyn[ch], spec["smooth_alpha"]) - ctx["state"].dyn[ch])

def eval_met_adv(spec, ctx):
    ch = spec["channel"]
    return cache_adv(ctx)[ch] - ctx["state"].dyn[ch]

def eval_met_primary_drift(spec, ctx):
    a=cache_adv(ctx); div = ctx["gal"].engine.grad_x(a["u"],ctx["gal"].spec)+ctx["gal"].engine.grad_y(a["v"],ctx["gal"].spec)
    return -ctx["gal"].spec.dt*0.55*a["primary"]/BASE_H*div

def eval_met_u_drift(spec, ctx):
    a=cache_adv(ctx); topo=ctx["state"].aux["topography"]; geop = G*(a["primary"]+0.18*topo); pgx = ctx["carr"]["pg_scale"]*ctx["gal"].engine.grad_x(geop,ctx["gal"].spec); topo_drag=1.0+0.00035*topo
    return -ctx["gal"].spec.dt*pgx + ctx["gal"].spec.dt*F0*a["v"] - ctx["gal"].spec.dt*ctx["carr"]["drag"]*topo_drag*a["u"]

def eval_met_v_drift(spec, ctx):
    a=cache_adv(ctx); topo=ctx["state"].aux["topography"]; geop = G*(a["primary"]+0.18*topo); pgy = ctx["carr"]["pg_scale"]*ctx["gal"].engine.grad_y(geop,ctx["gal"].spec); topo_drag=1.0+0.00035*topo
    return -ctx["gal"].spec.dt*pgy - ctx["gal"].spec.dt*F0*a["u"] - ctx["gal"].spec.dt*ctx["carr"]["drag"]*topo_drag*a["v"]

def eval_met_diff(spec, ctx):
    ch = spec["channel"]; a=cache_adv(ctx)
    return ctx["gal"].spec.dt * ctx["carr"][spec["coeff_key"]] * spec.get("scale",1.0) * ctx["gal"].engine.lap(a[ch], ctx["gal"].spec)

def eval_met_secondary_corr(spec, ctx):
    a=cache_adv(ctx); topo=ctx["state"].aux["topography"]; excess=np.maximum(a["tertiary"]-sat_q(a["secondary"]),0.0); cond=0.20*excess*ctx["carr"]["humid_couple"]; latent=(LV/CP)*cond*1.0e-4; T_eq=286.5-0.0032*topo
    return ctx["gal"].spec.dt*latent - ctx["gal"].spec.dt*1.4e-5*(a["secondary"]-T_eq)

def eval_met_tertiary_corr(spec, ctx):
    a=cache_adv(ctx); aux=ctx["state"].aux; excess=np.maximum(a["tertiary"]-sat_q(a["secondary"]),0.0); cond=0.20*excess*ctx["carr"]["humid_couple"]; q_source=2.0e-6*np.exp(-6.0*(aux["XX"]**2+aux["YY"]**2))
    return ctx["gal"].spec.dt*q_source - ctx["gal"].spec.dt*cond

def eval_met_obs(spec, ctx):
    ch = spec["channel"]
    return ctx["gal"].spec.dt * ctx["carr"]["nudging"] * (cache_obs(ctx)[ch] - cache_adv(ctx)[ch])

TERM_EVALUATORS = {
    "plan_affine": eval_plan_affine,
    "plan_smooth": eval_plan_smooth,
    "met_adv": eval_met_adv,
    "met_primary_drift": eval_met_primary_drift,
    "met_u_drift": eval_met_u_drift,
    "met_v_drift": eval_met_v_drift,
    "met_diff": eval_met_diff,
    "met_secondary_corr": eval_met_secondary_corr,
    "met_tertiary_corr": eval_met_tertiary_corr,
    "met_obs": eval_met_obs,
}

TERM_REGISTRY = {
    "plan": {
        "terms": {
            "advection": [],
            "drift": [{"kind":"plan_affine","channel":"primary","terms":[{"src":"A","coeff":0.015},{"src":"lock","coeff":0.010},{"src":"sigma","coeff":-0.012}]},{"kind":"plan_affine","channel":"secondary","terms":[{"src":"rho","coeff":0.012},{"src":"network_mask","coeff":0.020}]},{"kind":"plan_affine","channel":"tertiary","terms":[{"src":"sigma","coeff":0.010},{"src":"phase_mask","coeff":-0.020}]},{"kind":"plan_affine","channel":"resource","terms":[{"src":"A","coeff":0.010},{"src":"oversize","coeff":-0.010}]}],
            "diffusion": [{"kind":"plan_smooth","channel":"primary","alpha":0.10,"smooth_alpha":0.10},{"kind":"plan_smooth","channel":"secondary","alpha":0.10,"smooth_alpha":0.10},{"kind":"plan_smooth","channel":"tertiary","alpha":0.10,"smooth_alpha":0.10},{"kind":"plan_smooth","channel":"resource","alpha":0.10,"smooth_alpha":0.10}],
            "correction": [], "observation": [],
        },
        "smoothing": {"primary":0.10,"secondary":0.10,"tertiary":0.10,"resource":0.10},
        "bounds": {"primary":(0.0,1.0),"secondary":(0.0,1.0),"tertiary":(0.0,1.0),"resource":(0.0,1.0),"u":(-1e9,1e9),"v":(-1e9,1e9)},
    },
    "meteorology": {
        "terms": {
            "advection": [{"kind":"met_adv","channel":"primary"},{"kind":"met_adv","channel":"secondary"},{"kind":"met_adv","channel":"tertiary"},{"kind":"met_adv","channel":"u"},{"kind":"met_adv","channel":"v"}],
            "drift": [{"kind":"met_primary_drift","channel":"primary"},{"kind":"met_u_drift","channel":"u"},{"kind":"met_v_drift","channel":"v"}],
            "diffusion": [{"kind":"met_diff","channel":"primary","coeff_key":"Kh","scale":0.35},{"kind":"met_diff","channel":"secondary","coeff_key":"Kt","scale":1.0},{"kind":"met_diff","channel":"tertiary","coeff_key":"Kq","scale":1.0},{"kind":"met_diff","channel":"u","coeff_key":"Kh","scale":1.0},{"kind":"met_diff","channel":"v","coeff_key":"Kh","scale":1.0}],
            "correction": [{"kind":"met_secondary_corr","channel":"secondary"},{"kind":"met_tertiary_corr","channel":"tertiary"}],
            "observation": [{"kind":"met_obs","channel":"primary"},{"kind":"met_obs","channel":"secondary"},{"kind":"met_obs","channel":"tertiary"},{"kind":"met_obs","channel":"u"},{"kind":"met_obs","channel":"v"}],
        },
        "smoothing": {"primary":0.06,"secondary":0.05,"tertiary":0.05,"u":0.04,"v":0.04},
        "bounds": {"primary":(BASE_H-500.0,BASE_H+500.0),"secondary":(250.0,320.0),"tertiary":(1e-5,0.030),"resource":(-1e9,1e9),"u":(-40.0,40.0),"v":(-40.0,40.0)},
    },
}

def domain_manifest(req):
    return {
        "plan": {
            "grid": {"shape": tuple(req["runtime"]["plan_grid_shape"]), "dx": 1.0, "dy": 1.0, "dt": 1.0},
            "runtime": {"steps": 1, "postprocess": "top12"},
            "candidate_fn": generate_plan_candidates,
            "encode_fn": encode_plan_state_batch,
            "operator_family": "plan",
            "hydro_policy": None,
            "prediction_specs": [{"family":"plan_scalar_fields"}],
            "target_specs": [{"family":"zero_like", "channels":["feasibility","stability","field_fit","risk"]}],
            "metric_specs": {"feasibility": {"family":"field_mse", "pred":"feasibility", "target":"feasibility"},"stability": {"family":"field_mse", "pred":"stability", "target":"stability"},"field_fit": {"family":"field_mse", "pred":"field_fit", "target":"field_fit"},"risk": {"family":"field_mse", "pred":"risk", "target":"risk"},"spread_penalty": {"family":"field_spread", "channels":["feasibility","stability","field_fit"]}},
            "reward_schema": {"family":"weighted_linear","metric_keys":["feasibility","stability","field_fit","risk","spread_penalty"],"output_map":{"feasibility":"feasibility","stability":"stability","field_fit":"field_fit","risk":"risk"},"policy":{"name":"plan_nutrient"}},
        },
        "meteorology": {
            "grid": {"shape": tuple(req["runtime"]["weather_grid_shape"]), "dx": DX, "dy": DY, "dt": float(req["runtime"]["weather_dt"])},
            "runtime": {"steps": int(req["runtime"]["weather_steps"]), "postprocess": "all"},
            "candidate_fn": generate_weather_candidates,
            "encode_fn": encode_meteorology_state_batch,
            "operator_family": "meteorology",
            "hydro_policy": {"rescale_param": "pg_scale"},
            "prediction_specs": [{"family":"state_alias"}],
            "target_specs": [{"family":"weather_obs"}],
            "metric_specs": {"weather_h_err": {"family":"field_mse", "pred":"weather_h", "target":"weather_h"},"weather_t_err": {"family":"field_mse", "pred":"weather_T", "target":"weather_T"},"weather_q_err": {"family":"field_mse", "pred":"weather_q", "target":"weather_q"},"weather_w_err": {"family":"field_vector_mse", "pred":["weather_u","weather_v"], "target":["weather_u","weather_v"]},"weather_instability": {"family":"field_laplacian_energy", "channels":["weather_h","weather_T","weather_q","weather_u","weather_v"]}},
            "reward_schema": {"family":"weighted_linear","metric_keys":["weather_h_err","weather_t_err","weather_q_err","weather_w_err","weather_instability"],"output_map":{"weather_h_err":"h_err","weather_t_err":"t_err","weather_q_err":"q_err","weather_w_err":"w_err","weather_instability":"instability"}},
        },
    }

def td_step(state, carr, gal, operator_family):
    reg = TERM_REGISTRY[operator_family]
    dyn = {k: np.array(v, copy=True) for k, v in state.dyn.items()}
    ctx = {"state": state, "carr": carr, "gal": gal}
    for phase in ["advection", "drift", "diffusion", "correction", "observation"]:
        for spec in reg["terms"][phase]:
            ch = spec["channel"]
            dyn[ch] = dyn[ch] + TERM_EVALUATORS[spec["kind"]](spec, ctx)
            ctx["state"] = UnifiedState(dyn=dyn, aux=state.aux, meta=state.meta)
    for k, alpha in reg["smoothing"].items(): dyn[k] = gal.engine.smooth(dyn[k], alpha)
    for k, (lo, hi) in reg["bounds"].items(): dyn[k] = clip(dyn[k], lo, hi)
    return UnifiedState(dyn=dyn, aux={k: np.array(v, copy=True) for k, v in state.aux.items()}, meta=dict(state.meta))

def td_rollout(initial, carr, gal, steps, operator_family):
    state = UnifiedState(dyn={k: np.array(v, copy=True) for k, v in initial.dyn.items()}, aux={k: np.array(v, copy=True) for k, v in initial.aux.items()}, meta=dict(initial.meta))
    for _ in range(steps): state = td_step(state, carr, gal, operator_family)
    return state

def metric_field_mse(spec, ctx):
    return ((ctx["preds"][spec["pred"]] - ctx["tgts"][spec["target"]])**2).mean(axis=(1,2))

def metric_field_vector_mse(spec, ctx):
    return ((ctx["preds"][spec["pred"][0]] - ctx["tgts"][spec["target"][0]])**2 + (ctx["preds"][spec["pred"][1]] - ctx["tgts"][spec["target"][1]])**2).mean(axis=(1,2))

def metric_field_spread(spec, ctx):
    return np.std(np.stack([ctx["preds"][ch].mean(axis=(1,2)) for ch in spec["channels"]], axis=1), axis=1)

def metric_field_laplacian_energy(spec, ctx):
    preds = ctx["preds"]; req = ctx["req"]
    if "_metric_gspec" not in ctx:
        sample = preds[spec["channels"][0]]
        ctx["_metric_gspec"] = GridSpec(shape=(sample.shape[-1], sample.shape[-2]), dx=DX, dy=DY, dt=float(req["runtime"]["weather_dt"]))
        ctx["_metric_eng"] = GridComputeEngine()
    gspec = ctx["_metric_gspec"]; eng = ctx["_metric_eng"]
    return (np.abs(eng.lap(preds["weather_T"], gspec)).mean(axis=(1,2)) +
            0.8*np.abs(eng.lap(preds["weather_q"], gspec)).mean(axis=(1,2)) +
            0.5*np.abs(eng.lap(preds["weather_u"], gspec)).mean(axis=(1,2)) +
            0.5*np.abs(eng.lap(preds["weather_v"], gspec)).mean(axis=(1,2)) +
            0.35*np.abs(eng.lap(preds["weather_h"], gspec)).mean(axis=(1,2)))

METRIC_EVALUATORS = {
    "field_mse": metric_field_mse,
    "field_vector_mse": metric_field_vector_mse,
    "field_spread": metric_field_spread,
    "field_laplacian_energy": metric_field_laplacian_energy,
}

def build_tensor_bundle(final_state, carr, req, manifest):
    ctx = {"state": final_state, "candidate_arrays": carr, "req": req}
    predictions = build_from_specs(manifest["prediction_specs"], ctx); ctx["predictions"] = predictions; targets = build_from_specs(manifest["target_specs"], ctx)
    return {"predictions": predictions, "targets": targets, "metric_specs": manifest["metric_specs"], "reward_schema": manifest["reward_schema"], "meta": final_state.meta | {"family": carr.get("family"), "n": carr.get("n", None)}}

def build_metric_bundle(bundle, req):
    ctx = {"preds": bundle["predictions"], "tgts": bundle["targets"], "req": req}
    return {name: METRIC_EVALUATORS[spec["family"]](spec, ctx) for name, spec in bundle["metric_specs"].items()}

def apply_reward_policy(bundle, metrics, req):
    policy = bundle["reward_schema"].get("policy")
    if policy and policy["name"] == "plan_nutrient":
        fams = bundle["meta"]["family"]; n = bundle["meta"]["n"][:,0,0]; nutrient_cfg = req["reward"]["nutrient"]
        route_bonus = np.where(fams=="network", 0.14*metrics["field_fit"] + 0.06*metrics["feasibility"], 0.0) + np.where(fams=="phase", 0.07*(1.0-metrics["risk"]), 0.0) + np.where((fams=="batch") & (np.abs(n-20000.0)<=1e-6), 0.05, 0.0) + np.where(np.abs(n-20000.0)<=1e-6, 0.06, 0.0)
        nutrient = nutrient_cfg["feasibility_threshold_gain"]*np.maximum(0.0, metrics["feasibility"]-0.82) + nutrient_cfg["stability_threshold_gain"]*np.maximum(0.0, metrics["stability"]-0.80) + nutrient_cfg["field_fit_threshold_gain"]*np.maximum(0.0, metrics["field_fit"]-0.68) + route_bonus + nutrient_cfg["risk_penalty"]*metrics["risk"] + nutrient_cfg["oversize_penalty"]*np.maximum(0.0, (n-20000.0)/5000.0)
        return {"nutrient_gain": nutrient}
    return {}

def build_reward_bundle(bundle, metrics, req):
    reward = req["reward"]["components"]; schema = bundle["reward_schema"]; score = np.zeros_like(next(iter(metrics.values())))
    for k in schema["metric_keys"]: score = score + reward[k] * metrics[k]
    out = {"score": score}
    for src, dst in schema.get("output_map", {}).items(): out[dst] = metrics[src]
    out.update(apply_reward_policy(bundle, metrics, req))
    return out

def observe_batch(final_state, carr, req, manifest):
    bundle = build_tensor_bundle(final_state, carr, req, manifest); metrics = build_metric_bundle(bundle, req)
    return build_reward_bundle(bundle, metrics, req)

def batch_rows_from_metrics(candidates, metrics):
    rows = []
    for i, c in enumerate(candidates):
        row = {"family": c["family"], "template": c["template"], "params": c["params"]}
        for k, arr in metrics.items(): row[k] = float(arr[i])
        rows.append(row)
    return rows

def td_hydro_control(rows):
    ranked = sorted(rows, key=lambda x: x["score"], reverse=True)
    margin = ranked[0]["score"] - ranked[1]["score"] if len(ranked) > 1 else 0.0; spread = ranked[0]["score"] - ranked[-1]["score"] if len(ranked) > 1 else 0.0
    pressure_balance = 1.0 + (0.04 if margin < 0.08 else 0.0) - (0.03 if spread > 1.4 else 0.0)
    pressure_balance = float(np.clip(pressure_balance, 0.94, 1.08))
    return {"pressure_balance": pressure_balance, "top_margin": float(margin), "score_spread": float(spread), "mean_score": float(np.mean([m["score"] for m in rows])) if rows else 0.0}

def run_domain(req, domain, external_boost=None):
    manifest = domain_manifest(req)[domain]
    g = manifest["grid"]
    spec = GridSpec(shape=g["shape"], dx=g["dx"], dy=g["dy"], dt=g["dt"], engine=req["runtime"]["grid_engine"])
    candidates = manifest["candidate_fn"]()
    initial = manifest["encode_fn"](req, spec, len(candidates), external_boost)
    gal = GridAbstractionLayer(spec); carr = prepare_candidate_arrays(candidates)
    final_state = td_rollout(initial, carr, gal, manifest["runtime"]["steps"], manifest["operator_family"])
    metrics = observe_batch(final_state, carr, req, manifest)
    rows = sorted(batch_rows_from_metrics(candidates, metrics), key=lambda x: x["score"], reverse=True)
    scores = [r["score"] for r in rows]
    for i, row in enumerate(rows): row["branch_status"] = classify_relative(scores, i)
    hydro = td_hydro_control(rows if manifest["runtime"]["postprocess"] == "all" else rows[:12])
    if manifest["hydro_policy"] is not None:
        tuned = []
        param = manifest["hydro_policy"]["rescale_param"]
        for c in candidates:
            c2 = {"family": c["family"], "template": c["template"], "params": dict(c["params"]), "domain": c["domain"]}
            c2["params"][param] *= hydro["pressure_balance"]
            tuned.append(c2)
        carr = prepare_candidate_arrays(tuned)
        final_state = td_rollout(initial, carr, gal, manifest["runtime"]["steps"], manifest["operator_family"])
        metrics = observe_batch(final_state, carr, req, manifest)
        rows = sorted(batch_rows_from_metrics(tuned, metrics), key=lambda x: x["score"], reverse=True)
        scores = [r["score"] for r in rows]
        for i, row in enumerate(rows): row["branch_status"] = classify_relative(scores, i)
    return rows, gal, hydro

def weather_to_plan_boost(weather_domain):
    hist = weather_domain["status_histogram"]; total = max(1, sum(hist.values())); active_ratio = hist["active"] / total; restricted_ratio = hist["restricted"] / total
    score_spread = weather_domain["hydro_control"]["score_spread"]; best_branch = weather_domain["best"]["branch"]
    return {"field_coherence": 0.06*active_ratio - 0.02*restricted_ratio, "network_amplification": 0.04 if best_branch in ("high_mix","balanced","humid_bias") else -0.03, "phase_turbulence": -0.04*active_ratio + 0.03*(best_branch=="strong_pg"), "resource_elasticity": 0.02 if score_spread < 1.0 else -0.01}

def package_domain_output(name, rows, gal, hydro, mode):
    best = rows[0]
    payload = {
        "name": name,
        "mode": mode,
        "best": {
            "branch": best["family"],
            "status": best["branch_status"],
            "score": best["score"],
            "template": best["template"],
            "params": best["params"],
        },
        "status_histogram": histogram_of_status(rows if mode == "ranking" else rows[:12]),
        "hydro_control": hydro,
        "grid_summary": gal.aggregate(rows),
    }
    if mode == "ranking":
        payload["rows"] = rows
    else:
        payload["rows"] = rows[:5]
    return payload

def run_unified(req):
    routing = route_mappings(req)
    domains = {}
    selection = {"dominant_mapping": None, "best_domain": None, "best_branch": None}
    if routing["coupled"]:
        weather_rows, weather_gal, weather_hydro = run_domain(req, "meteorology")
        domains["meteorology"] = package_domain_output("meteorology", weather_rows, weather_gal, weather_hydro, "ranking")
        boost = weather_to_plan_boost(domains["meteorology"])
        plan_rows, plan_gal, plan_hydro = run_domain(req, "plan", boost)
        domains["plan"] = package_domain_output("plan", plan_rows, plan_gal, plan_hydro, "topk")
        selection["dominant_mapping"] = "coupled"
        selection["best_domain"] = "plan"
        selection["best_branch"] = domains["plan"]["best"]["branch"]
        oracle_summary = {
            "main_worldline_alive": domains["plan"]["best"]["status"] in ("active", "restricted"),
            "main_worldline_active": domains["plan"]["best"]["status"] == "active",
        }
    elif routing["meteorology"]:
        weather_rows, weather_gal, weather_hydro = run_domain(req, "meteorology")
        domains["meteorology"] = package_domain_output("meteorology", weather_rows, weather_gal, weather_hydro, "ranking")
        selection["dominant_mapping"] = "meteorology"
        selection["best_domain"] = "meteorology"
        selection["best_branch"] = domains["meteorology"]["best"]["branch"]
        oracle_summary = {
            "main_worldline_alive": domains["meteorology"]["best"]["status"] in ("active", "restricted"),
            "main_worldline_active": domains["meteorology"]["best"]["status"] == "active",
        }
    else:
        plan_rows, plan_gal, plan_hydro = run_domain(req, "plan")
        domains["plan"] = package_domain_output("plan", plan_rows, plan_gal, plan_hydro, "topk")
        selection["dominant_mapping"] = "plan"
        selection["best_domain"] = "plan"
        selection["best_branch"] = domains["plan"]["best"]["branch"]
        oracle_summary = {
            "main_worldline_alive": domains["plan"]["best"]["status"] in ("active", "restricted"),
            "main_worldline_active": domains["plan"]["best"]["status"] == "active",
        }
    return {
        "meta": {
            "engine": "tree_diagram_unified_operator_v27",
            "structure": "domain_manifest + term_registry + term_evaluators + metric_evaluators + unified_oracle_manifest",
        },
        "routing": routing,
        "domains": domains,
        "selection": selection,
        "oracle_summary": oracle_summary,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None)
    parser.add_argument("--outdir", default="./tree_diagram_unified_out_v27")
    args = parser.parse_args()
    req = load_request(args.input)
    oracle = run_unified(req)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / "unified_oracle.json"
    outpath.write_text(json.dumps(oracle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(oracle, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
