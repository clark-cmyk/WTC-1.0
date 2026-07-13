"""Parquet schema for China Policy track observations."""

from __future__ import annotations

import pyarrow as pa

from china_policy_track.version import SCHEMA_VERSION, TRACK_ID


def china_policy_parquet_schema() -> pa.Schema:
    """Versioned Parquet schema — nested structs per dimension."""
    return pa.schema(
        [
            ("track_id", pa.string()),
            ("schema_version", pa.string()),
            ("observation_id", pa.string()),
            ("as_of", pa.timestamp("us", tz="UTC")),
            ("source", pa.string()),
            (
                "policy_hierarchy_strength",
                pa.struct(
                    [
                        ("hierarchy_level", pa.string()),
                        ("policy_strength", pa.int32()),
                        ("dominant_theme", pa.string()),
                        ("supporting_signals", pa.list_(pa.string())),
                        ("notes", pa.string()),
                    ]
                ),
            ),
            (
                "state_control_impulse",
                pa.struct(
                    [
                        ("impulse_score", pa.int32()),
                        ("regulatory_direction", pa.string()),
                        ("state_intervention_level", pa.string()),
                        ("key_controls", pa.list_(pa.string())),
                        ("notes", pa.string()),
                    ]
                ),
            ),
            (
                "growth_market_impulse",
                pa.struct(
                    [
                        ("growth_impulse_score", pa.int32()),
                        ("market_sentiment", pa.string()),
                        ("liquidity_impulse", pa.string()),
                        ("key_indicators", pa.list_(pa.string())),
                        ("notes", pa.string()),
                    ]
                ),
            ),
        ],
        metadata={
            b"track": TRACK_ID.encode(),
            b"schema_version": SCHEMA_VERSION.encode(),
            b"description": b"China Policy track - isolated from Global track storage",
        },
    )


def schema_metadata_dict() -> dict[str, str]:
    sch = china_policy_parquet_schema()
    return {
        "track_id": TRACK_ID,
        "schema_version": SCHEMA_VERSION,
        "field_names": ",".join(sch.names),
        "parquet_metadata": str(sch.metadata),
    }