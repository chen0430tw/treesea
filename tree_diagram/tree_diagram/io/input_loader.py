from __future__ import annotations
import json
from pathlib import Path

from ..core.problem_seed import ProblemSeed


def load_seed_from_json(path: str) -> ProblemSeed:
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    return ProblemSeed.from_dict(data)


def load_seed_from_yaml(path: str) -> ProblemSeed:
    try:
        import yaml
    except ImportError as e:
        raise ImportError(
            "PyYAML is required to load YAML seeds. "
            "Install it with: pip install pyyaml"
        ) from e

    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return ProblemSeed.from_dict(data)
