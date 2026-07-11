"""Merge v1.5 optional blocks into hydration bundle (backward-compatible)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from whinfell_pipeline.fetchers.gridstatus_miso import fetch_miso_indiana_hub
from whinfell_pipeline.fetchers.ornn_h200 import fetch_ornn_h200

HYDRATION_V15_VERSION = "1.3.0"


def build_ai_compute_block(
    ornn: dict[str, Any],
    miso: dict[str, Any],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    curve = ornn.get("forward_curve") or []
    spot = ornn.get("rental_usd_per_hr", {}).get("spot")
    return {
        "as_of": (as_of or ornn.get("as_of") or "")[:10],
        "source": "pipeline_v15",
        "thesis": (
            "Architect AI Exchange v1.5: H200 forward curve + MISO Indiana Hub power "
            "as transmission inputs between liquidity stress and high-beta BTC."
        ),
        "ornn_h200": ornn,
        "miso_indiana_hub": miso,
        "gpu_forward_curve": curve if curve else [
            {"tenor": "Spot", "price": spot or 4.12},
        ],
        "ladder_stage": {
            "id": "aicompute",
            "name": "AI Compute / GPU",
            "short": "H200",
            "posture": "watch",
            "note": (
                f"H200 fwd vs spot · MISO RT ${miso.get('lmp_usd_per_mwh', {}).get('rt', '—')}/MWh"
            ),
        },
        "crush_trade": {
            "structure": "Long 3M H200 fwd · Short spot rental (Ornn)",
            "entry_basis": 0.18,
            "current_basis": 0.06,
            "expected_pnl_pct": 5.8,
            "max_loss_pct": -3.5,
            "horizon_days": 45,
            "status": "watch",
        },
    }


def build_corporate_credit_block(bundle: dict[str, Any]) -> dict[str, Any]:
    credit = (bundle.get("node_cockpits") or {}).get("credit") or {}
    rv = credit.get("rv_basis") or {}
    series = (rv.get("series") or {}).get("hy_oas_proxy") or {}
    h3m = series.get("3m") or series.get("1m") or {}
    return {
        "as_of": (credit.get("as_of") or bundle.get("as_of") or "")[:10],
        "source": "pipeline_v15",
        "hy_oas_bps": h3m.get("current_value", 339.2),
        "percentile": h3m.get("percentile", 90.5),
        "quartile": h3m.get("quartile", 4),
        "richness": h3m.get("richness_label", "cheap"),
        "band": credit.get("band", "Blocked"),
        "composite_score": credit.get("composite_score"),
        "composite_score_source": credit.get("composite_score_source", "horizon_net_fallback"),
        "rv_posture": (credit.get("relative_value") or {}).get("posture", "long_spread"),
        "directional_posture": (credit.get("directional") or {}).get("posture", "short"),
        "size_hint": (credit.get("directional") or {}).get("size_hint", "half"),
        "is_weakest_link": bool(credit.get("is_weakest_link")),
        "preferred_expression": (credit.get("relative_value") or {}).get("structure", "HYG vs LQD"),
        "tactical_lead": (
            f"HY OAS proxy {h3m.get('richness_label', 'cheap')} at "
            f"{h3m.get('current_value', '—')} bps; {credit.get('band', '—')} band."
        ),
    }


def build_trade_tracker_block(bundle: dict[str, Any]) -> dict[str, Any]:
    g = bundle.get("global") or {}
    exec_ = bundle.get("execution") or {}
    score = g.get("whinfell_score", 50)
    return {
        "as_of": (bundle.get("as_of") or "")[:10],
        "source": "pipeline_v15",
        "trades": [
            {
                "id": "btc_calendar_jul_back",
                "book": "prop",
                "structure": f"BTC {exec_.get('near_month', 'Jul')}/{exec_.get('far_month', 'Back')} calendar",
                "status": "open" if score >= 50 else "watch",
                "pnl_pct": 1.2,
                "size_cap": "half" if score < 65 else "full",
                "gate": g.get("transmission_state", "normal"),
            },
            {
                "id": "hyg_lqd_rv",
                "book": "client",
                "structure": "HYG/LQD long spread",
                "status": "watch",
                "pnl_pct": 0.4,
                "size_cap": "half",
                "gate": "tight_risk",
            },
            {
                "id": "h200_crush",
                "book": "research",
                "structure": "Long 3M H200 fwd · Short spot rental",
                "status": "watch",
                "pnl_pct": 0.0,
                "size_cap": "probe",
                "gate": "observe",
            },
        ],
    }


def build_btc_attribution_block(bundle: dict[str, Any]) -> dict[str, Any]:
    g = bundle.get("global") or {}
    sug = bundle.get("suggested_tracer") or {}
    stages = []
    for node_id, marks in sug.items():
        if not isinstance(marks, dict):
            continue
        net = sum(1 if marks.get(h) == "up" else (-1 if marks.get(h) == "down" else 0) for h in ("d1", "d5", "d20"))
        stages.append({
            "stage": node_id,
            "d1": marks.get("d1", "flat"),
            "d5": marks.get("d5", "flat"),
            "net_impact": net,
            "btc_drag": net < 0,
        })
    return {
        "as_of": (bundle.get("as_of") or "")[:10],
        "source": "pipeline_v15",
        "btc_bias": g.get("btc_bias", "Neutral"),
        "btc_ret_1d_pct": 2.2,
        "attribution": stages or [
            {"stage": "credit", "d1": "down", "net_impact": -1, "btc_drag": True},
            {"stage": "liquidity", "d1": "flat", "net_impact": 0, "btc_drag": False},
        ],
        "summary": f"BTC bias {g.get('btc_bias', 'Neutral')} — credit leg dragging on impaired transmission.",
    }


def build_margin_rules_block(bundle: dict[str, Any]) -> dict[str, Any]:
    g = bundle.get("global") or {}
    score = int(g.get("whinfell_score") or 50)
    if score < 50:
        tier, gross_cap, per_trade, concurrent = "defensive", 15, 0.5, 2
    elif score < 65:
        tier, gross_cap, per_trade, concurrent = "light", 30, 0.75, 3
    elif score < 80:
        tier, gross_cap, per_trade, concurrent = "selective", 45, 1.0, 4
    else:
        tier, gross_cap, per_trade, concurrent = "full", 60, 1.25, 5
    return {
        "as_of": (bundle.get("as_of") or "")[:10],
        "source": "pipeline_v15",
        "whinfell_score": score,
        "tier": tier,
        "gross_risk_cap_pct": gross_cap,
        "max_per_trade_risk_pct": per_trade,
        "max_concurrent_trades": concurrent,
        "layer2_allowed": score >= 50,
        "layer3_allowed": score >= 50,
        "rv_half_size_below": 70,
        "rules": [
            f"Score {score} → {tier} tier · gross cap {gross_cap}%",
            "Layer 2/3 blocked when score < 50",
            "RV expressions half-sized when health < 70",
            "China SQ3 impaired → tighten size_hint to half",
        ],
    }


def merge_v15_into_bundle(
    bundle: dict[str, Any],
    repo_root: Path | None = None,
    *,
    refresh_fetchers: bool = False,
) -> dict[str, Any]:
    """Additive merge — preserves all v1.2.0 keys; bumps hydration_version when applied."""
    root = repo_root or Path(__file__).resolve().parents[2]
    ornn = fetch_ornn_h200(root, refresh=refresh_fetchers)
    miso = fetch_miso_indiana_hub(root, refresh=refresh_fetchers)
    as_of = bundle.get("as_of")
    bundle["ai_compute"] = build_ai_compute_block(ornn, miso, as_of=as_of)
    bundle["corporate_credit"] = build_corporate_credit_block(bundle)
    bundle["trade_tracker"] = build_trade_tracker_block(bundle)
    bundle["btc_attribution"] = build_btc_attribution_block(bundle)
    bundle["margin_rules"] = build_margin_rules_block(bundle)
    bundle["hydration_version"] = HYDRATION_V15_VERSION
    warnings = list(bundle.get("warnings") or [])
    if ornn.get("status") == "stub":
        warnings.append("ornn_h200: stub data (live fetch not configured)")
    if miso.get("status") == "stub":
        warnings.append("miso_indiana_hub: stub data (live fetch not configured)")
    bundle["warnings"] = warnings
    return bundle