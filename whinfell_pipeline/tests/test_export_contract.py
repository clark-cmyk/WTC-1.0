"""Tests for locked WTM EXPORT v2.1 contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.export_contract import build_wtm_export_v21, parse_wtm_export_v21
from whinfell_pipeline.hydrate import build_hydration_bundle


class TestExportContract(unittest.TestCase):
    def test_roundtrip_full_example(self):
        sample = (REPO_ROOT / "whinfell_pipeline/examples/wtm_export_v21_full.txt").read_text()
        parsed = parse_wtm_export_v21(sample)
        self.assertEqual(parsed.whinfell_score, 58)
        self.assertEqual(parsed.sq3_score, 55)
        self.assertIn("credit", parsed.tracer_horizons)
        self.assertEqual(parsed.provenance.snapshot_id, "snap_20260627_koyfin_01")
        self.assertEqual(parsed.provenance.freshness_status, "fresh")

    def test_build_includes_provenance_and_tracer(self):
        block = build_wtm_export_v21(
            global_data={"whinfell_score": 62, "transmission_state": "stressed", "regime_tag": "Test"},
            china_data={"sq3_score": 55, "sq3_band": "Mixed / Fragile", "policy_strength": 70, "state_impulse_score": 10, "growth_impulse_score": 60},
            tracer_horizons={"highbeta": {"d1": "down", "d5": "flat"}},
            include_provenance=True,
        )
        self.assertIn("SQ3 Score: 55", block)
        self.assertIn("Signal Tracer — High-Beta / BTC", block)
        self.assertIn("Freshness Status:", block)

    def test_hydration_bundle_shape(self):
        bundle = build_hydration_bundle()
        self.assertEqual(bundle["hydration_version"], "1.2.0")
        self.assertIn("wtm_export_v21", bundle)
        self.assertIn("wtm_export_v22", bundle)
        self.assertIn("node_cockpits", bundle)
        self.assertIn("cockpit_context", bundle)
        self.assertIn("global", bundle)
        self.assertIn("execution", bundle)
        self.assertEqual(bundle["tracer_apply_mode"], "confirm_required")
        self.assertIn("WTM EXPORT v2.1", bundle["wtm_export_v21"])
        self.assertIn("WTM EXPORT v2.2", bundle["wtm_export_v22"])
        self.assertIn("freshness_status", bundle)

        st = bundle["suggested_tracer"]
        self.assertIsInstance(st, dict)
        self.assertGreaterEqual(len(st), 3)
        for stage in ("liquidity", "credit", "highbeta", "basis"):
            self.assertIn(stage, st)
            self.assertIn("d1", st[stage])

        self.assertIn("btc_bias", bundle["execution"])
        self.assertEqual(bundle["global"].get("btc_bias"), bundle["execution"]["btc_bias"])

    def test_hydration_bundle_l3_from_execution_sidecar(self):
        exec_json = REPO_ROOT / "whinfell_pipeline/examples/comet_barchart_btc.json"
        bundle = build_hydration_bundle(execution_path=exec_json)
        self.assertEqual(bundle["global"].get("near_month"), "Jul")
        self.assertEqual(bundle["global"].get("basis_spread"), "1.25")
        self.assertEqual(bundle["execution"].get("near_month"), "Jul")
        self.assertEqual(bundle["execution"].get("basis_spread"), "1.25")


if __name__ == "__main__":
    unittest.main()