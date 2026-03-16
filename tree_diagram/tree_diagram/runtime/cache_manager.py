from __future__ import annotations

"""runtime/cache_manager.py

Result cache manager for Tree Diagram runs.

Architecture position:
  runtime layer — provides an in-memory LRU cache and optional
  disk-backed JSON cache for oracle results and intermediate
  simulation outputs.

Cache key strategy:
  SHA-256 hash of (seed_title + params_json + mode + top_k)
  This ensures cache hits only on identical inputs.
"""

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    key:         str
    value:       Any
    created_at:  float
    hit_count:   int = 0
    size_bytes:  int = 0


# ---------------------------------------------------------------------------
# CacheManager
# ---------------------------------------------------------------------------

class CacheManager:
    """LRU in-memory cache with optional disk persistence.

    Usage::

        cache = CacheManager(max_size=128, disk_dir="/tmp/td_cache")
        cache.put("key", result)
        val = cache.get("key")
    """

    def __init__(
        self,
        max_size:  int = 256,
        disk_dir:  Optional[str] = None,
        ttl_sec:   Optional[float] = None,
    ) -> None:
        self.max_size  = max_size
        self.disk_dir  = Path(disk_dir) if disk_dir else None
        self.ttl_sec   = ttl_sec
        self._store:   OrderedDict = OrderedDict()
        self._hits:    int = 0
        self._misses:  int = 0

        if self.disk_dir:
            self.disk_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(seed_title: str, params: Dict, mode: str = "integrated", top_k: int = 12) -> str:
        """Generate a deterministic cache key."""
        payload = json.dumps(
            {"seed_title": seed_title, "params": params, "mode": mode, "top_k": top_k},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    # ------------------------------------------------------------------
    # Get / Put
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value.  Returns None on miss or expiry."""
        entry = self._store.get(key)
        if entry is None:
            # Check disk
            if self.disk_dir:
                entry = self._disk_get(key)
                if entry is not None:
                    self._store[key] = entry
                    self._store.move_to_end(key)

        if entry is None:
            self._misses += 1
            return None

        if self.ttl_sec is not None:
            if time.time() - entry.created_at > self.ttl_sec:
                self._evict(key)
                self._misses += 1
                return None

        entry.hit_count += 1
        self._store.move_to_end(key)
        self._hits += 1
        return entry.value

    def put(self, key: str, value: Any) -> None:
        """Store a value.  Evicts LRU entry if at capacity."""
        payload_str = json.dumps(value, default=str) if not isinstance(value, str) else value
        size = len(payload_str.encode())

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            size_bytes=size,
        )

        if key in self._store:
            self._store.move_to_end(key)
        elif len(self._store) >= self.max_size:
            oldest_key, _ = next(iter(self._store.items()))
            self._evict(oldest_key)

        self._store[key] = entry

        if self.disk_dir:
            self._disk_put(key, entry)

    def invalidate(self, key: str) -> None:
        self._evict(key)

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> Dict[str, Any]:
        return {
            "size":      self.size,
            "max_size":  self.max_size,
            "hits":      self._hits,
            "misses":    self._misses,
            "hit_rate":  round(self.hit_rate, 4),
            "disk_dir":  str(self.disk_dir) if self.disk_dir else None,
        }

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def _disk_path(self, key: str) -> Path:
        return self.disk_dir / f"{key}.json"  # type: ignore[operator]

    def _disk_put(self, key: str, entry: CacheEntry) -> None:
        try:
            data = {
                "key":        entry.key,
                "value":      entry.value,
                "created_at": entry.created_at,
            }
            self._disk_path(key).write_text(
                json.dumps(data, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
        except (OSError, TypeError):
            pass

    def _disk_get(self, key: str) -> Optional[CacheEntry]:
        path = self._disk_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return CacheEntry(
                key=data["key"],
                value=data["value"],
                created_at=data.get("created_at", 0.0),
            )
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _evict(self, key: str) -> None:
        self._store.pop(key, None)
        if self.disk_dir:
            try:
                p = self._disk_path(key)
                if p.exists():
                    p.unlink()
            except OSError:
                pass
