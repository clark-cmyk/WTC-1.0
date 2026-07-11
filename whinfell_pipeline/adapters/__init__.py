"""Source adapters — Comet collector, Koyfin, Barchart, legacy parsers."""

from whinfell_pipeline.adapters.base import AdapterResult, SourceAdapter
from whinfell_pipeline.adapters.registry import get_adapter_for_payload

__all__ = ["AdapterResult", "SourceAdapter", "get_adapter_for_payload"]