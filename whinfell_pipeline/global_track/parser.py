"""Parse WTM EXPORT v2.0 / v2.1 label blocks (mirrors Transmission Control JS parser)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from whinfell_pipeline.canonical import ValidationStatus
from whinfell_pipeline.lineage import make_snapshot_id
from whinfell_pipeline.version import DECISION_EXPORT_FORMAT, DECISION_EXPORT_FORMAT_LEGACY

_TX_PARSE = {
    "normal": "normal",
    "stressed": "stressed",
    "disorderly": "disorderly",
    "crisis": "crisis",
    "risk-on": "normal",
    "risk-off": "disorderly",
}


def _parse_score(val: str) -> int | None:
    n = int(re.sub(r"[^\d]", "", str(val)))
    return n if 0 <= n <= 100 else None


def _parse_transmission_state(val: str) -> str | None:
    key = re.sub(r"[^a-z-]", "", str(val).lower())
    return _TX_PARSE.get(key, key if key in _TX_PARSE.values() else None)


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


@dataclass
class ParsedWtmExport:
    observation_id: str
    as_of: datetime
    source: str
    whinfell_score: int | None
    transmission_state: str
    regime_tag: str
    key_observation: str
    sq3_score: int | None = None
    sq3_band: str = ""
    policy_strength: int | None = None
    state_impulse_score: int | None = None
    growth_impulse_score: int | None = None
    china_regime_tag: str = ""
    export_block: str = ""
    export_format: str = DECISION_EXPORT_FORMAT
    validation_status: ValidationStatus = ValidationStatus.PARSED
    warnings: list[str] = field(default_factory=list)

    def to_payload_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "whinfell_score": self.whinfell_score,
            "transmission_state": self.transmission_state,
            "regime_tag": self.regime_tag,
            "key_observation": self.key_observation,
            "sq3_score": self.sq3_score,
            "sq3_band": self.sq3_band,
            "policy_strength": self.policy_strength,
            "state_impulse_score": self.state_impulse_score,
            "growth_impulse_score": self.growth_impulse_score,
            "china_regime_tag": self.china_regime_tag,
            "source": self.source,
        }


def parse_wtm_export_text(text: str, *, source: str = "perplexity") -> ParsedWtmExport:
    block, fmt = extract_wtm_export_block(text)
    if not block:
        raise ValueError("Missing WTM EXPORT block")

    fields: dict[str, Any] = {}
    patterns: list[tuple[str, re.Pattern[str], Any]] = [
        ("whinfell_score", re.compile(r"^\s*Whinfell Score:\s*(.+)$", re.I | re.M), lambda v: _parse_score(v)),
        ("transmission_state", re.compile(r"^\s*Transmission State:\s*(.+)$", re.I | re.M), _parse_transmission_state),
        ("regime_tag", re.compile(r"^\s*Regime Tag:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("key_observation", re.compile(r"^\s*Key Observation:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("sq3_score", re.compile(r"^\s*SQ3 Score:\s*(\d{1,3})$", re.I | re.M), lambda v: _parse_score(v)),
        ("sq3_band", re.compile(r"^\s*SQ3 Band:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("policy_strength", re.compile(r"^\s*Policy Strength:\s*(\d{1,3})$", re.I | re.M), lambda v: _parse_score(v)),
        ("state_impulse_score", re.compile(r"^\s*State Impulse Score:\s*(-?\d{1,3})$", re.I | re.M), lambda v: int(v)),
        ("growth_impulse_score", re.compile(r"^\s*Growth Impulse Score:\s*(\d{1,3})$", re.I | re.M), lambda v: _parse_score(v)),
        ("china_regime_tag", re.compile(r"^\s*China Regime Tag:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
        ("timestamp", re.compile(r"^\s*Timestamp:\s*(.+)$", re.I | re.M), lambda v: v.strip()),
    ]
    for key, pattern, transform in patterns:
        m = pattern.search(block)
        if not m:
            continue
        val = transform(m[1])
        if val is None or val == "":
            continue
        fields[key] = val

    warnings: list[str] = []
    status = ValidationStatus.PARSED
    for req in ("whinfell_score", "transmission_state", "regime_tag"):
        if fields.get(req) is None:
            warnings.append(f"Missing {req}")
            status = ValidationStatus.PARTIAL

    ts_raw = fields.get("timestamp", datetime.now(timezone.utc).isoformat())
    as_of = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    return ParsedWtmExport(
        observation_id=make_snapshot_id("global"),
        as_of=as_of,
        source=source,
        whinfell_score=fields.get("whinfell_score"),
        transmission_state=str(fields.get("transmission_state", "")),
        regime_tag=str(fields.get("regime_tag", "")),
        key_observation=str(fields.get("key_observation", "")),
        sq3_score=fields.get("sq3_score"),
        sq3_band=str(fields.get("sq3_band", "")),
        policy_strength=fields.get("policy_strength"),
        state_impulse_score=fields.get("state_impulse_score"),
        growth_impulse_score=fields.get("growth_impulse_score"),
        china_regime_tag=str(fields.get("china_regime_tag", "")),
        export_block=f"--- {fmt} ---\n{block}",
        export_format=fmt,
        validation_status=status,
        warnings=warnings,
    )