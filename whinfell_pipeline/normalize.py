"""Convert canonical records to track-specific observations for Parquet."""

from __future__ import annotations

from typing import Any

from china_policy_track.models import ChinaPolicyObservation

from whinfell_pipeline.canonical import CanonicalRecord
from whinfell_pipeline.global_track.models import GlobalObservation
from whinfell_pipeline.version import CHINA_TRACK_ID, GLOBAL_TRACK_ID


def canonical_to_global(record: CanonicalRecord) -> GlobalObservation:
    payload = dict(record.payload)
    payload.setdefault("observation_id", record.snapshot_id)
    payload.setdefault("snapshot_id", record.snapshot_id)
    payload.setdefault("lineage_hash", record.lineage_hash)
    payload.setdefault("validation_status", record.validation_status.value)
    payload.setdefault("as_of", record.as_of)
    payload.setdefault("source", record.source)
    return GlobalObservation.from_mapping(payload)


def canonical_to_china(record: CanonicalRecord) -> ChinaPolicyObservation:
    payload = dict(record.payload)
    payload.setdefault("observation_id", record.snapshot_id)
    payload.setdefault("as_of", record.as_of)
    payload.setdefault("source", record.source)

    if "policy_hierarchy_strength" not in payload and payload.get("policy_strength") is not None:
        return ChinaPolicyObservation.from_mapping(
            {
                "observation_id": record.snapshot_id,
                "as_of": record.as_of.isoformat(),
                "source": record.source,
                "policy_strength": payload.get("policy_strength"),
                "state_impulse_score": payload.get("state_impulse_score", payload.get("state_impulse")),
                "growth_impulse_score": payload.get("growth_impulse_score", payload.get("growth_impulse")),
                "dominant_theme": payload.get("china_regime_tag", payload.get("dominant_theme", "")),
            }
        )
    return ChinaPolicyObservation.from_mapping(payload)


def partition_records(
    records: list[CanonicalRecord],
) -> tuple[list[GlobalObservation], list[ChinaPolicyObservation], list[dict[str, Any]]]:
    """Split canonical records by track_id."""
    global_obs: list[GlobalObservation] = []
    china_obs: list[ChinaPolicyObservation] = []
    execution: list[dict[str, Any]] = []

    for rec in records:
        if rec.track_id == GLOBAL_TRACK_ID:
            global_obs.append(canonical_to_global(rec))
        elif rec.track_id == CHINA_TRACK_ID:
            china_obs.append(canonical_to_china(rec))
        elif rec.track_id == "execution":
            execution.append(dict(rec.payload))

    return global_obs, china_obs, execution