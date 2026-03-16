from __future__ import annotations

"""runtime/state_store.py

State persistence store for Tree Diagram runtime.

Architecture position:
  runtime layer — provides durable key-value storage for run state,
  checkpoint data, and incremental IPL state.  Backed by JSON files
  on disk; in-memory mode available for testing.

Use cases:
  - IPL incremental state (prev_ipl dict between runs)
  - Run checkpoint: resume interrupted multi-step simulations
  - Session metadata: track run IDs, elapsed times, seed hashes
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# State record
# ---------------------------------------------------------------------------

@dataclass
class StateRecord:
    """A single persisted state entry."""
    key:         str
    value:       Any
    created_at:  float
    updated_at:  float
    tags:        List[str] = field(default_factory=list)
    version:     int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------

class StateStore:
    """Key-value state persistence store.

    Usage::

        store = StateStore(base_dir="/tmp/td_state")
        store.save("ipl_state", prev_ipl_dict, tags=["ipl"])
        val   = store.load("ipl_state")
    """

    def __init__(
        self,
        base_dir:    Optional[str] = None,
        in_memory:   bool = False,
    ) -> None:
        self._in_memory = in_memory
        self._memory:   Dict[str, StateRecord] = {}
        self._base_dir: Optional[Path] = None

        if not in_memory:
            if base_dir is None:
                base_dir = str(Path.home() / ".tree_diagram" / "state")
            self._base_dir = Path(base_dir)
            self._base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(
        self,
        key:   str,
        value: Any,
        tags:  Optional[List[str]] = None,
    ) -> StateRecord:
        """Persist a value under the given key."""
        now   = time.time()
        existing = self._read_record(key)
        version  = (existing.version + 1) if existing else 1

        record = StateRecord(
            key=key,
            value=value,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            tags=tags or [],
            version=version,
        )
        self._write_record(record)
        return record

    def load(self, key: str) -> Optional[Any]:
        """Load a value by key.  Returns None if not found."""
        record = self._read_record(key)
        return record.value if record else None

    def load_record(self, key: str) -> Optional[StateRecord]:
        """Load the full StateRecord by key."""
        return self._read_record(key)

    def delete(self, key: str) -> bool:
        """Remove a state entry.  Returns True if it existed."""
        if self._in_memory:
            existed = key in self._memory
            self._memory.pop(key, None)
            return existed
        path = self._key_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        if self._in_memory:
            return key in self._memory
        return self._key_path(key).exists()

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_keys(self, tag: Optional[str] = None) -> List[str]:
        """List all stored keys, optionally filtered by tag."""
        if self._in_memory:
            if tag is None:
                return list(self._memory.keys())
            return [k for k, r in self._memory.items() if tag in r.tags]

        if self._base_dir is None:
            return []

        keys: List[str] = []
        for p in sorted(self._base_dir.glob("*.json")):
            k = p.stem
            if tag is None:
                keys.append(k)
            else:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if tag in data.get("tags", []):
                        keys.append(k)
                except (OSError, json.JSONDecodeError):
                    pass
        return keys

    # ------------------------------------------------------------------
    # Checkpoint helpers
    # ------------------------------------------------------------------

    def save_checkpoint(
        self,
        run_id: str,
        step:   int,
        data:   Dict[str, Any],
    ) -> StateRecord:
        """Save a simulation checkpoint."""
        return self.save(
            key=f"checkpoint_{run_id}_step{step:06d}",
            value={"run_id": run_id, "step": step, "data": data},
            tags=["checkpoint", run_id],
        )

    def load_latest_checkpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load the most recent checkpoint for a run."""
        keys = [k for k in self.list_keys(tag=run_id) if k.startswith("checkpoint_")]
        if not keys:
            return None
        latest_key = sorted(keys)[-1]
        return self.load(latest_key)

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _key_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")[:64]
        return self._base_dir / f"{safe}.json"  # type: ignore[operator]

    def _write_record(self, record: StateRecord) -> None:
        if self._in_memory:
            self._memory[record.key] = record
            return
        try:
            self._key_path(record.key).write_text(
                json.dumps(record.to_dict(), default=str, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError):
            # Fall back to in-memory on write failure
            self._memory[record.key] = record

    def _read_record(self, key: str) -> Optional[StateRecord]:
        if self._in_memory:
            return self._memory.get(key)
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return StateRecord(
                key=data["key"],
                value=data["value"],
                created_at=data.get("created_at", 0.0),
                updated_at=data.get("updated_at", 0.0),
                tags=data.get("tags", []),
                version=data.get("version", 1),
            )
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def clear_all(self) -> None:
        """Remove all stored state (use with caution)."""
        if self._in_memory:
            self._memory.clear()
            return
        if self._base_dir:
            for p in self._base_dir.glob("*.json"):
                try:
                    p.unlink()
                except OSError:
                    pass
