"""China Transmission Ladder — canonical stage overlay (v1.1).

Authoritative ladder math for China track: stage weights, composites, SQ3 handicap,
and final bands. UI layers (TC, Deep Dive) derive from this module via
``whinfell_pipeline.desk_china_ladder_models`` — do not duplicate weights in JS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

# Spec version stamped into generated desk_china_ladder_models.js
LADDER_SPEC_VERSION = "china_ladder.v1.1"

# Canonical stage IDs — must match Global ladder (liquidity → basis).
CANONICAL_STAGE_IDS: tuple[str, ...] = (
    "liquidity",
    "credit",
    "breadth",
    "highbeta",
    "basis",
)

HORIZON_KEYS: tuple[str, ...] = ("d1", "d5", "d20", "d60")
HZ_SCORE: dict[str, int] = {"up": 1, "flat": 0, "down": -1, "": 0}
MARK_SCORE: dict[str, int] = {"up": 75, "flat": 50, "down": 25}

# Stage-level health bands (composite score per stage — same scale as Global ladder cards).
STAGE_HEALTH_BANDS: tuple[tuple[int, str, str], ...] = (
    (80, "Healthy", "healthy"),
    (65, "Constructive", "constructive"),
    (50, "Fragile", "fragile"),
    (0, "Broken", "broken"),
)

# Final China score interpretation bands (post-SQ3 handicap) — desk v1.1.
CHINA_LADDER_FINAL_BANDS: tuple[tuple[int, int, str, str], ...] = (
    (80, 100, "Strong", "Policy support aligned with ladder"),
    (65, 79, "Constructive", "Normal sizing acceptable"),
    (50, 64, "Mixed / Fragile", "Selective / reduced size"),
    (0, 49, "Impaired", "Heavily discount or avoid new exposure"),
)

# Back-compat alias — prefer CHINA_LADDER_FINAL_BANDS in new code.
CHINA_FINAL_BANDS = CHINA_LADDER_FINAL_BANDS

STAGE_TIE_RANK: dict[str, int] = {
    "liquidity": 0,
    "credit": 1,
    "breadth": 2,
    "highbeta": 3,
    "basis": 4,
}

# China stage card copy — track-specific; exported to generated JS (no Global BTC text).
CHINA_STAGE_UI_COPY: dict[str, dict[str, str]] = {
    "liquidity": {
        "state": "{score} / {band} — China funding and CNH liquidity {posture}.",
        "evidence": "GCN10YR / USDCNH net {net}; offshore funding sets daily China posture.",
        "trigger": "Sustained >60 with easier 5D/20D China rates / CNH marks.",
    },
    "credit": {
        "state": "{score} / {band} — {durability} cross-asset credit read.",
        "evidence": "KHYB vs 2829.HK net {net}; provisional proxy — validate live.",
        "trigger": "Net ≥+2 with SQ3 policy ≥50 and breadth confirm on CSI300/HSTECH.",
    },
    "breadth": {
        "state": "{score} / {band} — participation {participation}.",
        "evidence": "CSI300 vs HSTECH net {net}; broad vs tech leadership split.",
        "trigger": "5D/20D net ≥+1 unlocks larger China-linked sleeves.",
    },
    "highbeta": {
        "state": "{score} / {band} — cyclical beta {transmitting}.",
        "evidence": "Copper / iron ore net {net}; cyclical transmission vs policy impulse.",
        "trigger": "Net ≥+2 with credit stage ≥60 for larger cyclical beta.",
    },
    "basis": {
        "state": "{score} / {band} — {carry} Cu/IO curve quality.",
        "evidence": "Front vs deferred net {net}; warehouse carry not always backed.",
        "trigger": "Net ≥+1 and China final (adj.) ≥50 for aggressive curve harvest.",
    },
}

# Expert-judgment weights — China overlay v1.1 (sum = 100 per stage).
CHINA_STAGE_MODELS: dict[str, dict[str, Any]] = {
    "liquidity": {
        "name": "Liquidity & Rates",
        "components": [
            {"label": "1D funding impulse", "w": 15, "hz": "d1"},
            {"label": "5D funding trend", "w": 20, "hz": "d5"},
            {"label": "20D China rates / CNH", "w": 40, "hz": "d20"},
            {"label": "60D liquidity regime", "w": 25, "hz": "d60"},
        ],
        "proxies": ["GCN10YR", "USDCNH"],
        "status": "confirmed",
        "notes": "China 10Y + offshore CNH liquidity",
    },
    "credit": {
        "name": "Credit Confirmation",
        "components": [
            {"label": "1D HY vs govt impulse", "w": 20, "hz": "d1"},
            {"label": "5D credit momentum", "w": 30, "hz": "d5"},
            {"label": "20D KHYB vs 2829.HK", "w": 30, "hz": "d20"},
            {"label": "60D durability", "w": 20, "hz": "d60"},
        ],
        "proxies": ["KHYB", "2829.HK"],
        "status": "provisional",
        "notes": "Working desk proxy — validate over live sessions",
    },
    "breadth": {
        "name": "Equity Breadth",
        "components": [
            {"label": "1D participation", "w": 25, "hz": "d1"},
            {"label": "5D breadth thrust", "w": 25, "hz": "d5"},
            {"label": "20D CSI300 vs HSTECH", "w": 30, "hz": "d20"},
            {"label": "60D sustained breadth", "w": 20, "hz": "d60"},
        ],
        "proxies": ["000300.SS", "HSTECH"],
        "status": "confirmed",
        "notes": "Broad market vs tech participation",
    },
    "highbeta": {
        "name": "High-Beta / China Cyclical Transmission",
        "components": [
            {"label": "1D cyclical impulse", "w": 25, "hz": "d1"},
            {"label": "5D copper / iron ore", "w": 25, "hz": "d5"},
            {"label": "20D beta transmission", "w": 30, "hz": "d20"},
            {"label": "60D regime persistence", "w": 20, "hz": "d60"},
        ],
        "proxies": ["Copper futures", "Iron Ore futures"],
        "status": "confirmed",
        "notes": "Stage-4 cyclical beta analog",
    },
    "basis": {
        "name": "Basis & Term Structure",
        "components": [
            {"label": "1D curve impulse", "w": 20, "hz": "d1"},
            {"label": "5D roll pressure", "w": 25, "hz": "d5"},
            {"label": "20D front vs deferred", "w": 35, "hz": "d20"},
            {"label": "60D carry durability", "w": 20, "hz": "d60"},
        ],
        "proxies": ["Copper spreads", "Iron Ore spreads"],
        "status": "confirmed",
        "notes": "Front/deferred curve quality",
    },
}


@dataclass(frozen=True)
class ChinaFinalBand:
    band: str
    desk_meaning: str
    min_score: int
    max_score: int


@dataclass(frozen=True)
class ChinaLadderScoreResult:
    raw_ladder_score: int
    sq3_score: int
    multiplier: float
    final_china_score: int
    stage_scores: dict[str, int]
    band: str = ""
    desk_meaning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_ladder_score": self.raw_ladder_score,
            "sq3_score": self.sq3_score,
            "multiplier": round(self.multiplier, 2),
            "final_china_score": self.final_china_score,
            "band": self.band,
            "desk_meaning": self.desk_meaning,
            "stage_scores": dict(self.stage_scores),
        }


def stage_health_band(composite_score: int) -> tuple[str, str]:
    """Map stage composite to Healthy / Constructive / Fragile / Broken."""
    score = max(0, min(100, int(composite_score)))
    for threshold, band, status in STAGE_HEALTH_BANDS:
        if score >= threshold:
            return band, status
    return "Broken", "broken"


@dataclass(frozen=True)
class WeakestStageResult:
    stage_id: str
    name: str
    value: int
    mode: str


def weakest_stage(
    stages: list[dict[str, Any]],
    mode: Literal["composite", "net"] = "composite",
) -> WeakestStageResult:
    """Pick weakest canonical stage.

    composite — lowest weighted stage score (Deep Dive cards, TC China cluster).
    net       — lowest horizon net sum (tracer-style read only; document if used).
    Tie-break: STAGE_TIE_RANK (liquidity wins on equal scores).
    """
    if not stages:
        return WeakestStageResult(stage_id="", name="—", value=0, mode=mode)
    key = "score" if mode == "composite" else "net"

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        val = int(row.get(key, 0))
        sid = str(row.get("id", ""))
        return (val, STAGE_TIE_RANK.get(sid, 99))

    weakest = min(stages, key=sort_key)
    return WeakestStageResult(
        stage_id=str(weakest.get("id", "")),
        name=str(weakest.get("name", "—")),
        value=int(weakest.get(key, 0)),
        mode=mode,
    )


def interpretation_band_for_final_score(final_score: int) -> ChinaFinalBand:
    """Map SQ3-adjusted final China score to desk interpretation band."""
    score = max(0, min(100, int(final_score)))
    for lo, hi, band, meaning in CHINA_LADDER_FINAL_BANDS:
        if lo <= score <= hi:
            return ChinaFinalBand(band=band, desk_meaning=meaning, min_score=lo, max_score=hi)
    return ChinaFinalBand(
        band="Impaired",
        desk_meaning="Heavily discount or avoid new exposure",
        min_score=0,
        max_score=49,
    )


def sq3_multiplier(sq3_score: int) -> float:
    """SQ3 handicap multiplier per China Ladder v1.1."""
    if sq3_score >= 80:
        return 1.00
    if sq3_score >= 65:
        return 0.95
    if sq3_score >= 50:
        return 0.80
    return 0.60


def calculate_final_china_score(ladder_score: int, sq3_score: int) -> dict[str, Any]:
    """Apply SQ3 overlay to raw China ladder composite."""
    multiplier = sq3_multiplier(sq3_score)
    final_score = int(round(ladder_score * multiplier))
    final_score = max(0, min(100, final_score))
    band_info = interpretation_band_for_final_score(final_score)
    return {
        "raw_ladder_score": ladder_score,
        "sq3_score": sq3_score,
        "multiplier": round(multiplier, 2),
        "final_china_score": final_score,
        "band": band_info.band,
        "desk_meaning": band_info.desk_meaning,
    }


def _stage_horizons(horizons: Mapping[str, Any], stage_id: str) -> dict[str, str]:
    stage = horizons.get(stage_id) or {}
    if not isinstance(stage, dict):
        return {}
    return {k: str(stage.get(k, "flat")).lower() for k in HORIZON_KEYS}


def composite_stage_score(stage_id: str, horizons: Mapping[str, Any]) -> int:
    """Weighted composite for one canonical stage from tracer horizons."""
    model = CHINA_STAGE_MODELS.get(stage_id)
    if not model:
        return 50
    hz = _stage_horizons(horizons, stage_id)
    total = 0.0
    for comp in model["components"]:
        mark = hz.get(comp["hz"], "flat")
        sub = MARK_SCORE.get(mark, 50)
        total += comp["w"] * sub
    return int(round(total / 100.0))


def compute_raw_ladder_score(horizons: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    """Mean of five canonical stage composites."""
    stage_scores = {sid: composite_stage_score(sid, horizons) for sid in CANONICAL_STAGE_IDS}
    raw = int(round(sum(stage_scores.values()) / len(CANONICAL_STAGE_IDS)))
    return raw, stage_scores


def score_china_ladder(
    horizons: Mapping[str, Any],
    sq3_score: int,
) -> ChinaLadderScoreResult:
    """Full China ladder read: raw composite + SQ3-adjusted final."""
    raw, stage_scores = compute_raw_ladder_score(horizons)
    overlay = calculate_final_china_score(raw, sq3_score)
    return ChinaLadderScoreResult(
        raw_ladder_score=overlay["raw_ladder_score"],
        sq3_score=overlay["sq3_score"],
        multiplier=overlay["multiplier"],
        final_china_score=overlay["final_china_score"],
        stage_scores=stage_scores,
        band=overlay["band"],
        desk_meaning=overlay["desk_meaning"],
    )


def china_ladder_js_spec() -> dict[str, Any]:
    """Serializable spec for desk_china_ladder_models.js generation."""
    stages = []
    for stage_id in CANONICAL_STAGE_IDS:
        m = CHINA_STAGE_MODELS[stage_id]
        proxy_sub = " · ".join(m["proxies"][:2])
        if m.get("status") == "provisional":
            proxy_sub += " · provisional"
        stages.append(
            {
                "id": stage_id,
                "name": m["name"],
                "short": {
                    "liquidity": "Liq",
                    "credit": "Credit",
                    "breadth": "Breadth",
                    "highbeta": "Cyc",
                    "basis": "Basis",
                }[stage_id],
                "sub": proxy_sub,
            }
        )
    models = {}
    for stage_id, m in CHINA_STAGE_MODELS.items():
        models[stage_id] = {
            "components": m["components"],
            "proxies": m["proxies"],
            "status": m.get("status", "confirmed"),
        }
    return {
        "version": LADDER_SPEC_VERSION,
        "source": "china_policy_track/china_ladder.py",
        "stages": stages,
        "mark_score": MARK_SCORE,
        "stage_models": models,
        "final_bands": [
            {"min": lo, "max": hi, "band": band, "desk_meaning": meaning}
            for lo, hi, band, meaning in CHINA_LADDER_FINAL_BANDS
        ],
        "stage_health_bands": [
            {"min": t, "band": b, "status": s} for t, b, s in STAGE_HEALTH_BANDS
        ],
        "stage_tie_rank": STAGE_TIE_RANK,
        "ui_copy": CHINA_STAGE_UI_COPY,
        "sq3_multipliers": [
            {"min_sq3": 80, "multiplier": 1.00},
            {"min_sq3": 65, "multiplier": 0.95},
            {"min_sq3": 50, "multiplier": 0.80},
            {"min_sq3": 0, "multiplier": 0.60},
        ],
    }


def stage_map_for_desk() -> list[dict[str, Any]]:
    """Serializable stage mapping for UI / chart-link generators."""
    rows = []
    for stage_id in CANONICAL_STAGE_IDS:
        m = CHINA_STAGE_MODELS[stage_id]
        rows.append(
            {
                "id": stage_id,
                "name": m["name"],
                "proxies": list(m["proxies"]),
                "status": m["status"],
                "notes": m["notes"],
            }
        )
    return rows