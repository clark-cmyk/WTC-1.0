"""Parse structured China Policy inputs (Perplexity export blocks, Koyfin/Barchart dicts)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping

from china_policy_track.models import ChinaPolicyObservation
from china_policy_track.version import EXPORT_FORMAT, SCHEMA_VERSION

_EXPORT_HEADER = re.compile(r"---\s*CHINA POLICY EXPORT v1\.0\s*---", re.I)

_LABEL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("observation_id", re.compile(r"^\s*Observation ID:\s*(.+)$", re.I | re.M)),
    ("as_of", re.compile(r"^\s*Timestamp:\s*(.+)$", re.I | re.M)),
    ("source", re.compile(r"^\s*Source:\s*(.+)$", re.I | re.M)),
    ("hierarchy_level", re.compile(r"^\s*Policy Hierarchy Level:\s*(.+)$", re.I | re.M)),
    ("policy_strength", re.compile(r"^\s*Policy Strength:\s*(\d{1,3})$", re.I | re.M)),
    ("dominant_theme", re.compile(r"^\s*Dominant Policy Theme:\s*(.+)$", re.I | re.M)),
    ("policy_supporting_signals", re.compile(r"^\s*Policy Supporting Signals:\s*(.+)$", re.I | re.M)),
    ("policy_notes", re.compile(r"^\s*Policy Notes:\s*(.+)$", re.I | re.M)),
    ("state_impulse_score", re.compile(r"^\s*State Control Impulse Score:\s*(-?\d{1,3})$", re.I | re.M)),
    ("state_regulatory_direction", re.compile(r"^\s*Regulatory Direction:\s*(.+)$", re.I | re.M)),
    ("state_intervention_level", re.compile(r"^\s*State Intervention Level:\s*(.+)$", re.I | re.M)),
    ("state_key_controls", re.compile(r"^\s*Key State Controls:\s*(.+)$", re.I | re.M)),
    ("state_notes", re.compile(r"^\s*State Control Notes:\s*(.+)$", re.I | re.M)),
    ("growth_impulse_score", re.compile(r"^\s*Growth Impulse Score:\s*(\d{1,3})$", re.I | re.M)),
    ("growth_market_sentiment", re.compile(r"^\s*Market Sentiment:\s*(.+)$", re.I | re.M)),
    ("growth_liquidity_impulse", re.compile(r"^\s*Liquidity Impulse:\s*(.+)$", re.I | re.M)),
    ("growth_key_indicators", re.compile(r"^\s*Key Growth Indicators:\s*(.+)$", re.I | re.M)),
    ("growth_notes", re.compile(r"^\s*Growth Notes:\s*(.+)$", re.I | re.M)),
]


def extract_china_export_block(text: str) -> str | None:
    """Extract CHINA POLICY EXPORT v1.0 block from free text."""
    if not text:
        return None
    normalized = text.replace("\r\n", "\n")
    start = _EXPORT_HEADER.search(normalized)
    if not start:
        return None
    rest = normalized[start.end() :]
    end = re.search(r"\n---\s*CHINA POLICY EXPORT", rest, re.I)
    block = rest[: end.start()] if end else rest
    return block.strip()


def parse_labeled_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, pattern in _LABEL_PATTERNS:
        match = pattern.search(block)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def parse_perplexity_text(text: str) -> ChinaPolicyObservation:
    """Parse structured Perplexity-style export text into a model instance."""
    block = extract_china_export_block(text)
    if not block:
        raise ValueError(f"Missing {EXPORT_FORMAT} block in text")
    fields = parse_labeled_block(block)
    fields.setdefault("source", "perplexity")
    fields.setdefault("schema_version", SCHEMA_VERSION)
    return ChinaPolicyObservation.from_mapping(fields)


def parse_koyfin_barchart_export(data: Mapping[str, Any]) -> ChinaPolicyObservation:
    """Parse a structured dict export (Koyfin/Barchart/manual JSON)."""
    payload = dict(data)
    payload.setdefault("source", payload.get("source", "koyfin"))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    if "timestamp" in payload and "as_of" not in payload:
        payload["as_of"] = payload["timestamp"]
    return ChinaPolicyObservation.from_mapping(payload)


def parse_input(payload: str | Mapping[str, Any]) -> ChinaPolicyObservation:
    """Dispatch: str → Perplexity block; dict → structured export."""
    if isinstance(payload, str):
        return parse_perplexity_text(payload)
    if isinstance(payload, Mapping):
        return parse_koyfin_barchart_export(payload)
    raise TypeError("payload must be str (Perplexity text) or dict (export)")