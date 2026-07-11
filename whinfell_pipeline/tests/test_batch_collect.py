"""Batch CSV collection tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.batch_collect import (  # noqa: E402
    build_collection_plan,
    check_batch_ready,
    infer_canonical_name,
    is_canonical_name,
    load_desk_urls,
    load_manifest,
    normalize_drop_dir,
    resolve_batch_url,
)


class TestBatchCollectNormalize(unittest.TestCase):
    def test_infer_historical(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "btm26_daily-nearby_historical-data-06-28-2026.csv"
            path.write_text("Symbol,Time,Latest\n", encoding="utf-8")
            name = infer_canonical_name(path.name, path)
            self.assertIsNotNone(name)
            self.assertTrue(name.startswith("futures_daily_"))

    def test_infer_intraday(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bitcoin-futures-prices-intraday-06-28-2026.csv"
            path.write_text("Contract,Time,Latest\n", encoding="utf-8")
            name = infer_canonical_name(path.name, path)
            self.assertEqual(name.split("_")[0:2], ["futures", "intraday"])

    def test_normalize_renames(self):
        with tempfile.TemporaryDirectory() as tmp:
            drop = Path(tmp)
            src = drop / "koyfin_2026-06-28.csv"
            src.write_text("Date,BTCUSD Close\n", encoding="utf-8")
            result = normalize_drop_dir(drop)
            self.assertEqual(result.renamed, 1)
            self.assertTrue(any(p.name.startswith("rates_") for p in drop.glob("*.csv")))

    def test_skip_canonical(self):
        self.assertTrue(is_canonical_name("rates_20260628_1119.csv"))
        self.assertFalse(is_canonical_name("koyfin_2026-06-28.csv"))


class TestBatchCollectPlan(unittest.TestCase):
    def test_plan_has_batch_steps(self):
        manifest = load_manifest()
        plan = build_collection_plan(manifest)
        self.assertEqual(plan["mode"], "batch")
        self.assertGreaterEqual(plan["total_exports_required"], 5)
        self.assertIn("steps", plan)
        self.assertIn("optional_steps", plan)
        self.assertTrue(all("url" in s for s in plan["steps"]))
        opt_ids = [s["id"] for s in plan["optional_steps"]]
        self.assertIn("koyfin_crypto_price", opt_ids)
        core_batch = next(e for e in manifest["batch_exports"] if e["id"] == "barchart_core_batch")
        self.assertEqual(core_batch["symbols_ref"], "barchart_core")
        self.assertTrue(core_batch.get("optional"))

    def test_desk_urls_wire_barchart(self):
        manifest = load_manifest()
        desk = load_desk_urls()
        self.assertTrue(desk.get("barchart"))
        intraday = next(e for e in manifest["batch_exports"] if e["id"] == "barchart_futures_intraday")
        url = resolve_batch_url(intraday)
        self.assertIn("barchart.com", url)
        self.assertNotIn("${", url)

    def test_plan_includes_navigate_hints(self):
        plan = build_collection_plan()
        barchart_steps = [s for s in plan["steps"] if s.get("source") == "barchart"]
        self.assertTrue(any(s.get("navigate") for s in barchart_steps))

    def test_plan_json_serializable(self):
        plan = build_collection_plan()
        json.dumps(plan)


class TestBatchCollectPipeline(unittest.TestCase):
    def test_run_pipeline_daily_argv(self):
        from unittest.mock import patch
        from whinfell_pipeline.batch_collect import run_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            drop = Path(tmp)
            (drop / "rates_20260628_1119.csv").write_text(
                "observation_id,timestamp,whinfell_score,regime_tag,key_observation\n"
                "g-1,2026-06-28T11:00:00,58,stressed,ok\n",
                encoding="utf-8",
            )
            with patch("whinfell_pipeline.batch_collect.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                run_pipeline(drop, operator="desk", window="today")
            argv = mock_run.call_args[0][0]
            self.assertEqual(argv[2], "daily")
            self.assertNotIn("stage", argv[2:5])


class TestBarchartOnlyCommand(unittest.TestCase):
    def test_cmd_barchart_only_writes_outputs(self):
        import argparse
        from io import StringIO
        from unittest.mock import patch

        from whinfell_pipeline.batch_collect import cmd_barchart_only

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            args = argparse.Namespace(output_dir=str(out), start_date="20250101", api_key="")
            buf = StringIO()
            with patch("sys.stdout", buf):
                code = cmd_barchart_only(args)
            self.assertEqual(code, 0)
            output = buf.getvalue()
            self.assertIn("barchart_hydration_ok", output)
            self.assertIn("source=barchart_only", output)
            self.assertNotIn("koyfin", output.lower())
            self.assertTrue((out / "barchart_run_manifest.json").exists())
            manifest = json.loads((out / "barchart_run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["symbol_count_approved"], 78)
            self.assertEqual(len(manifest["outcomes"]), 78)
            self.assertIn("barchart_hydration_begin", output)
            self.assertEqual(manifest["symbol_count_ok"], 78)
            self.assertIn("local_supplements", manifest)


class TestBatchCollectReady(unittest.TestCase):
    def test_ready_when_canonical_present(self):
        manifest = load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            drop = Path(tmp)
            (drop / "rates_20260628_1119.csv").write_text("x\n", encoding="utf-8")
            (drop / "futures_intraday_20260628_1015.csv").write_text("x\n", encoding="utf-8")
            (drop / "futures_daily_20260628_1015.csv").write_text("x\n", encoding="utf-8")
            status = check_batch_ready(drop, manifest)
            self.assertTrue(status.ready)


if __name__ == "__main__":
    unittest.main()