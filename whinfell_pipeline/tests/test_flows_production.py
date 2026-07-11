"""Production-path tests — quarantine-first CSV resolution and basket health."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.flows_parser import (
    _canonical_flows_csv_paths,
    assess_flows_basket_health,
    ensure_flows_sidecar,
    find_latest_quarantine_flows_csv,
    parse_flows_csv,
    write_flows_sidecar,
)
from whinfell_pipeline.funds_flows import build_flows_sidecar_metadata
from whinfell_pipeline.hydrate import build_hydration_bundle

QUARANTINE_CSV = REPO_ROOT / "staged_raw" / "quarantine" / "20260629" / "WTM-Flows-Global.csv"
HEAD_CSV = REPO_ROOT / "whinfell_pipeline" / "examples" / "flows" / "WTM-Flows-Global-head.csv"


class TestFlowsProduction(unittest.TestCase):
    def test_find_latest_quarantine_flows_csv(self):
        self.assertTrue(QUARANTINE_CSV.is_file(), f"missing fixture {QUARANTINE_CSV}")
        latest = find_latest_quarantine_flows_csv(REPO_ROOT)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.name, "WTM-Flows-Global.csv")
        self.assertIn("quarantine", str(latest))

    def test_canonical_paths_quarantine_before_head_fixture(self):
        paths = _canonical_flows_csv_paths(REPO_ROOT)
        self.assertGreaterEqual(len(paths), 2)
        self.assertIn(QUARANTINE_CSV, paths)
        self.assertIn(HEAD_CSV, paths)
        self.assertLess(paths.index(QUARANTINE_CSV), paths.index(HEAD_CSV))

    def test_assess_basket_health_head_ok(self):
        payload = parse_flows_csv(HEAD_CSV)
        health = assess_flows_basket_health(payload, node_id="credit")
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["missing_tickers"], [])
        self.assertNotIn("partial_basket_coverage", health["warnings"])

    def test_assess_basket_health_quarantine_partial(self):
        payload = parse_flows_csv(QUARANTINE_CSV)
        health = assess_flows_basket_health(payload, node_id="credit")
        self.assertEqual(health["status"], "partial")
        self.assertIn("CWB", health["missing_tickers"])
        self.assertIn("partial_basket_coverage", health["warnings"])

    def test_build_flows_sidecar_metadata_includes_basket_warnings(self):
        payload = parse_flows_csv(QUARANTINE_CSV)
        meta = build_flows_sidecar_metadata(payload, node_id="credit")
        self.assertEqual(meta["flows_status"], "partial")
        self.assertIn("partial_basket_coverage", meta["warnings"])
        self.assertIn("basket_health", meta)
        self.assertEqual(meta["basket_health"]["status"], "partial")

    def test_hydrate_bundle_includes_flows_health(self):
        payload = parse_flows_csv(QUARANTINE_CSV)
        bundle = build_hydration_bundle(flows_sidecar=payload)
        self.assertIn("flows_health", bundle)
        self.assertEqual(bundle["flows_health"]["status"], "partial")
        self.assertEqual(bundle["flows_sidecar"]["flows_status"], "partial")

    def test_ensure_flows_sidecar_refreshes_when_quarantine_newer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            quarantine_dir = root / "staged_raw" / "quarantine" / "20260629"
            quarantine_dir.mkdir(parents=True)
            quarantine_csv = quarantine_dir / "WTM-Flows-Global.csv"
            quarantine_csv.write_text(QUARANTINE_CSV.read_text(encoding="utf-8"), encoding="utf-8")

            head_dir = root / "whinfell_pipeline" / "examples" / "flows"
            head_dir.mkdir(parents=True)
            head_fixture = head_dir / "WTM-Flows-Global-head.csv"
            head_fixture.write_text(HEAD_CSV.read_text(encoding="utf-8"), encoding="utf-8")

            sidecar_path = root / "data" / "flows" / "v1" / "latest_flows.json"
            stale = parse_flows_csv(head_fixture)
            write_flows_sidecar(stale, sidecar_path)
            old_mtime = time.time() - 3600
            import os

            os.utime(sidecar_path, (old_mtime, old_mtime))
            os.utime(quarantine_csv, (time.time(), time.time()))

            refreshed = ensure_flows_sidecar(root)
            self.assertIsNotNone(refreshed)
            loaded = json.loads(sidecar_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["source_file"], "WTM-Flows-Global.csv")
            health = assess_flows_basket_health(loaded, node_id="credit")
            self.assertEqual(health["status"], "partial")

    def test_ensure_flows_sidecar_keeps_healthy_sidecar_without_newer_quarantine(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            head_dir = root / "whinfell_pipeline" / "examples" / "flows"
            head_dir.mkdir(parents=True)
            head_fixture = head_dir / "WTM-Flows-Global-head.csv"
            head_fixture.write_text(HEAD_CSV.read_text(encoding="utf-8"), encoding="utf-8")

            sidecar_path = root / "data" / "flows" / "v1" / "latest_flows.json"
            healthy = parse_flows_csv(head_fixture)
            write_flows_sidecar(healthy, sidecar_path)

            with mock.patch(
                "whinfell_pipeline.flows_parser.find_latest_quarantine_flows_csv",
                return_value=None,
            ):
                kept = ensure_flows_sidecar(root)

            self.assertIsNotNone(kept)
            self.assertEqual(kept["source_file"], "WTM-Flows-Global-head.csv")


if __name__ == "__main__":
    unittest.main()