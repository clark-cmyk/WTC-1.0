"""Transmission Control Master Data Dictionary badge — source + headless render."""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

TC_HTML = REPO_ROOT / "08_Deliverables" / "Whinfell_Transmission_Control.html"


class TestMasterDictionaryTransmissionControl(unittest.TestCase):
    def test_html_contains_dd_badge_element(self):
        text = TC_HTML.read_text(encoding="utf-8")
        self.assertIn('id="ddVersionBadge"', text)
        self.assertIn("DD_BADGE_SYNC_START", text)
        self.assertIn("DICTIONARY_BADGE_DEFAULT", text)
        self.assertNotIn("MASTER_DATA_DICTIONARY_FALLBACK", text)

    def test_html_defines_render_function(self):
        text = TC_HTML.read_text(encoding="utf-8")
        self.assertIn("function renderDataDictionaryBadge(", text)
        self.assertIn("data_dictionary_meta.json", text)
        self.assertIn("fetchDataDictionaryMeta", text)
        self.assertIn("validateDataDictionaryMeta", text)
        self.assertNotIn("MASTER_DATA_DICTIONARY_FALLBACK", text)
        self.assertIn("getDictionaryBadgeDefault", text)

    def test_render_all_calls_dd_badge(self):
        text = TC_HTML.read_text(encoding="utf-8")
        idx = text.find("function renderAll()")
        self.assertGreater(idx, -1)
        snippet = text[idx : idx + 200]
        self.assertIn("renderDataDictionaryBadge", snippet)

    def test_headless_badge_load_and_refresh(self):
        script = REPO_ROOT / "whinfell_pipeline/tests/dd_badge_headless.mjs"
        proc = subprocess.run(
            ["node", str(script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("Master Data Dictionary v1.0", proc.stdout)
        self.assertIn("Locked", proc.stdout)

    def test_disk_backed_badge_file_evidence(self):
        """meta.json read from disk (file:// sibling path); sync block from yaml chain."""
        script = REPO_ROOT / "whinfell_pipeline/tests/dd_badge_file_evidence.mjs"
        proc = subprocess.run(
            ["node", str(script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("PASS dd_badge_file_evidence", proc.stdout)
        self.assertIn("validateDataDictionaryMeta: true", proc.stdout)


if __name__ == "__main__":
    unittest.main()