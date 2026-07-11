"""Tests for ARCH-1 M2 component_router."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.component_router import (
    count_live_components,
    derive_live_component_inputs,
)
from whinfell_pipeline.rv_history import ensure_dated_series_fixture, load_rv_history


class TestComponentRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_dated_series_fixture(REPO_ROOT, sessions=120)
        cls.history = load_rv_history(REPO_ROOT)

    def test_liquidity_components_have_rv_history_source(self):
        marks = {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"}
        comps = derive_live_component_inputs(
            "liquidity",
            marks,
            as_of="2026-06-30T12:00:00+00:00",
            spread_history=self.history,
        )
        self.assertGreaterEqual(len(comps), 2)
        live = [c for c in comps if c.get("source") == "rv_history"]
        self.assertGreaterEqual(len(live), 1)
        self.assertIsInstance(live[0]["value"], (int, float))

    def test_count_live_components(self):
        comps = [
            {"source": "rv_history", "direction": "up"},
            {"source": "rv_history", "direction": "flat"},
            {"source": "horizon_fallback", "direction": "up"},
        ]
        self.assertEqual(count_live_components(comps), 1)


if __name__ == "__main__":
    unittest.main()