"""Parquet read/write for China Policy track (isolated from Global storage)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from china_policy_track.models import (
    ChinaPolicyObservation,
    GrowthMarketImpulse,
    PolicyHierarchyStrength,
    StateControlImpulse,
)
from china_policy_track.schema import china_policy_parquet_schema
from china_policy_track.version import (
    CHINA_DATA_ROOT,
    GLOBAL_DATA_ROOT,
    PARQUET_FILENAME,
    SCHEMA_VERSION,
    TRACK_ID,
)


def default_parquet_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / CHINA_DATA_ROOT / "v1" / PARQUET_FILENAME


def _assert_not_global_path(path: Path) -> None:
    normalized = str(path).replace("\\", "/")
    if f"/{GLOBAL_DATA_ROOT}/" in normalized and CHINA_DATA_ROOT not in normalized:
        raise ValueError(f"Refusing to write China Policy data to Global path: {path}")


def observation_to_row(obs: ChinaPolicyObservation) -> dict:
    as_of = obs.as_of
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = as_of.astimezone(timezone.utc)

    ph = obs.policy_hierarchy_strength
    sc = obs.state_control_impulse
    gm = obs.growth_market_impulse
    return {
        "track_id": obs.track_id,
        "schema_version": obs.schema_version,
        "observation_id": obs.observation_id,
        "as_of": as_of,
        "source": obs.source,
        "policy_hierarchy_strength": {
            "hierarchy_level": ph.hierarchy_level,
            "policy_strength": ph.policy_strength,
            "dominant_theme": ph.dominant_theme,
            "supporting_signals": list(ph.supporting_signals),
            "notes": ph.notes,
        },
        "state_control_impulse": {
            "impulse_score": sc.impulse_score,
            "regulatory_direction": sc.regulatory_direction,
            "state_intervention_level": sc.state_intervention_level,
            "key_controls": list(sc.key_controls),
            "notes": sc.notes,
        },
        "growth_market_impulse": {
            "growth_impulse_score": gm.growth_impulse_score,
            "market_sentiment": gm.market_sentiment,
            "liquidity_impulse": gm.liquidity_impulse,
            "key_indicators": list(gm.key_indicators),
            "notes": gm.notes,
        },
    }


def row_to_observation(batch: dict) -> ChinaPolicyObservation:
    as_of = batch["as_of"]
    if isinstance(as_of, datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return ChinaPolicyObservation(
        observation_id=batch["observation_id"],
        as_of=as_of,
        source=batch["source"],
        policy_hierarchy_strength=PolicyHierarchyStrength.from_mapping(
            batch["policy_hierarchy_strength"]
        ),
        state_control_impulse=StateControlImpulse.from_mapping(batch["state_control_impulse"]),
        growth_market_impulse=GrowthMarketImpulse.from_mapping(batch["growth_market_impulse"]),
        schema_version=batch.get("schema_version", SCHEMA_VERSION),
        track_id=batch.get("track_id", TRACK_ID),
    )


def observations_to_table(observations: Sequence[ChinaPolicyObservation]) -> pa.Table:
    schema = china_policy_parquet_schema()
    rows = [observation_to_row(o) for o in observations]
    return pa.Table.from_pylist(rows, schema=schema)


def write_observations(
    observations: Sequence[ChinaPolicyObservation],
    path: Path | None = None,
    *,
    append: bool = True,
) -> Path:
    out = path or default_parquet_path()
    _assert_not_global_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    new_table = observations_to_table(observations)
    if append and out.exists():
        existing = pq.read_table(out)
        if not existing.schema.equals(new_table.schema):
            raise ValueError("Existing Parquet schema version mismatch — use a new file")
        combined = pa.concat_tables([existing, new_table])
        pq.write_table(combined, out, compression="snappy")
    else:
        pq.write_table(new_table, out, compression="snappy")
    return out


def read_observations(path: Path | None = None) -> list[ChinaPolicyObservation]:
    src = path or default_parquet_path()
    if not src.exists():
        return []
    table = pq.read_table(src)
    return [row_to_observation(batch) for batch in table.to_pylist()]