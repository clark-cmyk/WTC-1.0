"""Tests for China Policy track models, schema, storage, and ingestion."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from china_policy_track.data_parser import parse_input, parse_perplexity_text
from china_policy_track.ingest import ingest_payload
from china_policy_track.models import (
    GrowthMarketImpulse,
    PolicyHierarchyStrength,
    StateControlImpulse,
    build_observation_from_dimensions,
)
from china_policy_track.schema import china_policy_parquet_schema, schema_metadata_dict
from china_policy_track.storage import (
    default_parquet_path,
    read_observations,
    write_observations,
)
from china_policy_track.version import CHINA_DATA_ROOT, PARQUET_FILENAME, SCHEMA_VERSION, TRACK_ID


class TestChinaPolicyModels(unittest.TestCase):
    def test_three_dimensions_from_mapping(self):
        policy = PolicyHierarchyStrength.from_mapping(
            {"hierarchy_level": "central", "policy_strength": 72, "dominant_theme": "fiscal"}
        )
        state = StateControlImpulse.from_mapping(
            {"impulse_score": 15, "regulatory_direction": "neutral", "state_intervention_level": "medium"}
        )
        growth = GrowthMarketImpulse.from_mapping(
            {"growth_impulse_score": 58, "market_sentiment": "mixed", "liquidity_impulse": "stable"}
        )
        self.assertEqual(policy.hierarchy_level, "central")
        self.assertEqual(state.impulse_score, 15)
        self.assertEqual(growth.market_sentiment, "mixed")

    def test_build_observation_roundtrip_dict(self):
        obs = build_observation_from_dimensions(
            observation_id="test-001",
            as_of=datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
            source="manual",
            policy={"policy_strength": 80, "hierarchy_level": "central", "dominant_theme": "x"},
            state_control={"impulse_score": 10, "regulatory_direction": "easing", "state_intervention_level": "low"},
            growth={"growth_impulse_score": 70, "market_sentiment": "constructive", "liquidity_impulse": "expanding"},
        )
        d = obs.to_dict()
        self.assertEqual(d["schema_version"], SCHEMA_VERSION)
        self.assertEqual(d["policy_hierarchy_strength"]["policy_strength"], 80)


class TestChinaPolicyParquet(unittest.TestCase):
    def test_default_parquet_path_layout(self):
        path = default_parquet_path(REPO_ROOT)
        self.assertEqual(path.name, PARQUET_FILENAME)
        self.assertIn(CHINA_DATA_ROOT, str(path))
        self.assertTrue(str(path).endswith("data/china_policy/v1/china_policy_observations.parquet"))

    def test_write_read_roundtrip(self):
        obs = build_observation_from_dimensions(
            observation_id="pq-001",
            as_of=datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
            source="manual",
            policy={"policy_strength": 65, "hierarchy_level": "mixed", "dominant_theme": "industrial"},
            state_control={"impulse_score": 5, "regulatory_direction": "neutral", "state_intervention_level": "medium"},
            growth={"growth_impulse_score": 52, "market_sentiment": "mixed", "liquidity_impulse": "stable"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "china_policy_observations.parquet"
            write_observations([obs], path, append=False)
            back = read_observations(path)
            self.assertEqual(len(back), 1)
            self.assertEqual(back[0].observation_id, "pq-001")
            self.assertEqual(back[0].policy_hierarchy_strength.policy_strength, 65)

    def test_schema_version_embedded(self):
        sch = china_policy_parquet_schema()
        meta = schema_metadata_dict()
        self.assertEqual(meta["schema_version"], SCHEMA_VERSION)
        self.assertEqual(meta["track_id"], TRACK_ID)
        self.assertIn(b"schema_version", sch.metadata)


class TestChinaPolicyIngestion(unittest.TestCase):
    def test_parse_perplexity_example(self):
        text = (REPO_ROOT / "china_policy_track/examples/sample_perplexity_export.txt").read_text()
        obs = parse_perplexity_text(text)
        self.assertEqual(obs.source, "perplexity")
        self.assertEqual(obs.policy_hierarchy_strength.policy_strength, 74)
        self.assertEqual(obs.state_control_impulse.regulatory_direction, "tightening")

    def test_parse_koyfin_json_example(self):
        raw = json.loads(
            (REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json").read_text()
        )
        obs = parse_input(raw)
        self.assertEqual(obs.source, "koyfin")
        self.assertEqual(obs.growth_market_impulse.market_sentiment, "constructive")

    def test_ingest_cli_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "china_policy_observations.parquet"
            for inp in [
                REPO_ROOT / "china_policy_track/examples/sample_perplexity_export.txt",
                REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json",
            ]:
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "china_policy_track.ingest",
                        "--input",
                        str(inp),
                        "--output",
                        str(out),
                    ],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("china_policy_ingest_ok", proc.stdout)
            table = pq.read_table(out)
            self.assertEqual(table.num_rows, 2)
            self.assertTrue(all(t == TRACK_ID for t in table.column("track_id").to_pylist()))

    def test_ingest_cli_default_path(self):
        """CLI without --output writes to data/china_policy/v1/ (isolated from data/global/)."""
        out = default_parquet_path(REPO_ROOT)
        if out.exists():
            out.unlink()
        global_stub = REPO_ROOT / "data/global/v1/global_observations.parquet"
        global_mtime = global_stub.stat().st_mtime if global_stub.exists() else None

        inputs = [
            REPO_ROOT / "china_policy_track/examples/sample_perplexity_export.txt",
            REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json",
        ]
        for i, inp in enumerate(inputs):
            cmd = [
                sys.executable,
                "-m",
                "china_policy_track.ingest",
                "--input",
                str(inp),
            ]
            if i == 0:
                cmd.append("--no-append")
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(str(out), proc.stdout)

        self.assertTrue(out.exists())
        self.assertEqual(len(read_observations(out)), 2)
        if global_mtime is not None:
            self.assertEqual(global_stub.stat().st_mtime, global_mtime)


if __name__ == "__main__":
    unittest.main()