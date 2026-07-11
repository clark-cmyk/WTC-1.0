"""Sync pipeline: master_dictionary_info → meta.json + TC DD_BADGE_SYNC injection."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.data_dictionary import badge_default_payload, master_dictionary_info
from whinfell_pipeline.sync_dictionary_meta import (
    DD_BADGE_SYNC_END,
    DD_BADGE_SYNC_START,
    META_JSON,
    TC_HTML,
    inject_tc_badge_sync,
    sync_all,
)

TC_HTML_REL = Path("08_Deliverables/Whinfell_Transmission_Control.html")


class TestSyncDictionaryMeta(unittest.TestCase):
    def test_sync_writes_meta_matching_dictionary(self):
        sync_all()
        info = master_dictionary_info()
        meta = json.loads(META_JSON.read_text(encoding="utf-8"))
        self.assertEqual(meta["version"], info["version"])
        self.assertEqual(meta["status"], info["status"])
        self.assertEqual(meta["source"], "whinfell_pipeline/data_dictionary.yaml")

    def test_sync_injects_badge_default_into_html(self):
        inject_tc_badge_sync()
        text = TC_HTML.read_text(encoding="utf-8")
        self.assertIn(DD_BADGE_SYNC_START, text)
        self.assertIn(DD_BADGE_SYNC_END, text)
        self.assertIn("window.DICTIONARY_BADGE_DEFAULT", text)
        expected = badge_default_payload()
        m = re.search(r"window\.DICTIONARY_BADGE_DEFAULT\s*=\s*(\{[\s\S]*?\});", text)
        self.assertIsNotNone(m, "DICTIONARY_BADGE_DEFAULT block missing")
        injected = json.loads(m.group(1))
        self.assertEqual(injected["version"], expected["version"])
        self.assertEqual(injected["status"], expected["status"])
        self.assertEqual(injected["source"], expected["source"])


if __name__ == "__main__":
    unittest.main()