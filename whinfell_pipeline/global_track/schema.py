"""Parquet schema for Global track observations (v2.1.0)."""

from __future__ import annotations

import pyarrow as pa

from whinfell_pipeline.version import GLOBAL_SCHEMA_VERSION, GLOBAL_TRACK_ID


def global_parquet_schema() -> pa.Schema:
    """Versioned Parquet schema — WTM EXPORT v2.1 + lineage columns."""
    return pa.schema(
        [
            ("track_id", pa.string()),
            ("schema_version", pa.string()),
            ("observation_id", pa.string()),
            ("snapshot_id", pa.string()),
            ("lineage_hash", pa.string()),
            ("validation_status", pa.string()),
            ("as_of", pa.timestamp("us", tz="UTC")),
            ("source", pa.string()),
            ("whinfell_score", pa.int32()),
            ("transmission_state", pa.string()),
            ("regime_tag", pa.string()),
            ("sq3_score", pa.int32()),
            ("sq3_band", pa.string()),
            ("gate_status", pa.string()),
            ("key_observation", pa.string()),
            ("policy_strength", pa.int32()),
            ("state_impulse_score", pa.int32()),
            ("growth_impulse_score", pa.int32()),
        ],
        metadata={
            b"track": GLOBAL_TRACK_ID.encode(),
            b"schema_version": GLOBAL_SCHEMA_VERSION.encode(),
            b"description": b"Global track - WTM EXPORT v2.1 with SQ3 lineage",
        },
    )