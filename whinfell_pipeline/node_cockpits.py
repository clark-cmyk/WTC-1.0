"""Build per-node cockpit objects for hydration bundle v1.2.0."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from china_policy_track.china_ladder import (
    CANONICAL_STAGE_IDS,
    CHINA_STAGE_MODELS,
    HZ_SCORE,
    STAGE_TIE_RANK,
    composite_stage_score,
)
from whinfell_pipeline.data_dictionary import (
    funds_flow_basket_for_node,
    get_node_score_weights,
    get_rv_series_registry,
    node_score_components,
    rv_series_for_node,
    rv_series_primary,
)
from whinfell_pipeline.funds_flows import (
    apply_confidence_delta,
    build_funds_flows,
    merge_flow_rationale,
)

CANONICAL_NODE_IDS: tuple[str, ...] = CANONICAL_STAGE_IDS

_NODE_ORDER: tuple[str, ...] = ("liquidity", "credit", "breadth", "highbeta", "basis")

_MARK_TO_SYM = {"up": "↑", "flat": "→", "down": "↓"}

_RV_DEFAULT_STRUCTURE: dict[str, str] = {
    "liquidity": "2s10s curve trade / SOFR spread",
    "credit": "HYG vs LQD (or HY−IG OAS proxy)",
    "breadth": "IWM/SPY participation pair",
    "highbeta": "IBIT vs QQQ beta spread",
    "basis": "BT near vs deferred calendar",
}

_IMPLEMENTATION_CATALOG: dict[str, list[dict[str, Any]]] = {
    "liquidity": [
        {
            "id": "liq_ief_tlt",
            "instrument_class": "etf",
            "label": "IEF / TLT duration pair",
            "legs": [
                {"side": "long", "asset_id": "ief", "vendor_ticker": "IEF", "ratio": 1},
                {"side": "short", "asset_id": "tlt", "vendor_ticker": "TLT", "ratio": 1},
            ],
            "liquidity_tier": "institutional",
            "margin_profile": "ibkr_etf",
            "rank": 1,
        },
    ],
    "credit": [
        {
            "id": "credit_hyg_lqd",
            "instrument_class": "etf",
            "label": "HYG / LQD credit pair",
            "legs": [
                {"side": "long", "asset_id": "hyg", "vendor_ticker": "HYG", "ratio": 1},
                {"side": "short", "asset_id": "jaaa", "vendor_ticker": "LQD", "ratio": 1},
            ],
            "liquidity_tier": "institutional",
            "margin_profile": "ibkr_etf",
            "rank": 1,
        },
    ],
    "breadth": [
        {
            "id": "breadth_iwm_spy",
            "instrument_class": "etf",
            "label": "IWM / SPY participation pair",
            "legs": [
                {"side": "long", "asset_id": "spy", "vendor_ticker": "IWM", "ratio": 1},
                {"side": "short", "asset_id": "spy", "vendor_ticker": "SPY", "ratio": 1},
            ],
            "liquidity_tier": "institutional",
            "margin_profile": "ibkr_etf",
            "rank": 1,
        },
    ],
    "highbeta": [
        {
            "id": "highbeta_ibit_qqq",
            "instrument_class": "etf",
            "label": "IBIT vs QQQ beta spread",
            "legs": [
                {"side": "long", "asset_id": "btc_vehicle_ibit", "vendor_ticker": "IBIT", "ratio": 1},
                {"side": "short", "asset_id": "qqq", "vendor_ticker": "QQQ", "ratio": 1},
            ],
            "liquidity_tier": "institutional",
            "margin_profile": "ibkr_etf",
            "rank": 1,
        },
    ],
    "basis": [
        {
            "id": "basis_btc_calendar",
            "instrument_class": "futures",
            "label": "BT calendar spread",
            "legs": [
                {"side": "long", "asset_id": "btc_deferred_contract", "vendor_ticker": "BTQ26", "ratio": 1},
                {"side": "short", "asset_id": "btc_near_contract", "vendor_ticker": "BTM26", "ratio": 1},
            ],
            "liquidity_tier": "institutional",
            "margin_profile": "cme_btc",
            "rank": 1,
        },
        {
            "id": "basis_ibit_proxy",
            "instrument_class": "etf",
            "label": "IBIT warehouse proxy",
            "legs": [
                {"side": "long", "asset_id": "btc_vehicle_ibit", "vendor_ticker": "IBIT", "ratio": 1},
            ],
            "liquidity_tier": "institutional",
            "margin_profile": "ibkr_etf",
            "rank": 2,
        },
    ],
}


def default_spread_history_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "data" / "barchart" / "v1" / "barchart_spread_history.json"


def _horizon_net(marks: Mapping[str, str]) -> int:
    return sum(HZ_SCORE.get(str(marks.get(k, "flat")).lower(), 0) for k in ("d1", "d5", "d20", "d60"))


def _horizon_net_to_score(net: int) -> int:
    return max(0, min(100, int(round(50 + net * 12.5))))


def _score_to_band(score: int) -> tuple[str, str]:
    if score >= 70:
        return ("Supportive", "supportive")
    if score >= 55:
        return ("Mixed", "mixed")
    if score >= 40:
        return ("Fragile", "fragile")
    return ("Blocked", "blocked")


def _mark_consensus(marks: Mapping[str, str]) -> str:
    d5 = str(marks.get("d5", "flat")).lower()
    d20 = str(marks.get("d20", "flat")).lower()
    if d5 == "up" and d20 == "up":
        return "bullish"
    if d5 == "down" and d20 == "down":
        return "bearish"
    if d5 in ("up", "down") or d20 in ("up", "down"):
        return "mixed"
    return "unavailable"


def _direction_multipliers() -> dict[str, float]:
    design = (get_node_score_weights().get("design") or {})
    return dict(design.get("direction_multipliers") or {"bullish": 1.0, "bearish": -1.0, "mixed": 0.5, "unavailable": 0})


def _node_display_name(node_id: str) -> str:
    nodes = (get_node_score_weights().get("nodes") or {})
    spec = nodes.get(node_id) or {}
    if spec.get("display_name"):
        return str(spec["display_name"])
    return CHINA_STAGE_MODELS.get(node_id, {}).get("name", node_id)


def _derive_component_inputs(
    node_id: str,
    horizon_marks: Mapping[str, str],
    *,
    as_of: str,
    spread_history: Mapping[str, list[tuple[str, float]]] | None = None,
) -> list[dict[str, Any]]:
    from whinfell_pipeline.component_router import derive_live_component_inputs

    history = spread_history if spread_history is not None else _load_spread_history()
    live = derive_live_component_inputs(
        node_id,
        horizon_marks,
        as_of=as_of,
        spread_history=history,
    )
    if live:
        return live

    # Legacy tracer-stub fallback when no registry components or history
    consensus = _mark_consensus(horizon_marks)
    direction_map = {"bullish": "up", "bearish": "down", "mixed": "flat", "unavailable": "flat"}
    direction = direction_map[consensus]
    multipliers = _direction_multipliers()
    components: list[dict[str, Any]] = []

    if node_id == "credit" and not node_score_components(node_id):
        return components

    for comp in node_score_components(node_id):
        weight_pct = float(comp.get("weight_pct") or 0)
        weight = weight_pct / 100.0
        mult = float(multipliers.get(consensus, 0))
        contribution = round(weight_pct * mult, 2)
        asset_ids = list(comp.get("asset_ids") or [])
        components.append(
            {
                "asset_id": asset_ids[0] if asset_ids else comp.get("id", ""),
                "label": str(comp.get("signal") or comp.get("id", "")),
                "value": consensus,
                "unit": "signal",
                "weight": weight,
                "contribution": contribution,
                "direction": direction,
                "as_of": as_of,
                "source": "horizon_stub",
            }
        )
    return components


def _compute_composite_score(
    node_id: str,
    component_inputs: list[dict[str, Any]],
    horizon_net: int,
) -> tuple[int, str, str]:
    design = get_node_score_weights().get("design") or {}
    base = int(design.get("base_score") or 50)
    min_components = int(design.get("fallback_min_components") or 2)
    live = [c for c in component_inputs if c.get("source") == "rv_history" and c.get("direction") != "flat"]
    scorable = live or [c for c in component_inputs if c.get("direction") != "flat" or c.get("contribution")]

    if node_id == "credit" or len(scorable) < min_components:
        score = _horizon_net_to_score(horizon_net)
        return score, "horizon_net_fallback", "low" if node_id == "credit" else "medium"

    total = base + sum(float(c.get("contribution") or 0) for c in component_inputs)
    score = max(0, min(100, int(round(total))))
    zero_count = sum(1 for c in component_inputs if not c.get("contribution"))
    confidence = "low" if zero_count >= 2 else "medium"
    return score, "weighted_components", confidence


def _gate_zone(global_payload: Mapping[str, Any]) -> str:
    gate = str(global_payload.get("gate_status") or "").lower()
    if gate in ("red", "blocked"):
        return "red"
    if gate in ("amber", "caution"):
        return "amber"
    score = int(global_payload.get("whinfell_score") or 50)
    tx = str(global_payload.get("transmission_state") or "normal").lower()
    if tx in ("disorderly", "crisis") or score < 45:
        return "red"
    if tx == "stressed" or score < 60:
        return "amber"
    return "green"


def _gate_interaction(zone: str, composite_score: int) -> dict[str, Any]:
    blocks_directional = zone == "red"
    blocks_rv = zone == "red"
    note = ""
    if zone == "red":
        note = "Global gate Red — directional and RV expression blocked."
    elif zone == "amber":
        note = "Health below 70 — size_hint capped at half."
    elif composite_score < 50:
        note = "Node composite below 50 — prefer RV over directional beta."
    return {
        "zone": zone,
        "blocks_directional": blocks_directional,
        "blocks_rv": blocks_rv,
        "note": note,
    }


def _format_horizon_marks(marks: Mapping[str, str]) -> str:
    parts = []
    for key in ("d1", "d5", "d20", "d60"):
        sym = _MARK_TO_SYM.get(str(marks.get(key, "flat")).lower(), "→")
        parts.append(f"{key}{sym}")
    return " ".join(parts)


def _build_china_parallel(
    node_id: str,
    china_ladder: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not china_ladder:
        return None
    horizons = china_ladder.get("horizons") or {}
    hz = horizons.get(node_id)
    if not isinstance(hz, dict):
        return None
    net = _horizon_net(hz)
    stage_name = CHINA_STAGE_MODELS.get(node_id, {}).get("name", node_id)
    china_score = composite_stage_score(node_id, horizons)
    return {
        "present": True,
        "stage_id": node_id,
        "stage_name": stage_name,
        "horizon_marks": dict(hz),
        "horizon_net": net,
        "composite_score": china_score,
        "note": f"China {stage_name.lower()} stage horizon_net {net:+d} (informational)",
    }


def _load_spread_history(repo_root: Path | None = None) -> dict[str, list[tuple[str, float]]]:
    from whinfell_pipeline.rv_history import load_rv_history

    return load_rv_history(repo_root)


def _history_values_for_series(
    series_spec: Mapping[str, Any],
    spread_history: Mapping[str, list[tuple[str, float]]],
    execution: Mapping[str, Any],
) -> list[tuple[str, float]]:
    history_key = str(series_spec.get("history_key") or "").upper()
    if history_key and history_key in spread_history:
        return list(spread_history[history_key])
    for hk, values in spread_history.items():
        if history_key and history_key in hk.upper():
            return list(values)
    source = str(series_spec.get("history_source") or "")
    if source.startswith("barchart") and history_key:
        spread = execution.get("basis_spread")
        as_of = execution.get("as_of") or datetime.now(timezone.utc).date().isoformat()
        if spread not in (None, ""):
            try:
                return [(str(as_of)[:10], float(str(spread).replace("%", "")))]
            except ValueError:
                pass
    return []


def _empirical_percentile(current: float, values: list[float]) -> float:
    if not values:
        return 50.0
    n = len(values)
    count_le = sum(1 for v in values if v <= current)
    return round((count_le / n) * 100, 1)


def _percentile_to_quartile(pct: float) -> int:
    if pct <= 25:
        return 1
    if pct <= 50:
        return 2
    if pct <= 75:
        return 3
    return 4


def _richness_label(quartile: int, quartile_direction: str) -> str:
    if quartile_direction == "higher_is_cheaper":
        return {4: "cheap", 3: "fair", 2: "rich", 1: "extreme"}[quartile]
    return {1: "cheap", 2: "fair", 3: "rich", 4: "extreme"}[quartile]


def _build_rv_basis(
    node_id: str,
    *,
    as_of: datetime,
    execution: Mapping[str, Any],
    spread_history: Mapping[str, list[tuple[str, float]]] | None = None,
) -> dict[str, Any]:
    reg = get_rv_series_registry()
    lookbacks = dict(reg.get("lookback_trading_days") or {})
    active_series_id = rv_series_primary(node_id) or ""
    series_out: dict[str, Any] = {}
    history = spread_history if spread_history is not None else _load_spread_history()

    for row in rv_series_for_node(node_id):
        sid = str(row["series_id"])
        unit = str(row.get("unit") or "pct")
        qdir = str(row.get("quartile_direction") or "higher_is_richer")
        values = _history_values_for_series(row, history, execution)
        horizons_out: dict[str, Any] = {}

        for horizon_key, window in lookbacks.items():
            if not values:
                continue
            window_vals = [v for _, v in values[-int(window) :]]
            if len(window_vals) < 2:
                continue
            current = window_vals[-1]
            dates = [d for d, _ in values[-int(window) :]]
            pct = _empirical_percentile(current, window_vals)
            quartile = _percentile_to_quartile(pct)
            horizons_out[horizon_key] = {
                "current_value": current,
                "unit": unit,
                "percentile": pct,
                "quartile": quartile,
                "richness_label": _richness_label(quartile, qdir),
                "lookback_start": dates[0],
                "lookback_end": dates[-1],
                "n_observations": len(window_vals),
            }

        series_out[sid] = {
            "quartile_direction": qdir,
            "label": str(row.get("label") or sid),
            "horizons": horizons_out,
        }

    active_horizon = "3m"
    richness_label = ""
    quartile_context = ""
    if active_series_id and active_series_id in series_out:
        active_h = series_out[active_series_id]["horizons"].get(active_horizon)
        if active_h:
            richness_label = str(active_h.get("richness_label") or "")
            qdir = series_out[active_series_id]["quartile_direction"]
            quartile_context = (
                f"{series_out[active_series_id]['label']} Q{active_h['quartile']} "
                f"({active_h['percentile']}th pct) — {qdir}"
            )

    return {
        "active_horizon": active_horizon,
        "active_series_id": active_series_id,
        "richness_label": richness_label,
        "quartile_context": quartile_context,
        "series": series_out,
    }


def _build_directional(
    node_id: str,
    *,
    composite_score: int,
    horizon_marks: Mapping[str, str],
    gate: dict[str, Any],
    global_payload: Mapping[str, Any],
) -> dict[str, Any]:
    net = _horizon_net(horizon_marks)
    blocked = bool(gate.get("blocks_directional"))
    block_reason = str(gate.get("note") or "") if blocked else ""

    if blocked:
        posture, conviction = "no_trade", "low"
        rationale = block_reason or "Global gate blocks directional expression."
    elif net >= 2 and composite_score >= 60:
        posture, conviction = "long", "medium"
        rationale = f"{_node_display_name(node_id)} horizons confirming risk-on transmission."
    elif net <= -2 and composite_score < 50:
        posture, conviction = "short", "medium"
        rationale = f"{_node_display_name(node_id)} horizons impairing transmission."
    else:
        posture, conviction = "neutral", "low"
        rationale = f"{_node_display_name(node_id)} mixed marks — prefer RV or reduced size."

    if node_id == "highbeta":
        bias = str(global_payload.get("btc_bias") or "Neutral")
        if bias == "Dragging":
            posture = "short" if not blocked else "no_trade"
            rationale = "BTC lagging equities — beta-off bias."
        elif bias == "Confirming":
            posture = "long" if not blocked else "no_trade"
            rationale = "BTC confirming risk transmission."

    return {
        "posture": posture,
        "conviction": conviction,
        "rationale": rationale,
        "horizon": "20d",
        "invalidation": "",
        "size_hint": "flat" if blocked else ("half" if gate.get("zone") == "amber" else "probe"),
        "blocked": blocked,
        "block_reason": block_reason,
    }


def _build_relative_value(
    node_id: str,
    rv_basis: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    structure = _RV_DEFAULT_STRUCTURE.get(node_id, "")
    active_id = str(rv_basis.get("active_series_id") or "")
    series = (rv_basis.get("series") or {}).get(active_id) or {}
    active_h = (series.get("horizons") or {}).get(str(rv_basis.get("active_horizon") or "3m"))
    blocked = bool(gate.get("blocks_rv"))

    if active_h and active_h.get("richness_label") in ("rich", "extreme"):
        posture = "short_spread"
        conviction = "medium"
        rationale = f"{active_h['richness_label'].title()} vs history on {series.get('label', active_id)}."
    elif active_h and active_h.get("richness_label") == "cheap":
        posture = "long_spread"
        conviction = "medium"
        rationale = f"Cheap vs history on {series.get('label', active_id)}."
    else:
        posture = "neutral"
        conviction = "low"
        rationale = f"No extreme RV signal on {structure}."

    return {
        "posture": "no_trade" if blocked else posture,
        "structure": structure,
        "conviction": conviction,
        "rationale": rationale,
        "leg_long": "",
        "leg_short": "",
        "hedge_ratio": 1.0,
        "target": "",
        "stop": "",
        "blocked": blocked,
        "block_reason": str(gate.get("note") or "") if blocked else "",
    }


def _build_sizing() -> dict[str, Any]:
    return {
        "enabled": False,
        "portfolio_nav_usd": None,
        "risk_budget_bps": 25,
        "kelly_fraction": 0.25,
        "max_notional_usd": None,
        "recommended_notional_usd": None,
        "contracts_or_shares": None,
        "margin": None,
    }


def _node_key_observation(
    node_id: str,
    *,
    horizon_marks: Mapping[str, str],
    global_payload: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> str:
    net = _horizon_net(horizon_marks)
    if node_id == "basis" and execution.get("basis_spread"):
        return (
            f"Calendar at {execution['basis_spread']}% "
            f"({execution.get('near_month', '?')}/{execution.get('far_month', '?')}); "
            f"horizon_net {net:+d}."
        )
    if node_id == "highbeta":
        bias = global_payload.get("btc_bias") or "Neutral"
        return f"BTC bias {bias}; horizon_net {net:+d}."
    if node_id == "credit":
        obs = str(global_payload.get("key_observation") or "")
        if "credit" in obs.lower():
            return obs.split(".")[0] + "." if "." in obs else obs
    return f"{_node_display_name(node_id)} horizon_net {net:+d} from suggested tracer marks."


def _attach_funds_flows(
    cockpit: dict[str, Any],
    *,
    node_id: str,
    flows_sidecar: Mapping[str, Any] | None,
    as_of_iso: str,
) -> None:
    basket = funds_flow_basket_for_node(node_id)
    funds = build_funds_flows(
        node_id,
        sidecar=flows_sidecar,
        node_cockpit=cockpit,
        basket_spec=basket,
        as_of=as_of_iso[:10],
    )
    cockpit["funds_flows"] = funds
    cockpit["confidence"] = apply_confidence_delta(str(cockpit.get("confidence") or "low"), funds)
    if isinstance(cockpit.get("directional"), dict):
        cockpit["directional"]["rationale"] = merge_flow_rationale(
            str(cockpit["directional"].get("rationale") or ""),
            funds,
        )
    if isinstance(cockpit.get("relative_value"), dict):
        cockpit["relative_value"]["rationale"] = merge_flow_rationale(
            str(cockpit["relative_value"].get("rationale") or ""),
            funds,
        )


def build_node_cockpit(
    node_id: str,
    *,
    global_payload: Mapping[str, Any],
    horizon_marks: Mapping[str, str],
    as_of: datetime,
    freshness_status: str,
    china_ladder: Mapping[str, Any] | None = None,
    execution: Mapping[str, Any] | None = None,
    is_weakest_link: bool = False,
    weakest_context: Mapping[str, Any] | None = None,
    spread_history: Mapping[str, list[tuple[str, float]]] | None = None,
    flows_sidecar: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one node_cockpit object per Phase 2 data model."""
    as_of_iso = as_of.astimezone(timezone.utc).isoformat()
    exec_payload = dict(execution or {})
    net = _horizon_net(horizon_marks)
    history = spread_history if spread_history is not None else _load_spread_history()
    component_inputs = _derive_component_inputs(
        node_id, horizon_marks, as_of=as_of_iso, spread_history=history,
    )
    composite_score, score_source, confidence = _compute_composite_score(node_id, component_inputs, net)
    band, band_key = _score_to_band(composite_score)
    gate = _gate_interaction(_gate_zone(global_payload), composite_score)
    rv_basis = _build_rv_basis(node_id, as_of=as_of, execution=exec_payload, spread_history=spread_history)

    cockpit: dict[str, Any] = {
        "node_id": node_id,
        "display_name": _node_display_name(node_id),
        "composite_score": composite_score,
        "composite_score_source": score_source,
        "band": band,
        "band_key": band_key,
        "freshness_status": freshness_status,
        "as_of": as_of_iso,
        "horizon_marks": dict(horizon_marks),
        "horizon_net": net,
        "is_weakest_link": is_weakest_link,
        "key_observation": _node_key_observation(
            node_id,
            horizon_marks=horizon_marks,
            global_payload=global_payload,
            execution=exec_payload,
        ),
        "confidence": confidence,
        "gate_interaction": gate,
        "component_inputs": component_inputs,
        "directional": _build_directional(
            node_id,
            composite_score=composite_score,
            horizon_marks=horizon_marks,
            gate=gate,
            global_payload=global_payload,
        ),
        "relative_value": _build_relative_value(node_id, rv_basis, gate=gate),
        "implementations": list(_IMPLEMENTATION_CATALOG.get(node_id, [])),
        "selected_implementation_id": None,
        "sizing": _build_sizing(),
        "rv_basis": rv_basis,
    }

    china_parallel = _build_china_parallel(node_id, china_ladder)
    if china_parallel:
        cockpit["china_parallel"] = china_parallel
    if is_weakest_link and weakest_context:
        cockpit["weakest_context"] = dict(weakest_context)

    _attach_funds_flows(cockpit, node_id=node_id, flows_sidecar=flows_sidecar, as_of_iso=as_of_iso)
    return cockpit


