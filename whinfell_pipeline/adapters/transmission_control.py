"""Transmission Control browser bundle adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from whinfell_pipeline.adapters.base import AdapterResult, SourceAdapter
from whinfell_pipeline.canonical import CanonicalRecord, DecisionBundle, ValidationStatus
from whinfell_pipeline.lineage import compute_lineage_hash
from whinfell_pipeline.version import CHINA_TRACK_ID, GLOBAL_TRACK_ID


class TransmissionControlAdapter(SourceAdapter):
    """Parse DecisionBundle JSON exported from Whinfell_Transmission_Control.html."""

    @property
    def adapter_id(self) -> str:
        return "transmission_control"

    def can_handle(self, raw: Any) -> bool:
        return isinstance(raw, Mapping) and "bundle_version" in raw and "snapshot_id" in raw

    def parse(self, raw: Any) -> AdapterResult:
        if not isinstance(raw, Mapping):
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Expected bundle dict"])

        bundle = DecisionBundle.from_mapping(raw)
        lineage = bundle.lineage_hash or compute_lineage_hash(raw)
        records: list[CanonicalRecord] = []
        warnings = list(bundle.warnings)

        if bundle.global_payload:
            g = bundle.global_payload
            records.append(
                CanonicalRecord(
                    track_id=GLOBAL_TRACK_ID,
                    snapshot_id=bundle.snapshot_id,
                    lineage_hash=lineage,
                    validation_status=bundle.validation_status,
                    as_of=bundle.as_of.replace(tzinfo=timezone.utc) if bundle.as_of.tzinfo is None else bundle.as_of,
                    source=bundle.source,
                    payload=g,
                    adapter_id=self.adapter_id,
                )
            )

        if bundle.china_payload:
            records.append(
                CanonicalRecord(
                    track_id=CHINA_TRACK_ID,
                    snapshot_id=bundle.snapshot_id,
                    lineage_hash=lineage,
                    validation_status=bundle.validation_status,
                    as_of=bundle.as_of.replace(tzinfo=timezone.utc) if bundle.as_of.tzinfo is None else bundle.as_of,
                    source=bundle.source,
                    payload=bundle.china_payload,
                    adapter_id=self.adapter_id,
                )
            )

        if bundle.execution_payload:
            records.append(
                CanonicalRecord(
                    track_id="execution",
                    snapshot_id=bundle.snapshot_id,
                    lineage_hash=lineage,
                    validation_status=bundle.validation_status,
                    as_of=bundle.as_of.replace(tzinfo=timezone.utc) if bundle.as_of.tzinfo is None else bundle.as_of,
                    source=bundle.source,
                    payload=bundle.execution_payload,
                    adapter_id=self.adapter_id,
                )
            )

        if not records:
            return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Empty bundle — no track payloads"])

        return AdapterResult(
            records=records,
            validation_status=bundle.validation_status,
            lineage_hash=lineage,
            warnings=warnings,
            wtm_export_block=bundle.wtm_export_v21,
        )