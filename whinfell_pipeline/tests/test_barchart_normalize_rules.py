"""Verify Barchart native-export normalize rules cover quarantine patterns."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.batch_collect import infer_canonical_name


class TestBarchartNormalizeRules(unittest.TestCase):
    def test_quarantine_coverage_majority(self):
        qdirs = list((REPO_ROOT / "staged_raw/quarantine").glob("*/"))
        matched = 0
        total = 0
        for qd in qdirs:
            for path in qd.glob("*.csv"):
                total += 1
                if infer_canonical_name(path.name, path):
                    matched += 1
        self.assertGreater(total, 100)
        pct = matched / total * 100
        self.assertGreaterEqual(pct, 55.0, f"only {pct:.1f}% quarantine files have normalize rules")

    def test_daily_historical_maps_to_futures_daily(self):
        sample = REPO_ROOT / "staged_raw/quarantine/20260630/112239__btcusd_daily_historical-data-06-30-2026.csv"
        if not sample.is_file():
            self.skipTest("sample missing")
        dest = infer_canonical_name(sample.name, sample)
        self.assertTrue(dest)
        self.assertTrue(dest.startswith("futures_daily_"))

    def test_greeks_maps_to_greeks_dataset(self):
        sample = REPO_ROOT / "staged_raw/quarantine/20260630/112239__btn26-volatility-greeks-exp-07_31_26-50-strikes-+_--06-30-2026.csv"
        if not sample.is_file():
            self.skipTest("sample missing")
        dest = infer_canonical_name(sample.name, sample)
        self.assertTrue(dest)
        self.assertTrue(dest.startswith("greeks_"))

    def test_options_maps_to_options_dataset(self):
        sample = REPO_ROOT / "staged_raw/quarantine/20260630/btv26-options-monthly-options-exp-10_30_26-50-strikes-+_--side-by-side-intraday-06-30-2026.csv"
        if not sample.is_file():
            self.skipTest("sample missing")
        dest = infer_canonical_name(sample.name, sample)
        self.assertTrue(dest)
        self.assertTrue(dest.startswith("options_"))


if __name__ == "__main__":
    unittest.main()