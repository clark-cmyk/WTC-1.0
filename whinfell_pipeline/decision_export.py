"""WTM EXPORT v2.1 decision export writer (delegates to locked contract)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from whinfell_pipeline.export_contract import ProvenanceMeta, build_wtm_export_v21 as _build_contract


def write_wtm_export_v21(
    global_data: Mapping[str, Any],
    *,
    china_data: Mapping[str, Any] | None = None,
    tracer_horizons: Mapping[str, Mapping[str, str]] | None = None,
    provenance: ProvenanceMeta | None = None,
    gross_total_pct: float | None = None,
    posture: str = "",
    btc_bias: str = "Neutral",
    timestamp: datetime | None = None,
    include_tracer: bool = True,
    include_provenance: bool = True,
) -> str:
    """Build locked WTM EXPORT v2.1 block."""
    return _build_contract(
        global_data=global_data,
        china_data=china_data,
        tracer_horizons=tracer_horizons,
        provenance=provenance,
        gross_total_pct=gross_total_pct,
        posture=posture,
        btc_bias=btc_bias,
        timestamp=timestamp,
        include_tracer=include_tracer,
        include_provenance=include_provenance,
    )


def write_decision_export_file(
    path: str,
    global_data: Mapping[str, Any],
    **kwargs: Any,
) -> str:
    """Write WTM EXPORT v2.1 block to a text file."""
    block = write_wtm_export_v21(global_data, **kwargs)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(block)
        fh.write("\n")
    return block