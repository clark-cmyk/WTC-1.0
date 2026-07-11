"""Global track observation model (WTM EXPORT v2.1 aligned)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

from whinfell_pipeline.version import GLOBAL_SCHEMA_VERSION, GLOBAL_TRACK_ID


def _clamp_int(value: Any, lo: int, hi: int, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _norm_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


@dataclass(frozen=True)
class GlobalObservation:
    """Global Whinfell transmission observation with SQ3 lineage fields."""

    observation_id: str
    as_of: datetime
    source: str
    whinfell_score: int
    transmission_state: str
    regime_tag: str
    snapshot_id: str = ""
    lineage_hash: str = ""
    validation_status: str = "parsed"
    sq3_score: int | None = None
    sq3_band: str = ""
    gate_status: str = ""
    key_observation: str = ""
    policy_strength: int | None = None
    state_impulse_score: int | None = None
    growth_impulse_score: int | None = None
    schema_version: str = GLOBAL_SCHEMA_VERSION
    track_id: str = GLOBAL_TRACK_ID

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GlobalObservation:
        as_of_raw = data.get("as_of") or data.get("timestamp")
        if isinstance(as_of_raw, datetime):
            as_of = as_of_raw
        else:
            as_of = datetime.fromisoformat(_norm_str(as_of_raw, datetime.utcnow().isoformat()))

        score = _clamp_int(data.get("whinfell_score", data.get("whinfellScore")), 0, 100, 0)

        return cls(
            observation_id=_norm_str(data.get("observation_id"), "global-unknown"),
            as_of=as_of,
            source=_norm_str(data.get("source"), "manual"),
            whinfell_score=score or 0,
            transmission_state=_norm_str(data.get("transmission_state", data.get("transmissionState")), "normal"),
            regime_tag=_norm_str(data.get("regime_tag", data.get("regimeTag"))),
            snapshot_id=_norm_str(data.get("snapshot_id")),
            lineage_hash=_norm_str(data.get("lineage_hash")),
            validation_status=_norm_str(data.get("validation_status"), "parsed"),
            sq3_score=_clamp_int(data.get("sq3_score"), 0, 100),
            sq3_band=_norm_str(data.get("sq3_band")),
            gate_status=_norm_str(data.get("gate_status", data.get("gateStatus"))),
            key_observation=_norm_str(data.get("key_observation", data.get("keyObservation"))),
            policy_strength=_clamp_int(data.get("policy_strength"), 0, 100),
            state_impulse_score=_clamp_int(data.get("state_impulse_score"), -100, 100),
            growth_impulse_score=_clamp_int(data.get("growth_impulse_score"), 0, 100),
            schema_version=_norm_str(data.get("schema_version"), GLOBAL_SCHEMA_VERSION),
            track_id=_norm_str(data.get("track_id"), GLOBAL_TRACK_ID),
        )