from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict


from ..core.problem_seed import ProblemSeed


def load_seed_from_json(path: str) -> ProblemSeed:
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    return ProblemSeed.from_dict(data)


def load_seed_from_yaml(path: str) -> ProblemSeed:
    data = _load_yaml(path)
    return ProblemSeed.from_dict(data)


# ---------------------------------------------------------------------------
# Full run-config loader
# ---------------------------------------------------------------------------

def _load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError as e:
        raise ImportError(
            "PyYAML is required to load YAML configs. "
            "Install it with: pip install pyyaml"
        ) from e
    text = Path(path).read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def load_run_config(path: str) -> Dict[str, Any]:
    """Load a run config YAML (configs/td_*.yaml).

    If ``path`` is a job YAML that references another config via
    ``job.config``, that config is loaded first and then the job's
    inline ``profile``/``slurm``/``output``/``seed`` keys override it.

    Returns a flat dict with top-level keys:
        profile  : dict  (NX, NY, steps, top_k, device)
        slurm    : dict  (account, partition, nodes, gpus, time, out_dir, work_dir)
        output   : dict  (path)
        seed     : dict  (title, ...)
    """
    raw = _load_yaml(path)

    # If this is a job file that references a base config, load it first
    base: Dict[str, Any] = {}
    job_meta = raw.get("job", {})
    base_ref = job_meta.get("config")
    if base_ref:
        base_path = Path(path).parent.parent / base_ref
        if not base_path.exists():
            base_path = Path(base_ref)
        if base_path.exists():
            base = _load_yaml(str(base_path))

    def merge(key: str) -> dict:
        result = dict(base.get(key) or {})
        result.update(raw.get(key) or {})
        return result

    return {
        "profile": merge("profile"),
        "slurm":   merge("slurm"),
        "output":  merge("output"),
        "seed":    merge("seed"),
    }
