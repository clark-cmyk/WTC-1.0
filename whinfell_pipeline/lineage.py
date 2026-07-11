"""Lineage hashing for auditable data provenance."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Stable JSON serialization for hashing."""
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def compute_lineage_hash(payload: Any) -> str:
    """SHA-256 lineage hash over canonical JSON representation."""
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def make_snapshot_id(prefix: str = "snap") -> str:
    """Generate a time-based snapshot identifier."""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}_{ts}"