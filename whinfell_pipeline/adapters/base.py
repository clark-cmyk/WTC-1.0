"""SourceAdapter interface for the Whinfell data pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from whinfell_pipeline.canonical import CanonicalRecord, ValidationStatus


@dataclass
class AdapterResult:
    """Output of a SourceAdapter parse operation."""

    records: list[CanonicalRecord] = field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.PARSED
    lineage_hash: str = ""
    warnings: list[str] = field(default_factory=list)
    wtm_export_block: str = ""

    @property
    def ok(self) -> bool:
        return self.validation_status != ValidationStatus.FAILED and bool(self.records)


class SourceAdapter(ABC):
    """Wrap a data source and produce canonical records."""

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Stable adapter identifier for audit logs."""

    @abstractmethod
    def can_handle(self, raw: Any) -> bool:
        """Return True if this adapter can parse the raw payload."""

    @abstractmethod
    def parse(self, raw: Any) -> AdapterResult:
        """Parse raw input into canonical records."""