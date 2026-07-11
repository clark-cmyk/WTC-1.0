"""ARCH-1 M3 — ingest provenance aggregation tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.ingest_provenance import collect_staged_ingest_provenance, map_output_kind


class TestIngestProvenance(unittest.TestCase):
    def test_map_output_kind_snapshot(self):
        self.assertEqual(
            map_output_kind(["snapshot_validation", "universe_membership"]),
            "snapshot",
        )

    def test_map_output_kind_historical(self):
        self.assertEqual(map_output_kind(["historical_timeseries"]), "historical_timeseries")

    def test_collect_from_staged_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_dir = root / "source=koyfin" / "dataset=credit"
            meta_dir.mkdir(parents=True)
            now = datetime.now(timezone.utc).isoformat()
            payload = {
                "status": "staged",
                "staged_at": now,
                "filename": "credit_20260630_1200.csv",
                "dataset": "credit",
                "source": "koyfin",
                "sha256": "abc",
                "route": {
                    "source_class": "koyfin_snapshot_csv",
                    "vendor": "koyfin",
                    "output_kinds": ["snapshot_validation", "universe_membership"],
                    "canonical_assets": ["btc_spot_usd"],
                },
            }
            (meta_dir / "credit_20260630_1200.csv.meta.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            result = collect_staged_ingest_provenance(root, window_hours=48)
            self.assertEqual(result["staged_count"], 1)
            self.assertEqual(result["primary_output_kind"], "snapshot")
            self.assertEqual(result["entries"][0]["output_kind"], "snapshot")

    def test_hydration_bundle_includes_ingest_provenance(self):
        bundle = build_hydration_bundle()
        self.assertIn("ingest_provenance", bundle)
        prov = bundle["ingest_provenance"]
        self.assertIn("staged_count", prov)
        self.assertIn("primary_output_kind", prov)
        block = bundle.get("wtm_export_v22") or ""
        if prov.get("staged_count", 0) > 0:
            self.assertIn("Output Kind:", block)


if __name__ == "__main__":
    unittest.main()