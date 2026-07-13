"""SQ3 scoring engine for the China Policy track.

Transparent, auditable composite of three dimension scalars with fixed weights.
Does not interact with Global Credit Confirmation Score logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from china_policy_track.models import ChinaPolicyObservation

# --- Single-edit configuration (weights, scaling, bands) ---

WEIGHT_POLICY_HIERARCHY = 0.35
WEIGHT_STATE_CONTROL = 0.35
WEIGHT_GROWTH_MARKET = 0.30

# Signed impulse_score: positive = more state control (impairs transmission read).
# Linear map: +100 -> 0, 0 -> 50, -100 -> 100 on the 0-100 SQ3 sub-scale.
STATE_CONTROL_SCALE_MIN = -100
STATE_CONTROL_SCALE_MAX = 100

INTERPRETATION_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 49, "Impaired"),
    (50, 64, "Mixed / Fragile"),
    (65, 79, "Constructive"),
    (80, 100, "Strong"),
)


@dataclass(frozen=True)
class SQ3ScoreResult:
    """Auditable SQ3 output: numeric score plus interpretation band."""

    sq3_score: int
    interpretation_band: str
    policy_component: float
    state_control_component: float
    growth_market_component: float
    policy_normalized: float
    state_control_normalized: float
    growth_market_normalized: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sq3_score": self.sq3_score,
            "interpretation_band": self.interpretation_band,
            "components": {
                "policy_hierarchy": round(self.policy_component, 4),
                "state_control": round(self.state_control_component, 4),
                "growth_market": round(self.growth_market_component, 4),
            },
            "normalized_inputs": {
                "policy_hierarchy": self.policy_normalized,
                "state_control": self.state_control_normalized,
                "growth_market": self.growth_market_normalized,
            },
            "weights": {
                "policy_hierarchy": WEIGHT_POLICY_HIERARCHY,
                "state_control": WEIGHT_STATE_CONTROL,
                "growth_market": WEIGHT_GROWTH_MARKET,
            },
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def normalize_policy_strength(policy_strength: int) -> float:
    """Dimension 1 scalar already on 0-100."""
    return _clamp(float(policy_strength), 0.0, 100.0)


def normalize_state_control_impulse(impulse_score: int) -> float:
    """Map signed state-control impulse to 0-100 (higher control -> lower sub-score)."""
    clamped = _clamp(float(impulse_score), STATE_CONTROL_SCALE_MIN, STATE_CONTROL_SCALE_MAX)
    return (100.0 - clamped) / 2.0


def normalize_growth_impulse(growth_impulse_score: int) -> float:
    """Dimension 3 scalar already on 0-100."""
    return _clamp(float(growth_impulse_score), 0.0, 100.0)


def interpret_sq3_band(score: int) -> str:
    """Map numeric SQ3 score to interpretation band label."""
    bounded = int(_clamp(float(score), 0.0, 100.0))
    for lo, hi, label in INTERPRETATION_BANDS:
        if lo <= bounded <= hi:
            return label
    return "Unknown"


def calculate_sq3(
    policy_strength: int,
    state_impulse_score: int,
    growth_impulse_score: int,
) -> SQ3ScoreResult:
    """Core SQ3 calculation from the three dimension scalars."""
    policy_n = normalize_policy_strength(policy_strength)
    state_n = normalize_state_control_impulse(state_impulse_score)
    growth_n = normalize_growth_impulse(growth_impulse_score)

    policy_c = WEIGHT_POLICY_HIERARCHY * policy_n
    state_c = WEIGHT_STATE_CONTROL * state_n
    growth_c = WEIGHT_GROWTH_MARKET * growth_n

    raw = policy_c + state_c + growth_c
    score = int(round(_clamp(raw, 0.0, 100.0)))

    return SQ3ScoreResult(
        sq3_score=score,
        interpretation_band=interpret_sq3_band(score),
        policy_component=policy_c,
        state_control_component=state_c,
        growth_market_component=growth_c,
        policy_normalized=policy_n,
        state_control_normalized=state_n,
        growth_market_normalized=growth_n,
    )


def score_observation(observation: ChinaPolicyObservation) -> SQ3ScoreResult:
    """Score a parsed ChinaPolicyObservation."""
    ph = observation.policy_hierarchy_strength
    sc = observation.state_control_impulse
    gm = observation.growth_market_impulse
    return calculate_sq3(
        ph.policy_strength,
        sc.impulse_score,
        gm.growth_impulse_score,
    )


def score_from_mapping(data: Mapping[str, Any]) -> SQ3ScoreResult:
    """Score structured dict matching ChinaPolicyObservation / parse_input shape."""
    if isinstance(data, ChinaPolicyObservation):
        return score_observation(data)
    return score_observation(ChinaPolicyObservation.from_mapping(data))


def score_input(payload: str | Mapping[str, Any]) -> SQ3ScoreResult:
    """Parse Perplexity text or structured export, then score."""
    from china_policy_track.data_parser import parse_input

    return score_observation(parse_input(payload))