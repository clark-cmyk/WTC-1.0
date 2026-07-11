"""Tests for ARCH-1 source_router.route_ingest."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.source_router import extract_barchart_symbols, route_ingest

RATES_WIDE = REPO_ROOT / "staged_raw/quarantine/20260628/rates_20260628_1119.csv"
BTC_BASIS = REPO_ROOT / "staged_raw/quarantine/20260630/130935__futures-spreads-hgq26-06-30-2026.csv"
DAILY_HIST = REPO_ROOT / "staged_raw/quarantine/20260630/112239__btcusd_daily_historical-data-06-30-2026.csv"
GREEKS = REPO_ROOT / "staged_raw/quarantine/20260630/112239__btn26-volatility-greeks-exp-07_31_26-50-strikes-+_--06-30-2026.csv"
OPTIONS = REPO_ROOT / "staged_raw/quarantine/20260630/btv26-options-monthly-options-exp-10_30_26-50-strikes-+_--side-by-side-intraday-06-30-2026.csv"
COCKPIT_BUNDLE_DIR = REPO_ROOT / "whinfell_pipeline/examples"


class TestSourceRouter(unittest.TestCase):
    def test_extract_barchart_symbols_from_spread_filename(self):
        syms = extract_barchart_symbols("futures-spreads-bth27-06-30-2026.csv")
        self.assertIn("BTH27", syms)

    def test_route_koyfin_wide_rates(self):
        if not RATES_WIDE.is_file():
            self.skipTest("rates wide sample missing")
        route = route_ingest(RATES_WIDE)
        self.assertEqual(route.source_class, "koyfin_wide_timeseries")
        self.assertEqual(route.vendor, "koyfin")
        self.assertEqual(route.vendor_format, "koyfin_wide_timeseries")

    def test_route_barchart_curve_spread(self):
        if not BTC_BASIS.is_file():
            self.skipTest("spread sample missing")
        route = route_ingest(BTC_BASIS)
        self.assertIn(route.source_class, ("barchart_curve_history", "barchart_core_history", "barchart_quote_snapshot"))
        self.assertEqual(route.vendor, "barchart")

    def test_route_barchart_daily_historical(self):
        if not DAILY_HIST.is_file():
            self.skipTest("daily historical sample missing")
        route = route_ingest(DAILY_HIST)
        self.assertEqual(route.source_class, "barchart_core_history")
        self.assertEqual(route.vendor, "barchart")
        self.assertEqual(route.vendor_format, "barchart_historical")

    def test_route_barchart_greeks(self):
        if not GREEKS.is_file():
            self.skipTest("greeks sample missing")
        route = route_ingest(GREEKS)
        self.assertEqual(route.source_class, "barchart_core_history")
        self.assertIn(route.vendor_format, ("barchart_volgreeks", "barchart_options"))

    def test_route_barchart_options(self):
        if not OPTIONS.is_file():
            self.skipTest("options sample missing")
        route = route_ingest(OPTIONS)
        self.assertEqual(route.vendor_format, "barchart_options")

    def test_route_result_serializes_meta(self):
        if not RATES_WIDE.is_file():
            self.skipTest("rates wide sample missing")
        route = route_ingest(RATES_WIDE)
        meta = route.to_meta()
        self.assertIn("source_class", meta)
        self.assertIn("vendor_format", meta)


if __name__ == "__main__":
    unittest.main()