"""Koyfin structured export adapter (Global + China Policy tracks)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from whinfell_pipeline.adapters.base import AdapterResult, SourceAdapter
from whinfell_pipeline.canonical import CanonicalRecord, ValidationStatus
from whinfell_pipeline.lineage import compute_lineage_hash, make_snapshot_id
from whinfell_pipeline.version import CHINA_TRACK_ID, GLOBAL_TRACK_ID


def _parse_as_of(data: Mapping[str, Any]) -> datetime:
    raw = data.get("as_of") or data.get("timestamp")
    if isinstance(raw, datetime):
        dt = raw
    else:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _detect_track(data: Mapping[str, Any]) -> str:
    hint = str(data.get("_track_hint", "")).lower()
    if hint in (GLOBAL_TRACK_ID, CHINA_TRACK_ID):
        return hint
    if "policy_hierarchy_strength" in data or "policy_strength" in data:
        return CHINA_TRACK_ID
    if "whinfell_score" in data:
        return GLOBAL_TRACK_ID
    return GLOBAL_TRACK_ID


def _normalize_global_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    score = data.get("whinfell_score", data.get("whinfellScore"))
    return {
        "observation_id": str(data.get("observation_id", make_snapshot_id("global"))),
        "whinfell_score": int(score) if score is not None else None,
        "transmission_state": str(data.get("transmission_state", data.get("transmissionState", ""))).lower(),
        "regime_tag": str(data.get("regime_tag", data.get("regimeTag", ""))),
        "key_observation": str(data.get("key_observation", data.get("keyObservation", ""))),
        "sq3_score": data.get("sq3_score"),
        "sq3_band": data.get("sq3_band"),
        "page_url": data.get("_page_url", ""),
    }


def _normalize_china_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    return dict(data)


class KoyfinAdapter(SourceAdapter):
    """Parse Koyfin JSON exports into canonical records."""

    @property
    def adapter_id(self) -> str:
        return "koyfin"

    def can_handle(self, raw: Any) -> bool:
        if not isinstance(raw, Mapping):
            return False
        source = str(raw.get("source", "")).lower()
        if source == "koyfin":
            return True
        if raw.get("_track_hint") and "collector_version" not in raw:
            return False
        return "whinfell_score" in raw or "policy_hierarchy_strength" in raw or "policy_strength" in raw

    def parse(self, raw: Any) -> AdapterResult:
        if not isinstance(raw, Mapping):
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Expected dict"])

        track = _detect_track(raw)
        as_of = _parse_as_of(raw)
        lineage = compute_lineage_hash(raw)
        snapshot_id = str(raw.get("observation_id", make_snapshot_id(track.split("_")[0])))
        warnings: list[str] = []

        if track == CHINA_TRACK_ID:
            try:
                from china_policy_track.data_parser import parse_koyfin_barchart_export

                obs = parse_koyfin_barchart_export({**raw, "source": "koyfin"})
                payload = obs.to_dict()
                status = ValidationStatus.PARSED
            except Exception as exc:
                return AdapterResult(
                    validation_status=ValidationStatus.FAILED,
                    warnings=[f"China Koyfin parse failed: {exc}"],
                )
        else:
            payload = _normalize_global_payload(raw)
            missing = [k for k in ("whinfell_score", "transmission_state", "regime_tag") if not payload.get(k)]
            if missing:
                warnings.append(f"Missing global fields: {', '.join(missing)}")
                status = ValidationStatus.PARTIAL
            else:
                status = ValidationStatus.PARSED

        record = CanonicalRecord(
            track_id=track,
            snapshot_id=snapshot_id,
            lineage_hash=lineage,
            validation_status=status,
            as_of=as_of,
            source="koyfin",
            payload=payload,
            adapter_id=self.adapter_id,
            warnings=tuple(warnings),
        )
        return AdapterResult(
            records=[record],
            validation_status=status,
            lineage_hash=lineage,
            warnings=warnings,
        )