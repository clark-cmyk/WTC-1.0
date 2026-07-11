"""Parquet read/write for Global track (isolated from China Policy storage)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from whinfell_pipeline.global_track.models import GlobalObservation
from whinfell_pipeline.global_track.schema import global_parquet_schema
from whinfell_pipeline.version import (
    CHINA_TRACK_ID,
    GLOBAL_DATA_ROOT,
    GLOBAL_PARQUET_FILENAME,
    GLOBAL_SCHEMA_VERSION,
    GLOBAL_TRACK_ID,
)


def default_parquet_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / GLOBAL_DATA_ROOT / "v1" / GLOBAL_PARQUET_FILENAME


def _assert_not_china_path(path: Path) -> None:
    normalized = str(path).replace("\\", "/")
    if f"/{CHINA_TRACK_ID.replace('_', '/')}/" in normalized or "/data/china_policy/" in normalized:
        raise ValueError(f"Refusing to write Global data to China path: {path}")


def observation_to_row(obs: GlobalObservation) -> dict:
    as_of = obs.as_of
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = as_of.astimezone(timezone.utc)

    def _nullable_int(val: int | None) -> int | None:
        return int(val) if val is not None else None

    return {
        "track_id": obs.track_id,
        "schema_version": obs.schema_version,
        "observation_id": obs.observation_id,
        "snapshot_id": obs.snapshot_id,
        "lineage_hash": obs.lineage_hash,
        "validation_status": obs.validation_status,
        "as_of": as_of,
        "source": obs.source,
        "whinfell_score": int(obs.whinfell_score),
        "transmission_state": obs.transmission_state,
        "regime_tag": obs.regime_tag,
        "sq3_score": _nullable_int(obs.sq3_score) if obs.sq3_score is not None else None,
        "sq3_band": obs.sq3_band or "",
        "gate_status": obs.gate_status or "",
        "key_observation": obs.key_observation or "",
        "policy_strength": _nullable_int(obs.policy_strength) if obs.policy_strength is not None else None,
        "state_impulse_score": _nullable_int(obs.state_impulse_score) if obs.state_impulse_score is not None else None,
        "growth_impulse_score": _nullable_int(obs.growth_impulse_score) if obs.growth_impulse_score is not None else None,
    }


def row_to_observation(batch: dict) -> GlobalObservation:
    as_of = batch["as_of"]
    if isinstance(as_of, datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return GlobalObservation.from_mapping({**batch, "as_of": as_of})


def observations_to_table(observations: Sequence[GlobalObservation]) -> pa.Table:
    schema = global_parquet_schema()
    rows = [observation_to_row(o) for o in observations]
    return pa.Table.from_pylist(rows, schema=schema)


def write_observations(
    observations: Sequence[GlobalObservation],
    path: Path | None = None,
    *,
    append: bool = True,
) -> Path:
    out = path or default_parquet_path()
    _assert_not_china_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    new_table = observations_to_table(observations)
    if append and out.exists():
        existing = pq.read_table(out)
        if existing.num_rows == 0:
            pq.write_table(new_table, out, compression="snappy")
        elif not existing.schema.equals(new_table.schema):
            if existing.num_rows > 0:
                raise ValueError(
                    f"Existing Global Parquet schema mismatch (want {GLOBAL_SCHEMA_VERSION}) "
                    "— migrate or use --no-append"
                )
            pq.write_table(new_table, out, compression="snappy")
            return out
        else:
            combined = pa.concat_tables([existing, new_table])
            pq.write_table(combined, out, compression="snappy")
    else:
        pq.write_table(new_table, out, compression="snappy")
    return out


def read_observations(path: Path | None = None) -> list[GlobalObservation]:
    src = path or default_parquet_path()
    if not src.exists():
        return []
    table = pq.read_table(src)
    return [row_to_observation(batch) for batch in table.to_pylist()]