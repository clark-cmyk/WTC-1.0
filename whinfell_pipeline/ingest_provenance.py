"""ARCH-1 M3 — aggregate staged route metadata into hydration ingest_provenance."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_OUTPUT_KIND_MAP = {
    "snapshot_validation": "snapshot",
    "universe_membership": "snapshot",
    "historical_timeseries": "historical_timeseries",
    "correlation_series": "correlation_series",
    "curve_series": "curve_series",
    "derived_signals": "derived_signals",
}


def map_output_kind(raw_kinds: list[str] | None) -> str:
    """Map router output_kinds list to canonical taxonomy primary kind."""
    kinds = raw_kinds or []
    for raw in kinds:
        mapped = _OUTPUT_KIND_MAP.get(str(raw))
        if mapped:
            return mapped
    if kinds:
        return str(kinds[0])
    return "unknown"


def _parse_staged_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def collect_staged_ingest_provenance(
    staged_root: Path,
    *,
    window_hours: int = 48,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Scan staged `.meta.json` sidecars and aggregate route provenance."""
    root = staged_root.expanduser().resolve()
    cutoff = (as_of or datetime.now(timezone.utc)) - timedelta(hours=window_hours)

    entries: list[dict[str, Any]] = []
    output_kind_counts: dict[str, int] = {}
    source_classes: set[str] = set()

    if not root.is_dir():
        return {
            "window_hours": window_hours,
            "staged_count": 0,
            "entries": [],
            "output_kinds": {},
            "primary_output_kind": "unknown",
            "source_classes": [],
        }

    for meta_path in sorted(root.glob("source=*/dataset=*/*.meta.json")):
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("status") != "staged":
            continue
        staged_at = _parse_staged_at(str(payload.get("staged_at") or ""))
        if staged_at and staged_at < cutoff:
            continue

        route = payload.get("route") or {}
        if not isinstance(route, dict) or not route.get("source_class"):
            continue

        raw_kinds = [str(k) for k in (route.get("output_kinds") or [])]
        output_kind = map_output_kind(raw_kinds)
        output_kind_counts[output_kind] = output_kind_counts.get(output_kind, 0) + 1
        source_class = str(route.get("source_class") or "")
        source_classes.add(source_class)

        entries.append({
            "filename": str(payload.get("filename") or meta_path.name.replace(".meta.json", "")),
            "dataset": str(payload.get("dataset") or ""),
            "source": str(payload.get("source") or ""),
            "source_class": source_class,
            "output_kind": output_kind,
            "output_kinds": raw_kinds,
            "vendor": str(route.get("vendor") or ""),
            "priority": str(route.get("priority") or ""),
            "canonical_assets": list(route.get("canonical_assets") or []),
            "staged_at": staged_at.isoformat() if staged_at else "",
            "sha256": str(payload.get("sha256") or ""),
        })

    primary = "derived_signals"
    if output_kind_counts:
        primary = max(output_kind_counts, key=lambda k: output_kind_counts[k])

    return {
        "window_hours": window_hours,
        "staged_count": len(entries),
        "entries": entries,
        "output_kinds": output_kind_counts,
        "primary_output_kind": primary,
        "source_classes": sorted(source_classes),
    }