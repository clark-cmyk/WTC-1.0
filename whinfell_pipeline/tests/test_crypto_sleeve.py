"""Crypto sleeve — first-class BTC/ETH/XRP/SOL support tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.crypto_sleeve import (
    ASSET_TICKER_MAP,
    detect_crypto_source_type,
    hydration_crypto_block,
    ingest_crypto_file,
    ingest_crypto_paths,
    legacy_btc_price_alias,
    merge_crypto_payload,
    normalize_correlation_header,
    normalize_koyfin_header,
    parse_snapshot_rows,
)
from whinfell_pipeline.csv_download import infer_staged_destination, stage_file, cmd_init
from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.staged_csv import SOURCE_CRYPTO, StagedFile, validate_staged_file

WHINPUMP = REPO_ROOT / "staged_raw/quarantine/20260628/koyfin_WhinPump20260626_2026.06.28_10.47.58.001.csv"
WIDE_TS = REPO_ROOT / "staged_raw/quarantine/20260628/koyfin_2026-06-28.csv"


class TestCryptoHeaderNormalization(unittest.TestCase):
    def test_snapshot_headers(self):
        self.assertEqual(normalize_koyfin_header("Last Price"), ("last_price", "Last Price"))
        self.assertEqual(normalize_koyfin_header("Total Return (1D)"), ("chg_1d", "Total Return (1D)"))
        self.assertEqual(normalize_koyfin_header("Volatility (1M)"), ("vol_1m", "Volatility (1M)"))
        self.assertEqual(normalize_koyfin_header("Total Return (1M)"), ("tr_1m", "Total Return (1M)"))

    def test_correlation_headers(self):
        self.assertEqual(normalize_correlation_header("HYG SPY Corr"), "corr_hyg_spy")
        self.assertEqual(normalize_correlation_header("HYG / SPY Corr"), "corr_hyg_spy")
        self.assertEqual(normalize_correlation_header("XLRE SPY Corr"), "corr_xlre_spy")


class TestCryptoRouting(unittest.TestCase):
    def test_infer_crypto_datasets(self):
        self.assertEqual(infer_staged_destination("btc_price_chart_20260628_1038.csv"), (SOURCE_CRYPTO, "btc_price_chart"))
        self.assertEqual(infer_staged_destination("eth_correl_chart_20260628_1038.csv"), (SOURCE_CRYPTO, "eth_correl_chart"))
        self.assertEqual(infer_staged_destination("crypto_corr_series_20260628_1038.csv"), (SOURCE_CRYPTO, "crypto_corr_series"))
        self.assertEqual(infer_staged_destination("crypto_corr_series_20260628.csv"), (SOURCE_CRYPTO, "crypto_corr_series"))

    @unittest.skipUnless(WHINPUMP.exists(), "WhinPump fixture missing")
    def test_whinpump_snapshot_detection(self):
        import csv
        import io

        text = WHINPUMP.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(text))
        headers = list(reader.fieldnames or [])
        rows = list(reader)
        self.assertEqual(detect_crypto_source_type(headers, WHINPUMP.name, rows=rows), "snapshot")

    @unittest.skipUnless(WIDE_TS.exists(), "wide timeseries fixture missing")
    def test_wide_timeseries_backup_detection(self):
        text = WIDE_TS.read_text(encoding="utf-8")
        headers = text.splitlines()[0].replace('"', "").split(",")
        self.assertEqual(detect_crypto_source_type(headers, WIDE_TS.name), "wide_timeseries_backup")


class TestCryptoParsing(unittest.TestCase):
    @unittest.skipUnless(WHINPUMP.exists(), "WhinPump fixture missing")
    def test_parse_whinpump_assets(self):
        import csv
        import io

        text = WHINPUMP.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(text))
        headers = list(reader.fieldnames or [])
        rows = list(reader)
        parsed = parse_snapshot_rows(headers, rows, source_file=WHINPUMP.name)
        assets = parsed["assets"]
        self.assertIn("btc_spot_usd", assets)
        self.assertIn("eth_spot_usd", assets)
        self.assertIn("xrp_spot_usd", assets)
        self.assertIn("sol_spot_usd", assets)
        self.assertEqual(assets["btc_spot_usd"]["ticker"], "BTCUSD")
        self.assertIsNotNone(assets["btc_spot_usd"].get("last_price"))
        self.assertIn("_raw", assets["btc_spot_usd"])

    def test_parse_correlation_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crypto_corr_series_20260628_1200.csv"
            path.write_text(
                "Date,HYG SPY Corr,JAAA SPY Corr,BKLN SPY Corr,CWB SPY Corr,XLRE SPY Corr\n"
                "06-27-2026,0.78,0.55,0.42,0.61,0.33\n"
                "06-28-2026,0.80,0.57,0.44,0.63,0.35\n",
                encoding="utf-8",
            )
            patch, res = ingest_crypto_file(path, dataset="crypto_corr_series")
            self.assertTrue(res.ok, res.errors)
            self.assertEqual(res.source_type, "correlation_series")
            self.assertIn("corr_hyg_spy", patch["latest"])
            self.assertEqual(patch["latest"]["corr_hyg_spy"], 0.80)

    def test_parse_btc_price_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "btc_price_chart_20260628_1200.csv"
            path.write_text(
                "Date,BTCUSD Close\n"
                "06-27-2026,95000\n"
                "06-28-2026,96000\n",
                encoding="utf-8",
            )
            patch, res = ingest_crypto_file(path, dataset="btc_price_chart")
            self.assertTrue(res.ok, res.errors)
            self.assertEqual(patch["chart_key"], "btc_price_chart")
            self.assertEqual(patch["latest"]["close"], 96000.0)

    def test_legacy_btc_price_alias(self):
        payload = {
            "charts": {"btc_price_chart": {"latest": {"close": 59828.98}}},
            "assets": {"btc_spot_usd": {"last_price": 59828.98}},
        }
        self.assertEqual(legacy_btc_price_alias(payload), 59828.98)


class TestCryptoPipeline(unittest.TestCase):
    def test_stage_crypto_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "drop"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            src = downloads / "btc_correl_chart_20260628_1200.csv"
            src.write_text(
                "Date,BTCUSD / SPY Corr\n"
                "06-28-2026,0.54\n",
                encoding="utf-8",
            )
            cmd_init(staged_root)
            fr = stage_file(src, staged_root, operator="test")
            self.assertEqual(fr.status, "staged", fr.errors)
            staged = StagedFile(
                path=Path(fr.staged_path),
                source=SOURCE_CRYPTO,
                dataset="btc_correl_chart",
                filename=src.name,
            )
            self.assertTrue(validate_staged_file(staged).ok)

    def test_sidecar_merge_and_hydration(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "latest_crypto_sleeve.json"
            snap = Path(tmp) / "crypto_snapshot_20260628_1200.csv"
            snap.write_text(
                "Ticker,Name,Last Price,Total Return (1D),Volatility (1M)\n"
                "BTCUSD,Bitcoin - United States Dollar,59828.98,-0.0062,32.58\n"
                "ETHUSD,Ethereum - United States Dollar,1579.50,-0.0012,51.54\n"
                "XRPUSD,Ripple - United States Dollar,1.0507,-0.0027,50.89\n"
                "SOLUSD,Solana - United States Dollar,71.6500,0.0065,63.14\n",
                encoding="utf-8",
            )
            payload = ingest_crypto_paths([snap], sidecar_path=sidecar)
            self.assertIn("btc_spot_usd", payload["assets"])
            block = hydration_crypto_block(payload)
            self.assertEqual(block["legacy_BTCPRice"], 59828.98)
            self.assertEqual(len(block["assets"]), 4)

            bundle = build_hydration_bundle(crypto_path=sidecar)
            self.assertIn("crypto_sleeve", bundle)
            self.assertIn("btc_spot_usd", bundle["crypto_sleeve"]["assets"])

    def test_merge_prefers_primary_chart_over_backup(self):
        base = {
            "charts": {
                "btc_price_chart": {
                    "chart_key": "btc_price_chart",
                    "row_count": 10,
                    "priority": "backup",
                    "latest": {"close": 90000},
                }
            }
        }
        incoming = {
            "source_type": "chart_timeseries",
            "chart_key": "btc_price_chart",
            "row_count": 100,
            "latest": {"close": 96000},
        }
        merged = merge_crypto_payload(base, incoming)
        self.assertEqual(merged["charts"]["btc_price_chart"]["latest"]["close"], 96000)


if __name__ == "__main__":
    unittest.main()