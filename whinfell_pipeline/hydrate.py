#!/usr/bin/env python3
"""Parquet → hydration bundle for Transmission Control import."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from china_policy_track.sq3 import calculate_sq3
from china_policy_track.storage import default_parquet_path as china_default
from china_policy_track.storage import read_observations as read_china
from whinfell_pipeline.export_contract import ProvenanceMeta, build_wtm_export_v21, build_wtm_export_v22
from whinfell_pipeline.ingest_provenance import collect_staged_ingest_provenance
from whinfell_pipeline.flows_parser import assess_flows_basket_health, ensure_flows_sidecar
from whinfell_pipeline.funds_flows import build_flows_sidecar_metadata
from whinfell_pipeline.node_cockpits import build_cockpit_context, build_node_cockpits
from whinfell_pipeline.rv_history import ensure_dated_series_fixture, load_rv_history
from whinfell_pipeline.freshness import compute_freshness
from whinfell_pipeline.global_track.storage import default_parquet_path as global_default
from whinfell_pipeline.global_track.storage import read_observations as read_global
from whinfell_pipeline.lineage import compute_lineage_hash
from whinfell_pipeline.hydration_audit import build_hydration_audit, write_hydration_log
from whinfell_pipeline.fetchers.v15_blocks import HYDRATION_V15_VERSION, merge_v15_into_bundle
from whinfell_pipeline.version import BUNDLE_VERSION, PIPELINE_VERSION

HYDRATION_BUNDLE_VERSION = HYDRATION_V15_VERSION

_STAGE_IDS = ("liquidity", "credit", "breadth", "highbeta", "basis")
_L3_FIELD_KEYS = ("near_month", "far_month", "basis_spread", "ref_low", "ref_mid", "ref_high")


def default_execution_json_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "data" / "execution" / "v1" / "latest_execution.json"


def default_crypto_json_path(repo_root: Path | None = None) -> Path:
    from whinfell_pipeline.crypto_sleeve import default_crypto_json_path

    return default_crypto_json_path(repo_root)


def _load_execution_payload(path: Path | None = None) -> dict[str, Any]:
    p = path or default_execution_json_path()
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        return dict(data["payload"])
    return dict(data) if isinstance(data, dict) else {}


def _load_crypto_payload(path: Path | None = None) -> dict[str, Any]:
    from whinfell_pipeline.crypto_sleeve import hydration_crypto_block, load_crypto_sidecar

    payload = load_crypto_sidecar(path)
    if not payload:
        return {}
    return hydration_crypto_block(payload)


def _merge_l3_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in _L3_FIELD_KEYS:
        val = source.get(key)
        if val not in (None, ""):
            target[key] = val


def _horizon(d1: str, d5: str | None = None, d20: str | None = None, d60: str | None = None) -> dict[str, str]:
    d5 = d5 if d5 is not None else d1
    d20 = d20 if d20 is not None else d5
    d60 = d60 if d60 is not None else d20
    return {"d1": d1, "d5": d5, "d20": d20, "d60": d60}


def derive_btc_bias(key_observation: str) -> str:
    """Infer BTC bias label from observation text (deterministic)."""
    lower = (key_observation or "").lower()
    if any(p in lower for p in ("btc lagging", "btc dragging", "btc weak", "ibit lagging", "btc lag")):
        return "Dragging"
    if any(p in lower for p in ("btc confirming", "btc leading", "btc supportive", "ibit leading")):
        return "Confirming"
    return "Neutral"


def derive_suggested_tracer(
    global_payload: dict[str, Any],
    china_payload: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Pure heuristic tracer suggestions for rates/credit/BTC/basis stages."""
    obs = (global_payload.get("key_observation") or "").lower()
    score = int(global_payload.get("whinfell_score") or 50)
    tx = (global_payload.get("transmission_state") or "normal").lower()
    state_imp = int(china_payload.get("state_impulse_score") or 0)
    tracer: dict[str, dict[str, str]] = {}

    if any(w in obs for w in ("rates up", "curve steep", "yields rising", "liquidity tightening")):
        tracer["liquidity"] = _horizon("down", "down", "down", "flat")
    elif any(w in obs for w in ("rates down", "curve bull", "liquidity easing")):
        tracer["liquidity"] = _horizon("up", "up", "flat", "flat")
    elif tx in ("disorderly", "crisis"):
        tracer["liquidity"] = _horizon("down", "down", "down", "down")
    elif tx == "stressed":
        tracer["liquidity"] = _horizon("flat", "flat", "down", "flat")
    else:
        tracer["liquidity"] = _horizon("flat", "flat", "flat", "flat")

    if "credit" in obs and any(w in obs for w in ("mixed", "widen", "impair", "weak", "stress")):
        tracer["credit"] = _horizon("down", "down", "flat", "flat")
    elif "credit" in obs and any(w in obs for w in ("tight", "firm", "constructive", "improving")):
        tracer["credit"] = _horizon("up", "up", "flat", "flat")
    elif score < 50:
        tracer["credit"] = _horizon("down", "down", "down", "flat")
    elif score < 65:
        tracer["credit"] = _horizon("flat", "down", "flat", "flat")
    else:
        tracer["credit"] = _horizon("up", "flat", "up", "flat")

    if any(w in obs for w in ("breadth narrowing", "narrowing breadth", "breadth weak")):
        tracer["breadth"] = _horizon("flat", "down", "down", "flat")
    elif "breadth" in obs and any(w in obs for w in ("improving", "broad", "strong", "participation")):
        tracer["breadth"] = _horizon("up", "up", "flat", "flat")
    elif score >= 65:
        tracer["breadth"] = _horizon("flat", "up", "up", "flat")
    else:
        tracer["breadth"] = _horizon("flat", "flat", "flat", "flat")

    bias = derive_btc_bias(global_payload.get("key_observation") or "")
    if bias == "Dragging":
        tracer["highbeta"] = _horizon("down", "down", "flat", "flat")
    elif bias == "Confirming":
        tracer["highbeta"] = _horizon("up", "up", "flat", "flat")
    else:
        tracer["highbeta"] = _horizon("flat", "flat", "flat", "flat")

    if any(w in obs for w in ("contango", "basis rich", "calendar rich")):
        tracer["basis"] = _horizon("flat", "up", "up", "flat")
    elif any(w in obs for w in ("backwardation", "basis cheap", "calendar cheap")):
        tracer["basis"] = _horizon("flat", "down", "down", "flat")
    elif state_imp > 30:
        tracer["basis"] = _horizon("flat", "flat", "down", "flat")
    else:
        tracer["basis"] = _horizon("flat", "flat", "flat", "flat")

    return tracer


