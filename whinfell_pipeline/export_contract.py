"""Locked WTM EXPORT v2.1 contract — build and parse."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from china_policy_track.china_ladder import (
    CHINA_STAGE_MODELS,
    CANONICAL_STAGE_IDS,
    HZ_SCORE,
    composite_stage_score,
    score_china_ladder,
    weakest_stage,
)
from whinfell_pipeline.freshness import FreshnessStatus, compute_freshness
from whinfell_pipeline.version import (
    CHINA_LADDER_EXPORT_FORMAT,
    DECISION_EXPORT_FORMAT,
    DECISION_EXPORT_FORMAT_LEGACY,
    DECISION_EXPORT_FORMAT_V22,
    NODE_COCKPIT_EXPORT_PREFIX,
)

LADDER_STAGES = (
    "Liquidity & Rates",
    "Credit Confirmation",
    "Equity Breadth",
    "High-Beta / BTC",
    "Basis & Term Structure",
)

_STAGE_TO_ID = {
    "liquidity & rates": "liquidity",
    "credit confirmation": "credit",
    "equity breadth": "breadth",
    "high-beta / btc": "highbeta",
    "basis & term structure": "basis",
}

_HORIZON_LABELS = ("1d", "5d", "20d", "60d")
_MARK_TO_SYM = {"up": "↑", "flat": "→", "down": "↓"}
_SYM_TO_MARK = {"↑": "up", "→": "flat", "↓": "down", "up": "up", "flat": "flat", "down": "down"}

_TX_LABELS = {
    "normal": "Normal",
    "stressed": "Stressed",
    "disorderly": "Disorderly",
    "crisis": "Crisis",
}

_POSTURE_LABELS = {
    "full": "Full Gross",
    "selective": "Selective",
    "light": "Light Gross",
    "defensive": "Defensive",
    "flat": "Flat",
}


@dataclass
class ProvenanceMeta:
    snapshot_id: str = ""
    lineage_hash: str = ""
    validation_status: str = "parsed"
    data_as_of: datetime | None = None
    source_channel: str = "manual"
    freshness_status: str = FreshnessStatus.UNKNOWN.value
    output_kind: str = "derived_signals"


@dataclass
class ChinaLadderExportV11:
    china_raw_score: int | None = None
    china_final_score: int | None = None
    china_final_band: str = ""
    sq3_policy_score: int | None = None
    weakest_china_stage: str = ""
    key_china_observation: str = ""


@dataclass
class WtmExportV21:
    whinfell_score: int | None = None
    transmission_state: str = ""
    regime_tag: str = ""
    key_observation: str = ""
    gross_risk_recommendation: str = ""
    btc_bias: str = "Neutral"
    timestamp: datetime | None = None
    sq3_score: int | None = None
    sq3_band: str = ""
    policy_strength: int | None = None
    state_impulse_score: int | None = None
    growth_impulse_score: int | None = None
    china_regime_tag: str = ""
    tracer_horizons: dict[str, dict[str, str]] = field(default_factory=dict)
    provenance: ProvenanceMeta = field(default_factory=ProvenanceMeta)
    export_format: str = DECISION_EXPORT_FORMAT
    china_ladder: ChinaLadderExportV11 | None = None
    warnings: list[str] = field(default_factory=list)


def _parse_score(val: str) -> int | None:
    n = int(re.sub(r"[^\d]", "", str(val)))
    return n if 0 <= n <= 100 else None


def _tx_label(state: str) -> str:
    return _TX_LABELS.get(str(state).lower(), state or "—")


def _china_stage_rows(horizons: Mapping[str, Mapping[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sid in CANONICAL_STAGE_IDS:
        hz = horizons.get(sid) or {}
        if not isinstance(hz, dict):
            hz = {}
        net = sum(HZ_SCORE.get(str(hz.get(k, "flat")).lower(), 0) for k in ("d1", "d5", "d20", "d60"))
        rows.append(
            {
                "id": sid,
                "name": CHINA_STAGE_MODELS[sid]["name"],
                "score": composite_stage_score(sid, horizons),
                "net": net,
            }
        )
    return rows


def derive_china_ladder_key_observation(
    *,
    weakest_name: str,
    weakest_score: int,
    final_band: str,
) -> str:
    """One-line desk constraint for CHINA LADDER EXPORT v1.1."""
    if final_band == "Impaired":
        sizing = "avoid new China-linked exposure"
    elif final_band == "Mixed / Fragile":
        sizing = "keep China-linked beta selective and reduced size"
    elif final_band == "Constructive":
        sizing = "normal China-linked sizing acceptable within Global gate"
    else:
        sizing = "China ladder aligned — size within desk policy"
    return (
        f"Weakest stage {weakest_name} at {weakest_score}/100 — "
        f"{sizing} until composite clears 50."
    )


def build_china_ladder_export_v11(
    horizons: Mapping[str, Mapping[str, str]],
    sq3_score: int,
    *,
    key_observation: str = "",
) -> str:
    """Emit locked CHINA LADDER EXPORT v1.1 block."""
    if not horizons or sq3_score is None:
        return ""
    result = score_china_ladder(horizons, int(sq3_score))
    weakest = weakest_stage(_china_stage_rows(horizons), "composite")
    obs = key_observation or derive_china_ladder_key_observation(
        weakest_name=weakest.name,
        weakest_score=weakest.value,
        final_band=result.band,
    )
    lines = [
        f"--- {CHINA_LADDER_EXPORT_FORMAT} ---",
        f"China Raw Score: {result.raw_ladder_score}",
        f"China Final Score: {result.final_china_score}",
        f"China Final Band: {result.band}",
        f"SQ3 Policy Score: {result.sq3_score}",
        f"Weakest China Stage: {weakest.name}",
        f"Key China Observation: {obs}",
    ]
    return "\n".join(lines)


def extract_china_ladder_export_block(text: str) -> tuple[str | None, str]:
    normalized = text.replace("\r\n", "\n")
    match = re.search(rf"---\s*{re.escape(CHINA_LADDER_EXPORT_FORMAT)}\s*---", normalized, re.I)
    if not match:
        return None, ""
    start = match.start()
    rest = normalized[start:]
    rest = re.sub(
        rf"^---\s*{re.escape(CHINA_LADDER_EXPORT_FORMAT)}\s*---\s*",
        "",
        rest,
        flags=re.I,
    )
    end = re.search(r"\n---\s*(?:WTM EXPORT|CHINA LADDER EXPORT|CHINA POLICY EXPORT)", rest, re.I)
    block = (rest[: end.start()] if end else rest).strip()
    return block, CHINA_LADDER_EXPORT_FORMAT


def parse_china_ladder_export_v11(text: str) -> ChinaLadderExportV11:
    block, _fmt = extract_china_ladder_export_block(text)
    if not block:
        raise ValueError(f"Missing {CHINA_LADDER_EXPORT_FORMAT} block")

    result = ChinaLadderExportV11()
    label_patterns: list[tuple[str, re.Pattern[str], Any]] = [
        ("china_raw_score", re.compile(r"^\s*China Raw Score:\s*(\d{1,3}|N/A)\s*$", re.I | re.M), lambda v: _parse_score(v) if v.upper() != "N/A" else None),
        ("china_final_score", re.compile(r"^\s*China Final Score:\s*(\d{1,3}|N/A)\s*$", re.I | re.M), lambda v: _parse_score(v) if v.upper() != "N/A" else None),
        ("china_final_band", re.compile(r"^\s*China Final Band:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("sq3_policy_score", re.compile(r"^\s*SQ3 Policy Score:\s*(\d{1,3}|N/A)\s*$", re.I | re.M), lambda v: _parse_score(v) if v.upper() != "N/A" else None),
        ("weakest_china_stage", re.compile(r"^\s*Weakest China Stage:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("key_china_observation", re.compile(r"^\s*Key China Observation:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
    ]
    fields: dict[str, Any] = {}
    for key, pattern, transform in label_patterns:
        m = pattern.search(block)
        if m:
            fields[key] = transform(m[1])

    result.china_raw_score = fields.get("china_raw_score")
    result.china_final_score = fields.get("china_final_score")
    result.china_final_band = str(fields.get("china_final_band", ""))
    result.sq3_policy_score = fields.get("sq3_policy_score")
    result.weakest_china_stage = str(fields.get("weakest_china_stage", ""))
    result.key_china_observation = str(fields.get("key_china_observation", ""))
    return result


def tracer_line(stage_name: str, horizons: Mapping[str, str]) -> str:
    parts = []
    for h in _HORIZON_LABELS:
        key = {"1d": "d1", "5d": "d5", "20d": "d20", "60d": "d60"}[h]
        mark = horizons.get(key, horizons.get(h, ""))
        sym = _MARK_TO_SYM.get(str(mark).lower(), "→" if not mark else str(mark))
        parts.append(f"{h}: {sym}")
    return f"Signal Tracer — {stage_name}: {' | '.join(parts)}"


def parse_tracer_line(line: str) -> tuple[str, dict[str, str]] | None:
    m = re.match(r"^\s*Signal Tracer\s*—\s*(.+?):\s*(.+)$", line, re.I)
    if not m:
        return None
    stage_name = m.group(1).strip()
    stage_id = _STAGE_TO_ID.get(stage_name.lower())
    if not stage_id:
        return None
    horizons: dict[str, str] = {}
    for h in _HORIZON_LABELS:
        key = {"1d": "d1", "5d": "d5", "20d": "d20", "60d": "d60"}[h]
        hm = re.search(rf"{h}\s*:\s*([↑→↓]|up|flat|down)", m.group(2), re.I)
        if hm:
            horizons[key] = _SYM_TO_MARK.get(hm.group(1).lower(), hm.group(1).lower())
    return stage_id, horizons


def build_wtm_export_v21(
    *,
    global_data: Mapping[str, Any],
    china_data: Mapping[str, Any] | None = None,
    china_ladder_horizons: Mapping[str, Mapping[str, str]] | None = None,
    china_ladder_key_observation: str = "",
    tracer_horizons: Mapping[str, Mapping[str, str]] | None = None,
    provenance: ProvenanceMeta | None = None,
    gross_total_pct: float | None = None,
    posture: str = "",
    btc_bias: str = "Neutral",
    timestamp: datetime | None = None,
    include_tracer: bool = True,
    include_provenance: bool = True,
) -> str:
    """Emit locked WTM EXPORT v2.1 block."""
    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    score = global_data.get("whinfell_score", global_data.get("whinfellScore", "—"))
    tx = _tx_label(str(global_data.get("transmission_state", global_data.get("transmissionState", ""))))
    regime = global_data.get("regime_tag", global_data.get("regimeTag", "—"))
    obs = global_data.get("key_observation", global_data.get("keyObservation", "—"))

    gross_line = global_data.get("gross_risk_recommendation", "")
    if not gross_line and gross_total_pct is not None:
        posture_label = _POSTURE_LABELS.get(posture, posture or "—")
        gross_line = f"{gross_total_pct:.0f}% total, {posture_label} posture"

    lines = [
        f"--- {DECISION_EXPORT_FORMAT} ---",
        f"Whinfell Score: {score}",
        f"Transmission State: {tx}",
        f"Regime Tag: {regime}",
        f"Key Observation: {obs}",
        f"Gross Risk Recommendation: {gross_line or '—'}",
        f"BTC Bias: {btc_bias or 'Neutral'}",
        f"Timestamp: {ts.strftime('%Y-%m-%dT%H:%M:%S')}",
    ]

    china = china_data or {}
    sq3_score = china.get("sq3_score") or global_data.get("sq3_score")
    sq3_band = china.get("sq3_band") or global_data.get("sq3_band")
    policy = china.get("policy_strength", china.get("policyStrength"))
    state_imp = china.get("state_impulse_score", china.get("stateImpulse"))
    growth = china.get("growth_impulse_score", china.get("growthImpulse"))

    if sq3_score is not None:
        lines.append(f"SQ3 Score: {sq3_score}")
    if sq3_band:
        lines.append(f"SQ3 Band: {sq3_band}")
    if policy is not None:
        lines.append(f"Policy Strength: {policy}")
    if state_imp is not None:
        lines.append(f"State Impulse Score: {state_imp}")
    if growth is not None:
        lines.append(f"Growth Impulse Score: {growth}")

    china_regime = china.get("regime_tag", china.get("regimeTag", china.get("china_regime_tag")))
    if china_regime:
        lines.append(f"China Regime Tag: {china_regime}")

    if include_tracer and tracer_horizons:
        for stage in LADDER_STAGES:
            stage_id = _STAGE_TO_ID[stage.lower()]
            hz = tracer_horizons.get(stage_id)
            if hz and any(hz.values()):
                lines.append(tracer_line(stage, hz))

    prov = provenance or ProvenanceMeta()
    if include_provenance:
        data_as_of = prov.data_as_of or ts
        freshness = prov.freshness_status
        if freshness == FreshnessStatus.UNKNOWN.value and data_as_of:
            freshness = compute_freshness(data_as_of).value
        if prov.snapshot_id:
            lines.append(f"Snapshot ID: {prov.snapshot_id}")
        if prov.lineage_hash:
            lines.append(f"Lineage Hash: {prov.lineage_hash}")
        lines.append(f"Validation Status: {prov.validation_status or 'parsed'}")
        lines.append(f"Data As Of: {data_as_of.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
        lines.append(f"Source Channel: {prov.source_channel or 'manual'}")
        lines.append(f"Freshness Status: {freshness}")
        if prov.output_kind:
            lines.append(f"Output Kind: {prov.output_kind}")

    body = "\n".join(lines)
    sq3_for_ladder = china.get("sq3_score") or global_data.get("sq3_score")
    if china_ladder_horizons and sq3_for_ladder is not None:
        china_block = build_china_ladder_export_v11(
            china_ladder_horizons,
            int(sq3_for_ladder),
            key_observation=china_ladder_key_observation,
        )
        if china_block:
            body = f"{body}\n{china_block}"
    return body


def extract_wtm_export_block(text: str) -> tuple[str | None, str]:
    normalized = text.replace("\r\n", "\n")
    match = re.search(r"---\s*WTM EXPORT v2\.[01]\s*---", normalized, re.I)
    if not match:
        return None, ""
    fmt = DECISION_EXPORT_FORMAT if "v2.1" in match.group(0).lower() else DECISION_EXPORT_FORMAT_LEGACY
    start = match.start()
    rest = normalized[start:]
    rest = re.sub(r"^---\s*WTM EXPORT v2\.[01]\s*---\s*", "", rest, flags=re.I)
    end = re.search(r"\n---\s*WTM EXPORT", rest, re.I)
    block = (rest[: end.start()] if end else rest).strip()
    return block, fmt


def parse_wtm_export_v21(text: str, *, source: str = "perplexity") -> WtmExportV21:
    block, fmt = extract_wtm_export_block(text)
    if not block:
        raise ValueError("Missing WTM EXPORT block")

    result = WtmExportV21(export_format=fmt)
    label_patterns: list[tuple[str, re.Pattern[str], Any]] = [
        ("whinfell_score", re.compile(r"^\s*Whinfell Score:\s*(.+)$", re.I | re.M), lambda v: _parse_score(v)),
        ("transmission_state", re.compile(r"^\s*Transmission State:\s*(.+)$", re.I | re.M), lambda v: v.strip().lower()),
        ("regime_tag", re.compile(r"^\s*Regime Tag:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("key_observation", re.compile(r"^\s*Key Observation:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("gross_risk_recommendation", re.compile(r"^\s*Gross Risk Recommendation:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("btc_bias", re.compile(r"^\s*BTC Bias:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("sq3_score", re.compile(r"^\s*SQ3 Score:\s*(\d{1,3})$", re.I | re.M), lambda v: _parse_score(v)),
        ("sq3_band", re.compile(r"^\s*SQ3 Band:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("policy_strength", re.compile(r"^\s*Policy Strength:\s*(\d{1,3})$", re.I | re.M), lambda v: _parse_score(v)),
        ("state_impulse_score", re.compile(r"^\s*State Impulse Score:\s*(-?\d{1,3})$", re.I | re.M), lambda v: int(v)),
        ("growth_impulse_score", re.compile(r"^\s*Growth Impulse Score:\s*(\d{1,3})$", re.I | re.M), lambda v: _parse_score(v)),
        ("china_regime_tag", re.compile(r"^\s*China Regime Tag:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("snapshot_id", re.compile(r"^\s*Snapshot ID:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("lineage_hash", re.compile(r"^\s*Lineage Hash:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("validation_status", re.compile(r"^\s*Validation Status:\s*(.+)$", re.I | re.M), lambda v: v.strip().lower()),
        ("source_channel", re.compile(r"^\s*Source Channel:\s*(.+)$", re.I | re.M), lambda v: v.strip().lower()),
        ("freshness_status", re.compile(r"^\s*Freshness Status:\s*(.+)$", re.I | re.M), lambda v: v.strip().lower()),
        ("timestamp", re.compile(r"^\s*Timestamp:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("data_as_of", re.compile(r"^\s*Data As Of:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
    ]

    fields: dict[str, Any] = {}
    for key, pattern, transform in label_patterns:
        m = pattern.search(block)
        if not m:
            continue
        val = transform(m[1])
        if val is None or val == "":
            continue
        fields[key] = val

    for line in block.splitlines():
        parsed = parse_tracer_line(line)
        if parsed:
            stage_id, horizons = parsed
            result.tracer_horizons[stage_id] = horizons

    ts_raw = fields.get("data_as_of") or fields.get("timestamp", datetime.now(timezone.utc).isoformat())
    as_of = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    for req in ("whinfell_score", "transmission_state", "regime_tag"):
        if fields.get(req) is None:
            result.warnings.append(f"Missing {req}")

    result.whinfell_score = fields.get("whinfell_score")
    result.transmission_state = str(fields.get("transmission_state", ""))
    result.regime_tag = str(fields.get("regime_tag", ""))
    result.key_observation = str(fields.get("key_observation", ""))
    result.gross_risk_recommendation = str(fields.get("gross_risk_recommendation", ""))
    result.btc_bias = str(fields.get("btc_bias", "Neutral"))
    result.timestamp = as_of
    result.sq3_score = fields.get("sq3_score")
    result.sq3_band = str(fields.get("sq3_band", ""))
    result.policy_strength = fields.get("policy_strength")
    result.state_impulse_score = fields.get("state_impulse_score")
    result.growth_impulse_score = fields.get("growth_impulse_score")
    result.china_regime_tag = str(fields.get("china_regime_tag", ""))
    result.provenance = ProvenanceMeta(
        snapshot_id=str(fields.get("snapshot_id", "")),
        lineage_hash=str(fields.get("lineage_hash", "")),
        validation_status=str(fields.get("validation_status", "parsed")),
        data_as_of=as_of,
        source_channel=str(fields.get("source_channel", source)),
        freshness_status=str(fields.get("freshness_status", compute_freshness(as_of).value)),
    )
    try:
        result.china_ladder = parse_china_ladder_export_v11(text)
    except ValueError:
        result.china_ladder = None
    return result


_NODE_COCKPIT_ORDER: tuple[str, ...] = (
    "liquidity",
    "credit",
    "breadth",
    "highbeta",
    "basis",
)

_MARK_TO_SYM_EXPORT = {"up": "↑", "flat": "→", "down": "↓"}


def _horizon_marks_export_line(marks: Mapping[str, str]) -> str:
    parts = []
    for key in ("d1", "d5", "d20", "d60"):
        sym = _MARK_TO_SYM_EXPORT.get(str(marks.get(key, "flat")).lower(), "→")
        parts.append(f"{key}{sym}")
    return " ".join(parts)


def build_node_cockpit_export_block(cockpit: Mapping[str, Any]) -> str:
    """Emit one locked NODE COCKPIT block for WTM EXPORT v2.2."""
    display = str(cockpit.get("display_name") or cockpit.get("node_id") or "Unknown")
    lines = [
        f"--- {NODE_COCKPIT_EXPORT_PREFIX}: {display} ---",
        f"Node ID: {cockpit.get('node_id', '')}",
        f"Composite Score: {cockpit.get('composite_score', '—')}",
        f"Composite Score Source: {cockpit.get('composite_score_source', '')}",
        f"Band: {cockpit.get('band', '')}",
        f"Band Key: {cockpit.get('band_key', '')}",
        f"Freshness Status: {cockpit.get('freshness_status', '')}",
        f"Horizon Net: {cockpit.get('horizon_net', 0)}",
        f"Horizon Marks: {_horizon_marks_export_line(cockpit.get('horizon_marks') or {})}",
    ]

    directional = cockpit.get("directional") or {}
    lines.append(
        "Directional: "
        f"{directional.get('posture', 'neutral')} ({directional.get('conviction', 'low')}) — "
        f"{directional.get('rationale', '')}"
    )

    rv = cockpit.get("relative_value") or {}
    lines.append(
        "Relative Value: "
        f"{rv.get('posture', 'neutral')} — {rv.get('structure', '')} ({rv.get('conviction', 'low')})"
    )

    selected = cockpit.get("selected_implementation_id")
    lines.append(f"Selected Implementation: {selected or '—'}")

    rv_basis = cockpit.get("rv_basis") or {}
    active_series = str(rv_basis.get("active_series_id") or "")
    active_horizon = str(rv_basis.get("active_horizon") or "3m")
    if active_series:
        series = (rv_basis.get("series") or {}).get(active_series) or {}
        horizon = (series.get("horizons") or {}).get(active_horizon)
        lines.append(f"RV Series: {active_series}")
        lines.append(f"RV Direction: {series.get('quartile_direction', '')}")
        if horizon:
            lines.append(f"RV Horizon: {active_horizon}")
            lines.append(f"RV Quartile: Q{horizon.get('quartile', '')}")
            lines.append(f"RV Percentile: {horizon.get('percentile', '')}")
            lines.append(f"RV Richness: {horizon.get('richness_label', '')}")

    china = cockpit.get("china_parallel")
    if isinstance(china, dict) and china.get("present"):
        lines.append(f"China Parallel: present — horizon_net {china.get('horizon_net', 0)}")
        if china.get("note"):
            lines.append(f"China Parallel Note: {china['note']}")

    lines.append(f"Key Observation: {cockpit.get('key_observation', '')}")

    funds = cockpit.get("funds_flows") or {}
    if funds:
        meta = funds.get("flows_meta") or {}
        agg = funds.get("aggregate") or {}
        interp = funds.get("interpretation") or {}
        lines.append(f"Funds Flow Enabled: {str(funds.get('enabled', False)).lower()}")
        lines.append(f"Funds Flow Status: {meta.get('flows_status', '')}")
        lines.append(f"Funds Flow Source: {meta.get('flows_source', '')}")
        lines.append(f"Funds Flow Degraded: {str(meta.get('flows_degraded', False)).lower()}")
        lines.append(f"Funds Flow Fallback Reason: {meta.get('fallback_reason', '')}")
        lines.append(f"Funds Flow Verdict: {agg.get('verdict', 'neutral')}")
        agg_1d = agg.get("flow_pct_aum_1d")
        if agg_1d is not None:
            sign = "+" if float(agg_1d) >= 0 else ""
            lines.append(f"Funds Flow 1D: {sign}{float(agg_1d):.2f}% AUM")
        agg_5d = agg.get("flow_pct_aum_5d")
        if agg_5d is not None and meta.get("flows_status") != "fallback_1d":
            sign = "+" if float(agg_5d) >= 0 else ""
            lines.append(f"Funds Flow 5D: {sign}{float(agg_5d):.2f}% AUM")
        pos = agg.get("positive_count")
        total = agg.get("total_count")
        if pos is not None and total is not None:
            lines.append(f"Funds Flow Breadth: {pos}/{total}")
        lines.append(f"Funds Flow Confidence Penalty: {meta.get('flows_confidence_penalty', 0)}")
        summary = interp.get("summary") or "—"
        lines.append(f"Funds Flow Summary: {summary}")

    return "\n".join(lines)


def build_wtm_export_v22(
    *,
    global_data: Mapping[str, Any],
    china_data: Mapping[str, Any] | None = None,
    china_ladder_horizons: Mapping[str, Mapping[str, str]] | None = None,
    china_ladder_key_observation: str = "",
    tracer_horizons: Mapping[str, Mapping[str, str]] | None = None,
    provenance: ProvenanceMeta | None = None,
    gross_total_pct: float | None = None,
    posture: str = "",
    btc_bias: str = "Neutral",
    timestamp: datetime | None = None,
    include_tracer: bool = True,
    include_provenance: bool = True,
    node_cockpits: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    """Emit WTM EXPORT v2.2: v2.1 core plus optional per-node cockpit blocks."""
    core = build_wtm_export_v21(
        global_data=global_data,
        china_data=china_data,
        china_ladder_horizons=china_ladder_horizons,
        china_ladder_key_observation=china_ladder_key_observation,
        tracer_horizons=tracer_horizons,
        provenance=provenance,
        gross_total_pct=gross_total_pct,
        posture=posture,
        btc_bias=btc_bias,
        timestamp=timestamp,
        include_tracer=include_tracer,
        include_provenance=include_provenance,
    )
    if not node_cockpits:
        return core.replace(DECISION_EXPORT_FORMAT, DECISION_EXPORT_FORMAT_V22, 1)

    blocks = [core.replace(DECISION_EXPORT_FORMAT, DECISION_EXPORT_FORMAT_V22, 1)]
    for node_id in _NODE_COCKPIT_ORDER:
        cockpit = node_cockpits.get(node_id)
        if cockpit:
            blocks.append(build_node_cockpit_export_block(cockpit))
    return "\n\n".join(blocks)