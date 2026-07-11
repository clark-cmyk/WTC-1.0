"""WTM data dictionary loader tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.data_dictionary import (
    barchart_all_approved_symbols,
    barchart_core_symbols,
    barchart_curve_symbols,
    barchart_instrument_class_map,
    barchart_spread_symbols,
    canonical_asset_for_ticker,
    canonical_dataset_names,
    canonical_filename_patterns,
    canonical_saved_view_names,
    barchart_term_structure_universe,
    china_policy_industrial_proxy,
    china_policy_tickers,
    funds_flow_basket_for_node,
    funds_flow_column_map,
    funds_flow_node_ids,
    funds_flow_sidecar_path,
    funds_flow_thresholds,
    get_canonical_filename_patterns,
    get_column_mappings,
    get_funds_flow_baskets,
    get_funds_flow_ingest,
    get_json_field_map,
    get_node_score_weights,
    get_project_structure,
    get_rv_series_registry,
    get_ticker_standards,
    get_watchlist_names,
    koyfin_china_policy_universe,
    koyfin_provides_term_structure,
    node_score_components,
    term_structure_active_screens,
    term_structure_ladder_shortcuts,
    normalize_glob_rules,
    legacy_alias,
    load_data_dictionary,
    master_dictionary_info,
    rv_series_catalog,
    rv_series_for_node,
    rv_series_primary,
    raw_patterns_for_dataset,
    snapshot_field_map,
    source_system_ids,
)


class TestDataDictionary(unittest.TestCase):
    def test_loads_version(self):
        dd = load_data_dictionary()
        self.assertEqual(dd["version"], "1.0")
        info = master_dictionary_info(dd)
        self.assertEqual(info["version"], "1.0")
        self.assertEqual(info["status"], "Locked")
        self.assertEqual(info["date"], "2026-06-29")

    def test_master_sections_present(self):
        dd = load_data_dictionary()
        for key in (
            "project_structure",
            "watchlist_names",
            "file_naming_conventions",
            "json_structures",
            "column_mappings",
            "ticker_standards",
            "rv_series",
            "node_score_weights",
            "funds_flow_baskets",
            "funds_flow_thresholds",
            "funds_flow_column_patterns",
            "funds_flow_ingest",
        ):
            self.assertIn(key, dd, key)
        self.assertEqual(
            get_project_structure()["repo_root"],
            "~/Desktop/Whinfell_Transmission_Control",
        )
        views = canonical_saved_view_names()
        self.assertIn("WTM-Credit-Confirmation", views)
        self.assertIn("WTM-Rates-Credit", views)
        patterns = get_canonical_filename_patterns()
        self.assertIn("credit_vendor_snapshot", patterns["vendor_to_canonical"])
        rules = normalize_glob_rules()
        self.assertTrue(any(r.get("dataset") == "credit" for r in rules))
        jfm = get_json_field_map()
        self.assertIn("whinfell_score", jfm["hydration_bundle"]["blocks"]["global"])
        cm = get_column_mappings()
        self.assertEqual(cm["display_to_field"]["Whinfell Score"], "whinfell_score")
        ts = get_ticker_standards()
        self.assertEqual(ts["koyfin"]["format"], "uppercase_plain")
        wl = get_watchlist_names()
        self.assertEqual(wl["koyfin_saved_views"]["WTM-Credit-Confirmation"]["dataset"], "credit")

    def test_source_systems_present(self):
        ids = source_system_ids()
        self.assertIn("koyfin_snapshot_csv", ids)
        self.assertIn("barchart_core_history", ids)

    def test_ticker_resolution(self):
        self.assertEqual(canonical_asset_for_ticker("koyfin", "BTCUSD"), "btc_spot_usd")
        self.assertEqual(canonical_asset_for_ticker("barchart", "^BTCUSD"), "btc_spot_usd")

    def test_barchart_core_count(self):
        symbols = barchart_core_symbols()
        self.assertIn("^BTCUSD", symbols)
        self.assertEqual(len(symbols), 16)

    def test_barchart_all_approved_count(self):
        self.assertEqual(len(barchart_all_approved_symbols()), 78)
        self.assertEqual(len(barchart_spread_symbols()), 5)
        self.assertEqual(len(barchart_curve_symbols()), 57)

    def test_barchart_core_symbols_match_objective(self):
        expected = {
            "^BTCUSD", "^ETHUSD", "^XRPUSD", "^SOLUSD", "IBIT", "GBTC", "SOFR",
            "$HSI", "$VHSI", "$VXHY", "CBON", "KHYB", "ASHR", "DXY00", "GCY00", "HGY00",
        }
        self.assertEqual(set(barchart_core_symbols()), expected)

    def test_barchart_instrument_class_map(self):
        ic = barchart_instrument_class_map()
        self.assertEqual(ic["^BTCUSD"], "crypto_spot")
        self.assertEqual(ic["IBIT"], "etf")
        self.assertEqual(ic["GCY00"], "continuous")

    def test_legacy_alias(self):
        self.assertEqual(legacy_alias("BTCPRice"), "btc_spot_usd")

    def test_snapshot_field_map(self):
        fm = snapshot_field_map()
        self.assertEqual(fm["Last Price"], "last_price")
        self.assertEqual(fm["Volatility 1M"], "vol_1m")

    def test_rv_series_registry_locked(self):
        reg = get_rv_series_registry()
        self.assertEqual(reg["version"], "1.0")
        self.assertEqual(reg["status"], "Locked")
        catalog = rv_series_catalog()
        self.assertIn("btc_calendar_bt_near_deferred", catalog)
        self.assertEqual(catalog["hy_oas_proxy"]["quartile_direction"], "higher_is_cheaper")
        self.assertEqual(catalog["btc_calendar_bt_near_deferred"]["quartile_direction"], "higher_is_richer")
        self.assertEqual(rv_series_primary("basis"), "btc_calendar_bt_near_deferred")
        basis_rows = rv_series_for_node("basis")
        self.assertGreaterEqual(len(basis_rows), 1)
        horizons = reg["lookback_trading_days"]
        self.assertEqual(horizons["3m"], 63)

    def test_node_score_weights_interim(self):
        nsw = get_node_score_weights()
        self.assertEqual(nsw["status"], "Locked")
        liq = node_score_components("liquidity")
        self.assertEqual(len(liq), 5)
        self.assertEqual(sum(c["weight_pct"] for c in liq), 100)
        for node_id in ("breadth", "highbeta", "basis"):
            comps = node_score_components(node_id)
            self.assertEqual(len(comps), 5)
            self.assertEqual(sum(c["weight_pct"] for c in comps), 100)
        self.assertEqual(nsw["design"]["fallback_min_components"], 2)

    def test_funds_flow_baskets_locked(self):
        baskets = get_funds_flow_baskets()
        self.assertEqual(baskets["version"], "1.0")
        self.assertEqual(baskets["status"], "Locked")
        self.assertEqual(baskets["normalization"], "flow_pct_aum")
        node_ids = funds_flow_node_ids()
        self.assertEqual(len(node_ids), 5)
        self.assertEqual(
            set(node_ids),
            {"liquidity", "credit", "breadth", "highbeta", "basis"},
        )
        credit = funds_flow_basket_for_node("credit")
        self.assertIsNotNone(credit)
        assert credit is not None
        self.assertEqual(credit["basket_id"], "credit_hy_ig")
        self.assertEqual(credit["primary_ticker"], "HYG")
        self.assertEqual(len(credit["etfs"]), 4)
        primary = [e for e in credit["etfs"] if e.get("primary")]
        self.assertEqual(len(primary), 1)
        self.assertEqual(primary[0]["ticker"], "HYG")
        thresholds = funds_flow_thresholds()
        self.assertEqual(thresholds["supportive_5d_pct"], 0.15)
        self.assertEqual(thresholds["divergence_5d_pct"], -0.05)
        colmap = funds_flow_column_map()
        self.assertIn("{TICKER} Flow (D)", colmap["flow_usd_1d"])
        self.assertIn("Date", colmap["date"])
        ingest = get_funds_flow_ingest()
        self.assertEqual(ingest["units"]["flow_usd"], "millions_usd")
        self.assertIn("ok", ingest["flows_meta"]["flows_status"])
        self.assertEqual(funds_flow_sidecar_path(), "data/flows/v1/latest_flows.json")
        self.assertEqual(canonical_asset_for_ticker("koyfin", "SHY"), "shy")
        self.assertEqual(canonical_asset_for_ticker("koyfin", "IWM"), "iwm")
        self.assertEqual(canonical_asset_for_ticker("koyfin", "BITO"), "bito")

    def test_btc_basis_barchart_not_koyfin(self):
        wl = get_watchlist_names()
        self.assertNotIn("WTM-BTC-Basis", wl.get("koyfin_saved_views") or {})
        basis = (wl.get("barchart_screens") or {}).get("WTM-BTC-Basis") or {}
        self.assertEqual(basis.get("dataset"), "btc_basis")
        self.assertEqual(basis.get("front_contract"), "BTM26")
        self.assertEqual(basis.get("source"), "barchart")
        self.assertIn("basis_level", basis.get("metrics") or [])
        self.assertIn("calendar_spreads", basis.get("metrics") or [])
        patterns = raw_patterns_for_dataset("btc_basis")
        self.assertIn("futures-spreads-btm*", patterns)

    def test_term_structure_barchart_not_koyfin(self):
        self.assertFalse(koyfin_provides_term_structure())
        ts = barchart_term_structure_universe()
        self.assertEqual(ts.get("vendor"), "barchart")
        self.assertEqual(ts.get("status"), "active")
        screens = term_structure_active_screens()
        self.assertIn("WTM-BTC-Basis", screens)
        self.assertIn("WTM-China-Cyclical", screens)
        shortcuts = term_structure_ladder_shortcuts()
        self.assertIn("BT1", shortcuts)
        self.assertIn("ZN1", shortcuts)
        self.assertEqual(len(shortcuts), 13)

        wl = get_watchlist_names()
        self.assertNotIn("WTM-Import-Curves", wl.get("koyfin_watchlists") or {})
        universes = (load_data_dictionary().get("universes") or {})
        self.assertNotIn("WTM-Import-Curves", universes.get("koyfin_watchlists") or {})
        cancelled = (ts.get("cancelled_koyfin_watchlist") or {}).get("name")
        self.assertEqual(cancelled, "WTM-Import-Curves")

        curve_only = (load_data_dictionary().get("classification") or {}).get("curve_only") or []
        self.assertTrue(any("barchart_term_structure" in str(row) for row in curve_only))
        self.assertFalse(any("koyfin" in str(row).lower() for row in curve_only))

    def test_china_policy_validation(self):
        expected_tickers = ["KWEB", "000300.SS", "HSTECH", "ASHR", "KHYB", "CBON"]
        expected_koyfin_tickers = ["KWEB", "SHSZ300", "551550", "ASHR", "KHYB", "CBON"]
        expected_koyfin_map = {"000300.SS": "SHSZ300", "HSTECH": "551550"}
        china = koyfin_china_policy_universe()
        self.assertEqual(china.get("status"), "locked")
        self.assertEqual(china.get("saved_view"), "WTM-China-Policy")
        self.assertEqual(china_policy_tickers(), expected_tickers)
        self.assertEqual(china.get("koyfin_tickers"), expected_koyfin_tickers)
        self.assertEqual(china.get("koyfin_ticker_map"), expected_koyfin_map)
        self.assertEqual(canonical_asset_for_ticker("koyfin", "SHSZ300"), "csi300_index")
        self.assertEqual(canonical_asset_for_ticker("koyfin", "551550"), "hstech_index")
        proxy = china_policy_industrial_proxy()
        self.assertEqual(proxy.get("symbol"), "HG1")
        self.assertEqual(proxy.get("source"), "barchart")
        self.assertEqual(proxy.get("barchart_screen"), "WTM-China-Cyclical")

        wl = get_watchlist_names()
        policy = (wl.get("koyfin_saved_views") or {}).get("WTM-China-Policy") or {}
        self.assertEqual(policy.get("status"), "locked")
        self.assertEqual(policy.get("tickers"), expected_tickers)
        self.assertEqual(policy.get("koyfin_tickers"), expected_koyfin_tickers)
        self.assertEqual(policy.get("koyfin_ticker_map"), expected_koyfin_map)
        self.assertEqual((policy.get("industrial_proxy") or {}).get("symbol"), "HG1")

        cyclical = (wl.get("barchart_screens") or {}).get("WTM-China-Cyclical") or {}
        self.assertEqual(cyclical.get("primary_symbol"), "HG1")
        self.assertEqual(cyclical.get("symbols"), ["HG1"])
        self.assertEqual(cyclical.get("status"), "locked")
        for sym in cyclical.get("symbols") or []:
            self.assertNotIn("SCO1", str(sym))

        manifest_path = REPO_ROOT / "whinfell_pipeline" / "collection_manifest.yaml"
        desk_path = REPO_ROOT / "whinfell_pipeline" / "desk_urls.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        desk = yaml.safe_load(desk_path.read_text(encoding="utf-8")) or {}
        china_export = next(
            e for e in manifest.get("batch_exports", []) if e.get("id") == "koyfin_china"
        )
        self.assertEqual(china_export.get("tickers"), expected_tickers)
        self.assertEqual(china_export.get("koyfin_tickers"), expected_koyfin_tickers)
        self.assertEqual(china_export.get("koyfin_ticker_map"), expected_koyfin_map)
        self.assertEqual((china_export.get("industrial_proxy") or {}).get("symbol"), "HG1")

        policy_desk = (desk.get("koyfin") or {}).get("WTM-China-Policy") or {}
        self.assertEqual(policy_desk.get("tickers"), expected_tickers)
        self.assertEqual(policy_desk.get("koyfin_tickers"), expected_koyfin_tickers)
        self.assertEqual(policy_desk.get("koyfin_ticker_map"), expected_koyfin_map)

        barchart_cyc = (desk.get("barchart") or {}).get("WTM-China-Cyclical") or {}
        symbols = [str(s) for s in (barchart_cyc.get("symbols") or [])]
        self.assertTrue(symbols)
        for sym in symbols:
            self.assertNotRegex(sym.upper(), r"SCO")

    def test_flows_filename_pattern(self):
        datasets = canonical_dataset_names()
        self.assertIn("flows", datasets)
        patterns = get_canonical_filename_patterns()
        self.assertEqual(
            patterns["vendor_to_canonical"]["flows_vendor_timeseries"],
            "flows_{YYYYMMDD}_{HHMM}.csv",
        )
        rules = normalize_glob_rules()
        flows_rules = [r for r in rules if r.get("dataset") == "flows"]
        self.assertEqual(len(flows_rules), 1)
        self.assertEqual(flows_rules[0]["detect_glob"], "*WTM-Flows*.csv")
        self.assertEqual(
            flows_rules[0]["canonical_template"],
            "flows_{YYYYMMDD}_{HHMM}.csv",
        )
        wl = get_watchlist_names()
        self.assertIn("WTM-Flows", wl["koyfin_saved_views"])
        flows_view = wl["koyfin_saved_views"]["WTM-Flows"]
        self.assertEqual(flows_view["dataset"], "flows")
        self.assertTrue(flows_view.get("optional"))
        self.assertIn("flows_*", canonical_filename_patterns())
        jfm = get_json_field_map()
        self.assertEqual(jfm["hydration_bundle"]["expected_version"], "1.2.0")
        self.assertIn("flows_sidecar", jfm["hydration_bundle"]["blocks"])
        self.assertEqual(jfm["flows_sidecar"]["path"], "data/flows/v1/latest_flows.json")
        ps = get_project_structure()
        self.assertIn("data/hydration", ps["directories"])
        self.assertIn("whinfell_pipeline/auto_download", ps["directories"])
        self.assertIn("data/flows/v1", ps.get("pipeline_directories") or {})

    def test_project_structure_matches_tc_repo(self):
        ps = get_project_structure()
        self.assertEqual(ps.get("transmission_control"), "index.html")
        self.assertEqual(ps.get("hydration_path"), "data/hydration/latest.json")
        self.assertEqual(ps.get("pipeline_repo_root"), "~/Desktop/Whinfell_BUILD_Cousins_v2_OLD_2238_ARCHIVE")
        dirs = ps.get("directories") or {}
        for required in (
            "01_Strategy_Docs",
            "08_Deliverables",
            "css",
            "js",
            "documentation",
            "docs",
            "scripts",
            "tests",
            "whinfell_pipeline",
        ):
            self.assertIn(required, dirs, required)
        for absent in (
            "04_Score_Calculation",
            "05_Fallback_Tools",
            "06_Testing_Logs",
            "07_Reference_Materials",
            "data/global/v1",
        ):
            self.assertNotIn(absent, dirs, absent)
        tc_root = REPO_ROOT
        if tc_root.name == "Whinfell_BUILD_Cousins_v2_OLD_2238_ARCHIVE":
            tc_root = Path.home() / "Desktop" / "Whinfell_Transmission_Control"
        for rel in ("css", "js", "index.html", "whinfell_pipeline/data_dictionary.yaml"):
            self.assertTrue((tc_root / rel).is_file() or (tc_root / rel).is_dir(), rel)


if __name__ == "__main__":
    unittest.main()