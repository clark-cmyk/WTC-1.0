"""Legacy parser adapter — wraps china_policy_track.data_parser + WTM text exports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from whinfell_pipeline.adapters.base import AdapterResult, SourceAdapter
from whinfell_pipeline.canonical import CanonicalRecord, ValidationStatus
from whinfell_pipeline.global_track.parser import parse_wtm_export_text
from whinfell_pipeline.lineage import compute_lineage_hash, make_snapshot_id
from whinfell_pipeline.version import CHINA_TRACK_ID, GLOBAL_TRACK_ID


class LegacyParserAdapter(SourceAdapter):
    """Dispatch str → Perplexity/WTM blocks; dict → china_policy_track.data_parser."""

    @property
    def adapter_id(self) -> str:
        return "legacy_parser"

    def can_handle(self, raw: Any) -> bool:
        if isinstance(raw, str):
            upper = raw.upper()
            return "WTM EXPORT" in upper or "CHINA POLICY EXPORT" in upper
        if isinstance(raw, Mapping):
            if raw.get("bundle_version"):
                return False
            if raw.get("collector_version"):
                return False
            return True
        return False

    def parse(self, raw: Any) -> AdapterResult:
        lineage = compute_lineage_hash(raw)
        records: list[CanonicalRecord] = []
        warnings: list[str] = []
        wtm_block = ""
        status = ValidationStatus.PARSED

        if isinstance(raw, str):
            text = raw.replace("\r\n", "\n")

            if "CHINA POLICY EXPORT" in text.upper():
                try:
                    from china_policy_track.data_parser import parse_perplexity_text

                    obs = parse_perplexity_text(text)
                    records.append(
                        CanonicalRecord(
                            track_id=CHINA_TRACK_ID,
                            snapshot_id=obs.observation_id,
                            lineage_hash=lineage,
                            validation_status=ValidationStatus.PARSED,
                            as_of=obs.as_of.replace(tzinfo=timezone.utc) if obs.as_of.tzinfo is None else obs.as_of,
                            source=obs.source,
                            payload=obs.to_dict(),
                            adapter_id=self.adapter_id,
                        )
                    )
                except Exception as exc:
                    warnings.append(f"China text parse: {exc}")
                    status = ValidationStatus.PARTIAL

            if "WTM EXPORT" in text.upper():
                try:
                    parsed = parse_wtm_export_text(text)
                    wtm_block = parsed.export_block
                    records.append(
                        CanonicalRecord(
                            track_id=GLOBAL_TRACK_ID,
                            snapshot_id=parsed.observation_id,
                            lineage_hash=lineage,
                            validation_status=parsed.validation_status,
                            as_of=parsed.as_of,
                            source=parsed.source,
                            payload=parsed.to_payload_dict(),
                            adapter_id=self.adapter_id,
                            warnings=tuple(parsed.warnings),
                        )
                    )
                except Exception as exc:
                    warnings.append(f"WTM text parse: {exc}")
                    status = ValidationStatus.PARTIAL

            if not records:
                return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["No export blocks found"])

            return AdapterResult(records=records, validation_status=status, lineage_hash=lineage, warnings=warnings, wtm_export_block=wtm_block)

        if isinstance(raw, Mapping):
            try:
                from china_policy_track.data_parser import parse_input

                obs = parse_input(raw)
                records.append(
                    CanonicalRecord(
                        track_id=CHINA_TRACK_ID,
                        snapshot_id=obs.observation_id,
                        lineage_hash=lineage,
                        validation_status=ValidationStatus.PARSED,
                        as_of=obs.as_of.replace(tzinfo=timezone.utc) if obs.as_of.tzinfo is None else obs.as_of,
                        source=obs.source,
                        payload=obs.to_dict(),
                        adapter_id=self.adapter_id,
                    )
                )
                return AdapterResult(records=records, validation_status=ValidationStatus.PARSED, lineage_hash=lineage)
            except Exception as exc:
                return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=[str(exc)])

        return AdapterResult(validation_status=ValidationStatus.FAILED, warnings=["Unsupported payload type"])