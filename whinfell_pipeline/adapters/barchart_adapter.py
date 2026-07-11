"""Barchart structured export adapter (BTC execution + China Policy)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from whinfell_pipeline.adapters.base import AdapterResult, SourceAdapter
from whinfell_pipeline.canonical import CanonicalRecord, ValidationStatus
from whinfell_pipeline.lineage import compute_lineage_hash, make_snapshot_id
from whinfell_pipeline.version import CHINA_TRACK_ID, GLOBAL_TRACK_ID


def _parse_as_of(data: Mapping[str, Any]) -> datetime:
    raw = data.get("as_of") or data.get("timestamp") or data.get("collected_at")
    if raw is None:
        return datetime.now(timezone.utc)
    if isinstance(raw, datetime):
        dt = raw
    else:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_china_payload(data: Mapping[str, Any]) -> bool:
    return bool(
        data.get("policy_hierarchy_strength")
        or data.get("policy_strength")
        or data.get("state_control_impulse")
        or data.get("growth_market_impulse")
    )


def _is_execution_payload(data: Mapping[str, Any]) -> bool:
    return bool(
        data.get("near_month")
        or data.get("nearMonth")
        or data.get("basis_spread")
        or data.get("basisSpread")
        or data.get("far_month")
        or data.get("farMonth")
    )


class BarchartAdapter(SourceAdapter):
    """Parse Barchart JSON into execution or China canonical records."""

    @property
    def adapter_id(self) -> str:
        return "barchart"

    def can_handle(self, raw: Any) -> bool:
        if not isinstance(raw, Mapping):
            return False
        source = str(raw.get("source", "")).lower()
        if source == "barchart":
            return True
        return _is_execution_payload(raw) or (
            _is_china_payload(raw) and str(raw.get("source", "")).lower() in ("", "barchart")
        )

    def parse(self, raw: Any) -> AdapterResult:
        if not isinstance(raw, Mapping):
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Expected dict"])

        as_of = _parse_as_of(raw)
        lineage = compute_lineage_hash(raw)
        snapshot_id = str(raw.get("observation_id", make_snapshot_id("barchart")))
        warnings: list[str] = []

        if _is_china_payload(raw):
            try:
                from china_policy_track.data_parser import parse_koyfin_barchart_export

                obs = parse_koyfin_barchart_export({**raw, "source": "barchart"})
                record = CanonicalRecord(
                    track_id=CHINA_TRACK_ID,
                    snapshot_id=snapshot_id,
                    lineage_hash=lineage,
                    validation_status=ValidationStatus.PARSED,
                    as_of=as_of,
                    source="barchart",
                    payload=obs.to_dict(),
                    adapter_id=self.adapter_id,
                )
                return AdapterResult(records=[record], validation_status=ValidationStatus.PARSED, lineage_hash=lineage)
            except Exception as exc:
                return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=[f"China Barchart parse failed: {exc}"])

        execution = {
            "near_month": raw.get("near_month", raw.get("nearMonth", "")),
            "far_month": raw.get("far_month", raw.get("farMonth", "")),
            "basis_spread": raw.get("basis_spread", raw.get("basisSpread", "")),
            "ref_low": raw.get("ref_low", raw.get("refLow", "")),
            "ref_mid": raw.get("ref_mid", raw.get("refMid", "")),
            "ref_high": raw.get("ref_high", raw.get("refHigh", "")),
            "page_url": raw.get("_page_url", raw.get("page_url", "")),
        }
        if not any(execution.values()):
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["No Barchart execution fields found"])

        record = CanonicalRecord(
            track_id="execution",
            snapshot_id=snapshot_id,
            lineage_hash=lineage,
            validation_status=ValidationStatus.PARSED,
            as_of=as_of,
            source="barchart",
            payload=execution,
            adapter_id=self.adapter_id,
            warnings=tuple(warnings),
        )
        return AdapterResult(records=[record], validation_status=ValidationStatus.PARSED, lineage_hash=lineage, warnings=warnings)