def build_node_cockpits(
    *,
    global_payload: Mapping[str, Any],
    suggested_tracer: Mapping[str, Mapping[str, str]],
    as_of: datetime,
    freshness_status: str,
    china_ladder: Mapping[str, Any] | None = None,
    execution: Mapping[str, Any] | None = None,
    spread_history: Mapping[str, list[tuple[str, float]]] | None = None,
    flows_sidecar: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build all five node cockpit objects keyed by node_id."""
    default_marks = {"d1": "flat", "d5": "flat", "d20": "flat", "d60": "flat"}
    previews: list[tuple[str, int, int]] = []

    for node_id in _NODE_ORDER:
        marks = dict(suggested_tracer.get(node_id) or default_marks)
        net = _horizon_net(marks)
        history = spread_history if spread_history is not None else _load_spread_history()
        components = _derive_component_inputs(
            node_id,
            marks,
            as_of=as_of.astimezone(timezone.utc).isoformat(),
            spread_history=history,
        )
        score, source, _ = _compute_composite_score(node_id, components, net)
        previews.append((node_id, score, STAGE_TIE_RANK.get(node_id, 99)))

    weakest_id = min(previews, key=lambda x: (x[1], x[2]))[0]
    weakest_context = {
        "global_health_score": int(global_payload.get("whinfell_score") or 50),
        "transmission_state": str(global_payload.get("transmission_state") or "normal"),
        "key_observation": str(global_payload.get("key_observation") or ""),
    }

    cockpits: dict[str, dict[str, Any]] = {}
    for node_id in _NODE_ORDER:
        marks = dict(suggested_tracer.get(node_id) or default_marks)
        cockpits[node_id] = build_node_cockpit(
            node_id,
            global_payload=global_payload,
            horizon_marks=marks,
            as_of=as_of,
            freshness_status=freshness_status,
            china_ladder=china_ladder,
            execution=execution,
            is_weakest_link=(node_id == weakest_id),
            weakest_context=weakest_context if node_id == weakest_id else None,
            spread_history=spread_history,
            flows_sidecar=flows_sidecar,
        )
    return cockpits


def build_cockpit_context(
    *,
    global_payload: Mapping[str, Any],
    node_cockpits: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Shared metadata for hydration bundle v1.2.0."""
    weakest = min(
        node_cockpits.items(),
        key=lambda item: (int(item[1].get("composite_score") or 50), STAGE_TIE_RANK.get(item[0], 99)),
    )
    zone = _gate_zone(global_payload)
    return {
        "transmission_health_score": int(global_payload.get("whinfell_score") or 50),
        "transmission_state": str(global_payload.get("transmission_state") or "normal"),
        "weakest_node_id": weakest[0],
        "gate_zone": zone,
        "whinfell_score": int(global_payload.get("whinfell_score") or 50),
    }