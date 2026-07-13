"""Structured data models for the China Policy track (three dimensions)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from china_policy_track.version import SCHEMA_VERSION, TRACK_ID


HIERARCHY_LEVELS = frozenset({"central", "provincial", "sectoral", "mixed"})
REGULATORY_DIRECTIONS = frozenset({"tightening", "neutral", "easing"})
INTERVENTION_LEVELS = frozenset({"low", "medium", "high"})
MARKET_SENTIMENTS = frozenset({"constructive", "mixed", "impaired"})
LIQUIDITY_IMPULSES = frozenset({"expanding", "stable", "contracting"})
SOURCES = frozenset({"perplexity", "koyfin", "barchart", "manual"})


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _norm_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _norm_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",")]
        return [p for p in parts if p]
    if isinstance(value, Sequence):
        return [_norm_str(v) for v in value if _norm_str(v)]
    return []


def _norm_choice(value: Any, allowed: frozenset[str], default: str) -> str:
    key = _norm_str(value).lower()
    return key if key in allowed else default


@dataclass(frozen=True)
class PolicyHierarchyStrength:
    """Dimension 1: Policy Hierarchy & Strength."""

    hierarchy_level: str  # central | provincial | sectoral | mixed
    policy_strength: int  # 0–100
    dominant_theme: str
    supporting_signals: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> PolicyHierarchyStrength:
        return cls(
            hierarchy_level=_norm_choice(
                data.get("hierarchy_level", data.get("policy_hierarchy_level")),
                HIERARCHY_LEVELS,
                "central",
            ),
            policy_strength=_clamp_int(
                data.get("policy_strength", data.get("strength")),
                0,
                100,
                50,
            ),
            dominant_theme=_norm_str(
                data.get("dominant_theme", data.get("policy_dominant_theme")),
                "unspecified",
            ),
            supporting_signals=tuple(
                _norm_list(data.get("supporting_signals", data.get("policy_supporting_signals")))
            ),
            notes=_norm_str(data.get("notes", data.get("policy_notes"))),
        )


@dataclass(frozen=True)
class StateControlImpulse:
    """Dimension 2: State Control Impulse."""

    impulse_score: int  # -100..100 (positive = more state control)
    regulatory_direction: str  # tightening | neutral | easing
    state_intervention_level: str  # low | medium | high
    key_controls: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> StateControlImpulse:
        return cls(
            impulse_score=_clamp_int(
                data.get("impulse_score", data.get("state_impulse_score")),
                -100,
                100,
                0,
            ),
            regulatory_direction=_norm_choice(
                data.get("regulatory_direction", data.get("state_regulatory_direction")),
                REGULATORY_DIRECTIONS,
                "neutral",
            ),
            state_intervention_level=_norm_choice(
                data.get("state_intervention_level", data.get("intervention_level")),
                INTERVENTION_LEVELS,
                "medium",
            ),
            key_controls=tuple(
                _norm_list(data.get("key_controls", data.get("state_key_controls")))
            ),
            notes=_norm_str(data.get("notes", data.get("state_notes"))),
        )


@dataclass(frozen=True)
class GrowthMarketImpulse:
    """Dimension 3: Growth & Market Impulse."""

    growth_impulse_score: int  # 0–100
    market_sentiment: str  # constructive | mixed | impaired
    liquidity_impulse: str  # expanding | stable | contracting
    key_indicators: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GrowthMarketImpulse:
        return cls(
            growth_impulse_score=_clamp_int(
                data.get("growth_impulse_score", data.get("growth_score")),
                0,
                100,
                50,
            ),
            market_sentiment=_norm_choice(
                data.get("market_sentiment", data.get("growth_market_sentiment")),
                MARKET_SENTIMENTS,
                "mixed",
            ),
            liquidity_impulse=_norm_choice(
                data.get("liquidity_impulse", data.get("growth_liquidity_impulse")),
                LIQUIDITY_IMPULSES,
                "stable",
            ),
            key_indicators=tuple(
                _norm_list(data.get("key_indicators", data.get("growth_key_indicators")))
            ),
            notes=_norm_str(data.get("notes", data.get("growth_notes"))),
        )


@dataclass(frozen=True)
class ChinaPolicyObservation:
    """Top-level China Policy track record."""

    observation_id: str
    as_of: datetime
    source: str
    policy_hierarchy_strength: PolicyHierarchyStrength
    state_control_impulse: StateControlImpulse
    growth_market_impulse: GrowthMarketImpulse
    schema_version: str = SCHEMA_VERSION
    track_id: str = TRACK_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "as_of": self.as_of.isoformat(),
            "source": self.source,
            "policy_hierarchy_strength": self.policy_hierarchy_strength.to_dict(),
            "state_control_impulse": self.state_control_impulse.to_dict(),
            "growth_market_impulse": self.growth_market_impulse.to_dict(),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ChinaPolicyObservation:
        as_of_raw = data.get("as_of") or data.get("timestamp")
        if isinstance(as_of_raw, datetime):
            as_of = as_of_raw
        else:
            as_of = datetime.fromisoformat(_norm_str(as_of_raw, datetime.utcnow().isoformat()))

        return cls(
            observation_id=_norm_str(data.get("observation_id"), "china-unknown"),
            as_of=as_of,
            source=_norm_choice(data.get("source"), SOURCES, "manual"),
            policy_hierarchy_strength=PolicyHierarchyStrength.from_mapping(
                data.get("policy_hierarchy_strength", data)
            ),
            state_control_impulse=StateControlImpulse.from_mapping(
                data.get("state_control_impulse", data)
            ),
            growth_market_impulse=GrowthMarketImpulse.from_mapping(
                data.get("growth_market_impulse", data)
            ),
            schema_version=_norm_str(data.get("schema_version"), SCHEMA_VERSION),
            track_id=_norm_str(data.get("track_id"), TRACK_ID),
        )


def build_observation_from_dimensions(
    *,
    observation_id: str,
    as_of: datetime,
    source: str,
    policy: Mapping[str, Any],
    state_control: Mapping[str, Any],
    growth: Mapping[str, Any],
) -> ChinaPolicyObservation:
    """Pure constructor for the three dimension payloads."""
    return ChinaPolicyObservation(
        observation_id=observation_id,
        as_of=as_of,
        source=_norm_choice(source, SOURCES, "manual"),
        policy_hierarchy_strength=PolicyHierarchyStrength.from_mapping(policy),
        state_control_impulse=StateControlImpulse.from_mapping(state_control),
        growth_market_impulse=GrowthMarketImpulse.from_mapping(growth),
    )