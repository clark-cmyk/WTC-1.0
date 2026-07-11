"""Tests for desk chart link generation from desk_urls.yaml."""

import json
import unittest
from pathlib import Path

from whinfell_pipeline.desk_chart_links import build_chart_links, write_chart_links
from whinfell_pipeline.batch_collect import load_desk_urls


class TestDeskChartLinks(unittest.TestCase):
    def test_all_five_stages_present(self):
        payload = build_chart_links()
        links = payload["chartLinks"]
        self.assertEqual(len(links), 5)
        for stage_id, stage in links.items():
            self.assertTrue(stage["primary"]["url"])
            self.assertTrue(stage["secondary"]["url"])
            self.assertTrue(stage["note"])
            self.assertEqual(stage["primary"]["label"], "View Chart")

    def test_koyfin_primary_uses_share_placeholder_until_wired(self):
        payload = build_chart_links()
        liquidity = payload["chartLinks"]["liquidity"]
        self.assertEqual(liquidity["primary"]["url"], "REPLACE_WTM_RATES_CREDIT_SHARE_URL")
        self.assertEqual(liquidity["secondary"]["label"], "Assist")
        self.assertIn("USGG2Y10Y", liquidity["secondary"]["url"])

    def test_basis_prefers_barchart_spreads(self):
        payload = build_chart_links()
        basis = payload["chartLinks"]["basis"]
        self.assertEqual(basis["primary"]["source"], "Barchart")
        self.assertIn("spreads", basis["primary"]["url"])
        self.assertEqual(basis["secondary"]["source"], "Barchart")
        self.assertIn("historical-download", basis["secondary"]["url"])

    def test_highbeta_secondary_is_barchart_intraday(self):
        payload = build_chart_links()
        highbeta = payload["chartLinks"]["highbeta"]
        self.assertEqual(highbeta["primary"]["source"], "Koyfin")
        self.assertEqual(highbeta["secondary"]["label"], "Futures")
        self.assertEqual(highbeta["secondary"]["source"], "Barchart")
        self.assertIn("barchart.com", highbeta["secondary"]["url"])

    def test_write_outputs_json_and_js(self):
        repo = Path(__file__).resolve().parents[2]
        json_path = repo / "08_Deliverables" / "desk_chart_links.json"
        js_path = repo / "08_Deliverables" / "desk_chart_links.js"
        write_chart_links(json_path=json_path, js_path=js_path)
        self.assertTrue(json_path.exists())
        self.assertTrue(js_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("chartLinks", data)
        self.assertIn("const chartLinks =", js_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()