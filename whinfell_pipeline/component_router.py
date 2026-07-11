"""ARCH-1 M2 — live component inputs from RV history + horizon marks."""

from __future__ import annotations

from typing import Any, Mapping

from whinfell_pipeline.data_dictionary import get_rv_series_registry, node_score_components

# Component id → rv_series registry key
_COMPONENT_SERIES: dict[str, str] = {
    "usgg2y10y_direction": "usgg2y10y",
    "sofr_funding_stress": "sofr_ois_spread",
    "iwm_spy_ratio": "iwm_spy_ratio",
    "xlf_xlu_relative": "xlf_xlu_relative",
    "ibit_qqq_relative": "ibit_qqq_beta_spread",
    "ibit_spy_beta": "ibit_qqq_beta_spread",
    "btc_spy_decoupling": "btc_spy_corr",
    "btc_spot_momentum": "btc_spy_corr",
    "btc_calendar_level": "btc_calendar_bt_near_deferred",
    "btc_calendar_direction": "btc_calendar_bt_near_deferred",
    "contango_stability": "btc_calendar_bt_near_deferred",
    "basis_vs_ref_band": "btc_basis_vs_refs",
    "ibit_futures_basis_gap": "btc_basis_vs_refs",
}

_MARK_TO_CONSENSUS = {"up": "bullish", "down": "bearish", "flat": "mixed"}


def _series_registry() -> dict[str, dict[str, Any]]:
    reg = get_rv_series_registry()
    out: dict[str, dict[str, Any]] = {}
    for sid, row in (reg.get("series") or {}).items():
        if isinstance(row, dict):
            out[str(sid)] = row
    return out


def _history_key_for_component(comp_id: str) -> str | None:
    sid = _COMPONENT_SERIES.get(comp_id)
    if not sid:
        return None
    row = _series_registry().get(sid) or {}
    hk = str(row.get("history_key") or "").upper()
    return hk or None


def _lookup_history(
    history_key: str | None,
    spread_history: Mapping[str, list[tuple[str, float]]],
) -> list[tuple[str, float]]:
    if not history_key:
        return []
    key = history_key.upper()
    if key in spread_history:
        return list(spread_history[key])
    for hk, vals in spread_history.items():
        if key in str(hk).upper():
            return list(vals)
    return []


def _momentum_direction(
    values: list[tuple[str, float]],
    *,
    window: int = 5,
    rel_threshold: float = 0.002,
) -> str:
    if len(values) < window + 1:
        return "flat"
    recent = values[-1][1]
    prior = values[-1 - window][1]
    if prior == 0:
        delta = recent - prior
    else:
        delta = (recent - prior) / abs(prior)
    if abs(delta) < rel_threshold:
        return "flat"
    return "up" if recent > prior else "down"


def _consensus_from_marks(horizon_marks: Mapping[str, str]) -> str:
    marks = [str(horizon_marks.get(k, "flat")).lower() for k in ("d1", "d5", "d20", "d60")]
    ups = marks.count("up")
    downs = marks.count("down")
    if ups > downs and ups >= 2:
        return "bullish"
    if downs > ups and downs >= 2:
        return "bearish"
    if ups == downs == 0:
        return "unavailable"
    return "mixed"


def derive_live_component_inputs(
    node_id: str,
    horizon_marks: Mapping[str, str],
    *,
    as_of: str,
    spread_history: Mapping[str, list[tuple[str, float]]] | None = None,
) -> list[dict[str, Any]]:
    """Build component_inputs from RV history when available; horizon marks as fallback."""
    history = spread_history or {}
    fallback_consensus = _consensus_from_marks(horizon_marks)
    direction_map = {"up": "up", "down": "down", "flat": "flat"}
    components: list[dict[str, Any]] = []

    if node_id == "credit" and not node_score_components(node_id):
        return components

    for comp in node_score_components(node_id):
        comp_id = str(comp.get("id") or "")
        weight_pct = float(comp.get("weight_pct") or 0)
        weight = weight_pct / 100.0
        asset_ids = list(comp.get("asset_ids") or [])

        hk = _history_key_for_component(comp_id)
        values = _lookup_history(hk, history)
        unit = "signal"
        value: Any = "unavailable"
        direction = "flat"
        source = "horizon_fallback"

        if len(values) >= 2:
            momentum = _momentum_direction(values)
            direction = direction_map.get(momentum, "flat")
            value = round(values[-1][1], 4)
            row = _series_registry().get(_COMPONENT_SERIES.get(comp_id, ""), {})
            unit = str(row.get("unit") or "ratio")
            source = "rv_history"
        else:
            consensus = fallback_consensus
            direction = {"bullish": "up", "bearish": "down", "mixed": "flat", "unavailable": "flat"}[consensus]
            value = consensus

        mult_key = _MARK_TO_CONSENSUS.get(direction if direction != "flat" else "flat", "mixed")
        if direction == "flat":
            mult_key = fallback_consensus if fallback_consensus != "unavailable" else "mixed"
        multipliers = {"bullish": 1.0, "bearish": -1.0, "mixed": 0.5, "unavailable": 0}
        mult = float(multipliers.get(mult_key, 0.5))
        contribution = round(weight_pct * mult, 2) if source == "rv_history" else round(weight_pct * mult * 0.5, 2)

        components.append(
            {
                "asset_id": asset_ids[0] if asset_ids else comp_id,
                "label": str(comp.get("signal") or comp.get("id", "")),
                "value": value,
                "unit": unit,
                "weight": weight,
                "contribution": contribution,
                "direction": direction,
                "as_of": as_of,
                "source": source,
            }
        )
    return components


def count_live_components(components: list[dict[str, Any]]) -> int:
    return sum(1 for c in components if c.get("source") == "rv_history" and c.get("direction") != "flat")