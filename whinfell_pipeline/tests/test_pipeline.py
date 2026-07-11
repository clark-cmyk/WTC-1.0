"""Tests for whinfell_pipeline adapters, normalize, and ingest."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.adapters.comet_collector import CometCollectorAdapter
from whinfell_pipeline.adapters.koyfin_adapter import KoyfinAdapter
from whinfell_pipeline.adapters.barchart_adapter import BarchartAdapter
from whinfell_pipeline.adapters.transmission_control import TransmissionControlAdapter
from whinfell_pipeline.decision_export import write_wtm_export_v21
from whinfell_pipeline.global_track.parser import parse_wtm_export_text
from whinfell_pipeline.global_track.storage import read_observations
from whinfell_pipeline.ingest import ingest_file
from whinfell_pipeline.lineage import compute_lineage_hash
from whinfell_pipeline.version import COMET_COLLECTOR_VERSION, DECISION_EXPORT_FORMAT


EXAMPLES = REPO_ROOT / "whinfell_pipeline" / "examples"


class TestCometCollectorAdapter(unittest.TestCase):
    def test_koyfin_global_envelope(self):
        raw = json.loads((EXAMPLES / "comet_koyfin_global.json").read_text())
        result = CometCollectorAdapter().parse(raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.records[0].track_id, "global")
        self.assertTrue(result.lineage_hash.startswith("sha256:"))
        self.assertEqual(result.records[0].payload["whinfell_score"], 58)

    def test_koyfin_china_envelope(self):
        raw = json.loads((EXAMPLES / "comet_koyfin_china.json").read_text())
        result = CometCollectorAdapter().parse(raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.records[0].track_id, "china_policy")

    def test_barchart_execution_envelope(self):
        raw = json.loads((EXAMPLES / "comet_barchart_btc.json").read_text())
        result = CometCollectorAdapter().parse(raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.records[0].track_id, "execution")
        self.assertEqual(result.records[0].payload["basis_spread"], "1.25")


class TestKoyfinBarchartDirect(unittest.TestCase):
    def test_koyfin_china_sample(self):
        raw = json.loads((REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json").read_text())
        result = KoyfinAdapter().parse(raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.records[0].track_id, "china_policy")

    def test_barchart_execution_direct(self):
        result = BarchartAdapter().parse(
            {"source": "barchart", "near_month": "Aug", "basis_spread": "0.9"}
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.records[0].track_id, "execution")


class TestDecisionExport(unittest.TestCase):
    def test_wtm_export_v21_includes_sq3(self):
        block = write_wtm_export_v21(
            {"whinfell_score": 58, "transmission_state": "stressed", "regime_tag": "Fragile Risk-On"},
            china_data={"sq3_score": 55, "sq3_band": "Mixed / Fragile", "policy_strength": 74, "state_impulse_score": 38, "growth_impulse_score": 61},
            gross_total_pct=35.0,
            posture="light",
        )
        self.assertIn(DECISION_EXPORT_FORMAT, block)
        self.assertIn("SQ3 Score: 55", block)
        parsed = parse_wtm_export_text(block)
        self.assertEqual(parsed.whinfell_score, 58)
        self.assertEqual(parsed.sq3_score, 55)


class TestIngestPipeline(unittest.TestCase):
    def test_ingest_comet_koyfin_global_to_parquet(self):
        with tempfile.TemporaryDirectory() as tmp:
            g_out = Path(tmp) / "global.parquet"
            c_out = Path(tmp) / "china.parquet"
            export = Path(tmp) / "decision.txt"
            result = ingest_file(
                EXAMPLES / "comet_koyfin_global.json",
                global_output=g_out,
                china_output=c_out,
                append=False,
                write_export=export,
            )
            self.assertEqual(result.adapter_id, "comet_collector")
            self.assertEqual(result.global_written, 1)
            self.assertTrue(g_out.exists())
            rows = pq.read_table(g_out)
            self.assertEqual(rows.num_rows, 1)
            obs = read_observations(g_out)
            self.assertEqual(obs[0].whinfell_score, 58)
            self.assertTrue(export.exists())

    def test_transmission_control_bundle(self):
        bundle = {
            "bundle_version": "1.0.0",
            "snapshot_id": "snap_test_01",
            "lineage_hash": compute_lineage_hash({"test": 1}),
            "validation_status": "parsed",
            "as_of": "2026-06-27T16:00:00Z",
            "source": "transmission_control",
            "global": {
                "observation_id": "global-tc-01",
                "whinfell_score": 62,
                "transmission_state": "stressed",
                "regime_tag": "Fragile Risk-On",
                "gate_status": "Tight Risk Band",
            },
            "china": {
                "policy_strength": 74,
                "state_impulse_score": 38,
                "growth_impulse_score": 61,
                "sq3_score": 55,
                "sq3_band": "Mixed / Fragile",
            },
            "execution": {"basis_spread": "1.1", "near_month": "Jul"},
            "wtm_export_v21": "--- WTM EXPORT v2.1 ---\nWhinfell Score: 62\n",
        }
        adapter = TransmissionControlAdapter()
        self.assertTrue(adapter.can_handle(bundle))
        result = adapter.parse(bundle)
        self.assertEqual(len(result.records), 3)


if __name__ == "__main__":
    unittest.main()