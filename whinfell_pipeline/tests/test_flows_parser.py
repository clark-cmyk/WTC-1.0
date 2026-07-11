"""Tests for WTM-Flows parser (PR-3a)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.tests.goal_scratch import goal_scratch

SCRATCH = goal_scratch()

from whinfell_pipeline.flows_parser import (
    compute_rolling_metrics,
    detect_flows_format,
    ensure_flows_sidecar,
    parse_and_write,
    parse_flows_csv,
    try_parse_flows_csv,
    write_flows_sidecar,
)
from whinfell_pipeline.data_dictionary import funds_flow_basket_for_node as basket_for
from whinfell_pipeline.funds_flows import (
    build_flows_sidecar_metadata,
    build_funds_flows,
    resolve_degrade_mode,
)
from whinfell_pipeline.hydrate import build_hydration_bundle

QUARANTINE_CSV = REPO_ROOT / "staged_raw" / "quarantine" / "20260629" / "WTM-Flows-Global.csv"
HEAD_CSV = REPO_ROOT / "whinfell_pipeline" / "examples" / "flows" / "WTM-Flows-Global-head.csv"


class TestFlowsParser(unittest.TestCase):
    def test_detect_wtm_flows_wide(self):
        headers = ["Date", "HYG Flow (D)", "HYG AUM", "SPY Flow (D)", "SPY AUM"]
        self.assertEqual(detect_flows_format(headers), "wtm_flows_wide")
        self.assertEqual(detect_flows_format(["Ticker", "AUM"]), "invalid")

    def test_parse_quarantine_wtm_flows_global(self):
        self.assertTrue(QUARANTINE_CSV.is_file(), f"missing fixture {QUARANTINE_CSV}")
        payload = parse_flows_csv(QUARANTINE_CSV)
        self.assertEqual(payload["ingest_mode"], "timeseries_primary")
        self.assertEqual(payload["source_channel"], "koyfin_wtm_flows")
        self.assertGreaterEqual(payload["history_sessions"], 20)
        self.assertIn("HYG", payload["tickers"])
        self.assertIn("LQD", payload["tickers"])
        hyg = payload["tickers"]["HYG"]
        self.assertIsNotNone(hyg["latest"]["flow_pct_aum_1d"])
        self.assertIsNotNone(hyg["rolling"]["flow_pct_aum_5d"])
        self.assertGreaterEqual(hyg["rolling"]["sessions_in_5d"], 5)
        (SCRATCH / "quarantine_sidecar.json").write_text(json.dumps(payload, indent=2))

    def test_compute_rolling_metrics_sum_not_average(self):
        sessions = [
            {"flow_usd_1d": 10.0, "flow_pct_aum_1d": 0.1},
            {"flow_usd_1d": 20.0, "flow_pct_aum_1d": 0.2},
            {"flow_usd_1d": 30.0, "flow_pct_aum_1d": 0.3},
            {"flow_usd_1d": 40.0, "flow_pct_aum_1d": 0.4},
            {"flow_usd_1d": 50.0, "flow_pct_aum_1d": 0.5},
        ]
        rolling = compute_rolling_metrics(sessions)
        self.assertAlmostEqual(rolling["flow_pct_aum_5d"], 1.5, places=4)
        self.assertAlmostEqual(rolling["flow_usd_5d"], 150.0, places=2)

    def test_write_sidecar_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "latest_flows.json"
            payload = parse_flows_csv(HEAD_CSV)
            write_flows_sidecar(payload, out)
            self.assertTrue(out.is_file())
            loaded = json.loads(out.read_text())
            self.assertEqual(loaded["version"], "1.0.0")
            self.assertGreater(len(loaded["tickers"]), 0)

    def test_try_parse_missing_returns_none(self):
        self.assertIsNone(try_parse_flows_csv("/nonexistent/flows.csv"))

    def test_credit_full_basket_flows_meta_ok(self):
        payload = parse_flows_csv(HEAD_CSV)
        basket = basket_for("credit")
        degrade = resolve_degrade_mode(payload, "credit", basket)
        self.assertEqual(degrade, "full")
        ff = build_funds_flows("credit", sidecar=payload, node_cockpit={"node_id": "credit", "confidence": "low"})
        self.assertEqual(ff["flows_meta"]["flows_status"], "ok")
        self.assertEqual(ff["flows_meta"]["flows_source"], "wtm_flows_timeseries")
        self.assertFalse(ff["flows_meta"]["flows_degraded"])
        self.assertEqual(ff["flows_meta"]["flows_confidence_penalty"], 0)
        self.assertTrue(ff["enabled"])

    def test_quarantine_partial_basket_degrade(self):
        """Quarantine CSV lacks full credit basket (no CWB) → partial_basket."""
        payload = parse_flows_csv(QUARANTINE_CSV)
        basket = basket_for("credit")
        degrade = resolve_degrade_mode(payload, "credit", basket)
        self.assertEqual(degrade, "partial_basket")
        ff = build_funds_flows("credit", sidecar=payload, node_cockpit={"node_id": "credit", "confidence": "low"})
        self.assertEqual(ff["flows_meta"]["flows_status"], "partial")
        self.assertTrue(ff["flows_meta"]["flows_degraded"])
        self.assertEqual(ff["flows_meta"]["fallback_reason"], "missing_basket_etfs")

    def test_missing_sidecar_unavailable_meta(self):
        meta = build_flows_sidecar_metadata(None)
        self.assertEqual(meta["flows_status"], "unavailable")
        self.assertIn("missing_wtm_flows_file", meta["warnings"])

    def test_hydrate_credit_ok_with_head_fixture_sidecar(self):
        payload = parse_flows_csv(HEAD_CSV)
        bundle = build_hydration_bundle(flows_sidecar=payload)
        credit = bundle["node_cockpits"]["credit"]["funds_flows"]
        self.assertEqual(credit["flows_meta"]["flows_status"], "ok")
        self.assertEqual(credit["flows_meta"]["flows_source"], "wtm_flows_timeseries")
        self.assertFalse(credit["flows_meta"]["flows_degraded"])
        self.assertEqual(bundle["flows_sidecar"]["flows_status"], "ok")

    def test_ensure_flows_sidecar_via_hydrate_path(self):
        payload = ensure_flows_sidecar(REPO_ROOT)
        self.assertIsNotNone(payload)
        self.assertGreaterEqual(len(payload.get("tickers") or {}), 10)
        bundle = build_hydration_bundle()
        self.assertEqual(
            bundle["node_cockpits"]["credit"]["funds_flows"]["flows_meta"]["flows_status"],
            "ok",
        )

    def test_cli_parse_and_write(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "sidecar.json"
            payload = parse_and_write(HEAD_CSV, out)
            self.assertTrue(out.is_file())
            self.assertGreater(len(payload["tickers"]), 10)


if __name__ == "__main__":
    unittest.main()