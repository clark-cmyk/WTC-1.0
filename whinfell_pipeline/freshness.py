"""Freshness status from observation age."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


FRESH_HOURS = 4
STALE_HOURS = 24


def compute_freshness(as_of: datetime, *, now: datetime | None = None) -> FreshnessStatus:
    """Map observation timestamp to freshness band."""
    ref = now or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = as_of.astimezone(timezone.utc)
    age_h = (ref - as_of).total_seconds() / 3600.0
    if age_h < 0:
        return FreshnessStatus.FRESH
    if age_h < FRESH_HOURS:
        return FreshnessStatus.FRESH
    if age_h < STALE_HOURS:
        return FreshnessStatus.AGING
    return FreshnessStatus.STALE