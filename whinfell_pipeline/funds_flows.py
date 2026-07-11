"""Build per-node funds_flows L2 view from L1 sidecar — PR-2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from whinfell_pipeline.data_dictionary import (
    funds_flow_basket_for_node,
    funds_flow_sidecar_path,
    funds_flow_thresholds,
)

__all__ = [
    "apply_confidence_delta",
    "build_flows_sidecar_metadata",
    "build_funds_flows",
    "build_interpretation",
    "load_flows_sidecar",
    "merge_flow_rationale",
    "resolve_degrade_mode",
]

_CONFIDENCE_TIERS = ("low", "medium", "high")

_DEGRADE_NOTICES: dict[str, str] = {
    "full": "",
    "partial_basket": "Partial flow coverage — some basket ETFs missing from WTM-Flows.",
    "fallback_1d_credit": "5D flows unavailable — using 1D Credit cross-section fallback.",
    "unavailable": "Flows data not available for this session.",
}

_FLOWS_META_MAP: dict[str, dict[str, Any]] = {
    "full": {
        "flows_status": "ok",
        "flows_source": "wtm_flows_timeseries",
        "flows_degraded": False,
        "flows_confidence_penalty": 0,
        "fallback_reason": "",
    },
    "partial_basket": {
        "flows_status": "partial",
        "flows_source": "wtm_flows_timeseries",
        "flows_degraded": True,
        "flows_confidence_penalty": 0,
        "fallback_reason": "missing_basket_etfs",
    },
    "fallback_1d_credit": {
        "flows_status": "fallback_1d",
        "flows_source": "credit_cross_section",
        "flows_degraded": True,
        "flows_confidence_penalty": 1,
        "fallback_reason": "credit_cross_section_1d_only",
    },
    "unavailable": {
        "flows_status": "unavailable",
        "flows_source": "none",
        "flows_degraded": True,
        "flows_confidence_penalty": 0,
        "fallback_reason": "",
    },
}


def load_flows_sidecar(repo_root: Path | None = None) -> dict[str, Any] | None:
    """Load L1 sidecar JSON if present; return None when missing."""
    root = repo_root or Path(__file__).resolve().parents[1]
    path = root / funds_flow_sidecar_path()
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else None


def build_flows_sidecar_metadata(
    sidecar: Mapping[str, Any] | None,
    *,
    node_id: str = "credit",
) -> dict[str, Any]:
    """Top-level hydration mirror — always present so degrade ≠ silent absence."""
    from whinfell_pipeline.flows_parser import assess_flows_basket_health

    health = assess_flows_basket_health(sidecar, node_id=node_id)
    if not sidecar:
        return {
            "as_of": "",
            "source_file": "",
            "ingest_mode": "disabled",
            "flows_status": "unavailable",
            "ticker_count": 0,
            "warnings": list(health.get("warnings") or ["missing_wtm_flows_file"]),
            "basket_health": health,
        }
    tickers = sidecar.get("tickers") or {}
    ingest_mode = str(sidecar.get("ingest_mode") or "disabled")
    flows_status = "ok"
    if ingest_mode == "fallback_1d_only":
        flows_status = "fallback_1d"
    elif ingest_mode == "disabled":
        flows_status = "unavailable"
    elif health.get("status") == "partial":
        flows_status = "partial"
    elif health.get("status") == "unavailable":
        flows_status = "unavailable"

    base_warnings = list(sidecar.get("warnings") or [])
    health_warnings = list(health.get("warnings") or [])
    warnings = list(dict.fromkeys(base_warnings + health_warnings))

    return {
        "as_of": sidecar.get("as_of") or "",
        "source_file": sidecar.get("source_file") or "",
        "ingest_mode": ingest_mode,
        "flows_status": flows_status,
        "ticker_count": len(tickers),
        "warnings": warnings,
        "basket_health": health,
    }


def _ticker_sidecar_row(sidecar: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    if not sidecar:
        return None
    tickers = sidecar.get("tickers") or {}
    row = tickers.get(ticker.upper()) or tickers.get(ticker)
    return dict(row) if isinstance(row, dict) else None


def _basket_role(etf_spec: Mapping[str, Any]) -> str:
    if etf_spec.get("primary"):
        return "primary"
    role = str(etf_spec.get("role") or "")
    if "proxy" in role or "warehouse" in role or "trust" in role:
        return "proxy"
    return "supporting"


def compute_etf_row(
    node_id: str,
    etf_spec: Mapping[str, Any],
    sidecar: Mapping[str, Any] | None,
    *,
    degrade_mode: str,
) -> dict[str, Any]:
    """Map one basket ETF to L2 row."""
    ticker = str(etf_spec.get("ticker") or "").upper()
    row = _ticker_sidecar_row(sidecar, ticker)
    weight = float(etf_spec.get("weight") or 0.0)
    base: dict[str, Any] = {
        "ticker": ticker,
        "asset_id": str(etf_spec.get("asset_id") or ""),
        "node_affiliation": node_id,
        "basket_role": _basket_role(etf_spec),
        "basket_weight": weight,
        "flow_pct_aum_1d": None,
        "flow_pct_aum_5d": None,
        "flow_usd_1d": None,
        "flow_usd_5d": None,
        "persistence_score": None,
        "data_status": "missing",
    }
    if not row:
        return base

    latest = row.get("latest") or {}
    rolling = row.get("rolling") or {}
    has_1d = latest.get("flow_pct_aum_1d") is not None
    has_5d = rolling.get("flow_pct_aum_5d") is not None

    if has_1d:
        base["flow_pct_aum_1d"] = float(latest["flow_pct_aum_1d"])
        base["flow_usd_1d"] = latest.get("flow_usd_1d")
    if has_5d and degrade_mode not in ("fallback_1d_credit",):
        base["flow_pct_aum_5d"] = float(rolling["flow_pct_aum_5d"])
        base["flow_usd_5d"] = rolling.get("flow_usd_5d")
        base["persistence_score"] = rolling.get("persistence_score_20d")
        base["data_status"] = "ok"
    elif has_1d:
        base["data_status"] = "partial_1d_only"
    return base


def _renormalize_weights(etf_rows: list[dict[str, Any]]) -> list[float]:
    populated = [r for r in etf_rows if r["data_status"] != "missing"]
    total_w = sum(float(r["basket_weight"]) for r in populated)
    if total_w <= 0:
        return [0.0] * len(etf_rows)
    weights: list[float] = []
    for row in etf_rows:
        if row["data_status"] == "missing":
            weights.append(0.0)
        else:
            weights.append(float(row["basket_weight"]) / total_w)
    return weights


def compute_aggregate(
    etf_rows: list[dict[str, Any]],
    *,
    node_id: str,
    basket_spec: Mapping[str, Any],
    degrade_mode: str,
) -> dict[str, Any]:
    """Weighted aggregate with optional basis primary-led blend."""
    primary_ticker = str(basket_spec.get("primary_ticker") or "").upper()
    weights = _renormalize_weights(etf_rows)
    populated = [r for r in etf_rows if r["data_status"] != "missing"]
    total_count = len(etf_rows)

    def _wmean(field: str) -> float | None:
        vals = []
        for row, w in zip(etf_rows, weights):
            v = row.get(field)
            if v is not None and w > 0:
                vals.append((float(v), w))
        if not vals:
            return None
        return sum(v * w for v, w in vals) / sum(w for _, w in vals)

    agg_1d = _wmean("flow_pct_aum_1d")
    agg_5d = _wmean("flow_pct_aum_5d") if degrade_mode != "fallback_1d_credit" else None
    agg_usd_1d = _wmean("flow_usd_1d")
    agg_usd_5d = _wmean("flow_usd_5d") if degrade_mode != "fallback_1d_credit" else None

    if node_id == "basis" and agg_5d is not None:
        primary_row = next((r for r in etf_rows if r["ticker"] == primary_ticker), None)
        if primary_row and primary_row.get("flow_pct_aum_5d") is not None:
            p5 = float(primary_row["flow_pct_aum_5d"])
            agg_5d = 0.6 * p5 + 0.4 * float(agg_5d)
        if primary_row and primary_row.get("flow_pct_aum_1d") is not None and agg_1d is not None:
            p1 = float(primary_row["flow_pct_aum_1d"])
            agg_1d = 0.6 * p1 + 0.4 * float(agg_1d)

    positive_5d = [
        r for r in populated
        if r.get("flow_pct_aum_5d") is not None and float(r["flow_pct_aum_5d"]) > 0
    ]
    positive_1d = [
        r for r in populated
        if r.get("flow_pct_aum_1d") is not None and float(r["flow_pct_aum_1d"]) > 0
    ]
    use_5d = degrade_mode not in ("fallback_1d_credit",) and agg_5d is not None
    pos_count = len(positive_5d) if use_5d else len(positive_1d)

    primary_row = next((r for r in etf_rows if r["ticker"] == primary_ticker), None)
    primary_5d = primary_row.get("flow_pct_aum_5d") if primary_row else None

    signed_sum = sum(
        abs(float(r["flow_pct_aum_5d"]))
        for r in populated
        if r.get("flow_pct_aum_5d") is not None
    )
    concentration_flag = False
    if signed_sum > 0 and primary_row and primary_row.get("flow_pct_aum_5d") is not None:
        share = abs(float(primary_row["flow_pct_aum_5d"])) / signed_sum
        concentration_flag = share > float(funds_flow_thresholds().get("concentration_single_etf", 0.70))

    return {
        "flow_pct_aum_1d": round(agg_1d, 4) if agg_1d is not None else None,
        "flow_pct_aum_5d": round(agg_5d, 4) if agg_5d is not None else None,
        "flow_usd_1d": round(agg_usd_1d, 2) if agg_usd_1d is not None else None,
        "flow_usd_5d": round(agg_usd_5d, 2) if agg_usd_5d is not None else None,
        "positive_count": pos_count,
        "total_count": total_count,
        "populated_count": len(populated),
        "primary_ticker": primary_ticker,
        "primary_flow_pct_aum_5d": primary_5d,
        "concentration_flag": concentration_flag,
    }


def _base_verdict(
    aggregate: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    *,
    use_5d: bool,
) -> str:
    supportive = float(thresholds.get("supportive_5d_pct", 0.15))
    weak = float(thresholds.get("weak_5d_pct", 0.05))
    divergence = float(thresholds.get("divergence_5d_pct", -0.05))
    breadth_ratio = float(thresholds.get("breadth_supportive_ratio", 0.60))

    agg_5d = aggregate.get("flow_pct_aum_5d")
    agg_1d = aggregate.get("flow_pct_aum_1d")
    pos = int(aggregate.get("positive_count") or 0)
    total = int(aggregate.get("total_count") or 1)
    breadth = pos / total if total else 0.0

    if use_5d and agg_5d is not None:
        a5 = float(agg_5d)
        a1 = float(agg_1d) if agg_1d is not None else 0.0
        if a5 >= supportive and breadth >= breadth_ratio:
            return "supportive"
        if a5 <= divergence or (a1 > 0 and a5 < 0):
            return "mixed"
        if abs(a5) < weak:
            return "neutral"
        return "neutral"

    if agg_1d is not None:
        a1 = float(agg_1d)
        if abs(a1) < weak:
            return "neutral"
        if a1 > 0:
            return "mixed"
        return "mixed"
    return "neutral"


def assign_verdict(
    aggregate: Mapping[str, Any],
    node_cockpit: Mapping[str, Any],
    thresholds: Mapping[str, Any] | None,
    degrade_mode: str,
) -> tuple[str, int, bool]:
    """Return (verdict, confidence_delta, divergence_flag)."""
    th = thresholds or funds_flow_thresholds()
    use_5d = degrade_mode not in ("fallback_1d_credit",) and aggregate.get("flow_pct_aum_5d") is not None

    if degrade_mode == "unavailable":
        return "neutral", 0, False

    base = _base_verdict(aggregate, th, use_5d=use_5d)
    verdict = base
    divergence_flag = False

    directional = (node_cockpit.get("directional") or {})
    relative_value = (node_cockpit.get("relative_value") or {})
    dir_posture = str(directional.get("posture") or "neutral")
    rv_posture = str(relative_value.get("posture") or "neutral")
    conviction = str(directional.get("conviction") or "low")

    agg_5d = aggregate.get("flow_pct_aum_5d")
    agg_1d = aggregate.get("flow_pct_aum_1d")
    supportive = float(th.get("supportive_5d_pct", 0.15))
    weak = float(th.get("weak_5d_pct", 0.05))
    divergence = float(th.get("divergence_5d_pct", -0.05))

    if degrade_mode == "fallback_1d_credit":
        if verdict == "supportive":
            verdict = "mixed"
        if verdict == "diverging":
            verdict = "mixed"
        return verdict, 0, False

    if use_5d and agg_5d is not None:
        a5 = float(agg_5d)
        bullish = dir_posture in ("long", "long_spread") or rv_posture == "long_spread"
        bearish = dir_posture in ("short", "short_spread") or rv_posture == "short_spread"

        if bullish and a5 < divergence:
            verdict = "diverging"
            divergence_flag = True
        elif bullish and a5 < weak and conviction in ("medium", "high"):
            verdict = "diverging"
            divergence_flag = True
        elif bearish and a5 > supportive:
            verdict = "mixed"

        primary_ticker = str(aggregate.get("primary_ticker") or "").upper()
        primary_5d = aggregate.get("primary_flow_pct_aum_5d")
        if primary_5d is not None and rv_posture == "long_spread":
            p5 = float(primary_5d)
            if p5 < 0 and bullish:
                divergence_flag = True
                if verdict not in ("diverging",):
                    verdict = "diverging" if a5 < weak else "mixed"

    delta_map = {"supportive": 1, "neutral": 0, "mixed": 0, "diverging": -1}
    delta = delta_map.get(verdict, 0)
    if verdict == "supportive" and divergence_flag:
        delta = 0
        verdict = "mixed"
    return verdict, delta, divergence_flag


def build_interpretation(
    *,
    verdict: str,
    aggregate: Mapping[str, Any],
    node_cockpit: Mapping[str, Any],
    degrade_mode: str,
    divergence_flag: bool,
    basket_spec: Mapping[str, Any],
) -> dict[str, Any]:
    primary = str(basket_spec.get("primary_ticker") or "Primary ETF")
    agg_5d = aggregate.get("flow_pct_aum_5d")
    agg_1d = aggregate.get("flow_pct_aum_1d")

    supports = verdict == "supportive" and not divergence_flag
    degrade_notice = _DEGRADE_NOTICES.get(degrade_mode, "")

    if degrade_mode == "unavailable":
        return {
            "supports_node_thesis": False,
            "divergence_flag": False,
            "summary": "",
            "caution_line": "",
            "change_mind_trigger": "",
            "degrade_notice": degrade_notice,
        }

    if degrade_mode == "fallback_1d_credit":
        a1 = float(agg_1d) if agg_1d is not None else 0.0
        direction = "positive" if a1 >= 0 else "negative"
        return {
            "supports_node_thesis": False,
            "divergence_flag": False,
            "summary": f"1D credit flows mildly {direction} — 5D unavailable.",
            "caution_line": "",
            "change_mind_trigger": f"{primary} 5D % AUM turns negative while spread RV still rich.",
            "degrade_notice": degrade_notice,
        }

    if verdict == "supportive":
        summary = f"{primary} 5D inflows confirm constructive {_node_label(node_cockpit)} transmission."
    elif verdict == "diverging":
        summary = f"{primary} flows diverge from node directional/RV read."
    elif verdict == "mixed":
        summary = f"Mixed allocator sponsorship across {primary} basket."
    else:
        summary = f"{primary} flows neutral — limited sponsorship signal."

    caution = ""
    if divergence_flag or verdict == "diverging":
        caution = "Price/RV improving faster than allocator sponsorship."
    if aggregate.get("concentration_flag"):
        caution = caution or f"Flow concentration in {primary} — breadth thin."

    change_mind = f"{primary} 5D % AUM turns negative while node posture stays constructive."
    if degrade_mode == "partial_basket":
        change_mind = f"Full basket coverage restored with {primary} 5D confirming node thesis."

    return {
        "supports_node_thesis": supports,
        "divergence_flag": divergence_flag,
        "summary": summary,
        "caution_line": caution,
        "change_mind_trigger": change_mind,
        "degrade_notice": degrade_notice,
    }


def _node_label(node_cockpit: Mapping[str, Any]) -> str:
    name = str(node_cockpit.get("display_name") or node_cockpit.get("node_id") or "node")
    return name.split("&")[0].strip().lower() or "node"


def resolve_degrade_mode(
    sidecar: Mapping[str, Any] | None,
    node_id: str,
    basket_spec: Mapping[str, Any],
) -> str:
    if not sidecar:
        return "unavailable"

    ingest_mode = str(sidecar.get("ingest_mode") or "disabled")
    etfs = list(basket_spec.get("etfs") or [])

    if ingest_mode == "fallback_1d_only":
        if node_id == "credit":
            return "fallback_1d_credit"
        return "unavailable"

    if ingest_mode != "timeseries_primary":
        return "unavailable"

    populated_5d = 0
    populated_any = 0
    for etf in etfs:
        row = compute_etf_row(node_id, etf, sidecar, degrade_mode="full")
        if row["data_status"] != "missing":
            populated_any += 1
        if row.get("flow_pct_aum_5d") is not None:
            populated_5d += 1

    if populated_5d == 0 and populated_any == 0:
        return "unavailable"
    if populated_5d < len(etfs):
        return "partial_basket"
    return "full"


def _build_flows_meta(degrade_mode: str, node_id: str, sidecar: Mapping[str, Any] | None) -> dict[str, Any]:
    meta = dict(_FLOWS_META_MAP.get(degrade_mode, _FLOWS_META_MAP["unavailable"]))
    meta["degrade_mode"] = degrade_mode
    if degrade_mode == "unavailable":
        if sidecar and str(sidecar.get("ingest_mode")) == "fallback_1d_only" and node_id != "credit":
            meta["fallback_reason"] = "non_credit_node_no_fallback"
        elif not sidecar:
            meta["fallback_reason"] = "missing_wtm_flows_file"
        else:
            meta["fallback_reason"] = meta.get("fallback_reason") or "missing_wtm_flows_file"
    return meta


def build_funds_flows(
    node_id: str,
    *,
    sidecar: Mapping[str, Any] | None,
    node_cockpit: Mapping[str, Any],
    basket_spec: Mapping[str, Any] | None = None,
    as_of: str = "",
) -> dict[str, Any]:
    """Build L2 funds_flows block for one node cockpit."""
    basket = basket_spec or funds_flow_basket_for_node(node_id) or {}
    degrade_mode = resolve_degrade_mode(sidecar, node_id, basket)
    flows_meta = _build_flows_meta(degrade_mode, node_id, sidecar)
    session_as_of = as_of or (sidecar or {}).get("as_of") or str(node_cockpit.get("as_of") or "")[:10]

    if degrade_mode == "unavailable":
        return {
            "enabled": False,
            "source": "derived",
            "degrade_mode": degrade_mode,
            "as_of": session_as_of,
            "horizon_display": "5d",
            "basket_id": basket.get("basket_id") or "",
            "basket_label": basket.get("basket_label") or "",
            "node_id": node_id,
            "flows_meta": flows_meta,
            "aggregate": {"verdict": "neutral", "confidence_delta": 0},
            "etfs": [],
            "interpretation": build_interpretation(
                verdict="neutral",
                aggregate={},
                node_cockpit=node_cockpit,
                degrade_mode=degrade_mode,
                divergence_flag=False,
                basket_spec=basket,
            ),
        }

    etf_rows = [
        compute_etf_row(node_id, etf, sidecar, degrade_mode=degrade_mode)
        for etf in basket.get("etfs", [])
    ]
    aggregate = compute_aggregate(
        etf_rows,
        node_id=node_id,
        basket_spec=basket,
        degrade_mode=degrade_mode,
    )
    verdict, confidence_delta, divergence_flag = assign_verdict(
        aggregate,
        node_cockpit,
        funds_flow_thresholds(),
        degrade_mode,
    )
    aggregate["verdict"] = verdict
    aggregate["confidence_delta"] = confidence_delta

    horizon = "1d" if degrade_mode == "fallback_1d_credit" else "5d"
    etf_rows.sort(
        key=lambda r: (
            0 if r["basket_role"] == "primary" else 1,
            -abs(float(r["flow_pct_aum_5d"] or r["flow_pct_aum_1d"] or 0)),
        ),
    )

    return {
        "enabled": True,
        "source": "derived",
        "degrade_mode": degrade_mode,
        "as_of": session_as_of,
        "horizon_display": horizon,
        "basket_id": basket.get("basket_id") or "",
        "basket_label": basket.get("basket_label") or "",
        "node_id": node_id,
        "flows_meta": flows_meta,
        "aggregate": aggregate,
        "etfs": etf_rows,
        "interpretation": build_interpretation(
            verdict=verdict,
            aggregate=aggregate,
            node_cockpit=node_cockpit,
            degrade_mode=degrade_mode,
            divergence_flag=divergence_flag,
            basket_spec=basket,
        ),
    }


def apply_confidence_delta(confidence: str, funds_flows: Mapping[str, Any]) -> str:
    """Clamp confidence tier after applying funds_flow confidence_delta."""
    meta = funds_flows.get("flows_meta") or {}
    penalty = int(meta.get("flows_confidence_penalty") or 0)
    delta = int((funds_flows.get("aggregate") or {}).get("confidence_delta") or 0)
    if penalty >= 2:
        delta = 0
    elif penalty >= 1:
        delta = min(delta, 0)

    tier = confidence if confidence in _CONFIDENCE_TIERS else "low"
    idx = _CONFIDENCE_TIERS.index(tier)
    idx = max(0, min(len(_CONFIDENCE_TIERS) - 1, idx + delta))
    return _CONFIDENCE_TIERS[idx]


def merge_flow_rationale(base_rationale: str, funds_flows: Mapping[str, Any]) -> str:
    """Suffix-only rationale merge per spec §2.1."""
    rationale = (base_rationale or "").strip()
    degrade = str(funds_flows.get("degrade_mode") or "")
    interp = funds_flows.get("interpretation") or {}
    verdict = (funds_flows.get("aggregate") or {}).get("verdict")

    if degrade == "fallback_1d_credit":
        suffix = " (Flows: 1D fallback only — treat as indicative.)"
        return rationale + suffix if rationale else suffix.strip()

    if verdict in ("supportive", "diverging") and interp.get("summary"):
        suffix = f" {interp['summary']} (Flows: {verdict}.)"
        return rationale + suffix if rationale else suffix.strip()
    return rationale