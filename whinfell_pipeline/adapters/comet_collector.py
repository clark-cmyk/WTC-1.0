"""Comet first-pass collector envelope — routes to channel adapters."""

from __future__ import annotations

from typing import Any, Mapping

from whinfell_pipeline.adapters.base import AdapterResult, SourceAdapter
from whinfell_pipeline.adapters.barchart_adapter import BarchartAdapter
from whinfell_pipeline.adapters.koyfin_adapter import KoyfinAdapter
from whinfell_pipeline.canonical import ValidationStatus
from whinfell_pipeline.lineage import compute_lineage_hash
from whinfell_pipeline.version import COMET_COLLECTOR_ID, COMET_COLLECTOR_VERSION


def is_comet_collector_envelope(raw: Any) -> bool:
    if not isinstance(raw, Mapping):
        return False
    return (
        raw.get("collector_id") == COMET_COLLECTOR_ID
        or "collector_version" in raw
        and "source_channel" in raw
        and "payload" in raw
    )


class CometCollectorAdapter(SourceAdapter):
    """Wrap Comet's first-pass collector and delegate by source_channel."""

    def __init__(self) -> None:
        self._koyfin = KoyfinAdapter()
        self._barchart = BarchartAdapter()

    @property
    def adapter_id(self) -> str:
        return "comet_collector"

    def can_handle(self, raw: Any) -> bool:
        return is_comet_collector_envelope(raw)

    def parse(self, raw: Any) -> AdapterResult:
        if not isinstance(raw, Mapping):
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Expected dict envelope"])

        version = str(raw.get("collector_version", ""))
        if version and version != COMET_COLLECTOR_VERSION:
            return AdapterResult(
                validation_status=ValidationStatus.FAILED,
                warnings=[f"Unsupported collector_version: {version}"],
            )

        channel = str(raw.get("source_channel", "")).lower()
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Missing payload dict"])

        delegate: SourceAdapter | None = None
        if channel == "koyfin":
            delegate = self._koyfin
        elif channel == "barchart":
            delegate = self._barchart

        if delegate is None:
            return AdapterResult(
                validation_status=ValidationStatus.FAILED,
                warnings=[f"Unsupported source_channel: {channel}"],
            )

        enriched = dict(payload)
        enriched.setdefault("source", channel)
        if raw.get("page_url"):
            enriched["_page_url"] = raw["page_url"]
        if raw.get("collected_at"):
            ts = str(raw["collected_at"]).replace("Z", "+00:00")
            enriched.setdefault("timestamp", ts)
            enriched.setdefault("as_of", ts)

        track_hint = str(raw.get("track", "")).lower()
        if track_hint:
            enriched["_track_hint"] = track_hint

        result = delegate.parse(enriched)
        lineage = compute_lineage_hash(raw)
        result.lineage_hash = lineage
        for rec in result.records:
            if not rec.lineage_hash:
                object.__setattr__(rec, "lineage_hash", lineage)
        return result