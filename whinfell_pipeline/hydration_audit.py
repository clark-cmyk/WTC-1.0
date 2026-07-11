"""Field-by-field hydration audit for Transmission Control (production traceability)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

HYDRATION_AUDIT_VERSION = "1.0.0"

_NODE_IDS = ("liquidity", "credit", "breadth", "highbeta", "basis")
_EMPTY = (None, "", [], {})


def _is_empty(value: Any) -> bool:
    return value in _EMPTY


def _get_path(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(part)
    return cur


def _classify_value(value: Any, *, required: bool) -> str:
    if _is_empty(value):
        return "empty" if required else "optional_empty"
    return "ok"


def _rv_horizon_count(cockpit: Mapping[str, Any]) -> int:
    rv = cockpit.get("rv_basis") or {}
    sid = rv.get("active_series_id")
    if not sid:
        return 0
    series = (rv.get("series") or {}).get(sid) or {}
    return len(series.get("horizons") or {})


def _node_signals_status(cockpit: Mapping[str, Any]) -> str:
    inputs = list(cockpit.get("component_inputs") or [])
    score_source = str(cockpit.get("composite_score_source") or "")
    if not inputs:
        if score_source == "horizon_net_fallback":
            return "partial"
        return "miss"
    unavailable = sum(1 for c in inputs if str(c.get("value", "")).lower() == "unavailable")
    fallback = sum(1 for c in inputs if c.get("source") == "horizon_fallback")
    if unavailable >= len(inputs):
        return "miss"
    if unavailable or fallback > len(inputs) // 2:
        return "partial"
    return "ok"


def _bundle_quality_score(bundle: Mapping[str, Any]) -> int:
    """Mirror TC scoreHydrationBundleQuality (Python-side for audit log)."""
    score = 0
    flows = _get_path(bundle, "flows_sidecar.flows_status")
    if flows == "ok":
        score += 40
    elif flows in ("partial", "fallback_1d"):
        score += 22
    elif flows == "unavailable":
        score += 4
    cockpits = bundle.get("node_cockpits")
    if not isinstance(cockpits, Mapping):
        return score
    score += 10
    for node_id in _NODE_IDS:
        cockpit = cockpits.get(node_id)
        if not isinstance(cockpit, Mapping):
            continue
        score += 2
        if _rv_horizon_count(cockpit) >= 5:
            score += 4
        fm = _get_path(cockpit, "funds_flows.flows_meta.flows_status")
        if fm == "ok":
            score += 2
        elif fm and fm != "unavailable":
            score += 1
    return score


def _session_level(bundle: Mapping[str, Any], quality: int) -> str:
    if bundle.get("validation_status") == "missing":
        return "missing"
    cockpits = bundle.get("node_cockpits")
    if not isinstance(cockpits, Mapping) or not all(node_id in cockpits for node_id in _NODE_IDS):
        return "stale"
    if quality < 45:
        return "incomplete"
    return "ok"


def _field_row(
    *,
    section: str,
    field: str,
    bundle_path: str,
    ui_target: str,
    value: Any,
    required: bool,
    notes: str = "",
    status: str | None = None,
) -> dict[str, Any]:
    st = status or _classify_value(value, required=required)
    return {
        "section": section,
        "field": field,
        "bundle_path": bundle_path,
        "ui_target": ui_target,
        "status": st,
        "required": required,
        "value": value if not isinstance(value, (dict, list)) else ("…" if value else None),
        "value_preview": _preview(value),
        "notes": notes,
    }


def _preview(value: Any) -> str:
    if _is_empty(value):
        return "—"
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, str):
        return value[:120] + ("…" if len(value) > 120 else "")
    if isinstance(value, Mapping):
        return f"dict({len(value)} keys)"
    if isinstance(value, list):
        return f"list({len(value)} items)"
    return str(value)


def build_hydration_audit(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Produce field-by-field hydration audit for bundle + TC mapping."""
    fields: list[dict[str, Any]] = []
    remediation: list[dict[str, Any]] = []

    def add(
        section: str,
        field: str,
        path: str,
        ui: str,
        *,
        required: bool = True,
        notes: str = "",
        status: str | None = None,
        value: Any | None = None,
    ) -> None:
        val = value if value is not None else _get_path(bundle, path)
        row = _field_row(
            section=section,
            field=field,
            bundle_path=path,
            ui_target=ui,
            value=val,
            required=required,
            notes=notes,
            status=status,
        )
        fields.append(row)
        if row["status"] in ("empty", "miss") and required:
            remediation.append(
                {
                    "priority": "high",
                    "field": f"{section}.{field}",
                    "bundle_path": path,
                    "ui_target": ui,
                    "action": notes or f"Populate {path} in pipeline or staged ingest",
                }
            )
        elif row["status"] == "partial":
            remediation.append(
                {
                    "priority": "medium",
                    "field": f"{section}.{field}",
                    "bundle_path": path,
                    "ui_target": ui,
                    "action": notes or f"Review fallback for {path}",
                }
            )

    # --- Provenance / bundle header ---
    add("provenance", "snapshot_id", "snapshot_id", "command bar · provenance")
    add("provenance", "lineage_hash", "lineage_hash", "command bar · lineage")
    add("provenance", "as_of", "as_of", "freshness chip · data as-of")
    add("provenance", "freshness_status", "freshness_status", "freshness chip")
    add("provenance", "validation_status", "validation_status", "import guard")
    add("provenance", "hydration_version", "hydration_version", "import compatibility", required=True)

    # --- Global intake → DOM ---
    add("global_intake", "whinfell_score", "global.whinfell_score", "#whinfellScore")
    add("global_intake", "transmission_state", "global.transmission_state", "#transmissionState")
    add("global_intake", "regime_tag", "global.regime_tag", "#regimeTag")
    add("global_intake", "key_observation", "global.key_observation", "#keyObservation · handover")
    add("global_intake", "gate_status", "global.gate_status", "gate chip", required=False,
        notes="Often derived in TC from score + transmission; parquet may leave empty")
    add("global_intake", "btc_bias", "global.btc_bias", "BTC bias · execution rail")

    # --- China intake ---
    add("china_intake", "policy_strength", "china.policy_strength", "#chinaPolicyStrength")
    add("china_intake", "state_impulse_score", "china.state_impulse_score", "#chinaStateImpulse")
    add("china_intake", "growth_impulse_score", "china.growth_impulse_score", "#chinaGrowthImpulse")
    add("china_intake", "sq3_score", "china.sq3_score", "SQ3 chip · command bar")
    add("china_intake", "regime_tag", "china.regime_tag", "#chinaRegimeTag")
    add("china_intake", "as_of", "china.as_of", "China freshness", required=False)

    # --- L3 / execution ---
    for key, dom in (
        ("near_month", "L3 near month"),
        ("far_month", "L3 far month"),
        ("basis_spread", "L3 basis spread"),
        ("ref_low", "L3 ref low"),
        ("ref_mid", "L3 ref mid"),
        ("ref_high", "L3 ref high"),
    ):
        add("execution_l3", key, f"execution.{key}", dom)
    add("execution_l3", "btc_bias", "execution.btc_bias", "Layer 2/3 BTC bias")

    # --- Flows sponsorship ---
    flows_status = _get_path(bundle, "flows_sidecar.flows_status")
    add("flows", "flows_status", "flows_sidecar.flows_status", "coverage · flows pill")
    add("flows", "flows_as_of", "flows_sidecar.as_of", "flows sponsorship as-of", required=False,
        notes="Re-export WTM-Flows-Global.csv when stale")
    add("flows", "ticker_count", "flows_sidecar.ticker_count", "funds-flow card", required=False)

    # --- Node cockpits ---
    nodes_out: dict[str, Any] = {}
    cockpits = bundle.get("node_cockpits") or {}
    for node_id in _NODE_IDS:
        cockpit = cockpits.get(node_id) if isinstance(cockpits, Mapping) else None
        if not isinstance(cockpit, Mapping):
            add("node_cockpits", node_id, f"node_cockpits.{node_id}", f"node shell · {node_id}",
                status="empty", notes="Missing node cockpit block")
            continue

        rv_count = _rv_horizon_count(cockpit)
        comp_inputs = list(cockpit.get("component_inputs") or [])
        score_source = str(cockpit.get("composite_score_source") or "")
        signals = _node_signals_status(cockpit)
        flows_node = _get_path(cockpit, "funds_flows.flows_meta.flows_status")

        rv_status = "ok" if rv_count >= 5 else ("partial" if rv_count else "empty")
        add(
            "node_rv",
            f"{node_id}.rv_horizons",
            f"node_cockpits.{node_id}.rv_basis",
            f"CURRENT READING · RV chart · {node_id}",
            required=True,
            status=rv_status,
            value=rv_count,
            notes=f"{rv_count}/5 horizons on active series",
        )

        if node_id == "credit" and not comp_inputs:
            comp_status = "partial"
            comp_notes = (
                "Credit uses authoritative RV + horizon-net composite (C1 doc); "
                "component_inputs intentionally empty — not a ingest failure"
            )
        else:
            live = sum(1 for c in comp_inputs if c.get("source") == "rv_history")
            comp_status = "ok" if live >= 2 else ("partial" if comp_inputs else "empty")
            comp_notes = f"{live} rv_history · {len(comp_inputs)} total components"

        add(
            "node_signals",
            f"{node_id}.component_inputs",
            f"node_cockpits.{node_id}.component_inputs",
            f"mission read diagnostics · {node_id}",
            required=node_id != "credit",
            status=comp_status,
            value=len(comp_inputs),
            notes=comp_notes,
        )

        add(
            "node_flows",
            f"{node_id}.flows_status",
            f"node_cockpits.{node_id}.funds_flows.flows_meta.flows_status",
            f"funds-flow card · {node_id}",
            required=False,
            status="ok" if flows_node == "ok" else ("partial" if flows_node else "empty"),
            value=flows_node,
        )

        node_fields = [f for f in fields if f["field"].startswith(f"{node_id}.") or node_id in f.get("bundle_path", "")]
        nodes_out[node_id] = {
            "composite_score": cockpit.get("composite_score"),
            "composite_score_source": score_source,
            "rv_horizon_count": rv_count,
            "rv_richness": _get_path(cockpit, "rv_basis.richness_label"),
            "component_count": len(comp_inputs),
            "signals_status": signals,
            "flows_status": flows_node,
            "fields": [
                f for f in fields
                if f["section"] in ("node_rv", "node_signals", "node_flows")
                and f["field"].startswith(f"{node_id}.")
            ],
        }

        if rv_status != "ok":
            remediation.append({
                "priority": "high",
                "field": f"node.{node_id}.rv_basis",
                "bundle_path": f"node_cockpits.{node_id}.rv_basis",
                "ui_target": f"RV chart · {node_id}",
                "action": "Re-run barchart history + dated_series; verify rv_history keys in data/rv/v1",
            })

        for comp in comp_inputs:
            if str(comp.get("value", "")).lower() == "unavailable":
                remediation.append({
                    "priority": "medium",
                    "field": f"node.{node_id}.{comp.get('label', comp.get('asset_id'))}",
                    "bundle_path": f"node_cockpits.{node_id}.component_inputs",
                    "ui_target": f"mission diagnostics · {node_id}",
                    "action": f"Map RV history for component {comp.get('asset_id')} or accept horizon_fallback",
                })

    # --- Summary counts ---
    status_counts: dict[str, int] = {}
    for row in fields:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    required_rows = [r for r in fields if r["required"]]
    required_ok = sum(1 for r in required_rows if r["status"] == "ok")
    quality = _bundle_quality_score(bundle)
    session = _session_level(bundle, quality)

    return {
        "audit_version": HYDRATION_AUDIT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": bundle.get("snapshot_id"),
        "lineage_hash": bundle.get("lineage_hash"),
        "summary": {
            "total_fields": len(fields),
            "required_fields": len(required_rows),
            "required_ok": required_ok,
            "status_counts": status_counts,
            "bundle_quality_score": quality,
            "tc_session_level": session,
            "coverage_pct": round(100.0 * required_ok / max(len(required_rows), 1), 1),
        },
        "fields": fields,
        "nodes": nodes_out,
        "remediation": remediation[:40],
    }


def write_hydration_log(bundle: Mapping[str, Any], path: Any) -> dict[str, Any]:
    """Build audit and write standalone hydration_log.json."""
    from pathlib import Path

    audit = build_hydration_audit(bundle)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(__import__("json").dumps(audit, indent=2), encoding="utf-8")
    return audit