"""BUILD 2.2e — raw vendor CSV → WTM observation transform tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.csv_download import stage_file, cmd_init
from whinfell_pipeline.raw_csv_transform import (
    detect_vendor_format,
    is_wtm_observation,
    prepare_staged_csv,
    transform_file,
)
from whinfell_pipeline.staged_csv import SOURCE_BARCHART, SOURCE_KOYFIN, validate_staged_file, StagedFile


class TestRawCsvTransform(unittest.TestCase):
    def test_detect_koyfin_wide(self):
        headers = ["Date", "HYG Close", "IWM Close", "BTCUSD Close"]
        self.assertEqual(detect_vendor_format(headers, "rates_20260628.csv"), "koyfin_wide_timeseries")

    def test_detect_koyfin_return_timeseries(self):
        headers = ["Date", "CN10Y Return", "USDCNH Return", "KHYB Return"]
        self.assertEqual(
            detect_vendor_format(headers, "credit_20260629.csv"),
            "koyfin_return_timeseries",
        )

    def test_transform_koyfin_return_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "credit_20260629_0924.csv"
            path.write_text(
                '"Date","CN10Y Return","USDCNH Return","KHYB Return"\n'
                "06-27-2026,0.0021,-0.0010,0.0033\n"
                "06-30-2026,0.0061,-0.0020,0.0021\n",
                encoding="utf-8",
            )
            result = transform_file(path, source=SOURCE_KOYFIN, dataset="credit")
            self.assertTrue(result.transformed)
            self.assertIn("whinfell_score", path.read_text(encoding="utf-8"))

    def test_detect_barchart_historical(self):
        headers = ["Symbol", "Time", "Open", "High", "Low", "Latest"]
        self.assertEqual(detect_vendor_format(headers, "futures_daily_x.csv"), "barchart_historical")

    def test_detect_barchart_spreads(self):
        headers = ["Leg1", "Leg2", "Type", "Latest", "Time"]
        self.assertEqual(detect_vendor_format(headers, "btc_basis_x.csv"), "barchart_spreads")

    def test_transform_rates_produces_wtm_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rates_20260628_1200.csv"
            path.write_text(
                "Date,HYG Close,IWM Close,SPY Close,BTCUSD Close,LQD Close\n"
                "06-20-2026,75,190,520,95000,105\n"
                "06-27-2026,76,195,530,96000,106\n",
                encoding="utf-8",
            )
            result = transform_file(path, source=SOURCE_KOYFIN, dataset="rates")
            self.assertTrue(result.transformed)
            headers = path.read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("whinfell_score", headers)
            self.assertIn("timestamp", headers)
            self.assertTrue(is_wtm_observation(headers.split(","), SOURCE_KOYFIN))

    def test_transform_barchart_spreads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "btc_basis_20260628.csv"
            path.write_text(
                "Leg1,Leg2,Type,Latest,Time\n"
                "BTM6,BAN6,AE,-232.,2026-06-26\n",
                encoding="utf-8",
            )
            result = transform_file(path, source=SOURCE_BARCHART, dataset="futures_daily")
            self.assertTrue(result.transformed)
            text = path.read_text(encoding="utf-8")
            self.assertIn("basis_spread", text)
            self.assertIn("near_month", text)

    def test_barchart_historical_passthrough_stages_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "drop"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            src = downloads / "futures_daily_20260630_1200.csv"
            src.write_text(
                "Symbol,Time,Open,High,Low,Latest,Volume\n"
                "DXY00,2026-06-30,104.1,104.5,103.9,104.2,1000\n",
                encoding="utf-8",
            )
            cmd_init(staged_root)
            fr = stage_file(src, staged_root, operator="test")
            self.assertEqual(fr.status, "staged", fr.errors)
            text = Path(fr.staged_path).read_text(encoding="utf-8")
            self.assertIn("Symbol", text)
            self.assertIn("Latest", text)

    def test_stage_file_with_raw_vendor(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "drop"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            src = downloads / "rates_20260628_1200.csv"
            src.write_text(
                "Date,HYG Close,IWM Close,BTCUSD Close,LQD Close\n"
                "06-27-2026,76,195,96000,106\n",
                encoding="utf-8",
            )
            cmd_init(staged_root)
            fr = stage_file(src, staged_root, operator="test")
            self.assertEqual(fr.status, "staged", fr.errors)
            dest = Path(fr.staged_path)
            self.assertTrue(dest.exists())
            staged = StagedFile(path=dest, source=SOURCE_KOYFIN, dataset="rates", filename=dest.name)
            val = validate_staged_file(staged)
            self.assertTrue(val.ok, val.errors)


if __name__ == "__main__":
    unittest.main()