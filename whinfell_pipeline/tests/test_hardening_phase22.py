"""Phase 2.2 hardening — all five nodes, healthy + degraded paths, deterministic hydrate."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.flows_parser import parse_flows_csv
from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.node_cockpits import CANONICAL_NODE_IDS

HEAD_CSV = REPO_ROOT / "whinfell_pipeline" / "examples" / "flows" / "WTM-Flows-Global-head.csv"
RV_HORIZONS = ("1m", "3m", "6m", "12m", "3y")


class TestHardeningPhase22(unittest.TestCase):
    def _assert_node_cockpit_healthy(self, cockpit: dict, node_id: str) -> None:
        rv = cockpit["rv_basis"]
        sid = rv.get("active_series_id")
        self.assertTrue(sid, f"{node_id}: missing active_series_id")
        horizons = rv["series"][sid]["horizons"]
        self.assertEqual(set(horizons.keys()), set(RV_HORIZONS), node_id)
        for hz in RV_HORIZONS:
            self.assertIn("percentile", horizons[hz], f"{node_id}/{hz}")
            self.assertIn("quartile", horizons[hz], f"{node_id}/{hz}")
        self.assertNotIn("_degraded", rv)
        ff = cockpit["funds_flows"]["flows_meta"]
        self.assertIn(ff["flows_status"], ("ok", "partial", "fallback_1d", "unavailable"))
        self.assertIn("flows_degraded", ff)
        self.assertIn("flows_source", ff)

    def test_all_five_nodes_healthy_hydrate(self):
        payload = parse_flows_csv(HEAD_CSV)
        bundle = build_hydration_bundle(flows_sidecar=payload)
        self.assertEqual(set(bundle["node_cockpits"].keys()), set(CANONICAL_NODE_IDS))
        for node_id in CANONICAL_NODE_IDS:
            self._assert_node_cockpit_healthy(bundle["node_cockpits"][node_id], node_id)
        credit = bundle["node_cockpits"]["credit"]["funds_flows"]["flows_meta"]
        self.assertEqual(credit["flows_status"], "ok")
        self.assertFalse(credit["flows_degraded"])

    def test_all_five_nodes_degraded_without_sidecar(self):
        with mock.patch("whinfell_pipeline.hydrate.ensure_flows_sidecar", return_value=None):
            bundle = build_hydration_bundle()
        for node_id in CANONICAL_NODE_IDS:
            ff = bundle["node_cockpits"][node_id]["funds_flows"]
            self.assertEqual(ff["flows_meta"]["flows_status"], "unavailable")
            self.assertTrue(ff["flows_meta"]["flows_degraded"])
            self.assertFalse(ff["enabled"])
            self.assertEqual(ff["aggregate"]["verdict"], "neutral")

    def test_double_hydrate_cli_identical(self):
        with tempfile.TemporaryDirectory() as td:
            out1 = Path(td) / "a.json"
            out2 = Path(td) / "b.json"
            cmd = [sys.executable, "-m", "whinfell_pipeline.hydrate", "-o"]
            for out in (out1, out2):
                proc = subprocess.run([*cmd, str(out)], cwd=REPO_ROOT, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            b1 = json.loads(out1.read_text(encoding="utf-8"))
            b2 = json.loads(out2.read_text(encoding="utf-8"))
            self.assertEqual(b1, b2)

    def test_flows_health_present_on_bundle(self):
        bundle = build_hydration_bundle()
        self.assertIn("flows_health", bundle)
        self.assertIn("flows_sidecar", bundle)
        self.assertIn(bundle["flows_sidecar"]["flows_status"], ("ok", "partial", "unavailable", "fallback_1d"))


if __name__ == "__main__":
    unittest.main()