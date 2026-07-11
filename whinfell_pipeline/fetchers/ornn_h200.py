"""Ornn H200 forward/rental stub — cache at data/compute/v1/ornn_h200.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from whinfell_pipeline.fetchers.cache import read_cached, utc_now_iso, write_cached


def default_ornn_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "compute" / "v1" / "ornn_h200.json"


def stub_ornn_h200() -> dict[str, Any]:
    return {
        "source": "ornn_stub_v1",
        "as_of": utc_now_iso(),
        "gpu": "H200",
        "rental_usd_per_hr": {"spot": 4.12, "1m_fwd": 4.45, "3m_fwd": 4.78, "6m_fwd": 5.02},
        "forward_curve": [
            {"tenor": "Spot", "price": 4.12},
            {"tenor": "1M", "price": 4.45},
            {"tenor": "3M", "price": 4.78},
            {"tenor": "6M", "price": 5.02},
            {"tenor": "12M", "price": 5.28},
        ],
        "basis_vs_h100_pct": -8.4,
        "delivery_slippage_days": 12,
        "status": "stub",
    }


def fetch_ornn_h200(repo_root: Path | None = None, *, refresh: bool = False) -> dict[str, Any]:
    path = default_ornn_path(repo_root)
    if not refresh:
        cached = read_cached(path)
        if cached:
            return cached
    payload = stub_ornn_h200()
    write_cached(path, payload)
    return payload