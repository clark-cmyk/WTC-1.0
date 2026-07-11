"""GridStatus MISO Indiana Hub stub — cache at data/power/v1/miso_indiana_hub.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from whinfell_pipeline.fetchers.cache import read_cached, utc_now_iso, write_cached


def default_miso_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "power" / "v1" / "miso_indiana_hub.json"


def stub_miso_indiana_hub() -> dict[str, Any]:
    return {
        "source": "gridstatus_stub_v1",
        "as_of": utc_now_iso(),
        "hub": "MISO.INDIANA.HUB",
        "lmp_usd_per_mwh": {"rt": 38.6, "da": 35.2},
        "recent_rt": [
            {"hour": "H-4", "lmp": 41.2},
            {"hour": "H-3", "lmp": 39.8},
            {"hour": "H-2", "lmp": 37.1},
            {"hour": "H-1", "lmp": 38.6},
        ],
        "gpu_power_sensitivity": "med",
        "status": "stub",
    }


def fetch_miso_indiana_hub(repo_root: Path | None = None, *, refresh: bool = False) -> dict[str, Any]:
    path = default_miso_path(repo_root)
    if not refresh:
        cached = read_cached(path)
        if cached:
            return cached
    payload = stub_miso_indiana_hub()
    write_cached(path, payload)
    return payload