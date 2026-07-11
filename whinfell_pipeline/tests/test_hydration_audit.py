"""Tests for field-by-field hydration audit."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.hydration_audit import build_hydration_audit, write_hydration_log


class TestHydrationAudit(unittest.TestCase):
    def test_audit_embedded_in_bundle(self):
        bundle = build_hydration_bundle()
        self.assertIn("hydration_audit", bundle)
        audit = bundle["hydration_audit"]
        self.assertEqual(audit["audit_version"], "1.0.0")
        self.assertIn("summary", audit)
        self.assertGreater(audit["summary"]["required_fields"], 10)
        self.assertIn("fields", audit)
        paths = {r["bundle_path"] for r in audit["fields"]}
        self.assertIn("global.whinfell_score", paths)
        self.assertIn("node_cockpits.credit.rv_basis", paths)

    def test_credit_rv_documented_as_partial_not_failure(self):
        bundle = build_hydration_bundle()
        credit = bundle["hydration_audit"]["nodes"]["credit"]
        self.assertGreaterEqual(credit["rv_horizon_count"], 5)
        self.assertEqual(credit["signals_status"], "partial")
        comp_row = next(
            r for r in bundle["hydration_audit"]["fields"]
            if r["field"] == "credit.component_inputs"
        )
        self.assertEqual(comp_row["status"], "partial")
        self.assertIn("intentionally empty", comp_row["notes"])

    def test_write_hydration_log(self):
        bundle = build_hydration_bundle()
        log_path = REPO_ROOT / "data" / "hydration" / "_test_hydration_log.json"
        try:
            audit = write_hydration_log(bundle, log_path)
            self.assertTrue(log_path.is_file())
            self.assertEqual(audit["snapshot_id"], bundle["snapshot_id"])
        finally:
            if log_path.exists():
                log_path.unlink()


if __name__ == "__main__":
    unittest.main()