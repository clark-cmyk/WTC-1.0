"""Canonical decision schema with lineage and validation status."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class ValidationStatus(str, Enum):
    PARSED = "parsed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class CanonicalRecord:
    """Normalized intermediate record before track-specific Parquet write."""

    track_id: str
    snapshot_id: str
    lineage_hash: str
    validation_status: ValidationStatus
    as_of: datetime
    source: str
    payload: Mapping[str, Any]
    adapter_id: str = ""
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["validation_status"] = self.validation_status.value
        d["as_of"] = self.as_of.isoformat()
        return d


@dataclass
class DecisionBundle:
    """Dual-track decision snapshot from Transmission Control or batch ingest."""

    bundle_version: str
    snapshot_id: str
    lineage_hash: str
    validation_status: ValidationStatus
    as_of: datetime
    source: str
    global_payload: dict[str, Any] = field(default_factory=dict)
    china_payload: dict[str, Any] = field(default_factory=dict)
    execution_payload: dict[str, Any] = field(default_factory=dict)
    wtm_export_v21: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_version": self.bundle_version,
            "snapshot_id": self.snapshot_id,
            "lineage_hash": self.lineage_hash,
            "validation_status": self.validation_status.value,
            "as_of": self.as_of.isoformat(),
            "source": self.source,
            "global": self.global_payload,
            "china": self.china_payload,
            "execution": self.execution_payload,
            "wtm_export_v21": self.wtm_export_v21,
            "warnings": self.warnings,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> DecisionBundle:
        from whinfell_pipeline.version import BUNDLE_VERSION

        as_of_raw = data.get("as_of") or data.get("generated_at")
        if isinstance(as_of_raw, datetime):
            as_of = as_of_raw
        else:
            as_of = datetime.fromisoformat(str(as_of_raw).replace("Z", "+00:00"))

        status_raw = str(data.get("validation_status", ValidationStatus.PARSED.value)).lower()
        try:
            status = ValidationStatus(status_raw)
        except ValueError:
            status = ValidationStatus.PARTIAL

        return cls(
            bundle_version=str(data.get("bundle_version", BUNDLE_VERSION)),
            snapshot_id=str(data.get("snapshot_id", "snap-unknown")),
            lineage_hash=str(data.get("lineage_hash", "")),
            validation_status=status,
            as_of=as_of,
            source=str(data.get("source", "transmission_control")),
            global_payload=dict(data.get("global", {})),
            china_payload=dict(data.get("china", {})),
            execution_payload=dict(data.get("execution", {})),
            wtm_export_v21=str(data.get("wtm_export_v21", "")),
            warnings=list(data.get("warnings", [])),
        )