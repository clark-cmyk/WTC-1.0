"""Tests for ARCH-1 RV history loader and quartile horizons."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.node_cockpits import CANONICAL_NODE_IDS, build_node_cockpits
from whinfell_pipeline.rv_history import (
    default_dated_series_path,
    ensure_dated_series_fixture,
    load_koyfin_rv_series,
    load_rv_history,
)

RV_HORIZONS = ("1m", "3m", "6m", "12m", "3y")


class TestRvHistory(unittest.TestCase):
    def test_ensure_dated_series_fixture_writes_all_keys(self):
        path = ensure_dated_series_fixture(REPO_ROOT, sessions=800)
        self.assertTrue(path.is_file())
        self.assertEqual(path, default_dated_series_path(REPO_ROOT))
        history = load_rv_history(REPO_ROOT)
        self.assertGreater(len(history), 0)
        for key, vals in history.items():
            self.assertGreaterEqual(len(vals), 2, f"{key} needs >=2 points")

    def test_hydration_produces_five_horizons_per_node(self):
        bundle = build_hydration_bundle()
        for node_id in CANONICAL_NODE_IDS:
            cockpit = bundle["node_cockpits"][node_id]
            rv = cockpit["rv_basis"]
            series_id = rv.get("active_series_id")
            self.assertTrue(series_id, f"{node_id} missing active_series_id")
            series = rv["series"][series_id]
            horizons = series["horizons"]
            self.assertEqual(set(horizons.keys()), set(RV_HORIZONS), node_id)
            for hz in RV_HORIZONS:
                self.assertIn("percentile", horizons[hz])
                self.assertIn("quartile", horizons[hz])
                self.assertGreaterEqual(horizons[hz]["n_observations"], 2)

    def test_load_koyfin_rv_series_from_quarantine_wide_sample(self):
        sample = REPO_ROOT / "staged_raw/quarantine/20260628/rates_20260628_1119.csv"
        if not sample.is_file():
            self.skipTest("rates wide sample missing")
        from whinfell_pipeline.rv_history import _series_from_wide_csv

        series = _series_from_wide_csv(sample)
        self.assertIn("SOFR", series)
        self.assertGreaterEqual(len(series["SOFR"]), 100)

    def test_build_node_cockpits_uses_spread_history_param(self):
        history = load_rv_history(REPO_ROOT)
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed"},
            suggested_tracer={nid: {"d1": "flat", "d5": "flat", "d20": "flat", "d60": "flat"} for nid in CANONICAL_NODE_IDS},
            as_of=__import__("datetime").datetime(2026, 6, 29, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
            spread_history=history,
        )
        basis = cockpits["basis"]["rv_basis"]
        sid = basis["active_series_id"]
        self.assertEqual(len(basis["series"][sid]["horizons"]), 5)


if __name__ == "__main__":
    unittest.main()