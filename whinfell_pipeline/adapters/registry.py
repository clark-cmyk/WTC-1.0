"""Adapter registry — select SourceAdapter for a raw payload."""

from __future__ import annotations

from typing import Any, Sequence

from whinfell_pipeline.adapters.barchart_adapter import BarchartAdapter
from whinfell_pipeline.adapters.base import SourceAdapter
from whinfell_pipeline.adapters.comet_collector import CometCollectorAdapter
from whinfell_pipeline.adapters.koyfin_adapter import KoyfinAdapter
from whinfell_pipeline.adapters.legacy_parser import LegacyParserAdapter
from whinfell_pipeline.adapters.transmission_control import TransmissionControlAdapter

_DEFAULT_ADAPTERS: Sequence[SourceAdapter] = (
    TransmissionControlAdapter(),
    CometCollectorAdapter(),
    KoyfinAdapter(),
    BarchartAdapter(),
    LegacyParserAdapter(),
)


def get_adapter_for_payload(raw: Any, adapters: Sequence[SourceAdapter] | None = None) -> SourceAdapter | None:
    """Return the first adapter that can handle the payload."""
    for adapter in adapters or _DEFAULT_ADAPTERS:
        if adapter.can_handle(raw):
            return adapter
    return None


def parse_with_best_adapter(raw: Any) -> tuple[SourceAdapter | None, Any]:
    """Parse raw payload using the best-matching adapter."""
    from whinfell_pipeline.adapters.base import AdapterResult

    adapter = get_adapter_for_payload(raw)
    if adapter is None:
        return None, AdapterResult(warnings=["No adapter matched payload"])
    return adapter, adapter.parse(raw)