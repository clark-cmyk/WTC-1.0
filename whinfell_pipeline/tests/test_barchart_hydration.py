"""Barchart-only hydration — classify, normalize, ingest, manifest tests."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.barchart_hydration import (  # noqa: E402
    SupplementSource,
    classify_bucket,
    default_supplement_dirs,
    discover_local_supplements,
    fetch_barchart_daily_csv,
    hydrate_from_csv_body,
    hydrate_symbol,
    ingest_historical_csv,
    ingest_watchlist_snapshot,
    instrument_class_for_symbol,
    load_barchart_api_key,
    normalize_barchart_symbol,
    normalize_history_rows,
    parse_contract_meta,
    parse_spread_meta,
    recorded_examples_dir,
    run_barchart_hydration,
)
from whinfell_pipeline.data_dictionary import (  # noqa: E402
    barchart_all_approved_symbols,
    barchart_core_symbols,
    barchart_curve_symbols,
    barchart_spread_symbols,
)

RECORDED = recorded_examples_dir()
WATCHLIST_SRC = Path.home() / "Downloads/whinfell_drop/watchlist-wtm-canonical-universe-intraday-06-28-2026.csv"


class TestBarchartClassification(unittest.TestCase):
    def test_core_bucket(self):
        self.assertEqual(classify_bucket("^XRPUSD"), "core")

    def test_approved_count(self):
        self.assertEqual(len(barchart_core_symbols()), 16)
        self.assertEqual(len(barchart_curve_symbols()), 57)
        self.assertEqual(len(barchart_spread_symbols()), 5)
        self.assertEqual(len(barchart_all_approved_symbols()), 78)


class TestBarchartNormalization(unittest.TestCase):
    def test_core_canonical(self):
        n = normalize_barchart_symbol("^BTCUSD")
        self.assertEqual(n["canonical_id"], "btc_spot_usd")
        self.assertEqual(n["instrument_class"], "crypto_spot")

    def test_contract_meta(self):
        n = normalize_barchart_symbol("GCN26", group_hint="metals_curves")
        self.assertEqual(n["contract_meta"]["contract_type_bucket"], "metals-curves")

    def test_spread_meta(self):
        n = normalize_barchart_symbol("_S_BF_ZBU6_ZBZ6_ZBH7")
        self.assertEqual(n["instrument_class"], "spread")
        self.assertEqual(n["pricing_mode"], "derived_or_structured")


class TestRecordedIngest(unittest.TestCase):
    def test_ingest_recorded_core(self):
        record, outcome = ingest_historical_csv(RECORDED / "xrpusd_gethistory_daily.csv", "^XRPUSD")
        self.assertEqual(outcome.status, "ok")
        self.assertEqual(record["canonical_id"], "xrp_spot_usd")
        self.assertEqual(record["spread_meta"], {})

    def test_ingest_recorded_curve(self):
        record, outcome = ingest_historical_csv(RECORDED / "gcn26_daily-nearby_historical.csv", "GCN26")
        self.assertEqual(outcome.status, "ok")
        self.assertEqual(record["instrument_class"], "futures")

    def test_ingest_recorded_spread(self):
        sym = "_S_BF_ZBU6_ZBZ6_ZBH7"
        record, outcome = ingest_historical_csv(
            RECORDED / "s_bf_zbu6_zbz6_zbh7_gethistory_daily.csv", sym
        )
        self.assertEqual(outcome.status, "ok")
        self.assertEqual(record["spread_meta"]["spread_kind"], "BF")


class TestWatchlistSupplement(unittest.TestCase):
    def test_ingest_watchlist_core_and_spread(self):
        if not WATCHLIST_SRC.exists():
            self.skipTest("desk watchlist export missing")
        core, oc = ingest_watchlist_snapshot(WATCHLIST_SRC, "^XRPUSD")
        self.assertEqual(oc.status, "ok")
        self.assertEqual(core["fetch_mode"], "watchlist_snapshot_supplement")
        self.assertEqual(core["points"][0]["date"], "2026-06-28")
        spread, os_ = ingest_watchlist_snapshot(WATCHLIST_SRC, "_S_BF_ZBU6_ZBZ6_ZBH7")
        self.assertEqual(os_.status, "ok")
        self.assertEqual(spread["instrument_class"], "spread")

    def test_discover_prefers_history_over_watchlist(self):
        if not WATCHLIST_SRC.exists():
            self.skipTest("desk watchlist export missing")
        found = discover_local_supplements(default_supplement_dirs())
        self.assertEqual(found["BTN26"].fetch_mode, "local_csv_supplement")
        self.assertGreater(found["BTN26"].priority, found["^ETHUSD"].priority)
        btc = found["^BTCUSD"]
        self.assertIn(btc.fetch_mode, ("local_csv_supplement", "watchlist_snapshot_supplement"))


class TestHydrateFromCsvBody(unittest.TestCase):
    def test_api_shape(self):
        body = b"Date,Open,High,Low,Close,Volume\n2026-06-28,1,2,0.5,1.5,100\n"
        record, outcome = hydrate_from_csv_body("^BTCUSD", body, fetch_mode="api")
        self.assertEqual(outcome.status, "ok")
        self.assertEqual(record["points"][0]["close"], 1.5)


class TestRunBarchartHydration(unittest.TestCase):
    def test_run_isolated_no_supplements_fails_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = run_barchart_hydration(
                api_key="",
                output_dir=out,
                supplement_dirs=[],
                verbose=False,
            )
            self.assertEqual(result["manifest"]["symbol_count_failed"], 78)

    def test_run_with_watchlist_dir_covers_buckets(self):
        if not WATCHLIST_SRC.exists():
            self.skipTest("desk watchlist export missing")
        with tempfile.TemporaryDirectory() as tmp:
            drop = Path(tmp)
            shutil.copy(WATCHLIST_SRC, drop / WATCHLIST_SRC.name)
            out = Path(tmp) / "out"
            result = run_barchart_hydration(
                api_key="",
                output_dir=out,
                supplement_dirs=[drop],
                verbose=False,
            )
            self.assertEqual(result["counts"]["approved"], 78)
            self.assertEqual(result["counts"]["core_ok"], 16)
            self.assertEqual(result["counts"]["curve_ok"], 57)
            self.assertEqual(result["counts"]["spread_ok"], 5)
            core = json.loads((out / "barchart_core_history.json").read_text(encoding="utf-8"))
            self.assertEqual(core["records"][0]["fetch_mode"], "watchlist_snapshot_supplement")

    def test_api_path_via_hydrate_symbol_mock(self):
        body = b"Date,Open,High,Low,Close,Volume\n2026-06-28,1,2,0.5,1.5,100\n"
        with mock.patch(
            "whinfell_pipeline.barchart_hydration.fetch_barchart_daily_csv",
            return_value=body,
        ):
            record, outcome = hydrate_symbol("^BTCUSD", api_key="test-key", file_only=False)
        self.assertEqual(outcome.status, "ok")
        self.assertEqual(record["fetch_mode"], "api")


class TestLiveApiOptional(unittest.TestCase):
    def test_live_api_single_symbol_when_key_present(self):
        key = load_barchart_api_key()
        if not key:
            self.skipTest("BARCHART_API_KEY not configured")
        try:
            body = fetch_barchart_daily_csv("^BTCUSD", api_key=key, start_date="20250601", end_date="20250628")
        except Exception as exc:
            self.skipTest(f"Barchart API unavailable: {exc}")
        record, outcome = hydrate_from_csv_body("^BTCUSD", body, fetch_mode="api")
        self.assertEqual(outcome.status, "ok")
        self.assertGreater(record["row_count"], 0)


class TestInstrumentClassHelper(unittest.TestCase):
    def test_curve_defaults_futures(self):
        norm = normalize_barchart_symbol("CLQ26")
        self.assertEqual(instrument_class_for_symbol(norm, "curve"), "futures")


if __name__ == "__main__":
    unittest.main()