def derive_china_ladder_horizons(china_payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Seed China ladder stage horizons from SQ3 / policy impulses (desk heuristic)."""
    policy = int(china_payload.get("policy_strength") or 50)
    state = int(china_payload.get("state_impulse_score") or 0)
    growth = int(china_payload.get("growth_impulse_score") or 50)
    sq3 = int(china_payload.get("sq3_score") or 50)

    if state > 40:
        liquidity = _horizon("up", "up", "up", "flat")
    elif state > 25:
        liquidity = _horizon("flat", "flat", "flat", "flat")
    else:
        liquidity = _horizon("flat", "flat", "down", "flat")

    if policy >= 70:
        credit = _horizon("up", "flat", "flat", "flat")
    elif policy >= 55:
        credit = _horizon("flat", "flat", "flat", "down")
    else:
        credit = _horizon("down", "down", "flat", "down")

    if growth >= 60:
        breadth = _horizon("up", "up", "flat", "flat")
    elif growth >= 45:
        breadth = _horizon("up", "flat", "flat", "flat")
    else:
        breadth = _horizon("flat", "down", "down", "flat")

    if state < 30:
        highbeta = _horizon("flat", "down", "flat", "flat")
    elif growth >= 55 and policy >= 60:
        highbeta = _horizon("up", "up", "flat", "flat")
    else:
        highbeta = _horizon("flat", "flat", "flat", "flat")

    if state > 35 and sq3 >= 65:
        basis = _horizon("flat", "up", "up", "flat")
    elif state < 25:
        basis = _horizon("flat", "flat", "down", "flat")
    else:
        basis = _horizon("flat", "flat", "flat", "flat")

    return {
        "liquidity": liquidity,
        "credit": credit,
        "breadth": breadth,
        "highbeta": highbeta,
        "basis": basis,
    }


def derive_execution_payload(
    global_payload: dict[str, Any],
    china_payload: dict[str, Any],
    *,
    btc_bias: str,
) -> dict[str, Any]:
    """High-signal execution hints for L3 / research (basis + BTC bias)."""
    return {
        "btc_bias": btc_bias,
        "near_month": global_payload.get("near_month") or "",
        "far_month": global_payload.get("far_month") or "",
        "basis_spread": global_payload.get("basis_spread") or "",
        "ref_low": global_payload.get("ref_low") or "",
        "ref_mid": global_payload.get("ref_mid") or "",
        "ref_high": global_payload.get("ref_high") or "",
        "policy_strength": china_payload.get("policy_strength"),
        "state_impulse_score": china_payload.get("state_impulse_score"),
        "growth_impulse_score": china_payload.get("growth_impulse_score"),
        "source": global_payload.get("source") or china_payload.get("source") or "parquet",
    }


def _latest_by_as_of(rows: list[Any]) -> Any | None:
    if not rows:
        return None
    return max(rows, key=lambda r: r.as_of)


def _china_to_sq3_payload(obs) -> dict[str, Any]:
    ph = obs.policy_hierarchy_strength
    sc = obs.state_control_impulse
    gm = obs.growth_market_impulse
    sq3 = calculate_sq3(ph.policy_strength, sc.impulse_score, gm.growth_impulse_score)
    return {
        "policy_strength": ph.policy_strength,
        "state_impulse_score": sc.impulse_score,
        "growth_impulse_score": gm.growth_impulse_score,
        "sq3_score": sq3.sq3_score,
        "sq3_band": sq3.interpretation_band,
        "regime_tag": ph.dominant_theme,
        "observation_id": obs.observation_id,
        "as_of": obs.as_of.isoformat(),
        "source": obs.source,
    }


def build_hydration_bundle(
    *,
    global_path: Path | None = None,
    china_path: Path | None = None,
    execution_path: Path | None = None,
    crypto_path: Path | None = None,
    flows_sidecar: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Read latest Parquet rows and build console hydration JSON."""
    g_obs = _latest_by_as_of(read_global(global_path or global_default()))
    c_obs = _latest_by_as_of(read_china(china_path or china_default()))

    if not g_obs and not c_obs:
        raise ValueError("No observations in Global or China Parquet files")

    global_payload: dict[str, Any] = {}
    china_payload: dict[str, Any] = {}
    provenance_source = "parquet"
    data_as_of = datetime.now(timezone.utc)
    snapshot_id = "snap_parquet_unknown"
    lineage_hash = ""
    validation_status = "parsed"

    if g_obs:
        global_payload = {
            "observation_id": g_obs.observation_id,
            "whinfell_score": g_obs.whinfell_score,
            "transmission_state": g_obs.transmission_state,
            "regime_tag": g_obs.regime_tag,
            "key_observation": g_obs.key_observation,
            "gate_status": g_obs.gate_status,
            "sq3_score": g_obs.sq3_score,
            "sq3_band": g_obs.sq3_band,
        }
        data_as_of = g_obs.as_of if g_obs.as_of.tzinfo else g_obs.as_of.replace(tzinfo=timezone.utc)
        snapshot_id = g_obs.snapshot_id or g_obs.observation_id
        lineage_hash = g_obs.lineage_hash or ""
        validation_status = g_obs.validation_status or "parsed"
        provenance_source = g_obs.source or "parquet"

    if c_obs:
        china_payload = _china_to_sq3_payload(c_obs)
        if not g_obs:
            data_as_of = c_obs.as_of if c_obs.as_of.tzinfo else c_obs.as_of.replace(tzinfo=timezone.utc)
            snapshot_id = c_obs.observation_id
            provenance_source = c_obs.source

    if not global_payload.get("sq3_score") and china_payload.get("sq3_score"):
        global_payload["sq3_score"] = china_payload["sq3_score"]
        global_payload["sq3_band"] = china_payload["sq3_band"]

    exec_sidecar = _load_execution_payload(execution_path)
    if exec_sidecar:
        _merge_l3_fields(global_payload, exec_sidecar)

    crypto_block = _load_crypto_payload(crypto_path)

    btc_bias = derive_btc_bias(global_payload.get("key_observation") or "")
    global_payload["btc_bias"] = btc_bias
    suggested_tracer = derive_suggested_tracer(global_payload, china_payload)
    china_ladder: dict[str, Any] = {}
    if china_payload:
        china_ladder = {
            "sq3_score": china_payload.get("sq3_score"),
            "horizons": derive_china_ladder_horizons(china_payload),
        }
    execution = derive_execution_payload(global_payload, china_payload, btc_bias=btc_bias)

    core = {
        "global": global_payload,
        "china": china_payload,
        "china_ladder": china_ladder,
        "crypto_sleeve": crypto_block,
        "suggested_tracer": suggested_tracer,
        "execution": execution,
    }
    if not lineage_hash:
        lineage_hash = compute_lineage_hash(core)

    freshness = compute_freshness(data_as_of).value
    root = repo_root or Path(__file__).resolve().parents[1]
    ingest_provenance = collect_staged_ingest_provenance(root / "staged_raw", as_of=data_as_of)
    provenance = ProvenanceMeta(
        snapshot_id=snapshot_id,
        lineage_hash=lineage_hash,
        validation_status=validation_status,
        data_as_of=data_as_of,
        source_channel=provenance_source,
        freshness_status=freshness,
        output_kind=str(ingest_provenance.get("primary_output_kind") or "derived_signals"),
    )
    if flows_sidecar is not None:
        flows_data = flows_sidecar
    else:
        flows_data = ensure_flows_sidecar(root)

    ensure_dated_series_fixture(root)
    rv_history = load_rv_history(root)

    node_cockpits = build_node_cockpits(
        global_payload=global_payload,
        suggested_tracer=suggested_tracer,
        as_of=data_as_of,
        freshness_status=freshness,
        china_ladder=china_ladder or None,
        execution=execution,
        spread_history=rv_history,
        flows_sidecar=flows_data,
    )
    cockpit_context = build_cockpit_context(
        global_payload=global_payload,
        node_cockpits=node_cockpits,
    )

    wtm_block = build_wtm_export_v21(
        global_data=global_payload,
        china_data=china_payload,
        china_ladder_horizons=china_ladder.get("horizons") if china_ladder else None,
        tracer_horizons={},
        provenance=provenance,
        btc_bias=btc_bias,
        include_tracer=False,
        include_provenance=True,
        timestamp=data_as_of,
    )
    wtm_block_v22 = build_wtm_export_v22(
        global_data=global_payload,
        china_data=china_payload,
        china_ladder_horizons=china_ladder.get("horizons") if china_ladder else None,
        tracer_horizons={},
        provenance=provenance,
        btc_bias=btc_bias,
        include_tracer=False,
        include_provenance=True,
        timestamp=data_as_of,
        node_cockpits=node_cockpits,
    )

    bundle: dict[str, Any] = {
        "hydration_version": HYDRATION_BUNDLE_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "bundle_version": BUNDLE_VERSION,
        "snapshot_id": snapshot_id,
        "lineage_hash": lineage_hash,
        "validation_status": validation_status,
        "as_of": data_as_of.isoformat(),
        "source": "parquet_hydration",
        "freshness_status": freshness,
        "global": global_payload,
        "china": china_payload,
        "china_ladder": china_ladder,
        "crypto_sleeve": crypto_block,
        "execution": execution,
        "suggested_tracer": suggested_tracer,
        "tracer_apply_mode": "confirm_required",
        "node_cockpits": node_cockpits,
        "cockpit_context": cockpit_context,
        "wtm_export_v21": wtm_block,
        "wtm_export_v22": wtm_block_v22,
        "warnings": [] if g_obs and c_obs else (["Partial hydration — single track only"] if g_obs or c_obs else []),
    }
    flows_health = assess_flows_basket_health(flows_data, node_id="credit")
    bundle["flows_health"] = flows_health
    bundle["flows_sidecar"] = build_flows_sidecar_metadata(flows_data, node_id="credit")
    bundle["ingest_provenance"] = ingest_provenance
    merge_v15_into_bundle(bundle, repo_root=root)
    bundle["hydration_audit"] = build_hydration_audit(bundle)
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Parquet hydration bundle for Transmission Control")
    parser.add_argument("--global-parquet", default=None)
    parser.add_argument("--china-parquet", default=None)
    parser.add_argument("--execution-json", default=None, help="Optional execution/L3 JSON sidecar")
    parser.add_argument("--crypto-json", default=None, help="Optional crypto sleeve JSON sidecar")
    parser.add_argument("--output", "-o", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    try:
        bundle = build_hydration_bundle(
            global_path=Path(args.global_parquet) if args.global_parquet else None,
            china_path=Path(args.china_parquet) if args.china_parquet else None,
            execution_path=Path(args.execution_json) if args.execution_json else None,
            crypto_path=Path(args.crypto_json) if args.crypto_json else None,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    log_path = out.parent / "hydration_log.json"
    write_hydration_log(bundle, log_path)

    audit = bundle.get("hydration_audit") or {}
    summary = audit.get("summary") or {}
    print(f"hydration_ok version={HYDRATION_BUNDLE_VERSION}")
    print(
        f"audit_required_ok={summary.get('required_ok')}/{summary.get('required_fields')} "
        f"quality={summary.get('bundle_quality_score')} session={summary.get('tc_session_level')}"
    )
    print(f"hydration_log={log_path}")
    print(f"snapshot_id={bundle['snapshot_id']}")
    print(f"freshness_status={bundle['freshness_status']}")
    print(f"output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())